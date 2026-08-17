#!/usr/bin/env python3

import csv
import hashlib
import html
import json
import re
import sys
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE, artist_slugify
from data import missing_tracks_engine, missing_tracks


MISSING_PAGE = SITE / "missing.html"
ARTIST_IMAGES = SITE / "artist-images"

REPORT_DIR = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "artist-images"
)

PASS2_MODE = (
    __import__("os").environ.get(
        "WEFUNK_ARTIST_IMAGE_PASS2",
        "",
    ).strip().lower()
    in {
        "1",
        "true",
        "yes",
        "on",
    }
)

if PASS2_MODE:
    RESULTS_FILE = (
        REPORT_DIR
        / "musicbrainz-image-pass2-results.csv"
    )

    UNRESOLVED_FILE = (
        REPORT_DIR
        / "musicbrainz-image-pass2-unresolved.csv"
    )

    ATTRIBUTION_FILE = (
        REPORT_DIR
        / "musicbrainz-image-pass2-attribution.csv"
    )
else:
    RESULTS_FILE = (
        REPORT_DIR
        / "musicbrainz-image-results.csv"
    )

    UNRESOLVED_FILE = (
        REPORT_DIR
        / "musicbrainz-image-unresolved.csv"
    )

    ATTRIBUTION_FILE = (
        REPORT_DIR
        / "musicbrainz-image-attribution.csv"
    )

MB_API = "https://musicbrainz.org/ws/2"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_ENTITY = (
    "https://www.wikidata.org/wiki/"
    "Special:EntityData/{qid}.json"
)

HEADERS = {
    "User-Agent": (
        "WEFUNK-Dashboard/1.0 "
        "(personal music dashboard)"
    )
}

MIN_MB_SCORE = 100
IMAGE_SIZE = 900

# Be deliberately polite.
MB_DELAY = 1.2
IMAGE_DELAY = 4.0

TIMEOUT = 45

# Known Navidrome placeholder discovered in the earlier audit.
PLACEHOLDER_HASHES = {
    "f6bc764cfbad7e0a4c6e79cc2edec0e1",
}

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

ARTIST_IMAGES.mkdir(
    parents=True,
    exist_ok=True,
)

session = requests.Session()
session.headers.update(HEADERS)


def musicbrainz_get(url, params=None, attempts=3):
    delays = (2, 5, 10)

    last_error = None

    for attempt in range(attempts):
        try:
            response = session.get(
                url,
                params=params,
                timeout=TIMEOUT,
            )

            if response.status_code in (502, 503, 504):
                wait = delays[min(attempt, len(delays) - 1)]

                print(
                    f"  MusicBrainz temporary error "
                    f"{response.status_code}; retrying in {wait}s..."
                )

                time.sleep(wait)
                last_error = requests.HTTPError(
                    f"{response.status_code} Server Error for url: "
                    f"{response.url}"
                )
                continue

            response.raise_for_status()
            return response

        except requests.RequestException as exc:
            last_error = exc

            if attempt >= attempts - 1:
                break

            wait = delays[min(attempt, len(delays) - 1)]

            print(
                f"  MusicBrainz request error; "
                f"retrying in {wait}s..."
            )

            time.sleep(wait)

    raise last_error or RuntimeError(
        "MusicBrainz request failed"
    )


def md5_file(path):
    digest = hashlib.md5()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def usable_local_image(slug):
    for extension in (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    ):
        path = (
            ARTIST_IMAGES
            / f"{slug}{extension}"
        )

        if not path.exists():
            continue

        if path.stat().st_size <= 0:
            continue

        try:
            if md5_file(path) in PLACEHOLDER_HASHES:
                continue
        except OSError:
            continue

        return path

    return None


