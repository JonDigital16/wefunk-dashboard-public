#!/usr/bin/env python3

import sys
import re
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, artist_slugify, esc, slugify
from data import owned_tracks_enriched

TEMPLATE = SITE / "years.html"
YEAR_DIR = SITE / "years"

YEAR_DIR.mkdir(parents=True, exist_ok=True)

template = TEMPLATE.read_text(encoding="utf-8")

years = defaultdict(list)

for r in owned_tracks_enriched:
    raw = (r.get("matched_year") or "").strip()
    m = re.search(r"\d{4}", raw)
    if m:
        years[m.group(0)].append(r)

for year, items in sorted(years.items(), reverse=True):
    rows = "\n".join(
        f"<tr>"
        f"<td><a href='/shows/{esc(r.get('show_id',''))}.html'>{esc(r.get('show_id',''))}</a></td>"
        f"<td><a href='/artists/{artist_slugify(r.get('artist',''))}.html'>{esc(r.get('artist',''))}</a></td>"
        f"<td>{esc(r.get('track',''))}</td>"
        f"<td><a href='/albums/{esc(r.get('matched_album_slug',''))}.html'>{esc(r.get('matched_album',''))}</a></td>"
        f"<td><a href='/genres/{slugify(r.get('matched_genre',''))}.html'>{esc(r.get('matched_genre',''))}</a></td>"
        f"<td>{esc(r.get('score',''))}</td>"
        f"</tr>"
        for r in items
    )

    card = f"""
<div class="card">
<p><a href="/years.html">← Back to Year Index</a></p>
<h2>{esc(year)}</h2>
<p class="small">{len(items)} matched WEFUNK tracks from {esc(year)}.</p>

<input id="yearDetailFilter" placeholder="Filter this year..." oninput="filterTable('yearDetailFilter','yearDetail')">

<table id="yearDetail">
<thead>
<tr>
<th onclick="sortTable('yearDetail',0,true)">Show</th>
<th onclick="sortTable('yearDetail',1)">Artist</th>
<th onclick="sortTable('yearDetail',2)">Track</th>
<th onclick="sortTable('yearDetail',3)">Album</th>
<th onclick="sortTable('yearDetail',4)">Genre</th>
<th onclick="sortTable('yearDetail',5,true)">Score</th>
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

    (YEAR_DIR / f"{year}.html").write_text(page, encoding="utf-8")

print(f"Generated {len(years)} year pages")
