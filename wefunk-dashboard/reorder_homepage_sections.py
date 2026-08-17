#!/usr/bin/env python3

import re
from pathlib import Path

from common import SITE

INDEX = SITE / "index.html"

if not INDEX.exists():
    raise SystemExit(f"Homepage does not exist: {INDEX}")

html = INDEX.read_text(encoding="utf-8")


def find_card(page_html, marker):
    marker_position = page_html.find(marker)

    if marker_position == -1:
        raise ValueError(f"Could not find section marker: {marker}")

    card_start = page_html.rfind("<div", 0, marker_position)

    while card_start != -1:
        opening_end = page_html.find(">", card_start)

        if opening_end == -1:
            break

        opening_tag = page_html[card_start : opening_end + 1]

        if re.search(r'class=["\'][^"\']*\bcard\b', opening_tag):
            break

        card_start = page_html.rfind("<div", 0, card_start)

    if card_start == -1:
        raise ValueError(f"Could not find card containing: {marker}")

    depth = 0

    for match in re.finditer(
        r"<div\b[^>]*>|</div>",
        page_html[card_start:],
        flags=re.IGNORECASE,
    ):
        token = match.group(0).lower()

        if token.startswith("<div"):
            depth += 1
        else:
            depth -= 1

            if depth == 0:
                card_end = card_start + match.end()
                return card_start, card_end

    raise ValueError(f"Could not find card ending for: {marker}")


try:
    snapshot_start, snapshot_end = find_card(
        html,
        "<h2>📻 WEFUNK Snapshot</h2>",
    )
    score_start, score_end = find_card(
        html,
        "<h2>🏆 Collection Score</h2>",
    )
except ValueError as error:
    raise SystemExit(str(error))

snapshot_section = html[snapshot_start:snapshot_end]
score_section = html[score_start:score_end]

# Remove the movable sections from the bottom upward so positions stay valid.
for start, end in sorted(
    [
        (snapshot_start, snapshot_end),
        (score_start, score_end),
    ],
    reverse=True,
):
    html = html[:start] + html[end:]

try:
    _, overview_end = find_card(
        html,
        'id="collectionOverview"',
    )
except ValueError as error:
    raise SystemExit(str(error))

moved_sections = "\n\n" + snapshot_section + "\n\n" + score_section

html = html[:overview_end] + moved_sections + html[overview_end:]

INDEX.write_text(html, encoding="utf-8")

print("Moved WEFUNK Snapshot and Collection Score below Collection Overview")
