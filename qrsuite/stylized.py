# -*- coding: utf-8 -*-
"""qrsuite.stylized —— "样式化私有码"的结构识别与几何测量。

## 这是什么

微信小程序码（菊花码/太阳码）、微信赞赏码、抖音主页码这三类是**平台私有**的
放射/圆环状码。它们：

* **解不出内容**：协议私有、规格未公开、无任何公开实现（本仓库 NOTES-stylized-codes.md
  记录了 4 引擎 × 18 预处理的 0 命中实测）；
* **也没有"解出来能多拿什么"的收益**：2026-10-06 实测（官方抖音 40.0.0 + logcat）
  扫一张抖音主页码，客户端解出的 payload 是 `snssdk1128://user/profile` ——
  一条"打开某用户主页"的**明文深链**，不含路径/参数/票据；
* **抓包路线同样不通**：字节自研 TTNet/Cronet 在 native 层直连，实测 `is_proxy=0`，
  绕过系统代理与 VPN。

所以本模块**只做识别与测量**，不尝试解码。它回答的问题是：

    这张图是不是这类码？是哪一家？几何参数（定位点数、模块尺度、码半径、
    估计线数、角向主分度）是什么？

## 用途

全部标准引擎都失败时的**可解释失败**：与其只说"未解码"，不如告诉用户
"这是一张抖音主页码，请用抖音扫一扫" —— 见 `hint()`。

## 判定依据（来自已验证的检测内核，不新造阈值）

| 路线 | 判据 | 实测 |
|---|---|---|
| 抖音主页码 | 4 个环形定位点构成正方形，且质心≈码盘圆心 | `real_douyin.jpg`：正方形误差 0.0000、质心/盘心偏差 5.7px |
| 微信族 | 3 个牛眼构成等腰直角三角形，圆心=矩形第四角 | `real_wechat_reward.jpg`：等腰直角误差 0.0003、角向主分度 36.0 格/圈 |

已知局限（会误判的情形）：
* **带噪的普通二维码**可能被误判为微信族 —— QR 的三个定位符本来就构成等腰直角三角形，
  纯几何无法区分。已用 `angular_div` 作软指标缓解，未彻底解决。
* 叠加了辅助线的可视化标注图会干扰定位点检测。
"""
from __future__ import annotations

import math
import itertools
from dataclasses import dataclass, field, asdict

import numpy as np
import cv2

__all__ = ['StylizedInfo', 'classify', 'hint', 'KIND_LABELS']

# ------------------------------------------------------------------ 常量

KIND_LABELS = {
    'douyin_profile':    '抖音主页码',
    'wechat_miniprogram': '微信小程序码',
    'wechat_reward':     '微信赞赏码',
    'wechat_radial':     '微信样式化码',
    'unknown':           '未识别的样式化码',
}

HINTS = {
    'douyin_profile': '这是抖音主页码（平台私有格式，无法离线解出内容）。请打开抖音 App「扫一扫」识别。',
    'wechat_miniprogram': '这是微信小程序码（平台私有格式，无法离线解出内容）。请用微信「扫一扫」识别。',
    'wechat_reward': '这是微信赞赏码（平台私有格式，且涉及支付，无法离线解出内容）。请用微信「扫一扫」识别。',
    'wechat_radial': '这看起来是微信的样式化码（平台私有格式，无法离线解出内容）。请用微信「扫一扫」识别。',
    'unknown': '',
}


# ------------------------------------------------------------------ 结果

@dataclass
class StylizedInfo:
    kind: str = 'unknown'
    confidence: float = 0.0
    geometry: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)

    def to_dict(self):
        d = asdict(self)
        d['label'] = self.label
        d['hint'] = hint(self)
        return d


def hint(info: 'StylizedInfo') -> str:
    """给最终用户的一句话提示（用于解码失败的场景）。"""
    return HINTS.get(info.kind, '')


# ------------------------------------------------------------------ 检测内核

