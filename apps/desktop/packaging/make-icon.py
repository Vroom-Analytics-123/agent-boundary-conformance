#!/usr/bin/env python3
"""Make the first FinePrint app icon (assets/fineprint.{png,icns,ico}).

Design (on-brand with the repo palette): a navy canvas (#0F1B2D) rounded
square, a teal shield (#2AA5A0), a white check. Simple enough to read at
16x16, no text. This is a first icon, not a brand mark — a real brand icon
replaces it later.

Outputs (all derived from one 1024x1024 master, so they always agree):
  assets/fineprint.png   master PNG
  assets/fineprint.icns  macOS icon (ic07 128 / ic08 256 / ic09 512 /
                         ic10 1024, PNG elements — the modern format
                         macOS accepts; no macOS tooling needed)
  assets/fineprint.ico   Windows icon (16 / 32 / 48 / 256)

Run:  python3 packaging/make-icon.py   (from apps/desktop)
Needs: Pillow (pip install pillow). Stdlib + PIL only.
"""
import io
import math
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent.parent
ASSETS = HERE / "assets"

NAVY = (15, 27, 45, 255)      # #0F1B2D canvas
TEAL = (42, 165, 160, 255)    # #2AA5A0
WHITE = (255, 255, 255, 255)

SIZE = 1024


def shield_points(cx, top, half_w, mid_y, bottom_y, steps=24):
    """Shield outline as a polygon: flat top, sides curving to a bottom
    point. Returns a list of (x, y) points, clockwise from top-left."""
    pts = [(cx - half_w, top), (cx + half_w, top)]
    # Right side: straight down to mid_y, then a quadratic curve to the
    # bottom point.
    pts.append((cx + half_w, mid_y))
    for i in range(1, steps + 1):
        t = i / steps
        # Quadratic Bezier from (cx+half_w, mid_y) via (cx+half_w, bottom_y)
        # to (cx, bottom_y).
        x = (1 - t) ** 2 * (cx + half_w) + 2 * (1 - t) * t * (cx + half_w) + t * t * cx
        y = (1 - t) ** 2 * mid_y + 2 * (1 - t) * t * bottom_y + t * t * bottom_y
        pts.append((x, y))
    # Left side, mirrored, back up to the top-left.
    for i in range(1, steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * cx + 2 * (1 - t) * t * (cx - half_w) + t * t * (cx - half_w)
        y = (1 - t) ** 2 * bottom_y + 2 * (1 - t) * t * bottom_y + t * t * mid_y
        pts.append((x, y))
    pts.append((cx - half_w, top))
    return pts


def draw_master(size=SIZE):
    """The icon at `size` px. All geometry scales from the 1024 master."""
    s = size / SIZE
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # Navy rounded square, full-bleed with a small margin.
    m = int(48 * s)
    r = int(190 * s)
    d.rounded_rectangle([m, m, size - m, size - m], radius=r, fill=NAVY)
    # Teal shield, centred.
    cx = size // 2
    pts = shield_points(cx, int(250 * s), int(205 * s), int(500 * s), int(790 * s))
    d.polygon(pts, fill=TEAL)
    # White check, thick, inside the shield.
    check = [(int(400 * s), int(520 * s)),
             (int(482 * s), int(612 * s)),
             (int(648 * s), int(408 * s))]
    d.line(check, fill=WHITE, width=int(72 * s), joint="curve")
    return im


def png_bytes(im):
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def write_icns(pngs, out_path):
    """Minimal .icns writer: 'icns' magic + total length, then one
    element per size (OSType + length incl. header + PNG data)."""
    body = b""
    for ostype, data in pngs.items():
        body += ostype.encode("ascii") + struct.pack(">I", 8 + len(data)) + data
    out_path.write_bytes(b"icns" + struct.pack(">I", 8 + len(body)) + body)


def main():
    ASSETS.mkdir(exist_ok=True)
    master = draw_master()
    master.save(ASSETS / "fineprint.png")
    # .icns: PNG elements the modern format accepts.
    pngs = {
        "ic07": png_bytes(draw_master(128)),
        "ic08": png_bytes(draw_master(256)),
        "ic09": png_bytes(draw_master(512)),
        "ic10": png_bytes(draw_master(1024)),
    }
    write_icns(pngs, ASSETS / "fineprint.icns")
    # .ico: Pillow writes the multi-size container directly.
    master.save(ASSETS / "fineprint.ico",
                sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    for name in ("fineprint.png", "fineprint.icns", "fineprint.ico"):
        p = ASSETS / name
        print(f"wrote {p} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    sys.exit(main())
