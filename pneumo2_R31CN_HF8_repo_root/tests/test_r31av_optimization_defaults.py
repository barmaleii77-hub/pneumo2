from __future__ import annotations

from pathlib import Path
import json

from pneumo_solver_ui.optimization_defaults import (
    DEFAULT_OPTIMIZATION_OBJECTIVES,
    DIAGNOSTIC_OPT_JOBS_HINT,
    DIAGNOSTIC_SUITE_SELECTED_ID,
    diagnostics_jobs_default,
    objectives_text,
)


def test_r31av_default_objectives_vertical_lateral_energy_order() -> None:
    assert DEFAULT_OPTIMIZATION_OBJECTIVES == (
        "метрика_комфорт__RMS_ускор_рамы_микро_м_с2",
        "метрика_крен_ay3_град",
        "метрика_энергия_дроссели_микро_Дж",
    )
    assert objectives_text().splitlines() == list(DEFAULT_OPTIMIZATION_OBJECTIVES)


def test_r31av_jobs_default_follows_diagnostics_hint() -> None:
    assert diagnostics_jobs_default(64, platform_name="win32") == DIAGNOSTIC_OPT_JOBS_HINT
    assert diagnostics_jobs_default(8, platform_name="win32") == 8
    assert diagnostics_jobs_default(128, platform_name="win32") == 61


def test_r31cm_jobs_default_without_explicit_cpu_count_is_safe() -> None:
    value = diagnostics_jobs_default()
    assert isinstance(value, int)
    assert 1 <= value <= DIAGNOSTIC_OPT_JOBS_HINT


def test_r31av_default_suite_contains_diagnostics_selected_id() -> None:
    suite_path = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "default_suite.json"
    rows = json.loads(suite_path.read_text(encoding="utf-8"))
    ids = {str((row or {}).get("id") or "").strip() for row in rows}
    assert DIAGNOSTIC_SUITE_SELECTED_ID in ids


def test_r31av_optimization_page_wires_canonical_paths_and_os_import() -> None:
    page_path = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "pages" / "03_Optimization.py"
    launch_plan_path = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "optimization_launch_plan_runtime.py"
    page_src = page_path.read_text(encoding="utf-8")
    launch_src = launch_plan_path.read_text(encoding="utf-8")
    assert "import os" in page_src
    assert "_UI_JOBS_DEFAULT = int(diagnostics_jobs_default(os.cpu_count(), platform_name=sys.platform))" in page_src
    assert "diagnostics_jobs_default()" not in page_src
    assert "build_optimization_launch_plan(" in page_src
    for token in ["--model", "--worker", "--base_json", "--ranges_json", "--suite_json"]:
        assert token in launch_src
    for token in ["--model", "--worker", "--base-json", "--ranges-json", "--suite-json"]:
        assert token in launch_src


def test_r31av_coordinator_scripts_add_project_root_to_syspath() -> None:
    base = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "tools"
    for name in ["dist_opt_coordinator.py", "dbqueue_coordinator.py"]:
        src = (base / name).read_text(encoding="utf-8")
        assert "_PROJECT_ROOT = _PNEUMO_ROOT.parent" in src
        assert "for _p in (str(_PROJECT_ROOT), str(_PNEUMO_ROOT))" in src


def test_r31aw_run_id_sanitize_helper_available_for_optimization_runtime() -> None:
    app_path = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "pneumo_ui_app.py"
    sanitize_path = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "name_sanitize.py"
    src = app_path.read_text(encoding="utf-8")
    sanitize_src = sanitize_path.read_text(encoding="utf-8")
    assert "sanitize_id" in src
    assert 'run_id = sanitize_id(st.session_state.get("opt_run_name", "run")) or "run"' in src
    assert 'safe_stem = sanitize_id(out_prefix or "results_opt") or "results_opt"' in src
    assert 'sanitize_id = sanitize_unicode_id' in sanitize_src


def test_r31bb_default_ranges_include_piston_diameters_from_latest_diagnostics() -> None:
    ranges_path = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "default_ranges.json"
    rows = json.loads(ranges_path.read_text(encoding="utf-8"))
    assert rows.get("диаметр_поршня_Ц1") == [0.01, 0.1]
    assert rows.get("диаметр_поршня_Ц2") == [0.01, 0.1]
