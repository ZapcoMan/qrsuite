/*! QRSuite v2 · 解码 Worker：把像素处理与解码都放到后台线程，主线程只负责 UI（不卡界面、CPU 更省） */
importScripts('vendor/jsQR.js', 'vendor/zxing.min.js', 'decode.js');

self.onmessage = function (e) {
  const d = e.data;
  const t0 = Date.now();
  try {
    const rgba = new Uint8ClampedArray(d.buf);
    const r = self.QRCascade.decode(rgba, d.w, d.h, d.mode || 'balanced', !!d.verify);
    self.postMessage(Object.assign({ id: d.id, ok: true }, r));
  } catch (err) {
    self.postMessage({ id: d.id, ok: false, error: String(err && err.message || err), elapsed: (Date.now() - t0) / 1000 });
  }
};
