from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pneumo_solver_ui.optimization_coordinator_handoff import (
    COORDINATOR_HANDOFF_SEED_FILENAME,
    materialize_coordinator_handoff_plan,
)


def test_materialize_coordinator_handoff_plan_writes_seeded_full_ring_payload(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    suite_path = tmp_path / "suite_auto_ring.json"
    suite_path.write_text(
        json.dumps(
            [
                {"имя": "ringfrag_roll", "включен": True, "стадия": 1},
                {"имя": "ring_auto_full", "включен": True, "стадия": 2},
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    base_json = tmp_path / "base.json"
    base_json.write_text("{}", encoding="utf-8")
    ranges_json = tmp_path / "ranges.json"
    ranges_json.write_text(
        json.dumps({"foo": [0.0, 10.0], "bar": [0.0, 20.0]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    results_csv = tmp_path / "results_all.csv"
    pd.DataFrame(
        [
            {
                "id": 10,
                "candidate_role": "search",
                "meta_source": "search",
                "ошибка": "",
                "штраф_физичности_сумма": 0.0,
                "obj_a": 1.0,
                "obj_b": 2.0,
                "параметр__foo": 2.0,
                "параметр__bar": 3.0,
            },
            {
                "id": 11,
                "candidate_role": "search",
                "meta_source": "search",
                "ошибка": "",
                "штраф_физичности_сумма": 0.0,
                "obj_a": 0.5,
                "obj_b": 1.0,
                "параметр__foo": 1.5,
                "параметр__bar": 4.0,
            },
            {
                "id": 12,
                "candidate_role": "seed",
                "meta_source": "seed_points_json",
                "ошибка": "",
                "штраф_физичности_сумма": 9.0,
                "obj_a": 99.0,
                "obj_b": 99.0,
                "параметр__foo": 9.0,
                "параметр__bar": 9.0,
            },
        ]
    ).to_csv(results_csv, index=False)

    plan_path = materialize_coordinator_handoff_plan(
        run_dir,
        model_path=tmp_path / "model.py",
        worker_path=tmp_path / "worker.py",
        base_json_path=base_json,
        ranges_json_path=ranges_json,
        suite_json_path=suite_path,
        staged_results_csv=results_csv,
        objective_keys=("obj_a", "obj_b"),
        penalty_key="штраф_физичности_сумма",
        stage_tuner_plan={
            "coordinator_handoff": {
                "recommended_proposer": "portfolio",
                "recommended_q": 2,
                "requires_full_ring_validation": True,
            }
        },
        seed_limit=2,
    )

    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    seed_json = Path(payload["seed_json"])
    seed_payload = json.loads(seed_json.read_text(encoding="utf-8"))

    assert seed_json.name == COORDINATOR_HANDOFF_SEED_FILENAME
    assert len(seed_payload) == 2
    assert seed_payload[0]["foo"] == 1.5
    assert payload["suite_analysis"]["family"] == "auto_ring"
    assert payload["recommended_backend"] == "ray"
    assert payload["recommended_proposer"] == "portfolio"
    assert payload["recommended_q"] == 2
    assert payload["recommended_budget"] >= 48
    assert payload["requires_full_ring_validation"] is True
    assert payload["recommendation_reason"]["fragment_count"] == 1
    assert payload["recommendation_reason"]["has_full_ring"] is True
    assert payload["recommendation_reason"]["pipeline_hint"] == "staged_then_coordinator"
    assert payload["recommendation_reason"]["proposer_source"] == "auto_tuner"
    assert payload["recommendation_reason"]["q_source"] == "auto_tuner"
    assert payload["recommendation_reason"]["seed_bridge"]["staged_rows_total"] == 3
    assert payload["recommendation_reason"]["seed_bridge"]["staged_rows_ok"] == 3
    assert payload["recommendation_reason"]["seed_bridge"]["promotable_rows"] == 3
    assert payload["recommendation_reason"]["seed_bridge"]["selection_pool"] == "promotable"
    assert payload["recommendation_reason"]["seed_bridge"]["unique_param_candidates"] == 3
    assert payload["recommendation_reason"]["seed_bridge"]["seed_count"] == 2
    assert payload["recommendation_reason"]["budget_formula"]["full_ring_bonus"] == 24
    assert "--seed-json" in payload["cmd_args"]
    assert "portfolio" in payload["cmd_args"]
    assert "ring_auto_full" not in json.dumps(seed_payload, ensure_ascii=False)
