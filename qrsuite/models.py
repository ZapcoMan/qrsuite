# -*- coding: utf-8 -*-
"""WeChatQRCode 模型下载（可选引擎，专治小尺寸/模糊二维码）"""
from __future__ import annotations
import os, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, 'wechat_models')

FILES = {
    'detect.prototxt':   ('opencv/opencv', '4.x', 'modules/wechat_qrcode/misc/detect.prototxt'),
    'detect.caffemodel': ('opencv/opencv_3rdparty', 'wechat_qrcode_20210119', 'detect.caffemodel'),
    'sr.prototxt':       ('opencv/opencv', '4.x', 'modules/wechat_qrcode/misc/sr.prototxt'),
    'sr.caffemodel':     ('opencv/opencv_3rdparty', 'wechat_qrcode_20210119', 'sr.caffemodel'),
}
MIRRORS = [
    'https://cdn.jsdelivr.net/gh/{repo}@{ref}/{path}',
    'https://ghproxy.net/https://raw.githubusercontent.com/{repo}/{ref}/{path}',
    'https://raw.giteeusercontent.com/{repo}/{ref}/{path}',
    'https://raw.githubusercontent.com/{repo}/{ref}/{path}',
]


def fetch_wechat_models(model_dir=MODEL_DIR, quiet=False):
    os.makedirs(model_dir, exist_ok=True)
    ok = True
    for name, (repo, ref, path) in FILES.items():
        dst, tmp = os.path.join(model_dir, name), os.path.join(model_dir, name + '.part')
        if os.path.exists(dst) and os.path.getsize(dst) > 4096:
            if not quiet: print(f'已存在: {name} ({os.path.getsize(dst)//1024} KB)')
            continue
        done = False
        for tpl in MIRRORS:
            url = tpl.format(repo=repo, ref=ref, path=path)
            try:
                if not quiet: print(f'下载 {name} <- {url.split("/")[2]}')
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as f:
                    while True:
                        chunk = r.read(65536)
                        if not chunk: break
                        f.write(chunk)
                if os.path.getsize(tmp) > 4096:
                    os.replace(tmp, dst)
                    if not quiet: print(f'  ✓ {name} ({os.path.getsize(dst)//1024} KB)')
                    done = True; break
            except Exception as e:
                if not quiet: print(f'  镜像失败: {e}')
            finally:
                if os.path.exists(tmp): os.remove(tmp)
        if not done:
            ok = False
            if not quiet: print(f'  ✗ {name} 所有镜像均失败（该引擎会被跳过，其余引擎不受影响）')
    return ok
