from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_run_pointer_actions_ui import (
    build_run_pointer_meta_from_summary,
    open_results_via_run_pointer,
    save_run_pointer_to_latest,
)


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state = {}
        self.calls: list[tuple[str, str]] = []

    def success(self, text: str) -> None:
        self.calls.append(("success", text))

    def error(self, text: str) -> None:
        self.calls.append(("error", text))

    def info(self, text: str) -> None:
        self.calls.append(("info", text))

    def switch_page(self, text: str) -> None:
        self.calls.append(("switch_page", text))


def test_build_run_pointer_meta_from_summary_keeps_history_contract_fields() -> None:
    summary = SimpleNamespace(
        backend="ray",
        pipeline_mode="staged",
        status="done",
        row_count=12,
        done_count=11,
        running_count=0,
        error_count=1,
        objective_keys=("comfort", "roll"),
        penalty_key="penalty_total",
        penalty_tol=0.25,
        handoff_preset_tag="ray/portfolio/q2",
        handoff_budget=84,
        handoff_seed_count=6,
    )

    meta = build_run_pointer_meta_from_summary(summary, now_text="2026-04-08 20:00:00")

    assert meta["backend"] == "ray"
    assert meta["pipeline_mode"] == "staged"
    assert meta["rows"] == 12
    assert meta["objective_keys"] == ["comfort", "roll"]
    assert meta["penalty_key"] == "penalty_total"
    assert meta["penalty_tol"] == 0.25
    assert meta["handoff_preset"] == "ray/portfolio/q2"
    assert meta["handoff_budget"] == 84
    assert meta["handoff_seed_count"] == 6
    assert meta["selected_from"] == "optimization_history"
    assert meta["ts"] == "2026-04-08 20:00:00"


def test_save_and_open_run_pointer_actions_use_injected_side_effects() -> None:
    st = _FakeStreamlit()
    events: list[tuple[str, object]] = []
    run_dir = Path("C:/tmp/run")
    meta = {"backend": "ray"}

    def _save_ptr(path: Path, payload: dict) -> None:
        events.append(("save", path, dict(payload)))

    def _autoload(session_state) -> None:
        events.append(("autoload", dict(session_state)))

    def _rerun(streamlit_obj) -> None:
        events.append(("rerun", streamlit_obj))

    saved = save_run_pointer_to_latest(
        st,
        run_dir,
        meta,
        rerun_fn=_rerun,
        save_ptr_fn=_save_ptr,
        autoload_session_fn=_autoload,
    )
    opened = open_results_via_run_pointer(
        st,
        run_dir,
        meta,
        save_ptr_fn=_save_ptr,
        autoload_session_fn=_autoload,
    )

    assert saved is True
    assert opened is True
    assert ("success", "latest_optimization pointer перепривязан к выбранному run_dir.") in st.calls
    assert ("switch_page", "pages/20_DistributedOptimization.py") in st.calls
    assert [event[0] for event in events] == ["save", "autoload", "rerun", "save", "autoload"]
