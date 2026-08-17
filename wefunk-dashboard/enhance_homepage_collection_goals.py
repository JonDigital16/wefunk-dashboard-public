#!/usr/bin/env python3

import html
import os
import re
from pathlib import Path

SITE = Path(os.environ.get(
    "WEFUNK_SITE_DIR",
    str(Path(__file__).resolve().parents[1] / "site")
))

INDEX = SITE / "index.html"
SOURCE = SITE / "almost-complete.html"

if not INDEX.exists():
    raise SystemExit("index.html does not exist")

if not SOURCE.exists():
    raise SystemExit("almost-complete.html does not exist")

homepage = INDEX.read_text(encoding="utf-8")
source = SOURCE.read_text(encoding="utf-8")

if 'id="homepageCollectionGoals"' in homepage:
    print("Collection Goals already present")
    raise SystemExit(0)

def clean(value):
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()

goals = []

for row in re.findall(r"<tr[^>]*>(.*?)</tr>", source, flags=re.S | re.I):
    show_match = re.search(
        r'href=[\'"]/shows/([^\'"/]+)\.html[\'"]',
        row,
        flags=re.I,
    )

    if not show_match:
        continue

    cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S | re.I)
    values = [clean(cell) for cell in cells]

    percentage = None

    for value in values:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", value)
        if match:
            percentage = float(match.group(1))
            break

    if percentage is None:
        continue

    show_id = show_match.group(1)
    pct_text = f"{percentage:g}"

    goals.append(f"""
<a class="goal-card" href="/shows/{show_id}.html">
  <img src="/episode-art/{show_id}.jpg"
       loading="lazy"
       onerror="this.style.display='none';"
       alt="">
  <div class="goal-card-body">
    <div class="goal-card-top">
      <strong>Show {show_id}</strong>
      <span>{pct_text}%</span>
    </div>
    <div class="goal-progress">
      <div style="width:{min(100, percentage)}%"></div>
    </div>
    <div class="goal-meta">Almost complete</div>
  </div>
</a>
""")

    if len(goals) >= 6:
        break

section = f"""
<div class="card homepage-collection-goals" id="homepageCollectionGoals">
  <div class="goal-heading">
    <div>
      <h2>🎯 Collection Goals</h2>
      <p class="small">WEFUNK episodes closest to being fully matched.</p>
    </div>
    <a class="goal-link" href="/almost-complete.html">View all →</a>
  </div>

  <div class="goal-grid">
    {''.join(goals)}
  </div>
</div>
"""

css = """
<style>
.goal-heading{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  gap:18px;
  margin-bottom:18px;
}

.goal-link{
  padding:8px 12px;
  border:1px solid #2b2f36;
  border-radius:999px;
  color:#F7931E;
  font-size:13px;
  font-weight:800;
  text-decoration:none;
}

.goal-grid{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:15px;
}

.goal-card{
  display:grid;
  grid-template-columns:88px 1fr;
  overflow:hidden;
  border:1px solid #2b2f36;
  border-radius:16px;
  background:#171a1f;
  color:#f5f5f5;
  text-decoration:none;
}

.goal-card:hover{
  border-color:#F7931E;
  transform:translateY(-2px);
}

.goal-card img{
  width:88px;
  height:110px;
  object-fit:cover;
}

.goal-card-body{
  padding:13px;
}

.goal-card-top{
  display:flex;
  justify-content:space-between;
  gap:10px;
}

.goal-card-top span{
  color:#F7931E;
  font-weight:900;
}

.goal-progress{
  height:8px;
  margin-top:14px;
  overflow:hidden;
  border-radius:999px;
  background:#2b2f36;
}

.goal-progress div{
  height:100%;
  background:#F7931E;
}

.goal-meta{
  margin-top:9px;
  color:#999;
  font-size:12px;
}

@media(max-width:900px){
  .goal-grid{
    grid-template-columns:repeat(2,1fr);
  }
}

@media(max-width:600px){
  .goal-grid{
    grid-template-columns:1fr;
  }
}
</style>
"""

homepage = homepage.replace("</head>", css + "\n</head>", 1)

marker = homepage.find('id="homepageRecentMatches"')

if marker == -1:
    raise SystemExit("Homepage Recent Matches section not found")

insert_at = homepage.find('\n<div class="card">', marker)

if insert_at == -1:
    raise SystemExit("Could not find insertion point after Recent Matches")

homepage = homepage[:insert_at] + "\n" + section + homepage[insert_at:]

INDEX.write_text(homepage, encoding="utf-8")

print(f"Added {len(goals)} Collection Goal cards to homepage")
