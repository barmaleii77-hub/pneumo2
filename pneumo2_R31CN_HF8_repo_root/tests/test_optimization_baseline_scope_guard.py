from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.opt_stage_runner_v1 import (
    baseline_best_meta_payload,
    baseline_problem_scope_dir,
    decide_baseline_autoupdate,
    load_baseline_best_meta,
)
from pneumo_solver_ui.optimization_defaults import (
    DEFAULT_OPTIMIZATION_OBJECTIVES,
    DIST_OPT_PENALTY_KEY_DEFAULT,
)
from pneumo_solver_ui.optimization_objective_contract import (
    LEGACY_STAGE_RUNNER_OBJECTIVES,
    objective_contract_payload,
    score_payload,
)


OBJECTIVE_KEYS = tuple(str(x) for x in DEFAULT_OPTIMIZATION_OBJECTIVES)
PENALTY_KEY = str(DIST_OPT_PENALTY_KEY_DEFAULT)


def test_baseline_best_meta_payload_keeps_problem_scope_and_contract() -> None:
    contract = objective_contract_payload(
        objective_keys=OBJECTIVE_KEYS,
        penalty_key=PENALTY_KEY,
        source="baseline_scope_test",
    )
    score_obj = score_payload(
        [0.0, 1.0, 2.0, 3.0],
        objective_keys=OBJECTIVE_KEYS,
        penalty_key=PENALTY_KEY,
        source="baseline_scope_test",
    )
    payload = baseline_best_meta_payload(
        problem_hash="ph_scope_123",
        objective_contract=contract,
        run_dir=Path("C:/workspace/opt_runs/staged/p_scope"),
        stage_name="stage2_final",
        score=[0.0, 1.0, 2.0, 3.0],
        score_payload_obj=score_obj,
        params={"foo": 1.25},
    )

    assert payload["problem_hash"] == "ph_scope_123"
    assert payload["objective_contract"]["objective_keys"] == list(OBJECTIVE_KEYS)
    assert payload["score_payload"]["score"] == [0.0, 1.0, 2.0, 3.0]
    assert payload["params"]["foo"] == 1.25


def test_decide_baseline_autoupdate_blocks_explicit_different_problem_hash() -> None:
    prev_score = score_payload(
        [0.0, 0.5, 0.5, 0.5],
        objective_keys=OBJECTIVE_KEYS,
        penalty_key=PENALTY_KEY,
        source="baseline_prev",
    )
    prev_meta = {
        "problem_hash": "ph_old",
        "objective_contract": objective_contract_payload(
            objective_keys=OBJECTIVE_KEYS,
            penalty_key=PENALTY_KEY,
            source="baseline_prev",
        ),
    }

    apply_update, reason = decide_baseline_autoupdate(
        new_score=[0.0, 0.1, 0.1, 0.1],
        objective_keys=OBJECTIVE_KEYS,
        penalty_key=PENALTY_KEY,
        problem_hash="ph_new",
        prev_score_payload=prev_score,
        prev_meta=prev_meta,
    )

    assert apply_update is False
    assert reason == "different_problem_hash"


def test_decide_baseline_autoupdate_keeps_legacy_contract_changed_fallback() -> None:
    prev_score = score_payload(
        [0.0, 0.5, 0.5, 0.5],
        objective_keys=LEGACY_STAGE_RUNNER_OBJECTIVES,
        penalty_key=PENALTY_KEY,
        source="legacy_baseline_prev",
    )

    apply_update, reason = decide_baseline_autoupdate(
        new_score=[0.0, 0.1, 0.1, 0.1],
        objective_keys=OBJECTIVE_KEYS,
        penalty_key=PENALTY_KEY,
        problem_hash="ph_current",
        prev_score_payload=prev_score,
        prev_meta={},
    )

    assert apply_update is True
    assert reason == "objective_contract_changed"


def test_load_baseline_best_meta_falls_back_to_scoped_score_payload_and_scope_dir_is_stable(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir(parents=True)
    raw = score_payload(
        [0.0, 1.0, 2.0, 3.0],
        objective_keys=OBJECTIVE_KEYS,
        penalty_key=PENALTY_KEY,
        source="baseline_score_fallback",
    )
    raw["problem_hash"] = "ph_scope_456"
    raw["run_dir"] = "C:/workspace/opt_runs/staged/p_scope_456"

    meta = load_baseline_best_meta(baseline_dir, prev_score_raw=raw)
    scoped_dir = baseline_problem_scope_dir(baseline_dir, "ph_scope_456")

    assert meta["problem_hash"] == "ph_scope_456"
    assert meta["objective_contract"]["objective_keys"] == list(OBJECTIVE_KEYS)
    assert scoped_dir.name.startswith("p_ph_scope_456")
