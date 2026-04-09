from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_results_event_controls_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_event_controls_helpers.py"
RUNTIME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_runtime_helpers.py"


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def columns(self, specs):
        self.calls.append(("columns", list(specs)))
        return [_FakeColumn() for _ in specs]

    def checkbox(self, label: str, *, value: bool, key: str):
        self.calls.append(("checkbox", (label, value, key)))
        return value

    def slider(self, label: str, min_value, max_value, value, step, *, key: str):
        self.calls.append(("slider", (label, min_value, max_value, value, step, key)))
        return value

    def multiselect(self, label: str, *, options, default, key: str):
        self.calls.append(("multiselect", (label, list(options), list(default), key)))
        return list(default)


def test_render_results_event_controls_renders_app_like_widget_contract() -> None:
    fake_st = _FakeStreamlit()
    session_state: dict[str, object] = {}

    helpers.render_results_event_controls(
        fake_st,
        session_state=session_state,
        vacuum_label="Вакуум мин, атм(изб)",
        pmax_label="Запас к Pmax, атм",
        vacuum_state_key="events_vacuum_min_atm",
        pmax_state_key="events_pmax_margin_atm",
    )

    assert session_state == {}
    assert fake_st.calls == [
        ("columns", [1, 1, 1, 1]),
        ("checkbox", ("События/алёрты", True, "events_show")),
        ("slider", ("Вакуум мин, атм(изб)", -1.0, 0.0, -0.2, 0.05, "events_vacuum_min_atm")),
        ("slider", ("Запас к Pmax, атм", 0.0, 1.0, 0.1, 0.05, "events_pmax_margin_atm")),
        ("slider", ("Дребезг: toggles/окно", 3, 20, 6, 1, "events_chatter_toggles")),
        ("columns", [1, 2, 1, 1]),
        ("checkbox", ("Метки событий на графиках", True, "events_on_graphs")),
        ("multiselect", ("Уровни на графиках", ["error", "warn", "info"], ["error", "warn"], "events_graph_sev")),
        ("checkbox", ("Подписи error", False, "events_graph_labels")),
        ("slider", ("Макс. событий на графиках", 0, 300, 120, 10, "events_graph_max")),
    ]


def test_render_results_event_controls_handles_heavy_migration() -> None:
    fake_st = _FakeStreamlit()
    session_state: dict[str, object] = {
        "events_vacuum_min_atm": -0.2,
        "events_pmax_margin_atm": 0.1,
    }

    helpers.render_results_event_controls(
        fake_st,
        session_state=session_state,
        vacuum_label="Вакуум мин, бар(изб)",
        pmax_label="Запас к Pmax, бар",
        vacuum_state_key="events_vacuum_min_bar",
        pmax_state_key="events_pmax_margin_bar",
        migration_source_vacuum_key="events_vacuum_min_atm",
        migration_source_pmax_key="events_pmax_margin_atm",
        migration_scale=2.0,
    )

    assert session_state["events_vacuum_min_bar"] == -0.4
    assert session_state["events_pmax_margin_bar"] == 0.2


def test_entrypoints_use_shared_results_event_controls_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    runtime_text = RUNTIME_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_event_controls_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_results_event_controls_helpers import (" not in heavy_text
    assert "render_results_event_controls(" not in app_text
    assert "render_results_event_controls(" not in heavy_text
    assert "cols_evt = st.columns([1, 1, 1, 1])" not in app_text
    assert "cols_evt = st.columns([1, 1, 1, 1])" not in heavy_text
    assert "cols_evt2 = st.columns([1, 2, 1, 1])" not in app_text
    assert "cols_evt2 = st.columns([1, 2, 1, 1])" not in heavy_text
    assert 'key="events_graph_max"' not in app_text
    assert 'key="events_graph_max"' not in heavy_text
    assert "def render_results_event_controls(" in helper_text
    assert "render_results_event_controls(" in runtime_text
    assert 'session_state[vacuum_state_key] = float(session_state[migration_source_vacuum_key]) * float(migration_scale)' in helper_text
