#!/usr/bin/env python3

import os
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

CSS = """
<style>
@media(max-width:800px){
  table{
    display:block;
    width:100%;
    overflow-x:auto;
    white-space:nowrap;
  }

  th, td{
    font-size:13px;
    padding:9px 10px;
  }

  .card{
    padding:14px;
  }

  input{
    font-size:16px;
  }
}
</style>
"""

updated = 0

for path in SITE.rglob("*.html"):
    html = path.read_text(encoding="utf-8")

    if "overflow-x:auto" in html:
        continue

    html = html.replace("</head>", CSS + "\n</head>", 1)
    path.write_text(html, encoding="utf-8")
    updated += 1

print(f"Added mobile table polish to {updated} pages")
