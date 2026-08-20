#!/usr/bin/env python3

import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from common import (
    SITE,
    artist_display_name,
    artist_slugify,
    esc,
    slugify,
)
from data import album_index_by_artist_album
from collect_listening_history import ensure_schema


RANGES = {
    "7d": {
        "label": "7 Days",
        "seconds": 7 * 24 * 60 * 60,
    },
    "30d": {
        "label": "30 Days",
        "seconds": 30 * 24 * 60 * 60,
    },
    "90d": {
        "label": "90 Days",
        "seconds": 90 * 24 * 60 * 60,
    },
    "1y": {
        "label": "1 Year",
        "seconds": 365 * 24 * 60 * 60,
    },
    "all": {
        "label": "All Time",
        "seconds": None,
    },
}


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(
    os.environ.get(
        "WEFUNK_DATA_DIR",
        PROJECT_ROOT / "data",
    )
).expanduser().resolve()

DB_FILE = Path(
    os.environ.get(
        "WEFUNK_DB_FILE",
        DATA_ROOT / "db" / "wefunk.db",
    )
).expanduser().resolve()

OUT = SITE / "listening.html"
ARTIST_IMAGES = SITE / "artist-images"
COVERS = SITE / "covers"


def open_database():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def album_slug_for(artist, album):
    """
    Prefer WEFUNK's canonical album-index slug.

    Fall back to the standard artist-album slug only when an
    existing generated album page confirms that it is valid.
    """
    artist = str(artist or "").strip()
    album = str(album or "").strip()

    if not artist or not album:
        return ""

    row = album_index_by_artist_album.get(
        (
            artist.lower(),
            album.lower(),
        )
    )

    if row:
        slug = str(row.get("slug", "") or "").strip()
        if slug:
            return slug

    fallback = slugify(f"{artist}-{album}")

    if fallback and (SITE / "albums" / f"{fallback}.html").exists():
        return fallback

    return ""


def artist_image_html(artist, css_class="listening-artist-image"):
    slug = artist_slugify(artist)
    image = ARTIST_IMAGES / f"{slug}.jpg"

    if image.exists():
        version = int(image.stat().st_mtime)

        return (
            f"<img class='{css_class}' "
            f"src='/artist-images/{esc(slug)}.jpg?v={version}' "
            f"alt='{esc(artist)}' "
            f"loading='lazy'>"
        )

    initials = "".join(
        word[:1].upper()
        for word in str(artist).split()
        if word
    )[:2] or "♪"

    return (
        f"<div class='{css_class} listening-image-placeholder'>"
        f"{esc(initials)}"
        f"</div>"
    )


def album_cover_html(artist, album):
    slug = album_slug_for(artist, album)

    if slug:
        cover = COVERS / f"{slug}.jpg"

        if cover.exists():
            version = int(cover.stat().st_mtime)

            return (
                f"<img class='listening-album-cover' "
                f"src='/covers/{esc(slug)}.jpg?v={version}' "
                f"alt='{esc(album)}' "
                f"loading='lazy'>"
            )

    return (
        "<div class='listening-album-cover "
        "listening-image-placeholder'>💿</div>"
    )


def artist_link(artist):
    slug = artist_slugify(artist)
    display = artist_display_name(artist, slug)

    artist_page = SITE / "artists" / f"{slug}.html"

    if artist_page.exists():
        return (
            f"<a href='/artists/{esc(slug)}.html'>"
            f"{esc(display)}</a>"
        )

    return esc(display)


def album_link(artist, album):
    album = str(album or "").strip()

    if not album:
        return "<span class='listening-muted'>Unknown Album</span>"

    slug = album_slug_for(artist, album)

    if slug:
        return (
            f"<a href='/albums/{esc(slug)}.html'>"
            f"{esc(album)}</a>"
        )

    return esc(album)


def format_play_time(timestamp):
    try:
        dt = datetime.fromtimestamp(int(timestamp))
    except (TypeError, ValueError, OSError):
        return ""

    return dt.strftime("%b %-d, %Y · %-I:%M %p")


def load_summary(connection, since=None):
    where = ""
    params = []

    if since is not None:
        where = "WHERE played_at >= ?"
        params.append(int(since))

    return connection.execute(
        f"""
        SELECT
            COUNT(*) AS plays,

            COUNT(
                DISTINCT artist_norm || CHAR(31) || track_norm
            ) AS tracks,

            COUNT(
                DISTINCT artist_norm
            ) AS artists,

            COUNT(
                DISTINCT CASE
                    WHEN TRIM(COALESCE(album, '')) != ''
                    THEN LOWER(TRIM(album))
                END
            ) AS albums,

            COALESCE(
                SUM(
                    CASE
                        WHEN duration > 0
                        THEN duration
                        ELSE 0
                    END
                ),
                0
            ) AS listening_seconds

        FROM listening_plays
        {where}
        """,
        params,
    ).fetchone()


def load_episode_count(connection, since=None):
    where = ""
    params = []

    if since is not None:
        where = "WHERE lp.played_at >= ?"
        params.append(int(since))

    return connection.execute(
        f"""
        SELECT COUNT(DISTINCT t.show_id)

        FROM listening_play_tracks AS lpt

        INNER JOIN listening_plays AS lp
            ON lp.id = lpt.play_id

        INNER JOIN tracks AS t
            ON t.id = lpt.wefunk_track_id

        {where}
        """,
        params,
    ).fetchone()[0]


