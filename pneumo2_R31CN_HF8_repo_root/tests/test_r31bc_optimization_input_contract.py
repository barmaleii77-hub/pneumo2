from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.optimization_input_contract import (
    NON_DESIGN_RANGE_KEYS,
    normalize_suite_stage_numbers,
    sanitize_ranges_for_optimization,
)
from pneumo_solver_ui.opt_stage_runner_v1 import build_default_scenarios, expand_suite_by_scenarios, filter_and_scale_suite


def test_normalize_suite_stage_numbers_preserves_explicit_stage_numbers() -> None:
    suite = [
        {"имя": "ring_test_01", "тип": "maneuver_csv", "включен": True, "стадия": 1},
        {"имя": "ring_test_02", "тип": "maneuver_csv", "включен": False, "стадия": 3},
    ]
    normalized, audit = normalize_suite_stage_numbers(suite)
    assert audit["stage_bias_applied"] == 0
    assert audit["legacy_bias_rebase_disabled"] is True
    assert normalized[0]["стадия"] == 1
    assert normalized[0].get("_meta_stage_original") is None


def test_stage_filters_respect_explicit_entry_stage() -> None:
    base = {"начальное_давление_аккумулятора": 405300.0}
    suite = [{"имя": "ring_test_01", "тип": "maneuver_csv", "включен": True, "стадия": 1, "dt": 0.01, "t_end": 15.0}]
    suite_norm, _ = normalize_suite_stage_numbers(suite)
    suite_fs0 = filter_and_scale_suite(suite_norm, max_stage=0, dt_scale=2.5, t_end_scale=0.35)
    suite_fs1 = filter_and_scale_suite(suite_norm, max_stage=1, dt_scale=1.5, t_end_scale=1.0)
    assert suite_fs0 == []
    suite_exp = expand_suite_by_scenarios(suite_fs1, build_default_scenarios(base), base, scenario_ids=["nominal", "heavy"])
    assert len(suite_exp) == 2
    assert float(suite_exp[0]["dt"]) == 0.015
    assert float(suite_exp[0]["t_end"]) == 15.0


def test_sanitize_ranges_strips_service_keys_and_includes_base() -> None:
    base = {
        "vx0_м_с": 0.0,
        "верх_Ц1_перед_z_относительно_рамы_м": 0.6,
        "пружина_масштаб": 0.18,
    }
    ranges = {
        "vx0_м_с": [0.0, 25.0],
        "верх_Ц1_перед_z_относительно_рамы_м": [0.05, 0.35],
        "пружина_масштаб": [0.6, 2.0],
    }
    sanitized, audit = sanitize_ranges_for_optimization(base, ranges)
    assert "vx0_м_с" not in sanitized
    assert "vx0_м_с" in audit["removed_non_design_keys"]
    assert sanitized["верх_Ц1_перед_z_относительно_рамы_м"] == [0.05, 0.6]
    assert sanitized["пружина_масштаб"] == [0.18, 2.0]


def test_default_ranges_exclude_non_design_keys_and_cover_current_base() -> None:
    ui_root = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
    base = json.loads((ui_root / "default_base.json").read_text("utf-8"))
    ranges = json.loads((ui_root / "default_ranges.json").read_text("utf-8"))
    for key in NON_DESIGN_RANGE_KEYS:
        assert key not in ranges
    for key in [
        "верх_Ц1_зад_z_относительно_рамы_м",
        "верх_Ц1_перед_z_относительно_рамы_м",
        "верх_Ц2_зад_z_относительно_рамы_м",
        "верх_Ц2_перед_z_относительно_рамы_м",
        "пружина_масштаб",
    ]:
        lo, hi = ranges[key]
        assert float(lo) <= float(base[key]) <= float(hi)
    for key in [
        "верх_Ц1_зад_z_относительно_рамы_м",
        "верх_Ц1_перед_z_относительно_рамы_м",
        "верх_Ц2_зад_z_относительно_рамы_м",
        "верх_Ц2_перед_z_относительно_рамы_м",
    ]:
        assert float(ranges[key][1]) > float(base["высота_рамы"]), key


def test_sanitize_ranges_strips_integrator_runtime_knobs_from_optimizer_space() -> None:
    base = {
        "макс_шаг_интегрирования_с": 3.0e-4,
        "интегратор_rtol": 1e-3,
        "интегратор_atol": 1e-7,
        "интегратор_mass_rtol_scale_factor": 2.0,
        "интегратор_err_group_weight_mass": 0.92,
        "пружина_масштаб": 0.18,
    }
    ranges = {
        "макс_шаг_интегрирования_с": [1e-4, 5e-4],
        "интегратор_rtol": [1e-4, 1e-2],
        "интегратор_atol": [1e-8, 1e-6],
        "интегратор_mass_rtol_scale_factor": [1.0, 3.0],
        "интегратор_err_group_weight_mass": [0.8, 1.0],
        "пружина_масштаб": [0.1, 0.3],
    }

    sanitized, audit = sanitize_ranges_for_optimization(base, ranges)

    assert sanitized == {"пружина_масштаб": [0.1, 0.3]}
    assert set(audit["removed_non_design_keys"]) >= {
        "макс_шаг_интегрирования_с",
        "интегратор_rtol",
        "интегратор_atol",
        "интегратор_mass_rtol_scale_factor",
        "интегратор_err_group_weight_mass",
    }


def test_explicit_stage_numbers_do_not_push_disabled_stage0_to_minus_one() -> None:
    suite = [
        {"имя": "explicit_stage1", "тип": "maneuver_csv", "включен": True, "стадия": 1},
        {"имя": "disabled_template", "тип": "maneuver_csv", "включен": False, "стадия": 0},
    ]
    normalized, audit = normalize_suite_stage_numbers(suite)
    assert audit["stage_bias_applied"] == 0
    by_name = {str(r.get("имя")): r for r in normalized}
    assert by_name["explicit_stage1"]["стадия"] == 1
    assert by_name["disabled_template"]["стадия"] == 0
    assert by_name["disabled_template"].get("_meta_stage_original") is None


def test_ring_editor_source_declares_explicit_id_for_new_rows() -> None:
    ui_root = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
    text = (ui_root / "ui_scenario_ring.py").read_text("utf-8")
    assert '"id": str(uuid.uuid4())' in text



def test_ring_editor_selects_suite_rows_by_canonical_id() -> None:
    ui_root = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
    text = (ui_root / "ui_scenario_ring.py").read_text("utf-8")
    assert 'ui_suite_selected_id' in text
    assert 'st.session_state["ui_suite_selected_row"] =' not in text


def test_suite_card_editor_is_not_wrapped_in_form_anymore() -> None:
    ui_root = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
    text = (ui_root / "pneumo_ui_app.py").read_text("utf-8")
    assert 'with st.form(f"suite_card_' not in text
    assert '_suite_editor_widget_key(sid, "name")' in text
    assert 'ui_suite_apply_btn_' in text
