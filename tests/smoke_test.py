# -*- coding: utf-8 -*-
"""冒烟测试：引擎可用性 + 端到端解码 + 级联早退行为

用法: python tests/smoke_test.py
不依赖测试框架，退出码 0 = 全部通过。
"""
import io, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from qrsuite.core import Decoder, MODES  # noqa: E402

fails = []


def check(name, cond, extra=''):
    print(f'{"✓" if cond else "✗"} {name}{(" — " + extra) if extra else ""}')
    if not cond:
        fails.append(name)


def make_qr(text='SMOKE-TEST-2026'):
    """用 zxing-cpp 现场生成一张 QR PNG（离线，无需网络）。"""
    import zxingcpp as zx
    from PIL import Image
    import numpy as np
    img = zx.write_barcode_to_image(zx.create_barcode(text, zx.BarcodeFormat.QRCode), scale=8)
    arr = np.array(img)
    if arr.ndim == 2:
        pil = Image.fromarray(arr).convert('L')
    else:
        pil = Image.fromarray(arr[:, :, ::-1]).convert('RGB')   # BGR -> RGB
    fd, path = tempfile.mkstemp(suffix='.png'); os.close(fd)
    pil.save(path)
    return path, text


def main():
    dec = Decoder()
    eng = dec.available_engines()
    print(f'可用引擎: {", ".join(eng)}\n')
    check('至少 1 个引擎可用', len(eng) >= 1, ', '.join(eng))
    check('zxing 引擎可用（主力）', 'zxing' in eng)

    path, text = make_qr()
    try:
        for mode in ('fast', 'balanced', 'deep'):
            r = dec.decode_path(path, mode=mode)
            hit = next((h.text for h in r.hits), None)
            check(f'[{mode}] 解出正确内容', hit == text, f'got={hit!r}')
            check(f'[{mode}] 命中即停（早退）', r.stopped_early or mode == 'deep',
                  f'stages={r.stages_tried}')
        r = dec.decode_path(path, mode='fast')
        check('fast 模式只跑极少阶段（≤2）', r.stages_tried <= 2, f'stages={r.stages_tried}')

        # 交叉验证模式：要求 ≥2 引擎一致
        r = dec.decode_bytes(open(path, 'rb').read(), mode='balanced', verify=True)
        check('解码字节流（网页后端同一路径）', any(h.text == text for h in r.hits))

        # 非图片输入应给出错误而不是抛异常
        r = dec.decode_bytes(b'not an image')
        check('非法输入返回错误对象', bool(r.error), r.error[:40])
    finally:
        os.remove(path)

    print('-' * 46)
    if fails:
        print(f'FAILED: {len(fails)} 项 -> {fails}')
        return 1
    print('ALL PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
