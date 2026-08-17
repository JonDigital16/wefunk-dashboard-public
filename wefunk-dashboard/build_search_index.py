#!/usr/bin/env python3

import json
from pathlib import Path

from data import (
    owned_tracks_enriched,
    album_index,
    genre_dna,
    show_stats,
)
from common import SITE, artist_slugify, slugify

items = []



# Commands
commands = [
    ("Go Home", "/"),
    ("Open Search", "/search.html"),
    ("Browse Episodes", "/episodes.html"),
    ("Browse Albums", "/albums.html"),
    ("Browse Genres", "/genres.html"),
    ("Browse Years", "/years.html"),
    ("View Recent Matches", "/recent-matches.html"),
    ("Open Shopping List", "/shopping.html"),
    ("Open Recommended Albums", "/recommended-albums.html"),
    ("Open Missing Tracks", "/missing.html"),
    ("Open WEFUNK DNA", "/dna.html"),
]

for title, url in commands:
    items.append({
        "type": "command",
        "title": title,
        "url": url
    })

# Reports
reports = [
    ("Dashboard", "/"),
    ("Search", "/search.html"),
    ("Episodes Archive", "/episodes.html"),
    ("Recent Matches", "/recent-matches.html"),
    ("Missing Tracks", "/missing.html"),
    ("Smart Shopping List", "/shopping.html"),
    ("Recommended Albums", "/recommended-albums.html"),
    ("Album Index", "/albums.html"),
    ("Genre Index", "/genres.html"),
    ("Year Index", "/years.html"),
    ("Top Missing Artists", "/top-missing-artists.html"),
    ("Best Matching Shows", "/best-matching.html"),
    ("Almost Complete Shows", "/almost-complete.html"),
    ("WEFUNK DNA", "/dna.html"),
]

for title, url in reports:
    items.append({
        "type": "report",
        "title": title,
        "url": url
    })

# Artists
artists = set()

for r in owned_tracks_enriched:
    artist = (r.get("artist") or "").strip()

    if artist and artist.lower() not in artists:
        artists.add(artist.lower())
        items.append({
            "type": "artist",
            "title": artist,
            "url": f"/artists/{artist_slugify(artist)}.html"
        })

# Albums
for r in album_index:
    items.append({
        "type": "album",
        "title": f"{r['artist']} — {r['album']}",
        "url": f"/albums/{r['slug']}.html"
    })


# Tracks
seen_tracks = set()

for r in owned_tracks_enriched:
    artist = (r.get("artist") or "").strip()
    track = (r.get("track") or "").strip()
    show = (r.get("show_id") or "").strip()

    if not artist or not track:
        continue

    key = (artist.lower(), track.lower(), show)

    if key in seen_tracks:
        continue

    seen_tracks.add(key)

    items.append({
        "type": "track",
        "title": f"{artist} — {track}",
        "url": f"/shows/{show}.html"
    })

# Genres
for r in genre_dna:
    items.append({
        "type": "genre",
        "title": r["genre"],
        "url": f"/genres/{slugify(r['genre'])}.html"
    })


# Years
years = set()

for r in owned_tracks_enriched:
    year = str(r.get("matched_year", "")).strip()[:4]

    if year.isdigit() and year not in years:
        years.add(year)
        items.append({
            "type": "year",
            "title": year,
            "url": f"/years/{year}.html"
        })

# Shows
for r in show_stats:
    show = str(r.get("show_id",""))
    items.append({
        "type": "show",
        "title": show,
        "url": f"/shows/{show}.html"
    })

out = SITE / "search-index.json"

out.write_text(
    json.dumps(items, indent=2),
    encoding="utf-8"
)

print(f"Wrote {len(items)} search entries")
print(out)