def extract_missing_artists():
    rows_source = (
        missing_tracks_engine
        or missing_tracks
    )

    def pick(row, names):
        for name in names:
            value = row.get(name)

            if value:
                return str(value)

        return ""

    groups = {}

    for row in rows_source:
        artist = pick(
            row,
            ["artist", "wf_artist"],
        ).strip()

        track = pick(
            row,
            ["track", "wf_track", "title"],
        ).strip()

        if not artist and not track:
            continue

        key = (
            artist.casefold(),
            track.casefold(),
        )

        groups.setdefault(
            key,
            [],
        ).append(
            {
                "artist": artist,
                "track": track,
            }
        )

    # Match generate_missing_tracks_page.py:
    # highest-frequency missing tracks first,
    # and only the 1,000 groups rendered on missing.html.
    ranked_groups = sorted(
        groups.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    )[:1000]

    artists = {}

    for _key, items in ranked_groups:
        if not items:
            continue

        artist = items[0]["artist"]

        if not artist:
            continue

        cleaned_artist = artist.strip()

        if (
            cleaned_artist.casefold() in {
                "unknown",
                "various artists",
                "various",
                "n/a",
                "na",
            }
            or not any(character.isalnum() for character in cleaned_artist)
        ):
            continue

        slug = artist_slugify(
            cleaned_artist
        )

        if not slug:
            continue

        # Dict insertion order preserves priority from
        # the Missing Tracks ranking.
        artists.setdefault(
            slug,
            artist,
        )

    return artists


def normalized_name(value):
    value = html.unescape(
        str(value or "")
    ).casefold()

    value = value.replace(
        "‐",
        "-",
    )

    value = value.replace(
        "–",
        "-",
    )

    value = re.sub(
        r"[^a-z0-9]+",
        "",
        value,
    )

    return value


def artist_name_candidates(artist):
    original = html.unescape(
        str(artist or "")
    ).strip()

    # Conservative aliases for WEFUNK names that differ from
    # canonical MusicBrainz artist names.
    safe_aliases = {
        "andre ceccarelli": [
            "André Ceccarelli",
        ],
        "bush babees feat. mos def": [
            "Bush Babees",
            "The Bush Babees",
        ],
        "d'angelo & the vanguard": [
            "D'Angelo and the Vanguard",
            "D'Angelo & The Vanguard",
        ],
        "doug e. fresh & the get fresh crew": [
            "Doug E. Fresh and the Get Fresh Crew",
            "Doug E. Fresh & The Get Fresh Crew",
        ],
        "fatback band": [
            "Fatback",
        ],
        "fred wesley & the horny horns": [
            "Fred Wesley and The Horny Horns",
            "Fred Wesley & The Horny Horns",
        ],
        "fred wesley & the j.b.'s": [
            "Fred Wesley & The J.B.'s",
            "Fred Wesley and The J.B.'s",
        ],
        "gabor szabo": [
            "Gábor Szabó",
        ],
        "i.n.i.": [
            "InI",
        ],
        "intelligent hoodlum": [
            "Tragedy Khadafi",
        ],
        "jackson 5": [
            "The Jackson 5",
        ],
        "lowell fulsom": [
            "Lowell Fulson",
        ],
        "show & a.g.": [
            "Showbiz & A.G.",
        ],
        "sugarman three": [
            "The Sugarman 3",
        ],
        "tata vega": [
            "Táta Vega",
        ],
    }

    candidates = []

    def add(value):
        value = re.sub(
            r"\s+",
            " ",
            str(value or ""),
        ).strip()

        if (
            value
            and value.casefold()
            not in {
                item.casefold()
                for item in candidates
            }
        ):
            candidates.append(value)

    add(original)

    for alias in safe_aliases.get(
        original.casefold(),
        [],
    ):
        add(alias)

    # Remove featured-artist suffixes.
    base = re.split(
        r"\s+(?:feat(?:uring)?|ft)\.?\s+",
        original,
        maxsplit=1,
        flags=re.I,
    )[0].strip()

    add(base)

    # Handle parenthetical featured credits.
    base = re.sub(
        r"\s*[\(\[]\s*"
        r"(?:feat(?:uring)?|ft)\.?"
        r".*?[\)\]]\s*$",
        "",
        base,
        flags=re.I,
    ).strip()

    add(base)

    # K.R.S.-One -> KRS-One
    # D.J. Format -> DJ Format
    # E.P.M.D. -> EPMD
    no_periods = base.replace(
        ".",
        "",
    )

    add(no_periods)

    # A punctuation-light search form.
    search_friendly = re.sub(
        r"[^0-9A-Za-z&'’]+",
        " ",
        no_periods,
    )

    add(search_friendly)

    # Ampersand / "and" variants.
    if "&" in base:
        add(
            re.sub(
                r"\s*&\s*",
                " and ",
                base,
            )
        )

    if re.search(
        r"\band\b",
        base,
        flags=re.I,
    ):
        add(
            re.sub(
                r"\band\b",
                "&",
                base,
                flags=re.I,
            )
        )

    # Many catalog names omit a leading "The".
    # Examples:
    #   Isley Brothers -> The Isley Brothers
    #   O'Jays         -> The O'Jays
    #   Meters         -> The Meters
    if (
        base
        and not re.match(
            r"^the\s+",
            base,
            flags=re.I,
        )
    ):
        add(
            f"The {base}"
        )

        if no_periods != base:
            add(
                f"The {no_periods}"
            )

    return candidates


