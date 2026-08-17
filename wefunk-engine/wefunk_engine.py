import argparse
import csv
import json
import re
import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv
from mutagen import File as MutagenFile
from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load project-local configuration without overriding
# variables already supplied by the operating environment.
load_dotenv(PROJECT_ROOT / ".env", override=False)

JSON_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "json"
JSON_FILE = max(JSON_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
MUSIC_DIR = Path(os.environ.get("WEFUNK_MUSIC_DIR", Path.home() / "Music")).expanduser().resolve()
DB_FILE = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "db" / 'wefunk_engine.db'
EXPORT_DIR = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve()
PLAYLIST_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "playlists"

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav"}

EXPORT_DIR.mkdir(parents=True, exist_ok=True)
PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE.parent.mkdir(parents=True, exist_ok=True)

def clean(s):
    s = str(s).lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)
    s = re.sub(r"\b(feat|ft|featuring|with)\b.*", "", s)
    s = s.replace("&", "and")
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # Collapse acronym runs:
    # d m x -> dmx
    # l l cool j -> ll cool j
    parts = s.split()
    out = []
    i = 0
    while i < len(parts):
        if len(parts[i]) == 1 and parts[i].isalpha():
            j = i
            letters = []
            while j < len(parts) and len(parts[j]) == 1 and parts[j].isalpha():
                letters.append(parts[j])
                j += 1
            if len(letters) >= 2:
                out.append("".join(letters))
            else:
                out.extend(letters)
            i = j
        else:
            out.append(parts[i])
            i += 1
    s = " ".join(out)

    aliases = {
        "a tribe called quest": "tribe called quest",
        "notorious b i g": "notorious big",
        "notorious big": "notorious big",
        "biggie smalls": "notorious big",
        "ol dirty bastard": "odb",
        "o d b": "odb",
        "jay z": "jayz",
        "jay z": "jayz",
        "jay-z": "jayz",
        "mos def": "mos def",
        "yasiin bey": "mos def",
        "q tip": "qtip",
        "q tip": "qtip",
        "kool g rap": "kool g rap",
        "kool g rap and dj polo": "kool g rap",
        "pete rock and cl smooth": "pete rock cl smooth",
        "pete rock cl smooth": "pete rock cl smooth",
        "smif n wessun": "smif n wessun",
        "cocoa brovaz": "smif n wessun",
    }

    return aliases.get(s, s)


def is_unknown_value(s):
    s = str(s or "").strip().lower()
    return (
        not s
        or s in {"unknown", "unknown song", "(unknown song)", "???", "??", "untitled", "n/a", "na", "-"}
        or "unknown song" in s
    )

def extract_artist_track(item):
    artist = item.get("artist", "").strip()
    track = item.get("track", "").strip()

    if artist and track and not is_unknown_value(track):
        return artist, track

    raw = (
        item.get("title")
        or item.get("song")
        or item.get("name")
        or item.get("text")
        or item.get("raw")
        or ""
    ).strip()

    patterns = [
        r"^(.+?)\s+[-–—]\s+(.+)$",
        r"^(.+?)\s*:\s*(.+)$",
        r"^(.+?)\s*/\s*(.+)$",
        r"^(.+?)\s+[\"“](.+?)[\"”]$",
    ]

    for pat in patterns:
        m = re.match(pat, raw)
        if m:
            a, t = m.group(1).strip(), m.group(2).strip()
            if not is_unknown_value(a) and not is_unknown_value(t):
                return a, t

    return artist, track

def tag_value(audio, keys):
    if not audio or not audio.tags:
        return ""
    for key in keys:
        val = audio.tags.get(key)
        if val:
            return str(val[0] if isinstance(val, list) else val)
    return ""

