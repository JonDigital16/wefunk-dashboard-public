#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, esc, slugify
from data import genre_dna

TEMPLATE = SITE / "dna.html"
OUT = SITE / "genres.html"

template = TEMPLATE.read_text(encoding="utf-8")

rows = "\n".join(
    f"<tr>"
    f"<td><a href='/genres/{slugify(r.get('genre',''))}.html'>{esc(r.get('genre',''))}</a></td>"
    f"<td data-sort='{esc(r.get('count','0'))}'>{esc(r.get('count',''))}</td>"
    f"</tr>"
    for r in sorted(genre_dna, key=lambda x: int(x.get("count") or 0), reverse=True)
)

card = f"""
<div class="card">
<p><a href="/">← Back</a></p>
<h2>Genre Index</h2>
<p class="small">Genres represented in your matched WEFUNK tracks.</p>

<input id="genreIndexFilter" placeholder="Filter genres..." oninput="filterTable('genreIndexFilter','genreIndex')">

<table id="genreIndex">
<thead>
<tr>
<th onclick="sortTable('genreIndex',0)">Genre</th>
<th onclick="sortTable('genreIndex',1,true)">Matched Tracks</th>
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
