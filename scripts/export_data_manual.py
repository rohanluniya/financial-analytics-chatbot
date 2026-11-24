#!/usr/bin/env python
"""Write docs/data_manual.md: the Data Catalog content (coverage, organisation, P&L lines, metrics, ratios,
versions and periods, landing method and measured accuracy, data and sources) as one Markdown document.

Read live from the database and app/semantic/metrics.yaml, like the Data Catalog page, for the full group
scope by default:

    make data-manual            # or: python scripts/export_data_manual.py --user group_cfo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.semantic.catalog import data_manual_markdown  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", default="group_cfo", help="persona whose data access is used (default: group_cfo)")
    ap.add_argument("--out", default=str(ROOT / "docs" / "data_manual.md"))
    args = ap.parse_args()
    text = data_manual_markdown(args.user)
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"wrote {args.out} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