def musicbrainz_search(artist):
    candidates = artist_name_candidates(
        artist
    )

    for candidate_number, candidate in enumerate(
        candidates,
        start=1,
    ):
        response = musicbrainz_get(
            f"{MB_API}/artist",
            params={
                "query": f'artist:"{candidate}"',
                "fmt": "json",
                "limit": 10,
            },
        )

        results = (
            response.json()
            .get("artists", [])
        )

        wanted = normalized_name(
            candidate
        )

        exact = []

        for result in results:
            score = int(
                result.get("score")
                or 0
            )

            candidate_name = normalized_name(
                result.get("name")
            )

            if (
                score >= MIN_MB_SCORE
                and candidate_name == wanted
            ):
                exact.append(
                    result
                )

        if exact:
            match = dict(
                exact[0]
            )

            match[
                "_wefunk_query_name"
            ] = candidate

            return match

        # MusicBrainz asks clients to stay around
        # one request per second.
        if candidate_number < len(
            candidates
        ):
            time.sleep(
                MB_DELAY
            )

    return None


def musicbrainz_artist(mbid):
    response = musicbrainz_get(
        f"{MB_API}/artist/{mbid}",
        params={
            "inc": "url-rels",
            "fmt": "json",
        },
    )

    return response.json()


def commons_filename_from_url(url):
    parsed = urlparse(url)

    marker = "/wiki/File:"

    if marker not in parsed.path:
        return ""

    return unquote(
        parsed.path.split(
            marker,
            1,
        )[1]
    )


def relation_resources(relations):
    for relation in relations:
        resource = str(
            relation.get(
                "url",
                {},
            ).get(
                "resource",
                "",
            )
        ).strip()

        if resource:
            yield relation, resource


def direct_commons_filename(relations):
    for relation, resource in relation_resources(
        relations
    ):
        if (
            relation.get("type") == "image"
            and "commons.wikimedia.org/wiki/File:"
            in resource
        ):
            return commons_filename_from_url(
                resource
            )

    return ""


def wikidata_qid(relations):
    for _relation, resource in relation_resources(
        relations
    ):
        if "wikidata.org/wiki/" in resource:
            return (
                resource
                .rstrip("/")
                .rsplit("/", 1)[-1]
            )

    return ""


def wikipedia_url(relations):
    for relation, resource in relation_resources(
        relations
    ):
        if (
            relation.get("type")
            == "wikipedia"
            and "wikipedia.org/wiki/"
            in resource
        ):
            return resource

    return ""


