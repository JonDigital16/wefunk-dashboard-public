#!/usr/bin/env python3

import re
from pathlib import Path

from common import SITE

INDEX = SITE / "index.html"

if not INDEX.exists():
    raise SystemExit(f"Homepage does not exist: {INDEX}")

html = INDEX.read_text(encoding="utf-8")

marker = "<h2>Reports</h2>"
marker_position = html.find(marker)

if marker_position == -1:
    print("Homepage Reports section already absent")
    raise SystemExit(0)

card_start = html.rfind('<div class="card">', 0, marker_position)

if card_start == -1:
    raise SystemExit("Could not find opening Reports card")

depth = 0
card_end = None

for match in re.finditer(
    r"<div\b[^>]*>|</div>",
    html[card_start:],
    flags=re.IGNORECASE,
):
    token = match.group(0).lower()

    if token.startswith("<div"):
        depth += 1
    else:
        depth -= 1

        if depth == 0:
            card_end = card_start + match.end()
            break

if card_end is None:
    raise SystemExit("Could not find closing Reports card")

html = html[:card_start] + html[card_end:]

INDEX.write_text(html, encoding="utf-8")

print("Removed Reports section from homepage")
