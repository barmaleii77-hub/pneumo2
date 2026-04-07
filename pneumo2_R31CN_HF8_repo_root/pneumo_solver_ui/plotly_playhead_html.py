# -*- coding: utf-8 -*-
"""plotly_playhead_html.py

Клиентский (frontend) маркер playhead для Plotly-графиков в Streamlit.

Задача:
- Не делать лишние rerun в Streamlit при "Play".
- Синхронизировать вертикальный маркер (и, опционально, jump по клику) через localStorage,
  используя тот же storage_key/dataset_id, что и компонент playhead_ctrl.

Подход:
- Рендерим Plotly в iframe через st.components.v1.html().
- JS внутри iframe читает localStorage (storage_key) с частотой poll_ms
  и обновляет layout.shapes[0] (вертикальная линия) без участия Python.
- По клику на графике вычисляем ближайший idx по time[] и записываем его в localStorage.
  Компонент playhead_ctrl (R45+) умеет подхватывать внешние изменения из localStorage.

Ограничения:
- Для больших массивов график лучше предварительно децимировать на стороне Python
  (в compare_ui.py это уже сделано).
- Табличка "значения на playhead" в Python обновится только если включён send_hz>0
  или пользователь вручную перемотал (force event).

"""

from __future__ import annotations

import json
from typing import Any, Sequence, Optional

try:
    import plotly.graph_objects as go  # type: ignore
    from plotly.offline import get_plotlyjs  # type: ignore

    _HAS_PLOTLY = True
except Exception:
    go = None  # type: ignore
    get_plotlyjs = None  # type: ignore
    _HAS_PLOTLY = False


def _ensure_playhead_shape(fig: Any, *, x0: float = 0.0) -> Any:
    """Ensure fig.layout.shapes has at least one vertical line shape (playhead)."""
    try:
        # make sure user zoom is preserved when we only relayout shapes
        try:
            fig.update_layout(uirevision="playhead")
        except Exception:
            pass

        # existing shapes?
        shapes = None
        try:
            shapes = list(fig.layout.shapes) if getattr(fig.layout, "shapes", None) is not None else []
        except Exception:
            shapes = []
        if shapes:
            return fig

        line = dict(
            type="line",
            xref="x",
            yref="paper",
            x0=float(x0),
            x1=float(x0),
            y0=0.0,
            y1=1.0,
            line=dict(width=1, dash="dot"),
            layer="above",
        )
        try:
            fig.update_layout(shapes=[line])
        except Exception:
            pass
    except Exception:
        pass
    return fig


def render_plotly_playhead_html(
    *,
    st,
    fig: Any,
    dataset_id: str,
    storage_key: str,
    time: Sequence[float],
    height: int = 520,
    key: str = "plotly_playhead",
    poll_ms: int = 50,
    allow_click_jump: bool = True,
    show_info: bool = False,
) -> None:
    """Render Plotly fig in Streamlit with a client-side playhead marker.

    Parameters
    ----------
    st:
        streamlit module (passed explicitly).
    fig:
        plotly.graph_objects.Figure
    dataset_id, storage_key:
        Must match playhead_ctrl args for the same timeline.
    time:
        Full reference time array (len must be >=1). Used to map idx->t and click->idx.
    height:
        iframe height
    key:
        stable id to avoid collisions in a page
    poll_ms:
        polling interval for localStorage (ms)
    allow_click_jump:
        if True: click on plot sets playhead idx (writes to localStorage)
    show_info:
        if True: show small caption above plot (debug)
    """
    if not _HAS_PLOTLY:
        st.warning("Plotly не установлен — HTML playhead недоступен.")
        return

    try:
        import streamlit.components.v1 as components  # type: ignore
    except Exception:
        st.warning("streamlit.components недоступен — HTML playhead недоступен.")
        return

    time_list = [float(x) for x in list(time)[:]]  # copy
    if len(time_list) == 0:
        st.info("Нет time[] для playhead.")
        return

    fig = _ensure_playhead_shape(fig, x0=float(time_list[0]))

    try:
        fig_dict = fig.to_plotly_json()
    except Exception:
        # last resort
        fig_dict = {"data": [], "layout": {}}

    plotlyjs = ""
    try:
        plotlyjs = get_plotlyjs()
    except Exception:
        plotlyjs = ""

    div_id = f"pl_{key}"

    if show_info:
        st.caption(f"HTML playhead: dataset_id={dataset_id}, storage_key={storage_key}, poll_ms={poll_ms}")

    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
  html, body {{
    margin: 0;
    padding: 0;
    height: 100%;
    overflow: hidden;
    font-family: sans-serif;
  }}
  #{div_id} {{
    width: 100%;
    height: 100%;
  }}
