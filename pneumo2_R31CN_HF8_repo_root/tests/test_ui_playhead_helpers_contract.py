from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_playhead_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
EVENT_PANEL_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_event_panel_helpers.py"


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self, *, checkbox_value: bool, slider_values: dict[str, int] | None = None) -> None:
        self.checkbox_value = checkbox_value
        self.slider_values = slider_values or {}
        self.captions: list[str] = []
        self.warnings: list[str] = []

    def columns(self, spec, gap=None):
        assert list(spec) == [1.35, 0.95, 0.95, 0.95]
        assert gap == "medium"
        return [_Context(), _Context(), _Context(), _Context()]

    def checkbox(self, label: str, *, value: bool, key: str):
        assert key == "playhead_server_sync"
        return self.checkbox_value

    def slider(self, label: str, min_value: int, max_value: int, value: int, step: int, *, key: str, help: str):
        return int(self.slider_values.get(key, value))

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def warning(self, text: str) -> None:
        self.warnings.append(text)


def test_build_playhead_component_events_normalizes_t_and_label() -> None:
    assert ui_playhead_helpers.build_playhead_component_events(
        [
            {"t": 1.25, "label": "A"},
            {"t_s": 2, "label": 7},
            {"label": None},
        ]
    ) == [
        {"t": 1.25, "label": "A"},
        {"t": 2.0, "label": "7"},
        {"t": 0.0, "label": "None"},
    ]


def test_render_playhead_component_handles_render_no_time_and_missing() -> None:
    calls: list[dict[str, object]] = []
    infos: list[str] = []
    session_state = {"playhead_cmd": {"ts": 123}}

    def fake_component(**kwargs):
        calls.append(kwargs)

    status = ui_playhead_helpers.render_playhead_component(
        fake_component,
        time_s=[0.0, 1.0],
        dataset_id="dataset-1",
        session_state=session_state,
        events_list=[{"t": 1.5, "label": "A"}],
        send_hz=2,
        storage_hz=30,
        info_fn=infos.append,
    )
    assert status == "rendered"
    assert infos == []
    assert calls[0]["dataset_id"] == "dataset-1"
    assert calls[0]["cmd"] == {"ts": 123}
    assert calls[0]["events"] == [{"t": 1.5, "label": "A"}]
    assert calls[0]["events_max"] == 40

    status = ui_playhead_helpers.render_playhead_component(
        fake_component,
        time_s=[],
        dataset_id="dataset-2",
        session_state=session_state,
        events_list=[],
        send_hz=0,
        storage_hz=20,
        info_fn=infos.append,
    )
    assert status == "no_time"
    assert infos[-1] == ui_playhead_helpers.PLAYHEAD_NO_TIME_MESSAGE

    status = ui_playhead_helpers.render_playhead_component(
        None,
        time_s=[0.0],
        dataset_id="dataset-3",
        session_state=session_state,
        events_list=[],
        send_hz=0,
        storage_hz=20,
        info_fn=infos.append,
    )
    assert status == "missing"
    assert infos[-1] == ui_playhead_helpers.PLAYHEAD_COMPONENT_MISSING_MESSAGE


def test_playhead_command_builders_produce_expected_payloads() -> None:
    assert ui_playhead_helpers.make_playhead_reset_command(time_ms_fn=lambda: 1.234) == {
        "ts": 1234,
        "set_idx": 0,
        "set_playing": False,
        "set_loop": False,
        "set_speed": 0.25,
    }
    assert ui_playhead_helpers.make_playhead_jump_command(7, time_ms_fn=lambda: 2.5) == {
        "ts": 2500,
        "set_idx": 7,
        "set_playing": False,
    }
    assert ui_playhead_helpers.make_playhead_pause_command(time_ms_fn=lambda: 3.0) == {
        "ts": 3000,
        "set_playing": False,
    }


def test_pause_playhead_on_view_switch_updates_state_once() -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    state: dict[str, object] = {}

    changed = ui_playhead_helpers.pause_playhead_on_view_switch(
        state,
        view="Графики",
        cur_hash="abc",
        test_pick="test-1",
        log_event_fn=lambda event, **kwargs: calls.append((event, kwargs)),
        time_ms_fn=lambda: 4.0,
    )

    assert changed is True
    assert state["__prev_view_res__abc::test-1"] == "Графики"
    assert state["playhead_cmd"] == {"ts": 4000, "set_playing": False}
    assert calls == [("view_switch", {"view": "Графики", "test": "test-1"})]

    changed_again = ui_playhead_helpers.pause_playhead_on_view_switch(
        state,
        view="Графики",
        cur_hash="abc",
        test_pick="test-1",
        log_event_fn=lambda event, **kwargs: calls.append((event, kwargs)),
        time_ms_fn=lambda: 5.0,
    )

    assert changed_again is False
    assert calls == [("view_switch", {"view": "Графики", "test": "test-1"})]


