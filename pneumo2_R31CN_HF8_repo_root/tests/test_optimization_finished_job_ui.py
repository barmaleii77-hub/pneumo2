from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_finished_job_ui import (
    render_finished_optimization_job_panel,
)


class _FakeStreamlit:
    def __init__(self, *, clear_clicked: bool = False) -> None:
        self.session_state = {}
        self.calls: list[tuple[str, str]] = []
        self._clear_clicked = bool(clear_clicked)

    def warning(self, text: str) -> None:
        self.calls.append(("warning", text))

    def success(self, text: str) -> None:
        self.calls.append(("success", text))

    def error(self, text: str) -> None:
        self.calls.append(("error", text))

    def button(self, label: str, **kwargs) -> bool:
        self.calls.append(("button", label))
        return self._clear_clicked if label == "Очистить статус запуска" else False


def test_finished_job_panel_marks_soft_stop_and_saves_pointer_for_done_run() -> None:
    st = _FakeStreamlit(clear_clicked=True)
    events: list[tuple[str, object]] = []
    job = SimpleNamespace(run_dir=Path("C:/tmp/run"), backend="ray")
    summary = SimpleNamespace(
        pipeline_mode="staged",
        status="done",
        row_count=12,
        done_count=12,
        running_count=0,
        error_count=0,
        objective_keys=("comfort",),
        penalty_key="penalty_total",
        penalty_tol=0.0,
    )

    rendered = render_finished_optimization_job_panel(
        st,
        job,
        rc=0,
        soft_stop_requested=True,
        clear_job_fn=lambda: events.append(("clear", None)),
        rerun_fn=lambda _: events.append(("rerun", None)),
        summarize_run_fn=lambda _: summary,
        save_ptr_fn=lambda run_dir, meta: events.append(("save", run_dir, dict(meta))),
        autoload_session_fn=lambda _: events.append(("autoload", None)),
    )

    assert rendered is True
    assert ("warning", "Оптимизация остановлена по STOP-файлу (код=0).") in st.calls
    assert [event[0] for event in events] == ["save", "autoload", "clear", "rerun"]


def test_finished_job_panel_warns_when_artifacts_are_not_usable() -> None:
    st = _FakeStreamlit()
    job = SimpleNamespace(run_dir=Path("C:/tmp/run"), backend="ray")
    summary = SimpleNamespace(
        pipeline_mode="coordinator",
        status="error",
        row_count=0,
        done_count=0,
        running_count=0,
        error_count=1,
        objective_keys=(),
        penalty_key="",
        penalty_tol=None,
    )

    rendered = render_finished_optimization_job_panel(
        st,
        job,
        rc=1,
        soft_stop_requested=False,
        clear_job_fn=lambda: None,
        rerun_fn=lambda _: None,
        summarize_run_fn=lambda _: summary,
        save_ptr_fn=lambda run_dir, meta: (_ for _ in ()).throw(RuntimeError("should not save")),
        autoload_session_fn=lambda _: None,
    )

    assert rendered is True
    assert ("error", "Оптимизация завершилась с ошибкой (код=1).") in st.calls
    assert any(kind == "warning" and "usable optimization artifacts" in text for kind, text in st.calls)


def test_finished_job_panel_exposes_handoff_action_for_successful_staged_run() -> None:
    st = _FakeStreamlit()
    events: list[tuple[str, object]] = []
    job = SimpleNamespace(run_dir=Path("C:/tmp/run"), backend="ray", pipeline_mode="staged")
    summary = SimpleNamespace(
        pipeline_mode="staged",
        status="done",
        row_count=12,
        done_count=12,
        running_count=0,
        error_count=0,
        objective_keys=("comfort",),
        penalty_key="penalty_total",
        penalty_tol=0.0,
    )

    rendered = render_finished_optimization_job_panel(
        st,
        job,
        rc=0,
        soft_stop_requested=False,
        clear_job_fn=lambda: events.append(("clear", None)),
        rerun_fn=lambda _: events.append(("rerun", None)),
        summarize_run_fn=lambda _: summary,
        save_ptr_fn=lambda run_dir, meta: events.append(("save", run_dir, dict(meta))),
        autoload_session_fn=lambda _: events.append(("autoload", None)),
        start_handoff_fn=lambda run_dir: events.append(("handoff_start", run_dir)) or True,
        render_handoff_action_fn=lambda _st, **kwargs: events.append(
            (
                "handoff_render",
                kwargs["source_run_dir"],
                kwargs["start_handoff_fn"] is not None,
                kwargs["button_key"],
                kwargs.get("recommended_action", True),
                kwargs.get("button_label", ""),
            )
        ) or False,
    )

    assert rendered is True
    assert ("success", "Оптимизация завершена успешно (код=0).") in st.calls
    assert (
        "handoff_render",
        Path("C:/tmp/run"),
        True,
        "finished_job_start_coordinator_handoff",
        True,
        "",
    ) in events
