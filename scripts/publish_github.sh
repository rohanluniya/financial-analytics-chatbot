#!/usr/bin/env bash
# Create the private GitHub repository and push this project (same pattern as the other repos).
#   GITHUB_TOKEN=ghp_xxx ./scripts/publish_github.sh
set -euo pipefail

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "Usage: GITHUB_TOKEN=ghp_xxx ./scripts/publish_github.sh"
  exit 1
fi

GH_USER="${GH_USER:-ankdeshm}"
REPO="${REPO:-iris}"
DESC="IRIS (Intelligent Reporting & Insight System): conversational finance and workforce analytics over a general-ledger management P&L (SQL Server 2022, semantic layer, LangGraph agent, Streamlit) for a fictional TIC company - synthetic data"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Creating private GitHub repo ${GH_USER}/${REPO} ==="
curl -sS -X POST "https://api.github.com/user/repos" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -d "{\"name\":\"${REPO}\",\"description\":\"${DESC}\",\"private\":true}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Repo API status:', d.get('html_url') or d.get('message'))"

echo "=== Pushing to https://github.com/${GH_USER}/${REPO}.git ==="
git -C "${ROOT}" push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GH_USER}/${REPO}.git" main \
  || { echo "Push failed (if the repo already has commits, review and push manually)."; exit 1; }
# Record the remote without the token (never write the token into .git/config)
git -C "${ROOT}" remote get-url origin >/dev/null 2>&1 \
  || git -C "${ROOT}" remote add origin "https://github.com/${GH_USER}/${REPO}.git"
echo "Done: https://github.com/${GH_USER}/${REPO}"