def _gray(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def _downscale(g, max_side=1000):
    h, w = g.shape
    s = max_side / max(h, w)
    return cv2.resize(g, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else g


def _ring_score(dark, cx, cy, R, n_ang=40):
    """环形定位点评分：中心黑 + 环黑 + 环外白 + 各向一致性 → [-1, ~2]。"""
    u = R / 4.0
    h, w = dark.shape
    cen, ring, out = [], [], []
    for a in np.linspace(0, 2 * np.pi, n_ang, endpoint=False):
        ca, sa = math.cos(a), math.sin(a)
        x, y = int(round(cx + 0.55 * u * ca)), int(round(cy + 0.55 * u * sa))
        if 0 <= x < w and 0 <= y < h:
            cen.append(dark[y, x])
        vs = []
        for t in (1.05 * u, 1.7 * u, 2.4 * u):
            x, y = int(round(cx + t * ca)), int(round(cy + t * sa))
            if 0 <= x < w and 0 <= y < h:
                vs.append(dark[y, x])
        if vs:
            ring.append(float(np.mean(vs)))
        x, y = int(round(cx + 4.1 * u * ca)), int(round(cy + 4.1 * u * sa))
        if 0 <= x < w and 0 <= y < h:
            out.append(dark[y, x])
    if len(cen) < 8 or len(ring) < 8 or len(out) < 8:
        return -1.0
    c, r, o = float(np.mean(cen)), float(np.mean(ring)), float(np.mean(out))
    cons = float(np.mean([1.0 if v > 0.5 else 0.0 for v in ring]))
    return 0.9 * c + 0.9 * r - 1.1 * o + 0.6 * cons - 0.5


def _radial_flips(dark, cx, cy, rmax):
    """沿直径方向的环跳变数（牛眼 = 同心环 → 跳变数高）。"""
    vals = []
    for t in np.linspace(-rmax, rmax, max(6, int(rmax * 2))):
        x, y = int(round(cx)), int(round(cy + t))
        if 0 <= y < dark.shape[0] and 0 <= x < dark.shape[1]:
            vals.append(dark[y, x])
    v = np.array(vals, dtype=bool)
    return int(np.sum(v[1:] != v[:-1])) if len(v) > 3 else 0


def _largest_mask_blob(mask):
    n, _lbl, stats, cents = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if n <= 1:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    cw, ch = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
    area = int(stats[i, cv2.CC_STAT_AREA])
    return {'center': (float(cents[i][0]), float(cents[i][1])),
            'r': max(cw, ch) / 2.0, 'area': area,
            'fill': area / float(max(cw * ch, 1))}


def _masks(rgb, gray):
    """返回 [(名字, 暗掩膜, 白掩膜)]：灰度 OTSU 与 HSV 白盘两种独立分割。"""
    out = []
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    out.append(('otsu', (bw < 128).astype(np.uint8), (bw >= 128).astype(np.uint8)))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    sat, val = hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    out.append(('hsv', ((sat > 60) & (val < 245)).astype(np.uint8),
                ((sat < 50) & (val > 200)).astype(np.uint8)))
    return out


def _lab_dark_white(rgb):
    """移植自 analyze_douyin.load_binary：HSV 低饱和+高明度=白盘，高饱和偏暗=码点。"""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    sat, val = hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    white = ((sat < 45) & (val > 205)).astype(np.uint8)
    dark = ((sat > 60) & (val < 240)).astype(np.uint8)
    return dark, white


def _find_disc(white):
    """移植自 analyze_douyin.find_disc：最大白连通域 = 码盘。"""
    n, _lbl, stats, cents = cv2.connectedComponentsWithStats(white, 8)
    if n <= 1:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y = int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP])
    cw, ch = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
    area = int(stats[i, cv2.CC_STAT_AREA])
    return {'bbox': [x, y, cw, ch], 'cent': [float(cents[i][0]), float(cents[i][1])],
            'area': area, 'fill': round(area / float(max(cw * ch, 1)), 3)}


