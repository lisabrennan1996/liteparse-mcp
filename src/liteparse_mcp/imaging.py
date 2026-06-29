"""
Pure-Python PNG bounding-box overlay.

No Pillow or other imaging dependency — uses only stdlib struct + zlib.
Coordinate system: PDF points (1 pt = 1/72 in), origin top-left.
Scale to pixels: pixels = points * (dpi / 72).
"""

import struct
import zlib


# ---------------------------------------------------------------------------
# Internal PNG decode / encode
# ---------------------------------------------------------------------------

def _pack_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return length + chunk_type + data + struct.pack(">I", crc)


def _png_to_rows(png_bytes: bytes):
    """Decode PNG → (width, height, list-of-rows of (R,G,B,A) tuples)."""
    import io
    buf = io.BytesIO(png_bytes)
    buf.read(8)  # signature

    chunk_len = struct.unpack(">I", buf.read(4))[0]
    buf.read(4)  # IHDR
    width, height = struct.unpack(">II", buf.read(8))
    buf.read(1)  # bit depth
    color_type = struct.unpack("B", buf.read(1))[0]
    buf.read(3 + 4)  # compression / filter / interlace / CRC

    idat = []
    while True:
        clen = struct.unpack(">I", buf.read(4))[0]
        ctype = buf.read(4)
        cdata = buf.read(clen)
        buf.read(4)
        if ctype == b"IDAT":
            idat.append(cdata)
        elif ctype == b"IEND":
            break

    raw = zlib.decompress(b"".join(idat))
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]

    rows = []
    idx = 0
    prev = [0] * (width * channels)
    for _ in range(height):
        filt = raw[idx]; idx += 1
        line = list(raw[idx: idx + width * channels]); idx += width * channels
        bpp = channels

        if filt == 0:
            row = line
        elif filt == 1:
            row = list(line)
            for i in range(bpp, len(row)):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
        elif filt == 2:
            row = [(a + b) & 0xFF for a, b in zip(line, prev)]
        elif filt == 3:
            row = list(line)
            for i in range(len(row)):
                a = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + (a + prev[i]) // 2) & 0xFF
        else:  # Paeth (4)
            row = list(line)
            for i in range(len(row)):
                a = row[i - bpp] if i >= bpp else 0
                b = prev[i]; c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pr = a if abs(p-a) <= abs(p-b) and abs(p-a) <= abs(p-c) else (b if abs(p-b) <= abs(p-c) else c)
                row[i] = (row[i] + pr) & 0xFF

        rgba_row = []
        for px in range(width):
            base = px * channels
            if channels == 4:
                rgba_row.append(tuple(row[base:base + 4]))
            elif channels == 3:
                rgba_row.append((row[base], row[base+1], row[base+2], 255))
            else:
                v = row[base]; rgba_row.append((v, v, v, 255))
        rows.append(rgba_row)
        prev = row

    return width, height, rows


def _rows_to_png(width: int, height: int, rows) -> bytes:
    """Encode list-of-rows of (R,G,B,A) → PNG bytes."""
    raw = bytearray()
    for row in rows:
        raw += b"\x00"  # filter type None
        for r, g, b, a in row:
            raw += bytes([r, g, b, a])

    compressed = zlib.compress(bytes(raw), 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _pack_chunk(b"IHDR", ihdr)
        + _pack_chunk(b"IDAT", compressed)
        + _pack_chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def draw_bounding_boxes(
    png_bytes: bytes,
    text_items: list,
    page_width_pts: float,
    page_height_pts: float,
    dpi: float = 150.0,
    color: tuple = (255, 100, 0, 160),
    border: int = 2,
) -> bytes:
    """
    Draw semi-transparent bounding-box borders on a PNG.

    Parameters
    ----------
    png_bytes        : Raw bytes of the source PNG.
    text_items       : Objects with .x .y .width .height attributes (PDF points).
    page_width_pts   : Page width in PDF points (used for coordinate validation).
    page_height_pts  : Page height in PDF points.
    dpi              : DPI used when the screenshot was rendered.
    color            : (R, G, B, A) highlight colour; A=160 ≈ 63% opacity.
    border           : Border thickness in pixels.

    Returns
    -------
    bytes – PNG with boxes drawn.
    """
    if not text_items:
        return png_bytes

    scale = dpi / 72.0

    try:
        img_w, img_h, rows = _png_to_rows(png_bytes)
    except Exception:
        return png_bytes  # fall back gracefully

    def clamp(v, lo, hi):
        return max(lo, min(hi, v))

    def blend(pixel):
        a = color[3] / 255.0
        return (
            int(color[0] * a + pixel[0] * (1 - a)),
            int(color[1] * a + pixel[1] * (1 - a)),
            int(color[2] * a + pixel[2] * (1 - a)),
            pixel[3],
        )

    for item in text_items:
        x0 = int(clamp(item.x * scale,              0, img_w - 1))
        y0 = int(clamp(item.y * scale,              0, img_h - 1))
        x1 = int(clamp((item.x + item.width) * scale,  0, img_w - 1))
        y1 = int(clamp((item.y + item.height) * scale, 0, img_h - 1))

        for px in range(x0, x1 + 1):
            for dy in range(border):
                if y0 + dy < img_h:
                    rows[y0 + dy][px] = blend(rows[y0 + dy][px])
                if y1 - dy >= 0:
                    rows[y1 - dy][px] = blend(rows[y1 - dy][px])

        for py in range(y0, y1 + 1):
            for dx in range(border):
                if x0 + dx < img_w:
                    rows[py][x0 + dx] = blend(rows[py][x0 + dx])
                if x1 - dx >= 0:
                    rows[py][x1 - dx] = blend(rows[py][x1 - dx])

    return _rows_to_png(img_w, img_h, rows)
