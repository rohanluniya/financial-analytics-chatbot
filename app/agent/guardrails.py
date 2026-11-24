"""Guardrails.

1. SQL guard for the fallback tool `run_readonly_sql` (sqlglot):
   exactly one SELECT statement, only whitelisted views from sql/views.sql, no DML/DDL/EXEC,
   no table functions, automatic TOP/LIMIT 1000, 15 s timeout, and in DuckDB mode the
   row-level-security filter is injected into every fact view.
2. Numeric guardrail: every number in the LLM's answer must exist (within display rounding)
   in the tool outputs; otherwise the answer is regenerated once. If it still fails, the sentences
   with unsupported numbers are dropped (only while the headline sentence survives), else the
   templated answer is used (see app/agent/graph.py).
3. Narrative checks on top of the numbers:
   * month binding: a number the answer ties to a month ("62 in Apr 2026") must be one of the
     numbers the data ties to that month;
   * scope: an answer about "United States · Environmental Lab Testing" must not describe its
     figures as "the United States" only;
   * reasons: sentences that explain with causes the data does not contain ("higher sales volumes",
     "cost management") are dropped; in the headline sentence they count as a failure;
   * wording: customer-specific terms typed by the user (MAOP, management OP) are written with the
     app's generic names.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import pandas as pd
import sqlglot
from sqlglot import exp

from app.config import backend, settings
from app.db import run_with_timeout

WHITELIST = {"v_org", "v_account", "v_period", "v_version", "v_pnl_leaf", "v_pnl", "v_stats", "v_employee",
             "v_employee_month"}
RLS_VIEWS = {"v_pnl_leaf", "v_pnl", "v_stats", "v_employee", "v_employee_month"}
FORBIDDEN_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Merge,
                   exp.Command, exp.Into, exp.Grant, exp.TruncateTable, exp.Transaction, exp.Commit,
                   exp.Rollback, exp.Set, exp.Use, exp.Pragma, exp.Copy, exp.Describe)
FORBIDDEN_FUNCS = re.compile(r"^(openrowset|openquery|opendatasource|xp_\w*|sp_\w*|read_\w*|"
                             r"glob|load|install|attach|copy|pg_\w*|sqlite_\w*)$", re.I)
ROW_LIMIT = int(settings()["sql_guard"]["row_limit"])
TIMEOUT = int(settings()["sql_guard"]["timeout_seconds"])


class SqlGuardError(ValueError):
    pass


def _dialect() -> str:
    return "duckdb" if backend() == "duckdb" else "tsql"


def validate_sql(sql: str, allowed_bu_ids: set[int] | None = None, dialect: str | None = None) -> str:
    """Return a safe, row-limited SQL string or raise SqlGuardError."""
    dialect = dialect or _dialect()
    if not sql or not sql.strip():
        raise SqlGuardError("empty SQL")
    if re.search(r"\b(exec|execute|xp_cmdshell|sp_executesql|shutdown|dbcc|waitfor|reconfigure)\b", sql, re.I):
        raise SqlGuardError("procedure execution / server commands are not allowed")
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except sqlglot.errors.ParseError as exc:
        raise SqlGuardError(f"could not parse SQL: {str(exc).splitlines()[0]}") from exc
    if len(statements) != 1:
        raise SqlGuardError(f"exactly one statement is allowed (got {len(statements)})")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SqlGuardError(f"only SELECT statements are allowed (got {type(tree).__name__.upper()})")
    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SqlGuardError(f"{type(node).__name__.upper()} is not allowed")
        if isinstance(node, (exp.Anonymous, exp.Func)):
            fname = node.name if isinstance(node, exp.Anonymous) else (node.sql_name() or "")
            if FORBIDDEN_FUNCS.match(str(fname)):
                raise SqlGuardError(f"function {fname} is not allowed")
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            raise SqlGuardError("table functions are not allowed")
        name = table.name.lower()
        if name in cte_names and not table.db:
            continue
        if table.catalog or (table.db and table.db.lower() not in ("dbo", "main")):
            raise SqlGuardError(f"cross-database/schema access is not allowed: {table.sql()}")
        if name not in WHITELIST:
            raise SqlGuardError(f"table/view '{name}' is not whitelisted (allowed: {', '.join(sorted(WHITELIST))})")

    # Row-level security in DuckDB mode: wrap each fact view in a filtered subquery
    if allowed_bu_ids is not None:
        ids = ", ".join(str(i) for i in sorted(allowed_bu_ids)) or "-1"

        def _rls(node):
            if isinstance(node, exp.Table) and node.name.lower() in RLS_VIEWS and node.name.lower() not in cte_names:
                alias = node.alias or node.name
                sub = sqlglot.parse_one(f"(SELECT * FROM {node.name} WHERE bu_id IN ({ids})) AS {alias}", read="duckdb")
                return sub
            return node
        tree = tree.transform(_rls)

    # Automatic row limit
    if isinstance(tree, exp.Select):
        limit = tree.args.get("limit")
        current = None
        if limit is not None:
            try:
                current = int(limit.expression.name if hasattr(limit, "expression") and limit.expression else limit.this.name)
            except Exception:  # noqa: BLE001
                current = None
        if current is None or current > ROW_LIMIT:
            tree = tree.limit(ROW_LIMIT)
    else:
        tree = exp.select("*").from_(tree.subquery("q")).limit(ROW_LIMIT)
    return tree.sql(dialect=dialect)


def execute_readonly(engine, safe_sql: str, timeout_s: int = TIMEOUT) -> pd.DataFrame:
    from sqlalchemy import text

    with engine.connect() as conn:
        def _run():
            res = conn.execute(text(safe_sql))
            return pd.DataFrame(res.fetchall(), columns=list(res.keys()))
        df = run_with_timeout(conn, _run, timeout_s)
        conn.rollback()
    for c in df.columns:
        if df[c].dtype == object:
            try:
                df[c] = pd.to_numeric(df[c])
            except (ValueError, TypeError):
                pass
    return df


# ------------------------------------------------------------------------------------------
# Numeric guardrail
# ------------------------------------------------------------------------------------------
NUM_RX = re.compile(
    r"(?<![\w.])[-+−]?\(?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\)?\s*"
    r"(%|pp\b|percentage points?|bn\b|billion|mn\b|million|m\b|k\b|thousand)?", re.I)
SCALE = {"bn": 1e9, "billion": 1e9, "mn": 1e6, "million": 1e6, "m": 1e6, "k": 1e3, "thousand": 1e3}


@dataclass
class NumberToken:
    raw: str
    value: float          # scaled absolute value (percent -> fraction)
    decimals: int
    unit: str
    scale: float
    end: int = 0          # position after the token in the text (including its unit)
    start: int = 0


def extract_numbers(text: str) -> list[NumberToken]:
    out = []
    for m in NUM_RX.finditer(text or ""):
        intpart, frac, unit = m.group(1), m.group(2) or "", (m.group(3) or "").lower()
        # skip parts of codes like 7A1 (a letter right after the digits); FC2, Q3, R12M, H1 (preceded by a
        # letter) are handled by the lookbehind. "62 restructuring" is a number followed by a word: keep it.
        num_end = m.end(2) if m.group(2) else m.end(1)
        nxt = text[num_end:num_end + 1]
        if not unit and nxt.isalpha():
            continue
        v = float(intpart.replace(",", "") + frac)
        dec = len(frac) - 1 if frac else 0
        if unit in ("%",):
            scale = 0.01
        elif unit.startswith("pp") or unit.startswith("percentage"):
            scale, unit = 0.01, "pp"
        else:
            scale = SCALE.get(unit, 1.0)
        out.append(NumberToken(m.group(0).strip(), abs(v) * scale, dec, unit, scale, m.end(), m.start(1)))
    return out


def _numbers_in(obj, acc: list[float]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        if not (isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj))):
            acc.append(abs(float(obj)))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers_in(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numbers_in(v, acc)
    elif isinstance(obj, str):
        acc.extend(t.value for t in extract_numbers(obj))


def allowed_numbers(tool_outputs: list) -> list[float]:
    acc: list[float] = []
    for t in tool_outputs:
        d = t.model_dump() if hasattr(t, "model_dump") else t
        _numbers_in(d.get("facts", []), acc)
        _numbers_in(d.get("data", []), acc)
        _numbers_in(d.get("notes", []), acc)
        _numbers_in(d.get("extra", {}), acc)
        _numbers_in({k: v for k, v in (d.get("meta") or {}).items() if k.startswith("total")}, acc)
        _numbers_in(d.get("filters_used", {}), acc)
    return sorted(set(round(a, 9) for a in acc))


@dataclass
class GuardResult:
    ok: bool
    unsupported: list[str] = field(default_factory=list)
    checked: int = 0
    problems: list[str] = field(default_factory=list)      # plain-language reasons, fed back to the writer


_CMP_AFTER = re.compile(r"\s*(?:\(\s*[\d.,]+\s*%?\s*\)\s*)?(?:above|below|more|fewer|less|higher|lower|up|down|"
                        r"over|under)\b", re.I)


def _is_trivial(tok: NumberToken, question_numbers: set[str], text: str = "") -> bool:
    if tok.unit == "" and tok.decimals == 0:
        v = tok.value
        if 1990 <= v <= 2100:                     # years
            return True
        if v <= 31:                               # months, days, small counts, line numbers ...
            # ... unless stated as a difference ("30 above PY"): models compute those themselves
            return not (text and _CMP_AFTER.match(text, tok.end))
    return tok.raw.replace("−", "-").strip("+- ()") in question_numbers


def _supported(tok: NumberToken, allowed: list[float]) -> bool:
    """True if the token equals one of the allowed values within its display rounding."""
    half_unit = 0.5 * (10 ** -tok.decimals) * tok.scale
    tol = max(half_unit * 1.02, 1e-9)
    ok = any(abs(tok.value - a) <= tol or (tok.value > 0 and abs(tok.value - a) / tok.value <= 0.005)
             for a in allowed)
    if not ok and tok.unit in ("%", "pp"):
        # model may have written a fraction as percent number without scaling
        ok = any(abs(tok.value * 100 - a) <= tol * 100 for a in allowed)
    return ok


def check_numbers(answer: str, tool_outputs: list, question: str = "") -> GuardResult:
    allowed = allowed_numbers(tool_outputs)
    qnums = {t.raw.strip("+- ()") for t in extract_numbers(question or "")}
    bad, checked = [], 0
    for tok in extract_numbers(answer):
        if _is_trivial(tok, qnums, answer or ""):
            continue
        checked += 1
        if not _supported(tok, allowed):
            bad.append(tok.raw)
    return GuardResult(ok=not bad, unsupported=bad, checked=checked,
                       problems=[f"numbers that are not in FACTS: {', '.join(bad)}"] if bad else [])


# ------------------------------------------------------------------------------------------
# Narrative checks: month binding, scope, reasons that are not in the data, generic wording
# ------------------------------------------------------------------------------------------
_MON = {"jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "may": "May", "jun": "Jun", "jul": "Jul",
        "aug": "Aug", "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dec"}
MONTH_RX = re.compile(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
                      r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(20\d\d)\b")
# a month that bounds a period ("YTD Oct 2026", "Jan–Jun 2026", "from Apr 2026 to ...") is not a single month
_PERIOD_BEFORE = re.compile(r"(?:\bYTD|\bR12M?|\bto|\bthrough|\buntil|\bsince|\bfrom|\bbetween|\bending|\bup to|"
                            r"\bas of|\band|[–—-])\s*$", re.I)
_PERIOD_AFTER = re.compile(r"^\s*(?:[–—-]|to\b|through\b|and\b)", re.I)


def _month_mentions(text: str) -> list[tuple[str, bool]]:
    """(label, is_single_month) for every 'Mon YYYY' in the text, label normalised to 'Apr 2026'."""
    out = []
    for m in MONTH_RX.finditer(text or ""):
        before, after = text[max(0, m.start() - 12):m.start()], text[m.end():m.end() + 10]
        single = not (_PERIOD_BEFORE.search(before) or _PERIOD_AFTER.search(after))
        out.append((f"{_MON[m.group(1)[:3].lower()]} {m.group(2)}", single))
    return out


def _dump(t) -> dict:
    return t.model_dump() if hasattr(t, "model_dump") else t


def month_bindings(tool_outputs: list) -> dict[str, list[float]]:
    """Numbers the tool outputs attach to one month: 'Apr 2026' -> [2026, 63, 60, ...]."""
    out: dict[str, list[float]] = {}
    for t in tool_outputs:
        d = _dump(t)
        for s in [*(d.get("facts") or []), *(d.get("notes") or [])]:
            for piece in re.split(r";\s+", str(s)):
                ms = _month_mentions(piece)
                if len(ms) == 1 and ms[0][1]:
                    out.setdefault(ms[0][0], []).extend(tok.value for tok in extract_numbers(piece))
        for row in d.get("data") or []:
            if not isinstance(row, dict):
                continue
            ms = [x for v in row.values() if isinstance(v, str) for x in _month_mentions(v)]
            if len(ms) == 1:
                acc: list[float] = []
                _numbers_in({k: v for k, v in row.items() if not isinstance(v, str)}, acc)
                out.setdefault(ms[0][0], []).extend(acc)
    return out


def _period_months(tool_outputs: list, question: str) -> set[str]:
    """Months that are the question's own period (start / end): every figure belongs to them."""
    skip = {lab for lab, _ in _month_mentions(question or "")}
    for t in tool_outputs:
        f = _dump(t).get("filters_used") or {}
        for v in [f.get("period"), f.get("months"), *(f.get("versions") or [])]:
            skip |= {lab for lab, _ in _month_mentions(str(v or ""))}
    return skip


