"""Application-level access control (mirrors sql/rls.sql).

* SQL Server: the database enforces RLS natively (SESSION_CONTEXT + SECURITY POLICY).
* DuckDB: the same rule is applied in Python by filtering fact rows to `allowed_bus(user)`.
* Both: before querying, the requested org is checked against the user's scope so that the
  answer is a polite "no access" (never data, never a misleading partial total).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.semantic.dims import dims
from app.semantic.entity_resolver import LEVEL_LABEL, ORG_LEVELS, org_label


@dataclass
class AccessDecision:
    status: str                         # ok | narrowed | denied | empty
    org_filter: dict[str, list[str]]
    message: str | None = None
    bu_ids: set[int] = field(default_factory=set)


def user_rows(user_id: str) -> list[tuple[str, str]]:
    acc = dims().access
    rows = acc[acc["user_id"] == user_id]
    return [(r.org_level, r.org_value) for r in rows.itertuples()]


def user_display(user_id: str) -> str:
    u = dims().users
    row = u[u["user_id"] == user_id]
    return str(row.iloc[0]["display_name"]) if not row.empty else user_id


def bus_for_filter(org_filter: dict[str, list[str]] | None, org: pd.DataFrame | None = None) -> set[int]:
    org = dims().org if org is None else org
    mask = pd.Series(True, index=org.index)
    for level, values in (org_filter or {}).items():
        mask &= org[level].isin(values)
    return set(org.loc[mask, "bu_id"].astype(int))


def allowed_bus(user_id: str) -> set[int]:
    org = dims().org
    out: set[int] = set()
    for level, value in user_rows(user_id):
        if level in ORG_LEVELS:
            out |= set(org.loc[org[level] == value, "bu_id"].astype(int))
    return out


def scope_label(user_id: str) -> str:
    rows = user_rows(user_id)
    return ", ".join(v for _, v in rows) if rows else "nothing"


def default_org(user_id: str) -> dict[str, list[str]]:
    rows = user_rows(user_id)
    if len(rows) == 1 and rows[0][0] != "l1_group":
        return {rows[0][0]: [rows[0][1]]}
    return {}


def check_access(user_id: str, org_filter: dict[str, list[str]] | None) -> AccessDecision:
    org_filter = dict(org_filter or {})
    requested = bus_for_filter(org_filter)
    allowed = allowed_bus(user_id)
    label = org_label(org_filter)
    if not requested:
        return AccessDecision("empty", org_filter,
                              f"There is no business matching **{label}** in the RL Group organisation.")
    if not allowed:
        return AccessDecision("denied", org_filter,
                              "Your user has no data access assigned. Please contact Group Controlling.")
    if requested <= allowed:
        return AccessDecision("ok", org_filter, None, requested)
    overlap = requested & allowed
    scope = scope_label(user_id)
    if not overlap:
        return AccessDecision(
            "denied", org_filter,
            f"Sorry, you don't have access to **{label}**. Your access covers **{scope}** only. "
            f"I can answer the same question for {scope}.")
    narrowed = dict(org_filter)
    for level, value in user_rows(user_id):
        if level != "l1_group":
            narrowed.setdefault(level, [value])
    narrowed_bus = bus_for_filter(narrowed)
    if not narrowed_bus or not narrowed_bus <= allowed:
        return AccessDecision("denied", org_filter,
                              f"Sorry, you don't have access to **{label}**. Your access covers **{scope}** only.")
    return AccessDecision(
        "narrowed", narrowed,
        f"Your access covers **{scope}** only, so the figures below are for **{org_label(narrowed)}** "
        f"(not all of {label}).", narrowed_bus)


def child_level(org_filter: dict[str, list[str]] | None, bu_ids: set[int] | None = None) -> str | None:
    """Next org level below the filter: first level with more than one distinct value."""
    org = dims().org
    sub = org[org["bu_id"].isin(bu_ids)] if bu_ids is not None else org[org["bu_id"].isin(bus_for_filter(org_filter))]
    for level in ORG_LEVELS[1:]:
        if sub[level].nunique() > 1:
            return level
    return None


def level_label(level: str) -> str:
    return LEVEL_LABEL.get(level, level)
