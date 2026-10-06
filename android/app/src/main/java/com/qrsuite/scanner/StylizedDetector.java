package com.qrsuite.scanner;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * 样式化私有码（太阳码/抖音码）结构判定 —— 从 qrsuite/stylized.py 逐字移植。
 *
 * <p>设计约束：
 * <ul>
 *   <li><b>零 Android 依赖</b>：只用 java.* ，因此可在桌面 JVM 上离线回归测试，
 *       与 Python 参考实现逐张比对（见 tools/StylizedParityTest.java）。</li>
 *   <li><b>逐字移植，不重写思路</b>：上一轮实测表明"照思路重写"会退化，
 *       本文件刻意保留与 Python 相同的顺序、阈值与判据。</li>
 *   <li>只做**识别与几何测量**，不做 payload 解码 —— 这类码协议私有，无公开实现。</li>
 * </ul>
 *
 * <p>输入统一为 RGB 像素数组（每像素 0xRRGGBB），避免依赖 Android Bitmap。
 */
public final class StylizedDetector {

    // ---------------------------------------------------------------- 常量

    public static final String KIND_DOUYIN = "douyin_profile";
    public static final String KIND_WECHAT_MINIPROGRAM = "wechat_miniprogram";
    public static final String KIND_WECHAT_REWARD = "wechat_reward";
    public static final String KIND_UNKNOWN = "unknown";

    // ---------------------------------------------------------------- 结果

    public static final class Info {
        public final String kind;
        public final double confidence;
        public final String note;
        public final int nEyes;
        public final double[] center;      // {x, y}，可能为 null
        public final double angularDiv;    // 0 表示未测出
        public final double estLines;      // 0 表示未测出
        public final double squareErr;     // 抖音专用
        public final double isoRightErr;   // 微信专用

        Info(String kind, double confidence, String note, int nEyes, double[] center,
             double angularDiv, double estLines, double squareErr, double isoRightErr) {
            this.kind = kind;
            this.confidence = confidence;
            this.note = note;
            this.nEyes = nEyes;
            this.center = center;
            this.angularDiv = angularDiv;
            this.estLines = estLines;
            this.squareErr = squareErr;
            this.isoRightErr = isoRightErr;
        }

        public boolean isActionable() {
            return !KIND_UNKNOWN.equals(kind) && confidence >= 0.5;
        }

        @Override public String toString() {
            return String.format(Locale.ROOT,
                    "%s conf=%.3f nEyes=%d center=%s div=%.1f lines=%.0f sq=%.4f iso=%.4f",
                    kind, confidence, nEyes,
                    center == null ? "-" : String.format(Locale.ROOT, "(%.1f,%.1f)", center[0], center[1]),
                    angularDiv, estLines, squareErr, isoRightErr);
        }
    }

    private static Info unknown(int w, int h, String note) {
        return new Info(KIND_UNKNOWN, 0.0, note, 0, null, 0, 0, 0, 0);
    }

    // ---------------------------------------------------------------- 图像

    private final int w, h;
    private final int[] rgb;      // 0xRRGGBB
    private final int[] gray;     // 0..255, 0.299R+0.587G+0.114B

    public StylizedDetector(int[] rgb, int w, int h) {
        if (rgb.length != w * h) throw new IllegalArgumentException("像素数与尺寸不符");
        this.rgb = rgb;
        this.w = w;
        this.h = h;
        this.gray = new int[w * h];
        for (int i = 0; i < rgb.length; i++) {
            int p = rgb[i];
            int r = (p >> 16) & 0xFF, g = (p >> 8) & 0xFF, b = p & 0xFF;
            // 与 cv2.COLOR_RGB2GRAY 一致（BT.601 整数系数）
            gray[i] = (int) ((r * 299 + g * 587 + b * 114) / 1000.0 + 0.5);
        }
    }

