#!/usr/bin/env python3

import os
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", "/Users/jonathan/scripts/wefunk-dashboard/site"))

required_files = [
    "index.html",
    "episodes.html",
    "recent-matches.html",
    "missing.html",
    "shopping.html",
    "recommended-albums.html",
    "albums.html",
    "top-missing-artists.html",
    "best-matching.html",
    "almost-complete.html",
    "dna.html",
    "genres.html",
    "years.html",
    "search.html",
    "search-index.json",
    "now-playing.json",
    "favicon.svg",
    "favicon.png",
    "apple-touch-icon.png",
    "data/search_index.json",
]

missing = []

for file in required_files:
    path = SITE / file
    if not path.exists() or path.stat().st_size == 0:
        missing.append(file)

show_pages = list((SITE / "shows").glob("*.html")) if (SITE / "shows").exists() else []
artist_pages = list((SITE / "artists").glob("*.html")) if (SITE / "artists").exists() else []
genre_pages = list((SITE / "genres").glob("*.html")) if (SITE / "genres").exists() else []
album_pages = list((SITE / "albums").glob("*.html")) if (SITE / "albums").exists() else []
year_pages = list((SITE / "years").glob("*.html")) if (SITE / "years").exists() else []
episode_art_pages = list((SITE / "episode-art").glob("*.jpg")) if (SITE / "episode-art").exists() else []

if len(show_pages) < 1000:
    missing.append(f"shows/*.html only has {len(show_pages)} files")

if len(artist_pages) < 1000:
    missing.append(f"artists/*.html only has {len(artist_pages)} files")

if len(genre_pages) < 1:
    missing.append("genres/*.html has no files")

if len(album_pages) < 100:
    missing.append(f"albums/*.html only has {len(album_pages)} files")

if len(year_pages) < 10:
    missing.append(f"years/*.html only has {len(year_pages)} files")

if len(episode_art_pages) < 100:
    missing.append(f"episode-art/*.jpg only has {len(episode_art_pages)} files")


ui_checks = {
    "index.html": ["site-nav", "searchOverlay", "site-footer"],
    "episodes.html": ["site-nav", "searchOverlay", "site-footer"],
    "albums.html": ["site-nav", "searchOverlay", "site-footer"],
    "search.html": ["site-nav", "searchOverlay", "site-footer"],
}

for file, markers in ui_checks.items():
    path = SITE / file
    if path.exists():
        html = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in html:
                missing.append(f"{file} missing UI marker: {marker}")



# ------------------------------------------------------------------
# HTML STRUCTURE / PAGE IDENTITY VALIDATION
# ------------------------------------------------------------------

page_title_checks = {
    "shopping.html": "Smart Shopping List",
    "recommended-albums.html": "Recommended Albums",
    "albums.html": "Album Index",
    "artists.html": "Artist Index",
}

for file, expected_title in page_title_checks.items():
    path = SITE / file

    if not path.exists():
        continue

    html = path.read_text(encoding="utf-8")

    expected_title_tag = f"<title>{expected_title}</title>"

    if expected_title_tag not in html:
        missing.append(
            f"{file} has incorrect page title; expected {expected_title!r}"
        )

    if html.count("<body") != 1 or html.count("</body>") != 1:
        missing.append(
            f"{file} has invalid body structure "
            f"({html.count('<body')}/{html.count('</body>')})"
        )

    if html.count("<main") != 1 or html.count("</main>") != 1:
        missing.append(
            f"{file} has invalid main structure "
            f"({html.count('<main')}/{html.count('</main>')})"
        )


# These pages must never inherit the Smart Shopping List body.
for file in (
    "recommended-albums.html",
    "albums.html",
    "artists.html",
):
    path = SITE / file

    if path.exists():
        html = path.read_text(encoding="utf-8")

        if "<h2>Smart Shopping List</h2>" in html:
            missing.append(
                f"{file} contains Smart Shopping List page content"
            )


# Validate every generated individual album page.
for path in album_pages:
    html = path.read_text(encoding="utf-8")

    if "<h2>Smart Shopping List</h2>" in html:
        missing.append(
            f"albums/{path.name} contains Smart Shopping List page content"
        )

    if html.count("<body") != 1 or html.count("</body>") != 1:
        missing.append(
            f"albums/{path.name} has invalid body structure"
        )

    if html.count("<main") != 1 or html.count("</main>") != 1:
        missing.append(
            f"albums/{path.name} has invalid main structure"
        )



