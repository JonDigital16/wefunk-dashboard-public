#!/usr/bin/env python3

import os
import re
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

PAGE = SITE / "recommended-albums.html"

if not PAGE.exists():
    raise SystemExit("recommended-albums.html does not exist yet.")

html = PAGE.read_text(encoding="utf-8")

if "recommended-card-grid" in html:
    print("Recommended album cards already present")
    raise SystemExit(0)

rows = re.findall(r"<tr>(.*?)</tr>", html, flags=re.S)

cards = []

for row in rows:
    href = re.search(r"href='(/albums/[^']+\.html)'|href=\"(/albums/[^\"]+\.html)\"", row)
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)

    if not href or len(cells) < 4:
        continue

    url = href.group(1) or href.group(2)
    slug = Path(url).stem

    artist = re.sub(r"<.*?>", "", cells[0]).strip()
    album = re.sub(r"<.*?>", "", cells[1]).strip()
    tracks = re.sub(r"<.*?>", "", cells[2]).strip()
    shows = re.sub(r"<.*?>", "", cells[3]).strip()

    cards.append(f"""
<a class="recommended-card" href="{url}">
  <img src="/covers/{slug}.jpg" loading="lazy" onerror="this.style.display='none';">
  <div class="recommended-card-body">
    <div class="recommended-card-title">{album}</div>
    <div class="recommended-card-artist">{artist}</div>
    <div class="recommended-card-meta">{tracks} tracks gained · {shows} shows improved</div>
  </div>
</a>
""")

css = """
<style>
.recommended-card-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(180px,1fr));
  gap:18px;
  margin-top:22px;
}

.recommended-card{
  display:block;
  background:#171a1f;
  border:1px solid #2b2f36;
  border-radius:18px;
  overflow:hidden;
  text-decoration:none;
  color:#f5f5f5;
  transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}

.recommended-card:hover{
  transform:translateY(-4px);
  box-shadow:0 16px 42px rgba(0,0,0,.38);
  border-color:#F7931E;
}

.recommended-card img{
  width:100%;
  aspect-ratio:1/1;
  object-fit:cover;
  display:block;
  background:#0f1115;
}

.recommended-card-body{
  padding:13px;
}

.recommended-card-title{
  font-weight:900;
  line-height:1.25;
  margin-bottom:5px;
}

.recommended-card-artist{
  color:#F7931E;
  font-weight:700;
  font-size:13px;
  margin-bottom:7px;
}

.recommended-card-meta{
  color:#aaa;
  font-size:12px;
  line-height:1.35;
}

.recommended-view-toggle{
  display:flex;
  gap:10px;
  margin-top:18px;
}

.recommended-view-toggle button{
  padding:8px 13px;
  border-radius:999px;
  border:1px solid #2b2f36;
  background:#171a1f;
  color:#f5f5f5;
  cursor:pointer;
  font-weight:800;
}

.recommended-view-toggle button:hover{
  background:#F7931E;
  color:#111;
}

.recommended-view-toggle button.active{
  background:#F7931E;
  color:#111;
}

#recommendedAlbums{
  display:none;
}

.recommended-view-toggle{
  display:flex;
  gap:10px;
  margin-top:18px;
}

.recommended-view-toggle button{
  padding:8px 13px;
  border-radius:999px;
  border:1px solid #2b2f36;
  background:#171a1f;
  color:#f5f5f5;
  cursor:pointer;
  font-weight:800;
}

.recommended-view-toggle button:hover{
  background:#F7931E;
  color:#111;
}

#recommendedAlbums{
  display:none;
}

@media(max-width:700px){
  .recommended-card-grid{
    grid-template-columns:repeat(auto-fill,minmax(145px,1fr));
    gap:14px;
  }
}
</style>
"""

grid = f"""
<div class="recommended-view-toggle">
  <button onclick="showRecommendedCards()">Cards</button>
  <button onclick="showRecommendedTable()">Table</button>
</div>

<div class="recommended-card-grid" id="recommendedCardGrid">
{''.join(cards)}
</div>
"""


js = """
<script>
function setRecommendedView(view){
  const cards=document.getElementById("recommendedCardGrid");
  const table=document.getElementById("recommendedAlbums");
  const buttons=document.querySelectorAll(".recommended-view-toggle button");

  if(view==="table"){
    if(cards) cards.style.display="none";
    if(table) table.style.display="table";
    if(buttons.length>1){
      buttons[0].classList.remove("active");
      buttons[1].classList.add("active");
    }
    localStorage.setItem("recommendedView","table");
  }else{
    if(cards) cards.style.display="grid";
    if(table) table.style.display="none";
    if(buttons.length>1){
      buttons[0].classList.add("active");
      buttons[1].classList.remove("active");
    }
    localStorage.setItem("recommendedView","cards");
  }
}

function showRecommendedCards(){
  setRecommendedView("cards");
}

function showRecommendedTable(){
  setRecommendedView("table");
}

document.addEventListener("DOMContentLoaded",function(){
  setRecommendedView(localStorage.getItem("recommendedView") || "cards");
});
</script>
"""


html = html.replace("</head>", css + "\n</head>", 1)
html = html.replace("<table id=\"recommendedAlbums\">", grid + "\n<table id=\"recommendedAlbums\">", 1)

html = html.replace("</body>", js + "\n</body>", 1)

PAGE.write_text(html, encoding="utf-8")

print(f"Added {len(cards)} recommended album cards")
