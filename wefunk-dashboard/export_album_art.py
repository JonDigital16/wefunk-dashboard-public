#!/usr/bin/env python3
import os

from collections import defaultdict
from io import BytesIO
from pathlib import Path
import shutil

from mutagen import File
from PIL import Image

from common import SITE
from data import owned_tracks_enriched

LIVE_COVERS = Path(
    str(Path(os.environ.get("WEFUNK_SITE_DIR", Path(__file__).resolve().parents[1] / "site")) / "covers")
)
COVERS = SITE / "covers"

# Reuse existing live artwork during normal builds.
if LIVE_COVERS.exists() and not COVERS.exists():
    shutil.copytree(LIVE_COVERS, COVERS)

COVERS.mkdir(parents=True, exist_ok=True)


def get_art(audio):
    if not audio:
        return None

    if hasattr(audio, "pictures") and audio.pictures:
        return audio.pictures[0].data

    tags = getattr(audio, "tags", None)

    if not tags:
        return None

    for key in tags.keys():
        if str(key).startswith("APIC"):
            return tags[key].data

    covr = tags.get("covr")

    if covr:
        return bytes(covr[0])

    return None


def existing_cover(slug):
    for extension in (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    ):
        candidate = COVERS / f"{slug}{extension}"

        if candidate.exists():
            return candidate

    return None


# Keep every possible audio file for each canonical album.
album_paths = defaultdict(list)

for row in owned_tracks_enriched:
    slug = (
        row.get("matched_album_slug")
        or ""
    ).strip()

    path = Path(
        row.get("file_path")
        or ""
    )

    if (
        not slug
        or not path.exists()
        or path in album_paths[slug]
    ):
        continue

    album_paths[slug].append(path)


needed = {
    slug: paths
    for slug, paths in album_paths.items()
    if not existing_cover(slug)
}

saved = 0
failed = []
files_checked = 0

for slug, paths in needed.items():
    cover_saved = False

    for path in paths:
        files_checked += 1

        try:
            audio = File(path)
            art = get_art(audio)

            if not art:
                continue

            # Validate the artwork and determine its actual format.
            with Image.open(BytesIO(art)) as image:
                image.verify()
                extension = (
                    image.format
                    or "JPEG"
                ).lower()

            if extension == "jpeg":
                extension = "jpg"

            if extension not in {
                "jpg",
                "png",
                "webp",
            }:
                extension = "jpg"

            output = COVERS / f"{slug}.{extension}"
            output.write_bytes(art)

            saved += 1
            cover_saved = True
            break

        except Exception:
            continue

    if not cover_saved:
        failed.append(slug)


print("Album artwork export complete")
print(f"  Canonical albums checked: {len(album_paths)}")
print(f"  Albums needing artwork: {len(needed)}")
print(f"  Covers saved: {saved}")
print(f"  Audio files inspected: {files_checked}")
print(f"  Albums still missing artwork: {len(failed)}")
print(COVERS)

if failed:
    print("")
    print("Still missing:")

    for slug in failed[:50]:
        print(f"  {slug}")
