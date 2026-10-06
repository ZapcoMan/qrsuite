# -*- coding: utf-8 -*-
"""用真实抖音主页码 / 微信赞赏码，逐一测试本机所有可用解码器。

目的：搞清楚"用不了"到底是解码器不行，还是需要预处理/裁剪。
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, r'E:\学习\qcode\01-qrsuite-v2')

D = r'E:\学习\qcode\02-测试用例\real'


def load(path):
    im = Image.open(path).convert('RGB')
    rgb = np.asarray(im)
    bgr = rgb[:, :, ::-1].copy()
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return bgr, gray


def try_zxing(bgr):
    import zxingcpp
    out = []
    for r in zxingcpp.read_barcodes(bgr):
        t = getattr(r, 'text', '') or ''
        if t:
            out.append(t)
    return out


def try_zxing_multi(bgr):
    """zxing-cpp 自带的更激进检测（try_harder / 多码）"""
    import zxingcpp
    out = []
    try:
        res = zxingcpp.read_barcodes(bgr, try_harder=True, try_rotate=True,
                                     try_downscale=True, try_invert=True)
        for r in res:
            t = getattr(r, 'text', '') or ''
            if t:
                out.append(t)
    except TypeError as e:
        return [f'(参数不支持: {e})']
    return out


def try_cv2(gray):
    det = cv2.QRCodeDetector()
    out = []
    try:
        data, _, _ = det.detectAndDecode(gray)
        if data:
            out.append(data)
    except Exception:
        pass
    return out


def try_cv2_wechat(bgr):
    out = []
    try:
        wq = cv2.wechat_qrcode.WeChatQRCode()
        res = wq.detectAndDecode(bgr)
        texts = res[0] if isinstance(res, (tuple, list)) else res
        out = [t for t in (texts or []) if t]
    except Exception as e:
        out = [f'(异常 {e})']
    return out


def try_zbar(gray):
    out = []
    try:
        from pyzbar import pyzbar
        for r in pyzbar.decode(gray):
            try:
                out.append(r.data.decode('utf-8'))
            except Exception:
                out.append(r.data.decode('latin1'))
    except Exception as e:
        out = [f'(异常 {e})']
    return out


ENGINES = [
    ('zxing-cpp 默认', lambda b, g: try_zxing(b)),
    ('zxing-cpp 激进', lambda b, g: try_zxing_multi(b)),
    ('opencv QRCodeDetector', lambda b, g: try_cv2(g)),
    ('opencv wechat_qrcode', lambda b, g: try_cv2_wechat(b)),
    ('zbar(pyzbar)', lambda b, g: try_zbar(g)),
]


def main():
    files = sorted(f for f in os.listdir(D) if f.lower().endswith(('.jpg', '.png')))
    for f in files:
        bgr, gray = load(os.path.join(D, f))
        print(f'\n===== {f}  {bgr.shape[1]}x{bgr.shape[0]} =====')
        for name, fn in ENGINES:
            try:
                res = fn(bgr, gray)
            except Exception as e:
                res = [f'(异常 {e})']
            mark = 'OK ' if res and not str(res[0]).startswith('(') else '   '
            print(f'  {mark} {name:24} {res if res else "无结果"}')

    # 再试：先做灰度/Otsu/自适应阈值等预处理，看能否救回
    print('\n\n===== 预处理变体（以 zxing-cpp 激进 + opencv 微信引擎为准）=====')
    for f in files:
        bgr, gray = load(os.path.join(D, f))
        variants = {
            '原图': bgr,
            'Otsu': cv2.cvtColor(cv2.threshold(gray, 0, 255,
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1], cv2.COLOR_GRAY2BGR),
            '自适应阈值': cv2.cvtColor(cv2.adaptiveThreshold(gray, 255,
                            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10),
                            cv2.COLOR_GRAY2BGR),
            '自适应阈值(反色)': cv2.cvtColor(cv2.adaptiveThreshold(gray, 255,
                            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 10),
                            cv2.COLOR_GRAY2BGR),
        }
        print(f'\n-- {f} --')
        for vn, img in variants.items():
            a = try_zxing_multi(img)
            b = try_cv2_wechat(img)
            print(f'  {vn:16} zxing={a if a else "—"}  wechat={b if b else "—"}')


if __name__ == '__main__':
    main()
