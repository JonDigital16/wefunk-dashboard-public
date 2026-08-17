#!/usr/bin/env python3
import os

import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image
from rapidfuzz import fuzz

EXPORTS = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve()
MISSING_CSV = EXPORTS / "wefunk_missing_album_art.csv"
REPORT = EXPORTS / "wefunk_album_art_download_report.csv"
COVERS = Path(os.environ.get("WEFUNK_SITE_DIR", Path(__file__).resolve().parents[1] / "site")) / "covers"

USER_AGENT = "WEFUNK-Dashboard/1.0 (jonfeuer16@gmail.com)"
MUSICBRAINZ = "https://musicbrainz.org/ws/2"
COVER_ART = "https://coverartarchive.org"

MIN_SCORE = 82
REQUEST_DELAY = 1.1

COVERS.mkdir(parents=True, exist_ok=True)


def normalize(value):
    value = str(value or "").lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def first_year(value):
    match = re.search(r"\b(?:19|20)\d{2}\b", str(value or ""))
    return int(match.group(0)) if match else None


def request(url, accept="application/json"):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
    )

    with urllib.request.urlopen(req, timeout=25) as response:
        return (
            response.read(),
            response.headers.get("Content-Type", ""),
            response.geturl(),
        )


def existing_cover(slug):
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        path = COVERS / f"{slug}{ext}"
        if path.exists():
            return path
    return None


def search_release_groups(artist, album):
    album_variants = [album]

    # MusicBrainz titles sometimes omit subtitles or use different punctuation.
    for separator in (" - ", ": ", " / "):
        if separator in album:
            shorter = album.split(separator, 1)[0].strip()
            if shorter and shorter not in album_variants:
                album_variants.append(shorter)

    # Also try common punctuation-normalized forms.
    punctuation_clean = re.sub(r"[^A-Za-z0-9 ]+", " ", album)
    punctuation_clean = " ".join(punctuation_clean.split())

    if punctuation_clean and punctuation_clean not in album_variants:
        album_variants.append(punctuation_clean)

    queries = []

    for album_variant in album_variants:
        queries.append(
            f'artist:"{artist}" AND releasegroup:"{album_variant}"'
        )

    # Final broader fallback.
    queries.append(f'artist:"{artist}" AND "{album}"')

    found = {}

    for query in queries:
        url = (
            f"{MUSICBRAINZ}/release-group?"
            + urllib.parse.urlencode({
                "query": query,
                "fmt": "json",
                "limit": 15,
            })
        )

        data, _, _ = request(url)
        time.sleep(REQUEST_DELAY)

        for candidate in json.loads(data).get("release-groups", []):
            candidate_id = candidate.get("id")

            if candidate_id:
                found[candidate_id] = candidate

        if found:
            break

    return list(found.values())


def candidate_score(row, candidate):
    wanted_artist = normalize(row["artist"])
    wanted_album = normalize(row["album"])

    candidate_album = normalize(candidate.get("title"))

    credits = candidate.get("artist-credit") or []
    candidate_artist = " ".join(
        str(part.get("name") or "")
        for part in credits
        if isinstance(part, dict)
    )

    album_score = fuzz.token_set_ratio(
        wanted_album,
        candidate_album,
    )

    artist_score = fuzz.token_set_ratio(
        wanted_artist,
        normalize(candidate_artist),
    )

    score = (album_score * 0.65) + (artist_score * 0.35)

    wanted_year = first_year(row.get("year"))
    candidate_year = first_year(candidate.get("first-release-date"))

    if wanted_year and candidate_year:
        difference = abs(wanted_year - candidate_year)

        if difference == 0:
            score += 5
        elif difference <= 1:
            score += 2
        elif difference >= 5:
            score -= 5

    return round(min(100, score), 1), candidate_artist


