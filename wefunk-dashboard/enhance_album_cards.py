from shared_view_toggle import TOGGLE_JS

#!/usr/bin/env python3

import os
import re
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

ALBUMS = SITE / "albums.html"

if not ALBUMS.exists():
    raise SystemExit("albums.html does not exist yet.")

html = ALBUMS.read_text(encoding="utf-8")

# Only run once
if "album-card-grid" in html:
    print("Album cards already present")
    raise SystemExit(0)

rows = re.findall(r"<tr>(.*?)</tr>", html, flags=re.S)

cards = []

for row in rows:
    href = re.search(r"href='(/albums/[^']+\.html)'|href=\"(/albums/[^\"]+\.html)\"", row)
    img = re.search(r"src='(/covers/[^']+)'|src=\"(/covers/[^\"]+)\"", row)

    cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)

    if not href or len(cells) < 5:
        continue

    url = href.group(1) or href.group(2)
    cover = (img.group(1) or img.group(2)) if img else ""

    artist = re.sub(r"<.*?>", "", cells[0]).strip()
    album = re.sub(r"<.*?>", "", cells[1]).strip()
    genre = re.sub(r"<.*?>", "", cells[2]).strip()
    year = re.sub(r"<.*?>", "", cells[3]).strip()
    tracks = re.sub(r"<.*?>", "", cells[4]).strip()

    cards.append(f"""
<a class="album-card" href="{url}">
  <img src="{cover}" loading="lazy" onerror="this.style.display='none';">
  <div class="album-card-body">
    <div class="album-card-title">{album}</div>
    <div class="album-card-artist">{artist}</div>
    <div class="album-card-meta">{year} · {genre}</div>
    <div class="album-card-count">{tracks} matched tracks</div>
  </div>
</a>
""")

css = """
<style>
.album-card-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(180px,1fr));
  gap:18px;
  margin-top:22px;
}

.album-card{
  display:block;
  background:#171a1f;
  border:1px solid #2b2f36;
  border-radius:18px;
  overflow:hidden;
  text-decoration:none;
  color:#f5f5f5;
  transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}

.album-card:hover{
  transform:translateY(-4px);
  box-shadow:0 16px 42px rgba(0,0,0,.38);
  border-color:#F7931E;
}

.album-card img{
  width:100%;
  aspect-ratio:1/1;
  object-fit:cover;
  display:block;
  background:#0f1115;
}

.album-card-body{
  padding:13px;
}

.album-card-title{
  font-weight:900;
  line-height:1.25;
  margin-bottom:5px;
}

.album-card-artist{
  color:#F7931E;
  font-weight:700;
  font-size:13px;
  margin-bottom:7px;
}

.album-card-meta,
.album-card-count{
  color:#aaa;
  font-size:12px;
  line-height:1.35;
}

.album-view-toggle{
  display:flex;
  gap:10px;
  margin-top:18px;
}

.album-view-toggle button{
  padding:8px 13px;
  border-radius:999px;
  border:1px solid #2b2f36;
  background:#171a1f;
  color:#f5f5f5;
  cursor:pointer;
  font-weight:800;
}

.album-view-toggle button:hover{
  background:#F7931E;
  color:#111;
}

#albumIndex{
  display:none;
}

@media(max-width:700px){
  .album-card-grid{
    grid-template-columns:repeat(auto-fill,minmax(145px,1fr));
    gap:14px;
  }
}
</style>
"""

grid = f"""
<div class="album-view-toggle">
  <button onclick="showAlbumCards()">Cards</button>
  <button onclick="showAlbumTable()">Table</button>
</div>

<div class="album-card-grid" id="albumCardGrid">
{''.join(cards)}
</div>
"""

html = html.replace("</head>", css + "\n</head>", 1)

# Put cards before the table, preserving the table/filter underneath for power use.
html = html.replace("<table id=\"albumIndex\">", grid + "\n<table id=\"albumIndex\">", 1)

ALBUMS.write_text(html, encoding="utf-8")

print(f"Added {len(cards)} album cards")



js = TOGGLE_JS + """
<script>
function showAlbumCards(){
    setCardTableView(
        "albumCardGrid",
        "albumIndex",
        "album-view-toggle",
        "albumView",
        "cards"
    );
}
function showAlbumTable(){
    setCardTableView(
        "albumCardGrid",
        "albumIndex",
        "album-view-toggle",
        "albumView",
        "table"
    );
}
document.addEventListener("DOMContentLoaded",function(){
    initCardTableView(
        "albumCardGrid",
        "albumIndex",
        "album-view-toggle",
        "albumView"
    );
});
</script>
"""


html = html.replace("</body>", js + "\n</body>", 1)


# FINAL TOGGLE WRITE
ALBUMS.write_text(html, encoding="utf-8")
print("Saved card/table toggle JavaScript")
