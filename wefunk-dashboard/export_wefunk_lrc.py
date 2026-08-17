#!/usr/bin/env python3

import argparse
import json
import re
import shutil
import time
import urllib.error
import urllib.request
import os
from pathlib import Path

JSON_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "json"
EPISODE_DIR = Path(os.environ.get("WEFUNK_EPISODE_DIR", Path(os.environ.get("WEFUNK_MUSIC_DIR", Path.home() / "Music")) / "wefunkradio mixes")).expanduser().resolve()
TIMING_CACHE_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "timing-cache"
REPORT_FILE = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve() / 'wefunk_lrc_timing_report.csv'

SESSION_URL = "https://session.wefunkradio.com/show/{show_id}"
USER_AGENT = "WEFUNK-Dashboard/1.0"
REQUEST_DELAY = 0.35

TIMING_CACHE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate synchronized WEFUNK LRC tracklists."
    )
    parser.add_argument(
        "--show",
        help="Process only one WEFUNK show number, such as 1301.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Redownload timing data even when a cache exists.",
    )
    return parser.parse_args()


def latest_show_json():
    files = list(JSON_DIR.glob("wefunk_shows_*.json"))

    if not files:
        raise SystemExit(f"No WEFUNK JSON files found in {JSON_DIR}")

    return max(files, key=lambda path: path.stat().st_mtime)


def clean_text(value):
    return " ".join(str(value or "").split()).strip()


def lrc_timestamp(milliseconds):
    total_centiseconds = round(int(milliseconds or 0) / 10)
    minutes, remainder = divmod(total_centiseconds, 6000)
    seconds, centiseconds = divmod(remainder, 100)

    return f"[{minutes:02d}:{seconds:02d}.{centiseconds:02d}]"


def extract_session_metadata(raw_metadata):
    if isinstance(raw_metadata, dict):
        return raw_metadata

    if isinstance(raw_metadata, list):
        for item in raw_metadata:
            if isinstance(item, dict):
                return item

    return {}


def extract_javascript_json(html, variable_name):
    match = re.search(
        rf"var\s+{re.escape(variable_name)}\s*=\s*(.*?);",
        html,
        flags=re.S,
    )

    if not match:
        raise ValueError(f"Could not find {variable_name}")

    return json.loads(match.group(1))


def fetch_timing_data(show_id, refresh=False):
    cache_file = TIMING_CACHE_DIR / f"{show_id}.json"

    if cache_file.exists() and not refresh:
        try:
            cached = json.loads(
                cache_file.read_text(encoding="utf-8")
            )

            if (
                isinstance(cached, dict)
                and cached.get("tracks")
                and isinstance(cached.get("trackextra"), list)
            ):
                return cached, "cached"
        except (OSError, json.JSONDecodeError):
            pass

    request = urllib.request.Request(
        SESSION_URL.format(show_id=show_id),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html",
        },
    )

    with urllib.request.urlopen(request, timeout=35) as response:
        html = response.read().decode(
            "utf-8",
            errors="replace",
        )

    trackextra = extract_javascript_json(html, "trackextra")
    tracks = extract_javascript_json(html, "tracks")

    timed_tracks = tracks.get("tracks") or []

    if not timed_tracks:
        raise ValueError("No timed tracks returned")

    previous_position = -1

    for item in timed_tracks:
        if not isinstance(item, dict):
            raise ValueError("Invalid timed-track entry")

        milliseconds = int(item.get("mspos") or 0)

        if milliseconds < previous_position:
            raise ValueError("Track timestamps are not ordered")

        previous_position = milliseconds

    data = {
        "show_id": str(show_id),
        "showdate": tracks.get("showdate") or "",
        "mstotal": int(tracks.get("mstotal") or 0),
        "tracks": timed_tracks,
        "trackextra": trackextra,
    }

    temporary = cache_file.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(cache_file)

    return data, "downloaded"


def local_track_label(track):
    if not isinstance(track, dict):
        return ""

    artist = clean_text(track.get("artist"))
    title = clean_text(
        track.get("track")
        or track.get("title")
    )

    if artist and title:
        return f"{artist} - {title}"

    return artist or title


def session_track_label(raw_metadata):
    metadata = extract_session_metadata(raw_metadata)

    artist = clean_text(metadata.get("a"))
    title = clean_text(metadata.get("t"))

    if artist and title:
        return f"{artist} - {title}"

    return artist or title


