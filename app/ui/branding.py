"""IRIS branding: the only place where the product name, tagline, author credit and version are defined.

Every page, the sidebar footer, the page title and the docs generator read these constants; no other file
may hardcode them (tests/test_branding.py checks this).
"""
from __future__ import annotations

from pathlib import Path

APP_NAME = "IRIS"
APP_FULL_NAME = "Intelligent Reporting & Insight System"
TAGLINE = "See your business clearly."
AUTHOR = "Rohan Luniya"
AUTHOR_LINE = f"Developed and maintained by {AUTHOR}"
VERSION = "1.0.0"

ASSETS = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS / "iris_logo.svg"

# Palette taken from the logo (also used in .streamlit/config.toml and the charts' accents)
TEAL = "#0F766E"
INDIGO = "#3730A3"
INK = "#0B1F3A"


def page_title(page: str | None = None) -> str:
    return f"{APP_NAME} · {page}" if page else f"{APP_NAME} · {APP_FULL_NAME}"


def footer_line() -> str:
    return f"{APP_NAME} v{VERSION} · {AUTHOR_LINE}"
