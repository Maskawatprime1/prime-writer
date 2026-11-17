"""Prime Writer logo, drawn with Pillow (same geometry as frontend/public/logo.svg).

256-unit grid: gradient tile, a geometric "P" (stem + bowl, round caps) and a small AI sparkle.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

INDIGO, VIOLET = (99, 102, 241), (168, 85, 247)
GREY_A, GREY_B = (154, 161, 174), (107, 115, 133)
SS = 4  # supersampling for smooth edges


def _gradient(size: int, c1, c2) -> Image.Image:
    """Diagonal gradient, top-left c1 -> bottom-right c2."""
    g = Image.new("RGB", (size, size))
    px = g.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))
    return g


def _sparkle(cx, cy, r, steps=12):
    """4-point star with concave sides (quadratic curves through the centre)."""
    pts = []
    tips = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    for i in range(4):
        a, b = tips[i], tips[(i + 1) % 4]
        ctrl = (cx + (a[0] + b[0] - 2 * cx) * 0.12, cy + (a[1] + b[1] - 2 * cy) * 0.12)
        for k in range(steps):
            t = k / steps
            x = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * ctrl[0] + t * t * b[0]
            y = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * ctrl[1] + t * t * b[1]
            pts.append((x, y))
    return pts


def make_logo(size: int = 256, shape: str = "square", on: bool = True, sparkle: bool | None = None) -> Image.Image:
    """shape: 'square' (app/tray/exe icon) or 'circle' (floating button)."""
    S = size * SS
    k = S / 256
    c1, c2 = (INDIGO, VIOLET) if on else (GREY_A, GREY_B)
    grad = _gradient(64, c1, c2).resize((S, S), Image.BILINEAR)
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    if shape == "circle":
        md.ellipse((0, 0, S - 1, S - 1), fill=255)
    else:
        md.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(60 * k), fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)

    # soft top sheen: white fading to nothing by mid-height
    fade = Image.linear_gradient("L").resize((S, S)).point(lambda v: max(0, 40 - v * 80 // 255))
    hl = Image.composite(fade, Image.new("L", (S, S), 0), mask)
    img.paste((255, 255, 255), (0, 0), hl)

    d = ImageDraw.Draw(img)
    w = 34 * k
    white = (255, 255, 255, 255)
    # stem
    d.line([(94 * k, 70 * k), (94 * k, 188 * k)], fill=white, width=int(w))
    for y in (70, 188):
        d.ellipse((94 * k - w / 2, y * k - w / 2, 94 * k + w / 2, y * k + w / 2), fill=white)
    # bowl: two bars + half circle
    d.line([(94 * k, 70 * k), (142 * k, 70 * k)], fill=white, width=int(w))
    d.line([(94 * k, 130 * k), (142 * k, 130 * k)], fill=white, width=int(w))
    r = 30 * k + w / 2
    d.arc((142 * k - r, 100 * k - r, 142 * k + r, 100 * k + r), start=-90, end=90, fill=white, width=int(w))
    # sparkle (skipped at tiny sizes where it turns to mush)
    if sparkle if sparkle is not None else size >= 24:
        d.polygon([(x * k, y * k) for x, y in _sparkle(192, 184, 28)], fill=(255, 255, 255, 240))
    return img.resize((size, size), Image.LANCZOS)


def save_ico(path: str) -> None:
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    imgs = [make_logo(s) for s in sizes]
    imgs[-1].save(path, sizes=[(s, s) for s in sizes], append_images=imgs[:-1])


if __name__ == "__main__":
    make_logo(512).save("logo-preview.png")
