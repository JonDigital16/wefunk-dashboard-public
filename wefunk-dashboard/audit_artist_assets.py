#!/usr/bin/env python3
import os

import csv
import html
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(os.environ.get("WEFUNK_PROJECT_ROOT", Path(__file__).resolve().parents[1])).expanduser().resolve()
SITE = ROOT / "site"
ARTIST_DIR = SITE / "artists"
IMAGE_DIR = SITE / "artist-images"
BIO_FILE = SITE / "data" / "artist-bios.json"
REPORT_DIR = ROOT / "reports" / "artist-assets"

REPORT_DIR.mkdir(parents=True, exist_ok=True)


def normalized_identity(value: str) -> str:
    """Normalize likely aliases without changing the actual site slug."""
    value = html.unescape(str(value or "")).casefold().strip()
    value = re.sub(r"^the\s+", "", value)
    value = value.replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def extract_artist_name(page: Path) -> str:
    """Read the artist name from the artist profile heading."""
    text = page.read_text(encoding="utf-8", errors="replace")

    match = re.search(
        r'<div class="artist-profile-details">.*?'
        r'<h2[^>]*>(.*?)</h2>',
        text,
        flags=re.I | re.S,
    )

    if match:
        name = re.sub(r"<[^>]+>", "", match.group(1))
        name = html.unescape(name).strip()

        if name:
            return name

    return page.stem.replace("-", " ").title()


bios = {}

if BIO_FILE.exists():
    try:
        loaded = json.loads(BIO_FILE.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            bios = loaded
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: could not read biographies: {exc}")

page_rows = []
identity_groups = defaultdict(list)

for page in sorted(ARTIST_DIR.glob("*.html")):
    slug = page.stem
    artist = extract_artist_name(page)
    text = page.read_text(encoding="utf-8", errors="replace")

    image_exists = (IMAGE_DIR / f"{slug}.jpg").exists()
    bio_record = bios.get(slug) if isinstance(bios.get(slug), dict) else {}
    biography = str(bio_record.get("biography") or "").strip()
    biography_exists = bool(biography)

    page_uses_image = f"/artist-images/{slug}.jpg" in text
    page_uses_placeholder = "artist-profile-placeholder" in text

    row = {
        "artist": artist,
        "slug": slug,
        "page": str(page.relative_to(ROOT)),
        "image_exists": "yes" if image_exists else "no",
        "biography_exists": "yes" if biography_exists else "no",
        "page_uses_image": "yes" if page_uses_image else "no",
        "page_uses_placeholder": "yes" if page_uses_placeholder else "no",
        "normalized_identity": normalized_identity(artist),
    }

    page_rows.append(row)
    identity_groups[row["normalized_identity"]].append(row)

audit_path = REPORT_DIR / "artist-assets-audit.csv"

with audit_path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=page_rows[0].keys())
    writer.writeheader()
    writer.writerows(page_rows)

missing_image_rows = [
    row for row in page_rows
    if row["image_exists"] == "no"
]

missing_bio_rows = [
    row for row in page_rows
    if row["biography_exists"] == "no"
]

missing_rows = [
    row for row in page_rows
    if row["image_exists"] == "no"
    or row["biography_exists"] == "no"
]

missing_path = REPORT_DIR / "missing-artist-assets.csv"

with missing_path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=page_rows[0].keys())
    writer.writeheader()
    writer.writerows(missing_rows)

alias_rows = []

for identity, grouped_rows in sorted(identity_groups.items()):
    if not identity or len(grouped_rows) < 2:
        continue

    slugs = sorted({row["slug"] for row in grouped_rows})

    if len(slugs) < 2:
        continue

    complete_slugs = [
        row["slug"]
        for row in grouped_rows
        if row["image_exists"] == "yes"
        and row["biography_exists"] == "yes"
    ]

    for row in grouped_rows:
        alias_rows.append({
            "normalized_identity": identity,
            "artist": row["artist"],
            "slug": row["slug"],
            "image_exists": row["image_exists"],
            "biography_exists": row["biography_exists"],
            "possible_canonical_slug": (
                complete_slugs[0]
                if complete_slugs and row["slug"] not in complete_slugs
                else ""
            ),
            "all_related_slugs": " | ".join(slugs),
        })

alias_path = REPORT_DIR / "possible-artist-aliases.csv"

with alias_path.open("w", newline="", encoding="utf-8") as handle:
    fields = [
        "normalized_identity",
        "artist",
        "slug",
        "image_exists",
        "biography_exists",
        "possible_canonical_slug",
        "all_related_slugs",
    ]
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(alias_rows)

page_slugs = {row["slug"] for row in page_rows}
image_slugs = {path.stem for path in IMAGE_DIR.glob("*.jpg")}
bio_slugs = set(bios)

orphan_rows = []

for slug in sorted(image_slugs - page_slugs):
    orphan_rows.append({
        "slug": slug,
        "asset_type": "image",
        "path": str((IMAGE_DIR / f"{slug}.jpg").relative_to(ROOT)),
    })

for slug in sorted(bio_slugs - page_slugs):
    orphan_rows.append({
        "slug": slug,
        "asset_type": "biography",
        "path": str(BIO_FILE.relative_to(ROOT)),
    })

orphan_path = REPORT_DIR / "orphaned-artist-assets.csv"

with orphan_path.open("w", newline="", encoding="utf-8") as handle:
    fields = ["slug", "asset_type", "path"]
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(orphan_rows)

broken_links = []

for page in SITE.rglob("*.html"):
    text = page.read_text(encoding="utf-8", errors="replace")

    for slug in re.findall(r'href=["\']/artists/([^"\']+)\.html', text, flags=re.I):
        target = ARTIST_DIR / f"{slug}.html"

        if not target.exists():
            broken_links.append({
                "source_page": str(page.relative_to(ROOT)),
                "artist_slug": slug,
                "expected_target": str(target.relative_to(ROOT)),
            })

broken_path = REPORT_DIR / "broken-artist-links.csv"

with broken_path.open("w", newline="", encoding="utf-8") as handle:
    fields = ["source_page", "artist_slug", "expected_target"]
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(broken_links)

print("Artist asset audit complete")
print("----------------------------------------")
print(f"Artist pages:             {len(page_rows):,}")
print(f"Missing images:           {len(missing_image_rows):,}")
print(f"Missing biographies:      {len(missing_bio_rows):,}")
print(f"Missing image or bio:     {len(missing_rows):,}")
print(f"Possible alias rows:      {len(alias_rows):,}")
print(f"Orphaned assets:          {len(orphan_rows):,}")
print(f"Broken artist links:      {len(broken_links):,}")
print()
print(f"Full audit:       {audit_path}")
print(f"Missing assets:   {missing_path}")
print(f"Possible aliases: {alias_path}")
print(f"Orphaned assets:  {orphan_path}")
print(f"Broken links:     {broken_path}")
