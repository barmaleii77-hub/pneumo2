from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui import ui_svg_autotrace_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self, *, button_values=None) -> None:
        self.button_values = dict(button_values or {})
        self.session_state: dict[str, object] = {}
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.successes: list[str] = []
        self.warnings: list[str] = []
        self.captions: list[str] = []
        self.downloads: list[dict[str, object]] = []
        self.dataframes: list[tuple[object, int]] = []
        self.writes: list[object] = []

    def expander(self, label, *, expanded=False):
        return _Context()

    def columns(self, spec):
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(_Context() for _ in range(count))

    def error(self, text):
        self.errors.append(text)

    def info(self, text):
        self.infos.append(text)

    def success(self, text):
        self.successes.append(text)

    def warning(self, text):
        self.warnings.append(text)

    def caption(self, text):
        self.captions.append(text)

    def write(self, value):
        self.writes.append(value)

    def slider(self, label, min_value, max_value, value, *, step, key):
        return value

    def checkbox(self, label, *, value, key):
        return value

    def multiselect(self, label, *, options, default, key):
        return list(default)

    def button(self, label, *, key):
        return bool(self.button_values.get(key, False))

    def download_button(self, label, *, data, file_name, mime):
        self.downloads.append(
            {
                "label": label,
                "data": data,
                "file_name": file_name,
                "mime": mime,
            }
        )


def test_svg_autotrace_panel_handles_missing_module() -> None:
    fake_st = _FakeStreamlit()

    result = ui_svg_autotrace_helpers.render_svg_autotrace_panel(
        fake_st,
        svg_inline="<svg />",
        edge_columns=["edge_a"],
        selected_node_names=[],
        node_columns=[],
        has_svg_autotrace=False,
        extract_polylines_fn=lambda *args, **kwargs: None,
        auto_build_mapping_from_svg_fn=lambda *args, **kwargs: None,
        detect_component_bboxes_fn=lambda *args, **kwargs: [],
        safe_dataframe_fn=lambda df, height: None,
    )

    assert result == {"status": "missing"}
    assert fake_st.errors == [
        "pneumo_solver_ui.svg_autotrace не импортируется. Проверьте целостность пакета pneumo_solver_ui."
    ]


def test_svg_autotrace_panel_updates_state_and_renders_artifacts() -> None:
    fake_st = _FakeStreamlit(
        button_values={
            "btn_svg_autotrace_analyze": True,
            "btn_svg_autotrace_build": True,
            "btn_svg_find_components": True,
        }
    )
    dataframe_calls: list[tuple[object, int]] = []

    def _safe_dataframe(df, *, height):
        dataframe_calls.append((df, height))

    def _extract(svg_text, *, tol_merge):
        assert svg_text == "<svg />"
        assert tol_merge == 2.1
        return {
            "viewBox": "0 0 100 50",
            "nodes": [{"id": 1}],
            "edges": [{"id": 2}],
            "polylines": [{"id": 3}],
            "degree_counts": {"2": 1},
            "junction_nodes": [{"id": 4}],
            "poly_endpoints": [{"id": 5}],
            "texts": [{"text": "Ресивер1", "x": 10, "y": 20, "klass": "node"}],
        }

    def _build(**kwargs):
        assert kwargs["edge_names"] == ["edge_a"]
        assert kwargs["node_names"] == ["node_a"]
        return (
            {"edges": {"edge_a": []}, "nodes": {"node_a": None}},
            {
                "summary": {"ok": 1},
                "edges": [{"name": "edge_a", "score": 0.9, "dist": 5.0}],
                "nodes": [{"name": "node_a", "score": 0.8, "dist_label_poly": 3.0}],
                "unmatched_nodes": ["node_b"],
                "unmatched_edges": ["edge_b"],
            },
        )

    def _components(svg_text, *, radius):
        assert svg_text == "<svg />"
        assert radius == 120.0
        return [{"name": "comp_a"}]

    result = ui_svg_autotrace_helpers.render_svg_autotrace_panel(
        fake_st,
        svg_inline="<svg />",
        edge_columns=["edge_a"],
        selected_node_names=["node_a"],
        node_columns=["node_a", "node_b"],
        has_svg_autotrace=True,
        extract_polylines_fn=_extract,
        auto_build_mapping_from_svg_fn=_build,
        detect_component_bboxes_fn=_components,
        safe_dataframe_fn=_safe_dataframe,
    )

    assert result == {
        "status": "ok",
        "has_analysis": True,
        "has_report": True,
        "components_count": 1,
    }
    assert "svg_autotrace_analysis" in fake_st.session_state
    assert "svg_autotrace_report" in fake_st.session_state
    assert fake_st.session_state["svg_autotrace_components"] == [{"name": "comp_a"}]
    assert json.loads(fake_st.session_state["svg_mapping_text"]) == {
        "edges": {"edge_a": []},
        "nodes": {"node_a": None},
    }
    assert len(dataframe_calls) == 4
    assert [item["file_name"] for item in fake_st.downloads] == [
        "svg_analysis.json",
        "svg_autotrace_report.json",
        "svg_components.json",
    ]
    assert any("SVG разобран" in text for text in fake_st.successes)
    assert any("mapping обновлён" in text for text in fake_st.successes)
    assert any("Найдено компонентов" in text for text in fake_st.successes)
    assert fake_st.warnings == [
        "Не сопоставлены 1 узлов.",
        "Не сопоставлены 1 веток.",
    ]


def test_svg_autotrace_panel_clear_button_resets_session_state() -> None:
    fake_st = _FakeStreamlit(button_values={"btn_svg_autotrace_clear": True})
    fake_st.session_state.update(
        {
            "svg_autotrace_analysis": {"a": 1},
            "svg_autotrace_report": {"b": 2},
            "svg_autotrace_components": [{"c": 3}],
        }
    )

    result = ui_svg_autotrace_helpers.render_svg_autotrace_panel(
        fake_st,
        svg_inline="<svg />",
        edge_columns=[],
        selected_node_names=[],
        node_columns=[],
        has_svg_autotrace=True,
        extract_polylines_fn=lambda *args, **kwargs: {},
        auto_build_mapping_from_svg_fn=lambda **kwargs: ({}, {}),
        detect_component_bboxes_fn=lambda *args, **kwargs: [],
        safe_dataframe_fn=lambda df, height: None,
    )

    assert result == {
        "status": "ok",
        "has_analysis": False,
        "has_report": False,
        "components_count": 0,
    }
    for key in ui_svg_autotrace_helpers.AUTOTRACE_SESSION_KEYS:
        assert key not in fake_st.session_state
    assert fake_st.successes == ["Очищено."]


def test_entrypoints_use_shared_svg_autotrace_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in heavy_text
    assert "render_svg_scheme_section(" in app_text
    assert "render_svg_scheme_section(" in heavy_text
    assert "render_svg_autotrace_panel(" not in app_text
    assert "render_svg_autotrace_panel(" not in heavy_text
    assert "if False:  # legacy svg autotrace block kept for incremental cleanup" not in app_text
    assert "if False:  # legacy svg autotrace block kept for incremental cleanup" not in heavy_text
    assert 'do_analyze = st.button("Проанализировать SVG", key="btn_svg_autotrace_analyze")' not in app_text
    assert 'do_analyze = st.button("Проанализировать SVG", key="btn_svg_autotrace_analyze")' not in heavy_text
    assert 'mapping_auto, report_auto = auto_build_mapping_from_svg(' not in app_text
    assert 'mapping_auto, report_auto = auto_build_mapping_from_svg(' not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_autotrace_helpers import (" in section_text
    assert "render_svg_autotrace_panel(" in section_text
