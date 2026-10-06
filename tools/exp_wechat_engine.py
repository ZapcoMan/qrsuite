# -*- coding: utf-8 -*-
"""评估 OpenCV 5.0 内置 wechat_qrcode 引擎（无需 4 个模型文件）的实际命中。"""
import os
import sys
import time

import cv2
import numpy as np
from PIL import Image


def imread_unicode(path):
    """cv2.imread 在 Windows 上读不了含中文的路径，必须走 Pillow。"""
    try:
        im = Image.open(path).convert('RGB')
    except Exception:
        return None
    rgb = np.asarray(im)
    return rgb[:, :, ::-1].copy()          # RGB -> BGR


d = sys.argv[1] if len(sys.argv) > 1 else r'E:\学习\qcode\02-测试用例\irregular'
wq = cv2.wechat_qrcode.WeChatQRCode()
try:
    print('scaleFactor =', wq.getScaleFactor())
except Exception:
    pass

files = sorted(f for f in os.listdir(d) if f.endswith('.png'))
ok = 0
t0 = time.perf_counter()
for f in files:
    img = imread_unicode(os.path.join(d, f))
    if img is None:
        print('  [read fail]', f)
        continue
    text = ''
    try:
        res, pts = wq.detectAndDecode(img)
        good = [t for t in res if t]
        text = good[0] if good else ''
    except Exception as e:
        text = ''
    if text:
        ok += 1
    mark = 'OK ' if text else '   '
    print(f'  {mark} {f:34} {text[:60]}')
el = time.perf_counter() - t0
print(f'\n微信内置引擎: 命中 {ok}/{len(files)}，总耗时 {el:.2f}s，平均 {el/max(1,len(files))*1000:.1f}ms/张')