_QUAL_RX = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)\s+(restructuring|voluntary)\b", re.I)


def month_qualified(tool_outputs: list) -> dict[tuple[str, str], list[float]]:
    """Counts the data ties to a month and a leaver type: ('Apr 2026', 'restructuring') -> [60]."""
    out: dict[tuple[str, str], list[float]] = {}
    for t in tool_outputs:
        d = _dump(t)
        for s in [*(d.get("facts") or []), *(d.get("notes") or [])]:
            for piece in re.split(r";\s+", str(s)):
                ms = _month_mentions(piece)
                if len(ms) == 1 and ms[0][1]:
                    for m in _QUAL_RX.finditer(MONTH_RX.sub(" ", piece)):
                        out.setdefault((ms[0][0], m.group(2).lower()), []).append(float(m.group(1).replace(",", "")))
        for row in d.get("data") or []:
            if not isinstance(row, dict):
                continue
            ms = [x for v in row.values() if isinstance(v, str) for x in _month_mentions(v)]
            if len(ms) != 1:
                continue
            for k, v in row.items():
                key = str(k).lower()
                if isinstance(v, (int, float)) and not isinstance(v, bool) and "restructuring" in key and "py" not in key:
                    out.setdefault((ms[0][0], "restructuring"), []).append(float(v))
    return out


