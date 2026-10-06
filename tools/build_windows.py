# -*- coding: utf-8 -*-
"""Windows 版构建 + 可选代码签名。

用法：
    python tools/build_windows.py                 # 只构建
    python tools/build_windows.py --sign          # 构建后用证书签名

签名需要一张已导入证书存储的代码签名证书，或一个 .pfx 文件。凭据从**环境变量**读取，
不写进任何仓库文件：

    QRSUITE_SIGN_PFX        .pfx 文件路径（不提供则用证书存储里自动挑选的证书）
    QRSUITE_SIGN_PFX_PASS   .pfx 口令
    QRSUITE_SIGN_SHA1       证书指纹（可在多个证书时指定用哪一个）

签名用 Windows SDK 的 signtool.exe（若不在 PATH，可用 QRSUITE_SIGNTOOL 指定全路径）。

为什么要签名：无签名的 exe 会触发 SmartScreen「已保护你的电脑」提示，
需要用户手动点「仍要运行」。OV 证书可逐步建立声誉，EV 证书立即受信。
证书需自行向 CA 购买，本项目不附带任何证书。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')
ENTRY = os.path.join(ROOT, 'qrsuite', 'winapp.py')


def find_signtool() -> str | None:
    """优先环境变量，其次 PATH，最后在 Windows Kits 目录里找。"""
    env = os.environ.get('QRSUITE_SIGNTOOL')
    if env and os.path.isfile(env):
        return env
    which = shutil.which('signtool')
    if which:
        return which
    roots = [
        r'C:\Program Files (x86)\Windows Kits\10\bin',
        r'C:\Program Files\Windows Kits\10\bin',
    ]
    cands = []
    for r in roots:
        if not os.path.isdir(r):
            continue
        for ver in sorted(os.listdir(r), reverse=True):
            p = os.path.join(r, ver, 'x64', 'signtool.exe')
            if os.path.isfile(p):
                cands.append(p)
    return cands[0] if cands else None


def build(dist: str, name: str = 'QRSuite') -> str:
    cmd = [
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--console',
        '--name', name,
        # 自解析临时目录：单文件包默认会往系统临时目录解压，临时目录不可用时会直接报错退出
        '--runtime-tmpdir', '.',
        '--distpath', dist,
        '--workpath', os.path.join(dist, '_work'),
        '--specpath', dist,
        '--add-data', f'{DOCS}{os.pathsep}docs',
        '--hidden-import', 'zxingcpp',
        '--hidden-import', 'cv2',
        '--hidden-import', 'cv2.wechat_qrcode',
        '--collect-all', 'pyzbar',
        ENTRY,
    ]
    print('[build]', ' '.join(cmd[:8]), '…')
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(f'PyInstaller 失败，退出码 {r.returncode}')
    exe = os.path.join(dist, f'{name}.exe')
    if not os.path.isfile(exe):
        raise SystemExit(f'未找到产物：{exe}')
    print('[build] 产物:', exe, f'{os.path.getsize(exe) / 1048576:.1f} MB')
    return exe


def sign(exe: str, timestamp_url: str = 'http://timestamp.digicert.com') -> None:
    tool = find_signtool()
    if not tool:
        raise SystemExit('找不到 signtool.exe。请安装 Windows SDK，'
                         '或用 QRSUITE_SIGNTOOL 指定其完整路径。')

    pfx = os.environ.get('QRSUITE_SIGN_PFX')
    sha1 = os.environ.get('QRSUITE_SIGN_SHA1')

    cmd = [tool, 'sign', '/fd', 'SHA256', '/tr', timestamp_url, '/td', 'SHA256', '/v']
    if pfx:
        cmd += ['/f', pfx]
        pw = os.environ.get('QRSUITE_SIGN_PFX_PASS')
        if pw:
            cmd += ['/p', pw]
    elif sha1:
        cmd += ['/sha1', sha1]
    else:
        # 让 signtool 自动挑选合适的证书
        cmd += ['/a']
    cmd.append(exe)

    print('[sign] 使用', tool)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(f'signtool 签名失败，退出码 {r.returncode}')

    # 校验
    v = subprocess.run([tool, 'verify', '/pa', '/v', exe], capture_output=True, text=True)
    print('[sign] 校验输出（末尾）:')
    print('\n'.join((v.stdout or '').strip().split('\n')[-4:]))
    if v.returncode != 0:
        raise SystemExit('签名校验未通过')
    print('[sign] 已完成并对时间戳签名')


def main() -> int:
    ap = argparse.ArgumentParser(description='构建 Windows 单文件版（可选签名）')
    ap.add_argument('--dist', default=os.path.join(os.path.dirname(ROOT), '06-构建产物', 'win'),
                    help='产物输出目录')
    ap.add_argument('--name', default='QRSuite', help='产物文件名（不含 .exe）')
    ap.add_argument('--sign', action='store_true', help='构建后用证书签名')
    ap.add_argument('--no-build', action='store_true', help='跳过构建，只对已有 exe 签名')
    args = ap.parse_args()

    os.makedirs(args.dist, exist_ok=True)
    exe = os.path.join(args.dist, f'{args.name}.exe')
    if not args.no_build:
        exe = build(args.dist, args.name)
    elif not os.path.isfile(exe):
        raise SystemExit(f'--no-build 但产物不存在：{exe}')

    if args.sign:
        sign(exe)
    else:
        print('[hint] 未签名。发布时想消除 SmartScreen 提示，需购买代码签名证书后'
              '加 --sign，并设置 QRSUITE_SIGN_PFX / QRSUITE_SIGN_PFX_PASS（或 QRSUITE_SIGN_SHA1）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
