#!/usr/bin/env python
"""Generate the synthetic RL Certification & Inspection general-ledger (GL) P&L (Americas), seeded.

Generic monthly management P&L (line keys are internal; labels carry no codes):
  Billing, WIP & deferred income, REVENUE, Intragroup revenue, Intragroup subcontracting,
  PRODUCTION, Personnel costs (direct / indirect staff), External subcontracting, Other costs,
  Functional cost recharges, GROSS PROFIT, Functional costs, OPERATING PROFIT, Other operating
  expenses, EBIT, Financial result, Income taxes, NET INCOME  (+ FTE / headcount / hours statistics)
plus fictional employee-level data (codes only, no names) whose monthly hours, FTE and headcount add
up exactly to the BU statistics.

Billing follows a per-BU pattern (steady, quarter-end loaded, year-end loaded, seasonal with a March peak
and an August dip, or lumpy project billing) whose intensity drifts mildly over the years, scaled by the
month's working days (public holidays per country from the `holidays` package). Budgets and forecasts
carry a BU-specific bias (optimistic or conservative planners); forecasts know the expected path of the
business only partly and never the monthly noise.

Writes one Parquet file per table into data/, plus
  data/control_totals.parquet        intended subtotals per BU x month x version (scripts/reconcile.py)
  data/stories.json                  numbers behind the injected demo stories (docs/demo_stories.md)
  data/eval_truth_open_month.parquet true month-end values of the open month (tests and backtests ONLY;
                                     never loaded into the database or read by the app)
  data/eval_truth_patterns.parquet   generator billing pattern and forecast bias per BU (tests ONLY)

Storage rule: amounts are SIGNED (revenue +, cost -) and only LEAF accounts are stored.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import holidays
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402

DATA = ROOT / "data"
CFG = settings()
FIRST_YEAR, LAST_YEAR = int(CFG["first_year"]), int(CFG["last_year"])
SIM_START = FIRST_YEAR - 1                      # one extra year simulated as budget base
N_SIM = (LAST_YEAR - SIM_START + 1) * 12
N_OUT = (LAST_YEAR - FIRST_YEAR + 1) * 12
AVAIL_HOURS = float(CFG["available_hours_per_direct_fte_month"])
AS_OF = date.fromisoformat(str(CFG["as_of_date"]))
CLOSE_DAY = int(CFG["close_day_of_next_month"])

# --------------------------------------------------------------------------------------
# Organisation: Americas
# --------------------------------------------------------------------------------------
COUNTRIES = {
    #                code  region                     scale cost/FTE  tax    fx vol  fx bias hemi
    "United States": ("US", "US & Canada",              2.4, 98000, 0.25,  0.000, 0.0,   "N"),
    "Canada":        ("CA", "US & Canada",              1.3, 84000, 0.265, 0.002, 0.0,   "N"),
    "Mexico":        ("MX", "Mexico",                   1.2, 29000, 0.30,  0.006, 0.0,   "N"),
    "Colombia":      ("CO", "Northern South America",   0.7, 21000, 0.35,  0.006, 0.0,   "S"),
    "Peru":          ("PE", "Northern South America",   0.7, 20000, 0.295, 0.004, 0.0,   "S"),
    "Ecuador":       ("EC", "Northern South America",   0.45, 19000, 0.25, 0.000, 0.0,   "S"),
    "Argentina":     ("AR", "Southern South America",   0.7, 23000, 0.35,  0.020, -0.006, "S"),
    "Chile":         ("CL", "Southern South America",   0.9, 35000, 0.27,  0.005, 0.0,   "S"),
    "Brazil":        ("BR", "BPU",                      1.3, 31000, 0.34,  0.008, 0.0,   "S"),
    "Paraguay":      ("PY", "BPU",                      0.3, 16000, 0.10,  0.004, 0.0,   "S"),
    "Uruguay":       ("UY", "BPU",                      0.35, 33000, 0.25, 0.004, 0.0,   "S"),
}
CITIES = {
    "United States": [("Houston", "HOU"), ("Chicago", "CHI"), ("Los Angeles", "LAX"), ("New York", "NYC"),
                      ("Atlanta", "ATL"), ("Denver", "DEN"), ("Seattle", "SEA")],
    "Canada": [("Toronto", "TOR"), ("Montreal", "MTL"), ("Calgary", "CAL"), ("Vancouver", "VAN")],
    "Mexico": [("Mexico City", "MEX"), ("Monterrey", "MTY"), ("Guadalajara", "GDL"), ("Queretaro", "QRO")],
    "Colombia": [("Bogota", "BOG"), ("Medellin", "MDE"), ("Barranquilla", "BAQ")],
    "Peru": [("Lima", "LIM"), ("Arequipa", "AQP")],
    "Ecuador": [("Quito", "UIO"), ("Guayaquil", "GYE")],
    "Argentina": [("Buenos Aires", "BUE"), ("Cordoba", "COR"), ("Neuquen", "NQN")],
    "Chile": [("Calama", "CJC"), ("Antofagasta", "ANF"), ("Concepcion", "CCP")],
    "Brazil": [("Sao Paulo", "SAO"), ("Rio de Janeiro", "RIO"), ("Belo Horizonte", "BHZ"), ("Curitiba", "CWB")],
    "Paraguay": [("Asuncion", "ASU")],
    "Uruguay": [("Montevideo", "MVD")],
}
PRODUCT_LINES = {
    "Buildings & Infrastructure":     {"code": "BNI", "short": "B&I", "type": "infrastructure", "growth": 0.05, "scale": 1.2},
    "Industry & Energy":              {"code": "IND", "short": "Industry", "type": "industry", "growth": 0.04, "scale": 1.3},
    "Power & Utilities":              {"code": "PWR", "short": "Power", "type": "industry", "growth": 0.06, "scale": 0.9},
    "Elevators & Pressure Vessels":   {"code": "EPV", "short": "Elevators & PV", "type": "inspection", "growth": 0.03, "scale": 0.8},
    "Environmental Lab Testing":      {"code": "ENV", "short": "Env Lab", "type": "laboratory", "growth": 0.06, "scale": 0.9},
    "Consumer Products":              {"code": "CPS", "short": "Consumer Products", "type": "laboratory", "growth": 0.05, "scale": 0.8},
    "Certification & Sustainability": {"code": "CER", "short": "Certification", "type": "certification", "growth": 0.08, "scale": 0.5},
    "Metals & Minerals":              {"code": "MMI", "short": "M&M", "type": "laboratory", "growth": 0.05, "scale": 1.0},
}
# Environmental Lab Testing exists only in Canada (main business) and as one small US unit.
COUNTRY_PLS = {
    "United States": ["Buildings & Infrastructure", "Industry & Energy", "Power & Utilities",
                      "Elevators & Pressure Vessels", "Environmental Lab Testing", "Consumer Products",
                      "Certification & Sustainability"],
    "Canada": ["Buildings & Infrastructure", "Industry & Energy", "Power & Utilities", "Environmental Lab Testing",
               "Metals & Minerals", "Certification & Sustainability"],
    "Mexico": ["Buildings & Infrastructure", "Industry & Energy", "Consumer Products", "Elevators & Pressure Vessels",
               "Metals & Minerals", "Certification & Sustainability"],
    "Colombia": ["Buildings & Infrastructure", "Industry & Energy", "Certification & Sustainability"],
    "Peru": ["Metals & Minerals", "Buildings & Infrastructure", "Industry & Energy"],
    "Ecuador": ["Industry & Energy", "Buildings & Infrastructure"],
    "Argentina": ["Industry & Energy", "Buildings & Infrastructure", "Elevators & Pressure Vessels"],
    "Chile": ["Metals & Minerals", "Industry & Energy", "Buildings & Infrastructure"],
    "Brazil": ["Buildings & Infrastructure", "Industry & Energy", "Elevators & Pressure Vessels", "Metals & Minerals",
               "Certification & Sustainability", "Power & Utilities"],
    "Paraguay": ["Buildings & Infrastructure", "Certification & Sustainability"],
    "Uruguay": ["Buildings & Infrastructure", "Certification & Sustainability"],
}
# Size overrides per (country, product line): number of cities, max units per city, scale factor
PL_SIZE = {
    ("United States", "Environmental Lab Testing"): {"cities": 1, "max_units": 1, "scale": 0.35},
    ("Canada", "Environmental Lab Testing"): {"cities": 4, "max_units": 2, "scale": 1.25},
}
REGION_ORDER = ["US & Canada", "Mexico", "Northern South America", "Southern South America", "BPU"]
STORY = {"a": ("United States", "Elevators & Pressure Vessels"), "b": ("Canada", "Environmental Lab Testing"),
         "c": ("Mexico", "Buildings & Infrastructure"), "d": ("Chile", "Metals & Minerals"),
         "e": ("Canada", "Power & Utilities")}
# Landing demo stories (current-month landing, docs/demo_stories.md)
LANDING_STORY = {
    "momentum": ("United States", "Industry & Energy"),       # YoY momentum: lands above budget
    "optimistic_forecast": ("Canada", "Industry & Energy"),   # optimistic planners: bias correction lands below FC
    "shortfall": ("Mexico", "Consumer Products"),             # genuine shortfall from a downward trend
    "lumpy": ("United States", "Buildings & Infrastructure"),  # lumpy project billing: wide P10-P90
}

# Billing pattern per BU: probabilities by product line (BUs of the landing stories are fixed below)
PATTERNS = ("steady", "quarter_end", "year_end", "seasonal", "lumpy")
PATTERN_MIX = {
    "Elevators & Pressure Vessels":   {"steady": 0.70, "quarter_end": 0.30},
    "Buildings & Infrastructure":     {"lumpy": 0.55, "quarter_end": 0.30, "steady": 0.15},
    "Industry & Energy":              {"quarter_end": 0.50, "steady": 0.30, "lumpy": 0.20},
    "Power & Utilities":              {"seasonal": 0.50, "quarter_end": 0.30, "steady": 0.20},
    "Environmental Lab Testing":      {"seasonal": 0.70, "steady": 0.30},
    "Consumer Products":              {"seasonal": 0.55, "year_end": 0.45},
    "Certification & Sustainability": {"year_end": 0.70, "quarter_end": 0.30},
    "Metals & Minerals":              {"steady": 0.50, "lumpy": 0.25, "quarter_end": 0.25},
}
# ASSUMPTION: billing is partly proportional to working days (elasticity 0.7)
WD_ELASTICITY = 0.7

# Cost profiles as share of production by business type (centre values; BUs vary around them)
COST_PROFILES = {
    "inspection":     {"personnel": 0.600, "share_7a": 0.80, "subc": 0.065, "other": 0.130, "functional": 0.105},
    "infrastructure": {"personnel": 0.500, "share_7a": 0.78, "subc": 0.180, "other": 0.120, "functional": 0.105},
    "industry":       {"personnel": 0.550, "share_7a": 0.80, "subc": 0.110, "other": 0.140, "functional": 0.105},
    "laboratory":     {"personnel": 0.460, "share_7a": 0.75, "subc": 0.040, "other": 0.300, "functional": 0.105},
    "certification":  {"personnel": 0.500, "share_7a": 0.72, "subc": 0.090, "other": 0.080, "functional": 0.110},
}
OTHER_MIX = {
    "inspection":     {"9.1": 0.16, "9.2": 0.18, "9.3": 0.15, "9.4": 0.16, "9.5": 0.15, "9.6": 0.10, "9.7": 0.02, "9.8": 0.03, "9.9": 0.05},
    "infrastructure": {"9.1": 0.24, "9.2": 0.12, "9.3": 0.14, "9.4": 0.16, "9.5": 0.14, "9.6": 0.08, "9.7": 0.03, "9.8": 0.04, "9.9": 0.05},
    "industry":       {"9.1": 0.20, "9.2": 0.10, "9.3": 0.12, "9.4": 0.24, "9.5": 0.13, "9.6": 0.08, "9.7": 0.03, "9.8": 0.04, "9.9": 0.06},
    "laboratory":     {"9.1": 0.06, "9.2": 0.15, "9.3": 0.24, "9.4": 0.04, "9.5": 0.03, "9.6": 0.07, "9.7": 0.21, "9.8": 0.03, "9.9": 0.17},
    "certification":  {"9.1": 0.18, "9.2": 0.20, "9.3": 0.08, "9.4": 0.24, "9.5": 0.05, "9.6": 0.14, "9.7": 0.01, "9.8": 0.04, "9.9": 0.06},
}
VARIABLE_OTHER = {"9.1", "9.4", "9.5", "9.7", "9.9"}

# Seasonality. North (US, Canada, Mexico): March peak, August + December dips.
# South America: January/February summer + carnival dips, July winter break, December dip.
SEASON = {
    "N": np.array([0.93, 0.98, 1.10, 1.01, 1.03, 1.05, 0.99, 0.80, 1.05, 1.08, 1.06, 0.92]),
    "S": np.array([0.84, 0.88, 1.08, 1.06, 1.06, 1.04, 0.95, 1.03, 1.04, 1.06, 1.05, 0.91]),
}
SEASON = {k: v / v.mean() for k, v in SEASON.items()}
AVAIL_SEASON = {
    "N": np.array([0.97, 1.0, 1.02, 1.0, 1.0, 1.0, 0.95, 0.90, 1.0, 1.02, 1.0, 0.86]),
    "S": np.array([0.86, 0.90, 1.02, 1.0, 1.0, 1.0, 0.93, 1.0, 1.0, 1.02, 1.0, 0.90]),
}
OT_SEASON = np.array([0.9, 0.95, 1.2, 1.0, 1.0, 1.05, 0.9, 0.8, 1.05, 1.2, 1.15, 0.8])
PERS_SEASON = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.01, 1.0, 0.99, 1.0, 1.0, 1.0, 1.02])
PERS_SEASON = PERS_SEASON / PERS_SEASON.mean()
WIP_PROFILE = np.array([0.035, 0.030, 0.020, 0.025, 0.020, 0.015, 0.020, 0.030, 0.010, -0.010, -0.020])
# Deferred income: annual fees billed in advance in January, released through the year
UI_PROFILE = np.array([-0.050, 0.006, 0.006, 0.005, 0.005, 0.005, 0.004, 0.004, 0.004, 0.004, 0.004, 0.003])

# --------------------------------------------------------------------------------------
# Chart of accounts (general ledger). Line keys are internal (14-16 unused); labels carry no codes.
# (account_id, line_no, l1_name, l2_code, l2_name, l3_code, l3_name, is_leaf, is_subtotal,
#  natural_sign, display_order, favorable_direction)
# --------------------------------------------------------------------------------------
ACCOUNTS = [
    (100, 1, "Billing", "1", "Billing", "1", "Billing", 0, 0, 1, 100, "up"),
    (101, 1, "Billing", "1", "Billing", "1.1", "External billing", 1, 0, 1, 101, "up"),
    (102, 1, "Billing", "1", "Billing", "1.2", "Credit notes", 1, 0, 1, 102, "up"),
    (200, 2, "WIP & deferred income", "2", "WIP & deferred income", "2", "WIP & deferred income", 0, 0, 1, 200, "up"),
    (201, 2, "WIP & deferred income", "2", "WIP & deferred income", "2.1", "WIP change", 1, 0, 1, 201, "up"),
    (202, 2, "WIP & deferred income", "2", "WIP & deferred income", "2.2", "Deferred income change", 1, 0, 1, 202, "up"),
    (300, 3, "Revenue", "3", "Revenue", "3", "Revenue", 0, 1, 1, 300, "up"),
    (400, 4, "Intragroup revenue", "4", "Intragroup revenue", "4", "Intragroup revenue", 0, 0, 1, 400, "up"),
    (401, 4, "Intragroup revenue", "4", "Intragroup revenue", "4.1", "Intragroup revenue", 1, 0, 1, 401, "up"),
    (500, 5, "Intragroup subcontracting", "5", "Intragroup subcontracting", "5", "Intragroup subcontracting", 0, 0, -1, 500, "down"),
    (501, 5, "Intragroup subcontracting", "5", "Intragroup subcontracting", "5.1", "Intragroup subcontracting", 1, 0, -1, 501, "down"),
    (600, 6, "Production", "6", "Production", "6", "Production", 0, 1, 1, 600, "up"),
    (700, 7, "Personnel costs", "7", "Personnel costs", "7", "Personnel costs", 0, 0, -1, 700, "down"),
    (710, 7, "Personnel costs", "7A", "Direct staff costs", "7A", "Direct staff costs", 0, 0, -1, 710, "down"),
    (711, 7, "Personnel costs", "7A", "Direct staff costs", "7A1", "Direct staff salaries", 1, 0, -1, 711, "down"),
    (712, 7, "Personnel costs", "7A", "Direct staff costs", "7A2", "Direct staff bonus", 1, 0, -1, 712, "down"),
    (713, 7, "Personnel costs", "7A", "Direct staff costs", "7A3", "Direct staff overtime", 1, 0, -1, 713, "down"),
    (714, 7, "Personnel costs", "7A", "Direct staff costs", "7A4", "Direct staff social security", 1, 0, -1, 714, "down"),
    (715, 7, "Personnel costs", "7A", "Direct staff costs", "7A5", "Direct staff pension", 1, 0, -1, 715, "down"),
    (716, 7, "Personnel costs", "7A", "Direct staff costs", "7A6", "Direct staff other costs", 1, 0, -1, 716, "down"),
    (720, 7, "Personnel costs", "7B", "Indirect staff costs", "7B", "Indirect staff costs", 0, 0, -1, 720, "down"),
    (721, 7, "Personnel costs", "7B", "Indirect staff costs", "7B1", "Indirect staff salaries", 1, 0, -1, 721, "down"),
    (722, 7, "Personnel costs", "7B", "Indirect staff costs", "7B2", "Indirect staff bonus", 1, 0, -1, 722, "down"),
    (723, 7, "Personnel costs", "7B", "Indirect staff costs", "7B3", "Indirect staff social security", 1, 0, -1, 723, "down"),
    (724, 7, "Personnel costs", "7B", "Indirect staff costs", "7B4", "Indirect staff other costs", 1, 0, -1, 724, "down"),
    (800, 8, "External subcontracting", "8", "External subcontracting", "8", "External subcontracting", 0, 0, -1, 800, "down"),
    (801, 8, "External subcontracting", "8", "External subcontracting", "8.1", "External subcontractors", 1, 0, -1, 801, "down"),
    (802, 8, "External subcontracting", "8", "External subcontracting", "8.2", "Temporary staff", 1, 0, -1, 802, "down"),
    (900, 9, "Other costs", "9", "Other costs", "9", "Other costs", 0, 0, -1, 900, "down"),
    (901, 9, "Other costs", "9", "Other costs", "9.1", "Contract expenses", 1, 0, -1, 901, "down"),
    (902, 9, "Other costs", "9", "Other costs", "9.2", "Rent & utilities", 1, 0, -1, 902, "down"),
    (903, 9, "Other costs", "9", "Other costs", "9.3", "Depreciation", 1, 0, -1, 903, "down"),
    (904, 9, "Other costs", "9", "Other costs", "9.4", "Travel & living", 1, 0, -1, 904, "down"),
    (905, 9, "Other costs", "9", "Other costs", "9.5", "Vehicles", 1, 0, -1, 905, "down"),
    (906, 9, "Other costs", "9", "Other costs", "9.6", "IT & telecom", 1, 0, -1, 906, "down"),
    (907, 9, "Other costs", "9", "Other costs", "9.7", "Lab consumables", 1, 0, -1, 907, "down"),
    (908, 9, "Other costs", "9", "Other costs", "9.8", "Insurance", 1, 0, -1, 908, "down"),
    (909, 9, "Other costs", "9", "Other costs", "9.9", "Miscellaneous costs", 1, 0, -1, 909, "down"),
    (1000, 10, "Functional cost recharges", "10", "Functional cost recharges", "10", "Functional cost recharges", 0, 0, 1, 1000, "up"),
    (1001, 10, "Functional cost recharges", "10", "Functional cost recharges", "10.1", "Functional cost recharges", 1, 0, 1, 1001, "up"),
    (1100, 11, "Gross profit", "11", "Gross profit", "11", "Gross profit", 0, 1, 1, 1100, "up"),
    (1200, 12, "Functional costs", "12", "Functional costs", "12", "Functional costs", 0, 0, -1, 1200, "down"),
    (1201, 12, "Functional costs", "12", "Functional costs", "12.1", "Country functions", 1, 0, -1, 1201, "down"),
    (1202, 12, "Functional costs", "12", "Functional costs", "12.2", "Region functions", 1, 0, -1, 1202, "down"),
    (1203, 12, "Functional costs", "12", "Functional costs", "12.3", "HQ allocation", 1, 0, -1, 1203, "down"),
    (1300, 13, "Operating profit", "13", "Operating profit", "13", "Operating profit", 0, 1, 1, 1300, "up"),
    (1700, 17, "Other operating expenses", "17", "Other operating expenses", "17", "Other operating expenses", 0, 0, -1, 1700, "down"),
    (1701, 17, "Other operating expenses", "17", "Other operating expenses", "17.1", "Restructuring", 1, 0, -1, 1701, "down"),
    (1702, 17, "Other operating expenses", "17", "Other operating expenses", "17.2", "Amortisation of acquired intangibles", 1, 0, -1, 1702, "down"),
    (1703, 17, "Other operating expenses", "17", "Other operating expenses", "17.3", "Other non-recurring", 1, 0, -1, 1703, "down"),
    (1800, 18, "EBIT", "18", "EBIT", "18", "EBIT", 0, 1, 1, 1800, "up"),
    (1900, 19, "Financial result", "19", "Financial result", "19", "Financial result", 0, 0, 1, 1900, "up"),
    (1901, 19, "Financial result", "19", "Financial result", "19.1", "Net interest", 1, 0, 1, 1901, "up"),
    (1902, 19, "Financial result", "19", "Financial result", "19.2", "FX result", 1, 0, 1, 1902, "up"),
    (2000, 20, "Income taxes", "20", "Income taxes", "20", "Income taxes", 0, 0, -1, 2000, "down"),
    (2001, 20, "Income taxes", "20", "Income taxes", "20.1", "Income taxes", 1, 0, -1, 2001, "down"),
    (2100, 21, "Net income", "21", "Net income", "21", "Net income", 0, 1, 1, 2100, "up"),
]
LEAVES = [a for a in ACCOUNTS if a[7] == 1]
LEAF_CODES = [a[5] for a in LEAVES]
LEAF_ID = {a[5]: a[0] for a in LEAVES}
LEAF_LINE = {a[5]: a[1] for a in LEAVES}
REVENUE_SIDE = {"1.1", "1.2", "2.1", "2.2", "4.1", "5.1"}
NON_OPERATING = {"19.1", "19.2", "20.1"}
COST_LEAVES = [c for c in LEAF_CODES if c not in REVENUE_SIDE | NON_OPERATING]
VARIABLE_COSTS = {"7A3", "8.1", "8.2"} | VARIABLE_OTHER
STAT_KEYS = ("fte", "headcount", "direct_fte", "billable_hours", "available_hours", "overtime_hours")

VERSIONS = [(1, "Actual", 12, 0), (2, "Budget", 0, 0)]
_fc = CFG["forecasts"]
for _i, _name in enumerate(sorted(_fc), start=3):
    VERSIONS.append((_i, _name, int(_fc[_name]["actual_months"]), 1))
FC_ACCURACY = {k: float(v) for k, v in CFG["forecast_accuracy"].items()}

USERS = [
    ("group_cfo", "Group CFO", "Group CFO", "l1_group", CFG["company"]),
    ("us_country_head", "United States Country Head", "Country Head", "l3_country", "United States"),
    ("env_pl_leader", "Environmental Lab Testing PL Leader", "Product Line Leader",
     "l4_product_line", "Environmental Lab Testing"),
]


def t_index(year: int, month: int) -> int:
    return (year - SIM_START) * 12 + (month - 1)


def close_date(year: int, month: int) -> date:
    return date(year + (month == 12), month % 12 + 1, CLOSE_DAY)


def last_closed_month(as_of: date) -> tuple[int, int]:
    y, m = as_of.year, as_of.month
    for _ in range(36):
        y2, m2 = (y, m - 1) if m > 1 else (y - 1, 12)
        if close_date(y2, m2) <= as_of:
            return y2, m2
        y, m = y2, m2
    raise ValueError("no closed month found")


@dataclass
class BU:
    bu_id: int
    bu_name: str
    business: str
    pl: str
    country: str
    region: str
    city: str
    base: float
    growth: float
    noise: float
    pers_off: float
    subc_off: float
    other_off: float
    r_igr: float
    r_igs: float
    cn_ratio: float
    util: float
    ot: float
    hc_ratio: float
    amort: float
    pattern: str = "steady"      # billing pattern class (generator truth)
    qe: float = 0.0              # quarter-end uplift
    ye: float = 0.0              # December uplift
    season_amp: float = 0.0      # March peak / August dip amplitude
    drift: float = 0.0           # yearly drift of the pattern intensity
    lumpy_p: float = 0.0         # monthly probability of a large project billing
    fc_bias: float = 0.0         # forecast bias (+ optimistic, - conservative)

    @property
    def btype(self) -> str:
        return PRODUCT_LINES[self.pl]["type"]

    @property
    def hemi(self) -> str:
        return COUNTRIES[self.country][7]


# --------------------------------------------------------------------------------------
# Organisation
# --------------------------------------------------------------------------------------
def build_org(seed: int) -> list[BU]:
    target = int(CFG["target_bu_count"])
    plan = []
    for attempt in range(500):
        rng = np.random.default_rng(seed + attempt)
        plan = []
        for country in sorted(COUNTRIES, key=lambda c: (REGION_ORDER.index(COUNTRIES[c][1]), c)):
            for pl in COUNTRY_PLS[country]:
                size = PL_SIZE.get((country, pl), {})
                n_bus = min(int(rng.choice([1, 2, 3], p=[0.55, 0.30, 0.15])), len(CITIES[country]))
                n_bus = min(size.get("cities", n_bus), len(CITIES[country]))
                for ci in sorted(rng.choice(len(CITIES[country]), size=n_bus, replace=False)):
                    n_units = int(rng.choice([1, 2, 3, 4], p=[0.55, 0.28, 0.11, 0.06]))
                    n_units = min(n_units, size.get("max_units", n_units))
                    plan.append((country, pl, CITIES[country][ci], n_units))
        if abs(sum(p[-1] for p in plan) - target) <= 4:
            break
    rng = np.random.default_rng(seed + 1000)
    bus: list[BU] = []
    for country, pl, (city, ccode), n_units in plan:
        code, region, cscale = COUNTRIES[country][0], COUNTRIES[country][1], COUNTRIES[country][2]
        meta = PRODUCT_LINES[pl]
        size_scale = PL_SIZE.get((country, pl), {}).get("scale", 1.0)
        for k in range(1, n_units + 1):
            story = (country, pl) in STORY.values()
            spread = 0.4 if story else 1.0
            subc_sd = 0.03 if meta["type"] in ("infrastructure", "industry") else 0.012
            bus.append(BU(
                bu_id=len(bus) + 1, bu_name=f"{code}-{meta['code']}-{ccode}-{k:02d}",
                business=f"{meta['short']} {city}", pl=pl, country=country, region=region, city=city,
                base=8.0e6 * cscale * meta["scale"] * size_scale * float(rng.lognormal(0, 0.45)),
                growth=meta["growth"] + float(rng.normal(0, 0.012)),
                noise=float(rng.uniform(0.025, 0.045)),
                pers_off=float(rng.normal(0, 0.018)) * spread,
                subc_off=float(rng.normal(0, subc_sd)) * spread,
                other_off=float(rng.normal(0, 0.010)) * spread,
                r_igr=float(rng.uniform(0.02, 0.06)), r_igs=float(rng.uniform(0.02, 0.06)),
                cn_ratio=float(rng.uniform(0.008, 0.02)),
                util=float(rng.uniform(0.70, 0.78)), ot=float(rng.uniform(0.04, 0.08)),
                hc_ratio=float(rng.uniform(1.04, 1.09)),
                amort=float(rng.uniform(0.005, 0.015)) if rng.random() < 0.35 else 0.0,
            ))
    assign_patterns(bus, seed)
    return bus


def assign_patterns(bus: list[BU], seed: int) -> None:
    """Billing pattern, its parameters and the planners' forecast bias per BU (separate seeded stream)."""
    rng = np.random.default_rng(seed + 2000)
    for bu in bus:
        mix = PATTERN_MIX[bu.pl]
        bu.pattern = str(rng.choice(list(mix), p=np.array(list(mix.values())) / sum(mix.values())))
        if (bu.country, bu.pl) == LANDING_STORY["lumpy"]:
            bu.pattern = "lumpy"
        if (bu.country, bu.pl) == LANDING_STORY["momentum"]:
            bu.pattern = "quarter_end"
        bu.qe = float(rng.uniform(0.25, 0.40))
        bu.ye = float(rng.uniform(0.60, 1.00))
        bu.season_amp = float(rng.uniform(0.15, 0.22))
        bu.drift = float(rng.uniform(-0.08, 0.08))
        if bu.pattern == "lumpy":
            bu.noise = float(rng.uniform(0.10, 0.15))
            bu.lumpy_p = float(rng.uniform(0.10, 0.16))
        u = rng.random()
        if u < 0.25:
            bu.fc_bias = float(rng.uniform(0.04, 0.09))        # optimistic planners
        elif u < 0.40:
            bu.fc_bias = float(rng.uniform(-0.06, -0.025))     # conservative planners
        else:
            bu.fc_bias = float(rng.normal(0, 0.01))
        if (bu.country, bu.pl) == LANDING_STORY["optimistic_forecast"]:
            bu.fc_bias = float(rng.uniform(0.10, 0.12))


