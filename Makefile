# IRIS - task runner.
# Typical first run:   make setup db-up data load reconcile landing test run
SHELL := /bin/bash
.DEFAULT_GOAL := help

-include .env
DB_BACKEND ?= mssql
DB_UP_MODE ?= compose
PORT ?= 8501
UV ?= uv
PY := $(UV) run python

# Local-only cluster settings (gitignored) for the optional Kubernetes dev workflow
-include .deploy.env
NAMESPACE ?= iris
PREFIX ?= iris
KUBECTL ?= kubectl $(if $(KUBECONFIG_PATH),--kubeconfig $(KUBECONFIG_PATH),)
DEV_POD ?= $(PREFIX)-dev-0
WS ?= /workspace/iris

.PHONY: help setup db-up data load reconcile landing backtest data-manual test eval demo run duckdb clean \
        compose-up compose-down tunnel hf k8s-deploy k8s-cronjob k8s-secrets k8s-access-code k8s-env k8s-ready k8s-models \
        k8s-sync k8s-make k8s-forward k8s-pull

help: ## Show targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install Python deps with uv, export requirements.txt, create .env if missing
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example - edit passwords/model")
	$(UV) sync
	$(UV) export --no-hashes --no-dev --format requirements-txt -o requirements.txt >/dev/null
	@echo "setup done"

db-up: ## Start SQL Server 2022 (docker compose) or wait for an external one; create the database
ifeq ($(DB_BACKEND),mssql)
ifeq ($(DB_UP_MODE),compose)
	docker compose up -d mssql
endif
	$(PY) scripts/wait_for_db.py
else
	@echo "DB_BACKEND=$(DB_BACKEND): nothing to start"
endif

data: ## Generate the synthetic dataset (seeded) into data/
	$(PY) scripts/generate_data.py

load: ## Load data into the configured backend (SQL Server via ODBC 18, or DuckDB)
ifeq ($(DB_BACKEND),mssql)
	$(PY) scripts/load_mssql.py
else
	$(PY) scripts/export_duckdb.py
endif

duckdb: ## Build the DuckDB file from the generated data (same schema and rows)
	$(PY) scripts/export_duckdb.py

reconcile: ## Verify leaf sums = subtotals (50 random samples) + row counts per table/version
	$(PY) scripts/reconcile.py

landing: ## Compute the current-month landing (fact_landing) for the as-of date: make landing [AS_OF=2026-09-15]
	$(PY) scripts/run_landing.py $(if $(AS_OF),--as-of $(AS_OF),)

backtest: ## Backtest the landing on the last 24 closed months; writes docs/landing_backtest_report.md
	$(PY) scripts/backtest_landing.py

data-manual: ## Write docs/data_manual.md from the live catalog (same content as the Data Catalog page)
	$(PY) scripts/export_data_manual.py

test: ## Run all tests (semantic layer, guardrails, agent, landing, conversations, headless UI)
	$(UV) run pytest

eval: ## Golden-question evaluation (writes eval_report.md): make eval MODELS=rules,ollama/qwen2.5-coder:14b
	$(PY) tests/run_eval.py $(if $(MODELS),--models $(MODELS),)

demo: ## Run the demo questions and save every response to results/demo_responses/<model>/
	$(PY) scripts/run_demo_questions.py $(if $(MODEL),--model $(MODEL),)

run: ## Serve the app on http://localhost:$(PORT) (local only)
	$(UV) run streamlit run app/ui/streamlit_app.py --server.port $(PORT) --server.address 127.0.0.1

tunnel hf: ## Removed: public exposure is not allowed (use `make run` or `make k8s-forward`, localhost only)
	@echo "'make $@' was removed: IRIS runs locally/privately only. Use 'make run' (localhost) or 'make k8s-forward'."; exit 1

compose-up: ## docker compose: SQL Server + app (add --profile ollama for a local LLM)
	docker compose up -d --build

compose-down: ## Stop docker compose services
	docker compose down

