/*!
 * QRSuite v2 · 浏览器端解码级联（jsQR + ZXing-C++ 的 JS 版 ZXing-js）
 * 设计：级联 + 早退（命中即停）、变体按"命中率高/代价低"排序、纯像素运算无 DOM 依赖。
 * 可在 Web Worker 中运行，也可在 Node 中直接 require 做自动化测试。
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./vendor/jsQR.js'), require('./vendor/zxing.min.js'));
  } else {
    root.QRCascade = factory(root.jsQR, root.ZXing);
  }
})(typeof self !== 'undefined' ? self : this, function (jsQR, ZXing) {

  const MODES = { fast: { maxStages: 2 }, balanced: { maxStages: 7 }, deep: { maxStages: 99 } };

  /* ---------------- 像素工具（全部就地/线性，避免多余拷贝） ---------------- */
  function toGray(rgba, w, h) {
    const g = new Uint8ClampedArray(w * h);
    for (let i = 0, j = 0; i < g.length; i++, j += 4) g[i] = (rgba[j] * 0.299 + rgba[j + 1] * 0.587 + rgba[j + 2] * 0.114) | 0;
    return g;
  }
  function grayToRGBA(g, w, h) {
    const o = new Uint8ClampedArray(w * h * 4);
    for (let i = 0, j = 0; i < g.length; i++, j += 4) { o[j] = o[j + 1] = o[j + 2] = g[i]; o[j + 3] = 255; }
    return o;
  }
  function otsu(g) {
    const hist = new Uint32Array(256);
    for (let i = 0; i < g.length; i++) hist[g[i]]++;
    const total = g.length; let sum = 0;
    for (let i = 0; i < 256; i++) sum += i * hist[i];
    let sumB = 0, wB = 0, best = 0, thr = 128;
    for (let t = 0; t < 256; t++) {
      wB += hist[t]; if (!wB) continue;
      const wF = total - wB; if (!wF) break;
      sumB += t * hist[t];
      const mB = sumB / wB, mF = (sum - sumB) / wF, between = wB * wF * (mB - mF) * (mB - mF);
      if (between > best) { best = between; thr = t; }
    }
    const o = new Uint8ClampedArray(g.length);
    for (let i = 0; i < g.length; i++) o[i] = g[i] > thr ? 255 : 0;
    return o;
  }
  function invert(g) { const o = new Uint8ClampedArray(g.length); for (let i = 0; i < g.length; i++) o[i] = 255 - g[i]; return o; }
  function resize(g, w, h, f) {                        // 最近邻放大（条码识别足够，且比插值快数倍）
    const nw = w * f, nh = h * f, o = new Uint8ClampedArray(nw * nh);
    for (let y = 0; y < nh; y++) { const sy = (y / f) | 0, so = sy * w, dofs = y * nw;
      for (let x = 0; x < nw; x++) o[dofs + x] = g[so + ((x / f) | 0)]; }
    return { g: o, w: nw, h: nh };
  }
  function rot(g, w, h, deg) {
    if (deg === 90) { const o = new Uint8ClampedArray(w * h), nw = h, nh = w;
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) o[x * nw + (h - 1 - y)] = g[y * w + x];
      return { g: o, w: nw, h: nh }; }
    if (deg === 180) { const o = new Uint8ClampedArray(w * h);
      for (let i = 0; i < g.length; i++) o[i] = g[g.length - 1 - i]; return { g: o, w, h }; }
    const o = new Uint8ClampedArray(w * h), nw = h, nh = w;   // 270
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) o[(w - 1 - x) * nw + y] = g[y * w + x];
    return { g: o, w: nw, h: nh };
  }
  function crop(g, w, h, x0, y0, x1, y1) {
    x0 = Math.max(0, x0 | 0); y0 = Math.max(0, y0 | 0); x1 = Math.min(w, x1 | 0); y1 = Math.min(h, y1 | 0);
    const nw = x1 - x0, nh = y1 - y0, o = new Uint8ClampedArray(nw * nh);
    for (let y = 0; y < nh; y++) o.set(g.subarray((y0 + y) * w + x0, (y0 + y) * w + x1), y * nw);
    return { g: o, w: nw, h: nh };
  }
  /* 单通道灰度 + 对比度评估。
     为什么需要：亮度公式 0.299R+0.587G+0.114B 会把"颜色通道偏斜"的图压成低对比——
     典型是蓝色 LCD/彩色底的照片，蓝色权重只有 0.114，白底与深色码点的灰度差被压到
     149 左右；而取 R（蓝的补色）能得到 177，jsQR 立刻就能解出。
     所以对彩色图补一组"逐通道"变体，按对比度从高到低尝试。 */
  function channelImage(rgba, w, h, k) {
    const g = new Uint8ClampedArray(w * h);
    for (let i = 0, j = k; i < g.length; i++, j += 4) g[i] = rgba[j];
    return g;
  }
  function grayContrast(g) {
    let lo = 255, hi = 0;
    for (let i = 0; i < g.length; i++) { const v = g[i]; if (v < lo) lo = v; if (v > hi) hi = v; }
    return hi - lo;
  }

  /* ---------------- 两个解码引擎 ---------------- */
  function withSilencedLogs(fn) {                 // zxing-js 解码失败会 console.warn 刷屏
    const w = console.warn, e = console.error;
    console.warn = console.error = function () { };
    try { return fn(); } finally { console.warn = w; console.error = e; }
  }
  function readZXing(g, w, h) {
    if (!ZXing) return [];
    return withSilencedLogs(function () {
      try {
        const src = new ZXing.RGBLuminanceSource(g, w, h);      // zxing-js: 每像素 1 字节灰度
        const bmp = new ZXing.BinaryBitmap(new ZXing.HybridBinarizer(src));
        const reader = new ZXing.MultiFormatReader();
        const hints = new Map();
        hints.set(ZXing.DecodeHintType.TRY_HARDER, true);
        hints.set(ZXing.DecodeHintType.ALSO_INVERTED, true);
        reader.setHints(hints);
        const r = reader.decode(bmp);
        if (!r) return [];
        const bf = r.getBarcodeFormat ? r.getBarcodeFormat() : undefined;
        return [{ text: r.getText(), format: (ZXing.BarcodeFormat[bf] || 'Barcode') }];
      } catch (e) { return []; }
    });
  }
  function readJsQR(rgba, w, h) {
    if (!jsQR) return [];
    try {
      const r = jsQR(rgba, w, h, { inversionAttempts: 'attemptBoth' });
      return r && r.data ? [{ text: r.data, format: 'QRCode' }] : [];
    } catch (e) { return []; }
  }

  /* ---------------- 级联策略：有序变体 + 早退 ---------------- */
  function* stages(g, w, h, colorRGBA) {
    yield { name: '原图', g, w, h, rgba: colorRGBA };
    const o = otsu(g);
    yield { name: 'Otsu二值化', g: o, w, h, rgba: grayToRGBA(o, w, h) };
    const small = Math.max(w, h) < 700;
    if (small) { const r = resize(g, w, h, 2); yield { name: '放大2倍', ...r, rgba: grayToRGBA(r.g, r.w, r.h) }; }
    const inv = invert(g);
    yield { name: '反色', g: inv, w, h, rgba: grayToRGBA(inv, w, h) };
    // 逐通道灰度（仅彩色图）：按对比度从高到低排，专治蓝屏/彩底这类通道偏斜
    const chans = [];
    let colorful = false;
    for (let i = 0, j = 0; i < g.length; i++, j += 4) {
      if (colorRGBA[j] !== colorRGBA[j + 1] || colorRGBA[j] !== colorRGBA[j + 2]) { colorful = true; break; }
    }
    if (colorful) {
      for (const [k, nm] of [[0, 'R'], [1, 'G'], [2, 'B']]) chans.push([nm, channelImage(colorRGBA, w, h, k)]);
      chans.sort((a, b) => grayContrast(b[1]) - grayContrast(a[1]));
      for (const [nm, cg] of chans) {                       // 逐通道原图
        yield { name: '通道' + nm, g: cg, w, h, rgba: grayToRGBA(cg, w, h) };
      }
      for (const [nm, cg] of chans) {                       // 逐通道 Otsu
        const o = otsu(cg);
        yield { name: '通道' + nm + '+Otsu', g: o, w, h, rgba: grayToRGBA(o, w, h) };
      }
    }
    for (const deg of [90, 180, 270]) { const r = rot(g, w, h, deg); yield { name: '旋转' + deg, ...r, rgba: grayToRGBA(r.g, r.w, r.h) }; }
    yield { name: '中心裁剪', ...crop(g, w, h, w * 0.15, h * 0.15, w * 0.85, h * 0.85) };
    for (const [nm, box] of [['左上角', [0, 0, w / 2 + w / 8, h / 2 + h / 8]],
                             ['右上角', [w / 2 - w / 8, 0, w, h / 2 + h / 8]],
                             ['左下角', [0, h / 2 - h / 8, w / 2 + w / 8, h]],
                             ['右下角', [w / 2 - w / 8, h / 2 - h / 8, w, h]]]) {
      const r = crop(g, w, h, box[0], box[1], box[2], box[3]);
      yield { name: '裁剪' + nm, ...r, rgba: grayToRGBA(r.g, r.w, r.h) };
    }
    const sharp = new Uint8ClampedArray(g.length);   // 3x3 锐化
    for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      sharp[i] = 5 * g[i] - g[i - 1] - g[i + 1] - g[i - w] - g[i + w];
    }
    yield { name: '锐化', g: sharp, w, h, rgba: grayToRGBA(sharp, w, h) };
  }

  function decode(rgba, w, h, mode, verify) {
    const cfg = MODES[mode] || MODES.balanced;
    const t0 = (typeof performance !== 'undefined' ? performance : Date).now();
    const g0 = toGray(rgba, w, h);
    const hits = new Map();
    let stagesTried = 0, engineRuns = 0, early = false;

    for (const st of stages(g0, w, h, rgba)) {
      if (stagesTried >= cfg.maxStages) break;
      stagesTried++;
      const rgbaSt = st.rgba || grayToRGBA(st.g, st.w, st.h);
      for (const [eng, out] of [['jsqr', readJsQR(rgbaSt, st.w, st.h)], ['zxing', readZXing(st.g, st.w, st.h)]]) {
        engineRuns++;
        for (const hit of out) {
          if (!hit.text) continue;
          const cur = hits.get(hit.text) || { text: hit.text, format: hit.format, engines: new Set(), variants: new Set() };
          cur.engines.add(eng); cur.variants.add(st.name);
          hits.set(hit.text, cur);
        }
      }
      if (hits.size) {
        if (verify) {
          for (const v of hits.values()) if (v.engines.size >= 2) { early = true; break; }
          if (early) break;
        } else { early = true; break; }
      }
    }
    const tEnd = (typeof performance !== 'undefined' ? performance : Date).now();
    return {
      hits: [...hits.values()].map(v => ({ text: v.text, format: v.format, engines: [...v.engines], variants: [...v.variants] })),
      stages: stagesTried, engineRuns, elapsed: (tEnd - t0) / 1000, early
    };
  }

  return { decode, toGray, otsu, MODES };
});
