#!/usr/bin/env python3

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE

INDEX = SITE / "index.html"

if not INDEX.exists():
    raise SystemExit("Run generate_dashboard.py first.")

html = INDEX.read_text(encoding="utf-8")

new_cards = """
<a class="report-card" href="/best-matching.html">
  <div class="report-icon">🏆</div>
  <div class="report-title">Best Matching Shows</div>
  <div class="report-desc">See the WEFUNK episodes your collection matches best.</div>
</a>

<a class="report-card" href="/almost-complete.html">
  <div class="report-icon">✅</div>
  <div class="report-title">Almost Complete Shows</div>
  <div class="report-desc">Find episodes closest to being fully completed.</div>
</a>

<a class="report-card" href="/recommended-albums.html">
  <div class="report-icon">💿</div>
  <div class="report-title">Recommended Albums</div>
  <div class="report-desc">Albums that can improve the most WEFUNK episodes.</div>
</a>

<a class="report-card" href="/albums.html">
  <div class="report-icon">💽</div>
  <div class="report-title">Album Index</div>
  <div class="report-desc">Browse albums in your library that match WEFUNK tracks.</div>
</a>

<a class="report-card" href="/genres.html">
  <div class="report-icon">🧬</div>
  <div class="report-title">Genre Index</div>
  <div class="report-desc">Browse genres represented in your matched WEFUNK tracks.</div>
</a>

<a class="report-card" href="/years.html">
  <div class="report-icon">📅</div>
  <div class="report-title">Year Index</div>
  <div class="report-desc">Browse matched WEFUNK tracks by release year.</div>
</a>


<a class="report-card" href="/search.html">
  <div class="report-icon">🔎</div>
  <div class="report-title">Search</div>
  <div class="report-desc">Search artists, albums, genres, shows, and more from one place.</div>
</a>




<a class="report-card" href="/top-missing-artists.html">
  <div class="report-icon">🎤</div>
  <div class="report-title">Top Missing Artists</div>
  <div class="report-desc">Artists responsible for the most missing WEFUNK tracks.</div>
</a>
"""

if 'href="/best-matching.html"' not in html:
    marker = '</div>\n</div>\n\n<div class="card">\n<h2>Best Matching Shows</h2>'
    if marker in html:
        html = html.replace(
            marker,
            new_cards + '\n</div>\n</div>\n\n<div class="card">\n<h2>Best Matching Shows</h2>',
            1
        )
    else:
        raise SystemExit("Could not find Reports section insertion point.")

# Remove large homepage detail sections now that they have their own pages.
html = re.sub(
    r'\n<div class="card">\n<h2>Best Matching Shows</h2>.*?\n<script>',
    '\n<script>',
    html,
    flags=re.S
)




html = html.replace(
    "</body>",
    """
</body>
"""
)

INDEX.write_text(html, encoding="utf-8")

print(f"Wrote: {INDEX}")
