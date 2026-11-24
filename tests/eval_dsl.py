"""Independent expected values for the golden questions.

A small DSL compiled straight to SQL over the BASE tables (fact_pnl, fact_stats, dim_account,
dim_org, dim_version, fact_employee_month, dim_employee). It deliberately does not use the semantic
layer, the reporting views or the metric registry, so the evaluation checks the whole chain (entity
resolution -> tool choice -> semantic layer -> SQL) against a separate computation of the same number.

Spec keys (YAML):
    m: maop                     amount of a measure (see MEASURES), display sign (costs positive)
    s: fte                      statistic (stocks averaged over months, flows summed)
    r: [maop, revenue]          ratio of two measures / statistics; annualize: true for "per FTE"
    w: attrition                workforce figure from the employee records (see WORKFORCE);
                                emp: {staff_type: Direct} filters employees (role / grade / staff_type)
    org: {l3_country: Mexico}   org filter (value or list), default = whole group
    p: YTD-2026-10 | FY-2025 | M-2025-03 | Q-2025-3 | H1-2026 | R-2023-01:2026-10 | R12M-2026-10
    v: Actual (default) | Budget | FC1 | FC2 | FC3 | PY (= Actual, months shifted back 12)
    rank: {...value spec...}, level: l3_country, within: {...}, asc: false, n: 1
                                -> value AND name of the n-th entity of the ranking
    org_from_rank: {...rank spec...}   org = the entity returned by that ranking (follow-ups)
    v: LANDING  (p: M-2026-11)  landing P50 of the open month, summed over BUs from fact_landing
    v: YTDL     (p: YTD-2026-11) closed-month actuals + the landing P50 of the open month
    d: [spec_a, spec_b]         difference a - b (e.g. landing minus budget; works inside rank)
    c: regions | countries | product_lines | businesses | business_units, persona: us_country_head
                                -> number of entities the persona may see, and their names
    names_from_yaml: ratios | metrics   -> display names defined in app/semantic/metrics.yaml
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache

import yaml
from sqlalchemy import text

from app.config import ROOT, backend, data_as_of_date, settings
from app.db import get_engine

# measure -> (SQL predicate on dim_account a, display sign)
MEASURES: dict[str, tuple[str, int]] = {
    "billing": ("a.line_no = 1", 1),
    "wip": ("a.line_no = 2", 1),
    "revenue": ("a.line_no IN (1, 2)", 1),
    "production": ("a.line_no IN (1, 2, 4, 5)", 1),
    "personnel": ("a.line_no = 7", -1),
    "7a": ("a.l2_code = '7A'", -1),
    "7b": ("a.l2_code = '7B'", -1),
    "bonus_7a2": ("a.l3_code = '7A2'", -1),
    "subcontracting": ("a.line_no = 8", -1),
    "other_cost": ("a.line_no = 9", -1),
    "functional_cost": ("a.line_no = 12", -1),
    "gross_profit": ("a.line_no IN (1, 2, 4, 5, 7, 8, 9, 10)", 1),
    "maop": ("a.line_no IN (1, 2, 4, 5, 7, 8, 9, 10, 12)", 1),
    "management_op": ("a.line_no IN (1, 2, 4, 5, 7, 8, 9, 10, 12, 17)", 1),
    "net_income": ("a.line_no IN (1, 2, 4, 5, 7, 8, 9, 10, 12, 17, 19, 20)", 1),
    "direct_margin": ("(a.line_no IN (1, 2, 4, 5) OR a.l2_code = '7A')", 1),
    "restructuring": ("a.l3_code = '17.1'", -1),
}
STATS = {"fte": "avg", "headcount": "avg", "direct_fte": "avg", "billable_hours": "sum",
         "available_hours": "sum", "overtime_hours": "sum"}
# workforce figure -> display format (attrition = leavers x 12 / months / average headcount)
WORKFORCE = {"headcount": "num", "fte": "num", "hires": "num", "leavers": "num", "restructuring_leavers": "num",
             "attrition": "pct", "voluntary_attrition": "pct", "utilization": "pct", "overtime": "pct"}
EMP_COLS = ("role", "grade", "staff_type")
LEVELS = ("l1_group", "l2_region", "l3_country", "l4_product_line", "l5_business", "l6_bu")
# measure -> fact_landing.measure (P50 stored with the ledger sign, like fact_pnl)
LANDING_MEASURES = {"billing": "billing", "revenue": "revenue", "production": "production", "maop": "maop",
                    "gross_profit": "gross_profit", "personnel": "personnel", "subcontracting": "subcontracting",
                    "other_cost": "other_cost", "functional_cost": "functional_cost"}
CATALOG_LEVEL = {"regions": "l2_region", "countries": "l3_country", "product_lines": "l4_product_line",
                 "businesses": "l5_business", "business_units": "l6_bu"}
AS_OF = data_as_of_date()


def open_month(as_of: date = AS_OF) -> int:
    """Month after the last closed month (a month closes on the close day of the following month)."""
    close_day = int(settings()["close_day_of_next_month"])
    back = 1 if as_of.day >= close_day else 2          # months back to the last closed month
    return _add(_mk(as_of.year, as_of.month), 1 - back)


# --------------------------------------------------------------------------------- periods
def _mk(y: int, m: int) -> int:
    return y * 100 + m


def _add(k: int, n: int) -> int:
    y, m = divmod(k, 100)
    t = y * 12 + (m - 1) + n
    return _mk(t // 12, t % 12 + 1)


def _range(a: int, b: int) -> list[int]:
    out, k = [], a
    while k <= b:
        out.append(k)
        k = _add(k, 1)
    return out


def months_of(p: str) -> list[int]:
    kind, _, rest = p.partition("-")
    if kind == "YTD":
        y, m = map(int, rest.split("-"))
        return _range(_mk(y, 1), _mk(y, m))
    if kind == "FY":
        y = int(rest)
        return _range(_mk(y, 1), _mk(y, 12))
    if kind == "M":
        y, m = map(int, rest.split("-"))
        return [_mk(y, m)]
    if kind == "Q":
        y, q = map(int, rest.split("-"))
        return _range(_mk(y, 3 * q - 2), _mk(y, 3 * q))
    if kind in ("H1", "H2"):
        y = int(rest)
        return _range(_mk(y, 1), _mk(y, 6)) if kind == "H1" else _range(_mk(y, 7), _mk(y, 12))
    if kind == "R12M":
        y, m = map(int, rest.split("-"))
        return _range(_add(_mk(y, m), -11), _mk(y, m))
    if kind == "R":
        a, b = rest.split(":")
        (y0, m0), (y1, m1) = map(int, a.split("-")), map(int, b.split("-"))
        return _range(_mk(y0, m0), _mk(y1, m1))
    raise ValueError(f"bad period {p!r}")


# --------------------------------------------------------------------------------- SQL
@lru_cache(maxsize=1)
def _engine():
    return get_engine(admin=True) if backend() == "mssql" else get_engine("__eval__")


def _org_sql(org: dict | None, params: dict) -> str:
    parts = []
    for i, (lvl, vals) in enumerate((org or {}).items()):
        if lvl not in LEVELS:
            raise ValueError(f"bad org level {lvl}")
        vals = [vals] if isinstance(vals, str) else list(vals)
        names = []
        for j, v in enumerate(vals):
            params[f"o{i}_{j}"] = v
            names.append(f":o{i}_{j}")
        parts.append(f"o.{lvl} IN ({', '.join(names)})")
    return (" AND " + " AND ".join(parts)) if parts else ""


def _version_months(spec: dict) -> tuple[str, list[int]]:
    v = spec.get("v", "Actual")
    months = months_of(spec["p"])
    if v == "PY":
        return "Actual", [_add(k, -12) for k in months]
    return v, months


@lru_cache(maxsize=8)
def landing_snapshot(month: int, as_of: date = AS_OF):
    rows = _q("SELECT MAX(snapshot_date) FROM landing_run WHERE month_key = :m AND snapshot_date <= :a",
              {"m": month, "a": as_of})
    if not rows or rows[0][0] is None:
        raise ValueError(f"no landing snapshot for {month} on or before {as_of}")
    return rows[0][0]


def landing_amount(measure: str, org: dict | None, month: int, group: str | None = None):
    """Landing P50 of the open month summed over the BUs (display sign, like amount())."""
    if month != open_month():
        raise ValueError(f"landing exists for the open month {open_month()} only, not {month}")
    sign = MEASURES[measure][1]
    params = {"s": landing_snapshot(month), "m": month, "meas": LANDING_MEASURES[measure]}
    gsel = f"o.{group}, " if group else ""
    rows = _q(f"""SELECT {gsel}SUM(l.p50) FROM fact_landing l
                  JOIN dim_org o ON o.bu_id = l.bu_id
                  WHERE l.snapshot_date = :s AND l.month_key = :m AND l.measure = :meas{_org_sql(org, params)}
                  {'GROUP BY o.' + group if group else ''}""", params)
    if group:
        return {r[0]: float(r[1] or 0) * sign for r in rows}
    return float(rows[0][0] or 0) * sign


def _q(sql: str, params: dict):
    with _engine().connect() as c:
        return c.execute(text(sql), params).fetchall()


def _add_values(a, b):
    if isinstance(a, dict):
        return {k: a.get(k, 0.0) + b.get(k, 0.0) for k in set(a) | set(b)}
    return a + b


def amount(measure: str, org: dict | None, version: str, months: list[int], group: str | None = None):
    if version == "LANDING":
        return landing_amount(measure, org, months[-1], group)
    if version == "YTDL":                       # closed months (Actual) + the open month (landing P50)
        om = open_month()
        closed = [k for k in months if k < om]
        land = landing_amount(measure, org, om, group) if om in months else ({} if group else 0.0)
        return _add_values(amount(measure, org, "Actual", closed, group) if closed else ({} if group else 0.0), land)
    pred, sign = MEASURES[measure]
    params = {"ver": version, "m0": min(months), "m1": max(months)}
    gsel = f"o.{group}, " if group else ""
    rows = _q(f"""SELECT {gsel}SUM(f.amount_usd) FROM fact_pnl f
                  JOIN dim_account a ON a.account_id = f.account_id
                  JOIN dim_org o ON o.bu_id = f.bu_id
                  JOIN dim_version v ON v.version_id = f.version_id
                  WHERE v.name = :ver AND f.month_key BETWEEN :m0 AND :m1 AND {pred}{_org_sql(org, params)}
                  {'GROUP BY o.' + group if group else ''}""", params)
    if group:
        return {r[0]: float(r[1] or 0) * sign for r in rows}
    return float(rows[0][0] or 0) * sign


def stat(name: str, org: dict | None, version: str, months: list[int], group: str | None = None,
         raw_sum: bool = False):
    params = {"ver": version, "m0": min(months), "m1": max(months)}
    gsel = f"o.{group}, " if group else ""
    rows = _q(f"""SELECT {gsel}SUM(s.{name}), COUNT(DISTINCT s.month_key) FROM fact_stats s
                  JOIN dim_org o ON o.bu_id = s.bu_id
                  JOIN dim_version v ON v.version_id = s.version_id
                  WHERE v.name = :ver AND s.month_key BETWEEN :m0 AND :m1{_org_sql(org, params)}
                  {'GROUP BY o.' + group if group else ''}""", params)

    def val(total, n):
        total = float(total or 0)
        return total if (raw_sum or STATS[name] == "sum") else total / max(int(n or 1), 1)
    if group:
        return {r[0]: val(r[1], r[2]) for r in rows}
    return val(rows[0][0], rows[0][1])


def _component(name: str, org, version, months, group=None, raw_sum=False):
    if name in MEASURES:
        return amount(name, org, version, months, group)
    if name in STATS:
        return stat(name, org, version, months, group, raw_sum=raw_sum)
    raise ValueError(f"unknown measure/stat {name}")


def workforce(name: str, org: dict | None, months: list[int], group: str | None = None, emp: dict | None = None):
    """Workforce figure from the employee records (Actual months). Averages are over all months of
    the period; attrition (annualised) = leavers x 12 / months / average headcount."""
    if name not in WORKFORCE:
        raise ValueError(f"unknown workforce figure {name}")
    params = {"m0": min(months), "m1": max(months)}
    flt = ""
    for i, (col, val) in enumerate((emp or {}).items()):
        if col not in EMP_COLS:
            raise ValueError(f"bad employee filter {col}")
        params[f"e{i}"] = val
        flt += f" AND e.{col} = :e{i}"
    gsel = f"o.{group}, " if group else ""
    rows = _q(f"""SELECT {gsel}COUNT(*), SUM(f.fte), SUM(CAST(f.is_hire AS INT)), SUM(CAST(f.is_leaver AS INT)),
                         SUM(CASE WHEN e.leave_reason = 'Restructuring' THEN CAST(f.is_leaver AS INT) ELSE 0 END),
                         SUM(f.billable_hours), SUM(f.available_hours), SUM(f.overtime_hours)
                  FROM fact_employee_month f
                  JOIN dim_employee e ON e.employee_id = f.employee_id
                  JOIN dim_org o ON o.bu_id = f.bu_id
                  WHERE f.month_key BETWEEN :m0 AND :m1{_org_sql(org, params)}{flt}
                  {'GROUP BY o.' + group if group else ''}""", params)
    n = len(months)

    def val(r):
        cnt, fte, hires, leavers, restr, bill, avail, over = (float(x or 0) for x in r)
        return {"headcount": cnt / n, "fte": fte / n, "hires": hires, "leavers": leavers,
                "restructuring_leavers": restr,
                "attrition": leavers * 12.0 / cnt if cnt else None,
                "voluntary_attrition": (leavers - restr) * 12.0 / cnt if cnt else None,
                "utilization": bill / avail if avail else None,
                "overtime": over / avail if avail else None}[name]
    if group:
        return {r[0]: val(r[1:]) for r in rows}
    return val(rows[0])


def _fmt(spec: dict) -> str:
    if "d" in spec:
        return _fmt(spec["d"][0])
    if "c" in spec or "names_from_yaml" in spec:
        return "num"
    if "m" in spec:
        return "eur"
    if "s" in spec:
        return "num"
    if "w" in spec:
        return WORKFORCE[spec["w"]]
    num, den = spec["r"]
    if den in STATS and STATS[den] == "avg":
        return "eur"                       # per FTE (annualised) -> money
    if num in MEASURES and den in STATS:
        return "rate"                      # per hour -> small money amount
    return "pct"


def _value(spec: dict, org, version, months, group=None):
    if "d" in spec:
        a, b = (dict(x) for x in spec["d"])
        va = _value(a, org, *_version_months({**a, "p": a.get("p", spec.get("p"))}), group)
        vb = _value(b, org, *_version_months({**b, "p": b.get("p", spec.get("p"))}), group)
        if group:
            return {k: va[k] - vb[k] for k in set(va) & set(vb)}
        return va - vb
    if "m" in spec:
        return _component(spec["m"], org, version, months, group)
    if "s" in spec:
        return _component(spec["s"], org, version, months, group)
    if "w" in spec:
        return workforce(spec["w"], org, months, group, spec.get("emp"))
    num_n, den_n = spec["r"]
    annual = bool(spec.get("annualize"))
    num = _component(num_n, org, version, months, group)
    den = _component(den_n, org, version, months, group, raw_sum=annual)
    k = 12.0 if annual else 1.0
    if group:
        return {e: (num.get(e, 0.0) * k / den[e]) if den.get(e) else None for e in set(num) | set(den)}
    return num * k / den if den else None


def _persona_bus(persona: str) -> set[int]:
    rows = _q("SELECT org_level, org_value FROM user_org_access WHERE user_id = :u", {"u": persona})
    org = _q("SELECT bu_id, l1_group, l2_region, l3_country, l4_product_line, l5_business, l6_bu FROM dim_org", {})
    cols = ("bu_id", *LEVELS)
    out = set()
    for level, value in rows:
        i = cols.index(level)
        out |= {int(r[0]) for r in org if r[i] == value}
    return out


def catalog(kind: str, persona: str, within: dict | None = None) -> dict:
    """Entities of one organisation level the persona may see (count and names)."""
    lvl = CATALOG_LEVEL[kind]
    bus = _persona_bus(persona)
    params: dict = {}
    rows = _q(f"SELECT o.bu_id, o.{lvl} FROM dim_org o WHERE 1 = 1{_org_sql(within, params)}", params)
    names = sorted({r[1] for r in rows if int(r[0]) in bus})
    return {"value": float(len(names)), "fmt": "num", "name": None, "names": names}


def yaml_names(section: str) -> dict:
    defs = yaml.safe_load((ROOT / "app" / "semantic" / "metrics.yaml").read_text())
    items = defs.get(section) or {}
    vals = items.values() if isinstance(items, dict) else items
    names = sorted(str(v.get("name")) for v in vals if isinstance(v, dict) and v.get("name"))
    return {"value": float(len(names)), "fmt": "num", "name": None, "names": names}


def evaluate(spec: dict) -> dict:
    """Return {'value': float, 'fmt': 'eur'|'pct'|'num'|'rate', 'name': entity or None[, 'names': [...]]}."""
    if "c" in spec:
        return catalog(spec["c"], spec.get("persona", "group_cfo"), spec.get("within"))
    if "names_from_yaml" in spec:
        return yaml_names(spec["names_from_yaml"])
    if "rank" in spec:
        inner = dict(spec["rank"])
        inner.setdefault("p", spec.get("p"))
        if "d" in inner:                     # each side of a difference carries its own version / period
            version, months = None, None
        else:
            version, months = _version_months({**inner, "v": inner.get("v", "Actual")})
        vals = _value(inner, spec.get("within"), version, months, group=spec["level"])
        items = sorted(((e, v) for e, v in vals.items() if v is not None), key=lambda x: x[1],
                       reverse=not spec.get("asc", False))
        name, value = items[int(spec.get("n", 1)) - 1]
        return {"value": value, "fmt": _fmt(inner), "name": name}
    org = spec.get("org")
    if "org_from_rank" in spec:
        r = evaluate(spec["org_from_rank"])
        org = {**(org or {}), spec["org_from_rank"]["level"]: r["name"]}
    version, months = _version_months(spec)
    return {"value": _value(spec, org, version, months), "fmt": _fmt(spec), "name": None}
