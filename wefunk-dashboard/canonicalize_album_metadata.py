#!/usr/bin/env python3

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from common import EXPORTS, slugify

SOURCE = EXPORTS / "wefunk_owned_tracks_enriched.csv"
TEMP = EXPORTS / "wefunk_owned_tracks_enriched.tmp.csv"
REPORT = EXPORTS / "wefunk_album_canonicalization.csv"

GENERIC_FOLDERS = {
    "",
    "apple music library",
    "compilations",
    "music",
    "singles",
    "soundtracks",
    "unknown artist",
    "various artists",
}


def clean(value):
    return " ".join(str(value or "").strip().split())


def base_artist(value):
    value = clean(value)

    for pattern in [
        r"\s+(?:feat(?:uring)?|ft)\.?\s+.*$",
        r"\s+with\s+.*$",
    ]:
        value = re.sub(pattern, "", value, flags=re.I).strip()

    return value


def choose_artist(rows, album_folder):
    tagged = [
        clean(row.get("matched_album_artist"))
        for row in rows
        if clean(row.get("matched_album_artist"))
    ]

    if tagged:
        winner = Counter(x.lower() for x in tagged).most_common(1)[0][0]
        return next(x for x in tagged if x.lower() == winner)

    folder_artist = clean(album_folder.parent.name)

    if folder_artist.lower() not in GENERIC_FOLDERS:
        return folder_artist

    candidates = [
        base_artist(row.get("artist"))
        for row in rows
        if base_artist(row.get("artist"))
    ]

    if candidates:
        winner = Counter(x.lower() for x in candidates).most_common(1)[0][0]
        return next(x for x in candidates if x.lower() == winner)

    return "Various Artists"


with SOURCE.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    fieldnames = list(reader.fieldnames or [])
    rows = list(reader)

groups = defaultdict(list)

for row in rows:
    file_path = Path(clean(row.get("file_path")))
    album = clean(row.get("matched_album"))

    if album and file_path.name:
        groups[file_path.parent].append(row)

report = []
changed = 0

for album_folder, album_rows in groups.items():
    album_names = [
        clean(row.get("matched_album"))
        for row in album_rows
        if clean(row.get("matched_album"))
    ]

    if not album_names:
        continue

    winner = Counter(x.lower() for x in album_names).most_common(1)[0][0]
    canonical_album = next(x for x in album_names if x.lower() == winner)
    canonical_artist = choose_artist(album_rows, album_folder)
    canonical_slug = slugify(f"{canonical_artist}-{canonical_album}")

    previous_artists = sorted({
        clean(row.get("matched_album_artist"))
        or clean(row.get("artist"))
        for row in album_rows
    })

    for row in album_rows:
        old_artist = clean(row.get("matched_album_artist"))
        old_slug = clean(row.get("matched_album_slug"))

        row["matched_album_artist"] = canonical_artist
        row["matched_album"] = canonical_album
        row["matched_album_slug"] = canonical_slug

        if old_artist != canonical_artist or old_slug != canonical_slug:
            changed += 1

    report.append({
        "album_directory": str(album_folder),
        "canonical_artist": canonical_artist,
        "canonical_album": canonical_album,
        "canonical_slug": canonical_slug,
        "track_count": len(album_rows),
        "previous_artists": " | ".join(previous_artists),
    })

for column in [
    "matched_album_artist",
    "matched_album",
    "matched_album_slug",
]:
    if column not in fieldnames:
        fieldnames.append(column)

with TEMP.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)

TEMP.replace(SOURCE)

with REPORT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "album_directory",
            "canonical_artist",
            "canonical_album",
            "canonical_slug",
            "track_count",
            "previous_artists",
        ],
    )
    writer.writeheader()
    writer.writerows(report)

print("Canonical album metadata complete")
print(f"Physical albums: {len(groups)}")
print(f"Rows changed: {changed}")
print(REPORT)
