"""Finance number formatting shared by facts, tables and charts (currency from settings.yaml)."""
from __future__ import annotations

import math

from app.config import settings

CUR = settings().get("currency", "USD")
UNITS = {"k": 1e3, "M": 1e6}


def _bad(x) -> bool:
    return x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


def unit_label(units: str) -> str:
    return f"{CUR} {units}"


def plural(word: str) -> str:
    """English plural of an org level / group label: Country -> Countries, business -> businesses, BU -> BUs."""
    w = str(word)
    if w.isupper():
        return w + "s"
    if w.endswith("y") and len(w) > 1 and w[-2].lower() not in "aeiou":
        return w[:-1] + "ies"
    if w.endswith(("s", "x", "ch", "sh")):
        return w + "es"
    return w + "s"


def eur(x: float | None, units: str = "auto", decimals: int | None = None, signed: bool = False) -> str:
    """Money in finance shorthand: USD 23.1M / USD 845k / USD 512 (auto) or fixed k / M units.
    (Name kept for backwards compatibility; the currency comes from settings.yaml.)"""
    if _bad(x):
        return "n/a"
    sign = "+" if signed and x > 0 else ("-" if x < 0 else "")
    v = abs(float(x))
    if units == "auto":
        if v >= 1e9:
            body = f"{v / 1e9:,.{2 if decimals is None else decimals}f}bn"
        elif v >= 1e6:
            body = f"{v / 1e6:,.{1 if decimals is None else decimals}f}M"
        elif v >= 1e3:
            body = f"{v / 1e3:,.{0 if decimals is None else decimals}f}k"
        else:
            body = f"{v:,.{0 if decimals is None else decimals}f}"
    else:
        scale = UNITS.get(units, 1e3)
        d = (1 if units == "M" else 0) if decimals is None else decimals
        body = f"{v / scale:,.{d}f}{units}"
    return f"{sign}{CUR} {body}"


money = eur


def pct(x: float | None, decimals: int = 1, signed: bool = False) -> str:
    if _bad(x):
        return "n/a"
    return f"{x * 100:+.{decimals}f}%" if signed else f"{x * 100:.{decimals}f}%"


def pp(x: float | None, decimals: int = 1) -> str:
    if _bad(x):
        return "n/a"
    return f"{x * 100:+.{decimals}f} pp"


def num(x: float | None, decimals: int = 0) -> str:
    if _bad(x):
        return "n/a"
    return f"{x:,.{decimals}f}"


def rate(x: float | None) -> str:
    """Small currency amounts such as production per hour: USD 136.4"""
    if _bad(x):
        return "n/a"
    return f"{CUR} {x:,.1f}" if abs(x) < 1000 else eur(x)


def value(x: float | None, fmt: str, signed: bool = False) -> str:
    if fmt == "pct":
        return pct(x, signed=signed)
    if fmt == "pp":
        return pp(x)
    if fmt == "num":
        return num(x, 1 if (x is not None and not _bad(x) and abs(x) < 100) else 0)
    if fmt == "eur" and x is not None and not _bad(x) and abs(x) < 1000 and not signed:
        return rate(x)
    return eur(x, signed=signed)


def table_number(x: float | None, units: str = "k") -> str:
    """Table cell: thousands separators, negatives in parentheses."""
    if _bad(x):
        return ""
    scale = UNITS.get(units, 1e3)
    v = float(x) / scale
    d = 1 if units == "M" else 0
    if round(v, d) == 0:
        return f"{0:,.{d}f}"
    s = f"{abs(v):,.{d}f}"
    return f"({s})" if v < 0 else s


def table_money_small(x: float | None) -> str:
    """Per-hour / per-FTE amounts are shown in full units."""
    if _bad(x):
        return ""
    s = f"{abs(x):,.1f}" if abs(x) < 1000 else f"{abs(x):,.0f}"
    return f"({s})" if x < 0 else s


def table_pct(x: float | None, decimals: int = 1) -> str:
    if _bad(x):
        return ""
    v = x * 100
    s = f"{abs(v):.{decimals}f}%"
    return f"({s})" if v < 0 and round(v, decimals) != 0 else s


def table_pp(x: float | None, decimals: int = 1) -> str:
    if _bad(x):
        return ""
    v = x * 100
    if round(v, decimals) == 0:
        return f"{0:.{decimals}f} pp"
    return f"({abs(v):.{decimals}f} pp)" if v < 0 else f"{v:.{decimals}f} pp"
