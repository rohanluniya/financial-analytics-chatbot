"""Configuration helpers: settings.yaml + environment variables (.env)."""
from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)


@lru_cache(maxsize=1)
def settings() -> dict:
    with open(ROOT / "config" / "settings.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def data_as_of_date() -> date:
    """The as-of date the dataset was generated with (fixed in settings.yaml)."""
    return date.fromisoformat(str(settings()["as_of_date"]))


def as_of_date() -> date:
    """Effective as-of date: AS_OF_DATE env override, never later than the data as-of date."""
    raw = env("AS_OF_DATE")
    chosen = date.fromisoformat(raw) if raw else data_as_of_date()
    return min(chosen, data_as_of_date())


def backend() -> str:
    return (env("DB_BACKEND", "duckdb") or "duckdb").lower()


def forecast_actual_months() -> dict[str, int]:
    return {k: int(v["actual_months"]) for k, v in settings()["forecasts"].items()}
