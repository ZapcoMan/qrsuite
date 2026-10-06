/*! QRSuite v2 · 前端逻辑
 *  健壮性设计（v2.0.1 修复）：
 *   1) 先绑定 UI 事件，再做任何可能抛异常的初始化 —— 避免一处失败导致"拖拽/选择全失效"
 *   2) Worker 不可用（file:// 下 origin 'null' 会抛 SecurityError）时自动回退主线程解码
 *   3) 顶部状态条明示运行环境，失败不再静默
 */
'use strict';
const $ = s => document.querySelector(s);
const listEl = $('#list'), dropEl = $('#drop'), fileEl = $('#file'), statEl = $('#stats'), envEl = $('#env');

/* 内置自检二维码：data URI 形式，file:// 下也不会污染 canvas，可安全 getImageData */
const SELFTEST_QR = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAK4AAACuCAAAAACKZ2kyAAACEklEQVR4nO3cwY6jMBAA0XJp/v+XvYe5IEVEJjvRTJm8EwLHiVqiaRqcMSmRFEmRFEmRFEmRFEmRFEmRFEmRFEmRFEmRFEmRFEmRFEmRlK+zA2N5inkYf9w+Ott/Zu4RXUmRFEmRPTLDt+f9yfF05HwYc3XOfHQlRVIkRXbKDCyf3ev1AC9ljGR0JUVSJEX2ywwr5nItcaPoSoqkSIrcMzM85oTxhvwQi66kSIqkyH6ZYS6MuZoHJjeIrqRIiqTITplhXJzu7DnF/I85w9GVFEmRFEkZP9sHeF+HIRldSZEUSZE9MsN4et0/jmGhKpgnM69/VzK6kiIpkiI71Qxj4R5hvU4YD3uuzhCLrqRIiqTITjUDC9f39TchX8sG4ehKiqRIiuzRgZyH8/fsLF5553lePPq5m/g9kiIpsutTy3Gx/zBPto9z8nR/PrqSIimSIvd8NjGW+4rj4bOfu4m/QVIkRe651vJopZbgpA7ZKrqSIimSIndeazlOPjUfxp/N9rmb+D2SIilyz7WWr3UU52HMhtGVFEmRFEn5+tnpzvoJ42T7e+Snz/A3SIqkyD0zw7j43uNrNUksupIiKZIi91xrOZ92FOfJ/rNOxSbRlRRJkRS551rLcfG/nsbT96k2ia6kSIqkyJ3XWr6bpEiKpEiKpEiKpEiKpEiKpEiKpEiKpEiKpEiKpEiKpEiKv/0DrvkHvhNbb+6MR/YAAAAASUVORK5CYII=';
const MODES = { fast: 2, balanced: 7, deep: 99 };
let MODE = 'balanced';
let workerPool = null;      // null = 不可用，走主线程
let backendOK = false;      // 本机 Python 后端可用？
let ready = false;          // UI 是否已绑定

/* ============================ 状态提示 ============================ */
function banner(msg, kind = 'warn') {
  if (!envEl) { console.warn('[QRSuite]', msg); return; }
  const cls = kind === 'err' ? 'err' : kind === 'ok' ? 'ok' : 'warn';
  const old = envEl.dataset.keep === '1' ? envEl.innerHTML + '<br>' : '';
  envEl.innerHTML = old + `<span class="${cls}">${msg}</span>`;
}
function envInfo() {
  const proto = location.protocol;
  const parts = [`协议 <code>${proto}</code>`];
  parts.push(workerPool ? `Worker <b class="ok">可用</b>（${workerPool.length} 个）` : `Worker <b class="warn">不可用 → 主线程解码</b>`);
  parts.push(`引擎 <code>${(window.QRCascade ? 'jsQR+ZXing-js' : '未加载')}</code>`);
  if (proto === 'file:') parts.push(`<span class="warn">file:// 下建议改用本地服务：<code>python -m qrsuite --serve</code></span>`);
  if (backendOK) parts.push(`本机增强 <b class="ok">可用</b>`);
  return parts.join(' · ');
}
function refreshEnv() { if (envEl) envEl.innerHTML = envInfo(); }

