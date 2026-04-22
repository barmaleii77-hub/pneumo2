from __future__ import annotations

from types import SimpleNamespace

from pneumo_solver_ui.tools import dist_opt_coordinator as coord


def _args(*, proposer: str = "auto", n_init: int = 0, min_feasible: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        proposer=str(proposer),
        n_init=int(n_init),
        min_feasible=int(min_feasible),
    )


def test_r31dv_auto_mode_uses_default_n_init_floor_10_and_stays_random_until_ready() -> None:
    mode = coord.resolve_proposer_mode(
        _args(proposer="auto", n_init=0, min_feasible=0),
        done_n=9,
        feasible_n=0,
        dim=2,
    )
    assert mode["requested"] == "auto"
    assert mode["mode"] == "random"
    assert mode["n_init"] == 10
    assert mode["ready_by_done"] is False
    assert mode["ready_by_feasible"] is True


def test_r31dv_auto_mode_uses_dim_based_n_init_when_dim_large() -> None:
    mode = coord.resolve_proposer_mode(
        _args(proposer="auto", n_init=0, min_feasible=0),
        done_n=26,
        feasible_n=0,
        dim=12,
    )
    assert mode["requested"] == "auto"
    assert mode["mode"] == "qnehvi"
    assert mode["n_init"] == 26
    assert mode["ready_by_done"] is True
    assert mode["ready_by_feasible"] is True


def test_r31dv_auto_mode_respects_min_feasible_gate() -> None:
    mode = coord.resolve_proposer_mode(
        _args(proposer="auto", n_init=5, min_feasible=3),
        done_n=5,
        feasible_n=2,
        dim=2,
    )
    assert mode["mode"] == "random"
    assert mode["n_init"] == 5
    assert mode["min_feasible"] == 3
    assert mode["ready_by_done"] is True
    assert mode["ready_by_feasible"] is False


def test_r31dv_qnehvi_requested_degrades_to_random_when_gate_not_ready() -> None:
    mode = coord.resolve_proposer_mode(
        _args(proposer="qnehvi", n_init=8, min_feasible=1),
        done_n=7,
        feasible_n=1,
        dim=4,
    )
    assert mode["requested"] == "qnehvi"
    assert mode["mode"] == "random"
    assert mode["portfolio_enabled"] is False
    assert mode["ready_by_done"] is False
    assert mode["ready_by_feasible"] is True


def test_r31dv_portfolio_requested_keeps_portfolio_mode_when_ready() -> None:
    mode = coord.resolve_proposer_mode(
        _args(proposer="portfolio", n_init=3, min_feasible=2),
        done_n=3,
        feasible_n=2,
        dim=3,
    )
    assert mode["requested"] == "portfolio"
    assert mode["mode"] == "portfolio"
    assert mode["portfolio_enabled"] is True
    assert mode["ready_by_done"] is True
    assert mode["ready_by_feasible"] is True


def test_r31dv_portfolio_requested_degrades_to_random_and_disables_blend_when_not_ready() -> None:
    mode = coord.resolve_proposer_mode(
        _args(proposer="portfolio", n_init=3, min_feasible=2),
        done_n=3,
        feasible_n=1,
        dim=3,
    )
    assert mode["requested"] == "portfolio"
    assert mode["mode"] == "random"
    assert mode["portfolio_enabled"] is False
    assert mode["ready_by_done"] is True
    assert mode["ready_by_feasible"] is False


def test_r31dv_min_feasible_is_clamped_to_zero() -> None:
    mode = coord.resolve_proposer_mode(
        _args(proposer="auto", n_init=4, min_feasible=-11),
        done_n=4,
        feasible_n=0,
        dim=3,
    )
    assert mode["min_feasible"] == 0
    assert mode["ready_by_feasible"] is True
    assert mode["mode"] == "qnehvi"


def test_r31dv_requested_mode_is_trimmed_and_lowercased_for_portfolio() -> None:
    mode = coord.resolve_proposer_mode(
        _args(proposer="  PoRtFoLiO  ", n_init=2, min_feasible=1),
        done_n=2,
        feasible_n=1,
        dim=2,
    )
    assert mode["requested"] == "portfolio"
    assert mode["mode"] == "portfolio"
    assert mode["portfolio_enabled"] is True


def test_r31dv_requested_mode_is_trimmed_and_lowercased_for_qnehvi() -> None:
    mode = coord.resolve_proposer_mode(
        _args(proposer="  QNEHVI  ", n_init=2, min_feasible=1),
        done_n=2,
        feasible_n=1,
        dim=2,
    )
    assert mode["requested"] == "qnehvi"
    assert mode["mode"] == "qnehvi"
    assert mode["portfolio_enabled"] is False


def test_r31dv_unknown_requested_mode_degrades_to_random_after_normalization() -> None:
    mode = coord.resolve_proposer_mode(
        _args(proposer="  WeirdCustomMode  ", n_init=9, min_feasible=3),
        done_n=1,
        feasible_n=0,
        dim=2,
    )
    assert mode["requested"] == "weirdcustommode"
    assert mode["mode"] == "random"
    assert mode["portfolio_enabled"] is False
    assert mode["unsupported_requested"] is True
    assert mode["ready_by_done"] is False
    assert mode["ready_by_feasible"] is False
