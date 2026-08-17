import os
import csv
import json
import html
import re
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from common import (
    artist_display_name,
    artist_slugify,
    normalize_artist_name,
    SITE,
    SHOWS_DIR,
    ARTISTS_DIR,
    EXPORTS,
    load_csv,
    slugify,
)

from datetime import datetime
from collections import defaultdict
from urllib.parse import quote_plus

from data import owned_tracks_enriched

DB = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "db" / 'wefunk_engine.db'
STATS_CSV = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve() / 'wefunk_show_match_stats.csv'
MISSING_ARTISTS_CSV = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve() / 'wefunk_top_missing_artists.csv'
RECOMMENDED_ALBUMS_CSV = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve() / 'wefunk_recommended_albums.csv'


SITE = Path(
    os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site"))
)
SHOWS_DIR = SITE / "shows"
ARTISTS_DIR = SITE / "artists"
DATA_DIR = SITE / "data"
ARTIST_BIOS_FILE = DATA_DIR / "artist-bios.json"
ARTIST_ASSET_ALIASES_FILE = Path(__file__).with_name(
    "artist_asset_aliases.json"
)
ARTIST_DISPLAY_NAMES_FILE = Path(__file__).with_name(
    "artist_display_names.json"
)

artist_asset_aliases = {}
artist_display_names = {}

if ARTIST_DISPLAY_NAMES_FILE.exists():
    try:
        loaded_display_names = json.loads(
            ARTIST_DISPLAY_NAMES_FILE.read_text(encoding="utf-8")
        )

        if isinstance(loaded_display_names, dict):
            artist_display_names = {
                str(slug): str(name).strip()
                for slug, name in loaded_display_names.items()
                if slug and str(name).strip()
            }
    except (OSError, json.JSONDecodeError):
        artist_display_names = {}

if ARTIST_ASSET_ALIASES_FILE.exists():
    try:
        loaded_artist_aliases = json.loads(
            ARTIST_ASSET_ALIASES_FILE.read_text(encoding="utf-8")
        )

        if isinstance(loaded_artist_aliases, dict):
            artist_asset_aliases = {
                str(alias): str(canonical)
                for alias, canonical in loaded_artist_aliases.items()
                if alias and canonical
            }
    except (OSError, json.JSONDecodeError):
        artist_asset_aliases = {}

