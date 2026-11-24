"""Finance-style tables: thousand separators, negatives in parentheses, variance colour by
favourability, bold subtotal rows, USD k / USD M units. Also CSV/Excel export (raw numbers)."""
from __future__ import annotations

import html
import io

import pandas as pd

from app.viz import format as F


def build_table(out: dict) -> dict:
    """Turn a tool output into {columns, rows, col_fmt, row_meta, caption, extra_tables}."""
    kind, data, meta = out.get("kind"), out.get("data") or [], out.get("meta") or {}
    if out.get("ok", True) and meta.get("table_spec"):
        return meta["table_spec"]
    if not out.get("ok", True) or not data and kind != "drivers":
        return {"columns": [], "rows": [], "col_fmt": {}, "row_meta": [], "caption": "", "extra_tables": []}
    t = {"columns": [], "rows": data, "col_fmt": {}, "row_meta": [], "caption": "", "extra_tables": []}
    if kind in ("pnl", "versions"):
        labels = meta.get("series", [])
        if kind == "pnl":
            var_cols = [c for lab in labels[1:] for c in (f"Var vs {lab}", f"Var % vs {lab}")]
        else:
            ref = meta.get("reference")
            var_cols = [f"{lab} vs {ref}" for lab in labels if ref and lab != ref]
        t["columns"] = ["Line"] + labels + var_cols
        t["col_fmt"] = {**{lab: "eur" for lab in labels},
                        **{c: ("pct" if "Var %" in c else "eur") for c in var_cols}}
        for r in data:
            fav = {}
            for c in var_cols:
                lab = c.replace("Var % vs ", "").replace("Var vs ", "").split(" vs ")[0]
                fav[c] = r.get(f"_fav_{lab}")
            t["row_meta"].append({"kind": r.get("_kind", "line"), "level": r.get("_level", 0),
                                  "fmt": r.get("_fmt", "eur"), "fav": fav})
        t["caption"] = "Signed values: costs negative. Variances are profit impact (positive = favourable)."
    elif kind == "trend":
        cols = meta.get("series", [])
        t["columns"] = ["Month"] + cols
        fmt = meta.get("fmt", "eur")
        fmt = "rate" if (fmt == "eur" and meta.get("kind") == "ratio") else fmt
        t["col_fmt"] = {c: fmt for c in cols}
        t["row_meta"] = [{"kind": "line", "level": 0, "fmt": None, "fav": {}} for _ in data]
    elif kind == "ratio":
        name = meta.get("name")
        cols = [c for c in data[0].keys() if not c.startswith("_")]
        t["columns"] = cols
        fmt = meta.get("fmt", "pct")
        t["col_fmt"] = {cols[2]: "num" if meta.get("num_is_stat") else "eur",
                        cols[3]: "num" if meta.get("den_is_stat") else "eur",
                        name: "rate" if fmt == "eur" else fmt,
                        "Actual vs version": "pp" if fmt == "pct" else "rate"}
        t["row_meta"] = [{"kind": "line", "level": 0, "fmt": None, "fav": {"Actual vs version": r.get("_fav")}} for r in data]
    elif kind == "drivers":
        cur, cmp_ = meta.get("current"), meta.get("comparison")
        unit = meta.get("unit", "eur")
        vfmt = "pct" if unit == "pp" else ("eur" if meta.get("fmt") == "eur" else meta.get("fmt", "eur"))
        if data:
            t["columns"] = ["Driver", cmp_, cur, "Impact", "Share of variance"]
            t["col_fmt"] = {cmp_: vfmt, cur: vfmt, "Impact": "pp" if unit == "pp" else vfmt, "Share of variance": "pct"}
            t["row_meta"] = [{"kind": "line", "level": 0, "fmt": None, "fav": {"Impact": r.get("_fav")}} for r in data]
            if unit == "pp":
                how = " (percentage points)"
            elif meta.get("favorable") == "down":
                how = f" ({F.CUR}; positive = higher cost)"
            else:
                how = f" ({F.CUR}; positive = favourable)"
            t["caption"] = "Impact = contribution to the change in " + meta.get("name", "") + how
        groups = (out.get("extra") or {}).get("groups") or []
        if groups and data:
            t["extra_tables"].append({
                "columns": ["Group", cmp_, cur, "Impact"], "rows": groups,
                "col_fmt": {cmp_: "eur", cur: "eur", "Impact": "eur"},
                "row_meta": [{"kind": "line", "level": 0, "fmt": None, "fav": {"Impact": r.get("_fav")}} for r in groups],
                "caption": "By sub-group"})
        org_rows = (out.get("extra") or {}).get("org") or []
        if org_rows:
            lvl = [k for k in org_rows[0] if k not in (cur, cmp_, "Impact", "_fav")][0]
            ofmt = meta.get("fmt", "eur")
            sub = {"columns": [lvl, cmp_, cur, "Impact"], "rows": org_rows,
                   "col_fmt": {cmp_: ofmt, cur: ofmt, "Impact": "pp" if ofmt == "pct" else ofmt},
                   "row_meta": [{"kind": "line", "level": 0, "fmt": None, "fav": {"Impact": r.get("_fav")}} for r in org_rows],
                   "caption": f"By {lvl.lower()}"}
            if data:
                t["extra_tables"].append(sub)
            else:
                t = {**sub, "extra_tables": []}
    elif kind == "cockpit":
        cols = ["KPI", "MTD", "MTD vs LY", "MTD vs Budget", "YTD", "YTD vs LY", "YTD vs Budget"]
        t["columns"] = cols
        for r in data:
            f = r.get("_fmt", "eur")
            vfmt = "rate" if (f == "eur" and r.get("_code") not in ("production", "personnel_7a")) else f
            dfmt = "pp" if f == "pct" else "pct"
            t["row_meta"].append({"kind": "line", "level": 0, "fmt": None,
                                  "col_fmt": {"MTD": vfmt, "YTD": vfmt, "MTD vs LY": dfmt, "MTD vs Budget": dfmt,
                                              "YTD vs LY": dfmt, "YTD vs Budget": dfmt},
                                  "fav": {c: r.get(f"_fav_{c}") for c in cols[1:] if " vs " in c}})
        t["caption"] = ("MTD = month to date, YTD = year to date. Amount variances in %, ratio variances in "
                        "percentage points; green = favourable.")
    elif kind == "ranking":
        lvl, cur, fmt = meta.get("level_label"), meta.get("current"), meta.get("fmt", "eur")
        fmt = "rate" if (fmt == "eur" and meta.get("kind") == "ratio") else fmt
        cols = ["Rank", lvl, cur] + [c for c in ("PY", "Var", "Var %") if data and c in data[0]]
        t["columns"] = cols
        t["col_fmt"] = {"Rank": "int", cur: fmt, "PY": fmt, "Var": "pp" if fmt == "pct" else fmt, "Var %": "pct"}
        t["row_meta"] = [{"kind": "line", "level": 0, "fmt": None, "fav": {"Var": r.get("_fav"), "Var %": r.get("_fav")}} for r in data]
    elif kind == "workforce":
        label, cm = meta.get("group_label", "Scope"), meta.get("cols") or {}
        hc, fte = cm.get("headcount", "Avg headcount"), cm.get("fte", "Avg FTE")
        cols = [label, hc, "Headcount PY"] + ([fte] if meta.get("focus") == "fte" else []) + [
            "Hires", "Leavers", "of which restructuring", "Attrition", "Attrition PY", "Utilization", "Utilization PY",
            "Overtime ratio"]
        if not meta.get("has_py"):
            cols = [c for c in cols if not c.endswith(" PY")]
        t["columns"] = cols
        t["table_class"] = "wf"                     # many columns: headers may wrap
        t["col_fmt"] = {hc: "num", "Headcount PY": "num", fte: "num", "Hires": "int", "Leavers": "int",
                        "of which restructuring": "int", "Attrition": "pct", "Attrition PY": "pct", "Utilization": "pct",
                        "Utilization PY": "pct", "Overtime ratio": "pct"}
        t["row_meta"] = [{"kind": r.get("_kind", "line"), "level": 0, "fmt": None,
                          "fav": {"Attrition": r.get("_fav_Attrition"), "Utilization": r.get("_fav_Utilization")}}
                         for r in data]
        t["caption"] = ("Fictional employee records, closed months. Headcount and FTE are monthly averages; attrition = "
                        "leavers x 12 / months / average headcount"
                        + (" (monthly rows: rolling 12 months to that month)" if meta.get("group") == "month" else "")
                        + "; utilization and overtime use direct staff hours. Green / red = better / worse than PY.")
    else:
        cols = [c for c in data[0].keys() if not str(c).startswith("_")]
        t["columns"] = cols
        t["col_fmt"] = {c: "num" for c in cols if isinstance(data[0][c], (int, float)) and not isinstance(data[0][c], bool)}
        t["row_meta"] = [{"kind": "line", "level": 0, "fmt": None, "fav": {}} for _ in data]
    return t