_NEAR = 24          # characters between a number and the month it is tied to


def check_month_bindings(answer: str, tool_outputs: list, question: str = "") -> list[tuple[str, str]]:
    """(number, month) pairs where the answer ties a number to a month that the data does not tie it to.

    Checked per clause (sentence, semicolon or parenthesis), only when the clause names exactly one single
    month that the data has figures for and that is not the question's own period, and only for numbers
    next to the month ("63 in Apr 2026", "Apr 2026 at 63"). A count followed by a leaver type
    ("63 restructuring") must also match that type for the month.
    """
    binds = month_bindings(tool_outputs)
    quals = month_qualified(tool_outputs)
    skip = _period_months(tool_outputs, question)
    bad = []
    for clause in re.split(r"(?<=[.!?;])\s+|[()]", answer or ""):
        ms = _month_mentions(clause)
        if len(ms) != 1 or not ms[0][1] or ms[0][0] in skip or ms[0][0] not in binds:
            continue
        label, mm = ms[0][0], MONTH_RX.search(clause)

        def near(a: int, b: int) -> bool:          # span [a, b) close to the month mention, not inside it
            return not (mm.start() <= a < mm.end()) and (0 <= mm.start() - b <= _NEAR or 0 <= a - mm.end() <= _NEAR)
        for tok in extract_numbers(clause):
            if near(tok.start, tok.end) and not _supported(tok, binds[label]):
                bad.append((tok.raw, label))
        for m in _QUAL_RX.finditer(clause):
            key = (label, m.group(2).lower())
            if near(m.start(1), m.end()) and key in quals and float(m.group(1).replace(",", "")) not in quals[key]:
                bad.append((m.group(1), f"{label} {key[1]}"))
    return list(dict.fromkeys(bad))