def pattern_season(bu: BU, year: int) -> np.ndarray:
    """12 monthly billing factors (mean 1) for the BU's pattern in `year`; the intensity drifts mildly."""
    base = SEASON[bu.hemi]
    k = max(0.3, 1.0 + bu.drift * (year - 2024))
    if bu.pattern == "quarter_end":
        qe = np.isin(np.arange(12), [2, 5, 8, 11])
        s = (1 + 0.5 * (base - 1)) * np.where(qe, 1 + bu.qe * k, 1 - bu.qe * k / 2)
    elif bu.pattern == "year_end":
        s = (1 + 0.35 * (base - 1)).copy()
        s[11] *= 1 + bu.ye * k
        s[10] *= 1 + 0.15 * bu.ye * k
    elif bu.pattern == "seasonal":
        s = (1 + 0.5 * (base - 1)).copy()
        s[2] *= 1 + bu.season_amp * k
        s[1] *= 1 + 0.4 * bu.season_amp * k
        s[7] *= 1 - 1.5 * bu.season_amp * k
        s[6] *= 1 - 0.5 * bu.season_amp * k
    elif bu.pattern == "lumpy":
        s = 1 + 0.5 * (base - 1)
    else:                                               # steady
        s = 1 + 0.35 * (base - 1)
    return s / s.mean()


