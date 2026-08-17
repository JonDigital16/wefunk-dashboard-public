#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, artist_display_name, artist_slugify, esc
from data import top_missing_artists

TEMPLATE = SITE / "missing.html"
OUT = SITE / "top-missing-artists.html"

if not TEMPLATE.exists():
    raise SystemExit(
        "missing.html does not exist yet. Run dashboard first."
    )

template = TEMPLATE.read_text(encoding="utf-8")

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


def smart_artist_display(name):
    """
    Prefer the dashboard's canonical artist display name.

    If no canonical display name exists and the source is lowercase,
    apply conservative music-friendly capitalization.
    """
    original = str(name or "").strip()

    if not original:
        return ""

    slug = artist_slugify(original)

    canonical = artist_display_name(
        original,
        slug,
    ).strip()

    # If common.py supplied a genuinely different display name,
    # trust it completely.
    if canonical and canonical != original:
        return canonical

    # Already contains intentional capitalization.
    if original != original.lower():
        return original

    small_words = {
        "a",
        "an",
        "and",
        "as",
        "at",
        "but",
        "by",
        "for",
        "from",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "vs",
        "with",
    }

    def format_word(word, index):
        # Preserve punctuation around the actual word.
        match = re.match(
            r"^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9.]*)$",
            word,
        )

        if not match:
            return word

        prefix, core, suffix = match.groups()

        if not core:
            return word

        lower = core.lower()

        # Dotted initials/acronyms:
        # j. -> J.
        # c.l. -> C.L.
        # e.p.m.d. -> E.P.M.D.
        if re.fullmatch(
            r"(?:[a-z]\.){1,}[a-z]?",
            lower,
        ):
            formatted = "".join(
                char.upper()
                if char.isalpha()
                else char
                for char in core
            )

        # Hyphenated names such as k.r.s.-one.
        elif "-" in core:
            formatted = "-".join(
                format_word(
                    part,
                    index,
                )
                for part in core.split("-")
            )

        # Normal title casing, while keeping connecting words
        # lowercase except at the beginning.
        elif index > 0 and lower in small_words:
            formatted = lower

        else:
            formatted = (
                core[:1].upper()
                + core[1:]
            )

        return (
            prefix
            + formatted
            + suffix
        )

    words = original.split()

    return " ".join(
        format_word(word, index)
        for index, word in enumerate(words)
    )


def missing_count(row):
    try:
        return int(
            row.get(
                "missing_count",
                row.get("count", 0),
            )
            or 0
        )
    except Exception:
        return 0


artists = sorted(
    top_missing_artists,
    key=missing_count,
    reverse=True,
)

highest_missing = max(
    (missing_count(row) for row in artists),
    default=0,
)

total_missing = sum(
    missing_count(row)
    for row in artists
)

top_10_missing = sum(
    missing_count(row)
    for row in artists[:10]
)

featured_cards = []

for index, row in enumerate(
    artists[:12],
    start=1,
):
    artist = str(
        row.get("artist", "")
    ).strip()

    slug = artist_slugify(artist)

    display_artist = smart_artist_display(
        artist
    )

    count = missing_count(row)

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
        image_path = own_image

    elif canonical_image.exists():
        image_slug = canonical_slug
        image_path = canonical_image

    else:
        image_slug = ""
        image_path = None

    if image_slug and image_path:
        version = int(
            image_path.stat().st_mtime
        )

        image_html = (
            f"<img "
            f"src='/artist-images/"
            f"{esc(image_slug)}.jpg?v={version}' "
            f"alt='{esc(display_artist)}' "
            f"loading='lazy'>"
        )

    else:
        initial = (
            display_artist[:1].upper()
            if artist
            else "?"
        )

        image_html = (
            f"<div class='top-missing-placeholder'>"
            f"{esc(initial)}"
            f"</div>"
        )

    percent_of_max = (
        (count / highest_missing) * 100
        if highest_missing
        else 0
    )

    featured_cards.append(
        f"""
<a
  class="top-missing-card"
  href="/artists/{esc(slug)}.html"
>
  <div class="top-missing-image">
    {image_html}

    <span class="top-missing-rank">
      #{index}
    </span>

    <span class="top-missing-badge">
      {count:,} missing
    </span>
  </div>

  <div class="top-missing-body">
    <div class="top-missing-name">
      {esc(display_artist)}
    </div>

    <div class="top-missing-bar">
      <div
        class="top-missing-bar-fill"
        style="width:{percent_of_max:.1f}%"
      ></div>
    </div>

    <div class="top-missing-meta">
      {count:,} WEFUNK tracks missing
    </div>
  </div>
</a>
"""
    )


rows = "\n".join(
    f"<tr>"
    f"<td class='top-missing-artist-cell'>"
    f"<a href='/artists/"
    f"{esc(artist_slugify(r.get('artist','')))}.html'>"
    f"{esc(smart_artist_display(r.get('artist','')))}"
    f"</a>"
    f"</td>"
    f"<td data-sort='{missing_count(r)}'>"
    f"<span class='top-missing-count'>"
    f"{missing_count(r):,}"
    f"</span>"
    f"</td>"
    f"<td class='top-missing-progress-cell'>"
    f"<div class='top-missing-progress'>"
    f"<div class='top-missing-progress-fill' "
    f"style='width:{((missing_count(r) / highest_missing) * 100 if highest_missing else 0):.1f}%'>"
    f"</div>"
    f"</div>"
    f"</td>"
    f"</tr>"
    for r in artists
)


