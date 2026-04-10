from __future__ import annotations

from pneumo_solver_ui.tools import property_invariants as mod


class _WorkerEmptySuite:
    @staticmethod
    def build_test_suite(cfg):
        if cfg:
            return []
        return [
            (
                "микро_синфаза",
                {"road_func": object()},
                0.005,
                1.2,
                {},
            )
        ]

    @staticmethod
    def make_test_micro_sin(A: float, f: float):
        return {"A": float(A), "f": float(f)}


class _WorkerNoSuitesAtAll:
    @staticmethod
    def build_test_suite(cfg):
        return []

    @staticmethod
    def make_test_micro_sin(A: float, f: float):
        return {"A": float(A), "f": float(f)}


def test_pick_smoke_test_falls_back_to_builtin_suite_when_explicit_suite_empty() -> None:
    name, test_dict, dt, t_end = mod._pick_smoke_test(_WorkerEmptySuite(), {"suite": []})
    assert name == "микро_синфаза"
    assert isinstance(test_dict, dict)
    assert dt == 0.005
    assert t_end == 1.2


def test_pick_smoke_test_synthesizes_micro_sine_when_worker_returns_no_tests() -> None:
    name, test_dict, dt, t_end = mod._pick_smoke_test(_WorkerNoSuitesAtAll(), {"suite": []})
    assert name == "микро_синфаза_fallback"
    assert test_dict == {"A": 0.004, "f": 3.0}
    assert dt == 0.003
    assert t_end == 1.6
