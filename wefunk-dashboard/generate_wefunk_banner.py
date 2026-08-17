import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ART_DIR = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "artwork" / 'episodes'
OUT_DIR = Path(os.environ.get("WEFUNK_SITE_DIR", Path(__file__).resolve().parents[1] / "site")) / "static"
OUT = OUT_DIR / "wefunk-banner.jpg"

OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 2400, 650
TILE = 120
COLS = W // TILE
ROWS = H // TILE

images = sorted(
    [p for p in ART_DIR.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}],
    key=lambda p: p.name
)

if not images:
    raise SystemExit("No artwork found.")

canvas = Image.new("RGB", (W, H), "#101214")

i = 0
for y in range(ROWS + 1):
    for x in range(COLS + 1):
        img_path = images[i % len(images)]
        i += 1

        try:
            img = Image.open(img_path).convert("RGB")
            img = img.resize((TILE, TILE), Image.LANCZOS)
            canvas.paste(img, (x * TILE, y * TILE))
        except Exception:
            pass

canvas = canvas.filter(ImageFilter.GaussianBlur(radius=1.1))

overlay = Image.new("RGBA", (W, H), (0, 0, 0, 115))
canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)

draw = ImageDraw.Draw(canvas)
draw.rectangle((0, 0, W, H), outline=(247, 147, 30, 180), width=6)

canvas.convert("RGB").save(OUT, quality=90)
print(f"Generated: {OUT}")
