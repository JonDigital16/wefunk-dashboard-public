#!/usr/bin/env python3

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, esc
from data import owned_tracks_enriched

TEMPLATE = SITE / "episodes.html"
OUT = SITE / "years.html"

if not TEMPLATE.exists():
    raise SystemExit(
        "episodes.html does not exist yet. Run the dashboard build first."
    )

template = TEMPLATE.read_text(encoding="utf-8")

years = defaultdict(list)

for row in owned_tracks_enriched:
    raw = str(row.get("matched_year") or "").strip()
    match = re.search(r"\d{4}", raw)

    if match:
        years[match.group(0)].append(row)


year_data = [
    {
        "year": year,
        "count": len(items),
    }
    for year, items in years.items()
    if items
]

# Most represented years drive the visual map.
years_by_count = sorted(
    year_data,
    key=lambda item: (
        -item["count"],
        -int(item["year"]),
    ),
)

top_years = years_by_count[:20]
top_year_values = {
    item["year"]
    for item in top_years
}

# The remaining table is more useful chronologically.
remaining_years = sorted(
    [
        item
        for item in year_data
        if item["year"] not in top_year_values
    ],
    key=lambda item: int(item["year"]),
    reverse=True,
)

total_tracks = sum(
    item["count"]
    for item in year_data
)

largest_count = (
    top_years[0]["count"]
    if top_years
    else 1
)


def tile_size(index):
    if index == 0:
        return "year-tile-xl"

    if index in {1, 2}:
        return "year-tile-lg"

    if index <= 7:
        return "year-tile-md"

    return "year-tile-sm"


heat_tiles = []

for index, item in enumerate(top_years):
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
  class="year-heat-tile {tile_size(index)}"
  href="/years/{esc(item['year'])}.html"
  style="--year-heat:{intensity:.3f};"
>
  <strong>{esc(item['year'])}</strong>

  <span class="year-heat-count">
    {item['count']:,} matched tracks
  </span>

  <span class="year-heat-percent">
    {percentage:.1f}% of dated matches
  </span>
</a>
"""
    )


remaining_rows = "\n".join(
    f"<tr>"
    f"<td>"
    f"<a href='/years/{esc(item['year'])}.html'>"
    f"{esc(item['year'])}"
    f"</a>"
    f"</td>"
    f"<td data-sort='{item['count']}'>"
    f"{item['count']:,}"
    f"</td>"
    f"<td data-sort='{item['count']}'>"
    f"{(item['count'] / total_tracks * 100 if total_tracks else 0):.1f}%"
    f"</td>"
    f"</tr>"
    for item in remaining_years
)

if not remaining_rows:
    remaining_rows = """
<tr>
  <td colspan="3">
    All years are currently shown in the map.
  </td>
</tr>
"""


year_map_card = f"""
<div class="card year-map-card">
  <p><a href="/">← Back</a></p>

  <div class="year-map-heading">
    <div>
      <h2>📅 Year Map</h2>

      <p class="small">
        A visual timeline of the strongest release years in your matched
        WEFUNK collection.
      </p>

      <p class="year-map-note">
        Showing top 20 years by representation.
      </p>
    </div>

    <div class="year-map-summary">
      <strong>{len(year_data):,}</strong>
      <span>Total Years</span>
    </div>
  </div>

  <div class="year-heat-grid">
    {''.join(heat_tiles)}
  </div>
</div>
"""


remaining_card = f"""
<div class="card year-remainder-card">
  <div class="year-remainder-heading">
    <div>
      <h2>More Years</h2>

      <p class="small">
        Additional release years represented in your matched WEFUNK tracks.
      </p>
    </div>

    <div class="year-remainder-count">
      {len(remaining_years):,} years
    </div>
  </div>

  <input
    id="yearFilter"
    placeholder="Filter remaining years..."
    oninput="filterTable('yearFilter','yearIndex')"
  >

  <table id="yearIndex">
    <thead>
      <tr>
        <th onclick="sortTable('yearIndex',0,true)">
          Year
        </th>

        <th onclick="sortTable('yearIndex',1,true)">
          Matched Tracks
        </th>

        <th onclick="sortTable('yearIndex',2,true)">
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
.year-map-heading,
.year-remainder-heading{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:20px;
  margin-bottom:20px;
}