def qualified_counts(tool_outputs: list) -> dict[str, list[float]]:
    """Counts the data gives per leaver type, any period: 'restructuring' -> [62, 3, 60, ...]."""
    out: dict[str, list[float]] = {}
    for t in tool_outputs:
        d = _dump(t)
        for s in [*(d.get("facts") or []), *(d.get("notes") or [])]:
            for m in _QUAL_RX.finditer(MONTH_RX.sub(" ", str(s))):
                out.setdefault(m.group(2).lower(), []).append(float(m.group(1).replace(",", "")))
        for row in d.get("data") or []:
            if isinstance(row, dict):
                for k, v in row.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and "restructuring" in str(k).lower():
                        out.setdefault("restructuring", []).append(float(v))
    return out


def check_qualified(answer: str, tool_outputs: list) -> list[tuple[str, str]]:
    """(count, type) where the answer labels a count as restructuring / voluntary leavers but the data does not
    ("99 restructuring leavers" when 99 is all leavers and 62 were restructuring)."""
    quals = qualified_counts(tool_outputs)
    bad = []
    for m in _QUAL_RX.finditer(MONTH_RX.sub(" ", answer or "")):
        q = m.group(2).lower()
        if q in quals and float(m.group(1).replace(",", "")) not in quals[q]:
            bad.append((m.group(1), q))
    return list(dict.fromkeys(bad))


