import json
import re
import csv
import argparse
import os
from pathlib import Path
from urllib.parse import urljoin

import requests

JSON_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "json"
ART_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "artwork" / 'episodes'
REPORT = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "artwork" / 'wefunk_art_report.csv'

ART_DIR.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)

def newest_json():
    return max(JSON_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)

def find_image_url(html, base_url):
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
    ]

    for pat in patterns:
        m = re.search(pat, html, re.I)
        if m:
            return urljoin(base_url, m.group(1))

    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I)
    imgs = [
        urljoin(base_url, x)
        for x in imgs
        if not any(bad in x.lower() for bad in ["logo", "icon", "sprite", "blank", "avatar"])
    ]

    return imgs[0] if imgs else None

def ext_from_content_type(content_type):
    content_type = (content_type or "").lower()
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    return ".jpg"

def download_show(show, force=False):
    show_id = str(show.get("show_id", "")).strip()
    url = show.get("url", "").strip()

    if not show_id or not url:
        return [show_id, "", "", "missing show_id or url"]

    existing = list(ART_DIR.glob(f"{show_id}.*"))
    if existing and not force:
        return [show_id, str(existing[0]), "", "exists"]

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()

        image_url = find_image_url(r.text, url)
        if not image_url:
            return [show_id, "", url, "no image found"]

        img = requests.get(image_url, timeout=30)
        img.raise_for_status()

        ext = ext_from_content_type(img.headers.get("content-type"))
        out = ART_DIR / f"{show_id}{ext}"
        out.write_bytes(img.content)

        return [show_id, str(out), image_url, "downloaded"]

    except Exception as e:
        return [show_id, "", url, f"error: {e}"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Only download one show number")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    jf = newest_json()
    print(f"Using JSON: {jf}")

    shows = json.loads(jf.read_text(encoding="utf-8"))

    if args.only:
        shows = [s for s in shows if str(s.get("show_id")) == str(args.only)]

    rows = []
    for show in shows:
        result = download_show(show, force=args.force)
        print(result[0], "-", result[3])
        rows.append(result)

    with REPORT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["show_id", "art_path", "source_url", "status"])
        w.writerows(rows)

    print(f"Report: {REPORT}")
    print(f"Artwork folder: {ART_DIR}")

if __name__ == "__main__":
    main()
