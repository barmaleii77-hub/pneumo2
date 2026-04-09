from __future__ import annotations

from pathlib import Path
from typing import Any


def build_flow_animation_panel_kwargs(
    *,
    df_mdot,
    df_open,
    p_atm: float,
    model_module: Any,
    flow_scale_and_unit_fn: Any,
    render_flow_panel_html_fn: Any,
) -> dict[str, Any]:
    return {
        "df_mdot": df_mdot,
        "df_open": df_open,
        "p_atm": p_atm,
        "model_module": model_module,
        "flow_scale_and_unit_fn": flow_scale_and_unit_fn,
        "render_flow_panel_html_fn": render_flow_panel_html_fn,
    }


def build_svg_scheme_animation_surface_kwargs(
    session_state: dict[str, Any],
    *,
    df_mdot,
    df_open,
    df_p,
    base_dir: Path,
    default_svg_mapping_path: Any,
    route_write_view_box: str,
    do_rerun_fn: Any,
    log_event_fn: Any,
    p_atm: float,
    model_module: Any,
    pressure_divisor: float,
    pressure_unit: str,
    dataset_id: Any,
    safe_dataframe_fn: Any,
    flow_scale_and_unit_fn: Any,
    get_component_fn: Any,
    render_svg_flow_animation_html_fn: Any,
    has_svg_autotrace: bool,
    extract_polylines_fn: Any,
    auto_build_mapping_from_svg_fn: Any,
    detect_component_bboxes_fn: Any,
    name_score_fn: Any,
    shortest_path_fn: Any,
    evaluate_quality_fn: Any,
) -> dict[str, Any]:
    return {
        "svg_scheme_args": (session_state,),
        "svg_scheme_kwargs": {
            "df_mdot": df_mdot,
            "df_open": df_open,
            "df_p": df_p,
            "base_dir": base_dir,
            "default_svg_mapping_path": default_svg_mapping_path,
            "route_write_view_box": route_write_view_box,
            "do_rerun_fn": do_rerun_fn,
            "log_event_fn": log_event_fn,
            "p_atm": p_atm,
            "model_module": model_module,
            "pressure_divisor": pressure_divisor,
            "pressure_unit": pressure_unit,
            "dataset_id": dataset_id,
            "safe_dataframe_fn": safe_dataframe_fn,
            "flow_scale_and_unit_fn": flow_scale_and_unit_fn,
            "get_component_fn": get_component_fn,
            "render_svg_flow_animation_html_fn": render_svg_flow_animation_html_fn,
            "has_svg_autotrace": has_svg_autotrace,
            "extract_polylines_fn": extract_polylines_fn,
            "auto_build_mapping_from_svg_fn": auto_build_mapping_from_svg_fn,
            "detect_component_bboxes_fn": detect_component_bboxes_fn,
            "name_score_fn": name_score_fn,
            "shortest_path_fn": shortest_path_fn,
            "evaluate_quality_fn": evaluate_quality_fn,
        },
    }


