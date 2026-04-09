from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_results_playhead_reset_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_playhead_reset_helpers.py"
RUNTIME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_runtime_helpers.py"


def test_reset_results_playhead_on_dataset_change_updates_state_and_logs() -> None:
    state: dict[str, object] = {}
    calls: list[tuple[str, dict[str, object]]] = []

    changed = helpers.reset_results_playhead_on_dataset_change(
        session_state=state,
        cache_key="cache-1",
        dataset_id_ui="cache-1__nonce",
        time_s=[0.5, 1.0],
        make_playhead_reset_command_fn=lambda: {"set_idx": 0},
        log_event_fn=lambda event, **kwargs: calls.append((event, kwargs)),
    )

    assert changed is True
    assert state["playhead_active_dataset"] == "cache-1"
    assert state["playhead_idx"] == 0
    assert state["playhead_t"] == 0.5
    assert state["playhead_cmd"] == {"set_idx": 0}
    assert calls == [("playhead_reset", {"dataset_id": "cache-1__nonce"})]


def test_reset_results_playhead_on_dataset_change_is_noop_for_same_dataset() -> None:
    state: dict[str, object] = {
        "playhead_active_dataset": "cache-1",
        "playhead_idx": 7,
        "playhead_t": 2.0,
    }
    calls: list[tuple[str, dict[str, object]]] = []

    changed = helpers.reset_results_playhead_on_dataset_change(
        session_state=state,
        cache_key="cache-1",
        dataset_id_ui="cache-1__nonce",
        time_s=[0.5, 1.0],
        make_playhead_reset_command_fn=lambda: {"set_idx": 0},
        log_event_fn=lambda event, **kwargs: calls.append((event, kwargs)),
    )

    assert changed is False
    assert state["playhead_idx"] == 7
    assert state["playhead_t"] == 2.0
    assert calls == []


def test_entrypoints_use_shared_results_playhead_reset_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    runtime_text = RUNTIME_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_playhead_reset_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_results_playhead_reset_helpers import (" not in heavy_text
    assert "reset_results_playhead_on_dataset_change(" not in app_text
    assert "reset_results_playhead_on_dataset_change(" not in heavy_text
    assert 'if st.session_state.get("playhead_active_dataset") != cache_key:' not in app_text
    assert 'if st.session_state.get("playhead_active_dataset") != cache_key:' not in heavy_text
    assert 'st.session_state["playhead_cmd"] = make_playhead_reset_command()' not in app_text
    assert 'st.session_state["playhead_cmd"] = make_playhead_reset_command()' not in heavy_text
    assert 'log_event("playhead_reset", dataset_id=str(dataset_id_ui))' not in app_text
    assert 'log_event("playhead_reset", dataset_id=str(dataset_id_ui))' not in heavy_text
    assert "def reset_results_playhead_on_dataset_change(" in helper_text
    assert "reset_results_playhead_on_dataset_change(" in runtime_text
