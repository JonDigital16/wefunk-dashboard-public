#!/usr/bin/env python3

import csv
from pathlib import Path

from common import EXPORTS, slugify
from data import owned_tracks_enriched

OUT = EXPORTS / "wefunk_album_index.csv"

albums = {}

for r in owned_tracks_enriched:
    artist = (r.get("matched_album_artist") or r.get("artist") or "").strip()
    album = (r.get("matched_album") or "").strip()

    if not album:
        continue

    key = (artist.lower(), album.lower())

    if key not in albums:
        albums[key] = {
            "artist": artist,
            "album": album,
            "slug": slugify(f"{artist}-{album}"),
            "genre": r.get("matched_genre", ""),
            "year": r.get("matched_year", ""),
            "tracks": 0,
        }

    albums[key]["tracks"] += 1

with OUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "artist",
            "album",
            "slug",
            "genre",
            "year",
            "tracks",
        ],
    )

    writer.writeheader()

    for row in sorted(albums.values(), key=lambda x: (x["artist"], x["album"])):
        writer.writerow(row)

print(f"Wrote {len(albums)} albums")
print(OUT)
