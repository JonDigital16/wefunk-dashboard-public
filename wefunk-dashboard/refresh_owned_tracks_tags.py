#!/usr/bin/env python3

import csv
import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

DB_FILE = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "db" / 'wefunk.db'
MUSIC_DIR = Path(os.environ.get("WEFUNK_MUSIC_DIR", Path.home() / "Music")).expanduser().resolve()
EXPORT_DIR = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve()
PLAYLIST_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "playlists"

MATCHER = Path(os.environ.get("WEFUNK_MATCHER_SCRIPT", Path(__file__).resolve().parents[1] / "engine" / "match_library_tags_v2.py"))
OUTPUT = EXPORT_DIR / "wefunk_owned_tracks_tags.csv"
PLAYLIST = PLAYLIST_DIR / "WEFUNK_owned_tracks_tags.m3u"
CHECKSUM = EXPORT_DIR / "wefunk_owned_tracks_tags.inputs.sha256"

AUDIO_EXTS = {
    ".mp3", ".flac", ".m4a", ".aac",
    ".ogg", ".opus", ".wav"
}


def atomic_write_text(path: Path, text: str) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def calculate_input_hash() -> tuple[str, int, int]:
    """
    Hash the current music-library file inventory and the WEFUNK tracks
    used by the matcher. File contents are not hashed; path, size and
    modification time are enough to detect additions, removals and edits.
    """
    digest = hashlib.sha256()

    audio_files = sorted(
        path
        for path in MUSIC_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTS
    )

    for path in audio_files:
        try:
            stat = path.stat()
        except OSError:
            continue

        digest.update(str(path).encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode())
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode())
        digest.update(b"\n")

    with sqlite3.connect(DB_FILE) as connection:
        tracks = connection.execute(
            """
            SELECT show_id, artist, track
            FROM tracks
            WHERE artist != '' AND track != ''
            ORDER BY show_id, artist, track
            """
        ).fetchall()

    for show_id, artist, track in tracks:
        digest.update(str(show_id).encode("utf-8", errors="replace"))
        digest.update(b"\0")
        digest.update(str(artist).encode("utf-8", errors="replace"))
        digest.update(b"\0")
        digest.update(str(track).encode("utf-8", errors="replace"))
        digest.update(b"\n")

    return digest.hexdigest(), len(audio_files), len(tracks)


def clean_export() -> tuple[int, int]:
    """
    Remove exported rows whose matched audio files no longer exist.
    Rewrite the CSV and playlist atomically.
    """
    if not OUTPUT.exists():
        raise RuntimeError(f"Matcher did not create expected file: {OUTPUT}")

    with OUTPUT.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames

        if not fieldnames:
            raise RuntimeError(f"CSV has no header: {OUTPUT}")

        rows = list(reader)

    valid_rows = []
    stale_count = 0

    for row in rows:
        file_path = Path(row.get("file_path", ""))

        if file_path.is_file():
            valid_rows.append(row)
        else:
            stale_count += 1

    temp_csv = OUTPUT.with_suffix(".csv.tmp")

    with temp_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid_rows)

    os.replace(temp_csv, OUTPUT)

    seen = set()
    playlist_lines = ["#EXTM3U"]

    for row in valid_rows:
        file_path = row.get("file_path", "").strip()

        if file_path and file_path not in seen:
            playlist_lines.append(file_path)
            seen.add(file_path)

    atomic_write_text(PLAYLIST, "\n".join(playlist_lines) + "\n")

    return len(valid_rows), stale_count


def main() -> None:
    for required in (DB_FILE, MUSIC_DIR, MATCHER):
        if not required.exists():
            raise SystemExit(f"❌ Required path not found: {required}")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)

    print("Checking WEFUNK tag-matcher inputs...")

    current_hash, audio_count, track_count = calculate_input_hash()

    print(f"  Music files: {audio_count}")
    print(f"  WEFUNK tracks: {track_count}")

    cached_hash = (
        CHECKSUM.read_text(encoding="utf-8").strip()
        if CHECKSUM.exists()
        else ""
    )

    if OUTPUT.exists() and cached_hash == current_hash:
        print("✅ Music library and WEFUNK tracks unchanged.")
        print("   Skipping tag matcher.")
        return

    print("Changes detected. Rebuilding owned-track tag matches...")

    subprocess.run(
        [sys.executable, "-m", "engine.match_library_tags_v2"],
        check=True,
        cwd=MATCHER.parents[1],
    )

    valid_count, stale_count = clean_export()

    # Only record a successful input state after matching and validation finish.
    atomic_write_text(CHECKSUM, current_hash + "\n")

    print("✅ Owned-track tag export refreshed.")
    print(f"  Valid matched rows: {valid_count}")
    print(f"  Stale rows removed: {stale_count}")
    print(f"  CSV: {OUTPUT}")


if __name__ == "__main__":
    main()