    /** cv2.cvtColor(RGB2HSV)：H 0..179, S 0..255, V 0..255（与 OpenCV 相同约定）。 */
    private static int[] rgb2hsv(int p) {
        int r = (p >> 16) & 0xFF, g = (p >> 8) & 0xFF, b = p & 0xFF;
        int max = Math.max(r, Math.max(g, b));
        int min = Math.min(r, Math.min(g, b));
        int v = max;
        int s = (max == 0) ? 0 : (int) ((max - min) * 255.0 / max + 0.5);
        int hue;
        if (max == min) {
            hue = 0;
        } else {
            double d = max - min;
            double hh;
            if (max == r) hh = ((g - b) / d) % 6.0;
            else if (max == g) hh = ((b - r) / d) + 2.0;
            else hh = ((r - g) / d) + 4.0;
            hh *= 60.0;
            if (hh < 0) hh += 360.0;
            hue = (int) (hh / 2.0 + 0.5);   // OpenCV: H 0..179
        }
        return new int[]{hue, s, v};
    }

    /** 移植自 _lab_dark_white：HSV 低饱和+高明度=白盘，高饱和偏暗=码点。 */
    private boolean[][] labDarkWhite() {
        boolean[] white = new boolean[w * h];
        boolean[] dark = new boolean[w * h];
        for (int i = 0; i < rgb.length; i++) {
            int[] hsv = rgb2hsv(rgb[i]);
            int s = hsv[1], v = hsv[2];
            white[i] = (s < 45 && v > 205);
            dark[i] = (s > 60 && v < 240);
        }
        return new boolean[][]{dark, white};
    }

    // ---------------------------------------------------------------- 连通域

    /** 一次连通域分析的结果（等价于 cv2.connectedComponentsWithStats 的 stats/cents）。 */
    private static final class CC {
        int n;
        int[] left, top, cw, ch, area;
        double[] cx, cy;
    }

    /**
     * 8 连通域（并查集实现，替代 cv2.connectedComponentsWithStats）。
     * cv2 的质心是**像素索引的均值**，这里保持一致。
     */
    private CC connectedComponents(boolean[] mask, int w, int h) {
        int n = w * h;
        int[] parent = new int[n];
        Arrays.fill(parent, -1);                 // -1 = 背景
        // 第一遍：并查集
        int[] stack = new int[n];
        int[] label = new int[n];
        Arrays.fill(label, -1);
        for (int idx = 0; idx < n; idx++) {
            if (!mask[idx]) continue;
            // 检查左、上、左上、右上四个已访问邻居
            int x = idx % w, y = idx / w;
            int best = -1;
            int[] nx = {x - 1, x, x - 1, x + 1};
            int[] ny = {y, y - 1, y - 1, y - 1};
            for (int k = 0; k < 4; k++) {
                int ax = nx[k], ay = ny[k];
                if (ax < 0 || ax >= w || ay < 0 || ay >= h) continue;
                int nIdx = ay * w + ax;
                int lb = label[nIdx];
                if (lb < 0) continue;
                if (best < 0) best = find(parent, lb);
                else best = union(parent, best, find(parent, lb));
            }
            if (best < 0) {
                best = idx;
                parent[best] = best;
            }
            label[idx] = best;
        }
        // 第二遍：压缩 + 统计
        int[] remap = new int[n];
        Arrays.fill(remap, -1);
        CC cc = new CC();
        int count = 0;
        for (int idx = 0; idx < n; idx++) {
            if (!mask[idx]) continue;
            int root = find(parent, label[idx]);
            if (remap[root] < 0) remap[root] = count++;
            label[idx] = remap[root];
        }
        cc.n = count + 1;                        // +1：背景为 0，与 cv2 一致
        cc.left = new int[cc.n];
        cc.top = new int[cc.n];
        cc.cw = new int[cc.n];
        cc.ch = new int[cc.n];
        cc.area = new int[cc.n];
        cc.cx = new double[cc.n];
        cc.cy = new double[cc.n];
        int[] minX = new int[cc.n], minY = new int[cc.n], maxX = new int[cc.n], maxY = new int[cc.n];
        Arrays.fill(minX, Integer.MAX_VALUE);
        Arrays.fill(minY, Integer.MAX_VALUE);
        Arrays.fill(maxX, -1);
        Arrays.fill(maxY, -1);
        double[] sx = new double[cc.n], sy = new double[cc.n];
        for (int idx = 0; idx < n; idx++) {
            int lb = label[idx];
            if (lb < 0) continue;
            int x = idx % w, y = idx / w;
            cc.area[lb]++;
            sx[lb] += x;
            sy[lb] += y;
            if (x < minX[lb]) minX[lb] = x;
            if (y < minY[lb]) minY[lb] = y;
            if (x > maxX[lb]) maxX[lb] = x;
            if (y > maxY[lb]) maxY[lb] = y;
        }
        for (int lb = 0; lb < cc.n; lb++) {
            if (cc.area[lb] == 0) continue;
            cc.left[lb] = minX[lb];
            cc.top[lb] = minY[lb];
            cc.cw[lb] = maxX[lb] - minX[lb] + 1;
            cc.ch[lb] = maxY[lb] - minY[lb] + 1;
            cc.cx[lb] = sx[lb] / cc.area[lb];
            cc.cy[lb] = sy[lb] / cc.area[lb];
        }
        return cc;
    }

