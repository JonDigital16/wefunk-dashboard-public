#!/usr/bin/env python3

import os
from pathlib import Path
from PIL import Image, ImageDraw

SITE = Path(
    os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site"))
)

# Create favicon files
favicon_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#111419"/>
  <rect x="10" y="38" width="5" height="12" rx="2.5" fill="#F7931E"/>
  <rect x="18" y="30" width="5" height="20" rx="2.5" fill="#F7931E"/>
  <rect x="26" y="22" width="5" height="28" rx="2.5" fill="#F7931E"/>
  <rect x="34" y="14" width="5" height="36" rx="2.5" fill="#F7931E"/>
  <rect x="42" y="26" width="5" height="24" rx="2.5" fill="#F7931E"/>
  <rect x="50" y="34" width="5" height="16" rx="2.5" fill="#F7931E"/>
</svg>
"""

(SITE / "favicon.svg").write_text(favicon_svg, encoding="utf-8")


def make_icon(size, out):
    img = Image.new("RGB", (size, size), "#111419")
    d = ImageDraw.Draw(img)

    pad = size // 6
    bar_w = size // 12
    gap = size // 18
    heights = [12, 22, 32, 42, 28, 18]
    scale = size / 64

    x = pad
    base = size - pad

    for h in heights:
        hh = int(h * scale)
        d.rounded_rectangle(
            [x, base - hh, x + bar_w, base], radius=bar_w // 2, fill="#F7931E"
        )
        x += bar_w + gap

    img.save(out)


make_icon(32, SITE / "favicon.png")
make_icon(180, SITE / "apple-touch-icon.png")


HEAD = """
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.png" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">

