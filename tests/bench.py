# -*- coding: utf-8 -*-
"""v1 vs v2 基准对比：解析效率 / CPU 占用 / 阶段数（同一批图片、同一台机器）

用法: python tests/bench.py <cases_dir> <v1_qrsuite.py路径>
"""
import importlib.util, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

cases_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '..', 'cases')
v1_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join('E:', 'ToolDownloads', 'qrsuite.py')


def load_v1(path):
    spec = importlib.util.spec_from_file_location('qrsuite_v1', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def images():
    out = []
    for f in sorted(os.listdir(cases_dir)):
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
            out.append(os.path.join(cases_dir, f))
    return out


def main():
    from PIL import Image
    from qrsuite.core import Decoder

    imgs = images()
    print(f'用例: {len(imgs)} 张  ({cases_dir})\n')

    # ---------- v1：18 变体 × N 引擎，无早退 ----------
    v1_msgs = []
    if os.path.isfile(v1_path):
        v1 = load_v1(v1_path)
        v1_engines = [e for e in ('zxing', 'cv2', 'zbar') if e in v1.ENGINES]
        w0, c0 = time.perf_counter(), time.process_time()
        ok1 = variants1 = 0
        for p in imgs:
            img = Image.open(p); img.load()
            res, tried = v1.decode_image(img, v1_engines, True, progress=False)
            variants1 += tried
            ok1 += bool(res)
        v1_msgs.append(('v1 (旧流程, 无早退)', time.perf_counter() - w0, time.process_time() - c0, variants1, ok1))
    else:
        print(f'[skip] 未找到 v1 脚本: {v1_path}\n')

    # ---------- v2：级联 + 早退 ----------
    for mode in ('fast', 'balanced', 'deep'):
        dec = Decoder(original_exe=os.environ.get('QRSUITE_ORIGINAL_EXE'))
        w0, c0 = time.perf_counter(), time.process_time()
        ok2 = stages2 = runs2 = 0
        for p in imgs:
            r = dec.decode_path(p, mode=mode)
            stages2 += r.stages_tried; runs2 += r.engine_runs
            ok2 += bool(r.hits)
        v1_msgs.append((f'v2 --mode {mode}', time.perf_counter() - w0, time.process_time() - c0, stages2, ok2, runs2))

    print(f'{"方案":24s} {"墙钟(s)":>9s} {"CPU(s)":>8s} {"阶段合计":>9s} {"引擎调用":>9s} {"解出":>6s}')
    print('-' * 74)
    for row in v1_msgs:
        name, wall, cpu, stages, ok = row[0], row[1], row[2], row[3], row[4]
        runs = row[5] if len(row) > 5 else '-'
        print(f'{name:24s} {wall:9.2f} {cpu:8.2f} {stages:9d} {str(runs):>9s} {ok:5d}/{len(imgs)}')
    if v1_msgs:
        base = v1_msgs[0]
        print('-' * 74)
        for row in v1_msgs[1:]:
            print(f'{row[0]:24s} 墙钟 {base[1]/row[1]:5.1f}x 提升 | CPU {base[2]/row[2]:5.1f}x 降低 | 阶段 {base[3]/row[3]:5.1f}x 更少')


if __name__ == '__main__':
    main()