def _find_bullseyes(dark, disc, dense=True):
    """连通域牛眼检测（移植自 analyze_douyin.find_bullseyes）。

    dense=True 时额外做**稠密环带搜索**：网格步长可能正好错过牛眼圆心，
    而牛眼是规则同心环结构，稠密搜索能兜住这种情况（实测在 real_douyin 上补齐 4 个定位点）。
    """
    cx, cy = disc['cent']
    bx, by, bw, bh = disc['bbox']
    r_disc = max(bw, bh) / 2.0
    yy, xx = np.mgrid[0:dark.shape[0], 0:dark.shape[1]]
    r_map = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    mask = ((dark > 0) & (r_map <= r_disc * 1.02)).astype(np.uint8)
    n, _lbl, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
    cand = []
    for i in range(1, n):
        w0, h0 = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
        area = int(stats[i, cv2.CC_STAT_AREA])
        if w0 < 12 or h0 < 12 or area < 50:
            continue
        if not (0.6 < w0 / h0 < 1.7):
            continue
        fill = area / (w0 * h0)
        if not (0.10 <= fill <= 0.70):
            continue
        ccx, ccy = float(cents[i][0]), float(cents[i][1])
        r_c = math.hypot(ccx - cx, ccy - cy)
        if not (r_disc * 0.5 < r_c < r_disc * 1.0):
            continue
        R = (w0 + h0) / 4.0
        hit = _bullseye_verify(dark, ccx, ccy, R)
        if hit:
            cand.append(hit)

    if dense:
        # 稠密搜索：以盘心为基准，沿"到盘心的距离"和角度扫描，覆盖被网格错过的心。
        #
        # 注意（实测教训）：即使它**没有增加最终候选数量**，也**不能跳过**——
        # 试过"连通域已找到 ≥4 个高分牛眼就跳过稠密搜索"的早退优化，
        # 结果抖音码被误判成微信族：因为稠密搜索产生的重复候选会参与排序与去重，
        # 从而改变 _pick_four 实际看到的集合。判定正确性优先于这点开销。
        rr = np.arange(r_disc * 0.55, r_disc * 0.98, max(2.0, r_disc * 0.02))
        for R in (r_disc * 0.085, r_disc * 0.105, r_disc * 0.13):
            if R < 5:
                continue
            for r in rr:
                for a in np.linspace(0, 2 * np.pi, 64, endpoint=False):
                    x = cx + r * math.cos(a)
                    y = cy + r * math.sin(a)
                    hit = _bullseye_verify(dark, x, y, R)
                    if hit and hit['score'] > 0.55:
                        cand.append(hit)
    cand.sort(key=lambda c: -c['score'])
    keep = []
    for c in cand:
        if all((c['x'] - k['x']) ** 2 + (c['y'] - k['y']) ** 2 > (max(c['R'], k['R']) * 1.5) ** 2
               for k in keep):
            keep.append(c)
        if len(keep) >= 12:
            break
    return keep


