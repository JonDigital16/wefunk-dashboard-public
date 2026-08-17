#!/usr/bin/env python3

import os
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

CSS = """
<style>
body{
  animation:pageFadeIn .18s ease-out;
}

@keyframes pageFadeIn{
  from{
    opacity:0;
    transform:translateY(4px);
  }
  to{
    opacity:1;
    transform:translateY(0);
  }
}

@media (prefers-reduced-motion: reduce){
  body{
    animation:none;
  }
}
</style>
"""

updated = 0

for path in SITE.rglob("*.html"):
    html = path.read_text(encoding="utf-8")

    if "pageFadeIn" in html:
        continue

    html = html.replace("</head>", CSS + "\n</head>", 1)
    path.write_text(html, encoding="utf-8")
    updated += 1

print(f"Added page transitions to {updated} pages")
