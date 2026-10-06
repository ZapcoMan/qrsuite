# -*- coding: utf-8 -*-
"""构造"不规则二维码"回归样例：模拟抖音主页码 / 微信赞赏码的失败特征。

失败特征（按现实观察）：
  1. 中心大 logo：微信赞赏码中心是头像圆盘，抖音主页码中心也有 logo，遮挡中心 15%~32%
  2. 彩色 + 低对比：模块不是纯黑，底不是纯白，常有浅色渐变
  3. 二次压缩/缩放：截图或转发后码只有几百像素，模块边缘糊
  4. 组合：大 logo + 缩放，这是最容易崩的一类

用法：python tools/make_irregular_cases.py <输出目录>
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
import segno


def make_qr(payload: str, box: int = 10, border: int = 4, ec: str = 'h') -> Image.Image:
    q = segno.make(payload, error=ec)
    import io
    buf = io.BytesIO()
    q.save(buf, kind='png', scale=box, border=border, dark='#101010', light='#FFFFFF')
    buf.seek(0)
    return Image.open(buf).convert('RGB')


def overlay_logo(im: Image.Image, frac: float, shape: str = 'disc',
                 fg='#5B3FD6', ring='#FFFFFF') -> Image.Image:
    """在正中心覆盖一个 logo；frac 是相对码边长的直径占比。"""
    if frac <= 0:
        return im
    w, h = im.size
    d = int(min(w, h) * frac)
    cx, cy = w // 2, h // 2
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    box = [cx - d // 2, cy - d // 2, cx + d // 2, cy + d // 2]
    # 白色底圈（模拟赞赏码那圈白边），让 logo 与码点之间有对比过渡
    pad = max(2, d // 14)
    dr.ellipse([box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad], fill=ring)
    if shape == 'disc':
        dr.ellipse(box, fill=fg)
    else:
        dr.rounded_rectangle(box, radius=max(2, d // 6), fill=fg)
    return Image.alpha_composite(im.convert('RGBA'), layer).convert('RGB')


def recolor(im: Image.Image, dark=(20, 30, 90), light=(245, 245, 252)) -> Image.Image:
    """把黑白码换成彩色：模块偏深蓝、底色偏冷白（低对比）。"""
    a = np.asarray(im).astype(np.float32) / 255.0
    g = a.mean(axis=2, keepdims=True)
    out = g * np.array(dark, np.float32) + (1 - g) * np.array(light, np.float32)
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def soften_and_shrink(im: Image.Image, side: int) -> Image.Image:
    """模拟截图/转发：缩到 side 像素再插值回来，引入模糊与锯齿。"""
    small = im.resize((side, side), Image.LANCZOS)
    return small


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else r'E:\学习\qcode\02-测试用例\irregular'
    os.makedirs(out, exist_ok=True)
    payload = 'https://v.douyin.com/iRNBho6u/'
    made = []

    def save(im: Image.Image, name: str):
        p = os.path.join(out, name)
        im.save(p)
        made.append(name)

    # 基线：干净大字
    base = make_qr(payload, box=12)
    save(base, 'i_clean.png')

    # 中心 logo 递增遮挡
    for frac, tag in ((0.15, '15'), (0.22, '22'), (0.30, '30')):
        save(overlay_logo(base, frac), f'i_logo{tag}.png')

    # 彩色低对比
    col = recolor(base)
    save(col, 'i_color.png')
    save(overlay_logo(col, 0.22, fg='#3B2A8C'), 'i_color_logo.png')

    # 缩到截图尺寸（模块变糊）+ logo —— 最崩的一类
    small = soften_and_shrink(base, 420)
    save(small, 'i_small420.png')
    save(overlay_logo(small, 0.22), 'i_small_logo.png')
    save(soften_and_shrink(base, 300), 'i_small300.png')

    # 高密度长内容（微信赞赏码/小程序码风格：内容长、模块多）
    long_qr = make_qr('https://qr.weixin.qq.com/reward/abcdefghijklmnopqrstuvwxyz0123456789'
                      'ABCDEFGHIJKLMNOPQRSTUVWXYZ?ver=2&ts=1730000000000', box=9)
    save(long_qr, 'i_dense.png')
    save(overlay_logo(long_qr, 0.26), 'i_dense_logo.png')

    print(f'生成 {len(made)} 个样例 -> {out}')
    for m in made:
        print('  ', m)


if __name__ == '__main__':
    main()
