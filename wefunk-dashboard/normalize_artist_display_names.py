#!/usr/bin/env python3

import html
import os
import re
from pathlib import Path

from common import artist_display_name

SITE = Path(
    os.environ.get(
        "WEFUNK_SITE_DIR",
        str(Path(__file__).resolve().parents[1] / "site"),
    )
)

artist_link_pattern = re.compile(
    r'''(
        <a\b
        [^>]*?
        href=["']/artists/
        (?P<slug>[^"'?#/]+)
        \.html
        [^>]*>
    )
    (?P<label>.*?)
    (
        </a>
    )''',
    flags=re.I | re.S | re.X,
)

artist_name_div_pattern = re.compile(
    r'''(
        <div\b
        [^>]*class=["'][^"']*\bartist-name\b[^"']*["']
        [^>]*>
    )
    (?P<label>.*?)
    (
        </div>
    )''',
    flags=re.I | re.S | re.X,
)

signature_artist_pattern = re.compile(
    r'''(
        <div\b[^>]*class=["'][^"']*\bstat\b[^"']*["'][^>]*>
    )
    (?P<label>.*?)
    (
        </div>
        \s*
        <div\b[^>]*class=["'][^"']*\blabel\b[^"']*["'][^>]*>
        \s*Signature\ Artist\s*
        </div>
    )''',
    flags=re.I | re.S | re.X,
)

artist_profile_pattern = re.compile(
    r'''(
        <div\b[^>]*class=["'][^"']*\bartist-profile-details\b[^"']*["'][^>]*>
        .*?
        <h2\b[^>]*>
    )
    (?P<label>.*?)
    (
        </h2>
    )''',
    flags=re.I | re.S | re.X,
)


def plain_text(value):
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def replace_artist_link(match):
    label = match.group("label")

    # Avoid destroying links containing images or nested formatting.
    if "<" in label or ">" in label:
        return match.group(0)

    current_name = plain_text(label)
    slug = match.group("slug")

    preferred_name = artist_display_name(
        current_name,
        slug=slug,
    )

    if not preferred_name:
        return match.group(0)

    return (
        match.group(1)
        + html.escape(preferred_name)
        + match.group(4)
    )


def replace_name_container(match):
    label = match.group("label")

    if "<" in label or ">" in label:
        return match.group(0)

    current_name = plain_text(label)
    preferred_name = artist_display_name(current_name)

    if not preferred_name:
        return match.group(0)

    return (
        match.group(1)
        + html.escape(preferred_name)
        + match.group(3)
    )


updated_pages = 0
updated_names = 0

for path in SITE.rglob("*.html"):
    original = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    text = original

    for pattern, replacement in (
        (artist_link_pattern, replace_artist_link),
        (artist_name_div_pattern, replace_name_container),
        (signature_artist_pattern, replace_name_container),
        (artist_profile_pattern, replace_name_container),
    ):
        before = text
        text = pattern.sub(replacement, text)

        if text != before:
            updated_names += 1

    if text == original:
        continue

    path.write_text(text, encoding="utf-8")
    updated_pages += 1

print("Artist display-name normalization complete")
print(f"  Pages updated: {updated_pages:,}")
print(f"  Replacement groups: {updated_names:,}")
