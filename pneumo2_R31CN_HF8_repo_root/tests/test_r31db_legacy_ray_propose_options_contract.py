from __future__ import annotations

from types import SimpleNamespace

from pneumo_solver_ui.tools.run_ray_distributed_opt import _make_propose_options


def test_r31db_ray_make_propose_options_uses_current_field_names() -> None:
    args = SimpleNamespace(
        botorch=True,
        seed=11,
        n_init=19,
        feasible_tol=1e-7,
        min_feasible=5,
        heuristic_pool_size=512,
        heuristic_explore=0.35,
        no_constraints=True,
    )
    opt = _make_propose_options(args)

    assert str(opt.method) == "botorch"
    assert bool(opt.allow_botorch) is True
    assert int(opt.seed) == 11
    assert int(opt.n_init) == 19
    assert abs(float(opt.feasible_tol) - 1e-7) < 1e-12
    assert int(opt.min_feasible) == 5
    assert int(opt.heuristic_pool_size) == 512
    assert abs(float(opt.heuristic_explore) - 0.35) < 1e-12
    assert bool(opt.use_constraint_model) is False


def test_r31db_ray_make_propose_options_defaults_when_fields_missing() -> None:
    args = SimpleNamespace(
        botorch=False,
        seed=0,
        n_init=0,
        feasible_tol=1e-9,
        no_constraints=False,
    )
    opt = _make_propose_options(args)
    assert str(opt.method) == "auto"
    assert bool(opt.allow_botorch) is False
    assert int(opt.min_feasible) == 8
    assert int(opt.heuristic_pool_size) == 256
    assert abs(float(opt.heuristic_explore) - 0.70) < 1e-12
    assert bool(opt.use_constraint_model) is True
