"""Annotate the continuation-panel screenshot for the paper (Figure 2).

Input: a 2x headless-Chrome capture of /figure (temporary fixture route)
  chrome --headless=new --screenshot=ui-raw.png --window-size=1200,720 \
    --force-device-scale-factor=2 --virtual-time-budget=8000 \
    http://127.0.0.1:3000/figure

Output: docs/ismir2026/assets/ui-panel.png — cropped panel with a thin
frame and circled (a)-(e) callouts in a left margin band, keyed in the
figure caption.

Usage:
  python research/annotate_ui_figure.py <raw-capture.png>
"""

import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

CROP = (96, 150, 2312, 1220)  # panel region in the 2x capture
BAND = 120                    # left margin band width (px)
FRAME = "#b0aca6"

# (label, y in cropped coords)
CALLOUTS = [
    ("a", 120),   # session fingerprint summary
    ("b", 396),   # text intent field
    ("c", 535),   # intensity + ranker controls
    ("d", 772),   # evidence chips
    ("e", 908),   # audition / insert / skip actions
]


def serif_font(size):
    for name in ("Times New Roman.ttf", "Times.ttc", "Georgia.ttf"):
        try:
            return ImageFont.truetype(f"/System/Library/Fonts/Supplemental/{name}", size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    raw = pathlib.Path(sys.argv[1])
    im = Image.open(raw).convert("RGB").crop(CROP)
    w, h = im.size

    canvas = Image.new("RGB", (w + BAND, h), "#ffffff")
    canvas.paste(im, (BAND, 0))
    d = ImageDraw.Draw(canvas)

    # hairline frame around the screenshot
    d.rectangle([BAND, 0, BAND + w - 1, h - 1], outline=FRAME, width=2)

    font = serif_font(44)
    r = 34
    cx = BAND // 2
    for label, cy in CALLOUTS:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline="#4a4a4a", width=3)
        bb = d.textbbox((0, 0), label, font=font)
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0],
                cy - (bb[3] - bb[1]) / 2 - bb[1]),
               label, fill="#1a1a1a", font=font)
        d.line([cx + r, cy, BAND - 6, cy], fill="#8a8a8a", width=2)

    out = (pathlib.Path(__file__).resolve().parent.parent
           / "docs" / "ismir2026" / "assets" / "ui-panel.png")
    canvas.save(out, optimize=True)
    print(f"Saved {out} ({canvas.size[0]}x{canvas.size[1]})")


if __name__ == "__main__":
    main()