/* ============================ 1. 先绑定 UI（绝不依赖后续初始化） ============================ */
function handleFiles(files) {
  const imgs = [...files].filter(f => (f.type && f.type.startsWith('image/')) || /\.(png|jpe?g|gif|bmp|webp|tiff?)$/i.test(f.name || ''));
  if (!imgs.length) { banner('没有检测到图片文件，请拖入 png / jpg / gif / bmp / webp', 'err'); return; }
  banner(`已接收 ${imgs.length} 张图片，开始解码…`, 'ok');
  imgs.forEach(decodeFile);
}

function bindUI() {
  if (ready) return;
  ready = true;

  ['dragenter', 'dragover'].forEach(ev => document.addEventListener(ev, e => {
    e.preventDefault(); e.stopPropagation();
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
    dropEl.classList.add('hot');
  }, false));
  ['dragleave', 'dragend'].forEach(ev => document.addEventListener(ev, e => {
    e.preventDefault();
    if (ev === 'dragleave' && e.relatedTarget) return;
    dropEl.classList.remove('hot');
  }, false));
  document.addEventListener('drop', e => {
    e.preventDefault(); e.stopPropagation();
    dropEl.classList.remove('hot');
    const dt = e.dataTransfer;
    if (!dt) return;
    let files = [...(dt.files || [])];
    if (!files.length && dt.items) files = [...dt.items].map(i => i.getAsFile()).filter(Boolean);
    handleFiles(files);
  }, false);

  dropEl.addEventListener('click', () => fileEl.click());
  dropEl.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') fileEl.click(); });
  fileEl.addEventListener('change', () => { handleFiles([...fileEl.files]); fileEl.value = ''; });

  document.addEventListener('paste', e => {
    const items = [...((e.clipboardData || {}).items || [])].filter(i => i.type && i.type.startsWith('image/'));
    if (items.length) handleFiles(items.map(i => i.getAsFile()).filter(Boolean));
  });

  $('#mode').addEventListener('change', () => { MODE = $('#mode').value; });
  $('#selftest').addEventListener('click', () => runSelfTest(true));
  $('#exp-json').addEventListener('click', () => download('qrsuite-history.json', JSON.stringify(hist(), null, 2)));
  $('#exp-csv').addEventListener('click', () => {
    const rows = [['time', 'file', 'format', 'text', 'engines']].concat(hist().map(r =>
      [new Date(r.t).toLocaleString(), r.name, r.format, r.text, (r.engines || []).join('|')]));
    download('qrsuite-history.csv', '\ufeff' + rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n'));
  });
  $('#clear').addEventListener('click', () => { if (confirm('清空本机历史记录？')) { localStorage.removeItem(HKEY); renderHistory(); } });
  window.addEventListener('error', e => banner('脚本错误：' + (e.message || e.error), 'err'));
}

/* ============================ 2. 解码执行器（Worker 优先，主线程兜底） ============================ */
const pending = new Map();
let seq = 0, rr = 0;

function initWorkers() {
  if (typeof Worker === 'undefined') throw new Error('浏览器不支持 Web Worker');
  if (location.protocol === 'file:') throw new Error("file:// 下浏览器禁止创建 Worker（origin 'null'）");
  const n = Math.max(1, Math.min(4, (navigator.hardwareConcurrency || 4) - 1));
  const pool = [];
  for (let i = 0; i < n; i++) {
    const w = new Worker('decode.worker.js');
    w.onmessage = e => { const t = pending.get(e.data.id); if (t) { pending.delete(e.data.id); t(e.data); } };
    w.onerror = e => banner('Worker 出错：' + (e.message || ''), 'err');
    pool.push(w);
  }
  return pool;
}

function decodeViaWorker(rgba, w, h, mode, verify) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    const worker = workerPool[rr++ % workerPool.length];
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('Worker 超时')); }, 60000);
    pending.set(id, r => { clearTimeout(timer); r.ok ? resolve(r) : reject(new Error(r.error)); });
    worker.postMessage({ id, buf: rgba.buffer.slice(0), w, h, mode, verify });
  });
}

