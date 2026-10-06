# -*- coding: utf-8 -*-
"""QRSuite v2 —— 多引擎二维码/条码识别工具包

Python 部分：本地高精度解码（zxing-cpp / OpenCV / zbar / WeChatQRCode / v1 原程序）
Web 部分：docs/ 目录是纯前端静态站点，可直接部署到 GitHub Pages（浏览器内解码，无需后端）
"""
from .core import Decoder, Result, Hit, MODES

__version__ = '2.0.3'
__all__ = ['Decoder', 'Result', 'Hit', 'MODES', '__version__']
