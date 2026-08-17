#!/usr/bin/env python3

import sys
import json
from pathlib import Path
from collections import defaultdict
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, artist_slugify, esc, slugify
from data import missing_tracks_engine, missing_tracks

TEMPLATE = SITE / "shopping.html"
OUT = SITE / "shopping.html"

if not TEMPLATE.exists():
    raise SystemExit("shopping.html does not exist yet. Run generate_dashboard.py first.")

template = TEMPLATE.read_text(encoding="utf-8")

rows_source = missing_tracks_engine or missing_tracks

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

    except (OSError, json.JSONDecodeError):
        artist_asset_aliases = {}

def pick(row, names):
    for name in names:
        if name in row and row[name]:
            return row[name]
    return ""


def display_name(value):
    """
    Presentation-only capitalization.

    Keeps the stored/matching data untouched while making
    artist and track names look better on the shopping page.
    """
    value = str(value or "").strip()

    if not value:
        return ""

    small_words = {
        "a", "an", "and", "as", "at", "but",
        "by", "for", "from", "in", "of", "on",
        "or", "the", "to", "with",
    }

    known = {
        "dj": "DJ",
        "mc": "MC",
        "m.c.": "M.C.",
        "m.c.'s": "M.C.'s",
        "j.b.'s": "J.B.'s",
        "u.m.c.'s": "U.M.C.'s",
        "i.n.i.": "I.N.I.",
        "s.o.u.l.": "S.O.U.L.",
    }

    words = value.split()
    output = []

    for index, word in enumerate(words):
        prefix = ""
        suffix = ""
        core = word

        while core and core[0] in "([{'\"":
            prefix += core[0]
            core = core[1:]

        while core and core[-1] in ".,!?;:)]}'\"":
            suffix = core[-1] + suffix
            core = core[:-1]

        lower = core.lower()

        if lower in known:
            formatted = known[lower]
        elif (
            index > 0
            and lower in small_words
        ):
            formatted = lower
        elif lower.startswith("mc") and len(core) > 2:
            formatted = "MC" + core[2:].capitalize()
        else:
            formatted = core[:1].upper() + core[1:]

        output.append(
            prefix + formatted + suffix
        )

    return " ".join(output)

groups = defaultdict(list)

for r in rows_source:
    artist = pick(r, ["artist", "wf_artist"]).strip()
    track = pick(r, ["track", "wf_track", "title"]).strip()
    show = pick(r, ["show_id", "show"]).strip()

    if not artist and not track:
        continue

    key = (artist.lower(), track.lower())
    groups[key].append({
        "artist": artist,
        "track": track,
        "show": show,
    })

shopping_rows = []
shopping_targets = []

for (_artist_key, _track_key), items in sorted(
    groups.items(),
    key=lambda kv: len(kv[1]),
    reverse=True
):
    first = items[0]
    artist = first["artist"]
    track = first["track"]
    artist_slug = artist_slugify(artist)

    show_links = " ".join(
        f"<a href='/shows/{esc(x['show'])}.html'>{esc(x['show'])}</a>"
        for x in items[:20]
        if x["show"]
    )

    q = quote_plus(f"{artist} {track}")

    shopping_targets.append({
        "artist": artist,
        "track": track,
        "artist_slug": artist_slug,
        "shows_improved": len(items),
        "query": q,
    })

    impact = (
        "high"
        if len(items) >= 5
        else "medium"
        if len(items) >= 3
        else "normal"
    )

    artist_display = display_name(artist)
    track_display = display_name(track)

    shopping_rows.append(
        f"<tr data-impact='{impact}'>"
        f"<td>"
        f"<a class='shopping-artist-link' "
        f"href='/artists/{esc(artist_slug)}.html'>"
        f"{esc(artist_display)}</a>"
        f"</td>"
        f"<td class='shopping-track'>{esc(track_display)}</td>"
        f"<td data-sort='{len(items)}'>"
        f"<span class='shopping-impact {impact}'>"
        f"{'🔥 ' if impact == 'high' else ''}{len(items)}</span>"
        f"</td>"
        f"<td>"
        f"<div class='shopping-show-links'>{show_links}</div>"
        f"</td>"
        f"<td>"
        f"<div class='shopping-search-links'>"
        f"<a href='https://www.discogs.com/search/?q={q}&type=all'>Discogs</a>"
        f"<a href='https://www.youtube.com/results?search_query={q}'>YouTube</a>"
        f"<a href='https://bandcamp.com/search?q={q}'>Bandcamp</a>"
        f"</div>"
        f"</td>"
        f"</tr>"
    )

top_target_cards = []

