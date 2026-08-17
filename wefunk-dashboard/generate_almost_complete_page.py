#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, esc, z_date_short, z_date_sort
from data import show_stats

TEMPLATE = SITE / "episodes.html"
OUT = SITE / "almost-complete.html"

if not TEMPLATE.exists():
    raise SystemExit("episodes.html does not exist yet. Run dashboard first.")

template = TEMPLATE.read_text(encoding="utf-8")


def missing_count(row):
    try:
        return int(row.get("total_tracks") or 0) - int(row.get("matched_tracks") or 0)
    except Exception:
        return 9999


almost = [
    r for r in show_stats
    if 0 < missing_count(r) <= 10
]

almost = sorted(
    almost,
    key=lambda r: (
        missing_count(r),
        -float(r.get("match_percent") or 0),
    )
)

# ---------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------

one_away = sum(1 for r in almost if missing_count(r) == 1)
three_away = sum(1 for r in almost if missing_count(r) <= 3)

best_percent = max(
    (float(r.get("match_percent") or 0) for r in almost),
    default=0,
)

# ---------------------------------------------------------------------
# Featured cards
# ---------------------------------------------------------------------

featured_cards = []

for r in almost[:12]:
    show_id = esc(r["show_id"])
    recorded = esc(z_date_short(r["recorded"]))
    djs = esc(r.get("djs") or "")
    matched = esc(r.get("matched_tracks") or 0)
    total = esc(r.get("total_tracks") or 0)
    percent = esc(r.get("match_percent") or 0)
    missing = missing_count(r)

    missing_label = (
        "1 track missing"
        if missing == 1
        else f"{missing} tracks missing"
    )

    featured_cards.append(
        f"""
<a class="almost-feature-card" href="/shows/{show_id}.html">
  <div class="almost-feature-image">
    <img
      src="/episode-art/{show_id}.jpg"
      loading="lazy"
      alt="WEFUNK Show {show_id}"
      onerror="this.style.display='none';this.parentElement.classList.add('image-missing');"
    >
    <span class="almost-missing-badge">{esc(missing_label)}</span>
  </div>

  <div class="almost-feature-body">
    <div class="almost-feature-heading">
      <strong>Show {show_id}</strong>
      <span>{percent}%</span>
    </div>

    <div class="almost-feature-date">{recorded}</div>
    <div class="almost-feature-djs">{djs}</div>

    <div class="almost-feature-progress">
      <div
        class="almost-feature-progress-fill"
        style="width:{percent}%"
      ></div>
    </div>

    <div class="almost-feature-stats">
      {matched} of {total} tracks matched
    </div>
  </div>
</a>
"""
    )

# ---------------------------------------------------------------------
# Full table
# ---------------------------------------------------------------------

rows = "\n".join(
    f"<tr>"
    f"<td class='almost-show-cell'>"
    f"<img src='/episode-art/{esc(r['show_id'])}.jpg' "
    f"loading='lazy' "
    f"onerror=\"this.style.display='none';\">"
    f"<a href='/shows/{esc(r['show_id'])}.html'>Show {esc(r['show_id'])}</a>"
    f"</td>"
    f"<td data-sort='{z_date_sort(r['recorded'])}'>{esc(z_date_short(r['recorded']))}</td>"
    f"<td class='almost-djs'>{esc(r['djs'])}</td>"
    f"<td data-sort='{esc(r['matched_tracks'])}'>{esc(r['matched_tracks'])}/{esc(r['total_tracks'])}</td>"
    f"<td data-sort='{esc(r['match_percent'])}'><strong>{esc(r['match_percent'])}%</strong></td>"
    f"<td data-sort='{missing_count(r)}'>"
    f"<span class='almost-missing-count'>{missing_count(r)}</span>"
    f"</td>"
    f"<td class='almost-progress-cell'>"
    f"<div class='almost-progress'>"
    f"<div class='almost-progress-fill' style='width:{esc(r['match_percent'])}%'></div>"
    f"</div>"
    f"</td>"
    f"</tr>"
    for r in almost[:250]
)

