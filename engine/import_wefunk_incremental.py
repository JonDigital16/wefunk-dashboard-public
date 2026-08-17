#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
import os
from pathlib import Path
from typing import Any


DEFAULT_DB_FILE = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "db" / 'wefunk.db'
DEFAULT_JSON_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "json"


def clean_text(value: Any) -> str:
    """Convert a value to clean text without changing its meaning."""

    if value is None:
        return ""

    if isinstance(value, list):
        return ", ".join(
            clean_text(item)
            for item in value
            if clean_text(item)
        )

    return str(value).strip()


def find_latest_json(json_dir: Path) -> Path:
    """Return the newest WEFUNK JSON export."""

    candidates = sorted(
        json_dir.glob("wefunk_shows_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not candidates:
        raise FileNotFoundError(
            f"No wefunk_shows_*.json files found in {json_dir}"
        )

    return candidates[0]


def load_json_file(json_file: Path) -> list[dict[str, Any]]:
    """Load and validate the WEFUNK JSON export."""

    with json_file.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, dict):
        if isinstance(data.get("shows"), list):
            data = data["shows"]
        else:
            raise ValueError(
                "JSON root is an object, but it does not contain a "
                "'shows' list."
            )

    if not isinstance(data, list):
        raise ValueError("Expected the JSON root to be a list of shows.")

    return [
        show
        for show in data
        if isinstance(show, dict)
    ]


def get_show_id(show: dict[str, Any]) -> int:
    """Extract the numeric show ID."""

    value = show.get("show_id")

    if value in (None, ""):
        value = show.get("id")

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid show ID: {value!r}") from exc


def get_show_metadata(
    show: dict[str, Any],
) -> tuple[str, str, str, str]:
    """Extract metadata used by the existing shows table."""

    meta = show.get("meta_info")

    if not isinstance(meta, dict):
        meta = {}

    recorded = clean_text(
        show.get("recorded")
        or meta.get("recorded")
        or meta.get("date")
    )

    djs = clean_text(
        show.get("djs")
        or meta.get("djs")
        or show.get("dj")
        or meta.get("dj")
    )

    url = clean_text(
        show.get("url")
        or meta.get("url")
    )

    description = clean_text(
        show.get("description")
        or show.get("showdescription")
        or meta.get("description")
        or meta.get("showdescription")
    )

    return recorded, djs, url, description


def extract_artist_track(
    item: dict[str, Any],
) -> tuple[str, str]:
    """
    Extract one playlist entry.

    Direct artist/track fields are preferred. Limited fallbacks are retained
    for compatibility with WEFUNK export variations.
    """

    artist = clean_text(
        item.get("artist")
        or item.get("performer")
    )

    track = clean_text(
        item.get("track")
        or item.get("title")
        or item.get("song")
    )

    return artist, track


def parse_tracks(
    show: dict[str, Any],
) -> list[tuple[str, str]]:
    """
    Parse tracks for a newly discovered show.

    Intro, outro, and talk markers are omitted. Unknown and untitled tracks
    are preserved.
    """

    playlist = show.get("playlistbox") or []

    if not isinstance(playlist, list):
        return []

    tracks: list[tuple[str, str]] = []

    for item in playlist:
        if not isinstance(item, dict):
            continue

        artist, track = extract_artist_track(item)
        artist_lower = artist.lower()

        if artist_lower in {"intro", "outro"}:
            continue

        if artist_lower.startswith("talk"):
            continue

        if not artist and not track:
            continue

        tracks.append((artist, track))

    return tracks


def load_existing_show_ids(
    connection: sqlite3.Connection,
) -> set[int]:
    """Return all show IDs already stored in the database."""

    rows = connection.execute(
        "SELECT show_id FROM shows"
    ).fetchall()

    return {
        int(row[0])
        for row in rows
    }


def validate_database(connection: sqlite3.Connection) -> None:
    """Confirm that the required tables and columns exist."""

    required = {
        "shows": {
            "show_id",
            "recorded",
            "djs",
            "url",
            "description",
        },
        "tracks": {
            "id",
            "show_id",
            "artist",
            "track",
        },
    }

    for table, required_columns in required.items():
        row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table,),
        ).fetchone()

        if row is None:
            raise RuntimeError(
                f"Required table is missing: {table}"
            )

        actual_columns = {
            column[1]
            for column in connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }

        missing = required_columns - actual_columns

        if missing:
            raise RuntimeError(
                f"Table {table!r} is missing columns: "
                f"{', '.join(sorted(missing))}"
            )


def create_backup(db_file: Path) -> Path:
    """Create a timestamped copy of the database."""

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_file = db_file.with_name(
        f"{db_file.stem}.before-wefunk-import-{timestamp}"
        f"{db_file.suffix}"
    )

    shutil.copy2(db_file, backup_file)
    return backup_file


