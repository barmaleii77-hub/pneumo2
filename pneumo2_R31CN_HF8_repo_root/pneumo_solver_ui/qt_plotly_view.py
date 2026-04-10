# -*- coding: utf-8 -*-
"""qt_plotly_view.py

Небольшой wrapper для показа Plotly фигур внутри Qt (PySide6) через QtWebEngine.

Зачем:
- Веб (Streamlit) уже использует Plotly для интерактивных графиков.
- Для паритета Web/GUI и "CAD‑подобного" UX в Windows удобно встраивать
  те же Plotly‑виджеты в отдельное Qt окно (Dock/Tab) без переписывания.

Особенности:
- Есть канал обратной связи "клик/выделение" из Plotly → Python,
  чтобы реализовать linked‑brushing (выделил точки → выделились прогоны).
- Если QtWebEngine недоступен (PySide6-Addons не установлен),
  виджет показывает понятную заглушку.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import json

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except Exception:  # pragma: no cover
    QtCore = None  # type: ignore
    QtGui = None  # type: ignore
    QtWidgets = None  # type: ignore

try:
    import plotly.graph_objects as go  # type: ignore
    import plotly.io as pio  # type: ignore
except Exception:  # pragma: no cover
    go = None  # type: ignore
    pio = None  # type: ignore

try:  # pragma: no cover - optional runtime dependency
    import kaleido  # type: ignore  # noqa: F401

    HAVE_KALEIDO = True
except Exception:  # pragma: no cover
    HAVE_KALEIDO = False


HAVE_QTWEBENGINE = False
QWebEngineView = None  # type: ignore
QWebChannel = None  # type: ignore

if QtCore is not None:
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView  # type: ignore
        from PySide6.QtWebChannel import QWebChannel  # type: ignore

        HAVE_QTWEBENGINE = True
    except Exception:
        HAVE_QTWEBENGINE = False


class _Bridge(QtCore.QObject):  # type: ignore[misc]
    """QObject exposed to JS (QtWebChannel)."""

    runsSelected = QtCore.Signal(list)  # type: ignore[attr-defined]

    @QtCore.Slot(str)  # type: ignore[attr-defined]
    def onSelected(self, payload: str) -> None:
        try:
            obj = json.loads(payload or "[]")
            if isinstance(obj, list):
                self.runsSelected.emit([str(x) for x in obj])
        except Exception:
            return


@dataclass
class PlotlyHtmlSpec:
    """Input spec for PlotlyWebView."""

    fig_json: Dict[str, Any]
    title: str = ""
    allow_select: bool = True
    plotly_js: str = "cdn"  # 'cdn' only for now


class PlotlyWebView(QtWidgets.QWidget):  # type: ignore[misc]
    """Qt widget that renders Plotly figure in a WebEngine view."""

    runsSelected = QtCore.Signal(list)  # type: ignore[attr-defined]

    def __init__(self, parent=None):
        super().__init__(parent)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._bridge = None
        self._view = None
        self._last_spec: Optional[PlotlyHtmlSpec] = None

        if not HAVE_QTWEBENGINE:
            msg = QtWidgets.QLabel(
                "Plotly‑view недоступен: QtWebEngine не установлен.\n\n"
                "Решение: установите PySide6 (полный пакет) или PySide6-Addons,\n"
                "затем перезапустите приложение.\n"
                "(В инженерной среде это нормально: это не 'экспертный режим',\n"
                "а зависимость для интерактивного 3D/linked‑brushing.)"
            )
            msg.setWordWrap(True)
            msg.setStyleSheet("QLabel{padding:10px;color:#333;background:#fff7d6;border:1px solid #e6d18b;border-radius:6px;}")
            lay.addWidget(msg)
            return

        self._view = QWebEngineView(self)  # type: ignore[call-arg]
        lay.addWidget(self._view, stretch=1)

        # WebChannel for JS -> Python
        try:
            self._bridge = _Bridge()
            self._bridge.runsSelected.connect(self.runsSelected.emit)
            ch = QWebChannel(self._view.page())  # type: ignore[call-arg]
            ch.registerObject("pyBridge", self._bridge)
            self._view.page().setWebChannel(ch)
        except Exception:
            # No channel => still render, just without linked brushing.
            self._bridge = None

    def set_figure(self, spec: PlotlyHtmlSpec) -> None:
        """Render plotly figure. Safe to call often."""

        self._last_spec = PlotlyHtmlSpec(
            fig_json=dict(spec.fig_json or {}),
            title=str(spec.title or ""),
            allow_select=bool(spec.allow_select),
            plotly_js=str(spec.plotly_js or "cdn"),
        )

        if not HAVE_QTWEBENGINE or self._view is None:
            return

        fig_json = spec.fig_json or {}

        # Make figure JSON safe for embedding
        try:
            fig_js = json.dumps(fig_json, ensure_ascii=False)
        except Exception:
            fig_js = "{}"

        title = str(spec.title or "")
        allow_select = bool(spec.allow_select)

        # NOTE: Plotly JS is loaded from CDN to avoid shipping heavy assets.
        plotly_src = "https://cdn.plot.ly/plotly-2.30.0.min.js"

        js_select = ""
        if allow_select and self._bridge is not None:
            js_select = r"""