def download_cover(release_group_id, slug):
    urls = [
        f"{COVER_ART}/release-group/{release_group_id}/front-500",
        f"{COVER_ART}/release-group/{release_group_id}/front",
    ]

    for url in urls:
        try:
            data, _, final_url = request(url, accept="image/*")
            time.sleep(REQUEST_DELAY)

            with Image.open(BytesIO(data)) as image:
                image.load()
                image_format = (image.format or "JPEG").lower()

            if image_format == "jpeg":
                image_format = "jpg"

            if image_format not in {"jpg", "png", "webp"}:
                image_format = "jpg"

            destination = COVERS / f"{slug}.{image_format}"
            destination.write_bytes(data)

            return destination, final_url

        except urllib.error.HTTPError as exc:
            time.sleep(REQUEST_DELAY)

            if exc.code == 404:
                continue

            raise

    return None, ""


if not MISSING_CSV.exists():
    raise SystemExit(f"Missing input file: {MISSING_CSV}")

with MISSING_CSV.open(newline="", encoding="utf-8") as handle:
    albums = list(csv.DictReader(handle))

results = []
downloaded = 0
already_present = 0
low_confidence = 0
not_found = 0
errors = 0

for number, row in enumerate(albums, 1):
    artist = (row.get("artist") or "").strip()
    album = (row.get("album") or "").strip()
    slug = (row.get("slug") or "").strip()

    print(f"[{number}/{len(albums)}] {artist} — {album}")

    result = {
        "artist": artist,
        "album": album,
        "slug": slug,
        "status": "",
        "score": "",
        "musicbrainz_artist": "",
        "musicbrainz_album": "",
        "release_group_id": "",
        "cover_file": "",
        "source_url": "",
        "error": "",
    }

    current = existing_cover(slug)

    if current:
        result["status"] = "already_present"
        result["cover_file"] = str(current)
        already_present += 1
        results.append(result)
        print("  ↪ Already present")
        continue

    try:
        candidates = search_release_groups(artist, album)

        scored = []

        for candidate in candidates:
            score, candidate_artist = candidate_score(row, candidate)
            scored.append((score, candidate, candidate_artist))

        scored.sort(key=lambda item: item[0], reverse=True)

        if not scored:
            result["status"] = "not_found"
            not_found += 1
            results.append(result)
            print("  ✗ No MusicBrainz result")
            continue

        score, candidate, candidate_artist = scored[0]

        result["score"] = score
        result["musicbrainz_artist"] = candidate_artist
        result["musicbrainz_album"] = candidate.get("title") or ""
        result["release_group_id"] = candidate.get("id") or ""

        if score < MIN_SCORE:
            result["status"] = "low_confidence"
            low_confidence += 1
            results.append(result)

            print(f"  ⚠ Low confidence: {score}")
            print(
                f"    Candidate: {candidate_artist} — "
                f"{candidate.get('title', '')}"
            )
            continue

        cover, source_url = download_cover(
            candidate["id"],
            slug,
        )

        if not cover:
            result["status"] = "no_cover_art"
            not_found += 1
            results.append(result)
            print("  ✗ Match found, but no cover art")
            continue

        result["status"] = "downloaded"
        result["cover_file"] = str(cover)
        result["source_url"] = source_url
        downloaded += 1
        results.append(result)

        print(f"  ✓ Downloaded ({score} confidence)")

    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        errors += 1
        results.append(result)
        print(f"  ✗ Error: {exc}")

REPORT_FIELDS = [
    "artist",
    "album",
    "slug",
    "status",
    "score",
    "musicbrainz_artist",
    "musicbrainz_album",
    "release_group_id",
    "cover_file",
    "source_url",
    "error",
]

with REPORT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=REPORT_FIELDS,
    )
    writer.writeheader()
    writer.writerows(results)

print("")
print("Missing album artwork download complete")
print(f"  Albums checked: {len(albums)}")
print(f"  Downloaded: {downloaded}")
print(f"  Already present: {already_present}")
print(f"  Low confidence: {low_confidence}")
print(f"  Not found/no artwork: {not_found}")
print(f"  Errors: {errors}")
print(f"  Report: {REPORT}")
