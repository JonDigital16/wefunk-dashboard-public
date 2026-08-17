#!/usr/bin/env python3

import os
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

CSS = """
<style>
.site-footer{
  margin:34px 0 14px;
  padding:18px;
  text-align:center;
  color:#999;
  font-size:13px;
}

.site-footer a{
  color:#F7931E;
  text-decoration:none;
  margin:0 8px;
}

.site-footer a:hover{
  text-decoration:underline;
}
</style>
"""

FOOTER = """
<div class="site-footer">
  WEFUNK Dashboard ·
  <a href="/">Home</a>
  <a href="/search.html">Search</a>
  <a href="/episodes.html">Episodes</a>
  <a href="/albums.html">Albums</a>
  <a href="/genres.html">Genres</a>
  <a href="/years.html">Years</a>
</div>
"""

updated = 0

for path in SITE.rglob("*.html"):
    html = path.read_text(encoding="utf-8")

    if "class=\"site-footer\"" in html:
        continue

    html = html.replace("</head>", CSS + "\n</head>", 1)
    html = html.replace("</body>", FOOTER + "\n</body>", 1)

    path.write_text(html, encoding="utf-8")
    updated += 1

print(f"Added footer to {updated} pages")
