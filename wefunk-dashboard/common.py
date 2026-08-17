#!/usr/bin/env python3

import os
import csv
import html
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

#
# Directories
#

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent

# Load project-local configuration without overriding
# variables already supplied by the operating environment.
load_dotenv(PROJECT_ROOT / ".env", override=False)

SITE = Path(os.environ.get(
    "WEFUNK_SITE_DIR",
    str(PROJECT_ROOT / "site")
))

SHOWS_DIR = SITE / "shows"
ARTISTS_DIR = SITE / "artists"

SHOWS_DIR.mkdir(parents=True, exist_ok=True)
ARTISTS_DIR.mkdir(parents=True, exist_ok=True)

DATA_ROOT = Path(
    os.environ.get(
        "WEFUNK_DATA_DIR",
        PROJECT_ROOT / "data",
    )
).expanduser().resolve()

EXPORTS = Path(
    os.environ.get(
        "WEFUNK_EXPORT_DIR",
        DATA_ROOT / "exports",
    )
).expanduser().resolve()

#
# Helpers
#

def load_csv(path):
    path = Path(path)
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def esc(value):
    return html.escape(str(value or ""))


def slugify(text):
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def normalize_artist_name(name):
    """Normalize an artist name for grouping and URL generation."""
    name = str(name or "").lower()
    name = re.sub(r"\b(feat|ft|featuring)\b.*", "", name)
    name = re.sub(r"\bwith\b.*", "", name)
    name = name.replace("&", "and")
    name = re.sub(r"^the\s+", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def artist_slugify(name):
    """Create the canonical URL slug for an artist."""
    normalized = normalize_artist_name(name)
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "unknown"


_ARTIST_DISPLAY_NAMES_FILE = Path(__file__).with_name(
    "artist_display_names.json"
)

_ARTIST_ASSET_ALIASES_FILE = Path(__file__).with_name(
    "artist_asset_aliases.json"
)

_artist_display_names_cache = None
_artist_asset_aliases_cache = None


def _load_artist_display_data():
    """Load artist display names and approved aliases once."""
    global _artist_display_names_cache
    global _artist_asset_aliases_cache

    if _artist_display_names_cache is None:
        _artist_display_names_cache = {}

        if _ARTIST_DISPLAY_NAMES_FILE.exists():
            try:
                loaded = json.loads(
                    _ARTIST_DISPLAY_NAMES_FILE.read_text(
                        encoding="utf-8"
                    )
                )

                if isinstance(loaded, dict):
                    _artist_display_names_cache = {
                        str(slug): str(name).strip()
                        for slug, name in loaded.items()
                        if slug and str(name).strip()
                    }
            except (OSError, json.JSONDecodeError):
                _artist_display_names_cache = {}

    if _artist_asset_aliases_cache is None:
        _artist_asset_aliases_cache = {}

        if _ARTIST_ASSET_ALIASES_FILE.exists():
            try:
                loaded = json.loads(
                    _ARTIST_ASSET_ALIASES_FILE.read_text(
                        encoding="utf-8"
                    )
                )

                if isinstance(loaded, dict):
                    _artist_asset_aliases_cache = {
                        str(alias): str(canonical)
                        for alias, canonical in loaded.items()
                        if alias and canonical
                    }
            except (OSError, json.JSONDecodeError):
                _artist_asset_aliases_cache = {}

    return (
        _artist_display_names_cache,
        _artist_asset_aliases_cache,
    )


def artist_display_name(name, slug=None):
    """Return the preferred display casing for an artist."""
    original = str(name or "").strip()

    if slug:
        artist_slug = str(slug).strip()
    else:
        artist_slug = artist_slugify(original)

    display_names, aliases = _load_artist_display_data()
    canonical_slug = aliases.get(artist_slug, artist_slug)

    return (
        display_names.get(artist_slug)
        or display_names.get(canonical_slug)
        or original
    )

def z_date_short(date):
    if not date:
        return ""

    try:
        return datetime.strptime(date, "%Y-%m-%d").strftime("%b %d, %Y")
    except Exception:
        return date


def z_date_sort(date):
    if not date:
        return 0

    try:
        return int(datetime.strptime(date, "%Y-%m-%d").strftime("%Y%m%d"))
    except Exception:
        return 0