favicon_path = SITE / "index.html"
if favicon_path.exists():
    html = favicon_path.read_text(encoding="utf-8")
    if 'href="/favicon.svg"' not in html:
        missing.append("favicon.svg missing rel icon on index.html")



icon_html = SITE / "index.html"
if icon_html.exists():
    html = icon_html.read_text(encoding="utf-8")
    if 'href="/favicon.png"' not in html:
        missing.append("favicon.png missing rel icon on index.html")
    if 'href="/apple-touch-icon.png"' not in html:
        missing.append("apple-touch-icon missing on index.html")



album_index_page = SITE / "albums.html"
if album_index_page.exists():
    html = album_index_page.read_text(encoding="utf-8")
    if "album-card-grid" not in html:
        missing.append("albums.html missing album card grid")
    if "showAlbumTable" not in html:
        missing.append("albums.html missing card/table toggle")



recommended_page = SITE / "recommended-albums.html"
if recommended_page.exists():
    html = recommended_page.read_text(encoding="utf-8")
    if "recommended-card-grid" not in html:
        missing.append("recommended-albums.html missing card grid")
    if "showRecommendedTable" not in html:
        missing.append("recommended-albums.html missing card/table toggle")



episodes_page = SITE / "episodes.html"
if episodes_page.exists():
    html = episodes_page.read_text(encoding="utf-8")
    if "episode-card-grid" not in html:
        missing.append("episodes.html missing episode card grid")
    if "showEpisodeTable" not in html:
        missing.append("episodes.html missing card/table toggle")



homepage = SITE / "index.html"
if homepage.exists():
    html = homepage.read_text(encoding="utf-8")
    if "now-playing-card" not in html:
        missing.append("index.html missing Now Playing card")



homepage = SITE / "index.html"
if homepage.exists():
    html = homepage.read_text(encoding="utf-8")
    if "liveNowPlayingCard" not in html:
        missing.append("index.html missing live Now Playing card")
    if "loadNowPlaying" not in html:
        missing.append("index.html missing live Now Playing script")
    if "/now-playing.json" not in html:
        missing.append("index.html missing now-playing.json fetch")



# Dashboard v2 homepage validation
homepage_v2 = SITE / "index.html"

if homepage_v2.exists():
    homepage_html = homepage_v2.read_text(encoding="utf-8")

    homepage_sections = [
        ("liveNowPlayingCard", "Now Playing"),
        ("collectionOverview", "Collection Overview"),
        ("homepageRecentMatches", "Latest WEFUNK Matches"),
        ("homepageCollectionGoals", "Collection Goals"),
        ("homepageTopGenres", "Top Genres"),
        ("homepageTopArtists", "Top Artists"),
        ("homepageTopAlbums", "Top Albums"),
    ]

    section_positions = []

    for section_id, section_name in homepage_sections:
        position = homepage_html.find(f'id="{section_id}"')

        if position == -1:
            missing.append(
                f"index.html missing homepage section: {section_name}"
            )
        else:
            section_positions.append(
                (position, section_name)
            )

    if len(section_positions) == len(homepage_sections):
        actual_order = [
            name
            for _, name in sorted(section_positions)
        ]

        expected_order = [
            name
            for _, name in homepage_sections
        ]

        if actual_order != expected_order:
            missing.append(
                "index.html homepage section order is incorrect: "
                + " → ".join(actual_order)
            )

    if "homepage-album-row" not in homepage_html:
        missing.append(
            "index.html missing compact Top Album rows"
        )


if missing:
    print("❌ Site validation failed:")
    for item in missing:
        print(f"  - {item}")
    raise SystemExit(1)

print("✅ Site validation passed")
print(f"  Show pages: {len(show_pages)}")
print(f"  Artist pages: {len(artist_pages)}")
print(f"  Genre pages: {len(genre_pages)}")
print(f"  Album pages: {len(album_pages)}")
print(f"  Year pages: {len(year_pages)}")
print(f"  Episode art: {len(episode_art_pages)}")