def connect():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = connect()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS shows (
        show_id TEXT PRIMARY KEY,
        recorded TEXT,
        djs TEXT,
        url TEXT,
        description TEXT
    );

    CREATE TABLE IF NOT EXISTS wefunk_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        show_id TEXT,
        artist TEXT,
        track TEXT,
        artist_norm TEXT,
        track_norm TEXT
    );

    CREATE TABLE IF NOT EXISTS library_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        artist TEXT,
        title TEXT,
        artist_norm TEXT,
        title_norm TEXT,
        file_path TEXT UNIQUE
    );

    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        show_id TEXT,
        wefunk_artist TEXT,
        wefunk_track TEXT,
        library_artist TEXT,
        library_title TEXT,
        file_path TEXT,
        score INTEGER
    );

    CREATE INDEX IF NOT EXISTS idx_wefunk_artist ON wefunk_tracks(artist_norm);
    CREATE INDEX IF NOT EXISTS idx_library_artist ON library_tracks(artist_norm);
    CREATE INDEX IF NOT EXISTS idx_matches_show ON matches(show_id);
    """)
    conn.commit()
    conn.close()

def import_wefunk():
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM shows")
    cur.execute("DELETE FROM wefunk_tracks")

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        shows = json.load(f)

    for show in shows:
        show_id = show.get("show_id", "")
        meta = show.get("meta_info", {})

        cur.execute("""
        INSERT OR REPLACE INTO shows
        VALUES (?, ?, ?, ?, ?)
        """, (
            show_id,
            meta.get("recorded", ""),
            ", ".join(meta.get("djs", [])),
            show.get("url", ""),
            show.get("showdescription", "")
        ))

        for item in show.get("playlistbox", []):
            artist, track = extract_artist_track(item)

            if is_unknown_value(artist) or is_unknown_value(track):
                continue
            if artist.lower() in {"intro", "outro"}:
                continue
            if artist.lower().startswith("talk"):
                continue

            cur.execute("""
            INSERT INTO wefunk_tracks
            (show_id, artist, track, artist_norm, track_norm)
            VALUES (?, ?, ?, ?, ?)
            """, (show_id, artist, track, clean(artist), clean(track)))

    conn.commit()
    conn.close()
    print(f"Imported {len(shows)} WEFUNK shows")

def index_library():
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM library_tracks")

    count = 0

    for path in MUSIC_DIR.rglob("*"):
        if path.suffix.lower() not in AUDIO_EXTS:
            continue

        try:
            audio = MutagenFile(path, easy=True)
            artist = tag_value(audio, ["artist", "albumartist"])
            title = tag_value(audio, ["title"])
        except Exception:
            artist = ""
            title = ""

        if not artist:
            artist = path.parent.name
        if not title:
            title = path.stem

        cur.execute("""
        INSERT OR REPLACE INTO library_tracks
        (artist, title, artist_norm, title_norm, file_path)
        VALUES (?, ?, ?, ?, ?)
        """, (artist, title, clean(artist), clean(title), str(path)))

        count += 1

    conn.commit()
    conn.close()
    print(f"Indexed {count} library tracks")

def match_tracks():
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM matches")

    library = cur.execute("""
    SELECT artist, title, artist_norm, title_norm, file_path
    FROM library_tracks
    """).fetchall()

    # Exact artist lookup.
    by_artist = {}

    # Preserve original library order so equal-score tie behavior stays stable.
    artist_groups = {}

    for index, row in enumerate(library):
        artist, title, artist_norm, title_norm, file_path = row
        by_artist.setdefault(artist_norm, []).append((index, row))
        artist_groups.setdefault(artist_norm, []).append((index, row))

    library_artist_norms = list(artist_groups.keys())

    wefunk_tracks = cur.execute("""
    SELECT show_id, artist, track, artist_norm, track_norm
    FROM wefunk_tracks
    """).fetchall()

    # Cache fuzzy artist candidate rows once per unique WEFUNK artist.
    fuzzy_artist_cache = {}

    matched = 0
    pending_matches = []
    total = len(wefunk_tracks)

    for position, (
        show_id,
        wf_artist,
        wf_track,
        wf_artist_norm,
        wf_track_norm,
    ) in enumerate(wefunk_tracks, 1):

        exact_rows = by_artist.get(wf_artist_norm)

        if exact_rows:
            # Exact normalized artist match; artist score is effectively 100.
            candidates = [
                (index, row, 100)
                for index, row in exact_rows
            ]
        else:
            candidates = fuzzy_artist_cache.get(wf_artist_norm)

            if candidates is None:
                candidates = []

                # Score each distinct library artist only once.
                for lib_artist_norm in library_artist_norms:
                    artist_score = fuzz.token_set_ratio(
                        wf_artist_norm,
                        lib_artist_norm,
                    )

                    if artist_score >= 88:
                        for index, row in artist_groups[lib_artist_norm]:
                            candidates.append((index, row, artist_score))

                # Match the original library ordering.
                candidates.sort(key=lambda item: item[0])
                fuzzy_artist_cache[wf_artist_norm] = candidates

        best = None
        best_score = 0

        for _, row, artist_score in candidates:
            (
                lib_artist,
                lib_title,
                lib_artist_norm,
                lib_title_norm,
                file_path,
            ) = row

            title_score = fuzz.token_set_ratio(
                wf_track_norm,
                lib_title_norm,
            )

            score = int(
                (artist_score * 0.35) +
                (title_score * 0.65)
            )

            # If the title is nearly exact, allow a slightly weaker artist match.
            if title_score >= 96 and artist_score >= 75:
                score = max(score, 90)

            # If artist is very strong, allow a slightly weaker title match.
            if artist_score >= 94 and title_score >= 82:
                score = max(score, 88)

            if score > best_score:
                best_score = score
                best = (
                    lib_artist,
                    lib_title,
                    file_path,
                )

        if best and best_score >= 88:
            pending_matches.append((
                show_id,
                wf_artist,
                wf_track,
                best[0],
                best[1],
                best[2],
                best_score,
            ))
            matched += 1

        if position % 5000 == 0 or position == total:
            print(
                f"Matching tracks: {position}/{total} "
                f"({matched} matches)"
            )

    cur.executemany("""
    INSERT INTO matches
    (
        show_id,
        wefunk_artist,
        wefunk_track,
        library_artist,
        library_title,
        file_path,
        score
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, pending_matches)

    conn.commit()
    conn.close()

    print(f"Matched {matched} WEFUNK tracks")

