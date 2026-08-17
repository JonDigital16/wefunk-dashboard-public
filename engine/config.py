import os
from pathlib import Path
from dotenv import load_dotenv

# Load project-local configuration without overriding
# variables already supplied by the operating environment.
_PROJECT_ROOT_DEFAULT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT_DEFAULT / ".env", override=False)

PROJECT_ROOT = Path(
    os.environ.get(
        "WEFUNK_PROJECT_ROOT",
        Path(__file__).resolve().parents[1],
    )
).expanduser().resolve()

DATA_ROOT = Path(
    os.environ.get(
        "WEFUNK_DATA_DIR",
        PROJECT_ROOT / "data",
    )
).expanduser().resolve()

DB_DIR = DATA_ROOT / "db"
EXPORT_DIR = DATA_ROOT / "exports"
PLAYLIST_DIR = DATA_ROOT / "playlists"

DB_FILE = Path(
    os.environ.get(
        "WEFUNK_DB_FILE",
        DB_DIR / "wefunk.db",
    )
).expanduser().resolve()

MUSIC_DIR = Path(
    os.environ.get(
        "WEFUNK_MUSIC_DIR",
        Path.home() / "Music",
    )
).expanduser().resolve()

for directory in (
    DB_DIR,
    EXPORT_DIR,
    PLAYLIST_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)

AUDIO_EXTS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wav",
}
