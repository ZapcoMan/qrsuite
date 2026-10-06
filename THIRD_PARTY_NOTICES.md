# 第三方组件与许可

本项目自身代码采用 MIT（见 LICENSE）。以下是随仓库分发或运行时依赖的第三方组件。

## 随仓库内置（`docs/vendor/`，用于浏览器端解码）

| 组件 | 版本 | 许可 | 说明 |
|---|---|---|---|
| [jsQR](https://github.com/cozmo/jsQR) | 1.4.0 | Apache-2.0 | 纯 JS 二维码识别（`vendor/jsQR.js`，`vendor/LICENSE.jsQR.txt`） |
| [ZXing-js / @zxing/library](https://github.com/zxing-js/library) | 0.23.0 | Apache-2.0 | 多码制识别（`vendor/zxing.min.js`，`vendor/LICENSE.zxing.txt`） |

> 两者均为 UMD 构建，已本地化，无 CDN 依赖。若升级版本，请同步替换许可证文件。

## 运行时依赖（Python 本地版，`requirements.txt`）

| 组件 | 许可 | 用途 |
|---|---|---|
| [zxing-cpp](https://github.com/zxing-cpp/zxing-cpp) (Python 绑定) | Apache-2.0 | 主力引擎：QR/DataMatrix/Aztec/PDF417/一维码 |
| [OpenCV](https://opencv.org/) (opencv-contrib-python-headless) | Apache-2.0 | QRCodeDetector、图像预处理；WeChatQRCode 模块（可选） |
| [ZBar](http://zbar.sourceforge.net/) / [pyzbar](https://github.com/NaturalHistoryMuseum/pyzbar) | LGPL-2.1（ZBar）/ MIT（pyzbar） | 一维码与二维码；注意 ZBar 为 LGPL，动态链接使用 |
| [Pillow](https://python-pillow.org/) | HPND | 图像读取（兼容中文路径、EXIF 方向） |
| [NumPy](https://numpy.org/) | BSD-3-Clause | 数组运算 |
| WeChatQRCode 模型文件（可选，不随仓库分发） | Apache-2.0（OpenCV 项目） | 小尺寸/模糊二维码增强 |

## 关于 v1 兼容引擎与上游项目

`qrsuite/core.py` 中的 `OriginalEngine` 会以子进程方式调用 **QRCodeScanner.exe**（原作者作品），
仅传递图片路径并解析其标准输出。

| 角色 | 主体 | 链接 |
|---|---|---|
| 原作 | **ZapcoMan** | https://github.com/ZapcoMan/QRCodeScanner |
| 二创（本项目 v2） | **ZboY** | https://github.com/ibsibxi |

- 该二进制及其源码的版权归**原作者所有**，**不随本仓库分发**（本地留档在 `03-原版样本/`，已 gitignore）。
- 撰写时本机 DNS 屏蔽 GitHub，**未能核实原仓库许可证**；若原作未声明许可证，
  公开发布/再分发前请先取得原作者同意，并按其要求补充署名。