.year-map-heading h2,
.year-remainder-heading h2{
  margin-bottom:4px;
}

.year-map-note{
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

.year-map-summary{
  display:flex;
  min-width:108px;
  flex-direction:column;
  align-items:center;
  padding:12px 16px;
  border:1px solid #2b2f36;
  border-radius:14px;
  background:#171a1f;
}

.year-map-summary strong{
  color:#F7931E;
  font-size:26px;
  line-height:1;
}

.year-map-summary span{
  margin-top:7px;
  color:#aaa;
  font-size:12px;
  font-weight:700;
}

.year-heat-grid{
  display:grid;
  grid-auto-flow:dense;
  grid-auto-rows:118px;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:12px;
}

.year-heat-tile{
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
      rgba(247,147,30,var(--year-heat)),
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

.year-heat-tile:hover{
  transform:translateY(-3px);
  border-color:#F7931E;
  box-shadow:0 14px 34px rgba(0,0,0,.32);
}

.year-heat-tile strong{
  display:block;
  max-width:100%;
  font-size:22px;
  line-height:1.1;
}

.year-heat-count{
  margin-top:8px;
  color:#eee;
  font-size:12px;
  font-weight:800;
}

.year-heat-percent{
  margin-top:4px;
  color:#bbb;
  font-size:11px;
}

.year-tile-xl{
  grid-column:span 2;
  grid-row:span 2;
  min-height:248px;
}

.year-tile-xl strong{
  font-size:42px;
}

.year-tile-xl .year-heat-count{
  font-size:15px;
}

.year-tile-xl .year-heat-percent{
  font-size:13px;
}

.year-tile-lg{
  grid-column:span 2;
}

.year-tile-lg strong{
  font-size:30px;
}

.year-tile-md strong{
  font-size:24px;
}

.year-remainder-count{
  flex:0 0 auto;
  padding:7px 11px;
  border:1px solid #2b2f36;
  border-radius:999px;
  background:#171a1f;
  color:#aaa;
  font-size:12px;
  font-weight:800;
}

.year-remainder-card input{
  width:100%;
  margin-bottom:14px;
}

.year-remainder-card table a{
  color:#f5f5f5;
  font-weight:800;
  text-decoration:none;
}

.year-remainder-card table a:hover{
  color:#F7931E;
}

@media(max-width:900px){
  .year-heat-grid{
    grid-template-columns:repeat(2,minmax(0,1fr));
  }
}

@media(max-width:600px){
  .year-map-heading,
  .year-remainder-heading{
    display:block;
  }

  .year-map-summary{
    width:max-content;
    min-width:100px;
    margin-top:14px;
  }

  .year-remainder-count{
    display:inline-block;
    margin-top:12px;
  }

  .year-heat-grid{
    grid-auto-rows:104px;
    grid-template-columns:repeat(2,minmax(0,1fr));
    gap:9px;
  }

  .year-heat-tile{
    min-height:104px;
    padding:13px;
  }

  .year-tile-xl{
    grid-column:span 2;
    grid-row:span 2;
    min-height:217px;
  }

  .year-tile-lg{
    grid-column:span 2;
  }

  .year-tile-xl strong{
    font-size:36px;
  }

  .year-tile-lg strong{
    font-size:28px;
  }

  .year-heat-tile strong{
    font-size:21px;
  }
}
</style>
"""


content = (
    year_map_card
    + "\n"
    + remaining_card
)

start = template.find('<div class="card">')
end = template.rfind("</body>")

if start == -1 or end == -1:
    raise SystemExit(
        "Could not locate page content boundaries."
    )

page = (
    template[:start]
    + content
    + "\n"
    + template[end:]
)

page = page.replace(
    "</head>",
    css + "\n</head>",
    1,
)

OUT.write_text(
    page,
    encoding="utf-8",
)

print(f"Wrote: {OUT}")
print(f"Total years: {len(year_data):,}")
print(f"Years displayed in map: {len(top_years):,}")
print(f"Years displayed in table: {len(remaining_years):,}")
print(f"Dated matches: {total_tracks:,}")
