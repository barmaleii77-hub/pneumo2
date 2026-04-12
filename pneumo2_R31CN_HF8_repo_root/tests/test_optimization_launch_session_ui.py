from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_launch_session_ui import (
    render_optimization_launch_session_block,
)


class _FakeExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state = {}
        self.calls: list[tuple[str, object]] = []

    def expander(self, label: str, expanded: bool = False):
        self.calls.append(("expander", (label, expanded)))
        return _FakeExpander()

    def markdown(self, text: str) -> None:
        self.calls.append(("markdown", text))

    def success(self, text: str) -> None:
        self.calls.append(("success", text))


class _FakeProc:
    def __init__(self, poll_result):
        self.pid = 321
        self._poll_result = poll_result

    def poll(self):
        return self._poll_result


def test_launch_session_ui_calls_launch_callback_for_idle_stage_runner() -> None:
    st = _FakeStreamlit()
    events: list[tuple[str, object]] = []

    render_optimization_launch_session_block(
        st,
        job=None,
        is_staged=True,
        tail_file_text_fn=lambda _: "",
        soft_stop_requested_fn=lambda _: False,
        parse_done_from_log_fn=lambda _: None,
        render_stage_runtime_fn=None,
        write_soft_stop_file_fn=lambda _: True,
        terminate_process_fn=lambda _: None,
        rerun_fn=lambda _: None,
        sleep_fn=lambda _: None,
        clear_job_fn=lambda: None,
        launch_job_fn=lambda: events.append(("launch", "stage")),
        build_cmd_preview_text_fn=lambda: "python staged.py\n",
        render_launch_panel_fn=lambda _st, **kwargs: events.append(("launch_panel", kwargs["launch_button_label"])) or True,
    )

    assert ("expander", ("Запуск оптимизации", True)) in st.calls
    assert any(kind == "markdown" and "opt_stage_runner_v1.py" in text for kind, text in st.calls)
    assert events == [("launch_panel", "Запустить StageRunner"), ("launch", "stage")]


def test_launch_session_ui_routes_running_job_into_live_panel() -> None:
    st = _FakeStreamlit()
    st.session_state["__opt_active_launch_context"] = {
        "kind": "handoff",
        "run_dir": str(Path("C:/tmp/run-1").resolve()),
        "pipeline_mode": "coordinator",
        "backend": "Handoff/ray/portfolio/q2",
        "source_run_dir": str(Path("C:/tmp/staged-run").resolve()),
    }
    events: list[tuple[str, object]] = []
    job = SimpleNamespace(
        proc=_FakeProc(None),
        pipeline_mode="coordinator",
        backend="ray",
        run_dir=Path("C:/tmp/run-1"),
        log_path=Path("C:/tmp/run-1/coordinator.log"),
    )

    def _render_live(_st, _job, **kwargs):
        events.append(
            (
                "live",
                kwargs["coordinator_done"],
                kwargs["soft_stop_requested"],
                kwargs["current_problem_hash"],
                kwargs["current_problem_hash_mode"],
            )
        )
        return True

    render_optimization_launch_session_block(
        st,
        job=job,
        is_staged=False,
        current_problem_hash="ph_launch_ui_scope",
        current_problem_hash_mode="legacy",
        tail_file_text_fn=lambda _: "done=5",
        soft_stop_requested_fn=lambda _: True,
        parse_done_from_log_fn=lambda text: 5 if "5" in text else None,
        render_stage_runtime_fn=lambda _: events.append(("stage_runtime", None)),
        write_soft_stop_file_fn=lambda _: True,
        terminate_process_fn=lambda _: None,
        rerun_fn=lambda _: None,
        sleep_fn=lambda _: None,
        clear_job_fn=lambda: None,
        launch_job_fn=lambda: events.append(("launch", None)),
        build_cmd_preview_text_fn=lambda: "python coord.py\n",
        render_live_panel_fn=_render_live,
        render_launch_panel_fn=lambda _st, **kwargs: events.append(("launch_panel", kwargs["launch_button_label"])) or False,
    )

    assert any(kind == "markdown" and "dist_opt_coordinator.py" in text for kind, text in st.calls)
    assert any(
        kind == "success"
        and "seeded full-ring coordinator handoff" in text
        and "staged-run" in text
        and "run-1" in text
        for kind, text in st.calls
    )
    assert events == [("live", 5, True, "ph_launch_ui_scope", "legacy")]


def test_launch_session_ui_routes_finished_job_into_finished_panel() -> None:
    st = _FakeStreamlit()
    events: list[tuple[str, object]] = []
    job = SimpleNamespace(
        proc=_FakeProc(0),
        pipeline_mode="staged",
        backend="dask",
        run_dir=Path("C:/tmp/run-2"),
        log_path=Path("C:/tmp/run-2/stage_runner.log"),
    )

    def _render_finished(_st, _job, **kwargs):
        started = bool(kwargs["start_handoff_fn"] and kwargs["start_handoff_fn"]())
        events.append(("finished", kwargs["rc"], kwargs["soft_stop_requested"], started))
        return True

    render_optimization_launch_session_block(
        st,
        job=job,
        is_staged=True,
        tail_file_text_fn=lambda _: "",
        soft_stop_requested_fn=lambda _: False,
        parse_done_from_log_fn=lambda _: None,
        render_stage_runtime_fn=None,
        write_soft_stop_file_fn=lambda _: True,
        terminate_process_fn=lambda _: None,
        rerun_fn=lambda _: None,
        sleep_fn=lambda _: None,
        clear_job_fn=lambda: None,
        launch_job_fn=lambda: events.append(("launch", None)),
        start_handoff_job_fn=lambda run_dir: events.append(("handoff_start", run_dir)) or True,
        build_cmd_preview_text_fn=lambda: "python staged.py\n",
        render_finished_panel_fn=_render_finished,
        render_launch_panel_fn=lambda _st, **kwargs: events.append(("launch_panel", kwargs["launch_button_label"])) or False,
    )

    assert events == [
        ("handoff_start", Path("C:/tmp/run-2")),
        ("finished", 0, False, True),
        ("launch_panel", "Запустить StageRunner"),
    ]