_TYPED_DIFF_FACT = re.compile(r"\b(Restructuring|Voluntary) leavers: [\d,]+; ([\d,]+)(?: \([\d.]+%\))? (?:more|fewer) than PY",
                              re.I)
_TYPED_DIFF_ANSWER = re.compile(r"\b(restructuring|voluntary)\b[^.;\d]{0,40}?(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)\s*"
                                r"(?:\([^)]*\)\s*)?(?:more|fewer|above|below|higher|lower)\b", re.I)


def check_typed_differences(answer: str, tool_outputs: list) -> list[tuple[str, str]]:
    """(change, type) where the answer gives a leaver type a change vs PY that the facts give to another figure
    ("restructuring accounting for 67 more leavers" when 67 is the change in all leavers)."""
    diffs: dict[str, list[float]] = {}
    for t in tool_outputs:
        for s in _dump(t).get("facts") or []:
            for m in _TYPED_DIFF_FACT.finditer(str(s)):
                diffs.setdefault(m.group(1).lower(), []).append(float(m.group(2).replace(",", "")))
    bad = []
    for m in _TYPED_DIFF_ANSWER.finditer(answer or ""):
        q = m.group(1).lower()
        if q in diffs and float(m.group(2).replace(",", "")) not in diffs[q]:
            bad.append((m.group(2), q))
    return list(dict.fromkeys(bad))


