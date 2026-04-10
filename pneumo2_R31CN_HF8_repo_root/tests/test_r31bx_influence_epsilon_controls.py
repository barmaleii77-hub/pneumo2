from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.calibration.system_influence_report_v1 import (
    _parse_eps_grid,
    _select_adaptive_eps_candidate,
)
from pneumo_solver_ui.optimization_defaults import (
    DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID,
    DIAGNOSTIC_INFLUENCE_EPS_REL,
    influence_eps_grid_text,
)


def test_parse_eps_grid_includes_requested_eps_and_sorts() -> None:
    grid = _parse_eps_grid("1e-2, 1e-4, 3e-3", requested_eps_rel=3e-4)
    assert grid == [1e-4, 3e-4, 3e-3, 1e-2]


def test_select_adaptive_eps_candidate_prefers_stable_local_plateau() -> None:
    choice = _select_adaptive_eps_candidate(
        [
            {"eps_rel": 1e-4, "elasticities": {"elas_Kphi": 4.0, "elas_Ktheta": 4.0}},
            {"eps_rel": 3e-4, "elasticities": {"elas_Kphi": 1.0, "elas_Ktheta": 1.0}},
            {"eps_rel": 1e-3, "elasticities": {"elas_Kphi": 1.05, "elas_Ktheta": 0.95}},
            {"eps_rel": 3e-3, "elasticities": {"elas_Kphi": 1.02, "elas_Ktheta": 0.98}},
            {"eps_rel": 1e-2, "elasticities": {"elas_Kphi": 2.0, "elas_Ktheta": 2.0}},
        ],
        requested_eps_rel=1e-3,
    )
    assert float(choice["eps_rel"]) == 1e-3
    assert float(choice["adaptive_stability_loss"]) >= 0.0


def test_ui_and_stage_runner_sources_expose_influence_eps_controls() -> None:
    root = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
    ui_src = (root / "optimization_stage_runner_config_ui.py").read_text(encoding="utf-8")
    stage_src = (root / "opt_stage_runner_v1.py").read_text(encoding="utf-8")
    assert '"System Influence eps_rel"' in ui_src
    assert '"Adaptive epsilon для System Influence"' in ui_src
    assert '"--eps_rel"' in stage_src
    assert '"--adaptive_influence_eps"' in stage_src


def test_influence_default_grid_text_matches_constants() -> None:
    assert DIAGNOSTIC_INFLUENCE_EPS_REL == 1e-2
    assert DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID == (1e-4, 3e-4, 1e-3, 3e-3, 1e-2)
    assert influence_eps_grid_text() == "0.0001, 0.0003, 0.001, 0.003, 0.01"
