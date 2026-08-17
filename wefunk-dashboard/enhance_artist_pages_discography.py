#!/usr/bin/env python3

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, artist_slugify, esc, slugify
from data import owned_tracks_enriched

artists = defaultdict(lambda: defaultdict(int))

for r in owned_tracks_enriched:
    artist = (r.get("artist") or "").strip()
    album = (r.get("matched_album") or "").strip()
    album_slug = (r.get("matched_album_slug") or "").strip()

    if artist and album:
        artists[artist_slugify(artist)][(album, album_slug)] += 1

updated = 0

for artist_slug, albums in artists.items():
    page_path = SITE / "artists" / f"{artist_slug}.html"

    if not page_path.exists():
        continue

    html = page_path.read_text(encoding="utf-8")

    if "Albums in Your Library" in html:
        continue

    rows = "".join(
        f"<tr>"
        f"<td><a href='/albums/{esc(album_slug)}.html'>{esc(album)}</a></td>"
        f"<td>{count}</td>"
        f"</tr>"
        for (album, album_slug), count in sorted(
            albums.items(),
            key=lambda x: (-x[1], x[0][0].lower())
        )
    )

    card = f"""
<div class="card">
<h2>Albums in Your Library</h2>
<p class="small">Albums connected to this artist through matched WEFUNK tracks.</p>

<table>
<thead>
<tr>
<th>Album</th>
<th>Matched Tracks</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</div>
"""

    html = html.replace("</body>", card + "\n</body>")
    page_path.write_text(html, encoding="utf-8")
    updated += 1

print(f"Updated {updated} artist pages with discography sections")
