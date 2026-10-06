# -*- coding: utf-8 -*-
"""量化几种廉价候选改进对失败样例的实际收益（先测量，再决定改哪里）。"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np
from PIL import Image
import zxingcpp


def load(path):
    im = Image.open(path).convert('RGB')
    rgb = np.asarray(im)
    gray = np.dot(rgb[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
    return rgb[:, :, ::-1].copy(), gray


def try_decode(color, gray=None):
    try:
        for r in zxingcpp.read_barcodes(color):
            t = getattr(r, 'text', '') or ''
            if t:
                return t
    except Exception:
        pass
    return None


VARIANTS = {}


def variant(name):
    def deco(fn):
        VARIANTS[name] = fn
        return fn
    return deco


@variant('baseline')
def v_baseline(color, gray):
    return [('原图', color)]


@variant('up2')
def v_up2(color, gray):
    g = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return [('放大2倍', cv2.cvtColor(g, cv2.COLOR_GRAY2BGR))]


@variant('up3')
def v_up3(color, gray):
    g = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    return [('放大3倍', cv2.cvtColor(g, cv2.COLOR_GRAY2BGR))]


@variant('clahe')
def v_clahe(color, gray):
    eq = cv2.createCLAHE(3.0, (8, 8)).apply(gray)
    return [('CLAHE', cv2.cvtColor(eq, cv2.COLOR_GRAY2BGR))]


@variant('norm')
def v_norm(color, gray):
    n = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    return [('对比拉伸', cv2.cvtColor(n, cv2.COLOR_GRAY2BGR))]


@variant('adap')
def v_adap(color, gray):
    a = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                              cv2.THRESH_BINARY, 25, 8)
    return [('自适应阈值', cv2.cvtColor(a, cv2.COLOR_GRAY2BGR))]


@variant('adap_lo')
def v_adap_lo(color, gray):
    a = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                              cv2.THRESH_BINARY, 15, 4)
    return [('自适应阈值(小窗)', cv2.cvtColor(a, cv2.COLOR_GRAY2BGR))]


@variant('pad_white')
def v_pad(color, gray):
    """四周补白：被裁掉的码可能只差静区，补上静区常常能救回来。"""
    p = cv2.copyMakeBorder(color, 60, 60, 60, 60, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    return [('补白边', p)]


@variant('pad_white_up2')
def v_pad_up(color, gray):
    p = cv2.copyMakeBorder(color, 60, 60, 60, 60, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    g = cv2.resize(p, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return [('补白边+放大2倍', g)]


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else r'E:\学习\qcode\02-测试用例\irregular'
    files = sorted(f for f in os.listdir(d) if f.endswith('.png'))
    table = {}
    for f in files:
        path = os.path.join(d, f)
        color, gray = load(path)
        row = {}
        for name, fn in VARIANTS.items():
            hit = None
            for _, img in fn(color, gray):
                hit = try_decode(img)
                if hit:
                    break
            row[name] = hit
        table[f] = row

    names = list(VARIANTS)
    print(f'{"文件":34}' + ''.join(f'{n[:9]:>11}' for n in names))
    totals = {n: 0 for n in names}
    for f in files:
        cells = []
        for n in names:
            ok = table[f][n] is not None
            totals[n] += 1 if ok else 0
            cells.append('OK' if ok else '.')
        print(f'{f:34}' + ''.join(f'{c:>11}' for c in cells))
    print(f'{"合计命中":34}' + ''.join(f'{totals[n]:>11}' for n in names))
    print(f'\n总样例 {len(files)}')
    base = totals['baseline']
    print('相对 baseline 的增量：')
    for n in names:
        if n == 'baseline':
            continue
        d_ = totals[n] - base
        print(f'  {n:16} {totals[n]:>3}  ({d_:+d})')


if __name__ == '__main__':
    main()