def wikidata_payload(qid):
    if not qid:
        return {}

    response = session.get(
        WIKIDATA_ENTITY.format(
            qid=qid
        ),
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    return (
        response.json()
        .get("entities", {})
        .get(qid, {})
    )


def wikidata_image_filename(entity):
    claims = (
        entity
        .get("claims", {})
        .get("P18", [])
    )

    for claim in claims:
        try:
            value = (
                claim["mainsnak"]
                ["datavalue"]
                ["value"]
            )
        except (
            KeyError,
            TypeError,
        ):
            continue

        value = str(
            value or ""
        ).strip()

        if value:
            return value

    return ""


def wikidata_wikipedia_url(entity):
    sitelinks = entity.get(
        "sitelinks",
        {},
    )

    english = sitelinks.get(
        "enwiki",
        {},
    )

    title = str(
        english.get("title")
        or ""
    ).strip()

    if not title:
        return ""

    from urllib.parse import quote

    return (
        "https://en.wikipedia.org/wiki/"
        + quote(
            title.replace(
                " ",
                "_",
            )
        )
    )


def wikipedia_page_image(
    wikipedia_resource,
):
    if not wikipedia_resource:
        return ""

    parsed = urlparse(
        wikipedia_resource
    )

    hostname = parsed.hostname or ""

    title = unquote(
        parsed.path
        .split(
            "/wiki/",
            1,
        )[-1]
    )

    if not hostname or not title:
        return ""

    api = (
        f"https://{hostname}/w/api.php"
    )

    response = session.get(
        api,
        params={
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "piprop": "name",
            "titles": title,
        },
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    pages = (
        response.json()
        .get("query", {})
        .get("pages", {})
    )

    for page in pages.values():
        image = str(
            page.get("pageimage")
            or ""
        ).strip()

        if image:
            return image

    return ""


def commons_image_info(filename):
    if not filename:
        return None

    response = session.get(
        COMMONS_API,
        params={
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": (
                "url|extmetadata"
            ),
            "iiurlwidth": IMAGE_SIZE,
            "titles": f"File:{filename}",
        },
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    pages = (
        response.json()
        .get("query", {})
        .get("pages", {})
    )

    for page in pages.values():
        imageinfo = (
            page.get("imageinfo")
            or []
        )

        if not imageinfo:
            continue

        info = imageinfo[0]

        return {
            "url": (
                info.get("thumburl")
                or info.get("url")
                or ""
            ),
            "description_url": (
                info.get(
                    "descriptionurl"
                )
                or ""
            ),
            "metadata": (
                info.get(
                    "extmetadata"
                )
                or {}
            ),
        }

    return None


def metadata_value(
    metadata,
    key,
):
    value = metadata.get(
        key,
        {},
    )

    if isinstance(
        value,
        dict,
    ):
        return str(
            value.get("value")
            or ""
        ).strip()

    return ""


def download_image(
    url,
    destination,
):
    response = session.get(
        url,
        timeout=60,
    )

    if response.status_code == 429:
        return (
            False,
            "",
            "wikimedia-rate-limited",
        )

    response.raise_for_status()

    content_type = (
        response.headers
        .get(
            "Content-Type",
            "",
        )
        .lower()
    )

    if not content_type.startswith(
        "image/"
    ):
        return (
            False,
            "",
            f"not-image:{content_type}",
        )

    try:
        with Image.open(
            BytesIO(
                response.content
            )
        ) as image:
            image.load()

            if (
                image.width < 150
                or image.height < 150
            ):
                return (
                    False,
                    "",
                    (
                        "image-too-small:"
                        f"{image.width}x"
                        f"{image.height}"
                    ),
                )

            if image.mode != "RGB":
                if "A" in image.getbands():
                    background = Image.new(
                        "RGB",
                        image.size,
                        "black",
                    )

                    background.paste(
                        image,
                        mask=image.getchannel(
                            "A"
                        ),
                    )

                    image = background
                else:
                    image = image.convert(
                        "RGB"
                    )

            image.thumbnail(
                (
                    IMAGE_SIZE,
                    IMAGE_SIZE,
                )
            )

            dimensions = (
                f"{image.width}x"
                f"{image.height}"
            )

            image.save(
                destination,
                "JPEG",
                quality=90,
                optimize=True,
                progressive=True,
            )

            return (
                True,
                dimensions,
                "",
            )

    except Exception as exc:
        return (
            False,
            "",
            f"invalid-image:{exc}",
        )


def empty_row(
    artist,
    slug,
):
    return {
        "artist": artist,
        "slug": slug,
        "status": "",
        "message": "",
        "mb_score": "",
        "musicbrainz_name": "",
        "mbid": "",
        "source_method": "",
        "wikidata_qid": "",
        "wikipedia_url": "",
        "commons_filename": "",
        "commons_page": "",
        "license": "",
        "artist_credit": "",
        "dimensions": "",
        "local_path": "",
    }


artists = extract_missing_artists()

RETRY_NO_MATCH_ONLY = (
    __import__("os").environ.get(
        "WEFUNK_ARTIST_IMAGE_RETRY_NO_MATCH",
        "",
    ).strip().lower()
    in {
        "1",
        "true",
        "yes",
        "on",
    }
)

if RETRY_NO_MATCH_ONLY:
    retry_slugs = set()

    if UNRESOLVED_FILE.exists():
        with UNRESOLVED_FILE.open(
            newline="",
            encoding="utf-8",
        ) as handle:
            for retry_row in csv.DictReader(
                handle
            ):
                if (
                    retry_row.get("status")
                    == "no-high-confidence-match"
                ):
                    retry_slug = str(
                        retry_row.get("slug")
                        or ""
                    ).strip()

                    if retry_slug:
                        retry_slugs.add(
                            retry_slug
                        )

    artists = {
        slug: artist
        for slug, artist in artists.items()
        if slug in retry_slugs
    }

TEST_LIMIT = int(
    __import__("os").environ.get(
        "WEFUNK_ARTIST_IMAGE_LIMIT",
        "0",
    )
)

if TEST_LIMIT:
    artists = dict(
        list(
            artists.items()
        )[:TEST_LIMIT]
    )

print(
    f"Artists represented on Missing Tracks page: "
    f"{len(artists):,}"
)

results = []

for number, (
    slug,
    artist,
) in enumerate(
    sorted(
        artists.items(),
        key=lambda item: (
            item[1].casefold()
        ),
    ),
    start=1,
):
    row = empty_row(
        artist,
        slug,
    )

    existing = usable_local_image(
        slug
    )

    if existing:
        row["status"] = "existing"
        row["local_path"] = str(
            existing
        )

        results.append(row)

        print(
            f"[{number}/{len(artists)}] "
            f"existing       {artist}"
        )

        continue

    try:
        match = musicbrainz_search(
            artist
        )

        time.sleep(
            MB_DELAY
        )

        if not match:
            row["status"] = (
                "no-high-confidence-match"
            )

            row["message"] = (
                "No exact MusicBrainz "
                "score-100 name match"
            )

            results.append(row)

            print(
                f"[{number}/{len(artists)}] "
                f"no-match       {artist}"
            )

            continue

        mbid = str(
            match.get("id")
            or ""
        ).strip()

        row["mb_score"] = str(
            match.get("score")
            or ""
        )

        row["musicbrainz_name"] = str(
            match.get("name")
            or ""
        )

        row["mbid"] = mbid

        detail = musicbrainz_artist(
            mbid
        )

        time.sleep(
            MB_DELAY
        )

        relations = detail.get(
            "relations",
            [],
        )

        qid = wikidata_qid(
            relations
        )

        row["wikidata_qid"] = qid

        wiki_url = wikipedia_url(
            relations
        )

        entity = {}

        if qid:
            try:
                entity = wikidata_payload(
                    qid
                )
            except Exception:
                entity = {}

        if (
            not wiki_url
            and entity
        ):
            wiki_url = (
                wikidata_wikipedia_url(
                    entity
                )
            )

        row["wikipedia_url"] = (
            wiki_url
        )

        filename = (
            direct_commons_filename(
                relations
            )
        )

        if filename:
            row["source_method"] = (
                "musicbrainz-image"
            )

        if (
            not filename
            and entity
        ):
            filename = (
                wikidata_image_filename(
                    entity
                )
            )

            if filename:
                row["source_method"] = (
                    "wikidata-p18"
                )

        if (
            not filename
            and wiki_url
        ):
            try:
                filename = (
                    wikipedia_page_image(
                        wiki_url
                    )
                )
            except Exception:
                filename = ""

            if filename:
                row["source_method"] = (
                    "wikipedia-pageimage"
                )

        if not filename:
            row["status"] = "no-image"
            row["message"] = (
                "No Commons image through "
                "MusicBrainz, Wikidata or Wikipedia"
            )

            results.append(row)

            print(
                f"[{number}/{len(artists)}] "
                f"no-image       {artist}"
            )

            continue

        row["commons_filename"] = (
            filename
        )

        try:
            info = commons_image_info(
                filename
            )
        except Exception as exc:
            row["status"] = (
                "commons-metadata-error"
            )

            row["message"] = str(
                exc
            )

            results.append(row)

            print(
                f"[{number}/{len(artists)}] "
                f"metadata-error {artist}"
            )

            continue

        if (
            not info
            or not info.get("url")
        ):
            row["status"] = (
                "commons-image-unresolved"
            )

            results.append(row)

            print(
                f"[{number}/{len(artists)}] "
                f"unresolved     {artist}"
            )

            continue

        metadata = info[
            "metadata"
        ]

        row["commons_page"] = (
            info["description_url"]
        )

        row["license"] = (
            metadata_value(
                metadata,
                "LicenseShortName",
            )
            or metadata_value(
                metadata,
                "UsageTerms",
            )
        )

        row["artist_credit"] = (
            metadata_value(
                metadata,
                "Artist",
            )
            or metadata_value(
                metadata,
                "Credit",
            )
        )

        destination = (
            ARTIST_IMAGES
            / f"{slug}.jpg"
        )

        success, dimensions, message = (
            download_image(
                info["url"],
                destination,
            )
        )

        if success:
            row["status"] = (
                "downloaded"
            )

            row["dimensions"] = (
                dimensions
            )

            row["local_path"] = str(
                destination
            )

            print(
                f"[{number}/{len(artists)}] "
                f"downloaded     {artist}"
            )

        else:
            row["status"] = message
            row["message"] = message

            print(
                f"[{number}/{len(artists)}] "
                f"{message:<14} {artist}"
            )

        # Don't repeatedly hammer the image CDN.
        time.sleep(
            IMAGE_DELAY
        )

    except requests.HTTPError as exc:
        row["status"] = "http-error"
        row["message"] = str(
            exc
        )

        results.append(row)

        print(
            f"[{number}/{len(artists)}] "
            f"http-error      {artist}"
        )

        continue

    except Exception as exc:
        row["status"] = "error"
        row["message"] = str(
            exc
        )

        results.append(row)

        print(
            f"[{number}/{len(artists)}] "
            f"error           {artist}"
        )

        continue

    results.append(row)


fields = list(
    empty_row(
        "",
        "",
    ).keys()
)


with RESULTS_FILE.open(
    "w",
    newline="",
    encoding="utf-8",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=fields,
    )

    writer.writeheader()
    writer.writerows(
        results
    )


unresolved = [
    row
    for row in results
    if row["status"]
    not in (
        "existing",
        "downloaded",
    )
]

with UNRESOLVED_FILE.open(
    "w",
    newline="",
    encoding="utf-8",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=fields,
    )

    writer.writeheader()
    writer.writerows(
        unresolved
    )


attribution = [
    row
    for row in results
    if row["status"] == "downloaded"
]

with ATTRIBUTION_FILE.open(
    "w",
    newline="",
    encoding="utf-8",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=fields,
    )

    writer.writeheader()
    writer.writerows(
        attribution
    )


counts = {}

for row in results:
    status = row["status"]

    counts[status] = (
        counts.get(
            status,
            0,
        )
        + 1
    )


print()
print("=" * 60)
print("MusicBrainz artist-image enrichment complete")
print("=" * 60)

for status, count in sorted(
    counts.items()
):
    print(
        f"{status:28} "
        f"{count:5,}"
    )

print()
print(
    f"Results:     {RESULTS_FILE}"
)
print(
    f"Unresolved:  {UNRESOLVED_FILE}"
)
print(
    f"Attribution: {ATTRIBUTION_FILE}"
)
