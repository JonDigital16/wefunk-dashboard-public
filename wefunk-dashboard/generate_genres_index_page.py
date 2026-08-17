#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, esc, slugify
from data import genre_dna

TEMPLATE = SITE / "dna.html"
OUT = SITE / "genres.html"

if not TEMPLATE.exists():
    raise SystemExit(
        "dna.html does not exist yet. Run the dashboard build first."
    )

template = TEMPLATE.read_text(encoding="utf-8")

genres = []

for row in genre_dna:
    genre = str(row.get("genre") or "").strip()

    try:
        count = int(row.get("count") or 0)
    except (TypeError, ValueError):
        count = 0

    if genre and count > 0:
        genres.append(
            {
                "genre": genre,
                "count": count,
                "slug": slugify(genre),
            }
        )

genres.sort(
    key=lambda item: (
        -item["count"],
        item["genre"].lower(),
    )
)

top_genres = genres[:20]
remaining_genres = genres[20:]

total_tracks = sum(item["count"] for item in genres)
largest_count = top_genres[0]["count"] if top_genres else 1


def tile_size(index, count):
    if index == 0:
        return "genre-tile-xl"

    if index in {1, 2}:
        return "genre-tile-lg"

    if index <= 7:
        return "genre-tile-md"

    return "genre-tile-sm"


heat_tiles = []

for index, item in enumerate(top_genres):
    percentage = (
        item["count"] / total_tracks * 100
        if total_tracks
        else 0
    )

    intensity = (
        0.18 + 0.68 * (item["count"] / largest_count)
        if largest_count
        else 0.18
    )

    heat_tiles.append(
        f"""
<a
  class="genre-heat-tile {tile_size(index, item['count'])}"
  href="/genres/{esc(item['slug'])}.html"
  style="--genre-heat:{intensity:.3f};"
>
  <strong>{esc(item['genre'])}</strong>

  <span class="genre-heat-count">
    {item['count']:,} matched tracks
  </span>

  <span class="genre-heat-percent">
    {percentage:.1f}% of tagged matches
  </span>
</a>
"""
    )

remaining_rows = "\n".join(
    f"<tr>"
    f"<td>"
    f"<a href='/genres/{esc(item['slug'])}.html'>"
    f"{esc(item['genre'])}"
    f"</a>"
    f"</td>"
    f"<td data-sort='{item['count']}'>"
    f"{item['count']:,}"
    f"</td>"
    f"<td data-sort='{item['count']}'>"
    f"{(item['count'] / total_tracks * 100 if total_tracks else 0):.1f}%"
    f"</td>"
    f"</tr>"
    for item in remaining_genres
)

if not remaining_rows:
    remaining_rows = """
<tr>
  <td colspan="3">All genres are currently shown in the map.</td>
</tr>
"""

heatmap_card = f"""
<div class="card genre-map-card">
  <p><a href="/">← Back</a></p>

  <div class="genre-map-heading">
    <div>
      <h2>🧬 Genre Map</h2>

      <p class="small">
        A visual fingerprint of the strongest genres in your matched
        WEFUNK collection.
      </p>

      <p class="genre-map-note">
        Showing top 20 genres by representation.
      </p>
    </div>

    <div class="genre-map-summary">
      <strong>{len(genres):,}</strong>
      <span>Total Genres</span>
    </div>
  </div>

  <div class="genre-heat-grid">
    {''.join(heat_tiles)}
  </div>
</div>
"""

remaining_card = f"""
<div class="card genre-remainder-card">
  <div class="genre-remainder-heading">
    <div>
      <h2>More Genres</h2>

      <p class="small">
        Smaller genre groups represented in your matched WEFUNK tracks.
      </p>
    </div>

    <div class="genre-remainder-count">
      {len(remaining_genres):,} genres
    </div>
  </div>

  <input
    id="genreIndexFilter"
    placeholder="Filter remaining genres..."
    oninput="filterTable('genreIndexFilter','genreIndex')"
  >

  <table id="genreIndex">
    <thead>
      <tr>
        <th onclick="sortTable('genreIndex',0)">Genre</th>

        <th onclick="sortTable('genreIndex',1,true)">
          Matched Tracks
        </th>

        <th onclick="sortTable('genreIndex',2,true)">
          Share
        </th>
      </tr>
    </thead>

    <tbody>
      {remaining_rows}
    </tbody>
  </table>
</div>
"""

