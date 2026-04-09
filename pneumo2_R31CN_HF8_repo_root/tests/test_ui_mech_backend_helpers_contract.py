from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_mech_backend_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_mech_backend_helpers.py"
ANIM_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_mech_animation_helpers.py"


class _FakeColumn:
    def __enter__(self) -> "_FakeColumn":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeStreamlit:
    def __init__(self, selected_backend: str) -> None:
        self.selected_backend = selected_backend
        self.captions: list[str] = []
        self.selectboxes: list[dict[str, object]] = []

    def columns(self, spec):
        assert list(spec) == [1, 2]
        return _FakeColumn(), _FakeColumn()

    def selectbox(self, label, options, *, index: int, key: str, help: str):
        self.selectboxes.append(
            {
                "label": label,
                "options": list(options),
                "index": index,
                "key": key,
                "help": help,
            }
        )
        return self.selected_backend

    def caption(self, text: str) -> None:
        self.captions.append(text)


def test_render_mechanical_animation_backend_selector_logs_and_hints_component_mode() -> None:
    fake_st = _FakeStreamlit(helpers.MECH_BACKEND_OPTIONS[1])
    session_state: dict[str, object] = {}
    events: list[tuple[str, dict[str, object]]] = []

    use_component = helpers.render_mechanical_animation_backend_selector(
        fake_st,
        session_state,
        cache_key="cache-1",
        dataset_id="dataset-1",
        log_event_fn=lambda name, **kwargs: events.append((name, kwargs)),
        proc_metrics_fn=lambda: {"cpu": 1},
        default_backend_index=1,
        description_text="component-first",
    )

    assert use_component is True
    assert fake_st.selectboxes == [
        {
            "label": "Движок анимации",
            "options": helpers.MECH_BACKEND_OPTIONS,
            "index": 1,
            "key": "anim_backend_cache-1",
            "help": helpers.MECH_BACKEND_HELP,
        }
    ]
    assert fake_st.captions == ["component-first", helpers.MECH_COMPONENT_TIMELINE_HINT]
    assert session_state["_anim_backend_last::cache-1"] == "component"
    assert events == [
        (
            "anim_backend_selected",
            {"backend": "component", "dataset_id": "dataset-1", "proc": {"cpu": 1}},
        )
    ]


def test_render_mechanical_animation_backend_selector_keeps_fallback_mode_without_extra_hint() -> None:
    fake_st = _FakeStreamlit(helpers.MECH_BACKEND_OPTIONS[0])
    session_state = {"_anim_backend_last::cache-2": "fallback"}
    events: list[tuple[str, dict[str, object]]] = []

    use_component = helpers.render_mechanical_animation_backend_selector(
        fake_st,
        session_state,
        cache_key="cache-2",
        dataset_id="dataset-2",
        log_event_fn=lambda name, **kwargs: events.append((name, kwargs)),
        proc_metrics_fn=lambda: {"cpu": 2},
        default_backend_index=0,
        description_text="fallback-first",
    )

    assert use_component is False
    assert fake_st.captions == ["fallback-first"]
    assert events == []


def test_entrypoints_use_shared_mechanical_backend_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    anim_helper_text = ANIM_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_mech_backend_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_mech_backend_helpers import (" not in heavy_text
    assert "render_mechanical_animation_backend_selector(" not in app_text
    assert "render_mechanical_animation_backend_selector(" not in heavy_text
    assert "anim_backend = st.selectbox(" not in app_text
    assert "anim_backend = st.selectbox(" not in heavy_text
    assert '"anim_backend_selected"' not in app_text
    assert '"anim_backend_selected"' not in heavy_text
    assert "from pneumo_solver_ui.ui_mech_backend_helpers import (" in anim_helper_text
    assert "render_mechanical_animation_backend_selector," in anim_helper_text
    assert "backend_selector_fn: Any = render_mechanical_animation_backend_selector" in anim_helper_text
    assert "MECH_BACKEND_OPTIONS = [" in helper_text
    assert "MECH_COMPONENT_TIMELINE_HINT" in helper_text
    assert 'log_event_fn(' in helper_text
