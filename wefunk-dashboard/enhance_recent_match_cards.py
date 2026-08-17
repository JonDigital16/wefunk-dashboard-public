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

PAGE = SITE / "recent-matches.html"

if not PAGE.exists():
    raise SystemExit(
        "recent-matches.html does not exist yet. "
        "Run generate_recent_matches_page.py first."
    )

html = PAGE.read_text(encoding="utf-8")

if 'id="recentMatchCardGrid"' in html:
    print("Recent Match cards already present")
    raise SystemExit(0)


def plain(value):
    value = re.sub(r"<[^>]+>", "", value)
    return html_lib.unescape(value).strip()


rows = re.findall(
    r"<tr>(.*?)</tr>",
    html,
    flags=re.S,
)

cards = []

for row in rows:
    cells = re.findall(
        r"<td[^>]*>(.*?)</td>",
        row,
        flags=re.S,
    )

    if len(cells) < 8:
        continue

    show_link = re.search(
        r"""href=['"](/shows/[^'"]+\.html)['"]""",
        cells[1],
        flags=re.I,
    )

    image = re.search(
        r"""src=['"](/episode-art/[^'"]+)['"]""",
        cells[1],
        flags=re.I,
    )

    artist_link = re.search(
        r"""href=['"](/artists/[^'"]+\.html)['"]""",
        cells[2],
        flags=re.I,
    )

    album_link = re.search(
        r"""href=['"](/albums/[^'"]+\.html)['"]""",
        cells[5],
        flags=re.I,
    )

    genre_link = re.search(
        r"""href=['"](/genres/[^'"]+\.html)['"]""",
        cells[6],
        flags=re.I,
    )

    if not show_link:
        continue

    date_added = plain(cells[0])
    show = plain(cells[1])
    artist = plain(cells[2])
    track = plain(cells[3])
    match = plain(cells[4])
    album = plain(cells[5])
    genre = plain(cells[6])
    year = plain(cells[7])

    show_url = show_link.group(1)
    cover = (
        image.group(1)
        if image
        else f"/episode-art/{show}.jpg"
    )

    artist_url = (
        artist_link.group(1)
        if artist_link
        else ""
    )

    album_url = (
        album_link.group(1)
        if album_link
        else ""
    )

    genre_url = (
        genre_link.group(1)
        if genre_link
        else ""
    )

    if artist_url:
        artist_html = (
            f'<a class="recent-match-artist" '
            f'href="{artist_url}">'
            f'{html_lib.escape(artist)}'
            f'</a>'
        )
    else:
        artist_html = (
            f'<div class="recent-match-artist">'
            f'{html_lib.escape(artist)}'
            f'</div>'
        )

    if album and album_url:
        album_html = (
            f'<a class="recent-match-album" '
            f'href="{album_url}">'
            f'{html_lib.escape(album)}'
            f'</a>'
        )
    elif album:
        album_html = (
            f'<div class="recent-match-album">'
            f'{html_lib.escape(album)}'
            f'</div>'
        )
    else:
        album_html = ""

    if genre and genre_url:
        genre_html = (
            f'<a href="{genre_url}">'
            f'{html_lib.escape(genre)}'
            f'</a>'
        )
    else:
        genre_html = html_lib.escape(genre)

    year_separator = (
        " · "
        if genre and year
        else ""
    )

    cards.append(
        f"""
<div class="recent-match-card">
  <a
    class="recent-match-cover-link"
    href="{show_url}"
  >
    <img
      src="{cover}"
      loading="lazy"
      onerror="this.style.display='none';"
      alt=""
    >
  </a>

  <div class="recent-match-card-body">
    <div class="recent-match-show-line">
      <a href="{show_url}">
        Show {html_lib.escape(show)}
      </a>

      <span>
        {html_lib.escape(date_added)}
      </span>
    </div>

    <a
      class="recent-match-track"
      href="{show_url}"
    >
      {html_lib.escape(track)}
    </a>

    {artist_html}

    {album_html}

    <div class="recent-match-meta">
      {genre_html}{year_separator}{html_lib.escape(year)}
    </div>

    <div class="recent-match-library">
      <span>Your Match</span>
      {html_lib.escape(match)}
    </div>
  </div>
</div>
"""
    )


