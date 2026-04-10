from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_animation_results_section_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_animation_results_section_helpers.py"
SECONDARY_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_secondary_views_helpers.py"


def test_render_app_animation_results_section_uses_shared_builders_and_section() -> None:
    calls: list[tuple[str, object]] = []
    original_app_builder = helpers.build_app_mechanical_animation_panel_kwargs
    original_flow_builder = helpers.build_flow_animation_panel_kwargs
    original_svg_builder = helpers.build_svg_scheme_animation_surface_kwargs
    original_section = helpers.render_animation_results_section
    try:
        helpers.build_app_mechanical_animation_panel_kwargs = (
            lambda session_state, **kwargs: {
                "builder": "app",
                "session_state": session_state,
                "test_cfg": kwargs["test_cfg"],
            }
        )
        helpers.build_flow_animation_panel_kwargs = lambda **kwargs: {
            "builder": "flow",
            "model": kwargs["model_module"],
        }
        helpers.build_svg_scheme_animation_surface_kwargs = lambda session_state, **kwargs: {
            "svg_scheme_args": (session_state,),
            "svg_scheme_kwargs": {
                "builder": "svg",
                "pressure_unit": kwargs["pressure_unit"],
            },
        }
        helpers.render_animation_results_section = lambda st, **kwargs: calls.append(
            ("section", kwargs)
        ) or "mech"

        selected = helpers.render_app_animation_results_section(
            "st",
            cur_hash="hash-1",
            test_pick="test-1",
            session_state={"demo": True},
            cache_key="cache-1",
            dataset_id="dataset-1",
            df_main="df_main",
            base_override={"base": 1},
            model_mod="model_mod",
            tests_map={"test-1": {"cfg": True}},
            compute_road_profile_fn="road_fn",
            log_event_fn="log_fn",
            proc_metrics_fn="proc_fn",
            safe_image_fn="safe_image_fn",
            base_dir=Path("C:/demo"),
            get_mech_anim_component_fn="mech2d_fn",
            get_mech_car3d_component_fn="mech3d_fn",
            mech_fallback_module="fallback_mod",
            render_mechanics_panel_fn="render_mech",
            render_flow_tool_panel_fn="render_flow",
            render_flow_panel_html_fn="flow_html_fn",
            render_svg_scheme_section_fn="render_svg",
            df_mdot="df_mdot",
            df_open="df_open",
            df_p="df_p",
            p_atm=101325.0,
            default_svg_mapping_path="mapping.json",
            route_write_view_box="0 0 100 100",
            do_rerun_fn="rerun_fn",
            pressure_divisor=101325.0,
            pressure_unit="atm",
            safe_dataframe_fn="safe_df_fn",
            flow_scale_and_unit_fn="flow_scale_fn",
            get_svg_component_fn="svg_component_fn",
            render_svg_flow_animation_html_fn="svg_html_fn",
            has_svg_autotrace=True,
            extract_polylines_fn="poly_fn",
            auto_build_mapping_from_svg_fn="auto_fn",
            detect_component_bboxes_fn="bbox_fn",
            name_score_fn="score_fn",
            shortest_path_fn="path_fn",
            evaluate_quality_fn="quality_fn",
        )

        assert selected == "mech"
        assert calls == [
            (
                "section",
                {
                    "cur_hash": "hash-1",
                    "test_pick": "test-1",
                    "render_mechanics_panel_fn": "render_mech",
                    "mechanics_panel_kwargs": {
                        "builder": "app",
                        "session_state": {"demo": True},
                        "test_cfg": {"cfg": True},
                    },
                    "render_flow_tool_panel_fn": "render_flow",
                    "flow_panel_kwargs": {
                        "builder": "flow",
                        "model": "model_mod",
                    },
                    "render_svg_scheme_section_fn": "render_svg",
                    "svg_scheme_args": ({"demo": True},),
                    "svg_scheme_kwargs": {
                        "builder": "svg",
                        "pressure_unit": "atm",
                    },
                },
            )
        ]
    finally:
        helpers.build_app_mechanical_animation_panel_kwargs = original_app_builder
        helpers.build_flow_animation_panel_kwargs = original_flow_builder
        helpers.build_svg_scheme_animation_surface_kwargs = original_svg_builder
        helpers.render_animation_results_section = original_section