def build_app_mechanical_animation_panel_kwargs(
    session_state: dict[str, Any],
    *,
    cache_key: str,
    dataset_id: Any,
    df_main,
    base_override: dict[str, Any],
    model_mod: Any,
    test_cfg: dict[str, Any] | None,
    test_pick: str,
    compute_road_profile_fn: Any,
    log_event_fn: Any,
    proc_metrics_fn: Any,
    safe_image_fn: Any,
    base_dir: Path,
    get_mech_anim_component_fn: Any,
    get_mech_car3d_component_fn: Any,
    mech_fallback_module: Any,
) -> dict[str, Any]:
    return {
        "session_state": session_state,
        "cache_key": cache_key,
        "dataset_id": dataset_id,
        "df_main": df_main,
        "base_override": base_override,
        "model_mod": model_mod,
        "test_cfg": test_cfg,
        "compute_road_profile_fn": compute_road_profile_fn,
        "log_event_fn": log_event_fn,
        "wheel_column_resolver_fn": (lambda c: f"перемещение_колеса_{c}_м"),
        "road_column_resolver_fn": (lambda c: f"дорога_{c}_м"),
        "stroke_column_resolver_fn": (lambda c: f"положение_штока_{c}_м"),
        "z_column": "перемещение_рамы_z_м",
        "phi_column": "крен_phi_рад",
        "theta_column": "тангаж_theta_рад",
        "road_restored_log_kwargs": {"test": test_pick},
        "playhead_idx": None,
        "show_2d_controls": None,
        "section_kwargs": {
            "log_cb": log_event_fn,
            "proc_metrics_fn": proc_metrics_fn,
            "safe_image_fn": safe_image_fn,
            "base_dir": base_dir,
            "get_mech_anim_component_fn": get_mech_anim_component_fn,
            "get_mech_car3d_component_fn": get_mech_car3d_component_fn,
            "mech_fallback_module": mech_fallback_module,
            "backend_default_index": 1,
            "backend_description_text": (
                "По умолчанию включён компонентный режим (SVG/Canvas): Play/Pause выполняются в браузере и не дёргают сервер на каждый кадр. "
                "Если компоненты Streamlit не загружаются/видишь ошибки вида `apiVersion undefined` — переключись на встроенный режим (matplotlib)."
            ),
            "path_checkbox_label": "3D: доп. траектории (НЕ физика, только визуализация)",
            "path_demo_options": [
                "Статика (без движения)",
                "По ax/ay из модели",
                "Прямая",
                "Слалом",
                "Поворот (радиус)",
            ],
            "path_demo_info_text": (
                "3D: траектория X/Z сейчас кинематическая (только визуализация) и НЕ влияет на расчёт. "
                "Крен/тангаж/высоты берутся из результатов симуляции. Реальная продольная/поперечная динамика "
                "(передача момента/торможение, скорость по дороге и т.д.) — TODO."
            ),
            "path_non_demo_caption": (
                "По умолчанию X/Z‑движение отключено. В 3D рисуются только величины из результатов расчёта "
                "(крен/тангаж/ходы/дорога)."
            ),
            "base_default": 2.8,
            "track_default": 1.6,
            "camera_follow_default": True,
            "road_mesh_step_default": 6,
        },
    }


def _pick_rel0_column(df_main, base: str, *, use_rel0: bool) -> str:
    rel0_column = f"{base}_rel0"
    if use_rel0 and df_main is not None and rel0_column in getattr(df_main, "columns", ()):
        return rel0_column
    return base


