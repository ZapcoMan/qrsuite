# -*- coding: utf-8 -*-
"""同一进程内对比：微信惰性引擎开关对速度/精度的影响（多次重复取中位数，避免噪声误判）。"""
from __future__ import annotations

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qrsuite.core import Decoder, MODES   # noqa: E402

CHOICES = {
    'new(带wechat)': ('zxing', 'cv2', 'zbar', 'wechat'),
    'old(无wechat)': ('zxing', 'cv2', 'zbar'),
}


def run(dec, folder, engines, mode='balanced', repeats=3):
    orig = MODES[mode]
    backup = orig['engines']
    orig['engines'] = engines
    times, solved = [], 0
    try:
        files = sorted(f for f in os.listdir(folder)
                       if f.lower().endswith(('.png', '.jpg', '.jpeg')))
        for _ in range(repeats):
            t0 = time.perf_counter()
            cnt = 0
            for f in files:
                r = dec.decode_path(os.path.join(folder, f), mode=mode)
                if r.hits:
                    cnt += 1
            times.append(time.perf_counter() - t0)
            solved = cnt
    finally:
        orig['engines'] = backup
    return solved, len(files), times


def main():
    sets = {
        '基准13(易)': r'E:\学习\qcode\02-测试用例\cases',
        '不规则27(难)': r'E:\学习\qcode\02-测试用例\irregular',
    }
    dec = Decoder()
    print('可用引擎:', dec.available_engines())
    for label, folder in sets.items():
        print(f'\n=== {label} ===')
        for name, engines in CHOICES.items():
            solved, total, times = run(dec, folder, engines)
            med = statistics.median(times)
            print(f'  {name:16} 解出 {solved}/{total}   中位耗时 {med:.2f}s   '
                  f'每张 {med/total*1000:.1f}ms   各次 {[round(t,2) for t in times]}')


if __name__ == '__main__':
    main()
