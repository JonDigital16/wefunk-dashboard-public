import os
import csv
import re
import sys
from pathlib import Path
from html import escape
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from common import SITE, artist_slugify, slugify

CSV = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve() / 'wefunk_recent_matches.csv'
TEMPLATE = SITE / "episodes.html"
OUT = SITE / "recent-matches.html"

template = TEMPLATE.read_text(encoding="utf-8")

rows = []
if CSV.exists():
    with CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

rows = rows[:250]

def pretty_date(value):
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return value, ""

    diff = datetime.now() - dt

    if diff < timedelta(hours=24):
        if diff < timedelta(minutes=1):
            return "Just now", "NEW"
        if diff < timedelta(hours=1):
            return f"{int(diff.total_seconds() / 60)} min ago", "NEW"
        return dt.strftime("Today %-I:%M %p"), "NEW"

    if diff < timedelta(days=2):
        return dt.strftime("Yesterday %-I:%M %p"), ""

    return dt.strftime("%b %-d %-I:%M %p"), ""

table_rows = []

for r in rows:
    display_date, badge = pretty_date(r.get("date_added", ""))
    badge_html = "<span class='new-badge'>NEW</span> " if badge == "NEW" else ""
    show = str(r.get("show", "")).strip()

    table_rows.append(
        f"<tr>"
        f"<td>{badge_html}{escape(display_date)}</td>"
        f"<td style='display:flex;align-items:center;gap:12px;'>"
        f"<img src='/episode-art/{escape(show)}.jpg' loading='lazy' onerror=\"this.style.display='none';\" style='width:46px;height:46px;object-fit:cover;border-radius:8px;'>"
        f"<a href='/shows/{escape(show)}.html'>{escape(show)}</a>"
        f"</td>"
        f"<td><a href='/artists/{artist_slugify(r.get('artist',''))}.html'>{escape(r.get('artist',''))}</a></td>"
        f"<td>{escape(r.get('track',''))}</td>"
        f"<td>{escape(r.get('match',''))}</td>"
        f"<td><a href='/albums/{escape(r.get('album_slug') or slugify((r.get('artist','')) + '-' + (r.get('album',''))))}.html'>{escape(r.get('album',''))}</a></td>"
        f"<td><a href='/genres/{slugify(r.get('genre',''))}.html'>{escape(r.get('genre',''))}</a></td>"
        f"<td>{escape(r.get('year',''))}</td>"
        f"</tr>"
    )

if table_rows:
    table_html = "\n".join(table_rows)
else:
    table_html = "<tr><td colspan='8'>No recent matches yet. Future scans will populate this page.</td></tr>"

recent_card = f"""
<div class="card">
<p><a href="/">← Back</a></p>
<h2>Recent Matches</h2>
<p class="small">Newly discovered WEFUNK matches from recent scans.</p>

<input id="recentFilter" placeholder="Filter recent matches..." oninput="filterTable('recentFilter','recentMatches')">

<table id="recentMatches">
<thead>
<tr>
<th>Date Added</th>
<th>Show</th>
<th>WEFUNK Artist</th>
<th>WEFUNK Track</th>
<th>Your Match</th>
<th>Album</th>
<th>Genre</th>
<th>Year</th>
</tr>
</thead>
<tbody>
{table_html}
</tbody>
</table>
</div>
"""

extra_css = """
<style>
.new-badge{
  display:inline-block;
  margin-right:6px;
  padding:2px 7px;
  border-radius:999px;
  background:#F7931E;
  color:#111;
  font-size:12px;
  font-weight:800;
}
</style>
"""

template = template.replace("</head>", extra_css + "\n</head>")

start = template.find('<div class="card">')
end = template.rfind("</body>")

page = template[:start] + recent_card + "\n" + template[end:]

OUT.write_text(page, encoding="utf-8")
print(f"Wrote: {OUT}")
