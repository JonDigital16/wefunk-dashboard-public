#!/usr/bin/env python3

import os
import json
import time
import hashlib
import urllib.parse
import urllib.request
from pathlib import Path

from common import SITE

OUT = SITE / "now-playing.json"

ND_URL = os.environ.get("ND_URL", "").rstrip("/")
ND_USER = os.environ.get("ND_USER", "")
ND_PASS = os.environ.get("ND_PASS", "")

def write_empty(reason):
    OUT.write_text(json.dumps({
        "ok": False,
        "reason": reason,
        "updated": int(time.time()),
        "now_playing": [],
        "rediscover": []
    }, indent=2), encoding="utf-8")
    print(f"Wrote empty now-playing.json: {reason}")

if not ND_USER or not ND_PASS:
    write_empty("Missing ND_USER or ND_PASS")
    raise SystemExit(0)

salt = "wefunk"
token = hashlib.md5((ND_PASS + salt).encode()).hexdigest()

params = {
    "u": ND_USER,
    "t": token,
    "s": salt,
    "v": "1.16.1",
    "c": "wefunk-dashboard",
    "f": "json",
}

def subsonic(endpoint, extra=None):
    q = params.copy()
    if extra:
        q.update(extra)

    url = f"{ND_URL}/rest/{endpoint}.view?" + urllib.parse.urlencode(q)

    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))

try:
    data = subsonic("getNowPlaying")
    songs = data.get("subsonic-response", {}).get("nowPlaying", {}).get("entry", [])

    if isinstance(songs, dict):
        songs = [songs]

    now = []

    for s in songs:
        cover_id = s.get("coverArt", "")
        cover_url = ""
        if cover_id:
            cover_params = params.copy()
            cover_params["id"] = cover_id
            cover_url = f"{ND_URL}/rest/getCoverArt.view?" + urllib.parse.urlencode(cover_params)

        now.append({
            "title": s.get("title", ""),
            "artist": s.get("artist", ""),
            "album": s.get("album", ""),
            "username": s.get("username", ""),
            "duration": s.get("duration", 0),
            "minutesAgo": s.get("minutesAgo", 0),
            "playerId": s.get("playerId", ""),
            "playCount": s.get("playCount", 0),
            "starred": s.get("starred", ""),
            "cover": cover_url,
        })

    data_recent = subsonic("getRandomSongs", {"size": 10})
    recent_songs = data_recent.get("subsonic-response", {}).get("randomSongs", {}).get("song", [])

    if isinstance(recent_songs, dict):
        recent_songs = [recent_songs]

    rediscover = []

    for s in recent_songs:
        cover_id = s.get("coverArt", "")
        cover_url = ""
        if cover_id:
            cover_params = params.copy()
            cover_params["id"] = cover_id
            cover_url = f"{ND_URL}/rest/getCoverArt.view?" + urllib.parse.urlencode(cover_params)

        rediscover.append({
            "title": s.get("title", ""),
            "artist": s.get("artist", ""),
            "album": s.get("album", ""),
            "duration": s.get("duration", 0),
            "minutesAgo": s.get("minutesAgo", 0),
            "playerId": s.get("playerId", ""),
            "playCount": s.get("playCount", 0),
            "starred": s.get("starred", ""),
            "cover": cover_url,
        })

    OUT.write_text(json.dumps({
        "ok": True,
        "updated": int(time.time()),
        "now_playing": now,
        "rediscover": rediscover
    }, indent=2), encoding="utf-8")

    print(f"Wrote now-playing.json with {len(now)} active track(s)")

except Exception as e:
    write_empty(str(e))