</style>
<script>
{plotlyjs}
</script>
</head>
<body>
<div id="{div_id}"></div>
<script>
(function() {{
  const DIV_ID = "{div_id}";
  const STORAGE_KEY = {json.dumps(str(storage_key))};
  const DATASET_ID = {json.dumps(str(dataset_id))};
  const TIME = {json.dumps(time_list)};
  const POLL_MS = {int(poll_ms)};
  const ALLOW_CLICK = {str(bool(allow_click_jump)).lower()};

  const fig = {json.dumps(fig_dict)};
  const gd = document.getElementById(DIV_ID);

  function clamp(v, a, b) {{ return Math.max(a, Math.min(b, v)); }}

  function nearestIndex(t) {{
    if (!Number.isFinite(t)) return 0;
    let lo = 0, hi = TIME.length - 1;
    while (hi - lo > 1) {{
      const mid = (lo + hi) >> 1;
      if (TIME[mid] <= t) lo = mid;
      else hi = mid;
    }}
    // pick closest of lo/hi
    const dlo = Math.abs(TIME[lo] - t);
    const dhi = Math.abs(TIME[hi] - t);
    return (dhi < dlo) ? hi : lo;
  }}

  function readState() {{
    try {{
      const s = localStorage.getItem(STORAGE_KEY);
      if (!s) return null;
      const obj = JSON.parse(s);
      if (!obj || typeof obj !== 'object') return null;
      if (String(obj.dataset_id || '') !== String(DATASET_ID || '')) return null;
      return obj;
    }} catch (e) {{
      return null;
    }}
  }}

  function writeState(newIdx, setPlaying) {{
    try {{
      let obj = null;
      try {{
        const s = localStorage.getItem(STORAGE_KEY);
        if (s) obj = JSON.parse(s);
      }} catch(e) {{
        obj = null;
      }}
      if (!obj || typeof obj !== 'object') obj = {{}};
      obj.dataset_id = String(DATASET_ID || '');
      obj.idx = Number(newIdx || 0);
      if (setPlaying !== null && setPlaying !== undefined) obj.playing = !!setPlaying;
      if (obj.speed === undefined) obj.speed = 1.0;
      if (obj.loop === undefined) obj.loop = true;
      obj.ts = Date.now();
      localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
    }} catch(e) {{
      return;
    }}
  }}

  // Ensure we have a playhead shape.
  function ensureShape(t) {{
    const lay = gd.layout || {{}};
    const shapes = (lay.shapes && Array.isArray(lay.shapes)) ? lay.shapes : [];
    if (shapes.length > 0) return;
    const line = {{
      type: 'line',
      xref: 'x',
      yref: 'paper',
      x0: t, x1: t,
      y0: 0, y1: 1,
      line: {{width: 1, dash: 'dot'}},
      layer: 'above'
    }};
    Plotly.relayout(gd, {{'shapes': [line]}});
  }}

  let lastIdx = null;
  function updatePlayhead() {{
    const obj = readState();
    if (!obj) return;
    const idx = clamp(Math.round(Number(obj.idx || 0)), 0, TIME.length - 1);
    if (lastIdx !== null && idx === lastIdx) return;
    lastIdx = idx;
    const t = TIME[idx];
    ensureShape(t);
    try {{
      // Update all shapes if there are multiple (e.g. for multiple xaxes)
      const n = (gd.layout && gd.layout.shapes && Array.isArray(gd.layout.shapes)) ? gd.layout.shapes.length : 1;
      const upd = {{}};
      for (let i = 0; i < n; i++) {{
        upd[`shapes[${{i}}].x0`] = t;
        upd[`shapes[${{i}}].x1`] = t;
      }}
      Plotly.relayout(gd, upd);
    }} catch(e) {{}}
  }}

  Plotly.newPlot(gd, fig.data || [], fig.layout || {{}}, fig.config || {{responsive: true}})
    .then(() => {{
      // initial marker
      ensureShape(TIME[0]);
      updatePlayhead();

      if (ALLOW_CLICK) {{
        gd.on('plotly_click', (ev) => {{
          try {{
            if (!ev || !ev.points || !ev.points.length) return;
            const x = ev.points[0].x;
            const t = Number(x);
            if (!Number.isFinite(t)) return;
            const idx = nearestIndex(t);
            writeState(idx, false);
            updatePlayhead();
          }} catch(e) {{}}
        }});
      }}
    }});

  let __phTimer = 0;
  function schedulePlayheadLoop() {{
    try {{ if (__phTimer) clearTimeout(__phTimer); }} catch(e) {{}}
    const obj = readState();
    const playing = !!(obj && obj.playing);
    const ms = playing ? Math.max(40, Number(POLL_MS || 120)) : (document.hidden ? 8000 : 1800);
    __phTimer = setTimeout(playheadLoop, ms);
  }}
  function playheadLoop() {{
    updatePlayhead();
    schedulePlayheadLoop();
  }}
  document.addEventListener('visibilitychange', () => {{ try {{ schedulePlayheadLoop(); }} catch(e) {{}} }});
  playheadLoop();
}})();
</script>
</body>
</html>
"""
    components.html(html, height=int(height), scrolling=False)
