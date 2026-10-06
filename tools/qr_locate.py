# -*- coding: utf-8 -*-
"""二维码定位符查找（轮廓层级法）—— 带中间量输出，便于验证而非盲猜。

标准 QR 定位符 = 7x7 模块的"黑框-白环-黑实心"结构，在二值图上表现为
三层嵌套轮廓。用 RETR_TREE + 层级链天然就能筛出来，比行游程扫描稳。
"""
from __future__ import annotations

import sys

import numpy as np
import cv2
from PIL import Image


def find_finders(gray: np.ndarray, debug: bool = False):
    """返回 [(cx, cy, size), ...]，size 为定位符外框边长（像素）。"""
    # 局部自适应二值化：对 LCD/照片的不均匀光照比全局 Otsu 稳
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 25, 10)
    # 轻微形态学闭运算，把 LCD 像素点之间的缝隙补上
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE,
                          cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    cnts, hier = cv2.findContours(bw, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None:
        return []
    hier = hier[0]
    out = []
    for i, c in enumerate(cnts):
        area = cv2.contourArea(c)
        if area < 25:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if w == 0 or h == 0:
            continue
        ar = w / float(h)
        if not (0.7 <= ar <= 1.4):          # 定位符近似正方形
            continue
        # 三层嵌套：自己 -> 父 -> 祖父 都存在
        p1 = hier[i][3]                      # 父
        if p1 < 0:
            continue
        p2 = hier[p1][3]                     # 祖父
        if p2 < 0:
            continue
        # 外层是实心方块区域（填充率较高），内层也应有合理填充
        fill_self = area / float(w * h)
        if fill_self < 0.45:
            continue
        # 父轮廓（白环）应比自身大一圈
        px, py, pw, ph = cv2.boundingRect(cnts[p1])
        if pw <= w or ph <= h:
            continue
        ratio = pw / float(w)
        if not (1.5 <= ratio <= 4.0):        # 白环宽度比例
            continue
        size = float((pw + ph) / 2.0)
        out.append((x + w / 2.0, y + h / 2.0, size))
        if debug:
            print(f'    finder 候选: 中心({x + w/2:.0f},{y + h/2:.0f}) '
                  f'内框{w}x{h} 外框{pw}x{ph} size={size:.0f} ratio={ratio:.2f} fill={fill_self:.2f}')

    # 合并靠得很近的重复检测（同一物理定位符会被内外两层各命中一次）
    merged = []
    for cx, cy, s in sorted(out, key=lambda t: -t[2]):
        for m in merged:
            d = ((m[0] - cx) ** 2 + (m[1] - cy) ** 2) ** 0.5
            if d < max(8.0, 0.6 * max(s, m[2])):
                break
        else:
            merged.append([cx, cy, s])
    return [(m[0], m[1], m[2]) for m in merged]


def qr_box_from_three(fps, gray_shape, quiet_ratio=0.12):
    """由 3 个定位符中心算整码包围盒（外扩静区）。"""
    pts = np.array([[p[0], p[1]] for p in fps], np.float32)
    sizes = [p[2] for p in fps]
    x0, y0 = pts[:, 0].min(), pts[:, 1].min()
    x1, y1 = pts[:, 0].max(), pts[:, 1].max()
    span = max(x1 - x0, y1 - y0)
    # 定位符中心到码边缘：定位符中心在距边缘 3.5 模块处，码边长≈(跨度+7模块)
    mod = float(np.median(sizes)) / 7.0
    side = span + 7 * mod
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    pad = side * quiet_ratio
    h, w = gray_shape[:2]
    bx0 = int(max(0, cx - side / 2 - pad))
    by0 = int(max(0, cy - side / 2 - pad))
    bx1 = int(min(w, cx + side / 2 + pad))
    by1 = int(min(h, cy + side / 2 + pad))
    return (bx0, by0, bx1, by1), mod


def find_qr_triple(fps, debug=False):
    """从候选里挑出"尺寸一致 + 构成直角等腰三角形"的三个定位符。

    标准 QR 的硬约束：三个定位符等大，且两两构成等腰直角三角形
    （直角顶点 = 左上，两条直角边 = 右上/左下）。
    这一条足以筛掉灯、插座、纹理等误报。
    """
    import itertools
    best = None
    for combo in itertools.combinations(fps, 3):
        sizes = sorted(p[2] for p in combo)
        # 1) 尺寸一致（最小与最大相差不超过 25%）
        if sizes[0] <= 0 or sizes[2] / sizes[0] > 1.25:
            continue
        pts = [(p[0], p[1]) for p in combo]
        # 2) 找出"最接近 90°"的那个顶点作为直角顶点。
        #    注意：QR 三个定位符构成等腰直角三角形，直角顶点处 90°、另两处各 45°；
        #    所以必须挑"离 90° 最近"的角，而不是挑最小角（上一版那样会永远选中 45°）。
        ang90 = None
        for i in range(3):
            a = np.array(pts[i], float)
            b = np.array(pts[(i + 1) % 3], float)
            c = np.array(pts[(i + 2) % 3], float)
            v1, v2 = b - a, c - a
            n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
            if n1 < 1e-6 or n2 < 1e-6:
                continue
            cos = abs(float(np.dot(v1, v2)) / (n1 * n2))
            ang = np.degrees(np.arccos(min(1.0, cos)))
            if ang90 is None or abs(ang - 90.0) < abs(ang90[0] - 90.0):
                ang90 = (ang, i, n1, n2)
        if ang90 is None:
            continue
        ang, idx, n1, n2 = ang90
        # 直角顶点处的角必须"接近 90°"（±20°）
        if not (70.0 <= ang <= 110.0):
            if debug:
                print(f'   [排除] 角度 {ang:.1f}° 不在 70~110  ({pts})')
            continue
        # 3) 两条直角边近似等长（等腰）
        if max(n1, n2) / max(1e-6, min(n1, n2)) > 1.3:
            continue
        # 4) 中心距应与定位符尺寸成合理比例。
        #    不用"模块尺寸"推算——那需要对码版本做假设，实测误差可达 30%。
        #    直接用比值：真实码里 中心距/定位符宽 ≈ (版本模块数-7)/7，
        #    对版本 1~10 落在 2.0~13 区间；这里放宽到 1.5~14，只排除明显挤压/过远。
        side = (n1 + n2) / 2.0
        fsz = float(np.median([p[2] for p in combo]))
        r = side / max(1e-6, fsz)
        if not (1.5 <= r <= 14.0):
            if debug:
                print(f'   [排除] 尺寸{sizes} 直角{ang:.1f}° 边{n1:.0f}/{n2:.0f} 比值{r:.2f}')
            continue
        score = ang + abs(n1 - n2) / max(n1, n2) * 20
        if best is None or score < best[0]:
            best = (score, combo, idx, ang)
    if best is None:
        return None
    _, combo, idx, ang = best
    if debug:
        print(f'   选中三个: ' + ', '.join(f'({p[0]:.0f},{p[1]:.0f},s={p[2]:.0f})' for p in combo)
              + f'  直角={ang:.1f}°')
    return combo


def main():
    p = sys.argv[1] if len(sys.argv) > 1 else r'E:\学习\qcode\02-测试用例\real\real_charger_lcd.jpg'
    gray = np.asarray(Image.open(p).convert('L'))
    print(f'图像 {gray.shape[1]}x{gray.shape[0]}')
    print('--- 定位符检测 ---')
    fps = find_finders(gray, debug=True)
    print(f'合并后定位符候选数: {len(fps)}')
    for cx, cy, s in fps:
        print(f'   ({cx:.0f},{cy:.0f}) size={s:.0f}')
    print('--- 几何筛选（等大 + 直角等腰）---')
    tri = find_qr_triple(fps, debug=True)
    if tri is None:
        print('   未找到符合条件的三个定位符')
        return
    box, mod = qr_box_from_three(tri, gray.shape)
    print(f'   模块尺寸 ≈ {mod:.1f}px  包围盒 {box}  尺寸 {box[2]-box[0]}x{box[3]-box[1]}')
    print(f'   真实码区 ≈ (592,654)-(836,907) 即 244x253，模块≈9.8px（25 模块版本）')


if __name__ == '__main__':
    main()
