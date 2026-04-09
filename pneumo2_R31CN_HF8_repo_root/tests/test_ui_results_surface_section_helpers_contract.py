from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_results_surface_section_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


class _FakeStreamlit:
    def info(self, text: str) -> None:
        pass

    def caption(self, text: str) -> None:
        pass

    def expander(self, *args, **kwargs):
        return object()

    def columns(self, count):
        return [object()] * int(count)

    def checkbox(self, *args, **kwargs) -> bool:
        return True


def test_render_app_results_surface_section_builds_app_specific_kwargs(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(helpers, "get_playhead_ctrl_component", lambda: "playhead-component")
    monkeypatch.setattr(
        helpers,
        "render_results_surface",
        lambda st, **kwargs: captured.update({"st": st, **kwargs}) or ("Графики", "ok"),
    )

    result = helpers.render_app_results_surface_section(
        _FakeStreamlit(),
        session_state={"demo": True},
        options=["Графики", "Анимация"],
        cur_hash="hash-1",
        test_pick="test-1",
        cache_key="cache-1",
        dataset_id="dataset-1",
        time_s=[0.0, 1.0],
        playhead_x=1.0,
        events_list=[{"severity": "warn"}],
        df_main="df_main",
        df_p="df_p",
        df_mdot="df_mdot",
        df_open="df_open",
        df_egroups="df_egroups",
        df_eedges="df_eedges",
        plot_lines_fn="plot-lines",
        plot_timeseries_fn="plot-timeseries",
        excel_bytes_fn="excel-bytes",
        safe_dataframe_fn="safe-df",
        p_atm=101325.0,
        pressure_from_pa_fn="atm-convert",
        pressure_divisor=101325.0,
        flow_scale_and_unit_fn="flow-scale",
        model_module="model-module",
        has_plotly=True,
        px_module="px-module",
        safe_plotly_chart_fn="plotly-chart",
        log_event_fn="log-event",
        base_override={"alpha": 1},
        tests_map={"test-1": {"name": "demo"}},
        compute_road_profile_fn="road-profile",
        proc_metrics_fn="proc-metrics",
        safe_image_fn="safe-image",
        base_dir=REPO_ROOT,
        mech_fallback_module="mech-fallback",
        default_svg_mapping_path="mapping.json",
        route_write_view_box="0 0 100 100",
        do_rerun_fn="do-rerun",
        render_svg_flow_animation_html_fn="svg-html",
        has_svg_autotrace=True,
        extract_polylines_fn="extract",
        auto_build_mapping_from_svg_fn="auto-map",
        detect_component_bboxes_fn="detect-boxes",
        name_score_fn="name-score",
        shortest_path_fn="shortest-path",
        evaluate_quality_fn="quality",
    )

    assert result == ("Графики", "ok")
    assert isinstance(captured["st"], _FakeStreamlit)
    assert captured["render_playhead_results_section_fn"] is helpers.render_playhead_results_section
    assert captured["render_results_section_fn"] is helpers.render_results_section
    playhead_kwargs = captured["playhead_results_section_kwargs"]
    assert isinstance(playhead_kwargs, dict)
    assert playhead_kwargs["playhead_component"] == "playhead-component"
    assert playhead_kwargs["pressure_unit"] == "атм (изб.)"
    assert playhead_kwargs["stroke_unit"] == "м"
    results_kwargs = captured["results_section_kwargs"]
    assert isinstance(results_kwargs, dict)
    assert results_kwargs["options"] == ["Графики", "Анимация"]
    assert results_kwargs["results_graph_section_kwargs"]["graph_studio_drop_all_nan"] is False
    assert (
        results_kwargs["secondary_results_views_kwargs"]["render_animation_section_fn"]
        is helpers.render_app_animation_results_section
    )


def test_render_heavy_results_surface_section_builds_heavy_specific_kwargs(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fallback() -> None:
        pass

    monkeypatch.setattr(helpers, "get_playhead_ctrl_component", lambda: "playhead-component")
    monkeypatch.setattr(
        helpers,
        "render_results_surface",
        lambda st, **kwargs: captured.update({"st": st, **kwargs}) or ("Анимация", "missing"),
    )

    result = helpers.render_heavy_results_surface_section(
        _FakeStreamlit(),
        session_state={"demo": True},
        cur_hash="hash-2",
        test_pick="test-2",
        cache_key="cache-2",
        dataset_id="dataset-2",
        time_s=[0.0, 1.0],
        playhead_idx=7,
        playhead_x=1.0,
        events_list=[{"severity": "error"}],
        df_main="df_main",
        df_p="df_p",
        df_mdot="df_mdot",
        df_open="df_open",
        df_egroups="df_egroups",
        df_eedges="df_eedges",
        plot_lines_fn="plot-lines",
        plot_timeseries_fn="plot-timeseries",
        excel_bytes_fn="excel-bytes",
        safe_dataframe_fn="safe-df",
        p_atm=101325.0,
        pressure_from_pa_fn="bar-convert",
        pressure_divisor=100000.0,
        flow_scale_and_unit_fn="flow-scale",
        model_module="model-module",
        has_plotly=True,
        px_module="px-module",
        safe_plotly_chart_fn="plotly-chart",
        log_event_fn="log-event",
        base_override={"beta": 2},
        tests_map={"test-2": {"name": "demo"}},
        compute_road_profile_fn="road-profile",
        proc_metrics_fn="proc-metrics",
        safe_image_fn="safe-image",
        base_dir=REPO_ROOT,
        ring_visual_base_dir=REPO_ROOT,
        mech_fallback_module="mech-fallback",
        get_float_param_fn="get-float",
        fallback_error="fallback-error",
        ring_visual_pick="pick",
        ring_visual_workspace_exports_dir=REPO_ROOT / "workspace",
        ring_visual_latest_export_paths_fn="latest-paths",
        default_svg_mapping_path="mapping.json",
        route_write_view_box="0 0 100 100",
        do_rerun_fn="do-rerun",
        render_svg_flow_animation_html_fn="svg-html",
        has_svg_autotrace=True,
        extract_polylines_fn="extract",
        auto_build_mapping_from_svg_fn="auto-map",
        detect_component_bboxes_fn="detect-boxes",
        name_score_fn="name-score",
        shortest_path_fn="shortest-path",
        evaluate_quality_fn="quality",
        missing_playhead_fallback_fn=_fallback,
    )

    assert result == ("Анимация", "missing")
    playhead_kwargs = captured["playhead_results_section_kwargs"]
    assert isinstance(playhead_kwargs, dict)
    assert playhead_kwargs["missing_component_fallback_fn"] is _fallback
    assert playhead_kwargs["pressure_unit"] == "бар (изб.)"
    assert playhead_kwargs["stroke_unit"] == "мм"
    results_kwargs = captured["results_section_kwargs"]
    assert isinstance(results_kwargs, dict)
    assert results_kwargs["options"] == ["Графики", "Потоки", "Энерго-аудит", "Анимация"]
    assert results_kwargs["results_graph_section_kwargs"]["graph_studio_drop_all_nan"] is True
    animation_kwargs = results_kwargs["secondary_results_views_kwargs"]["animation_section_kwargs"]
    assert animation_kwargs["playhead_idx"] == 7
    assert animation_kwargs["component_last_error_fn"] is helpers.component_last_error
    assert (
        results_kwargs["secondary_results_views_kwargs"]["render_animation_section_fn"]
        is helpers.render_heavy_animation_results_section
    )


def test_entrypoints_use_shared_results_surface_section_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_surface_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_results_surface_section_helpers import (" in heavy_text
    assert "render_app_results_surface_section(" in app_text
    assert "render_heavy_results_surface_section(" in heavy_text
    assert "render_results_surface(" not in app_text
    assert "render_results_surface(" not in heavy_text
    assert "render_results_section(" not in app_text
    assert "render_results_section(" not in heavy_text
    assert "render_results_graph_section(" not in app_text
    assert "render_results_graph_section(" not in heavy_text
    assert "render_secondary_results_views(" not in app_text
    assert "render_secondary_results_views(" not in heavy_text
    assert "render_playhead_results_section(" not in app_text
    assert "render_playhead_results_section(" not in heavy_text
    assert "def render_app_results_surface_section(" in helper_text
    assert "def render_heavy_results_surface_section(" in helper_text
    assert "render_results_surface(" in helper_text