function _extractRuns(ev){
  if(!ev || !ev.points) return [];
  const out = [];
  for(const p of ev.points){
    if(p && p.text){ out.push(String(p.text)); continue; }
    if(p && p.customdata){
      if(Array.isArray(p.customdata) && p.customdata.length>0){ out.push(String(p.customdata[0])); continue; }
      out.push(String(p.customdata));
    }
  }
  return Array.from(new Set(out)).filter(x=>x && x!=='undefined' && x!=='null');
}

function _sendRuns(runs){
  try{ pyBridge.onSelected(JSON.stringify(runs||[])); }catch(e){}
}

gd.on('plotly_selected', function(ev){ _sendRuns(_extractRuns(ev)); });
gd.on('plotly_click', function(ev){ _sendRuns(_extractRuns(ev)); });
"""

        # QWebChannel bootstrap (only if bridge exists)
        js_channel = ""
        if allow_select and self._bridge is not None:
            js_channel = r"""
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
  new QWebChannel(qt.webChannelTransport, function(channel) {
    window.pyBridge = channel.objects.pyBridge;
  });
</script>
"""

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <script src=\"{plotly_src}\"></script>
  <style>
    html, body {{ height: 100%; margin: 0; padding: 0; overflow: hidden; }}
    #plot {{ width: 100%; height: 100%; }}
  </style>
  {js_channel}
</head>
<body>
  <div id=\"plot\"></div>
  <script>
    const fig = {fig_js};
    const gd = document.getElementById('plot');
    const cfg = {{responsive: true, displaylogo: false}};
    try {{
      Plotly.newPlot(gd, fig.data || [], fig.layout || {{}}, cfg);
    }} catch(e) {{
      document.body.innerHTML = '<pre style="padding:10px">Plotly render error: '+e+'</pre>';
    }}
    {js_select}
  </script>
</body>
</html>"""

        try:
            self._view.setHtml(html)
        except Exception:
            return

    def render_static_qimage(self, *, width: int, height: int, scale: float = 1.0):
        """Best-effort static Plotly render for PNG export workflows."""

        if QtGui is None or go is None or pio is None or (not HAVE_KALEIDO):
            return None
        spec = self._last_spec
        if spec is None or not isinstance(spec.fig_json, dict) or not spec.fig_json:
            return None
        try:
            fig = go.Figure(spec.fig_json)
        except Exception:
            return None
        try:
            png_bytes = pio.to_image(
                fig,
                format="png",
                width=max(64, int(width)),
                height=max(64, int(height)),
                scale=max(1.0, float(scale)),
            )
        except Exception:
            return None
        image = QtGui.QImage()
        try:
            image.loadFromData(png_bytes, "PNG")
        except Exception:
            return None
        if image.isNull():
            return None
        return image