def load_recent_plays(connection, limit=50, since=None):
    where = ""
    params = []

    if since is not None:
        where = "WHERE played_at >= ?"
        params.append(int(since))

    params.append(limit)

    plays = connection.execute(
        f"""
        SELECT
            id,
            played_at,
            artist,
            track,
            album,
            duration

        FROM listening_plays

        {where}

        ORDER BY
            played_at DESC,
            id DESC

        LIMIT ?
        """,
        params,
    ).fetchall()

    result = []

    for play in plays:
        show_rows = connection.execute(
            """
            SELECT DISTINCT
                t.show_id

            FROM listening_play_tracks AS lpt

            INNER JOIN tracks AS t
                ON t.id = lpt.wefunk_track_id

            WHERE lpt.play_id = ?

            ORDER BY
                CAST(t.show_id AS INTEGER),
                t.show_id
            """,
            (play["id"],),
        ).fetchall()

        item = dict(play)
        item["shows"] = [
            str(row["show_id"])
            for row in show_rows
            if row["show_id"] is not None
        ]

        result.append(item)

    return result


def load_activity(connection, range_key, since=None):
    """
    Build a continuous activity series.

    Short ranges use daily buckets.
    One year uses weekly buckets.
    All time uses monthly buckets.

    Missing periods are explicitly returned with zero plays.
    """
    params = []
    where = ""

    if since is not None:
        where = "WHERE played_at >= ?"
        params.append(int(since))

    rows = connection.execute(
        f"""
        SELECT
            played_at,
            COALESCE(duration, 0) AS duration

        FROM listening_plays

        {where}

        ORDER BY played_at
        """,
        params,
    ).fetchall()

    activity = {}

    for row in rows:
        played_at = int(row["played_at"])
        duration = int(row["duration"] or 0)

        dt = datetime.fromtimestamp(played_at)

        if range_key in {"7d", "30d", "90d"}:
            bucket = dt.strftime("%Y-%m-%d")

        elif range_key == "1y":
            monday = (
                dt.date()
                - timedelta(days=dt.weekday())
            )
            bucket = monday.isoformat()

        else:
            bucket = dt.strftime("%Y-%m")

        item = activity.setdefault(
            bucket,
            {
                "plays": 0,
                "seconds": 0,
            },
        )

        item["plays"] += 1
        item["seconds"] += duration

    now = datetime.now()

    if range_key in {"7d", "30d", "90d"}:
        days = {
            "7d": 7,
            "30d": 30,
            "90d": 90,
        }[range_key]

        today = now.date()
        start = today - timedelta(days=days - 1)

        buckets = [
            (
                start + timedelta(days=offset)
            ).isoformat()
            for offset in range(days)
        ]

    elif range_key == "1y":
        current_monday = (
            now.date()
            - timedelta(days=now.weekday())
        )

        # 53 buckets safely covers the entire trailing year.
        start_monday = (
            current_monday
            - timedelta(weeks=52)
        )

        buckets = [
            (
                start_monday
                + timedelta(weeks=offset)
            ).isoformat()
            for offset in range(53)
        ]

    else:
        if not rows:
            return []

        first_dt = datetime.fromtimestamp(
            int(rows[0]["played_at"])
        )

        year = first_dt.year
        month = first_dt.month

        end_year = now.year
        end_month = now.month

        buckets = []

        while (
            year < end_year
            or (
                year == end_year
                and month <= end_month
            )
        ):
            buckets.append(
                f"{year:04d}-{month:02d}"
            )

            month += 1

            if month == 13:
                month = 1
                year += 1

    return [
        {
            "bucket": bucket,
            "plays": activity.get(
                bucket,
                {},
            ).get("plays", 0),
            "seconds": activity.get(
                bucket,
                {},
            ).get("seconds", 0),
        }
        for bucket in buckets
    ]



def load_top_artists(connection, limit=10, since=None):
    where = ""
    params = []

    if since is not None:
        where = "WHERE played_at >= ?"
        params.append(int(since))

    params.append(limit)

    return connection.execute(
        f"""
        SELECT
            artist,
            artist_norm,
            COUNT(*) AS plays

        FROM listening_plays

        {where}

        GROUP BY artist_norm

        ORDER BY
            plays DESC,
            artist COLLATE NOCASE

        LIMIT ?
        """,
        params,
    ).fetchall()


def load_top_tracks(connection, limit=10, since=None):
    where = ""
    params = []

    if since is not None:
        where = "WHERE played_at >= ?"
        params.append(int(since))

    params.append(limit)

    return connection.execute(
        f"""
        SELECT
            artist,
            track,
            artist_norm,
            track_norm,
            COUNT(*) AS plays

        FROM listening_plays

        {where}

        GROUP BY
            artist_norm,
            track_norm

        ORDER BY
            plays DESC,
            artist COLLATE NOCASE,
            track COLLATE NOCASE

        LIMIT ?
        """,
        params,
    ).fetchall()


def load_top_albums(connection, limit=10, since=None):
    clauses = [
        "TRIM(COALESCE(album, '')) != ''"
    ]
    params = []

    if since is not None:
        clauses.append("played_at >= ?")
        params.append(int(since))

    params.append(limit)

    where = "WHERE " + " AND ".join(clauses)

    return connection.execute(
        f"""
        SELECT
            artist,
            album,
            artist_norm,
            LOWER(TRIM(album)) AS album_norm,
            COUNT(*) AS plays

        FROM listening_plays

        {where}

        GROUP BY
            artist_norm,
            album_norm

        ORDER BY
            plays DESC,
            artist COLLATE NOCASE,
            album COLLATE NOCASE

        LIMIT ?
        """,
        params,
    ).fetchall()


def recent_play_html(play):
    artist = play["artist"]
    track = play["track"]
    album = play["album"]
    shows = play["shows"]

    show_links = " ".join(
        (
            f"<a class='listening-show-pill' "
            f"href='/shows/{esc(show)}.html'>"
            f"#{esc(show)}</a>"
        )
        for show in shows
    )

    if not show_links:
        show_links = (
            "<span class='listening-muted'>"
            "WEFUNK appearance unavailable"
            "</span>"
        )

    return f"""
    <article class="listening-recent-row">

      <a
        class="listening-recent-art"
        href="/artists/{esc(artist_slugify(artist))}.html"
        aria-label="{esc(artist)}"
      >
        {artist_image_html(artist)}
      </a>

      <div class="listening-recent-main">

        <div class="listening-track-title">
          {esc(track)}
        </div>

        <div class="listening-track-artist">
          {artist_link(artist)}
        </div>

        <div class="listening-track-album">
          {album_link(artist, album)}
        </div>

        <div class="listening-show-links">
          {show_links}
        </div>

      </div>

      <div class="listening-play-time">
        {esc(format_play_time(play["played_at"]))}
      </div>

    </article>
    """


