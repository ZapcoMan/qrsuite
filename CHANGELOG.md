# 变更记录

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [2.1.0] — 2026-10-06

### 新增 Added
- **样式化私有码结构识别 `qrsuite/stylized.py`**：微信小程序码 / 微信赞赏码 / 抖音主页码
  这三类是平台私有的放射/圆环状码，**无法离线解出内容**（本仓库 `tools/NOTES-stylized-codes.md`
  记录了 4 引擎 × 18 预处理的 0 命中实测）。新增的模块不尝试解码，只做**结构判定与几何测量**：
  是哪一家的码、定位点数、圆心、模块尺度、估计线数、角向主分度格数。
  - 判定内核复用本次调研中**被实测验证过**的两条管线（不是新造阈值）：
    抖音式 4 定位点（HSV 白盘 → 连通域牛眼 → 正方形/同心校验）与
    微信式 3+1 牛眼（同心环 → 等腰直角三角形 → 圆心=矩形第四角）。
  - 实测：`real_douyin.jpg` 正方形误差 0.0051、置信度 0.88；
    `real_wechat_reward.jpg` 圆心 (575.8,419.8)、等腰直角误差 0.0003、角向主分度 36.0 格/圈、置信度 1.00。
- **命令行**：`--stylized/--no-stylized`（默认开）。全部引擎失败时输出「ⓘ 结构判定」及
  面向用户的提示（如"这是抖音主页码，请用抖音扫一扫"），JSON 输出同步携带 `stylized` 字段。
- **网页端**：`/api/decode` 的响应已带 `stylized`（走 `Result.to_dict()`），
  `docs/app.js` 在未解码时渲染该判定块，`docs/i18n.js` 补中英文案 4 键。
- **测试**：`tests/test_stylized.py`（6 项断言：两类真样本判定 + 几何精度 + 性能预算 <0.6s）。

### 变更 Changed
- `Decoder.decode_path/decode_bytes/decode_arrays` 新增 `stylized=True` 参数；
  **仅在全部引擎未命中时**运行结构判定，命中路径行为与耗时不变
  （13 张基准：balanced 0.52s / 12-13 命中，与改动前一致）。
- `docs/sw.js` 缓存版本 `qrsuite-v2.0.7` → `qrsuite-v2.1.0`（遵循本仓库"改 docs 必升版本"的约定）。

### 已知限制 Known limitations
- **普通二维码可能被判为微信族**：QR 的三个定位符本来就构成等腰直角三角形，纯几何无法与
  微信牛眼区分（`h_noise.png` 等）。实际管线中这类图会被标准引擎先解出，`classify` 不会被调用。
- 环宽比判别（QR 1:1:3:1:1 vs 微信 0.8:1.2:1:1.2:0.8）**试过但失败**，未采纳
  （径向剖线抽不出干净的环序列，见 `07-太阳码调研/exp_ring_ratio.py`）。

---

## [2.0.4] — 2026-10-06

### 新增 Added
- **网页端中英双语**：\docs/i18n.js\（78 个文案键，中英完全对齐），右上角一键切换，
  并自动跟随浏览器语言（\zh*\ → 中文，其余 → 英文）。Android 同步补 es/values-en\。
- **Android 发布由 CI 自动签名**：打 \*\ tag 触发 \.github/workflows/release.yml\，
  构建正式签名 APK → 自动校验「不是 debug 证书」→ 上传到对应 Release。
- Windows 构建/签名脚本 \	ools/build_windows.py\（\--sign\ 走 \signtool\）与
  \.github/workflows/windows.yml\（配置证书 Secrets 后自动签名）。

### 修复 Fixed
- **彩色/蓝屏照片解不出码**：浏览器端只用亮度公式灰度，而蓝色 LCD 的蓝色通道占绝对主导，
  亮度公式给蓝仅 0.114 权重，导致白底/码点灰度差被压到 149，jsQR 判不出。
  现对彩色图增加**逐通道灰度**（按对比度从高到低尝试原图与 Otsu）。
  实测 43 张样例解出数 36 → 37、总耗时未增加、无回归。
- **状态条永久停在「正在初始化…」**：\#env\ 挂了 \data-i18n\，i18n 的 \pply()\ 在
  DOMContentLoaded 时用 textContent 覆盖了 app.js 刚写入的环境信息。
- **\data-i18n-html\ 元素漏译**：\querySelectorAll('[data-i18n]')\ 不匹配
  \data-i18n-html/-title/-content\（属性名不同），导致两处含内联标签的文案在英文界面下仍为中文。