def _bullseye_verify(dark, ccx, ccy, R):
    """验证 (ccx,ccy,R) 是否为一个牛眼（中心黑 + 环黑 + 环外白）。命中返回候选，否则 None。

    性能说明：本函数在稠密搜索里会被调用数千次，占整个判定 ~90% 的时间。
    因此先用少量像素做一次**保守预筛**（真牛眼中心必然是黑的），
    预算中不通过就直接返回，避免为每个候选都重建极坐标网格。
    """
    py0, py1 = int(ccy - R), int(ccy + R + 1)
    px0, px1 = int(ccx - R), int(ccx + R + 1)
    if py0 < 0 or px0 < 0 or py1 > dark.shape[0] or px1 > dark.shape[1] or py1 <= py0 or px1 <= px0:
        return None
    patch = dark[py0:py1, px0:px1]
    ph, pw = patch.shape

    # --- 预筛：中心 0.15R 圆内取 8 个采样点，要求 ≥6 个是暗的 ---
    # 阈值刻意保守（验证阶段要求 center_frac ≥ 0.6），避免把真眼拒掉。
    r_in = max(1.0, R * 0.15)
    ccx_i, ccy_i = (pw - 1) / 2.0, (ph - 1) / 2.0
    dark_hits = 0
    for k in range(8):
        a = k * math.pi / 4.0
        sx = int(round(ccx_i + r_in * math.cos(a)))
        sy = int(round(ccy_i + r_in * math.sin(a)))
        if 0 <= sy < ph and 0 <= sx < pw and patch[sy, sx]:
            dark_hits += 1
    if dark_hits < 6:
        return None

    pjy, pjx = np.mgrid[0:ph, 0:pw]
    pr = np.sqrt((pjx - ccx_i) ** 2 + (pjy - ccy_i) ** 2)
    m_c = pr < R * 0.22
    m_r = (pr > R * 0.35) & (pr < R * 0.95)
    m_o = (pr > R * 1.02) & (pr < R * 1.6)
    if not (m_c.any() and m_r.any() and m_o.any()):
        return None
    center_frac = float(patch[m_c].mean())
    ring_frac = float(patch[m_r].mean())
    around_frac = float(patch[m_o].mean())
    if center_frac < 0.6:
        return None
    score = center_frac - around_frac
    if score <= 0.25:
        return None
    return {'x': float(ccx), 'y': float(ccy), 'R': float(R), 'flips': 0,
            'score': round(score, 3), 'center_frac': round(center_frac, 2),
            'ring_frac': round(ring_frac, 2), 'around_frac': round(around_frac, 2),
            'fill': 0.0}


def _pick_four(cand, disc):
    """移植自 analyze_douyin.pick_four：同一环带 + 半径接近 + 正方形 + 质心≈盘心。"""
    dc = np.array(disc['cent'])
    for c in cand:
        c['r_c'] = float(math.hypot(c['x'] - dc[0], c['y'] - dc[1]))
    pool = [c for c in cand if c.get('center_frac', 1) > 0.65]
    best = None
    for combo in itertools.combinations(pool[:12], 4):
        rs = np.array([c['r_c'] for c in combo])
        if rs.max() - rs.min() > rs.mean() * 0.12:
            continue
        pts = np.array([[c['x'], c['y']] for c in combo])
        cen = pts.mean(axis=0)
        d = sorted(float(np.linalg.norm(pts[i] - pts[j]))
                   for i in range(4) for j in range(i + 1, 4))
        side, diag = float(np.mean(d[:4])), float(np.mean(d[4:6]))
        if side <= 0:
            continue
        sq = abs(diag / side - math.sqrt(2))
        cen_err = float(np.linalg.norm(cen - dc))
        score = cen_err / 5.0 + sq * 300.0 + (rs.max() - rs.min()) / 5.0
        if best is None or score < best[0]:
            best = (score, combo, cen, (side, diag, sq, float(rs.mean()),
                                        float(rs.max() - rs.min()), cen_err))
    if best is None:
        return None, None, None
    return list(best[1]), best[2], best[3]


def _find_eyes_in_center(gray):
    """移植自 analyze_reward.find_eyes_in_center：中心区域找同心环牛眼（微信族）。"""
    h, w = gray.shape
    cx0, cy0 = w // 2, h // 2
    r = int(min(h, w) * 0.36)
    y0, y1 = max(0, cy0 - r), min(h, cy0 + r)
    x0, x1 = max(0, cx0 - r), min(w, cx0 + r)
    sub = gray[y0:y1, x0:x1]
    binary = (sub < 128).astype(np.uint8)
    n, _lbl, stats, cents = cv2.connectedComponentsWithStats(binary, 8)
    eyes = []
    for i in range(1, n):
        bw, bh = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
        area = int(stats[i, cv2.CC_STAT_AREA])
        if bw < 8 or bh < 8 or area < 40:
            continue
        if not (0.75 < bw / bh < 1.33):
            continue
        if area / (bw * bh) > 0.5:
            continue
        ccx, ccy = float(cents[i][0]), float(cents[i][1])
        rmax = min(bw, bh) / 2
        vals = []
        for t in np.linspace(-rmax, rmax, max(4, int(rmax * 2))):
            yy, xx = int(round(ccy + t)), int(round(ccx))
            if 0 <= yy < sub.shape[0] and 0 <= xx < sub.shape[1]:
                vals.append(sub[yy, xx])
        v = np.array(vals) < 128
        flips = int(np.sum(v[1:] != v[:-1])) if len(v) > 2 else 0
        if flips >= 3:
            eyes.append({'x': ccx + x0, 'y': ccy + y0, 'd': (bw + bh) / 2, 'flips': flips})
    eyes.sort(key=lambda e: -e['flips'])
    return eyes[:8]


