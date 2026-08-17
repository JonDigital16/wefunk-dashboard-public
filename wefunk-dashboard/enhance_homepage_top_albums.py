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
SOURCE = EXPORTS / "wefunk_album_index.csv"

if not INDEX.exists():
    raise SystemExit("index.html does not exist")

if not SOURCE.exists():
    raise SystemExit("wefunk_album_index.csv does not exist")

homepage = INDEX.read_text(encoding="utf-8")

if 'id="homepageTopAlbums"' in homepage:
    print("Homepage Top Albums already present")
    raise SystemExit(0)

albums = []

with SOURCE.open(newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        try:
            tracks = int(row.get("tracks") or 0)
        except ValueError:
            tracks = 0

        albums.append({
            "artist": (row.get("artist") or "").strip(),
            "album": (row.get("album") or "").strip(),
            "slug": (row.get("slug") or "").strip(),
            "genre": (row.get("genre") or "").strip(),
            "year": (row.get("year") or "").strip()[:4],
            "tracks": tracks,
        })

top_albums = sorted(
    albums,
    key=lambda item: (
        -item["tracks"],
        item["artist"].lower(),
        item["album"].lower(),
    ),
)[:10]

cards = []

for album in top_albums:
    slug = album["slug"]
    artist = album["artist"]
    title = album["album"]
    genre = album["genre"]
    year = album["year"]
    tracks = album["tracks"]

    meta = " · ".join(
        part for part in [year, genre] if part
    )

    cards.append(f"""
<a class="homepage-album-row" href="/albums/{slug}.html">
  <img
    src="/covers/{slug}.jpg"
    loading="lazy"
    onerror="this.style.display='none';"
    alt=""
  >

  <div class="homepage-album-row-body">
    <div class="homepage-album-row-title">{title}</div>
    <div class="homepage-album-row-artist">{artist}</div>
    <div class="homepage-album-row-meta">{meta}</div>
  </div>

  <div class="homepage-album-row-count">
    {tracks:,}
    <span>tracks</span>
  </div>
</a>
""")

section = f"""
<div class="card homepage-top-albums" id="homepageTopAlbums">
  <div class="homepage-albums-heading">
    <div>
      <h2>💿 Top Albums</h2>
      <p class="small">
        Albums with the most matched WEFUNK tracks.
      </p>
    </div>

    <a class="homepage-albums-link" href="/albums.html">
      View all →
    </a>
  </div>

  <div class="homepage-album-list">
    {''.join(cards)}
  </div>
</div>
"""

css = """
<style>
.homepage-albums-heading{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:18px;
  margin-bottom:18px;
}

.homepage-albums-heading h2{
  margin-bottom:4px;
}

.homepage-albums-link{
  flex-shrink:0;
  padding:8px 12px;
  border:1px solid #2b2f36;
  border-radius:999px;
  color:#F7931E;
  font-size:13px;
  font-weight:800;
  text-decoration:none;
}

.homepage-albums-link:hover{
  border-color:#F7931E;
  background:#F7931E;
  color:#111;
}

.homepage-album-list{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:12px;
}

.homepage-album-row{
  display:grid;
  grid-template-columns:72px minmax(0,1fr) auto;
  align-items:center;
  gap:12px;
  min-height:72px;
  overflow:hidden;
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

.homepage-album-row:hover{
  transform:translateY(-2px);
  border-color:#F7931E;
  box-shadow:0 12px 28px rgba(0,0,0,.25);
}

.homepage-album-row img{
  display:block;
  width:72px;
  height:72px;
  object-fit:cover;
  background:#0f1115;
}

.homepage-album-row-body{
  min-width:0;
  padding:9px 0;
}

.homepage-album-row-title{
  overflow:hidden;
  font-size:14px;
  font-weight:900;
  line-height:1.2;
  text-overflow:ellipsis;
  white-space:nowrap;
}

.homepage-album-row-artist{
  margin-top:4px;
  overflow:hidden;
  color:#F7931E;
  font-size:12px;
  font-weight:800;
  text-overflow:ellipsis;
  white-space:nowrap;
}

.homepage-album-row-meta{
  margin-top:4px;
  overflow:hidden;
  color:#888;
  font-size:11px;
  text-overflow:ellipsis;
  white-space:nowrap;
}

.homepage-album-row-count{
  padding:0 14px 0 4px;
  color:#F7931E;
  font-size:16px;
  font-weight:900;
  text-align:right;
}

.homepage-album-row-count span{
  display:block;
  margin-top:2px;
  color:#777;
  font-size:10px;
  font-weight:700;
  text-transform:uppercase;
}

@media(max-width:800px){
  .homepage-album-list{
    grid-template-columns:1fr;
  }
}

@media(max-width:600px){
  .homepage-albums-heading{
    display:block;
  }

  .homepage-albums-link{
    display:inline-block;
    margin-top:10px;
  }

  .homepage-album-row{
    grid-template-columns:64px minmax(0,1fr) auto;
    min-height:64px;
  }

  .homepage-album-row img{
    width:64px;
    height:64px;
  }
}
</style>
"""

homepage = homepage.replace(
    "</head>",
    css + "\n</head>",
    1,
)

marker = homepage.find('id="homepageTopArtists"')

if marker == -1:
    raise SystemExit("Top Artists section not found")

insert_at = homepage.find(
    '\n<div class="card">',
    marker,
)

if insert_at == -1:
    raise SystemExit("Could not find insertion point after Top Artists")

homepage = (
    homepage[:insert_at]
    + "\n"
    + section
    + homepage[insert_at:]
)

INDEX.write_text(homepage, encoding="utf-8")

print(f"Added {len(top_albums)} compact Top Album rows to homepage")
