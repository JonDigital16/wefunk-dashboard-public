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

source = live_site / "data" / "artist-bios.json"
target = build_site / "data" / "artist-bios.json"

if not source.exists():
    print("No existing artist biography cache found; skipping")
    raise SystemExit(0)

target.parent.mkdir(
    parents=True,
    exist_ok=True,
)

shutil.copy2(
    source,
    target,
)

print("Preserved artist biography cache")
print(target)