<style>
.site-nav{position:sticky;top:0;z-index:999;display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 18px;padding:12px 14px;background:rgba(17,20,25,.96);border:1px solid #2b2f36;border-radius:0 0 16px 16px;backdrop-filter:blur(10px)}
.site-nav a{color:#f5f5f5;text-decoration:none;font-weight:700;font-size:14px;padding:7px 10px;border-radius:999px;background:#171a1f;border:1px solid #2b2f36}
.site-nav a:hover{background:#F7931E;color:#111}

.nav-dropdown{
  position:relative;
  padding-bottom:8px;
  margin-bottom:-8px;
}

.nav-dropdown-toggle{
  display:block;
  appearance:none;
  cursor:pointer;
  color:#f5f5f5;
  font-family:inherit;
  font-weight:700;
  font-size:14px;
  padding:7px 10px;
  border:1px solid #2b2f36;
  border-radius:999px;
  background:#171a1f;
}

.nav-dropdown-toggle:hover,
.nav-dropdown-toggle[aria-expanded="true"]{
  border-color:#F7931E;
  background:#F7931E;
  color:#111;
}

.nav-dropdown-arrow{
  display:inline-block;
  margin-left:3px;
  transition:transform .18s ease;
}

.nav-dropdown-toggle[aria-expanded="true"] .nav-dropdown-arrow{
  transform:rotate(180deg);
}

.nav-dropdown-menu{
  display:none;
  position:absolute;
  top:100%;
  right:0;
  z-index:1200;
  min-width:280px;
  max-height:min(70vh,620px);
  overflow-y:auto;
  padding:8px;
  border:1px solid #2b2f36;
  border-radius:14px;
  background:#111419;
  box-shadow:0 18px 50px rgba(0,0,0,.45);
  overscroll-behavior:contain;
}

.nav-dropdown.is-open .nav-dropdown-menu{
  display:grid;
  gap:4px;
}

@media(hover:hover) and (pointer:fine){
  .nav-dropdown:hover .nav-dropdown-menu,
  .nav-dropdown-menu:hover{
    display:grid;
    gap:4px;
  }
}

.site-nav .nav-dropdown-menu a{
  display:block;
  width:100%;
  box-sizing:border-box;
  padding:10px 12px;
  border:0;
  border-radius:9px;
  background:transparent;
  font-size:13px;
  white-space:normal;
}

.site-nav .nav-dropdown-menu a:hover,
.site-nav .nav-dropdown-menu a:focus{
  background:#F7931E;
  color:#111;
}

@media(max-width:800px){
  .nav-dropdown-menu{
    position:fixed;
    left:12px;
    right:12px;
    width:auto;
    min-width:0;
    max-height:calc(100dvh - 180px);
    padding:10px;
  }

  .site-nav .nav-dropdown-menu a{
    padding:12px 14px;
    font-size:15px;
  }
}

.nav-key{display:inline-block;margin-left:5px;padding:1px 6px;border-radius:6px;background:#2b2f36;color:#f5f5f5;font-size:12px}

img[src^="/covers/"],img[src^="/episode-art/"]{transition:transform .18s ease,box-shadow .18s ease,opacity .18s ease}
img[src^="/covers/"]:hover,img[src^="/episode-art/"]:hover{transform:scale(1.04);box-shadow:0 10px 28px rgba(0,0,0,.45)}
.report-card{transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}
.report-card:hover{transform:translateY(-2px);box-shadow:0 12px 32px rgba(0,0,0,.32);border-color:#F7931E}

.search-overlay{display:none;position:fixed;inset:0;z-index:2000;background:rgba(0,0,0,.72);backdrop-filter:blur(8px);padding:8vh 16px}
.search-panel{position:relative;max-width:760px;margin:0 auto;background:#111419;border:1px solid #2b2f36;border-radius:20px;padding:18px;box-shadow:0 20px 80px rgba(0,0,0,.45)}
.search-panel input{width:100%;font-size:20px;padding:14px 16px;border-radius:14px}
.search-close{position:absolute;right:14px;top:10px;border:0;background:transparent;color:#f5f5f5;font-size:28px;cursor:pointer}
.search-results{margin-top:14px;max-height:60vh;overflow:auto}
.search-result{display:block;padding:12px 14px;border-bottom:1px solid #2b2f36;color:#f5f5f5;text-decoration:none}
.search-result:hover,.search-result.selected{background:#F7931E;color:#111}
.search-type{font-size:12px;opacity:.75;text-transform:uppercase;margin-right:8px;color:#F7931E;font-weight:800}
.search-empty{padding:18px;color:#aaa;text-align:center;border:1px dashed #2b2f36;border-radius:14px}

.back-to-top{position:fixed;right:18px;bottom:18px;z-index:1800;display:none;width:46px;height:46px;border-radius:999px;border:1px solid #2b2f36;background:#F7931E;color:#111;font-size:22px;font-weight:900;cursor:pointer;box-shadow:0 10px 30px rgba(0,0,0,.35)}

.site-footer{margin:34px 0 14px;padding:18px;text-align:center;color:#999;font-size:13px}
.site-footer a{color:#F7931E;text-decoration:none;margin:0 8px}

body{animation:pageFadeIn .18s ease-out}
@keyframes pageFadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}

@media(max-width:800px){
  table{display:block;width:100%;overflow-x:auto;white-space:nowrap}
  th,td{font-size:13px;padding:9px 10px}
  .card{padding:14px}
  input{font-size:16px}
}
</style>
"""

BODY_TOP = """
<div class="site-nav">
  <a href="/">🏠 Home</a>
  <a href="#" onclick="openSearchOverlay(); return false;">🔍 Search</a>
  <a href="/episodes.html">📻 Episodes</a>
  <a href="/albums.html">💿 Albums</a>
  <a href="/artists.html">🎤 Artists</a>
  <a href="/genres.html">🧬 Genres</a>
  <a href="/years.html">📅 Years</a>
  <a href="/recent-matches.html">🆕 Recent</a>
  <a href="/listening.html">🎧 Listening</a>
  <a href="/status.html">🟢 Status</a>

  <div class="nav-dropdown">
    <button
      class="nav-dropdown-toggle"
      type="button"
      aria-expanded="false"
      aria-haspopup="true"
      onclick="toggleInsightsMenu(event)"
    >
      ⭐ Insights <span class="nav-dropdown-arrow">▾</span>
    </button>

    <div class="nav-dropdown-menu">
      <a href="/missing.html">🎯 Missing Tracks</a>
      <a href="/shopping.html">🛒 Smart Shopping List</a>
      <a href="/dna.html">🎧 WEFUNK DNA</a>
      <a href="/episodes.html">📻 All Episodes Archive</a>
      <a href="/recent-matches.html">🆕 Recent Matches</a>
      <a href="/best-matching.html">🏆 Best Matching Shows</a>
      <a href="/almost-complete.html">✅ Almost Complete Shows</a>
      <a href="/recommended-albums.html">💿 Recommended Albums</a>
      <a href="/albums.html">📀 Album Index</a>
      <a href="/genres.html">🧬 Genre Index</a>
      <a href="/years.html">📅 Year Index</a>
      <a href="/search.html">🔎 Search</a>
      <a href="/top-missing-artists.html">🎤 Top Missing Artists</a>
    </div>
  </div>
</div>
"""

BODY_END = """
<button class="back-to-top" id="backToTop" onclick="window.scrollTo({top:0,behavior:'smooth'})">↑</button>

<div class="search-overlay" id="searchOverlay">
  <div class="search-panel">
    <button class="search-close" onclick="closeSearchOverlay()">×</button>
    <input id="overlaySearchInput" placeholder="Search WEFUNK..." autocomplete="off">
    <div class="small" style="margin-top:8px;">↑ ↓ Navigate &nbsp;&nbsp; Enter Open &nbsp;&nbsp; Esc Close &nbsp;&nbsp; / Search</div>
    <div class="search-results" id="overlaySearchResults"></div>
  </div>
</div>

<div class="site-footer">
  WEFUNK Dashboard ·
  <a href="/">Home</a>
  <a href="/search.html">Search</a>
  <a href="/episodes.html">Episodes</a>
  <a href="/albums.html">Albums</a>
  <a href="/artists.html">Artists</a>
  <a href="/genres.html">Genres</a>
  <a href="/years.html">Years</a>
</div>

<script>
function closeInsightsMenu(){
  const dropdown=document.querySelector('.nav-dropdown');
  const toggle=document.querySelector('.nav-dropdown-toggle');
  const menu=document.querySelector('.nav-dropdown-menu');

  if(dropdown) dropdown.classList.remove('is-open');
  if(toggle) toggle.setAttribute('aria-expanded','false');

  if(menu){
    menu.style.top='';
  }
}

function positionInsightsMenu(){
  const toggle=document.querySelector('.nav-dropdown-toggle');
  const menu=document.querySelector('.nav-dropdown-menu');

  if(!toggle || !menu || window.innerWidth>800) return;

  const rect=toggle.getBoundingClientRect();
  const availableBelow=window.innerHeight-rect.bottom-20;
  const availableAbove=rect.top-20;

  if(availableBelow>=220 || availableBelow>=availableAbove){
    menu.style.top=Math.round(rect.bottom+8)+'px';
    menu.style.maxHeight=Math.max(180,availableBelow)+'px';
  }else{
    const height=Math.min(availableAbove,menu.scrollHeight);
    menu.style.top=Math.max(12,Math.round(rect.top-height-8))+'px';
    menu.style.maxHeight=Math.max(180,availableAbove)+'px';
  }
}

function toggleInsightsMenu(event){
  event.preventDefault();
  event.stopPropagation();

  const dropdown=document.querySelector('.nav-dropdown');
  const toggle=document.querySelector('.nav-dropdown-toggle');

  if(!dropdown || !toggle) return;

  const opening=!dropdown.classList.contains('is-open');

  closeInsightsMenu();

  if(opening){
    dropdown.classList.add('is-open');
    toggle.setAttribute('aria-expanded','true');
    requestAnimationFrame(positionInsightsMenu);
  }
}

document.addEventListener('click',function(event){
  const dropdown=document.querySelector('.nav-dropdown');

  if(
    dropdown &&
    dropdown.classList.contains('is-open') &&
    !dropdown.contains(event.target)
  ){
    closeInsightsMenu();
  }
});

window.addEventListener('resize',function(){
  const dropdown=document.querySelector('.nav-dropdown');

  if(dropdown && dropdown.classList.contains('is-open')){
    positionInsightsMenu();
  }
});

let overlaySearchData=[];
let overlaySelectedIndex=-1;
let overlayCurrentHits=[];

fetch('/search-index.json').then(r=>r.json()).then(j=>overlaySearchData=j);

function openSearchOverlay(){
  const overlay=document.getElementById('searchOverlay');
  const input=document.getElementById('overlaySearchInput');
  overlay.style.display='block';
  input.value='';
  document.getElementById('overlaySearchResults').innerHTML='';
  setTimeout(()=>input.focus(),50);
}

function closeSearchOverlay(){
  document.getElementById('searchOverlay').style.display='none';
}

function runOverlaySearch(){
  const q=document.getElementById('overlaySearchInput').value.toLowerCase().trim();
  const box=document.getElementById('overlaySearchResults');

  if(q.length<2){box.innerHTML='';return;}

  overlayCurrentHits=overlaySearchData.filter(x =>
    (x.title || '').toLowerCase().includes(q) ||
    (x.type || '').toLowerCase().includes(q)
  ).map(x=>{
    const t=(x.title || '').toLowerCase();
    let score=0;
    if(t===q) score+=1000;
    else if(t.startsWith(q)) score+=500;
    else if(t.includes(q)) score+=250;
    if(x.type==='command') score+=100;
    if(x.type==='artist') score+=40;
    if(x.type==='album') score+=30;
    if(x.type==='show') score+=20;
    return {...x,score};
  }).sort((a,b)=>b.score-a.score).slice(0,50);

  overlaySelectedIndex=overlayCurrentHits.length?0:-1;

  if(!overlayCurrentHits.length){
    box.innerHTML='<div class="search-empty">No results found. Try artist, album, genre, year, show, or command.</div>';
    return;
  }

  box.innerHTML=overlayCurrentHits.map((x,i)=>
    `<a class="search-result ${i===overlaySelectedIndex?'selected':''}" href="${x.url}">
      <span class="search-type">${x.type==='command'?'⚡ command':x.type}</span>${x.title}
    </a>`
  ).join('');
}

document.addEventListener('keydown',function(e){
  const overlay=document.getElementById('searchOverlay');
  const isOpen=overlay && overlay.style.display==='block';

  if(e.key==='/' && !['INPUT','TEXTAREA'].includes(document.activeElement.tagName)){
    e.preventDefault();openSearchOverlay();return;
  }

  if(e.key==='Escape'){
    closeSearchOverlay();
    closeInsightsMenu();
    return;
  }

  if(!isOpen || !overlayCurrentHits.length) return;

  if(e.key==='ArrowDown'){
    e.preventDefault();
    overlaySelectedIndex=(overlaySelectedIndex+1)%overlayCurrentHits.length;
  }

  if(e.key==='ArrowUp'){
    e.preventDefault();
    overlaySelectedIndex=(overlaySelectedIndex-1+overlayCurrentHits.length)%overlayCurrentHits.length;
  }

  if(e.key==='Enter' && overlaySelectedIndex>=0){
    e.preventDefault();
    window.location.href=overlayCurrentHits[overlaySelectedIndex].url;
    return;
  }

  if(e.key==='ArrowDown' || e.key==='ArrowUp'){
    document.querySelectorAll('.search-result').forEach((el,i)=>{
      el.classList.toggle('selected',i===overlaySelectedIndex);
      if(i===overlaySelectedIndex) el.scrollIntoView({block:'nearest'});
    });
  }
});

document.addEventListener('input',function(e){
  if(e.target && e.target.id==='overlaySearchInput') runOverlaySearch();
});

window.addEventListener('scroll',function(){
  const btn=document.getElementById('backToTop');
  if(btn) btn.style.display=window.scrollY>600?'block':'none';
});
</script>
"""

updated = 0

for path in SITE.rglob("*.html"):
    html = path.read_text(encoding="utf-8")

    if "site-nav" in html and "searchOverlay" in html and "site-footer" in html:
        continue

    html = html.replace("</head>", HEAD + "\n</head>", 1)
    html = html.replace("<body>", "<body>\n" + BODY_TOP, 1)
    html = html.replace("</body>", BODY_END + "\n</body>", 1)

    path.write_text(html, encoding="utf-8")
    updated += 1

print(f"Applied global UI to {updated} pages")