- 页脚链接此前无 \\ 规则、使用浏览器默认链接蓝，现统一为品牌色。

---

## [2.0.3] — 2026-10-06

不规则二维码（抖音主页码 / 微信赞赏码这类「中心大 logo + 彩色 + 截图模糊」的码）专项调研与改进。
结论先行：**瓶颈不在本项目的预处理级联**，而是微信引擎一直被误判为不可用。

### 修复 Fixed

- **`WeChatEngine` 实际从未运行**：它要求 `detect/sr` 的 4 个模型文件存在才启用，而 **OpenCV 5.0 起
  `cv2.wechat_qrcode.WeChatQRCode()` 可无参构造，模型已编进 `cv2.pyd`**，无需任何外部文件。
  现改为「优先无参构造，旧版回退到 4 文件」，该引擎终于真正生效。
- Windows 单文件版打包补上 `--hidden-import cv2.wechat_qrcode`，否则 PyInstaller 不带 contrib 子模块
  （实测打包版 `/health` 由 `["cv2","zbar","zxing"]` 变为 `["cv2","wechat","zbar","zxing"]`）。

### 性能 Performance

微信模型约 20ms/张，比其它引擎贵一个量级，因此做成**惰性引擎**：只有 zxing/cv2/zbar 全部失败后，
才补跑一次原图（`LAZY_ENGINES` / `LAZY_MAX_STAGES`）。`fast` 模式完全不启用它。

同进程、3 次取中位数（新增 27 张不规则压力样例）：

| 数据集 | 改动前 | 改动后 | 说明 |
|---|---|---|---|
| 原 13 张基准 | 12/13，32.6 ms/张 | 12/13，34.4 ms/张 | 差异在噪声范围 |
| 27 张不规则 | 25/27，61.1 ms/张 | **26/27**，69.9 ms/张 | 多解出「顶部被裁」那张，只有微信引擎能解 |

### 已评估但未采纳（有测量数据）

- **新增预处理变体**：CLAHE、对比拉伸、四周补白、放大 2×/3×、自适应阈值全部实测增益为 **0**；
  自适应阈值反而把命中从 25 打到 6（会毁掉干净码）。因此没有往级联里加任何阶段——避免白白拖慢。
- **两定位符几何重建**（参考 qqAys/Robust-QR-Code-Detector）：定位符检测严重误报（干净图也报 4~19 个），
  产出数百无效组合、0 命中；需严格的 1:1:3:1:1 扫描线校验才可用，投入大且收益不确定，未并入。

### 已知限制 Known limitations

- 仍无法解码**整行定位符丢失**的严重残缺码（如底部被裁 20%，`j_long_cropped20.png`）——
  这需要真正的几何重建能力，属当前边界。
- 版本号字符串（`qrsuite/__init__.py`、`docs/sw.js`、`app/build.gradle`、README 徽标）尚未统一升到 2.0.3，
  留待下次一并处理；CHANGELOG 与 `qrsuite/winapp.py` 的 `--version` 输出可能暂时不一致。

---

## [2.0.0] — 2026-10-06

首个 v2 版本：把「命令行工具 + 本地网页 + 多引擎解码」合并为一套代码，并做成可直接部署到 GitHub Pages 的静态站。

### 新增 Added

**输入方式（原版只能手动交互输入）**
- 命令行参数：图片路径、目录（自动递归）、通配符、图片 URL，可一次多个
- Windows 拖拽启动器：把图片/文件夹拖到 `.bat` 上直接识别
- 网页端：拖拽、点击选择、`Ctrl+V` 粘贴截图，支持一次多张并发
- 无参数时保留交互式输入（兼容原版习惯）

**解码能力**
- 单引擎 → **多引擎并联**：zxing-cpp + OpenCV QRCodeDetector + zbar(pyzbar) + 可选 WeChatQRCode + 原版 bardecoder
- 码制：仅 QR → **QR / MicroQR / DataMatrix / Aztec / PDF417 / Code128·39·93 / EAN·UPC / ITF / Codabar**
- **交叉验证模式**（`--verify`）：要求 ≥2 引擎结果一致才判定成功，抑制误读
- **三档解码模式**：`fast` / `balanced` / `deep`，按场景取舍速度与识别率
- 结果**按内容去重**，并标注命中的引擎与生效的预处理变体

