"""Repository rules: branding constants only in app/ui/branding.py, no tunnels or public exposure (Services
are ClusterIP; no LoadBalancer, NodePort or Ingress), secrets never committed, Deploy button hidden."""
from __future__ import annotations

import ast
import re
import subprocess

import pytest

from app.config import ROOT
from app.ui import branding as B

BRAND_STRINGS = [re.compile(r"\bIRIS\b"), re.compile(re.escape(B.APP_FULL_NAME)), re.compile(re.escape(B.TAGLINE)),
                 re.compile(re.escape(B.AUTHOR)), re.compile("Developed and maintained by")]
TUNNEL_RX = re.compile(r"\b(cloudflared|ngrok|localtunnel|lt --port|trycloudflare|serveo|localhost\.run|bore\.pub)\b",
                       re.I)


def _code_strings(path) -> list[tuple[int, str]]:
    """String constants of a Python file, without docstrings."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docs.add(id(body[0].value))
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def test_branding_strings_only_in_branding_py():
    hits = []
    for p in sorted((ROOT / "app").rglob("*.py")):
        if p.name == "branding.py":
            continue
        for line, s in _code_strings(p):
            if any(rx.search(s) for rx in BRAND_STRINGS):
                hits.append(f"{p.relative_to(ROOT)}:{line}: {s[:60]!r}")
    assert hits == [], hits


def test_branding_constants():
    assert (B.APP_NAME, B.APP_FULL_NAME, B.TAGLINE) == ("IRIS", "Intelligent Reporting & Insight System",
                                                       "See your business clearly.")
    assert B.AUTHOR_LINE == f"Developed and maintained by {B.AUTHOR}" and B.LOGO_PATH.exists()
    assert B.footer_line() == f"IRIS v{B.VERSION} · Developed and maintained by {B.AUTHOR}"


def _repo_files() -> tuple[list, bool]:
    """(files that would be committed, True if git listed them; else the working tree minus local-only files)."""
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.splitlines()
        return [ROOT / f for f in out if (ROOT / f).is_file()], True
    except Exception:  # noqa: BLE001 - a synced copy without .git: scan the working tree
        skip = {".git", ".venv", "data", "results", "scratch", "__pycache__", ".pytest_cache"}
        local = {".env", ".deploy.env", ".app-ready"}
        return [p for p in ROOT.rglob("*") if p.is_file() and p.name not in local
                and not (set(p.relative_to(ROOT).parts) & skip)], False


def _tracked_files() -> list:
    return _repo_files()[0]


def test_no_tunnel_tools_or_scripts():
    me = __file__.rsplit("/", 1)[-1]
    hits = []
    for p in _tracked_files():
        if p.suffix not in (".py", ".sh", ".yaml", ".yml", ".toml", ".md", ".env", "") and p.name != "Makefile":
            continue
        if p.name in (me,) or "tunnel" in p.name.lower():
            hits += [str(p.relative_to(ROOT))] if "tunnel" in p.name.lower() else []
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if TUNNEL_RX.search(text):
            hits.append(str(p.relative_to(ROOT)))
    assert hits == [], hits


def test_kubernetes_services_are_cluster_ip_only():
    import yaml

    docs = []
    for p in sorted((ROOT / "deploy").rglob("*.yaml")):
        for d in yaml.safe_load_all(re.sub(r"\$\{(\w+)\}", r"__\1__", p.read_text())):
            if d:
                docs.append((p.name, d))
    kinds = {d.get("kind") for _, d in docs}
    assert "Ingress" not in kinds
    services = [(n, d) for n, d in docs if d.get("kind") == "Service"]
    assert services
    for name, svc in services:
        assert svc["spec"].get("type", "ClusterIP") == "ClusterIP", name
        for port in svc["spec"].get("ports", []):
            assert "nodePort" not in port, name
    text = "\n".join(p.read_text() for p in (ROOT / "deploy").rglob("*.yaml"))
    assert not re.search(r"\b(LoadBalancer|NodePort|hostNetwork:\s*true|hostPort)\b", text)


def test_local_runs_bind_to_localhost():
    make = (ROOT / "Makefile").read_text()
    assert "--server.address 127.0.0.1" in make and "port-forward --address 127.0.0.1" in make
    compose = (ROOT / "docker-compose.yml").read_text()
    published = re.findall(r'ports:\s*\[([^\]]*)\]', compose)
    assert published and all(p.strip().strip('"').startswith("127.0.0.1:") for grp in published for p in grp.split(","))


def test_manifest_render_substitutes_every_placeholder():
    """`#` starts a comment in a Makefile variable, so check what make keeps of RENDER against deploy/."""
    line = next(ln for ln in (ROOT / "Makefile").read_text().splitlines() if ln.startswith("RENDER ="))
    kept = line.split("#", 1)[0]
    used = set()
    for p in (ROOT / "deploy").rglob("*"):
        if p.is_file():
            used |= set(re.findall(r"\$\{(\w+)\}", p.read_text()))
    missing = sorted(n for n in used if "{" + n + "}" not in kept)
    assert used and missing == [], missing


def test_secrets_are_not_committed():
    gi = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in gi and ".deploy.env" in gi
    files, from_git = _repo_files()
    if from_git:
        tracked = {str(p.relative_to(ROOT)) for p in files}
        assert ".env" not in tracked and ".deploy.env" not in tracked
    example = (ROOT / ".env.example").read_text()
    assert re.search(r"^APP_ACCESS_CODE=\s*$", example, re.M)


def test_deploy_button_hidden_and_usage_stats_off():
    cfg = (ROOT / ".streamlit" / "config.toml").read_text()
    assert re.search(r'toolbarMode\s*=\s*"minimal"', cfg) and re.search(r"headless\s*=\s*true", cfg)
    assert re.search(r"gatherUsageStats\s*=\s*false", cfg)
    assert re.search(r'serverAddress\s*=\s*"localhost"', cfg)  # no public-IP lookup or "External URL"


def test_app_image_carries_the_files_the_ui_reads():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "COPY .streamlit" in dockerfile and "docs/user_guide.md" in dockerfile and "docs/img" in dockerfile
    ignore = (ROOT / ".dockerignore").read_text().splitlines()
    assert "!docs/user_guide.md" in ignore and "!docs/img" in ignore


@pytest.mark.parametrize("doc", ["README.md", "docs/user_guide.md", "docs/landing_methodology.md",
                                 "docs/landing_backtest_report.md", "docs/data_manual.md", "docs/demo_script.md",
                                 "docs/architecture.md", "docs/demo_stories.md"])
def test_docs_exist_without_commit_hashes(doc):
    p = ROOT / doc
    assert p.exists(), doc
    assert not re.search(r"\b[0-9a-f]{40}\b", p.read_text()), doc
