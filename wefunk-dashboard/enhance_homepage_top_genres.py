#!/usr/bin/env python3

import csv
import os
from collections import Counter
from pathlib import Path

from common import slugify

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

if 'id="homepageTopGenres"' in homepage:
    print("Homepage Top Genres already present")
    raise SystemExit(0)

genres = Counter()

with SOURCE.open(newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        genre = (row.get("matched_genre") or "").strip()

        if genre:
            genres[genre] += 1

top_genres = genres.most_common(8)
largest = top_genres[0][1] if top_genres else 1

rows = []

for genre, count in top_genres:
    width = max(4, round((count / largest) * 100))

    rows.append(f"""
<a class="homepage-genre-row" href="/genres/{slugify(genre)}.html">
  <div class="homepage-genre-heading">
    <strong>{genre}</strong>
    <span>{count:,} tracks</span>
  </div>

  <div class="homepage-genre-progress">
    <div style="width:{width}%"></div>
  </div>
</a>
""")

section = f"""
<div class="card homepage-top-genres" id="homepageTopGenres">
  <div class="homepage-genres-heading">
    <div>
      <h2>🧬 Top Genres</h2>
      <p class="small">
        The most represented genres in your matched collection.
      </p>
    </div>

    <a class="homepage-genres-link" href="/genres.html">
      View all →
    </a>
  </div>

  <div class="homepage-genres-grid">
    {''.join(rows)}
  </div>
</div>
"""

css = """
<style>
.homepage-genres-heading{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:18px;
  margin-bottom:18px;
}

.homepage-genres-heading h2{
  margin-bottom:4px;
}

.homepage-genres-link{
  flex-shrink:0;
  padding:8px 12px;
  border:1px solid #2b2f36;
  border-radius:999px;
  color:#F7931E;
  font-size:13px;
  font-weight:800;
  text-decoration:none;
}

.homepage-genres-link:hover{
  border-color:#F7931E;
  background:#F7931E;
  color:#111;
}

.homepage-genres-grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:14px;
}

.homepage-genre-row{
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

.homepage-genre-row:hover{
  transform:translateY(-2px);
  border-color:#F7931E;
  box-shadow:0 12px 30px rgba(0,0,0,.25);
}

.homepage-genre-heading{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
}

.homepage-genre-heading strong{
  font-size:14px;
}

.homepage-genre-heading span{
  color:#999;
  font-size:12px;
}

.homepage-genre-progress{
  height:8px;
  margin-top:12px;
  overflow:hidden;
  border-radius:999px;
  background:#2b2f36;
}

.homepage-genre-progress div{
  height:100%;
  border-radius:999px;
  background:#F7931E;
}

@media(max-width:650px){
  .homepage-genres-heading{
    display:block;
  }

  .homepage-genres-link{
    display:inline-block;
    margin-top:10px;
  }

  .homepage-genres-grid{
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

marker = homepage.find('id="homepageCollectionGoals"')

if marker == -1:
    raise SystemExit("Collection Goals section not found")

insert_at = homepage.find(
    '\n<div class="card">',
    marker,
)

if insert_at == -1:
    raise SystemExit("Could not find insertion point after Collection Goals")

homepage = (
    homepage[:insert_at]
    + "\n"
    + section
    + homepage[insert_at:]
)

INDEX.write_text(homepage, encoding="utf-8")

print(f"Added {len(top_genres)} Top Genre rows to homepage")
