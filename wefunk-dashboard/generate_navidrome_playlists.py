#!/usr/bin/env python3

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

try:
    from mutagen import File as MutagenFile
except ImportError:
    raise SystemExit(
        "Mutagen is required. Run this script from the WEFUNK virtual environment."
    )


GENRE_MIN_TRACKS = 5
ARTIST_MIN_TRACKS = 5
FAVORITES_MIN_PLAYS = 2
HEAVY_ROTATION_MIN_EPISODES = 5
EPISODE_RANGE_SIZE = 100


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def atomic_write_json(path: Path, data) -> None:
    text = json.dumps(
        data,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"
    atomic_write_text(path, text)


def clean_filename(value: str) -> str:
    value = str(value or "").strip()
    value = value.replace("/", " - ")
    value = value.replace("\\", " - ")
    value = value.replace(":", " - ")
    value = re.sub(r'[\x00-\x1f<>:"|?*]', "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or "Unknown"


def normalize_text(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip().lower(),
    )


def split_genres(values):
    genres = []

    for value in values or []:
        for part in re.split(r"[;/]", str(value)):
            part = part.strip()
            if part:
                genres.append(part)

    return genres


def read_audio_metadata(path: Path, fallback_artist="", fallback_title=""):
    artist = fallback_artist
    title = fallback_title
    genres = []

    try:
        audio = MutagenFile(path, easy=True)

        if audio is None:
            return {
                "artist": artist,
                "title": title,
                "genres": genres,
                "tag_error": "Mutagen returned None",
            }

        artist_values = audio.get("artist", [])
        title_values = audio.get("title", [])
        genre_values = audio.get("genre", [])

        if artist_values:
            artist = str(artist_values[0]).strip() or artist

        if title_values:
            title = str(title_values[0]).strip() or title

        genres = split_genres(genre_values)

        return {
            "artist": artist,
            "title": title,
            "genres": genres,
            "tag_error": None,
        }

    except Exception as exc:
        return {
            "artist": artist,
            "title": title,
            "genres": genres,
            "tag_error": f"{type(exc).__name__}: {exc}",
        }


def open_database(path: Path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def load_matches(connection):
    rows = connection.execute(
        """
        SELECT
            tm.library_file_path,
            tm.show_id,
            tm.artist,
            tm.track,
            tm.artist_norm,
            tm.track_norm
        FROM track_matches AS tm
        WHERE tm.matched = 1
          AND tm.library_file_path IS NOT NULL
          AND TRIM(tm.library_file_path) != ''
        ORDER BY
            tm.library_file_path,
            tm.show_id
        """
    ).fetchall()

    grouped = {}

    for row in rows:
        raw_path = row["library_file_path"]

        if raw_path not in grouped:
            grouped[raw_path] = {
                "path": Path(raw_path),
                "shows": set(),
                "db_artists": [],
                "db_tracks": [],
                "norm_pairs": set(),
            }

        item = grouped[raw_path]

        if row["show_id"] is not None:
            item["shows"].add(str(row["show_id"]))

        if row["artist"]:
            item["db_artists"].append(str(row["artist"]))

        if row["track"]:
            item["db_tracks"].append(str(row["track"]))

        if row["artist_norm"] and row["track_norm"]:
            item["norm_pairs"].add(
                (
                    str(row["artist_norm"]),
                    str(row["track_norm"]),
                )
            )

    return grouped


def load_favorite_counts(connection):
    rows = connection.execute(
        """
        SELECT
            tm.library_file_path,
            COUNT(DISTINCT lp.id) AS play_count
        FROM listening_plays AS lp

        INNER JOIN listening_play_tracks AS lpt
            ON lpt.play_id = lp.id

        INNER JOIN track_matches AS tm
            ON tm.wefunk_track_id = lpt.wefunk_track_id

        WHERE tm.matched = 1
          AND tm.library_file_path IS NOT NULL

        GROUP BY tm.library_file_path
        """
    ).fetchall()

    return {
        str(row["library_file_path"]): int(row["play_count"])
        for row in rows
    }


def choose_fallback(values):
    for value in values:
        value = str(value or "").strip()
        if value:
            return value
    return ""


def prepare_tracks(connection, music_root: Path):
    grouped = load_matches(connection)
    favorite_counts = load_favorite_counts(connection)

    tracks = []
    stale = []
    tag_errors = []
    no_genre = []

    for raw_path, item in grouped.items():
        path = item["path"]

        if not path.is_file():
            stale.append(path)
            continue

        try:
            relative = path.relative_to(music_root)
        except ValueError:
            stale.append(path)
            continue

        fallback_artist = choose_fallback(item["db_artists"])
        fallback_title = choose_fallback(item["db_tracks"])

        metadata = read_audio_metadata(
            path,
            fallback_artist=fallback_artist,
            fallback_title=fallback_title,
        )

        if metadata["tag_error"]:
            tag_errors.append(
                (
                    path,
                    metadata["tag_error"],
                )
            )

        if not metadata["genres"]:
            no_genre.append(path)

        numeric_shows = set()

        for show in item["shows"]:
            try:
                numeric_shows.add(int(show))
            except (TypeError, ValueError):
                pass

        tracks.append(
            {
                "host_path": path,
                "relative_path": relative,
                "artist": metadata["artist"] or fallback_artist or "Unknown Artist",
                "title": metadata["title"] or fallback_title or path.stem,
                "genres": metadata["genres"],
                "shows": item["shows"],
                "numeric_shows": numeric_shows,
                "episode_count": len(item["shows"]),
                "favorite_plays": favorite_counts.get(raw_path, 0),
            }
        )

    return tracks, stale, tag_errors, no_genre


def sort_alpha(track):
    return (
        normalize_text(track["artist"]),
        normalize_text(track["title"]),
        str(track["relative_path"]).lower(),
    )


def container_path(track, navidrome_root: str):
    root = navidrome_root.rstrip("/")
    return f"{root}/{track['relative_path'].as_posix()}"


def playlist_text(tracks, navidrome_root: str):
    lines = ["#EXTM3U"]

    for track in tracks:
        lines.append(
            container_path(
                track,
                navidrome_root,
            )
        )

    return "\n".join(lines) + "\n"


def load_state(path: Path):
    if not path.exists():
        return {
            "version": 1,
            "initialized_at": None,
            "first_seen": {},
            "manifest": {
                "genres": [],
                "artists": [],
                "episode_ranges": [],
            },
        }

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(
            f"Could not read playlist state file {path}: {exc}"
        )

    data.setdefault("version", 1)
    data.setdefault("initialized_at", None)
    data.setdefault("first_seen", {})
    data.setdefault(
        "manifest",
        {
            "genres": [],
            "artists": [],
            "episode_ranges": [],
        },
    )

    data["manifest"].setdefault("genres", [])
    data["manifest"].setdefault("artists", [])
    data["manifest"].setdefault("episode_ranges", [])

    return data


def current_dynamic_groups(tracks):
    genres = defaultdict(list)
    artists = defaultdict(list)
    episode_ranges = defaultdict(list)

    for track in tracks:
        for genre in track["genres"]:
            genres[genre].append(track)

        artists[track["artist"]].append(track)

        ranges_seen = set()

        for show_id in track["numeric_shows"]:
            start = (show_id // EPISODE_RANGE_SIZE) * EPISODE_RANGE_SIZE

            if start in ranges_seen:
                continue

            ranges_seen.add(start)
            episode_ranges[start].append(track)

    eligible_genres = {
        name: items
        for name, items in genres.items()
        if len(items) >= GENRE_MIN_TRACKS
    }

    eligible_artists = {
        name: items
        for name, items in artists.items()
        if len(items) >= ARTIST_MIN_TRACKS
    }

    eligible_ranges = {
        start: items
        for start, items in episode_ranges.items()
        if items
    }

    return (
        eligible_genres,
        eligible_artists,
        eligible_ranges,
    )


def update_first_seen(state, tracks, now):
    first_seen = state["first_seen"]

    for track in tracks:
        key = track["relative_path"].as_posix()

        if key not in first_seen:
            first_seen[key] = now


def initialize_or_expand_manifest(
    state,
    eligible_genres,
    eligible_artists,
    eligible_ranges,
    expand=False,
):
    manifest = state["manifest"]

    current_genres = set(manifest["genres"])
    current_artists = set(manifest["artists"])
    current_ranges = {
        int(value)
        for value in manifest["episode_ranges"]
    }

    if state["initialized_at"] is None or expand:
        current_genres.update(eligible_genres.keys())
        current_artists.update(eligible_artists.keys())
        current_ranges.update(eligible_ranges.keys())

    manifest["genres"] = sorted(
        current_genres,
        key=normalize_text,
    )

    manifest["artists"] = sorted(
        current_artists,
        key=normalize_text,
    )

    manifest["episode_ranges"] = sorted(current_ranges)


def build_playlists(
    tracks,
    state,
    eligible_genres,
    eligible_artists,
    eligible_ranges,
    now,
):
    playlists = {}

    playlists["WEFUNK - All Matches"] = sorted(
        tracks,
        key=sort_alpha,
    )

    playlists["WEFUNK - Most Played on WEFUNK"] = sorted(
        tracks,
        key=lambda track: (
            -track["episode_count"],
            *sort_alpha(track),
        ),
    )

    playlists["WEFUNK - Deep Cuts"] = sorted(
        [
            track
            for track in tracks
            if track["episode_count"] == 1
        ],
        key=sort_alpha,
    )

    playlists["WEFUNK - Heavy Rotation"] = sorted(
        [
            track
            for track in tracks
            if track["episode_count"] >= HEAVY_ROTATION_MIN_EPISODES
        ],
        key=lambda track: (
            -track["episode_count"],
            *sort_alpha(track),
        ),
    )

    playlists["WEFUNK - Favorites"] = sorted(
        [
            track
            for track in tracks
            if track["favorite_plays"] >= FAVORITES_MIN_PLAYS
        ],
        key=lambda track: (
            -track["favorite_plays"],
            -track["episode_count"],
            *sort_alpha(track),
        ),
    )

    for days in (30, 90):
        cutoff = now - (days * 86400)

        recent = [
            track
            for track in tracks
            if int(
                state["first_seen"].get(
                    track["relative_path"].as_posix(),
                    now,
                )
            ) >= cutoff
        ]

        playlists[
            f"WEFUNK - Recently Discovered - {days} Days"
        ] = sorted(
            recent,
            key=lambda track: (
                -int(
                    state["first_seen"].get(
                        track["relative_path"].as_posix(),
                        now,
                    )
                ),
                *sort_alpha(track),
            ),
        )

    for genre in state["manifest"]["genres"]:
        items = eligible_genres.get(genre, [])

        playlists[
            f"WEFUNK - {genre}"
        ] = sorted(
            items,
            key=sort_alpha,
        )

    for artist in state["manifest"]["artists"]:
        items = eligible_artists.get(artist, [])

        playlists[
            f"WEFUNK - Artist - {artist}"
        ] = sorted(
            items,
            key=lambda track: (
                normalize_text(track["title"]),
                str(track["relative_path"]).lower(),
            ),
        )

    for start in state["manifest"]["episode_ranges"]:
        start = int(start)
        end = start + EPISODE_RANGE_SIZE - 1
        items = eligible_ranges.get(start, [])

        playlists[
            f"WEFUNK - Episodes {start:04d}-{end:04d}"
        ] = sorted(
            items,
            key=sort_alpha,
        )

    return playlists


def playlist_file_name(name):
    return clean_filename(name) + ".m3u8"


def detect_filename_collisions(playlists):
    by_filename = defaultdict(list)

    for name in playlists:
        by_filename[playlist_file_name(name)].append(name)

    collisions = {
        filename: names
        for filename, names in by_filename.items()
        if len(names) > 1
    }

    if collisions:
        print("ERROR: Playlist filename collisions detected:")

        for filename, names in collisions.items():
            print(f"  {filename}")
            for name in names:
                print(f"    - {name}")

        raise SystemExit(1)


def print_summary(
    tracks,
    stale,
    tag_errors,
    no_genre,
    playlists,
    state,
    state_exists,
    expand,
):
    print("===== WEFUNK NAVIDROME PLAYLISTS =====")
    print()
    print(f"Valid matched files:        {len(tracks)}")
    print(f"Stale DB paths skipped:     {len(stale)}")
    print(f"Audio tag read warnings:    {len(tag_errors)}")
    print(f"Files without genre:        {len(no_genre)}")
    print()

    if not state_exists:
        print("Manifest:                   would initialize")
    elif expand:
        print("Manifest:                   expand requested")
    else:
        print("Manifest:                   existing canonical set")

    print(
        f"Genre playlists:            "
        f"{len(state['manifest']['genres'])}"
    )
    print(
        f"Artist playlists:           "
        f"{len(state['manifest']['artists'])}"
    )
    print(
        f"Episode range playlists:    "
        f"{len(state['manifest']['episode_ranges'])}"
    )

    print()
    print("===== PLAYLIST COUNTS =====")

    for name in sorted(playlists, key=normalize_text):
        print(f"{len(playlists[name]):>5}  {name}")

    if stale:
        print()
        print("===== FIRST 10 STALE DB PATHS =====")

        for path in stale[:10]:
            print(path)

    if tag_errors:
        print()
        print("===== FIRST 10 TAG WARNINGS =====")

        for path, error in tag_errors[:10]:
            print(path)
            print(f"  {error}")


def apply_playlists(
    playlists,
    playlist_dir: Path,
    navidrome_root: str,
):
    playlist_dir.mkdir(parents=True, exist_ok=True)

    written = set()

    for name, tracks in playlists.items():
        filename = playlist_file_name(name)
        destination = playlist_dir / filename

        atomic_write_text(
            destination,
            playlist_text(
                tracks,
                navidrome_root,
            ),
        )

        written.add(filename)

    return written


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate canonical WEFUNK playlists for Navidrome."
        )
    )

    default_data_root = Path(
        os.environ.get(
            "WEFUNK_DATA_DIR",
            Path.home() / ".local" / "share" / "wefunk",
        )
    ).expanduser()

    default_music_root = Path(
        os.environ.get(
            "WEFUNK_MUSIC_DIR",
            Path.home() / "Music",
        )
    ).expanduser()

    parser.add_argument(
        "--db",
        type=Path,
        default=Path(
            os.environ.get(
                "WEFUNK_DB_FILE",
                default_data_root / "db" / "wefunk.db",
            )
        ),
    )

    parser.add_argument(
        "--music-root",
        type=Path,
        default=default_music_root,
    )

    parser.add_argument(
        "--playlist-dir",
        type=Path,
        default=None,
    )

    parser.add_argument(
        "--state",
        type=Path,
        default=default_data_root / "state" / "navidrome-playlists.json",
    )

    parser.add_argument(
        "--navidrome-root",
        default="/music",
        help="MusicFolder path as visible inside Navidrome.",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write playlists and persistent state.",
    )

    parser.add_argument(
        "--expand",
        action="store_true",
        help=(
            "Add newly qualifying Genre, Artist, and Episode Range "
            "playlists to the canonical manifest."
        ),
    )

    args = parser.parse_args()

    db = args.db.expanduser().resolve()
    music_root = args.music_root.expanduser().resolve()

    playlist_dir = (
        args.playlist_dir.expanduser().resolve()
        if args.playlist_dir
        else music_root / "playlists" / "wefunk"
    )

    state_path = args.state.expanduser().resolve()

    if not db.is_file():
        raise SystemExit(f"Database not found: {db}")

    if not music_root.is_dir():
        raise SystemExit(f"Music root not found: {music_root}")

    state_exists = state_path.exists()
    state = load_state(state_path)

    now = int(time.time())

    connection = open_database(db)

    try:
        tracks, stale, tag_errors, no_genre = prepare_tracks(
            connection,
            music_root,
        )
    finally:
        connection.close()

    update_first_seen(
        state,
        tracks,
        now,
    )

    (
        eligible_genres,
        eligible_artists,
        eligible_ranges,
    ) = current_dynamic_groups(tracks)

    initialize_or_expand_manifest(
        state,
        eligible_genres,
        eligible_artists,
        eligible_ranges,
        expand=args.expand,
    )

    if state["initialized_at"] is None:
        state["initialized_at"] = now

    playlists = build_playlists(
        tracks,
        state,
        eligible_genres,
        eligible_artists,
        eligible_ranges,
        now,
    )

    detect_filename_collisions(playlists)

    print_summary(
        tracks,
        stale,
        tag_errors,
        no_genre,
        playlists,
        state,
        state_exists,
        args.expand,
    )

    print()

    if not args.apply:
        print("DRY RUN — no files or state were modified.")
        print()
        print(f"Playlist directory: {playlist_dir}")
        print(f"State file:         {state_path}")
        return

    written = apply_playlists(
        playlists,
        playlist_dir,
        args.navidrome_root,
    )

    atomic_write_json(
        state_path,
        state,
    )

    print("✅ WEFUNK Navidrome playlists updated.")
    print(f"   Playlist files written: {len(written)}")
    print(f"   Playlist directory:     {playlist_dir}")
    print(f"   State file:             {state_path}")


if __name__ == "__main__":
    main()
