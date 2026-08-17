#!/usr/bin/env python3

import os
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

CSS = """
<style>
.search-overlay{
  display:none;
  position:fixed;
  inset:0;
  z-index:2000;
  background:rgba(0,0,0,.72);
  backdrop-filter:blur(8px);
  padding:8vh 16px;
}

.search-panel{
  position:relative;
  max-width:760px;
  margin:0 auto;
  background:#111419;
  border:1px solid #2b2f36;
  border-radius:20px;
  padding:18px;
  box-shadow:0 20px 80px rgba(0,0,0,.45);
}

.search-close{
  position:absolute;
  right:14px;
  top:10px;
  border:0;
  background:transparent;
  color:#f5f5f5;
  font-size:28px;
  cursor:pointer;
}

.search-panel input{
  width:100%;
  font-size:20px;
  padding:14px 16px;
  border-radius:14px;
}

.search-results{
  margin-top:14px;
  max-height:60vh;
  overflow:auto;
}

.search-result{
  display:block;
  padding:12px 14px;
  border-bottom:1px solid #2b2f36;
  color:#f5f5f5;
  text-decoration:none;
}

.search-result:hover,
.search-result.selected{
  background:#F7931E;
  color:#111;
}

.search-type{
  font-size:12px;
  opacity:.75;
  text-transform:uppercase;
  margin-right:8px;
  color:#F7931E;
  font-weight:800;
}

.search-empty{
  padding:18px;
  color:#aaa;
  text-align:center;
  border:1px dashed #2b2f36;
  border-radius:14px;
}
</style>
"""

JS = """
<div class="search-overlay" id="searchOverlay">
  <div class="search-panel">
    <button class="search-close" onclick="closeSearchOverlay()">×</button>
    <input id="overlaySearchInput" placeholder="Search WEFUNK..." autocomplete="off">
    
<div class="small" style="margin-top:8px;">
↑ ↓ Navigate &nbsp;&nbsp; Enter Open &nbsp;&nbsp; Esc Close &nbsp;&nbsp; / Search
</div>

    <div class="search-results" id="overlaySearchResults"></div>
  </div>
</div>

<script>
let overlaySearchData = [];
let overlaySelectedIndex = -1;
let overlayCurrentHits = [];

fetch('/search-index.json')
  .then(r => r.json())
  .then(j => overlaySearchData = j);

function openSearchOverlay(){
  const overlay = document.getElementById('searchOverlay');
  const input = document.getElementById('overlaySearchInput');
  overlay.style.display = 'block';
  input.value = '';
  document.getElementById('overlaySearchResults').innerHTML = '';
  setTimeout(() => input.focus(), 50);
}

function closeSearchOverlay(){
  document.getElementById('searchOverlay').style.display = 'none';
}

function runOverlaySearch(){
  const q = document.getElementById('overlaySearchInput').value.toLowerCase().trim();
  const box = document.getElementById('overlaySearchResults');

  if(q.length < 2){
    box.innerHTML = '';
    return;
  }

  overlayCurrentHits = overlaySearchData.filter(x =>
    (x.title || '').toLowerCase().includes(q) ||
    (x.type || '').toLowerCase().includes(q)
  ).map(x => {
      const t = (x.title || '').toLowerCase();
      let score = 0;

      if(t === q) score += 1000;
      else if(t.startsWith(q)) score += 500;
      else if(t.includes(q)) score += 250;

      if(x.type === 'command') score += 100;
      if(x.type === 'artist') score += 40;
      if(x.type === 'album') score += 30;
      if(x.type === 'show') score += 20;

      return {...x, score};
  }).sort((a,b) => b.score - a.score)
    .slice(0,50);

  overlaySelectedIndex = overlayCurrentHits.length ? 0 : -1;

  if(!overlayCurrentHits.length){
    box.innerHTML = `<div class="search-empty">No results found. Try artist, album, genre, year, show, or command.</div>`;
    return;
  }

  box.innerHTML = overlayCurrentHits.map((x, i) =>
    `<a class="search-result ${i === overlaySelectedIndex ? 'selected' : ''}" href="${x.url}">
      <span class="search-type">${x.type === 'command' ? '⚡ command' : x.type}</span>${x.title}
    </a>`
  ).join('');
}

document.addEventListener('keydown', function(e){
  const overlay = document.getElementById('searchOverlay');
  const isOpen = overlay && overlay.style.display === 'block';

  if(e.key === '/' && !['INPUT','TEXTAREA'].includes(document.activeElement.tagName)){
    e.preventDefault();
    openSearchOverlay();
    return;
  }

  if(e.key === 'Escape'){
    closeSearchOverlay();
    return;
  }

  if(!isOpen || !overlayCurrentHits.length){
    return;
  }

  if(e.key === 'ArrowDown'){
    e.preventDefault();
    overlaySelectedIndex = (overlaySelectedIndex + 1) % overlayCurrentHits.length;
  }

  if(e.key === 'ArrowUp'){
    e.preventDefault();
    overlaySelectedIndex = (overlaySelectedIndex - 1 + overlayCurrentHits.length) % overlayCurrentHits.length;
  }

  if(e.key === 'Enter' && overlaySelectedIndex >= 0){
    e.preventDefault();
    window.location.href = overlayCurrentHits[overlaySelectedIndex].url;
    return;
  }

  if(e.key === 'ArrowDown' || e.key === 'ArrowUp'){
    document.querySelectorAll('.search-result').forEach((el, i) => {
      el.classList.toggle('selected', i === overlaySelectedIndex);
      if(i === overlaySelectedIndex) el.scrollIntoView({block:'nearest'});
    });
  }
});

document.addEventListener('input', function(e){
  if(e.target && e.target.id === 'overlaySearchInput'){
    runOverlaySearch();
  }
});

document.addEventListener('click', function(e){
  if(e.target && e.target.id === 'searchOverlay'){
    closeSearchOverlay();
  }
});
</script>
"""

updated = 0

for path in SITE.rglob("*.html"):
    html = path.read_text(encoding="utf-8")

    if "searchOverlay" in html:
        continue

    if "</head>" in html:
        html = html.replace("</head>", CSS + "\n</head>", 1)

    if "</body>" in html:
        html = html.replace("</body>", JS + "\n</body>", 1)

    path.write_text(html, encoding="utf-8")
    updated += 1

print(f"Added search overlay to {updated} pages")