clean: ## Remove generated data
	rm -rf data/*.parquet data/*.duckdb data/stories.json

# ---------------------------------------------------------------------------------------
# Kubernetes dev workflow (used for this prototype: SQL Server + Ollama + app run as pods on a
# CPU node pool; nothing runs on the laptop except kubectl). Settings come from .deploy.env.
# ---------------------------------------------------------------------------------------
RENDER = sed -e "s/\$${NAMESPACE}/$(NAMESPACE)/g" -e "s/\$${PREFIX}/$(PREFIX)/g" -e "s/\$${NODE_POOL}/$(NODE_POOL)/g" -e "s/\$${GCP_PROJECT}/$(GCP_PROJECT)/g" -e "s|\$${WS}|$(WS)|g"

k8s-deploy: ## Render deploy/k8s/*.yaml with .deploy.env, create the SQL secret once, apply (ClusterIP only)
	@$(RENDER) deploy/k8s/00-namespace.yaml | $(KUBECTL) apply -f -
	@$(MAKE) --no-print-directory k8s-secrets
	@for f in deploy/k8s/*.yaml; do $(RENDER) $$f | $(KUBECTL) apply -f - ; done

k8s-cronjob: ## Optional: private daily CronJob that refreshes the landing (no Service, no exposure)
	@$(RENDER) deploy/k8s/optional/40-landing-cronjob.yaml | $(KUBECTL) apply -f -

k8s-secrets: ## Create the Secret once: SQL Server passwords + demo sign-in code (random, never printed)
	@$(KUBECTL) -n $(NAMESPACE) get secret $(PREFIX)-secrets >/dev/null 2>&1 && echo "secret exists" || \
	  $(KUBECTL) -n $(NAMESPACE) create secret generic $(PREFIX)-secrets \
	    --from-literal=MSSQL_SA_PASSWORD="Sa1!$$(openssl rand -hex 12)" \
	    --from-literal=MSSQL_APP_PASSWORD="Rd1!$$(openssl rand -hex 12)" \
	    --from-literal=APP_ACCESS_CODE="$$(openssl rand -hex 8)"
	@$(KUBECTL) -n $(NAMESPACE) get secret $(PREFIX)-secrets -o jsonpath='{.data.APP_ACCESS_CODE}' | grep -q . || \
	  { $(KUBECTL) -n $(NAMESPACE) patch secret $(PREFIX)-secrets --type merge \
	      -p "{\"stringData\":{\"APP_ACCESS_CODE\":\"$$(openssl rand -hex 8)\"}}" >/dev/null && \
	    echo "added APP_ACCESS_CODE to the secret (restart the app container to use it)"; }

k8s-access-code: ## Print the demo sign-in code from the Secret (falls back to the dev pod's .env)
	@code="$$($(KUBECTL) -n $(NAMESPACE) get secret $(PREFIX)-secrets -o jsonpath='{.data.APP_ACCESS_CODE}' 2>/dev/null | base64 --decode)"; \
	  [ -n "$$code" ] || code="$$($(KUBECTL) -n $(NAMESPACE) exec $(DEV_POD) -c dev -- sh -c "sed -n 's/^APP_ACCESS_CODE=//p' $(WS)/.env")"; \
	  echo "$${code:-not set: run make k8s-secrets, then restart the app container}"

k8s-env: ## Write the dev pod's .env from deploy/k8s/dev.env (service names, no passwords)
	@$(RENDER) deploy/k8s/dev.env | $(KUBECTL) -n $(NAMESPACE) exec -i $(DEV_POD) -c dev -- \
	  bash -c "mkdir -p $(WS) && cat > $(WS)/.env" && echo "wrote .env in $(DEV_POD)"

k8s-ready: ## Tell the app container that the workspace is ready (it then starts Streamlit)
	$(KUBECTL) -n $(NAMESPACE) exec $(DEV_POD) -c dev -- touch $(WS)/.app-ready

OLLAMA_MODELS ?= qwen2.5-coder:14b gpt-oss:20b
k8s-models: ## Pull the local LLMs into the Ollama pod (about 22 GB for the default two)
	@for m in $(OLLAMA_MODELS); do $(KUBECTL) -n $(NAMESPACE) exec $(PREFIX)-ollama-0 -- ollama pull $$m; done

k8s-sync: ## Copy the working tree into the dev pod workspace
	@tar czf - --exclude=.venv --exclude=data --exclude=.git --exclude=__pycache__ --exclude=.env --exclude=.deploy.env --exclude=scratch . | \
	  $(KUBECTL) -n $(NAMESPACE) exec -i $(DEV_POD) -c dev -- bash -c "mkdir -p $(WS) && tar xzf - -C $(WS)"
	@echo "synced to $(DEV_POD):$(WS)"

k8s-make: ## Run a make target inside the dev pod: make k8s-make T="data load reconcile"
	$(KUBECTL) -n $(NAMESPACE) exec $(DEV_POD) -c dev -- bash -lc "cd $(WS) && make $(T)"

k8s-pull: ## Copy generated artefacts (results/, generated docs, lock files) back from the dev pod
	$(KUBECTL) -n $(NAMESPACE) exec $(DEV_POD) -c dev -- bash -c "cd $(WS) && tar czf - \$$(ls -d results eval_report.md uv.lock requirements.txt docs/landing_backtest_report.md docs/data_manual.md docs/img 2>/dev/null)" | tar xzf - -C .

k8s-forward: ## Private access to the UI on http://localhost:8501 (authenticated kubectl port-forward)
	$(KUBECTL) -n $(NAMESPACE) port-forward --address 127.0.0.1 svc/$(PREFIX)-app 8501:8501
