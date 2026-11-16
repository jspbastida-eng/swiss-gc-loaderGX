#!/usr/bin/env python3
"""
make_covers.py - convert box art images into .cvr files for Swiss' Cover Flow browser.

Usage:
    python make_covers.py <input folder> <output folder> [--rgb565]

  <input folder>   PNG/JPG/BMP/WEBP covers, named by game ID, e.g. GALE01.png
                   (the same naming USB Loader GX / WiiFlow / GameTDB use, so their
                   2D cover folders can be used as-is). Any other name works too
                   and is matched against the game's file name (without extension).
  <output folder>  Copy the result to  swiss/covers/  on the SD card (or device)
                   that holds your games.
  --rgb565         Better colours, 4x bigger files (~70 KB instead of ~18 KB each).

Needs Python 3 and Pillow:  pip install pillow
"""
import os
import struct
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is missing. Install it with:  pip install pillow")

WIDTH, HEIGHT = 160, 224        # GameTDB 2D cover size, multiple of 8
GX_TF_RGB565 = 0x4
GX_TF_CMPR = 0xE
EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")


def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def unpack565(c):
    r, g, b = (c >> 11) & 0x1F, (c >> 5) & 0x3F, c & 0x1F
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def encode_dxt1_block(px):
    """px: list of 16 (r,g,b) tuples, row major. Returns 8 bytes, GameCube byte order."""
    # Endpoints: extremes along the axis of greatest spread (cheap but decent)
    spreads = [max(p[i] for p in px) - min(p[i] for p in px) for i in range(3)]
    axis = spreads.index(max(spreads))
    lo = min(px, key=lambda p: (p[axis], sum(p)))
    hi = max(px, key=lambda p: (p[axis], sum(p)))
    c0, c1 = rgb565(*hi), rgb565(*lo)
    if c0 == c1:
        return struct.pack(">HHI", c0, c1, 0)
    if c0 < c1:
        c0, c1 = c1, c0
    e0, e1 = unpack565(c0), unpack565(c1)
    palette = [e0, e1,
               tuple((2 * a + b) // 3 for a, b in zip(e0, e1)),
               tuple((a + 2 * b) // 3 for a, b in zip(e0, e1))]
    bits = 0
    for p in px:
        best = min(range(4), key=lambda i: sum((p[k] - palette[i][k]) ** 2 for k in range(3)))
        bits = (bits << 2) | best      # first pixel ends up in the top bits, as GX expects
    return struct.pack(">HHI", c0, c1, bits)


def to_cmpr(img):
    pix = img.load()
    out = bytearray()
    # 8x8 tiles, each made of 4 DXT1 blocks: top-left, top-right, bottom-left, bottom-right
    for ty in range(0, HEIGHT, 8):
        for tx in range(0, WIDTH, 8):
            for by, bx in ((0, 0), (0, 4), (4, 0), (4, 4)):
                block = [pix[tx + bx + x, ty + by + y] for y in range(4) for x in range(4)]
                out += encode_dxt1_block(block)
    return bytes(out)


def to_rgb565(img):
    pix = img.load()
    out = bytearray()
    # 4x4 tiles of big endian RGB565
    for ty in range(0, HEIGHT, 4):
        for tx in range(0, WIDTH, 4):
            for y in range(4):
                for x in range(4):
                    out += struct.pack(">H", rgb565(*pix[tx + x, ty + y]))
    return bytes(out)


def convert(src, dst, use_rgb565):
    img = Image.open(src).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
    fmt = GX_TF_RGB565 if use_rgb565 else GX_TF_CMPR
    data = to_rgb565(img) if use_rgb565 else to_cmpr(img)
    header = b"SWCV" + struct.pack(">HHB", WIDTH, HEIGHT, fmt)
    header += b"\0" * (32 - len(header))
    with open(dst, "wb") as f:
        f.write(header + data)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    src_dir, dst_dir = args
    use_rgb565 = "--rgb565" in sys.argv
    os.makedirs(dst_dir, exist_ok=True)
    files = sorted(f for f in os.listdir(src_dir) if f.lower().endswith(EXTENSIONS))
    if not files:
        sys.exit("No images found in " + src_dir)
    for i, name in enumerate(files, 1):
        stem = os.path.splitext(name)[0]
        try:
            convert(os.path.join(src_dir, name), os.path.join(dst_dir, stem + ".cvr"), use_rgb565)
            print(f"[{i}/{len(files)}] {stem}.cvr")
        except Exception as e:
            print(f"[{i}/{len(files)}] skipped {name}: {e}")
    print(f"Done. Copy the contents of '{dst_dir}' to swiss/covers/ on your SD card.")


if __name__ == "__main__":
    main()