function decodeViaMainThread(rgba, w, h, mode, verify) {
  if (!window.QRCascade) return Promise.reject(new Error('decode.js 未加载'));
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      try { const r = window.QRCascade.decode(new Uint8ClampedArray(rgba.buffer), w, h, mode, verify); r.ok = true; resolve(r); }
      catch (e) { reject(e); }
    }, 0);
  });
}

/* ============================ 3. 取像素 ============================ */
async function fileToRGBA(file) {
  let bitmap = null, img = null;
  try {
    if (typeof createImageBitmap === 'function') bitmap = await createImageBitmap(file);
  } catch (e) { bitmap = null; }
  if (!bitmap) {
    img = await new Promise((res, rej) => {
      const i = new Image();
      i.onload = () => res(i); i.onerror = () => rej(new Error('图片解码失败（格式不支持？）'));
      i.src = URL.createObjectURL(file);
    });
  }
  const src = bitmap || img, w = src.width, h = src.height;
  let ctx;
  if (typeof OffscreenCanvas !== 'undefined') {
    ctx = new OffscreenCanvas(w, h).getContext('2d', { willReadFrequently: true });
  } else {
    const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
    ctx = cv.getContext('2d', { willReadFrequently: true });
  }
  ctx.drawImage(src, 0, 0);
  const data = ctx.getImageData(0, 0, w, h).data;
  if (bitmap && bitmap.close) try { bitmap.close(); } catch (e) { }
  if (img) URL.revokeObjectURL(img.src);
  return { rgba: data, w, h };
}

/* ============================ 4. 主流程 ============================ */
async function decodeFile(file) {
  const card = makeCard(file);
  const t0 = performance.now();
  try {
    const { rgba, w, h } = await fileToRGBA(file);
    const useWorker = !!workerPool;
    let res = useWorker
      ? await decodeViaWorker(rgba, w, h, MODE, $('#verify').checked)
      : await decodeViaMainThread(rgba, w, h, MODE, $('#verify').checked);

    if (backendOK && $('#backend').checked) {
      const br = await fetch('/api/decode', {
        method: 'POST', body: file, headers: {
          'X-Filename': encodeURIComponent(file.name || 'clipboard.png'),
          'X-Mode': MODE, 'X-Verify': $('#verify').checked ? '1' : '0'
        }
      }).then(r => r.json()).catch(() => null);
      if (br && br.ok) res = mergeBackend(res, br);
    }
    res.width = w; res.height = h; res.viaWorker = useWorker;
    render(card, res, (performance.now() - t0) / 1000, file);
  } catch (err) {
    card.querySelector('.meta').className = 'meta err';
    card.querySelector('.meta').textContent = '❌ ' + (err && err.message || err);
    banner('解码失败：' + (err && err.message || err), 'err');
  }
}

function mergeBackend(js, py) {
  const hits = new Map();
  for (const h of js.hits) hits.set(h.text, { text: h.text, format: h.format, engines: new Set(h.engines), variants: new Set(h.variants) });
  for (const h of py.results) {
    const cur = hits.get(h.text) || { text: h.text, format: h.format, engines: new Set(), variants: new Set() };
    h.engines.forEach(e => cur.engines.add('py:' + e));
    h.variants.forEach(v => cur.variants.add(v));
    hits.set(h.text, cur);
  }
  return Object.assign({}, js, {
    hits: [...hits.values()].map(v => ({ text: v.text, format: v.format, engines: [...v.engines], variants: [...v.variants] })),
    backend: true
  });
}

