#!/usr/bin/env python3

import csv
import os
from pathlib import Path

SITE = Path(
    os.environ.get(
        "WEFUNK_SITE_DIR",
        str(Path(__file__).resolve().parents[1] / "site"),
    )
)

EXPORTS = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve()
INDEX = SITE / "index.html"
ENRICHED = EXPORTS / "wefunk_owned_tracks_enriched.csv"
ALBUM_INDEX = EXPORTS / "wefunk_album_index.csv"

if not INDEX.exists():
    raise SystemExit("index.html does not exist.")

html = INDEX.read_text(encoding="utf-8")

if 'id="collectionOverview"' in html:
    print("Collection Overview already present")
    raise SystemExit(0)

tracks = 0
artists = set()
genres = set()
years = set()

if ENRICHED.exists():
    with ENRICHED.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tracks += 1

            artist = (row.get("artist") or "").strip()
            genre = (row.get("matched_genre") or "").strip()
            year = (row.get("matched_year") or "").strip()[:4]

            if artist:
                artists.add(artist.lower())

            if genre:
                genres.add(genre.lower())

            if year.isdigit():
                years.add(year)

albums = 0

if ALBUM_INDEX.exists():
    with ALBUM_INDEX.open(newline="", encoding="utf-8") as f:
        albums = sum(1 for _ in csv.DictReader(f))

shows = len(list((SITE / "shows").glob("*.html")))
episode_art = len(list((SITE / "episode-art").glob("*.jpg")))

card = f"""
<div class="card collection-overview" id="collectionOverview">
  <div class="collection-heading">
    <div>
      <h2>📊 Collection Overview</h2>
      <p class="small">Your matched WEFUNK collection at a glance.</p>
    </div>
  </div>

  <div class="collection-stat-grid">
    <a class="collection-stat" href="/recent-matches.html">
      <strong>{tracks:,}</strong>
      <span>Matched Tracks</span>
    </a>

    <a class="collection-stat" href="/albums.html">
      <strong>{albums:,}</strong>
      <span>Albums</span>
    </a>

    <a class="collection-stat" href="/artists.html">
      <strong>{len(artists):,}</strong>
      <span>Owned Artists</span>
    </a>

    <a class="collection-stat" href="/episodes.html">
      <strong>{shows:,}</strong>
      <span>WEFUNK Shows</span>
    </a>

    <a class="collection-stat" href="/genres.html">
      <strong>{len(genres):,}</strong>
      <span>Genres</span>
    </a>

    <a class="collection-stat" href="/years.html">
      <strong>{len(years):,}</strong>
      <span>Release Years</span>
    </a>
  </div>

  <p class="collection-art-note">
    Episode artwork available for {episode_art:,} shows.
  </p>
</div>
"""

css = """
<style>
.collection-heading{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:16px;
}

.collection-heading h2{
  margin-bottom:4px;
}

.collection-stat-grid{
  display:grid;
  grid-template-columns:repeat(6,minmax(120px,1fr));
  gap:14px;
  margin-top:20px;
}

.collection-stat{
  display:flex;
  min-height:112px;
  flex-direction:column;
  justify-content:center;
  padding:16px;
  border:1px solid #2b2f36;
  border-radius:16px;
  background:#171a1f;
  color:#f5f5f5;
  text-align:center;
  text-decoration:none;
  transition:
    transform .18s ease,
    border-color .18s ease,
    box-shadow .18s ease;
}

.collection-stat:hover{
  transform:translateY(-3px);
  border-color:#F7931E;
  box-shadow:0 14px 34px rgba(0,0,0,.28);
}

.collection-stat strong{
  color:#F7931E;
  font-size:28px;
  line-height:1;
}

.collection-stat span{
  margin-top:9px;
  color:#aaa;
  font-size:13px;
  font-weight:700;
}

.collection-art-note{
  margin:16px 0 0;
  color:#888;
  font-size:12px;
  text-align:right;
}

@media(max-width:1050px){
  .collection-stat-grid{
    grid-template-columns:repeat(3,1fr);
  }
}

@media(max-width:600px){
  .collection-stat-grid{
    grid-template-columns:repeat(2,1fr);
  }

  .collection-stat{
    min-height:96px;
  }

  .collection-stat strong{
    font-size:24px;
  }
}
</style>
"""

html = html.replace("</head>", css + "\n</head>", 1)
html = html.replace('<div class="card">', card + '\n<div class="card">', 1)

INDEX.write_text(html, encoding="utf-8")

print("Added Collection Overview to homepage")
print(f"  Tracks: {tracks}")
print(f"  Albums: {albums}")
print(f"  Artists: {len(artists)}")
print(f"  Shows: {shows}")
print(f"  Genres: {len(genres)}")
print(f"  Years: {len(years)}")
