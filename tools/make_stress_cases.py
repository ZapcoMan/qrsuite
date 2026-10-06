# -*- coding: utf-8 -*-
"""压力样例矩阵：找出当前引擎真正的失效边界（比"看着像"更重要）。

现实里扫不出来的组合通常是：
  低对比/彩色  +  截图级模糊（BGR 下采样再插值）  +  JPEG 二次压缩
  高密度码     +  模块变小                          +  中心大 logo
  样式化模块（圆角/图形化）会让传统检测器失效
"""
import io
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw
import segno


def qr_png(payload: str, box: int, ec: str = 'h', dark='#101010', light='#FFFFFF') -> Image.Image:
    q = segno.make(payload, error=ec)
    b = io.BytesIO()
    q.save(b, kind='png', scale=box, border=4, dark=dark, light=light)
    b.seek(0)
    return Image.open(b).convert('RGB')


def logo(im: Image.Image, frac: float, fg='#5B3FD6') -> Image.Image:
    w, h = im.size
    d = int(min(w, h) * frac)
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(lay)
    cx, cy = w // 2, h // 2
    box = [cx - d // 2, cy - d // 2, cx + d // 2, cy + d // 2]
    pad = max(2, d // 12)
    dr.ellipse([box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad], fill='#FFFFFF')
    dr.ellipse(box, fill=fg)
    return Image.alpha_composite(im.convert('RGBA'), lay).convert('RGB')


def recolor(im: Image.Image, dark=(60, 70, 130), light=(235, 238, 245)) -> Image.Image:
    """低对比彩色：模块深蓝灰 / 底浅灰蓝。"""
    a = np.asarray(im).astype(np.float32) / 255.0
    g = a.mean(axis=2, keepdims=True)
    out = g * np.array(dark, np.float32) + (1 - g) * np.array(light, np.float32)
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def blur_shrink(im: Image.Image, side: int, jpeg_q: int = 0) -> Image.Image:
    """截图链路：缩到 side -> 放大回来 -> 高斯模糊 ->（可选）JPEG 压缩。"""
    small = im.resize((side, side), Image.LANCZOS)
    back = small.resize(im.size, Image.BICUBIC)
    arr = np.asarray(back)
    k = max(1, im.size[0] // 300)
    arr = cv2.GaussianBlur(arr, (k * 2 + 1, k * 2 + 1), 0)
    out = Image.fromarray(arr)
    if jpeg_q:
        b = io.BytesIO()
        out.save(b, 'JPEG', quality=jpeg_q)
        b.seek(0)
        out = Image.open(b).convert('RGB')
    return out


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else r'E:\学习\qcode\02-测试用例\irregular'
    os.makedirs(out, exist_ok=True)
    short = 'https://v.douyin.com/iRNBho6u/'
    long = ('https://qr.weixin.qq.com/reward/abcdefghijklmnopqrstuvwxyz0123456789'
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ?ver=2&ts=1730000000000')
    made = []

    def save(im, name):
        p = os.path.join(out, name)
        im.save(p)
        made.append(name)

    s_big = qr_png(short, 12)          # 约 500px
    s_small = qr_png(short, 5)         # 约 230px
    l_big = qr_png(long, 9)            # 约 800px
    l_small = qr_png(long, 4)          # 约 380px

    # 清晰基线
    save(s_big, 'j_short_clean.png')
    save(l_big, 'j_long_clean.png')

    # 截图链路：模糊 + JPEG
    save(blur_shrink(s_big, 300, 60), 'j_short_blur300_jpeg60.png')
    save(blur_shrink(s_big, 200, 40), 'j_short_blur200_jpeg40.png')
    save(blur_shrink(l_big, 420, 55), 'j_long_blur420_jpeg55.png')
    save(blur_shrink(l_big, 300, 40), 'j_long_blur300_jpeg40.png')

    # 低对比彩色
    save(recolor(s_big), 'j_short_lowcontrast.png')
    save(recolor(l_big), 'j_long_lowcontrast.png')
    save(blur_shrink(recolor(s_big), 260, 50), 'j_short_lc_blur_jpeg.png')
    save(blur_shrink(recolor(l_big), 360, 50), 'j_long_lc_blur_jpeg.png')

    # 中心大 logo（含白圈）
    save(logo(s_big, 0.26), 'j_short_logo26.png')
    save(logo(l_big, 0.28), 'j_long_logo28.png')

    # 组合拳：小尺寸 + 低对比 + logo + 模糊 JPEG（最可能崩）
    save(blur_shrink(logo(recolor(s_small), 0.24), 180, 45), 'j_short_hard.png')
    save(blur_shrink(logo(recolor(l_small), 0.26), 260, 45), 'j_long_hard.png')

    # 底部被裁掉一块（模拟不完整截图）
    hi = qr_png(long, 9)
    w, h = hi.size
    save(hi.crop((0, 0, w, int(h * 0.80))), 'j_long_cropped20.png')
    save(hi.crop((0, int(h * 0.10), w, h)), 'j_long_cropped_top.png')

    print(f'生成 {len(made)} 个压力样例 -> {out}')
    for m in made:
        print('  ', m)


if __name__ == '__main__':
    main()
