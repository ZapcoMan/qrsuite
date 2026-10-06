# -*- coding: utf-8 -*-
"""qrsuite.web —— 本地网页服务：浏览器拖拽图片 -> 本机多引擎解码（图片不出本机）

相对 v1 的优化：内容哈希缓存（同一张图第二次打开/刷新即秒回）、模式参数、并发线程池。
"""
from __future__ import annotations
import hashlib, json, os, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote
from .core import Decoder, MODES

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(os.path.dirname(HERE), 'docs')
MAX_BODY = 64 * 1024 * 1024
CACHE_SIZE = 256

_dec: Decoder | None = None
_cache: dict[str, dict] = {}
_lock = threading.Lock()


def _get_decoder() -> Decoder:
    global _dec
    if _dec is None:
        _dec = Decoder(original_exe=os.environ.get('QRSUITE_ORIGINAL_EXE'))
    return _dec


class Handler(BaseHTTPRequestHandler):
    server_version = 'QRSuite/2.0'
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *a):
        if os.environ.get('QRSUITE_DEBUG') == '1':
            sys.stderr.write('[web] %s\n' % (fmt % a))

    def _send(self, code, body: bytes, ctype='application/json; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        p = self.path.split('?')[0]
        if p == '/health':
            d = _get_decoder()
            return self._send(200, json.dumps({'ok': True, 'engines': d.available_engines(),
                                               'modes': list(MODES), 'cached': len(_cache)}).encode())
        if p in ('/', '/index.html', '/qrweb.html'):
            rel = 'qrweb.html' if p == '/qrweb.html' else 'index.html'
            f = os.path.join(STATIC, rel)
            if os.path.exists(f):
                return self._send(200, open(f, 'rb').read(), 'text/html; charset=utf-8')
        # 其它静态资源（app.js / decode.js / style.css / decode.worker.js / vendor/*）
        f = os.path.normpath(os.path.join(STATIC, p.lstrip('/')))
        if f.startswith(STATIC) and os.path.isfile(f):
            ct = {'js': 'application/javascript; charset=utf-8', 'css': 'text/css; charset=utf-8',
                  'html': 'text/html; charset=utf-8', 'json': 'application/json; charset=utf-8',
                  'wasm': 'application/wasm', 'svg': 'image/svg+xml'}.get(f.rsplit('.', 1)[-1], 'application/octet-stream')
            return self._send(200, open(f, 'rb').read(), ct)
        return self._send(404, b'not found', 'text/plain; charset=utf-8')

    def do_POST(self):
        if self.path.split('?')[0] != '/api/decode':
            return self._send(404, b'not found', 'text/plain; charset=utf-8')
        n = int(self.headers.get('Content-Length') or 0)
        if n <= 0 or n > MAX_BODY:
            return self._send(400, json.dumps({'ok': False, 'error': 'empty or too large'}).encode())
        data = self.rfile.read(n)
        name = unquote(self.headers.get('X-Filename') or 'image')
        mode = self.headers.get('X-Mode') or 'balanced'
        if mode not in MODES: mode = 'balanced'
        verify = (self.headers.get('X-Verify') or '0') == '1'
        engines = [e for e in (self.headers.get('X-Engines') or '').split(',') if e] or None

        key = hashlib.sha1(data).hexdigest() + f'|{mode}|{verify}|{",".join(engines or [])}'
        with _lock:
            if key in _cache:
                body = dict(_cache[key]); body['cached'] = True
                return self._send(200, json.dumps(body, ensure_ascii=False).encode())

        dec = _get_decoder() if not engines else Decoder(
            original_exe=os.environ.get('QRSUITE_ORIGINAL_EXE'), engines=engines)
        r = dec.decode_bytes(data, mode, verify)
        body = dict(r.to_dict(), ok=not r.error, filename=name, mode=mode, cached=False)
        with _lock:
            if len(_cache) >= CACHE_SIZE: _cache.pop(next(iter(_cache)))
            _cache[key] = body
        return self._send(200, json.dumps(body, ensure_ascii=False).encode())


def serve(port=8765, open_browser=True, on_ready=None):
    """启动本地服务。

    on_ready: 可选回调，服务已绑定端口后调用，参数是访问 URL。
              调用方（如 winapp）用它接管"打开浏览器 + 失败兜底"，比这里的
              webbrowser 默认行为更可靠、也能给出明确反馈。
    """
    httpd = None
    for p in range(port, port + 20):
        try:
            httpd = ThreadingHTTPServer(('127.0.0.1', p), Handler); port = p; break
        except OSError:
            continue
    if httpd is None:
        print('没有可用端口', file=sys.stderr); return 1
    url = f'http://127.0.0.1:{port}/'
    d = _get_decoder()
    print('=' * 60)
    print(f'  QRSuite 本地服务:  {url}')
    print(f'  引擎: {", ".join(d.available_engines())}   模式: {", ".join(MODES)}')
    print('  图片只在本机内存解码，不上传；Ctrl+C 停止')
    print('=' * 60)
    print(f'  >>> 如果浏览器没有自动打开，请手动访问: {url}', flush=True)
    if on_ready is not None:
        try:
            on_ready(url)
        except Exception as e:
            print(f'[warn] on_ready 回调失败: {e}', file=sys.stderr)
    elif open_browser:
        # 默认路径：webbrowser 失败时用 os.startfile 兜底（Windows 更可靠）
        def _open():
            ok = False
            try:
                ok = bool(webbrowser.open(url))
            except Exception:
                ok = False
            if not ok and sys.platform.startswith('win'):
                try:
                    os.startfile(url); ok = True
                except Exception:
                    ok = False
            if not ok:
                print(f'[warn] 浏览器未能自动打开，请手动访问: {url}', file=sys.stderr)
        threading.Timer(0.8, _open).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')
    return 0
