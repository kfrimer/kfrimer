"""
One-time builder for the ASCII portrait.

Usage:
    pip install pillow numpy
    python scripts/build_portrait.py path/to/cutout.png

The input should be a PNG with a transparent background (e.g. made with
`rembg`). The script writes:
    assets/src/portrait.json   – compact grid used by generate_profile.py
    assets/ascii-portrait.svg  – large standalone animated portrait
and then refreshes every other SVG.
"""
import colorsys
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COLS = 104                       # characters per row
CELL_ASPECT = 9 / 5.4            # cell height / cell width (monospace glyph)
CROP = (110, 160, 1096, 1330)    # x0, y0, x1, y1 in source pixels
RAMP = " .:-=+*o#%@"              # sparse → dense (dark bg: bright = dense)
QUANT = 10                       # colour quantisation step


def build(src):
    im = Image.open(src).convert("RGBA").crop(CROP)
    w, h = im.size
    rows = round(h / (w / COLS) / CELL_ASPECT)

    rgb = np.asarray(im.convert("RGB")).astype(np.float32) / 255
    alpha = np.asarray(im.getchannel("A")).astype(np.float32) / 255
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]

    # local contrast: subtract a heavy blur so eyes / nose / mouth pop out
    lum_img = Image.fromarray((lum * 255).astype(np.uint8))
    blur = np.asarray(lum_img.filter(ImageFilter.GaussianBlur(16))).astype(np.float32) / 255
    detail = lum + 1.2 * (lum - blur)

    # stretch tones inside the subject only
    m = alpha > 0.5
    lo, hi = np.percentile(detail[m], [3, 99.5])
    tone = np.clip((detail - lo) / (hi - lo), 0, 1)

    def down(a):
        return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((COLS, rows), Image.BOX)).astype(np.float32) / 255

    tone_s = down(tone)
    alpha_s = down(alpha)
    rgb_s = np.asarray(im.convert("RGB").resize((COLS, rows), Image.BOX)).astype(np.float32) / 255

    grid = []
    for y in range(rows):
        row = []
        for x in range(COLS):
            if alpha_s[y, x] < 0.45:
                row.append([" ", None])
                continue
            t = (1 - tone_s[y, x]) ** 0.9   # "ink" mode: dark features = dense glyphs
            ch = RAMP[1 + min(len(RAMP) - 2, int(t * (len(RAMP) - 1)))]
            r, g, b = rgb_s[y, x]
            hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
            vv = 0.42 + 0.58 * vv
            ss = min(1.0, ss * 1.15)
            cr, cg, cb = colorsys.hsv_to_rgb(hh, ss, min(vv, 1))
            col = tuple(min(255, int(round(c * 255 / QUANT) * QUANT)) for c in (cr, cg, cb))
            row.append([ch, "#%02x%02x%02x" % col])
        grid.append(row)

    while grid and all(c[0] == " " for c in grid[0]):
        grid.pop(0)

    rle = []
    for row in grid:
        runs = []
        for ch, col in row:
            if ch == " ":
                col = None
            if runs and runs[-1][0] == col:
                runs[-1][1] += ch
            else:
                runs.append([col, ch])
        if runs and runs[-1][0] is None:
            runs.pop()
        rle.append(runs)

    os.makedirs(os.path.join(ROOT, "assets", "src"), exist_ok=True)
    with open(os.path.join(ROOT, "assets", "src", "portrait.json"), "w", encoding="utf-8") as f:
        json.dump({"cols": COLS, "rows": len(rle), "data": rle}, f, separators=(",", ":"))
    print(f"portrait grid: {COLS} x {len(rle)}")


if __name__ == "__main__":
    build(sys.argv[1])
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import generate_profile  # noqa: E402
    generate_profile.write_standalone_portrait()
