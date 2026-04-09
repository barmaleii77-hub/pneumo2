from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_results_runtime_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_runtime_helpers.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []


def test_prepare_results_runtime_coordinates_shared_layers(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        helpers,
        "reset_results_playhead_on_dataset_change",
        lambda **kwargs: calls.append(("reset", kwargs)) or True,
    )
    monkeypatch.setattr(
        helpers,
        "apply_results_playhead_request_x",
        lambda **kwargs: calls.append(("jump", kwargs)) or 7,
    )
    monkeypatch.setattr(
        helpers,
        "prepare_results_timeline_prelude",
        lambda st, **kwargs: calls.append(("timeline", kwargs)) or (3, 1.5),
    )
    monkeypatch.setattr(
        helpers,
        "render_results_event_controls",
        lambda st, **kwargs: calls.append(("controls", kwargs)),
    )
    monkeypatch.setattr(
        helpers,
        "compute_results_events",
        lambda **kwargs: calls.append(("events", kwargs)) or [{"kind": "warn"}],
    )

    result = helpers.prepare_results_runtime(
        _FakeStreamlit(),
        session_state={"demo": True},
        cache_key="cache-1",
        get_ui_nonce_fn=lambda: "nonce-1",
        time_s=[0.0, 1.5],
        make_playhead_reset_command_fn=lambda: {"reset": True},
        make_playhead_jump_command_fn=lambda idx: {"jump": idx},
        log_event_fn=lambda *args, **kwargs: None,
        event_controls_kwargs={"vacuum_label": "atm"},
        compute_results_events_kwargs={"compute_events_fn": object(), "base_override": {"alpha": 1}},
    )

    assert result == {
        "dataset_id_ui": "cache-1__nonce-1",
        "playhead_idx": 3,
        "playhead_x": 1.5,
        "events_list": [{"kind": "warn"}],
    }
    assert [name for name, _ in calls] == ["reset", "jump", "timeline", "controls", "events"]
    assert calls[0][1]["dataset_id_ui"] == "cache-1__nonce-1"
    assert calls[1][1]["make_playhead_jump_command_fn"](5) == {"jump": 5}
    assert calls[3][1]["session_state"] == {"demo": True}
    assert calls[4][1]["session_state"] == {"demo": True}


def test_entrypoints_use_shared_results_runtime_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_runtime_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_results_runtime_helpers import (" in heavy_text
    assert "prepare_results_runtime(" in app_text
    assert "prepare_results_runtime(" in heavy_text
    assert "def prepare_results_runtime(" in helper_text
    assert "reset_results_playhead_on_dataset_change(" in helper_text
    assert "apply_results_playhead_request_x(" in helper_text
    assert "prepare_results_timeline_prelude(" in helper_text
    assert "render_results_event_controls(" in helper_text
    assert "compute_results_events(" in helper_text
