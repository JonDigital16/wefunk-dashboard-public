#!/usr/bin/env python3

import os
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

favicon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#111419"/>
  <rect x="10" y="38" width="5" height="12" rx="2.5" fill="#F7931E"/>
  <rect x="18" y="30" width="5" height="20" rx="2.5" fill="#F7931E"/>
  <rect x="26" y="22" width="5" height="28" rx="2.5" fill="#F7931E"/>
  <rect x="34" y="14" width="5" height="36" rx="2.5" fill="#F7931E"/>
  <rect x="42" y="26" width="5" height="24" rx="2.5" fill="#F7931E"/>
  <rect x="50" y="34" width="5" height="16" rx="2.5" fill="#F7931E"/>
</svg>
"""

(SITE / "favicon.svg").write_text(favicon, encoding="utf-8")

updated = 0

for path in SITE.rglob("*.html"):
    html = path.read_text(encoding="utf-8")

    if 'rel="icon"' not in html:
        html = html.replace(
            "</head>",
            '<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n</head>',
            1
        )
        path.write_text(html, encoding="utf-8")
        updated += 1

print(f"Added favicon to {updated} pages")