card = f"""
<style>
.top-missing-page {{
  width: min(
    1800px,
    calc(100vw - 48px)
  ) !important;

  max-width: none !important;

  margin-left: auto !important;
  margin-right: auto !important;

  box-sizing: border-box;
}}

.top-missing-back {{
  display: inline-block;
  margin-bottom: 14px;
}}

.top-missing-title h2 {{
  margin: 0;
  color: #F7931E;
  font-size: clamp(
    30px,
    3vw,
    46px
  );
}}

.top-missing-subtitle {{
  margin: 8px 0 0;
  color: #aaa;
  font-size: 15px;
  line-height: 1.5;
}}

.top-missing-stats {{
  display: grid;
  grid-template-columns:
    repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 24px;
}}

.top-missing-stat {{
  border: 1px solid #2b2f36;
  border-radius: 14px;
  padding: 16px 18px;
  background: #101214;
}}

.top-missing-stat-value {{
  display: block;
  color: #F7931E;
  font-size: 28px;
  line-height: 1;
  font-weight: 900;
}}

.top-missing-stat-label {{
  display: block;
  margin-top: 7px;
  color: #888;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
}}

.top-missing-section {{
  margin-top: 30px;
}}

.top-missing-section-heading {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}}

.top-missing-section-heading h3 {{
  margin: 0;
  font-size: 21px;
}}

.top-missing-section-heading p {{
  margin: 0;
  color: #888;
  font-size: 12px;
}}

.top-missing-grid {{
  display: grid;
  grid-template-columns:
    repeat(6, minmax(0, 1fr));
  gap: 16px;
}}

.top-missing-card {{
  min-width: 0;
  overflow: hidden;
  display: block;

  border: 1px solid #2b2f36;
  border-radius: 16px;

  background: #101214;
  color: #f5f5f5;
  text-decoration: none;

  transition:
    transform .18s ease,
    border-color .18s ease,
    box-shadow .18s ease;
}}

.top-missing-card:hover {{
  transform: translateY(-4px);
  border-color: #F7931E;
  box-shadow:
    0 14px 34px
    rgba(0,0,0,.32);
}}

.top-missing-image {{
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  overflow: hidden;

  background:
    radial-gradient(
      circle at 30% 25%,
      rgba(247,147,30,.25),
      transparent 45%
    ),
    #111419;
}}

.top-missing-image img {{
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;

  transition:
    transform .22s ease;
}}

.top-missing-card:hover
.top-missing-image img {{
  transform: scale(1.035);
}}

.top-missing-placeholder {{
  width: 100%;
  height: 100%;

  display: grid;
  place-items: center;

  color: #F7931E;
  font-size: 4rem;
  font-weight: 900;
}}

.top-missing-rank {{
  position: absolute;
  top: 10px;
  left: 10px;

  display: inline-flex;
  align-items: center;
  justify-content: center;

  min-width: 30px;
  height: 30px;

  padding: 0 8px;

  border-radius: 999px;

  background:
    rgba(16,18,20,.92);

  border:
    1px solid rgba(
      255,
      255,
      255,
      .15
    );

  color: #fff;
  font-size: 12px;
  font-weight: 900;
}}

.top-missing-badge {{
  position: absolute;
  right: 10px;
  bottom: 10px;

  padding: 5px 9px;

  border-radius: 999px;

  background:
    rgba(16,18,20,.92);

  border:
    1px solid
    rgba(247,147,30,.7);

  color: #F7931E;

  font-size: 11px;
  font-weight: 900;
}}

.top-missing-body {{
  padding: 13px 14px 14px;
}}

.top-missing-name {{
  color: #fff;
  font-size: 16px;
  font-weight: 900;
  line-height: 1.25;

  min-height: 2.5em;
}}

.top-missing-bar {{
  height: 7px;
  margin-top: 12px;

  overflow: hidden;
  border-radius: 999px;

  background: #292d33;
}}

.top-missing-bar-fill {{
  height: 100%;
  border-radius: inherit;
  background: #F7931E;
}}

.top-missing-meta {{
  margin-top: 7px;
  color: #888;
  font-size: 11px;
}}

.top-missing-toolbar {{
  display: flex;
  justify-content: space-between;
  align-items: center;

  gap: 16px;

  margin: 30px 0 14px;
}}

.top-missing-toolbar h3 {{
  margin: 0;
  font-size: 20px;
}}

#missingArtistsFilter {{
  width: min(520px, 100%);
  max-width: none;
  box-sizing: border-box;
}}

.top-missing-table-wrap {{
  width: 100%;
  overflow-x: auto;

  border: 1px solid #2b2f36;
  border-radius: 14px;
}}

#missingArtists {{
  width: 100%;
  margin: 0;
}}

#missingArtists th {{
  background: #14171b;
}}

#missingArtists tbody tr:hover {{
  background:
    rgba(255,255,255,.025);
}}

.top-missing-artist-cell a {{
  font-weight: 800;
}}

.top-missing-count {{
  display: inline-flex;
  justify-content: center;
  align-items: center;

  min-width: 52px;
  height: 30px;

  padding: 0 9px;
  box-sizing: border-box;

  border-radius: 999px;

  background:
    rgba(247,147,30,.13);

  border:
    1px solid
    rgba(247,147,30,.35);

  color: #F7931E;
  font-weight: 900;
}}

.top-missing-progress-cell {{
  width: 45%;
  min-width: 220px;
}}

.top-missing-progress {{
  width: 100%;
  height: 10px;

  overflow: hidden;

  border-radius: 999px;
  background: #292d33;
}}

.top-missing-progress-fill {{
  height: 100%;
  border-radius: inherit;
  background: #F7931E;
}}

@media (max-width: 1300px) {{
  .top-missing-grid {{
    grid-template-columns:
      repeat(4, minmax(0, 1fr));
  }}
}}

@media (max-width: 900px) {{
  .top-missing-page {{
    width:
      calc(100vw - 24px)
      !important;
  }}

  .top-missing-stats {{
    grid-template-columns:
      repeat(2, minmax(0, 1fr));
  }}

  .top-missing-grid {{
    grid-template-columns:
      repeat(2, minmax(0, 1fr));
  }}

  .top-missing-toolbar {{
    flex-direction: column;
    align-items: stretch;
  }}
}}

@media (max-width: 560px) {{
  .top-missing-stats {{
    grid-template-columns: 1fr;
  }}

  .top-missing-grid {{
    grid-template-columns: 1fr;
  }}

  .top-missing-section-heading p {{
    display: none;
  }}
}}
</style>

<div class="card top-missing-page">

  <a
    class="top-missing-back"
    href="/"
  >
    ← Back
  </a>

  <div class="top-missing-title">

    <h2>
      🎤 Top Missing Artists
    </h2>

    <p class="top-missing-subtitle">
      Artists responsible for the
      largest number of missing
      tracks across your WEFUNK
      archive.
    </p>

  </div>

  <div class="top-missing-stats">

    <div class="top-missing-stat">
      <span class="top-missing-stat-value">
        {len(artists):,}
      </span>

      <span class="top-missing-stat-label">
        Artists Ranked
      </span>
    </div>

    <div class="top-missing-stat">
      <span class="top-missing-stat-value">
        {total_missing:,}
      </span>

      <span class="top-missing-stat-label">
        Missing Tracks
      </span>
    </div>

    <div class="top-missing-stat">
      <span class="top-missing-stat-value">
        {highest_missing:,}
      </span>

      <span class="top-missing-stat-label">
        Highest Artist Count
      </span>
    </div>

    <div class="top-missing-stat">
      <span class="top-missing-stat-value">
        {top_10_missing:,}
      </span>

      <span class="top-missing-stat-label">
        Missing From Top 10
      </span>
    </div>

  </div>

  <section class="top-missing-section">

    <div class="top-missing-section-heading">

      <h3>
        🔥 Highest-Impact Missing Artists
      </h3>

      <p>
        Your top 12 artists by
        missing WEFUNK tracks
      </p>

    </div>

    <div class="top-missing-grid">
      {''.join(featured_cards)}
    </div>

  </section>

  <div class="top-missing-toolbar">

    <h3>
      All Missing Artists
    </h3>

    <input
      id="missingArtistsFilter"
      placeholder=
        "Search artists..."
      oninput=
        "filterTable(
          'missingArtistsFilter',
          'missingArtists'
        )"
    >

  </div>

  <div class="top-missing-table-wrap">

    <table id="missingArtists">

      <thead>
        <tr>

          <th
            onclick=
              "sortTable(
                'missingArtists',
                0
              )"
          >
            Artist
          </th>

          <th
            onclick=
              "sortTable(
                'missingArtists',
                1,
                true
              )"
          >
            Missing Count
          </th>

          <th>
            Relative Impact
          </th>

        </tr>
      </thead>

      <tbody>
        {rows}
      </tbody>

    </table>

  </div>

</div>
"""

start = template.find(
    '<div class="card top-missing-page">'
)

if start == -1:
    start = template.find(
        '<div class="card missing-page">'
    )

if start == -1:
    start = template.find(
        '<div class="card">'
    )

end = template.rfind(
    "</body>"
)

if start == -1 or end == -1:
    raise SystemExit(
        "Could not find replaceable "
        "page body."
    )

page = (
    template[:start]
    + card
    + "\n"
    + template[end:]
)

OUT.write_text(
    page,
    encoding="utf-8",
)

print(f"Wrote: {OUT}")
print(
    f"Artists ranked: "
    f"{len(artists):,}"
)
print(
    f"Total missing tracks: "
    f"{total_missing:,}"
)
print(
    f"Highest artist count: "
    f"{highest_missing:,}"
)
