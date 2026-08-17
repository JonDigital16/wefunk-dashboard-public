import csv
import sqlite3
import os
from pathlib import Path
from collections import Counter
from mutagen import File as MutagenFile

DB = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "db" / 'wefunk_engine.db'
OUT = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve() / 'wefunk_genre_dna.csv'

def split_genres(value):
    if not value:
        return []
    value = str(value).replace(";", ",").replace("/", ",")
    return [g.strip().title() for g in value.split(",") if g.strip()]

conn = sqlite3.connect(DB)
cur = conn.cursor()

rows = cur.execute("""
SELECT DISTINCT file_path
FROM matches
WHERE file_path IS NOT NULL AND file_path != ''
""").fetchall()

counts = Counter()

for (file_path,) in rows:
    try:
        audio = MutagenFile(file_path, easy=True)
        genres = []
        if audio and audio.tags:
            genres = audio.tags.get("genre", [])
        for genre in genres:
            for g in split_genres(genre):
                counts[g] += 1
    except Exception:
        pass

with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["genre", "count"])
    for genre, count in counts.most_common(50):
        w.writerow([genre, count])

print(f"Wrote {len(counts)} genres to {OUT}")
