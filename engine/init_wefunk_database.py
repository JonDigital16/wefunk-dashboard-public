#!/usr/bin/env python3

import os
import sqlite3
from pathlib import Path


DATA_ROOT = Path(
    os.environ.get(
        "WEFUNK_DATA_DIR",
        Path.home() / ".local" / "share" / "wefunk",
    )
).expanduser().resolve()

DB_FILE = Path(
    os.environ.get(
        "WEFUNK_DB_FILE",
        DATA_ROOT / "db" / "wefunk.db",
    )
).expanduser().resolve()


def initialize_database(db_file: Path) -> None:
    db_file.parent.mkdir(parents=True, exist_ok=True)

    if db_file.exists():
        print(f"✅ Database already exists: {db_file}")
        return

    connection = sqlite3.connect(db_file)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        connection.executescript(
            """
            CREATE TABLE shows (
                show_id TEXT PRIMARY KEY,
                recorded TEXT,
                djs TEXT,
                url TEXT,
                description TEXT
            );

            CREATE TABLE tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                show_id TEXT,
                artist TEXT,
                track TEXT,
                FOREIGN KEY(show_id) REFERENCES shows(show_id)
            );
            """
        )

        connection.commit()

    except Exception:
        connection.rollback()
        connection.close()

        if db_file.exists():
            db_file.unlink()

        raise

    finally:
        try:
            connection.close()
        except Exception:
            pass

    print(f"✅ Created WEFUNK database: {db_file}")


def main() -> None:
    initialize_database(DB_FILE)


if __name__ == "__main__":
    main()
