# -*- coding: utf-8 -*-
"""真实样式化码的深入诊断：zxing-cpp 正确 API、多种二值化、区域裁剪、形态学还原。"""
import os
import sys

import cv2
import numpy as np
from PIL import Image
import zxingcpp

D = r'E:\学习\qcode\02-测试用例\real'


def load(path):
    im = Image.open(path).convert('RGB')
    bgr = np.asarray(im)[:, :, ::-1].copy()
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return bgr, gray


def zx(bgr, **kw):
    out = []
    try:
        for r in zxingcpp.read_barcodes(bgr, **kw):
            t = getattr(r, 'text', '') or ''
            if t:
                out.append(t)
    except Exception as e:
        out.append(f'ERR:{e}')
    return out


def wechat(bgr):
    try:
        wq = cv2.wechat_qrcode.WeChatQRCode()
        res = wq.detectAndDecode(bgr)
        texts = res[0] if isinstance(res, (tuple, list)) else res
        return [t for t in (texts or []) if t]
    except Exception as e:
        return [f'ERR:{e}']


def report(tag, img):
    z1 = zx(img)
    z2 = zx(img, try_rotate=True, try_downscale=True, try_invert=True)
    z3 = zx(img, binarizer=zxingcpp.Binarizer.GlobalHistogram)
    w = wechat(img)
    hits = [x for x in (z1, z2, z3, w) if x and not str(x[0]).startswith('ERR')]
    print(f'  {"HIT " if hits else "    "} {tag:34} zxing={z1 or "—"} '
          f'| aggressive={z2 or "—"} | global={z3 or "—"} | wechat={w or "—"}')
    return bool(hits)


def main():
    for f in sorted(os.listdir(D)):
        if not f.lower().endswith(('.jpg', '.png')):
            continue
        bgr, gray = load(os.path.join(D, f))
        h, w = gray.shape
        print(f'\n########## {f}  {w}x{h} ##########')
        print('-- 整图 --')
        report('整图', bgr)

        print('-- 区域裁剪（各 1/2、3/5 居中）--')
        for frac in (0.5, 0.6, 0.7, 0.8):
            ch, cw = int(h * frac), int(w * frac)
            y0, x0 = (h - ch) // 2, (w - cw) // 2
            report(f'居中裁剪 {int(frac*100)}%', bgr[y0:y0 + ch, x0:x0 + cw])

        print('-- 二值化 + 灰度 --')
        otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        report('Otsu', cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR))
        adap = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 10)
        report('自适应阈值', cv2.cvtColor(adap, cv2.COLOR_GRAY2BGR))
        adap_inv = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY_INV, 31, 10)
        report('自适应阈值反色', cv2.cvtColor(adap_inv, cv2.COLOR_GRAY2BGR))
        # 圆点模块 → 膨胀成方块
        for k in (3, 5, 7):
            ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
            dil = cv2.dilate(otsu, ker, iterations=1)
            report(f'Otsu+膨胀{k}', cv2.cvtColor(cv2.bitwise_not(dil), cv2.COLOR_GRAY2BGR))
            cls = cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, ker)
            report(f'Otsu+闭运算{k}', cv2.cvtColor(cv2.bitwise_not(cls), cv2.COLOR_GRAY2BGR))

        print('-- 缩放（样式化码在小尺寸下更接近标准）--')
        for side in (400, 600, 900):
            s = cv2.resize(bgr, (side, side), interpolation=cv2.INTER_AREA)
            report(f'缩到 {side}px', s)


if __name__ == '__main__':
    main()
