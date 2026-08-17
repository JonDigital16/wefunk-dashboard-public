#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, esc, z_date_short, z_date_sort
from data import show_stats

TEMPLATE = SITE / "episodes.html"
OUT = SITE / "best-matching.html"

if not TEMPLATE.exists():
    raise SystemExit("episodes.html does not exist yet. Run dashboard first.")

template = TEMPLATE.read_text(encoding="utf-8")

ranked = sorted(
    show_stats,
    key=lambda x: float(x.get("match_percent") or 0),
    reverse=True,
)[:250]

top_matches = ranked[:6]

best_percent = max(
    (float(r.get("match_percent") or 0) for r in ranked),
    default=0,
)

most_matched = max(
    (int(r.get("matched_tracks") or 0) for r in ranked),
    default=0,
)

rows = "\n".join(
    f"<tr>"
    f"<td>"
    f"<div class='best-show-cell'>"
    f"<img class='best-show-thumb' src='/episode-art/{esc(r['show_id'])}.jpg' "
    f"loading='lazy' onerror=\"this.style.display='none';\">"
    f"<a class='best-show-link' href='/shows/{esc(r['show_id'])}.html'>Show {esc(r['show_id'])}</a>"
    f"</div>"
    f"</td>"
    f"<td data-sort='{z_date_sort(r['recorded'])}'>{esc(z_date_short(r['recorded']))}</td>"
    f"<td class='best-djs'>{esc(r['djs'])}</td>"
    f"<td>{esc(r['matched_tracks'])}</td>"
    f"<td>{esc(r['total_tracks'])}</td>"
    f"<td data-sort='{esc(r['match_percent'])}'><span class='best-percent'>{esc(r['match_percent'])}%</span></td>"
    f"<td class='best-progress-cell'>"
    f"<div class='best-progress'>"
    f"<div class='best-progress-fill' style='width:{esc(r['match_percent'])}%'></div>"
    f"</div>"
    f"</td>"
    f"</tr>"
    for r in ranked
)

top_cards = "\n".join(
    f"""
    <a class="best-feature-card" href="/shows/{esc(r['show_id'])}.html">
      <div class="best-feature-art">
        <img
          src="/episode-art/{esc(r['show_id'])}.jpg"
          loading="lazy"
          alt="WEFUNK Show {esc(r['show_id'])}"
          onerror="this.style.display='none';"
        >
        <span class="best-feature-rank">#{i}</span>
        <span class="best-feature-percent">{esc(r['match_percent'])}%</span>
      </div>

      <div class="best-feature-body">
        <div class="best-feature-title">Show {esc(r['show_id'])}</div>
        <div class="best-feature-date">{esc(z_date_short(r['recorded']))}</div>
        <div class="best-feature-djs">{esc(r['djs'])}</div>

        <div class="best-feature-trackline">
          <strong>{esc(r['matched_tracks'])}</strong> of
          <strong>{esc(r['total_tracks'])}</strong> tracks matched
        </div>

        <div class="best-feature-progress">
          <div
            class="best-feature-progress-fill"
            style="width:{esc(r['match_percent'])}%"
          ></div>
        </div>
      </div>
    </a>
    """
    for i, r in enumerate(top_matches, start=1)
)