/* ============================ 5. 渲染 ============================ */
function makeCard(file) {
  const el = document.createElement('div');
  el.className = 'card';
  el.innerHTML = `<img class="thumb" alt=""><div class="cnt">
      <div class="fname"></div><div class="meta spin">解码中…</div><div class="body"></div></div>`;
  el.querySelector('.fname').textContent = file.name || 'clipboard.png';
  el.querySelector('.thumb').src = URL.createObjectURL(file);
  listEl.prepend(el);
  return el;
}

function render(card, res, total, file) {
  const meta = card.querySelector('.meta'), body = card.querySelector('.body');
  const tag = (res.backend ? ' · 本机增强' : '') + (res.viaWorker === false ? ' · 主线程' : '');
  if (!res.ok) { meta.className = 'meta err'; meta.textContent = '❌ ' + (res.error || '解码失败'); return; }
  if (!res.hits.length) {
    meta.className = 'meta err';
    meta.textContent = `❌ 未解码 · ${res.width}×${res.height} · ${res.stages} 阶段 · ${(total * 1000).toFixed(0)}ms${tag}`;
    return;
  }
  stat.n++; stat.ok++; stat.ms += total * 1000; bumpStats();
  meta.textContent = `${res.width}×${res.height} · 解出 ${res.hits.length} 条 · ${(total * 1000).toFixed(0)}ms · ${res.stages} 阶段${res.early ? ' · 早退' : ''}${tag}`;
  res.hits.forEach(h => {
    const d = document.createElement('div');
    d.className = 'res';
    d.innerHTML = `<div><span class="badge f"></span>${h.engines.map(e => `<span class="badge g">${e}</span>`).join('')}` +
      `${h.variants.slice(0, 4).map(v => `<span class="badge">${v}</span>`).join('')}</div>
      <div class="val"></div><div class="row"><button>复制</button><button>打开链接</button></div>`;
    d.querySelector('.badge.f').textContent = h.format;
    d.querySelector('.val').textContent = h.text;
    const [b1, b2] = d.querySelectorAll('button');
    b1.onclick = () => { navigator.clipboard.writeText(h.text).catch(() => { }); b1.textContent = '已复制'; setTimeout(() => b1.textContent = '复制', 1200); };
    b2.onclick = () => window.open(h.text, '_blank');
    body.appendChild(d);
    history_add({ name: file.name || 'clipboard', format: h.format, text: h.text, engines: h.engines, file: file.size });
  });
}

/* ============================ 6. 历史 ============================ */
const HKEY = 'qrsuite.history';
function hist() { try { return JSON.parse(localStorage.getItem(HKEY) || '[]'); } catch (e) { return []; } }
function history_add(rec) {
  const h = hist(); h.unshift(Object.assign({ t: Date.now() }, rec));
  try { localStorage.setItem(HKEY, JSON.stringify(h.slice(0, 200))); } catch (e) { }
  renderHistory();
}
function renderHistory() {
  const h = hist(); $('#hcount').textContent = h.length;
  $('#hlist').innerHTML = h.slice(0, 30).map(r =>
    `<div class="hrow"><span class="badge f">${r.format}</span><span class="hname">${esc(r.name)}</span>
     <span class="hval" title="点击复制">${esc(r.text)}</span>
     <button data-copy="${encodeURIComponent(r.text)}">复制</button></div>`).join('');
  $('#hlist').querySelectorAll('button[data-copy]').forEach(b => b.onclick = () => {
    navigator.clipboard.writeText(decodeURIComponent(b.dataset.copy)).catch(() => { }); b.textContent = '✓';
  });
}
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function download(name, text) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
  a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 3000);
}

/* ============================ 7. 统计 ============================ */
const stat = { n: 0, ok: 0, ms: 0 };
function bumpStats() {
  statEl.textContent = stat.n ? `本次已处理 ${stat.n} 张 · 成功 ${stat.ok} · 平均 ${(stat.ms / stat.n).toFixed(0)}ms` : '';
}