def export_reports():
    conn = connect()
    cur = conn.cursor()

    show_stats = cur.execute("""
    SELECT
        s.show_id,
        s.recorded,
        s.djs,
        COUNT(DISTINCT wt.id) AS total_tracks,
        COUNT(DISTINCT m.id) AS matched_tracks,
        ROUND((COUNT(DISTINCT m.id) * 100.0) / COUNT(DISTINCT wt.id), 1) AS match_percent
    FROM shows s
    JOIN wefunk_tracks wt ON wt.show_id = s.show_id
    LEFT JOIN matches m ON m.show_id = s.show_id
    GROUP BY s.show_id
    HAVING total_tracks > 0
    ORDER BY match_percent DESC, matched_tracks DESC
    """).fetchall()

    with open(EXPORT_DIR / "wefunk_show_match_stats.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["show_id", "recorded", "djs", "total_tracks", "matched_tracks", "match_percent"])
        writer.writerows(show_stats)

    missing = cur.execute("""
    SELECT wt.show_id, wt.artist, wt.track
    FROM wefunk_tracks wt
    LEFT JOIN matches m
      ON wt.show_id = m.show_id
     AND wt.artist = m.wefunk_artist
     AND wt.track = m.wefunk_track
    WHERE m.id IS NULL
    ORDER BY wt.artist, wt.track
    """).fetchall()

    with open(EXPORT_DIR / "wefunk_missing_tracks_engine.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["show_id", "artist", "track"])
        writer.writerows(missing)

    top_missing_artists = cur.execute("""
    SELECT wt.artist, COUNT(*) AS missing_count
    FROM wefunk_tracks wt
    LEFT JOIN matches m
      ON wt.show_id = m.show_id
     AND wt.artist = m.wefunk_artist
     AND wt.track = m.wefunk_track
    WHERE m.id IS NULL
    GROUP BY wt.artist
    ORDER BY missing_count DESC
    LIMIT 100
    """).fetchall()

    with open(EXPORT_DIR / "wefunk_top_missing_artists.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["artist", "missing_count"])
        writer.writerows(top_missing_artists)


    print(f"Reports exported to {EXPORT_DIR}")

def export_playlists():
    conn = connect()
    cur = conn.cursor()

    top_shows = cur.execute("""
    SELECT show_id, COUNT(*) AS matched_tracks
    FROM matches
    GROUP BY show_id
    HAVING matched_tracks >= 7
    ORDER BY matched_tracks DESC
    """).fetchall()

    top_dir = PLAYLIST_DIR / "engine-top-shows"
    top_dir.mkdir(parents=True, exist_ok=True)

    for show_id, matched_tracks in top_shows:
        rows = cur.execute("""
        SELECT DISTINCT file_path
        FROM matches
        WHERE show_id = ?
        ORDER BY id
        """, (show_id,)).fetchall()

        path = top_dir / f"WEFUNK_Show_{show_id}_{matched_tracks}_matches.m3u"

        with open(path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"# WEFUNK Show {show_id}\n")
            f.write(f"# Matched tracks: {matched_tracks}\n")
            for (file_path,) in rows:
                f.write(file_path + "\n")

    all_rows = cur.execute("""
    SELECT DISTINCT file_path
    FROM matches
    ORDER BY id
    """).fetchall()

    with open(PLAYLIST_DIR / "WEFUNK_engine_all_owned.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for (file_path,) in all_rows:
            f.write(file_path + "\n")

    conn.close()
    print(f"Playlists exported to {PLAYLIST_DIR}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-library-index", action="store_true")
    args = parser.parse_args()

    init_db()
    import_wefunk()

    if args.skip_library_index:
        print("Skipping library index; using existing library_tracks table")
    else:
        index_library()

    match_tracks()
    export_reports()
    export_playlists()
    print("WEFUNK engine complete")

if __name__ == "__main__":
    main()
