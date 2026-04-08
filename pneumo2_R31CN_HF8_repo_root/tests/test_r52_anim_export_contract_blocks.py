from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.anim_export_contract import summarize_anim_export_contract, summarize_anim_export_objective_metrics
from pneumo_solver_ui.data_contract import build_geometry_meta_from_base
from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle
from pneumo_solver_ui.solver_points_contract import CORNERS, KNOWN_POINT_KINDS, point_cols
from pneumo_solver_ui.suspension_family_runtime import spring_family_active_flag_column, spring_family_runtime_column
from pneumo_solver_ui.tools.make_send_bundle import _collect_anim_latest_bundle_diagnostics


def _geometry_meta() -> dict:
    geom = build_geometry_meta_from_base(
        {
            "база": 2.8,
            "колея": 1.6,
            "диаметр_поршня_Ц1": 0.032,
            "диаметр_штока_Ц1": 0.016,
            "диаметр_поршня_Ц2": 0.05,
            "диаметр_штока_Ц2": 0.014,
            "ход_штока_Ц1_перед_м": 0.25,
            "ход_штока_Ц1_зад_м": 0.25,
            "ход_штока_Ц2_перед_м": 0.25,
            "ход_штока_Ц2_зад_м": 0.25,
            "мёртвый_объём_камеры": 1.5e-5,
            "стенка_толщина_м": 0.003,
            "пружина_Ц1_перед_геом_диаметр_проволоки_м": 0.008,
            "пружина_Ц1_перед_геом_диаметр_средний_м": 0.060,
            "пружина_Ц1_перед_длина_свободная_м": 0.31,
            "пружина_Ц1_перед_длина_солид_м": 0.085,
            "пружина_Ц1_перед_верхний_отступ_от_крышки_м": 0.02,
            "пружина_Ц1_перед_запас_до_coil_bind_минимум_м": 0.005,
            "пружина_Ц1_перед_преднатяг_на_отбое_минимум_м": 0.01,
            "пружина_Ц1_зад_геом_диаметр_проволоки_м": 0.009,
            "пружина_Ц1_зад_геом_диаметр_средний_м": 0.064,
            "пружина_Ц1_зад_длина_свободная_м": 0.32,
            "пружина_Ц1_зад_длина_солид_м": 0.090,
            "пружина_Ц1_зад_верхний_отступ_от_крышки_м": 0.021,
            "пружина_Ц1_зад_запас_до_coil_bind_минимум_м": 0.006,
            "пружина_Ц1_зад_преднатяг_на_отбое_минимум_м": 0.011,
            "пружина_Ц2_перед_геом_диаметр_проволоки_м": 0.007,
            "пружина_Ц2_перед_геом_диаметр_средний_м": 0.072,
            "пружина_Ц2_перед_длина_свободная_м": 0.30,
            "пружина_Ц2_перед_длина_солид_м": 0.084,
            "пружина_Ц2_перед_верхний_отступ_от_крышки_м": 0.019,
            "пружина_Ц2_перед_запас_до_coil_bind_минимум_м": 0.005,
            "пружина_Ц2_перед_преднатяг_на_отбое_минимум_м": 0.010,
            "пружина_Ц2_зад_геом_диаметр_проволоки_м": 0.007,
            "пружина_Ц2_зад_геом_диаметр_средний_м": 0.074,
            "пружина_Ц2_зад_длина_свободная_м": 0.31,
            "пружина_Ц2_зад_длина_солид_м": 0.086,
            "пружина_Ц2_зад_верхний_отступ_от_крышки_м": 0.020,
            "пружина_Ц2_зад_запас_до_coil_bind_минимум_м": 0.006,
            "пружина_Ц2_зад_преднатяг_на_отбое_минимум_м": 0.011,
        }
    )
    return {"geometry": geom, "source": "pytest"}