css = """
<style>
.genre-map-heading,
.genre-remainder-heading{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:20px;
  margin-bottom:20px;
}

.genre-map-heading h2,
.genre-remainder-heading h2{
  margin-bottom:4px;
}

.genre-map-note{
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

.genre-map-summary{
  display:flex;
  min-width:108px;
  flex-direction:column;
  align-items:center;
  padding:12px 16px;
  border:1px solid #2b2f36;
  border-radius:14px;
  background:#171a1f;
}

.genre-map-summary strong{
  color:#F7931E;
  font-size:26px;
  line-height:1;
}

.genre-map-summary span{
  margin-top:7px;
  color:#aaa;
  font-size:12px;
  font-weight:700;
}

.genre-heat-grid{
  display:grid;
  grid-auto-flow:dense;
  grid-auto-rows:118px;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:12px;
}

.genre-heat-tile{
  display:flex;
  min-width:0;
  min-height:118px;
  flex-direction:column;
  justify-content:center;
  padding:16px;
  overflow:hidden;
  border:1px solid rgba(247,147,30,.34);
  border-radius:16px;
  background:
    linear-gradient(
      145deg,
      rgba(247,147,30,var(--genre-heat)),
      rgba(23,26,31,.97) 78%
    );
  color:#f5f5f5;
  text-decoration:none;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.04);
  transition:
    transform .18s ease,
    border-color .18s ease,
    box-shadow .18s ease;
}

.genre-heat-tile:hover{
  transform:translateY(-3px);
  border-color:#F7931E;
  box-shadow:0 14px 34px rgba(0,0,0,.32);
}

.genre-heat-tile strong{
  display:block;
  max-width:100%;
  overflow-wrap:break-word;
  font-size:16px;
  line-height:1.2;
}

.genre-heat-count{
  margin-top:8px;
  color:#eee;
  font-size:12px;
  font-weight:800;
}

.genre-heat-percent{
  margin-top:4px;
  color:#bbb;
  font-size:11px;
}

.genre-tile-xl{
  grid-column:span 2;
  grid-row:span 2;
  min-height:248px;
}

.genre-tile-xl strong{
  font-size:28px;
}

.genre-tile-lg{
  grid-column:span 2;
  grid-row:span 1;
}

.genre-tile-lg strong{
  font-size:20px;
}

.genre-tile-md{
  grid-column:span 1;
  grid-row:span 1;
}

.genre-tile-sm{
  grid-column:span 1;
  grid-row:span 1;
}

.genre-remainder-count{
  flex-shrink:0;
  padding:7px 11px;
  border:1px solid #2b2f36;
  border-radius:999px;
  color:#aaa;
  font-size:12px;
  font-weight:800;
}

@media(max-width:1000px){
  .genre-heat-grid{
    grid-template-columns:repeat(3,minmax(0,1fr));
  }

  .genre-tile-xl,
  .genre-tile-lg{
    grid-column:span 2;
  }
}

@media(max-width:700px){
  .genre-map-heading,
  .genre-remainder-heading{
    flex-direction:column;
  }

  .genre-heat-grid{
    grid-auto-rows:112px;
    grid-template-columns:repeat(2,minmax(0,1fr));
  }

  .genre-tile-xl,
  .genre-tile-lg{
    grid-column:span 2;
  }

  .genre-tile-xl{
    grid-row:span 2;
    min-height:236px;
  }

  .genre-tile-md,
  .genre-tile-sm{
    grid-column:span 1;
    grid-row:span 1;
  }

  .genre-heat-tile{
    padding:14px;
  }

  .genre-heat-tile strong{
    font-size:14px;
  }
}
</style>
"""

start = template.find('<div class="card">')
end = template.rfind("</body>")

if start == -1 or end == -1:
    raise SystemExit(
        "Could not locate page-content boundaries in template."
    )

page = (
    template[:start]
    + heatmap_card
    + "\n"
    + remaining_card
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
print(f"Total genres: {len(genres)}")
print(f"Genres displayed in map: {len(top_genres)}")
print(f"Genres displayed in table: {len(remaining_genres)}")
print(f"Tagged matches: {total_tracks}")
