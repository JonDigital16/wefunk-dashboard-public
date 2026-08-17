#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, artist_slugify, esc, slugify
from data import album_index

TEMPLATE = SITE / "recommended-albums.html"
OUT = SITE / "albums.html"

if not TEMPLATE.exists():
    raise SystemExit("recommended-albums.html does not exist yet. Run dashboard first.")

template = TEMPLATE.read_text(encoding="utf-8")

rows = "\n".join(
    f"<tr>"
    f"<td><a href='/artists/{artist_slugify(r.get('artist',''))}.html'>{esc(r.get('artist',''))}</a></td>"
    f"<td style='display:flex;align-items:center;gap:12px;'>"
    f"<img src='/covers/{esc(r.get('slug',''))}.jpg' loading='lazy' onerror=\"this.style.display='none';\" style='width:46px;height:46px;object-fit:cover;border-radius:8px;'>"
    f"<a href='/albums/{esc(r.get('slug',''))}.html'>{esc(r.get('album',''))}</a>"
    f"</td>"
    f"<td><a href='/genres/{slugify(r.get('genre',''))}.html'>{esc(r.get('genre',''))}</a></td>"
    f"<td>{esc(r.get('year',''))}</td>"
    f"<td data-sort='{esc(r.get('tracks','0'))}'>{esc(r.get('tracks',''))}</td>"
    f"</tr>"
    for r in sorted(album_index, key=lambda x: int(x.get("tracks") or 0), reverse=True)
)

card = f"""
<div class="card">
<p><a href="/">← Back</a></p>
<h2>Album Index</h2>
<p class="small">Albums in your library that match WEFUNK tracks.</p>

<input id="albumIndexFilter" placeholder="Filter albums..." oninput="filterTable('albumIndexFilter','albumIndex')">

<table id="albumIndex">
<thead>
<tr>
<th onclick="sortTable('albumIndex',0)">Artist</th>
<th onclick="sortTable('albumIndex',1)">Album</th>
<th onclick="sortTable('albumIndex',2)">Genre</th>
<th onclick="sortTable('albumIndex',3,true)">Year</th>
<th onclick="sortTable('albumIndex',4,true)">Matched Tracks</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</div>
"""

start = template.find("<main>")
end = template.rfind("</main>")

if start == -1 or end == -1:
    raise SystemExit("Could not locate <main> page boundaries")

start += len("<main>")

page = template[:start] + "\n" + card + "\n" + template[end:]
page = page.replace(
    "<title>Recommended Albums</title>",
    "<title>Album Index</title>",
    1,
)
OUT.write_text(page, encoding="utf-8")

print(f"Wrote: {OUT}")
