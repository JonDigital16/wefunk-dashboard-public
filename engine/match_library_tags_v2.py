from engine.profiler import timer, print_summary
from collections import defaultdict
import argparse
import csv
import os
from pathlib import Path
import re
from engine.library_index import sync_library_index

from engine.database import (
    clear_track_matches,
    ensure_library_index_table,
    ensure_track_matches_table,
    load_cached_track_matches,
    load_current_results,
    load_library_index_rows,
    load_tracks_with_ids,
    open_database,
    prune_orphaned_track_matches,
    rebuild_legacy_matches_table,
    upsert_track_matches,
)
from engine.matcher import build_match_index, is_match, match_track

DB_FILE = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "db" / 'wefunk.db'
MUSIC_DIR = Path(os.environ.get("WEFUNK_MUSIC_DIR", Path.home() / "Music")).expanduser().resolve()
EXPORT_DIR = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve()
PLAYLIST_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "playlists"

# Change this whenever matching rules or normalization behavior changes.
MATCHER_VERSION = "tags-v2.3"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Match WEFUNK tracks against local music tags."
    )
    parser.add_argument(
        "--full-rebuild",
        action="store_true",
        help="Discard persistent match results and rematch every track.",
    )
    return parser.parse_args()


def clean(value):
    value = str(value or "").lower()
    value = re.sub(r"\(.*?\)|\[.*?\]", "", value)
    value = re.sub(r"\b(feat|ft|featuring)\b.*", "", value)
    value = re.sub(r"^the\s+", "", value)
    value = value.replace("&", "and")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def build_library(conn):
    """Build matcher structures from the persistent SQLite library index."""

    print("Loading music library from persistent index...")

    ensure_library_index_table(conn)
    cached_rows = load_library_index_rows(conn)

    if not cached_rows:
        raise RuntimeError(
            "The persistent library_index table is empty. "
            "Run: python -m engine.sync_library_index"
        )

    library = []
    library_by_artist = defaultdict(list)

    for row in cached_rows:
        item = {
            "path": row["file_path"],
            "artist": row["artist"],
            "title": row["title"],
            "artist_c": row["artist_norm"],
            "title_c": row["title_norm"],
            "combined_c": row["combined_norm"],
        }

        # Candidates with an empty normalized artist or title contain no
        # reliable text for fuzzy matching. Keep them in the persistent
        # library index, but exclude them from matcher candidate collections.
        if not item["artist_c"] or not item["title_c"]:
            continue

        library.append(item)
        library_by_artist[item["artist_c"]].append(item)

    print(f"Loaded {len(library):,} indexed tracks")
    print(f"Loaded {len(library_by_artist):,} indexed artists")

    return library, library_by_artist


def export_results(results):
    owned_csv = EXPORT_DIR / "wefunk_owned_tracks_tags.csv"
    missing_csv = EXPORT_DIR / "wefunk_missing_tracks_tags.csv"
    playlist_file = PLAYLIST_DIR / "WEFUNK_owned_tracks_tags.m3u"

    matched = [row for row in results if row["matched"]]
    missing = [row for row in results if not row["matched"]]

    with owned_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "show_id",
                "artist",
                "track",
                "file_path",
                "score",
            ]
        )

        for row in matched:
            writer.writerow(
                [
                    row["show_id"],
                    row["artist"],
                    row["track"],
                    row["library_file_path"],
                    row["score"],
                ]
            )

    with missing_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "show_id",
                "artist",
                "track",
                "best_score",
            ],
        )
        writer.writeheader()

        for row in missing:
            writer.writerow(
                {
                    "show_id": row["show_id"],
                    "artist": row["artist"],
                    "track": row["track"],
                    "best_score": row["score"],
                }
            )

    with playlist_file.open("w", encoding="utf-8") as file:
        file.write("#EXTM3U\n")

        seen = set()

        for row in matched:
            file_path = row["library_file_path"]

            if not file_path or file_path in seen:
                continue

            file.write(f"{file_path}\n")
            seen.add(file_path)

    return (
        owned_csv,
        missing_csv,
        playlist_file,
        len(matched),
        len(missing),
    )


def make_persistent_row(
    track_id,
    show_id,
    artist,
    track,
    artist_norm,
    track_norm,
    matched,
    library_file_path,
    best_candidate_path,
    score,
):
    return (
        track_id,
        str(show_id or ""),
        str(artist or ""),
        str(track or ""),
        artist_norm,
        track_norm,
        int(bool(matched)),
        library_file_path,
        best_candidate_path,
        int(score) if score is not None else None,
        MATCHER_VERSION,
    )


