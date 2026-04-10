from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_animation_results_builders as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_animation_results_builders.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_animation_results_section_helpers.py"


def test_build_flow_animation_panel_kwargs_keeps_shared_runtime_contract() -> None:
    kwargs = helpers.build_flow_animation_panel_kwargs(
        df_mdot="df_mdot",
        df_open="df_open",
        p_atm=101325.0,
        model_module="model_mod",
        flow_scale_and_unit_fn="scale_fn",
        render_flow_panel_html_fn="html_fn",
    )

    assert kwargs == {
        "df_mdot": "df_mdot",
        "df_open": "df_open",
        "p_atm": 101325.0,
        "model_module": "model_mod",
        "flow_scale_and_unit_fn": "scale_fn",
        "render_flow_panel_html_fn": "html_fn",
    }


def test_build_svg_scheme_animation_surface_kwargs_wraps_args_and_kwargs() -> None:
    session_state = {"demo": True}

    surface = helpers.build_svg_scheme_animation_surface_kwargs(
        session_state,
        df_mdot="df_mdot",
        df_open="df_open",
        df_p="df_p",
        base_dir=Path("C:/demo"),
        default_svg_mapping_path="mapping.json",
        route_write_view_box="0 0 1920 1080",
        do_rerun_fn="rerun",
        log_event_fn="log",
        p_atm=101325.0,
        model_module="model_mod",
        pressure_divisor=1.0,
        pressure_unit="атм (изб.)",
        dataset_id="dataset",
        safe_dataframe_fn="safe_df",
        flow_scale_and_unit_fn="scale_fn",
        get_component_fn="component_fn",
        render_svg_flow_animation_html_fn="html_fn",
        has_svg_autotrace=True,
        extract_polylines_fn="poly_fn",
        auto_build_mapping_from_svg_fn="auto_fn",
        detect_component_bboxes_fn="bbox_fn",
        name_score_fn="score_fn",
        shortest_path_fn="path_fn",
        evaluate_quality_fn="quality_fn",
    )

    assert surface["svg_scheme_args"] == (session_state,)
    assert surface["svg_scheme_kwargs"]["route_write_view_box"] == "0 0 1920 1080"
    assert surface["svg_scheme_kwargs"]["pressure_unit"] == "атм (изб.)"
    assert surface["svg_scheme_kwargs"]["get_component_fn"] == "component_fn"


def test_build_app_mechanical_animation_panel_kwargs_uses_legacy_defaults() -> None:
    kwargs = helpers.build_app_mechanical_animation_panel_kwargs(
        {"session": True},
        cache_key="cache-1",
        dataset_id="dataset-1",
        df_main="df_main",
        base_override={"base": 1},
        model_mod="model_mod",
        test_cfg={"cfg": True},
        test_pick="test-1",
        compute_road_profile_fn="road_fn",
        log_event_fn="log_fn",
        proc_metrics_fn="proc_fn",
        safe_image_fn="safe_image_fn",
        base_dir=Path("C:/demo"),
        get_mech_anim_component_fn="mech2d_fn",
        get_mech_car3d_component_fn="mech3d_fn",
        mech_fallback_module="fallback_mod",
    )

    assert kwargs["wheel_column_resolver_fn"]("ЛП") == "перемещение_колеса_ЛП_м"
    assert kwargs["road_column_resolver_fn"]("ПП") == "дорога_ПП_м"
    assert kwargs["stroke_column_resolver_fn"]("ЛЗ") == "положение_штока_ЛЗ_м"
    assert kwargs["z_column"] == "перемещение_рамы_z_м"
    assert kwargs["road_restored_log_kwargs"] == {"test": "test-1"}
    assert kwargs["section_kwargs"]["backend_default_index"] == 1
    assert kwargs["section_kwargs"]["camera_follow_default"] is True
    assert kwargs["section_kwargs"]["road_mesh_step_default"] == 6


