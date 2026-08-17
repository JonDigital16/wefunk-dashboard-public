import os
#!/usr/bin/env python3

import importlib.util
import json
import re
import time
from pathlib import Path

JSON_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "json"
EPISODE_DIR = Path(os.environ.get("WEFUNK_EPISODE_DIR", Path(os.environ.get("WEFUNK_MUSIC_DIR", Path.home() / "Music")) / "wefunkradio mixes")).expanduser().resolve()
SCRAPER = Path(
    os.environ.get("WEFUNK_SCRAPER_SCRIPT", "")
)

JSON_PATTERN = re.compile(
    r"^wefunk_shows_(\d+)_(\d+)\.json$"
)

AUDIO_PATTERN = re.compile(
    r"^WEFUNK_Show_(\d+)_"
)


def available_json_files():
    results = []

    for path in JSON_DIR.glob("wefunk_shows_*.json"):
        match = JSON_PATTERN.match(path.name)

        if not match:
            continue

        start_show = int(match.group(1))
        end_show = int(match.group(2))

        results.append(
            (start_show, end_show, path)
        )

    return results


def newest_json():
    files = available_json_files()

    if not files:
        raise SystemExit(
            f"No WEFUNK show JSON files found in {JSON_DIR}"
        )

    # Prefer the file covering the highest show number,
    # rather than relying only on modification time.
    return max(
        files,
        key=lambda item: (
            item[1],
            item[0],
        ),
    )


def newest_audio_show():
    show_ids = []

    for path in EPISODE_DIR.glob("WEFUNK_Show_*"):
        if path.suffix.lower() not in {
            ".mp3",
            ".m4a",
            ".flac",
        }:
            continue

        match = AUDIO_PATTERN.match(path.name)

        if match:
            show_ids.append(
                int(match.group(1))
            )

    if not show_ids:
        raise SystemExit(
            f"No WEFUNK episode audio found in {EPISODE_DIR}"
        )

    return max(show_ids)


def load_scraper():
    if not SCRAPER.exists():
        raise SystemExit(
            f"WEFUNK scraper not found: {SCRAPER}"
        )

    spec = importlib.util.spec_from_file_location(
        "wefunk_scraper",
        SCRAPER,
    )

    if not spec or not spec.loader:
        raise SystemExit(
            f"Could not load WEFUNK scraper: {SCRAPER}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(module)

    return module


def main():
    start_show, current_end, source = newest_json()
    newest_audio = newest_audio_show()

    print(
        f"Current metadata: "
        f"{source.name}"
    )
    print(
        f"Newest downloaded audio: "
        f"Show {newest_audio}"
    )

    if newest_audio <= current_end:
        print(
            "✅ WEFUNK show metadata is already current."
        )
        return

    scraper = load_scraper()

    shows = json.loads(
        source.read_text(
            encoding="utf-8"
        )
    )

    existing_ids = {
        str(show.get("show_id") or "").strip()
        for show in shows
    }

    added = []

    for show_id in range(
        current_end + 1,
        newest_audio + 1,
    ):
        if str(show_id) in existing_ids:
            continue

        print()
        print(
            f"Scraping WEFUNK Show {show_id}..."
        )

        show = scraper.parse_show(
            show_id
        )

        if not show:
            raise SystemExit(
                f"❌ Could not retrieve Show {show_id}. "
                "Existing JSON was left unchanged."
            )

        shows.append(show)
        existing_ids.add(str(show_id))
        added.append(show_id)

        # Be polite to the WEFUNK server if several
        # episodes need to be caught up at once.
        if show_id < newest_audio:
            time.sleep(3)

    if not added:
        print(
            "✅ No new show metadata needed."
        )
        return

    destination = (
        JSON_DIR
        / f"wefunk_shows_{start_show}_{max(added)}.json"
    )

    temporary = destination.with_suffix(
        ".json.tmp"
    )

    temporary.write_text(
        json.dumps(
            shows,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary.replace(
        destination
    )

    print()
    print(
        f"✅ Added {len(added)} show(s): "
        + ", ".join(
            str(show_id)
            for show_id in added
        )
    )
    print(
        f"✅ Total shows: {len(shows):,}"
    )
    print(
        f"✅ Wrote: {destination}"
    )


if __name__ == "__main__":
    main()
