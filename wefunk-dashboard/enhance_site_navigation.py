#!/usr/bin/env python3

import os
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

NAV = """
<div class="site-nav">
  <a href="/">🏠 Home</a>
  <a href="#" onclick="openSearchOverlay(); return false;">🔍 Search <span class="nav-key">/</span></a>
  <a href="/episodes.html">📻 Episodes</a>
  <a href="/albums.html">💿 Albums</a>
  <a href="/genres.html">🧬 Genres</a>
  <a href="/years.html">📅 Years</a>
  <a href="/recent-matches.html">🆕 Recent</a>
</div>
"""

CSS = """
<style>
.site-nav{
  position:sticky;
  top:0;
  z-index:999;
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  align-items:center;
  margin:0 0 18px 0;
  padding:12px 14px;
  background:rgba(17,20,25,.96);
  border:1px solid #2b2f36;
  border-radius:0 0 16px 16px;
  backdrop-filter:blur(10px);
}

.site-nav a{
  color:#f5f5f5;
  text-decoration:none;
  font-weight:700;
  font-size:14px;
  padding:7px 10px;
  border-radius:999px;
  background:#171a1f;
  border:1px solid #2b2f36;
}

.site-nav a:hover{
  background:#F7931E;
  color:#111;
}

@media(max-width:700px){
  .site-nav{
    position:relative;
    gap:8px;
    padding:10px;
  }

  .site-nav a{
    font-size:13px;
    padding:6px 9px;
  }
}
</style>
"""

updated = 0

for path in SITE.rglob("*.html"):
    html = path.read_text(encoding="utf-8")

    if "class=\"site-nav\"" in html:
        continue

    if "</head>" in html:
        html = html.replace("</head>", CSS + "\n</head>", 1)

    if "<body>" in html:
        html = html.replace("<body>", "<body>\n" + NAV, 1)
    else:
        continue

    path.write_text(html, encoding="utf-8")
    updated += 1

print(f"Added navigation to {updated} pages")
