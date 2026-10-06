# -*- coding: utf-8 -*-
"""qrsuite 统一命令行入口：识别 / 批量 / 目录 / URL / 本地网页服务 / 模型下载"""
from __future__ import annotations
import argparse, glob, json, os, re, sys, time
from .core import Decoder, MODES, __doc__ as _coredoc

BANNER = 'QRSuite v2 · 多引擎二维码识别'


def _iter_inputs(paths, use_dir=False):
    for p in paths:
        if re.match(r'^https?://', p):
            yield p; continue
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tif', '.tiff')):
                        yield os.path.join(root, f)
        elif any(ch in p for ch in '*?['):
            for g in glob.glob(p): yield g
        else:
            yield p


def _fetch(url, timeout=30):
    import urllib.request, tempfile
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'image/*,*/*;q=0.8'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = r.headers.get('Content-Type', ''); data = r.read(64 * 1024 * 1024)
    if not ctype.startswith('image/') and data[:4] not in (b'\x89PNG', b'\xff\xd8\xff\xff', b'GIF8', b'RIFF', b'BM'):
        raise ValueError(f'URL 内容不是图片类型: {ctype}')
    return data


def cmd_scan(a, dec: Decoder):
    items = list(_iter_inputs(a.paths, a.dir))
    if not items:
        print('请输入二维码图片的路径或图片 URL（多个用英文逗号分隔）: ', end='', flush=True)
        items = [t.strip().strip('"') for t in re.split(r'[,\r\n]+', sys.stdin.readline() or '') if t.strip()]
    if not items:
        print('未提供输入路径', file=sys.stderr); return 1
    print(f'{BANNER}\n引擎: {", ".join(dec.available_engines())} | 模式: {a.mode}'
          f'{" | 验证模式" if a.verify else ""} | 目标: {len(items)} 个')
    allres, t0, cpu0 = [], time.perf_counter(), time.process_time()
    for i, item in enumerate(items, 1):
        print(f'[{i}/{len(items)}] {item}')
        try:
            if re.match(r'^https?://', item):
                r = dec.decode_bytes(_fetch(item), a.mode, a.verify, a.max_side)
            else:
                r = dec.decode_path(item, a.mode, a.verify, a.max_side)
        except Exception as e:
            print(f'  ERROR 无法获取: {e}', file=sys.stderr); continue
        if r.error:
            print(f'  ERROR {r.error}', file=sys.stderr); continue
        if not r.hits:
            print(f'  ✗ 未解码（{r.stages_tried} 阶段 / {r.engine_runs} 次引擎调用 / {r.elapsed:.2f}s）')
        for h in r.hits:
            print(f'  ✓ [{h.format}] {h.text}')
            print(f'     引擎: {", ".join(sorted(h.engines))} | 生效变体: {", ".join(sorted(h.variants))}')
            allres.append(dict(source=item, text=h.text, format=h.format,
                               engines=sorted(h.engines), variants=sorted(h.variants)))
        if a.verbose:
            print(f'     阶段 {r.stages_tried} / 引擎调用 {r.engine_runs} / 用时 {r.elapsed:.3f}s / CPU {r.cpu:.3f}s'
                  f'{" / 早退" if r.stopped_early else ""}')
    dt, dcpu = time.perf_counter() - t0, time.process_time() - cpu0
    print('-' * 62)
    print(f'完成: {len(items)} 个输入, 解出 {len(allres)} 条, 墙钟 {dt:.2f}s, CPU {dcpu:.2f}s'
          f'{f", 平均 {dt/len(items):.3f}s/张" if items else ""}')
    if a.json:
        json.dump(allres, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'结果已写入 {a.json}')
    return 0 if allres else 1


def cmd_serve(a, dec: Decoder):
    from .web import serve
    return serve(port=a.port, open_browser=not a.no_browser)


def cmd_models(a, dec: Decoder):
    from .models import fetch_wechat_models
    return 0 if fetch_wechat_models() else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog='qrsuite', description=BANNER)
    ap.add_argument('paths', nargs='*', help='图片路径 / 目录 / 通配符 / 图片 URL')
    ap.add_argument('--mode', choices=list(MODES), default='balanced',
                    help='fast=只试2阶段, balanced=默认, deep=全阶段全引擎')
    ap.add_argument('--verify', action='store_true', help='需 ≥2 引擎一致才停（降低误读，稍慢）')
    ap.add_argument('--dir', action='store_true', help='参数按目录递归')
    ap.add_argument('--json', metavar='FILE', help='结果写入 JSON')
    ap.add_argument('--engines', help='限定引擎, 逗号分隔: ' + ','.join(['zxing', 'cv2', 'zbar', 'wechat', 'original']))
    ap.add_argument('--max-side', type=int, default=1800, help='大图先缩放到该边长（默认 1800，省 CPU）')
    ap.add_argument('--original-exe', default=os.environ.get('QRSUITE_ORIGINAL_EXE'),
                    help='v1 的 QRCodeScanner.exe 路径（作为 original 引擎）')
    ap.add_argument('--model-dir', default=None, help='WeChatQRCode 模型目录')
    ap.add_argument('--serve', action='store_true', help='启动本地网页服务（浏览器拖拽识别）')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true')
    ap.add_argument('--fetch-models', action='store_true', help='下载 WeChatQRCode 模型')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args(argv)

    engines = [e.strip() for e in a.engines.split(',')] if a.engines else None
    dec = Decoder(model_dir=a.model_dir, original_exe=a.original_exe, engines=engines)
    if a.fetch_models: return cmd_models(a, dec)
    if a.serve:        return cmd_serve(a, dec)
    return cmd_scan(a, dec)
