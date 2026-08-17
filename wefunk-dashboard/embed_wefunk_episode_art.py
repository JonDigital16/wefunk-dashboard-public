#!/usr/bin/env python3

import re
import os
from pathlib import Path

from mutagen.id3 import APIC, ID3, ID3NoHeaderError

EPISODE_DIR = Path(os.environ.get("WEFUNK_EPISODE_DIR", Path(os.environ.get("WEFUNK_MUSIC_DIR", Path.home() / "Music")) / "wefunkradio mixes")).expanduser().resolve()

ART_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "artwork" / 'episodes'

AUDIO_PATTERN = re.compile(
    r"^WEFUNK_Show_(\d+)_.*\.mp3$",
    flags=re.I,
)


def find_art(show_id):
    for extension in (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    ):
        candidate = ART_DIR / f"{show_id}{extension}"

        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate

    return None


def mime_for(path):
    suffix = path.suffix.lower()

    if suffix == ".png":
        return "image/png"

    if suffix == ".webp":
        return "image/webp"

    return "image/jpeg"


def embed_art(mp3, art):
    try:
        tags = ID3(mp3)
    except ID3NoHeaderError:
        tags = ID3()

    existing = [
        frame
        for frame in tags.values()
        if frame.FrameID == "APIC"
    ]

    art_bytes = art.read_bytes()

    # Avoid rewriting the file when the correct artwork
    # is already embedded.
    for frame in existing:
        if frame.data == art_bytes:
            return "unchanged"

    tags.delall("APIC")

    tags.add(
        APIC(
            encoding=3,
            mime=mime_for(art),
            type=3,
            desc="Cover",
            data=art_bytes,
        )
    )

    tags.save(mp3)

    return "embedded"


def main():
    embedded = 0
    unchanged = 0
    missing_art = 0
    failed = 0

    audio_files = sorted(
        EPISODE_DIR.glob("WEFUNK_Show_*.mp3")
    )

    for mp3 in audio_files:
        match = AUDIO_PATTERN.match(mp3.name)

        if not match:
            continue

        show_id = match.group(1)
        art = find_art(show_id)

        if not art:
            missing_art += 1
            continue

        try:
            status = embed_art(
                mp3,
                art,
            )

            if status == "embedded":
                embedded += 1
                print(
                    f"{show_id} - embedded"
                )
            else:
                unchanged += 1

        except Exception as exc:
            failed += 1
            print(
                f"{show_id} - error: {exc}"
            )

    print()
    print("WEFUNK episode artwork embed summary:")
    print(f"  Embedded:    {embedded}")
    print(f"  Unchanged:   {unchanged}")
    print(f"  Missing art: {missing_art}")
    print(f"  Failed:      {failed}")


if __name__ == "__main__":
    main()
