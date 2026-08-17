#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, esc, z_date_short, z_date_sort
from data import show_stats, play_counts_by_show

TEMPLATE = SITE / "episodes.html"
OUT = SITE / "episodes.html"

if not TEMPLATE.exists():
    raise SystemExit("episodes.html does not exist yet. Run generate_dashboard.py first.")

template = TEMPLATE.read_text(encoding="utf-8")

all_episode_rows = "\n".join(
    f"<tr>"
    f"<td style='display:flex;align-items:center;gap:12px;'>"
    f"<img src='/episode-art/{esc(r['show_id'])}.jpg' loading='lazy' onerror=\"this.style.display='none';\" style='width:46px;height:46px;object-fit:cover;border-radius:8px;'>"
    f"<a href='/shows/{esc(r['show_id'])}.html'>{esc(r['show_id'])}</a>"
    f"</td>"
    f"<td data-sort='{z_date_sort(r['recorded'])}'>{esc(z_date_short(r['recorded']))}</td>"
    f"<td>{esc(r['djs'])}</td>"
    f"<td data-sort='{int(play_counts_by_show.get(str(r['show_id']), {}).get('play_count') or 0)}'>{esc(play_counts_by_show.get(str(r['show_id']), {}).get('play_count') or '0')}</td>"
    f"<td>{esc(r['matched_tracks'])}/{esc(r['total_tracks'])}</td>"
    f"<td>{esc(r['match_percent'])}%</td>"
    f"<td><div class='bar'><div class='fill' style='width:{esc(r['match_percent'])}%'></div></div></td>"
    f"</tr>"
    for r in sorted(show_stats, key=lambda x: int(x["show_id"]), reverse=True)
)

episodes_card = f"""
<div class="card">
<p><a href="/">← Back</a></p>
<h2>All Episodes Archive</h2>
<p class="small">Every WEFUNK episode in your dashboard, newest first.</p>

<input id="episodesFilter" placeholder="Filter episodes by show, date, DJ..." oninput="filterTable('episodesFilter','episodesArchive')">

<table id="episodesArchive">
<thead>
<tr>
<th onclick="sortTable('episodesArchive',0,true)">Show</th>
<th onclick="sortTable('episodesArchive',1)">Date</th>
<th onclick="sortTable('episodesArchive',2)">DJs</th>
<th onclick="sortTable('episodesArchive',3,true)">Plays</th>
<th onclick="sortTable('episodesArchive',4,true)">Matched</th>
<th onclick="sortTable('episodesArchive',5,true)">Match %</th>
<th></th>
</tr>
</thead>
<tbody>
{all_episode_rows}
</tbody>
</table>
</div>
"""

start = template.find('<div class="card">')
end = template.rfind("</body>")

if start == -1 or end == -1:
    raise SystemExit("Could not find replaceable page body in episodes.html")

page = template[:start] + episodes_card + "\n" + template[end:]

OUT.write_text(page, encoding="utf-8")

print(f"Wrote: {OUT}")
