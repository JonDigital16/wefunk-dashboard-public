from pathlib import Path
import os
import shutil

project = Path(
    os.environ.get(
        "WEFUNK_PROJECT_ROOT",
        Path(__file__).resolve().parents[1],
    )
)

live_site = Path(
    os.environ.get(
        "WEFUNK_LIVE_SITE_DIR",
        project / "site",
    )
)

build_site = Path(
    os.environ.get(
        "WEFUNK_SITE_DIR",
        project / "site-next",
    )
)

source = live_site / "artist-images"
target = build_site / "artist-images"

if not source.exists():
    print("No existing artist-image cache found; skipping")
    raise SystemExit(0)

target.mkdir(parents=True, exist_ok=True)

copied = 0

for src in source.rglob("*"):
    if not src.is_file():
        continue

    rel = src.relative_to(source)
    dst = target / rel
    dst.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src, dst)
    copied += 1

print(f"Preserved {copied} artist-image files")
print(target)
