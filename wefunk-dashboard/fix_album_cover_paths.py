#!/usr/bin/env python3

import csv
import json
import os
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

SITE = Path(
    os.environ.get(
        "WEFUNK_SITE_DIR",
        str(Path(__file__).resolve().parents[1] / "site"),
    )
)

EXPORTS = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve()
ALBUM_INDEX = EXPORTS / "wefunk_album_index.csv"
COVERS = SITE / "covers"
PLACEHOLDER = COVERS / "placeholder.svg"
ALIAS_REPORT = EXPORTS / "wefunk_album_cover_aliases.json"

EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

COVERS.mkdir(parents=True, exist_ok=True)

PLACEHOLDER.write_text(
    """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600">
  <rect width="600" height="600" fill="#111419"/>
  <circle cx="300" cy="280" r="165"
          fill="#171a1f"
          stroke="#2b2f36"
          stroke-width="14"/>
  <circle cx="300" cy="280" r="48" fill="#f7931e"/>
  <text x="300" y="500"
        text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif"
        font-size="38"
        font-weight="700"
        fill="#f7931e">WEFUNK</text>
</svg>
""",
    encoding="utf-8",
)


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def base_artist(value):
    """
    Reduce featured-artist forms to their main artist.

    Examples:
      OutKast feat. Raekwon -> outkast
      Gang Starr featuring K-Ci -> gang starr
    """
    value = normalize(value)

    separators = (
        " featuring ",
        " feat ",
        " ft ",
        " with ",
        " presents ",
    )

    for separator in separators:
        if separator in value:
            value = value.split(separator, 1)[0].strip()

    return value


def cover_filename(slug):
    for extension in EXTENSIONS:
        candidate = COVERS / f"{slug}{extension}"

        if candidate.exists():
            return candidate.name

    return None


if not ALBUM_INDEX.exists():
    raise SystemExit(f"Missing album index: {ALBUM_INDEX}")

with ALBUM_INDEX.open(newline="", encoding="utf-8") as handle:
    albums = list(csv.DictReader(handle))

available = {
    path.stem: path.name
    for path in COVERS.iterdir()
    if path.is_file() and path.suffix.lower() in EXTENSIONS
}

# Group album records by normalized album title.
by_album_title = defaultdict(list)

for row in albums:
    slug = (row.get("slug") or "").strip()
    album = (row.get("album") or "").strip()
    artist = (row.get("artist") or "").strip()

    if not slug or not album:
        continue

    by_album_title[normalize(album)].append({
        "slug": slug,
        "album": album,
        "artist": artist,
        "artist_base": base_artist(artist),
        "cover": available.get(slug),
    })


aliases = {}

for album_title, group in by_album_title.items():
    covered = [item for item in group if item["cover"]]

    if not covered:
        continue

    for item in group:
        if item["cover"]:
            continue

        best = None
        best_score = -1

        for candidate in covered:
            score = 0

            if item["artist_base"] == candidate["artist_base"]:
                score += 100

            elif (
                item["artist_base"]
                and candidate["artist_base"]
                and (
                    item["artist_base"] in candidate["artist_base"]
                    or candidate["artist_base"] in item["artist_base"]
                )
            ):
                score += 70

            item_tokens = set(item["artist_base"].split())
            candidate_tokens = set(candidate["artist_base"].split())

            if item_tokens and candidate_tokens:
                overlap = len(item_tokens & candidate_tokens)
                score += overlap * 10

            # Exact album title is already guaranteed by the group.
            # Prefer shorter canonical artist names in a tie.
            score -= len(candidate["artist_base"]) / 1000

            if score > best_score:
                best_score = score
                best = candidate

        # If there is only one covered version of this exact album title,
        # it is safe to reuse it even when the featured artist is unusual.
        if best and (best_score >= 20 or len(covered) == 1):
            aliases[item["slug"]] = {
                "cover": best["cover"],
                "canonical_slug": best["slug"],
                "album": item["album"],
                "artist": item["artist"],
                "canonical_artist": best["artist"],
            }


pattern = re.compile(
    r'(?P<prefix>(?:src|href)=["\'])'
    r'/covers/(?P<slug>[^"\']+?)'
    r'\.(?P<ext>jpg|jpeg|png|webp)'
    r'(?P<suffix>["\'])',
    flags=re.I,
)

corrected_extensions = 0
canonical_reused = 0
placeholder_references = 0
pages_updated = 0
unique_placeholder_slugs = set()


def replace_cover(match):
    global corrected_extensions
    global canonical_reused
    global placeholder_references

    slug = match.group("slug")
    requested_extension = "." + match.group("ext").lower()
    requested = COVERS / f"{slug}{requested_extension}"

    if requested.exists():
        return match.group(0)

    exact_cover = cover_filename(slug)

    if exact_cover:
        corrected_extensions += 1
        return (
            f'{match.group("prefix")}'
            f'/covers/{exact_cover}'
            f'{match.group("suffix")}'
        )

    alias = aliases.get(slug)

    if alias:
        canonical_reused += 1
        return (
            f'{match.group("prefix")}'
            f'/covers/{alias["cover"]}'
            f'{match.group("suffix")}'
        )

    placeholder_references += 1
    unique_placeholder_slugs.add(slug)

    return (
        f'{match.group("prefix")}'
        f'/covers/placeholder.svg'
        f'{match.group("suffix")}'
    )


for page in SITE.rglob("*.html"):
    original = page.read_text(encoding="utf-8")
    updated = pattern.sub(replace_cover, original)

    if updated != original:
        page.write_text(updated, encoding="utf-8")
        pages_updated += 1


ALIAS_REPORT.write_text(
    json.dumps(
        {
            "aliases": aliases,
            "unique_unresolved_slugs": sorted(unique_placeholder_slugs),
        },
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)

print("Album cover resolution complete")
print(f"  Corrected extensions: {corrected_extensions}")
print(f"  Canonical covers reused: {canonical_reused}")
print(f"  Placeholder references: {placeholder_references}")
print(f"  Unique unresolved albums: {len(unique_placeholder_slugs)}")
print(f"  Pages updated: {pages_updated}")
print(f"  Alias report: {ALIAS_REPORT}")
