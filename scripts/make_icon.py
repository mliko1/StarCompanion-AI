# -*- coding: utf-8 -*-
"""生成产品图标 assets/xingban.ico。

优先使用 assets/app_icon.png（或 .jpg/.jpeg/.webp）作为图标源图；
没有源图时回退到内置的蓝底白星图标。
"""

import math
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
TARGET = os.path.join(ASSETS, "xingban.ico")
SOURCE_NAMES = ("app_icon.png", "app_icon.jpg", "app_icon.jpeg", "app_icon.webp")
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def star_points(cx, cy, outer, inner, count=5, start=-90):
    pts = []
    for i in range(count * 2):
        angle = math.radians(start + i * 180 / count)
        radius = outer if i % 2 == 0 else inner
        pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return pts


def find_source():
    for name in SOURCE_NAMES:
        path = os.path.join(ASSETS, name)
        if os.path.exists(path):
            return path
    return None


def builtin_icon():
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((12, 12, 244, 244), radius=56, fill=(11, 99, 206, 255))
    draw.rounded_rectangle((24, 24, 232, 232), radius=46,
                           outline=(150, 195, 245, 255), width=3)
    draw.polygon(star_points(128, 124, 76, 33), fill=(255, 255, 255, 255))
    draw.ellipse((182, 44, 210, 72), fill=(255, 190, 80, 255))
    return img


def from_source(path):
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2,
                    (w + side) // 2, (h + side) // 2))
    return img.resize((256, 256), Image.LANCZOS)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    source = find_source()
    img = from_source(source) if source else builtin_icon()
    img.save(TARGET, format="ICO", sizes=ICO_SIZES)
    print("已生成图标:", TARGET)
    if source:
        print("源图:", source)


if __name__ == "__main__":
    main()
