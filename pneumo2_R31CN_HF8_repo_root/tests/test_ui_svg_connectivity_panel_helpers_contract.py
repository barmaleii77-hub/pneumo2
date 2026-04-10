from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_svg_connectivity_panel_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_connectivity_panel_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"


class _FakeExpander:
    def __enter__(self) -> "_FakeExpander":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeStreamlit:
    def __init__(self, text_input_return: str = "") -> None:
        self.expanders: list[tuple[str, bool]] = []
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.text_inputs: list[tuple[str, str, str | None]] = []
        self._text_input_return = text_input_return

    def expander(self, label: str, expanded: bool = False) -> _FakeExpander:
        self.expanders.append((label, expanded))
        return _FakeExpander()

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def text_input(self, label: str, value: str = "", key: str | None = None) -> str:
        self.text_inputs.append((label, value, key))
        return self._text_input_return


def test_render_svg_connectivity_panel_warns_without_analysis() -> None:
    fake_st = _FakeStreamlit()
    session_state: dict[str, object] = {}

    ui_svg_connectivity_panel_helpers.render_svg_connectivity_panel(
        fake_st,
        session_state,
        ["edge-a"],
        "0 0 100 100",
        name_score_fn=lambda *_args, **_kwargs: 0.0,
        shortest_path_fn=lambda *_args, **_kwargs: None,
        evaluate_quality_fn=lambda *_args, **_kwargs: None,
        safe_dataframe_fn=lambda *_args, **_kwargs: None,
    )

    assert fake_st.expanders == [("Путь по схеме (connectivity beta)", False)]
    assert any("Сначала нажмите **Проанализировать SVG**" in msg for msg in fake_st.warnings)


def test_render_svg_connectivity_panel_delegates_to_shared_subpanels(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    session_state: dict[str, object] = {
        "svg_autotrace_analysis": {
            "texts": [
                {"text": "Reservoir1", "x": 10, "y": 20},
                {"text": "ValveB", "x": 30, "y": 40},
            ]
        }
    }
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        ui_svg_connectivity_panel_helpers,
        "render_svg_route_guided_panel",
        lambda session_state, items, edge_options, **kwargs: calls.append(
            ("guided", (session_state, items, edge_options, kwargs))
        ),
    )
    monkeypatch.setattr(
        ui_svg_connectivity_panel_helpers,
        "render_svg_route_auto_panel",
        lambda session_state, items, texts, analysis, edge_options, **kwargs: calls.append(
            ("auto", (session_state, items, texts, analysis, edge_options, kwargs))
        ),
    )
    monkeypatch.setattr(
        ui_svg_connectivity_panel_helpers,
        "render_svg_route_search_panel",
        lambda session_state, items, opts, opt_to_idx, texts, analysis, edge_options, **kwargs: calls.append(
            (
                "search",
                (session_state, items, opts, opt_to_idx, texts, analysis, edge_options, kwargs),
            )
        ),
    )

    ui_svg_connectivity_panel_helpers.render_svg_connectivity_panel(
        fake_st,
        session_state,
        ["edge-a", "edge-b"],
        "0 0 320 240",
        name_score_fn=lambda *_args, **_kwargs: 1.0,
        shortest_path_fn=lambda *_args, **_kwargs: None,
        evaluate_quality_fn=lambda *_args, **_kwargs: None,
        safe_dataframe_fn=lambda *_args, **_kwargs: None,
    )

    assert [name for name, _payload in calls] == ["guided", "auto", "search"]
    guided_payload = calls[0][1]
    search_payload = calls[2][1]
    assert guided_payload[1] == [
        (0, "Reservoir1", 10.0, 20.0),
        (1, "ValveB", 30.0, 40.0),
    ]
    assert guided_payload[2] == ["edge-a", "edge-b"]
    assert search_payload[2] == [
        "#000 | Reservoir1 | (10,20)",
        "#001 | ValveB | (30,40)",
    ]
    assert search_payload[3] == {
        "#000 | Reservoir1 | (10,20)": 0,
        "#001 | ValveB | (30,40)": 1,
    }
    assert fake_st.text_inputs == [
        ("Фильтр меток (подстрока, регистр не важен)", "", "svg_route_filter")
    ]


def test_entrypoints_use_shared_svg_connectivity_panel_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import render_svg_scheme_section" in surface_text
    assert '"render_svg_scheme_section_fn": render_svg_scheme_section' in surface_text
    assert "render_svg_connectivity_panel(" not in app_text
    assert "render_svg_connectivity_panel(" not in heavy_text
    assert 'with st.expander("Путь по схеме (connectivity beta)", expanded=False):' not in app_text
    assert 'with st.expander("Путь по схеме (connectivity beta)", expanded=False):' not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_connectivity_panel_helpers import (" in section_text
    assert "render_svg_connectivity_panel(" in section_text
    assert "from pneumo_solver_ui.ui_svg_route_helpers import (" in helper_text
    assert "render_svg_route_guided_panel(" in helper_text
    assert "render_svg_route_auto_panel(" in helper_text
    assert "render_svg_route_search_panel(" in helper_text
    assert "build_svg_route_label_items(" in helper_text
    assert "build_svg_route_options(" in helper_text
