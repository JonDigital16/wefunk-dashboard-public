#!/usr/bin/env python3

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import artist_slugify, esc

SITE = Path(
    os.environ.get(
        "WEFUNK_SITE_DIR",
        str(Path(__file__).resolve().parents[1] / "site"),
    )
)

EXPORTS = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve()
SOURCE = EXPORTS / "wefunk_owned_tracks_enriched.csv"
TEMPLATE = SITE / "albums.html"
OUT = SITE / "artists.html"
ARTIST_IMAGES = SITE / "artist-images"
ARTIST_ASSET_ALIASES_FILE = Path(__file__).with_name(
    "artist_asset_aliases.json"
)
ARTIST_DISPLAY_NAMES_FILE = Path(__file__).with_name(
    "artist_display_names.json"
)

artist_asset_aliases = {}
artist_display_names = {}

if ARTIST_DISPLAY_NAMES_FILE.exists():
    try:
        loaded_display_names = json.loads(
            ARTIST_DISPLAY_NAMES_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(loaded_display_names, dict):
            artist_display_names = {
                str(slug): str(name).strip()
                for slug, name in loaded_display_names.items()
                if slug and str(name).strip()
            }
    except (OSError, json.JSONDecodeError):
        artist_display_names = {}

if ARTIST_ASSET_ALIASES_FILE.exists():
    try:
        loaded_aliases = json.loads(
            ARTIST_ASSET_ALIASES_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(loaded_aliases, dict):
            artist_asset_aliases = {
                str(alias): str(canonical)
                for alias, canonical in loaded_aliases.items()
                if alias and canonical
            }
    except (OSError, json.JSONDecodeError):
        artist_asset_aliases = {}

if not SOURCE.exists():
    raise SystemExit(f"Missing source export: {SOURCE}")

if not TEMPLATE.exists():
    raise SystemExit(
        "albums.html does not exist yet. "
        "Run generate_albums_index_page.py first."
    )

artists = defaultdict(
    lambda: {
        "display": "",
        "tracks": 0,
        "albums": set(),
        "genres": defaultdict(int),
    }
)

with SOURCE.open(newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        artist = (row.get("artist") or "").strip()
        album = (row.get("matched_album") or "").strip()
        genre = (row.get("matched_genre") or "").strip()

        if not artist:
            continue

        key = artist.lower()
        entry = artists[key]

        entry["display"] = artist
        entry["tracks"] += 1

        if album:
            entry["albums"].add(album.lower())

        if genre:
            entry["genres"][genre] += 1


def primary_genre(entry):
    if not entry["genres"]:
        return ""

    return sorted(
        entry["genres"].items(),
        key=lambda item: (-item[1], item[0].lower()),
    )[0][0]


artist_rows = sorted(
    artists.values(),
    key=lambda entry: (
        -entry["tracks"],
        -len(entry["albums"]),
        entry["display"].lower(),
    ),
)

featured_artists = artist_rows[:24]

featured_cards = []

for entry in featured_artists:
    source_name = entry["display"]
    slug = artist_slugify(source_name)
    canonical_asset_slug = artist_asset_aliases.get(slug, slug)

    name = (
        artist_display_names.get(slug)
        or artist_display_names.get(canonical_asset_slug)
        or source_name
    )

    tracks = entry["tracks"]
    albums = len(entry["albums"])
    genre = primary_genre(entry)

    canonical_asset_slug = artist_asset_aliases.get(
        slug,
        slug,
    )

    own_image_path = ARTIST_IMAGES / f"{slug}.jpg"
    canonical_image_path = (
        ARTIST_IMAGES / f"{canonical_asset_slug}.jpg"
    )

    if own_image_path.exists():
        image_slug = slug
    elif canonical_image_path.exists():
        image_slug = canonical_asset_slug
    else:
        image_slug = ""

    image_html = ""

    if image_slug:
        image_html = (
            f"<img "
            f"src='/artist-images/{esc(image_slug)}.jpg' "
            f"alt='{esc(name)}' "
            f"loading='lazy'>"
        )
    else:
        image_html = (
            f"<div class='artist-card-placeholder'>"
            f"{esc(name[:1].upper())}"
            f"</div>"
        )

    album_label = "album" if albums == 1 else "albums"
    track_label = "track" if tracks == 1 else "tracks"

    featured_cards.append(
        f"""
<a class="artist-feature-card" href="/artists/{esc(slug)}.html">
  <div class="artist-feature-image">
    {image_html}
  </div>

  <div class="artist-feature-body">
    <strong>{esc(name)}</strong>

    <div class="artist-feature-meta">
      {tracks:,} matched {track_label}
      ·
      {albums:,} {album_label}
    </div>

    <div class="artist-feature-genre">
      {esc(genre) if genre else "Genre unavailable"}
    </div>
  </div>
</a>
"""
    )

def artist_display_name(entry):
    source_name = entry["display"]
    slug = artist_slugify(source_name)
    canonical_slug = artist_asset_aliases.get(slug, slug)

    return (
        artist_display_names.get(slug)
        or artist_display_names.get(canonical_slug)
        or source_name
    )


rows = "\n".join(
    f"<tr>"
    f"<td>"
    f"<a href='/artists/{artist_slugify(entry['display'])}.html'>"
    f"{esc(artist_display_name(entry))}"
    f"</a>"
    f"</td>"
    f"<td data-sort='{entry['tracks']}'>{entry['tracks']:,}</td>"
    f"<td data-sort='{len(entry['albums'])}'>{len(entry['albums']):,}</td>"
    f"<td>{esc(primary_genre(entry))}</td>"
    f"</tr>"
    for entry in artist_rows
)

featured_card = f"""
<div class="card artist-featured-card">
  <p><a href="/">← Back</a></p>

  <div class="artist-featured-heading">
    <div>
      <h2>🎤 Featured Artists</h2>

      <p class="small">
        The most represented artists in your matched WEFUNK collection.
      </p>

      <p class="artist-featured-note">
        Showing top 24 artists by matched-track count.
      </p>
    </div>

    <div class="artist-featured-summary">
      <strong>{len(artist_rows):,}</strong>
      <span>Total Artists</span>
    </div>
  </div>

  <div class="artist-feature-grid">
    {''.join(featured_cards)}
  </div>
</div>
"""

index_card = f"""
<div class="card">
  <div class="artist-index-heading">
    <div>
      <h2>Artist Index</h2>

      <p class="small">
        Browse, filter, and sort all artists represented in your matched
        WEFUNK collection.
      </p>
    </div>
  </div>

  <input
    id="artistIndexFilter"
    placeholder="Filter artists..."
    oninput="filterTable('artistIndexFilter','artistIndex')"
  >

  <table id="artistIndex">
    <thead>
      <tr>
        <th onclick="sortTable('artistIndex',0)">Artist</th>
        <th onclick="sortTable('artistIndex',1,true)">
          Matched Tracks
        </th>
        <th onclick="sortTable('artistIndex',2,true)">
          Albums
        </th>
        <th onclick="sortTable('artistIndex',3)">
          Primary Genre
        </th>
      </tr>
    </thead>

    <tbody>
      {rows}
    </tbody>
  </table>
</div>
"""

css = """
<style>
.artist-featured-heading{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:20px;
  margin-bottom:20px;
}

.artist-featured-heading h2{
  margin-bottom:4px;
}

.artist-featured-note{
  display:inline-block;
  margin:8px 0 0;
  padding:6px 10px;
  border:1px solid rgba(247,147,30,.35);
  border-radius:999px;
  background:rgba(247,147,30,.08);
  color:#F7931E;
  font-size:12px;
  font-weight:800;
}

.artist-featured-summary{
  display:flex;
  min-width:108px;
  flex-direction:column;
  align-items:center;
  padding:12px 16px;
  border:1px solid #2b2f36;
  border-radius:14px;
  background:#171a1f;
}

.artist-featured-summary strong{
  color:#F7931E;
  font-size:26px;
  line-height:1;
}

.artist-featured-summary span{
  margin-top:7px;
  color:#aaa;
  font-size:12px;
  font-weight:700;
}

.artist-feature-grid{
  display:grid;
  grid-template-columns:repeat(6,minmax(0,1fr));
  gap:14px;
}

.artist-feature-card{
  display:block;
  min-width:0;
  overflow:hidden;
  border:1px solid #2b2f36;
  border-radius:16px;
  background:#171a1f;
  color:#f5f5f5;
  text-decoration:none;
  transition:
    transform .18s ease,
    border-color .18s ease,
    box-shadow .18s ease;
}

.artist-feature-card:hover{
  transform:translateY(-3px);
  border-color:#F7931E;
  box-shadow:0 14px 34px rgba(0,0,0,.32);
}

.artist-feature-image{
  aspect-ratio:1 / 1;
  overflow:hidden;
  background:#111419;
}

.artist-feature-image img{
  display:block;
  width:100%;
  height:100%;
  object-fit:cover;
  transition:transform .22s ease;
}

.artist-feature-card:hover .artist-feature-image img{
  transform:scale(1.04);
}

.artist-card-placeholder{
  display:flex;
  width:100%;
  height:100%;
  align-items:center;
  justify-content:center;
  background:
    linear-gradient(
      145deg,
      rgba(247,147,30,.42),
      rgba(23,26,31,.98)
    );
  color:#F7931E;
  font-size:44px;
  font-weight:900;
}

.artist-feature-body{
  padding:14px;
}

.artist-feature-body strong{
  display:block;
  overflow:hidden;
  font-size:15px;
  line-height:1.25;
  text-overflow:ellipsis;
  white-space:nowrap;
}

.artist-feature-meta{
  margin-top:8px;
  color:#bbb;
  font-size:12px;
  font-weight:700;
  line-height:1.35;
}

.artist-feature-genre{
  margin-top:7px;
  color:#F7931E;
  font-size:11px;
  font-weight:800;
  line-height:1.3;
}

.artist-index-heading{
  margin-bottom:18px;
}

@media(max-width:1200px){
  .artist-feature-grid{
    grid-template-columns:repeat(4,minmax(0,1fr));
  }
}

@media(max-width:800px){
  .artist-featured-heading{
    flex-direction:column;
  }

  .artist-feature-grid{
    grid-template-columns:repeat(3,minmax(0,1fr));
  }
}

@media(max-width:560px){
  .artist-feature-grid{
    grid-template-columns:repeat(2,minmax(0,1fr));
  }

  .artist-feature-body{
    padding:12px;
  }

  .artist-feature-body strong{
    font-size:14px;
  }

  .artist-feature-meta{
    font-size:11px;
  }
}
</style>
"""

template = TEMPLATE.read_text(encoding="utf-8")

start = template.find('<div class="card">')
end = template.rfind("</body>")

if start == -1 or end == -1:
    raise SystemExit("Could not locate page content boundaries")

page = (
    template[:start]
    + featured_card
    + "\n"
    + index_card
    + "\n"
    + template[end:]
)

page = page.replace(
    "</head>",
    css + "\n</head>",
    1,
)

OUT.write_text(page, encoding="utf-8")

print(f"Wrote: {OUT}")
print(f"Artists: {len(artist_rows)}")
print(f"Featured artists: {len(featured_artists)}")
