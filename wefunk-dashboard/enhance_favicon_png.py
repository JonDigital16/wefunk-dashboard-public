#!/usr/bin/env python3

import os
from pathlib import Path
from PIL import Image, ImageDraw

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

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
            [x, base - hh, x + bar_w, base],
            radius=bar_w // 2,
            fill="#F7931E"
        )
        x += bar_w + gap

    img.save(out)

make_icon(32, SITE / "favicon.png")
make_icon(180, SITE / "apple-touch-icon.png")

updated = 0

for path in SITE.rglob("*.html"):
    html = path.read_text(encoding="utf-8")

    if 'apple-touch-icon.png' not in html:
        html = html.replace(
            "</head>",
            '<link rel="icon" href="/favicon.png" type="image/png">\n'
            '<link rel="apple-touch-icon" href="/apple-touch-icon.png">\n'
            '</head>',
            1
        )
        path.write_text(html, encoding="utf-8")
        updated += 1

print(f"Added PNG favicon links to {updated} pages")
