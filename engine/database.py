"""SQLite helpers for WEFUNK track matching."""

import sqlite3


def open_database(db_file):
    """Open the WEFUNK SQLite database."""

    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def reset_matches_table(conn):
    """Recreate the legacy matches_tags export table."""

    conn.execute("DROP TABLE IF EXISTS matches_tags")
    conn.execute(
        """
        CREATE TABLE matches_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            show_id TEXT,
            artist TEXT,
            track TEXT,
            file_path TEXT,
            score INTEGER
        )
        """
    )
    conn.commit()


def load_tracks(conn):
    """Load valid WEFUNK tracks using the legacy three-column format."""

    return conn.execute(
        """
        SELECT show_id, artist, track
        FROM tracks
        WHERE TRIM(COALESCE(artist, '')) != ''
          AND TRIM(COALESCE(track, '')) != ''
        ORDER BY id
        """
    ).fetchall()


def load_tracks_with_ids(conn):
    """Load WEFUNK tracks with their persistent source IDs."""

    return conn.execute(
        """
        SELECT id, show_id, artist, track
        FROM tracks
        ORDER BY id
        """
    ).fetchall()


def insert_matches(conn, matched):
    """Insert matched tracks into the legacy matches_tags table."""

    conn.executemany(
        """
        INSERT INTO matches_tags (
            show_id,
            artist,
            track,
            file_path,
            score
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        matched,
    )
    conn.commit()


def ensure_track_matches_table(conn):
    """Create the persistent incremental match-results table."""

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS track_matches (
            wefunk_track_id INTEGER PRIMARY KEY,

            show_id TEXT NOT NULL,
            artist TEXT NOT NULL,
            track TEXT NOT NULL,

            artist_norm TEXT NOT NULL,
            track_norm TEXT NOT NULL,

            matched INTEGER NOT NULL
                CHECK (matched IN (0, 1)),

            library_file_path TEXT,
            best_candidate_path TEXT,
            score INTEGER,

            matcher_version TEXT NOT NULL DEFAULT '1.0',

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (wefunk_track_id)
                REFERENCES tracks(id)
                ON DELETE CASCADE
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_track_matches_matched
        ON track_matches(matched)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_track_matches_show_id
        ON track_matches(show_id)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_track_matches_artist_track
        ON track_matches(artist_norm, track_norm)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_track_matches_library_path
        ON track_matches(library_file_path)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_track_matches_matcher_version
        ON track_matches(matcher_version)
        """
    )

    conn.commit()


def clear_track_matches(conn):
    """Clear all persistent match results."""

    conn.execute("DELETE FROM track_matches")
    conn.commit()


def load_cached_track_matches(conn, matcher_version):
    """Load cached results for the requested matcher version."""

    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            wefunk_track_id,
            show_id,
            artist,
            track,
            artist_norm,
            track_norm,
            matched,
            library_file_path,
            best_candidate_path,
            score,
            matcher_version
        FROM track_matches
        WHERE matcher_version = ?
        """,
        (matcher_version,),
    ).fetchall()

    return [dict(row) for row in rows]


def upsert_track_matches(conn, rows):
    """Insert or update persistent match and unmatched results."""

    conn.executemany(
        """
        INSERT INTO track_matches (
            wefunk_track_id,
            show_id,
            artist,
            track,
            artist_norm,
            track_norm,
            matched,
            library_file_path,
            best_candidate_path,
            score,
            matcher_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(wefunk_track_id) DO UPDATE SET
            show_id = excluded.show_id,
            artist = excluded.artist,
            track = excluded.track,
            artist_norm = excluded.artist_norm,
            track_norm = excluded.track_norm,
            matched = excluded.matched,
            library_file_path = excluded.library_file_path,
            best_candidate_path = excluded.best_candidate_path,
            score = excluded.score,
            matcher_version = excluded.matcher_version,
            updated_at = CURRENT_TIMESTAMP
        """,
        rows,
    )

    conn.commit()


def prune_orphaned_track_matches(conn):
    """Remove cached entries whose source track no longer exists."""

    cursor = conn.execute(
        """
        DELETE FROM track_matches
        WHERE wefunk_track_id NOT IN (
            SELECT id
            FROM tracks
        )
        """
    )

    conn.commit()
    return cursor.rowcount


def rebuild_legacy_matches_table(conn, matcher_version):
    """Rebuild matches_tags from persistent matched results."""

    reset_matches_table(conn)

    conn.execute(
        """
        INSERT INTO matches_tags (
            show_id,
            artist,
            track,
            file_path,
            score
        )
        SELECT
            show_id,
            artist,
            track,
            library_file_path,
            score
        FROM track_matches
        WHERE matcher_version = ?
          AND matched = 1
          AND library_file_path IS NOT NULL
        ORDER BY wefunk_track_id
        """,
        (matcher_version,),
    )

    conn.commit()


def load_current_results(conn, matcher_version):
    """Load persistent results that still correspond to current tracks."""

    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            tm.wefunk_track_id,
            tm.show_id,
            tm.artist,
            tm.track,
            tm.artist_norm,
            tm.track_norm,
            tm.matched,
            tm.library_file_path,
            tm.best_candidate_path,
            tm.score
        FROM track_matches AS tm
        INNER JOIN tracks AS t
            ON t.id = tm.wefunk_track_id
        WHERE tm.matcher_version = ?
        ORDER BY tm.wefunk_track_id
        """,
        (matcher_version,),
    ).fetchall()

    return [dict(row) for row in rows]


