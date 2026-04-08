from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_svg_scheme_section_helpers as section_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
INPUT_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_input_helpers.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.captions: list[str] = []

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def caption(self, message: str) -> None:
        self.captions.append(message)


def test_render_svg_scheme_section_warns_without_df_mdot() -> None:
    fake_st = _FakeStreamlit()

    section_helpers.render_svg_scheme_section(
        fake_st,
        {},
        df_mdot=None,
        df_open="df_open",
        df_p="df_p",
        base_dir=Path("."),
        default_svg_mapping_path=Path("mapping.json"),
        route_write_view_box="0 0 100 100",
        do_rerun_fn=lambda: None,
        log_event_fn=lambda *args, **kwargs: None,
        p_atm=101325.0,
        model_module="model",
        pressure_divisor=101325.0,
        pressure_unit="atm",
        dataset_id="dataset-1",
        safe_dataframe_fn=lambda value: value,
        flow_scale_and_unit_fn=lambda *_args, **_kwargs: (1.0, "unit"),
        get_component_fn=lambda: None,
        render_svg_flow_animation_html_fn=lambda **_kwargs: "<div></div>",
        has_svg_autotrace=True,
        extract_polylines_fn=lambda *_args, **_kwargs: None,
        auto_build_mapping_from_svg_fn=lambda *_args, **_kwargs: None,
        detect_component_bboxes_fn=lambda *_args, **_kwargs: None,
        name_score_fn=lambda *_args, **_kwargs: 0.0,
        shortest_path_fn=lambda *_args, **_kwargs: None,
        evaluate_quality_fn=lambda *_args, **_kwargs: None,
    )

    assert fake_st.info_messages == [
        "Анимация по схеме (SVG) доступна только при record_full=True (df_mdot + mapping)."
    ]
    assert fake_st.captions == []


def test_render_svg_scheme_section_delegates_to_shared_subhelpers(monkeypatch, tmp_path) -> None:
    fake_st = _FakeStreamlit()
    session_state = {"svg_mapping_text": '{"edges":{}}'}
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        section_helpers,
        "render_svg_scheme_inputs",
        lambda st, **kwargs: calls.append(("inputs", kwargs))
        or {
            "edge_columns": ["edge-a", "edge-b"],
            "node_columns": ["node-a", "node-b"],
            "selected_node_names": ["node-b"],
            "svg_inline": "<svg/>",
        },
    )
    monkeypatch.setattr(
        section_helpers,
        "render_svg_autotrace_panel",
        lambda st, **kwargs: calls.append(("autotrace", kwargs)),
    )
    monkeypatch.setattr(
        section_helpers,
        "render_svg_connectivity_panel",
        lambda st, session_state, edge_columns, route_write_view_box, **kwargs: calls.append(
            ("connectivity", (session_state, edge_columns, route_write_view_box, kwargs))
        ),
    )
    monkeypatch.setattr(
        section_helpers,
        "render_svg_mapping_workbench_section",
        lambda st, session_state, **kwargs: calls.append(("workbench", (session_state, kwargs))),
    )

    section_helpers.render_svg_scheme_section(
        fake_st,
        session_state,
        df_mdot="df_mdot",
        df_open="df_open",
        df_p="df_p",
        base_dir=tmp_path,
        default_svg_mapping_path=tmp_path / "mapping.json",
        route_write_view_box="0 0 320 240",
        do_rerun_fn="rerun",
        log_event_fn="log",
        p_atm=101325.0,
        model_module="model",
        pressure_divisor=101325.0,
        pressure_unit="atm",
        dataset_id="dataset-1",
        safe_dataframe_fn="safe_df",
        flow_scale_and_unit_fn="flow_fn",
        get_component_fn="component_fn",
        render_svg_flow_animation_html_fn="html_fn",
        has_svg_autotrace=True,
        extract_polylines_fn="extract_fn",
        auto_build_mapping_from_svg_fn="auto_map_fn",
        detect_component_bboxes_fn="bbox_fn",
        name_score_fn="score_fn",
        shortest_path_fn="path_fn",
        evaluate_quality_fn="quality_fn",
    )

    assert [name for name, _payload in calls] == [
        "inputs",
        "autotrace",
        "connectivity",
        "workbench",
    ]
    assert fake_st.captions == []
    assert calls[0][1]["df_mdot"] == "df_mdot"
    assert calls[0][1]["df_p"] == "df_p"
    assert calls[1][1]["edge_columns"] == ["edge-a", "edge-b"]
    assert calls[1][1]["node_columns"] == ["node-a", "node-b"]
    assert calls[2][1][1] == ["edge-a", "edge-b"]
    assert calls[2][1][2] == "0 0 320 240"
    assert calls[3][1][1]["edge_columns"] == ["edge-a", "edge-b"]
    assert calls[3][1][1]["node_columns"] == ["node-a", "node-b"]
    assert calls[3][1][1]["selected_node_names"] == ["node-b"]


def test_entrypoints_use_shared_svg_scheme_section_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    input_text = INPUT_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in heavy_text
    assert "render_svg_scheme_section(" in app_text
    assert "render_svg_scheme_section(" in heavy_text
    assert "render_svg_click_mode_selector(" not in app_text
    assert "render_svg_click_mode_selector(" not in heavy_text
    assert "render_svg_autotrace_panel(" not in app_text
    assert "render_svg_autotrace_panel(" not in heavy_text
    assert "render_svg_connectivity_panel(" not in app_text
    assert "render_svg_connectivity_panel(" not in heavy_text
    assert "render_svg_mapping_workbench_section(" not in app_text
    assert "render_svg_mapping_workbench_section(" not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_scheme_input_helpers import (" in helper_text
    assert "render_svg_scheme_inputs(" in helper_text
    assert "from pneumo_solver_ui.ui_svg_autotrace_helpers import (" in helper_text
    assert "from pneumo_solver_ui.ui_svg_connectivity_panel_helpers import (" in helper_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in helper_text
    assert "from pneumo_solver_ui.ui_svg_flow_helpers import (" in input_text
