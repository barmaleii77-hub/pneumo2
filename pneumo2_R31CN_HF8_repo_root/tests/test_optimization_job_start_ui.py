from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_job_start_ui import (
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
    events: list[str] = []

    ok = start_optimization_job_with_feedback(
        st,
        session_state={},
        ui_root=Path("C:/repo/pneumo_solver_ui"),
        ui_jobs_default=7,
        python_executable="python",
        problem_hash_mode="stable",
        rerun_fn=lambda _st: events.append("rerun"),
        start_job_fn=lambda *args, **kwargs: events.append("start"),
    )

    assert ok is True
    assert ("success", "Запуск создан. Лог и прогресс появятся через пару секунд.") in st.calls
    assert events == ["start", "rerun"]


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
