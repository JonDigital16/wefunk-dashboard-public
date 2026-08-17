#!/usr/bin/env python3

import html as html_lib
import os
import re
from pathlib import Path

from common import artist_display_name

SITE = Path(
    os.environ.get(
        "WEFUNK_SITE_DIR",
        str(Path(__file__).resolve().parents[1] / "site"),
    )
)

INDEX = SITE / "index.html"
RECENT = SITE / "recent-matches.html"

if not INDEX.exists():
    raise SystemExit("index.html does not exist.")

if not RECENT.exists():
    raise SystemExit("recent-matches.html does not exist.")

homepage = INDEX.read_text(encoding="utf-8")
recent_html = RECENT.read_text(encoding="utf-8")

if 'id="homepageRecentMatches"' in homepage:
    print("Homepage Recent Matches already present")
    raise SystemExit(0)


def plain(value):
    value = re.sub(r"<[^>]+>", "", value)
    return html_lib.unescape(value).strip()


rows = re.findall(
    r"<tr[^>]*>(.*?)</tr>",
    recent_html,
    flags=re.S | re.I,
)

cards = []

for row in rows:
    cells = re.findall(
        r"<td[^>]*>(.*?)</td>",
        row,
        flags=re.S | re.I,
    )

    if len(cells) < 4:
        continue

    show_match = re.search(
        r'href=[\'"]/shows/([^\'"/]+)\.html[\'"]',
        row,
        flags=re.I,
    )

    if not show_match:
        continue

    show_id = show_match.group(1)

    # Current Recent Matches layout:
    # Show, Date, Artist, Track, Match, Album, Genre, Year
    show = plain(cells[0])
    date = plain(cells[1]) if len(cells) > 1 else ""
    artist = artist_display_name(
        plain(cells[2]) if len(cells) > 2 else ""
    )

    original_track = plain(cells[3]) if len(cells) > 3 else ""
    matched_value = plain(cells[4]) if len(cells) > 4 else ""

    if " - " in matched_value:
        _, matched_track = matched_value.split(" - ", 1)
        matched_track = matched_track.strip()
    else:
        matched_track = matched_value

    track = matched_track or original_track
    album = plain(cells[5]) if len(cells) > 5 else ""
    genre = plain(cells[6]) if len(cells) > 6 else ""

    cards.append(f"""
<a class="homepage-match-card" href="/shows/{show_id}.html">
  <img
    src="/episode-art/{show_id}.jpg"
    loading="lazy"
    onerror="this.style.display='none';"
    alt=""
  >

  <div class="homepage-match-body">
    <div class="homepage-match-show">Show {show}</div>
    <div class="homepage-match-track">{track}</div>
    <div class="homepage-match-artist">{artist}</div>
    <div class="homepage-match-meta">{album}</div>
    <div class="homepage-match-footer">
      <span>{date}</span>
      <span>{genre}</span>
    </div>
  </div>
</a>
""")

    if len(cards) >= 8:
        break

if not cards:
    section_body = """
<p class="small">No new WEFUNK matches are currently recorded.</p>
"""
else:
    section_body = f"""
<div class="homepage-match-grid">
{''.join(cards)}
</div>
"""

section = f"""
<div class="card homepage-recent-matches" id="homepageRecentMatches">
  <div class="homepage-section-heading">
    <div>
      <h2>✨ Latest WEFUNK Matches</h2>
      <p class="small">
        The newest tracks connected to your music collection.
      </p>
    </div>

    <a class="homepage-section-link" href="/recent-matches.html">
      View all →
    </a>
  </div>

  {section_body}
</div>
"""

css = """
<style>
.homepage-section-heading{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:18px;
  margin-bottom:18px;
}

.homepage-section-heading h2{
  margin-bottom:4px;
}

.homepage-section-link{
  flex-shrink:0;
  padding:8px 12px;
  border:1px solid #2b2f36;
  border-radius:999px;
  color:#F7931E;
  font-size:13px;
  font-weight:800;
  text-decoration:none;
}

.homepage-section-link:hover{
  border-color:#F7931E;
  background:#F7931E;
  color:#111;
}

.homepage-match-grid{
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:16px;
}

.homepage-match-card{
  display:block;
  overflow:hidden;
  border:1px solid #2b2f36;
  border-radius:17px;
  background:#171a1f;
  color:#f5f5f5;
  text-decoration:none;
  transition:
    transform .18s ease,
    border-color .18s ease,
    box-shadow .18s ease;
}

.homepage-match-card:hover{
  transform:translateY(-3px);
  border-color:#F7931E;
  box-shadow:0 14px 34px rgba(0,0,0,.3);
}

.homepage-match-card img{
  display:block;
  width:100%;
  height:120px;
  object-fit:cover;
  background:#0f1115;
}

.homepage-match-body{
  padding:13px;
}

.homepage-match-show{
  color:#F7931E;
  font-size:12px;
  font-weight:900;
  text-transform:uppercase;
}

.homepage-match-track{
  margin-top:7px;
  font-size:16px;
  font-weight:900;
  line-height:1.25;
}

.homepage-match-artist{
  margin-top:5px;
  font-size:13px;
  font-weight:750;
}

.homepage-match-meta{
  min-height:18px;
  margin-top:5px;
  color:#999;
  font-size:12px;
  line-height:1.35;
}

.homepage-match-footer{
  display:flex;
  justify-content:space-between;
  gap:8px;
  margin-top:11px;
  color:#777;
  font-size:11px;
}

@media(max-width:1050px){
  .homepage-match-grid{
    grid-template-columns:repeat(2,minmax(0,1fr));
  }
}

@media(max-width:600px){
  .homepage-section-heading{
    display:block;
  }

  .homepage-section-link{
    display:inline-block;
    margin-top:10px;
  }

  .homepage-match-grid{
    grid-template-columns:1fr;
  }

  .homepage-match-card{
    display:grid;
    grid-template-columns:110px 1fr;
  }

  .homepage-match-card img{
    width:110px;
    height:110px;
    aspect-ratio:auto;
  }
}
</style>
"""

homepage = homepage.replace(
    "</head>",
    css + "\n</head>",
    1,
)

homepage = homepage.replace(
    '<div class="card">',
    section + '\n<div class="card">',
    1,
)

INDEX.write_text(homepage, encoding="utf-8")

print(f"Added {len(cards)} recent-match cards to homepage")
