from pathlib import Path
from types import ModuleType, SimpleNamespace

import pandas as pd

import pneumo_solver_ui
import pneumo_solver_ui.ui_simulation_helpers as sim_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ENTRYPOINTS = [
    REPO_ROOT / "pneumo_solver_ui" / "app.py",
    REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py",
]


def test_call_simulate_compiles_timeseries_and_logs_dropped_kwargs(monkeypatch) -> None:
    events = []
    monkeypatch.setattr(sim_helpers, "st", SimpleNamespace(session_state={"_log_event_cb": lambda event, **kw: events.append((event, kw))}))

    stub_mod = ModuleType("pneumo_solver_ui.opt_worker_v3_margins_energy")

    def _compile_timeseries_inputs(test):
        out = dict(test)
        out["compiled"] = True
        out["road_dfunc"] = lambda t: t
        return out

    stub_mod._compile_timeseries_inputs = _compile_timeseries_inputs  # type: ignore[attr-defined]
    monkeypatch.setattr(pneumo_solver_ui, "opt_worker_v3_margins_energy", stub_mod, raising=False)

    seen = {}

    class FakeModel:
        @staticmethod
        def simulate(*, params, test, dt, t_end, record_full):
            seen["params"] = params
            seen["test"] = test
            seen["dt"] = dt
            seen["t_end"] = t_end
            seen["record_full"] = record_full
            return "ok"

    result = sim_helpers.call_simulate(
        FakeModel(),
        {"dt": 0.02},
        {"road_csv": "road.csv", "timeseries_strict": True},
        t_end=3.0,
        record_full=True,
        unexpected=123,
    )

    assert result == "ok"
    assert seen["dt"] == 0.02
    assert seen["t_end"] == 3.0
    assert seen["record_full"] is True
    assert seen["test"]["compiled"] is True
    assert callable(seen["test"]["road_func_dot"])
    assert ("call_simulate_dropped_kwargs", {"dropped": ["unexpected"]}) in events


def test_compute_road_profile_and_parse_sim_output_cover_common_formats() -> None:
    class FakeModel:
        @staticmethod
        def _compile_suite_test_inputs(test_obj, params):
            assert test_obj == {"name": "demo"}
            assert params == {"база": 3.2, "колея": 1.8}
            return {"road_func": lambda t: [t, t + 1.0, t + 2.0, t + 3.0]}

    profile = sim_helpers.compute_road_profile_from_suite(
        FakeModel(),
        {"name": "demo"},
        [0.0, 1.0],
        3.2,
        1.8,
        ["FL", "FR", "RL", "RR"],
    )
    assert profile == {
        "FL": [0.0, 1.0],
        "FR": [1.0, 2.0],
        "RL": [2.0, 3.0],
        "RR": [3.0, 4.0],
    }

    df_main = pd.DataFrame({"t": [0.0, 1.0]})
    df_tail = pd.DataFrame({"x": [1]})
    parsed = sim_helpers.parse_sim_output(
        (
            df_main,
            "drossel",
            "energy",
            "nodes",
            "edges",
            "eedges0",
            "egroups0",
            "atm0",
            "p",
            "mdot",
            "open",
            df_tail,
            df_tail,
            df_tail,
        ),
        want_full=True,
    )
    assert parsed["df_main"] is df_main
    assert parsed["df_p"] == "p"
    assert parsed["df_open"] == "open"
    assert parsed["df_Eedges"] is df_tail
    assert parsed["df_Egroups"] is df_tail
    assert parsed["df_atm"] is df_tail

    parsed_dict = sim_helpers.parse_sim_output({"main": "main_df"})
    assert parsed_dict["df_main"] == "main_df"


def test_large_ui_entrypoints_import_shared_simulation_helpers() -> None:
    for path in UI_ENTRYPOINTS:
        src = path.read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_simulation_helpers import (" in src
        assert "def call_simulate(" not in src
        assert "def compute_road_profile_from_suite(" not in src
        assert "def parse_sim_output(" not in src
