# IRIS - application image (Streamlit UI + LangGraph agent + semantic layer + landing engine).
#
#   docker build -t iris .
#   docker run -p 8501:8501 --env-file .env iris
#
# Talks to SQL Server through Microsoft ODBC Driver 18 (DB_BACKEND=mssql) or reads a DuckDB file
# (DB_BACKEND=duckdb, for example on a laptop). The LLM is any LiteLLM model string (LLM_MODEL).
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8501

# Microsoft ODBC Driver 18 for SQL Server (Debian 12 package repository)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg2 ca-certificates unixodbc \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list -o /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
 && apt-get purge -y gnupg2 && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.9.*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY config ./config
COPY sql ./sql
COPY scripts ./scripts
COPY Makefile .env.example ./
# Read by the UI at runtime: theme / hidden Deploy button, and the User Guide page with its screenshots
COPY .streamlit ./.streamlit
COPY docs/user_guide.md ./docs/user_guide.md
COPY docs/img ./docs/img
# Optional: a pre-built DuckDB file for the duckdb backend (created by `make data duckdb`)
COPY data ./data

RUN useradd -m -u 1000 app && chown -R app:app /app
USER app
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fs "http://localhost:${PORT}/_stcore/health" || exit 1
CMD ["sh", "-c", "streamlit run app/ui/streamlit_app.py --server.port ${PORT} --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false"]
