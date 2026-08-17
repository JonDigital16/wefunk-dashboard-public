#!/usr/bin/env python3

import re
import os
from pathlib import Path

from mutagen.id3 import COMM, ID3, ID3NoHeaderError, TRCK

EPISODE_DIR = Path(os.environ.get("WEFUNK_EPISODE_DIR", Path(os.environ.get("WEFUNK_MUSIC_DIR", Path.home() / "Music")) / "wefunkradio mixes")).expanduser().resolve()

STATE_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "state"
STATE_FILE = STATE_DIR / "last_episode_metadata_show.txt"

STATE_DIR.mkdir(parents=True, exist_ok=True)

episodes = []

for path in EPISODE_DIR.glob("WEFUNK_Show_*.mp3"):
    match = re.search(r"WEFUNK_Show_(\d+)_", path.name)

    if match:
        episodes.append((int(match.group(1)), path))

if not episodes:
    raise SystemExit("No WEFUNK episode MP3 files found.")

episodes.sort()
highest_show = episodes[-1][0]

# On the first run, process only the newest existing episode.
if STATE_FILE.exists():
    try:
        last_processed = int(STATE_FILE.read_text().strip())
    except ValueError:
        last_processed = highest_show - 1
else:
    last_processed = highest_show - 1

pending = [
    (show_id, path)
    for show_id, path in episodes
    if show_id > last_processed
]

if not pending:
    print(
        f"Episode metadata already current through show "
        f"{last_processed}"
    )
    raise SystemExit(0)

updated = 0

for show_id, path in pending:
    try:
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()

        # Remove standard ID3 comment frames.
        tags.delall("COMM")

        # Remove comment-like custom text fields if present.
        for key in list(tags.keys()):
            upper = key.upper()

            if (
                upper.startswith("TXXX:COMMENT")
                or upper.startswith("TXXX:COMMENTS")
            ):
                del tags[key]

        # Replace the track-number frame.
        tags.delall("TRCK")
        tags.add(
            TRCK(
                encoding=3,
                text=[f"{show_id}/{highest_show}"],
            )
        )

        tags.save(path, v2_version=3)

        print(
            f"{show_id} - comment cleared, "
            f"track set to {show_id}/{highest_show}"
        )

        updated += 1

    except Exception as exc:
        raise SystemExit(
            f"Failed updating show {show_id}: {exc}"
        )

STATE_FILE.write_text(
    str(highest_show),
    encoding="utf-8",
)

print("")
print("Episode metadata summary:")
print(f"  Updated: {updated}")
print(f"  Current highest show: {highest_show}")
print(f"  State file: {STATE_FILE}")
