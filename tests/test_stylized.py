# -*- coding: utf-8 -*-
"""stylized 模块回归测试：权威样本 + 误报样本。

用法：python tests/test_stylized.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from PIL import Image

from qrsuite.stylized import classify, hint, KIND_LABELS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL = os.path.join(os.path.dirname(ROOT), '02-测试用例', 'real')

# (文件, 期望 kind, 允许的备选 kind)
CASES = [
    ('real_douyin.jpg', 'douyin_profile', set()),
    ('real_wechat_reward.jpg', 'wechat_reward', {'wechat_miniprogram'}),
]

# 反例：这些**不是**样式化私有码，必须判为 unknown。
# 普通二维码的三个定位符同样构成等腰直角三角形，纯几何无法与微信牛眼区分；
# 唯一可靠的判别是"角向格律"（微信族应为 36/54/72 线档、周期强度足够）。
# 这些样本曾经全部被误判成 wechat_*，是本模块最关键的一组回归断言。
NEGATIVE = [
    ('f_qr.png', '标准二维码'),
    ('h_blur.png', '模糊QR'),
    ('h_lowcontrast.png', '低对比QR'),
    ('h_noise.png', '带噪QR'),
    ('h_rot15.png', '旋转15°QR'),
    ('h_tiny.png', '极小QR'),
    ('f_c128.png', 'Code128 一维码'),
    ('f_dm.png', 'DataMatrix'),
    ('f_pdf.png', 'PDF417'),
    ('f_az.png', 'Aztec'),
    ('h_invert.png', '反色QR'),
    ('h_partial.png', '残缺QR'),
]

# 性能预算：classify 只在整个引擎级联失败后调用，允许 <0.6s
BUDGET_SEC = 0.6


def _load(name):
    p = os.path.join(REAL, name)
    if not os.path.exists(p):
        alt = os.path.join(os.path.dirname(ROOT), '02-测试用例', 'cases', name)
        p = alt if os.path.exists(alt) else p
    if not os.path.exists(p):
        return None
    return np.array(Image.open(p).convert('RGB'))


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    import time
    ok, fail = 0, 0
    print('=' * 74)
    print('qrsuite.stylized 回归测试')
    print('=' * 74)

    for name, expect, alts in CASES:
        rgb = _load(name)
        if rgb is None:
            print(f'  SKIP  {name} 不存在')
            continue
        t0 = time.perf_counter()
        info = classify(rgb)
        dt = time.perf_counter() - t0
        good = (info.kind == expect) or (info.kind in alts)
        mark = 'PASS' if good else 'FAIL'
        ok, fail = (ok + 1, fail) if good else (ok, fail + 1)
        g = info.geometry
        extra = ' '.join(f'{k}={g[k]}' for k in ('n_eyes', 'square_err', 'iso_right_err') if k in g)
        print(f'  [{mark}] {name:26s} -> {info.kind:18s} conf={info.confidence:.2f} '
              f'{dt*1000:5.0f}ms  {extra}')
        if not good:
            print(f'         期望: {expect}（或 {sorted(alts)}）')
        h = hint(info)
        if good:
            assert h, f'{name}: 异形码应有提示文案'
            print(f'         提示: {h[:56]}...')
        # 性能预算
        if dt > BUDGET_SEC:
            print(f'  [FAIL] 耗时 {dt*1000:.0f}ms 超预算 {BUDGET_SEC*1000:.0f}ms')
            fail += 1
        else:
            ok += 1

    # 几何精度断言（对已实测的权威值）
    rgb = _load('real_douyin.jpg')
    if rgb is not None:
        info = classify(rgb)
        if info.kind == 'douyin_profile':
            se = info.geometry.get('square_err', 9)
            cond = se <= 0.01
            print(f'  [{"PASS" if cond else "FAIL"}] 抖音正方形误差 {se} ≤ 0.01')
            ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    rgb = _load('real_wechat_reward.jpg')
    if rgb is not None:
        info = classify(rgb)
        if info.kind.startswith('wechat'):
            err = info.geometry.get('iso_right_err', 9)
            cx, cy = info.geometry.get('center', (0, 0))
            near = abs(cx - 575.8) < 3 and abs(cy - 419.8) < 3
            print(f'  [{"PASS" if near else "FAIL"}] 赞赏码圆心 ({cx},{cy}) ≈ (575.8,419.8)  '
                  f'等腰直角误差 {err}')
            ok, fail = (ok + 1, fail) if near else (ok, fail + 1)

    # ---- 反例：不是样式化码的必须判 unknown ----
    print('-' * 74)
    print('反例（必须判为 unknown，否则会误导用户去扫错 App）：')
    neg_bad = []
    for name, desc in NEGATIVE:
        rgb = _load(name)
        if rgb is None:
            continue
        t0 = time.perf_counter()
        info = classify(rgb)
        dt = time.perf_counter() - t0
        good = (info.kind == 'unknown')
        if not good:
            neg_bad.append(name)
        print(f'  [{"PASS" if good else "FAIL"}] {name:22s} {desc:14s} -> {info.kind:18s} '
              f'conf={info.confidence:.2f} {dt*1000:5.0f}ms')
        # 反例通常应很快，但阈值放宽以免脆
        if dt > BUDGET_SEC:
            print(f'  [FAIL] 耗时 {dt*1000:.0f}ms 超预算')
            neg_bad.append(name)
    ok += len(NEGATIVE) - len([n for n in neg_bad])
    fail += len(neg_bad)

    print('-' * 74)
    print(f'结果: {ok} 通过 / {fail} 失败')
    if neg_bad:
        print(f'  被误判成样式化码的反例: {neg_bad}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
