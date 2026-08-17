#!/usr/bin/env python3

import html as html_lib
import os
import re
from pathlib import Path

from shared_view_toggle import TOGGLE_JS

SITE = Path(
    os.environ.get(
        "WEFUNK_SITE_DIR",
        str(Path(__file__).resolve().parents[1] / "site"),
    )
)

PAGE = SITE / "missing.html"
ARTIST_IMAGES = SITE / "artist-images"

if not PAGE.exists():
    raise SystemExit(
        "missing.html does not exist yet. "
        "Run generate_missing_tracks_page.py first."
    )

html = PAGE.read_text(encoding="utf-8")

if 'id="missingTrackCardGrid"' in html:
    print("Missing Track cards already present")
    raise SystemExit(0)


def plain(value):
    value = re.sub(r"<[^>]+>", "", value)
    return html_lib.unescape(value).strip()


def priority_for(count):
    if count >= 10:
        return "Critical", "critical"

    if count >= 5:
        return "High", "high"

    if count >= 3:
        return "Medium", "medium"

    return "Low", "low"


rows = re.findall(
    r"<tr>(.*?)</tr>",
    html,
    flags=re.S,
)

cards = []
artist_names = set()
total_appearances = 0

for row in rows:
    cells = re.findall(
        r"<td[^>]*>(.*?)</td>",
        row,
        flags=re.S,
    )

    if len(cells) < 5:
        continue

    artist_link = re.search(
        r"""href=['"](/artists/([^'"]+)\.html)['"]""",
        cells[0],
        flags=re.I,
    )

    if not artist_link:
        continue

    artist_url = artist_link.group(1)
    artist_slug = artist_link.group(2)

    artist = plain(cells[0])
    track = plain(cells[1])
    count_text = plain(cells[2])

    try:
        show_count = int(count_text)
    except ValueError:
        show_count = 0

    if not artist and not track:
        continue

    total_appearances += show_count
    artist_names.add(artist.casefold())

    priority_label, priority_class = priority_for(show_count)

    show_links = re.findall(
        r"""href=['"](/shows/([^'"]+)\.html)['"]""",
        cells[3],
        flags=re.I,
    )

    show_html = []

    for show_url, show_id in show_links[:12]:
        show_html.append(
            f'<a class="missing-show-chip" '
            f'href="{show_url}">'
            f'{html_lib.escape(show_id)}'
            f'</a>'
        )

    extra_shows = max(0, len(show_links) - 12)

    if extra_shows:
        show_html.append(
            f'<span class="missing-show-more">'
            f'+{extra_shows} more'
            f'</span>'
        )

    search_links = re.findall(
        r"""href=['"]([^'"]+)['"][^>]*>([^<]+)</a>""",
        cells[4],
        flags=re.I,
    )

    search_buttons = []

    for url, label in search_links:
        search_buttons.append(
            f'<a class="missing-search-button" '
            f'href="{html_lib.escape(url)}" '
            f'target="_blank" '
            f'rel="noopener noreferrer">'
            f'{html_lib.escape(label.strip())}'
            f'</a>'
        )

    artist_image = ARTIST_IMAGES / f"{artist_slug}.jpg"

    if artist_image.exists():
        image_version = int(artist_image.stat().st_mtime)

        visual = (
            f'<img '
            f'class="missing-track-artist-image" '
            f'src="/artist-images/{artist_slug}.jpg?v={image_version}" '
            f'alt="{html_lib.escape(artist)}" '
            f'loading="lazy">'
        )

    else:
        initial = next(
            (
                character.upper()
                for character in artist
                if character.isalnum()
            ),
            "♪",
        )

        visual = (
            '<div class="missing-track-placeholder">'
            f'{html_lib.escape(initial)}'
            '</div>'
        )

    cards.append(
        f"""
<div class="missing-track-card">
  <a
    class="missing-track-visual"
    href="{artist_url}"
  >
    {visual}

    <span class="missing-priority missing-priority-{priority_class}">
      {priority_label}
    </span>
  </a>

  <div class="missing-track-card-body">
    <a
      class="missing-track-title"
      href="{artist_url}"
    >
      {html_lib.escape(track)}
    </a>

    <a
      class="missing-track-artist"
      href="{artist_url}"
    >
      {html_lib.escape(artist)}
    </a>

    <div class="missing-track-frequency">
      <strong>{show_count:,}</strong>
      <span>
        WEFUNK {"appearance" if show_count == 1 else "appearances"}
      </span>
    </div>

    <div class="missing-track-shows">
      <div class="missing-track-section-label">
        Appears In
      </div>

      <div class="missing-show-chips">
        {''.join(show_html)}
      </div>
    </div>

    <div class="missing-track-actions">
      {''.join(search_buttons)}
    </div>
  </div>
</div>
"""
    )


