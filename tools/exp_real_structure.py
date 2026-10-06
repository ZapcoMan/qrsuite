# -*- coding: utf-8 -*-
"""结构诊断：这两张真实码到底是不是标准 QR？"""
import os
import numpy as np
import cv2
from PIL import Image

D = r'E:\学习\qcode\02-测试用例\real'
det = cv2.QRCodeDetector()

for f in sorted(os.listdir(D)):
    if not f.lower().endswith(('.jpg', '.png')):
        continue
    p = os.path.join(D, f)
    bgr = np.asarray(Image.open(p).convert('RGB'))[:, :, ::-1].copy()
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    print(f'\n===== {f}  {bgr.shape[1]}x{bgr.shape[0]} =====')

    # 1) OpenCV 检测
    try:
        ok, pts = det.detect(bgr)
        print(f'  QRCodeDetector.detect -> {ok}')
    except Exception as e:
        print(f'  detect 异常: {e}')

    # 2) zxing-cpp 位置信息（找得到但解不出？）
    try:
        import zxingcpp
        res = zxingcpp.read_barcodes(bgr, return_errors=True)
        print(f'  zxing 候选数: {len(res)}')
        for r in res:
            pos = getattr(r, 'position', None)
            print(f'     text={getattr(r,"text","")!r} valid={getattr(r,"valid",None)} '
                  f'format={getattr(r,"format",None)} error={getattr(r,"error",None)} '
                  f'pos={pos}')
    except Exception as e:
        print(f'  zxing 异常: {e}')

    # 3) 定位符结构：在图上找"同心环"（标准 QR 定位符是 1:1:3:1:1）
    #    用轮廓层级统计，看是否存在标准三层方块结构
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cnts, hier = cv2.findContours(bw, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    depth3 = 0
    rings = 0
    if hier is not None:
        hier = hier[0]
        for i, c in enumerate(cnts):
            a = cv2.contourArea(c)
            if a < 60:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if h == 0:
                continue
            ar = w / float(h)
            circ = 4 * np.pi * a / (cv2.arcLength(c, True) ** 2 + 1e-9)
            p1 = hier[i][3]
            p2 = hier[p1][3] if p1 >= 0 else -1
            if p1 >= 0 and p2 >= 0:
                depth3 += 1
            # 圆度高 → 像圆点/圆环
            if 0.7 <= ar <= 1.4 and circ > 0.75:
                rings += 1
    print(f'  三层嵌套轮廓(像标准定位符): {depth3}')
    print(f'  近圆形轮廓(像圆点/圆环): {rings}')
