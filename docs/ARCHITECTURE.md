# 架构与实现原理

本文说明 QRSuite v2 的整体架构、解码流水线设计与性能取舍。适合想理解"为什么快"、
或想二次开发的人阅读。

---

## 一、三种形态，一套策略

```
                    ┌──────────────────────────────────────┐
                    │  共享的解码策略（级联 + 早退 + 多引擎）  │
                    └──────────────────────────────────────┘
                          │              │              │
        ┌─────────────────┘              │              └─────────────────┐
        ▼                                ▼                                ▼
┌────────────────┐            ┌────────────────────┐            ┌──────────────────┐
│ Python CLI/服务 │            │ 浏览器静态站 docs/   │            │ Android 原生 App  │
│ qrsuite/       │            │ jsQR + ZXing-js    │            │ CameraX + ML Kit │
│ zxing-cpp      │            │ (Web Worker 内解码) │            │ (C++ 原生推理)     │
│ OpenCV / zbar  │            │ 无 CDN、可离线       │            │ 无网络权限         │
│ WeChatQRCode   │            │                    │            │                  │
└────────────────┘            └────────────────────┘            └──────────────────┘
   高精度 / 批量                  零安装 / 可分享                  随手扫 / 移动端
```

三端**不共享代码**（语言与运行环境不同），但共享同一套工程策略：
**按"代价低 / 命中率高"排序，命中即停**。这是 v2 相对 v1 提速的根本原因。

---

## 二、Python 端：级联 + 早退

### 2.1 为什么 v1 慢

v1 对每张图**穷举** 18 种预处理变体 × N 个引擎，全部跑完才汇总。
绝大多数图片在**第一个变体**（原图）就已经能解出来，后面的 17 个变体纯属浪费。

### 2.2 v2 的做法

`qrsuite/core.py` 的 `build_stages()` 生成一个**有序**变体序列，`Decoder.decode_arrays()`
逐级尝试，**一旦有命中立即停止**：

```
阶段 0  原图            ← 命中率最高、代价最低，绝大多数图在这一步就结束
阶段 1  灰度
阶段 2  放大 2×         ← 仅小图（<700px）才生成，大图跳过
阶段 3  Otsu 二值化
阶段 4  CLAHE
阶段 5  放大 3×         ← 同样仅小图
阶段 6  反色
阶段 7  自适应阈值
...
阶段 16 中心/四角裁剪    ← 最贵，最后才用
```

关键点：**变体是惰性生成的**（生成器），大图不会白白生成"放大 3×"这种只会更慢的变体。

### 2.3 三档模式

| 模式 | 阶段上限 | 引擎 | 定位 |
|---|---:|---|---|
| `fast` | 2 | zxing, cv2 | 单张秒出，只试原图/灰度 |
| `balanced`（默认） | 7 | zxing, cv2, zbar | 覆盖到二值化级别 |
| `deep` | 全部 | + wechat, original | 最难图；仍命中即停 |

### 2.4 引擎与惰性策略

| 引擎 | 依赖 | 特点 |
|---|---|---|
| `zxing` | zxing-cpp | 主力，多码制，速度快 |
| `cv2` | OpenCV QRCodeDetector | 与 zxing 互补 |
| `zbar` | pyzbar (libzbar) | 一维码强项 |
| `wechat` | OpenCV wechat_qrcode | **代价高**（约 20ms/张 + 固定初始化） |
| `original` | v1 的 QRCodeScanner.exe | 仅 deep、仅本地文件 |

`wechat` 被标记为**惰性引擎**（`LAZY_ENGINES`）：只在便宜引擎**全部失败后**才补跑一次。
它不放在默认 `balanced` 里——实测会让默认墙钟翻倍，而它多解出的图与
"抖音/赞赏码"无关（那类私有码它同样不支持），为默认路径付 2× 代价不划算。

### 2.5 其它优化

- **灰度只算一次**并全程复用；裁剪用数组切片（零拷贝）。v1 每个变体都做 PIL 往返。
- **分辨率闸门**：长边 >1800px 先降采样；只有小图才放大，避免"放大反而更慢"。
- **结果缓存**：本地服务按「图片哈希 + 模式 + 引擎集」缓存，重复请求直接命中。

---

## 三、浏览器端：零依赖静态站

