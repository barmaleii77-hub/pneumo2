from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_input_contract import (
    STAGE_RUNTIME_ROLE_DESCRIPTIONS,
    describe_runtime_stage,
    infer_suite_stage,
    normalize_suite_stage_numbers,
)
from pneumo_solver_ui.opt_stage_runner_v1 import infer_test_stage

ROOT = Path(__file__).resolve().parents[1]


def test_r31br_missing_stage_values_are_inferred_and_made_explicit() -> None:
    suite = [
        {"имя": "micro_roll", "тип": "микро_синфаза", "включен": True, "стадия": None},
        {"имя": "long_ring", "тип": "maneuver_csv", "включен": True, "стадия": ""},
    ]
    normalized, audit = normalize_suite_stage_numbers(suite)
    by_name = {str(r.get("имя")): r for r in normalized}
    assert by_name["micro_roll"]["стадия"] == 0
    assert by_name["long_ring"]["стадия"] == 1
    assert audit["inferred_missing_rows"] == 2
    assert audit["after"]["enabled_stage_counts"] == {"0": 1, "1": 1}



def test_r31br_stage_inference_and_runner_use_one_contract() -> None:
    recs = [
        {"тип": "инерция_крен", "стадия": None},
        {"тип": "maneuver_csv", "стадия": None, "road_csv": "x.csv", "axay_csv": "y.csv"},
        {"тип": "maneuver_csv", "стадия": -4},
    ]
    for rec in recs:
        assert infer_test_stage(rec) == infer_suite_stage(rec)
    assert infer_test_stage(recs[0]) == 0
    assert infer_test_stage(recs[1]) == 1
    assert infer_test_stage(recs[2]) == 0



def test_r31br_stage_descriptions_are_defined_for_runtime_stages() -> None:
    assert set(STAGE_RUNTIME_ROLE_DESCRIPTIONS) == {"stage0_relevance", "stage1_long", "stage2_final"}
    assert "Быстрый relevance-screen" in describe_runtime_stage("stage0_relevance")
    assert "длинные дорожные" in describe_runtime_stage("stage1_long").lower()
    assert "финальная robustness" in describe_runtime_stage("stage2_final").lower()



def test_r31br_suite_apply_uses_pending_selection_and_rerun_instead_of_direct_widget_write() -> None:
    src = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    assert '_queue_suite_selected_id(sid)' in src
    assert 'st.session_state["ui_suite_selected_id"] = sid' not in src
    assert 'st.rerun()' in src
    assert 'st.session_state["_ui_suite_autosave_pending"] = True' in src



def test_r31br_suite_filters_use_pending_flags_and_stage_extend_queue() -> None:
    src = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    assert 'st.session_state["_ui_suite_filters_reset_pending"] = True' in src
    assert 'st.session_state["_ui_suite_show_all_pending"] = True' in src
    assert 'st.session_state["_ui_suite_stage_filter"] = stages' not in src
    assert '_queue_stage_filter_extend(stage_i)' in src
    assert 'st.session_state["ui_suite_stage_filter"] = sorted(set(cur))' not in src



def test_r31br_ui_filters_use_inferred_stage_logic_and_show_stage_help() -> None:
    src = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    assert 'infer_suite_stage(_row.to_dict())' in src
    assert 'Логика staged optimization: S0 — быстрый relevance-screen; S1 — длинные дорожные/манёвренные тесты; S2 — финальная robustness-стадия.' in src
    assert 'stage 1 не должен молча переписываться в 0' in src
    assert 'st.caption(describe_runtime_stage(stage_name))' in src



def test_r31br_stage_plan_preview_includes_human_description() -> None:
    src = (ROOT / "pneumo_solver_ui" / "opt_stage_runner_v1.py").read_text(encoding="utf-8")
    assert '"description": describe_runtime_stage(stg.get("name"))' in src
