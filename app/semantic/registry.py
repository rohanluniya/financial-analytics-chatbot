"""Metric registry built from app/semantic/metrics.yaml + the chart of accounts (dim_account).

Every metric resolves to a column of the "wide" frame produced by query_builder:
  L1..L21   P&L lines by internal key (subtotals)  7A / 7B   account groups (direct / indirect staff)
  DM / DMS  computed amounts (direct margin)       <l3_code> leaf accounts (e.g. 7A2, 9.3)
  <stat>_sum statistics (FTE, headcount, hours) + n_months
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from app.semantic.dims import dims

METRICS_YAML = Path(__file__).with_name("metrics.yaml")


@dataclass(frozen=True)
class MetricDef:
    id: str
    name: str
    kind: str                    # line | group | computed | leaf | stat
    column: str
    natural_sign: int = 1
    favorable: str = "up"
    line: int | None = None
    code: str | None = None
    subtotal: bool = False
    formula: tuple[int, ...] = ()
    synonyms: tuple[str, ...] = ()
    agg: str = "sum"             # stats: avg | sum

    @property
    def is_cost(self) -> bool:
        return self.natural_sign < 0


@dataclass(frozen=True)
class RatioDef:
    id: str
    name: str
    num: str
    den: str
    fmt: str = "pct"             # pct | eur
    favorable: str = "neutral"
    annualize: bool = False
    synonyms: tuple[str, ...] = ()


@dataclass(frozen=True)
class PairDef:
    """Generic wording that means two ratios side by side (e.g. "profit %" = both operating margins)."""
    id: str
    name: str
    members: tuple[str, ...]
    synonyms: tuple[str, ...] = ()


@dataclass
class Registry:
    metrics: dict[str, MetricDef] = field(default_factory=dict)
    ratios: dict[str, RatioDef] = field(default_factory=dict)
    pairs: dict[str, PairDef] = field(default_factory=dict)
    drivers: dict[str, list[str]] = field(default_factory=dict)
    line_formulas: dict[int, tuple[int, ...]] = field(default_factory=dict)
    computed: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    cockpit: list[str] = field(default_factory=list)
    _lookup: dict[str, tuple[str, str]] = field(default_factory=dict)
    _pair_lookup: dict[str, str] = field(default_factory=dict)

    # -------------------------------------------------------------- lookup
    def _key(self, s: str) -> str:
        return re.sub(r"\s+", " ", str(s).lower().replace("&", " and ").replace("_", " ")).strip()

    def build_lookup(self) -> None:
        for m in self.metrics.values():
            for s in (m.id, m.name, *m.synonyms, *( [m.code] if m.code else [])):
                self._lookup.setdefault(self._key(s), ("metric", m.id))
            if m.line:
                self._lookup.setdefault(f"line {m.line}", ("metric", m.id))
                self._lookup.setdefault(str(m.line), ("metric", m.id))
        for r in self.ratios.values():
            for s in (r.id, r.name, *r.synonyms):
                self._lookup.setdefault(self._key(s), ("ratio", r.id))
        for p in self.pairs.values():
            for s in (p.id, p.name, *p.synonyms):
                self._pair_lookup.setdefault(self._key(s), p.id)

    def pair_for(self, name: str | None) -> PairDef | None:
        """The ratio pair named by `name` (id, name or generic synonym such as "profit %"), else None."""
        if not name:
            return None
        raw = str(name).strip()
        if raw in self.pairs:
            return self.pairs[raw]
        pid = self._pair_lookup.get(self._key(raw))
        return self.pairs[pid] if pid else None

    def resolve(self, name: str | None) -> tuple[str | None, object | None]:
        """Return ('metric', MetricDef) or ('ratio', RatioDef) for an id/name/synonym/code.

        A ratio pair (generic margin wording) resolves to its first member; callers that can show both
        check `pair_for()`."""
        if not name:
            return None, None
        raw = str(name).strip()
        pair = self.pair_for(raw)
        if pair is not None:
            return "ratio", self.ratios[pair.members[0]]
        if raw.startswith("ratio:") or ("/" in raw and not re.match(r"^\d", raw)):
            r = self.get_ratio(raw)
            if r:
                return "ratio", r
        if raw.startswith("acct:") and raw in self.metrics:
            return "metric", self.metrics[raw]
        if raw in self.metrics:
            return "metric", self.metrics[raw]
        if raw in self.ratios:
            return "ratio", self.ratios[raw]
        hit = self._lookup.get(self._key(raw))
        if hit:
            kind, mid = hit
            return kind, (self.metrics[mid] if kind == "metric" else self.ratios[mid])
        code = raw.upper().replace(" ", "")
        if f"acct:{code}" in self.metrics:
            return "metric", self.metrics[f"acct:{code}"]
        # last resort: entity resolver style match on the text
        from app.semantic.entity_resolver import _find_matches, _metric_index, normalize  # noqa: WPS433
        hits = _find_matches(normalize(raw), _metric_index(), "metric")
        if hits:
            targets = [t for t in hits[0].payload["targets"] if t["kind"] in ("metric", "ratio", "pair")]
            t = sorted(targets, key=lambda x: 0 if x["kind"] in ("ratio", "pair") else 1)[0]
            if t["kind"] == "pair":
                return "ratio", self.ratios[self.pairs[t["id"]].members[0]]
            return t["kind"], (self.metrics[t["id"]] if t["kind"] == "metric" else self.ratios[t["id"]])
        return None, None

    def get_metric(self, name: str | None) -> MetricDef | None:
        kind, obj = self.resolve(name)
        return obj if kind == "metric" else None

    def get_ratio(self, name: str | None) -> RatioDef | None:
        if not name:
            return None
        raw = str(name).strip()
        if raw in self.ratios:
            return self.ratios[raw]
        if raw.startswith("ratio:") or "/" in raw:
            body = raw.split(":", 1)[1] if raw.startswith("ratio:") else raw
            if "/" in body:
                a, b = [x.strip() for x in body.split("/", 1)]
                ma, mb = self.get_metric(a), self.get_metric(b)
                if ma and mb:
                    rid = self.find_ratio(ma.id, mb.id)
                    if rid:
                        return self.ratios[rid]
                    fav = "down" if ma.is_cost else "up"
                    per_head = mb.kind == "stat" and mb.agg == "avg"
                    per_hour = mb.kind == "stat" and mb.agg == "sum" and ma.kind != "stat"
                    fmt = "eur" if (per_head or per_hour) else "pct"
                    return RatioDef(id=f"ratio:{ma.id}/{mb.id}", name=f"{ma.name} / {mb.name}",
                                    num=ma.id, den=mb.id, fmt=fmt, favorable=fav, annualize=per_head)
        kind, obj = self.resolve(raw) if not raw.startswith("ratio:") else (None, None)
        return obj if kind == "ratio" else None

    @property
    def stat_ids(self) -> list[str]:
        return [m.id for m in self.metrics.values() if m.kind == "stat"]

    def find_ratio(self, num: str, den: str) -> str | None:
        for r in self.ratios.values():
            if r.num == num and r.den == den:
                return r.id
        return None

    def ratio_parts(self, rid: str | None) -> set[str]:
        r = self.get_ratio(rid) if rid else None
        return {r.num, r.den} if r else set()

    def leaf_codes(self, metric: MetricDef) -> list[str]:
        acc = dims().leaves
        if metric.kind == "leaf":
            return [metric.code]
        if metric.kind == "group":
            return acc[acc["l2_code"] == metric.code]["l3_code"].tolist()
        if metric.kind == "line":
            lines = self.expand_line(metric.line)
            return acc[acc["line_no"].isin(lines)]["l3_code"].tolist()
        return []

    def expand_line(self, line: int) -> list[int]:
        if line in self.line_formulas:
            out: list[int] = []
            for part in self.line_formulas[line]:
                out += self.expand_line(part)
            return out
        return [line]

    def children(self, metric: MetricDef, depth: int = 1) -> list[MetricDef]:
        """Direct drivers of a metric (depth 1) or its leaf accounts (depth >= 2)."""
        if metric.id in self.drivers and depth <= 1:
            return [self.metrics[c] for c in self.drivers[metric.id]]
        if metric.id in self.drivers and depth >= 2:
            out: list[MetricDef] = []
            for c in self.drivers[metric.id]:
                cm = self.metrics[c]
                sub = self.children(cm, depth - 1) if cm.subtotal or cm.id in self.drivers or cm.kind == "group" else []
                out += sub or [cm]
            return out
        if metric.kind in ("line", "group"):
            codes = self.leaf_codes(metric)
            if metric.kind == "line" and metric.line == 7 and depth <= 1:
                return [self.metrics["personnel_7a"], self.metrics["personnel_7b"]]
            return [self.metrics[f"acct:{c}"] for c in codes]
        return []


@lru_cache(maxsize=1)
def registry() -> Registry:
    spec = yaml.safe_load(METRICS_YAML.read_text())
    reg = Registry()
    for ln in spec["lines"]:
        reg.metrics[ln["id"]] = MetricDef(
            id=ln["id"], name=ln["name"], kind="line", column=f"L{ln['line']}",
            natural_sign=int(ln["natural_sign"]), favorable=ln["favorable"], line=int(ln["line"]),
            subtotal=bool(ln.get("subtotal", False)), formula=tuple(ln.get("formula", [])),
            synonyms=tuple(ln.get("synonyms", [])))
        if ln.get("subtotal"):
            reg.line_formulas[int(ln["line"])] = tuple(ln["formula"])
    for g in spec["groups"]:
        reg.metrics[g["id"]] = MetricDef(
            id=g["id"], name=g["name"], kind="group", column=g["code"], code=g["code"],
            natural_sign=int(g["natural_sign"]), favorable=g["favorable"], line=7,
            synonyms=tuple(g.get("synonyms", [])))
    extra = {str(k): v for k, v in (spec.get("leaf_synonyms") or {}).items()}
    for _, a in dims().leaves.iterrows():
        code = str(a["l3_code"])
        mid = f"acct:{code}"
        reg.metrics[mid] = MetricDef(
            id=mid, name=str(a['l3_name']), kind="leaf", column=code, code=code,
            natural_sign=int(a["natural_sign"]), favorable=str(a["favorable_direction"]),
            line=int(a["line_no"]), synonyms=tuple(extra.get(code, [])) + (str(a["l3_name"]),))
    for c in spec.get("computed", []):
        reg.metrics[c["id"]] = MetricDef(
            id=c["id"], name=c["name"], kind="computed", column=c["column"],
            natural_sign=int(c["natural_sign"]), favorable=c["favorable"], formula=tuple(),
            synonyms=tuple(c.get("synonyms", [])))
        reg.computed.append((c["column"], tuple(str(x) for x in c["formula"])))
    for sid, st in spec["stats"].items():
        reg.metrics[sid] = MetricDef(id=sid, name=st["name"], kind="stat", column=f"{sid}_sum",
                                     favorable="neutral", agg=st.get("agg", "sum"),
                                     synonyms=tuple(st.get("synonyms", [])))
    for rid, r in spec["ratios"].items():
        reg.ratios[rid] = RatioDef(id=rid, name=r["name"], num=r["num"], den=r["den"],
                                   fmt=r.get("format", "pct"), favorable=r.get("favorable", "neutral"),
                                   annualize=bool(r.get("annualize", False)),
                                   synonyms=tuple(r.get("synonyms", [])))
    for pid, p in (spec.get("ratio_pairs") or {}).items():
        reg.pairs[pid] = PairDef(id=pid, name=p["name"], members=tuple(p["members"]),
                                 synonyms=tuple(p.get("synonyms", [])))
    reg.drivers = {k: list(v) for k, v in (spec.get("drivers") or {}).items()}
    reg.cockpit = list(spec.get("cockpit") or [])
    reg.build_lookup()
    return reg