def build_heavy_mechanical_animation_panel_kwargs(
    session_state: dict[str, Any],
    *,
    cache_key: str,
    dataset_id: Any,
    df_main,
    base_override: dict[str, Any],
    model_mod: Any,
    test_cfg: dict[str, Any] | None,
    test_pick: str,
    compute_road_profile_fn: Any,
    log_event_fn: Any,
    proc_metrics_fn: Any,
    safe_image_fn: Any,
    base_dir: Path,
    get_mech_anim_component_fn: Any,
    get_mech_car3d_component_fn: Any,
    mech_fallback_module: Any,
    get_float_param_fn: Any,
    playhead_idx: int,
    component_last_error_fn: Any,
    fallback_error: Any,
    ring_visual_tests_map: Any,
    ring_visual_pick: Any,
    ring_visual_workspace_exports_dir: Path,
    ring_visual_latest_export_paths_fn: Any,
    ring_visual_base_dir: Path,
) -> dict[str, Any]:
    use_rel0_anim = bool(session_state.get("use_rel0_for_plots", True))

    return {
        "session_state": session_state,
        "cache_key": cache_key,
        "dataset_id": dataset_id,
        "df_main": df_main,
        "base_override": base_override,
        "model_mod": model_mod,
        "test_cfg": test_cfg,
        "compute_road_profile_fn": compute_road_profile_fn,
        "log_event_fn": log_event_fn,
        "wheel_column_resolver_fn": (
            lambda c, _df=df_main, _use_rel0=use_rel0_anim: _pick_rel0_column(
                _df,
                f"перемещение_колеса_{c}_м",
                use_rel0=_use_rel0,
            )
        ),
        "road_column_resolver_fn": (
            lambda c, _df=df_main, _use_rel0=use_rel0_anim: _pick_rel0_column(
                _df,
                f"дорога_{c}_м",
                use_rel0=_use_rel0,
            )
        ),
        "stroke_column_resolver_fn": (lambda c: f"положение_штока_{c}_м"),
        "z_column": _pick_rel0_column(df_main, "перемещение_рамы_z_м", use_rel0=use_rel0_anim),
        "phi_column": _pick_rel0_column(df_main, "крен_phi_рад", use_rel0=use_rel0_anim),
        "theta_column": _pick_rel0_column(df_main, "тангаж_theta_рад", use_rel0=use_rel0_anim),
        "normalize_restored_road_fn": (
            (lambda restored_road: {
                corner: [float(value) - float(values[0]) for value in values] if values else values
                for corner, values in restored_road.items()
            })
            if use_rel0_anim
            else None
        ),
        "get_float_param_fn": get_float_param_fn,
        "wheelbase_default": 1.5,
        "track_default": 1.0,
        "playhead_idx": int(playhead_idx),
        "show_2d_controls": False,
        "road_restored_log_kwargs": {"test": test_pick},
        "section_kwargs": {
            "log_cb": log_event_fn,
            "proc_metrics_fn": proc_metrics_fn,
            "safe_image_fn": safe_image_fn,
            "base_dir": base_dir,
            "get_mech_anim_component_fn": get_mech_anim_component_fn,
            "get_mech_car3d_component_fn": get_mech_car3d_component_fn,
            "mech_fallback_module": mech_fallback_module,
            "backend_default_index": 0,
            "backend_description_text": (
                "По умолчанию включён встроенный режим (matplotlib): он самый надёжный и не зависит от Streamlit Components. "
                "Компонентный режим (SVG/Canvas) — экспериментальный: если он у тебя падает/не грузится — оставь встроенный."
            ),
            "path_checkbox_label": "3D: выбор траектории (vx/yaw = из расчёта, остальное — демо)",
            "path_demo_options": [
                "По vx/yaw из модели",
                "Статика (без движения)",
                "По ax/ay из модели",
                "Прямая",
                "Слалом",
                "Поворот (радиус)",
            ],
            "path_demo_info_text": (
                "3D: режим **По vx/yaw из модели** использует реальную траекторию из расчёта. "
                "Остальные режимы — кинематика/демо (НЕ влияет на расчёт)."
            ),
            "path_non_demo_caption": (
                "3D: world-траектория недоступна (нет колонок скорость_vx_м_с / yaw_рад). "
                "По умолчанию X/Z-движение выключено — показываем только крен/тангаж/ходы/дорогу."
            ),
            "base_default": 1.5,
            "track_default": 1.0,
            "camera_follow_default": False,
            "road_mesh_step_default": 2,
            "get_float_param_fn": get_float_param_fn,
            "enable_model_path_mode": True,
            "model_path_caption": (
                "3D: траектория берётся из расчёта (vx + yaw) → скорость соответствует расчётной, повороты видны по yaw."
            ),
            "component_last_error_fn": component_last_error_fn,
            "fallback_error": fallback_error,
            "ring_visual_tests_map": ring_visual_tests_map,
            "ring_visual_test_pick": test_pick,
            "ring_visual_pick": ring_visual_pick,
            "ring_visual_workspace_exports_dir": ring_visual_workspace_exports_dir,
            "ring_visual_latest_export_paths_fn": ring_visual_latest_export_paths_fn,
            "ring_visual_base_dir": ring_visual_base_dir,
        },
    }
