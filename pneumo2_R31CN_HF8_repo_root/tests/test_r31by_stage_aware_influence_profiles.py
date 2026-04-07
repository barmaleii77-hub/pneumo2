from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.calibration.system_influence_report_v1 import _select_adaptive_eps_candidate
from pneumo_solver_ui.optimization_defaults import (
    build_stage_aware_influence_profile,
    stage_aware_influence_profiles_text,
)
from pneumo_solver_ui.opt_stage_runner_v1 import build_system_influence_cmd, stage_aware_influence_report_matches



def test_stage_aware_profiles_bias_grid_by_runtime_stage() -> None:
    stage0 = build_stage_aware_influence_profile(
        "stage0_relevance",
        requested_eps_rel=1e-2,
        base_grid=(1e-4, 3e-4, 1e-3, 3e-3, 1e-2),
    )
    stage1 = build_stage_aware_influence_profile(
        "stage1_long",
        requested_eps_rel=1e-2,
        base_grid=(1e-4, 3e-4, 1e-3, 3e-3, 1e-2),
    )
    stage2 = build_stage_aware_influence_profile(
        "stage2_final",
        requested_eps_rel=1e-2,
        base_grid=(1e-4, 3e-4, 1e-3, 3e-3, 1e-2),
    )
    assert stage0["adaptive_strategy"] == "coarse"
    assert stage1["adaptive_strategy"] == "balanced"
    assert stage2["adaptive_strategy"] == "fine"
    assert stage0["adaptive_grid"] == [1e-3, 3e-3, 1e-2, 3e-2]
    assert stage1["adaptive_grid"] == [3e-4, 1e-3, 3e-3, 1e-2, 3e-2]
    assert stage2["adaptive_grid"] == [1e-4, 3e-4, 1e-3, 3e-3, 1e-2]



def test_stage_aware_profiles_text_is_human_readable() -> None:
    text = stage_aware_influence_profiles_text(requested_eps_rel=1e-2)
    assert "stage0_relevance=" in text
    assert "[coarse]" in text
    assert "stage2_final=" in text
    assert "[fine]" in text



def test_select_adaptive_eps_candidate_supports_stage_specific_tiebreak_strategy() -> None:
    candidates = [
        {"eps_rel": 3e-4, "elasticities": {"elas_Kphi": 1.00, "elas_Ktheta": 1.00}},
        {"eps_rel": 1e-3, "elasticities": {"elas_Kphi": 1.00, "elas_Ktheta": 1.00}},
        {"eps_rel": 3e-3, "elasticities": {"elas_Kphi": 1.00, "elas_Ktheta": 1.00}},
    ]
    coarse = _select_adaptive_eps_candidate(candidates, requested_eps_rel=1e-3, strategy="coarse")
    balanced = _select_adaptive_eps_candidate(candidates, requested_eps_rel=1e-3, strategy="balanced")
    fine = _select_adaptive_eps_candidate(candidates, requested_eps_rel=1e-3, strategy="fine")
    assert float(coarse["eps_rel"]) == 3e-3
    assert float(balanced["eps_rel"]) == 1e-3
    assert float(fine["eps_rel"]) == 3e-4



def test_stage_runner_passes_stage_name_and_strategy_to_system_influence() -> None:
    worker = Path("/proj/pneumo_solver_ui/opt_worker_v3_margins_energy.py")
    cmd = build_system_influence_cmd(
        worker_path=worker,
        staging_dir=Path("/run/staging/stage_aware/stage0_relevance"),
        model_path=Path("/proj/pneumo_solver_ui/model_pneumo_v9_doublewishbone_camozzi.py"),
        base_json=Path("/run/base.json"),
        ranges_json=Path("/run/staging/fit_ranges_stage_00.json"),
        eps_rel=1e-2,
        adaptive_eps=True,
        adaptive_eps_grid="0.001,0.003,0.01,0.03",
        adaptive_eps_strategy="coarse",
        stage_name="stage0_relevance",
    )
    assert "--adaptive_eps_strategy" in cmd
    assert "coarse" in cmd
    assert "--stage_name" in cmd
    assert "stage0_relevance" in cmd



def test_stage_aware_report_match_detects_strategy_and_stage(tmp_path: Path) -> None:
    report = tmp_path / "system_influence.json"
    report.write_text(
        """
        {
          "config": {
            "requested_eps_rel": 0.01,
            "adaptive_eps_grid": [0.001, 0.003, 0.01, 0.03],
            "adaptive_eps_strategy": "coarse",
            "stage_name": "stage0_relevance"
          }
        }
        """.strip(),
        encoding="utf-8",
    )
    assert stage_aware_influence_report_matches(
        report,
        requested_eps_rel=1e-2,
        adaptive_grid=(1e-3, 3e-3, 1e-2, 3e-2),
        adaptive_strategy="coarse",
        stage_name="stage0_relevance",
    )
    assert not stage_aware_influence_report_matches(
        report,
        requested_eps_rel=1e-2,
        adaptive_grid=(1e-4, 3e-4, 1e-3),
        adaptive_strategy="fine",
        stage_name="stage2_final",
    )