summary = f"""
<div class="missing-summary-grid">
  <div class="missing-summary-card">
    <strong>{len(cards):,}</strong>
    <span>Missing Track Groups</span>
  </div>

  <div class="missing-summary-card">
    <strong>{total_appearances:,}</strong>
    <span>Missing Appearances</span>
  </div>

  <div class="missing-summary-card">
    <strong>{len(artist_names):,}</strong>
    <span>Artists Affected</span>
  </div>
</div>
"""


grid = f"""
{summary}

<div class="missing-view-toggle">
  <button onclick="showMissingCards()">
    Cards
  </button>

  <button onclick="showMissingTable()">
    Table
  </button>
</div>

<div
  class="missing-track-card-grid"
  id="missingTrackCardGrid"
>
  {''.join(cards)}
</div>
"""


css = """
<style>
.missing-summary-grid{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:12px;
  margin:18px 0;
}

.missing-summary-card{
  display:flex;
  min-width:0;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  padding:18px 12px;
  border:1px solid #2b2f36;
  border-radius:16px;
  background:#171a1f;
  text-align:center;
}

.missing-summary-card strong{
  color:#F7931E;
  font-size:27px;
  line-height:1;
}

.missing-summary-card span{
  margin-top:7px;
  color:#aaa;
  font-size:12px;
  font-weight:700;
}

.missing-view-toggle{
  display:flex;
  gap:10px;
  margin-top:18px;
}

.missing-view-toggle button{
  padding:8px 13px;
  border:1px solid #2b2f36;
  border-radius:999px;
  background:#171a1f;
  color:#f5f5f5;
  cursor:pointer;
  font-weight:800;
}

.missing-view-toggle button:hover{
  background:#F7931E;
  color:#111;
}

.missing-track-card-grid{
  display:grid;
  grid-template-columns:repeat(
    auto-fill,
    minmax(230px,1fr)
  );
  gap:18px;
  margin-top:22px;
}

.missing-track-card{
  display:flex;
  min-width:0;
  flex-direction:column;
  overflow:hidden;
  border:1px solid #2b2f36;
  border-radius:18px;
  background:#171a1f;
  color:#f5f5f5;
  transition:
    transform .18s ease,
    box-shadow .18s ease,
    border-color .18s ease;
}

.missing-track-card:hover{
  transform:translateY(-4px);
  border-color:#F7931E;
  box-shadow:0 16px 42px rgba(0,0,0,.38);
}

.missing-track-visual{
  position:relative;
  display:block;
  aspect-ratio:16/10;
  overflow:hidden;
  background:#0f1115;
  text-decoration:none;
}

.missing-track-artist-image{
  display:block;
  width:100%;
  height:100%;
  object-fit:cover;
}

.missing-track-placeholder{
  display:flex;
  width:100%;
  height:100%;
  align-items:center;
  justify-content:center;
  background:
    radial-gradient(
      circle at 30% 20%,
      rgba(247,147,30,.28),
      rgba(23,26,31,.98) 64%
    );
  color:#F7931E;
  font-size:54px;
  font-weight:900;
}

.missing-priority{
  position:absolute;
  top:11px;
  right:11px;
  padding:4px 9px;
  border-radius:999px;
  font-size:10px;
  font-weight:900;
  text-transform:uppercase;
  box-shadow:0 4px 16px rgba(0,0,0,.35);
}

.missing-priority-critical{
  background:#F7931E;
  color:#111;
}

.missing-priority-high{
  background:#d98727;
  color:#111;
}

.missing-priority-medium{
  background:#363b43;
  color:#f5f5f5;
}

.missing-priority-low{
  background:#262a30;
  color:#aaa;
}

.missing-track-card-body{
  display:flex;
  min-width:0;
  flex:1;
  flex-direction:column;
  padding:14px;
}

.missing-track-card a{
  text-decoration:none;
}

.missing-track-title{
  color:#f5f5f5;
  font-size:16px;
  font-weight:900;
  line-height:1.3;
}

.missing-track-title:hover{
  color:#F7931E;
}

.missing-track-artist{
  margin-top:6px;
  color:#bbb;
  font-size:13px;
  font-weight:800;
  line-height:1.35;
}

.missing-track-artist:hover{
  color:#F7931E;
}

.missing-track-frequency{
  display:flex;
  align-items:baseline;
  gap:6px;
  margin-top:13px;
}

.missing-track-frequency strong{
  color:#F7931E;
  font-size:22px;
}

.missing-track-frequency span{
  color:#888;
  font-size:11px;
  font-weight:700;
}

.missing-track-shows{
  margin-top:13px;
}

.missing-track-section-label{
  margin-bottom:7px;
  color:#666;
  font-size:10px;
  font-weight:900;
  text-transform:uppercase;
}

.missing-show-chips{
  display:flex;
  flex-wrap:wrap;
  gap:5px;
}

.missing-show-chip{
  padding:4px 7px;
  border:1px solid #30343b;
  border-radius:7px;
  background:#111419;
  color:#bbb;
  font-size:10px;
  font-weight:800;
}

.missing-show-chip:hover{
  border-color:#F7931E;
  color:#F7931E;
}

.missing-show-more{
  padding:4px 4px;
  color:#666;
  font-size:10px;
}

.missing-track-actions{
  display:flex;
  flex-wrap:wrap;
  gap:6px;
  margin-top:auto;
  padding-top:14px;
}

.missing-search-button{
  padding:6px 9px;
  border:1px solid #30343b;
  border-radius:999px;
  background:#111419;
  color:#bbb;
  font-size:10px;
  font-weight:800;
}

.missing-search-button:hover{
  border-color:#F7931E;
  background:#F7931E;
  color:#111;
}

#missingTracks{
  display:none;
}

@media(max-width:700px){
  .missing-summary-grid{
    grid-template-columns:1fr;
  }

  .missing-track-card-grid{
    grid-template-columns:1fr;
    gap:12px;
  }

  .missing-track-card{
    display:grid;
    grid-template-columns:118px minmax(0,1fr);
  }

  .missing-track-visual{
    width:118px;
    height:100%;
    min-height:150px;
    aspect-ratio:auto;
  }

  .missing-track-card-body{
    padding:12px;
  }

  .missing-track-frequency{
    margin-top:9px;
  }

  .missing-track-shows{
    margin-top:9px;
  }
}
</style>
"""


html = html.replace(
    "</head>",
    css + "\n</head>",
    1,
)

html = html.replace(
    '<table id="missingTracks">',
    grid + '\n<table id="missingTracks">',
    1,
)


js = TOGGLE_JS + """
<script>
function showMissingCards(){
    setCardTableView(
        "missingTrackCardGrid",
        "missingTracks",
        "missing-view-toggle",
        "missingTrackView",
        "cards"
    );
}

function showMissingTable(){
    setCardTableView(
        "missingTrackCardGrid",
        "missingTracks",
        "missing-view-toggle",
        "missingTrackView",
        "table"
    );
}

document.addEventListener(
    "DOMContentLoaded",
    function(){
        initCardTableView(
            "missingTrackCardGrid",
            "missingTracks",
            "missing-view-toggle",
            "missingTrackView"
        );
    }
);
</script>
"""


html = html.replace(
    "</body>",
    js + "\n</body>",
    1,
)

PAGE.write_text(
    html,
    encoding="utf-8",
)

print(f"Added {len(cards):,} Missing Track cards")
print(f"Missing appearances represented: {total_appearances:,}")
print(f"Artists represented: {len(artist_names):,}")
print("Saved Missing Tracks card/table toggle JavaScript")