def main():
    args = parse_args()

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    conn = open_database(DB_FILE)

    try:
        ensure_track_matches_table(conn)

        if args.full_rebuild:
            print("Full rebuild requested. Clearing persistent match cache...")
            clear_track_matches(conn)

        removed = prune_orphaned_track_matches(conn)

        if removed:
            print(f"Removed {removed:,} orphaned cached results")

        tracks = load_tracks_with_ids(conn)
        cached_rows = load_cached_track_matches(
            conn,
            MATCHER_VERSION,
        )

        cache_by_id = {row["wefunk_track_id"]: row for row in cached_rows}

        # This fallback preserves cache usefulness even if imported track IDs
        # are regenerated while artist/title values remain unchanged.
        cache_by_signature = {}

        for row in cached_rows:
            key = (row["artist_norm"], row["track_norm"])
            cache_by_signature.setdefault(key, row)

        pending = []
        cached_count = 0
        invalid_count = 0
        migrated_cache_rows = []

        for track_id, show_id, artist, track in tracks:
            artist_norm = clean(artist)
            track_norm = clean(track)

            if not artist_norm or not track_norm:
                invalid_count += 1
                continue

            cached = cache_by_id.get(track_id)

            if cached is not None:
                same_source = (
                    cached["artist_norm"] == artist_norm
                    and cached["track_norm"] == track_norm
                )

                if same_source:
                    cached_count += 1
                    continue

            signature = (artist_norm, track_norm)
            signature_cached = cache_by_signature.get(signature)

            if signature_cached is not None:
                migrated_cache_rows.append(
                    make_persistent_row(
                        track_id=track_id,
                        show_id=show_id,
                        artist=artist,
                        track=track,
                        artist_norm=artist_norm,
                        track_norm=track_norm,
                        matched=signature_cached["matched"],
                        library_file_path=signature_cached["library_file_path"],
                        best_candidate_path=signature_cached["best_candidate_path"],
                        score=signature_cached["score"],
                    )
                )
                cached_count += 1
                continue

            pending.append(
                (
                    track_id,
                    show_id,
                    artist,
                    track,
                    artist_norm,
                    track_norm,
                )
            )

        if migrated_cache_rows:
            upsert_track_matches(conn, migrated_cache_rows)

        print(f"Loaded {len(tracks):,} WEFUNK track entries")
        print(f"Cached results reused: {cached_count:,}")
        print(f"Tracks requiring matching: {len(pending):,}")
        print(f"Skipped invalid tracks: {invalid_count:,}")

        with timer("Sync music library"):
            summary = sync_library_index(
                conn,
                MUSIC_DIR,
                full_rebuild=False,
            )

        print(
            f"Library sync: "
            f"{summary['reused']:,} reused, "
            f"{summary['written']:,} written, "
            f"{summary['deleted']:,} deleted"
        )
        if pending:
            with timer("Build music library"):
                library, library_by_artist = build_library(conn)

            if not library:
                raise RuntimeError(
                    "The persistent library index is empty. "
                    "Run: python -m engine.sync_library_index"
                )

            print("Building vectorized match index...")

            with timer("Build vector index"):
                match_index = build_match_index(library)

            print("Matching uncached WEFUNK tracks against the music library...")

            result_rows = []
            runtime_cache = {}
            runtime_cache_hits = 0
            unique_searches = 0
            newly_matched = 0
            newly_missing = 0

            with timer("Track matching"):
                for index, (
                    track_id,
                    show_id,
                    artist,
                    track,
                    artist_norm,
                    track_norm,
                ) in enumerate(pending, start=1):
                    signature = (artist_norm, track_norm)

                    if signature in runtime_cache:
                        best, best_score = runtime_cache[signature]
                        runtime_cache_hits += 1
                    else:
                        best, best_score = match_track(
                            artist,
                            track,
                            library,
                            library_by_artist,
                            match_index,
                        )
                        runtime_cache[signature] = (best, best_score)
                        unique_searches += 1

                    accepted = is_match(best, best_score)
                    best_path = best["path"] if best else None
                    library_path = best_path if accepted else None

                    if accepted:
                        newly_matched += 1
                    else:
                        newly_missing += 1

                    result_rows.append(
                        make_persistent_row(
                            track_id=track_id,
                            show_id=show_id,
                            artist=artist,
                            track=track,
                            artist_norm=artist_norm,
                            track_norm=track_norm,
                            matched=accepted,
                            library_file_path=library_path,
                            best_candidate_path=best_path,
                            score=best_score,
                        )
                    )

                    if index % 1000 == 0 or index == len(pending):
                        print(
                            f"Processed {index:,} of {len(pending):,} "
                            f"uncached tracks — matched "
                            f"{newly_matched:,}"
                        )

            with timer("Database write"):
                upsert_track_matches(conn, result_rows)

            print()
            print(f"Newly matched: {newly_matched:,}")
            print(f"Newly unmatched: {newly_missing:,}")
            print(f"Unique match searches: {unique_searches:,}")
            print(f"Runtime duplicate reuses: {runtime_cache_hits:,}")
        else:
            print("No uncached tracks require matching.")

        with timer("Database write"):
            rebuild_legacy_matches_table(
                conn,
                MATCHER_VERSION,
            )

        current_results = load_current_results(
            conn,
            MATCHER_VERSION,
        )

        with timer("Export CSV/Playlist"):
            (
                owned_csv,
                missing_csv,
                playlist_file,
                matched_count,
                missing_count,
            ) = export_results(current_results)

    finally:
        conn.close()

    print()
    print("Matching complete")
    print(f"Persistent results: {len(current_results):,}")
    print(f"Matched tracks: {matched_count:,}")
    print(f"Missing tracks: {missing_count:,}")
    print(f"Skipped invalid tracks: {invalid_count:,}")
    print(f"Owned tracks CSV: {owned_csv}")
    print(f"Missing tracks CSV: {missing_csv}")
    print(f"Playlist created: {playlist_file}")
    print(f"Matcher version: {MATCHER_VERSION}")
    print_summary()


if __name__ == "__main__":
    main()
