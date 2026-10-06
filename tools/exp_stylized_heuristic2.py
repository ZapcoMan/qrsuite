# -*- coding: utf-8 -*-
"""第二轮：用自适应阈值 + 去背景统计，找出对"海报里的样式化码"稳健且不误伤的判据。"""
import os

import numpy as np
import cv2
from PIL import Image

N = 256
MIN_A, MAX_A = 3, 400


def stats(path, block=31, C=10, min_area=3, max_area=400, circ_thr=0.65):
    im = Image.open(path).convert('L').resize((N, N), Image.BILINEAR)
    g = np.asarray(im)
    # 自适应阈值：对海报背景（大片同色）免疫，比全局 Otsu 稳
    bw = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, block, C)
    ink = bw > 0
    n, lab, st, cent = cv2.connectedComponentsWithStats(
        ink.astype(np.uint8), connectivity=8)
    small = round_ = 0
    for i in range(1, n):
        area = int(st[i, cv2.CC_STAT_AREA])
        if area < min_area or area > max_area:
            continue
        w, h = int(st[i, cv2.CC_STAT_WIDTH]), int(st[i, cv2.CC_STAT_HEIGHT])
        if max(w, h) > 3 * min(w, h):
            continue
        m = (lab == i).astype(np.uint8)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cnts:
            continue
        perim = cv2.arcLength(cnts[0], True)
        if perim <= 0:
            continue
        small += 1
        circ = 4 * np.pi * area / (perim * perim)
        if circ >= circ_thr:
            round_ += 1
    return small, round_, (round_ / small if small else 0.0)


REAL = r'E:\学习\qcode\02-测试用例\real'
SETS = [r'E:\学习\qcode\02-测试用例\cases', r'E:\学习\qcode\02-测试用例\irregular']


def scan(tag, block, C, min_area, max_area, circ_thr):
    print(f'\n### {tag}  block={block} C={C} area={min_area}-{max_area} circ>={circ_thr}')
    print('  -- 真实私有码 --')
    real_res = []
    for f in sorted(os.listdir(REAL)):
        if not f.lower().endswith(('.jpg', '.png')):
            continue
        s, r, ratio = stats(os.path.join(REAL, f), block, C, min_area, max_area, circ_thr)
        real_res.append((f, s, r, ratio))
        print(f'     {f:28} small={s:4} round={r:4} ratio={ratio:.3f}')
    print('  -- 标准样例（误伤检查）--')
    fp, total, worst = 0, 0, []
    for d in SETS:
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(('.png', '.jpg')):
                continue
            total += 1
            s, r, ratio = stats(os.path.join(d, f), block, C, min_area, max_area, circ_thr)
            worst.append((ratio, f, s))
    worst.sort(reverse=True)
    print(f'     标准样例 {total} 张，圆度占比最高的 5 张：')
    for ratio, f, s in worst[:5]:
        print(f'       {f:34} ratio={ratio:.3f} small={s}')
    lo = min(x[3] for x in real_res)
    hi = worst[0][0]
    print(f'  >> 私有码最低占比 {lo:.3f}  标准码最高占比 {hi:.3f}  '
          f'{"可分" if lo > hi else "不可分"}')


if __name__ == '__main__':
    scan('A', 31, 10, 3, 400, 0.65)
    scan('B', 21, 8, 3, 800, 0.60)
    scan('C', 41, 12, 4, 600, 0.70)
