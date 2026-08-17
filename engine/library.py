"""Music-library scanning for the WEFUNK matching engine."""

from collections import defaultdict
from pathlib import Path

from mutagen import File as MutagenFile

from engine.config import AUDIO_EXTS, MUSIC_DIR
from engine.utils import clean, tag_value


def load_library(
    music_dir: Path = MUSIC_DIR,
    audio_exts: set[str] = AUDIO_EXTS,
):
    """Read music metadata and build the matching indexes.

    Returns:
        A tuple containing:

        - A list of every indexed library track.
        - A dictionary grouping tracks by cleaned artist name.
    """
    print("Reading music tags...")

    library = []
    library_by_artist = defaultdict(list)

    for path in music_dir.rglob("*"):
        if path.suffix.lower() not in audio_exts:
            continue

        try:
            audio = MutagenFile(path, easy=True)
            artist = tag_value(audio, ["artist", "albumartist"])
            title = tag_value(audio, ["title"])
        except Exception:
            artist = ""
            title = ""

        if not artist or not title:
            artist = path.parent.name
            title = path.stem

        item = {
            "path": str(path),
            "artist": artist,
            "title": title,
            "artist_c": clean(artist),
            "title_c": clean(title),
            "combined_c": clean(f"{artist} {title}"),
        }

        library.append(item)
        library_by_artist[item["artist_c"]].append(item)

    print(f"Indexed {len(library)} tracks")
    print(f"Indexed {len(library_by_artist)} artists")

    return library, library_by_artist