#!/usr/bin/env python3

import os
import re
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))
SHOWS = SITE / "shows"
ART = SITE / "episode-art"

updated = 0

for page in SHOWS.glob("*.html"):
    show_id = page.stem
    art = ART / f"{show_id}.jpg"

    if not art.exists():
        continue

    html = page.read_text(encoding="utf-8")

    if "/episode-art/" in html:
        continue

    block = f"""
<div style="display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap;">
  <div>
    <img src="/episode-art/{show_id}.jpg"
         loading="lazy"
         style="width:240px;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.35);">
  </div>
  <div style="flex:1;min-width:320px;">
"""

    html = html.replace('<div class="card">', '<div class="card">\n' + block, 1)
    html = html.replace('<div class="card">\n<h2>Full Tracklist</h2>', '</div>\n</div>\n<div class="card">\n<h2>Full Tracklist</h2>', 1)

    page.write_text(html, encoding="utf-8")
    updated += 1

print(f"Added episode artwork to {updated} show pages")
