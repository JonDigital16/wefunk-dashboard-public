"""Synchronize the persistent WEFUNK local-music library index."""

import argparse
import os
from pathlib import Path

from engine.database import open_database
from engine.library_index import (
    print_sync_summary,
    sync_library_index,
)


DB_FILE = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "db" / 'wefunk.db'
MUSIC_DIR = Path(os.environ.get("WEFUNK_MUSIC_DIR", Path.home() / "Music")).expanduser().resolve()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Synchronize the persistent local-music library index."
    )
    parser.add_argument(
        "--full-rebuild",
        action="store_true",
        help="Clear the existing library index and reread every music file.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    with open_database(DB_FILE) as conn:
        stats = sync_library_index(
            conn,
            MUSIC_DIR,
            full_rebuild=args.full_rebuild,
        )

    print_sync_summary(stats)


if __name__ == "__main__":
    main()