for d in [SITE, SHOWS_DIR, ARTISTS_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def z_date_sort(s):
    from datetime import datetime

    s = str(s or "").strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s


def z_date_short(s):
    from datetime import datetime

    s = str(s or "").strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%m/%d/%y")
        except ValueError:
            pass
    return s


CSS = """

.artist-profile{
  display:grid;
  grid-template-columns:220px minmax(0,1fr);
  gap:26px;
  align-items:center;
}

.artist-profile-image-wrap{
  width:220px;
  aspect-ratio:1;
  overflow:hidden;
  border-radius:18px;
  border:1px solid #2b2f36;
  background:
    radial-gradient(circle at 30% 25%,rgba(247,147,30,.28),transparent 42%),
    linear-gradient(145deg,#252a31,#101214);
}

.artist-profile-image{
  display:block;
  width:100%;
  height:100%;
  object-fit:cover;
  transition:transform .22s ease;
}

.artist-profile-image:hover{
  transform:scale(1.04);
}

.artist-profile-placeholder{
  width:100%;
  height:100%;
  display:flex;
  align-items:center;
  justify-content:center;
  color:#F7931E;
  font-size:68px;
  font-weight:900;
}

.artist-profile-details h2{
  margin:8px 0;
  color:#F7931E;
  font-size:clamp(30px,5vw,52px);
  line-height:1.05;
}

.artist-profile-details .small{
  font-size:15px;
  line-height:1.5;
}

.artist-biography h2{
  margin-top:0;
  color:#F7931E;
}

.artist-biography p{
  margin-bottom:0;
  font-size:16px;
  line-height:1.75;
  color:#d7d7d7;
  max-width:1000px;
}

@media(max-width:700px){
  .artist-profile{
    grid-template-columns:1fr;
    gap:18px;
  }

  .artist-profile-image-wrap{
    width:min(100%,320px);
  }
}

.hero-banner{
  background-image:linear-gradient(rgba(16,18,20,.35),rgba(16,18,20,.85)),url('/episode-art/wefunk-banner.jpg');
  background-size:cover;
  background-position:center;
  border-bottom:1px solid #2b2f36;
}

.hero-banner h1 span:first-child{font-size:72px!important}
.hero-banner h1 span:last-child{font-size:32px!important}
.hero-banner .small{font-size:18px;margin-top:8px}
.hero-search{width:min(820px,90vw);margin-top:26px}
.hero-search input{width:100%;max-width:none;font-size:16px;padding:16px 18px}
.hero-search #globalResults{text-align:left;background:#171a1f;border:1px solid #2b2f36;border-radius:14px;margin-top:12px;padding:12px;max-height:420px;overflow:auto}
.hero-search #globalResults:empty{display:none;}
.hero-banner header{
  background:transparent;
  border-bottom:none;
  min-height:260px;
  display:flex;
  flex-direction:column;
  justify-content:center;
}

body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial;background:#101214;color:#e8e8e8;margin:0}
header{
padding-bottom:18px;background:#171a1f;padding:24px 36px;border-bottom:1px solid #2b2f36}
h1{margin:0;color:#F7931E}
main{padding:28px 36px}
.card{background:#171a1f;border:1px solid #2b2f36;border-radius:14px;padding:18px;margin-bottom:22px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}
.stat{font-size:30px;font-weight:800;color:#F7931E}
.label,.small{color:#aaa;font-size:13px}
table{border-collapse:collapse;width:100%}
td,th{padding:10px;border-bottom:1px solid #2b2f36;text-align:left}
th{color:#F7931E;cursor:pointer;user-select:none}
a{color:#6ab7ff;text-decoration:none}
input{background:#0d0f11;color:#eee;border:1px solid #333;border-radius:8px;padding:12px;width:100%;max-width:520px}
.yes{color:#F7931E;font-weight:700}
.no{color:#ff6b6b;font-weight:700}
.bar{
    background:#333;
    border-radius:8px;
    overflow:hidden;
    height:18px;
}

.fill{
    background:#00d084;
    height:18px;
    transition:width .3s ease;
}
.badge{display:inline-block;padding:3px 8px;border-radius:999px;background:#252a31}

details summary{
  color:#66b3ff;
  cursor:pointer;
  font-weight:600;
  margin-top:4px;
  user-select:none;
}

details summary:hover{
  text-decoration:underline;
}

details summary::-webkit-details-marker{
  color:#66b3ff;
}

.global-search{margin-bottom:22px}
.global-search input{max-width:760px}
#globalResults{margin-top:12px}
.report-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.report-card{display:block;background:#101214;border:1px solid #2b2f36;border-radius:14px;padding:18px;color:#e8e8e8}
.report-card:hover{border-color:#F7931E}
.report-icon{font-size:28px;margin-bottom:8px}
.report-title{font-size:18px;font-weight:800;color:#F7931E;margin-bottom:6px}
.report-desc{color:#aaa;font-size:13px;line-height:1.4}

.waveform{display:flex;gap:4px;align-items:end;height:18px;margin:8px 0 2px 2px}
.waveform span{display:block;width:4px;background:#F7931E;border-radius:999px;opacity:.95}
.waveform span:nth-child(1){height:6px}
.waveform span:nth-child(2){height:14px}
.waveform span:nth-child(3){height:9px}
.waveform span:nth-child(4){height:18px}
.waveform span:nth-child(5){height:11px}
.waveform span:nth-child(6){height:15px}
.waveform span:nth-child(7){height:7px}
.waveform span:nth-child(8){height:13px}

.episode-art{max-width:420px;width:100%;border-radius:16px;border:1px solid #2b2f36;margin:14px 0 18px 0;display:block}
.genre-heatmap{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.genre-tile{border:1px solid #2b2f36;border-radius:14px;padding:14px;background:#171a1f}
.genre-name{font-weight:800;color:#fff;margin-bottom:6px}
.genre-count{color:#aaa;font-size:13px}

.artist-heatmap{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.artist-tile{border:1px solid #2b2f36;border-radius:14px;padding:14px;background:#171a1f}
.artist-name{font-weight:800;color:#fff;margin-bottom:6px}
.artist-count{color:#aaa;font-size:13px}
.artist-pct{color:#F7931E;font-size:13px;margin-top:4px}

@media (max-width: 800px){
  header{
padding-bottom:18px;padding:20px}
  main{padding:18px}
  h1{font-size:34px}
  h2{font-size:22px}
  .card{padding:14px;border-radius:12px}
  .stat{font-size:28px}
  table{display:block;overflow-x:auto;white-space:nowrap}
  td,th{padding:8px}
  input{max-width:100%;box-sizing:border-box}
}

.roadmap-list{margin:12px 0 0 0;padding-left:22px;line-height:1.7}
.roadmap-list li{border-bottom:1px solid #2b2f36;padding:6px 0}

.excellent{color:#F7931E;font-weight:bold;}
.great{color:#4da3ff;font-weight:bold;}
.good{color:#ffd54f;font-weight:bold;}
.poor{color:#ff6b6b;font-weight:bold;}
"""

JS = """
<script>

function sortTable(tableId,col,numeric=false){
    const table = typeof tableId === "string" ? document.getElementById(tableId) : tableId;
    if(!table) return;

    const tbody = table.tBodies[0];
    if(!tbody) return;

    const rows = Array.from(tbody.rows);
    const ths = Array.from(table.querySelectorAll("th"));

    let asc = table.dataset.sortCol != col || table.dataset.sortDir !== "asc";

    table.dataset.sortCol = col;
    table.dataset.sortDir = asc ? "asc" : "desc";

    ths.forEach(th => {
        th.textContent = th.textContent.replace(/ ▲| ▼/g,"");
    });

    if(ths[col]) ths[col].textContent += asc ? " ▲" : " ▼";

    rows.sort((a,b) => {
        let av = a.cells[col]?.dataset.sort || a.cells[col]?.innerText.trim() || "";
        let bv = b.cells[col]?.dataset.sort || b.cells[col]?.innerText.trim() || "";

        let an = parseFloat(av.replace("%",""));
        let bn = parseFloat(bv.replace("%",""));

        if(numeric || (!isNaN(an) && !isNaN(bn))){
            return asc ? an - bn : bn - an;
        }

        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
    });

    rows.forEach(r => tbody.appendChild(r));
}

function filterTable(inputId, tableId) {
  const q = document.getElementById(inputId).value.toLowerCase();
  const rows = document.querySelectorAll("#" + tableId + " tbody tr");
  rows.forEach(row => {
    row.style.display = row.innerText.toLowerCase().includes(q) ? "" : "none";
  });
}
</script>
"""


def esc(x):
    return html.escape(str(x or ""))


def page(title, body):
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="hero-banner">
<header>
<h1>
<a href="/" style="text-decoration:none;display:inline-block;line-height:1.05;">
<span style="display:block;color:#F7931E;font-weight:900;font-size:1.25em;letter-spacing:.03em;">WEFUNK</span>
<div class="waveform">
  <span></span><span></span><span></span><span></span>
  <span></span><span></span><span></span><span></span>
</div>
<span style="display:block;color:#ffffff;font-weight:800;font-size:.72em;">Dashboard</span>
</a>
</h1>
<div class="small">Your WEFUNK archive matched against your personal music collection</div>

<div class="hero-search">
<input id="globalSearch" placeholder="Search show, artist, track, match, or missing..." oninput="doGlobalSearch()">
<div id="globalResults"></div>
</div>

</header>
</div>
<main>
{body}
</main>
{JS}
</body>
</html>"""


shows = load_csv(STATS_CSV)

artist_bios = {}

if ARTIST_BIOS_FILE.exists():
    try:
        loaded_artist_bios = json.loads(ARTIST_BIOS_FILE.read_text(encoding="utf-8"))

        if isinstance(loaded_artist_bios, dict):
            artist_bios = loaded_artist_bios
    except (OSError, json.JSONDecodeError):
        artist_bios = {}


missing_by_show = {}

for row in load_csv(
    Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve() / 'wefunk_missing_tracks_engine.csv'
):
    show = row["show_id"]
    missing_by_show.setdefault(show, []).append(f"{row['artist']} – {row['track']}")


recommended_albums = []

if RECOMMENDED_ALBUMS_CSV.exists():
    recommended_albums = load_csv(RECOMMENDED_ALBUMS_CSV)

missing_artists = []
if MISSING_ARTISTS_CSV.exists():
    for row in load_csv(MISSING_ARTISTS_CSV):
        if row.get("artist", "").strip("_ -"):
            missing_artists.append(row)

conn = sqlite3.connect(DB)
cur = conn.cursor()

archive_total_tracks = cur.execute("SELECT COUNT(*) FROM wefunk_tracks").fetchone()[0]
matched_tracks = cur.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
total_shows = len(shows)
best = shows[0] if shows else {"show_id": "—", "match_percent": "0"}

search_index = []
artist_pages = defaultdict(list)
missing_tracks = defaultdict(list)

# Canonical artist index.
#
# This initially exists alongside artist_pages so the current generated
# pages remain unchanged while the new index is validated.
artist_index = defaultdict(
    lambda: {
        "display_name": "",
        "normalized_name": "",
        "wefunk": [],
        "albums": {},
    }
)

for show in shows:
    show_id = show["show_id"]

    meta = cur.execute(
        """
        SELECT show_id, recorded, djs, url, description
        FROM shows
        WHERE show_id = ?
    """,
        (show_id,),
    ).fetchone()

    full_rows = cur.execute(
        """
        SELECT
          wt.id,
          wt.artist,
          wt.track,
          m.library_artist,
          m.library_title,
          m.score
        FROM wefunk_tracks wt
        LEFT JOIN matches m
          ON wt.show_id = m.show_id
         AND wt.artist = m.wefunk_artist
         AND wt.track = m.wefunk_track
        WHERE wt.show_id = ?
        ORDER BY wt.id
    """,
        (show_id,),
    ).fetchall()

    total_tracks = len(full_rows)

    owned_count = sum(1 for r in full_rows if r[3])
    missing_count = total_tracks - owned_count

    completion_pct = round((owned_count / total_tracks) * 100, 1) if total_tracks else 0

    if completion_pct >= 90:
        quality = "<span class='excellent'>🟢 Excellent</span>"
    elif completion_pct >= 75:
        quality = "<span class='great'>🔵 Great</span>"
    elif completion_pct >= 50:
        quality = "<span class='good'>🟡 Good</span>"
    else:
        quality = "<span class='poor'>🔴 Needs Work</span>"

    missing_roadmap_items = "\n".join(
        f"<li><span class='no'>MISSING</span> {esc(r[1])} – {esc(r[2])}</li>"
        for r in full_rows
        if not r[3]
    )

    if missing_count == 0:
        roadmap_message = "This show is complete."
        missing_roadmap_items = "<li><span class='yes'>COMPLETE</span> Every listed track is in your library.</li>"
    elif missing_count == 1:
        roadmap_message = "Add 1 more track to complete this show."
    else:
        roadmap_message = f"Add these {missing_count} tracks to complete this show."

    roadmap_card = f"""
<div class="card">
<h2>Show Completion Roadmap</h2>
<p class="small">{roadmap_message}</p>


<h2>📻 WEFUNK Snapshot</h2>
<div class="grid">

  <div class="card"><div class="stat">{missing_count}</div><div class="label">Tracks Needed</div></div>
  <div class="card"><div class="stat">{completion_pct}%</div><div class="label">Current Completion</div></div>
  <div class="card"><div class="stat">100%</div><div class="label">After Completing</div></div>
</div>

<ul class="roadmap-list">
{missing_roadmap_items}
</ul>
</div>
"""

    art_path = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "artwork" / 'episodes' / f"{show_id}.jpg"
    episode_art_html = ""
    if art_path.exists():
        episode_art_html = f"<img class='episode-art' src='/episode-art/{show_id}.jpg' alt='WEFUNK Show {show_id} artwork'>"

    if "play_counts" not in globals():
        play_counts = {
            r["show_id"]: r
            for r in load_csv(
                Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve() / 'wefunk_show_play_counts.csv'
            )
        }

    pc = play_counts.get(str(show_id), {})
    play_count = pc.get("play_count", "0") or "0"
    last_played = pc.get("last_played", "")
    last_played_short = z_date_short(last_played[:10]) if last_played else "Never"

    play_stats_html = f"""
<div class="grid">
  <div class="card"><div class="stat">{esc(play_count)}</div><div class="label">Plays</div></div>
  <div class="card"><div class="stat">{esc(last_played_short)}</div><div class="label">Last Played</div></div>
</div>
"""

    rows_html = []

    for pos, r in enumerate(full_rows, start=1):
        _, wf_artist, wf_track, lib_artist, lib_title, score = r
        status = "owned" if lib_artist else "missing"
        artist_slug = artist_slugify(wf_artist)
        match_text = f"{lib_artist} - {lib_title}" if lib_artist else ""

        search_index.append(
            {
                "show": show_id,
                "artist": wf_artist,
                "artist_slug": artist_slug,
                "track": wf_track,
                "status": status,
                "match": match_text,
                "url": f"/shows/{show_id}.html",
            }
        )

        artist_key = normalize_artist_name(wf_artist)
        if artist_key:
            appearance = {
                "show": show_id,
                "artist": wf_artist,
                "track": wf_track,
                "status": status,
                "match": match_text,
                "score": score or "",
                "url": f"/shows/{show_id}.html",
            }

            # Existing artist-page dataset. Keep this unchanged for now.
            artist_pages[artist_key].append(appearance)

            # New canonical artist index.
            artist_entry = artist_index[artist_slug]
            if not artist_entry["display_name"]:
                artist_entry["display_name"] = wf_artist

            artist_entry["normalized_name"] = artist_key
            artist_entry["wefunk"].append(appearance)

        if status == "missing":
            missing_key = (artist_key, wf_track.lower().strip())
            missing_tracks[missing_key].append(
                {
                    "show": show_id,
                    "artist": wf_artist,
                    "artist_slug": artist_slug,
                    "track": wf_track,
                    "url": f"/shows/{show_id}.html",
                }
            )

        rows_html.append(
            f"<tr>"
            f"<td>{pos}</td>"
            f"<td class='{'yes' if status == 'owned' else 'no'}'>{status.upper()}</td>"
            f"<td><a href='/artists/{artist_slug}.html'>{esc(wf_artist)}</a></td>"
            f"<td>{esc(wf_track)}</td>"
            f"<td>{esc(match_text)}</td>"
            f"<td>{esc(score or '')}</td>"
            f"</tr>"
        )

    body = f"""
<div class="card">
<p><a href="/">← Back</a></p>
<h2>WEFUNK Show {esc(show_id)}</h2>
{episode_art_html}
{play_stats_html}
<p class="small">{esc(meta[1] if meta else '')} • {esc(meta[2] if meta else '')}</p>
<p>{esc(meta[4] if meta else '')}</p>
<p><a href="{esc(meta[3] if meta else '#')}">Open WEFUNK page</a></p>
</div>

<div class="grid">
  <div class="card">
    <div class="stat">{total_tracks}</div>
    <div class="label">Tracks</div>
  </div>

  <div class="card">
    <div class="stat">{owned_count}</div>
    <div class="label">Owned</div>
  </div>

  <div class="card">
    <div class="stat">{missing_count}</div>
    <div class="label">Missing</div>
  </div>

  <div class="card">
    <div class="stat">{completion_pct}%</div>
    <div class="label">Completion</div>
  </div>


  <div class="card">
    <div class="stat">{quality}</div>
    <div class="label">Quality</div>
  </div>
</div>

<div class="card">
    <div class="label">Collection Progress</div>

    <div class="bar" style="margin-top:10px;">
        <div class="fill" style="width:{completion_pct}%"></div>
    </div>

    <div class="small" style="margin-top:10px;">
        {owned_count} of {total_tracks} tracks in your library
    </div>
</div>

{roadmap_card}

<div class="card">
<h2>Full Tracklist</h2>
<input id="showFilter" placeholder="Filter this show..." oninput="filterTable('showFilter','showTracks')">
<table id="showTracks">
<thead>
<tr>
<th onclick="sortTable('showTracks',0,true)">#</th>
<th onclick="sortTable('showTracks',1)">Status</th>
<th onclick="sortTable('showTracks',2)">Artist</th>
<th onclick="sortTable('showTracks',3)">Track</th>
<th onclick="sortTable('showTracks',4)">Your Library Match</th>
<th onclick="sortTable('showTracks',5,true)">Score</th>
</tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</div>
"""
    (SHOWS_DIR / f"{show_id}.html").write_text(
        page(f"WEFUNK Show {show_id}", body), encoding="utf-8"
    )

# Add artists and albums discovered through matched library metadata.
#
# This ensures that artists linked from album pages are represented in the
# canonical index even when they do not have a primary WEFUNK appearance.
for row in owned_tracks_enriched:
    album = str(row.get("matched_album") or "").strip()
    album_artist = str(
        row.get("matched_album_artist")
        or row.get("library_artist")
        or row.get("artist")
        or ""
    ).strip()

    if not album_artist:
        continue

    artist_slug = artist_slugify(album_artist)
    artist_entry = artist_index[artist_slug]

    if not artist_entry["display_name"]:
        artist_entry["display_name"] = album_artist

    if not artist_entry["normalized_name"]:
        artist_entry["normalized_name"] = normalize_artist_name(album_artist)

    if not album:
        continue

    album_slug = str(
        row.get("matched_album_slug") or slugify(f"{album_artist}-{album}")
    ).strip()

    if not album_slug:
        continue

    album_entry = artist_entry["albums"].setdefault(
        album_slug,
        {
            "album": album,
            "slug": album_slug,
            "year": str(row.get("matched_year") or "").strip(),
            "genre": str(row.get("matched_genre") or "").strip(),
            "matched_tracks": set(),
        },
    )

    track_name = str(
        row.get("matched_title") or row.get("library_title") or row.get("track") or ""
    ).strip()

    if track_name:
        album_entry["matched_tracks"].add(track_name)



def track_display_name(track, match="", status=""):
    """
    Return a presentation-quality track title without changing stored data.

    Owned matches prefer the properly cased library title. Missing tracks
    receive conservative title casing based on the WEFUNK title.
    """
    track = str(track or "").strip()
    match = str(match or "").strip()
    status = str(status or "").strip().lower()

    if status == "owned" and " - " in match:
        matched_title = match.split(" - ", 1)[1].strip()

        if matched_title:
            return matched_title

    if not track:
        return ""

    small_words = {
        "a", "an", "and", "as", "at", "but", "by", "for", "from",
        "in", "into", "nor", "of", "on", "or", "over", "the",
        "to", "up", "via", "with",
    }

    words = track.split()
    formatted = []

    for index, word in enumerate(words):
        if not word:
            continue

        prefix = ""
        suffix = ""

        while word and not word[0].isalnum():
            prefix += word[0]
            word = word[1:]

        while word and not word[-1].isalnum():
            suffix = word[-1] + suffix
            word = word[:-1]

        if not word:
            formatted.append(prefix + suffix)
            continue

        lower = word.lower()

        if index not in (0, len(words) - 1) and lower in small_words:
            converted = lower
        else:
            converted = lower[:1].upper() + lower[1:]

        # Correct lowercase letters following apostrophes without producing
        # Python str.title() results such as "Can'T".
        converted = converted.replace("'S", "'s")
        converted = converted.replace("'T", "'t")
        converted = converted.replace("'Re", "'re")
        converted = converted.replace("'Ve", "'ve")
        converted = converted.replace("'Ll", "'ll")
        converted = converted.replace("'D", "'d")
        converted = converted.replace("'M", "'m")

        formatted.append(prefix + converted + suffix)

    return " ".join(formatted)



for slug, artist_record in sorted(artist_index.items()):
    artist_key = (
        artist_record["normalized_name"]
        or normalize_artist_name(artist_record["display_name"])
        or slug.replace("-", " ")
    )

    canonical_asset_slug = artist_asset_aliases.get(slug, slug)

    display_name = (
        artist_display_names.get(slug)
        or artist_display_names.get(canonical_asset_slug)
        or artist_record["display_name"]
        or artist_key.title()
    )

    items = artist_record["wefunk"]

    owned = [x for x in items if x["status"] == "owned"]
    missing = [x for x in items if x["status"] == "missing"]
    pct = round((len(owned) / len(items)) * 100, 1) if items else 0

    top_missing_tracks = {}
    for x in missing:
        key = x["track"]
        top_missing_tracks.setdefault(key, 0)
        top_missing_tracks[key] += 1

    top_missing_rows = "\n".join(
        f"<tr><td>{esc(track_display_name(track))}</td><td>{count}</td></tr>"
        for track, count in sorted(
            top_missing_tracks.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )[:25]
    )

    if not top_missing_rows:
        top_missing_rows = (
            "<tr><td colspan='2' class='small'>"
            "No missing WEFUNK tracks for this artist."
            "</td></tr>"
        )

    rows = "\n".join(
        f"<tr>"
        f"<td><a href='{esc(x['url'])}'>{esc(x['show'])}</a></td>"
        f"<td class='{'yes' if x['status'] == 'owned' else 'no'}'>{esc(x['status'].upper())}</td>"
        f"<td>{esc(artist_display_name(x['artist']))}</td>"
        f"<td>{esc(track_display_name(x['track'], x.get('match'), x.get('status')))}</td>"
        f"<td>{esc(x['match'])}</td>"
        f"<td>{esc(x['score'])}</td>"
        f"</tr>"
        for x in items
    )

    if not rows:
        rows = (
            "<tr><td colspan='6' class='small'>"
            "No primary WEFUNK appearances are currently listed for this artist."
            "</td></tr>"
        )

    own_artist_image_path = (
        SITE / "artist-images" / f"{slug}.jpg"
    )

    canonical_artist_image_path = (
        SITE
        / "artist-images"
        / f"{canonical_asset_slug}.jpg"
    )

    if own_artist_image_path.exists():
        artist_image_slug = slug
        artist_image_path = own_artist_image_path
    elif canonical_artist_image_path.exists():
        artist_image_slug = canonical_asset_slug
        artist_image_path = canonical_artist_image_path
    else:
        artist_image_slug = ""
        artist_image_path = None

    if artist_image_slug and artist_image_path:
        artist_image_version = int(artist_image_path.stat().st_mtime)

        artist_visual = (
            f"<img class='artist-profile-image' "
            f"src='/artist-images/{esc(artist_image_slug)}.jpg?v={artist_image_version}' "
            f"alt='{esc(display_name)}' "
            f"loading='eager'>"
        )
    else:
        artist_initial = next(
            (character.upper() for character in display_name if character.isalnum()),
            "♪",
        )

        artist_visual = (
            "<div class='artist-profile-placeholder' "
            "aria-hidden='true'>"
            f"{esc(artist_initial)}"
            "</div>"
        )

    bio_record = artist_bios.get(slug, {})

    if (
        not str(bio_record.get("biography") or "").strip()
        and canonical_asset_slug != slug
    ):
        bio_record = artist_bios.get(
            canonical_asset_slug,
            bio_record,
        )

    artist_biography = str(
        bio_record.get("biography") or ""
    ).strip()

    artist_lastfm_url = str(
        bio_record.get("lastfm_url") or ""
    ).strip()

    if artist_biography:
        biography_source = ""

        if artist_lastfm_url:
            biography_source = (
                "<p class='small' style='margin-top:14px;'>"
                f"<a href='{esc(artist_lastfm_url)}' "
                "target='_blank' rel='noopener noreferrer'>"
                "Artist information source"
                "</a>"
                "</p>"
            )

        artist_bio_html = f"""
<div class="card artist-biography">
  <h2>Artist Biography</h2>
  <p>{esc(artist_biography)}</p>
  {biography_source}
</div>
"""
    else:
        artist_bio_html = ""

    body = f"""
<div class="card artist-profile">
  <div class="artist-profile-image-wrap">
    {artist_visual}
  </div>

  <div class="artist-profile-details">
    <p><a href="/">← Back</a></p>
    <h2>{esc(display_name)}</h2>
    <p class="small">Artist collection scorecard across all WEFUNK appearances.</p>
  </div>
</div>

{artist_bio_html}

<div class="grid">
  <div class="card"><div class="stat">{len(items)}</div><div class="label">WEFUNK Appearances</div></div>
  <div class="card"><div class="stat">{len(owned)}</div><div class="label">Owned</div></div>
  <div class="card"><div class="stat">{len(missing)}</div><div class="label">Missing</div></div>
  <div class="card"><div class="stat">{pct}%</div><div class="label">Completion</div></div>
</div>

<div class="card">
  <div class="label">Artist Collection Progress</div>
  <div class="bar" style="margin-top:10px;">
    <div class="fill" style="width:{pct}%"></div>
  </div>
  <div class="small" style="margin-top:10px;">
    {len(owned)} of {len(items)} WEFUNK appearances are matched in your library.
  </div>
</div>

<div class="card">
<h2>Top Missing Tracks</h2>
<p class="small">The missing tracks by this artist that appear most often across WEFUNK shows.</p>
<table id="artistMissing">
<thead>
<tr>
<th onclick="sortTable('artistMissing',0)">Track</th>
<th onclick="sortTable('artistMissing',1,true)">Missing From Shows</th>
</tr>
</thead>
<tbody>
{top_missing_rows}
</tbody>
</table>
</div>

<div class="card">
<h2>All WEFUNK Appearances</h2>
<input id="artistFilter" placeholder="Filter artist page..." oninput="filterTable('artistFilter','artistTracks')">
<table id="artistTracks">
<thead>
<tr>
<th onclick="sortTable('artistTracks',0,true)">Show</th>
<th onclick="sortTable('artistTracks',1)">Status</th>
<th onclick="sortTable('artistTracks',2)">Listed Artist</th>
<th onclick="sortTable('artistTracks',3)">Track</th>
<th onclick="sortTable('artistTracks',4)">Your Match</th>
<th onclick="sortTable('artistTracks',5,true)">Score</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</div>
"""
    (ARTISTS_DIR / f"{slug}.html").write_text(
        page(f"Artist: {display_name}", body), encoding="utf-8"
    )


# WEFUNK DNA page

genre_dna = []
genre_csv = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve() / 'wefunk_genre_dna.csv'
if genre_csv.exists():
    genre_dna = load_csv(genre_csv)

max_genre_count = max([int(r["count"]) for r in genre_dna], default=1)

genre_heatmap_rows = "\n".join(
    f"<a class='genre-tile' href='/genres/{slugify(r['genre'])}.html' style='background:rgba(247,147,30,{0.18 + (int(r['count']) / max_genre_count) * 0.55}); text-decoration:none; color:inherit;'>"
    f"<div class='genre-name'>{esc(r['genre'])}</div>"
    f"<div class='genre-count'>{esc(r['count'])} matched tracks</div>"
    f"</a>"
    for r in genre_dna[:40]
)


dna_artists = []

for artist_key, items in artist_pages.items():
    owned = [x for x in items if x["status"] == "owned"]
    missing = [x for x in items if x["status"] == "missing"]
    total = len(items)
    if total == 0:
        continue

    pct = round((len(owned) / total) * 100, 1)
    dna_artists.append(
        {
            "artist": artist_key.title(),
            "slug": artist_slugify(artist_key),
            "total": total,
            "owned": len(owned),
            "missing": len(missing),
            "pct": pct,
        }
    )

signature_artists = sorted(dna_artists, key=lambda x: x["owned"], reverse=True)[:25]
strongest_artists = sorted(
    [x for x in dna_artists if x["total"] >= 5],
    key=lambda x: (x["pct"], x["owned"]),
    reverse=True,
)[:25]
blind_spots = sorted(
    [x for x in dna_artists if x["total"] >= 5], key=lambda x: (x["pct"], -x["total"])
)[:25]

artist_heatmap_source = sorted(
    [x for x in dna_artists if x["total"] >= 5], key=lambda x: x["owned"], reverse=True
)[:60]

max_artist_owned = max([x["owned"] for x in artist_heatmap_source], default=1)

artist_heatmap_rows = "\n".join(
    f"<a class='artist-tile' href='/artists/{esc(r['slug'])}.html' "
    f"style='background:rgba(247,147,30,{0.14 + (r['owned'] / max_artist_owned) * 0.60});'>"
    f"<div class='artist-name'>{esc(r['artist'])}</div>"
    f"<div class='artist-count'>{esc(r['owned'])} owned / {esc(r['total'])} appearances</div>"
    f"<div class='artist-pct'>{esc(r['pct'])}% complete</div>"
    f"</a>"
    for r in artist_heatmap_source
)


def dna_rows(rows):
    return "\n".join(
        f"<tr>"
        f"<td><a href='/artists/{esc(r['slug'])}.html'>{esc(r['artist'])}</a></td>"
        f"<td>{esc(str(r['owned']))} / {esc(str(r['total']))}</td>"
        f"<td>{esc(r['missing'])}</td>"
        f"<td>{esc(str(r['pct']))}%</td>"
        f"<td><div class='bar'><div class='fill' style='width:{esc(r['pct'])}%'></div></div></td>"
        f"</tr>"
        for r in rows
    )


dna_body = f"""
<div class="card">
<p><a href="/">← Back</a></p>
<h2>WEFUNK DNA</h2>
<p class="small">A snapshot of your WEFUNK collection identity based on artists you own, artists you are strongest on, and blind spots to improve.</p>
</div>

<div class="grid">
  <div class="card"><div class="stat">{len(dna_artists)}</div><div class="label">Artists Analyzed</div></div>
  <div class="card"><div class="stat">{sum(x['owned'] for x in dna_artists)}</div><div class="label">Owned Artist Appearances</div></div>
  <div class="card"><div class="stat">{sum(x['missing'] for x in dna_artists)}</div><div class="label">Missing Artist Appearances</div></div>
  <div class="card"><div class="stat">{signature_artists[0]['artist'] if signature_artists else '—'}</div><div class="label">Signature Artist</div></div>
</div>

<div class="card">
<h2>Genre Heat Map</h2>
<p class="small">Genres represented most strongly in your matched WEFUNK collection.</p>
<div class="genre-heatmap">
{genre_heatmap_rows}
</div>
</div>

<div class="card">
<h2>Artist Heat Map</h2>
<p class="small">Artists with the strongest matched presence in your WEFUNK collection. Darker tiles mean more owned WEFUNK appearances.</p>
<div class="artist-heatmap">
{artist_heatmap_rows}
</div>
</div>

<div class="card">
<h2>Signature Artists</h2>
<p class="small">Artists you own the most WEFUNK appearances for.</p>
<table id="signatureArtists">
<thead>
<tr>
<th onclick="sortTable('signatureArtists',0)">Artist</th>
<th onclick="sortTable('signatureArtists',1,true)">Owned / Total</th>
<th onclick="sortTable('signatureArtists',2,true)">Missing</th>
<th onclick="sortTable('signatureArtists',3,true)">Completion</th>
<th></th>
</tr>
</thead>
<tbody>
{dna_rows(signature_artists)}
</tbody>
</table>
</div>

<div class="card">
<h2>Collection Strengths</h2>
<p class="small">Artists with at least 5 WEFUNK appearances where your collection is strongest.</p>
<table id="strongestArtists">
<thead>
<tr>
<th onclick="sortTable('strongestArtists',0)">Artist</th>
<th onclick="sortTable('strongestArtists',1,true)">Owned / Total</th>
<th onclick="sortTable('strongestArtists',2,true)">Missing</th>
<th onclick="sortTable('strongestArtists',3,true)">Completion</th>
<th></th>
</tr>
</thead>
<tbody>
{dna_rows(strongest_artists)}
</tbody>
</table>
</div>

<div class="card">
<h2>Biggest Blind Spots</h2>
<p class="small">Artists with at least 5 WEFUNK appearances where you have the most room to improve.</p>
<table id="blindSpots">
<thead>
<tr>
<th onclick="sortTable('blindSpots',0)">Artist</th>
<th onclick="sortTable('blindSpots',1,true)">Owned / Total</th>
<th onclick="sortTable('blindSpots',2,true)">Missing</th>
<th onclick="sortTable('blindSpots',3,true)">Completion</th>
<th></th>
</tr>
</thead>
<tbody>
{dna_rows(blind_spots)}
</tbody>
</table>
</div>
"""

(SITE / "dna.html").write_text(page("WEFUNK DNA", dna_body), encoding="utf-8")


missing_rows = []
for (artist_key, track_key), entries in sorted(
    missing_tracks.items(), key=lambda kv: len(kv[1]), reverse=True
):
    first = entries[0]
    show_links = ", ".join(
        f"<a href='{esc(e['url'])}'>{esc(e['show'])}</a>" for e in entries[:12]
    )
    if len(entries) > 12:
        show_links += f" + {len(entries)-12} more"

    q = quote_plus(f"{first['artist']} {first['track']}")

    missing_rows.append(
        f"<tr>"
        f"<td><a href='/artists/{esc(first['artist_slug'])}.html'>{esc(first['artist'])}</a></td>"
        f"<td>{esc(first['track'])}</td>"
        f"<td>{len(entries)}</td>"
        f"<td>{show_links}</td>"
        f"<td>"
        f"<a href='https://www.discogs.com/search/?q={q}&type=all'>Discogs</a> · "
        f"<a href='https://www.youtube.com/results?search_query={q}'>YouTube</a> · "
        f"<a href='https://bandcamp.com/search?q={q}'>Bandcamp</a> · "
        f"<a href='https://music.apple.com/search?term={q}'>Apple Music</a>"
        f"</td>"
        f"</tr>"
    )

missing_body = f"""
<div class="card">
<p><a href="/">← Back</a></p>
<h2>Missing Tracks</h2>
<p class="small">Tracks appearing in WEFUNK playlists that were not matched in your library.</p>
<input id="missingFilter" placeholder="Filter missing tracks..." oninput="filterTable('missingFilter','missingTracks')">
<table id="missingTracks">
<thead>
<tr>
<th onclick="sortTable('missingTracks',0)">Artist</th>
<th onclick="sortTable('missingTracks',1)">Track</th>
<th onclick="sortTable('missingTracks',2,true)">Shows</th>
<th>Missing From</th>\n<th>Search</th>
</tr>
</thead>
<tbody>
{''.join(missing_rows)}
</tbody>
</table>
</div>
"""
(SITE / "missing.html").write_text(
    page("Missing Tracks", missing_body), encoding="utf-8"
)


shopping_rows = []
unknown_values = {
    "",
    "unknown",
    "unknown song",
    "(unknown song)",
    "???",
    "??",
    "untitled",
    "n/a",
    "na",
    "-",
}

for (artist_key, track_key), entries in sorted(
    missing_tracks.items(), key=lambda kv: len(kv[1]), reverse=True
):
    first = entries[0]
    artist = first["artist"]
    track = first["track"]

    if str(artist).strip().lower() in unknown_values:
        continue
    if (
        str(track).strip().lower() in unknown_values
        or "unknown song" in str(track).strip().lower()
    ):
        continue
    q = quote_plus(f"{artist} {track}")

    show_links = ", ".join(
        f"<a href='{esc(e['url'])}'>{esc(e['show'])}</a>" for e in entries[:10]
    )

    if len(entries) > 10:
        show_links += f" + {len(entries) - 10} more"

    shopping_rows.append(
        f"<tr>"
        f"<td><a href='/artists/{esc(first['artist_slug'])}.html'>{esc(artist)}</a></td>"
        f"<td>{esc(track)}</td>"
        f"<td>{len(entries)}</td>"
        f"<td>{show_links}</td>"
        f"<td>"
        f"<a href='https://www.discogs.com/search/?q={q}&type=all'>Discogs</a> · "
        f"<a href='https://www.youtube.com/results?search_query={q}'>YouTube</a> · "
        f"<a href='https://bandcamp.com/search?q={q}'>Bandcamp</a>"
        f"</td>"
        f"</tr>"
    )

shopping_body = f"""
<div class="card">
<p><a href="/">← Back</a></p>
<h2>Smart Shopping List</h2>
<p class="small">
Missing tracks ranked by how many WEFUNK shows they would improve.
</p>

<input id="shoppingFilter" placeholder="Filter shopping list..." oninput="filterTable('shoppingFilter','shoppingList')">

<table id="shoppingList">
<thead>
<tr>
<th onclick="sortTable('shoppingList',0)">Artist</th>
<th onclick="sortTable('shoppingList',1)">Track</th>
<th onclick="sortTable('shoppingList',2,true)">Shows Improved</th>
<th>Appears In</th>
<th>Search</th>
</tr>
</thead>
<tbody>
{''.join(shopping_rows[:500])}
</tbody>
</table>
</div>
"""

(SITE / "shopping.html").write_text(
    page("Smart Shopping List", shopping_body), encoding="utf-8"
)


episode_play_counts = {
    r["show_id"]: r
    for r in load_csv(Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve() / 'wefunk_show_play_counts.csv')
}

all_episode_rows = "\n".join(
    f"<tr>"
    f"<td><a href='/shows/{esc(r['show_id'])}.html'>{esc(r['show_id'])}</a></td>"
    f"<td data-sort='{z_date_sort(r['recorded'])}'>{esc(z_date_short(r['recorded']))}</td>"
    f"<td>{esc(r['djs'])}</td>"
    f"<td data-sort='{int(episode_play_counts.get(r['show_id'], {}).get('play_count') or 0)}'>{esc(episode_play_counts.get(r['show_id'], {}).get('play_count') or '0')}</td>"
    f"<td>{esc(r['matched_tracks'])}/{esc(r['total_tracks'])}</td>"
    f"<td>{esc(r['match_percent'])}%</td>"
    f"<td><div class='bar'><div class='fill' style='width:{esc(r['match_percent'])}%'></div></div></td>"
    f"</tr>"
    for r in sorted(shows, key=lambda x: int(x["show_id"]), reverse=True)
)

episodes_body = f"""
<div class="card">
<p><a href="/">← Back</a></p>
<h2>All Episodes Archive</h2>
<p class="small">Every WEFUNK episode in your dashboard, newest first.</p>

<input id="episodesFilter" placeholder="Filter episodes by show, date, DJ..." oninput="filterTable('episodesFilter','episodesArchive')">

<table id="episodesArchive">
<thead>
<tr>
<th onclick="sortTable('episodesArchive',0,true)">Show</th>
<th onclick="sortTable('episodesArchive',1)">Date</th>
<th onclick="sortTable('episodesArchive',2)">DJs</th>
<th onclick="sortTable('episodesArchive',3,true)">Plays</th>
<th onclick="sortTable('episodesArchive',4,true)">Matched</th>
<th onclick="sortTable('episodesArchive',5,true)">Match %</th>
<th></th>
</tr>
</thead>
<tbody>
{all_episode_rows}
</tbody>
</table>
</div>
"""

(SITE / "episodes.html").write_text(
    page("All Episodes Archive", episodes_body), encoding="utf-8"
)


top_rows = "\n".join(
    f"<tr><td><a href='/shows/{esc(r['show_id'])}.html'>{esc(r['show_id'])}</a></td>"
    f"<td>{esc(r['recorded'])}</td><td>{esc(r['djs'])}</td>"
    f"<td>{esc(r['matched_tracks'])}</td><td>{esc(r['total_tracks'])}</td>"
    f"<td>{esc(r['match_percent'])}%</td>"
    f"<td><div class='bar'><div class='fill' style='width:{esc(r['match_percent'])}%'></div></div></td></tr>"
    for r in shows[:100]
)

recommended_album_rows = "\n".join(
    f"<tr><td>{esc(r['artist'])}</td>"
    f"<td>{esc(r['album'])}</td>"
    f"<td>{esc(r.get('tracks_gained', r.get('matched_tracks', '')))}</td>"
    f"<td>{esc(r.get('shows_improved', ''))}</td></tr>"
    for r in recommended_albums[:100]
)


missing_artist_rows = "\n".join(
    f"<tr><td><a href='/artists/{artist_slugify(r['artist'])}.html'>{esc(r['artist'])}</a></td><td>{esc(r['missing_count'])}</td></tr>"
    for r in missing_artists[:100]
)


almost_complete_candidates = [
    r
    for r in sorted(
        shows,
        key=lambda x: (
            float(x["total_tracks"]) - float(x["matched_tracks"]),
            -float(x["match_percent"]),
        ),
    )
    if float(r["match_percent"]) < 100 and float(r["match_percent"]) >= 75
][:50]


almost_complete_candidates = [
    r
    for r in sorted(
        shows,
        key=lambda x: (
            float(x["total_tracks"]) - float(x["matched_tracks"]),
            -float(x["match_percent"]),
        ),
    )
    if float(r["match_percent"]) < 100
][:50]

almost_complete_rows = "\n".join(
    f"<tr>"
    f"<td><a href='/shows/{esc(r['show_id'])}.html'>{esc(r['show_id'])}</a></td>"
    f"<td data-sort='{z_date_sort(r['recorded'])}'>{esc(z_date_short(r['recorded']))}</td>"
    f"<td>{esc(r['djs'])}</td>"
    f"<td>{esc(r['matched_tracks'])}/{esc(r['total_tracks'])}</td>"
    f"<td>{esc(r['match_percent'])}%</td>"
    f"<td>"
    f"{esc(missing_by_show.get(r['show_id'], [''])[0])}"
    f"{('<details><summary>+ ' + str(len(missing_by_show.get(r['show_id'], []))-1) + ' more tracks</summary>' + '<br>'.join(esc(x) for x in missing_by_show.get(r['show_id'], [])[1:]) + '</details>') if len(missing_by_show.get(r['show_id'], [])) > 1 else ''}"
    f"</td>"
    f"</tr>"
    for r in almost_complete_candidates
)


collection_scores = [float(r["match_percent"]) for r in shows if r.get("match_percent")]
average_completion = (
    round(sum(collection_scores) / len(collection_scores), 1)
    if collection_scores
    else 0
)

complete_shows = sum(1 for r in shows if float(r["match_percent"]) >= 100)
excellent_shows = sum(1 for r in shows if float(r["match_percent"]) >= 20)
great_shows = sum(1 for r in shows if 15 <= float(r["match_percent"]) < 20)
good_shows = sum(1 for r in shows if 10 <= float(r["match_percent"]) < 15)
needs_work_shows = sum(1 for r in shows if float(r["match_percent"]) < 10)

total_wefunk_tracks = sum(int(float(r["total_tracks"])) for r in shows)
total_matched_tracks = sum(int(float(r["matched_tracks"])) for r in shows)
total_missing_tracks = total_wefunk_tracks - total_matched_tracks
overall_completion = (
    round((total_matched_tracks / total_wefunk_tracks) * 100, 2)
    if total_wefunk_tracks
    else 0
)

collection_score_section = f"""
<div class="card">
<h2>🏆 Collection Score</h2>

<div class="grid">
  <div class="card"><div class="stat">{overall_completion}%</div><div class="label">Overall Completion</div></div>
  <div class="card"><div class="stat">{total_matched_tracks}</div><div class="label">Matched Tracks</div></div>
  <div class="card"><div class="stat">{average_completion}%</div><div class="label">Average Show Completion</div></div>
  <div class="card"><div class="stat">{total_missing_tracks}</div><div class="label">Missing Tracks</div></div>
</div>

<div class="bar" style="margin-top:12px;">
  <div class="fill" style="width:{overall_completion}%"></div>
</div>

<div class="grid" style="margin-top:18px;">
  <div class="card"><div class="stat">🟢 {excellent_shows}</div><div class="label">Excellent 20%+</div></div>
  <div class="card"><div class="stat">🔵 {great_shows}</div><div class="label">Great 15–20%</div></div>
  <div class="card"><div class="stat">🟡 {good_shows}</div><div class="label">Good 10–15%</div></div>
  <div class="card"><div class="stat">🔴 {needs_work_shows}</div><div class="label">Needs Work <10%</div></div>
</div>
</div>
"""

body = f"""
<div class="card">
<h2>📻 WEFUNK Snapshot</h2>
<div class="grid">
  <div class="card"><div class="stat">{total_shows}</div><div class="label">Shows analyzed</div></div>
  <div class="card"><div class="stat">{total_matched_tracks}</div><div class="label">Matched tracks</div></div>
  <div class="card"><div class="stat">{overall_completion}%</div><div class="label">Archive match rate</div></div>
  <div class="card"><div class="stat">{esc(best['show_id'])}</div><div class="label">Best matching show</div></div>
</div>
</div>
</div>

{collection_score_section}

<div class="card">
<h2>Reports</h2>
<div class="report-grid">

<a class="report-card" href="/missing.html">
  <div class="report-icon">🎯</div>
  <div class="report-title">Missing Tracks</div>
  <div class="report-desc">All tracks missing from your library, ranked by WEFUNK appearances.</div>
</a>

<a class="report-card" href="/shopping.html">
  <div class="report-icon">🛒</div>
  <div class="report-title">Smart Shopping List</div>
  <div class="report-desc">Actionable missing tracks with one-click search links.</div>
</a>

<a class="report-card" href="/dna.html">
  <div class="report-icon">🎧</div>
  <div class="report-title">WEFUNK DNA</div>
  <div class="report-desc">Your strongest artists, signature sounds, and biggest blind spots.</div>
</a>

<a class="report-card" href="/episodes.html">
  <div class="report-icon">📻</div>
  <div class="report-title">All Episodes Archive</div>
  <div class="report-desc">Browse every WEFUNK episode in your dashboard archive.</div>
</a>

<a class="report-card" href="/recent-matches.html">
  <div class="report-icon">🆕</div>
  <div class="report-title">Recent Matches</div>
  <div class="report-desc">See newly discovered tracks matched from recent scans.</div>
</a>


</div>
</div>

<div class="card">
<h2>Best Matching Shows</h2>
<table id="topShows">
<thead>
<tr>
<th onclick="sortTable('topShows',0,true)">Show</th>
<th onclick="sortTable('topShows',1)">Date</th>
<th onclick="sortTable('topShows',2)">DJs</th>
<th onclick="sortTable('topShows',3,true)">Matched</th>
<th onclick="sortTable('topShows',4,true)">Total</th>
<th onclick="sortTable('topShows',5,true)">Match %</th>

</tr>
</thead>
<tbody>
{top_rows}
</tbody>
</table>
</div>

<div class="card">
<h2>Almost Complete Shows</h2>
<p class="small">Shows that are close to complete, sorted by fewest missing tracks.</p>

<table id="almostComplete">
<thead>
<tr>
<th onclick="sortTable('almostComplete',0,true)">Show</th>
<th onclick="sortTable('almostComplete',1)">Date</th>
<th onclick="sortTable('almostComplete',2)">DJs</th>
<th onclick="sortTable('almostComplete',3,true)">Matched</th>
<th onclick="sortTable('almostComplete',4,true)">Match %</th>
<th>Missing Tracks</th>

</tr>
</thead>
<tbody>
{almost_complete_rows}
</tbody>
</table>
</div>


<div class="card">
<h2>Recommended Albums</h2>

<p class="small">
Albums already represented heavily in WEFUNK.
Buying these will likely increase your collection the fastest.
</p>

<table id="recommendedAlbums">
<thead>
<tr>
<th onclick="sortTable('recommendedAlbums',0)">Artist</th>
<th onclick="sortTable('recommendedAlbums',1)">Album</th>
<th onclick="sortTable('recommendedAlbums',2,true)">Tracks Gained</th>\n<th onclick="sortTable('recommendedAlbums',3,true)">Shows Improved</th>
</tr>
</thead>
<tbody>
{recommended_album_rows}
</tbody>
</table>

</div>


<div class="card">
<h2>Top Missing Artists</h2>
<table id="missingArtists">
<thead><tr>
<th onclick="sortTable('missingArtists',0)">Artist</th>
<th onclick="sortTable('missingArtists',1,true)">Missing count</th>
</tr></thead>
<tbody>
{missing_artist_rows}
</tbody>
</table>
</div>

<script>
let data = [];
fetch('/data/search_index.json').then(r => r.json()).then(j => data = j);

function doGlobalSearch(){{ doSearch(); }}

function doSearch(){{
  const q = document.getElementById('globalSearch').value.toLowerCase();
  const box = document.getElementById('globalResults');
  if(q.length < 2){{ box.innerHTML = ''; return; }}
  const hits = data.filter(x =>
    (x.artist||'').toLowerCase().includes(q) ||
    (x.track||'').toLowerCase().includes(q) ||
    (x.match||'').toLowerCase().includes(q) ||
    (x.status||'').toLowerCase().includes(q)
  ).slice(0, 75);
  box.innerHTML = '<table id="searchTable"><thead><tr><th>Show</th><th>Status</th><th>Artist</th><th>Track</th><th>Your Match</th></tr></thead><tbody>' +
    hits.map(x => `<tr><td><a href="${{x.url}}">${{x.show}}</a></td><td>${{x.status}}</td><td><a href="/artists/${{x.artist_slug}}.html">${{x.artist}}</a></td><td>${{x.track}}</td><td>${{x.match}}</td></tr>`).join('') +
    '</tbody></table>';
}}
</script>
"""

(SITE / "index.html").write_text(page("WEFUNK Dashboard", body), encoding="utf-8")
(DATA_DIR / "search_index.json").write_text(json.dumps(search_index), encoding="utf-8")

conn.close()


print("Generated dashboard:")
print(f"  {SITE / 'index.html'}")
print(f"  {len(shows)} show pages")
print(f"  {len(artist_pages)} artist pages")

canonical_wefunk_artists = sum(
    1 for artist in artist_index.values() if artist["wefunk"]
)

canonical_album_artists = sum(1 for artist in artist_index.values() if artist["albums"])

canonical_album_only_artists = sum(
    1 for artist in artist_index.values() if artist["albums"] and not artist["wefunk"]
)

print(f"  {len(artist_index)} canonical artists")
print(f"  {canonical_wefunk_artists} canonical artists with WEFUNK appearances")
print(f"  {canonical_album_artists} canonical artists with owned albums")
print(f"  {canonical_album_only_artists} album-only artists awaiting pages")
print(f"  {len(missing_tracks)} missing track groups")
print(f"  {len(search_index)} search entries")
