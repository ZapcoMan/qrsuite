/*!
 * QRSuite v2 · 界面多语言（中/英）
 *
 * 设计：
 *   - 语言优先级：localStorage 里的用户选择 > 浏览器语言（zh* → 中文，其余 → 英文）
 *   - HTML 用 data-i18n="key" 标记；JS 里用 t('key', {占位符})
 *   - 切换语言会重刷 data-i18n 文本、<title>、meta description 与 <html lang>
 *   - 无构建步骤，纯静态可用（file:// 亦可）
 */
(function (root) {
  'use strict';

  const STR = {
    zh: {
      'app.title': 'QRSuite · 多引擎二维码识别',
      'app.desc': '纯浏览器端二维码/条码识别：支持 QR / MicroQR / DataMatrix / Aztec / PDF417 / 一维码，图片不上传，可离线使用。',
      'lang.toggle': 'EN',
      'lang.title': '切换为英文界面',
      'hero.lead': '浏览器内本地解码 · 支持 <b>QR / MicroQR / DataMatrix / Aztec / PDF417 / Code128·39·93 / EAN·UPC / ITF / Codabar</b><br>图片<b>不会被上传</b>，全部在本机内存处理，可离线使用。',
      'drop.title': '拖拽图片到这里，或点击选择文件',
      'drop.sub': '支持一次多张 · 支持 <b>Ctrl+V</b> 粘贴截图 · 支持摄像头拍的原图',
      'opt.mode': '模式',
      'mode.fast': '快速（只试 2 阶段，最省 CPU）',
      'mode.balanced': '均衡（默认，命中即停）',
      'mode.deep': '深度（全部变体，最难图）',
      'opt.verify': '交叉验证',
      'opt.verifyTip': '要求 2 个引擎结果一致才判定成功，可降低误读',
      'opt.selftest': '🧪 自检',
      'opt.selftestTip': '在浏览器内生成一张二维码再解码，验证整条链路',
      'opt.backend': '本机增强引擎',
      'opt.backendTip': '调用本机 Python 多引擎（OpenCV / zbar / bardecoder / WeChatQRCode）',
      'hist.title': '识别历史',
      'hist.hint': '（存于本机浏览器，共 {n} 条）',
      'hist.exportJson': '导出 JSON',
      'hist.exportCsv': '导出 CSV',
      'hist.clear': '清空',
      'hist.confirmClear': '清空本机历史记录？',
      'foot.manual': '📖 使用手册',
      'foot.repo': '项目仓库',
      'foot.note': '浏览器解码 jsQR + ZXing-js（本地化，无 CDN 依赖）· 本机 Python 后端可选',

      'env.proto': '协议 <code>{p}</code>',
      'env.workerOk': 'Worker <b class="ok">可用</b>（{n} 个）',
      'env.workerNo': 'Worker <b class="warn">不可用 → 主线程解码</b>',
      'env.engines': '引擎 <code>{e}</code>',
      'env.notLoaded': '未加载',
      'env.fileHint': '<span class="warn">file:// 下建议改用本地服务：<code>python -m qrsuite --serve</code></span>',
      'env.backendOk': '本机增强 <b class="ok">可用</b>',

      'err.noImages': '没有检测到图片文件，请拖入 png / jpg / gif / bmp / webp',
      'msg.received': '已接收 {n} 张图片，开始解码…',
      'err.script': '脚本错误：{msg}',
      'err.noWorker': '浏览器不支持 Web Worker',
      'err.fileWorker': "file:// 下浏览器禁止创建 Worker（origin 'null'）",
      'err.worker': 'Worker 出错：{msg}',
      'err.workerTimeout': 'Worker 超时',
      'err.cascadeMissing': 'decode.js 未加载',
      'err.imgDecode': '图片解码失败（格式不支持？）',
      'err.decode': '解码失败：{msg}',
      'err.decodeShort': '解码失败',
      'msg.decoding': '解码中…',
      'tag.backend': ' · 本机增强',
      'tag.mainThread': ' · 主线程',
      'meta.notDecoded': '❌ 未解码 · {w}×{h} · {stages} 阶段 · {ms}ms{tag}',
      'meta.decoded': '{w}×{h} · 解出 {n} 条 · {ms}ms · {stages} 阶段{early}{tag}',
      'meta.early': ' · 早退',
      'btn.copy': '复制',
      'btn.open': '打开链接',
      'btn.copied': '已复制',
      'hist.copyTitle': '点击复制',
      'stat.summary': '本次已处理 {n} 张 · 成功 {ok} · 平均 {ms}ms',

      'selftest.title': '【QRSuite 自检 {result}】',
      'selftest.pass': '通过',
      'selftest.fail': '未通过',
      'selftest.banner': '自检{result}：{detail}',
      'st.protocol': '页面协议',
      'st.decodeJs': 'decode.js 已加载',
      'st.decodeJsOk': 'QRCascade.decode 可用',
      'st.missing': '缺失',
      'st.dragBound': '拖拽事件已绑定',
      'st.dragOk': 'drop/paste/click 已就绪',
      'st.dragNo': '未绑定（脚本中断）',
      'st.worker': 'Worker 可用',
      'st.workerN': '{n} 个',
      'st.workerFile': 'file:// 下浏览器禁止 Worker，已自动回退主线程（正常）',
      'st.workerFallback': '不可用，已回退主线程',
      'st.sw': '离线缓存(SW)',
      'st.swOk': '已注册',
      'st.swNa': 'file:// 下不适用',
      'err.selfTestImg': '内置测试图加载失败',
      'st.e2e': '图片→解码 全链路',
      'st.e2eOk': '得到「{text}」，{via}',
      'st.e2eNo': '未解出',
      'msg.workerFallback': '后台线程不可用（{msg}），已切换为主线程解码；功能不受影响。',
    },

    en: {
      'app.title': 'QRSuite · Multi-engine QR & barcode scanner',
      'app.desc': 'Decode QR / MicroQR / DataMatrix / Aztec / PDF417 / 1D barcodes entirely in your browser. Images are never uploaded, and it works offline.',
      'lang.toggle': '中文',
      'lang.title': 'Switch to Chinese',
      'hero.lead': 'Decoded locally in your browser · supports <b>QR / MicroQR / DataMatrix / Aztec / PDF417 / Code128·39·93 / EAN·UPC / ITF / Codabar</b><br>Images are <b>never uploaded</b> — everything happens in your device\'s memory, and it works offline.',
      'drop.title': 'Drop images here, or click to choose files',
      'drop.sub': 'Multiple files at once · paste a screenshot with <b>Ctrl+V</b> · camera photos welcome',
      'opt.mode': 'Mode',
      'mode.fast': 'Fast (2 stages only, lowest CPU)',
      'mode.balanced': 'Balanced (default, stops on first hit)',
      'mode.deep': 'Deep (all variants, hardest images)',
      'opt.verify': 'Cross-verify',
      'opt.verifyTip': 'Only accept a result when two engines agree — reduces misreads',
      'opt.selftest': '🧪 Self-test',
      'opt.selftestTip': 'Generate a QR code in the browser and decode it, exercising the whole pipeline',
      'opt.backend': 'Local engine boost',
      'opt.backendTip': 'Call the local Python engines (OpenCV / zbar / bardecoder / WeChatQRCode)',
      'hist.title': 'History',
      'hist.hint': '(stored in this browser, {n} items)',
      'hist.exportJson': 'Export JSON',
      'hist.exportCsv': 'Export CSV',
      'hist.clear': 'Clear',
      'hist.confirmClear': 'Clear the history stored in this browser?',
      'foot.manual': '📖 Manual',
      'foot.repo': 'Repository',
      'foot.note': 'Browser decoding by jsQR + ZXing-js (bundled locally, no CDN) · optional local Python backend',

      'env.proto': 'protocol <code>{p}</code>',
      'env.workerOk': 'Worker <b class="ok">available</b> ({n})',
      'env.workerNo': 'Worker <b class="warn">unavailable → decoding on the main thread</b>',
      'env.engines': 'engines <code>{e}</code>',
      'env.notLoaded': 'not loaded',
      'env.fileHint': '<span class="warn">On file:// consider running the local server: <code>python -m qrsuite --serve</code></span>',
      'env.backendOk': 'local boost <b class="ok">available</b>',

      'err.noImages': 'No image files detected — please drop png / jpg / gif / bmp / webp',
      'msg.received': 'Got {n} image(s), decoding…',
      'err.script': 'Script error: {msg}',
      'err.noWorker': 'This browser does not support Web Workers',
      'err.fileWorker': "Browsers forbid creating a Worker on file:// (origin 'null')",
      'err.worker': 'Worker error: {msg}',
      'err.workerTimeout': 'Worker timed out',
      'err.cascadeMissing': 'decode.js is not loaded',
      'err.imgDecode': 'Could not decode the image (unsupported format?)',
      'err.decode': 'Decoding failed: {msg}',
      'err.decodeShort': 'Decoding failed',
      'msg.decoding': 'Decoding…',
      'tag.backend': ' · local boost',
      'tag.mainThread': ' · main thread',
      'meta.notDecoded': '❌ Not decoded · {w}×{h} · {stages} stages · {ms}ms{tag}',
      'meta.decoded': '{w}×{h} · {n} result(s) · {ms}ms · {stages} stages{early}{tag}',
      'meta.early': ' · early exit',
      'btn.copy': 'Copy',
      'btn.open': 'Open link',
      'btn.copied': 'Copied',
      'hist.copyTitle': 'Click to copy',
      'stat.summary': 'Processed {n} · succeeded {ok} · avg {ms}ms',

      'selftest.title': '[QRSuite self-test {result}] ',
      'selftest.pass': 'passed',
      'selftest.fail': 'failed',
      'selftest.banner': 'Self-test {result}: {detail}',
      'st.protocol': 'Page protocol',
      'st.decodeJs': 'decode.js loaded',
      'st.decodeJsOk': 'QRCascade.decode is available',
      'st.missing': 'missing',
      'st.dragBound': 'Drag & drop bound',
      'st.dragOk': 'drop/paste/click ready',
      'st.dragNo': 'not bound (script aborted)',
      'st.worker': 'Worker available',
      'st.workerN': '{n}',
      'st.workerFile': 'browsers forbid Workers on file:// — fell back to the main thread (expected)',
      'st.workerFallback': 'unavailable — fell back to the main thread',
      'st.sw': 'Offline cache (SW)',
      'st.swOk': 'registered',
      'st.swNa': 'not applicable on file://',
      'err.selfTestImg': 'Failed to load the built-in test image',
      'st.e2e': 'Image → decode pipeline',
      'st.e2eOk': 'got "{text}", {via}',
      'st.e2eNo': 'no result',
      'msg.workerFallback': 'Background worker unavailable ({msg}) — switched to main-thread decoding; functionality is unaffected.',
    },
  };

  const LKEY = 'qrsuite.lang';

  function detect() {
    try {
      const saved = localStorage.getItem(LKEY);
      if (saved === 'zh' || saved === 'en') return saved;
    } catch (e) { /* 隐私模式下 localStorage 可能抛异常 */ }
    const nav = (navigator.language || navigator.userLanguage || 'en');
    return /^zh/i.test(nav) ? 'zh' : 'en';
  }

  let lang = detect();

  /** 取文案并替换 {占位符} */
  function t(key, vars) {
    const table = STR[lang] || STR.en;
    let s = table[key];
    if (s === undefined) s = (STR.zh[key] !== undefined ? STR.zh[key] : key);
    if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined ? vars[k] : m));
    return s;
  }

  /** 把带 data-i18n* 的元素刷新一遍。
   *
   *  注意：`querySelectorAll('[data-i18n]')` 只匹配**字面量**属性名，
   *  不会匹配 `data-i18n-html` / `-title` / `-content`（它们是不同的属性名），
   *  所以必须分别收集——曾因此漏译了两个含内联标签的文案（hero.lead / drop.sub）。
   */
  function apply(rootEl) {
    const scope = rootEl || document;
    // 纯文本
    scope.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    // 含内联标签（<b> 等），需要 innerHTML
    scope.querySelectorAll('[data-i18n-html]').forEach(el => {
      el.innerHTML = t(el.getAttribute('data-i18n-html'));
    });
    scope.querySelectorAll('[data-i18n-title]').forEach(el => {
      el.setAttribute('title', t(el.getAttribute('data-i18n-title')));
    });
    scope.querySelectorAll('[data-i18n-content]').forEach(el => {
      el.setAttribute('content', t(el.getAttribute('data-i18n-content')));
    });
    // <html lang> 与 <title>
    document.documentElement.lang = (lang === 'zh') ? 'zh-CN' : 'en';
    document.title = t('app.title');
  }

  function setLang(next) {
    lang = (next === 'zh') ? 'zh' : 'en';
    try { localStorage.setItem(LKEY, lang); } catch (e) { /* ignore */ }
    apply();
    // 让页面自己重刷动态文案（状态条、统计、自检结果等）
    if (typeof root.onLangChange === 'function') {
      try { root.onLangChange(lang); } catch (e) { /* ignore */ }
    }
  }

  function toggle() { setLang(lang === 'zh' ? 'en' : 'zh'); }

  root.QRi18n = { t: t, apply: apply, setLang: setLang, toggle: toggle, get lang() { return lang; }, STR: STR };

  // 自动注入切换按钮：找到 header 则在其中插入，否则固定右上角
  function injectToggle() {
    if (document.getElementById('lang-toggle')) return;
    const btn = document.createElement('button');
    btn.id = 'lang-toggle';
    btn.type = 'button';
    btn.className = 'lang-toggle';
    btn.setAttribute('data-i18n', 'lang.toggle');
    btn.setAttribute('data-i18n-title', 'lang.title');
    btn.addEventListener('click', () => toggle());
    const header = document.querySelector('header');
    if (header) header.appendChild(btn);
    else { btn.classList.add('floating'); document.body.appendChild(btn); }
  }

  root.addEventListener('DOMContentLoaded', () => {
    injectToggle();
    apply();
  });
})(typeof self !== 'undefined' ? self : this);
