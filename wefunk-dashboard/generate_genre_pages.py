#!/usr/bin/env python3

import sys
import re
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, artist_slugify, esc, slugify
from data import owned_tracks_enriched

TEMPLATE = SITE / "dna.html"
GENRE_DIR = SITE / "genres"

GENRE_DIR.mkdir(parents=True, exist_ok=True)

if not TEMPLATE.exists():
    raise SystemExit("dna.html does not exist yet. Run dashboard first.")

template = TEMPLATE.read_text(encoding="utf-8")

genres = defaultdict(list)

for r in owned_tracks_enriched:
    raw_genre = (r.get("matched_genre") or "").strip()
    if not raw_genre:
        continue

    for genre in re.split(r"[,;/|]", raw_genre):
        genre = genre.strip()
        if genre:
            genres[genre].append(r)

for genre, items in sorted(genres.items()):
    rows = "\n".join(
        f"<tr>"
        f"<td><a href='/shows/{esc(r.get('show_id',''))}.html'>{esc(r.get('show_id',''))}</a></td>"
        f"<td><a href='/artists/{artist_slugify(r.get('artist',''))}.html'>{esc(r.get('artist',''))}</a></td>"
        f"<td>{esc(r.get('track',''))}</td>"
        f"<td><a href='/albums/{esc(r.get('matched_album_slug') or slugify((r.get('artist','')) + '-' + (r.get('matched_album',''))))}.html'>{esc(r.get('matched_album',''))}</a></td>"
        f"<td>{esc(r.get('matched_year',''))}</td>"
        f"<td>{esc(r.get('score',''))}</td>"
        f"</tr>"
        for r in items
    )

    card = f"""
<div class="card">
<p><a href="/dna.html">← Back to WEFUNK DNA</a></p>
<h2>{esc(genre)}</h2>
<p class="small">{len(items)} matched tracks in this genre.</p>

<input id="genreFilter" placeholder="Filter this genre..." oninput="filterTable('genreFilter','genreTable')">

<table id="genreTable">
<thead>
<tr>
<th onclick="sortTable('genreTable',0,true)">Show</th>
<th onclick="sortTable('genreTable',1)">WEFUNK Artist</th>
<th onclick="sortTable('genreTable',2)">WEFUNK Track</th>
<th onclick="sortTable('genreTable',3)">Album</th>
<th onclick="sortTable('genreTable',4,true)">Year</th>
<th onclick="sortTable('genreTable',5,true)">Score</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</div>
"""

    start = template.find('<div class="card">')
    end = template.rfind("</body>")
    page = template[:start] + card + "\n" + template[end:]

    out = GENRE_DIR / f"{slugify(genre)}.html"
    out.write_text(page, encoding="utf-8")

print(f"Generated {len(genres)} genre pages")
