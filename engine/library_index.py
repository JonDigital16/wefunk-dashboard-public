"""Shared local-music library-index functionality for the WEFUNK engine."""

from pathlib import Path
import re

from mutagen import File as MutagenFile

from engine.database import (
    clear_library_index,
    delete_library_index_paths,
    ensure_library_index_table,
    load_library_index,
    upsert_library_index_rows,
)


AUDIO_EXTS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wav",
}


def clean(value):
    """Normalize artist and title text for matching."""

    value = str(value or "").lower()
    value = re.sub(r"\(.*?\)|\[.*?\]", "", value)
    value = re.sub(r"\b(feat|ft|featuring)\b.*", "", value)
    value = re.sub(r"^the\s+", "", value)
    value = value.replace("&", "and")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tag_value(audio, keys):
    """Return the first available tag value for the supplied tag keys."""

    if audio is None or not audio.tags:
        return ""

    for key in keys:
        value = audio.tags.get(key)

        if not value:
            continue

        if isinstance(value, list):
            return str(value[0]) if value else ""

        return str(value)

    return ""


def read_library_tags(path):
    """Read artist and title tags from an audio file."""

    try:
        audio = MutagenFile(path, easy=True)
        artist = tag_value(audio, ["artist", "albumartist"])
        title = tag_value(audio, ["title"])
    except Exception as error:
        print(f"Could not read tags: {path}")
        print(f"  {error}")
        artist = ""
        title = ""

    if not artist:
        artist = path.parent.name

    if not title:
        title = path.stem

    return artist, title


def iter_audio_files(music_dir):
    """Yield supported audio files beneath the supplied music directory."""

    music_dir = Path(music_dir)

    for path in music_dir.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in AUDIO_EXTS:
            continue

        yield path


def sync_library_index(
    conn,
    music_dir,
    *,
    full_rebuild=False,
    progress_interval=1000,
):
    """
    Synchronize the persistent library index with the music filesystem.

    Only new or changed files have their audio tags reread. Unchanged files
    reuse their existing database rows, and rows for deleted files are removed.

    Returns a dictionary containing synchronization statistics.
    """

    music_dir = Path(music_dir)

    if not music_dir.exists():
        raise FileNotFoundError(f"Music directory not found: {music_dir}")

    if not music_dir.is_dir():
        raise NotADirectoryError(f"Music path is not a directory: {music_dir}")

    ensure_library_index_table(conn)

    cleared = 0

    if full_rebuild:
        cleared = clear_library_index(conn)
        print(f"Cleared {cleared:,} cached library rows")

    cached = load_library_index(conn)

    seen_paths = set()
    changed_rows = []

    discovered = 0
    reused = 0
    added = 0
    changed = 0
    stat_errors = 0

    print(f"Scanning: {music_dir}")

    for path in iter_audio_files(music_dir):
        discovered += 1
        file_path = str(path)
        seen_paths.add(file_path)

        try:
            stat = path.stat()
        except OSError as error:
            stat_errors += 1
            print(f"Could not inspect file: {path}")
            print(f"  {error}")
            continue

        cached_row = cached.get(file_path)

        unchanged = (
            cached_row is not None
            and cached_row["file_size"] == stat.st_size
            and cached_row["mtime_ns"] == stat.st_mtime_ns
        )

        if unchanged:
            reused += 1
        else:
            artist, title = read_library_tags(path)

            artist_norm = clean(artist)
            title_norm = clean(title)
            combined_norm = clean(f"{artist} {title}")

            changed_rows.append(
                (
                    file_path,
                    stat.st_size,
                    stat.st_mtime_ns,
                    artist,
                    title,
                    artist_norm,
                    title_norm,
                    combined_norm,
                )
            )

            if cached_row is None:
                added += 1
            else:
                changed += 1

        if progress_interval and discovered % progress_interval == 0:
            print(
                f"Scanned {discovered:,} files "
                f"— reused {reused:,}, "
                f"new {added:,}, changed {changed:,}"
            )

    stale_paths = set(cached) - seen_paths

    written = upsert_library_index_rows(conn, changed_rows)
    deleted = delete_library_index_paths(conn, stale_paths)

    final_count = conn.execute(
        "SELECT COUNT(*) FROM library_index"
    ).fetchone()[0]

    return {
        "cleared": cleared,
        "discovered": discovered,
        "reused": reused,
        "added": added,
        "changed": changed,
        "written": written,
        "deleted": deleted,
        "stat_errors": stat_errors,
        "final_count": final_count,
    }


def print_sync_summary(stats):
    """Print a human-readable library synchronization summary."""

    print()
    print("Library-index synchronization complete")
    print(f"Audio files discovered: {stats['discovered']:,}")
    print(f"Unchanged rows reused:  {stats['reused']:,}")
    print(f"New files indexed:      {stats['added']:,}")
    print(f"Changed files indexed:  {stats['changed']:,}")
    print(f"Rows written:           {stats['written']:,}")
    print(f"Deleted files removed:  {stats['deleted']:,}")
    print(f"File-stat errors:       {stats['stat_errors']:,}")
    print(f"Library-index rows:     {stats['final_count']:,}")

    expected_count = stats["discovered"] - stats["stat_errors"]

    if stats["final_count"] != expected_count:
        print()
        print(
            "⚠️ Index count differs from the successfully inspected "
            "filesystem count."
        )