def ensure_library_index_table(conn):
    """Create the persistent local-music library index."""

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS library_index (
            file_path TEXT PRIMARY KEY,

            file_size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,

            artist TEXT NOT NULL,
            title TEXT NOT NULL,

            artist_norm TEXT NOT NULL,
            title_norm TEXT NOT NULL,
            combined_norm TEXT NOT NULL,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_library_index_artist_norm
        ON library_index(artist_norm)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_library_index_title_norm
        ON library_index(title_norm)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_library_index_artist_title
        ON library_index(artist_norm, title_norm)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_library_index_mtime
        ON library_index(mtime_ns)
        """
    )

    conn.commit()


def load_library_index(conn):
    """Load all persistent library-index rows keyed by file path."""

    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            file_path,
            file_size,
            mtime_ns,
            artist,
            title,
            artist_norm,
            title_norm,
            combined_norm
        FROM library_index
        ORDER BY file_path
        """
    ).fetchall()

    return {
        row["file_path"]: dict(row)
        for row in rows
    }


def load_library_index_rows(conn):
    """Load all library-index rows as dictionaries."""

    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            file_path,
            file_size,
            mtime_ns,
            artist,
            title,
            artist_norm,
            title_norm,
            combined_norm
        FROM library_index
        ORDER BY file_path
        """
    ).fetchall()

    return [dict(row) for row in rows]


def upsert_library_index_rows(conn, rows):
    """Insert new library files or update changed library files."""

    if not rows:
        return 0

    conn.executemany(
        """
        INSERT INTO library_index (
            file_path,
            file_size,
            mtime_ns,
            artist,
            title,
            artist_norm,
            title_norm,
            combined_norm
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            file_size = excluded.file_size,
            mtime_ns = excluded.mtime_ns,
            artist = excluded.artist,
            title = excluded.title,
            artist_norm = excluded.artist_norm,
            title_norm = excluded.title_norm,
            combined_norm = excluded.combined_norm,
            updated_at = CURRENT_TIMESTAMP
        """,
        rows,
    )

    conn.commit()
    return len(rows)


def delete_library_index_paths(conn, file_paths):
    """Delete specific paths from the persistent library index."""

    file_paths = list(file_paths)

    if not file_paths:
        return 0

    conn.executemany(
        """
        DELETE FROM library_index
        WHERE file_path = ?
        """,
        ((file_path,) for file_path in file_paths),
    )

    conn.commit()
    return len(file_paths)


def clear_library_index(conn):
    """Clear the entire persistent library index."""

    cursor = conn.execute("DELETE FROM library_index")
    conn.commit()
    return cursor.rowcount


def count_library_index_rows(conn):
    """Return the number of cached local-library files."""

    return conn.execute(
        """
        SELECT COUNT(*)
        FROM library_index
        """
    ).fetchone()[0]