def _solver_df_with_optional_hardpoints_and_nan_lengths() -> pd.DataFrame:
    t = np.array([0.0, 0.1], dtype=float)
    data: dict[str, object] = {
        "время_с": t,
        "скорость_vx_м_с": np.array([1.0, 1.0], dtype=float),
        "yaw_рад": np.array([0.0, 0.0], dtype=float),
    }

    seed = 0.0
    for family in KNOWN_POINT_KINDS:
        for corner in CORNERS:
            for axis_i, col in enumerate(point_cols(family, corner)):
                base = seed + float(axis_i)
                data[col] = np.array([base, base + 0.01], dtype=float)
            seed += 0.1

    # Override cylinder mount hardpoints so endpoint distance is exact and easy to assert.
    cyl1_lengths = {"ЛП": (0.30, 0.31), "ПП": (0.32, 0.33), "ЛЗ": (0.34, 0.35), "ПЗ": (0.36, 0.37)}
    cyl2_lengths = {"ЛП": (0.45, 0.46), "ПП": (0.47, 0.48), "ЛЗ": (0.49, 0.50), "ПЗ": (0.51, 0.52)}
    for idx, corner in enumerate(CORNERS):
        x0 = float(idx)
        x1 = x0 + 0.1
        # C1 top/body side
        data[f"cyl1_top_{corner}_x_м"] = np.array([x0, x1], dtype=float)
        data[f"cyl1_top_{corner}_y_м"] = np.array([0.0, 0.0], dtype=float)
        data[f"cyl1_top_{corner}_z_м"] = np.array([0.0, 0.0], dtype=float)
        data[f"cyl1_bot_{corner}_x_м"] = np.array([x0, x1], dtype=float)
        data[f"cyl1_bot_{corner}_y_м"] = np.array([cyl1_lengths[corner][0], cyl1_lengths[corner][1]], dtype=float)
        data[f"cyl1_bot_{corner}_z_м"] = np.array([0.0, 0.0], dtype=float)
        # C2 top/body side
        data[f"cyl2_top_{corner}_x_м"] = np.array([x0 + 10.0, x1 + 10.0], dtype=float)
        data[f"cyl2_top_{corner}_y_м"] = np.array([0.0, 0.0], dtype=float)
        data[f"cyl2_top_{corner}_z_м"] = np.array([0.0, 0.0], dtype=float)
        data[f"cyl2_bot_{corner}_x_м"] = np.array([x0 + 10.0, x1 + 10.0], dtype=float)
        data[f"cyl2_bot_{corner}_y_м"] = np.array([cyl2_lengths[corner][0], cyl2_lengths[corner][1]], dtype=float)
        data[f"cyl2_bot_{corner}_z_м"] = np.array([0.0, 0.0], dtype=float)
        data[f"положение_штока_{corner}_м"] = np.array([0.05, 0.06], dtype=float)
        data[f"положение_штока_Ц2_{corner}_м"] = np.array([0.07, 0.08], dtype=float)
        data[f"длина_цилиндра_{corner}_м"] = np.array([np.nan, np.nan], dtype=float)
        data[f"длина_цилиндра_Ц2_{corner}_м"] = np.array([np.nan, np.nan], dtype=float)
        data[f"пружина_длина_{corner}_м"] = np.array([0.24 + 0.01 * idx, 0.23 + 0.01 * idx], dtype=float)
        data[f"пружина_зазор_до_крышки_{corner}_м"] = np.array([0.015, 0.012], dtype=float)
        data[f"пружина_запас_до_coil_bind_{corner}_м"] = np.array([0.020, 0.018], dtype=float)
        data[spring_family_active_flag_column("Ц1", corner)] = np.array([1.0, 1.0], dtype=float)
        data[spring_family_runtime_column("длина_м", "Ц1", corner)] = np.array([0.24 + 0.01 * idx, 0.23 + 0.01 * idx], dtype=float)
        data[spring_family_runtime_column("зазор_до_крышки_м", "Ц1", corner)] = np.array([0.015, 0.012], dtype=float)
        data[spring_family_runtime_column("запас_до_coil_bind_м", "Ц1", corner)] = np.array([0.020, 0.018], dtype=float)
        data[spring_family_runtime_column("длина_установленная_м", "Ц1", corner)] = np.array([0.24 + 0.01 * idx, 0.23 + 0.01 * idx], dtype=float)
        data[spring_family_runtime_column("компрессия_м", "Ц1", corner)] = np.array([0.06, 0.07], dtype=float)
        data[spring_family_active_flag_column("Ц2", corner)] = np.array([0.0, 0.0], dtype=float)
        data[spring_family_runtime_column("длина_м", "Ц2", corner)] = np.array([np.nan, np.nan], dtype=float)
        data[spring_family_runtime_column("зазор_до_крышки_м", "Ц2", corner)] = np.array([np.nan, np.nan], dtype=float)
        data[spring_family_runtime_column("запас_до_coil_bind_м", "Ц2", corner)] = np.array([np.nan, np.nan], dtype=float)
        data[spring_family_runtime_column("длина_установленная_м", "Ц2", corner)] = np.array([np.nan, np.nan], dtype=float)
        data[spring_family_runtime_column("компрессия_м", "Ц2", corner)] = np.array([np.nan, np.nan], dtype=float)

    return pd.DataFrame(data)


def _read_npz_meta(npz_path: Path) -> tuple[dict, list[str], np.ndarray]:
    with np.load(npz_path, allow_pickle=True) as data:
        meta = json.loads(str(data["meta_json"].item()))
        cols = [str(x) for x in data["main_cols"].tolist()]
        values = np.asarray(data["main_values"], dtype=float)
    return meta, cols, values


