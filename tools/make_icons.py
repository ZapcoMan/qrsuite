# -*- coding: utf-8 -*-
"""生成 PWA 图标（192 / 512 / apple-touch 180 / favicon 32），纯 PIL 绘制，无需设计资源。

用法: python tools/make_icons.py
输出: docs/icon-512.png, docs/icon-192.png, docs/apple-touch-icon.png, docs/favicon-32.png
"""
import os, random
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'docs')
S = 512


def rounded_mask(size, radius):
    m = Image.new('L', (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def gradient(size, c1, c2):
    g = Image.new('RGB', (size, size))
    d = ImageDraw.Draw(g)
    for y in range(size):
        t = y / (size - 1)
        d.line([(0, y), (size, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    return g


def draw_finder(d, x, y, cell, color):
    """画定位角（7x7 模块）"""
    d.rectangle([x, y, x + 7 * cell - 1, y + 7 * cell - 1], fill=color)
    d.rectangle([x + cell, y + cell, x + 6 * cell - 1, y + 6 * cell - 1], fill='white')
    d.rectangle([x + 2 * cell, y + 2 * cell, x + 5 * cell - 1, y + 5 * cell - 1], fill=color)


def main():
    os.makedirs(OUT, exist_ok=True)
    icon = gradient(S, (62, 166, 255), (49, 196, 141)).convert('RGBA')
    icon.putalpha(rounded_mask(S, 110))

    pad, radius = 74, 44
    plate = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle([pad, pad, S - pad, S - pad], radius=radius, fill=(255, 255, 255, 255))
    icon = Image.alpha_composite(icon, plate)

    inner = S - 2 * pad - 52
    cell = inner / 21.0
    ox = oy = pad + 26
    dark = (16, 24, 38, 255)
    d = ImageDraw.Draw(icon)
    for (cx, cy) in ((0, 0), (14, 0), (0, 14)):
        draw_finder(d, ox + cx * cell, oy + cy * cell, cell, dark)

    rnd = random.Random(20261006)
    for ry in range(21):
        for rx in range(21):
            if (rx < 8 and ry < 8) or (rx > 12 and ry < 8) or (rx < 8 and ry > 12):
                continue                                     # 让开三个定位角
            if rnd.random() < 0.46:
                x0, y0 = ox + rx * cell, oy + ry * cell
                d.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=dark)

    icon.convert('RGB').save(os.path.join(OUT, 'icon-512.png'))
    icon.resize((192, 192), Image.LANCZOS).convert('RGB').save(os.path.join(OUT, 'icon-192.png'))
    icon.resize((180, 180), Image.LANCZOS).convert('RGB').save(os.path.join(OUT, 'apple-touch-icon.png'))
    icon.resize((32, 32), Image.LANCZOS).convert('RGB').save(os.path.join(OUT, 'favicon-32.png'))
    for f in ('icon-512.png', 'icon-192.png', 'apple-touch-icon.png', 'favicon-32.png'):
        p = os.path.join(OUT, f)
        print(f'{f:24s} {os.path.getsize(p)//1024:4d} KB')


if __name__ == '__main__':
    main()
