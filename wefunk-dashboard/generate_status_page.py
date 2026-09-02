#!/usr/bin/env python3

import json
import os
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from common import DATA_ROOT, SITE

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_FILE = Path(
    os.environ.get(
        "WEFUNK_DB_FILE",
        DATA_ROOT / "db" / "wefunk.db",
    )
).expanduser().resolve()

RECOVERY_DIR = Path(
    os.environ.get(
        "WEFUNK_RECOVERY_DIR",
        DATA_ROOT / "recovery",
    )
).expanduser().resolve()

PORT = int(
    os.environ.get(
        "WEFUNK_PORT",
        "8099",
    )
)

DASHBOARD_LABEL = os.environ.get(
    "WEFUNK_DASHBOARD_LABEL",
    "org.wefunk.dashboard",
)

NOWPLAYING_LABEL = os.environ.get(
    "WEFUNK_NOWPLAYING_LABEL",
    "org.wefunk.dashboard.nowplaying",
)

LOCAL_URL = f"http://127.0.0.1:{PORT}"

JSON_OUT = SITE / "status.json"


CORE_FILES = [
    "index.html",
    "search.html",
    "episodes.html",
    "albums.html",
    "genres.html",
    "years.html",
]


def human_bytes(value):
    value = int(value or 0)

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ]

    size = float(value)

    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"

            return f"{size:.1f} {unit}"

        size /= 1024

    return f"{value} B"


def age_seconds(timestamp):
    if timestamp is None:
        return None

    try:
        return max(
            0,
            int(time.time()) - int(timestamp),
        )
    except (TypeError, ValueError):
        return None


def human_age(seconds):
    if seconds is None:
        return None

    seconds = int(seconds)

    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60

    if minutes < 60:
        return f"{minutes}m"

    hours = minutes // 60

    if hours < 24:
        return f"{hours}h {minutes % 60}m"

    days = hours // 24

    return f"{days}d {hours % 24}h"


def directory_size(path):
    if not path.exists():
        return 0

    total = 0

    try:
        for item in path.rglob("*"):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except OSError:
                pass
    except OSError:
        pass

    return total