def top_artist_html(row, rank):
    artist = row["artist"]
    plays = row["plays"]

    return f"""
    <div class="listening-chart-row">

      <div class="listening-chart-rank">
        {rank}
      </div>

      <div class="listening-chart-thumb">
        {artist_image_html(
            artist,
            "listening-chart-image"
        )}
      </div>

      <div class="listening-chart-info">
        <strong>{artist_link(artist)}</strong>
      </div>

      <div class="listening-chart-count">
        {plays:,}
        <span>play{"s" if plays != 1 else ""}</span>
      </div>

    </div>
    """


def top_album_html(row, rank):
    artist = row["artist"]
    album = row["album"]
    plays = row["plays"]

    return f"""
    <div class="listening-chart-row">

      <div class="listening-chart-rank">
        {rank}
      </div>

      <div class="listening-chart-thumb">
        {album_cover_html(artist, album)}
      </div>

      <div class="listening-chart-info">
        <strong>{album_link(artist, album)}</strong>
        <span>{artist_link(artist)}</span>
      </div>

      <div class="listening-chart-count">
        {plays:,}
        <span>play{"s" if plays != 1 else ""}</span>
      </div>

    </div>
    """


def top_track_html(row, rank):
    artist = row["artist"]
    track = row["track"]
    plays = row["plays"]

    return f"""
    <div class="listening-chart-row">

      <div class="listening-chart-rank">
        {rank}
      </div>

      <div class="listening-chart-thumb">
        {artist_image_html(
            artist,
            "listening-chart-image"
        )}
      </div>

      <div class="listening-chart-info">
        <strong>{esc(track)}</strong>
        <span>{artist_link(artist)}</span>
      </div>

      <div class="listening-chart-count">
        {plays:,}
        <span>play{"s" if plays != 1 else ""}</span>
      </div>

    </div>
    """


def format_listening_time(seconds):
    seconds = int(seconds or 0)

    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60

    if minutes < 60:
        return f"{minutes} min"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours < 24:
        if remaining_minutes:
            return f"{hours}h {remaining_minutes}m"
        return f"{hours}h"

    days = hours // 24
    remaining_hours = hours % 24

    if remaining_hours:
        return f"{days}d {remaining_hours}h"

    return f"{days}d"


def stat_card(value, label, card_id=""):
    id_attr = (
        f" id='{esc(card_id)}'"
        if card_id
        else ""
    )

    return f"""
    <div class="listening-stat-card"{id_attr}>
      <strong>{value:,}</strong>
      <span>{esc(label)}</span>
    </div>
    """


def empty_state():
    return """
    <div class="listening-empty">
      <div class="listening-empty-icon">🎧</div>
      <h3>No WEFUNK listening history yet</h3>
      <p>
        Plays will appear here automatically after a
        qualifying track from the WEFUNK database is heard.
      </p>
    </div>
    """


