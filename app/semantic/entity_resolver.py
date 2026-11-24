"""Deterministic entity resolution for finance questions.

Finds, in free text:
* org entities at any level L1..L6 (exact aliases, ISO codes, BU codes, fuzzy typos via rapidfuzz)
* metrics (P&L lines, 7A/7B, leaf accounts, stats), ratios (library + "X as % of Y" composition)
* periods (via time_intel), versions (Budget/FC1-3/latest forecast) and comparisons (PY ...)
* analysis hints: intent (why / trend / rank / breakdown / versions / pnl), top-N, ranking level

The output is used directly by the tools (robust to small LLMs) and shown to the LLM as hints.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from functools import lru_cache

import pandas as pd
from rapidfuzz import fuzz, process
from rapidfuzz.distance import DamerauLevenshtein

from app.semantic import time_intel as ti
from app.semantic.registry import registry

ORG_LEVELS = ["l1_group", "l2_region", "l3_country", "l4_product_line", "l5_business", "l6_bu"]
LEVEL_LABEL = {"l1_group": "Group", "l2_region": "Region", "l3_country": "Country",
               "l4_product_line": "Product line", "l5_business": "Business", "l6_bu": "BU"}

GROUP_ALIASES = ["rl group", "rl", "rl americas", "the group", "whole group", "total group", "group total",
                 "group level", "whole company", "total company", "consolidated", "overall", "americas",
                 "total americas", "group"]
REGION_ALIASES = {
    "US & Canada": ["us and canada", "us canada", "usca", "us/canada", "usa and canada", "north america",
                    "united states and canada", "nam", "us and ca"],
    "Mexico": [],                      # region and country share the name: the country alias is used
    "Northern South America": ["northern south america", "north south america", "nsa", "andean region", "andean",
                               "northern latam"],
    "Southern South America": ["southern south america", "south south america", "ssa", "southern cone",
                               "southern latam"],
    "BPU": ["bpu", "brazil paraguay uruguay", "brazil paraguay and uruguay", "brazil, paraguay and uruguay"],
}
# phrases that cover several regions (OR within the level)
MULTI_REGION_ALIASES = {
    "south america": ["Northern South America", "Southern South America", "BPU"],
    "latin america": ["Mexico", "Northern South America", "Southern South America", "BPU"],
    "latam": ["Mexico", "Northern South America", "Southern South America", "BPU"],
}
COUNTRY_ALIASES = {
    "United States": ["united states", "usa", "u s a", "united states of america", "the us", "the states",
                      "american business", "u s"],
    "Canada": ["canada", "canadian"],
    "Mexico": ["mexico", "mexican"],
    "Colombia": ["colombia", "colombian"],
    "Peru": ["peru", "peruvian"],
    "Ecuador": ["ecuador", "ecuadorian"],
    "Argentina": ["argentina", "argentinian", "argentine"],
    "Chile": ["chile", "chilean"],
    "Brazil": ["brazil", "brasil", "brazilian"],
    "Paraguay": ["paraguay", "paraguayan"],
    "Uruguay": ["uruguay", "uruguayan"],
}
# ISO codes, matched only when written in upper case. "PY" is deliberately absent (= prior year).
COUNTRY_CODES = {"US": "United States", "USA": "United States", "CA": "Canada", "MX": "Mexico",
                 "CO": "Colombia", "PE": "Peru", "EC": "Ecuador", "AR": "Argentina", "CL": "Chile",
                 "BR": "Brazil", "UY": "Uruguay"}
PL_ALIASES = {
    "Buildings & Infrastructure": ["buildings and infrastructure", "b and i", "bni", "buildings", "building",
                                   "infrastructure", "infra", "building inspection", "buildings inspection",
                                   "building and inspection", "construction"],
    "Industry & Energy": ["industry and energy", "industry", "industrial", "energy", "oil and gas",
                          "industry capex", "industry opex", "i and e"],
    "Power & Utilities": ["power and utilities", "power", "utilities", "power generation", "utility"],
    "Elevators & Pressure Vessels": ["elevators and pressure vessels", "elevators and pv", "elevators", "elevator",
                                     "lifts", "lift", "escalators", "pressure vessels", "pressure vessel",
                                     "pressure equipment", "boilers", "epv"],
    "Environmental Lab Testing": ["environmental lab testing", "environmental testing", "environmental lab",
                                  "environmental labs", "environmental laboratories", "environmental",
                                  "env lab", "env labs", "env testing", "env", "environment", "lab testing"],
    "Consumer Products": ["consumer products", "consumer product", "consumer", "consumer product testing",
                          "product testing", "softlines", "hardlines"],
    "Certification & Sustainability": ["certification and sustainability", "certification", "certifications",
                                       "sustainability", "cert", "esg", "iso certification", "management systems"],
    "Metals & Minerals": ["metals and minerals", "metals", "minerals", "mining", "m and m"],
}
PL_CODES = {"BNI": "Buildings & Infrastructure", "IND": "Industry & Energy", "PWR": "Power & Utilities",
            "EPV": "Elevators & Pressure Vessels", "ENV": "Environmental Lab Testing", "CPS": "Consumer Products",
            "CER": "Certification & Sustainability", "MMI": "Metals & Minerals", "MM": "Metals & Minerals"}
PL_SHORT = {"Buildings & Infrastructure": "B&I", "Industry & Energy": "Industry", "Power & Utilities": "Power",
            "Elevators & Pressure Vessels": "Elevators & PV", "Environmental Lab Testing": "Env Lab",
            "Consumer Products": "Consumer Products", "Certification & Sustainability": "Certification",
            "Metals & Minerals": "M&M"}

STOPWORDS = set("""a an the for of in on at to by vs versus and or with from this that these those
show me what how is are was were did do does give tell list which who why when where same period
last next year years month months quarter ytd qtd fy now then also please all each per across
compare comparison against than as percent percentage trend over time since until through split
break down breakdown top bottom best worst highest lowest rank ranking cost costs total value
values number numbers drop dropped increase increased decrease decreased happen happened change
changed driver drivers explain about our my their its it be been being get got report view""".split())

INTENT_PATTERNS = {
    "why": r"\b(why|drivers?|driving|drove|explain|explanation|reasons?|caused?|causes|bridge|walk|root cause|what explains)\b",
    "trend": r"\b(trend|trends|over time|monthly|month by month|month-by-month|since|evolution|evolve|evolved|develop|develops|development|history|historical|progression|what happened|how has .* developed|developed)\b",
    "rank": r"\b(top|bottom|rank|ranking|ranked|best|worst|highest|lowest|largest|smallest|biggest|leaders|laggards|which (bu|bus|business|businesses|country|countries|product line|product lines|region|regions))\b",
    "breakdown": r"\b(break ?down|breakdown|split|composition|mix|components|by account|detail|details|drill)\b",
    "versions": r"\b(versions|budget vs\.? fc|fc\d? vs|vs\.? fc\d|forecast vs|vs\.? forecast|compare (the )?(budget|forecast|fc))\b",
    "pnl": r"(p&l|\bpnl\b|p and l|income statement|profit and loss|\bstatement\b|full p ?& ?l|\bgeneral ledger\b|\bgl\b)",
    "cockpit": r"\b(cockpit|kpis?|dashboard|operational profitability|scorecard|key metrics|key figures|performance overview|direct margin drivers)\b",
    # employee records: attrition, hires / leavers, and anything by role, grade or staff type ("turnover" alone
    # is revenue; "staff turnover" / "turnover rate" is attrition)
    "workforce": r"\b(attrition|churn|retention|leavers?|resign\w*|quits?|layoffs?|laid off|redundanc\w*|"
                 r"hires|new hires?|hiring|hired|joiners?|new starters?|recruit\w*|workforce|grades?|seniority|"
                 r"staff types?|job roles?|roles|by role|per role|each role)\b"
                 r"|\b(staff|employee|people|personnel)\s+turnover\b|\bturnover rate\b"
                 r"|\b(employees|people|staff|headcount)\s+(have\s+|has\s+)?left\b|\bhow many (employees|people)\b"
                 r"|\bdirect\s+(vs\.?|versus|and)\s+indirect\s+(staff|employees|people|headcount)\b(?!\s+costs?)",
    # current-month landing: expected month-end of the open month (and YTD / full year including it)
    "landing": r"\b(landings?|lands?|landed|expected month[- ]end|month[- ]end (estimate|outlook|projection|forecast)|"
               r"nowcast|full[- ]year outlook|fy outlook|year[- ]end outlook)\b"
               r"|\bwhere will\b.*\bland\b|\b(expected|projected|likely|set|on track|going) to (miss|beat|hit|make|exceed|"
               r"land|fall short of|come in)\b|\bwill\b.{0,40}\b(miss|beat|hit|make|exceed)\b.{0,12}\bbudget\b",
    # discovery: what IRIS covers (answered from the data catalog, never with SQL)
    "catalog": r"\b(what|which) (regions|countries|businesses|business units|bus|product lines|metrics|measures|kpis|"
               r"ratios|versions|periods|accounts|p&l lines|billing patterns)\b.{0,40}\b(in scope|can i|could i|are there|"
               r"do you|are available|available|covered|exist|supported|do we have|are included|included)\b"
               r"|\b(list|show|name)( me)?( all| the)? (regions|countries|businesses|business units|bus|product lines|"
               r"metrics|measures|kpis|ratios|versions|accounts|p&l lines|billing patterns)\b(?!\s+(by|with|for|in)\b)"
               r"|\bwhat (can|do) you (do|know|cover|support|offer)\b|\bwhat data\b|\bwhich data\b|\bdata catalog\b"
               r"|\bwhat can i ask\b|\bexample questions\b|\bcapabilities\b|\bhow do i use\b|^\s*help\s*[?!.]*\s*$"
               r"|\bwhat (ratios|metrics) do you\b|\bin scope\b"
               r"|\b(what|which) (regions|countries|businesses|business units|bus|product lines)\s+(are|exist|sit|belong)"
               r"\s+(in|within|under|to)\b(?!.*\b(red|black|loss|losses|profit|budget|margin|revenue|billing|growth|"
               r"decline|drop|deficit|target|plan)\b)",
}
LEVEL_PATTERNS = [
    ("l6_bu", r"\b(by|per|each|across|which|all|top|bottom|worst|best)\s+(\d+\s+)?(bus|bu|business units?)\b|\bbus\b|\bbu by bu\b"),
    ("l5_business", r"\b(by|per|each|across|which|all|top|bottom|worst|best)\s+(\d+\s+)?(businesses|business)\b|\bbusinesses\b"),
    ("l4_product_line", r"\b(by|per|each|across|which|all|top|bottom|worst|best)\s+(\d+\s+)?(product lines?|pls?)\b|\bproduct lines\b"),
    ("l3_country", r"\b(by|per|each|across|which|all|top|bottom|worst|best)\s+(\d+\s+)?(countries|country)\b|\bcountries\b"),
    ("l2_region", r"\b(by|per|each|across|which|all|top|bottom|worst|best)\s+(\d+\s+)?(regions?)\b|\bregions\b"),
]
PY_RX = re.compile(r"\b(?:vs\.?|versus|compared? (?:(?:it|that|this|them|these|those) )?(?:to|with)|"
                   r"comparison (?:to|with)|against|than|relative to|over)\s+(?:the\s+)?"
                   r"(?:last year|prior year|previous year|py|ly|same period last year|a year ago)\b"
                   r"|\b(?:yoy|y-o-y|year[- ]over[- ]year|year[- ]on[- ]year)\b|\bsame period last year\b"
                   r"|\bvs\.?\s*py\b")
# Corrections ("not YTD, full year 2025", "net income, not operating profit", "Q3 instead of YTD"): the negated
# phrase is removed before parsing, but only when it starts with something the resolver knows (period, version,
# comparison, measure, workforce figure, org), so "BUs that did not meet budget" keeps its meaning.
NEGATION_RX = re.compile(r"\b(?:not|instead of|rather than)\s+(?P<phrase>[^,.;:?!]+?)"
                         r"(?=\s*(?:[,.;:?!]|\bbut\b|\brather\b|\binstead\b|\bplease\b|$))", re.I)
NEG_LEAD_RX = re.compile(r"^(?:(?:the|for|in|on|at|of|vs\.?|versus|against|compared (?:to|with))\s+)+", re.I)
NOT_A_CORRECTION = set("""meet met meeting reach reached achieve achieved hit beat beating exceed exceeded make made
perform performing performed doing done do profitable good bad enough so very too as yet only just much many sure
right correct wrong included including counting part available growing improving""".split())
SLOT_START_RX = re.compile(r"^(?:py|ly|prior year|previous year|last year|budget|plan|forecast|outlook|fc\s*[123]|"
                           r"actuals?|attrition|voluntary attrition|leavers?|restructuring leavers|hires|headcount|"
                           r"utili[sz]ation|overtime|fte)\b", re.I)
VERSION_RXS = [
    ("FC1", re.compile(r"\b(?:fc\s*1|forecast\s*1|first forecast)\b")),
    ("FC2", re.compile(r"\b(?:fc\s*2|forecast\s*2|second forecast)\b")),
    ("FC3", re.compile(r"\b(?:fc\s*3|forecast\s*3|third forecast)\b")),
    ("LatestFC", re.compile(r"\b(?:latest|current|last|newest)\s+(?:forecast|fc|outlook|estimate)\b|\boutlook\b|\bforecast\b(?!\s*\d)")),
    ("Budget", re.compile(r"\bbudget(?:s|ed)?\b|\bplan\b")),
    ("Actual", re.compile(r"\bactuals?\b")),
]
BU_CODE_RX = re.compile(r"\b([A-Za-z]{2})[- ]([A-Za-z]{3})[- ]([A-Za-z]{3})[- ](\d{2})\b")
RATIO_CONNECTOR = re.compile(r"(as\s+(?:a\s+)?(?:%|percent(?:age)?|share)\s+of|%\s+of|\s/\s|/|\bto\b|\bover\b|\brelative to\b|\bper\b|\bdivided by\b|\bratio\b)")


@dataclass
class Match:
    kind: str           # org | metric | ratio | ambiguous_org
    text: str
    start: int
    end: int
    score: float
    payload: dict


@dataclass
class Resolution:
    text: str
    org_filter: dict[str, list[str]] = field(default_factory=dict)
    org_matches: list[dict] = field(default_factory=list)
    ambiguous: list[dict] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    ratio: str | None = None
    period: dict | None = None
    period_is_range: bool = False
    versions: list[str] = field(default_factory=list)
    comparisons: list[str] = field(default_factory=list)
    level_hint: str | None = None
    top_n: int | None = None
    ascending: bool | None = None
    intents: list[str] = field(default_factory=list)
    negated: list[str] = field(default_factory=list)     # phrases corrected away ("not YTD" -> ["YTD"])
    clean_text: str = ""                                 # the question without those phrases
    both_margins: bool = False                           # "profit %" / "margin" without a base: show both

    @property
    def metric(self) -> str | None:
        return self.ratio or (self.metrics[0] if self.metrics else None)

    def org_label(self) -> str:
        return org_label(self.org_filter)

    def period_obj(self) -> ti.Period | None:
        if not self.period:
            return None
        if self.period["type"] == "RANGE":
            return ti.Period("RANGE", self.period["end"], self.period["start"])
        return ti.Period(self.period["type"], self.period["end"])

    def to_dict(self) -> dict:
        d = asdict(self)
        d["org_label"] = self.org_label() if self.org_filter else None
        d["metric"] = self.metric
        return d


def org_label(org_filter: dict[str, list[str]] | None) -> str:
    if not org_filter:
        return "RL Group"
    parts = []
    specific = any(lvl in org_filter for lvl in ORG_LEVELS[1:])
    for lvl in ORG_LEVELS:
        if lvl in org_filter and not (lvl == "l1_group" and specific):
            parts.append(" + ".join(org_filter[lvl]))
    return " · ".join(parts)


def normalize(text: str) -> str:
    t = text.lower().replace("&", " and ").replace("’", "'")
    t = re.sub(r"[^\w%./\-' ]+", " ", t)
    t = re.sub(r"(?<!\d)\.(?!\d)", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ------------------------------------------------------------------------------------------
# Alias index
# ------------------------------------------------------------------------------------------
@lru_cache(maxsize=4)
def _org_index(org_records: tuple) -> dict[str, list[dict]]:
    org = pd.DataFrame(list(org_records), columns=["l1_group", "l2_region", "l3_country",
                                                    "l4_product_line", "l5_business", "l6_bu", "city"])
    idx: dict[str, list[dict]] = {}

    def add(alias: str, level: str, value: str):
        key = normalize(alias)
        if not key:
            return
        entry = {"level": level, "value": value}
        if entry not in idx.setdefault(key, []):
            idx[key].append(entry)

    for g in org["l1_group"].unique():
        add(g, "l1_group", g)
        for a in GROUP_ALIASES:
            add(a, "l1_group", g)
    countries = set(org["l3_country"].unique())
    for r in org["l2_region"].unique():
        if r not in countries:
            add(r, "l2_region", r)
        for a in REGION_ALIASES.get(r, []):
            add(a, "l2_region", r)
    for alias, regions in MULTI_REGION_ALIASES.items():
        for r in regions:
            if r in set(org["l2_region"]):
                add(alias, "l2_region", r)
    for c in org["l3_country"].unique():
        add(c, "l3_country", c)
        for a in COUNTRY_ALIASES.get(c, []):
            add(a, "l3_country", c)
    for p in org["l4_product_line"].unique():
        add(p, "l4_product_line", p)
        for a in PL_ALIASES.get(p, []):
            add(a, "l4_product_line", p)
    for _, row in org.drop_duplicates("l5_business").iterrows():
        b, city, pl = row["l5_business"], row["city"], row["l4_product_line"]
        add(b, "l5_business", b)
        for pl_alias in [PL_SHORT.get(pl, pl)] + PL_ALIASES.get(pl, [])[:4]:
            add(f"{pl_alias} {city}", "l5_business", b)
            add(f"{city} {pl_alias}", "l5_business", b)
            add(f"{pl_alias} in {city}", "l5_business", b)
    for _, row in org.iterrows():
        add(row["l6_bu"], "l6_bu", row["l6_bu"])
    # bare city names -> all businesses in that city (may be ambiguous)
    for city, grp in org.groupby("city"):
        for b in sorted(grp["l5_business"].unique()):
            add(city, "l5_business", b)
    return idx


@lru_cache(maxsize=1)
def _metric_index() -> dict[str, list[dict]]:
    reg = registry()
    idx: dict[str, list[dict]] = {}

    def add(alias: str, kind: str, mid: str):
        key = normalize(alias)
        if key and {"kind": kind, "id": mid} not in idx.setdefault(key, []):
            idx[key].append({"kind": kind, "id": mid})

    for m in reg.metrics.values():
        for s in m.synonyms:
            add(s, "metric", m.id)
        add(m.name, "metric", m.id)
        if m.kind == "leaf":
            add(m.code, "metric", m.id)
        if m.kind == "line":
            add(f"line {m.line}", "metric", m.id)
    for r in reg.ratios.values():
        add(r.name, "ratio", r.id)
        for s in r.synonyms:
            add(s, "ratio", r.id)
    for p in reg.pairs.values():
        add(p.name, "pair", p.id)
        for s in p.synonyms:
            add(s, "pair", p.id)
    return idx


def _org_records(org_df: pd.DataFrame) -> tuple:
    cols = ["l1_group", "l2_region", "l3_country", "l4_product_line", "l5_business", "l6_bu", "city"]
    return tuple(map(tuple, org_df[cols].drop_duplicates().itertuples(index=False, name=None)))


# ------------------------------------------------------------------------------------------
# Matching
# ------------------------------------------------------------------------------------------
def _tokens(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in re.finditer(r"[\w%./\-']+", text)]


def _is_transposition(a: str, b: str) -> bool:
    """True if b is a with exactly one pair of adjacent letters swapped."""
    if len(a) != len(b) or a == b:
        return False
    diff = [i for i in range(len(a)) if a[i] != b[i]]
    return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]


def _fuzzy_ok(ngram: str, alias: str, **_kwargs) -> float:
    if len(ngram) < 5 or len(alias) < 5:
        return 0.0
    if ngram in STOPWORDS:
        return 0.0
    if _is_transposition(ngram, alias):
        return 90.0
    s1 = fuzz.ratio(ngram, alias)
    s2 = DamerauLevenshtein.normalized_similarity(ngram, alias) * 100
    return max(s1, s2)


def _find_matches(norm: str, index: dict[str, list[dict]], kind: str, max_n: int = 6,
                  fuzzy: bool = True, blocked: list[tuple[int, int]] | None = None) -> list[Match]:
    toks = _tokens(norm)
    # typo-tolerant matching only for single words and only for coarse org levels / metrics
    keys = [k for k, targets in index.items() if " " not in k and all(
        t.get("level") in (None, "l1_group", "l2_region", "l3_country", "l4_product_line") for t in targets)]
    found: list[Match] = []
    blocked = blocked or []
    for n in range(min(max_n, len(toks)), 0, -1):
        for i in range(len(toks) - n + 1):
            start, end = toks[i][1], toks[i + n - 1][2]
            if any(not (end <= b0 or start >= b1) for b0, b1 in blocked):
                continue
            gram = norm[start:end]
            if toks[i][0] in STOPWORDS and n > 1 and gram not in index:
                continue
            if gram in index:
                found.append(Match(kind, gram, start, end, 100.0 + n, {"targets": index[gram]}))
                continue
            if fuzzy and n == 1 and gram not in STOPWORDS and keys:
                best = process.extractOne(gram, keys, scorer=_fuzzy_ok, score_cutoff=86)
                if best:
                    found.append(Match(kind, gram, start, end, float(best[1]) + n,
                                       {"targets": index[best[0]], "alias": best[0]}))
    # greedy, longest/highest first, non-overlapping
    found.sort(key=lambda m: (-(m.end - m.start), -m.score))
    chosen: list[Match] = []
    for m in found:
        if all(m.end <= c.start or m.start >= c.end for c in chosen):
            chosen.append(m)
    return sorted(chosen, key=lambda m: m.start)


def _names_a_slot(phrase: str, org_idx: dict[str, list[dict]], as_of: date) -> bool:
    """True if the phrase starts with something the resolver knows: a period, version, comparison, measure,
    workforce figure or org ("YTD", "net income", "Canada"), not a verb or adjective ("meet budget")."""
    core = NEG_LEAD_RX.sub("", phrase.strip())
    words = core.split()
    if not words or words[0].lower() in NOT_A_CORRECTION:
        return False
    if SLOT_START_RX.match(core) or words[0] in COUNTRY_CODES or words[0] in PL_CODES:
        return True
    pp = ti.parse_period_text(core, as_of)
    if pp.period and pp.matched and core.lower().startswith(pp.matched[0].strip()):
        return True
    norm = normalize(core)
    for idx, kind in ((_metric_index(), "metric"), (org_idx, "org")):
        hits = _find_matches(norm, idx, kind, fuzzy=False)
        if hits and hits[0].start == 0:
            return True
    return False


def strip_negations(text: str, org_idx: dict[str, list[dict]], as_of: date) -> tuple[str, list[str]]:
    """Blank out corrected-away phrases ("not YTD", "instead of net income"). Returns (text, removed phrases);
    the text keeps its length and letter case, so code and position-based matching still work."""
    removed: list[str] = []

    def repl(m: re.Match) -> str:
        if not _names_a_slot(m.group("phrase"), org_idx, as_of):
            return m.group(0)
        removed.append(NEG_LEAD_RX.sub("", m.group("phrase").strip()))
        return " " * len(m.group(0))

    return NEGATION_RX.sub(repl, text or ""), removed


def resolve(text: str, org_df: pd.DataFrame, as_of: date | None = None) -> Resolution:
    as_of = as_of or ti.as_of_date()
    res = Resolution(text=text)
    org_idx = _org_index(_org_records(org_df))
    raw, res.negated = strip_negations(text or "", org_idx, as_of)
    res.clean_text = re.sub(r"\s+", " ", raw).strip(" ,;")
    low = raw.lower()

    # comparisons / versions (remove PY phrases before period parsing)
    py = list(PY_RX.finditer(low))
    if py:
        res.comparisons.append("PY")
    stripped = PY_RX.sub(" ", low)
    for name, rx in VERSION_RXS:
        if rx.search(stripped):
            if name == "LatestFC" and any(v in res.versions for v in ("FC1", "FC2", "FC3")):
                continue
            res.versions.append(name)

    # period
    pp = ti.parse_period_text(stripped, as_of)
    if pp.period:
        res.period = pp.period.to_dict()
        res.period_is_range = pp.is_range

    # intents / ranking hints
    for name, pat in INTENT_PATTERNS.items():
        if re.search(pat, low):
            res.intents.append(name)
    if m := re.search(r"\b(?:top|best|highest|largest|biggest)\s*(\d{1,2})\b", low):
        res.top_n, res.ascending = int(m.group(1)), False
    elif m := re.search(r"\b(?:bottom|worst|lowest|smallest|weakest)\s*(\d{1,2})\b", low):
        res.top_n, res.ascending = int(m.group(1)), True
    elif re.search(r"\b(worst|lowest|smallest|weakest|bottom|least)\b", low):
        res.ascending = True
    elif re.search(r"\b(best|highest|largest|biggest|top|most)\b", low):
        res.ascending = False
    for lvl, pat in LEVEL_PATTERNS:
        if re.search(pat, low):
            res.level_hint = lvl
            break

    norm = normalize(raw)
    # BU codes (exact)
    org_hits: list[Match] = []
    blocked: list[tuple[int, int]] = []
    bu_set = set(org_df["l6_bu"])
    for m in BU_CODE_RX.finditer(raw):
        code = "-".join(g.upper() for g in m.groups())
        if code in bu_set:
            org_hits.append(Match("org", code, m.start(), m.end(), 200,
                                  {"targets": [{"level": "l6_bu", "value": code}]}))

    # metrics first (so "intra-group revenue", "lab consumables", "central functions" win)
    metric_hits = _find_matches(norm, _metric_index(), "metric", fuzzy=True)
    metric_spans = [(m.start, m.end) for m in metric_hits]
    period_spans = []
    for s in pp.matched:
        i = norm.find(normalize(s))
        if i >= 0:
            period_spans.append((i, i + len(normalize(s))))
    org_hits += _find_matches(norm, org_idx, "org", fuzzy=True, blocked=metric_spans + period_spans)

    # ISO country / product-line codes: only when written in upper case
    masked = raw
    for h in org_hits + metric_hits:
        words = [re.escape(w) for w in h.text.split()]
        if len(words) < 2 and "-" not in h.text:
            continue
        rx = r"\b" + r"[\s\-/,]*".join(w if w != "and" else r"(?:and|&)" for w in words) + r"\b"
        masked = re.sub(rx, lambda mm: " " * len(mm.group(0)), masked, flags=re.I)
    for m in re.finditer(r"\b([A-Z]{2,3})\b", masked):
        code = m.group(1)
        if code in COUNTRY_CODES:
            org_hits.append(Match("org", code, m.start(), m.end(), 150,
                                  {"targets": [{"level": "l3_country", "value": COUNTRY_CODES[code]}]}))
        elif code in PL_CODES:
            org_hits.append(Match("org", code, m.start(), m.end(), 150,
                                  {"targets": [{"level": "l4_product_line", "value": PL_CODES[code]}]}))

    # Combine org hits into a conjunctive filter; detect ambiguity
    filt: dict[str, list[str]] = {}
    pl_mentioned = {t["value"] for h in org_hits for t in h.payload["targets"] if t["level"] == "l4_product_line"}
    country_mentioned = {t["value"] for h in org_hits for t in h.payload["targets"] if t["level"] == "l3_country"}
    for h in org_hits:
        targets = h.payload["targets"]
        if len(targets) > 1:
            # e.g. a bare city name -> several businesses: narrow by other mentions
            narrowed = [t for t in targets if _business_matches(org_df, t["value"], pl_mentioned, country_mentioned)]
            if len(narrowed) == 1:
                targets = narrowed
            elif len({t["level"] for t in targets}) == 1 and targets[0]["level"] == "l5_business":
                res.ambiguous.append({"text": h.text, "options": [t["value"] for t in (narrowed or targets)]})
                continue
        if len(targets) > 1 and len({t["level"] for t in targets}) == 1 and targets[0]["level"] != "l5_business":
            chosen = targets                    # e.g. "South America" -> three regions
        else:
            chosen = [targets[0]]
        if chosen[0]["level"] == "l1_group" and h.text in ("group", "overall") and len(org_hits) > 1:
            continue
        for t in chosen:
            vals = filt.setdefault(t["level"], [])
            if t["value"] not in vals:
                vals.append(t["value"])
            res.org_matches.append({"text": h.text, "level": t["level"], "value": t["value"],
                                    "score": round(h.score, 1), "fuzzy": "alias" in h.payload})
    # drop L1 if more specific levels present
    if len(filt) > 1:
        filt.pop("l1_group", None)
    # a business implies its PL/country; drop redundant PL/country constraints that conflict
    res.org_filter = filt

    # metrics / ratios
    mids: list[tuple[int, str, str]] = []
    for h in metric_hits:
        targets = h.payload["targets"]
        t = sorted(targets, key=lambda x: 0 if x["kind"] in ("ratio", "pair") else 1)[0]
        mids.append((h.start, t["kind"], t["id"]))
    ratio_ids = [mid for _, kind, mid in mids if kind == "ratio"]
    pair_ids = [mid for _, kind, mid in mids if kind == "pair"]
    metric_ids = [mid for _, kind, mid in mids if kind == "metric"]
    if ratio_ids:
        res.ratio = ratio_ids[0]
    elif pair_ids:
        res.ratio = registry().pairs[pair_ids[0]].members[0]
        res.both_margins = True
    elif len(metric_ids) >= 2:
        # compose "A as % of B" / "A / B" / "A to B ratio" / "A per FTE"
        first, second = [m for m in mids if m[1] == "metric"][:2]
        between = norm[first[0]:second[0]]
        if RATIO_CONNECTOR.search(between) or re.search(r"\bratio\b", norm):
            rid = registry().find_ratio(first[2], second[2])
            res.ratio = rid or f"ratio:{first[2]}/{second[2]}"
    if re.search(r"\bper\s+(fte|head|employee)\b", norm) and metric_ids and not res.ratio:
        rid = registry().find_ratio(metric_ids[0], "fte")
        res.ratio = rid or f"ratio:{metric_ids[0]}/fte"
    parts = registry().ratio_parts(res.ratio) if res.ratio else set()
    res.metrics = [m for m in metric_ids if m not in parts]
    if "landing" in res.intents and res.period and res.period["type"] == "MONTH" and \
            not re.search(r"\b20\d\d\b|'\d\d\b", low):
        # in a landing question a month without a year means this year's month: the open month is the
        # landing month, earlier months are closed, later months are in the future
        open_key = ti.add_months(ti.last_closed_month(as_of), 1)
        key = open_key if re.search(r"\b(this|current)\s+month\b", low) else ti.mk(open_key // 100, res.period["end"] % 100)
        res.period = ti.Period("MONTH", key).to_dict()
    return res


def _business_matches(org_df: pd.DataFrame, business: str, pls: set[str], countries: set[str]) -> bool:
    rows = org_df[org_df["l5_business"] == business]
    if rows.empty:
        return False
    ok = True
    if pls:
        ok &= rows["l4_product_line"].isin(pls).any()
    if countries:
        ok &= rows["l3_country"].isin(countries).any()
    return bool(ok) and bool(pls or countries)


def resolve_org_text(text: str | None, org_df: pd.DataFrame) -> tuple[dict[str, list[str]], list[dict]]:
    """Resolve an org argument passed by the LLM (e.g. 'Brazil Environmental Lab Testing')."""
    if not text or normalize(text) in ("", "none", "null", "all", "group", "rl group", "total"):
        return {}, []
    res = resolve(text, org_df)
    return res.org_filter, res.ambiguous
