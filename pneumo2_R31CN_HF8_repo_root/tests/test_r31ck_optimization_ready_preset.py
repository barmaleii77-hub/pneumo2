from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.optimization_defaults import DEFAULT_OPTIMIZATION_OBJECTIVES
from pneumo_solver_ui.optimization_ready_preset import (
    READY_PROFILE_NAME,
    CANONICAL_OPTIMIZATION_TEST_TYPES,
    materialize_optimization_ready_suite_json,
    optimization_ready_session_defaults,
)


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"
PAGE = UI_ROOT / "pages" / "03_Optimization.py"
APP = UI_ROOT / "pneumo_ui_app.py"
LAUNCH_PLAN = UI_ROOT / "optimization_launch_plan_runtime.py"


def test_r31ck_ready_preset_materializes_valid_30min_suite(tmp_path: Path) -> None:
    suite_path = materialize_optimization_ready_suite_json(
        tmp_path / "workspace",
        base_json_path=UI_ROOT / "default_base.json",
        suite_source_path=UI_ROOT / "default_suite.json",
    )
    rows = json.loads(suite_path.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    assert len(rows) >= 18

    enabled = {
        str((row or {}).get("имя") or "").strip(): row
        for row in rows
        if isinstance(row, dict) and bool(row.get("включен"))
    }
    required_enabled = {
        "инерция_крен_ay3": 0,
        "инерция_тангаж_ax3": 0,
        "микро_синфаза": 0,
        "микро_pitch": 0,
        "микро_diagonal": 0,
        "кочка_ЛП_короткая": 1,
        "комбо_ay3_плюс_микро": 1,
        "world_ridge_bump_demo": 1,
        "ring_город_неровная_дорога_20кмч_15s": 2,
        READY_PROFILE_NAME: 2,
    }
    assert required_enabled.keys() <= enabled.keys()
    for name, stage in required_enabled.items():
        assert int(enabled[name]["стадия"]) == stage

    ring = enabled["ring_город_неровная_дорога_20кмч_15s"]
    assert ring["тип"] == "maneuver_csv"
    assert Path(ring["road_csv"]).is_absolute() and Path(ring["road_csv"]).exists()
    assert Path(ring["axay_csv"]).is_absolute() and Path(ring["axay_csv"]).exists()
    assert Path(ring["scenario_json"]).is_absolute() and Path(ring["scenario_json"]).exists()
    assert float(ring["t_end"]) >= 14.0
    assert ring["target_мин_зазор_пружина_цилиндр_м"] == 0.001
    assert ring["target_мин_зазор_пружина_пружина_м"] == 0.001
    assert ring["target_макс_ошибка_midstroke_t0_м"] == 0.03
    assert ring["target_мин_запас_до_coil_bind_пружины_м"] == 0.003
    ring_spec = json.loads(Path(ring["scenario_json"]).read_text(encoding="utf-8"))
    ring_segments = list(ring_spec.get("segments") or [])
    assert ring_segments
    assert all("turn_direction" in seg for seg in ring_segments)
    assert all("speed_end_kph" in seg for seg in ring_segments)
    assert all("drive_mode" not in seg for seg in ring_segments)
    assert all("speed_kph" not in seg for seg in ring_segments)
    assert all("v_end_kph" not in seg for seg in ring_segments)
    ring_meta = dict(ring_spec.get("_generated_meta") or {})
    assert abs(float(ring["dt"]) - float(ring_spec["dt_s"])) < 1e-12
    assert abs(float(ring["t_end"]) - float(ring_meta["lap_time_s"])) < 1e-12
    assert abs(float(ring["vx0_м_с"]) - (float(ring_spec["v0_kph"]) / 3.6)) < 1e-12

    profile = enabled[READY_PROFILE_NAME]
    assert profile["тип"] == "road_profile_csv"
    assert Path(profile["road_csv"]).is_absolute() and Path(profile["road_csv"]).exists()
    assert Path(profile["scenario_json"]).is_absolute() and Path(profile["scenario_json"]).exists()
    assert abs(float(profile["vx0_м_с"]) - (20.0 / 3.6)) < 1e-9
    assert profile["target_мин_зазор_пружина_цилиндр_м"] == 0.001
    assert profile["target_мин_зазор_пружина_пружина_м"] == 0.001
    assert profile["target_макс_ошибка_midstroke_t0_м"] == 0.03
    assert profile["target_мин_запас_до_coil_bind_пружины_м"] == 0.003


def test_r31ck_ready_session_defaults_seed_stage_runner_30min() -> None:
    defaults = optimization_ready_session_defaults(cpu_count=32, platform_name="win32")
    assert defaults["ui_opt_minutes"] == 30.0
    assert defaults["ui_jobs"] == 24
    assert defaults["opt_use_staged"] is True
    assert defaults["opt_stage_resume"] is False
    assert defaults["opt_autoupdate_baseline"] is True
    assert defaults["warmstart_mode"] == "surrogate"
    assert defaults["surrogate_samples"] == 8000
    assert defaults["surrogate_top_k"] == 64
    assert defaults["sort_tests_by_cost"] is True
    assert defaults["ui_seed_candidates"] == 1
    assert defaults["ui_seed_conditions"] == 1
    assert defaults["stage_policy_mode"] == "influence_weighted"
    assert defaults["settings_opt_problem_hash_mode"] == "stable"
    assert defaults["opt_objectives"].splitlines() == list(DEFAULT_OPTIMIZATION_OBJECTIVES)


def test_r31ck_page_and_classic_ui_use_optimization_ready_preset() -> None:
    page_src = PAGE.read_text(encoding="utf-8")
    app_src = APP.read_text(encoding="utf-8")
    launch_plan_src = LAUNCH_PLAN.read_text(encoding="utf-8")

    assert "seed_optimization_ready_session_state" in page_src
    assert "build_optimization_launch_plan" in page_src
    assert "materialize_optimization_ready_suite_json" in launch_plan_src
    assert "return canonical_suite_json_path(_ui_root())" not in page_src

    assert "load_optimization_ready_suite_rows" in app_src
    assert "seed_optimization_ready_session_state" in app_src
    assert "CANONICAL_OPTIMIZATION_TEST_TYPES" in app_src
    assert "load_default_suite_disabled(DEFAULT_SUITE_PATH)" not in app_src


def test_r31ck_supported_types_cover_pitch_and_diagonal_micro_scenarios() -> None:
    supported = set(CANONICAL_OPTIMIZATION_TEST_TYPES)
    assert "микро_разнофаза_перед_зад" in supported
    assert "микро_разнофаза_диагональ" in supported
    assert "road_profile_csv" in supported
    assert "maneuver_csv" in supported