    private static int find(int[] parent, int x) {
        while (parent[x] != x) {
            parent[x] = parent[parent[x]];
            x = parent[x];
        }
        return x;
    }

    private static int union(int[] parent, int a, int b) {
        if (a == b) return a;
        parent[b] = a;
        return a;
    }

    // ---------------------------------------------------------------- 牛眼

    /** 移植自 _bullseye_verify：中心黑 + 环黑 + 环外白。含性能预筛（8 点中心采样）。 */
    private static final class Eye {
        double x, y, r, score, centerFrac;
    }

    private Eye bullseyeVerify(boolean[] dark, double ccx, double ccy, double R) {
        int py0 = (int) (ccy - R), py1 = (int) (ccy + R + 1);
        int px0 = (int) (ccx - R), px1 = (int) (ccx + R + 1);
        if (py0 < 0 || px0 < 0 || py1 > h || px1 > w || py1 <= py0 || px1 <= px0) return null;
        int ph = py1 - py0, pw = px1 - px0;

        double ccxi = (pw - 1) / 2.0, ccyi = (ph - 1) / 2.0;

        // 预筛：中心 0.15R 圆内 8 点采样，要求 ≥6 暗
        double rIn = Math.max(1.0, R * 0.15);
        int hits = 0;
        for (int k = 0; k < 8; k++) {
            double a = k * Math.PI / 4.0;
            int sx = (int) Math.round(ccxi + rIn * Math.cos(a));
            int sy = (int) Math.round(ccyi + rIn * Math.sin(a));
            if (sy >= 0 && sy < ph && sx >= 0 && sx < pw) {
                if (dark[(py0 + sy) * w + (px0 + sx)]) hits++;
            }
        }
        if (hits < 6) return null;

        double cThr = R * 0.22, rIn0 = R * 0.35, rIn1 = R * 0.95, rOut0 = R * 1.02, rOut1 = R * 1.6;
        int nC = 0, nR = 0, nO = 0, dC = 0, dR = 0, dO = 0;
        for (int yy = 0; yy < ph; yy++) {
            for (int xx = 0; xx < pw; xx++) {
                double dx = xx - ccxi, dy = yy - ccyi;
                double pr = Math.sqrt(dx * dx + dy * dy);
                boolean d = dark[(py0 + yy) * w + (px0 + xx)];
                if (pr < cThr) { nC++; if (d) dC++; }
                else if (pr > rIn0 && pr < rIn1) { nR++; if (d) dR++; }
                else if (pr > rOut0 && pr < rOut1) { nO++; if (d) dO++; }
            }
        }
        if (nC == 0 || nR == 0 || nO == 0) return null;
        double centerFrac = (double) dC / nC;
        double aroundFrac = (double) dO / nO;
        if (centerFrac < 0.6) return null;
        double score = centerFrac - aroundFrac;
        if (score <= 0.25) return null;

        Eye e = new Eye();
        e.x = ccx; e.y = ccy; e.r = R;
        e.score = Math.round(score * 1000.0) / 1000.0;
        e.centerFrac = centerFrac;
        return e;
    }

