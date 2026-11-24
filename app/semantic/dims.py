"""Cached dimension tables (org hierarchy, chart of accounts, versions, users, access rules).

Dimensions are small and not row-level filtered, so they are read once per process.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
from sqlalchemy import select

from app.config import backend
from app.db import app_user, dim_account, dim_org, dim_version, get_engine, user_org_access


@dataclass(frozen=True)
class Dims:
    org: pd.DataFrame
    account: pd.DataFrame
    version: pd.DataFrame
    users: pd.DataFrame
    access: pd.DataFrame

    @property
    def leaves(self) -> pd.DataFrame:
        return self.account[self.account["is_leaf"].astype(bool)].sort_values("display_order")


@lru_cache(maxsize=4)
def _load(backend_key: str) -> Dims:
    eng = get_engine("__dims__")
    with eng.connect() as conn:
        org = pd.read_sql(select(dim_org), conn)
        account = pd.read_sql(select(dim_account), conn)
        version = pd.read_sql(select(dim_version), conn)
        users = pd.read_sql(select(app_user), conn)
        access = pd.read_sql(select(user_org_access), conn)
    for col in ("is_leaf", "is_subtotal"):
        account[col] = account[col].astype(bool)
    account["natural_sign"] = account["natural_sign"].astype(int)
    return Dims(org=org, account=account, version=version, users=users, access=access)


def dims() -> Dims:
    return _load(backend())


def clear_cache() -> None:
    _load.cache_clear()
