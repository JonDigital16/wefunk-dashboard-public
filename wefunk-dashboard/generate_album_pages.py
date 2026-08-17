#!/usr/bin/env python3

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, artist_slugify, esc, slugify
from data import owned_tracks_enriched

TEMPLATE = SITE / "recommended-albums.html"
ALBUM_DIR = SITE / "albums"

ALBUM_DIR.mkdir(parents=True, exist_ok=True)

if not TEMPLATE.exists():
    raise SystemExit("recommended-albums.html does not exist yet. Run dashboard first.")

template = TEMPLATE.read_text(encoding="utf-8")

albums = {}

for r in owned_tracks_enriched:
    album = (r.get("matched_album") or "").strip()
    artist = (r.get("matched_album_artist") or r.get("artist") or "").strip()

    if not album:
        continue

    slug = (r.get("matched_album_slug") or slugify(f"{artist}-{album}")).strip()

    # Skip incomplete metadata rather than creating site/albums/.html.
    if not artist or not album or not slug:
        continue

    if slug not in albums:
        albums[slug] = {
            "artist": artist,
            "album": album,
            "items": [],
        }

    albums[slug]["items"].append(r)

for album_slug, album_data in sorted(albums.items(), key=lambda kv: kv[1]["album"].lower()):
    artist = album_data["artist"]
    album = album_data["album"]
    items = album_data["items"]
    rows = "\n".join(
        f"<tr>"
        f"<td><a href='/shows/{esc(r.get('show_id',''))}.html'>{esc(r.get('show_id',''))}</a></td>"
        f"<td><a href='/artists/{artist_slugify(r.get('artist',''))}.html'>{esc(r.get('artist',''))}</a></td>"
        f"<td>{esc(r.get('track',''))}</td>"
        f"<td><a href='/genres/{slugify(r.get('matched_genre',''))}.html'>{esc(r.get('matched_genre',''))}</a></td>"
        f"<td>{esc(r.get('matched_year',''))}</td>"
        f"<td>{esc(r.get('score',''))}</td>"
        f"</tr>"
        for r in items
    )

    card = f"""
<div class="card">
<p><a href="/recommended-albums.html">← Back to Recommended Albums</a></p>
<div style="display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap;">
<div>
<img src="/covers/{album_slug}.jpg"
     loading="lazy"
     onerror="this.style.display='none';"
     style="width:240px;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.35);">
</div>

<div style="flex:1;min-width:320px;">
<h2>{esc(album)}</h2>
<p class="small">{esc(artist)}</p>

<p class="small">{esc(artist)} · {len(items)} matched WEFUNK tracks from this album.</p>

<input id="albumFilter" placeholder="Filter this album..." oninput="filterTable('albumFilter','albumTable')">

<table id="albumTable">
<thead>
<tr>
<th onclick="sortTable('albumTable',0,true)">Show</th>
<th onclick="sortTable('albumTable',1)">WEFUNK Artist</th>
<th onclick="sortTable('albumTable',2)">WEFUNK Track</th>
<th onclick="sortTable('albumTable',3)">Genre</th>
<th onclick="sortTable('albumTable',4,true)">Year</th>
<th onclick="sortTable('albumTable',5,true)">Score</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</div>
</div>
"""

    start = template.find('<div class="card">')
    end = template.rfind("</body>")
    page = template[:start] + card + "\n" + template[end:]

    out = ALBUM_DIR / f"{album_slug}.html"
    out.write_text(page, encoding="utf-8")

print(f"Generated {len(albums)} album pages")
