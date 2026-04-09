from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_results_event_runtime_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_event_runtime_helpers.py"
RUNTIME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_runtime_helpers.py"


def test_compute_results_events_builds_runtime_kwargs_for_app_like_view() -> None:
    calls: list[dict[str, object]] = []

    result = helpers.compute_results_events(
        compute_events_fn=lambda **kwargs: calls.append(kwargs) or [{"kind": "warn"}],
        base_override={"alpha": 1},
        p_atm=101325.0,
        session_state={
            "events_show": True,
            "events_vacuum_min_atm": -0.3,
            "events_pmax_margin_atm": 0.15,
            "events_chatter_toggles": 8,
        },
        df_main="df_main",
        df_p="df_p",
        df_open="df_open",
        test={"test": 1},
        vacuum_state_key="events_vacuum_min_atm",
        pmax_state_key="events_pmax_margin_atm",
        vacuum_kwarg_name="vacuum_min_gauge_atm",
        pmax_kwarg_name="pmax_margin_atm",
    )

    assert result == [{"kind": "warn"}]
    assert calls == [
        {
            "df_main": "df_main",
            "df_p": "df_p",
            "df_open": "df_open",
            "params_abs": {"alpha": 1, "_P_ATM": 101325.0},
            "test": {"test": 1},
            "chatter_window_s": 0.25,
            "chatter_toggle_count": 8,
            "max_events": 240,
            "vacuum_min_gauge_atm": -0.3,
            "pmax_margin_atm": 0.15,
        }
    ]


def test_compute_results_events_handles_disabled_and_exceptions() -> None:
    disabled = helpers.compute_results_events(
        compute_events_fn=lambda **kwargs: [{"kind": "never"}],
        base_override={"beta": 2},
        p_atm=100000.0,
        session_state={"events_show": False},
        df_main="df_main",
        df_p="df_p",
        df_open="df_open",
        test={},
        vacuum_state_key="events_vacuum_min_bar",
        pmax_state_key="events_pmax_margin_bar",
        vacuum_kwarg_name="vacuum_min_gauge_bar",
        pmax_kwarg_name="pmax_margin_bar",
    )
    errored = helpers.compute_results_events(
        compute_events_fn=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
        base_override={"beta": 2},
        p_atm=100000.0,
        session_state={"events_show": True},
        df_main="df_main",
        df_p="df_p",
        df_open="df_open",
        test={},
        vacuum_state_key="events_vacuum_min_bar",
        pmax_state_key="events_pmax_margin_bar",
        vacuum_kwarg_name="vacuum_min_gauge_bar",
        pmax_kwarg_name="pmax_margin_bar",
    )

    assert disabled == []
    assert errored == []


def test_entrypoints_use_shared_results_event_runtime_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    runtime_text = RUNTIME_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_event_runtime_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_results_event_runtime_helpers import (" not in heavy_text
    assert "compute_results_events(" not in app_text
    assert "compute_results_events(" not in heavy_text
    assert "events_list = compute_events(" not in app_text
    assert "events_list = compute_events(" not in heavy_text
    assert 'params_for_events = dict(base_override)' not in app_text
    assert 'params_for_events = dict(base_override)' not in heavy_text
    assert 'params_for_events["_P_ATM"] = float(P_ATM)' not in app_text
    assert 'params_for_events["_P_ATM"] = float(P_ATM)' not in heavy_text
    assert "def compute_results_events(" in helper_text
    assert "compute_results_events(" in runtime_text
    assert 'params_for_events["_P_ATM"] = float(p_atm)' in helper_text
