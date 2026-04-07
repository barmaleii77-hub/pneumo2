from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_flow_panel_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


def test_render_flow_panel_html_renders_payload_via_components_html(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_html(html: str, *, height: int, scrolling: bool) -> None:
        calls.append({"html": html, "height": height, "scrolling": scrolling})

    monkeypatch.setattr(ui_flow_panel_helpers.components, "html", fake_html)

    ui_flow_panel_helpers.render_flow_panel_html(
        time_s=[0.0, 0.5, 1.0],
        edge_series=[{"name": "Edge A", "q": [0.0, 1.2, -0.5], "open": [1, 1, 0], "unit": "kg/s"}],
        title="Flow Test",
        height=640,
    )

    assert len(calls) == 1
    assert calls[0]["height"] == 640
    assert calls[0]["scrolling"] is True
    html = str(calls[0]["html"])
    assert "__JS_DATA__" not in html
    assert '"title": "Flow Test"' in html
    assert '"name": "Edge A"' in html
    assert '"unit": "kg/s"' in html
    assert "requestAnimationFrame(step)" in html
    assert "real-time" in html


def test_entrypoints_use_shared_flow_panel_helper_without_local_duplicates() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_flow_panel_helpers import render_flow_panel_html" in app_text
    assert "from pneumo_solver_ui.ui_flow_panel_helpers import render_flow_panel_html" in heavy_text
    assert "def render_flow_panel_html(" not in app_text
    assert "def render_flow_panel_html(" not in heavy_text
    assert "components.html(html, height=height, scrolling=True)" not in app_text
    assert "components.html(html, height=height, scrolling=True)" not in heavy_text
    assert "import streamlit.components.v1 as components" not in app_text
    assert "import streamlit.components.v1 as components" not in heavy_text
