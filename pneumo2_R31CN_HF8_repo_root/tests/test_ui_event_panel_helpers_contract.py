from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_event_panel_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
PLAYHEAD_SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_playhead_section_helpers.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self, *, session_state: dict[str, object], selected_index: int = 0, button_pressed: bool = False) -> None:
        self.session_state = session_state
        self.selected_index = selected_index
        self.button_pressed = button_pressed
        self.captions: list[str] = []
        self.selectbox_calls: list[dict[str, object]] = []

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def expander(self, label: str, *, expanded: bool):
        assert label == "События/алёрты"
        assert expanded is False
        return _Context()

    def selectbox(self, label: str, *, options, format_func, key: str):
        self.selectbox_calls.append(
            {
                "label": label,
                "options": list(options),
                "preview": format_func(self.selected_index),
                "key": key,
            }
        )
        return self.selected_index

    def button(self, label: str, *, key: str):
        assert label == "Перейти (jump playhead)"
        assert key == "events_jump_btn"
        return self.button_pressed


def test_build_event_alerts_table_and_format_option() -> None:
    events = [
        {"t": 1.25, "severity": "warn", "kind": "vacuum", "name": "nodes", "label": "Low pressure", "idx": 7},
    ]

    table = ui_event_panel_helpers.build_event_alerts_table(events)

    assert table.to_dict(orient="records") == [
        {
            "t, s": 1.25,
            "severity": "warn",
            "kind": "vacuum",
            "name": "nodes",
            "label": "Low pressure",
            "idx": 7,
        }
    ]
    assert ui_event_panel_helpers.format_event_jump_option(events, 0) == "t=1.250s | warn | Low pressure"


def test_render_event_alerts_panel_updates_playhead_on_jump(monkeypatch) -> None:
    fake_st = _FakeStreamlit(
        session_state={
            "events_show": True,
            "playhead_picked_event": {"label": "Picked"},
        },
        selected_index=1,
        button_pressed=True,
    )
    captured_tables: list[tuple[object, int]] = []
    monkeypatch.setattr(ui_event_panel_helpers, "st", fake_st)

    ui_event_panel_helpers.render_event_alerts_panel(
        [
            {"t": 1.0, "severity": "info", "label": "A", "idx": 3},
            {"t": 2.5, "severity": "warn", "label": "B", "idx": 9},
        ],
        safe_dataframe_fn=lambda df, *, height: captured_tables.append((df.copy(), height)),
        time_ms_fn=lambda: 123.456,
    )

    assert fake_st.captions[0] == "Последний клик по событию: Picked"
    assert fake_st.captions[1] == "Найдено событий: 2"
    assert captured_tables[0][1] == 240
    assert fake_st.session_state["playhead_idx"] == 9
    assert fake_st.session_state["playhead_t"] == 2.5
    assert fake_st.session_state["playhead_cmd"] == {"ts": 123456, "set_idx": 9, "set_playing": False}
    assert fake_st.selectbox_calls[0]["preview"] == "t=2.500s | warn | B"


def test_entrypoints_use_shared_event_panel_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    playhead_text = PLAYHEAD_SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_event_panel_helpers import render_event_alerts_panel" in playhead_text
    assert "render_event_alerts_panel_fn(" in playhead_text
    assert "render_playhead_results_section_fn=render_playhead_results_section" in surface_text
    assert "df_events_view = pd.DataFrame([" not in app_text
    assert "df_events_view = pd.DataFrame([" not in heavy_text
    assert 'st.button("Перейти (jump playhead)", key="events_jump_btn")' not in app_text
    assert 'st.button("Перейти (jump playhead)", key="events_jump_btn")' not in heavy_text
