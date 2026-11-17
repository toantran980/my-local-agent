"""Generate small, synthetic PNG fixtures for the local vision evaluation."""

import struct
import zlib
from pathlib import Path

WIDTH = 640
HEIGHT = 400
WHITE = (255, 255, 255)
BLACK = (25, 30, 35)
GRAY = (215, 220, 225)
BLUE = (55, 120, 210)
ORANGE = (235, 145, 45)
GREEN = (65, 160, 95)
RED = (210, 55, 55)

FONT = {
    " ": ("00000",) * 7,
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
}


class Canvas:
    def __init__(self):
        self.pixels = bytearray(WHITE * (WIDTH * HEIGHT))

    def pixel(self, x, y, color):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            offset = (y * WIDTH + x) * 3
            self.pixels[offset : offset + 3] = bytes(color)

    def rect(self, x1, y1, x2, y2, color):
        for y in range(max(0, y1), min(HEIGHT, y2)):
            for x in range(max(0, x1), min(WIDTH, x2)):
                self.pixel(x, y, color)

    def line(self, x1, y1, x2, y2, color):
        dx = abs(x2 - x1)
        dy = -abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        error = dx + dy
        while True:
            self.pixel(x1, y1, color)
            if x1 == x2 and y1 == y2:
                break
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x1 += sx
            if doubled <= dx:
                error += dx
                y1 += sy

    def text(self, x, y, value, scale, color=BLACK):
        for character in value:
            glyph = FONT[character]
            for row, pattern in enumerate(glyph):
                for column, bit in enumerate(pattern):
                    if bit == "1":
                        self.rect(
                            x + column * scale,
                            y + row * scale,
                            x + (column + 1) * scale,
                            y + (row + 1) * scale,
                            color,
                        )
            x += 6 * scale

    def circle(self, center_x, center_y, radius, color):
        for y in range(center_y - radius, center_y + radius + 1):
            for x in range(center_x - radius, center_x + radius + 1):
                if (x - center_x) ** 2 + (y - center_y) ** 2 <= radius**2:
                    self.pixel(x, y, color)

    def triangle(self, points, color):
        (ax, ay), (bx, by), (cx, cy) = points
        for y in range(min(ay, by, cy), max(ay, by, cy) + 1):
            for x in range(min(ax, bx, cx), max(ax, bx, cx) + 1):
                first = (x - bx) * (ay - by) - (ax - bx) * (y - by)
                second = (x - cx) * (by - cy) - (bx - cx) * (y - cy)
                third = (x - ax) * (cy - ay) - (cx - ax) * (y - ay)
                if (first >= 0 and second >= 0 and third >= 0) or (
                    first <= 0 and second <= 0 and third <= 0
                ):
                    self.pixel(x, y, color)

    def save(self, path):
        raw = b"".join(
            b"\x00" + self.pixels[y * WIDTH * 3 : (y + 1) * WIDTH * 3]
            for y in range(HEIGHT)
        )

        def chunk(kind, data):
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )
        path.write_bytes(png)


def make_ocr_image(path):
    canvas = Canvas()
    canvas.rect(28, 28, 612, 372, (245, 247, 249))
    canvas.rect(40, 40, 600, 360, WHITE)
    canvas.text(72, 76, "RECEIPT 817", 5)
    canvas.line(72, 135, 565, 135, GRAY)
    canvas.text(72, 170, "ITEM TEA", 4)
    canvas.text(72, 250, "TOTAL $18.75", 4)
    canvas.save(path)


def make_chart_image(path):
    canvas = Canvas()
    canvas.text(190, 25, "UNITS SOLD", 4)
    left, top, right, bottom = 115, 105, 570, 325
    for value in (0, 2, 4, 6):
        y = bottom - value * 30
        canvas.line(left, y, right, y, GRAY)
        canvas.text(65, y - 7, str(value), 2)
    canvas.line(left, top, left, bottom, BLACK)
    canvas.line(left, bottom, right, bottom, BLACK)
    bars = (("A", 3, 175, BLUE), ("B", 6, 315, ORANGE), ("C", 2, 455, GREEN))
    for label, value, x, color in bars:
        bar_top = bottom - value * 30
        canvas.rect(x, bar_top, x + 75, bottom, color)
        canvas.text(x + 24, bar_top - 28, str(value), 3)
        canvas.text(x + 28, bottom + 18, label, 3)
    canvas.save(path)


def make_objects_image(path):
    canvas = Canvas()
    for center_x in (135, 320, 505):
        canvas.circle(center_x, 115, 42, RED)
    canvas.rect(170, 245, 250, 325, BLUE)
    canvas.rect(390, 245, 470, 325, BLUE)
    canvas.triangle(((320, 225), (270, 325), (370, 325)), GREEN)
    canvas.save(path)


def main():
    image_dir = Path(__file__).parent / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    make_ocr_image(image_dir / "ocr-receipt.png")
    make_chart_image(image_dir / "bar-chart.png")
    make_objects_image(image_dir / "objects.png")


if __name__ == "__main__":
    main()