def insert_new_show(
    connection: sqlite3.Connection,
    show_id: int,
    show: dict[str, Any],
    tracks: list[tuple[str, str]],
) -> None:
    """Insert one new show and its ordered tracks."""

    recorded, djs, url, description = get_show_metadata(show)

    connection.execute(
        """
        INSERT INTO shows (
            show_id,
            recorded,
            djs,
            url,
            description
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            show_id,
            recorded,
            djs,
            url,
            description,
        ),
    )

    connection.executemany(
        """
        INSERT INTO tracks (
            show_id,
            artist,
            track
        )
        VALUES (?, ?, ?)
        """,
        [
            (show_id, artist, track)
            for artist, track in tracks
        ],
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Append new WEFUNK shows without modifying existing "
            "shows or track IDs."
        )
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_FILE,
        help=f"SQLite database path (default: {DEFAULT_DB_FILE})",
    )

    parser.add_argument(
        "--json",
        type=Path,
        help=(
            "Specific WEFUNK JSON file. By default, the newest "
            "wefunk_shows_*.json file is used."
        ),
    )

    parser.add_argument(
        "--json-dir",
        type=Path,
        default=DEFAULT_JSON_DIR,
        help=f"JSON directory (default: {DEFAULT_JSON_DIR})",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the import. Without this option, only report changes.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    db_file = args.db.expanduser().resolve()

    if not db_file.exists():
        raise FileNotFoundError(
            f"Database does not exist: {db_file}"
        )

    if args.json:
        json_file = args.json.expanduser().resolve()
    else:
        json_file = find_latest_json(
            args.json_dir.expanduser().resolve()
        )

    if not json_file.exists():
        raise FileNotFoundError(
            f"JSON file does not exist: {json_file}"
        )

    json_shows = load_json_file(json_file)

    incoming: dict[int, dict[str, Any]] = {}

    for show in json_shows:
        show_id = get_show_id(show)

        if show_id in incoming:
            raise ValueError(
                f"Duplicate show ID in JSON: {show_id}"
            )

        incoming[show_id] = show

    connection = sqlite3.connect(db_file)

    try:
        validate_database(connection)
        existing_show_ids = load_existing_show_ids(connection)

        new_show_ids = sorted(
            set(incoming) - existing_show_ids
        )

        skipped_show_ids = sorted(
            set(incoming) & existing_show_ids
        )

        parsed_new_shows: list[
            tuple[int, dict[str, Any], list[tuple[str, str]]]
        ] = []

        for show_id in new_show_ids:
            show = incoming[show_id]
            tracks = parse_tracks(show)

            parsed_new_shows.append(
                (show_id, show, tracks)
            )

        new_track_count = sum(
            len(tracks)
            for _, _, tracks in parsed_new_shows
        )

        print(f"Database: {db_file}")
        print(f"JSON:     {json_file}")
        print()
        print(f"JSON shows:       {len(incoming):,}")
        print(f"Existing shows:   {len(existing_show_ids):,}")
        print(f"Skipped existing: {len(skipped_show_ids):,}")
        print(f"New shows:        {len(new_show_ids):,}")
        print(f"New tracks:       {new_track_count:,}")
        print("Changed shows:    0")
        print("Replacement tracks: 0")

        if new_show_ids:
            print()
            print("New show IDs:")
            print(", ".join(map(str, new_show_ids)))

            print()
            print("New-show track counts:")

            for show_id, _, tracks in parsed_new_shows:
                print(f"  {show_id}: {len(tracks):,}")

        if not args.apply:
            print()
            print("Dry run only — no database changes were made.")
            print("Use --apply after reviewing this report.")
            return

        if not new_show_ids:
            print()
            print("Nothing to import. The database is already current.")
            return

        backup_file = create_backup(db_file)

        print()
        print(f"Backup:   {backup_file}")

        try:
            connection.execute("BEGIN IMMEDIATE")

            # Recheck inside the write transaction to prevent duplicates if
            # another importer ran after the dry-run calculations.
            current_ids = load_existing_show_ids(connection)

            actually_inserted_shows = 0
            actually_inserted_tracks = 0

            for show_id, show, tracks in parsed_new_shows:
                if show_id in current_ids:
                    print(
                        f"Skipping show {show_id}: "
                        "it was inserted by another process."
                    )
                    continue

                insert_new_show(
                    connection,
                    show_id,
                    show,
                    tracks,
                )

                current_ids.add(show_id)
                actually_inserted_shows += 1
                actually_inserted_tracks += len(tracks)

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        print()
        print("Import complete.")
        print(
            f"Inserted shows: {actually_inserted_shows:,}"
        )
        print(
            f"Inserted tracks: {actually_inserted_tracks:,}"
        )
        print("Existing shows and track IDs were not modified.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