for target in shopping_targets[:12]:
    artist = target["artist"]
    track = target["track"]
    slug = target["artist_slug"]
    impact = target["shows_improved"]
    q = target["query"]

    canonical_slug = artist_asset_aliases.get(
        slug,
        slug,
    )

    own_image = (
        ARTIST_IMAGES / f"{slug}.jpg"
    )

    canonical_image = (
        ARTIST_IMAGES / f"{canonical_slug}.jpg"
    )

    if own_image.exists():
        image_slug = slug
    elif canonical_image.exists():
        image_slug = canonical_slug
    else:
        image_slug = ""

    artist_display = display_name(artist)
    track_display = display_name(track)

    if image_slug:
        image_path = (
            ARTIST_IMAGES
            / f"{image_slug}.jpg"
        )

        image_version = int(
            image_path.stat().st_mtime
        )

        image_html = (
            f"<img "
            f"src='/artist-images/{esc(image_slug)}.jpg"
            f"?v={image_version}' "
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
            f"<div class='shopping-target-placeholder'>"
            f"{esc(initial)}"
            f"</div>"
        )

    top_target_cards.append(
        f"<article class='shopping-target-card'>"

        f"<a class='shopping-target-image' "
        f"href='/artists/{esc(slug)}.html'>"
        f"{image_html}"
        f"</a>"

        f"<div class='shopping-target-body'>"

        f"<div class='shopping-target-impact'>"
        f"🔥 {impact} shows improved"
        f"</div>"

        f"<a class='shopping-target-artist' "
        f"href='/artists/{esc(slug)}.html'>"
        f"{esc(artist_display)}</a>"

        f"<div class='shopping-target-track'>"
        f"{esc(track_display)}"
        f"</div>"

        f"<div class='shopping-target-actions'>"

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


top_1000_artists = len({
    target["artist"].casefold()
    for target in shopping_targets[:1000]
    if target["artist"]
})


shopping_card = f"""
<style>
.shopping-page {{
  width: min(1800px, calc(100vw - 48px)) !important;
  max-width: none !important;
  margin-left: auto !important;
  margin-right: auto !important;
  box-sizing: border-box;
}}

.shopping-hero {{
  display: grid;
  gap: 18px;
  margin-bottom: 20px;
}}

.shopping-title-row {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}}

.shopping-title-row h2 {{
  margin: 0;
}}

.shopping-subtitle {{
  margin: 6px 0 0;
  opacity: 0.75;
}}

.shopping-stats {{
  display: grid;
  grid-template-columns: repeat(3, minmax(150px, 1fr));
  gap: 12px;
}}

.shopping-stat {{
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  padding: 14px 16px;
  background: rgba(255,255,255,0.03);
}}

.shopping-stat-value {{
  display: block;
  font-size: 1.5rem;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 6px;
}}

.shopping-stat-label {{
  font-size: 0.8rem;
  opacity: 0.65;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}}

.shopping-targets-section {{
  margin-top: 6px;
  margin-bottom: 26px;
}}

.shopping-targets-heading {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}}

.shopping-targets-heading h3 {{
  margin: 0;
  font-size: 1.05rem;
}}

.shopping-targets-heading p {{
  margin: 0;
  opacity: 0.6;
  font-size: 0.82rem;
}}

.shopping-target-grid {{
  display: grid;
  grid-template-columns:
    repeat(4, minmax(0, 1fr));
  gap: 14px;
}}

.shopping-target-card {{
  min-width: 0;
  overflow: hidden;
  border:
    1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  background:
    rgba(255,255,255,0.025);
  transition:
    transform 0.16s ease,
    border-color 0.16s ease,
    background 0.16s ease;
}}

.shopping-target-card:hover {{
  transform: translateY(-2px);
  border-color:
    rgba(255,255,255,0.15);
  background:
    rgba(255,255,255,0.04);
}}

.shopping-target-image {{
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background:
    rgba(255,255,255,0.04);
}}

.shopping-target-image img {{
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  transition:
    transform 0.25s ease;
}}

.shopping-target-card:hover
.shopping-target-image img {{
  transform: scale(1.025);
}}

.shopping-target-placeholder {{
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  font-size: 3rem;
  font-weight: 800;
  opacity: 0.4;
}}

.shopping-target-body {{
  padding: 13px 14px 14px;
}}

.shopping-target-impact {{
  display: inline-flex;
  margin-bottom: 8px;
  padding: 4px 8px;
  border-radius: 999px;
  background:
    rgba(46, 204, 113, 0.15);
  font-size: 0.72rem;
  font-weight: 750;
}}

.shopping-target-artist {{
  display: block;
  font-size: 1rem;
  font-weight: 800;
  line-height: 1.2;
  text-decoration: none;
}}

.shopping-target-track {{
  margin-top: 4px;
  min-height: 2.5em;
  line-height: 1.25;
  font-size: 0.84rem;
  opacity: 0.75;
}}

.shopping-target-actions {{
  display: flex;
  gap: 6px;
  margin-top: 12px;
  flex-wrap: wrap;
}}

.shopping-target-actions a {{
  padding: 5px 8px;
  border-radius: 7px;
  background:
    rgba(255,255,255,0.06);
  text-decoration: none;
  font-size: 0.72rem;
}}

.shopping-toolbar {{
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}}

#shoppingFilter {{
  flex: 1 1 320px;
  min-width: 240px;
  padding: 12px 14px;
  border-radius: 10px;
}}

.shopping-table-wrap {{
  overflow-x: auto;
}}

#shoppingList {{
  width: 100%;
}}

#shoppingList td {{
  vertical-align: middle;
}}

.shopping-artist-link {{
  font-weight: 750;
  text-decoration: none;
}}

.shopping-track {{
  font-weight: 600;
}}

.shopping-impact {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  height: 32px;
  padding: 0 11px;
  border-radius: 999px;
  font-weight: 800;
  background: rgba(255,255,255,0.08);
}}

.shopping-impact.high {{
  background: rgba(46, 204, 113, 0.18);
}}

.shopping-impact.medium {{
  background: rgba(241, 196, 15, 0.18);
}}

.shopping-show-links {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}}

.shopping-show-links a {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 38px;
  padding: 4px 7px;
  border-radius: 7px;
  background: rgba(255,255,255,0.06);
  text-decoration: none;
  font-size: 0.78rem;
}}

.shopping-search-links {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}}

.shopping-search-links a {{
  display: inline-flex;
  align-items: center;
  padding: 6px 9px;
  border-radius: 8px;
  text-decoration: none;
  background: rgba(255,255,255,0.06);
  font-size: 0.8rem;
  white-space: nowrap;
}}

#shoppingList tbody tr[data-impact="high"] {{
  background: rgba(46, 204, 113, 0.035);
}}

#shoppingList tbody tr:hover {{
  background: rgba(255,255,255,0.035);
}}

@media (max-width: 1100px) {{
  .shopping-target-grid {{
    grid-template-columns:
      repeat(2, minmax(0, 1fr));
  }}
}}

@media (max-width: 800px) {{
  .shopping-stats {{
    grid-template-columns: 1fr;
  }}

  .shopping-target-grid {{
    grid-template-columns: 1fr;
  }}
}}
</style>

<div class="card shopping-page">
  <div class="shopping-hero">
    <p><a href="/">← Back</a></p>

    <div class="shopping-title-row">
      <div>
        <h2>Smart Shopping List</h2>
        <p class="shopping-subtitle">
          Missing tracks ranked by how many WEFUNK shows each purchase would improve.
        </p>
      </div>
    </div>

    <div class="shopping-stats">
      <div class="shopping-stat">
        <span class="shopping-stat-value">{len(shopping_rows[:1000]):,}</span>
        <span class="shopping-stat-label">Priority Tracks</span>
      </div>

      <div class="shopping-stat">
        <span class="shopping-stat-value">{top_1000_artists:,}</span>
        <span class="shopping-stat-label">Artists in Top 1,000</span>
      </div>

      <div class="shopping-stat">
        <span class="shopping-stat-value">{max((len(v) for v in groups.values()), default=0):,}</span>
        <span class="shopping-stat-label">Highest Show Impact</span>
      </div>
    </div>

    <section class="shopping-targets-section">
      <div class="shopping-targets-heading">
        <h3>🔥 Top Shopping Targets</h3>
        <p>Highest-impact missing tracks</p>
      </div>

      <div class="shopping-target-grid">
        {''.join(top_target_cards)}
      </div>
    </section>

    <div class="shopping-toolbar">
      <input
        id="shoppingFilter"
        placeholder="Search artist, track, or show..."
        oninput="filterTable('shoppingFilter','shoppingList')"
      >
    </div>
  </div>

  <div class="shopping-table-wrap">
    <table id="shoppingList">
      <thead>
        <tr>
          <th onclick="sortTable('shoppingList',0)">Artist</th>
          <th onclick="sortTable('shoppingList',1)">Track</th>
          <th onclick="sortTable('shoppingList',2,true)">Shows Improved</th>
          <th>Appears In</th>
          <th>Search</th>
        </tr>
      </thead>
      <tbody>
        {''.join(shopping_rows[:1000])}
      </tbody>
    </table>
  </div>
</div>
"""

start = template.find('<div class="card shopping-page">')

if start == -1:
    start = template.find('<div class="card">')

end = template.rfind("</main>")

if start == -1 or end == -1:
    raise SystemExit("Could not find replaceable <main> content in shopping.html")

page = template[:start] + shopping_card + "\n" + template[end:]

if "/js/table-helpers.js" not in page:
    page = page.replace(
        "</head>",
        '    <script src="/js/table-helpers.js"></script>\n</head>'
    )


OUT.write_text(page, encoding="utf-8")

print(f"Wrote: {OUT}")
