#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, esc, slugify
from data import recommended_albums, album_index_by_artist_album

TEMPLATE = SITE / "shopping.html"
OUT = SITE / "recommended-albums.html"

if not TEMPLATE.exists():
    raise SystemExit("shopping.html does not exist yet. Run dashboard first.")

template = TEMPLATE.read_text(encoding="utf-8")

rows = "\n".join(
    f"<tr>"
    f"<td>{esc(r.get('artist',''))}</td>"
    f"<td><a href='/albums/{esc(album_index_by_artist_album.get((str(r.get('artist','')).strip().lower(), str(r.get('album','')).strip().lower()), {}).get('slug') or slugify((r.get('artist','')) + '-' + (r.get('album',''))))}.html'>{esc(r.get('album',''))}</a></td>"
    f"<td data-sort='{esc(r.get('tracks_gained', r.get('matched_tracks', '0')))}'>{esc(r.get('tracks_gained', r.get('matched_tracks', '')))}</td>"
    f"<td data-sort='{esc(r.get('shows_improved', '0'))}'>{esc(r.get('shows_improved', ''))}</td>"
    f"</tr>"
    for r in recommended_albums
)

card = f"""
<div class="card">
<p><a href="/">← Back</a></p>
<h2>Recommended Albums</h2>
<p class="small">Albums already represented heavily in WEFUNK. Buying these will likely increase your collection the fastest.</p>

<input id="recommendedFilter" placeholder="Filter recommended albums..." oninput="filterTable('recommendedFilter','recommendedAlbums')">

<table id="recommendedAlbums">
<thead>
<tr>
<th onclick="sortTable('recommendedAlbums',0)">Artist</th>
<th onclick="sortTable('recommendedAlbums',1)">Album</th>
<th onclick="sortTable('recommendedAlbums',2,true)">Tracks Gained</th>
<th onclick="sortTable('recommendedAlbums',3,true)">Shows Improved</th>
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
OUT.write_text(page, encoding="utf-8")

print(f"Wrote: {OUT}")
