from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_results_timeline_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_timeline_helpers.py"
RUNTIME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_runtime_helpers.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.markdowns: list[str] = []

    def markdown(self, text: str) -> None:
        self.markdowns.append(text)


def test_prepare_results_timeline_prelude_clamps_and_syncs_state() -> None:
    fake_st = _FakeStreamlit()
    session_state: dict[str, object] = {"playhead_idx": 99}

    playhead_idx, playhead_x = helpers.prepare_results_timeline_prelude(
        fake_st,
        session_state=session_state,
        time_s=[0.0, 0.5, 1.0],
    )

    assert playhead_idx == 2
    assert playhead_x == 1.0
    assert session_state["playhead_idx"] == 2
    assert session_state["playhead_t"] == 1.0
    assert fake_st.markdowns == ["### ⏱ Общий таймлайн"]


def test_prepare_results_timeline_prelude_handles_empty_time_vector() -> None:
    fake_st = _FakeStreamlit()
    session_state: dict[str, object] = {"playhead_idx": "oops"}

    playhead_idx, playhead_x = helpers.prepare_results_timeline_prelude(
        fake_st,
        session_state=session_state,
        time_s=[],
    )

    assert playhead_idx == 0
    assert playhead_x is None
    assert "playhead_t" not in session_state
    assert fake_st.markdowns == ["### ⏱ Общий таймлайн"]


def test_entrypoints_use_shared_results_timeline_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    runtime_text = RUNTIME_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_timeline_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_results_timeline_helpers import (" not in heavy_text
    assert "prepare_results_timeline_prelude(" not in app_text
    assert "prepare_results_timeline_prelude(" not in heavy_text
    assert 'playhead_x = None' not in app_text
    assert 'playhead_x = None' not in heavy_text
    assert 'st.markdown("### вЏ± РћР±С‰РёР№ С‚Р°Р№РјР»Р°Р№РЅ")' not in app_text
    assert 'st.markdown("### вЏ± РћР±С‰РёР№ С‚Р°Р№РјР»Р°Р№РЅ")' not in heavy_text
    assert "def prepare_results_timeline_prelude(" in helper_text
    assert "prepare_results_timeline_prelude(" in runtime_text
    assert 'st.markdown(heading_markdown)' in helper_text