**输出与集成**
- JSON 输出（`--json`）
- 网页识别历史（localStorage）+ 导出 JSON / CSV
- 结果一键复制；内容为网址时可一键打开
- 命令行退出码语义化：解出 ≥1 条 = 0

**工程化**
- 合并为单一 Python 包 `qrsuite`（`core` 引擎策略 / `cli` 入口 / `web` 服务 / `models` 模型）
- 本地服务统一入口 `python -m qrsuite --serve`，并内置**结果缓存**（图片哈希 + 模式）
- `docs/` 改写为**纯前端静态站**（jsQR + ZXing-js 本地化，无 CDN 依赖），可直接跑在 GitHub Pages
- 静态站可**自动探测本地 Python 后端**并启用「本机增强引擎」
- 浏览器解码全部移入 **Web Worker**，界面不阻塞
- `run.bat` 菜单式入口（网页版 / 交互 / 快速 / 深度 / 下载模型 / 基准）
- 测试：`tests/smoke_test.py`（引擎可用性 + 端到端 + 早退行为）、`tests/bench.py`（v1 与 v2 性能精度对比）
- 文档：`README.md`、`MANUAL.md`（+ 网页版 `docs/manual.html`，构建脚本 `tools/build_manual.py`）
- 仓库：`LICENSE`(MIT)、`THIRD_PARTY_NOTICES.md`、`.gitignore`、`.gitattributes`、GitHub Actions Pages 工作流

### 性能 Performance

同样 13 张用例（6 种码制 + 7 种困难场景）、同一台机器：

| 指标 | v1 旧流程 | v2 默认（balanced） | 变化 |
|---|---:|---:|---:|
| 墙钟时间 | 3.40 s | 0.32 s | **10.5× 更快** |
| CPU 时间 | 6.78 s | 0.45 s | **15× 更低** |
| 预处理阶段总数 | 234 | 21 | **11× 更少** |
| 解出数量 | 12/13 | 12/13 | 持平 |

优化手段：
- **级联 + 早退**：变体按「命中率高 / 代价低」排序，命中即停（原先 18 个变体全跑完）
- **分辨率闸门**：大图（>1800px）先降采样；仅小图（<700px）才做放大，跳过最贵的无效变体
- **减少拷贝**：灰度只计算一次并复用；裁剪为数组切片零拷贝；全程 NumPy/OpenCV（原先每个变体都做 PIL 往返）
- **缓存**：本地服务对「图片哈希 + 模式 + 引擎集合」缓存结果，重复请求即时返回
- 浏览器端：平均 **44 ms/张**（fast）、平均仅 **1.2 个阶段**，且运行在后台线程

### 修复 Fixed

- 原版「拖到图标上/带参数启动无反应」——因为它不读命令行参数（仅 `stdin`），现已支持全部输入方式
- 原版「双击后窗口一闪而过」——现所有启动器末尾均等待按键
- 中文路径读图：改用 Pillow + EXIF 方向处理（规避 Windows 下 `cv2.imread` 不支持中文路径的问题）
- 原版无输出汇总/无结构化结果——现提供逐项明细、统计与 JSON

### 兼容性 Compatibility

- 原版 `QRCodeScanner.exe` **仍可作为 `original` 引擎挂载**使用（`--original-exe` 或环境变量 `QRSUITE_ORIGINAL_EXE`），仅在 `deep` 模式对本地文件生效
- **破坏性变更**：入口由 `python qrsuite.py` 改为 `python -m qrsuite`；原 `qrweb.py` 由 `python -m qrsuite --serve` 取代（旧文件保留亦不受影响）
- 未随仓库分发任何第三方二进制；模型文件与 v1 exe 需自备（见 `MANUAL.md` 第 6 章）

### 已知限制 Known limitations

- 浏览器端（jsQR + ZXing-js）识别率略低于 Python 端：某张强噪声用例仅 Python 端（OpenCV/zbar）能解出；需要时在本机跑 `--serve` 启用「本机增强引擎」
- WeChatQRCode 模型未内置，需 `--fetch-models`（多镜像回退）；若网络屏蔽 GitHub 需手动放置 4 个模型文件
- GitHub Pages 为纯静态托管，无后端，因此线上页面不包含 OpenCV / WeChatQRCode 引擎

---

## [1.x] — 原版（原作者）

- Rust 单文件 CLI `QRCodeScanner.exe`，单引擎（bardecoder）+ 多预处理变体
- 仅支持交互式输入（启动提示后手动输入图片路径或 URL）
- 不支持命令行参数、无网页界面、无结构化输出