def test_render_heavy_animation_results_section_uses_shared_builders_and_section() -> None:
    calls: list[tuple[str, object]] = []
    original_heavy_builder = helpers.build_heavy_mechanical_animation_panel_kwargs
    original_flow_builder = helpers.build_flow_animation_panel_kwargs
    original_svg_builder = helpers.build_svg_scheme_animation_surface_kwargs
    original_section = helpers.render_animation_results_section
    try:
        helpers.build_heavy_mechanical_animation_panel_kwargs = (
            lambda session_state, **kwargs: {
                "builder": "heavy",
                "session_state": session_state,
                "playhead_idx": kwargs["playhead_idx"],
                "ring_visual_pick": kwargs["ring_visual_pick"],
            }
        )
        helpers.build_flow_animation_panel_kwargs = lambda **kwargs: {
            "builder": "flow",
            "model": kwargs["model_module"],
        }
        helpers.build_svg_scheme_animation_surface_kwargs = lambda session_state, **kwargs: {
            "svg_scheme_args": (session_state,),
            "svg_scheme_kwargs": {
                "builder": "svg",
                "pressure_unit": kwargs["pressure_unit"],
            },
        }
        helpers.render_animation_results_section = lambda st, **kwargs: calls.append(
            ("section", kwargs)
        ) or "svg"

        selected = helpers.render_heavy_animation_results_section(
            "st",
            cur_hash="hash-2",
            test_pick="test-2",
            session_state={"heavy": True},
            cache_key="cache-2",
            dataset_id="dataset-2",
            df_main="df_main",
            base_override={"base": 2},
            model_mod="model_mod",
            tests_map={"test-2": {"cfg": True}},
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
            ring_visual_latest_export_paths_fn="latest_export_paths_fn",
            ring_visual_base_dir=Path("C:/ring"),
            render_mechanics_panel_fn="render_mech",
            render_flow_tool_panel_fn="render_flow",
            render_flow_panel_html_fn="flow_html_fn",
            render_svg_scheme_section_fn="render_svg",
            df_mdot="df_mdot",
            df_open="df_open",
            df_p="df_p",
            p_atm=101325.0,
            default_svg_mapping_path="mapping.json",
            route_write_view_box="0 0 100 100",
            do_rerun_fn="rerun_fn",
            pressure_divisor=100000.0,
            pressure_unit="bar",
            safe_dataframe_fn="safe_df_fn",
            flow_scale_and_unit_fn="flow_scale_fn",
            get_svg_component_fn="svg_component_fn",
            render_svg_flow_animation_html_fn="svg_html_fn",
            has_svg_autotrace=True,
            extract_polylines_fn="poly_fn",
            auto_build_mapping_from_svg_fn="auto_fn",
            detect_component_bboxes_fn="bbox_fn",
            name_score_fn="score_fn",
            shortest_path_fn="path_fn",
            evaluate_quality_fn="quality_fn",
        )

        assert selected == "svg"
        assert calls == [
            (
                "section",
                {
                    "cur_hash": "hash-2",
                    "test_pick": "test-2",
                    "render_mechanics_panel_fn": "render_mech",
                    "mechanics_panel_kwargs": {
                        "builder": "heavy",
                        "session_state": {"heavy": True},
                        "playhead_idx": 7,
                        "ring_visual_pick": "pick.npz",
                    },
                    "render_flow_tool_panel_fn": "render_flow",
                    "flow_panel_kwargs": {
                        "builder": "flow",
                        "model": "model_mod",
                    },
                    "render_svg_scheme_section_fn": "render_svg",
                    "svg_scheme_args": ({"heavy": True},),
                    "svg_scheme_kwargs": {
                        "builder": "svg",
                        "pressure_unit": "bar",
                    },
                },
            )
        ]
    finally:
        helpers.build_heavy_mechanical_animation_panel_kwargs = original_heavy_builder
        helpers.build_flow_animation_panel_kwargs = original_flow_builder
        helpers.build_svg_scheme_animation_surface_kwargs = original_svg_builder
        helpers.render_animation_results_section = original_section


def test_entrypoints_use_shared_animation_results_section_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    secondary_text = SECONDARY_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_animation_results_section_helpers import (" in surface_text
    assert "render_app_animation_results_section," in surface_text
    assert "render_heavy_animation_results_section," in surface_text
    assert "render_app_animation_results_section(" not in app_text
    assert "render_heavy_animation_results_section(" not in heavy_text
    assert "render_animation_results_section(" not in app_text
    assert "render_animation_results_section(" not in heavy_text
    assert "build_app_mechanical_animation_panel_kwargs(" not in app_text
    assert "build_heavy_mechanical_animation_panel_kwargs(" not in heavy_text
    assert "build_flow_animation_panel_kwargs(" not in app_text
    assert "build_flow_animation_panel_kwargs(" not in heavy_text
    assert "build_svg_scheme_animation_surface_kwargs(" not in app_text
    assert "build_svg_scheme_animation_surface_kwargs(" not in heavy_text
    assert "animation_section_fn=render_app_animation_results_section" in surface_text
    assert "animation_section_fn=render_heavy_animation_results_section" in surface_text
    assert "animation_section_kwargs" in secondary_text
    assert "def render_app_animation_results_section(" in helper_text
    assert "def render_heavy_animation_results_section(" in helper_text
    assert "return _render_built_animation_results_section(" in helper_text
