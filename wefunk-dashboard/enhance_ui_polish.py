#!/usr/bin/env python3

import os
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

CSS = """
<style>
img[src^="/covers/"],
img[src^="/episode-art/"]{
  transition:transform .18s ease, box-shadow .18s ease, opacity .18s ease;
}

img[src^="/covers/"]:hover,
img[src^="/episode-art/"]:hover{
  transform:scale(1.04);
  box-shadow:0 10px 28px rgba(0,0,0,.45);
}

.report-card{
  transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}

.report-card:hover{
  transform:translateY(-2px);
  box-shadow:0 12px 32px rgba(0,0,0,.32);
  border-color:#F7931E;
}

.card{
  transition:border-color .18s ease, box-shadow .18s ease;
}

.card:hover{
  border-color:#343a45;
}
</style>
"""

updated = 0

for path in SITE.rglob("*.html"):
    html = path.read_text(encoding="utf-8")

    if "report-card:hover" in html:
        continue

    if "</head>" in html:
        html = html.replace("</head>", CSS + "\n</head>", 1)
        path.write_text(html, encoding="utf-8")
        updated += 1

print(f"Added UI polish to {updated} pages")
