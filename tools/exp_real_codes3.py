# -*- coding: utf-8 -*-
"""最后一搏：微信引擎的 scaleFactor、放大、格式限定、多尺度组合。"""
import os
import numpy as np
import cv2
from PIL import Image
import zxingcpp

D = r'E:\学习\qcode\02-测试用例\real'


def load(p):
    return np.asarray(Image.open(p).convert('RGB'))[:, :, ::-1].copy()


def wechat_try(bgr, sf):
    try:
        wq = cv2.wechat_qrcode.WeChatQRCode()
        try:
            wq.setScaleFactor(sf)
        except Exception:
            pass
        res = wq.detectAndDecode(bgr)
        texts = res[0] if isinstance(res, (tuple, list)) else res
        return [t for t in (texts or []) if t]
    except Exception as e:
        return [f'ERR:{e}']


for f in sorted(os.listdir(D)):
    if not f.lower().endswith(('.jpg', '.png')):
        continue
    bgr = load(os.path.join(D, f))
    print(f'\n===== {f} =====')
    # 微信引擎在不同 scaleFactor 下
    for sf in (0.5, 1.0, 2.0, 3.0):
        r = wechat_try(bgr, sf)
        print(f'  wechat scaleFactor={sf:>4} -> {r or "—"}')
    # 放大后再试
    for f2 in (1.5, 2.0):
        up = cv2.resize(bgr, None, fx=f2, fy=f2, interpolation=cv2.INTER_CUBIC)
        print(f'  放大{f2}x: wechat -> {wechat_try(up, 1.0) or "—"}  '
              f'zxing -> {[getattr(x,"text","") for x in zxingcpp.read_barcodes(up)] or "—"}')
    # 只允许 QR 格式 + 各种二值化器
    for name, binr in (('LocalAverage', zxingcpp.Binarizer.LocalAverage),
                       ('GlobalHistogram', zxingcpp.Binarizer.GlobalHistogram),
                       ('FixedThreshold', zxingcpp.Binarizer.FixedThreshold)):
        try:
            out = [getattr(x, 'text', '') for x in zxingcpp.read_barcodes(
                bgr, formats=zxingcpp.BarcodeFormat.QRCode, binarizer=binr)]
            print(f'  zxing QR-only {name:16} -> {out or "—"}')
        except Exception as e:
            print(f'  zxing {name} 异常: {e}')