def _cell(v, fmt: str | None, units: str) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return ""
    if fmt == "eur":
        return F.table_number(v, units)
    if fmt == "rate":
        return F.table_money_small(v)
    if fmt == "pct":
        return F.table_pct(v)
    if fmt == "pp":
        return F.table_pp(v)
    if fmt == "num":
        s = f"{abs(v):,.1f}" if abs(v) < 10 else f"{abs(v):,.0f}"
        return f"({s})" if v < 0 and s.strip("0.,") else s
    if fmt == "int":
        return f"{int(round(v)):,}"
    return html.escape(str(v))


def _cell_fmt(t: dict, m: dict | None, c: str) -> str | None:
    """Format code for one cell: column format, overridden by the row's own format (ratio / stat rows)."""
    m = m or {}
    row_fmt = m.get("fmt")
    fmt = m.get("col_fmt", {}).get(c, t["col_fmt"].get(c))
    if row_fmt == "pct" and fmt in ("eur",):
        fmt = "pp" if (" vs " in c or c.startswith(("Var", "vs ", "Gap"))) else "pct"
    elif row_fmt == "pct" and fmt == "pct" and "Var %" in c:
        fmt = None
    elif row_fmt == "num" and fmt == "eur":
        fmt = "num"
    return fmt


def _caption(t: dict, units: str) -> str:
    cap = t.get("caption") or ""
    has_money = any(v == "eur" for v in t["col_fmt"].values()) or any(
        v == "eur" for m in t.get("row_meta") or [] for v in (m or {}).get("col_fmt", {}).values())
    unit_note = F.unit_label(units) if has_money else (F.CUR if any(v == "rate" for v in t["col_fmt"].values()) else "")
    return " · ".join(x for x in (unit_note, cap) if x)


