from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_results_playhead_jump_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_playhead_jump_helpers.py"
RUNTIME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_runtime_helpers.py"


def test_apply_results_playhead_request_x_updates_state_to_nearest_sample() -> None:
    state: dict[str, object] = {"playhead_request_x": 0.91}
    calls: list[int] = []

    jump_index = helpers.apply_results_playhead_request_x(
        session_state=state,
        time_s=[0.0, 0.5, 1.0, 2.0],
        make_playhead_jump_command_fn=lambda idx: calls.append(idx) or {"set_idx": idx},
    )

    assert jump_index == 2
    assert calls == [2]
    assert "playhead_request_x" not in state
    assert state["playhead_idx"] == 2
    assert state["playhead_t"] == 1.0
    assert state["playhead_cmd"] == {"set_idx": 2}


def test_apply_results_playhead_request_x_handles_missing_time_or_bad_value() -> None:
    empty_state: dict[str, object] = {"playhead_request_x": 1.0}
    bad_state: dict[str, object] = {"playhead_request_x": "oops"}

    assert (
        helpers.apply_results_playhead_request_x(
            session_state=empty_state,
            time_s=[],
            make_playhead_jump_command_fn=lambda idx: {"set_idx": idx},
        )
        is None
    )
    assert (
        helpers.apply_results_playhead_request_x(
            session_state=bad_state,
            time_s=[0.0, 1.0],
            make_playhead_jump_command_fn=lambda idx: {"set_idx": idx},
        )
        is None
    )

    assert "playhead_request_x" not in empty_state
    assert "playhead_request_x" not in bad_state
    assert "playhead_idx" not in bad_state


def test_entrypoints_use_shared_results_playhead_jump_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    runtime_text = RUNTIME_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_playhead_jump_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_results_playhead_jump_helpers import (" not in heavy_text
    assert "apply_results_playhead_request_x(" not in app_text
    assert "apply_results_playhead_request_x(" not in heavy_text
    assert 'req_x = st.session_state.pop("playhead_request_x", None)' not in app_text
    assert 'req_x = st.session_state.pop("playhead_request_x", None)' not in heavy_text
    assert "j = int(np.argmin(np.abs(arr - req_x_f)))" not in app_text
    assert "j = int(np.argmin(np.abs(arr - req_x_f)))" not in heavy_text
    assert "st.session_state[\"playhead_cmd\"] = make_playhead_jump_command(j)" not in app_text
    assert "st.session_state[\"playhead_cmd\"] = make_playhead_jump_command(j)" not in heavy_text
    assert "def apply_results_playhead_request_x(" in helper_text
    assert "apply_results_playhead_request_x(" in runtime_text
    assert "jump_index = int(np.argmin(np.abs(arr - req_x_f)))" in helper_text
