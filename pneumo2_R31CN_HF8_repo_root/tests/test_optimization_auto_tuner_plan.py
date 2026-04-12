from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.optimization_auto_ring_suite import (
    materialize_optimization_auto_ring_suite_json,
)
from pneumo_solver_ui.optimization_auto_tuner_plan import (
    is_auto_ring_suite_json,
    materialize_optimization_auto_tuner_plan_json,
    resolve_stage_tuner_stage_config,
)


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def _make_synthetic_ring_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    t = np.arange(0.0, 12.0 + 1e-12, 0.1)
    road = pd.DataFrame(
        {
            "t": t,
            "z0": 0.010 * np.exp(-((t - 1.0) / 0.35) ** 2) - 0.006 * np.exp(-((t - 4.0) / 0.25) ** 2),
            "z1": 0.011 * np.exp(-((t - 1.0) / 0.35) ** 2) + 0.006 * np.exp(-((t - 4.0) / 0.25) ** 2),
            "z2": 0.009 * np.exp(-((t - 1.0) / 0.35) ** 2) + 0.006 * np.exp(-((t - 4.0) / 0.25) ** 2),
            "z3": 0.010 * np.exp(-((t - 1.0) / 0.35) ** 2) - 0.006 * np.exp(-((t - 4.0) / 0.25) ** 2),
        }
    )
    axay = pd.DataFrame(
        {
            "t": t,
            "ax": 1.6 * np.exp(-((t - 9.0) / 0.5) ** 2),
            "ay": 2.4 * np.exp(-((t - 7.0) / 0.5) ** 2),
        }
    )
    spec = {
        "schema_version": "ring_v2",
        "v0_kph": 36.0,
        "dt_s": 0.1,
        "wheelbase_m": 1.6,
        "track_m": 1.1,
        "segments": [
            {"name": "S1_rough", "duration_s": 3.0, "turn_direction": "STRAIGHT", "road": {"mode": "ISO8608"}, "events": []},
            {"name": "S2_turn", "duration_s": 4.0, "turn_direction": "LEFT", "road": {"mode": "SINE"}, "events": []},
            {"name": "S3_exit", "duration_s": 5.0, "turn_direction": "STRAIGHT", "road": {"mode": "ISO8608"}, "events": []},
        ],
        "_generated_meta": {
            "dt_s": 0.1,
            "lap_time_s": 12.0,
            "ring_length_m": 120.0,
            "wheelbase_m": 1.6,
            "track_m": 1.1,
        },
    }
    road_csv = tmp_path / "ring_road.csv"
    axay_csv = tmp_path / "ring_axay.csv"
    scenario_json = tmp_path / "ring_spec.json"
    road.to_csv(road_csv, index=False)
    axay.to_csv(axay_csv, index=False)
    scenario_json.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return road_csv, axay_csv, scenario_json


def test_materialize_auto_tuner_plan_for_auto_ring_suite(tmp_path: Path) -> None:
    road_csv, axay_csv, scenario_json = _make_synthetic_ring_inputs(tmp_path)
    workspace = tmp_path / "workspace"
    suite_path = materialize_optimization_auto_ring_suite_json(
        workspace,
        suite_source_path=UI_ROOT / "default_suite.json",
        road_csv=road_csv,
        axay_csv=axay_csv,
        scenario_json=scenario_json,
        window_s=4.0,
    )

    assert is_auto_ring_suite_json(suite_path) is True

    plan_path = materialize_optimization_auto_tuner_plan_json(
        workspace,
        suite_json_path=suite_path,
        minutes_total=12.0,
        jobs_hint=8,
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    assert plan["suite_family"] == "auto_ring"
    assert plan["coordinator_handoff"]["recommended_proposer"] == "portfolio"
    assert plan["coordinator_handoff"]["requires_full_ring_validation"] is True

    stage0 = resolve_stage_tuner_stage_config(plan, "stage0_relevance")
    stage1 = resolve_stage_tuner_stage_config(plan, "stage1_long")
    stage2 = resolve_stage_tuner_stage_config(plan, "stage2_final")

    assert stage0["warmstart_mode"] == "archive"
    assert stage0["guided_mode"] == "mutation"
    assert stage1["warmstart_mode"] == "surrogate"
    assert int(stage1["surrogate_samples"]) > 0
    assert int(stage1["surrogate_top_k"]) >= 32
    assert stage2["warmstart_mode"] == "surrogate"
    assert int(stage2["surrogate_samples"]) > int(stage1["surrogate_samples"])
    assert int(stage2["surrogate_top_k"]) > int(stage1["surrogate_top_k"])
    assert stage2["env_overrides"]["PNEUMO_GUIDED_MODE"] == "auto"
