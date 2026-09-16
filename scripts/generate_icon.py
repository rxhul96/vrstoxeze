"""Write assets/nifty.ico — dark desk + teal mark. No Pillow required."""
from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "nifty.ico"


def _rgba(w: int, h: int) -> bytes:
    bg = (11, 14, 17, 255)
    teal = (46, 196, 182, 255)
    amber = (212, 160, 23, 255)
    rows = []
    for y in range(h):
        row = bytearray()
        for x in range(w):
            nx = (x + 0.5) / w
            ny = (y + 0.5) / h
            # Teal triangle pointing up (Command Desk mark).
            in_tri = ny > 0.22 and ny < 0.82 and abs(nx - 0.5) < (ny - 0.22) * 0.62
            bar = 0.78 < ny < 0.88 and 0.18 < nx < 0.82
            if in_tri:
                row += bytes(teal)
            elif bar:
                row += bytes(amber)
            else:
                row += bytes(bg)
        rows.append(bytes(row))
    return b"".join(reversed(rows))  # BMP is bottom-up


def _bmp(w: int, h: int) -> bytes:
    pixels = _rgba(w, h)
    # BITMAPINFOHEADER + BGRA XOR bitmap + 1-bit AND mask
    xor = pixels  # already BGRA-like? we stored RGBA — ICO wants BGRA
    bgra = bytearray()
    for i in range(0, len(pixels), 4):
        r, g, b, a = pixels[i : i + 4]
        bgra += bytes((b, g, r, a))
    row_and = ((w + 31) // 32) * 4
    and_mask = bytes(row_and * h)
    dib = struct.pack(
        "<IiiHHIIiiII",
        40,
        w,
        h * 2,
        1,
        32,
        0,
        len(bgra),
        0,
        0,
        0,
        0,
    )
    return dib + bytes(bgra) + and_mask


def write_ico(path: Path, sizes=(16, 32, 48, 256)) -> None:
    images = []
    for s in sizes:
        if s > 64:
            # skip huge uncompressed 256 for a tiny mark; 48 is enough
            continue
        images.append((s, _bmp(s, s)))
    count = len(images)
    offset = 6 + 16 * count
    buf = bytearray(struct.pack("<HHH", 0, 1, count))
    blobs = b""
    for s, data in images:
        buf += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(buf) + blobs)


if __name__ == "__main__":
    write_ico(OUT)
    print("wrote", OUT, "bytes", OUT.stat().st_size)