def test_export_anim_latest_bundle_writes_contract_blocks_and_repairs_nan_cylinder_lengths(tmp_path: Path) -> None:
    npz_path, _ptr_path = export_anim_latest_bundle(
        exports_dir=tmp_path,
        df_main=_solver_df_with_optional_hardpoints_and_nan_lengths(),
        meta=_geometry_meta(),
        mirror_global_pointer=False,
    )
    meta, cols, values = _read_npz_meta(npz_path)

    assert meta["solver_points"]["schema"] == "solver_points.contract.v1"
    assert meta["hardpoints"]["schema"] == "hardpoints.export.v1"
    assert meta["packaging"]["schema"] == "cylinder_packaging.contract.v1"
    assert "frame_corner" in meta["solver_points"]["visible_suspension_skeleton_families"]
    assert "lower_arm_frame_front" in meta["solver_points"]["visible_suspension_skeleton_families"]
    assert set(meta["solver_points"]["legacy_alias_families"]) >= {"arm_pivot", "arm_joint", "arm2_pivot", "arm2_joint"}
    assert (
        meta["hardpoints"]["families"]["lower_arm_frame_front"]["corners"]["ЛП"]["column_map"]["x"]
        == "lower_arm_frame_front_ЛП_x_м"
    )

    packaging = meta["packaging"]
    assert packaging["status"] == "partial"
    assert "gland_or_sleeve_position_m" in packaging["missing_advanced_fields"]
    assert packaging["cylinders"]["cyl1"]["mount_families"]["top"] == "cyl1_top"
    assert packaging["cylinders"]["cyl1"]["length_status_by_corner"]["ЛП"] == "filled_from_endpoint_distance"
    assert packaging["cylinders"]["cyl2"]["length_status_by_corner"]["ПЗ"] == "filled_from_endpoint_distance"
    assert packaging["cylinders"]["cyl1"]["resolved_geometry_by_axle"]["front"]["stroke_m"] == 0.25
    assert packaging["cylinders"]["cyl2"]["stroke_midstroke_t0_by_axle"]["rear"]["midstroke_target_m"] == 0.125
    assert packaging["spring_families"]["cyl1_front"]["resolved_geometry"]["inner_diameter_m"] == 0.052
    assert packaging["spring_families"]["cyl1_front"]["host_clearance_ok"] is True
    assert packaging["spring_families"]["cyl1_front"]["runtime_source"] == "explicit_family_columns"
    assert packaging["spring_families"]["cyl1_front"]["runtime_family"]["active_t0_mean"] == 1.0
    assert packaging["spring_families"]["cyl2_front"]["runtime_family"]["active_t0_mean"] == 0.0
    assert packaging["shared_spring_runtime_by_axle"]["front"]["min_gap_to_cap_m"] == 0.012
    assert packaging["shared_spring_runtime_by_axle"]["rear"]["min_coil_bind_margin_m"] == 0.018
    assert packaging["spring_pair_clearance_by_corner"]["ЛП"]["clearance_ok"] is True
    assert packaging["spring_pair_clearance_by_corner"]["ЛП"]["radial_clearance_t0_m"] > 9.9

    c1_idx = cols.index("длина_цилиндра_ЛП_м")
    c2_idx = cols.index("длина_цилиндра_Ц2_ПЗ_м")
    assert np.isfinite(values[:, c1_idx]).all()
    assert np.isfinite(values[:, c2_idx]).all()
    assert abs(float(values[0, c1_idx]) - 0.30) < 1e-12
    assert abs(float(values[-1, c1_idx]) - 0.31) < 1e-12
    assert abs(float(values[0, c2_idx]) - 0.51) < 1e-12
    assert abs(float(values[-1, c2_idx]) - 0.52) < 1e-12

    summary = summarize_anim_export_contract(meta)
    assert summary["has_solver_points_block"] is True
    assert summary["has_hardpoints_block"] is True
    assert summary["has_packaging_block"] is True
    assert summary["packaging_status"] == "partial"
    assert summary["packaging_truth_ready"] is False
    assert summary["spring_family_count"] >= 2
    assert summary["spring_host_interference_families"] == []
    assert summary["spring_pair_interference_corners"] == []
    assert summary["spring_runtime_negative_families"] == []
    assert summary["spring_runtime_fallback_families"] == []
    assert summary["shared_spring_runtime_negative_axes"] == []
    objective_metrics = summarize_anim_export_objective_metrics(meta)
    assert objective_metrics["мин_зазор_пружина_цилиндр_м"] > 0.0
    assert objective_metrics["мин_зазор_пружина_пружина_м"] > 9.9
    assert objective_metrics["макс_ошибка_midstroke_t0_м"] == 0.075
    assert objective_metrics["мин_запас_до_coil_bind_пружины_м"] == 0.018


def test_collect_anim_latest_bundle_diagnostics_surfaces_contract_summary(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    exports_dir = workspace / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))

    export_anim_latest_bundle(
        exports_dir=exports_dir,
        df_main=_solver_df_with_optional_hardpoints_and_nan_lengths(),
        meta=_geometry_meta(),
    )

    diag, _md = _collect_anim_latest_bundle_diagnostics(tmp_path)
    assert diag["anim_latest_has_solver_points_block"] is True
    assert diag["anim_latest_has_hardpoints_block"] is True
    assert diag["anim_latest_has_packaging_block"] is True
    assert diag["anim_latest_packaging_status"] == "partial"
    assert diag["anim_latest_packaging_truth_ready"] is False
    assert "gland_or_sleeve_position_m" in diag["anim_latest_packaging_missing_advanced_fields"]
