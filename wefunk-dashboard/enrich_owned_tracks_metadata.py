#!/usr/bin/env python3

import csv
import hashlib
import sys
from pathlib import Path

from mutagen import File

sys.path.insert(0, str(Path(__file__).parent))

from common import EXPORTS, slugify

SRC = EXPORTS / "wefunk_owned_tracks_tags.csv"
OUT = EXPORTS / "wefunk_owned_tracks_enriched.csv"
CHECKSUM = EXPORTS / "wefunk_owned_tracks_enriched.sha256"

current_hash = hashlib.sha256(SRC.read_bytes()).hexdigest()

if OUT.exists() and CHECKSUM.exists() and CHECKSUM.read_text().strip() == current_hash:
    print("Enriched owned tracks already current")
    print(OUT)
    raise SystemExit(0)

def tag(audio, names):
    if not audio:
        return ""

    for name in names:
        value = audio.get(name)

        if value:
            if isinstance(value, list):
                return str(value[0])
            if hasattr(value, "text") and value.text:
                return str(value.text[0])
            return str(value)

    return ""

rows = []

with SRC.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for r in reader:
        path = Path(r.get("file_path", ""))

        album = ""
        album_artist = ""
        genre = ""
        year = ""
        duration = ""
        bitrate = ""

        try:
            audio = File(path, easy=True)


            album = tag(audio, ["album"])
            album_artist = (
                tag(audio, ["albumartist", "album artist"])
                or tag(audio, ["artist"])
            )
            genre = tag(audio, ["genre"])
            year = tag(audio, ["date", "year", "originaldate"])

            if audio and audio.info:
                duration = round(getattr(audio.info, "length", 0) or 0)
                bitrate = getattr(audio.info, "bitrate", "") or ""

        except Exception:
            pass

        rows.append({
            **r,
            "matched_album": album,
            "matched_album_artist": album_artist,
            "matched_genre": genre,
            "matched_year": year,
            "matched_album_slug": slugify(f"{album_artist or r.get('artist','')}-{album}") if album else "",
            "duration_seconds": duration,
            "bitrate": bitrate,
        })

fieldnames = list(rows[0].keys()) if rows else [
    "show_id", "artist", "track", "file_path", "score",
    "matched_album", "matched_album_artist", "matched_genre",
    "matched_year", "matched_album_slug", "duration_seconds", "bitrate"
]

with OUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

CHECKSUM.write_text(current_hash)

print(f"Wrote {len(rows)} enriched owned tracks")
print(OUT)
