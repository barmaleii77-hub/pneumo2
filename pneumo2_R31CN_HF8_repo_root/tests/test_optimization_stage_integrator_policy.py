from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.opt_stage_runner_v1 import (
    build_stage_runtime_base_params,
    materialize_stage_runtime_base_json,
)


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def test_stage_runtime_base_policy_enables_err_control_only_for_long_stages() -> None:
    base = {
        "интегратор_контроль_локальной_ошибки": False,
        "интегратор_rtol": 1e-3,
        "интегратор_atol": 1e-7,
        "интегратор_mass_rtol_scale_factor": 2.0,
        "интегратор_err_group_weight_mass": 0.92,
        "пружина_масштаб": 0.18,
    }

    s0 = build_stage_runtime_base_params(base, "stage0_relevance")
    s1 = build_stage_runtime_base_params(base, "stage1_long")
    s2 = build_stage_runtime_base_params(base, "stage2_final")

    assert bool(s0["интегратор_контроль_локальной_ошибки"]) is False
    assert bool(s1["интегратор_контроль_локальной_ошибки"]) is True
    assert bool(s2["интегратор_контроль_локальной_ошибки"]) is True
    assert float(s1["интегратор_rtol"]) == 1e-3
    assert float(s1["интегратор_atol"]) == 1e-7
    assert float(s1["интегратор_mass_rtol_scale_factor"]) == 2.0
    assert float(s1["интегратор_err_group_weight_mass"]) == 0.92
    assert float(s2["пружина_масштаб"]) == 0.18


def test_materialize_stage_runtime_base_json_writes_effective_base_and_policy(tmp_path: Path) -> None:
    base = {
        "интегратор_контроль_локальной_ошибки": False,
        "интегратор_rtol": 1e-3,
        "интегратор_atol": 1e-7,
        "интегратор_mass_rtol_scale_factor": 2.0,
        "интегратор_err_group_weight_mass": 0.92,
    }

    base_json, policy = materialize_stage_runtime_base_json(
        tmp_path,
        base_params=base,
        stage_name="stage2_final",
    )

    payload = json.loads(base_json.read_text(encoding="utf-8"))
    policy_payload = json.loads((tmp_path / "integrator_runtime_policy.json").read_text(encoding="utf-8"))

    assert base_json == (tmp_path / "base_effective.json")
    assert bool(payload["интегратор_контроль_локальной_ошибки"]) is True
    assert bool(policy["интегратор_контроль_локальной_ошибки"]) is True
    assert bool(policy_payload["интегратор_контроль_локальной_ошибки"]) is True
    assert float(policy_payload["интегратор_err_group_weight_mass"]) == 0.92


def test_stage_runner_source_uses_stage_specific_base_json_for_worker() -> None:
    src = (UI_ROOT / "opt_stage_runner_v1.py").read_text(encoding="utf-8")

    assert "materialize_stage_runtime_base_json(" in src
    assert "str(stage_base_json)" in src
    assert '"stage_integrator_runtime": dict(stage_integrator_runtime)' in src