# --------------------------------------------------------------------------------------
# Working-day calendar: Monday-Friday minus public holidays (holidays package), per country
# --------------------------------------------------------------------------------------
def calendar_frame(first_year: int, last_year: int) -> pd.DataFrame:
    rows = []
    days = pd.date_range(date(first_year, 1, 1), date(last_year, 12, 31), freq="D")
    for country, spec in COUNTRIES.items():
        hol = holidays.country_holidays(spec[0], years=range(first_year, last_year + 1))
        for d in days:
            dd = d.date()
            rows.append((dd, country, bool(dd.weekday() < 5 and dd not in hol)))
    return pd.DataFrame(rows, columns=["date", "country", "is_working_day"])


def working_days_frame(cal: pd.DataFrame) -> pd.DataFrame:
    c = cal.assign(month_key=[d.year * 100 + d.month for d in cal["date"]])
    wd = c.groupby(["month_key", "country"], as_index=False)["is_working_day"].sum()
    return wd.rename(columns={"is_working_day": "working_days"}).astype({"working_days": int})


def wd_factors(wd: pd.DataFrame) -> dict[str, np.ndarray]:
    """Per country and simulated month: (working days / average for that calendar month) ** elasticity."""
    out = {}
    for country in COUNTRIES:
        s = wd[wd.country == country].set_index("month_key")["working_days"]
        arr = np.array([float(s[(SIM_START + i // 12) * 100 + i % 12 + 1]) for i in range(N_SIM)])
        typical = arr.reshape(-1, 12).mean(axis=0)
        out[country] = (arr / np.tile(typical, N_SIM // 12)) ** WD_ELASTICITY
    return out


WD_FACTOR: dict[str, np.ndarray] = {}


# --------------------------------------------------------------------------------------
# Simulation of the "true" monthly P&L per BU (signed leaf amounts)
# --------------------------------------------------------------------------------------
def simulate_bu(rng: np.random.Generator, bu: BU):
    n = N_SIM
    t = np.arange(n)
    m = t % 12
    yi = t // 12
    prof = COST_PROFILES[bu.btype]
    season = SEASON[bu.hemi]
    _, _, _, cpf, tax_rate, fx_vol, fx_bias, _ = COUNTRIES[bu.country]

    trend = bu.base / 12.0 * (1 + bu.growth) ** (t / 12.0)
    pseason = np.concatenate([pattern_season(bu, SIM_START + y) for y in range(n // 12)])
    mult = np.ones(n)                               # known structural changes in production (stories)
    pers_factor = np.ones(n)
    pers_adj = np.zeros(n)
    other_adj = np.zeros(n)
    restructuring_extra = np.zeros(n)

    # Story (b): Canada Environmental Lab Testing loses a large contract from Feb 2026:
    # production -20% immediately, personnel adjusts only from May 2026 (3-month lag), with a
    # one-off restructuring (severance) charge in May 2026.
    if (bu.country, bu.pl) == STORY["b"]:
        mult = np.where(t >= t_index(2026, 2), mult * 0.80, mult)
        pers_factor = np.where(t >= t_index(2026, 5), 0.84, 1.0)
        restructuring_extra[t_index(2026, 5)] = trend[t_index(2026, 5)] * prof["personnel"] * 0.16 * 3
    # Landing story: United States Industry & Energy gains momentum from Jul 2025 (+0.8% a month)
    if (bu.country, bu.pl) == LANDING_STORY["momentum"]:
        k0 = t_index(2025, 7)
        mult = mult * np.where(t >= k0, 1.008 ** (t - k0 + 1), 1.0)
    # Landing story: Mexico Consumer Products declines from Jan 2026 (-1% a month); costs stay
    if (bu.country, bu.pl) == LANDING_STORY["shortfall"]:
        k0 = t_index(2026, 1)
        mult = mult * np.where(t >= k0, 0.99 ** (t - k0 + 1), 1.0)

    expected = trend * pseason * WD_FACTOR[bu.country] * mult
    spikes = np.where(rng.random(n) < bu.lumpy_p, rng.uniform(1.35, 1.9, n), 1.0) if bu.lumpy_p else np.ones(n)
    prod = expected * spikes * (1 + rng.normal(0, bu.noise, n))

    # Story (e): Canada Power & Utilities - steady margin improvement 2022-2026.
    if (bu.country, bu.pl) == STORY["e"]:
        years_since = (t - t_index(FIRST_YEAR, 1)) / 12.0
        pers_adj = 0.035 - 0.012 * years_since
        other_adj = 0.008 - 0.003 * years_since

    prod_ratio = prod / (trend * pseason)
    leaves: dict[str, np.ndarray] = {}

    # Revenue side: production -> intragroup -> revenue -> WIP & deferred income -> billing ------------
    igr = prod * bu.r_igr * (1 + rng.normal(0, 0.03, n))
    igs = -prod * bu.r_igs * (1 + rng.normal(0, 0.03, n))
    rev = prod - igr - igs
    wip = np.zeros(n)
    for y in range(n // 12):
        s = y * 12
        wip[s:s + 11] = rev[s:s + 11] * (WIP_PROFILE + rng.normal(0, 0.008, 11))
        wip[s + 11] = -0.85 * wip[s:s + 11].sum() * (1 + rng.normal(0, 0.05))
    ui_amp = 3.0 if bu.btype == "certification" else 1.0
    ui = rev * UI_PROFILE[m] * ui_amp * (1 + rng.normal(0, 0.10, n))
    billing = rev - wip - ui
    credit = -billing * bu.cn_ratio * (1 + rng.normal(0, 0.10, n))
    leaves["1.1"], leaves["1.2"] = billing - credit, credit
    leaves["2.1"], leaves["2.2"] = wip, ui
    leaves["4.1"], leaves["5.1"] = igr, igs

    # Personnel charges (7) - smooth, follows the trend not monthly production ------------
    pr = prof["personnel"] + bu.pers_off + pers_adj
    pers_total = trend * pr * pers_factor * PERS_SEASON[m] * (1 + rng.normal(0, 0.01, n))
    p7a = pers_total * prof["share_7a"]
    p7b = pers_total - p7a
    trueup_a = rng.normal(0.6, 0.2, n // 12)
    trueup_b = rng.normal(0.4, 0.15, n // 12)
    bonus_a = np.where(m == 2, 1 + trueup_a[yi], 1.0)
    bonus_b = np.where(m == 2, 1 + trueup_b[yi], 1.0)
    leaves["7A1"] = -p7a * 0.65
    leaves["7A2"] = -p7a * 0.08 * bonus_a
    leaves["7A3"] = -p7a * 0.05 * pseason * prod_ratio
    leaves["7A4"] = -p7a * 0.15 * (1 + rng.normal(0, 0.01, n))
    leaves["7A5"] = -p7a * 0.05 * (1 + rng.normal(0, 0.01, n))
    leaves["7A6"] = -p7a * 0.02 * (1 + rng.normal(0, 0.08, n))
    leaves["7B1"] = -p7b * 0.70
    leaves["7B2"] = -p7b * 0.08 * bonus_b
    leaves["7B3"] = -p7b * 0.17 * (1 + rng.normal(0, 0.01, n))
    leaves["7B4"] = -p7b * 0.05 * (1 + rng.normal(0, 0.08, n))

    # External subcontracting (8) -----------------------------------------------------------
    sr = max(prof["subc"] + bu.subc_off, 0.015)
    subc = prod * sr * (1 + rng.normal(0, 0.06, n))
    ext = subc * 0.70 * (1 + rng.normal(0, 0.03, n))
    leaves["8.1"], leaves["8.2"] = -ext, -(subc - ext)

    # Other costs (9) -----------------------------------------------------------------------
    orat = prof["other"] + bu.other_off + other_adj
    for code, share in OTHER_MIX[bu.btype].items():
        if code in VARIABLE_OTHER:
            leaves[code] = -prod * orat * share * (1 + rng.normal(0, 0.06, n))
        else:
            leaves[code] = -trend * orat * share * (1 + rng.normal(0, 0.01, n))

    # Functional neutralization (10) and total functional costs (12) -----------------------
    fr = prof["functional"]
    yearly_trend = np.repeat(trend.reshape(-1, 12).mean(axis=1), 12)
    leaves["10.1"] = trend * 0.025 * (1 + rng.normal(0, 0.02, n))
    leaves["12.1"] = -trend * fr * 0.43 * (1 + rng.normal(0, 0.01, n))
    leaves["12.2"] = -trend * fr * 0.24 * (1 + rng.normal(0, 0.01, n))
    leaves["12.3"] = -yearly_trend * fr * 0.33

    # Other operating expenses (17): lumpy restructuring, PPA amortisation, small other ------
    events = rng.random(n) < 0.03
    leaves["17.1"] = -(np.where(events, trend * rng.uniform(0.02, 0.08, n), 0.0) + restructuring_extra)
    leaves["17.2"] = -yearly_trend * bu.amort
    leaves["17.3"] = -trend * np.abs(rng.normal(0, 0.002, n))

    # Financial result (19): net interest + FX result (country FX volatility; USD = 0) -----
    leaves["19.1"] = -trend * 0.006 * (1 + rng.normal(0, 0.05, n))
    leaves["19.2"] = trend * (fx_bias + rng.normal(0, fx_vol, n)) if fx_vol > 0 else np.zeros(n)

    # Statistics -------------------------------------------------------------------------------
    cost_per_fte = cpf * 1.03 ** (t / 12.0)
    fte = trend * pr * pers_factor * 12.0 / cost_per_fte * (1 + rng.normal(0, 0.004, n))
    direct_fte = fte * prof["share_7a"]
    avail = direct_fte * AVAIL_HOURS * AVAIL_SEASON[bu.hemi][m] * (1 + rng.normal(0, 0.01, n))
    util = np.clip(bu.util * prod_ratio ** 0.8 / pers_factor ** 0.8 * (1 + rng.normal(0, 0.012, n)), 0.45, 0.97)
    stats = {"fte": fte, "headcount": fte * bu.hc_ratio, "direct_fte": direct_fte,
             "available_hours": avail, "billable_hours": avail * util,
             "overtime_hours": avail * bu.ot * OT_SEASON[m] * np.clip(prod_ratio, 0.5, 1.5) ** 1.5}
    return leaves, prod, stats, expected


def add_taxes(leaves: dict[str, np.ndarray], tax_rates: np.ndarray) -> None:
    """Corporate taxes (20.1) = -rate x pre-tax result (lines 1..19), per BU-month."""
    pre_tax = sum(leaves[c] for c in LEAF_CODES if c != "20.1")
    leaves["20.1"] = -pre_tax * tax_rates[:, None]


# --------------------------------------------------------------------------------------
# Fictional employees (codes only: no names, gender, age or other personal attributes)
# --------------------------------------------------------------------------------------
ROLES = {
    "inspection": {"Direct": [("Inspector", 0.55), ("Senior inspector", 0.30), ("Lead inspector", 0.15)],
                   "Indirect": [("Scheduler", 0.30), ("Sales", 0.25), ("Administration", 0.30), ("Manager", 0.15)]},
    "infrastructure": {"Direct": [("Field engineer", 0.40), ("Inspector", 0.35), ("Project manager", 0.25)],
                       "Indirect": [("Sales", 0.30), ("Administration", 0.40), ("Manager", 0.30)]},
    "industry": {"Direct": [("Inspector", 0.45), ("Engineer", 0.35), ("NDT technician", 0.20)],
                 "Indirect": [("Sales", 0.30), ("Administration", 0.40), ("Manager", 0.30)]},
    "laboratory": {"Direct": [("Lab technician", 0.50), ("Lab analyst", 0.35), ("Chemist", 0.15)],
                   "Indirect": [("Sample reception", 0.30), ("Quality", 0.20), ("Administration", 0.30),
                                ("Manager", 0.20)]},
    "certification": {"Direct": [("Auditor", 0.55), ("Lead auditor", 0.30), ("Technical reviewer", 0.15)],
                      "Indirect": [("Sales", 0.35), ("Administration", 0.40), ("Manager", 0.25)]},
}
GRADES = ["G1", "G2", "G3", "G4", "G5"]
GRADE_P = np.array([0.22, 0.30, 0.25, 0.15, 0.08])
SENIOR_ROLES = {"Manager", "Lead inspector", "Lead auditor", "Project manager"}
GRADE_UTIL = {"G1": 0.97, "G2": 1.03, "G3": 1.04, "G4": 0.97, "G5": 0.82}
ROLE_UTIL = {"Project manager": 0.85, "Lead inspector": 0.92, "Lead auditor": 0.92, "Technical reviewer": 0.95}
GRADE_ATTRITION = {"G1": 1.4, "G2": 1.15, "G3": 0.9, "G4": 0.75, "G5": 0.6}
GRADE_OT = {"G1": 1.2, "G2": 1.2, "G3": 1.0, "G4": 0.8, "G5": 0.5}


def build_employees(bus: list[BU], stats_out: dict[str, np.ndarray], n_act: int, seed: int):
    """Simulate a roster per BU for the first n_act output months (closed Actual months).

    Monthly headcount follows the simulated BU headcount; leavers are voluntary (monthly hazard by
    region and grade) or restructuring (when the BU headcount falls). Direct staff carry available,
    billable and overtime hours; the BU sums reproduce the simulated utilization and overtime ratio.
    Returns (dim_employee, fact_employee_month, stats) where stats holds the Actual BU statistics
    recomputed from the employees for those months.
    """
    rng = np.random.default_rng(seed + 7)
    emp: dict[str, list] = {k: [] for k in ("bu_id", "role", "grade", "staff_type", "fte_pct", "hire_m",
                                             "leave_m", "reason", "util_w", "ot_w", "tenure_days")}
    rows = {k: [] for k in ("employee_id", "month_idx", "bu_id", "fte", "available_hours", "billable_hours",
                            "overtime_hours")}
    new_stats = {k: stats_out[k][:, :n_act].copy() for k in STAT_KEYS}

    def hire(b: int, bu: BU, staff: str, month: int, tenure: float = 0.0) -> int:
        names, probs = zip(*ROLES[bu.btype][staff])
        role = str(rng.choice(names, p=np.array(probs) / sum(probs)))
        g = int(rng.choice(5, p=GRADE_P))
        if role in SENIOR_ROLES:
            g = max(g, 2 + int(rng.integers(0, 3)))
        grade = GRADES[min(g, 4)]
        p_pt = float(np.clip((1 - 1 / bu.hc_ratio) / 0.29, 0.0, 0.6))
        fte_pct = 1.0 if rng.random() > p_pt else (0.8 if rng.random() < 0.7 else 0.5)
        emp["bu_id"].append(bu.bu_id)
        emp["role"].append(role)
        emp["grade"].append(grade)
        emp["staff_type"].append(staff)
        emp["fte_pct"].append(fte_pct)
        emp["hire_m"].append(month)
        emp["leave_m"].append(None)
        emp["reason"].append(None)
        emp["util_w"].append(GRADE_UTIL[grade] * ROLE_UTIL.get(role, 1.0) * float(rng.lognormal(0, 0.07)))
        emp["ot_w"].append(GRADE_OT[grade] * float(rng.lognormal(0, 0.6)))
        emp["tenure_days"].append(tenure)
        return len(emp["bu_id"]) - 1

    for b, bu in enumerate(bus):
        north = COUNTRIES[bu.country][7] == "N"
        base_hazard = (0.11 if north else 0.14) / 12.0
        roster: list[int] = []
        for t in range(n_act):
            m = t % 12
            target = int(round(stats_out["headcount"][b, t]))
            share = float(stats_out["direct_fte"][b, t] / max(stats_out["fte"][b, t], 1e-9))
            target_direct = min(target, max(1, int(round(target * share)))) if target > 0 else 0
            if t == 0:
                for _ in range(target_direct):
                    roster.append(hire(b, bu, "Direct", -1, float(min(rng.exponential(6 * 365), 30 * 365))))
                for _ in range(target - target_direct):
                    roster.append(hire(b, bu, "Indirect", -1, float(min(rng.exponential(6 * 365), 30 * 365))))
            else:
                roster = [e for e in roster if emp["leave_m"][e] is None]
                for staff, tgt in (("Direct", target_direct), ("Indirect", target - target_direct)):
                    cur = [e for e in roster if emp["staff_type"][e] == staff]
                    if len(cur) > tgt:                      # headcount fell: restructuring at end of t-1
                        for e in rng.choice(cur, size=len(cur) - tgt, replace=False):
                            emp["leave_m"][int(e)], emp["reason"][int(e)] = t - 1, "Restructuring"
                    elif len(cur) < tgt:
                        roster += [hire(b, bu, staff, t) for _ in range(tgt - len(cur))]
                roster = [e for e in roster if emp["leave_m"][e] is None]
            # voluntary leavers: work month t, gone from t+1
            for e in roster:
                if rng.random() < base_hazard * GRADE_ATTRITION[emp["grade"][e]]:
                    emp["leave_m"][e], emp["reason"][e] = t, "Voluntary"
            ids = np.array(roster)
            fte = np.array([emp["fte_pct"][e] for e in roster])
            direct = np.array([emp["staff_type"][e] == "Direct" for e in roster])
            avail = np.where(direct, fte * AVAIL_HOURS * AVAIL_SEASON[bu.hemi][m]
                             * (1 + rng.normal(0, 0.03, len(roster))), 0.0)
            util = stats_out["billable_hours"][b, t] / stats_out["available_hours"][b, t]
            ot = stats_out["overtime_hours"][b, t] / stats_out["available_hours"][b, t]
            uw = np.array([emp["util_w"][e] for e in roster])
            ow = np.array([emp["ot_w"][e] for e in roster])
            bill = avail * util * uw / max((avail * uw).sum() / max(avail.sum(), 1e-9), 1e-9)
            bill = np.minimum(bill, avail * 0.98)
            bill *= util * avail.sum() / max(bill.sum(), 1e-9)       # BU utilization reproduced exactly
            over = avail * ot * ow / max((avail * ow).sum() / max(avail.sum(), 1e-9), 1e-9)
            rows["employee_id"].append(ids)
            rows["month_idx"].append(np.full(len(roster), t))
            rows["bu_id"].append(np.full(len(roster), bu.bu_id))
            rows["fte"].append(fte)
            rows["available_hours"].append(np.round(avail, 1))
            rows["billable_hours"].append(np.round(bill, 1))
            rows["overtime_hours"].append(np.round(over, 1))
            new_stats["headcount"][b, t] = len(roster)
            new_stats["fte"][b, t] = fte.sum()
            new_stats["direct_fte"][b, t] = fte[direct].sum()
            new_stats["available_hours"][b, t] = np.round(avail, 1).sum()
            new_stats["billable_hours"][b, t] = np.round(bill, 1).sum()
            new_stats["overtime_hours"][b, t] = np.round(over, 1).sum()

    fact = pd.DataFrame({k: np.concatenate(v) for k, v in rows.items()})
    leave_m = np.array([-10**6 if x is None else x for x in emp["leave_m"]])
    hire_m = np.array(emp["hire_m"])
    fact["is_hire"] = hire_m[fact["employee_id"].to_numpy()] == fact["month_idx"].to_numpy()
    fact["is_leaver"] = leave_m[fact["employee_id"].to_numpy()] == fact["month_idx"].to_numpy()

    def month_date(idx: int, day: int) -> date:
        y, mo = FIRST_YEAR + idx // 12, idx % 12 + 1
        return date(y, mo, min(day, 28)) if day < 29 else (date(y + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1))

    start = date(FIRST_YEAR, 1, 1)
    dim = pd.DataFrame({
        "employee_id": np.arange(1, len(emp["bu_id"]) + 1),
        "employee_code": [f"E{100000 + i:06d}" for i in range(1, len(emp["bu_id"]) + 1)],
        "bu_id": emp["bu_id"], "role": emp["role"], "grade": emp["grade"], "staff_type": emp["staff_type"],
        "fte_pct": emp["fte_pct"],
        "hire_date": [start - timedelta(days=int(tn) + 1) if hm < 0 else month_date(hm, int(1 + (i * 7) % 27))
                      for i, (hm, tn) in enumerate(zip(emp["hire_m"], emp["tenure_days"]))],
        "leave_date": [None if lm is None else month_date(lm, 31) for lm in emp["leave_m"]],
        "leave_reason": emp["reason"],
    })
    fact["employee_id"] = fact["employee_id"] + 1
    fact["month_key"] = [(FIRST_YEAR + i // 12) * 100 + i % 12 + 1 for i in fact["month_idx"]]
    fact = fact.drop(columns=["month_idx"])[["month_key", "employee_id", "bu_id", "fte", "available_hours",
                                              "billable_hours", "overtime_hours", "is_hire", "is_leaver"]]
    return dim, fact, new_stats


# --------------------------------------------------------------------------------------
# Budget: prior-year actual x (1 + target growth), slight optimism bias
# --------------------------------------------------------------------------------------
def build_budget(bus, truth, prod, stats):
    nb = len(bus)
    bud = {c: np.zeros((nb, N_OUT)) for c in LEAF_CODES}
    bud_prod = np.zeros((nb, N_OUT))
    bud_stats = {k: np.zeros((nb, N_OUT)) for k in STAT_KEYS}
    flat = np.full(12, 1 / 12)
    for yo, year in enumerate(range(FIRST_YEAR, LAST_YEAR + 1)):
        py = slice(t_index(year - 1, 1), t_index(year - 1, 1) + 12)
        out = slice(yo * 12, yo * 12 + 12)
        for b, bu in enumerate(bus):
            # planners phase the budget with the BU's billing pattern and the year's working days
            prof_y = pattern_season(bu, year) * WD_FACTOR[bu.country][t_index(year, 1):t_index(year, 1) + 12]
            seas = prof_y / prof_y.sum()
            g = PRODUCT_LINES[bu.pl]["growth"]
            p_py = prod[b, py].sum()
            bp = p_py * (1 + g + 0.015) * (1 + 0.5 * bu.fc_bias) * seas
            igr = bp * truth["4.1"][b, py].sum() / p_py
            igs = bp * truth["5.1"][b, py].sum() / p_py
            br = bp - igr - igs
            bw = np.zeros(12)
            bw[:11] = br[:11] * WIP_PROFILE
            bw[11] = -0.85 * bw[:11].sum()
            bui = br * UI_PROFILE * (3.0 if bu.btype == "certification" else 1.0)
            bbill = br - bw - bui
            bill_py = truth["1.1"][b, py].sum() + truth["1.2"][b, py].sum()
            cn = -truth["1.2"][b, py].sum() / bill_py
            credit = -bbill * cn
            bud["1.1"][b, out], bud["1.2"][b, out] = bbill - credit, credit
            bud["2.1"][b, out], bud["2.2"][b, out] = bw, bui
            bud["4.1"][b, out], bud["5.1"][b, out] = igr, igs
            cost_growth = 1 + 0.92 * (g + 0.015)
            for code in COST_LEAVES:
                profile = seas if code in VARIABLE_COSTS else flat
                total = truth[code][b, py].sum()
                if code == "17.1":
                    total = -p_py * 0.003          # restructuring: small provision only
                elif code == "17.3":
                    total = 0.0
                bud[code][b, out] = total * cost_growth * profile
            bud["19.1"][b, out] = truth["19.1"][b, py].sum() * (1 + g) * flat
            bud["19.2"][b, out] = 0.0                   # FX result is not budgeted
            bud_prod[b, out] = bp
            fte_py = stats["fte"][b, py]
            fte_b = fte_py.mean() * (1 + g * 0.5)
            ratio = lambda k: stats[k][b, py].sum() / fte_py.sum()  # noqa: E731
            avail_b = fte_b * ratio("available_hours") * 12 * AVAIL_SEASON[bu.hemi] / AVAIL_SEASON[bu.hemi].sum()
            util_py = stats["billable_hours"][b, py].sum() / stats["available_hours"][b, py].sum()
            ot_py = stats["overtime_hours"][b, py].sum() / stats["available_hours"][b, py].sum()
            bud_stats["fte"][b, out] = fte_b
            bud_stats["headcount"][b, out] = fte_b * ratio("headcount")
            bud_stats["direct_fte"][b, out] = fte_b * ratio("direct_fte")
            bud_stats["available_hours"][b, out] = avail_b
            bud_stats["billable_hours"][b, out] = avail_b * util_py
            bud_stats["overtime_hours"][b, out] = avail_b * ot_py * OT_SEASON / OT_SEASON.mean()
    return bud, bud_prod, bud_stats


def main() -> None:
    seed = int(CFG["seed"])
    DATA.mkdir(parents=True, exist_ok=True)
    calendar = calendar_frame(SIM_START, LAST_YEAR)
    working_days = working_days_frame(calendar)
    WD_FACTOR.update(wd_factors(working_days))
    bus = build_org(seed)
    nb = len(bus)
    rng = np.random.default_rng(seed)
    tax_rates = np.array([COUNTRIES[bu.country][4] for bu in bus])

    truth = {c: np.zeros((nb, N_SIM)) for c in LEAF_CODES}
    prod = np.zeros((nb, N_SIM))
    expected = np.zeros((nb, N_SIM))
    stats = {k: np.zeros((nb, N_SIM)) for k in STAT_KEYS}
    for b, bu in enumerate(bus):
        leaves, p, st, ex = simulate_bu(rng, bu)
        for c in LEAF_CODES:
            if c in leaves:
                truth[c][b] = leaves[c]
        prod[b] = p
        expected[b] = ex
        for k in STAT_KEYS:
            stats[k][b] = st[k]
    add_taxes(truth, tax_rates)

    bud, bud_prod, bud_stats = build_budget(bus, truth, prod, stats)
    add_taxes(bud, tax_rates)

    def sel(key):
        country, pl = STORY[key]
        return [b for b, bu in enumerate(bus) if bu.country == country and bu.pl == pl]

    # Story (a): United States Elevators & Pressure Vessels - 7A2 bonus spike March 2025, about 3x a
    # normal March (normal March = monthly accrual x 1.6 average true-up; accrual = 8/65 of 7A1)
    for b in sel("a"):
        t25 = t_index(2025, 3)
        normal_march = truth["7A1"][b, t25] * (0.08 / 0.65) * 1.6
        truth["7A2"][b, t25] = 3.0 * normal_march
    # Story (c): Mexico Buildings & Infrastructure - WIP build-up Jan-Jun 2026, reversal Jul-Sep
    for b in sel("c"):
        rev = sum(truth[c][b] for c in ("1.1", "1.2", "2.1", "2.2"))
        s = t_index(2026, 1)
        build = rev[s:s + 6] * (0.15 + rng.normal(0, 0.01, 6))
        truth["2.1"][b, s:s + 6] = build
        truth["2.1"][b, s + 6:s + 9] = -build.sum() * np.array([0.32, 0.33, 0.30])
        new_bill = rev - truth["2.1"][b] - truth["2.2"][b]
        ratio = -truth["1.2"][b] / (truth["1.1"][b] + truth["1.2"][b])
        truth["1.2"][b] = -new_bill * ratio
        truth["1.1"][b] = new_bill - truth["1.2"][b]
    # Story (d): Chile Metals & Minerals - external subcontracting 2026 running +35% vs budget
    off26 = (2026 - FIRST_YEAR) * 12
    for b in sel("d"):
        for code in ("8.1", "8.2"):
            truth[code][b, t_index(2026, 1):t_index(2026, 1) + 12] = (
                bud[code][b, off26:off26 + 12] * 1.35 * (1 + rng.normal(0, 0.03, 12)))
    add_taxes(truth, tax_rates)                       # re-compute taxes after the stories

    sim_out = slice(t_index(FIRST_YEAR, 1), t_index(FIRST_YEAR, 1) + N_OUT)
    truth_out = {c: truth[c][:, sim_out] for c in LEAF_CODES}
    stats_out = {k: stats[k][:, sim_out] for k in STAT_KEYS}
    prod_out, expected_out = prod[:, sim_out], expected[:, sim_out]
    ly0, lm0 = last_closed_month(AS_OF)
    n_act = (ly0 - FIRST_YEAR) * 12 + lm0
    dim_employee, fact_employee_month, emp_stats = build_employees(bus, stats_out, n_act, seed)
    for k in STAT_KEYS:                                # Actual BU statistics = employee totals
        stats_out[k][:, :n_act] = emp_stats[k]
    # Forecasts: reforecast months blend the expected path (what planners can know) with the budget,
    # carry the BU's planner bias and forecast noise; production-driven lines follow the forecast
    # production, the other lines blend Actual and Budget as before. Monthly noise and project spikes
    # are never known in advance.
    fc_bias = np.array([bu.fc_bias for bu in bus])[:, None]
    fc_noise = {k: float(v) for k, v in (CFG.get("forecast_noise_sd") or {}).items()}
    prod_driven = {"1.1", "1.2", "4.1", "5.1"} | VARIABLE_COSTS
    forecasts, fc_stats = {}, {}
    for _vid, vname, k_act, is_fc in VERSIONS:
        if not is_fc:
            continue
        a = FC_ACCURACY[vname]
        sd = fc_noise.get(vname, 0.03)
        fc_prod = (a * expected_out + (1 - a) * bud_prod) * (1 + fc_bias) * (1 + rng.normal(0, sd, prod_out.shape))
        ratio = fc_prod / np.where(np.abs(prod_out) > 1e-9, prod_out, 1e-9)
        fc = {}
        for c in LEAF_CODES:
            arr = truth_out[c].copy()
            for yo in range(N_OUT // 12):
                tail = slice(yo * 12 + k_act, yo * 12 + 12)
                if c in prod_driven:
                    arr[:, tail] = truth_out[c][:, tail] * ratio[:, tail]
                else:
                    arr[:, tail] = (a * truth_out[c][:, tail] + (1 - a) * bud[c][:, tail]) * (
                        1 + rng.normal(0, 0.01, arr[:, tail].shape))
            fc[c] = arr
        add_taxes(fc, tax_rates)
        st = {}
        for key in STAT_KEYS:
            arr = stats_out[key].copy()
            for yo in range(N_OUT // 12):
                tail = slice(yo * 12 + k_act, yo * 12 + 12)
                arr[:, tail] = a * stats_out[key][:, tail] + (1 - a) * bud_stats[key][:, tail]
            st[key] = arr
        forecasts[vname], fc_stats[vname] = fc, st

    # ----------------------------------------------------------------------------------
    # Tables
    # ----------------------------------------------------------------------------------
    month_keys = np.array([(FIRST_YEAR + i // 12) * 100 + i % 12 + 1 for i in range(N_OUT)])
    ly, lm = last_closed_month(AS_OF)
    last_closed_key = ly * 100 + lm
    actual_mask = month_keys <= last_closed_key

    dim_org = pd.DataFrame([{
        "bu_id": bu.bu_id, "bu_name": bu.bu_name, "l6_bu": bu.bu_name, "l5_business": bu.business,
        "l4_product_line": bu.pl, "l3_country": bu.country, "l2_region": bu.region,
        "l1_group": CFG["company"], "business_type": bu.btype, "city": bu.city,
        "valid_from": date(FIRST_YEAR, 1, 1), "valid_to": date(9999, 12, 31),
    } for bu in bus])
    dim_account = pd.DataFrame(ACCOUNTS, columns=[
        "account_id", "line_no", "l1_name", "l2_code", "l2_name", "l3_code", "l3_name",
        "is_leaf", "is_subtotal", "natural_sign", "display_order", "favorable_direction"])
    dim_account["is_leaf"] = dim_account["is_leaf"].astype(bool)
    dim_account["is_subtotal"] = dim_account["is_subtotal"].astype(bool)
    dim_version = pd.DataFrame(VERSIONS, columns=["version_id", "name", "actual_months", "is_forecast"])
    dim_version["is_forecast"] = dim_version["is_forecast"].astype(bool)
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    dim_period = pd.DataFrame([{
        "month_key": int(k), "year": int(k // 100), "quarter": (int(k % 100) - 1) // 3 + 1,
        "month": int(k % 100), "month_name": month_names[int(k % 100) - 1],
        "close_date": close_date(int(k // 100), int(k % 100)),
        "is_closed": close_date(int(k // 100), int(k % 100)) <= AS_OF,
    } for k in month_keys])

    bu_ids = np.array([bu.bu_id for bu in bus])
    version_id = {v[1]: v[0] for v in VERSIONS}
    fact_parts, stat_parts = [], []

    def add(vname, arrays, stat_arrays, mask):
        keys = month_keys[mask]
        nm = len(keys)
        for c in LEAF_CODES:
            fact_parts.append(pd.DataFrame({
                "month_key": np.tile(keys, nb), "bu_id": np.repeat(bu_ids, nm),
                "account_id": LEAF_ID[c], "version_id": version_id[vname],
                "amount_usd": np.round(arrays[c][:, mask].ravel(), 2)}))
        part = {"month_key": np.tile(keys, nb), "bu_id": np.repeat(bu_ids, nm), "version_id": version_id[vname]}
        for k in STAT_KEYS:
            part[k] = np.round(stat_arrays[k][:, mask].ravel(), 2 if k in ("fte", "headcount", "direct_fte") else 1)
        stat_parts.append(pd.DataFrame(part))

    all_months = np.ones(N_OUT, dtype=bool)
    add("Actual", truth_out, stats_out, actual_mask)
    add("Budget", bud, bud_stats, all_months)
    for vname in forecasts:
        add(vname, forecasts[vname], fc_stats[vname], all_months)
    fact_pnl = pd.concat(fact_parts, ignore_index=True)
    fact_stats = pd.concat(stat_parts, ignore_index=True)

    app_user = pd.DataFrame([(u[0], u[1], u[2]) for u in USERS], columns=["user_id", "display_name", "role"])
    user_org_access = pd.DataFrame([(u[0], u[3], u[4]) for u in USERS], columns=["user_id", "org_level", "org_value"])

    # Control totals: intended Production (independent variable) + subtotals from unrounded leaves
    ctrl_parts = []

    def ctrl(vname, arrays, prod_arr, mask):
        keys = month_keys[mask]
        line = {}
        for ln in sorted(set(LEAF_LINE.values())):
            line[ln] = sum(arrays[c][:, mask] for c in LEAF_CODES if LEAF_LINE[c] == ln)
        revenue = line[1] + line[2]
        production = prod_arr[:, mask] if prod_arr is not None else revenue + line[4] + line[5]
        gross = production + line[7] + line[8] + line[9] + line[10]
        maop = gross + line[12]
        mop = maop + line[17]
        net = mop + line[19] + line[20]
        ctrl_parts.append(pd.DataFrame({
            "month_key": np.tile(keys, nb), "bu_id": np.repeat(bu_ids, len(keys)),
            "version_id": version_id[vname], "revenue": revenue.ravel(), "production": production.ravel(),
            "gross_profit": gross.ravel(), "maop": maop.ravel(), "management_op": mop.ravel(),
            "net_income": net.ravel()}))

    ctrl("Actual", truth_out, prod[:, sim_out], actual_mask)
    ctrl("Budget", bud, bud_prod, all_months)
    for vname in forecasts:
        ctrl(vname, forecasts[vname], None, all_months)
    control = pd.concat(ctrl_parts, ignore_index=True)

    first_day = date(FIRST_YEAR, 1, 1)
    dim_calendar = calendar[calendar["date"] >= first_day].reset_index(drop=True)
    working_days_out = working_days[working_days["month_key"] >= FIRST_YEAR * 100 + 1].reset_index(drop=True)
    tables = {"dim_org": dim_org, "dim_account": dim_account, "dim_version": dim_version,
              "dim_period": dim_period, "fact_pnl": fact_pnl, "fact_stats": fact_stats,
              "app_user": app_user, "user_org_access": user_org_access,
              "dim_employee": dim_employee, "fact_employee_month": fact_employee_month,
              "dim_calendar": dim_calendar, "working_days": working_days_out}
    for name, df in tables.items():
        df.to_parquet(DATA / f"{name}.parquet", index=False)
    control.to_parquet(DATA / "control_totals.parquet", index=False)

    # Hidden truth for tests and backtests ONLY (never loaded into the database, never read by the app):
    # the true month-end values of the open month and the generator's pattern / bias per BU.
    open_idx = int(np.argmax(~actual_mask)) if (~actual_mask).any() else None
    if open_idx is not None:
        open_key = int(month_keys[open_idx])
        pd.DataFrame([{"month_key": open_key, "bu_id": int(bu_ids[b]), "account_id": LEAF_ID[c],
                       "amount_usd": round(float(truth_out[c][b, open_idx]), 2)}
                      for b in range(nb) for c in LEAF_CODES]).to_parquet(
            DATA / "eval_truth_open_month.parquet", index=False)
    pd.DataFrame([{"bu_id": bu.bu_id, "pattern": bu.pattern, "fc_bias": round(bu.fc_bias, 4),
                   "landing_story": next((k for k, v in LANDING_STORY.items() if v == (bu.country, bu.pl)), None)}
                  for bu in bus]).to_parquet(DATA / "eval_truth_patterns.parquet", index=False)
    stories = compute_stories(tables)
    (DATA / "stories.json").write_text(json.dumps(stories, indent=2, default=str))

    print(f"Generated {nb} BUs in {dim_org.l3_country.nunique()} countries / {dim_org.l2_region.nunique()} regions, "
          f"last closed month {last_closed_key}")
    for name, df in tables.items():
        print(f"  {name:<16} {len(df):>9,} rows")
    print("  fact_pnl rows per version:",
          fact_pnl.groupby("version_id").size().rename(index={v[0]: v[1] for v in VERSIONS}).to_dict())


# --------------------------------------------------------------------------------------
# Story numbers (computed from the generated tables, exactly as stored)
# --------------------------------------------------------------------------------------
def compute_stories(t: dict[str, pd.DataFrame]) -> dict:
    f = t["fact_pnl"].merge(t["dim_account"][["account_id", "line_no", "l3_code"]], on="account_id")
    f = f.merge(t["dim_org"][["bu_id", "l3_country", "l4_product_line"]], on="bu_id")
    f["version"] = f["version_id"].map(dict(zip(t["dim_version"].version_id, t["dim_version"].name)))
    s = t["fact_stats"].merge(t["dim_org"][["bu_id", "l3_country", "l4_product_line"]], on="bu_id")
    s["version"] = s["version_id"].map(dict(zip(t["dim_version"].version_id, t["dim_version"].name)))

    def lines(df):
        g = df.groupby("line_no")["amount_usd"].sum()
        get = lambda k: float(g.get(k, 0.0))  # noqa: E731
        rev = get(1) + get(2)
        prod_ = rev + get(4) + get(5)
        gross = prod_ + get(7) + get(8) + get(9) + get(10)
        maop = gross + get(12)
        mop = maop + get(17)
        p7a = -float(df[df.l3_code.str.startswith("7A")]["amount_usd"].sum())
        return {"billing": get(1), "wip_ui": get(2), "revenue": rev, "production": prod_,
                "personnel": -get(7), "personnel_7a": p7a, "subcontracting": -get(8), "other": -get(9),
                "functional_costs": -get(12), "gross_profit": gross, "maop": maop,
                "other_opex": -get(17), "management_op": mop, "net_income": mop + get(19) + get(20)}

    def slice_(story, version, k0, k1, frame=None):
        frame = f if frame is None else frame
        d = frame[(frame.version == version) & (frame.month_key >= k0) & (frame.month_key <= k1)]
        if story:
            country, pl = STORY[story]
            d = d[(d.l3_country == country) & (d.l4_product_line == pl)]
        return d

    r = lambda x: round(float(x), 2)  # noqa: E731
    out = {"stories": {k: f"{v[0]} · {v[1]}" for k, v in STORY.items()}}

    d = slice_("a", "Actual", 202201, 202612)
    bonus = -d[d.l3_code == "7A2"].groupby("month_key")["amount_usd"].sum()
    others = bonus[(bonus.index >= 202501) & (bonus.index <= 202512) & (bonus.index != 202503)]
    p7a = -d[d.l3_code.str.startswith("7A")].groupby("month_key")["amount_usd"].sum()
    out["a"] = {"bonus_7A2_mar_2025": r(bonus.get(202503, 0)), "bonus_7A2_mar_2024": r(bonus.get(202403, 0)),
                "bonus_7A2_avg_other_months_2025": r(others.mean()),
                "ratio_vs_mar_2024": r(bonus.get(202503, 0) / bonus.get(202403, 1)),
                "personnel_7A_mar_2025": r(p7a.get(202503, 0)), "personnel_7A_mar_2024": r(p7a.get(202403, 0))}

    cy, py, bu = (lines(slice_("b", "Actual", 202601, 202610)), lines(slice_("b", "Actual", 202501, 202510)),
                  lines(slice_("b", "Budget", 202601, 202610)))
    monthly = {}
    for k in range(202601, 202611):
        x = lines(slice_("b", "Actual", k, k))
        monthly[k] = {"production": r(x["production"]), "personnel": r(x["personnel"]), "maop": r(x["maop"]),
                      "maop_margin_revenue_pct": r(100 * x["maop"] / x["revenue"])}
    st_cy = slice_("b", "Actual", 202601, 202610, s)
    st_py = slice_("b", "Actual", 202501, 202510, s)
    restr = slice_("b", "Actual", 202605, 202605)
    out["b"] = {"ytd_oct_2026": {k: r(v) for k, v in cy.items()}, "ytd_oct_2025": {k: r(v) for k, v in py.items()},
                "budget_ytd_oct_2026": {k: r(v) for k, v in bu.items()},
                "production_change_vs_py_pct": r(100 * (cy["production"] / py["production"] - 1)),
                "production_change_vs_budget_pct": r(100 * (cy["production"] / bu["production"] - 1)),
                "maop_margin_revenue_ytd_2026_pct": r(100 * cy["maop"] / cy["revenue"]),
                "maop_margin_revenue_ytd_2025_pct": r(100 * py["maop"] / py["revenue"]),
                "utilization_ytd_2026_pct": r(100 * st_cy.billable_hours.sum() / st_cy.available_hours.sum()),
                "utilization_ytd_2025_pct": r(100 * st_py.billable_hours.sum() / st_py.available_hours.sum()),
                "restructuring_may_2026": r(-restr[restr.l3_code == "17.1"].amount_usd.sum()),
                "monthly_2026": monthly}

    w = slice_("c", "Actual", 202501, 202610)
    wip = w[w.l3_code == "2.1"].groupby("month_key")["amount_usd"].sum()
    bill = w[w.line_no == 1].groupby("month_key")["amount_usd"].sum()
    in26 = lambda ser, a, b: ser[(ser.index >= a) & (ser.index <= b)]  # noqa: E731
    out["c"] = {"wip_change_by_month_2026": {int(k): r(v) for k, v in in26(wip, 202601, 202610).items()},
                "billing_by_month_2026": {int(k): r(v) for k, v in in26(bill, 202601, 202610).items()},
                "wip_build_jan_jun_2026": r(in26(wip, 202601, 202606).sum()),
                "wip_reversal_jul_sep_2026": r(in26(wip, 202607, 202609).sum()),
                "wip_ytd_oct_2026": r(in26(wip, 202601, 202610).sum()),
                "wip_ytd_oct_2025": r(in26(wip, 202501, 202510).sum())}

    act26, bud26, act25 = (lines(slice_("d", "Actual", 202601, 202610)), lines(slice_("d", "Budget", 202601, 202610)),
                           lines(slice_("d", "Actual", 202501, 202510)))
    out["d"] = {"subcontracting_ytd_oct_2026_actual": r(act26["subcontracting"]),
                "subcontracting_ytd_oct_2026_budget": r(bud26["subcontracting"]),
                "subcontracting_ytd_oct_2025_actual": r(act25["subcontracting"]),
                "vs_budget_pct": r(100 * (act26["subcontracting"] / bud26["subcontracting"] - 1)),
                "vs_py_pct": r(100 * (act26["subcontracting"] / act25["subcontracting"] - 1)),
                "subcontracting_pct_of_production_2026": r(100 * act26["subcontracting"] / act26["production"]),
                "subcontracting_pct_of_production_2025": r(100 * act25["subcontracting"] / act25["production"]),
                "maop_ytd_oct_2026_actual": r(act26["maop"]), "maop_ytd_oct_2026_budget": r(bud26["maop"])}

    marg, marg_fy = {}, {}
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        x = lines(slice_("e", "Actual", y * 100 + 1, y * 100 + 10))
        marg[f"YTD Oct {y}"] = r(100 * x["maop"] / x["revenue"])
        if y < LAST_YEAR:
            x = lines(slice_("e", "Actual", y * 100 + 1, y * 100 + 12))
            marg_fy[f"FY {y}"] = r(100 * x["maop"] / x["revenue"])
    out["e"] = {"maop_margin_revenue_pct_ytd_oct": marg, "maop_margin_revenue_pct_fy": marg_fy}

    g = lines(slice_(None, "Actual", 202501, 202512))
    gs = slice_(None, "Actual", 202501, 202512, s)
    out["group_fy2025"] = {k: r(v) for k, v in g.items()}
    out["group_fy2025"].update({
        "maop_margin_revenue_pct": r(100 * g["maop"] / g["revenue"]),
        "direct_margin_pct": r(100 * (g["production"] - g["personnel_7a"]) / g["production"]),
        "avg_fte": r(gs.groupby("month_key").fte.sum().mean()),
        "avg_headcount": r(gs.groupby("month_key").headcount.sum().mean()),
        "utilization_pct": r(100 * gs.billable_hours.sum() / gs.available_hours.sum())})

    # Workforce (employee tables)
    fe = t["fact_employee_month"].merge(t["dim_employee"][["employee_id", "role", "grade", "staff_type",
                                                           "leave_reason"]], on="employee_id")
    fe = fe.merge(t["dim_org"][["bu_id", "l3_country", "l4_product_line"]], on="bu_id")

    def wf(df):
        hc = df.groupby("month_key").size()
        months = max(len(hc), 1)
        leavers = int(df.is_leaver.sum())
        return {"avg_headcount": r(hc.mean()), "leavers": leavers, "hires": int(df.is_hire.sum()),
                "voluntary_leavers": int((df.is_leaver & (df.leave_reason == "Voluntary")).sum()),
                "restructuring_leavers": int((df.is_leaver & (df.leave_reason == "Restructuring")).sum()),
                "attrition_annualised_pct": r(100 * leavers / max(hc.mean(), 1e-9) * 12 / months),
                "utilization_pct": r(100 * df.billable_hours.sum() / max(df.available_hours.sum(), 1e-9))}

    in_range = lambda df, a, b: df[(df.month_key >= a) & (df.month_key <= b)]  # noqa: E731
    out["workforce_group_fy2025"] = wf(in_range(fe, 202501, 202512))
    country, pl = STORY["b"]
    sb = fe[(fe.l3_country == country) & (fe.l4_product_line == pl)]
    out["workforce_b"] = {"ytd_oct_2026": wf(in_range(sb, 202601, 202610)),
                          "ytd_oct_2025": wf(in_range(sb, 202501, 202510)),
                          "restructuring_leavers_by_month_2026": {
                              int(k): int(v) for k, v in in_range(sb, 202601, 202610)[
                                  lambda d: d.is_leaver & (d.leave_reason == "Restructuring")]
                              .groupby("month_key").size().items()},
                          "utilization_by_role_ytd_oct_2026_pct": {
                              role: r(100 * g.billable_hours.sum() / g.available_hours.sum())
                              for role, g in in_range(sb[sb.staff_type == "Direct"], 202601, 202610).groupby("role")}}
    return out


if __name__ == "__main__":
    main()
