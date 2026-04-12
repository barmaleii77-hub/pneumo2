from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_job_start_ui import (
    start_coordinator_handoff_job_with_feedback,
    start_optimization_job_with_feedback,
)


class _FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def success(self, text: str) -> None:
        self.calls.append(("success", text))

    def error(self, text: str) -> None:
        self.calls.append(("error", text))


def test_job_start_ui_reports_success_and_requests_rerun() -> None:
    st = _FakeStreamlit()
    session_state: dict[str, object] = {}
    events: list[str] = []

    ok = start_optimization_job_with_feedback(
        st,
        session_state=session_state,
        ui_root=Path("C:/repo/pneumo_solver_ui"),
        ui_jobs_default=7,
        python_executable="python",
        problem_hash_mode="stable",
        rerun_fn=lambda _st: events.append("rerun"),
        start_job_fn=lambda *args, **kwargs: events.append("start") or type(
            "Job",
            (),
            {
                "run_dir": Path("C:/workspace/opt_runs/staged/p_stage_1"),
                "pipeline_mode": "staged",
                "backend": "StageRunner",
            },
        )(),
    )

    assert ok is True
    assert ("success", "Запуск создан. Лог и прогресс появятся через пару секунд.") in st.calls
    assert events == ["start", "rerun"]
    assert session_state["__opt_history_selected_run_dir"] == str(Path("C:/workspace/opt_runs/staged/p_stage_1").resolve())
    assert session_state["opt_use_staged"] is True
    assert session_state["use_staged_opt"] is True


def test_job_start_ui_reports_errors_honestly() -> None:
    st = _FakeStreamlit()

    ok = start_optimization_job_with_feedback(
        st,
        session_state={},
        ui_root=Path("C:/repo/pneumo_solver_ui"),
        ui_jobs_default=7,
        python_executable="python",
        problem_hash_mode="stable",
        rerun_fn=lambda _st: (_ for _ in ()).throw(RuntimeError("should not rerun")),
        start_job_fn=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert ok is False
    assert ("error", "Не удалось запустить оптимизацию: boom") in st.calls


def test_handoff_job_start_ui_reports_success_and_requests_rerun() -> None:
    st = _FakeStreamlit()
    session_state: dict[str, object] = {}
    events: list[str] = []

    ok = start_coordinator_handoff_job_with_feedback(
        st,
        session_state=session_state,
        source_run_dir=Path("C:/workspace/opt_runs/staged/run_1"),
        ui_root=Path("C:/repo/pneumo_solver_ui"),
        python_executable="python",
        problem_hash_mode="stable",
        rerun_fn=lambda _st: events.append("rerun"),
        start_job_fn=lambda *args, **kwargs: events.append("start") or type(
            "Job",
            (),
            {
                "run_dir": Path("C:/workspace/opt_runs/coord/handoff_1"),
                "pipeline_mode": "coordinator",
                "backend": "Handoff/ray/portfolio/q2",
            },
        )(),
    )

    assert ok is True
    assert ("success", "Coordinator handoff запущен. Full-ring лог появится через пару секунд.") in st.calls
    assert events == ["start", "rerun"]
    assert session_state["__opt_history_selected_run_dir"] == str(Path("C:/workspace/opt_runs/coord/handoff_1").resolve())
    assert session_state["opt_use_staged"] is False
    assert session_state["use_staged_opt"] is False
    assert session_state["__opt_active_launch_context"] == {
        "kind": "handoff",
        "run_dir": str(Path("C:/workspace/opt_runs/coord/handoff_1").resolve()),
        "pipeline_mode": "coordinator",
        "backend": "Handoff/ray/portfolio/q2",
        "source_run_dir": str(Path("C:/workspace/opt_runs/staged/run_1").resolve()),
    }


def test_handoff_job_start_ui_reports_errors_honestly() -> None:
    st = _FakeStreamlit()

    ok = start_coordinator_handoff_job_with_feedback(
        st,
        session_state={},
        source_run_dir=Path("C:/workspace/opt_runs/staged/run_1"),
        ui_root=Path("C:/repo/pneumo_solver_ui"),
        python_executable="python",
        problem_hash_mode="stable",
        rerun_fn=lambda _st: (_ for _ in ()).throw(RuntimeError("should not rerun")),
        start_job_fn=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("handoff boom")),
    )

    assert ok is False
    assert ("error", "Не удалось запустить coordinator handoff: handoff boom") in st.calls