card = f"""
<style>
.almost-page {{
  width: calc(100vw - 72px);
  max-width: none;
  margin-left: calc(50% - 50vw + 36px);
  margin-right: calc(50% - 50vw + 36px);
  box-sizing: border-box;
}}

.almost-hero {{
  padding: 8px 4px 4px;
}}

.almost-back {{
  display: inline-block;
  margin-bottom: 12px;
}}

.almost-title-row {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}}

.almost-title-row h2 {{
  margin: 0;
  color: #F7931E;
  font-size: clamp(30px, 3vw, 46px);
}}

.almost-subtitle {{
  margin: 8px 0 0;
  color: #aaa;
  font-size: 15px;
  line-height: 1.5;
}}

.almost-stats {{
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 14px;
  margin-top: 24px;
}}

.almost-stat {{
  background: #101214;
  border: 1px solid #2b2f36;
  border-radius: 14px;
  padding: 16px 18px;
}}

.almost-stat-value {{
  display: block;
  color: #F7931E;
  font-size: 28px;
  line-height: 1;
  font-weight: 900;
}}

.almost-stat-label {{
  display: block;
  margin-top: 7px;
  color: #aaa;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .04em;
}}

.almost-feature-section {{
  margin-top: 30px;
}}

.almost-section-heading {{
  margin-bottom: 14px;
}}

.almost-section-heading h3 {{
  margin: 0;
  color: #f5f5f5;
  font-size: 21px;
}}

.almost-section-heading p {{
  margin: 5px 0 0;
  color: #888;
  font-size: 13px;
}}

.almost-feature-grid {{
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 16px;
}}

.almost-feature-card {{
  min-width: 0;
  overflow: hidden;
  display: block;
  background: #101214;
  border: 1px solid #2b2f36;
  border-radius: 16px;
  color: #f5f5f5;
  text-decoration: none;
  transition:
    transform .18s ease,
    border-color .18s ease,
    box-shadow .18s ease;
}}

.almost-feature-card:hover {{
  transform: translateY(-4px);
  border-color: #F7931E;
  box-shadow: 0 14px 34px rgba(0,0,0,.32);
}}

.almost-feature-image {{
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  overflow: hidden;
  background:
    radial-gradient(circle at 30% 25%, rgba(247,147,30,.25), transparent 45%),
    #111419;
}}

.almost-feature-image img {{
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform .22s ease;
}}

.almost-feature-card:hover .almost-feature-image img {{
  transform: scale(1.035);
}}

.almost-missing-badge {{
  position: absolute;
  left: 10px;
  bottom: 10px;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(16,18,20,.92);
  border: 1px solid rgba(247,147,30,.7);
  color: #F7931E;
  font-size: 11px;
  font-weight: 900;
  backdrop-filter: blur(8px);
}}

.almost-feature-body {{
  padding: 13px;
}}

.almost-feature-heading {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}}

.almost-feature-heading strong {{
  color: #fff;
  font-size: 16px;
}}

.almost-feature-heading span {{
  color: #F7931E;
  font-size: 13px;
  font-weight: 900;
}}

.almost-feature-date {{
  margin-top: 5px;
  color: #aaa;
  font-size: 12px;
}}

.almost-feature-djs {{
  margin-top: 7px;
  color: #ccc;
  font-size: 12px;
  line-height: 1.4;
  min-height: 34px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}

.almost-feature-progress {{
  height: 7px;
  margin-top: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: #292d33;
}}

.almost-feature-progress-fill {{
  height: 100%;
  border-radius: inherit;
  background: #00d084;
}}

.almost-feature-stats {{
  margin-top: 7px;
  color: #888;
  font-size: 11px;
}}

.almost-toolbar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 30px 0 14px;
}}

.almost-toolbar h3 {{
  margin: 0;
  font-size: 20px;
}}

#almostFilter {{
  width: min(520px, 100%);
  max-width: none;
  box-sizing: border-box;
}}

.almost-table-wrap {{
  width: 100%;
  overflow-x: auto;
}}

#almostComplete {{
  width: 100%;
  table-layout: auto;
}}

#almostComplete td {{
  vertical-align: middle;
}}

.almost-show-cell {{
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 145px;
}}

.almost-show-cell img {{
  width: 48px;
  height: 48px;
  flex: 0 0 48px;
  object-fit: cover;
  border-radius: 9px;
  background: #101214;
}}

.almost-show-cell a {{
  font-weight: 800;
}}

.almost-djs {{
  min-width: 220px;
  max-width: 420px;
  line-height: 1.4;
}}

.almost-missing-count {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  padding: 0 7px;
  box-sizing: border-box;
  border-radius: 999px;
  background: rgba(247,147,30,.12);
  border: 1px solid rgba(247,147,30,.35);
  color: #F7931E;
  font-weight: 900;
}}

.almost-progress-cell {{
  width: 18%;
  min-width: 150px;
}}

.almost-progress {{
  width: 100%;
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: #292d33;
}}

.almost-progress-fill {{
  height: 100%;
  border-radius: inherit;
  background: #00d084;
}}

@media (max-width: 1250px) {{
  .almost-feature-grid {{
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }}
}}

@media (max-width: 900px) {{
  .almost-page {{
    width: calc(100vw - 36px);
    margin-left: calc(50% - 50vw + 18px);
    margin-right: calc(50% - 50vw + 18px);
  }}

  .almost-stats {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}

  .almost-feature-grid {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}

  .almost-toolbar {{
    align-items: stretch;
    flex-direction: column;
  }}
}}

@media (max-width: 560px) {{
  .almost-stats {{
    grid-template-columns: 1fr 1fr;
  }}

  .almost-feature-grid {{
    grid-template-columns: 1fr;
  }}
}}
</style>

<div class="card almost-page">
  <div class="almost-hero">
    <a class="almost-back" href="/">← Back</a>

    <div class="almost-title-row">
      <div>
        <h2>Almost Complete Shows</h2>
        <p class="almost-subtitle">
          The WEFUNK episodes closest to completion, ranked by the
          fewest tracks still missing from your collection.
        </p>
      </div>
    </div>

    <div class="almost-stats">
      <div class="almost-stat">
        <span class="almost-stat-value">{len(almost):,}</span>
        <span class="almost-stat-label">Almost Complete</span>
      </div>

      <div class="almost-stat">
        <span class="almost-stat-value">{one_away:,}</span>
        <span class="almost-stat-label">Only 1 Track Away</span>
      </div>

      <div class="almost-stat">
        <span class="almost-stat-value">{three_away:,}</span>
        <span class="almost-stat-label">3 Tracks or Less</span>
      </div>

      <div class="almost-stat">
        <span class="almost-stat-value">{best_percent:.1f}%</span>
        <span class="almost-stat-label">Highest Match</span>
      </div>
    </div>

    <section class="almost-feature-section">
      <div class="almost-section-heading">
        <h3>Closest to Complete</h3>
        <p>Your 12 best opportunities to finish an entire WEFUNK episode.</p>
      </div>

      <div class="almost-feature-grid">
        {''.join(featured_cards)}
      </div>
    </section>

    <div class="almost-toolbar">
      <h3>All Almost Complete Shows</h3>

      <input
        id="almostFilter"
        placeholder="Filter by show, date, DJ, match, or missing tracks..."
        oninput="filterTable('almostFilter','almostComplete')"
      >
    </div>
  </div>

  <div class="almost-table-wrap">
    <table id="almostComplete">
      <thead>
        <tr>
          <th onclick="sortTable('almostComplete',0,true)">Show</th>
          <th onclick="sortTable('almostComplete',1)">Date</th>
          <th onclick="sortTable('almostComplete',2)">DJs</th>
          <th onclick="sortTable('almostComplete',3,true)">Matched</th>
          <th onclick="sortTable('almostComplete',4,true)">Match %</th>
          <th onclick="sortTable('almostComplete',5,true)">Missing</th>
          <th>Progress</th>
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
    raise SystemExit("Could not find replaceable page body in episodes.html")

page = template[:start] + card + "\n" + template[end:]

OUT.write_text(page, encoding="utf-8")

print(f"Wrote: {OUT}")
