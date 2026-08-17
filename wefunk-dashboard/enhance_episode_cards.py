from shared_view_toggle import TOGGLE_JS

#!/usr/bin/env python3

import os
import re
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))
PAGE = SITE / "episodes.html"

if not PAGE.exists():
    raise SystemExit("episodes.html does not exist yet.")

html = PAGE.read_text(encoding="utf-8")

if "episode-card-grid" in html:
    print("Episode cards already present")
    raise SystemExit(0)

rows = re.findall(r"<tr>(.*?)</tr>", html, flags=re.S)
cards = []

for row in rows:
    href = re.search(r"href='(/shows/[^']+\.html)'|href=\"(/shows/[^\"]+\.html)\"", row)
    img = re.search(r"src='(/episode-art/[^']+)'|src=\"(/episode-art/[^\"]+)\"", row)
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)

    if not href or len(cells) < 6:
        continue

    url = href.group(1) or href.group(2)
    cover = (img.group(1) or img.group(2)) if img else ""
    show = re.sub(r"<.*?>", "", cells[0]).strip()
    date = re.sub(r"<.*?>", "", cells[1]).strip()
    djs = re.sub(r"<.*?>", "", cells[2]).strip()
    plays = re.sub(r"<.*?>", "", cells[3]).strip()
    matched = re.sub(r"<.*?>", "", cells[4]).strip()
    pct = re.sub(r"<.*?>", "", cells[5]).strip()

    cards.append(f"""
<a class="episode-card" href="{url}">
  <img src="{cover}" loading="lazy" onerror="this.style.display='none';">
  <div class="episode-card-body">
    <div class="episode-card-title">Show {show}</div>
    <div class="episode-card-meta">{date}</div>
    <div class="episode-card-djs">{djs}</div>
    <div class="episode-card-stats">{pct} matched · {matched} tracks · {plays} plays</div>
  </div>
</a>
""")

css = """
<style>
.episode-card-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
  gap:18px;
  margin-top:22px;
}

.episode-card{
  display:block;
  background:#171a1f;
  border:1px solid #2b2f36;
  border-radius:18px;
  overflow:hidden;
  text-decoration:none;
  color:#f5f5f5;
  transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}

.episode-card:hover{
  transform:translateY(-4px);
  box-shadow:0 16px 42px rgba(0,0,0,.38);
  border-color:#F7931E;
}

.episode-card img{
  width:100%;
  aspect-ratio:1/1;
  object-fit:cover;
  display:block;
  background:#0f1115;
}

.episode-card-body{
  padding:13px;
}

.episode-card-title{
  font-weight:900;
  margin-bottom:5px;
}

.episode-card-meta,
.episode-card-djs,
.episode-card-stats{
  color:#aaa;
  font-size:12px;
  line-height:1.4;
}
.episode-view-toggle{
  display:flex;
  gap:10px;
  margin-top:18px;
}

.episode-view-toggle button{
  padding:8px 13px;
  border-radius:999px;
  border:1px solid #2b2f36;
  background:#171a1f;
  color:#f5f5f5;
  cursor:pointer;
  font-weight:800;
}

.episode-view-toggle button:hover{
  background:#F7931E;
  color:#111;
}

#episodesArchive{
  display:none;
}

</style>
"""

grid = f"""
<div class="episode-view-toggle">
  <button onclick="showEpisodeCards()">Cards</button>
  <button onclick="showEpisodeTable()">Table</button>
</div>

<div class="episode-card-grid" id="episodeCardGrid">
{''.join(cards)}
</div>
"""

html = html.replace("</head>", css + "\n</head>", 1)
html = html.replace("<table id=\"episodesArchive\">", grid + "\n<table id=\"episodesArchive\">", 1)

PAGE.write_text(html, encoding="utf-8")

print(f"Added {len(cards)} episode cards")



js = TOGGLE_JS + """
<script>
function showEpisodeCards(){
    setCardTableView(
        "episodeCardGrid",
        "episodesArchive",
        "episode-view-toggle",
        "episodeView",
        "cards"
    );
}
function showEpisodeTable(){
    setCardTableView(
        "episodeCardGrid",
        "episodesArchive",
        "episode-view-toggle",
        "episodeView",
        "table"
    );
}
document.addEventListener("DOMContentLoaded",function(){
    initCardTableView(
        "episodeCardGrid",
        "episodesArchive",
        "episode-view-toggle",
        "episodeView"
    );
});
</script>
"""


html = html.replace("</body>", js + "\n</body>", 1)


# FINAL TOGGLE WRITE
PAGE.write_text(html, encoding="utf-8")
print("Saved card/table toggle JavaScript")
