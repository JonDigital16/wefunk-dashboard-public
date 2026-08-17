#!/usr/bin/env python3
import os

from pathlib import Path
import shutil
from mutagen import File

from common import SITE

SOURCE = Path(os.environ.get("WEFUNK_EPISODE_DIR", Path(os.environ.get("WEFUNK_MUSIC_DIR", Path.home() / "Music")) / "wefunkradio mixes")).expanduser().resolve()
DOWNLOADED_ART = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "artwork" / 'episodes'
OUT = SITE / "episode-art"
PREVIOUS = Path(os.environ.get("WEFUNK_SITE_DIR", Path(__file__).resolve().parents[1] / "site")) / "episode-art"

# Copy existing art from live site into site-next first
if PREVIOUS.exists() and not OUT.exists():
    shutil.copytree(PREVIOUS, OUT)

OUT.mkdir(parents=True, exist_ok=True)

audio_files = [
    p for p in SOURCE.glob("WEFUNK_Show_*")
    if p.suffix.lower() in [".mp3", ".m4a", ".flac"]
]

def extract_show_id(path):
    parts = path.stem.split("_")
    for p in parts:
        if p.isdigit():
            return p
    return None

missing = []

for path in audio_files:
    show_id = extract_show_id(path)
    if show_id and not (OUT / f"{show_id}.jpg").exists():
        missing.append((show_id, path))

if not missing:
    print(f"Episode art already complete: {len(audio_files)} files checked")
    print(OUT)
    raise SystemExit(0)

saved = 0

for show_id, path in missing:
    try:
        # Prefer artwork already downloaded from the WEFUNK show page.
        downloaded_art = None

        for extension in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = DOWNLOADED_ART / f"{show_id}{extension}"

            if candidate.exists() and candidate.stat().st_size > 0:
                downloaded_art = candidate
                break

        if downloaded_art:
            shutil.copy2(
                downloaded_art,
                OUT / f"{show_id}.jpg",
            )
            saved += 1
            continue

        # Fall back to artwork embedded in the audio file.
        audio = File(path)

        if not audio or not audio.tags:
            continue

        art = None

        for key in audio.tags.keys():
            if key.startswith("APIC"):
                art = audio.tags[key].data
                break

        if not art:
            continue

        (OUT / f"{show_id}.jpg").write_bytes(art)
        saved += 1

    except Exception as exc:
        print(
            f"Could not export artwork for show {show_id}: {exc}"
        )
        continue

print(f"Saved {saved} episode covers")
print(f"Missing before run: {len(missing)}")
print(OUT)
