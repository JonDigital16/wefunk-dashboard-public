import os
import re
import argparse
from pathlib import Path
from mutagen.id3 import ID3, COMM, ID3NoHeaderError

MUSIC_DIR = Path(os.environ.get("WEFUNK_EPISODE_DIR", Path(os.environ.get("WEFUNK_MUSIC_DIR", Path.home() / "Music")) / "wefunkradio mixes")).expanduser().resolve()
BASE_URL = os.environ.get("WEFUNK_PUBLIC_URL", "").rstrip("/") + "/shows"

def show_id_from_path(path):
    m = re.search(r"WEFUNK[_\s-]*Show[_\s-]*(\d{3,4})", path.name, re.I)
    return m.group(1) if m else None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    matches = []
    for audio in sorted(MUSIC_DIR.glob("*.mp3")):
        show_id = show_id_from_path(audio)
        if show_id:
            matches.append((audio, show_id, f"{BASE_URL}/{show_id}.html"))

    print(f"Matched {len(matches)} MP3 files")

    for audio, show_id, url in matches[:50]:
        print(f"{audio.name}  ->  {url}")
    if len(matches) > 50:
        print(f"...and {len(matches) - 50} more")

    if not args.apply:
        print("\nDry run only. To write comments, run with --apply")
        return

    for audio, show_id, url in matches:
        try:
            tags = ID3(audio)
        except ID3NoHeaderError:
            tags = ID3()

        # Remove all existing comment frames cleanly
        for key in list(tags.keys()):
            if key.startswith("COMM"):
                del tags[key]

        tags.add(COMM(
            encoding=3,
            lang="eng",
            desc="WEFUNK Dashboard",
            text=f"WEFUNK episode page: {url}"
        ))

        # Save as ID3v2.3 and remove old ID3v1 tag if present
        tags.save(audio, v2_version=3, v1=0)

    print(f"Tagged {len(matches)} files with clean WEFUNK episode links")

if __name__ == "__main__":
    main()
