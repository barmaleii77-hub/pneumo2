from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.calibration.param_staging_v3_influence import _sys_score_from_influence
from pneumo_solver_ui.opt_stage_runner_v1 import (
    build_param_staging_cmd,
    build_system_influence_cmd,
    expand_suite_by_scenarios,
    staging_plan_ready,
)
from pneumo_solver_ui.opt_worker_v3_margins_energy import build_test_suite


def test_sys_score_from_influence_accepts_current_record_list_schema() -> None:
    sysinf = {
        "params": [
            {
                "param": "p_fast",
                "score": 3.25,
                "elas_Kphi": 1.0,
            },
            {
                "param": "p_mid",
                "elas_min_bottleneck_mdot": -0.7,
                "elas_Ktheta": 0.2,
            },
            {
                "param": "p_legacy_shape",
                "elasticity": {"Kphi": -1.5, "min_bottleneck_mdot": 0.1},
            },
        ]
    }
    scores = _sys_score_from_influence(sysinf)
    assert scores["p_fast"] == 3.25
    assert scores["p_mid"] > 0.8
    assert scores["p_legacy_shape"] > 1.5


def test_build_system_influence_cmd_passes_model_and_never_uses_out_json() -> None:
    worker = Path("/proj/pneumo_solver_ui/opt_worker_v3_margins_energy.py")
    cmd = build_system_influence_cmd(
        worker_path=worker,
        staging_dir=Path("/run/staging"),
        model_path=Path("/proj/pneumo_solver_ui/model_pneumo_v9_doublewishbone_camozzi.py"),
        base_json=Path("/run/base.json"),
        ranges_json=Path("/run/ranges.json"),
        eps_rel=3e-3,
        adaptive_eps=True,
        adaptive_eps_grid="1e-4,1e-3,1e-2",
    )
    assert "--model" in cmd
    assert "/proj/pneumo_solver_ui/model_pneumo_v9_doublewishbone_camozzi.py" in cmd
    assert "--out_json" not in cmd
    assert "--run_dir" in cmd
    assert "--eps_rel" in cmd
    assert "0.003" in cmd
    assert "--adaptive_eps" in cmd
    assert "--adaptive_eps_grid" in cmd


def test_build_param_staging_cmd_points_to_current_contract_files() -> None:
    worker = Path("/proj/pneumo_solver_ui/opt_worker_v3_margins_energy.py")
    cmd = build_param_staging_cmd(
        worker_path=worker,
        ranges_json=Path("/run/ranges.json"),
        system_influence_json=Path("/run/staging/system_influence.json"),
        staging_dir=Path("/run/staging"),
    )
    assert "--fit_ranges_json" in cmd
    assert "/run/ranges.json" in cmd
    assert "--system_influence_json" in cmd
    assert "/run/staging/system_influence.json" in cmd
    assert "--out_dir" in cmd
    assert "/run/staging" in cmd


def test_staging_plan_ready_uses_stages_influence_not_legacy_plan_name(tmp_path: Path) -> None:
    stg = tmp_path / "staging"
    stg.mkdir()
    (stg / "plan.json").write_text("{}", encoding="utf-8")
    assert staging_plan_ready(stg) is False
    (stg / "stages_influence.json").write_text("{}", encoding="utf-8")
    (stg / "fit_ranges_stage_00.json").write_text("{}", encoding="utf-8")
    assert staging_plan_ready(stg) is True


def test_expand_suite_by_scenarios_accepts_russian_name_key() -> None:
    suite = [{"имя": "ring_test_01", "тип": "maneuver_csv", "включен": True, "стадия": 0}]
    expanded = expand_suite_by_scenarios(suite, {"nominal": {}}, {}, scenario_ids=["nominal"])
    assert len(expanded) == 1
    assert expanded[0]["имя"] == "ring_test_01"
    assert expanded[0]["name"] == "ring_test_01"


def test_build_test_suite_fails_fast_for_explicit_empty_suite() -> None:
    try:
        build_test_suite({
            "suite": [],
            "__suite_explicit__": True,
            "__suite_json_path__": "/tmp/empty_suite.json",
        })
    except ValueError as exc:
        assert "suite_json" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("explicit empty suite_json must fail fast")


def test_build_test_suite_fails_fast_for_explicit_suite_without_enabled_tests() -> None:
    try:
        build_test_suite({
            "suite": [{"имя": "ring_test_01", "тип": "maneuver_csv", "включен": False}],
            "__suite_explicit__": True,
            "__suite_json_path__": "/tmp/disabled_suite.json",
        })
    except ValueError as exc:
        assert "ни одного включённого" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("explicit suite_json with zero enabled tests must fail fast")
