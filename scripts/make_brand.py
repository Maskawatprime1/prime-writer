"""Make Prime Writer logo assets from brand/logo-source.webp (the designer's 2000x2000 logo).

Outputs
  writer/assets/logo-mark.png          circle + "p" mark, transparent outside the circle (tray, exe, button)
  frontend/public/brand/logo-mark.png  same mark for the web UI and favicon
  frontend/public/brand/logo-full.png        full "pw. prime writer" logo, charcoal, transparent background
  frontend/public/brand/logo-full-light.png  same, light grey, for dark backgrounds
Run:  .venv\\Scripts\\python scripts\\make_brand.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "brand" / "logo-source.webp"
CHARCOAL = (61, 59, 57)
LIGHT = (232, 232, 230)
# circle measured on the 2000x2000 source
CX, CY, R = 812, 1000, 286


def mark(size: int = 1024) -> Image.Image:
    src = Image.open(SRC).convert("RGB")
    box = (CX - R, CY - R, CX + R, CY + R)
    crop = src.crop(box).resize((size, size), Image.LANCZOS)
    ss = 4
    mask = Image.new("L", (size * ss, size * ss), 0)
    ImageDraw.Draw(mask).ellipse((2, 2, size * ss - 3, size * ss - 3), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(crop, (0, 0), mask)
    return out


def full(color) -> Image.Image:
    src = Image.open(SRC).convert("L")
    pad = 30
    src = src.crop((526 - pad, 714 - pad, 1684 + pad, 1286 + pad))
    # darkness -> opacity; the white "p" inside the circle becomes see-through
    alpha = src.point(lambda v: max(0, min(255, int((235 - v) * 255 / (235 - 61)))))
    out = Image.new("RGBA", src.size, color + (0,))
    out.putalpha(alpha)
    return out


def main() -> None:
    (ROOT / "writer" / "assets").mkdir(parents=True, exist_ok=True)
    web = ROOT / "frontend" / "public" / "brand"
    web.mkdir(parents=True, exist_ok=True)
    m = mark()
    m.save(ROOT / "writer" / "assets" / "logo-mark.png")
    m.resize((256, 256), Image.LANCZOS).save(web / "logo-mark.png")
    f = full(CHARCOAL)
    f.save(web / "logo-full.png")
    full(LIGHT).save(web / "logo-full-light.png")
    print("brand assets written:", m.size, f.size)


if __name__ == "__main__":
    main()
