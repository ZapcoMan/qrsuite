# -*- coding: utf-8 -*-
"""Windows 启动器入口：启动本地服务，并把访问地址明确告诉用户。

关于窗口形态（重要）：
  `--noconsole` 版本没有控制台，`sys.stdout is None`，于是 **URL 提示和"浏览器已打开"的反馈
  全部丢失**；用户只看到解压出的文件夹，会以为程序没反应。所以交付版应使用 `--console`，
  让地址始终可见、打不开时还能手动访问。

打包命令（在项目根目录执行，注意必须带 --console）：
  python -m PyInstaller --noconfirm --onefile --console --name QRSuite ^
      --runtime-tmpdir "." ^
      --add-data "docs;docs" ^
      --hidden-import zxingcpp --hidden-import cv2 --hidden-import cv2.wechat_qrcode ^
      --collect-all pyzbar qrsuite/winapp.py

可选参数：`QRSuite.exe 9000` 指定端口；`--no-browser` 不自动开浏览器；`--version` 打印版本。
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOG_NAME = 'qrweb.log'


def _log_path():
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    d = os.path.join(base, 'QRSuite')
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        return None
    return os.path.join(d, LOG_NAME)


def _open_streams():
    """保证 print 不会因为 stdout 为 None 而抛异常，同时把输出留一份到日志便于排障。

    返回 (是否追加了文件日志, 日志路径)。控制台已存在时仍然记日志，方便事后查。
    """
    lp = _log_path()
    fh = None
    if lp:
        try:
            fh = open(lp, 'a', encoding='utf-8', buffering=1)
            print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] ---- QRSuite 启动 ----', file=fh)
        except Exception:
            fh = None
    if sys.stdout is None or sys.stderr is None:
        # 无控制台（--noconsole）：把标准流指向日志，避免 print 崩溃导致秒退
        target = fh if fh is not None else open(os.devnull, 'w', encoding='utf-8')
        if sys.stdout is None:
            sys.stdout = target
        if sys.stderr is None:
            sys.stderr = target
    return fh, lp


def _set_console_title(title):
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        pass


def _configure_console_utf8():
    """控制台默认是 GBK，直接 print 中文会乱码/抛 UnicodeEncodeError。"""
    if not sys.platform.startswith('win'):
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)   # UTF-8
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None and hasattr(stream, 'reconfigure'):
                stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


def _msgbox(title, text):
    """无控制台时，用弹窗把地址告诉用户（浏览器没开成时的兜底）。"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)  # MB_ICONINFORMATION
    except Exception:
        pass


def _open_browser_later(url, log, delay=0.8):
    def work():
        time.sleep(delay)
        ok = False
        try:
            import webbrowser
            ok = bool(webbrowser.open(url))
        except Exception as e:
            print(f'[warn] webbrowser 打开失败: {e}', file=sys.stderr)
        if not ok and sys.platform.startswith('win'):
            # os.startfile 走 ShellExecute，通常比 webbrowser 更可靠
            try:
                os.startfile(url)
                ok = True
            except Exception as e:
                print(f'[warn] os.startfile 打开失败: {e}', file=sys.stderr)
        print(f'[info] 打开浏览器{"成功" if ok else "失败"}', file=sys.stdout)
        if log:
            print(f'[info] 打开浏览器{"成功" if ok else "失败"}', file=log)
        if not ok:
            _msgbox('QRSuite 已启动',
                    f'浏览器没有自动打开。\n\n请手动在浏览器访问：\n{url}\n\n'
                    f'（保持本窗口开着，关掉它就停止服务）')
    t = threading.Thread(target=work, name='open-browser', daemon=True)
    t.start()


def main():
    _configure_console_utf8()
    log, lp = _open_streams()
    _set_console_title('QRSuite 二维码识别（关闭本窗口即停止服务）')

    if '--version' in sys.argv:
        from qrsuite import __version__
        print(f'QRSuite {__version__}')
        return 0

    port = 8765
    for a in sys.argv[1:]:
        if a.isdigit():
            port = int(a)

    from qrsuite import __version__
    print('=' * 64)
    print(f'  QRSuite v{__version__}  正在启动本地服务…')
    print('  首次运行需解压运行时文件，约 10 秒，请稍等；')
    print('  随后会自动打开浏览器；若没打开，请手动访问下面显示的地址。')
    print('=' * 64)
    if lp:
        print(f'  （排障日志：{lp}）')

    from qrsuite.web import serve
    return serve(port=port, open_browser=('--no-browser' not in sys.argv),
                 on_ready=lambda url: _open_browser_later(url, log))


if __name__ == '__main__':
    sys.exit(main())
