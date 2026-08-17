#!/usr/bin/env python3

import csv
import hashlib
import os
import secrets
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

from common import artist_slugify

SITE = Path(
    os.environ.get(
        "WEFUNK_SITE_DIR",
        str(Path(__file__).resolve().parents[1] / "site"),
    )
)

ARTIST_IMAGES = SITE / "artist-images"
REPORT = Path(
    str(Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve()) + "/"
    "wefunk_artist_image_download_report.csv"
)

ND_URL = os.environ.get("ND_URL", "").rstrip("/")
ND_USER = os.environ.get("ND_USER", "")
ND_PASS = os.environ.get("ND_PASS", "")

REQUEST_DELAY = 0.10
IMAGE_SIZE = 700
TIMEOUT = 60

# Known Navidrome generic artist placeholder.
PLACEHOLDER_HASHES = {
    "f6bc764cfbad7e0a4c6e79cc2edec0e1",
}

PROJECT_ROOT = Path(os.environ.get("WEFUNK_PROJECT_ROOT", Path(__file__).resolve().parents[1])).expanduser().resolve()
PLACEHOLDER_BACKUP_DIR = (
    PROJECT_ROOT
    / "backups"
    / "artist-images"
    / "navidrome-placeholders"
)

ARTIST_IMAGES.mkdir(parents=True, exist_ok=True)
PLACEHOLDER_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


if not ND_URL:
    fail("ND_URL is not set")

if not ND_USER:
    fail("ND_USER is not set")

if not ND_PASS:
    fail("ND_PASS is not set")


salt = secrets.token_hex(8)
token = hashlib.md5((ND_PASS + salt).encode()).hexdigest()


def params(extra=None):
    values = {
        "u": ND_USER,
        "t": token,
        "s": salt,
        "v": "1.16.1",
        "c": "wefunk-dashboard",
        "f": "json",
    }

    if extra:
        values.update(extra)

    return values


def api_json(endpoint, extra=None):
    response = requests.get(
        f"{ND_URL}/rest/{endpoint}.view",
        params=params(extra),
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    payload = response.json().get("subsonic-response", {})

    if payload.get("status") != "ok":
        error = payload.get("error", {})
        raise RuntimeError(
            error.get("message") or f"Navidrome API error: {endpoint}"
        )

    return payload


def all_artists():
    payload = api_json("getArtists")
    groups = payload.get("artists", {}).get("index", [])

    artists = []

    for group in groups:
        for artist in group.get("artist", []):
            artist_id = str(artist.get("id") or "").strip()
            artist_name = str(artist.get("name") or "").strip()

            if artist_id and artist_name:
                artists.append(
                    {
                        "id": artist_id,
                        "name": artist_name,
                    }
                )

    return artists


def file_md5(path):
    digest = hashlib.md5()

    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def is_placeholder_image(path):
    path = Path(path)

    if not path.exists() or path.stat().st_size <= 0:
        return False

    return file_md5(path) in PLACEHOLDER_HASHES


def quarantine_placeholder(path):
    path = Path(path)

    destination = PLACEHOLDER_BACKUP_DIR / path.name

    if destination.exists():
        stem = destination.stem
        suffix = destination.suffix
        counter = 2

        while destination.exists():
            destination = (
                PLACEHOLDER_BACKUP_DIR
                / f"{stem}-{counter}{suffix}"
            )
            counter += 1

    path.replace(destination)

    print(
        f"  Quarantined placeholder: "
        f"{path.name} -> {destination}"
    )

    return destination


def existing_image(slug):
    for extension in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = ARTIST_IMAGES / f"{slug}{extension}"

        if not candidate.exists() or candidate.stat().st_size <= 0:
            continue

        if is_placeholder_image(candidate):
            quarantine_placeholder(candidate)
            continue

        return candidate

    return None


def download_artist_image(artist):
    slug = artist_slugify(artist["name"])

    if not slug:
        return {
            "artist": artist["name"],
            "artist_id": artist["id"],
            "slug": "",
            "path": "",
            "status": "invalid-slug",
            "message": "",
        }

    current = existing_image(slug)

    if current:
        return {
            "artist": artist["name"],
            "artist_id": artist["id"],
            "slug": slug,
            "path": str(current),
            "status": "existing",
            "message": "",
        }

    response = requests.get(
        f"{ND_URL}/rest/getCoverArt.view",
        params=params({
            "id": artist["id"],
            "size": IMAGE_SIZE,
        }),
        timeout=TIMEOUT,
    )

    if response.status_code == 404:
        return {
            "artist": artist["name"],
            "artist_id": artist["id"],
            "slug": slug,
            "path": "",
            "status": "not-found",
            "message": "Navidrome returned 404",
        }

    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()

    if not content_type.startswith("image/"):
        return {
            "artist": artist["name"],
            "artist_id": artist["id"],
            "slug": slug,
            "path": "",
            "status": "not-image",
            "message": content_type,
        }

    try:
        with Image.open(BytesIO(response.content)) as image:
            image.load()

            if image.width < 100 or image.height < 100:
                raise ValueError(
                    f"image is too small: {image.width}x{image.height}"
                )

            if image.mode not in ("RGB", "L"):
                background = Image.new("RGB", image.size, "black")

                if "A" in image.getbands():
                    background.paste(image, mask=image.getchannel("A"))
                else:
                    background.paste(image)

                image = background
            else:
                image = image.convert("RGB")

            destination = ARTIST_IMAGES / f"{slug}.jpg"

            image.thumbnail((IMAGE_SIZE, IMAGE_SIZE))
            image.save(
                destination,
                format="JPEG",
                quality=88,
                optimize=True,
                progressive=True,
            )

            if is_placeholder_image(destination):
                quarantine_placeholder(destination)

                return {
                    "artist": artist["name"],
                    "artist_id": artist["id"],
                    "slug": slug,
                    "path": "",
                    "status": "placeholder",
                    "message": "Navidrome returned generic artist placeholder",
                }

    except Exception as exc:
        return {
            "artist": artist["name"],
            "artist_id": artist["id"],
            "slug": slug,
            "path": "",
            "status": "invalid-image",
            "message": str(exc),
        }

    return {
        "artist": artist["name"],
        "artist_id": artist["id"],
        "slug": slug,
        "path": str(destination),
        "status": "downloaded",
        "message": "",
    }


def write_report(rows):
    fields = [
        "artist",
        "artist_id",
        "slug",
        "path",
        "status",
        "message",
    ]

    with REPORT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    artists = all_artists()

    print(f"Found {len(artists)} Navidrome artists")
    print(f"Artist image directory: {ARTIST_IMAGES}")

    results = []

    for number, artist in enumerate(artists, start=1):
        try:
            result = download_artist_image(artist)
        except Exception as exc:
            result = {
                "artist": artist["name"],
                "artist_id": artist["id"],
                "slug": artist_slugify(artist["name"]),
                "path": "",
                "status": "error",
                "message": str(exc),
            }

        results.append(result)

        print(
            f"[{number}/{len(artists)}] "
            f"{result['status']:13} "
            f"{artist['name']}"
        )

        if result["status"] not in ("existing", "invalid-slug"):
            time.sleep(REQUEST_DELAY)

    write_report(results)

    counts = {}

    for row in results:
        status = row["status"]
        counts[status] = counts.get(status, 0) + 1

    print()
    print("Artist image results")

    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    print()
    print(f"Report: {REPORT}")


if __name__ == "__main__":
    main()
