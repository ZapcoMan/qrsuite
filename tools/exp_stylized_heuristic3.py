# -*- coding: utf-8 -*-
"""第三轮：把"小样本占比"与规模门槛结合，并加入更能区分圆点 vs 方块的形状特征。

发现：单看圆度占比会被"只有 1~8 个连通域"的图骗到（比值恒为 1.000），
也会被 61 个圆胞的模糊标准码逼近，所以必须同时约束"数量足够"。
"""
import os
import numpy as np
import cv2
from PIL import Image

N = 256
REAL = r'E:\学习\qcode\02-测试用例\real'
SETS = [r'E:\学习\qcode\02-测试用例\cases', r'E:\学习\qcode\02-测试用例\irregular']


def feats(path, block=21, C=8, min_area=4, max_area=600, circ_thr=0.65):
    g = np.asarray(Image.open(path).convert('L').resize((N, N), Image.BILINEAR))
    bw = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, block, C)
    ink = (bw > 0).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    small = []
    for i in range(1, n):
        a = int(st[i, cv2.CC_STAT_AREA])
        if a < min_area or a > max_area:
            continue
        w, h = int(st[i, cv2.CC_STAT_WIDTH]), int(st[i, cv2.CC_STAT_HEIGHT])
        ar = max(w, h) / max(1, min(w, h))
        cnts, _ = cv2.findContours((lab == i).astype(np.uint8),
                                   cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cnts:
            continue
        p = cv2.arcLength(cnts[0], True)
        if p <= 0:
            continue
        circ = 4 * np.pi * a / (p * p)
        small.append((a, circ, ar))
    if not small:
        return dict(n=0, ratio=0.0, circ_med=0.0, ar_med=0.0, area_cv=0.0)
    small = np.array(small)
    round_mask = (small[:, 1] >= circ_thr) & (small[:, 2] <= 2.0)
    return dict(
        n=len(small),
        ratio=float(round_mask.mean()),
        circ_med=float(np.median(small[round_mask, 1])) if round_mask.any() else 0.0,
        ar_med=float(np.median(small[round_mask, 2])) if round_mask.any() else 0.0,
        area_cv=float(np.std(small[:, 0]) / max(1e-6, np.mean(small[:, 0]))),
    )


def main():
    cfgs = [
        dict(block=21, C=8, min_area=4, max_area=600, circ_thr=0.65),
        dict(block=21, C=8, min_area=6, max_area=600, circ_thr=0.70),
        dict(block=15, C=6, min_area=4, max_area=600, circ_thr=0.70),
    ]
    for cfg in cfgs:
        print(f'\n#### {cfg}')
        rl = []
        for f in sorted(os.listdir(REAL)):
            if f.lower().endswith(('.jpg', '.png')):
                rl.append((f, feats(os.path.join(REAL, f), **cfg)))
        for f, d in rl:
            print(f'   REAL {f:26} n={d["n"]:4} ratio={d["ratio"]:.3f} '
                  f'circ_med={d["circ_med"]:.3f} ar_med={d["ar_med"]:.3f} area_cv={d["area_cv"]:.3f}')
        std = []
        for d0 in SETS:
            for f in sorted(os.listdir(d0)):
                if f.lower().endswith(('.png', '.jpg')):
                    std.append((f, feats(os.path.join(d0, f), **cfg)))
        std.sort(key=lambda x: -x[1]['ratio'])
        print('   标准样例 ratio 最高的 6 张：')
        for f, d in std[:6]:
            print(f'   STD  {f:26} n={d["n"]:4} ratio={d["ratio"]:.3f} '
                  f'circ_med={d["circ_med"]:.3f} ar_med={d["ar_med"]:.3f} area_cv={d["area_cv"]:.3f}')
        rn = min(d['n'] for _, d in rl)
        sn = max(d['n'] for _, d in std)
        print(f'   >> 私有码 n 最小={rn}  标准码 n 最大={sn}')
        for key in ('ratio', 'area_cv'):
            rv = [d[key] for _, d in rl]
            sv = [d[key] for _, d in std]
            print(f'   >> {key}: 私有码 {min(rv):.3f}~{max(rv):.3f}   '
                  f'标准码 {min(sv):.3f}~{max(sv):.3f}  '
                  f'{"可分" if min(rv) > max(sv) else "重叠"}')


if __name__ == '__main__':
    main()