def test_build_heavy_mechanical_animation_panel_kwargs_supports_rel0_and_heavy_runtime() -> None:
    df_main = pd.DataFrame(
        {
            "перемещение_рамы_z_м_rel0": [0.1],
            "крен_phi_рад_rel0": [0.2],
            "тангаж_theta_рад_rel0": [0.3],
            "перемещение_колеса_ЛП_м_rel0": [0.4],
            "дорога_ЛП_м_rel0": [0.5],
        }
    )

    kwargs = helpers.build_heavy_mechanical_animation_panel_kwargs(
        {"use_rel0_for_plots": True},
        cache_key="cache-2",
        dataset_id="dataset-2",
        df_main=df_main,
        base_override={"base": 2},
        model_mod="model_mod",
        test_cfg={"cfg": True},
        test_pick="test-2",
        compute_road_profile_fn="road_fn",
        log_event_fn="log_fn",
        proc_metrics_fn="proc_fn",
        safe_image_fn="safe_image_fn",
        base_dir=Path("C:/demo"),
        get_mech_anim_component_fn="mech2d_fn",
        get_mech_car3d_component_fn="mech3d_fn",
        mech_fallback_module="fallback_mod",
        get_float_param_fn="get_float_param",
        playhead_idx=7,
        component_last_error_fn="component_last_error",
        fallback_error="fallback_error",
        ring_visual_tests_map={"test-2": {"cfg": True}},
        ring_visual_pick="pick.npz",
        ring_visual_workspace_exports_dir=Path("C:/exports"),
        ring_visual_latest_export_paths_fn="latest_export_paths",
        ring_visual_base_dir=Path("C:/ring"),
    )

    assert kwargs["wheel_column_resolver_fn"]("ЛП") == "перемещение_колеса_ЛП_м_rel0"
    assert kwargs["road_column_resolver_fn"]("ЛП") == "дорога_ЛП_м_rel0"
    assert kwargs["z_column"] == "перемещение_рамы_z_м_rel0"
    assert kwargs["phi_column"] == "крен_phi_рад_rel0"
    assert kwargs["theta_column"] == "тангаж_theta_рад_rel0"
    assert kwargs["normalize_restored_road_fn"]({"ЛП": [5.0, 6.5]}) == {"ЛП": [0.0, 1.5]}
    assert kwargs["playhead_idx"] == 7
    assert kwargs["show_2d_controls"] is False
    assert kwargs["section_kwargs"]["backend_default_index"] == 0
    assert kwargs["section_kwargs"]["enable_model_path_mode"] is True
    assert kwargs["section_kwargs"]["ring_visual_pick"] == "pick.npz"


def test_entrypoints_use_shared_animation_results_builders() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_animation_results_builders import (" not in app_text
    assert "from pneumo_solver_ui.ui_animation_results_builders import (" not in heavy_text
    assert "build_app_mechanical_animation_panel_kwargs(" not in app_text
    assert "build_flow_animation_panel_kwargs(" not in app_text
    assert "build_svg_scheme_animation_surface_kwargs(" not in app_text
    assert "build_heavy_mechanical_animation_panel_kwargs(" not in heavy_text
    assert "build_flow_animation_panel_kwargs(" not in heavy_text
    assert "build_svg_scheme_animation_surface_kwargs(" not in heavy_text
    assert '"wheel_column_resolver_fn":' not in app_text
    assert '"wheel_column_resolver_fn":' not in heavy_text
    assert '"road_column_resolver_fn":' not in app_text
    assert '"road_column_resolver_fn":' not in heavy_text
    assert '"path_demo_options": [' not in app_text
    assert '"path_demo_options": [' not in heavy_text
    assert "from pneumo_solver_ui.ui_animation_results_section_helpers import (" in surface_text
    assert "render_app_animation_results_section," in surface_text
    assert "render_heavy_animation_results_section," in surface_text
    assert '"render_flow_panel_html_fn": render_flow_panel_html_fn or render_flow_panel_html' in surface_text
    assert '"route_write_view_box": route_write_view_box' in surface_text
    assert "from pneumo_solver_ui.ui_animation_results_builders import (" in section_text
    assert "build_app_mechanical_animation_panel_kwargs(" in section_text
    assert "build_heavy_mechanical_animation_panel_kwargs(" in section_text
    assert "build_flow_animation_panel_kwargs(" in section_text
    assert "build_svg_scheme_animation_surface_kwargs(" in section_text
    assert "def build_flow_animation_panel_kwargs(" in helper_text
    assert "def build_svg_scheme_animation_surface_kwargs(" in helper_text
    assert "def build_app_mechanical_animation_panel_kwargs(" in helper_text
    assert "def build_heavy_mechanical_animation_panel_kwargs(" in helper_text