    /** 移植自 _find_disc：最大白连通域 = 码盘。 */
    private static final class Disc {
        int bx, by, bw, bh, area;
        double cx, cy, fill;
        double radius() { return Math.max(bw, bh) / 2.0; }
    }

    private Disc findDisc(boolean[] white) {
        CC cc = connectedComponents(white, w, h);
        if (cc.n <= 1) return null;
        int best = -1, bestArea = -1;
        for (int i = 1; i < cc.n; i++) {
            if (cc.area[i] > bestArea) { bestArea = cc.area[i]; best = i; }
        }
        if (best < 0) return null;
        Disc d = new Disc();
        d.bx = cc.left[best]; d.by = cc.top[best];
        d.bw = cc.cw[best]; d.bh = cc.ch[best]; d.area = cc.area[best];
        d.cx = cc.cx[best]; d.cy = cc.cy[best];
        d.fill = Math.round(d.area / (double) Math.max(d.bw * d.bh, 1) * 1000.0) / 1000.0;
        return d;
    }

    /** 移植自 _find_bullseyes（含稠密搜索；该搜索不可跳过，见 Python 侧注释）。 */
    private List<Eye> findBullseyes(boolean[] dark, Disc disc) {
        double cx = disc.cx, cy = disc.cy;
        double rDisc = disc.radius();
        boolean[] mask = new boolean[w * h];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int i = y * w + x;
                if (!dark[i]) continue;
                double dx = x - cx, dy = y - cy;
                if (dx * dx + dy * dy <= (rDisc * 1.02) * (rDisc * 1.02)) mask[i] = true;
            }
        }
        CC cc = connectedComponents(mask, w, h);
        List<Eye> cand = new ArrayList<>();
        for (int i = 1; i < cc.n; i++) {
            int w0 = cc.cw[i], h0 = cc.ch[i], area = cc.area[i];
            if (w0 < 12 || h0 < 12 || area < 50) continue;
            double wh = (double) w0 / h0;
            if (!(wh > 0.6 && wh < 1.7)) continue;
            double fill = area / (double) (w0 * h0);
            if (!(fill >= 0.10 && fill <= 0.70)) continue;
            double ccx = cc.cx[i], ccy = cc.cy[i];
            double rC = Math.hypot(ccx - cx, ccy - cy);
            if (!(rC > rDisc * 0.5 && rC < rDisc)) continue;
            double R = (w0 + h0) / 4.0;
            Eye hit = bullseyeVerify(dark, ccx, ccy, R);
            if (hit != null) cand.add(hit);
        }

        // 稠密搜索（不可跳过）
        double rrStart = rDisc * 0.55, rrEnd = rDisc * 0.98;
        double rrStep = Math.max(2.0, rDisc * 0.02);
        double[] radii = {rDisc * 0.085, rDisc * 0.105, rDisc * 0.13};
        for (double R : radii) {
            if (R < 5) continue;
            for (double r = rrStart; r < rrEnd; r += rrStep) {
                for (int k = 0; k < 64; k++) {
                    double a = 2 * Math.PI * k / 64.0;
                    double x = cx + r * Math.cos(a);
                    double y = cy + r * Math.sin(a);
                    Eye hit = bullseyeVerify(dark, x, y, R);
                    if (hit != null && hit.score > 0.55) cand.add(hit);
                }
            }
        }

        cand.sort((p, q) -> Double.compare(q.score, p.score));
        List<Eye> keep = new ArrayList<>();
        for (Eye c : cand) {
            boolean ok = true;
            for (Eye k : keep) {
                double dx = c.x - k.x, dy = c.y - k.y;
                double lim = Math.max(c.r, k.r) * 1.5;
                if (dx * dx + dy * dy <= lim * lim) { ok = false; break; }
            }
            if (ok) keep.add(c);
            if (keep.size() >= 12) break;
        }
        return keep;
    }

    /** 移植自 _pick_four：同一环带 + 半径接近 + 正方形 + 质心≈盘心。 */
    private static final class Four {
        List<Eye> combo;
        double[] cen;
        double side, diag, sqErr, rMean, cenErr;
    }

    private Four pickFour(List<Eye> cand, Disc disc) {
        for (Eye c : cand) c.r = c.r;   // r 已保存
        List<Eye> pool = new ArrayList<>();
        for (Eye c : cand) if (c.centerFrac > 0.65) pool.add(c);
        List<Eye> pool12 = pool.size() > 12 ? pool.subList(0, 12) : pool;
        Four best = null;
        double bestScore = Double.MAX_VALUE;
        int n = pool12.size();
        for (int a = 0; a < n; a++)
            for (int b = a + 1; b < n; b++)
                for (int c = b + 1; c < n; c++)
                    for (int d = c + 1; d < n; d++) {
                        Eye[] cb = {pool12.get(a), pool12.get(b), pool12.get(c), pool12.get(d)};
                        double[] rs = new double[4];
                        for (int i = 0; i < 4; i++) {
                            rs[i] = Math.hypot(cb[i].x - disc.cx, cb[i].y - disc.cy);
                        }
                        double rMin = min(rs), rMax = max(rs), rMean = (rMin + rMax) / 2;
                        // 与 Python 一致：rs.max()-rs.min() > rs.mean()*0.12 则跳过
                        double rsMean = 0;
                        for (double v : rs) rsMean += v;
                        rsMean /= 4;
                        if (rMax - rMin > rsMean * 0.12) continue;

                        double cenX = 0, cenY = 0;
                        for (Eye e : cb) { cenX += e.x; cenY += e.y; }
                        cenX /= 4; cenY /= 4;

                        double[] dist = new double[6];
                        int t = 0;
                        for (int i = 0; i < 4; i++)
                            for (int j = i + 1; j < 4; j++)
                                dist[t++] = Math.hypot(cb[i].x - cb[j].x, cb[i].y - cb[j].y);
                        Arrays.sort(dist);
                        double side = (dist[0] + dist[1] + dist[2] + dist[3]) / 4.0;
                        double diag = (dist[4] + dist[5]) / 2.0;
                        if (side <= 0) continue;
                        double sq = Math.abs(diag / side - Math.sqrt(2));
                        double cenErr = Math.hypot(cenX - disc.cx, cenY - disc.cy);
                        double score = cenErr / 5.0 + sq * 300.0 + (rMax - rMin) / 5.0;
                        if (score < bestScore) {
                            bestScore = score;
                            best = new Four();
                            best.combo = new ArrayList<>(Arrays.asList(cb));
                            best.cen = new double[]{cenX, cenY};
                            best.side = side; best.diag = diag; best.sqErr = sq;
                            best.rMean = rsMean; best.cenErr = cenErr;
                        }
                    }
        return best;
    }

    private static double min(double[] a) {
        double m = a[0];
        for (double v : a) if (v < m) m = v;
        return m;
    }

    private static double max(double[] a) {
        double m = a[0];
        for (double v : a) if (v > m) m = v;
        return m;
    }

    // ---------------------------------------------------------------- 微信路线

    /** 移植自 _find_eyes_in_center：中心区域找同心环牛眼。返回 {x, y, d, flips}。 */
    private List<double[]> findEyesInCenter() {
        int cx0 = w / 2, cy0 = h / 2;
        int r = (int) (Math.min(h, w) * 0.36);
        int y0 = Math.max(0, cy0 - r), y1 = Math.min(h, cy0 + r);
        int x0 = Math.max(0, cx0 - r), x1 = Math.min(w, cx0 + r);
        int sw = x1 - x0, sh = y1 - y0;
        boolean[] binary = new boolean[sw * sh];
        for (int yy = 0; yy < sh; yy++)
            for (int xx = 0; xx < sw; xx++)
                binary[yy * sw + xx] = gray[(y0 + yy) * w + (x0 + xx)] < 128;

        CC cc = connectedComponents(binary, sw, sh);
        List<double[]> eyes = new ArrayList<>();
        for (int i = 1; i < cc.n; i++) {
            int bw = cc.cw[i], bh = cc.ch[i], area = cc.area[i];
            if (bw < 8 || bh < 8 || area < 40) continue;
            double ratio = (double) bw / bh;
            if (!(ratio > 0.75 && ratio < 1.33)) continue;
            if (area / (double) (bw * bh) > 0.5) continue;
            double ccx = cc.cx[i], ccy = cc.cy[i];
            double rmax = Math.min(bw, bh) / 2.0;
            int steps = Math.max(4, (int) (rmax * 2));
            int prev = -1, flips = 0, count = 0;
            for (int s = 0; s < steps; s++) {
                double t = -rmax + (2 * rmax) * s / (steps - 1.0);
                int yy = (int) Math.round(ccy + t), xx = (int) Math.round(ccx);
                if (yy < 0 || yy >= sh || xx < 0 || xx >= sw) continue;
                int v = binary[yy * sw + xx] ? 1 : 0;
                if (prev >= 0 && v != prev) flips++;
                prev = v;
                count++;
            }
            if (count > 2 && flips >= 3) {
                eyes.add(new double[]{ccx + x0, ccy + y0, (bw + bh) / 2.0, flips});
            }
        }
        eyes.sort((p, q) -> Double.compare(q[3], p[3]));
        return eyes.size() > 8 ? eyes.subList(0, 8) : eyes;
    }

    /** 移植自 _fit_tri_center：3 牛眼 = 矩形三角 → 圆心 = 另两角中点。返回 {cx, cy, err}。 */
    private static double[] fitTriCenter(List<double[]> pts) {
        int[][] perms = {{0, 1, 2}, {0, 2, 1}, {1, 0, 2}, {1, 2, 0}, {2, 0, 1}, {2, 1, 0}};
        double bestSc = Double.MAX_VALUE;
        double bx = 0, by = 0;
        for (int[] o : perms) {
            double[] v = pts.get(o[0]), a = pts.get(o[1]), b = pts.get(o[2]);
            double da = Math.hypot(v[0] - a[0], v[1] - a[1]);
            double db = Math.hypot(v[0] - b[0], v[1] - b[1]);
            double sc = Math.abs(da - db) / Math.max(Math.max(da, db), 1e-6);
            if (sc < bestSc) {
                bestSc = sc;
                bx = (a[0] + b[0]) / 2.0;
                by = (a[1] + b[1]) / 2.0;
            }
        }
        return new double[]{bx, by, bestSc};
    }

    /**
     * 移植自 _angular_div：极坐标展开后沿角度自相关 → 主分度数。
     * 这是区分"微信族"与"普通二维码"的**唯一权威判据**（微信官方仅 36/54/72 线档）。
     */
    private double[] angularDiv(double cx, double cy, double r0, double r1) {
        if (r1 <= r0 * 1.25) return null;
        final int nAng = 1440, nRad = 200;
        // 双线性采样（等价 cv2.remap INTER_LINEAR + BORDER_CONSTANT 255）
        double[] prof = new double[nAng];
        int bandStart = (int) (0.35 * nRad), bandEnd = (int) (0.9 * nRad);
        int[] darkCount = new int[nAng];
        int rows = 0;
        for (int ri = bandStart; ri < bandEnd; ri++) {
            double rad = r0 + (r1 - r0) * ri / (nRad - 1.0);
            rows++;
            for (int ai = 0; ai < nAng; ai++) {
                double ang = 2 * Math.PI * ai / nAng;
                double sx = cx + rad * Math.cos(ang);
                double sy = cy + rad * Math.sin(ang);
                int v = bilinearGray(sx, sy);
                if (v < 128) darkCount[ai]++;
            }
        }
        if (rows == 0) return null;
        double mean = 0;
        for (int i = 0; i < nAng; i++) {
            prof[i] = (double) darkCount[i] / rows;
            mean += prof[i];
        }
        mean /= nAng;
        for (int i = 0; i < nAng; i++) prof[i] -= mean;

        // 自相关（lag 0..nAng-1）
        double[] ac = new double[nAng];
        for (int lag = 0; lag < nAng; lag++) {
            double s = 0;
            for (int i = 0; i + lag < nAng; i++) s += prof[i] * prof[i + lag];
            ac[lag] = s;
        }
        double ac0 = ac[0] + 1e-9;
        for (int i = 0; i < nAng; i++) ac[i] /= ac0;

        int bestLag = -1;
        double bestVal = -1;
        for (int lag = 3; lag < 160 && lag + 1 < nAng; lag++) {
            if (ac[lag] >= ac[lag - 1] && ac[lag] >= ac[lag + 1] && ac[lag] > 0.15) {
                if (ac[lag] > bestVal) { bestVal = ac[lag]; bestLag = lag; }
            }
        }
        if (bestLag < 0) return null;
        double angleDeg = bestLag * 360.0 / nAng;
        double div = Math.round(360.0 / angleDeg * 10.0) / 10.0;
        double peak = Math.round(bestVal * 1000.0) / 1000.0;
        return new double[]{div, angleDeg, peak};
    }

    /** 双线性灰度采样；越界返回 255（等价 BORDER_CONSTANT + borderValue=255）。 */
    private int bilinearGray(double x, double y) {
        if (x < 0 || y < 0 || x > w - 1 || y > h - 1) {
            // 边缘一半在内时按 OpenCV 的边界处理近似：直接取最近有效像素；完全在外则 255
            if (x < -1 || y < -1 || x > w || y > h) return 255;
        }
        int x0 = (int) Math.floor(x), y0 = (int) Math.floor(y);
        int x1 = x0 + 1, y1 = y0 + 1;
        double fx = x - x0, fy = y - y0;
        int v00 = grayAt(x0, y0), v10 = grayAt(x1, y0), v01 = grayAt(x0, y1), v11 = grayAt(x1, y1);
        double top = v00 * (1 - fx) + v10 * fx;
        double bot = v01 * (1 - fx) + v11 * fx;
        return (int) (top * (1 - fy) + bot * fy + 0.5);
    }

    private int grayAt(int x, int y) {
        if (x < 0 || y < 0 || x >= w || y >= h) return 255;
        return gray[y * w + x];
    }

    // ---------------------------------------------------------------- 主入口

    /** 移植自 classify()。调用方应已确认标准解码器全部失败。 */
    public Info classify() {
        // ---------------- 路线 A：抖音式 4 定位点 ----------------
        try {
            boolean[][] dw = labDarkWhite();
            boolean[] dark = dw[0], white = dw[1];
            Disc disc = findDisc(white);
            if (disc != null && disc.fill > 0.45) {
                List<Eye> eyes = findBullseyes(dark, disc);
                if (eyes.size() >= 4) {
                    Four four = pickFour(eyes, disc);
                    if (four != null) {
                        double discR = disc.radius();
                        if (four.sqErr <= 0.02 && four.cenErr <= 0.08 * Math.max(discR, 1)) {
                            double Rm = 0;
                            for (Eye e : four.combo) Rm += e.r;
                            Rm /= four.combo.size();
                            double mod = Rm / 3.5;
                            double rCode = discR;
                            double[] div = angularDiv(four.cen[0], four.cen[1],
                                    Math.max(Rm * 2.0, 0.3 * rCode), rCode * 0.96);
                            double conf = Math.min(1.0, 0.80 + (0.02 - four.sqErr) * 5);
                            String note = "4 定位点构成正方形，质心≈码盘圆心 → 抖音主页码";
                            return new Info(KIND_DOUYIN, Math.round(conf * 1000.0) / 1000.0, note,
                                    4, four.cen,
                                    div == null ? 0 : div[0],
                                    Math.round(2 * rCode / mod), four.sqErr, 0);
                        }
                    }
                }
            }
        } catch (RuntimeException ignored) {
            // 与 Python 一致：路线异常不阻断另一条路线
        }

        // ---------------- 路线 B：微信式 3+1 牛眼 ----------------
        try {
            List<double[]> eyes = findEyesInCenter();
            double bestScore = -1;
            double[] bestCen = null;
            double bestSc = 1, bestRMean = 0, bestDEye = 0, bestFlips = 0;
            int ne = Math.min(eyes.size(), 5);
            for (int a = 0; a < ne; a++)
                for (int b = a + 1; b < ne; b++)
                    for (int c = b + 1; c < ne; c++) {
                        List<double[]> combo = Arrays.asList(eyes.get(a), eyes.get(b), eyes.get(c));
                        double[] fit = fitTriCenter(combo);
                        double sc = fit[2];
                        if (sc > 0.10) continue;
                        double rMean = 0;
                        for (double[] e : combo) rMean += e[2];
                        rMean = rMean / 3.0 / 4.0;
                        double dEye = 0;
                        for (double[] e : combo) dEye += Math.hypot(e[0] - fit[0], e[1] - fit[1]);
                        dEye /= 3.0;
                        if (!(0.18 * w < fit[0] && fit[0] < 0.82 * w
                                && 0.18 * h < fit[1] && fit[1] < 0.82 * h)) continue;
                        double flipsMean = 0;
                        for (double[] e : combo) flipsMean += e[3];
                        flipsMean /= 3.0;
                        double score = (1 - sc) * 0.7 + Math.min(1.0, flipsMean / 7.0) * 0.3;
                        if (score > bestScore) {
                            bestScore = score;
                            bestCen = new double[]{fit[0], fit[1]};
                            bestSc = sc; bestRMean = rMean; bestDEye = dEye; bestFlips = flipsMean;
                        }
                    }
            if (bestCen != null) {
                double rCode = bestDEye + 2.0 * bestRMean;
                double[] div = angularDiv(bestCen[0], bestCen[1],
                        Math.max(bestRMean * 2.2, 0.3 * rCode), rCode * 0.97);

                // ---- 权威判别：角向格律（硬门槛，必须测出且合规）----
                if (div == null) {
                    return unknown(w, h, "3 牛眼呈等腰直角三角形，但测不出角向格律 → 更可能是普通二维码或整幅照片");
                }
                if (!(div[0] >= 30.0 && div[0] <= 80.0 && div[2] >= 0.60)) {
                    return unknown(w, h, String.format(Locale.ROOT,
                            "3 牛眼呈等腰直角三角形，但角向格律不符合微信规格（实测 %.1f 格/圈、周期强度 %.3f）→ 更可能是普通二维码",
                            div[0], div[2]));
                }
                // 彩色占比决定赞赏码 / 小程序码
                int x0 = (int) Math.max(0, bestCen[0] - rCode), x1 = (int) Math.min(w, bestCen[0] + rCode);
                int y0 = (int) Math.max(0, bestCen[1] - rCode), y1 = (int) Math.min(h, bestCen[1] + rCode);
                long total = 0, colorful = 0;
                for (int y = y0; y < y1; y++)
                    for (int x = x0; x < x1; x++) {
                        int[] hsv = rgb2hsv(rgb[y * w + x]);
                        total++;
                        if (hsv[1] > 60) colorful++;
                    }
                double ratio = total == 0 ? 0 : (double) colorful / total;
                String kind = ratio > 0.10 ? KIND_WECHAT_REWARD : KIND_WECHAT_MINIPROGRAM;
                double conf = Math.max(0.0, Math.min(1.0, 0.55 + 0.45 * bestScore + 0.20));
                String note = String.format(Locale.ROOT,
                        "3 牛眼构成等腰直角三角形 → 微信族；角向分度 %.1f 格/圈、彩色占比 %.2f",
                        div[0], ratio);
                return new Info(kind, Math.round(conf * 1000.0) / 1000.0, note,
                        3, bestCen, div[0], Math.round(2 * rCode / (bestRMean / 3.5)), 0, bestSc);
            }
        } catch (RuntimeException ignored) {
        }

        return unknown(w, h, "未检出 3/4 定位点的规则几何结构");
    }
}