_GENERIC_TAIL = {"Testing", "Products", "Vessels", "Energy", "Minerals", "Infrastructure", "Sustainability"}


def _aliases(value: str) -> list[str]:
    """Ways an answer may name one org value: full name, leading word, initials (B&I), city of a business."""
    v = value.strip()
    if re.search(r"\d", v):                                   # BU codes
        return [v]
    al = {v}
    words = [w for w in v.split() if w not in ("&", "and")]
    if words and len(words[0]) >= 5:
        al.add(words[0])
    if len(words) > 1 and len(words[-1]) >= 5 and words[-1] not in _GENERIC_TAIL:
        al.add(words[-1])
    if "&" in v:
        al.add("&".join("".join(w[0] for w in part.split()) for part in v.split("&")))
    if v == "United States":
        al |= {"US", "U.S."}
    if v.startswith("Environmental"):
        al.add("Env Lab")
    return sorted(al, key=len, reverse=True)


def _mentions(text: str, part: str) -> str | None:
    for value in part.split(" + "):
        for a in _aliases(value):
            if re.search(rf"(?<!\w){re.escape(a)}(?!\w)", text, re.I if len(a) > 4 else 0):
                return a
    return None


def check_scope(answer: str, tool_outputs: list) -> str | None:
    """Problem text if the answer names a broader scope (the country) but not the scope that was queried."""
    label = next((lab for t in tool_outputs if (lab := (_dump(t).get("filters_used") or {}).get("org"))), None)
    if not label or " · " not in label or not answer:
        return None
    parts = label.split(" · ")
    if _mentions(answer, parts[-1]):
        return None
    broader = next((hit for p in parts[:-1] if (hit := _mentions(answer, p))), None)
    if broader:
        return (f"the figures are for '{label.replace(' · ', ' ')}', but the answer calls them '{broader}'; "
                "name the scope in full")
    return None


REASON_RX = re.compile(
    r"\b(sales volumes?|higher volumes?|volume growth|cost (?:management|control|discipline|savings|efficienc\w*)|"
    r"efficienc\w*|productivity|demand|pricing|price (?:increases?|rises?)|markets?|seasonal\w*|"
    r"strong performance|robust performance|operational (?:improvements?|excellence)|economic|macro\w*|"
    r"competition|competitive|customer (?:wins?|demand|mix|base)|new (?:contracts?|clients?|customers?)|"
    r"contract (?:wins?|losses?)|lost (?:contracts?|clients?|customers?)|business growth|strategic|investments?|"
    r"(?:has|have) been stable|remained stable|no significant)\b", re.I)


def split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z*_])", (text or "").strip()) if s]


def _facts_text(tool_outputs: list) -> str:
    return " ".join(str(x) for t in tool_outputs for k in ("facts", "notes") for x in (_dump(t).get(k) or [])).lower()


def ungrounded_reasons(sentence: str, facts_text: str) -> list[str]:
    """Cause words in the sentence that the tool outputs never mention."""
    hits = {m.group(0).lower() for m in REASON_RX.finditer(sentence or "")}
    return sorted(h for h in hits if h not in facts_text)


CAUSAL_RX = re.compile(r"\b(driven by|due to|because(?: of)?|as a result of|thanks to|caused by|owing to|"
                       r"on the back of|attributable to|reflect(?:s|ed|ing)?|explained by|stem(?:s|med|ming)? from|"
                       r"resulting from)\b", re.I)
_LABEL_STOP = {"total", "actual", "budget", "py", "rl group", "group", "n/a"}