def build_timed_lrc(show, timing_data):
    local_tracks = show.get("playlistbox") or []
    timed_tracks = timing_data.get("tracks") or []
    trackextra = timing_data.get("trackextra") or []

    if not timed_tracks:
        raise ValueError("No timestamp entries")

    lines = ["[00:00.00]Intro"]

    # Session entry zero represents the show intro.
    # Actual songs begin at timing entry one.
    for position, timing in enumerate(
        timed_tracks[1:],
        start=1,
    ):
        milliseconds = int(timing.get("mspos") or 0)

        if milliseconds <= 0:
            raise ValueError(
                f"Invalid timestamp at session position {position}"
            )

        # The local WEFUNK playlist includes its intro entry at
        # position zero, matching the session timing array.
        local_position = position

        local_label = (
            local_track_label(local_tracks[local_position])
            if local_position < len(local_tracks)
            else ""
        )

        session_label = (
            session_track_label(trackextra[position])
            if position < len(trackextra)
            else ""
        )

        label = (
            local_label
            or session_label
            or f"Track {position}"
        )

        lines.append(
            f"{lrc_timestamp(milliseconds)}{label}"
        )

    expected_local_count = len(timed_tracks)

    # Allow a small mismatch for occasional talk/interlude entries,
    # but reject obviously unrelated data.
    if local_tracks and abs(len(local_tracks) - expected_local_count) > 3:
        raise ValueError(
            "Track-count mismatch: "
            f"local={len(local_tracks)}, "
            f"timed={expected_local_count}"
        )

    return "\n".join(lines).rstrip() + "\n"


def write_report(rows):
    import csv

    fields = [
        "show_id",
        "mp3",
        "lrc",
        "status",
        "timing_source",
        "message",
    ]

    with REPORT_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()

    source_json = latest_show_json()
    shows = json.loads(
        source_json.read_text(encoding="utf-8")
    )

    shows_by_id = {
        str(show.get("show_id") or "").strip(): show
        for show in shows
        if str(show.get("show_id") or "").strip()
    }

    mp3_files = sorted(
        EPISODE_DIR.glob("WEFUNK_Show_*.mp3")
    )

    if args.show:
        mp3_files = [
            path
            for path in mp3_files
            if re.search(
                rf"WEFUNK_Show_{re.escape(args.show)}_",
                path.name,
            )
        ]

        if not mp3_files:
            raise SystemExit(
                f"No MP3 found for show {args.show}"
            )

    created = 0
    updated = 0
    unchanged = 0
    failed = 0
    reports = []

    for number, mp3 in enumerate(mp3_files, start=1):
        match = re.search(
            r"WEFUNK_Show_(\d+)_",
            mp3.name,
        )

        if not match:
            continue

        show_id = match.group(1)
        show = shows_by_id.get(show_id)
        lrc = mp3.with_suffix(".lrc")

        row = {
            "show_id": show_id,
            "mp3": str(mp3),
            "lrc": str(lrc),
            "status": "",
            "timing_source": "",
            "message": "",
        }

        if not show:
            failed += 1
            row["status"] = "missing-metadata"
            row["message"] = "Show not found in local JSON"
            reports.append(row)
            print(f"{show_id} - missing local JSON metadata")
            continue

        try:
            timing_data, timing_source = fetch_timing_data(
                show_id,
                refresh=args.refresh,
            )

            content = build_timed_lrc(
                show,
                timing_data,
            )

            row["timing_source"] = timing_source

            if lrc.exists():
                existing = lrc.read_text(
                    encoding="utf-8",
                    errors="replace",
                )

                if existing == content:
                    unchanged += 1
                    row["status"] = "unchanged"
                    reports.append(row)
                    print(
                        f"[{number}/{len(mp3_files)}] "
                        f"{show_id} - unchanged ({timing_source})"
                    )
                    continue

                backup = lrc.with_suffix(
                    ".lrc.untimed-backup"
                )

                if not backup.exists():
                    shutil.copy2(lrc, backup)

                lrc.write_text(
                    content,
                    encoding="utf-8",
                )

                updated += 1
                row["status"] = "updated"
                reports.append(row)

                print(
                    f"[{number}/{len(mp3_files)}] "
                    f"{show_id} - updated ({timing_source})"
                )
            else:
                lrc.write_text(
                    content,
                    encoding="utf-8",
                )

                created += 1
                row["status"] = "created"
                reports.append(row)

                print(
                    f"[{number}/{len(mp3_files)}] "
                    f"{show_id} - created ({timing_source})"
                )

        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
            OSError,
        ) as exc:
            failed += 1
            row["status"] = "failed"
            row["message"] = str(exc)
            reports.append(row)
            print(f"{show_id} - FAILED: {exc}")

        if not args.show:
            time.sleep(REQUEST_DELAY)

    write_report(reports)

    print()
    print("Timed LRC summary:")
    print(f"  Created:   {created}")
    print(f"  Updated:   {updated}")
    print(f"  Unchanged: {unchanged}")
    print(f"  Failed:    {failed}")
    print(f"  Source:    {source_json}")
    print(f"  Cache:     {TIMING_CACHE_DIR}")
    print(f"  Report:    {REPORT_FILE}")


if __name__ == "__main__":
    main()
