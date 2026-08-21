#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITE = PROJECT_ROOT / "site"

DATA_ROOT = Path(
    os.environ.get(
        "WEFUNK_DATA_DIR",
        PROJECT_ROOT / "data",
    )
).expanduser().resolve()

DB_FILE = Path(
    os.environ.get(
        "WEFUNK_DB_FILE",
        DATA_ROOT / "db" / "wefunk.db",
    )
).expanduser().resolve()

NOW_PLAYING_FILE = SITE / "now-playing.json"


def clean(value):
    """
    Match the normalization used by the existing WEFUNK matcher.
    """
    value = str(value or "").lower()
    value = re.sub(r"\(.*?\)|\[.*?\]", "", value)
    value = re.sub(r"\b(feat|ft|featuring)\b.*", "", value)
    value = re.sub(r"^the\s+", "", value)
    value = value.replace("&", "and")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def open_database():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def ensure_schema(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS listening_plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            played_at INTEGER NOT NULL,

            artist TEXT NOT NULL,
            track TEXT NOT NULL,
            album TEXT,

            artist_norm TEXT NOT NULL,
            track_norm TEXT NOT NULL,

            duration INTEGER,
            username TEXT,
            player_id TEXT,

            source TEXT NOT NULL DEFAULT 'navidrome',

            play_key TEXT NOT NULL UNIQUE,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_listening_plays_played_at
            ON listening_plays(played_at);

        CREATE INDEX IF NOT EXISTS idx_listening_plays_artist_track
            ON listening_plays(artist_norm, track_norm);


        CREATE TABLE IF NOT EXISTS listening_play_tracks (
            play_id INTEGER NOT NULL,
            wefunk_track_id INTEGER NOT NULL,

            PRIMARY KEY (
                play_id,
                wefunk_track_id
            ),

            FOREIGN KEY (play_id)
                REFERENCES listening_plays(id)
                ON DELETE CASCADE,

            FOREIGN KEY (wefunk_track_id)
                REFERENCES tracks(id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_listening_play_tracks_wefunk
            ON listening_play_tracks(wefunk_track_id);


        CREATE TABLE IF NOT EXISTS listening_state (
            player_key TEXT PRIMARY KEY,

            fingerprint TEXT NOT NULL,

            artist TEXT NOT NULL,
            track TEXT NOT NULL,
            album TEXT,

            artist_norm TEXT NOT NULL,
            track_norm TEXT NOT NULL,

            duration INTEGER,

            first_seen INTEGER NOT NULL,
            last_seen INTEGER NOT NULL,

            recorded INTEGER NOT NULL DEFAULT 0
                CHECK (recorded IN (0, 1))
        );
        """
    )

    connection.commit()


def load_now_playing():
    if not NOW_PLAYING_FILE.exists():
        return []

    data = json.loads(
        NOW_PLAYING_FILE.read_text(encoding="utf-8")
    )

    if not data.get("ok"):
        return []

    songs = data.get("now_playing", [])

    if isinstance(songs, dict):
        songs = [songs]

    return songs


def find_wefunk_tracks(connection, artist_norm, track_norm):
    """
    Use the already-normalized track_matches cache where available.

    We intentionally DO NOT require matched=1 here.

    The listening feature asks:
        "Has this song appeared on WEFUNK?"

    It does not ask:
        "Did the library matching engine successfully match this row?"
    """
    rows = connection.execute(
        """
        SELECT
            tm.wefunk_track_id,
            tm.show_id,
            tm.artist,
            tm.track
        FROM track_matches AS tm
        INNER JOIN tracks AS t
            ON t.id = tm.wefunk_track_id
        WHERE tm.artist_norm = ?
          AND tm.track_norm = ?
        ORDER BY
            tm.show_id,
            tm.wefunk_track_id
        """,
        (
            artist_norm,
            track_norm,
        ),
    ).fetchall()

    if rows:
        return rows

    # Small fallback for tracks that do not yet have a track_matches row.
    candidates = connection.execute(
        """
        SELECT
            id AS wefunk_track_id,
            show_id,
            artist,
            track
        FROM tracks
        WHERE TRIM(COALESCE(artist, '')) != ''
          AND TRIM(COALESCE(track, '')) != ''
        """
    ).fetchall()

    return [
        row
        for row in candidates
        if clean(row["artist"]) == artist_norm
        and clean(row["track"]) == track_norm
    ]


def required_seconds(duration):
    try:
        duration = int(duration or 0)
    except (TypeError, ValueError):
        duration = 0

    if duration <= 0:
        return 30

    return max(
        30,
        min(
            int(duration * 0.50),
            240,
        ),
    )


def build_fingerprint(song):
    artist = clean(song.get("artist", ""))
    track = clean(song.get("title", ""))

    raw = "\x1f".join(
        [
            str(song.get("username", "")),
            str(song.get("playerId", "")),
            artist,
            track,
            str(song.get("album", "")),
        ]
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def build_player_key(song):
    username = str(song.get("username", "") or "")
    player = str(song.get("playerId", "") or "")

    if username or player:
        return f"{username}:{player}"

    return "default"


def process_song(connection, song, dry_run=False):
    now = int(time.time())

    artist = str(song.get("artist", "") or "").strip()
    track = str(song.get("title", "") or "").strip()
    album = str(song.get("album", "") or "").strip()

    if not artist or not track:
        print("IGNORE  missing artist/title")
        return

    artist_norm = clean(artist)
    track_norm = clean(track)

    if not artist_norm or not track_norm:
        print(
            f"IGNORE  unusable normalized metadata: "
            f"{artist} — {track}"
        )
        return

    matches = find_wefunk_tracks(
        connection,
        artist_norm,
        track_norm,
    )

    if not matches:
        print(
            f"IGNORE  not in WEFUNK: "
            f"{artist} — {track}"
        )
        return

    show_ids = sorted(
        {
            str(row["show_id"])
            for row in matches
            if row["show_id"] is not None
        }
    )

    duration = int(song.get("duration", 0) or 0)
    threshold = required_seconds(duration)

    player_key = build_player_key(song)
    fingerprint = build_fingerprint(song)

    state = connection.execute(
        """
        SELECT *
        FROM listening_state
        WHERE player_key = ?
        """,
        (player_key,),
    ).fetchone()

    if state is None or state["fingerprint"] != fingerprint:
        if dry_run:
            print(
                f"MATCH   {artist} — {track}"
            )
            print(
                f"        WEFUNK occurrence(s): {len(matches)}"
            )
            print(
                f"        Episode(s): {', '.join(show_ids[:20])}"
                + (
                    " ..."
                    if len(show_ids) > 20
                    else ""
                )
            )
            print(
                f"        Would start candidate; "
                f"threshold={threshold}s"
            )
            return

        connection.execute(
            """
            INSERT INTO listening_state (
                player_key,
                fingerprint,
                artist,
                track,
                album,
                artist_norm,
                track_norm,
                duration,
                first_seen,
                last_seen,
                recorded
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)

            ON CONFLICT(player_key) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                artist = excluded.artist,
                track = excluded.track,
                album = excluded.album,
                artist_norm = excluded.artist_norm,
                track_norm = excluded.track_norm,
                duration = excluded.duration,
                first_seen = excluded.first_seen,
                last_seen = excluded.last_seen,
                recorded = 0
            """,
            (
                player_key,
                fingerprint,
                artist,
                track,
                album,
                artist_norm,
                track_norm,
                duration,
                now,
                now,
            ),
        )

        connection.commit()

        print(
            f"CANDIDATE  {artist} — {track} "
            f"({len(matches)} WEFUNK occurrence(s), "
            f"threshold={threshold}s)"
        )

        return

    connection.execute(
        """
        UPDATE listening_state
        SET last_seen = ?
        WHERE player_key = ?
        """,
        (
            now,
            player_key,
        ),
    )

    connection.commit()

    elapsed = now - int(state["first_seen"])

    if state["recorded"]:
        print(
            f"ACTIVE  already recorded: "
            f"{artist} — {track}"
        )
        return

    if elapsed < threshold:
        print(
            f"WAIT    {artist} — {track} "
            f"{elapsed}s/{threshold}s"
        )
        return

    session_start = int(state["first_seen"])

    play_key_raw = "\x1f".join(
        [
            player_key,
            fingerprint,
            str(session_start),
        ]
    )

    play_key = hashlib.sha256(
        play_key_raw.encode("utf-8")
    ).hexdigest()

    if dry_run:
        print(
            f"RECORD  would record: "
            f"{artist} — {track}"
        )
        return

    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO listening_plays (
            played_at,
            artist,
            track,
            album,
            artist_norm,
            track_norm,
            duration,
            username,
            player_id,
            source,
            play_key
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'navidrome', ?)
        """,
        (
            session_start,
            artist,
            track,
            album,
            artist_norm,
            track_norm,
            duration,
            str(song.get("username", "") or ""),
            str(song.get("playerId", "") or ""),
            play_key,
        ),
    )

    if cursor.rowcount:
        play_id = cursor.lastrowid

        connection.executemany(
            """
            INSERT OR IGNORE INTO listening_play_tracks (
                play_id,
                wefunk_track_id
            )
            VALUES (?, ?)
            """,
            [
                (
                    play_id,
                    row["wefunk_track_id"],
                )
                for row in matches
            ],
        )

    connection.execute(
        """
        UPDATE listening_state
        SET recorded = 1,
            last_seen = ?
        WHERE player_key = ?
        """,
        (
            now,
            player_key,
        ),
    )

    connection.commit()

    print(
        f"RECORDED  {artist} — {track} "
        f"| {len(matches)} WEFUNK occurrence(s)"
    )

    if cursor.rowcount:
        refresh_listening_page()


def refresh_listening_page():
    """
    Rebuild the Listening page after a newly qualified play is recorded.
    """
    dashboard_dir = Path(__file__).resolve().parent

    generator = dashboard_dir / "generate_listening_page.py"
    global_ui = dashboard_dir / "enhance_global_ui.py"

    try:
        subprocess.run(
            [
                sys.executable,
                str(generator),
            ],
            cwd=dashboard_dir,
            check=True,
        )

        subprocess.run(
            [
                sys.executable,
                str(global_ui),
            ],
            cwd=dashboard_dir,
            check=True,
        )

        print("REFRESH   listening.html updated")

    except subprocess.CalledProcessError as exc:
        # The listening play is already safely stored.
        # A page-generation problem should not lose listening history.
        print(
            "WARNING  Listening page refresh failed "
            f"(exit {exc.returncode})"
        )


def print_status(connection):
    play_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM listening_plays
        """
    ).fetchone()[0]

    linked_rows = connection.execute(
        """
        SELECT COUNT(*)
        FROM listening_play_tracks
        """
    ).fetchone()[0]

    unique_tracks = connection.execute(
        """
        SELECT COUNT(
            DISTINCT artist_norm || CHAR(31) || track_norm
        )
        FROM listening_plays
        """
    ).fetchone()[0]

    print("Listening History")
    print("-----------------")
    print(f"Plays:                 {play_count}")
    print(f"Unique songs:          {unique_tracks}")
    print(f"WEFUNK episode links:  {linked_rows}")


def main():
    parser = argparse.ArgumentParser(
        description="Collect WEFUNK-only listening history."
    )

    parser.add_argument(
        "--init",
        action="store_true",
        help="Create listening-history database tables.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect current track without modifying listening history.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show listening-history counts.",
    )

    args = parser.parse_args()

    if not DB_FILE.exists():
        raise SystemExit(
            f"Database does not exist: {DB_FILE}"
        )

    connection = open_database()

    try:
        ensure_schema(connection)

        if args.init:
            print(
                f"Listening-history schema ready: {DB_FILE}"
            )

        if args.status:
            print_status(connection)
            return

        if args.init and not args.dry_run:
            return

        songs = load_now_playing()

        if not songs:
            print("No active Navidrome track.")
            return

        for song in songs:
            process_song(
                connection,
                song,
                dry_run=args.dry_run,
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