/* ============================ 8. 自检（内置二维码图 → 像素 → 解码，全链路） ============================ */
async function runSelfTest(verbose) {
  const out = [];
  const ok = (name, cond, extra) => { out.push(`${cond ? '✓' : '✗'} ${name}${extra ? ' — ' + extra : ''}`); return cond; };
  ok('页面协议', true, location.protocol);
  ok('decode.js 已加载', !!window.QRCascade, window.QRCascade ? 'QRCascade.decode 可用' : '缺失');
  ok('拖拽事件已绑定', ready, ready ? 'drop/paste/click 已就绪' : '未绑定（脚本中断）');
  const isFile = location.protocol === 'file:';
  ok('Worker 可用', !!workerPool || isFile,
     workerPool ? `${workerPool.length} 个` : (isFile ? 'file:// 下浏览器禁止 Worker，已自动回退主线程（正常）' : '不可用，已回退主线程'));
  ok('离线缓存(SW)', 'serviceWorker' in navigator, location.protocol.startsWith('http') ? '已注册' : 'file:// 下不适用');

  let text = null, via = '';
  try {
    // 用 <img> 加载（file:// 下 fetch 本地文件被浏览器禁止，<img> 可以）
    const img = await new Promise((res, rej) => {
      const i = new Image();
      i.onload = () => res(i); i.onerror = () => rej(new Error('内置测试图加载失败'));
      i.src = SELFTEST_QR;
    });
    let ctx;
    if (typeof OffscreenCanvas !== 'undefined') ctx = new OffscreenCanvas(img.width, img.height).getContext('2d');
    else { const cv = document.createElement('canvas'); cv.width = img.width; cv.height = img.height; ctx = cv.getContext('2d'); }
    ctx.drawImage(img, 0, 0);
    const rgba = ctx.getImageData(0, 0, img.width, img.height);
    const t0 = performance.now();
    const r = workerPool ? await decodeViaWorker(rgba.data, img.width, img.height, 'fast', false)
                         : await decodeViaMainThread(rgba.data, img.width, img.height, 'fast', false);
    const ms = (performance.now() - t0).toFixed(0);
    text = r.hits.length ? r.hits[0].text : null;
    via = `${r.stages} 阶段 / ${ms}ms / ${workerPool ? 'Worker' : '主线程'}`;
    ok('图片→解码 全链路', text === 'QRSUITE-SELFTEST-OK', text ? `得到「${text}」，${via}` : '未解出');
  } catch (e) { ok('图片→解码 全链路', false, String(e)); }

  const pass = out.every(l => l.startsWith('✓'));
  const report = `【QRSuite 自检 ${pass ? '通过' : '未通过'}】` + out.join('；');
  statEl.textContent = report;
  banner(`自检${pass ? '<b class="ok">通过</b>' : '<b class="err">未通过</b>'}：${out.join('；')}`, pass ? 'ok' : 'err');
  if (verbose) console.log(report);
  return pass;
}

/* ============================ 9. 启动 ============================ */
bindUI();                                    // ← 先绑定，任何后续失败都不影响交互
try {
  workerPool = initWorkers();
} catch (e) {
  workerPool = null;
  banner(`后台线程不可用（${e.message}），已切换为主线程解码；功能不受影响。`, 'warn');
}
refreshEnv();
renderHistory();

(async () => {
  try {
    const r = await fetch('/health', { cache: 'no-store' });
    if (!r.ok) return;
    const j = await r.json();
    backendOK = !!(j && j.ok);
    if (backendOK) {
      $('#backend-row').style.display = '';
      $('#backend-engines').textContent = (j.engines || []).join(' / ');
      refreshEnv();
    }
  } catch (e) { /* file:// 或纯静态部署：正常情况 */ }
})();

if (location.search.includes('selftest=1')) setTimeout(() => runSelfTest(true), 300);

/* PWA：可安装到桌面/手机，离线可用（仅 http(s) 生效） */
if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
  navigator.serviceWorker.register('sw.js').catch(() => { });
}
window.QRS = { runSelfTest, decodeFile, handleFiles, get workerOk() { return !!workerPool; } };
