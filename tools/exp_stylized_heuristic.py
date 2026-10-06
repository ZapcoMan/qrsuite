# -*- coding: utf-8 -*-
"""离线验证 Android 端"样式化码判定"启发式（与 MainActivity 同逻辑）。

要求：对两张真实私有码判 True，对全部标准样例判 False（不能误伤）。
"""
import os
import sys

import numpy as np
from PIL import Image

N = 256
MIN_A, MAX_A = 3, 400


def otsu(gray):
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    total = gray.size
    sum_all = np.dot(np.arange(256), hist)
    sum_b = 0.0
    w_b = 0
    best, thr = -1.0, 128
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        between = w_b * w_f * (m_b - m_f) ** 2
        if between > best:
            best, thr = between, t
    return thr


def heavy_stylized(path):
    im = Image.open(path).convert('L').resize((N, N), Image.BILINEAR)
    gray = np.asarray(im, dtype=np.int32)
    thr = otsu(gray)
    ink = gray <= thr
    ink_ratio = ink.mean()
    if ink_ratio < 0.015 or ink_ratio > 0.55:
        return False, f'墨量异常 {ink_ratio:.3f}'

    # 8 邻域连通域
    lab = np.full((N, N), -1, np.int32)
    small = round_ = 0
    ys, xs = np.nonzero(ink)
    for sy, sx in zip(ys, xs):
        if lab[sy, sx] >= 0:
            continue
        stack = [(sy, sx)]
        lab[sy, sx] = 1
        area = perim = 0
        minx, maxx, miny, maxy = N, -1, N, -1
        while stack:
            y, x = stack.pop()
            area += 1
            minx, maxx = min(minx, x), max(maxx, x)
            miny, maxy = min(miny, y), max(maxy, y)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if nx < 0 or ny < 0 or nx >= N or ny >= N:
                        perim += 1
                        continue
                    if not ink[ny, nx]:
                        perim += 1
                    elif lab[ny, nx] < 0:
                        lab[ny, nx] = 1
                        stack.append((ny, nx))
        if area < MIN_A or area > MAX_A:
            continue
        small += 1
        bw, bh = maxx - minx + 1, maxy - miny + 1
        if max(bw, bh) > 3 * min(bw, bh):
            continue
        circ = 4 * np.pi * area / (perim * perim) if perim else 0
        if circ >= 0.65:
            round_ += 1

    verdict = small >= 25 and round_ >= 0.72 * small
    return verdict, f'small={small} round={round_} ratio={round_/max(1,small):.2f}'


def main():
    real = r'E:\学习\qcode\02-测试用例\real'
    print('===== 真实私有码（期望 True）=====')
    for f in sorted(os.listdir(real)):
        if f.lower().endswith(('.jpg', '.png')):
            v, why = heavy_stylized(os.path.join(real, f))
            print(f'  {"STYLIZED" if v else "normal  "}  {f:28} {why}')

    print('\n===== 标准/合成样例（期望全部 False）=====')
    bad = 0
    total = 0
    for d in (r'E:\学习\qcode\02-测试用例\cases',
              r'E:\学习\qcode\02-测试用例\irregular'):
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(('.png', '.jpg')):
                continue
            total += 1
            v, why = heavy_stylized(os.path.join(d, f))
            if v:
                bad += 1
                print(f'  !! 误判为样式化: {f}  {why}')
    print(f'  标准样例 {total} 张，误判 {bad} 张')
    print('  结论:', 'PASS（无误伤）' if bad == 0 else f'FAIL（{bad} 张误伤，需收紧阈值）')


if __name__ == '__main__':
    main()
