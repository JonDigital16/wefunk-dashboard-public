import os, re, csv, hashlib, secrets, requests
from pathlib import Path

OUT = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve() / 'wefunk_show_play_counts.csv'

url = os.environ["ND_URL"].rstrip("/")
u = os.environ["ND_USER"]
p = os.environ["ND_PASS"]

salt = secrets.token_hex(8)
token = hashlib.md5((p + salt).encode()).hexdigest()

def params(extra):
    base = {"u":u,"t":token,"s":salt,"v":"1.16.1","c":"wefunk-dashboard","f":"json"}
    base.update(extra)
    return base

def show_id(song):
    blob = " ".join(str(song.get(k,"")) for k in ["title","album","artist","path"])
    for pat in [r"#(\d{3,4})", r"WEFUNK[_\s-]*Show[_\s-]*(\d{3,4})", r"\bShow[_\s-]*(\d{3,4})\b"]:
        m = re.search(pat, blob, re.I)
        if m:
            return m.group(1)
    return None

rows = {}
offset = 0

while True:
    r = requests.get(f"{url}/rest/search3.view", params=params({
        "query":"WEFUNK","songCount":500,"songOffset":offset,
        "artistCount":0,"albumCount":0
    }), timeout=60)
    r.raise_for_status()
    songs = r.json()["subsonic-response"].get("searchResult3", {}).get("song", [])
    if not songs:
        break

    for s in songs:
        sid = show_id(s)
        if not sid:
            continue

        plays = int(s.get("playCount") or 0)
        duration = int(float(s.get("duration") or 0))
        played = s.get("played") or ""

        rows[sid] = {
            "play_count": plays,
            "last_played": played,
            "duration_seconds": duration,
            "total_seconds": plays * duration
        }

    offset += 500
    print(f"Processed {offset} songs...")

OUT.parent.mkdir(parents=True, exist_ok=True)

with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["show_id","play_count","last_played","duration_seconds","total_seconds"])
    for sid in sorted(rows, key=lambda x:int(x)):
        r = rows[sid]
        w.writerow([sid,r["play_count"],r["last_played"],r["duration_seconds"],r["total_seconds"]])

print(f"Wrote {len(rows)} rows")
print(OUT)
