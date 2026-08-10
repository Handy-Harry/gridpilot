"""Generate dependency-free GridPilot PNG brand assets."""

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).parents[1]
BRAND = ROOT / "custom_components" / "gridpilot" / "brand"


def _inside_polygon(x: int, y: int, points: list[tuple[int, int]]) -> bool:
    inside = False
    previous = points[-1]
    for current in points:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def _chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return (
        struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))
    )


def generate(path: Path, size: int) -> None:
    """Generate one square RGBA PNG."""
    scale = size / 256
    bolt = [
        (124, 75),
        (88, 137),
        (119, 137),
        (108, 181),
        (169, 105),
        (134, 105),
        (149, 75),
    ]
    rows = bytearray()
    for output_y in range(size):
        rows.append(0)
        y = int(output_y / scale)
        for output_x in range(size):
            x = int(output_x / scale)
            color = (16, 42, 67, 255)
            battery_border = (
                34 <= x <= 214
                and 62 <= y <= 194
                and (x <= 48 or x >= 200 or y <= 76 or y >= 180)
            )
            terminal = 214 <= x <= 231 and 105 <= y <= 151
            if battery_border or terminal:
                color = (215, 227, 237, 255)
            if _inside_polygon(x, y, bolt):
                color = (245, 158, 11, 255)
            rows.extend(color)

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", header)
    png += _chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
    png += _chunk(b"IEND", b"")
    path.write_bytes(png)


if __name__ == "__main__":
    BRAND.mkdir(exist_ok=True)
    generate(BRAND / "icon.png", 256)
    generate(BRAND / "logo.png", 512)
