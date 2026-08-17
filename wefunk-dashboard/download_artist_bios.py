#!/usr/bin/env python3

import hashlib
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))

from common import artist_slugify

SITE = Path(
    os.environ.get(
        "WEFUNK_SITE_DIR",
        str(Path(__file__).resolve().parents[1] / "site"),
    )
)

BIO_FILE = SITE / "data" / "artist-bios.json"

ND_URL = os.environ.get("ND_URL", "").rstrip("/")
ND_USER = os.environ.get("ND_USER", "")
ND_PASS = os.environ.get("ND_PASS", "")

TIMEOUT = 60
REQUEST_DELAY = 0.15

BIO_FILE.parent.mkdir(parents=True, exist_ok=True)


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


def load_existing():
    if not BIO_FILE.exists():
        return {}

    try:
        data = json.loads(BIO_FILE.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass

    return {}


def write_bios(data):
    temporary = BIO_FILE.with_suffix(".json.tmp")

    temporary.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary.replace(BIO_FILE)


def all_artists():
    payload = api_json("getArtists")
    groups = payload.get("artists", {}).get("index", [])

    artists = []

    for group in groups:
        for artist in group.get("artist", []):
            artist_id = str(artist.get("id") or "").strip()
            artist_name = str(artist.get("name") or "").strip()

            if artist_id and artist_name:
                artists.append({
                    "id": artist_id,
                    "name": artist_name,
                })

    return artists


def fetch_biography(artist):
    payload = api_json(
        "getArtistInfo2",
        {
            "id": artist["id"],
            "count": 0,
            "includeNotPresent": "false",
        },
    )

    info = payload.get("artistInfo2", {})

    biography = " ".join(
        str(info.get("biography") or "").split()
    ).strip()

    return {
        "artist": artist["name"],
        "artist_id": artist["id"],
        "biography": biography,
        "lastfm_url": str(info.get("lastFmUrl") or "").strip(),
        "musicbrainz_id": str(
            info.get("musicBrainzId") or ""
        ).strip(),
        "status": "available" if biography else "not-available",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    artists = all_artists()
    bios = load_existing()

    print(f"Found {len(artists)} Navidrome artists")
    print(f"Biography cache: {BIO_FILE}")

    new_count = 0
    available_count = 0
    unavailable_count = 0
    existing_count = 0
    error_count = 0

    for number, artist in enumerate(artists, start=1):
        slug = artist_slugify(artist["name"])

        if not slug:
            print(
                f"[{number}/{len(artists)}] "
                f"invalid-slug  {artist['name']}"
            )
            continue

        if slug in bios:
            existing_count += 1
            print(
                f"[{number}/{len(artists)}] "
                f"existing      {artist['name']}"
            )
            continue

        try:
            record = fetch_biography(artist)
            bios[slug] = record
            new_count += 1

            if record["status"] == "available":
                available_count += 1
            else:
                unavailable_count += 1

            print(
                f"[{number}/{len(artists)}] "
                f"{record['status']:13} "
                f"{artist['name']}"
            )

            # Save after every successful artist so an interrupted
            # first run does not lose completed work.
            write_bios(bios)

        except Exception as exc:
            error_count += 1
            print(
                f"[{number}/{len(artists)}] "
                f"error         {artist['name']}: {exc}"
            )

        time.sleep(REQUEST_DELAY)

    write_bios(bios)

    print()
    print("Artist biography results")
    print(f"  Existing cache entries: {existing_count}")
    print(f"  New biographies:        {available_count}")
    print(f"  New without biography:  {unavailable_count}")
    print(f"  Errors:                  {error_count}")
    print(f"  Total cached artists:    {len(bios)}")
    print()
    print(f"Biography cache: {BIO_FILE}")


if __name__ == "__main__":
    main()