def data_labels(tool_outputs: list) -> list[str]:
    """Lower-case names the tool outputs report on: the row labels of their data (lines, accounts, drivers,
    KPIs, roles, grades, BUs, countries, months), plus the long first word of multi-word labels."""
    labs: set[str] = set()
    for t in tool_outputs:
        for row in _dump(t).get("data") or []:
            if not isinstance(row, dict):
                continue
            for k, v in row.items():
                if not isinstance(v, str) or str(k).startswith("_") or not 2 <= len(v.strip()) <= 60:
                    continue
                low = v.strip().lower()
                if low in _LABEL_STOP:
                    continue
                base = re.sub(r"\s+as % of .*$", "", low)
                labs |= {low, base}
                first = base.split()[0] if base.split() else ""
                if len(first) >= 8:
                    labs.add(first)
    return sorted(labs, key=len, reverse=True)


def unsupported_cause(sentence: str, labels: list[str]) -> str | None:
    """The cause clause of a sentence ('... driven by X') when X names nothing the data reports on."""
    m = CAUSAL_RX.search(sentence or "")
    if not m:
        return None
    tail = MONTH_RX.sub(lambda mm: f"{_MON[mm.group(1)[:3].lower()]} {mm.group(2)}", sentence[m.end():]).lower()
    if any(re.search(rf"(?<!\w){re.escape(lab)}(?!\w)", tail) for lab in labels):
        return None
    return sentence[m.start():].strip()[:120]


def drop_ungrounded(answer: str, tool_outputs: list) -> tuple[str, list[str]]:
    """Drop the sentences after the headline that explain with causes the data does not contain: cause words
    the facts never mention, or a 'driven by / due to ...' clause that names nothing in the data."""
    ft, labels = _facts_text(tool_outputs), data_labels(tool_outputs)
    sents = split_sentences(answer)
    bad = [s for s in sents[1:] if ungrounded_reasons(s, ft) or unsupported_cause(s, labels)]
    keep = sents[:1] + [s for s in sents[1:] if s not in bad]
    return " ".join(keep).strip(), bad


_CANONICAL = [(re.compile(r"\bMAOP margins?\b", re.I), "operating margin"),
              (re.compile(r"\bMAOP\b", re.I), "operating profit"),
              (re.compile(r"\bmanagement OP\b", re.I), "EBIT")]


def canonical_terms(text: str) -> str:
    """Write customer-specific terms with the app's generic names (capitalised at a sentence start)."""
    for rx, rep in _CANONICAL:
        def _sub(m, t=text, rep=rep):
            pre = t[:m.start()].rstrip()
            start = not pre or pre.endswith((".", "!", "?", "*", "\n", ":"))
            return rep[0].upper() + rep[1:] if start else rep
        text = rx.sub(_sub, text)
    return text


def check_answer(answer: str, tool_outputs: list, question: str = "") -> GuardResult:
    """Numbers, month binding, scope and headline reasons; problems are phrased for the rewrite prompt."""
    g = check_numbers(answer, tool_outputs, question)
    bad, problems = list(g.unsupported), list(g.problems)
    mb = check_month_bindings(answer, tool_outputs, question)
    if mb:
        bad += [raw for raw, _ in mb]
        problems += [f"{raw} is not the {label} figure in FACTS" for raw, label in mb]
    mq = [(raw, q) for raw, q in check_qualified(answer, tool_outputs) if raw not in bad]
    if mq:
        bad += [raw for raw, _ in mq]
        problems += [f"{raw} is not the {q} figure in FACTS" for raw, q in mq]
    md = [(raw, q) for raw, q in check_typed_differences(answer, tool_outputs) if raw not in bad]
    if md:
        bad += [raw for raw, _ in md]
        problems += [f"{raw} is not the change in {q} leavers (figure in FACTS)" for raw, q in md]
    sc = check_scope(answer, tool_outputs)
    if sc:
        problems.append(sc)
    sents = split_sentences(answer)
    if sents:
        rs = ungrounded_reasons(sents[0], _facts_text(tool_outputs))
        cause = unsupported_cause(sents[0], data_labels(tool_outputs))
        if rs or cause:
            problems.append("reasons that are not in FACTS: " + ", ".join(rs + ([f"'{cause}'"] if cause else [])))
    return GuardResult(ok=not problems, unsupported=list(dict.fromkeys(bad)), checked=g.checked, problems=problems)

