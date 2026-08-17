#!/usr/bin/env python3
import os

import csv
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from mutagen import File

sys.path.insert(0, str(Path(__file__).parent))

from common import slugify

SITE_DATA = Path(
    str(Path(os.environ.get("WEFUNK_SITE_DIR", Path(__file__).resolve().parents[1] / "site")) / "data" / "search_index.json")
)
EXPORTS = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve()
ENRICHED = EXPORTS / "wefunk_owned_tracks_enriched.csv"
SNAPSHOT = EXPORTS / "search_index.previous.json"
OUT = EXPORTS / "wefunk_recent_matches.csv"
DB = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "db" / 'wefunk_engine.db'


def norm(value):
    return str(value or "").strip().lower()


def owned_keys(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [row for row in data if row.get("status") == "owned"]

    keys = {}

    for row in rows:
        key = (
            str(row.get("show", "")).strip(),
            norm(row.get("artist")),
            norm(row.get("track")),
            norm(row.get("match")),
        )
        keys[key] = row

    return keys


def load_enriched():
    lookup = {}

    if not ENRICHED.exists():
        return lookup

    with ENRICHED.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (
                str(row.get("show_id", "")).strip(),
                norm(row.get("artist")),
                norm(row.get("track")),
            )
            lookup[key] = row

    return lookup


def load_database_matches():
    lookup = {}

    if not DB.exists():
        return lookup

    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row

    rows = connection.execute(
        """
        SELECT
            show_id,
            wefunk_artist,
            wefunk_track,
            library_artist,
            library_title,
            file_path,
            score
        FROM matches
        WHERE file_path IS NOT NULL
          AND TRIM(file_path) != ''
        """
    ).fetchall()

    connection.close()

    for row in rows:
        key = (
            str(row["show_id"] or "").strip(),
            norm(row["wefunk_artist"]),
            norm(row["wefunk_track"]),
        )
        lookup[key] = dict(row)

    return lookup


def tag(audio, names):
    if not audio:
        return ""

    for name in names:
        value = audio.get(name)

        if not value:
            continue

        if isinstance(value, list):
            return str(value[0]).strip()

        if hasattr(value, "text") and value.text:
            return str(value.text[0]).strip()

        return str(value).strip()

    return ""


audio_metadata_cache = {}


def metadata_from_file(file_path, fallback_artist=""):
    file_path = str(file_path or "").strip()

    if not file_path:
        return {}

    if file_path in audio_metadata_cache:
        return audio_metadata_cache[file_path]

    path = Path(file_path)

    metadata = {
        "album": "",
        "album_slug": "",
        "genre": "",
        "year": "",
    }

    try:
        audio = File(path, easy=True)

        album = tag(audio, ["album"])
        album_artist = (
            tag(audio, ["albumartist", "album artist"])
            or tag(audio, ["artist"])
            or fallback_artist
        )
        genre = tag(audio, ["genre"])
        year = tag(audio, ["date", "year", "originaldate"])

        metadata = {
            "album": album,
            "album_slug": (
                slugify(f"{album_artist}-{album}")
                if album
                else ""
            ),
            "genre": genre,
            "year": year,
        }

    except Exception:
        pass

    audio_metadata_cache[file_path] = metadata
    return metadata


enriched = load_enriched()
database_matches = load_database_matches()


def lookup_metadata(show, artist, track):
    key = (
        str(show or "").strip(),
        norm(artist),
        norm(track),
    )

    enriched_row = enriched.get(key, {})

    metadata = {
        "album": str(enriched_row.get("matched_album") or "").strip(),
        "album_slug": str(
            enriched_row.get("matched_album_slug") or ""
        ).strip(),
        "genre": str(enriched_row.get("matched_genre") or "").strip(),
        "year": str(enriched_row.get("matched_year") or "").strip(),
    }

    # The enriched export may not contain every current engine match.
    # Fall back to the engine database and read tags from the matched file.
    if not all(
        metadata.get(field)
        for field in ("album", "genre", "year")
    ):
        db_row = database_matches.get(key, {})

        file_metadata = metadata_from_file(
            db_row.get("file_path"),
            fallback_artist=str(
                db_row.get("library_artist") or artist or ""
            ),
        )

        for field in ("album", "album_slug", "genre", "year"):
            if not metadata[field]:
                metadata[field] = file_metadata.get(field, "")

    return metadata


current = owned_keys(SITE_DATA)
recent = []

if SNAPSHOT.exists():
    previous = owned_keys(SNAPSHOT)

    for key, row in current.items():
        if key in previous:
            continue

        metadata = lookup_metadata(
            row.get("show"),
            row.get("artist"),
            row.get("track"),
        )

        recent.append({
            "date_added": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "show": row.get("show", ""),
            "artist": row.get("artist", ""),
            "track": row.get("track", ""),
            "match": row.get("match", ""),
            **metadata,
            "url": row.get("url", ""),
        })


existing = []

if OUT.exists():
    with OUT.open(newline="", encoding="utf-8") as handle:
        existing = list(csv.DictReader(handle))


seen = {
    (
        row.get("show", ""),
        norm(row.get("artist")),
        norm(row.get("track")),
        norm(row.get("match")),
    )
    for row in existing
}

new_unique = []

for row in recent:
    key = (
        row["show"],
        norm(row["artist"]),
        norm(row["track"]),
        norm(row["match"]),
    )

    if key not in seen:
        new_unique.append(row)


fieldnames = [
    "date_added",
    "show",
    "artist",
    "track",
    "match",
    "album",
    "album_slug",
    "genre",
    "year",
    "url",
]

all_rows = []
backfilled = 0

for row in new_unique + existing:
    output_row = {
        field: row.get(field, "")
        for field in fieldnames
    }

    missing_before = any(
        not str(output_row.get(field) or "").strip()
        for field in ("album", "genre", "year")
    )

    if missing_before:
        metadata = lookup_metadata(
            output_row.get("show"),
            output_row.get("artist"),
            output_row.get("track"),
        )

        changed = False

        for field in ("album", "album_slug", "genre", "year"):
            if not str(output_row.get(field) or "").strip():
                value = metadata.get(field, "")

                if value:
                    output_row[field] = value
                    changed = True

        if changed:
            backfilled += 1

    all_rows.append(output_row)


with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_rows)

shutil.copy2(SITE_DATA, SNAPSHOT)

print(f"New recent matches: {len(new_unique)}")
print(f"Existing rows backfilled: {backfilled}")
print(f"Wrote: {OUT}")
print(f"Baseline updated: {SNAPSHOT}")