def service_status():
    domain = f"gui/{os.getuid()}/{DASHBOARD_LABEL}"

    try:
        result = subprocess.run(
            [
                "launchctl",
                "print",
                domain,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

        loaded = result.returncode == 0

    except OSError:
        loaded = False

    pid = None

    try:
        result = subprocess.run(
            [
                "lsof",
                "-nP",
                f"-iTCP:{PORT}",
                "-sTCP:LISTEN",
                "-t",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]

        if lines:
            pid = int(lines[0])

    except (OSError, ValueError):
        pid = None

    return {
        "loaded": loaded,
        "port": PORT,
        "listening": pid is not None,
    }


def http_status():
    try:
        request = urllib.request.Request(
            LOCAL_URL,
            method="GET",
        )

        with urllib.request.urlopen(
            request,
            timeout=3,
        ) as response:
            code = response.getcode()

        return {
            "reachable": True,
            "status": code,
        }

    except urllib.error.HTTPError as exc:
        return {
            "reachable": True,
            "status": exc.code,
        }

    except Exception:
        return {
            "reachable": False,
            "status": None,
        }


def database_status():
    result = {
        "exists": DB_FILE.exists(),
        "bytes": 0,
        "size": None,
        "quick_check": None,
        "healthy": False,
    }

    if not DB_FILE.exists():
        return result

    try:
        result["bytes"] = DB_FILE.stat().st_size
        result["size"] = human_bytes(result["bytes"])

        connection = sqlite3.connect(
            f"file:{DB_FILE}?mode=ro",
            uri=True,
        )

        try:
            row = connection.execute("PRAGMA quick_check").fetchone()

            check = row[0] if row else None

            result["quick_check"] = check
            result["healthy"] = check == "ok"

        finally:
            connection.close()

    except sqlite3.Error as exc:
        result["error"] = str(exc)

    return result


def site_status():
    files = {}

    for filename in CORE_FILES:
        path = SITE / filename

        files[filename] = {
            "exists": path.is_file(),
            "bytes": (path.stat().st_size if path.is_file() else 0),
        }

    homepage = SITE / "index.html"

    updated = None
    updated_epoch = None

    if homepage.exists():
        updated_epoch = int(homepage.stat().st_mtime)

        updated = datetime.fromtimestamp(updated_epoch).astimezone().isoformat()

    count_specs = {
        "shows": (
            SITE / "shows",
            "*.html",
        ),
        "artists": (
            SITE / "artists",
            "*.html",
        ),
        "albums": (
            SITE / "albums",
            "*.html",
        ),
        "genres": (
            SITE / "genres",
            "*.html",
        ),
        "years": (
            SITE / "years",
            "*.html",
        ),
        "episode_art": (
            SITE / "episode-art",
            "*.jpg",
        ),
    }

    counts = {}

    for name, (directory, pattern) in count_specs.items():
        if directory.exists():
            counts[name] = sum(1 for _ in directory.glob(pattern))
        else:
            counts[name] = 0

    search_index = SITE / "search-index.json"

    return {
        "core_files": files,
        "core_files_ok": all(
            item["exists"] and item["bytes"] > 0 for item in files.values()
        ),
        "homepage_updated": updated,
        "homepage_age_seconds": age_seconds(updated_epoch),
        "homepage_age": human_age(age_seconds(updated_epoch)),
        "search_index": {
            "exists": search_index.is_file(),
            "bytes": (search_index.stat().st_size if search_index.is_file() else 0),
            "size": (
                human_bytes(search_index.stat().st_size)
                if search_index.is_file()
                else None
            ),
        },
        "counts": counts,
    }


def now_playing_status():
    path = SITE / "now-playing.json"

    domain = f"gui/{os.getuid()}/{NOWPLAYING_LABEL}"

    try:
        service_result = subprocess.run(
            [
                "launchctl",
                "print",
                domain,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

        service_loaded = (
            service_result.returncode == 0
        )

    except OSError:
        service_loaded = False

    result = {
        "exists": path.exists(),
        "ok": False,
        "service_loaded": service_loaded,
        "updated": None,
        "age_seconds": None,
        "age": None,
        "current": None,
    }

    if not path.exists():
        return result

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        updated = data.get("updated")

        result["ok"] = bool(data.get("ok"))

        result["updated"] = updated
        result["age_seconds"] = age_seconds(updated)
        result["age"] = human_age(result["age_seconds"])

        now = data.get("now_playing") or []

        if now:
            track = now[0]

            result["current"] = {
                "artist": track.get("artist"),
                "track": track.get("title"),
                "album": track.get("album"),
            }

    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        result["error"] = str(exc)

    return result


def listening_status():
    result = {
        "available": False,
        "plays": 0,
        "latest_played_at": None,
        "latest_play_age_seconds": None,
        "latest_play_age": None,
        "collector_last_seen": None,
        "collector_age_seconds": None,
        "collector_age": None,
    }

    if not DB_FILE.exists():
        return result

    try:
        connection = sqlite3.connect(
            f"file:{DB_FILE}?mode=ro",
            uri=True,
        )

        try:
            tables = {row[0] for row in connection.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type='table'
                    """)}

            required = {
                "listening_plays",
                "listening_play_tracks",
                "listening_state",
            }

            result["available"] = required <= tables

            if not result["available"]:
                return result

            row = connection.execute("""
                SELECT
                    COUNT(*),
                    MAX(played_at)
                FROM listening_plays
                """).fetchone()

            result["plays"] = int(row[0] or 0)

            latest_play = row[1]

            result["latest_played_at"] = latest_play

            result["latest_play_age_seconds"] = age_seconds(latest_play)

            result["latest_play_age"] = human_age(result["latest_play_age_seconds"])

            row = connection.execute("""
                SELECT MAX(last_seen)
                FROM listening_state
                """).fetchone()

            last_seen = row[0] if row else None

            result["collector_last_seen"] = last_seen

            result["collector_age_seconds"] = age_seconds(last_seen)

            result["collector_age"] = human_age(result["collector_age_seconds"])

        finally:
            connection.close()

    except sqlite3.Error as exc:
        result["error"] = str(exc)

    return result


def recovery_status():
    result = {
        "available": RECOVERY_DIR.exists(),
        "latest": None,
        "count": 0,
        "bytes": 0,
        "size": None,
    }

    if not RECOVERY_DIR.exists():
        return result

    snapshots = sorted(
        [path for path in RECOVERY_DIR.iterdir() if path.is_dir()],
        key=lambda path: path.name,
        reverse=True,
    )

    result["count"] = len(snapshots)

    total_bytes = directory_size(RECOVERY_DIR)

    result["bytes"] = total_bytes
    result["size"] = human_bytes(total_bytes)

    if not snapshots:
        return result

    latest = snapshots[0]

    manifest = latest / "manifest.txt"

    description = None
    created = None
    db_check = None

    if manifest.exists():
        try:
            for line in manifest.read_text(encoding="utf-8").splitlines():

                if line.startswith("Created:"):
                    created = line.split(
                        ":",
                        1,
                    )[1].strip()

                elif line.startswith("Description:"):
                    description = line.split(
                        ":",
                        1,
                    )[1].strip()

                elif line.startswith("Snapshot DB check:"):
                    db_check = line.split(
                        ":",
                        1,
                    )[1].strip()

        except OSError:
            pass

    timestamp = int(latest.stat().st_mtime)

    result["latest"] = {
        "id": latest.name,
        "description": description,
        "created": created,
        "database_check": db_check,
        "age_seconds": age_seconds(timestamp),
        "age": human_age(age_seconds(timestamp)),
    }

    return result


def esc(value):
    import html

    return html.escape(str(value or ""))


def status_badge(state):
    labels = {
        "healthy": ("Operational", "status-good"),
        "degraded": ("Degraded", "status-warning"),
        "unhealthy": ("Unhealthy", "status-bad"),
    }

    label, css_class = labels.get(
        state,
        ("Unknown", "status-warning"),
    )

    return f"<span class='status-badge {css_class}'>" f"{esc(label)}</span>"


def yes_no(value):
    if value:
        return "<span class='value-good'>● Operational</span>"

    return "<span class='value-bad'>● Problem</span>"


def render_html(data):
    overall = data["overall"]
    service = data["service"]
    http = data["http"]
    database = data["database"]
    site = data["site"]
    now = data["now_playing"]
    listening = data["listening"]
    recovery = data["recovery"]

    counts = site["counts"]

    latest_recovery = recovery.get("latest") or {}

    current_track = now.get("current")

    if current_track:
        now_detail = (
            f"{esc(current_track.get('artist'))} — "
            f"{esc(current_track.get('track'))}"
        )
    else:
        now_detail = "Nothing playing"

    generated = (
        datetime.fromtimestamp(data["generated_epoch"])
        .astimezone()
        .strftime("%b %-d, %Y · %-I:%M %p")
    )

    recovery_detail = "No snapshots"

    if latest_recovery:
        recovery_detail = esc(latest_recovery.get("id"))

        if latest_recovery.get("description"):
            recovery_detail += " · " + esc(latest_recovery["description"])

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">

<title>WEFUNK Dashboard Status</title>

<style>
:root {{
  color-scheme: dark;
}}

* {{
  box-sizing: border-box;
}}

body {{
  margin: 0;
  background: #0c0e12;
  color: #f3f3f3;
  font-family:
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    sans-serif;
}}

.status-page {{
  width: min(1180px, calc(100% - 32px));
  margin: 32px auto 60px;
}}

.status-header {{
  margin-bottom: 28px;
}}

.status-header h1 {{
  margin: 0 0 8px;
  font-size: clamp(30px, 5vw, 48px);
}}

.status-header p {{
  margin: 0;
  color: #aaa;
}}

.overall-card {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin: 24px 0;
  padding: 24px;
  background: #111419;
  border: 1px solid #2b2f36;
  border-radius: 20px;
}}

.overall-title {{
  font-size: 24px;
  font-weight: 800;
}}

.status-badge {{
  display: inline-flex;
  align-items: center;
  padding: 9px 14px;
  border-radius: 999px;
  font-weight: 800;
}}

.status-good {{
  color: #91e6ae;
  background: rgba(46, 160, 67, .16);
  border: 1px solid rgba(46, 160, 67, .5);
}}

.status-warning {{
  color: #ffd166;
  background: rgba(210, 153, 34, .14);
  border: 1px solid rgba(210, 153, 34, .5);
}}

.status-bad {{
  color: #ff8d8d;
  background: rgba(248, 81, 73, .14);
  border: 1px solid rgba(248, 81, 73, .5);
}}

.status-grid {{
  display: grid;
  grid-template-columns:
    repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
}}

.status-card {{
  min-height: 170px;
  padding: 20px;
  background: #111419;
  border: 1px solid #2b2f36;
  border-radius: 18px;
}}

.status-card h2 {{
  margin: 0 0 14px;
  font-size: 17px;
}}

.status-card .primary {{
  margin-bottom: 8px;
  font-size: 22px;
  font-weight: 800;
}}

.status-card .detail {{
  color: #aaa;
  font-size: 14px;
  line-height: 1.55;
}}

.value-good {{
  color: #91e6ae;
}}

.value-bad {{
  color: #ff8d8d;
}}

.section-title {{
  margin: 34px 0 14px;
  font-size: 22px;
}}

.content-stats {{
  display: grid;
  grid-template-columns:
    repeat(auto-fit, minmax(130px, 1fr));
  gap: 12px;
}}

.stat {{
  padding: 18px;
  text-align: center;
  background: #111419;
  border: 1px solid #2b2f36;
  border-radius: 16px;
}}

.stat strong {{
  display: block;
  margin-bottom: 4px;
  color: #F7931E;
  font-size: 26px;
}}

.stat span {{
  color: #aaa;
  font-size: 13px;
}}

.details-table {{
  width: 100%;
  border-collapse: collapse;
  overflow: hidden;
  background: #111419;
  border: 1px solid #2b2f36;
  border-radius: 16px;
}}

.details-table th,
.details-table td {{
  padding: 12px 14px;
  border-bottom: 1px solid #2b2f36;
  text-align: left;
}}

.details-table th {{
  width: 34%;
  color: #aaa;
  font-weight: 600;
}}

.details-table tr:last-child th,
.details-table tr:last-child td {{
  border-bottom: 0;
}}

@media(max-width: 700px) {{
  .status-page {{
    width: min(100% - 20px, 1180px);
    margin-top: 20px;
  }}

  .details-table th,
  .details-table td {{
    display: block;
    width: 100%;
  }}

  .details-table th {{
    padding-bottom: 3px;
    border-bottom: 0;
  }}

  .details-table td {{
    padding-top: 3px;
  }}
}}
</style>
</head>

<body>

<main class="status-page">

  <header class="status-header">
    <h1>WEFUNK Dashboard Status</h1>
    <p>
      System health and operational status ·
      Last checked {esc(generated)}
    </p>
  </header>

  <section class="overall-card">
    <div>
      <div class="overall-title">
        WEFUNK Dashboard
      </div>
      <div style="color:#aaa;margin-top:6px;">
        Core dashboard systems and supporting services
      </div>
    </div>

    {status_badge(overall["state"])}
  </section>

  <section class="status-grid">

    <div class="status-card">
      <h2>🖥 Dashboard Service</h2>
      <div class="primary">
        {yes_no(service["loaded"] and service["listening"])}
      </div>
      <div class="detail">
        Port {service["port"]}<br>
        LaunchAgent: {"Loaded" if service["loaded"] else "Not loaded"}
      </div>
    </div>

    <div class="status-card">
      <h2>🌐 HTTP</h2>
      <div class="primary">
        {"HTTP " + str(http["status"]) if http["status"] else "Unavailable"}
      </div>
      <div class="detail">
        Local dashboard availability
      </div>
    </div>

    <div class="status-card">
      <h2>🗄 Database</h2>
      <div class="primary">
        {yes_no(database["healthy"])}
      </div>
      <div class="detail">
        quick_check: {esc(database["quick_check"] or "unknown")}<br>
        Size: {esc(database["size"] or "—")}
      </div>
    </div>

    <div class="status-card">
      <h2>🏗 Site Build</h2>
      <div class="primary">
        {yes_no(site["core_files_ok"])}
      </div>
      <div class="detail">
        Homepage age: {esc(site["homepage_age"] or "—")}<br>
        Search index: {esc(site["search_index"]["size"] or "—")}
      </div>
    </div>

    <div class="status-card">
      <h2>🎵 Now Playing</h2>
      <div class="primary">
        {yes_no(
            now["exists"]
            and now["service_loaded"]
            and (
                now["age_seconds"] is None
                or now["age_seconds"] <= 300
            )
        )}
      </div>
      <div class="detail">
        {now_detail}<br>
        Updated {esc(now["age"] or "—")} ago
      </div>
    </div>

    <div class="status-card">
      <h2>🎧 Listening History</h2>
      <div class="primary">
        {yes_no(listening["available"])}
      </div>
      <div class="detail">
        {listening["plays"]:,} recorded plays<br>
        Collector activity:
        {esc(listening["collector_age"] or "—")} ago
      </div>
    </div>

    <div class="status-card">
      <h2>🛟 Recovery</h2>
      <div class="primary">
        {recovery["count"]} snapshots
      </div>
      <div class="detail">
        {recovery_detail}<br>
        Latest:
        {esc(latest_recovery.get("age") or "—")} ago
      </div>
    </div>

    <div class="status-card">
      <h2>💾 Recovery Storage</h2>
      <div class="primary">
        {esc(recovery["size"] or "—")}
      </div>
      <div class="detail">
        Recovery toolkit snapshot storage
      </div>
    </div>

  </section>

  <h2 class="section-title">Library</h2>

  <section class="content-stats">

    <div class="stat">
      <strong>{counts["shows"]:,}</strong>
      <span>Shows</span>
    </div>

    <div class="stat">
      <strong>{counts["artists"]:,}</strong>
      <span>Artists</span>
    </div>

    <div class="stat">
      <strong>{counts["albums"]:,}</strong>
      <span>Albums</span>
    </div>

    <div class="stat">
      <strong>{counts["genres"]:,}</strong>
      <span>Genres</span>
    </div>

    <div class="stat">
      <strong>{counts["years"]:,}</strong>
      <span>Years</span>
    </div>

    <div class="stat">
      <strong>{counts["episode_art"]:,}</strong>
      <span>Episode Art</span>
    </div>

  </section>

  <h2 class="section-title">System Details</h2>

  <table class="details-table">

    <tr>
      <th>Status generated</th>
      <td>{esc(data["generated_at"])}</td>
    </tr>

    <tr>
      <th>Database integrity</th>
      <td>{esc(database["quick_check"] or "unknown")}</td>
    </tr>

    <tr>
      <th>Latest listening play</th>
      <td>{esc(listening["latest_play_age"] or "—")} ago</td>
    </tr>

    <tr>
      <th>Latest recovery snapshot</th>
      <td>{recovery_detail}</td>
    </tr>

  </table>

</main>

</body>
</html>
"""

    return html


def determine_overall(
    service,
    http,
    database,
    site,
    now_playing,
    listening,
):
    critical_failures = []

    if not service["loaded"]:
        critical_failures.append("dashboard_service")

    if not service["listening"]:
        critical_failures.append("dashboard_port")

    if http["status"] != 200:
        critical_failures.append("dashboard_http")

    if not database["healthy"]:
        critical_failures.append("database")

    if not site["core_files_ok"]:
        critical_failures.append("site_files")

    if not site["search_index"]["exists"]:
        critical_failures.append("search_index")

    warnings = []

    if not now_playing["exists"]:
        warnings.append("now_playing_missing")

    elif not now_playing["service_loaded"]:
        warnings.append("now_playing_service")

    elif (
        now_playing["age_seconds"] is not None
        and now_playing["age_seconds"] > 300
    ):
        warnings.append("now_playing_stale")

    if not listening["available"]:
        warnings.append("listening_history")

    if critical_failures:
        state = "unhealthy"
    elif warnings:
        state = "degraded"
    else:
        state = "healthy"

    return {
        "state": state,
        "critical_failures": critical_failures,
        "warnings": warnings,
    }


def main():
    generated_epoch = int(time.time())

    service = service_status()
    http = http_status()
    database = database_status()
    site = site_status()
    now_playing = now_playing_status()
    listening = listening_status()
    recovery = recovery_status()

    overall = determine_overall(
        service,
        http,
        database,
        site,
        now_playing,
        listening,
    )

    data = {
        "generated_at": datetime.fromtimestamp(generated_epoch)
        .astimezone()
        .isoformat(),
        "generated_epoch": generated_epoch,
        "overall": overall,
        "service": service,
        "http": http,
        "database": database,
        "site": site,
        "now_playing": now_playing,
        "listening": listening,
        "recovery": recovery,
    }

    SITE.mkdir(
        parents=True,
        exist_ok=True,
    )

    JSON_OUT.write_text(
        json.dumps(
            data,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    html_out = SITE / "status.html"

    html_out.write_text(
        render_html(data),
        encoding="utf-8",
    )

    print(f"Wrote: {html_out}")
    print(f"Wrote: {JSON_OUT}")

    print(
        "Overall:",
        overall["state"],
    )

    print(
        "Database:",
        database["quick_check"],
    )

    print(
        "HTTP:",
        http["status"],
    )

    print(
        "Shows:",
        site["counts"]["shows"],
    )

    print(
        "Artists:",
        site["counts"]["artists"],
    )


if __name__ == "__main__":
    main()
