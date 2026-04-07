from __future__ import annotations

from pneumo_solver_ui.tools import dist_opt_coordinator as coord
from pneumo_solver_ui.pneumo_dist import trial_hash as inner_trial_hash


def test_r31cp_dist_opt_coordinator_hash_params_accepts_float_ndigits_kw() -> None:
    params = {"a": 0.12345678901234567, "nested": {"b": [1.0, 2.0, 3.141592653589793]}}
    h_default = coord.hash_params(params)
    h_kw = coord.hash_params(params, float_ndigits=12)
    assert isinstance(h_kw, str) and len(h_kw) == 64
    assert h_kw == h_default


def test_r31cp_inner_trial_hash_backcompat_surface_accepts_float_ndigits_kw() -> None:
    params = {"x": 1.2345678901234567, "y": {"z": 9.876543210987654}}
    h1 = inner_trial_hash.hash_params(params, float_ndigits=12)
    h2 = inner_trial_hash.stable_hash_params(params, float_ndigits=12)
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) == 64


def test_r31cp_inner_hash_problem_accepts_float_ndigits_kw() -> None:
    spec = inner_trial_hash.make_problem_spec(
        model_path=__file__,
        worker_path=__file__,
        base_json='',
        ranges_json='',
        suite_json='',
        cfg={},
        include_file_hashes=False,
    )
    digest = inner_trial_hash.hash_problem(spec, float_ndigits=12)
    assert isinstance(digest, str) and len(digest) == 64