def _fit_tri_center(pts):
    """3 牛眼 = 矩形三角 → 圆心 = 另两角中点。"""
    e = np.asarray(pts, float)
    best = None
    for order in itertools.permutations(range(3)):
        v, a, b = (e[i] for i in order)
        da, db = float(np.linalg.norm(v - a)), float(np.linalg.norm(v - b))
        sc = abs(da - db) / max(da, db, 1e-6)
        if best is None or sc < best[0]:
            best = (sc, (a + b) / 2.0)
    return best[1], best[0]


def _sq_err(pts):
    p = np.asarray(pts, float)
    d = sorted(float(np.linalg.norm(p[i] - p[j])) for i in range(4) for j in range(i + 1, 4))
    side, diag = float(np.mean(d[:4])), float(np.mean(d[4:6]))
    return (None, None) if side <= 0 else (side, abs(diag / side - math.sqrt(2)))


def _tri_err(pts):
    e = np.asarray(pts, float)
    best = None
    for o in itertools.permutations(range(3)):
        v, a, b = (e[i] for i in o)
        da, db = float(np.linalg.norm(v - a)), float(np.linalg.norm(v - b))
        sc = abs(da - db) / max(da, db, 1e-6)
        if best is None or sc < best[0]:
            best = (sc, (a + b) / 2.0)
    return best[1], best[0]


