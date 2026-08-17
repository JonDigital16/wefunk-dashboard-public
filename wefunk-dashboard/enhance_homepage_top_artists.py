#!/usr/bin/env python3

import csv
import os
from collections import defaultdict
from pathlib import Path

from common import artist_display_name, artist_slugify

SITE = Path(
    os.environ.get(
        "WEFUNK_SITE_DIR",
        str(Path(__file__).resolve().parents[1] / "site"),
    )
)

EXPORTS = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve()
INDEX = SITE / "index.html"
SOURCE = EXPORTS / "wefunk_owned_tracks_enriched.csv"

if not INDEX.exists():
    raise SystemExit("index.html does not exist")

if not SOURCE.exists():
    raise SystemExit("wefunk_owned_tracks_enriched.csv does not exist")

homepage = INDEX.read_text(encoding="utf-8")

if 'id="homepageTopArtists"' in homepage:
    print("Homepage Top Artists already present")
    raise SystemExit(0)

artists = defaultdict(lambda: {
    "display": "",
    "tracks": 0,
    "albums": set(),
})

with SOURCE.open(newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        artist = (row.get("artist") or "").strip()
        album = (row.get("matched_album") or "").strip()

        if not artist:
            continue

        key = artist.lower()

        artists[key]["display"] = artist
        artists[key]["tracks"] += 1

        if album:
            artists[key]["albums"].add(album.lower())

top_artists = sorted(
    artists.values(),
    key=lambda item: (
        -item["tracks"],
        -len(item["albums"]),
        item["display"].lower(),
    ),
)[:10]

largest = top_artists[0]["tracks"] if top_artists else 1

cards = []

for artist in top_artists:
    name = artist["display"]
    display_name = artist_display_name(name)
    tracks = artist["tracks"]
    albums = len(artist["albums"])
    width = max(4, round((tracks / largest) * 100))

    album_label = "album" if albums == 1 else "albums"

    cards.append(f"""
<a class="homepage-artist-row" href="/artists/{artist_slugify(name)}.html">
  <div class="homepage-artist-heading">
    <strong>{display_name}</strong>
    <span>{tracks:,} tracks</span>
  </div>

  <div class="homepage-artist-progress">
    <div style="width:{width}%"></div>
  </div>

  <div class="homepage-artist-meta">
    {albums:,} matched {album_label}
  </div>
</a>
""")

section = f"""
<div class="card homepage-top-artists" id="homepageTopArtists">
  <div class="homepage-artists-heading">
    <div>
      <h2>🎤 Top Artists</h2>
      <p class="small">
        The most represented artists in your matched WEFUNK collection.
      </p>
    </div>

    <a class="homepage-artists-link" href="/artists.html">
      Browse artists →
    </a>
  </div>

  <div class="homepage-artists-grid">
    {''.join(cards)}
  </div>
</div>
"""

css = """
<style>
.homepage-artists-heading{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:18px;
  margin-bottom:18px;
}

.homepage-artists-heading h2{
  margin-bottom:4px;
}

.homepage-artists-link{
  flex-shrink:0;
  padding:8px 12px;
  border:1px solid #2b2f36;
  border-radius:999px;
  color:#F7931E;
  font-size:13px;
  font-weight:800;
  text-decoration:none;
}

.homepage-artists-link:hover{
  border-color:#F7931E;
  background:#F7931E;
  color:#111;
}

.homepage-artists-grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:14px;
}

.homepage-artist-row{
  display:block;
  padding:15px;
  border:1px solid #2b2f36;
  border-radius:15px;
  background:#171a1f;
  color:#f5f5f5;
  text-decoration:none;
  transition:
    transform .18s ease,
    border-color .18s ease,
    box-shadow .18s ease;
}

.homepage-artist-row:hover{
  transform:translateY(-2px);
  border-color:#F7931E;
  box-shadow:0 12px 30px rgba(0,0,0,.25);
}

.homepage-artist-heading{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
}

.homepage-artist-heading strong{
  font-size:14px;
}

.homepage-artist-heading span{
  color:#999;
  font-size:12px;
}

.homepage-artist-progress{
  height:8px;
  margin-top:12px;
  overflow:hidden;
  border-radius:999px;
  background:#2b2f36;
}

.homepage-artist-progress div{
  height:100%;
  border-radius:999px;
  background:#F7931E;
}

.homepage-artist-meta{
  margin-top:9px;
  color:#888;
  font-size:12px;
}

@media(max-width:650px){
  .homepage-artists-heading{
    display:block;
  }

  .homepage-artists-link{
    display:inline-block;
    margin-top:10px;
  }

  .homepage-artists-grid{
    grid-template-columns:1fr;
  }
}
</style>
"""

homepage = homepage.replace(
    "</head>",
    css + "\n</head>",
    1,
)

marker = homepage.find('id="homepageTopGenres"')

if marker == -1:
    raise SystemExit("Top Genres section not found")

insert_at = homepage.find(
    '\n<div class="card">',
    marker,
)

if insert_at == -1:
    raise SystemExit("Could not find insertion point after Top Genres")

homepage = (
    homepage[:insert_at]
    + "\n"
    + section
    + homepage[insert_at:]
)

INDEX.write_text(homepage, encoding="utf-8")

print(f"Added {len(top_artists)} Top Artist rows to homepage")