card = f"""
<style>
.best-page {{
  width: min(1800px, calc(100vw - 48px)) !important;
  max-width: none !important;
  margin-left: auto !important;
  margin-right: auto !important;
  box-sizing: border-box;
}}

.best-hero {{
  margin-bottom: 24px;
}}

.best-back {{
  display: inline-block;
  margin-bottom: 18px;
  font-size: 13px;
}}

.best-title-row {{
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}}

.best-title-row h2 {{
  margin: 0 0 6px;
  font-size: 28px;
}}

.best-subtitle {{
  margin: 0;
  color: #aaa;
  line-height: 1.5;
}}

.best-stats {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 20px;
}}

.best-stat {{
  border: 1px solid #2b2f36;
  border-radius: 14px;
  padding: 15px 16px;
  background: rgba(255,255,255,.025);
}}

.best-stat-value {{
  display: block;
  font-size: 1.55rem;
  line-height: 1;
  font-weight: 900;
  color: #fff;
  margin-bottom: 7px;
}}

.best-stat-label {{
  display: block;
  color: #888;
  font-size: .72rem;
  text-transform: uppercase;
  letter-spacing: .07em;
}}

.best-section-heading {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  margin: 26px 0 12px;
}}

.best-section-heading h3 {{
  margin: 0;
  font-size: 15px;
}}

.best-section-note {{
  color: #777;
  font-size: 11px;
}}

.best-feature-grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}}

.best-feature-card {{
  display: block;
  overflow: hidden;
  background: #1b1e23;
  border: 1px solid #2b2f36;
  border-radius: 14px;
  color: #eee;
  text-decoration: none;
  transition:
    transform .16s ease,
    border-color .16s ease,
    box-shadow .16s ease;
}}

.best-feature-card:hover {{
  transform: translateY(-3px);
  border-color: #F7931E;
  box-shadow: 0 12px 30px rgba(0,0,0,.3);
}}

.best-feature-art {{
  position: relative;
  aspect-ratio: 16 / 8.5;
  overflow: hidden;
  background:
    linear-gradient(135deg, #222831, #111419);
}}

.best-feature-art img {{
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}}

.best-feature-art::after {{
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(
      to bottom,
      rgba(0,0,0,.03) 45%,
      rgba(0,0,0,.55) 100%
    );
  pointer-events: none;
}}

.best-feature-rank {{
  position: absolute;
  z-index: 2;
  top: 10px;
  left: 10px;
  padding: 5px 8px;
  border-radius: 999px;
  background: rgba(12,14,17,.84);
  border: 1px solid rgba(255,255,255,.13);
  color: #fff;
  font-size: 11px;
  font-weight: 900;
  backdrop-filter: blur(8px);
}}

.best-feature-percent {{
  position: absolute;
  z-index: 2;
  right: 10px;
  bottom: 10px;
  padding: 6px 9px;
  border-radius: 999px;
  background: rgba(0,208,132,.92);
  color: #08120e;
  font-size: 12px;
  font-weight: 900;
  box-shadow: 0 3px 12px rgba(0,0,0,.3);
}}

.best-feature-body {{
  padding: 13px 14px 14px;
}}

.best-feature-title {{
  color: #6ab7ff;
  font-weight: 900;
  font-size: 15px;
  margin-bottom: 4px;
}}

.best-feature-date {{
  color: #ddd;
  font-size: 12px;
  margin-bottom: 6px;
}}

.best-feature-djs {{
  color: #999;
  font-size: 11px;
  line-height: 1.4;
  min-height: 31px;
}}

.best-feature-trackline {{
  color: #aaa;
  font-size: 11px;
  margin-top: 10px;
}}

.best-feature-trackline strong {{
  color: #eee;
}}

.best-feature-progress {{
  height: 5px;
  margin-top: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: #30343a;
}}

.best-feature-progress-fill {{
  height: 100%;
  border-radius: inherit;
  background: #00d084;
}}

.best-toolbar {{
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 28px 0 14px;
}}

#bestFilter {{
  width: 100%;
  max-width: none;
  box-sizing: border-box;
  padding: 13px 15px;
  border-radius: 11px;
}}

.best-table-wrap {{
  overflow-x: auto;
  border: 1px solid #2b2f36;
  border-radius: 14px;
}}

#bestMatchingShows {{
  margin: 0;
}}

#bestMatchingShows th {{
  white-space: nowrap;
  background: #14171b;
  position: sticky;
  top: 0;
}}

#bestMatchingShows tbody tr {{
  transition: background .12s ease;
}}

#bestMatchingShows tbody tr:hover {{
  background: rgba(255,255,255,.025);
}}

.best-show-cell {{
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 115px;
}}

.best-show-thumb {{
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 9px;
  border: 1px solid #30343a;
  background: #111;
}}

.best-show-link {{
  font-weight: 850;
  white-space: nowrap;
}}

.best-djs {{
  max-width: 360px;
  color: #bbb;
  line-height: 1.4;
}}

.best-percent {{
  display: inline-block;
  min-width: 50px;
  padding: 4px 8px;
  text-align: center;
  border-radius: 999px;
  background: rgba(0,208,132,.11);
  border: 1px solid rgba(0,208,132,.2);
  color: #48dfaa;
  font-weight: 850;
}}

.best-progress-cell {{
  min-width: 150px;
}}

.best-progress {{
  height: 8px;
  width: 100%;
  overflow: hidden;
  border-radius: 999px;
  background: #30343a;
}}

.best-progress-fill {{
  height: 100%;
  border-radius: inherit;
  background: #00d084;
}}

@media (max-width: 900px) {{
  .best-feature-grid {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}
}}

@media (max-width: 700px) {{
  .best-stats {{
    grid-template-columns: 1fr;
  }}

  .best-feature-grid {{
    grid-template-columns: 1fr;
  }}

  .best-section-note {{
    display: none;
  }}

  .best-title-row h2 {{
    font-size: 24px;
  }}
}}
</style>

<div class="card best-page">
  <div class="best-hero">
    <a class="best-back" href="/">← Back</a>

    <div class="best-title-row">
      <div>
        <h2>🏆 Best Matching Shows</h2>
        <p class="best-subtitle">
          WEFUNK episodes ranked by how closely they match your personal music collection.
        </p>
      </div>
    </div>

    <div class="best-stats">
      <div class="best-stat">
        <span class="best-stat-value">{len(ranked):,}</span>
        <span class="best-stat-label">Top Shows Ranked</span>
      </div>

      <div class="best-stat">
        <span class="best-stat-value">{best_percent:.1f}%</span>
        <span class="best-stat-label">Highest Match</span>
      </div>

      <div class="best-stat">
        <span class="best-stat-value">{most_matched:,}</span>
        <span class="best-stat-label">Most Tracks Matched</span>
      </div>
    </div>

    <div class="best-section-heading">
      <h3>🔥 Your Top Matches</h3>
      <span class="best-section-note">
        Episodes with the strongest collection overlap
      </span>
    </div>

    <div class="best-feature-grid">
      {top_cards}
    </div>

    <div class="best-toolbar">
      <input
        id="bestFilter"
        placeholder="Search show, date, DJ, or match..."
        oninput="filterTable('bestFilter','bestMatchingShows')"
      >
    </div>
  </div>

  <div class="best-table-wrap">
    <table id="bestMatchingShows">
      <thead>
        <tr>
          <th onclick="sortTable('bestMatchingShows',0,true)">Show</th>
          <th onclick="sortTable('bestMatchingShows',1)">Date</th>
          <th onclick="sortTable('bestMatchingShows',2)">DJs</th>
          <th onclick="sortTable('bestMatchingShows',3,true)">Matched</th>
          <th onclick="sortTable('bestMatchingShows',4,true)">Total</th>
          <th onclick="sortTable('bestMatchingShows',5,true)">Match %</th>
          <th>Match Strength</th>
        </tr>
      </thead>

      <tbody>
        {rows}
      </tbody>
    </table>
  </div>
</div>
"""

start = template.find('<div class="card">')
end = template.rfind("</body>")

if start == -1 or end == -1:
    raise SystemExit("Could not locate replacement area in episodes.html")

page = template[:start] + card + "\n" + template[end:]

OUT.write_text(page, encoding="utf-8")

print(f"Wrote: {OUT}")
print(f"Ranked shows: {len(ranked)}")
print(f"Highest match: {best_percent:.1f}%")
print(f"Most tracks matched: {most_matched}")
