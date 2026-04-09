from __future__ import annotations

import json
from typing import Any, Dict, List

import streamlit.components.v1 as components


def render_flow_panel_html(
    time_s: List[float],
    edge_series: List[Dict[str, Any]],
    title: str = "Анимация потоков (MVP)",
    height: int = 520,
) -> None:
    """Рендерит HTML (SVG) панель анимации потоков."""
    payload = {
        "title": title,
        "time": time_s,
        "edges": edge_series,
    }
    js_data = json.dumps(payload, ensure_ascii=False)

    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; }
    .wrap { padding: 8px 10px; }
    .hdr { display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
    .hdr h3 { margin: 0; font-size: 16px; }
    .btn { padding: 4px 10px; border: 1px solid #bbb; border-radius: 6px; background: #fff; cursor: pointer; }
    .btn:active { transform: translateY(1px); }
    .row { display:flex; align-items:center; gap:10px; margin: 6px 0; }
    .name { width: 380px; font-size: 12px; line-height: 1.1; }
    .val { width: 120px; font-size: 12px; text-align:right; font-variant-numeric: tabular-nums; }
    .svg { flex: 1; height: 18px; }
    .line { stroke: #888; stroke-width: 3; stroke-linecap: round; }
    .line.closed { stroke: #ccc; }
    .dot { fill: #1f77b4; }
    .dot.closed { fill: #bbb; }
    .time { font-variant-numeric: tabular-nums; }
    input[type=range] { width: 320px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hdr">
      <h3 id="title"></h3>
      <button id="play" class="btn">▶︎</button>
      <button id="pause" class="btn">⏸</button>
      <span class="time">t=<span id="t">0.000</span> s</span>
      <input id="slider" type="range" min="0" max="0" value="0" step="1"/>
      <span class="time">idx=<span id="idx">0</span></span>
    </div>
    <div id="rows"></div>
  </div>
  <script>
    const DATA = __JS_DATA__;
    const titleEl = document.getElementById('title');
    const rowsEl = document.getElementById('rows');
    const tEl = document.getElementById('t');
    const idxEl = document.getElementById('idx');
    const slider = document.getElementById('slider');

    titleEl.textContent = DATA.title || 'Flow';

    const T = DATA.time || [];
    const edges = DATA.edges || [];
    const n = T.length;
    slider.max = Math.max(0, n-1);

    // построение строк
    const state = edges.map((e, i) => ({ phase: Math.random(), qmax: 1e-9 }));
    edges.forEach((e, i) => {
      const q = e.q || [];
      let qmax = 1e-9;
      for (let k=0; k<q.length; k++) qmax = Math.max(qmax, Math.abs(q[k]));
      state[i].qmax = qmax;

      const row = document.createElement('div');
      row.className = 'row';

      const name = document.createElement('div');
      name.className = 'name';
      name.textContent = e.name;

      const val = document.createElement('div');
      val.className = 'val';
      val.innerHTML = '<span class="q">0</span> ' + (e.unit || '');

      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('class', 'svg');
      svg.setAttribute('viewBox', '0 0 500 18');

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', '10');
      line.setAttribute('y1', '9');
      line.setAttribute('x2', '490');
      line.setAttribute('y2', '9');
      line.setAttribute('class', 'line');
      svg.appendChild(line);

      const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('r', '5');
      dot.setAttribute('cy', '9');
      dot.setAttribute('cx', '10');
      dot.setAttribute('class', 'dot');
      svg.appendChild(dot);

      row.appendChild(name);
      row.appendChild(svg);
      row.appendChild(val);
      rowsEl.appendChild(row);

      e._dom = {row, line, dot, val};
    });

    function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }

    let idx = 0;
    let playing = false;
    let lastTs = performance.now();
    let lastRenderedIdx = -1;
    let lastRenderedPlaying = null;
    const speedTime = 1.0; // множитель скорости времени (1.0 = real-time)
    const speedDots = 1.5; // скорость «бегущих точек»

    function renderFrame(dt) {
      idxEl.textContent = String(idx);
      tEl.textContent = (T[idx] ?? 0).toFixed(3);

      // обновление каждой ветки
      edges.forEach((e, i) => {
        const q = e.q || [];
        const open = e.open || null;
        const qv = (q[idx] ?? 0);
        const s = state[i];
        const dir = (qv >= 0) ? 1 : -1;
        const mag = Math.abs(qv);
        const norm = clamp(mag / (s.qmax || 1e-9), 0, 1);

        // фазу маркера крутим только при реальном проигрывании
        if (playing && dt > 0) {
          s.phase = (s.phase + dir * speedDots * norm * dt) % 1;
          if (s.phase < 0) s.phase += 1;
        }
        const x = 10 + s.phase * (490 - 10);
        e._dom.dot.setAttribute('cx', x.toFixed(2));

        const isOpen = open ? !!open[idx] : true;
        e._dom.line.setAttribute('class', 'line' + (isOpen ? '' : ' closed'));
        e._dom.dot.setAttribute('class', 'dot' + (isOpen ? '' : ' closed'));

        const qEl = e._dom.val.querySelector('.q');
        if (qEl) qEl.textContent = (qv).toFixed(2);
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

      if (playing) {
        idx = idx + Math.max(1, Math.floor(speedTime * dt * 60));
        if (idx >= n) idx = 0;
        slider.value = String(idx);
      }

      const shouldRender = playing || (idx !== lastRenderedIdx) || (lastRenderedPlaying !== playing);
      if (shouldRender) renderFrame(dt);

      if (playing && !document.hidden && __frameInParentViewport()) __scheduleStep('raf', 0);
      else __clearScheduledStep();
    }

    slider.addEventListener('input', (ev) => {
      idx = parseInt(slider.value || '0', 10) || 0;
      __wakeStep(true);
    });
    document.getElementById('play').addEventListener('click', () => { playing = true; __wakeStep(true); });
    document.getElementById('pause').addEventListener('click', () => { playing = false; __wakeStep(true); });
    window.addEventListener('focus', () => { try { __wakeStep(true); } catch(_e) {} });
    document.addEventListener('visibilitychange', () => { if (!document.hidden) __wakeStep(true); });
window.addEventListener('scroll', () => { try { __wakeStep(true); } catch(_e) {} }, {passive:true});
window.addEventListener('resize', () => { try { __wakeStep(true); } catch(_e) {} }, {passive:true});

    __wakeStep(true);
  </script>
</body>
 </html>"""

    html = html.replace("__JS_DATA__", js_data)
    components.html(html, height=height, scrolling=True)


__all__ = ["render_flow_panel_html"]