def render_html(t: dict, units: str = "k") -> str:
    if not t.get("columns"):
        return ""
    cols = t["columns"]
    head = "".join(f'<th class="{"num" if i else "label"}">{html.escape(str(c))}</th>' for i, c in enumerate(cols))
    body = []
    for r, m in zip(t["rows"], t["row_meta"] or [{}] * len(t["rows"])):
        cls = (m or {}).get("kind", "line")
        tds = []
        for i, c in enumerate(cols):
            txt = _cell(r.get(c), _cell_fmt(t, m, c), units) if i else html.escape(str(r.get(c, "")))
            fav = (m or {}).get("fav", {}).get(c)
            fcls = " fav" if fav is True else (" unfav" if fav is False else "")
            style = f' style="padding-left:{8 + 16 * int((m or {}).get("level", 0))}px"' if i == 0 else ""
            tds.append(f'<td class="{"num" if i else "label"}{fcls}"{style}>{txt}</td>')
        body.append(f'<tr class="{cls}">{"".join(tds)}</tr>')
    extra_cls = f" {t['table_class']}" if t.get("table_class") else ""
    return (f'<div class="fin-wrap"><table class="fin-table{extra_cls}"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>'
            f'<div class="fin-caption">{html.escape(_caption(t, units))}</div></div>')


def render_markdown(t: dict, units: str = "k") -> str:
    """Same table as render_html, as GitHub Markdown (subtotal rows in bold)."""
    if not t.get("columns"):
        return ""
    cols = t["columns"]
    lines = ["| " + " | ".join(str(c) for c in cols) + " |",
             "|" + "|".join(":---" if i == 0 else "---:" for i in range(len(cols))) + "|"]
    for r, m in zip(t["rows"], t["row_meta"] or [{}] * len(t["rows"])):
        bold = (m or {}).get("kind") == "subtotal"
        cells = []
        for i, c in enumerate(cols):
            txt = html.unescape(_cell(r.get(c), _cell_fmt(t, m, c), units)) if i else str(r.get(c, ""))
            txt = txt.replace("|", "/")
            if i == 0 and (m or {}).get("level"):
                txt = "&nbsp;&nbsp;" * int(m["level"]) + txt
            cells.append(f"**{txt}**" if bold and txt.strip() else txt)
        lines.append("| " + " | ".join(cells) + " |")
    cap = _caption(t, units)
    return "\n".join(lines) + (f"\n\n_{cap}_" if cap else "")


def to_dataframe(t: dict) -> pd.DataFrame:
    if not t.get("columns"):
        return pd.DataFrame()
    return pd.DataFrame([{c: r.get(c) for c in t["columns"]} for r in t["rows"]])


def to_csv_bytes(t: dict) -> bytes:
    return to_dataframe(t).to_csv(index=False).encode("utf-8")


def to_excel_bytes(t: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        to_dataframe(t).to_excel(xw, index=False, sheet_name="answer")
        for i, extra in enumerate(t.get("extra_tables", []), start=1):
            to_dataframe(extra).to_excel(xw, index=False, sheet_name=f"detail_{i}")
    return buf.getvalue()


TABLE_CSS = """
<style>
.fin-wrap {overflow-x:auto; margin: 0.25rem 0 0.75rem 0;}
.fin-table {border-collapse: collapse; width: 100%; font-size: 0.86rem; font-family: Inter, 'Segoe UI', Helvetica, Arial, sans-serif;}
.fin-table th {background:#0B3D91; color:#fff; padding:6px 8px; font-weight:600; white-space:nowrap;}
.fin-table.wf th {white-space:normal; vertical-align:bottom; line-height:1.2;}
.fin-table td {padding:5px 8px; border-bottom:1px solid #E5E8EB; white-space:nowrap;}
.fin-table td.num, .fin-table th.num {text-align:right; font-variant-numeric: tabular-nums;}
.fin-table td.label, .fin-table th.label {text-align:left;}
.fin-table tr.subtotal td {font-weight:700; background:#F2F4F7; border-top:1.5px solid #0B3D91;}
.fin-table tr.ratio td {font-style:italic; color:#34495E;}
.fin-table tr.group td {font-weight:600;}
.fin-table td.fav {color:#1E8449; font-weight:600;}
.fin-table td.unfav {color:#C0392B; font-weight:600;}
.fin-caption {font-size:0.75rem; color:#6B7785; margin-top:4px;}
</style>
"""
