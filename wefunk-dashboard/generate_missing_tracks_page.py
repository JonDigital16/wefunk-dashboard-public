#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from collections import defaultdict
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, artist_slugify, esc
from data import missing_tracks_engine, missing_tracks

TEMPLATE = SITE / "missing.html"
OUT = SITE / "missing.html"

if not TEMPLATE.exists():
    raise SystemExit(
        "missing.html does not exist yet. "
        "Run generate_dashboard.py first."
    )

template = TEMPLATE.read_text(
    encoding="utf-8"
)

rows_source = (
    missing_tracks_engine
    or missing_tracks
)

ARTIST_IMAGES = SITE / "artist-images"

ARTIST_ALIASES_FILE = (
    Path(__file__).parent
    / "artist_asset_aliases.json"
)

artist_asset_aliases = {}

if ARTIST_ALIASES_FILE.exists():
    try:
        loaded = json.loads(
            ARTIST_ALIASES_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(loaded, dict):
            artist_asset_aliases = {
                str(alias): str(canonical)
                for alias, canonical in loaded.items()
                if alias and canonical
            }

    except (
        OSError,
        json.JSONDecodeError,
    ):
        artist_asset_aliases = {}


def pick(row, names):
    for name in names:
        if name in row and row[name]:
            return row[name]

    return ""


def display_name(value):
    value = " ".join(
        str(value or "").split()
    )

    if not value:
        return ""

    return value.title()


groups = defaultdict(list)

for row in rows_source:
    artist = pick(
        row,
        [
            "artist",
            "wf_artist",
        ],
    ).strip()

    track = pick(
        row,
        [
            "track",
            "wf_track",
            "title",
        ],
    ).strip()

    show = pick(
        row,
        [
            "show_id",
            "show",
        ],
    ).strip()

    if not artist and not track:
        continue

    key = (
        artist.lower(),
        track.lower(),
    )

    groups[key].append({
        "artist": artist,
        "track": track,
        "show": show,
    })


ranked_groups = sorted(
    groups.values(),
    key=len,
    reverse=True,
)

missing_rows = []
missing_targets = []

for items in ranked_groups:
    first = items[0]

    artist = first["artist"]
    track = first["track"]

    artist_slug = artist_slugify(
        artist
    )

    show_links = " ".join(
        f"<a href='/shows/{esc(x['show'])}.html'>"
        f"{esc(x['show'])}"
        f"</a>"
        for x in items[:20]
        if x["show"]
    )

    q = quote_plus(
        f"{artist} {track}"
    )

    missing_targets.append({
        "artist": artist,
        "track": track,
        "artist_slug": artist_slug,
        "show_count": len(items),
        "query": q,
    })

    if len(items) >= 10:
        impact = "high"
    elif len(items) >= 5:
        impact = "medium"
    else:
        impact = "normal"

    missing_rows.append(
        f"<tr data-impact='{impact}'>"

        f"<td>"
        f"<a class='missing-artist-link' "
        f"href='/artists/{esc(artist_slug)}.html'>"
        f"{esc(display_name(artist))}"
        f"</a>"
        f"</td>"

        f"<td class='missing-track'>"
        f"{esc(display_name(track))}"
        f"</td>"

        f"<td data-sort='{len(items)}'>"
        f"<span class='missing-impact {impact}'>"
        f"{len(items)}"
        f"</span>"
        f"</td>"

        f"<td>"
        f"<div class='missing-show-links'>"
        f"{show_links}"
        f"</div>"
        f"</td>"

        f"<td>"
        f"<div class='missing-search-links'>"

        f"<a href='https://www.discogs.com/search/"
        f"?q={q}&type=all'>Discogs</a>"

        f"<a href='https://www.youtube.com/results"
        f"?search_query={q}'>YouTube</a>"

        f"<a href='https://bandcamp.com/search"
        f"?q={q}'>Bandcamp</a>"

        f"</div>"
        f"</td>"

        f"</tr>"
    )


top_cards = []

for target in missing_targets[:12]:
    artist = target["artist"]
    track = target["track"]
    slug = target["artist_slug"]
    show_count = target["show_count"]
    q = target["query"]

    canonical_slug = (
        artist_asset_aliases.get(
            slug,
            slug,
        )
    )

    own_image = (
        ARTIST_IMAGES
        / f"{slug}.jpg"
    )

    canonical_image = (
        ARTIST_IMAGES
        / f"{canonical_slug}.jpg"
    )

    if own_image.exists():
        image_slug = slug
    elif canonical_image.exists():
        image_slug = canonical_slug
    else:
        image_slug = ""

    artist_display = display_name(
        artist
    )

    track_display = display_name(
        track
    )

    if image_slug:
        image_path = (
            ARTIST_IMAGES
            / f"{image_slug}.jpg"
        )

        version = int(
            image_path.stat().st_mtime
        )

        image_html = (
            f"<img "
            f"src='/artist-images/"
            f"{esc(image_slug)}.jpg?v={version}' "
            f"alt='{esc(artist_display)}' "
            f"loading='lazy'>"
        )

    else:
        initial = (
            artist_display[:1].upper()
            if artist_display
            else "?"
        )

        image_html = (
            f"<div class='missing-target-placeholder'>"
            f"{esc(initial)}"
            f"</div>"
        )

    top_cards.append(
        f"<article class='missing-target-card'>"

        f"<a class='missing-target-image' "
        f"href='/artists/{esc(slug)}.html'>"
        f"{image_html}"
        f"</a>"

        f"<div class='missing-target-body'>"

        f"<div class='missing-target-impact'>"
        f"🔥 Appears in {show_count} shows"
        f"</div>"

        f"<a class='missing-target-artist' "
        f"href='/artists/{esc(slug)}.html'>"
        f"{esc(artist_display)}"
        f"</a>"

        f"<div class='missing-target-track'>"
        f"{esc(track_display)}"
        f"</div>"

        f"<div class='missing-target-actions'>"

        f"<a href='https://www.discogs.com/search/"
        f"?q={q}&type=all'>Discogs</a>"

        f"<a href='https://www.youtube.com/results"
        f"?search_query={q}'>YouTube</a>"

        f"<a href='https://bandcamp.com/search"
        f"?q={q}'>Bandcamp</a>"

        f"</div>"
        f"</div>"
        f"</article>"
    )


top_1000 = missing_targets[:1000]

top_1000_artists = len({
    target["artist"].casefold()
    for target in top_1000
    if target["artist"]
})

highest_impact = max(
    (
        target["show_count"]
        for target in missing_targets
    ),
    default=0,
)


missing_card = f"""
<style>
.missing-page {{
  width:
    min(
      1800px,
      calc(100vw - 48px)
    ) !important;

  max-width: none !important;

  margin-left: auto !important;
  margin-right: auto !important;

  box-sizing: border-box;
}}

.missing-hero {{
  margin-bottom: 24px;
}}

.missing-back {{
  display: inline-block;
  margin-bottom: 16px;
  font-size: 13px;
}}

.missing-title-row h2 {{
  margin: 0 0 6px;
  font-size: 28px;
}}

.missing-subtitle {{
  margin: 0;
  color: #aaa;
  line-height: 1.5;
}}

.missing-stats {{
  display: grid;
  grid-template-columns:
    repeat(3, 1fr);
  gap: 12px;
  margin-top: 20px;
}}

.missing-stat {{
  border:
    1px solid #2b2f36;

  border-radius: 14px;

  padding: 15px 16px;

  background:
    rgba(255,255,255,.025);
}}

.missing-stat-value {{
  display: block;
  font-size: 1.55rem;
  line-height: 1;
  font-weight: 900;
  color: #fff;
  margin-bottom: 7px;
}}

.missing-stat-label {{
  display: block;
  color: #888;
  font-size: .72rem;
  text-transform: uppercase;
  letter-spacing: .07em;
}}

.missing-targets-heading {{
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin: 28px 0 14px;
}}

.missing-targets-heading h3 {{
  margin: 0;
  font-size: 15px;
}}

.missing-targets-heading p {{
  margin: 0;
  color: #777;
  font-size: 11px;
}}

.missing-target-grid {{
  display: grid;
  grid-template-columns:
    repeat(4, minmax(0,1fr));
  gap: 14px;
}}

.missing-target-card {{
  min-width: 0;
  overflow: hidden;

  border:
    1px solid #2b2f36;

  border-radius: 14px;

  background:
    #1b1e23;

  transition:
    transform .16s ease,
    border-color .16s ease,
    box-shadow .16s ease;
}}

.missing-target-card:hover {{
  transform:
    translateY(-3px);

  border-color:
    #F7931E;

  box-shadow:
    0 12px 30px rgba(0,0,0,.3);
}}

.missing-target-image {{
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  overflow: hidden;

  background:
    linear-gradient(
      135deg,
      #252a31,
      #101214
    );
}}

.missing-target-image img {{
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}}

.missing-target-placeholder {{
  width: 100%;
  height: 100%;

  display: grid;
  place-items: center;

  color: #F7931E;
  font-size: 3rem;
  font-weight: 900;
}}

.missing-target-body {{
  padding: 13px 14px 14px;
}}

.missing-target-impact {{
  display: inline-flex;

  padding: 4px 8px;

  border-radius: 999px;

  background:
    rgba(247,147,30,.13);

  color: #ffae4d;

  font-size: .72rem;
  font-weight: 800;

  margin-bottom: 8px;
}}

.missing-target-artist {{
  display: block;

  font-size: 1rem;
  font-weight: 850;

  line-height: 1.2;

  text-decoration: none;
}}

.missing-target-track {{
  margin-top: 4px;
  min-height: 2.5em;

  line-height: 1.25;

  font-size: .84rem;
  color: #bbb;
}}

.missing-target-actions {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;

  margin-top: 12px;
}}

.missing-target-actions a {{
  padding: 5px 8px;

  border-radius: 7px;

  background:
    rgba(255,255,255,.06);

  text-decoration: none;

  font-size: .72rem;
}}

.missing-toolbar {{
  margin: 28px 0 14px;
}}

#missingFilter {{
  width: 100%;
  max-width: none;

  box-sizing: border-box;

  padding: 13px 15px;

  border-radius: 11px;
}}

.missing-table-wrap {{
  overflow-x: auto;

  border:
    1px solid #2b2f36;

  border-radius: 14px;
}}

#missingTracks {{
  margin: 0;
}}

#missingTracks th {{
  white-space: nowrap;
  background: #14171b;
}}

#missingTracks tbody tr:hover {{
  background:
    rgba(255,255,255,.025);
}}

#missingTracks tbody tr[data-impact="high"] {{
  background:
    rgba(247,147,30,.025);
}}

.missing-artist-link {{
  font-weight: 800;
  text-decoration: none;
}}

.missing-track {{
  font-weight: 600;
}}

.missing-impact {{
  display: inline-block;

  min-width: 48px;

  padding: 4px 8px;

  text-align: center;

  border-radius: 999px;

  background:
    rgba(255,255,255,.06);

  font-weight: 850;
}}

.missing-impact.high {{
  background:
    rgba(247,147,30,.16);

  color:
    #ffae4d;
}}

.missing-impact.medium {{
  background:
    rgba(255,213,79,.12);

  color:
    #ffd54f;
}}

.missing-show-links {{
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}}

.missing-show-links a {{
  display: inline-block;

  min-width: 38px;

  padding: 4px 6px;

  border-radius: 7px;

  background:
    rgba(255,255,255,.05);

  text-align: center;

  font-size: 11px;
}}

.missing-search-links {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}}

.missing-search-links a {{
  padding: 5px 8px;

  border-radius: 7px;

  background:
    rgba(255,255,255,.05);

  font-size: 11px;
}}

@media (max-width: 1100px) {{
  .missing-target-grid {{
    grid-template-columns:
      repeat(2, minmax(0,1fr));
  }}
}}

@media (max-width: 800px) {{
  .missing-page {{
    width:
      calc(100vw - 24px)
      !important;
  }}

  .missing-stats {{
    grid-template-columns:
      1fr;
  }}

  .missing-target-grid {{
    grid-template-columns:
      1fr;
  }}

  .missing-targets-heading p {{
    display: none;
  }}
}}
</style>

<div class="card missing-page">
  <div class="missing-hero">

    <a
      class="missing-back"
      href="/"
    >
      ← Back
    </a>

    <div class="missing-title-row">
      <h2>🎯 Missing Tracks</h2>

      <p class="missing-subtitle">
        Tracks missing from your library,
        ranked by how often they appear
        across WEFUNK.
      </p>
    </div>

    <div class="missing-stats">

      <div class="missing-stat">
        <span class="missing-stat-value">
          {len(missing_rows[:1000]):,}
        </span>

        <span class="missing-stat-label">
          Priority Tracks
        </span>
      </div>

      <div class="missing-stat">
        <span class="missing-stat-value">
          {top_1000_artists:,}
        </span>

        <span class="missing-stat-label">
          Artists in Top 1,000
        </span>
      </div>

      <div class="missing-stat">
        <span class="missing-stat-value">
          {highest_impact:,}
        </span>

        <span class="missing-stat-label">
          Highest Show Impact
        </span>
      </div>

    </div>

    <div class="missing-targets-heading">
      <h3>🔥 Top Missing Tracks</h3>

      <p>
        Highest-impact tracks
        across your WEFUNK archive
      </p>
    </div>

    <div class="missing-target-grid">
      {''.join(top_cards)}
    </div>

    <div class="missing-toolbar">

      <input
        id="missingFilter"
        placeholder=
          "Search artist, track, or show..."
        oninput=
          "filterTable(
            'missingFilter',
            'missingTracks'
          )"
      >

    </div>

  </div>

  <div class="missing-table-wrap">

    <table id="missingTracks">

      <thead>
        <tr>

          <th
            onclick=
              "sortTable(
                'missingTracks',
                0
              )"
          >
            Artist
          </th>

          <th
            onclick=
              "sortTable(
                'missingTracks',
                1
              )"
          >
            Track
          </th>

          <th
            onclick=
              "sortTable(
                'missingTracks',
                2,
                true
              )"
          >
            Shows
          </th>

          <th>
            Appears In
          </th>

          <th>
            Search
          </th>

        </tr>
      </thead>

      <tbody>
        {''.join(missing_rows[:1000])}
      </tbody>

    </table>

  </div>
</div>
"""

start = template.find(
    '<div class="card">'
)

end = template.rfind(
    "</body>"
)

if start == -1 or end == -1:
    raise SystemExit(
        "Could not find replaceable "
        "page body in missing.html"
    )

page = (
    template[:start]
    + missing_card
    + "\n"
    + template[end:]
)

OUT.write_text(
    page,
    encoding="utf-8",
)

print(f"Wrote: {OUT}")
print(
    f"Priority tracks: "
    f"{len(missing_rows[:1000]):,}"
)
print(
    f"Artists in Top 1,000: "
    f"{top_1000_artists:,}"
)
print(
    f"Highest show impact: "
    f"{highest_impact:,}"
)