def _angular_div(gray, center, r0, r1, n_ang=1440):
    """极坐标展开后沿角度自相关 → 主分度数（微信族实测 36/54/72 格/圈）。"""
    if r1 <= r0 * 1.25:
        return None
    cx, cy = center
    ang = np.linspace(0, 2 * np.pi, n_ang, endpoint=False)
    rad = np.linspace(r0, r1, 200)
    A, R = np.meshgrid(ang, rad)
    X = (cx + R * np.cos(A)).astype(np.float32)
    Y = (cy + R * np.sin(A)).astype(np.float32)
    polar = cv2.remap(gray.astype(np.float32), X, Y, cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    band = polar[int(0.35 * 200):int(0.9 * 200), :]
    prof = (band < 128).mean(axis=0)
    prof = prof - prof.mean()
    ac = np.correlate(prof, prof, mode='full')[len(prof) - 1:]
    ac = ac / (ac[0] + 1e-9)
    peaks = [(lag, float(ac[lag])) for lag in range(3, 160)
             if ac[lag] >= ac[lag - 1] and ac[lag] >= ac[lag + 1] and ac[lag] > 0.15]
    peaks.sort(key=lambda t: -t[1])
    if not peaks:
        return None
    lag, val = peaks[0]
    return {'div': round(360.0 / (lag * 360.0 / n_ang), 1),
            'angle_deg': round(lag * 360.0 / n_ang, 3), 'peak': round(val, 3)}


# ------------------------------------------------------------------ 主入口

def classify(rgb, gray=None, max_side=1000) -> StylizedInfo:
    """判定 rgb（numpy HxWx3, RGB）是否为样式化私有码。

    调用方应已确认标准解码器全部失败（本函数不做标准 QR 排除，以免与引擎级联重复）。

    两条**已验证**的检测管线（逐字移植，不做"思路参考"）：
      A. 抖音式 4 定位点：HSV 白盘 → 连通域牛眼 → 4 点正方形 + 质心≈盘心
         （real_douyin.jpg 实测：正方形误差 0.0000、质心/盘心偏差 5.7px）
      B. 微信式 3+1 牛眼：中心区同心环 → 等腰直角三角形 → 圆心=矩形第四角
         （real_wechat_reward.jpg 实测：等腰直角误差 0.0003、圆心 (575.8,419.8)）
    """
    rgb = np.asarray(rgb)
    if gray is None:
        gray = _gray(rgb)
    # 注意：A/B 两条检测管线都在**原分辨率**上跑 —— 缩略到 1000px 会把牛眼环打碎，
    # 导致真实定位点被漏检（实测教训）。
    H, W = gray.shape

    # ---------------- 路线 A：抖音式 4 定位点 ----------------
    try:
        dark_l, white_l = _lab_dark_white(rgb)
        disc = _find_disc(white_l)
        if disc and disc['fill'] > 0.45:
            eyes = _find_bullseyes(dark_l, disc)
            four, cen, sq = _pick_four(eyes, disc) if len(eyes) >= 4 else (None, None, None)
            if four and sq is not None:
                side, diag, sqerr, rcm, rcsp, cenerr = sq
                disc_r = max(disc['bbox'][2], disc['bbox'][3]) / 2.0
                if sqerr <= 0.02 and cenerr <= 0.08 * max(disc_r, 1):
                    Rm = float(np.mean([e['R'] for e in four]))
                    mod = Rm / 3.5
                    r_code = disc_r
                    div = _angular_div(gray, tuple(cen), max(Rm * 2.0, 0.3 * r_code), r_code * 0.96)
                    geo = {
                        'center': [round(float(cen[0]), 1), round(float(cen[1]), 1)],
                        'n_eyes': 4,
                        'eyes': [{'x': round(e['x'], 1), 'y': round(e['y'], 1),
                                  'R': round(e['R'], 1), 'score': e['score']} for e in four],
                        'square_err': round(sqerr, 4),
                        'side_px': round(side, 1),
                        'centroid_vs_disc_px': round(cenerr, 1),
                        'disc_center': [round(disc['cent'][0], 1), round(disc['cent'][1], 1)],
                        'disc_fill': disc['fill'],
                        'module_px': round(mod, 2),
                        'code_radius_px': round(r_code, 1),
                        'est_lines': round(2 * r_code / mod, 0),
                        'image': [W, H],
                    }
                    if div:
                        geo['angular_div'] = div
                    conf = min(1.0, 0.80 + (0.02 - sqerr) * 5)
                    notes = ['4 定位点构成正方形，质心≈码盘圆心 → 抖音主页码',
                             f'正方形误差 {sqerr:.4f}，质心与盘心偏差 {cenerr:.1f}px']
                    if div:
                        notes.append(f"角向主分度≈{div['div']} 格/圈")
                    notes.append('不做 payload 解码：厂商私有语义（实测等同于「打开谁的主页」）')
                    return StylizedInfo('douyin_profile', round(conf, 3), geo, notes)
    except Exception:
        pass

    # ---------------- 路线 B：微信式 3+1 牛眼 ----------------
    try:
        eyes = _find_eyes_in_center(gray)
        best = None
        for combo in itertools.combinations(eyes[:5], 3):
            pts = [(e['x'], e['y']) for e in combo]
            cen, sc = _fit_tri_center(pts)
            if sc > 0.10:
                continue
            R_mean = float(np.mean([e['d'] for e in combo])) / 4.0
            d_eye = float(np.mean([math.hypot(p[0] - cen[0], p[1] - cen[1]) for p in pts]))
            # 圆心须落在图像中部（真码的圆心就是码心）
            if not (0.18 * W < cen[0] < 0.82 * W and 0.18 * H < cen[1] < 0.82 * H):
                continue
            score = (1 - sc) * 0.7 + min(1.0, float(np.mean([e['flips'] for e in combo])) / 7.0) * 0.3
            if best is None or score > best[0]:
                best = (score, combo, cen, sc, R_mean, d_eye)
        if best:
            score, combo, cen, sc, R_mean, d_eye = best
            mod = R_mean / 3.5
            r_code = d_eye + 2.0 * R_mean
            div = _angular_div(gray, tuple(cen), max(R_mean * 2.2, 0.3 * r_code), r_code * 0.97)

            # ---- 权威判别：角向格律（硬门槛，必须测出且合规）----
            # 微信小程序码官方规格只有 36 / 54 / 72 线三档，数据区是**规则极坐标格**，
            # 因此角向自相关应能测出 30~80 格/圈且周期足够强。
            #
            # 实测分界（这是本模块唯一能区分"微信族"与"普通二维码"的依据）：
            #   真微信赞赏码      : 4 种半径带下均为 (36.0, peak 0.71~0.74)，完全稳定
            #   普通二维码(打印)  : (27~28, peak 0.21~0.44)，分度不符且周期弱
            #   充电桩LCD照片     : 4 种半径带下均为 None（整幅照片没有极坐标格律）
            # 普通二维码的三个定位符同样构成等腰直角三角形，纯几何无法区分，必须靠这一条。
            # 注意"测不出"要判否而不是放过——放过会让整幅照片级别的图蒙混过关。
            if div is None:
                return StylizedInfo('unknown', 0.0, {'image': [W, H]},
                                    ['3 牛眼呈等腰直角三角形，但测不出角向格律'
                                     '（微信族应有 36/54/72 线档的规则极坐标格律）'
                                     '→ 更可能是普通二维码或整幅照片'])
            if not (30.0 <= div['div'] <= 80.0 and div['peak'] >= 0.60):
                return StylizedInfo('unknown', 0.0, {'image': [W, H]},
                                    [f"3 牛眼呈等腰直角三角形，但角向格律不符合微信规格"
                                     f"（实测 {div['div']} 格/圈、周期强度 {div['peak']:.3f}；"
                                     f"要求 30~80 格/圈且强度 ≥0.60）→ 更可能是普通二维码"])
            div_bonus = 0.20
            x0, x1 = max(0, int(cen[0] - r_code)), min(W, int(cen[0] + r_code))
            y0, y1 = max(0, int(cen[1] - r_code)), min(H, int(cen[1] + r_code))
            patch = rgb[y0:y1, x0:x1]
            colorful = 0.0
            if patch.size:
                hh = cv2.cvtColor(patch, cv2.COLOR_RGB2HSV)
                colorful = float((hh[:, :, 1] > 60).mean())
            kind = 'wechat_reward' if colorful > 0.10 else 'wechat_miniprogram'
            geo = {
                'center': [round(float(cen[0]), 1), round(float(cen[1]), 1)],
                'n_eyes': 3,
                'eyes': [{'x': round(e['x'], 1), 'y': round(e['y'], 1),
                          'd': round(e['d'], 1), 'flips': e['flips']} for e in combo],
                'iso_right_err': round(sc, 4),
                'module_px': round(mod, 2),
                'code_radius_px': round(r_code, 1),
                'est_lines': round(2 * r_code / mod, 0),
                'color_ratio': round(colorful, 3),
                'image': [W, H],
            }
            if div:
                geo['angular_div'] = div
            notes = ['3 牛眼构成等腰直角三角形 → 微信族异形码',
                     f'等腰直角误差 {sc:.4f}', f'码区彩色占比 {colorful:.2f}']
            if div:
                notes.append(f"角向主分度≈{div['div']} 格/圈")
            notes.append('不做 payload 解码：厂商私有语义（实测等同于「打开谁的主页」）')
            return StylizedInfo(kind, round(max(0.0, min(1.0, 0.55 + 0.45 * score + div_bonus)), 3),
                                geo, notes)
    except Exception:
        pass

    return StylizedInfo('unknown', 0.0, {'image': [W, H]},
                        ['未检出 3/4 定位点的规则几何结构'])
