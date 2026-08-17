#!/usr/bin/env python3

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from data import owned_tracks_enriched

artists = defaultdict(set)

for r in owned_tracks_enriched:
    artist = (r.get("artist") or "").strip()
    album = (r.get("matched_album") or "").strip()

    if artist and album:
        artists[artist].add(album)

print()
print("Artists with matched albums")
print("---------------------------")

for artist, albums in sorted(
    artists.items(),
    key=lambda x: (-len(x[1]), x[0].lower())
)[:50]:
    print(f"{artist:35} {len(albums):3} albums")
