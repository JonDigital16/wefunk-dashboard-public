#!/usr/bin/env python3

import argparse
import re
import os
from pathlib import Path

from mutagen.id3 import APIC, ID3, ID3NoHeaderError


EPISODE_DIR = Path(os.environ.get("WEFUNK_EPISODE_DIR", Path(os.environ.get("WEFUNK_MUSIC_DIR", Path.home() / "Music")) / "wefunkradio mixes")).expanduser().resolve()

ART_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "artwork" / 'episodes'

# Require the exact WEFUNK downloader filename convention.
EPISODE_FILENAME_RE = re.compile(
    r"^WEFUNK_Show_(\d+)_.*\.mp3$",
    re.IGNORECASE,
)


def show_id_from_episode_filename(path: Path) -> str | None:
    """
    Return a show number only for a verified WEFUNK episode filename.

    Examples accepted:
        WEFUNK_Show_311_2005-01-01_hq.mp3
        WEFUNK_Show_1298_2026-07-25_hq.mp3

    Examples rejected:
        311 - Grassroots.mp3
        Artist 311 - Song.mp3
        Album 1999 - Track.mp3
    """
    match = EPISODE_FILENAME_RE.fullmatch(path.name)

    if not match:
        return None

    return match.group(1)


def find_episode_art(show_id: str) -> Path | None:
    """
    Find artwork for one exact show number.

    JPG is preferred, followed by PNG and WEBP.
    """
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = ART_DIR / f"{show_id}{suffix}"

        if candidate.is_file():
            return candidate

    return None


def artwork_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".png":
        return "image/png"

    if suffix == ".webp":
        return "image/webp"

    return "image/jpeg"


def collect_matches() -> list[tuple[Path, Path, str]]:
    matches: list[tuple[Path, Path, str]] = []

    if not EPISODE_DIR.is_dir():
        raise SystemExit(
            f"WEFUNK episode directory was not found:\n{EPISODE_DIR}"
        )

    if not ART_DIR.is_dir():
        raise SystemExit(
            f"WEFUNK artwork directory was not found:\n{ART_DIR}"
        )

    # Do not recursively scan the complete music library.
    # Only inspect verified files inside the dedicated episode directory.
    for audio in sorted(EPISODE_DIR.glob("WEFUNK_Show_*.mp3")):
        if not audio.is_file():
            continue

        show_id = show_id_from_episode_filename(audio)

        if show_id is None:
            continue

        art = find_episode_art(show_id)

        if art is None:
            continue

        matches.append((audio, art, show_id))

    return matches


def write_episode_art(audio: Path, art: Path) -> None:
    try:
        tags = ID3(audio)
    except ID3NoHeaderError:
        tags = ID3()

    tags.delall("APIC")

    tags.add(
        APIC(
            encoding=3,
            mime=artwork_mime_type(art),
            type=3,
            desc="Cover",
            data=art.read_bytes(),
        )
    )

    tags.save(audio, v2_version=3)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Safely apply WEFUNK episode artwork only to files using "
            "the verified WEFUNK_Show_<number> filename format."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write artwork. Without this option, perform a dry run.",
    )

    args = parser.parse_args()

    matches = collect_matches()

    print("WEFUNK episode artwork tagger")
    print("-----------------------------")
    print(f"Episode directory: {EPISODE_DIR}")
    print(f"Artwork directory: {ART_DIR}")
    print(f"Verified matches: {len(matches):,}")
    print("")

    for audio, art, show_id in matches:
        print(
            f"Show {show_id}: "
            f"{audio.name}  <--  {art.name}"
        )

    if not args.apply:
        print("")
        print("Dry run only. No media files were changed.")
        print("To write the verified artwork, run with --apply.")
        return

    updated = 0

    for audio, art, show_id in matches:
        try:
            write_episode_art(audio, art)
            print(f"Updated show {show_id}: {audio.name}")
            updated += 1

        except Exception as exc:
            raise SystemExit(
                f"Failed writing artwork for show {show_id}:\n"
                f"{audio}\n"
                f"{exc}"
            ) from exc

    print("")
    print("Episode artwork summary:")
    print(f"  Verified files: {len(matches):,}")
    print(f"  Updated: {updated:,}")


if __name__ == "__main__":
    main()