def main():
    if not DB_FILE.exists():
        raise SystemExit(
            f"Database does not exist: {DB_FILE}"
        )

    connection = open_database()

    try:
        # Listening History is optional. Ensure the empty schema exists
        # so a normal dashboard build succeeds before the user has ever
        # enabled or collected listening history.
        ensure_schema(connection)

        now = int(time.time())
        range_data = {}

        for range_key, config in RANGES.items():
            seconds = config["seconds"]

            since = (
                now - seconds
                if seconds is not None
                else None
            )

            summary = load_summary(
                connection,
                since=since,
            )

            episodes = load_episode_count(
                connection,
                since=since,
            )

            recent = load_recent_plays(
                connection,
                since=since,
            )

            top_artists = load_top_artists(
                connection,
                since=since,
            )

            top_albums = load_top_albums(
                connection,
                since=since,
            )

            top_tracks = load_top_tracks(
                connection,
                since=since,
            )

            activity = load_activity(
                connection,
                range_key,
                since=since,
            )

            range_data[range_key] = {
                "label": config["label"],
                "summary": dict(summary),
                "episodes": episodes,
                "recent": [
                    dict(item)
                    for item in recent
                ],
                "top_artists": [
                    dict(item)
                    for item in top_artists
                ],
                "top_albums": [
                    dict(item)
                    for item in top_albums
                ],
                "top_tracks": [
                    dict(item)
                    for item in top_tracks
                ],
                "activity": activity,
            }

        summary = range_data["all"]["summary"]
        episodes = range_data["all"]["episodes"]
        recent = range_data["all"]["recent"]
        top_artists = range_data["all"]["top_artists"]
        top_albums = range_data["all"]["top_albums"]
        top_tracks = range_data["all"]["top_tracks"]

    finally:
        connection.close()

    recent_html = (
        "".join(
            recent_play_html(play)
            for play in recent
        )
        if recent
        else empty_state()
    )

    artist_chart = (
        "".join(
            top_artist_html(row, rank)
            for rank, row in enumerate(
                top_artists,
                start=1,
            )
        )
        or empty_state()
    )

    album_chart = (
        "".join(
            top_album_html(row, rank)
            for rank, row in enumerate(
                top_albums,
                start=1,
            )
        )
        or empty_state()
    )

    track_chart = (
        "".join(
            top_track_html(row, rank)
            for rank, row in enumerate(
                top_tracks,
                start=1,
            )
        )
        or empty_state()
    )

    html = f"""<!doctype html>
<html lang="en">
<head>

<meta charset="utf-8">
<meta
  name="viewport"
  content="width=device-width, initial-scale=1"
>

<title>Listening · WEFUNK Dashboard</title>

<style>

:root {{
  color-scheme: dark;
}}

* {{
  box-sizing: border-box;
}}

body {{
  margin: 0;
  padding: 0 18px 40px;
  background: #0d0f12;
  color: #f2f2f2;
  font-family:
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    sans-serif;
}}

a {{
  color: #F7931E;
  text-decoration: none;
}}

a:hover {{
  text-decoration: underline;
}}

.listening-page {{
  max-width: 1500px;
  margin: 0 auto;
}}

.listening-hero {{
  padding: 34px 0 22px;
}}

.listening-kicker {{
  color: #F7931E;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: .12em;
  text-transform: uppercase;
  margin-bottom: 7px;
}}

.listening-hero h1 {{
  margin: 0;
  font-size: clamp(34px, 5vw, 58px);
  letter-spacing: -.04em;
}}

.listening-hero p {{
  max-width: 780px;
  color: #aeb2b8;
  font-size: 16px;
  line-height: 1.55;
  margin: 10px 0 0;
}}

.listening-range-tabs {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 18px;
}}

.listening-range-tabs button {{
  appearance: none;
  border: 1px solid #30353d;
  border-radius: 999px;
  padding: 8px 14px;
  background: #15191e;
  color: #b4b8be;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}}

.listening-range-tabs button:hover {{
  border-color: #F7931E;
  color: #fff;
}}

.listening-range-tabs button.is-active {{
  border-color: #F7931E;
  background: #F7931E;
  color: #111;
}}


.listening-stats {{
  display: grid;
  grid-template-columns:
    repeat(6, minmax(135px, 1fr));
  gap: 12px;
  margin-bottom: 26px;
}}

.listening-stat-card {{
  min-height: 112px;
  padding: 20px;
  border: 1px solid #292d34;
  border-radius: 16px;
  background:
    linear-gradient(
      145deg,
      #171a1f,
      #111419
    );
}}

.listening-stat-card strong {{
  display: block;
  color: #fff;
  font-size: 30px;
  line-height: 1;
  letter-spacing: -.03em;
}}

.listening-stat-card span {{
  display: block;
  margin-top: 10px;
  color: #9ca1a9;
  font-size: 13px;
}}

.listening-activity-panel {{
  margin-bottom: 20px;
}}

.listening-activity-actions {{
  display: flex;
  align-items: center;
  gap: 12px;
}}

.listening-activity-metric {{
  display: flex;
  gap: 4px;
  padding: 3px;
  border: 1px solid #30353d;
  border-radius: 999px;
  background: #15191e;
}}

.listening-activity-metric button {{
  appearance: none;
  border: 0;
  border-radius: 999px;
  padding: 6px 11px;
  background: transparent;
  color: #9298a1;
  font: inherit;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
}}

.listening-activity-metric button:hover {{
  color: #fff;
}}

.listening-activity-metric button.is-active {{
  background: #F7931E;
  color: #111;
}}

.listening-activity-total {{
  color: #F7931E;
  font-size: 13px;
  font-weight: 800;
  white-space: nowrap;
}}

.listening-activity-chart {{
  position: relative;
  height: 280px;
  padding: 16px 16px 8px;
  overflow: hidden;
}}

.listening-activity-svg {{
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}}

.listening-activity-grid-line {{
  stroke: #252a31;
  stroke-width: 1;
}}

.listening-activity-baseline {{
  stroke: #343941;
  stroke-width: 1;
}}

.listening-activity-area {{
  fill: rgba(247, 147, 30, .11);
}}

.listening-activity-line {{
  fill: none;
  stroke: #F7931E;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}}

.listening-activity-point {{
  fill: #F7931E;
  stroke: #111419;
  stroke-width: 3;
  transition:
    r .15s ease,
    opacity .15s ease;
}}

.listening-activity-point:hover {{
  r: 7;
}}

.listening-activity-axis-label {{
  fill: #737982;
  font-size: 11px;
  text-anchor: middle;
}}

.listening-activity-y-label {{
  fill: #737982;
  font-size: 10px;
  text-anchor: end;
}}

.listening-activity-empty {{
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #777d85;
  text-align: center;
}}

@media (max-width: 650px) {{

  .listening-activity-chart {{
    height: 220px;
    padding-left: 4px;
    padding-right: 4px;
  }}

  .listening-activity-axis-label {{
    font-size: 9px;
  }}

}}


.listening-grid {{
  display: grid;
  grid-template-columns:
    minmax(0, 1.45fr)
    minmax(360px, .75fr);
  gap: 20px;
  align-items: start;
}}

.listening-panel {{
  border: 1px solid #292d34;
  border-radius: 18px;
  background: #111419;
  overflow: hidden;
}}

.listening-panel-header {{
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: end;
  padding: 18px 20px;
  border-bottom: 1px solid #292d34;
}}

.listening-panel-header h2 {{
  margin: 0;
  font-size: 20px;
}}

.listening-panel-header span {{
  color: #858b94;
  font-size: 12px;
}}

.listening-recent-row {{
  display: grid;
  grid-template-columns: 72px 1fr auto;
  gap: 15px;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid #23272d;
}}

.listening-recent-row:last-child {{
  border-bottom: 0;
}}

.listening-recent-row:hover {{
  background: #15191e;
}}

.listening-recent-art {{
  display: block;
  width: 72px;
  height: 72px;
}}

.listening-artist-image {{
  display: block;
  width: 72px;
  height: 72px;
  border-radius: 12px;
  object-fit: cover;
  background: #22262c;
}}

.listening-image-placeholder {{
  display: flex;
  align-items: center;
  justify-content: center;
  color: #F7931E;
  background:
    linear-gradient(
      145deg,
      #262b32,
      #171a1f
    );
  font-weight: 900;
}}

.listening-track-title {{
  color: #fff;
  font-size: 16px;
  font-weight: 800;
  margin-bottom: 4px;
}}

.listening-track-artist {{
  font-size: 14px;
  margin-bottom: 2px;
}}

.listening-track-album {{
  color: #90959d;
  font-size: 13px;
}}

.listening-track-album a {{
  color: #aeb2b8;
}}

.listening-show-links {{
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 8px;
}}

.listening-show-pill {{
  display: inline-block;
  padding: 3px 7px;
  border: 1px solid #343941;
  border-radius: 999px;
  color: #b7bbc1;
  background: #191d22;
  font-size: 11px;
  font-weight: 700;
}}

.listening-show-pill:hover {{
  color: #111;
  background: #F7931E;
  border-color: #F7931E;
  text-decoration: none;
}}

.listening-play-time {{
  color: #747a83;
  font-size: 12px;
  text-align: right;
  white-space: nowrap;
}}

.listening-side {{
  display: grid;
  gap: 20px;
}}

.listening-chart-row {{
  display: grid;
  grid-template-columns:
    28px
    50px
    minmax(0, 1fr)
    auto;
  gap: 10px;
  align-items: center;
  padding: 11px 14px;
  border-bottom: 1px solid #23272d;
}}

.listening-chart-row:last-child {{
  border-bottom: 0;
}}

.listening-chart-row:hover {{
  background: #15191e;
}}

.listening-chart-rank {{
  color: #686e77;
  font-size: 13px;
  font-weight: 800;
  text-align: center;
}}

.listening-chart-thumb {{
  width: 50px;
  height: 50px;
}}

.listening-chart-image,
.listening-album-cover {{
  width: 50px;
  height: 50px;
  border-radius: 8px;
  object-fit: cover;
}}

.listening-chart-info {{
  min-width: 0;
}}

.listening-chart-info strong {{
  display: block;
  color: #f3f3f3;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}

.listening-chart-info strong a {{
  color: #f3f3f3;
}}

.listening-chart-info span {{
  display: block;
  color: #858b94;
  font-size: 12px;
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}

.listening-chart-count {{
  color: #f3f3f3;
  font-size: 13px;
  font-weight: 800;
  text-align: right;
}}

.listening-chart-count span {{
  display: block;
  color: #70767e;
  font-size: 10px;
  font-weight: 500;
  margin-top: 2px;
}}

.listening-muted {{
  color: #777d85;
}}

.listening-empty {{
  padding: 38px 20px;
  color: #858b94;
  text-align: center;
}}

.listening-empty-icon {{
  font-size: 32px;
}}

.listening-empty h3 {{
  color: #ddd;
  margin: 10px 0 6px;
}}

.listening-empty p {{
  max-width: 430px;
  margin: 0 auto;
  line-height: 1.5;
}}

@media (max-width: 1100px) {{

  .listening-stats {{
    grid-template-columns:
      repeat(3, 1fr);
  }}

  .listening-grid {{
    grid-template-columns: 1fr;
  }}

}}

@media (max-width: 650px) {{

  body {{
    padding-left: 10px;
    padding-right: 10px;
  }}

  .listening-stats {{
    grid-template-columns:
      repeat(2, 1fr);
  }}

  .listening-recent-row {{
    grid-template-columns:
      58px
      minmax(0, 1fr);
  }}

  .listening-recent-art,
  .listening-artist-image {{
    width: 58px;
    height: 58px;
  }}

  .listening-play-time {{
    grid-column: 2;
    text-align: left;
  }}

}}

</style>

</head>

<body>

<div class="listening-page">

  <header class="listening-hero">

    <div class="listening-kicker">
      Your WEFUNK Listening
    </div>

    <h1>Listening</h1>

    <p>
      Your personal listening history, limited exclusively
      to tracks that have appeared on WEFUNK Radio.
    </p>

  </header>

  <nav
    class="listening-range-tabs"
    aria-label="Listening time range"
  >
    <button data-range="7d">7 Days</button>
    <button data-range="30d">30 Days</button>
    <button data-range="90d">90 Days</button>
    <button data-range="1y">1 Year</button>
    <button data-range="all">All Time</button>
  </nav>

  <section class="listening-stats">

    {stat_card(summary["plays"], "Total Plays", "listeningStatPlays")}

    {stat_card(summary["tracks"], "Unique Tracks", "listeningStatTracks")}

    {stat_card(summary["artists"], "Unique Artists", "listeningStatArtists")}

    {stat_card(summary["albums"], "Unique Albums", "listeningStatAlbums")}

    {stat_card(episodes, "Episodes Represented", "listeningStatEpisodes")}

    <div class="listening-stat-card" id="listeningStatTime">
      <strong>{esc(format_listening_time(summary["listening_seconds"]))}</strong>
      <span>Listening Time</span>
    </div>

  </section>

  <section class="listening-panel listening-activity-panel">

    <header class="listening-panel-header">

      <div>
        <h2>📈 Listening Activity</h2>
        <span id="listeningActivitySubtitle">
          Plays over time
        </span>
      </div>

      <div class="listening-activity-actions">

        <div
          class="listening-activity-metric"
          role="group"
          aria-label="Listening activity metric"
        >
          <button
            type="button"
            data-activity-metric="plays"
            class="is-active"
          >
            Plays
          </button>

          <button
            type="button"
            data-activity-metric="time"
          >
            Listening Time
          </button>
        </div>

        <div
          class="listening-activity-total"
          id="listeningActivityTotal"
        ></div>

      </div>

    </header>

    <div
      class="listening-activity-chart"
      id="listeningActivityChart"
      aria-label="Listening activity chart"
    ></div>

  </section>

  <div class="listening-grid">

    <section class="listening-panel">

      <header class="listening-panel-header">
        <h2>🎧 Recent Listening</h2>
        <span id="listeningRecentRangeLabel">Latest 50 WEFUNK-matched plays</span>
      </header>

      <div id="listeningRecent">
        {recent_html}
      </div>

    </section>

    <aside class="listening-side">

      <section class="listening-panel">

        <header class="listening-panel-header">
          <h2>🎤 Top Artists</h2>
          <span id="listeningTopArtistsRangeLabel">All time</span>
        </header>

        <div id="listeningTopArtists">
          {artist_chart}
        </div>

      </section>

      <section class="listening-panel">

        <header class="listening-panel-header">
          <h2>💿 Top Albums</h2>
          <span id="listeningTopAlbumsRangeLabel">All time</span>
        </header>

        <div id="listeningTopAlbums">
          {album_chart}
        </div>

      </section>

      <section class="listening-panel">

        <header class="listening-panel-header">
          <h2>🔥 Top Tracks</h2>
          <span id="listeningTopTracksRangeLabel">All time</span>
        </header>

        <div id="listeningTopTracks">
          {track_chart}
        </div>

      </section>

    </aside>

  </div>

</div>

<script>

const listeningRanges = {json.dumps(
    range_data,
    ensure_ascii=False,
).replace("</", "<\\/")};


function listeningEscape(value) {{
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}}


function formatListeningTime(seconds) {{
  seconds = Number(seconds || 0);

  if (seconds < 60) {{
    return `${{seconds}}s`;
  }}

  const minutes = Math.floor(seconds / 60);

  if (minutes < 60) {{
    return `${{minutes}} min`;
  }}

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  if (hours < 24) {{
    return remainingMinutes
      ? `${{hours}}h ${{remainingMinutes}}m`
      : `${{hours}}h`;
  }}

  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;

  return remainingHours
    ? `${{days}}d ${{remainingHours}}h`
    : `${{days}}d`;
}}


function artistSlug(value) {{
  let text = String(value || "").toLowerCase();

  text = text.replace(
    /\b(feat|ft|featuring)\b.*/,
    ""
  );

  text = text.replace(
    /\bwith\b.*/,
    ""
  );

  text = text.replace(/^the\\s+/, "");
  text = text.replaceAll("&", "and");
  text = text.replace(/[^a-z0-9\\s]/g, " ");
  text = text.replace(/\\s+/g, " ").trim();

  return text
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "unknown";
}}


function recentRow(play) {{
  const artist = listeningEscape(play.artist);
  const track = listeningEscape(play.track);
  const album = listeningEscape(
    play.album || "Unknown Album"
  );

  const slug = artistSlug(play.artist);

  const shows = (play.shows || [])
    .map(show =>
      `<a class="listening-show-pill"
          href="/shows/${{listeningEscape(show)}}.html">
         #${{listeningEscape(show)}}
       </a>`
    )
    .join(" ");

  const date = new Date(
    Number(play.played_at) * 1000
  );

  const formatted = date.toLocaleString(
    undefined,
    {{
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }}
  );

  return `
    <article class="listening-recent-row">

      <a
        class="listening-recent-art"
        href="/artists/${{slug}}.html"
      >
        <img
          class="listening-artist-image"
          src="/artist-images/${{slug}}.jpg"
          alt="${{artist}}"
          loading="lazy"
          onerror="this.style.display='none'"
        >
      </a>

      <div class="listening-recent-main">

        <div class="listening-track-title">
          ${{track}}
        </div>

        <div class="listening-track-artist">
          <a href="/artists/${{slug}}.html">
            ${{artist}}
          </a>
        </div>

        <div class="listening-track-album">
          ${{album}}
        </div>

        <div class="listening-show-links">
          ${{shows}}
        </div>

      </div>

      <div class="listening-play-time">
        ${{formatted}}
      </div>

    </article>
  `;
}}


function chartRows(rows, type) {{
  if (!rows.length) {{
    return `
      <div class="listening-empty">
        No listening data for this period.
      </div>
    `;
  }}

  return rows.map((row, index) => {{
    const artist = listeningEscape(row.artist);
    const artistSlugValue = artistSlug(row.artist);

    let title = "";
    let subtitle = "";

    if (type === "artist") {{
      title = `
        <a href="/artists/${{artistSlugValue}}.html">
          ${{artist}}
        </a>
      `;
    }}

    if (type === "album") {{
      title = listeningEscape(row.album);
      subtitle = `
        <a href="/artists/${{artistSlugValue}}.html">
          ${{artist}}
        </a>
      `;
    }}

    if (type === "track") {{
      title = listeningEscape(row.track);
      subtitle = `
        <a href="/artists/${{artistSlugValue}}.html">
          ${{artist}}
        </a>
      `;
    }}

    return `
      <div class="listening-chart-row">

        <div class="listening-chart-rank">
          ${{index + 1}}
        </div>

        <div class="listening-chart-thumb">
          <img
            class="listening-chart-image"
            src="/artist-images/${{artistSlugValue}}.jpg"
            alt="${{artist}}"
            loading="lazy"
            onerror="this.style.display='none'"
          >
        </div>

        <div class="listening-chart-info">
          <strong>${{title}}</strong>
          ${{subtitle ? `<span>${{subtitle}}</span>` : ""}}
        </div>

        <div class="listening-chart-count">
          ${{Number(row.plays).toLocaleString()}}
          <span>
            play${{Number(row.plays) === 1 ? "" : "s"}}
          </span>
        </div>

      </div>
    `;
  }}).join("");
}}


function formatActivityBucket(bucket, rangeKey) {{
  if (rangeKey === "all") {{
    const parts = bucket.split("-");

    if (parts.length === 2) {{
      const date = new Date(
        Number(parts[0]),
        Number(parts[1]) - 1,
        1
      );

      return date.toLocaleDateString(
        undefined,
        {{
          month: "short",
          year: "numeric",
        }}
      );
    }}

    return bucket;
  }}

  const parts = bucket.split("-");

  if (parts.length === 3) {{
    const date = new Date(
      Number(parts[0]),
      Number(parts[1]) - 1,
      Number(parts[2])
    );

    return date.toLocaleDateString(
      undefined,
      {{
        month: "short",
        day: "numeric",
      }}
    );
  }}

  return bucket;
}}


function shouldShowActivityLabel(index, count) {{
  if (count <= 10) {{
    return true;
  }}

  const stride = Math.ceil(
    (count - 1) / 5
  );

  return (
    index === 0 ||
    index === count - 1 ||
    index % stride === 0
  );
}}


let listeningActivityMetric = "plays";


function renderListeningActivity(data, rangeKey) {{
  const chart = document.getElementById(
    "listeningActivityChart"
  );

  const total = document.getElementById(
    "listeningActivityTotal"
  );

  const subtitle = document.getElementById(
    "listeningActivitySubtitle"
  );

  const activity = data.activity || [];

  const totalPlays = activity.reduce(
    (sum, item) =>
      sum + Number(item.plays || 0),
    0
  );

  const totalSeconds = activity.reduce(
    (sum, item) =>
      sum + Number(item.seconds || 0),
    0
  );

  if (listeningActivityMetric === "time") {{
    total.textContent =
      formatListeningTime(totalSeconds);
  }} else {{
    total.textContent =
      `${{totalPlays.toLocaleString()}} ` +
      `play${{totalPlays === 1 ? "" : "s"}}`;
  }}

  const subtitles = {{
    "7d": "Daily plays · last 7 days",
    "30d": "Daily plays · last 30 days",
    "90d": "Daily plays · last 90 days",
    "1y": "Weekly plays · last year",
    "all": "Monthly plays · all time",
  }};

  subtitle.textContent =
    subtitles[rangeKey]
    || "Plays over time";

  if (!activity.length) {{
    chart.innerHTML = `
      <div class="listening-activity-empty">
        No listening data for this period.
      </div>
    `;
    return;
  }}

  const width = 1000;
  const height = 240;

  const left = 46;
  const right = 18;
  const top = 18;
  const bottom = 42;

  const plotWidth =
    width - left - right;

  const plotHeight =
    height - top - bottom;

  const baseline =
    top + plotHeight;

  const activityValues = activity.map(item => {{
    if (listeningActivityMetric === "time") {{
      return Number(item.seconds || 0) / 60;
    }}

    return Number(item.plays || 0);
  }});

  const maxPlays = Math.max(
    ...activityValues,
    1
  );

  const pointX = (index) => {{
    if (activity.length === 1) {{
      return left + plotWidth / 2;
    }}

    return (
      left +
      (
        index /
        (activity.length - 1)
      ) * plotWidth
    );
  }};

  function niceIntegerTicks(maxValue) {{
    maxValue = Math.max(
      1,
      Math.ceil(Number(maxValue || 0))
    );

    if (maxValue <= 4) {{
      return Array.from(
        {{length: maxValue + 1}},
        (_, index) => maxValue - index
      );
    }}

    const rawStep = maxValue / 4;

    let step = 1;

    if (rawStep > 1) {{
      const magnitude = Math.pow(
        10,
        Math.floor(
          Math.log10(rawStep)
        )
      );

      const normalized =
        rawStep / magnitude;

      if (normalized <= 1) {{
        step = 1 * magnitude;
      }} else if (normalized <= 2) {{
        step = 2 * magnitude;
      }} else if (normalized <= 5) {{
        step = 5 * magnitude;
      }} else {{
        step = 10 * magnitude;
      }}
    }}

    const topValue =
      Math.ceil(maxValue / step) * step;

    const ticks = [];

    for (
      let value = topValue;
      value >= 0;
      value -= step
    ) {{
      ticks.push(value);
    }}

    return ticks;
  }}

  const yTicks = niceIntegerTicks(maxPlays);
  const yMax = Math.max(...yTicks, 1);

  const pointY = (plays) => {{
    const ratio =
      Number(plays || 0) / yMax;

    return (
      baseline -
      ratio * plotHeight
    );
  }};

  const points = activity.map(
    (item, index) => ({{
      x: pointX(index),
      y: pointY(
        listeningActivityMetric === "time"
          ? Number(item.seconds || 0) / 60
          : Number(item.plays || 0)
      ),
      item,
      index,
    }})
  );

  const linePath = points
    .map(
      (point, index) =>
        `${{index === 0 ? "M" : "L"}} ` +
        `${{point.x.toFixed(2)}} ` +
        `${{point.y.toFixed(2)}}`
    )
    .join(" ");

  let areaPath = "";

  if (points.length === 1) {{
    const point = points[0];

    areaPath =
      `M ${{point.x}} ${{baseline}} ` +
      `L ${{point.x}} ${{point.y}} ` +
      `L ${{point.x}} ${{baseline}} Z`;
  }} else {{
    areaPath =
      `M ${{points[0].x}} ${{baseline}} ` +
      points.map(
        point =>
          `L ${{point.x}} ${{point.y}}`
      ).join(" ") +
      ` L ${{points.at(-1).x}} ${{baseline}} Z`;
  }}

  const gridLines = yTicks.map(value => {{
    const ratio = value / yMax;

    const y =
      baseline -
      ratio * plotHeight;

    return `
      <line
        class="listening-activity-grid-line"
        x1="${{left}}"
        y1="${{y}}"
        x2="${{width - right}}"
        y2="${{y}}"
      ></line>

      <text
        class="listening-activity-y-label"
        x="${{left - 10}}"
        y="${{y + 4}}"
      >
        ${{
          listeningActivityMetric === "time"
            ? `${{value}}m`
            : value
        }}
      </text>
    `;
  }}).join("");

  const xLabels = points
    .filter(
      point =>
        shouldShowActivityLabel(
          point.index,
          points.length
        )
    )
    .map(point => `
      <text
        class="listening-activity-axis-label"
        x="${{point.x}}"
        y="${{height - 12}}"
      >
        ${{
          listeningEscape(
            formatActivityBucket(
              point.item.bucket,
              rangeKey
            )
          )
        }}
      </text>
    `)
    .join("");

  const pointMarkup = points
    .map(point => {{
      const label =
        formatActivityBucket(
          point.item.bucket,
          rangeKey
        );

      const plays =
        Number(point.item.plays || 0);

      const seconds =
        Number(point.item.seconds || 0);

      const hasValue =
        listeningActivityMetric === "time"
          ? seconds > 0
          : plays > 0;

      return `
        <circle
          class="listening-activity-point"
          cx="${{point.x}}"
          cy="${{point.y}}"
          r="${{hasValue ? 5 : 3}}"
          opacity="${{hasValue ? 1 : .35}}"
        >
          <title>
            ${{
              listeningEscape(label)
            }} ·
            ${{plays}}
            play${{plays === 1 ? "" : "s"}} ·
            ${{
              formatListeningTime(seconds)
            }}
          </title>
        </circle>
      `;
    }})
    .join("");

  chart.innerHTML = `
    <svg
      class="listening-activity-svg"
      viewBox="0 0 ${{width}} ${{height}}"
      role="img"
      aria-label="Listening activity"
      preserveAspectRatio="none"
    >

      ${{gridLines}}

      <line
        class="listening-activity-baseline"
        x1="${{left}}"
        y1="${{baseline}}"
        x2="${{width - right}}"
        y2="${{baseline}}"
      ></line>

      <path
        class="listening-activity-area"
        d="${{areaPath}}"
      ></path>

      <path
        class="listening-activity-line"
        d="${{linePath}}"
      ></path>

      ${{pointMarkup}}

      ${{xLabels}}

    </svg>
  `;
}}


function setListeningRange(rangeKey) {{
  if (!listeningRanges[rangeKey]) {{
    rangeKey = "all";
  }}

  const data = listeningRanges[rangeKey];
  const summary = data.summary;

  const rangeLabels = {{
    "7d": "Last 7 days",
    "30d": "Last 30 days",
    "90d": "Last 90 days",
    "1y": "Last year",
    "all": "All time",
  }};

  const rangeLabel =
    rangeLabels[rangeKey] || "All time";

  document.getElementById(
    "listeningTopArtistsRangeLabel"
  ).textContent = rangeLabel;

  document.getElementById(
    "listeningTopAlbumsRangeLabel"
  ).textContent = rangeLabel;

  document.getElementById(
    "listeningTopTracksRangeLabel"
  ).textContent = rangeLabel;

  document.getElementById(
    "listeningRecentRangeLabel"
  ).textContent =
    rangeKey === "all"
      ? "Latest 50 WEFUNK-matched plays"
      : `Latest WEFUNK plays · ${{rangeLabel.toLowerCase()}}`;

  renderListeningActivity(
    data,
    rangeKey
  );

  document.querySelector(
    "#listeningStatPlays strong"
  ).textContent =
    Number(summary.plays).toLocaleString();

  document.querySelector(
    "#listeningStatTracks strong"
  ).textContent =
    Number(summary.tracks).toLocaleString();

  document.querySelector(
    "#listeningStatArtists strong"
  ).textContent =
    Number(summary.artists).toLocaleString();

  document.querySelector(
    "#listeningStatAlbums strong"
  ).textContent =
    Number(summary.albums).toLocaleString();

  document.querySelector(
    "#listeningStatEpisodes strong"
  ).textContent =
    Number(data.episodes).toLocaleString();

  document.querySelector(
    "#listeningStatTime strong"
  ).textContent =
    formatListeningTime(
      summary.listening_seconds
    );

  document.getElementById(
    "listeningRecent"
  ).innerHTML =
    data.recent.length
      ? data.recent.map(recentRow).join("")
      : `
        <div class="listening-empty">
          No listening data for this period.
        </div>
      `;

  document.getElementById(
    "listeningTopArtists"
  ).innerHTML =
    chartRows(
      data.top_artists,
      "artist"
    );

  document.getElementById(
    "listeningTopAlbums"
  ).innerHTML =
    chartRows(
      data.top_albums,
      "album"
    );

  document.getElementById(
    "listeningTopTracks"
  ).innerHTML =
    chartRows(
      data.top_tracks,
      "track"
    );

  document
    .querySelectorAll(
      ".listening-range-tabs button"
    )
    .forEach(button => {{
      button.classList.toggle(
        "is-active",
        button.dataset.range === rangeKey
      );
    }});

  const url = new URL(window.location.href);

  if (rangeKey === "all") {{
    url.searchParams.delete("range");
  }} else {{
    url.searchParams.set(
      "range",
      rangeKey
    );
  }}

  window.history.replaceState(
    {{}},
    "",
    url
  );
}}


document
  .querySelectorAll(
    ".listening-range-tabs button"
  )
  .forEach(button => {{
    button.addEventListener(
      "click",
      () => setListeningRange(
        button.dataset.range
      )
    );
  }});


document
  .querySelectorAll(
    "[data-activity-metric]"
  )
  .forEach(button => {{
    button.addEventListener(
      "click",
      () => {{
        listeningActivityMetric =
          button.dataset.activityMetric;

        document
          .querySelectorAll(
            "[data-activity-metric]"
          )
          .forEach(item => {{
            item.classList.toggle(
              "is-active",
              item === button
            );
          }});

        const activeRange =
          document.querySelector(
            ".listening-range-tabs button.is-active"
          )?.dataset.range || "all";

        renderListeningActivity(
          listeningRanges[activeRange],
          activeRange
        );
      }}
    );
  }});


const requestedRange =
  new URLSearchParams(
    window.location.search
  ).get("range") || "all";

setListeningRange(requestedRange);

</script>

</body>
</html>
"""

    OUT.write_text(
        html,
        encoding="utf-8",
    )

    print(f"Wrote: {OUT}")
    print(f"Plays: {summary['plays']}")
    print(f"Artists: {summary['artists']}")
    print(f"Albums: {summary['albums']}")
    print(f"Episodes represented: {episodes}")


if __name__ == "__main__":
    main()
