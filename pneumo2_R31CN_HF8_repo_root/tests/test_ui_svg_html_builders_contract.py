from pathlib import Path

import pneumo_solver_ui.ui_svg_html_builders as svg_builders


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ENTRYPOINTS = [
    REPO_ROOT / "pneumo_solver_ui" / "app.py",
    REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py",
]


def test_svg_html_builders_emit_html_via_components(monkeypatch) -> None:
    calls = []

    def _capture(html: str, height: int, scrolling: bool):
        calls.append({"html": html, "height": height, "scrolling": scrolling})

    monkeypatch.setattr(svg_builders.components, "html", _capture)

    svg_builders.render_svg_edge_mapper_html("<svg></svg>", ["edge_A"], height=555, title="Edge map")
    svg_builders.render_svg_node_mapper_html("<svg></svg>", ["node_A"], ["edge_A"], height=556, title="Node map")
    svg_builders.render_svg_flow_animation_html(
        "<svg></svg>",
        {"version": 2, "edges": {}, "nodes": {}},
        [0.0, 1.0],
        [{"name": "edge_A", "q": [0.0, 1.0], "open": [1.0, 1.0], "unit": "m3/s"}],
        [{"name": "node_A", "p": [1.0, 1.1], "unit": "bar"}],
        title="Flow anim",
        height=557,
    )

    assert [c["height"] for c in calls] == [555, 556, 557]
    assert [c["scrolling"] for c in calls] == [False, False, False]
    assert '"edgeNames": ["edge_A"]' in calls[0]["html"]
    assert '"nodeNames": ["node_A"]' in calls[1]["html"]
    assert '"title": "Flow anim"' in calls[2]["html"]


def test_large_ui_entrypoints_import_shared_svg_html_builders() -> None:
    for path in UI_ENTRYPOINTS:
        src = path.read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_svg_html_builders import (" in src
        assert "def render_svg_edge_mapper_html(" not in src
        assert "def render_svg_node_mapper_html(" not in src
        assert "def render_svg_flow_animation_html(" not in src
