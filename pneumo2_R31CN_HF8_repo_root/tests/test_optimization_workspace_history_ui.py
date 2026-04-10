from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_workspace_history_ui import (
    render_workspace_run_history_block,
)


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}
        self.calls: list[tuple[str, object]] = []

    def info(self, text: str) -> None:
        self.calls.append(("info", text))

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def selectbox(self, label: str, **kwargs):
        self.calls.append(("selectbox", label))
        options = kwargs.get("options") or []
        index = int(kwargs.get("index", 0) or 0)
        return options[index] if options else None

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]

    def metric(self, label: str, value) -> None:
        self.calls.append(("metric", (label, value)))


def test_workspace_history_ui_renders_selected_summary_and_delegates_details() -> None:
    st = _FakeStreamlit()
    events: list[tuple[str, object]] = []
    summary = SimpleNamespace(
        run_dir=Path("C:/tmp/run-1"),
        status_label="done",
        pipeline_mode="coordinator",
        row_count=0,
        done_count=12,
        backend="ray",
        error_count=0,
        running_count=1,
    )

    render_workspace_run_history_block(
        st,
        workspace_dir=Path("C:/tmp/workspace"),
        active_job=None,
        session_state={"opt_objectives": "comfort\nroll", "opt_penalty_key": "penalty_total"},
        current_problem_hash="ph_current_ui_scope",
        current_problem_hash_mode="legacy",
        default_objectives=("comfort", "roll", "energy"),
        objectives_text_fn=lambda values: "\n".join(values),
        penalty_key_default="penalty_total",
        current_penalty_tol=0.0,
        load_log_text=lambda _path: "",
        rerun_fn=lambda _st: events.append(("rerun", None)),
        discover_runs_fn=lambda *_args, **_kwargs: [summary],
        format_run_choice_fn=lambda item: item.run_dir.name,
        render_details_fn=lambda _st, item, **kwargs: events.append(
            (
                "details",
                item.run_dir.name,
                kwargs["current_objective_keys"],
                kwargs["current_penalty_key"],
                kwargs["current_problem_hash"],
                kwargs["current_problem_hash_mode"],
            )
        ),
        render_pointer_actions_fn=lambda _st, item, **kwargs: events.append(
            ("actions", item.run_dir.name, kwargs["make_latest_label"], kwargs["open_results_label"])
        ),
    )

    assert ("selectbox", "Выберите run для разбора") in st.calls
    assert ("metric", ("DONE", 12)) in st.calls
    assert ("metric", ("RUNNING", 1)) in st.calls
    assert any(kind == "caption" and "Если вы запускаете оптимизации последовательно" in text for kind, text in st.calls)
    assert events == [
        ("details", "run-1", ("comfort", "roll"), "penalty_total", "ph_current_ui_scope", "legacy"),
        ("actions", "run-1", "Сделать текущей «последней оптимизацией»", "Открыть результаты выбранного run"),
    ]