css = """
<style>
.recent-match-card-grid{
  display:grid;
  grid-template-columns:repeat(
    auto-fill,
    minmax(210px,1fr)
  );
  gap:18px;
  margin-top:22px;
}

.recent-match-card{
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

.recent-match-card:hover{
  transform:translateY(-4px);
  border-color:#F7931E;
  box-shadow:0 16px 42px rgba(0,0,0,.38);
}

.recent-match-cover-link{
  display:block;
  background:#0f1115;
}

.recent-match-card img{
  display:block;
  width:100%;
  aspect-ratio:1/1;
  object-fit:cover;
}

.recent-match-card-body{
  display:flex;
  min-width:0;
  flex:1;
  flex-direction:column;
  padding:13px;
}

.recent-match-card a{
  text-decoration:none;
}

.recent-match-show-line{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
  margin-bottom:8px;
  color:#888;
  font-size:11px;
}

.recent-match-show-line a{
  color:#F7931E;
  font-weight:900;
}

.recent-match-show-line span{
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
}

.recent-match-track{
  display:block;
  color:#f5f5f5;
  font-size:16px;
  font-weight:900;
  line-height:1.3;
}

.recent-match-track:hover{
  color:#F7931E;
}

.recent-match-artist{
  display:block;
  margin-top:6px;
  color:#ddd;
  font-size:13px;
  font-weight:800;
  line-height:1.35;
}

a.recent-match-artist:hover{
  color:#F7931E;
}

.recent-match-album{
  display:block;
  margin-top:7px;
  color:#aaa;
  font-size:12px;
  line-height:1.35;
}

a.recent-match-album:hover{
  color:#F7931E;
}

.recent-match-meta{
  margin-top:5px;
  color:#777;
  font-size:11px;
  line-height:1.35;
}

.recent-match-meta a{
  color:#999;
}

.recent-match-meta a:hover{
  color:#F7931E;
}

.recent-match-library{
  margin-top:auto;
  padding-top:11px;
  border-top:1px solid #262a30;
  color:#999;
  font-size:11px;
  line-height:1.35;
}

.recent-match-library span{
  display:block;
  margin-bottom:3px;
  color:#666;
  font-size:10px;
  font-weight:900;
  text-transform:uppercase;
}

.recent-match-view-toggle{
  display:flex;
  gap:10px;
  margin-top:18px;
}

.recent-match-view-toggle button{
  padding:8px 13px;
  border:1px solid #2b2f36;
  border-radius:999px;
  background:#171a1f;
  color:#f5f5f5;
  cursor:pointer;
  font-weight:800;
}

.recent-match-view-toggle button:hover{
  background:#F7931E;
  color:#111;
}

#recentMatches{
  display:none;
}

@media(max-width:600px){
  .recent-match-card-grid{
    grid-template-columns:1fr;
    gap:12px;
  }

  .recent-match-card{
    display:grid;
    grid-template-columns:118px minmax(0,1fr);
  }

  .recent-match-card img{
    width:118px;
    height:100%;
    min-height:118px;
    aspect-ratio:auto;
  }

  .recent-match-card-body{
    padding:12px;
  }

  .recent-match-library{
    margin-top:9px;
  }
}
</style>
"""


grid = f"""
<div class="recent-match-view-toggle">
  <button onclick="showRecentMatchCards()">
    Cards
  </button>

  <button onclick="showRecentMatchTable()">
    Table
  </button>
</div>

<div
  class="recent-match-card-grid"
  id="recentMatchCardGrid"
>
  {''.join(cards)}
</div>
"""


html = html.replace(
    "</head>",
    css + "\n</head>",
    1,
)

html = html.replace(
    '<table id="recentMatches">',
    grid + '\n<table id="recentMatches">',
    1,
)


js = TOGGLE_JS + """
<script>
function showRecentMatchCards(){
    setCardTableView(
        "recentMatchCardGrid",
        "recentMatches",
        "recent-match-view-toggle",
        "recentMatchView",
        "cards"
    );
}

function showRecentMatchTable(){
    setCardTableView(
        "recentMatchCardGrid",
        "recentMatches",
        "recent-match-view-toggle",
        "recentMatchView",
        "table"
    );
}

document.addEventListener(
    "DOMContentLoaded",
    function(){
        initCardTableView(
            "recentMatchCardGrid",
            "recentMatches",
            "recent-match-view-toggle",
            "recentMatchView"
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

print(
    f"Added {len(cards)} Recent Match cards"
)
print(
    "Saved Recent Matches card/table toggle JavaScript"
)
