"""Prime Writer logo for the tray, exe icon and floating button.

The artwork is writer/assets/logo-mark.png (circle + "p"), cut from brand/logo-source.webp by scripts/make_brand.py.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageEnhance

MARK = Path(__file__).resolve().parent / "assets" / "logo-mark.png"


@lru_cache(maxsize=1)
def _mark() -> Image.Image:
    return Image.open(MARK).convert("RGBA")


def make_logo(size: int = 256, shape: str = "circle", on: bool = True, sparkle: bool | None = None) -> Image.Image:
    """The round mark at `size` px. on=False gives a faded grey version (Prime Writer switched off).
    `shape` and `sparkle` are accepted for compatibility; the mark is always round."""
    img = _mark().resize((size, size), Image.LANCZOS)
    if not on:
        r, g, b, a = img.split()
        rgb = ImageEnhance.Brightness(Image.merge("RGB", (r, g, b))).enhance(2.2)
        img = Image.merge("RGBA", (*rgb.split(), a.point(lambda v: v * 3 // 4)))
    return img


def save_ico(path: str) -> None:
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    imgs = [make_logo(s) for s in sizes]
    imgs[-1].save(path, sizes=[(s, s) for s in sizes], append_images=imgs[:-1])


if __name__ == "__main__":
    make_logo(512).save("logo-preview.png")
