from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List

try:
    import streamlit.components.v1 as components
except Exception:
    components = SimpleNamespace(html=lambda *args, **kwargs: None)

def render_svg_edge_mapper_html(
    svg_inline: str,
    edge_names: List[str],
    height: int = 740,
    title: str = "Разметка веток по SVG (клик → точки → сегмент)",
):
    """HTML-инструмент для создания mapping JSON: edge_name -> polyline(points).

    Важно: это односторонний компонент (Streamlit components.html), поэтому:
    - JSON выдаётся в textarea + кнопка Download/Copy.
    - затем пользователь загружает JSON обратно в Streamlit для анимации.

    Mapping формат (version 2):
      {
        "version": 2,
        "viewBox": "0 0 1920 1080",
        "edges": {
          "edgeA": [
             [[x,y],[x,y],...],   # polyline 1
             [[x,y],...],         # polyline 2 ...
          ],
          ...
        },
        "nodes": {
          "Ресивер3": [x,y],
          ...
        }
      }

    Поле nodes можно размечать отдельным инструментом render_svg_node_mapper_html().
    """
    payload = {
        "title": title,
        "svg": svg_inline,
        "edgeNames": edge_names,
    }
    js_data = json.dumps(payload, ensure_ascii=False)

    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; }
    .wrap { display:flex; gap:0; height: 100%; min-height: 640px; }
    .left { width: 360px; padding: 10px; border-right: 1px solid #e6e6e6; box-sizing:border-box; overflow:auto; }
    .right { flex: 1; position: relative; overflow:hidden; background: #fafafa; }
    h3 { margin: 0 0 6px 0; font-size: 16px; }
    .muted { color:#666; font-size: 12px; line-height: 1.35; margin-bottom: 8px; }
    label { display:block; font-size:12px; color:#444; margin-top:8px; }
    select, textarea { width:100%; box-sizing:border-box; }
    textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; }
    .row { display:flex; gap:8px; margin: 8px 0; flex-wrap: wrap; }
    .btn { padding: 6px 10px; border: 1px solid #bbb; border-radius: 8px; background:#fff; cursor:pointer; font-size: 12px; }
    .btn.primary { border-color:#1f77b4; }
    .btn.danger { border-color:#c62828; }
    .btn:active { transform: translateY(1px); }

    /* SVG */
    #svgHost svg { width: 100%; height: 100%; display:block; background: white; user-select:none; }
    .edgePath { fill:none; stroke: rgba(220,0,0,0.55); stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; }
    .edgePath.other { stroke: rgba(0,0,0,0.10); stroke-width: 3; }
    .draft { fill:none; stroke: rgba(0,128,255,0.90); stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 10 7; }
    .pt { fill: rgba(0,128,255,0.90); }
    .hud { position:absolute; left: 10px; top: 10px; padding: 6px 8px; background: rgba(255,255,255,0.85); border: 1px solid #ddd; border-radius: 8px; font-size: 12px; }
    .hud b { font-variant-numeric: tabular-nums; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="left">
      <h3 id="title"></h3>
      <div class="muted">
        <div><b>Режим “Рисовать”</b>: клик по схеме → добавляется точка.</div>
        <div>Нажмите <b>“Завершить сегмент”</b>, чтобы сохранить polyline для выбранной ветки.</div>
        <div><b>Режим “Пан”</b>: drag мышью. Колёсико — zoom. Кнопка “Сброс вида”.</div>
        <div style="margin-top:6px;">Дальше: скачайте JSON и загрузите его в Streamlit в блоке анимации “По схеме”.</div>
      </div>

      <label>Ветка (edge)</label>
      <select id="edgeSel"></select>

      <div class="row">
        <button id="modeDraw" class="btn primary">✏️ Рисовать</button>
        <button id="modePan" class="btn">✋ Пан</button>
        <button id="resetView" class="btn">↺ Сброс вида</button>
      </div>

      <div class="row">
        <button id="undo" class="btn">↶ Undo</button>
        <button id="finish" class="btn primary">✅ Завершить сегмент</button>
        <button id="clearEdge" class="btn danger">🗑 Очистить ветку</button>
      </div>

      <div class="row">
        <button id="copy" class="btn">📋 Copy JSON</button>
        <button id="download" class="btn">⬇️ Download JSON</button>
      </div>

      <label>Mapping JSON</label>
      <textarea id="json" rows="16" spellcheck="false"></textarea>

      <div class="row">
        <button id="loadJson" class="btn">⭮ Загрузить из поля</button>
      </div>
    </div>

    <div class="right">
      <div id="svgHost">__SVG_INLINE__</div>
      <div class="hud">
        режим: <b id="mode">draw</b> ·
        edge: <b id="edgeName"></b> ·
        pts: <b id="pts">0</b>
      </div>
    </div>
  </div>

<script>
const DATA = __JS_DATA__;
document.getElementById('title').textContent = DATA.title || 'SVG mapping';
const edgeSel = document.getElementById('edgeSel');
const modeEl = document.getElementById('mode');
const edgeNameEl = document.getElementById('edgeName');
const ptsEl = document.getElementById('pts');
const jsonEl = document.getElementById('json');

const EDGE_NAMES = DATA.edgeNames || [];
EDGE_NAMES.forEach(n => {
  const opt = document.createElement('option');
  opt.value = n; opt.textContent = n;
  edgeSel.appendChild(opt);
});

// SVG
const svgHost = document.getElementById('svgHost');
svgHost.innerHTML = DATA.svg || '';
const svg = svgHost.querySelector('svg');
if (!svg) {
  svgHost.innerHTML = '<div style="padding:12px;color:#c00">SVG не найден в HTML.</div>';
}

function parseViewBox(vbStr) {
  // NOTE: двойной backslash нужен, чтобы не ловить Python SyntaxWarning
  // "invalid escape sequence '\\s'" при генерации HTML из строки.
  const a = (vbStr || '').trim().split(/\\s+/).map(parseFloat);
  if (a.length !== 4 || a.some(x => Number.isNaN(x))) return null;
  return {x:a[0], y:a[1], w:a[2], h:a[3]};
}
const vb0 = parseViewBox(svg?.getAttribute('viewBox')) || {x:0, y:0, w:1920, h:1080};
let view = {...vb0};

function setViewBox(v) {
  svg.setAttribute('viewBox', `${v.x} ${v.y} ${v.w} ${v.h}`);
}
function resetView() { view = {...vb0}; setViewBox(view); }

// overlay
const NS = "http://www.w3.org/2000/svg";
const overlay = document.createElementNS(NS, 'g');
overlay.setAttribute('id', 'pneumo_overlay');
svg.appendChild(overlay);

const segLayer = document.createElementNS(NS, 'g');
const draftLayer = document.createElementNS(NS, 'g');
overlay.appendChild(segLayer);
overlay.appendChild(draftLayer);

// mapping state
let mapping = { version: 2, viewBox: svg.getAttribute('viewBox') || `${vb0.x} ${vb0.y} ${vb0.w} ${vb0.h}`, edges: {}, nodes: {} };
EDGE_NAMES.forEach(n => { mapping.edges[n] = []; });

let mode = 'draw'; // draw | pan
let selectedEdge = EDGE_NAMES[0] || '';
edgeNameEl.textContent = selectedEdge;

let curPts = [];
let dragging = false;
let dragStart = null;

function getSvgPoint(clientX, clientY) {
  const pt = svg.createSVGPoint();
  pt.x = clientX; pt.y = clientY;
  const ctm = svg.getScreenCTM();
  if (!ctm) return {x:0,y:0};
  const sp = pt.matrixTransform(ctm.inverse());
  return {x: sp.x, y: sp.y};
}

function polyToPath(points) {
  if (!points || points.length < 2) return '';
  const p0 = points[0];
  let d = `M ${p0[0]} ${p0[1]}`;
  for (let i=1;i<points.length;i++) {
    const p = points[i];
    d += ` L ${p[0]} ${p[1]}`;
  }
  return d;
}

function rebuildSegments() {
  while (segLayer.firstChild) segLayer.removeChild(segLayer.firstChild);
  for (const [edge, segs] of Object.entries(mapping.edges)) {
    const isSel = (edge === selectedEdge);
    for (const seg of (segs || [])) {
      const path = document.createElementNS(NS, 'path');
      path.setAttribute('d', polyToPath(seg));
      path.setAttribute('class', 'edgePath' + (isSel ? '' : ' other'));
      segLayer.appendChild(path);
    }
  }
}

function rebuildDraft() {
  while (draftLayer.firstChild) draftLayer.removeChild(draftLayer.firstChild);
  if (curPts.length >= 2) {
    const pts = curPts.map(p => [p.x, p.y]);
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', polyToPath(pts));
    path.setAttribute('class', 'draft');
    draftLayer.appendChild(path);
  }
  for (const p of curPts) {
    const c = document.createElementNS(NS, 'circle');
    c.setAttribute('cx', p.x);
    c.setAttribute('cy', p.y);
    c.setAttribute('r', 6);
    c.setAttribute('class', 'pt');
    draftLayer.appendChild(c);
  }
  ptsEl.textContent = String(curPts.length);
}

function syncJson(pretty=true) {
  const s = JSON.stringify(mapping, null, pretty ? 2 : 0);
  jsonEl.value = s;
}

function setMode(m) {
  mode = m;
  modeEl.textContent = mode;
  document.getElementById('modeDraw').classList.toggle('primary', mode === 'draw');
  document.getElementById('modePan').classList.toggle('primary', mode === 'pan');
}

edgeSel.addEventListener('change', () => {
  selectedEdge = edgeSel.value;
  edgeNameEl.textContent = selectedEdge;
  curPts = [];
  rebuildDraft();
  rebuildSegments();
  syncJson(true);
});

document.getElementById('modeDraw').addEventListener('click', () => setMode('draw'));
document.getElementById('modePan').addEventListener('click', () => setMode('pan'));
document.getElementById('resetView').addEventListener('click', () => resetView());

document.getElementById('undo').addEventListener('click', () => {
  curPts.pop();
  rebuildDraft();
});

document.getElementById('finish').addEventListener('click', () => {
  if (curPts.length < 2) return;
  const seg = curPts.map(p => [Number(p.x.toFixed(2)), Number(p.y.toFixed(2))]);
  mapping.edges[selectedEdge] = mapping.edges[selectedEdge] || [];
  mapping.edges[selectedEdge].push(seg);
  curPts = [];
  rebuildDraft();
  rebuildSegments();
  syncJson(true);
});

document.getElementById('clearEdge').addEventListener('click', () => {
  mapping.edges[selectedEdge] = [];
  curPts = [];
  rebuildDraft();
  rebuildSegments();
  syncJson(true);
});

document.getElementById('copy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(jsonEl.value || '');
  } catch(e) {}
});

document.getElementById('download').addEventListener('click', () => {
  const blob = new Blob([jsonEl.value || ''], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'pneumo_svg_mapping.json';
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById('loadJson').addEventListener('click', () => {
  try {
    const obj = JSON.parse(jsonEl.value || '{}');
    if (!obj || typeof obj !== 'object') return;
    if (!obj.edges) obj.edges = {};
    if (!obj.nodes) obj.nodes = {};
    // Если в JSON нет некоторых веток — добавляем пустые
    EDGE_NAMES.forEach(n => { if (!obj.edges[n]) obj.edges[n] = []; });
    mapping = obj;
    if (!mapping.viewBox) mapping.viewBox = svg.getAttribute('viewBox') || `${vb0.x} ${vb0.y} ${vb0.w} ${vb0.h}`;
    rebuildSegments();
  } catch(e) {}
});


// zoom (wheel)
svg.addEventListener('wheel', (e) => {
  e.preventDefault();
  const z = (e.deltaY < 0) ? 0.9 : 1.1;
  const p = getSvgPoint(e.clientX, e.clientY);
  const nx = p.x - (p.x - view.x) * z;
  const ny = p.y - (p.y - view.y) * z;
  view = { x: nx, y: ny, w: view.w * z, h: view.h * z };
  setViewBox(view);
}, {passive:false});

// pan (drag)
svg.addEventListener('pointerdown', (e) => {
  if (mode !== 'pan') return;
  dragging = true;
  svg.setPointerCapture(e.pointerId);
  dragStart = { p: getSvgPoint(e.clientX, e.clientY), v: {...view} };
});
svg.addEventListener('pointermove', (e) => {
  if (!dragging || mode !== 'pan') return;
  const p = getSvgPoint(e.clientX, e.clientY);
  const dx = p.x - dragStart.p.x;
  const dy = p.y - dragStart.p.y;
  view = { x: dragStart.v.x - dx, y: dragStart.v.y - dy, w: dragStart.v.w, h: dragStart.v.h };
  setViewBox(view);
});
svg.addEventListener('pointerup', (e) => {
  dragging = false;
  dragStart = null;
});

// draw (click)
svg.addEventListener('click', (e) => {
  if (mode !== 'draw') return;
  const p = getSvgPoint(e.clientX, e.clientY);
  curPts.push(p);
  rebuildDraft();
});

setMode('draw');
rebuildDraft();
rebuildSegments();
syncJson(true);

</script>
</body>
</html>"""

    html = html.replace("__SVG_INLINE__", svg_inline)
    html = html.replace("__JS_DATA__", js_data)

    components.html(html, height=height, scrolling=False)


def render_svg_node_mapper_html(
    svg_inline: str,
    node_names: List[str],
    edge_names: List[str] | None = None,
    height: int = 740,
    title: str = "Разметка узлов давления по SVG (клик → позиция)",
):
    """HTML-инструмент для создания mapping JSON: node_name -> (x,y) в координатах SVG.

    Это дополняет mapping веток (edges). Идея такая:
    - Ветки размечаются в render_svg_edge_mapper_html() (polyline сегменты).
    - Узлы давления размечаются здесь: один клик = одна точка (узел).

    Формат (version 2):
      {
        "version": 2,
        "viewBox": "0 0 1920 1080",
        "edges": { ... },
        "nodes": {
           "Ресивер3": [x,y],
           ...
        }
      }

    Компонент односторонний (components.html), поэтому итоговый JSON
    нужно скачать/скопировать и загрузить обратно в блок анимации.
    """
    payload = {
        "title": title,
        "svg": svg_inline,
        "nodeNames": node_names,
        "edgeNames": (edge_names or []),
    }
    js_data = json.dumps(payload, ensure_ascii=False)

    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; }
    .wrap { display:flex; gap:0; height: 100%; min-height: 640px; }
    .left { width: 360px; padding: 10px; border-right: 1px solid #e6e6e6; box-sizing:border-box; overflow:auto; }
    .right { flex: 1; position: relative; overflow:hidden; background: #fafafa; }
    h3 { margin: 0 0 6px 0; font-size: 16px; }
    .muted { color:#666; font-size: 12px; line-height: 1.35; margin-bottom: 8px; }
    label { display:block; font-size:12px; color:#444; margin-top:8px; }
    select, textarea { width:100%; box-sizing:border-box; }
    textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; }
    .row { display:flex; gap:8px; margin: 8px 0; flex-wrap: wrap; }
    .btn { padding: 6px 10px; border: 1px solid #bbb; border-radius: 8px; background:#fff; cursor:pointer; font-size: 12px; }
    .btn.primary { border-color:#1f77b4; }
    .btn.danger { border-color:#c62828; }
    .btn:active { transform: translateY(1px); }

    #svgHost svg { width: 100%; height: 100%; display:block; background: white; user-select:none; }

    .nodeDot { fill: rgba(0,128,255,0.85); stroke: rgba(255,255,255,0.9); stroke-width: 3; }
    .nodeDot.missing { fill: rgba(200,200,200,0.7); }
    .nodeLabel {
      font-size: 14px;
      fill: rgba(0,0,0,0.85);
      stroke: rgba(255,255,255,0.95);
      stroke-width: 3;
      paint-order: stroke;
      font-variant-numeric: tabular-nums;
    }
    .hud { position:absolute; left: 10px; top: 10px; padding: 6px 8px; background: rgba(255,255,255,0.85); border: 1px solid #ddd; border-radius: 8px; font-size: 12px; }
    .hud b { font-variant-numeric: tabular-nums; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="left">
      <h3 id="title"></h3>
      <div class="muted">
        <div><b>Режим “Поставить”</b>: клик по схеме → координата выбранного узла.</div>
        <div><b>Режим “Пан”</b>: drag мышью. Колёсико — zoom. Кнопка “Сброс вида”.</div>
        <div style="margin-top:6px;">Скачайте JSON и загрузите обратно в Streamlit (в блоке анимации “По схеме”).</div>
      </div>

      <label>Узел (node)</label>
      <select id="nodeSel"></select>

      <div class="row">
        <button id="modePlace" class="btn primary">📍 Поставить</button>
        <button id="modePan" class="btn">✋ Пан</button>
        <button id="resetView" class="btn">↺ Сброс вида</button>
      </div>

      <div class="row">
        <button id="clearNode" class="btn danger">🗑 Очистить узел</button>
      </div>

      <div class="row">
        <button id="copy" class="btn">📋 Copy JSON</button>
        <button id="download" class="btn">⬇️ Download JSON</button>
      </div>

      <label>Mapping JSON</label>
      <textarea id="json" rows="16" spellcheck="false"></textarea>

      <div class="row">
        <button id="loadJson" class="btn">⭮ Загрузить из поля</button>
      </div>
    </div>

    <div class="right">
      <div id="svgHost">__SVG_INLINE__</div>
      <div class="hud">
        режим: <b id="mode">place</b> ·
        node: <b id="nodeName"></b> ·
        xy: <b id="xy">—</b>
      </div>
    </div>
  </div>

<script>
const DATA = __JS_DATA__;
document.getElementById('title').textContent = DATA.title || 'SVG node mapping';
const nodeSel = document.getElementById('nodeSel');
const modeEl = document.getElementById('mode');
const nodeNameEl = document.getElementById('nodeName');
const xyEl = document.getElementById('xy');
const jsonEl = document.getElementById('json');

const NODE_NAMES = DATA.nodeNames || [];
NODE_NAMES.forEach(n => {
  const opt = document.createElement('option');
  opt.value = n; opt.textContent = n;
  nodeSel.appendChild(opt);
});

// SVG
const svgHost = document.getElementById('svgHost');
svgHost.innerHTML = DATA.svg || '';
const svg = svgHost.querySelector('svg');
if (!svg) {
  svgHost.innerHTML = '<div style="padding:12px;color:#c00">SVG не найден в HTML.</div>';
}

function parseViewBox(vbStr) {
  // NOTE: двойной backslash нужен, чтобы не ловить Python SyntaxWarning
  // "invalid escape sequence '\\s'" при генерации HTML из строки.
  const a = (vbStr || '').trim().split(/\\s+/).map(parseFloat);
  if (a.length !== 4 || a.some(x => Number.isNaN(x))) return null;
  return {x:a[0], y:a[1], w:a[2], h:a[3]};
}
const vb0 = parseViewBox(svg?.getAttribute('viewBox')) || {x:0, y:0, w:1920, h:1080};
let view = {...vb0};
function setViewBox(v) { svg.setAttribute('viewBox', `${v.x} ${v.y} ${v.w} ${v.h}`); }
function resetView() { view = {...vb0}; setViewBox(view); }

const NS = 'http://www.w3.org/2000/svg';
const overlay = document.createElementNS(NS, 'g');
overlay.setAttribute('id', 'pneumo_overlay_nodes');
svg.appendChild(overlay);

let mapping = { version: 2, viewBox: svg.getAttribute('viewBox') || `${vb0.x} ${vb0.y} ${vb0.w} ${vb0.h}`, edges: {}, nodes: {} };
const EDGE_NAMES = DATA.edgeNames || [];
EDGE_NAMES.forEach(n => { if (!(n in mapping.edges)) mapping.edges[n] = []; });
// В шаблоне держим все узлы (значение null, пока не задано)
NODE_NAMES.forEach(n => { if (!(n in mapping.nodes)) mapping.nodes[n] = null; });

let mode = 'place'; // place | pan
let selectedNode = NODE_NAMES[0] || '';
nodeNameEl.textContent = selectedNode;

let dragging = false;
let dragStart = null;

function getSvgPoint(clientX, clientY) {
  const pt = svg.createSVGPoint();
  pt.x = clientX; pt.y = clientY;
  const ctm = svg.getScreenCTM();
  if (!ctm) return {x:0,y:0};
  const sp = pt.matrixTransform(ctm.inverse());
  return {x: sp.x, y: sp.y};
}

function syncJson(pretty=true) {
  const s = JSON.stringify(mapping, null, pretty ? 2 : 0);
  jsonEl.value = s;
}

function rebuild() {
  while (overlay.firstChild) overlay.removeChild(overlay.firstChild);
  for (const [name, xy] of Object.entries(mapping.nodes || {})) {
    if (!xy || !Array.isArray(xy) || xy.length < 2) continue;
    const x = xy[0], y = xy[1];
    const c = document.createElementNS(NS, 'circle');
    c.setAttribute('cx', x);
    c.setAttribute('cy', y);
    c.setAttribute('r', 10);
    c.setAttribute('class', 'nodeDot');
    overlay.appendChild(c);

    const t = document.createElementNS(NS, 'text');
    t.setAttribute('x', x + 12);
    t.setAttribute('y', y - 12);
    t.setAttribute('class', 'nodeLabel');
    t.textContent = name;
    overlay.appendChild(t);
  }
  // HUD
  const xy = mapping.nodes?.[selectedNode];
  if (xy && Array.isArray(xy)) xyEl.textContent = `${xy[0].toFixed(1)}, ${xy[1].toFixed(1)}`;
  else xyEl.textContent = '—';
  syncJson(true);
}

function setMode(m) {
  mode = m;
  modeEl.textContent = mode;
  document.getElementById('modePlace').classList.toggle('primary', mode === 'place');
  document.getElementById('modePan').classList.toggle('primary', mode === 'pan');
}

nodeSel.addEventListener('change', () => {
  selectedNode = nodeSel.value;
  nodeNameEl.textContent = selectedNode;
  rebuild();
});

// buttons
document.getElementById('modePlace').addEventListener('click', () => setMode('place'));
document.getElementById('modePan').addEventListener('click', () => setMode('pan'));
document.getElementById('resetView').addEventListener('click', () => resetView());

document.getElementById('clearNode').addEventListener('click', () => {
  mapping.nodes[selectedNode] = null;
  rebuild();
});

document.getElementById('copy').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(jsonEl.value || ''); } catch(e) {}
});

document.getElementById('download').addEventListener('click', () => {
  const blob = new Blob([jsonEl.value || ''], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'pneumo_svg_mapping_nodes.json';
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById('loadJson').addEventListener('click', () => {
  try {
    const obj = JSON.parse(jsonEl.value || '{}');
    if (!obj || typeof obj !== 'object') return;
    if (!obj.nodes) obj.nodes = {};
    if (!obj.edges) obj.edges = {};
    EDGE_NAMES.forEach(n => { if (!obj.edges[n]) obj.edges[n] = []; });
    NODE_NAMES.forEach(n => { if (!(n in obj.nodes)) obj.nodes[n] = null; });
    mapping = obj;
    if (!mapping.viewBox) mapping.viewBox = svg.getAttribute('viewBox') || `${vb0.x} ${vb0.y} ${vb0.w} ${vb0.h}`;
    rebuild();
  } catch(e) {}
});

// zoom
svg.addEventListener('wheel', (e) => {
  e.preventDefault();
  const z = (e.deltaY < 0) ? 0.9 : 1.1;
  const p = getSvgPoint(e.clientX, e.clientY);
  const nx = p.x - (p.x - view.x) * z;
  const ny = p.y - (p.y - view.y) * z;
  view = { x: nx, y: ny, w: view.w * z, h: view.h * z };
  setViewBox(view);
}, {passive:false});

// pan
svg.addEventListener('pointerdown', (e) => {
  if (mode !== 'pan') return;
  dragging = true;
  svg.setPointerCapture(e.pointerId);
  dragStart = { p: getSvgPoint(e.clientX, e.clientY), v: {...view} };
});
svg.addEventListener('pointermove', (e) => {
  if (!dragging || mode !== 'pan') return;
  const p = getSvgPoint(e.clientX, e.clientY);
  const dx = p.x - dragStart.p.x;
  const dy = p.y - dragStart.p.y;
  view = { x: dragStart.v.x - dx, y: dragStart.v.y - dy, w: dragStart.v.w, h: dragStart.v.h };
  setViewBox(view);
});
svg.addEventListener('pointerup', (e) => {
  dragging = false;
  dragStart = null;
});

// place
svg.addEventListener('click', (e) => {
  if (mode !== 'place') return;
  const p = getSvgPoint(e.clientX, e.clientY);
  mapping.nodes[selectedNode] = [Number(p.x.toFixed(2)), Number(p.y.toFixed(2))];
  rebuild();
});

setMode('place');
resetView();
rebuild();

</script>
</body>
</html>"""

    html = html.replace("__SVG_INLINE__", svg_inline)
    html = html.replace("__JS_DATA__", js_data)
    components.html(html, height=height, scrolling=False)


def render_svg_flow_animation_html(
    svg_inline: str,
    mapping: Dict[str, Any],
    time_s: List[float],
    edge_series: List[Dict[str, Any]],
    node_series: List[Dict[str, Any]] | None = None,
    title: str = "Анимация по схеме (SVG)",
    height: int = 740,
):
    """Проигрывает потоки по “ручной” геометрии (mapping JSON) поверх SVG схемы.

    edge_series: [{name, q, open, unit}]
    node_series: [{name, p, unit}] (давление узлов, обычно в атм (изб.))
    mapping:
      version 1: {viewBox, edges}
      version 2: {viewBox, edges, nodes}

    Реализация:
    - координаты “точек” берём из mapping,
    - движение маркера по polyline делаем через SVGPathElement.getTotalLength()/getPointAtLength(),
    - пан/зум: управляем viewBox.
    """
    payload = {
        "title": title,
        "svg": svg_inline,
        "mapping": mapping,
        "time": time_s,
        "edges": edge_series,
        "nodes": (node_series or []),
    }
    js_data = json.dumps(payload, ensure_ascii=False)

    html = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\"/>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; }
    .wrap { display:flex; flex-direction:column; height:100%; min-height: 640px; }
    .hdr { display:flex; align-items:center; gap:10px; padding: 8px 10px; border-bottom: 1px solid #e6e6e6; flex-wrap: wrap; }
    .hdr h3 { margin:0; font-size:16px; }
    .btn { padding: 4px 10px; border: 1px solid #bbb; border-radius: 8px; background:#fff; cursor:pointer; font-size: 12px; }
    .btn.primary { border-color:#1f77b4; }
    input[type=range] { width: 320px; }
    .time { font-variant-numeric: tabular-nums; font-size: 12px; color:#333; }

    .main { flex: 1; display:flex; min-height: 520px; }
    .left { flex: 1; position: relative; overflow:hidden; background:#fafafa; }
    .right { width: 360px; border-left: 1px solid #e6e6e6; padding: 10px; box-sizing:border-box; overflow:auto; }

    #svgHost svg { width:100%; height:100%; display:block; background:white; user-select:none; }

    /* flow paths */
    .edgePath { fill:none; stroke-linecap: round; stroke-linejoin: round; }
    .edgePath.pos { stroke: rgba(0,120,255,0.70); }
    .edgePath.neg { stroke: rgba(255,80,0,0.70); }
    .edgePath.closed { stroke: rgba(180,180,180,0.30); }

    .dot { }
    .dot.pos { fill: rgba(0,120,255,0.95); }
    .dot.neg { fill: rgba(255,80,0,0.95); }
    .dot.closed { fill: rgba(180,180,180,0.65); }

    /* node labels */
    .nodeDot { fill: rgba(0,0,0,0.55); stroke: rgba(255,255,255,0.90); stroke-width: 3; }
    .nodeText {
      font-size: 14px;
      fill: rgba(0,0,0,0.85);
      stroke: rgba(255,255,255,0.95);
      stroke-width: 3;
      paint-order: stroke;
      font-variant-numeric: tabular-nums;
    }

    .h4 { font-size: 12px; color:#222; margin: 10px 0 6px 0; text-transform: uppercase; letter-spacing: .04em; }

    .controls { display:flex; gap:10px; flex-wrap:wrap; padding-bottom: 8px; border-bottom: 1px solid #eee; }
    .controls label { font-size: 12px; color:#333; user-select:none; display:flex; gap:6px; align-items:center; }

    .legend { margin-top: 8px; border: 1px solid #eee; border-radius: 10px; padding: 8px; background: #fff; }
    .legendRow { display:flex; align-items:center; gap:8px; font-size: 12px; color:#333; }
    .swatch { width: 28px; height: 8px; border-radius: 999px; }
    .swatch.pos { background: rgba(0,120,255,0.80); }
    .swatch.neg { background: rgba(255,80,0,0.80); }
    .swatch.closed { background: rgba(180,180,180,0.45); }

    .row { display:flex; justify-content:space-between; gap:10px; border-bottom:1px dashed #eee; padding: 6px 0; }
    .row .name { font-size: 12px; width: 220px; word-break: break-word; }
    .row .val  { font-size: 12px; text-align:right; font-variant-numeric: tabular-nums; color:#333; }

    .hint { font-size: 11px; color:#666; line-height: 1.35; margin-top: 10px; }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"hdr\">
      <h3 id=\"title\"></h3>
      <button id=\"play\" class=\"btn primary\">▶︎</button>
      <button id=\"pause\" class=\"btn\">⏸</button>
      <span class=\"time\">t=<span id=\"t\">0.000</span> s</span>
      <input id=\"slider\" type=\"range\" min=\"0\" max=\"0\" value=\"0\" step=\"1\"/>
      <span class=\"time\">idx=<span id=\"idx\">0</span></span>
      <button id=\"resetView\" class=\"btn\">↺ Сброс вида</button>
    </div>

    <div class=\"main\">
      <div class=\"left\">
        <div id=\"svgHost\">__SVG_INLINE__</div>
      </div>
      <div class=\"right\">
        <div class=\"controls\">
          <label><input id=\"togPaths\" type=\"checkbox\" checked/>Пути</label>
          <label><input id=\"togDots\" type=\"checkbox\" checked/>Маркеры</label>
          <label><input id=\"togNodes\" type=\"checkbox\" checked/>Давление</label>
          <label><input id=\"togLegend\" type=\"checkbox\" checked/>Легенда</label>
        </div>

        <div id=\"legend\" class=\"legend\">
          <div class=\"legendRow\"><span class=\"swatch pos\"></span><span>Q ≥ 0 (направление как задано веткой)</span></div>
          <div class=\"legendRow\" style=\"margin-top:6px\"><span class=\"swatch neg\"></span><span>Q &lt; 0 (реверс потока)</span></div>
          <div class=\"legendRow\" style=\"margin-top:6px\"><span class=\"swatch closed\"></span><span>closed (элемент закрыт)</span></div>
        </div>

        <div class=\"h4\">Узлы</div>
        <div id=\"nodesList\"></div>

        <div class=\"h4\">Ветки</div>
        <div id=\"edgesList\"></div>

        <div class=\"hint\">
          Пан: перетащите мышью (всегда). Zoom: колёсико мыши.<br/>
          Толщина/яркость пути ~ |Q|, цвет ~ знак Q.
        </div>
      </div>
    </div>
  </div>

<script>
const DATA = __JS_DATA__;
document.getElementById('title').textContent = DATA.title || 'SVG flow';
const slider = document.getElementById('slider');
const tEl = document.getElementById('t');
const idxEl = document.getElementById('idx');

const edges = DATA.edges || [];
const nodes = DATA.nodes || [];
const mapping = DATA.mapping || {};
const time = DATA.time || [];
const n = time.length;
slider.max = Math.max(0, n-1);

const svgHost = document.getElementById('svgHost');
svgHost.innerHTML = DATA.svg || '';
const svg = svgHost.querySelector('svg');

function parseViewBox(vbStr) {
  // NOTE: двойной backslash нужен, чтобы не ловить Python SyntaxWarning
  // "invalid escape sequence '\\s'" при генерации HTML из строки.
  const a = (vbStr || '').trim().split(/\\s+/).map(parseFloat);
  if (a.length !== 4 || a.some(x => Number.isNaN(x))) return null;
  return {x:a[0], y:a[1], w:a[2], h:a[3]};
}
const vb0 = parseViewBox(mapping.viewBox) || parseViewBox(svg?.getAttribute('viewBox')) || {x:0, y:0, w:1920, h:1080};
let view = {...vb0};
function setViewBox(v) { svg.setAttribute('viewBox', `${v.x} ${v.y} ${v.w} ${v.h}`); }
function resetView() { view = {...vb0}; setViewBox(view); }
resetView();

const NS = "http://www.w3.org/2000/svg";
const overlay = document.createElementNS(NS, 'g');
overlay.setAttribute('id','pneumo_overlay_anim');
svg.appendChild(overlay);

const pathLayer = document.createElementNS(NS, 'g');
const dotLayer  = document.createElementNS(NS, 'g');
const nodeLayer = document.createElementNS(NS, 'g');
overlay.appendChild(pathLayer);
overlay.appendChild(dotLayer);
overlay.appendChild(nodeLayer);

function getSvgPoint(clientX, clientY) {
  const pt = svg.createSVGPoint();
  pt.x = clientX; pt.y = clientY;
  const ctm = svg.getScreenCTM();
  if (!ctm) return {x:0,y:0};
  const sp = pt.matrixTransform(ctm.inverse());
  return {x: sp.x, y: sp.y};
}

function polyToPath(points) {
  if (!points || points.length < 2) return '';
  const p0 = points[0];
  let d = `M ${p0[0]} ${p0[1]}`;
  for (let i=1;i<points.length;i++) {
    const p = points[i];
    d += ` L ${p[0]} ${p[1]}`;
  }
  return d;
}

function clamp(x,a,b){ return Math.max(a, Math.min(b,x)); }

// --- right panel lists
const edgesListEl = document.getElementById('edgesList');
const nodesListEl = document.getElementById('nodesList');

edges.forEach((e) => {
  const row = document.createElement('div');
  row.className = 'row';
  row.innerHTML = `<div class="name">${e.name}</div><div class="val"><span class="q">0</span> ${e.unit||''}</div>`;
  edgesListEl.appendChild(row);
  e._row = row;
});

nodes.forEach((nd) => {
  const row = document.createElement('div');
  row.className = 'row';
  row.innerHTML = `<div class="name">${nd.name}</div><div class="val"><span class="p">0</span> ${nd.unit||''}</div>`;
  nodesListEl.appendChild(row);
  nd._row = row;
});

// --- build paths/dots
const segs = []; // {edgeIdx, path, dot, len, phase}
const qMax = edges.map(e => {
  let m = 1e-9;
  (e.q || []).forEach(v => { m = Math.max(m, Math.abs(v)); });
  return m;
});

edges.forEach((e, ei) => {
  const polys = (mapping.edges && mapping.edges[e.name]) ? mapping.edges[e.name] : [];
  if (!polys || polys.length === 0) return;
  polys.forEach((poly) => {
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', polyToPath(poly));
    path.setAttribute('class','edgePath pos');
    path.setAttribute('stroke-width','4');
    pathLayer.appendChild(path);

    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('r','6');
    dot.setAttribute('class','dot pos');
    dotLayer.appendChild(dot);

    const len = path.getTotalLength();
    segs.push({ edgeIdx: ei, path, dot, len, phase: Math.random() });
  });
});

// --- nodes overlay
const nodeObjs = []; // {name, circle, text, pArr, unit}
(nodes || []).forEach((nd) => {
  const xy = (mapping.nodes && mapping.nodes[nd.name]) ? mapping.nodes[nd.name] : null;
  if (!xy || !Array.isArray(xy) || xy.length < 2) return;
  const x = xy[0], y = xy[1];

  const g = document.createElementNS(NS, 'g');
  const c = document.createElementNS(NS, 'circle');
  c.setAttribute('cx', x);
  c.setAttribute('cy', y);
  c.setAttribute('r', 10);
  c.setAttribute('class', 'nodeDot');
  g.appendChild(c);

  const t = document.createElementNS(NS, 'text');
  t.setAttribute('x', x + 12);
  t.setAttribute('y', y - 12);
  t.setAttribute('class', 'nodeText');
  t.textContent = '0.00';
  g.appendChild(t);

  const tt = document.createElementNS(NS, 'title');
  tt.textContent = nd.name;
  g.appendChild(tt);

  nodeLayer.appendChild(g);

  nodeObjs.push({name: nd.name, circle: c, text: t, pArr: nd.p || [], unit: nd.unit || ''});
});

// --- toggles
const togPaths = document.getElementById('togPaths');
const togDots  = document.getElementById('togDots');
const togNodes = document.getElementById('togNodes');
const togLegend = document.getElementById('togLegend');
const legendEl = document.getElementById('legend');

function applyToggles() {
  pathLayer.style.display = togPaths.checked ? 'block' : 'none';
  dotLayer.style.display  = togDots.checked ? 'block' : 'none';
  nodeLayer.style.display = (togNodes.checked && nodeObjs.length>0) ? 'block' : 'none';
  legendEl.style.display  = togLegend.checked ? 'block' : 'none';
  nodesListEl.style.display = (togNodes.checked && nodes.length>0) ? 'block' : 'none';
}
[togPaths, togDots, togNodes, togLegend].forEach(el => el.addEventListener('change', applyToggles));
applyToggles();

// --- interactions: zoom/pan
let idx = 0;
let playing = false;
let lastTs = performance.now();
let dragging = false;
let dragStart = null;

svg.addEventListener('wheel', (e) => {
  e.preventDefault();
  const z = (e.deltaY < 0) ? 0.9 : 1.1;
  const p = getSvgPoint(e.clientX, e.clientY);
  const nx = p.x - (p.x - view.x) * z;
  const ny = p.y - (p.y - view.y) * z;
  view = { x: nx, y: ny, w: view.w * z, h: view.h * z };
  setViewBox(view);
}, {passive:false});

svg.addEventListener('pointerdown', (e) => {
  dragging = true;
  svg.setPointerCapture(e.pointerId);
  dragStart = { p: getSvgPoint(e.clientX, e.clientY), v: {...view} };
});
svg.addEventListener('pointermove', (e) => {
  if (!dragging) return;
  const p = getSvgPoint(e.clientX, e.clientY);
  const dx = p.x - dragStart.p.x;
  const dy = p.y - dragStart.p.y;
  view = { x: dragStart.v.x - dx, y: dragStart.v.y - dy, w: dragStart.v.w, h: dragStart.v.h };
  setViewBox(view);
});
svg.addEventListener('pointerup', (e) => {
  dragging = false;
  dragStart = null;
});

// transport
slider.addEventListener('input', () => { idx = parseInt(slider.value||'0',10) || 0; });
document.getElementById('resetView').addEventListener('click', () => resetView());
document.getElementById('play').addEventListener('click', () => { playing = true; });
document.getElementById('pause').addEventListener('click', () => { playing = false; });

let lastRenderedIdx = -1;
let lastRenderedPlaying = null;

function renderFrame(dt) {
  idxEl.textContent = String(idx);
  tEl.textContent = (time[idx] ?? 0).toFixed(3);

  // edges numeric list
  edges.forEach((e) => {
    const qv = (e.q && e.q[idx] !== undefined) ? e.q[idx] : 0;
    const qEl = e._row?.querySelector('.q');
    if (qEl) qEl.textContent = Number(qv).toFixed(2);
  });

  // nodes numeric list
  nodes.forEach((nd) => {
    const pv = (nd.p && nd.p[idx] !== undefined) ? nd.p[idx] : 0;
    const pEl = nd._row?.querySelector('.p');
    if (pEl) pEl.textContent = Number(pv).toFixed(2);
  });

  // node overlay labels
  nodeObjs.forEach((nd) => {
    const pv = (nd.pArr && nd.pArr[idx] !== undefined) ? nd.pArr[idx] : 0;
    nd.text.textContent = Number(pv).toFixed(2);
  });

  // flow segments
  segs.forEach((s) => {
    const e = edges[s.edgeIdx];
    const qv = (e.q && e.q[idx] !== undefined) ? e.q[idx] : 0;
    const openArr = e.open || null;
    const isOpen = openArr ? !!openArr[idx] : true;

    const dir = (qv >= 0) ? 1 : -1;
    const mag = Math.abs(qv);
    const norm = clamp(mag / (qMax[s.edgeIdx] || 1e-9), 0, 1);

    // marker movement only while playing
    if (playing && dt > 0) {
      const speed = 0.15 + 1.8 * norm;
      s.phase = (s.phase + dir * speed * dt) % 1;
      if (s.phase < 0) s.phase += 1;
    }

    const pt = s.path.getPointAtLength(s.phase * s.len);
    s.dot.setAttribute('cx', pt.x);
    s.dot.setAttribute('cy', pt.y);

    // style
    const w = 2.0 + 6.0 * norm;
    s.path.setAttribute('stroke-width', w.toFixed(2));
    s.path.style.opacity = (0.15 + 0.85 * norm).toFixed(3);

    // direction classes
    if (dir >= 0) {
      s.path.classList.add('pos');
      s.path.classList.remove('neg');
      s.dot.classList.add('pos');
      s.dot.classList.remove('neg');
    } else {
      s.path.classList.add('neg');
      s.path.classList.remove('pos');
      s.dot.classList.add('neg');
      s.dot.classList.remove('pos');
    }

    if (!isOpen) {
      s.path.classList.add('closed');
      s.dot.classList.add('closed');
    } else {
      s.path.classList.remove('closed');
      s.dot.classList.remove('closed');
    }
  });

  lastRenderedIdx = idx;
  lastRenderedPlaying = playing;
}

function __frameInParentViewport(){
  try {
    const fe = window.frameElement;
    if (!fe || !fe.getBoundingClientRect) return true;
    const r = fe.getBoundingClientRect();
    const w = Number(r.width || Math.max(0, (r.right || 0) - (r.left || 0)) || 0);
    const h = Number(r.height || Math.max(0, (r.bottom || 0) - (r.top || 0)) || 0);
    if (w <= 2 || h <= 2) return false;
    if ((Number(fe.clientWidth || 0) <= 2) || (Number(fe.clientHeight || 0) <= 2)) return false;
    let hiddenByCss = false;
    try {
      const hostView = fe.ownerDocument && fe.ownerDocument.defaultView;
      const cs = (hostView && hostView.getComputedStyle) ? hostView.getComputedStyle(fe) : null;
      hiddenByCss = !!(cs && (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity || '1') === 0));
    } catch(_cssErr) {}
    if (hiddenByCss) return false;
    const hostWin = (window.top && window.top !== window) ? window.top : window;
    const vh = Number(hostWin.innerHeight || window.innerHeight || 0);
    const vw = Number(hostWin.innerWidth || window.innerWidth || 0);
    const margin = 64;
    return (r.bottom >= -margin) && (r.top <= vh + margin) && (r.right >= -margin) && (r.left <= vw + margin);
  } catch(_e) {
    return true;
  }
}
let __STEP_HANDLE = 0;
let __STEP_KIND = '';
function __clearScheduledStep(){
  try {
    if (!__STEP_HANDLE) return;
    if (__STEP_KIND === 'raf' && window.cancelAnimationFrame) window.cancelAnimationFrame(__STEP_HANDLE);
    else clearTimeout(__STEP_HANDLE);
  } catch(_e) {}
  __STEP_HANDLE = 0;
  __STEP_KIND = '';
}
function __scheduleStep(kind, delayMs){
  __clearScheduledStep();
  if (kind === 'raf') {
    __STEP_KIND = 'raf';
    __STEP_HANDLE = requestAnimationFrame(step);
  } else {
    __STEP_KIND = 'timeout';
    __STEP_HANDLE = setTimeout(step, Math.max(0, Number(delayMs) || 0));
  }
}
function __wakeStep(forceRender){
  if (forceRender) {
    lastRenderedIdx = -1;
    lastRenderedPlaying = null;
  }
  if (!document.hidden && __frameInParentViewport()) __scheduleStep('raf', 0);
  else { __clearScheduledStep(); }
}

function step(ts) {
  const dt = Math.max(0, (ts - lastTs) / 1000.0);
  lastTs = ts;

  if (playing && n > 0) {
    idx = idx + Math.max(1, Math.floor(dt * 60));
    if (idx >= n) idx = 0;
    slider.value = String(idx);
  }

  const shouldRender = playing || (idx !== lastRenderedIdx) || (lastRenderedPlaying !== playing);
  if (shouldRender) renderFrame(dt);

  if (playing && !document.hidden && __frameInParentViewport()) __scheduleStep('raf', 0);
  else __clearScheduledStep();
}

window.addEventListener('focus', () => { try { __wakeStep(true); } catch(_e) {} });
document.addEventListener('visibilitychange', () => { if (!document.hidden) __wakeStep(true); });
window.addEventListener('scroll', () => { try { __wakeStep(true); } catch(_e) {} }, {passive:true});
window.addEventListener('resize', () => { try { __wakeStep(true); } catch(_e) {} }, {passive:true});
__wakeStep(true);
</script>
</body>
</html>"""

    html = html.replace("__SVG_INLINE__", svg_inline)
    html = html.replace("__JS_DATA__", js_data)

    components.html(html, height=height, scrolling=False)