def test_render_results_view_selector_renders_radio_and_pauses() -> None:
    radio_calls: list[dict[str, object]] = []
    pause_calls: list[dict[str, object]] = []

    def radio_fn(label: str, *, options, horizontal: bool, key: str):
        radio_calls.append(
            {
                "label": label,
                "options": list(options),
                "horizontal": horizontal,
                "key": key,
            }
        )
        return "Потоки"

    original_pause = ui_playhead_helpers.pause_playhead_on_view_switch
    try:
        ui_playhead_helpers.pause_playhead_on_view_switch = lambda session_state, **kwargs: pause_calls.append(  # type: ignore[assignment]
            {"session_state": session_state, **kwargs}
        ) or True
        state: dict[str, object] = {}
        selected = ui_playhead_helpers.render_results_view_selector(
            options=["Графики", "Потоки"],
            session_state=state,
            cur_hash="abc",
            test_pick="test-1",
            log_event_fn=lambda *args, **kwargs: None,
            radio_fn=radio_fn,
        )
    finally:
        ui_playhead_helpers.pause_playhead_on_view_switch = original_pause  # type: ignore[assignment]

    assert selected == "Потоки"
    assert radio_calls == [
        {
            "label": "Раздел результатов",
            "options": ["Графики", "Потоки"],
            "horizontal": True,
            "key": "baseline_view_res",
        }
    ]
    assert len(pause_calls) == 1
    assert pause_calls[0]["session_state"] is state
    assert pause_calls[0]["view"] == "Потоки"
    assert pause_calls[0]["cur_hash"] == "abc"
    assert pause_calls[0]["test_pick"] == "test-1"
    assert callable(pause_calls[0]["log_event_fn"])


def test_render_playhead_sync_controls_returns_values_and_warns_on_high_hz(monkeypatch) -> None:
    fake_st = _FakeStreamlit(
        checkbox_value=True,
        slider_values={
            "playhead_send_hz": 4,
            "playhead_storage_hz": 24,
        },
    )
    monkeypatch.setattr(ui_playhead_helpers, "st", fake_st)

    ph_server_sync, ph_send_hz, ph_storage_hz = ui_playhead_helpers.render_playhead_sync_controls()

    assert ph_server_sync is True
    assert ph_send_hz == 4
    assert ph_storage_hz == 24
    assert len(fake_st.captions) == 1
    assert len(fake_st.warnings) == 1


def test_render_playhead_sync_controls_zeros_server_hz_when_disabled(monkeypatch) -> None:
    fake_st = _FakeStreamlit(
        checkbox_value=False,
        slider_values={
            "playhead_storage_hz": 18,
        },
    )
    monkeypatch.setattr(ui_playhead_helpers, "st", fake_st)

    ph_server_sync, ph_send_hz, ph_storage_hz = ui_playhead_helpers.render_playhead_sync_controls()

    assert ph_server_sync is False
    assert ph_send_hz == 0
    assert ph_storage_hz == 18
    assert fake_st.warnings == []


def test_entrypoints_use_shared_playhead_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    event_panel_text = EVENT_PANEL_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_playhead_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_playhead_helpers import (" in heavy_text
    assert "render_results_view_selector(" in app_text
    assert "render_results_view_selector(" in heavy_text
    assert "radio_fn=st.radio" in app_text
    assert "radio_fn=st.radio" in heavy_text
    assert "make_playhead_reset_command()" in app_text
    assert "make_playhead_reset_command()" in heavy_text
    assert "make_playhead_jump_command(j)" in app_text
    assert "make_playhead_jump_command(j)" in heavy_text
    assert "make_playhead_jump_command(jump_index, time_ms_fn=time_ms_fn)" in event_panel_text
    assert "cols_phsync = st.columns([1.35, 0.95, 0.95, 0.95], gap=\"medium\")" not in app_text
    assert "cols_phsync = st.columns([1.35, 0.95, 0.95, 0.95], gap=\"medium\")" not in heavy_text
    assert "build_playhead_component_events(events_list)" not in app_text
    assert "build_playhead_component_events(events_list)" not in heavy_text
    assert "events=[{'t': float(ev.get('t', ev.get('t_s', 0.0))), 'label': str(ev.get('label', ''))} for ev in (events_list or [])]" not in app_text
    assert "events=[{'t': float(ev.get('t', ev.get('t_s', 0.0))), 'label': str(ev.get('label', ''))} for ev in (events_list or [])]" not in heavy_text
    assert '{"ts": int(time.time() * 1000), "set_idx": 0, "set_playing": False, "set_loop": False, "set_speed": 0.25}' not in app_text
    assert '{"ts": int(time.time() * 1000), "set_idx": 0, "set_playing": False, "set_loop": False, "set_speed": 0.25}' not in heavy_text
    assert '{"ts": int(time.time() * 1000), "set_idx": j, "set_playing": False}' not in app_text
    assert '{"ts": int(time.time() * 1000), "set_idx": j, "set_playing": False}' not in heavy_text
    assert "if ph_comp is not None and time_s:" not in app_text
    assert "if ph_comp is not None and time_s:" not in heavy_text
    assert 'view_res = st.radio(' not in app_text
    assert 'view_res = st.radio(' not in heavy_text