- `docs/` 就是站点根目录，**零构建、零依赖**，任意静态托管可直接跑。
- jsQR + ZXing-js **已本地化进仓库**（`docs/vendor/`），不依赖任何 CDN，可完全离线。
- 解码跑在 **Web Worker** 里，界面不阻塞；主线程只负责交互与渲染。
- `file://` 下无法创建 Worker，自动**回退主线程**解码，并在顶部状态条说明当前环境。
- 可选**本机增强**：页面探测到本地 `python -m qrsuite --serve` 时，可把图片交给
  Python 端多引擎处理（网页版拿不到的 OpenCV/zbar 能力）。

> 注意：`file://` 下从 URL 加载的图片会污染 canvas（`getImageData` 抛 SecurityError），
> 因此自检二维码用 **data URI 内嵌**在 `app.js` 里。

---

## 四、Android 端：原生 CameraX + ML Kit

### 4.1 为什么不用 WebView

WebView 方案需要把 `docs/` 打进 assets，且相机/Worker 需要 https 源
（要用 `WebViewAssetLoader`）；解码跑 JS，**CPU 占用明显高于原生**。
所以选择原生：CameraX 取景 + ML Kit（C++ 推理），并配上真正的原生 UI。

### 4.2 降 CPU 的三个手段

1. **中央裁切**：只把与取景框对应的中央区域（屏幕方向 80%×52%）重排成 NV21 交给
   ML Kit，像素量约为全帧 40%。注意 ML Kit 会按 `rotationDegrees` 旋转，
   所以裁切要**先在屏幕方向算好再映射回缓冲区**。
2. **背压 KEEP_ONLY_LATEST**：识别跟不上时直接丢帧，不排队累积。
3. **720p 分析分辨率**：`setTargetResolution(1280, 720)` 足够识别二维码，
   比 1080p 少约 55% 像素。

### 4.3 其它

- **格式收敛**：`BarcodeScannerOptions` 只注册 QR/DataMatrix/Aztec/PDF417/常用一维码。
- **仅 arm64**：`.so` 只打 `arm64-v8a`，体积 23.4 MB → 7.59 MB。
- **零网络权限**：Manifest 里用 `tools:node="remove"` 显式移除依赖库合并进来的
  `INTERNET` / `ACCESS_NETWORK_STATE`，保证"图片不出设备"可被审计验证。
- 12 及以下没有 `READ_MEDIA_IMAGES`，相册选图走 `ACTION_GET_CONTENT` 回退。

---

## 五、已知能力边界

**标准二维码/条码**：三端都能解，且对轻微的 logo 遮挡、低对比、模糊、旋转有容错。

**样式化私有码**（抖音主页码、微信赞赏码/小程序码）：**解不了**，而且不是本项目的缺陷。
这类码的模块被渲染成**圆点/圆环**，破坏了标准 QR 解码依赖的两个前提：
定位符的 1:1:3:1:1 直线扫描判定、以及方块模块的采样网格。实测
`QRCodeDetector.detect()` 直接返回 `False`——**连"检测到码"都做不到**。

更根本的是，微信赞赏码/小程序码是**同心圆环结构**，数据按环排布，
还原链接或 `scene` 参数需要**平台服务端的业务密钥**；抖音码同理。
这已不属于解码器能力问题，而是平台私有加密协议。详见
[`tools/NOTES-stylized-codes.md`](NOTES-stylized-codes.md)（含对若干第三方方案的评估结论）。

---

## 六、目录结构

```
01-qrsuite-v2/
├── qrsuite/            Python 包
│   ├── core.py         解码核心：引擎、预处理级联、早退、缓存
│   ├── cli.py          命令行入口
│   ├── web.py          本地 HTTP 服务（供网页版调用）
│   ├── winapp.py       Windows 单文件版入口
│   └── models.py       数据模型
├── docs/               纯前端静态站（GitHub Pages 根目录）
│   ├── app.js  decode.js  decode.worker.js
│   └── vendor/         jsQR / ZXing-js（已本地化）
├── android/            Android 原生 App（Gradle 子项目）
│   └── app/src/main/java/com/qrsuite/scanner/
│       ├── MainActivity.java      相机 + 识别 + 面板
│       ├── ScanOverlayView.java   取景遮罩自绘
│       └── HistoryStore.java      历史记录（SQLite）
├── tests/              smoke_test.py（引擎与早退自检）、bench.py（性能对比）
├── tools/              构建与实验脚本、踩坑与调研记录
└── .github/workflows/  Pages 部署 + Android CI
```
