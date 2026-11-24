"""Time intelligence: periods (month, QTD, YTD, R12M, FY, quarter, range), comparisons
(PY, Budget, FC1/FC2/FC3, latest forecast), variances and favourability.

Conventions
* month keys are integers YYYYMM.
* A month is closed (has Actuals) when its close date (5th of the next month) <= as-of date.
* Default period = YTD of the last closed month.
* Comparisons are like-for-like: PY uses the same months shifted by one year; when a period
  reaches beyond the last closed month, all series are truncated to the closed months.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.config import as_of_date, forecast_actual_months, settings

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_LOOKUP = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9, "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
PERIOD_TYPES = ("MONTH", "QTD", "YTD", "R12M", "FY", "QUARTER", "RANGE")
COMPARISONS = ("PY", "Budget", "FC1", "FC2", "FC3", "LatestFC")


# ------------------------------------------------------------------------------------------
# Calendar helpers
# ------------------------------------------------------------------------------------------
def mk(year: int, month: int) -> int:
    return year * 100 + month


def ym(key: int) -> tuple[int, int]:
    return key // 100, key % 100


def add_months(key: int, n: int) -> int:
    y, m = ym(key)
    idx = y * 12 + (m - 1) + n
    return mk(idx // 12, idx % 12 + 1)


def month_range(start_key: int, end_key: int) -> list[int]:
    out, k = [], start_key
    while k <= end_key:
        out.append(k)
        k = add_months(k, 1)
    return out


def month_label(key: int) -> str:
    y, m = ym(key)
    return f"{MONTH_NAMES[m - 1]} {y}"


def close_date(year: int, month: int) -> date:
    day = int(settings()["close_day_of_next_month"])
    return date(year + (month == 12), month % 12 + 1, day)


def is_closed(key: int, as_of: date | None = None) -> bool:
    as_of = as_of or as_of_date()
    y, m = ym(key)
    return close_date(y, m) <= as_of


def last_closed_month(as_of: date | None = None) -> int:
    as_of = as_of or as_of_date()
    key = mk(as_of.year, as_of.month)
    for _ in range(36):
        key = add_months(key, -1)
        if is_closed(key, as_of):
            return key
    raise ValueError("no closed month")


def data_bounds() -> tuple[int, int]:
    s = settings()
    return mk(int(s["first_year"]), 1), mk(int(s["last_year"]), 12)


# ------------------------------------------------------------------------------------------
# Periods
# ------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Period:
    period_type: str            # MONTH | QTD | YTD | R12M | FY | QUARTER | RANGE
    end_key: int                # last month of the period
    start_key: int | None = None

    def months(self) -> list[int]:
        y, m = ym(self.end_key)
        if self.period_type == "MONTH":
            return [self.end_key]
        if self.period_type == "YTD":
            return month_range(mk(y, 1), self.end_key)
        if self.period_type == "QTD":
            return month_range(mk(y, (m - 1) // 3 * 3 + 1), self.end_key)
        if self.period_type == "QUARTER":
            return month_range(add_months(self.end_key, -2), self.end_key)
        if self.period_type == "FY":
            return month_range(mk(y, 1), mk(y, 12))
        if self.period_type == "R12M":
            return month_range(add_months(self.end_key, -11), self.end_key)
        if self.period_type == "RANGE":
            return month_range(self.start_key or self.end_key, self.end_key)
        raise ValueError(f"unknown period type {self.period_type}")

    @property
    def year(self) -> int:
        return ym(self.end_key)[0]

    def shift_years(self, n: int) -> "Period":
        return Period(self.period_type, add_months(self.end_key, 12 * n),
                      add_months(self.start_key, 12 * n) if self.start_key else None)

    def truncate(self, last_key: int) -> "Period":
        """Restrict to months <= last_key (keeps the period type for labelling)."""
        if self.end_key <= last_key:
            return self
        months = [k for k in self.months() if k <= last_key]
        if not months:
            return self
        return Period("RANGE", months[-1], months[0]) if self.period_type != "YTD" else Period("YTD", months[-1])

    def label(self) -> str:
        y, m = ym(self.end_key)
        if self.period_type == "MONTH":
            return month_label(self.end_key)
        if self.period_type == "YTD":
            return f"YTD {MONTH_NAMES[m - 1]} {y}"
        if self.period_type == "QTD":
            return f"QTD {MONTH_NAMES[m - 1]} {y}"
        if self.period_type == "QUARTER":
            return f"Q{(m - 1) // 3 + 1} {y}"
        if self.period_type == "FY":
            return f"FY {y}"
        if self.period_type == "R12M":
            return f"R12M to {MONTH_NAMES[m - 1]} {y}"
        months = self.months()
        return f"{month_label(months[0])} - {month_label(months[-1])}"

    def to_dict(self) -> dict:
        months = self.months()
        return {"type": self.period_type, "label": self.label(), "start": months[0], "end": months[-1]}


def default_period(as_of: date | None = None) -> Period:
    return Period("YTD", last_closed_month(as_of))


# Regexes for period expressions (applied to lower-cased text)
_MONTHS_RX = "|".join(sorted(MONTH_LOOKUP, key=len, reverse=True))
RX = {
    "iso_range": re.compile(r"\b(20\d\d)[-/](0?[1-9]|1[0-2])\s*(?:to|until|through|-|–)\s*(20\d\d)[-/](0?[1-9]|1[0-2])\b"),
    "month_range": re.compile(r"\b(?:from\s+|between\s+)?(" + _MONTHS_RX + r")\.?\s*'?(20\d\d|\d\d)\s*(?:-|–|to|until|through|and)\s*("
                              + _MONTHS_RX + r")\.?\s*'?(20\d\d|\d\d)\b"),
    "month_range_1y": re.compile(r"\b(?:from\s+|between\s+)?(" + _MONTHS_RX + r")\.?\s*(?:-|–|to|until|through|and)\s*("
                                 + _MONTHS_RX + r")\.?\s*'?(20\d\d|\d\d)\b"),
    "since": re.compile(r"\bsince\s+(?:(" + _MONTHS_RX + r")\s+)?(20\d\d)\b"),
    "from_to": re.compile(r"\b(?:from\s+)?(20\d\d)\s*(?:-|to|until|through)\s*(20\d\d)\b"),
    "half": re.compile(r"\bh([12])\s*'?(20\d\d|\d\d)?\b"),
    "quarter": re.compile(r"\bq([1-4])\s*'?(20\d\d|\d\d)?\b"),
    "quarter2": re.compile(r"\b(20\d\d)\s*q([1-4])\b"),
    "ytd": re.compile(r"\b(ytd|year[- ]to[- ]date)\b(?:\s+(" + _MONTHS_RX + r"))?(?:\s+(20\d\d))?"),
    "qtd": re.compile(r"\b(qtd|quarter[- ]to[- ]date)\b"),
    "r12": re.compile(r"\b(r12m|rolling\s*12(?:\s*months)?|ltm|last\s+(?:twelve|12)\s+months|trailing\s+(?:twelve|12)(?:\s*months)?)\b"),
    "fy": re.compile(r"\b(?:fy\s*'?(20\d\d|\d\d)|full[- ]year\s+(20\d\d)|(20\d\d)\s+full[- ]year)\b"),
    "fy_bare": re.compile(r"\b(full[- ]year|fy)\b"),
    "month_year": re.compile(r"\b(" + _MONTHS_RX + r")\.?\s*'?(20\d\d|\d\d)\b"),
    "iso_month": re.compile(r"\b(20\d\d)[-/](0?[1-9]|1[0-2])\b"),
    "key_month": re.compile(r"\b(20\d\d)(0[1-9]|1[0-2])\b"),
    "month_only": re.compile(r"\b(?:in\s+)?(" + _MONTHS_RX + r")\b"),
    "last_month": re.compile(r"\b(last|previous|prior)\s+month\b"),
    "this_month": re.compile(r"\b(this|current)\s+month\b"),
    "this_year": re.compile(r"\b(this|current)\s+year\b"),
    "last_year": re.compile(r"\b(last|previous|prior)\s+year\b"),
    "year": re.compile(r"\b(20\d\d)\b"),
}


def _year(tok: str | None, default: int) -> int:
    if not tok:
        return default
    tok = tok.strip("'")
    return 2000 + int(tok) if len(tok) == 2 else int(tok)


@dataclass
class PeriodParse:
    period: Period | None = None
    matched: list[str] = field(default_factory=list)
    is_range: bool = False      # trend-style range (since / from-to)


def parse_period_text(text: str, as_of: date | None = None) -> PeriodParse:
    """Find a period expression in free text. Returns PeriodParse(period=None) if none found."""
    as_of = as_of or as_of_date()
    t = (text or "").lower()
    last = last_closed_month(as_of)
    ly, lm = ym(last)
    out = PeriodParse()

    def done(p: Period, m: re.Match, is_range=False) -> PeriodParse:
        out.period, out.is_range = p, is_range
        out.matched.append(m.group(0))
        return out

    if m := RX["iso_range"].search(t):
        a, b = mk(int(m.group(1)), int(m.group(2))), mk(int(m.group(3)), int(m.group(4)))
        if a <= b:
            return done(Period("RANGE", b, a), m)
    if m := RX["month_range"].search(t):
        a = mk(_year(m.group(2), ly), MONTH_LOOKUP[m.group(1)])
        b = mk(_year(m.group(4), ly), MONTH_LOOKUP[m.group(3)])
        if a <= b:
            return done(Period("RANGE", b, a), m)
    if m := RX["month_range_1y"].search(t):
        y = _year(m.group(3), ly)
        a, b = mk(y, MONTH_LOOKUP[m.group(1)]), mk(y, MONTH_LOOKUP[m.group(2)])
        if a <= b:
            return done(Period("RANGE", b, a), m)
    if m := RX["since"].search(t):
        mon = MONTH_LOOKUP.get(m.group(1) or "", 1)
        return done(Period("RANGE", last, mk(int(m.group(2)), mon)), m, True)
    if m := RX["from_to"].search(t):
        y1, y2 = int(m.group(1)), int(m.group(2))
        if y1 <= y2:
            return done(Period("RANGE", min(mk(y2, 12), last), mk(y1, 1)), m, True)
    if m := RX["r12"].search(t):
        return done(Period("R12M", last), m)
    if m := RX["ytd"].search(t):
        y = _year(m.group(3), ly)
        mon = MONTH_LOOKUP.get(m.group(2) or "", lm if y >= ly else lm)
        end = min(mk(y, mon), last) if y >= ly else mk(y, mon)
        return done(Period("YTD", end), m)
    if m := RX["qtd"].search(t):
        return done(Period("QTD", last), m)
    if m := RX["quarter"].search(t) or RX["quarter2"].search(t):
        if m.re is RX["quarter2"]:
            q, y = int(m.group(2)), int(m.group(1))
        else:
            q, y = int(m.group(1)), _year(m.group(2), ly)
        return done(Period("QUARTER", mk(y, q * 3)), m)
    if m := RX["half"].search(t):
        h, y = int(m.group(1)), _year(m.group(2), ly)
        return done(Period("RANGE", mk(y, 6 * h), mk(y, 6 * h - 5)), m)
    if m := RX["fy"].search(t):
        y = _year(m.group(1) or m.group(2) or m.group(3), ly)
        return done(Period("FY", mk(y, 12)), m)
    if m := RX["month_year"].search(t):
        return done(Period("MONTH", mk(_year(m.group(2), ly), MONTH_LOOKUP[m.group(1)])), m)
    if m := RX["iso_month"].search(t):
        return done(Period("MONTH", mk(int(m.group(1)), int(m.group(2)))), m)
    if m := RX["key_month"].search(t):
        return done(Period("MONTH", mk(int(m.group(1)), int(m.group(2)))), m)
    if m := RX["last_month"].search(t) or RX["this_month"].search(t):
        return done(Period("MONTH", last), m)
    if m := RX["this_year"].search(t):
        return done(Period("YTD", last), m)
    if m := RX["fy_bare"].search(t):
        return done(Period("FY", mk(ly, 12)), m)
    if m := RX["year"].search(t):
        y = int(m.group(1))
        return done(Period("YTD", last) if y == ly else Period("FY", mk(y, 12)), m)
    if m := RX["last_year"].search(t):
        return done(Period("FY", mk(ly - 1, 12)), m)
    if m := RX["month_only"].search(t):
        mon = MONTH_LOOKUP[m.group(1)]
        if m.group(1) == "may" and not re.search(r"\bin\s+may\b", t):
            return out          # "may" is usually the verb
        y = ly if mk(ly, mon) <= last else ly - 1
        return done(Period("MONTH", mk(y, mon)), m)
    return out


def parse_period(period: str | None = None, period_type: str | None = None,
                 as_of: date | None = None) -> Period:
    """Parse a tool-style period argument. Falls back to YTD of the last closed month."""
    as_of = as_of or as_of_date()
    last = last_closed_month(as_of)
    ptype = (period_type or "").strip().upper() or None
    if ptype in ("FULL_YEAR", "FULLYEAR", "YEAR"):
        ptype = "FY"
    if ptype in ("ROLLING12", "LTM", "ROLLING_12M"):
        ptype = "R12M"
    if ptype in ("Q", "QTR"):
        ptype = "QUARTER"
    if ptype not in PERIOD_TYPES:
        ptype = None
    parsed = parse_period_text(period or "", as_of).period if period else None
    if parsed is None:
        return Period(ptype or "YTD", last) if ptype != "FY" else Period("FY", mk(ym(last)[0], 12))
    if ptype and ptype != parsed.period_type and parsed.period_type in ("MONTH", "FY", "YTD"):
        y, m = ym(parsed.end_key)
        if ptype == "FY":
            return Period("FY", mk(y, 12))
        if ptype in ("YTD", "QTD", "R12M", "MONTH"):
            end = parsed.end_key if parsed.period_type == "MONTH" else min(mk(y, ym(last)[1]), last) if y == ym(last)[0] else mk(y, ym(last)[1])
            if parsed.period_type == "FY" and y < ym(last)[0] and ptype == "YTD":
                end = mk(y, ym(last)[1])
            return Period(ptype, end)
        if ptype == "QUARTER":
            return Period("QUARTER", mk(y, ((m - 1) // 3 + 1) * 3))
    return parsed


# ------------------------------------------------------------------------------------------
# Versions & comparisons
# ------------------------------------------------------------------------------------------
def forecast_available(fc: str, year: int, as_of: date | None = None) -> bool:
    k = forecast_actual_months().get(fc)
    if k is None:
        return False
    return close_date(year, k) <= (as_of or as_of_date())


def latest_forecast(year: int, as_of: date | None = None) -> str | None:
    """Highest FC available for `year` as of the as-of date (FC3 > FC2 > FC1)."""
    best = None
    for fc in sorted(forecast_actual_months(), key=lambda f: forecast_actual_months()[f]):
        if forecast_available(fc, year, as_of):
            best = fc
    return best


def normalize_version(v: str | None) -> str | None:
    if not v:
        return None
    s = str(v).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    mapping = {
        "actual": "Actual", "actuals": "Actual", "act": "Actual", "cy": "Actual",
        "budget": "Budget", "bud": "Budget", "bgt": "Budget", "plan": "Budget",
        "fc1": "FC1", "forecast1": "FC1", "fc2": "FC2", "forecast2": "FC2",
        "fc3": "FC3", "forecast3": "FC3",
        "latestfc": "LatestFC", "latestforecast": "LatestFC", "forecast": "LatestFC", "fc": "LatestFC",
        "currentforecast": "LatestFC", "outlook": "LatestFC", "le": "LatestFC",
        "py": "PY", "prioryear": "PY", "lastyear": "PY", "previousyear": "PY", "ly": "PY",
        "landing": "Landing", "currentmonthlanding": "Landing", "monthendlanding": "Landing", "lnd": "Landing",
    }
    return mapping.get(s)


@dataclass(frozen=True)
class Series:
    """One column of numbers: a version over a set of months."""
    label: str          # e.g. "Actual", "PY", "Budget", "FC2", "Landing"
    version: str        # database version name ("LANDING" = stored landing P50, open month only)
    period: Period
    months: tuple[int, ...]


def open_month(as_of: date | None = None) -> int:
    """The month after the last closed month: the current-month landing is computed for it."""
    return add_months(last_closed_month(as_of), 1)


def resolve_series(primary_version: str, period: Period, comparisons: list[str],
                   as_of: date | None = None) -> tuple[list[Series], list[str]]:
    """Build the primary series plus comparison series (like-for-like), with notes."""
    as_of = as_of or as_of_date()
    last = last_closed_month(as_of)
    notes: list[str] = []
    primary_version = normalize_version(primary_version) or "Actual"
    if primary_version == "LatestFC":
        primary_version = latest_forecast(period.year, as_of) or "Budget"
    eff = period
    if primary_version == "Landing":
        eff = Period("MONTH", open_month(as_of))
        if period.months() != eff.months():
            notes.append(f"The landing exists for the open month only ({month_label(eff.end_key)}); "
                         f"all columns cover {eff.label()}.")
    if primary_version == "Actual" and period.end_key > last:
        eff = period.truncate(last)
        if eff.months()[-1] <= last and eff != period:
            notes.append(f"{period.label()} is not complete: Actuals are available to "
                         f"{month_label(last)}, so all columns cover {eff.label()} (like-for-like).")
    db_version = "LANDING" if primary_version == "Landing" else primary_version
    series = [Series(primary_version, db_version, eff, tuple(eff.months()))]
    seen = {primary_version}
    for c in comparisons:
        cn = normalize_version(c) or c
        if cn == "PY":
            p = eff.shift_years(-1)
            if "PY" not in seen:
                series.append(Series("PY", "Actual", p, tuple(p.months())))
                seen.add("PY")
            continue
        if cn == "Landing":
            if eff.months() == [open_month(as_of)] and "Landing" not in seen:
                series.append(Series("Landing", "LANDING", eff, tuple(eff.months())))
                seen.add("Landing")
            elif "Landing" not in seen:
                notes.append(f"The landing exists for {month_label(open_month(as_of))} only.")
            continue
        if cn == "LatestFC":
            fc = latest_forecast(eff.year, as_of)
            if not fc:
                notes.append(f"No forecast is available yet for {eff.year} as of {as_of.isoformat()}.")
                continue
            cn = fc
            notes.append(f"Latest forecast for {eff.year} as of {as_of.isoformat()} is {fc}.")
        if cn in ("FC1", "FC2", "FC3") and not forecast_available(cn, eff.year, as_of):
            notes.append(f"{cn} {eff.year} is not available as of {as_of.isoformat()}.")
            continue
        if cn in ("Budget", "FC1", "FC2", "FC3", "Actual") and cn not in seen:
            series.append(Series(cn, cn, eff, tuple(eff.months())))
            seen.add(cn)
    return series, notes


# ------------------------------------------------------------------------------------------
# Variance & favourability
# ------------------------------------------------------------------------------------------
def variance(current: float | None, comparison: float | None) -> tuple[float | None, float | None]:
    """Absolute and relative variance (current - comparison). % is vs |comparison|."""
    if current is None or comparison is None:
        return None, None
    diff = current - comparison
    pct = diff / abs(comparison) if comparison not in (0, 0.0) else None
    return diff, pct


def is_favorable(diff: float | None, direction: str) -> bool | None:
    """direction 'up' = higher is better (revenue/profit), 'down' = lower is better (costs)."""
    if diff is None or direction not in ("up", "down") or abs(diff) < 1e-9:
        return None
    return diff > 0 if direction == "up" else diff < 0
