from __future__ import annotations

import csv
import json
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

    def write(self, text: str) -> None:
        self.calls.append(("write", text))

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

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


def test_finished_job_panel_surfaces_final_runtime_diagnostics_for_handoff_run(tmp_path: Path) -> None:
    st = _FakeStreamlit()
    run_dir = tmp_path / "coord_done"
    export_dir = run_dir / "export"
    export_dir.mkdir(parents=True)
    (export_dir / "run_scope.json").write_text(
        json.dumps(
            {
                "objective_keys": ["comfort", "energy"],
                "penalty_key": "penalty_total",
                "penalty_tol": 0.25,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (export_dir / "trials.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["trial_id", "status", "error_text", "g_json", "y_json", "metrics_json"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "trial_id": "1",
                "status": "DONE",
                "error_text": "",
                "g_json": json.dumps([-0.25], ensure_ascii=False),
                "y_json": json.dumps([0.8, 1.8], ensure_ascii=False),
                "metrics_json": json.dumps(
                    {"comfort": 0.8, "energy": 1.8, "penalty_total": 0.0},
                    ensure_ascii=False,
                ),
            }
        )
        writer.writerow(
            {
                "trial_id": "2",
                "status": "DONE",
                "error_text": "",
                "g_json": json.dumps([0.35], ensure_ascii=False),
                "y_json": json.dumps([1.5, 5.3], ensure_ascii=False),
                "metrics_json": json.dumps(
                    {"comfort": 1.5, "energy": 5.3, "penalty_total": 0.6},
                    ensure_ascii=False,
                ),
            }
        )
        writer.writerow(
            {
                "trial_id": "3",
                "status": "ERROR",
                "error_text": "bad physics",
                "g_json": "",
                "y_json": "",
                "metrics_json": "",
            }
        )

    job = SimpleNamespace(
        run_dir=run_dir,
        backend="Handoff/ray/portfolio/q2",
        pipeline_mode="coordinator",
        budget=84,
    )
    summary = SimpleNamespace(
        pipeline_mode="coordinator",
        status="partial",
        row_count=0,
        done_count=2,
        running_count=0,
        error_count=1,
        objective_keys=("comfort", "energy"),
        penalty_key="penalty_total",
        penalty_tol=0.25,
    )

    rendered = render_finished_optimization_job_panel(
        st,
        job,
        rc=0,
        soft_stop_requested=False,
        clear_job_fn=lambda: None,
        rerun_fn=lambda _: None,
        summarize_run_fn=lambda _: summary,
        save_ptr_fn=lambda *_args, **_kwargs: None,
        autoload_session_fn=lambda _: None,
        active_launch_context={
            "kind": "handoff",
            "run_dir": str(run_dir.resolve()),
            "source_run_dir": str((tmp_path / "staged_source").resolve()),
        },
    )

    assert rendered is True
    assert ("success", "Оптимизация завершена успешно (код=0).") in st.calls
    assert ("write", "**Final runtime diagnostics**") in st.calls
    assert any(
        kind == "caption"
        and "Final handoff progress:" in text
        and "done=2 / 84" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "caption"
        and "Final handoff trial health:" in text
        and "DONE=2, RUNNING=0, ERROR=1" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "caption"
        and "Final handoff penalty gate:" in text
        and "infeasible DONE=1" in text
        and "`penalty_total`=0.6 > 0.25" in text
        and "comfort +0.7" in text
        and "energy +3.5" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "caption"
        and "Recent handoff errors:" in text
        and "bad physics" in text
        for kind, text in st.calls
    )
