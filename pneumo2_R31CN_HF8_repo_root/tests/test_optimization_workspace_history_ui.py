from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_workspace_history_ui import (
    build_handoff_overview_rows,
    enrich_handoff_overview_rows,
    filter_handoff_overview_rows,
    handoff_quality_score,
    render_workspace_run_history_block,
    sort_handoff_overview_rows,
    with_active_job_placeholder,
)


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self, *, select_values: dict[str, object] | None = None, checkbox_values: dict[str, bool] | None = None, number_values: dict[str, int] | None = None, button_values: dict[str, bool] | None = None) -> None:
        self.session_state: dict[str, object] = {}
        self.calls: list[tuple[str, object]] = []
        self._select_values = dict(select_values or {})
        self._checkbox_values = dict(checkbox_values or {})
        self._number_values = dict(number_values or {})
        self._button_values = dict(button_values or {})

    def info(self, text: str) -> None:
        self.calls.append(("info", text))

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def markdown(self, text: str) -> None:
        self.calls.append(("markdown", text))

    def selectbox(self, label: str, **kwargs):
        self.calls.append(("selectbox", label))
        if label in self._select_values:
            return self._select_values[label]
        options = kwargs.get("options") or []
        index = int(kwargs.get("index", 0) or 0)
        return options[index] if options else None

    def checkbox(self, label: str, **kwargs) -> bool:
        self.calls.append(("checkbox", label))
        return bool(self._checkbox_values.get(label, kwargs.get("value", False)))

    def number_input(self, label: str, **kwargs) -> int:
        self.calls.append(("number_input", label))
        return int(self._number_values.get(label, kwargs.get("value", 0)))

    def button(self, label: str, **kwargs) -> bool:
        self.calls.append(("button", (label, dict(kwargs))))
        return bool(self._button_values.get(label, False))

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]

    def metric(self, label: str, value) -> None:
        self.calls.append(("metric", (label, value)))

    def dataframe(self, frame, **kwargs) -> None:
        self.calls.append(("dataframe", (frame.copy(), dict(kwargs))))


def test_workspace_history_handoff_quality_helpers_rank_and_filter_rows() -> None:
    rows = [
        {
            "run": "run-a",
            "status": "DONE",
            "preset": "ray/portfolio/q2",
            "budget": 84,
            "seeds": 6,
            "valid_rows": 9,
            "promotable": 7,
            "unique": 6,
            "pool": "promotable",
            "fragments": 4,
            "full_ring": "yes",
            "suite": "auto_ring",
        },
        {
            "run": "run-b",
            "status": "PARTIAL",
            "preset": "ray/q1",
            "budget": 60,
            "seeds": 2,
            "valid_rows": 8,
            "promotable": 2,
            "unique": 5,
            "pool": "ok_rows",
            "fragments": 2,
            "full_ring": "no",
            "suite": "auto_ring",
        },
    ]

    assert handoff_quality_score(rows[0]) > handoff_quality_score(rows[1])
    enriched = enrich_handoff_overview_rows(rows)
    assert enriched[0]["quality_score"] > enriched[1]["quality_score"]
    filtered = filter_handoff_overview_rows(enriched, full_ring_only=True, done_only=True, min_seeds=3)
    assert [row["run"] for row in filtered] == ["run-a"]
    ranked = sort_handoff_overview_rows(enriched, sort_mode="Лучшие для continuation")
    assert [row["run"] for row in ranked] == ["run-a", "run-b"]
    cheapest = sort_handoff_overview_rows(enriched, sort_mode="Минимальный budget")
    assert [row["run"] for row in cheapest] == ["run-b", "run-a"]


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
        start_handoff_fn=lambda run_dir: events.append(("handoff_start", run_dir)) or True,
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
                callable(kwargs["start_handoff_fn"]),
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
        ("details", "run-1", ("comfort", "roll"), "penalty_total", "ph_current_ui_scope", "legacy", True),
        ("actions", "run-1", "Сделать текущей «последней оптимизацией»", "Открыть результаты выбранного run"),
    ]


def test_workspace_history_ui_surfaces_handoff_comparison_rows() -> None:
    st = _FakeStreamlit()
    events: list[tuple[str, object]] = []
    staged = SimpleNamespace(
        run_dir=Path("C:/tmp/run-stage"),
        status_label="DONE",
        pipeline_mode="staged",
        row_count=14,
        done_count=0,
        backend="StageRunner",
        error_count=0,
        running_count=0,
        handoff_available=True,
        handoff_target_run_dir=Path("C:/tmp/run-coord"),
        handoff_preset_tag="ray/portfolio/q2",
        handoff_budget=84,
        handoff_seed_count=6,
        handoff_staged_rows_ok=9,
        handoff_promotable_rows=7,
        handoff_unique_param_candidates=6,
        handoff_selection_pool="promotable",
        handoff_fragment_count=4,
        handoff_has_full_ring=True,
        handoff_suite_family="auto_ring",
    )
    coord = SimpleNamespace(
        run_dir=Path("C:/tmp/run-coord"),
        status_label="PARTIAL",
        pipeline_mode="coordinator",
        row_count=0,
        done_count=12,
        backend="ray",
        error_count=1,
        running_count=2,
        handoff_available=False,
    )

    rows = build_handoff_overview_rows([staged, coord])
    assert rows == [
        {
            "__run_dir": "C:\\tmp\\run-stage",
            "__target_run_dir": "C:\\tmp\\run-coord",
            "run": "run-stage",
            "status": "DONE",
            "preset": "ray/portfolio/q2",
            "budget": 84,
            "seeds": 6,
            "valid_rows": 9,
            "promotable": 7,
            "unique": 6,
            "pool": "promotable",
            "fragments": 4,
            "full_ring": "yes",
            "suite": "auto_ring",
        }
    ]

    render_workspace_run_history_block(
        st,
        workspace_dir=Path("C:/tmp/workspace"),
        active_job=None,
        session_state={"opt_objectives": "comfort\nroll", "opt_penalty_key": "penalty_total"},
        start_handoff_fn=lambda run_dir: events.append(("handoff_start", run_dir)) or True,
        current_problem_hash="ph_current_ui_scope",
        current_problem_hash_mode="legacy",
        default_objectives=("comfort", "roll", "energy"),
        objectives_text_fn=lambda values: "\n".join(values),
        penalty_key_default="penalty_total",
        current_penalty_tol=0.0,
        load_log_text=lambda _path: "",
        rerun_fn=lambda _st: events.append(("rerun", None)),
        discover_runs_fn=lambda *_args, **_kwargs: [staged, coord],
        format_run_choice_fn=lambda item: item.run_dir.name,
        render_details_fn=lambda _st, item, **kwargs: events.append(("details", item.run_dir.name)),
        render_pointer_actions_fn=lambda _st, item, **kwargs: events.append(("actions", item.run_dir.name)),
    )

    assert any(kind == "markdown" and "Сравнение handoff-решений" in text for kind, text in st.calls)
    df_calls = [payload for kind, payload in st.calls if kind == "dataframe"]
    assert len(df_calls) == 1
    frame, kwargs = df_calls[0]
    assert list(frame["preset"]) == ["ray/portfolio/q2"]
    assert list(frame["budget"]) == [84]
    assert list(frame["seeds"]) == [6]
    assert list(frame["quality_score"]) == [91.1]
    assert kwargs["use_container_width"] is True
    assert kwargs["hide_index"] is True
    assert events[:2] == [("details", "run-stage"), ("actions", "run-stage")]
    assert any(
        kind == "button"
        and isinstance(payload, tuple)
        and payload[0] == "Запустить лучший handoff (ray/portfolio/q2)"
        and payload[1].get("type") == "primary"
        for kind, payload in st.calls
    )


def test_workspace_history_ui_applies_quick_handoff_filters() -> None:
    st = _FakeStreamlit(
        select_values={"Ranking handoff": "Минимальный budget", "Выберите run для разбора": str(Path("C:/tmp/run-stage-a"))},
        checkbox_values={"Только full-ring": True, "Только DONE": True},
        number_values={"Мин. seeds": 5},
    )
    staged_a = SimpleNamespace(
        run_dir=Path("C:/tmp/run-stage-a"),
        status_label="DONE",
        pipeline_mode="staged",
        row_count=14,
        done_count=0,
        backend="StageRunner",
        error_count=0,
        running_count=0,
        handoff_available=True,
        handoff_target_run_dir=Path("C:/tmp/run-coord-a"),
        handoff_preset_tag="ray/portfolio/q2",
        handoff_budget=84,
        handoff_seed_count=6,
        handoff_staged_rows_ok=9,
        handoff_promotable_rows=7,
        handoff_unique_param_candidates=6,
        handoff_selection_pool="promotable",
        handoff_fragment_count=4,
        handoff_has_full_ring=True,
        handoff_suite_family="auto_ring",
    )
    staged_b = SimpleNamespace(
        run_dir=Path("C:/tmp/run-stage-b"),
        status_label="PARTIAL",
        pipeline_mode="staged",
        row_count=11,
        done_count=0,
        backend="StageRunner",
        error_count=0,
        running_count=0,
        handoff_available=True,
        handoff_target_run_dir=Path("C:/tmp/run-coord-b"),
        handoff_preset_tag="ray/q1",
        handoff_budget=60,
        handoff_seed_count=2,
        handoff_staged_rows_ok=8,
        handoff_promotable_rows=2,
        handoff_unique_param_candidates=5,
        handoff_selection_pool="ok_rows",
        handoff_fragment_count=2,
        handoff_has_full_ring=False,
        handoff_suite_family="auto_ring",
    )

    render_workspace_run_history_block(
        st,
        workspace_dir=Path("C:/tmp/workspace"),
        active_job=None,
        session_state={"opt_objectives": "comfort\nroll", "opt_penalty_key": "penalty_total"},
        start_handoff_fn=None,
        current_problem_hash="ph_current_ui_scope",
        current_problem_hash_mode="legacy",
        default_objectives=("comfort", "roll", "energy"),
        objectives_text_fn=lambda values: "\n".join(values),
        penalty_key_default="penalty_total",
        current_penalty_tol=0.0,
        load_log_text=lambda _path: "",
        rerun_fn=lambda _st: None,
        discover_runs_fn=lambda *_args, **_kwargs: [staged_a, staged_b],
        format_run_choice_fn=lambda item: str(item.run_dir),
        render_details_fn=lambda *_args, **_kwargs: None,
        render_pointer_actions_fn=lambda *_args, **_kwargs: None,
    )

    assert ("checkbox", "Только full-ring") in st.calls
    assert ("checkbox", "Только DONE") in st.calls
    assert ("number_input", "Мин. seeds") in st.calls
    df_calls = [payload for kind, payload in st.calls if kind == "dataframe"]
    assert len(df_calls) == 1
    frame, _kwargs = df_calls[0]
    assert list(frame["run"]) == ["run-stage-a"]
    assert any(
        kind == "caption" and "Quick best handoff сейчас" in text and "run=run-stage-a" in text
        for kind, text in st.calls
    )


def test_workspace_history_ui_can_start_best_handoff_from_comparison_block() -> None:
    st = _FakeStreamlit(
        button_values={"Запустить лучший handoff (ray/portfolio/q2)": True},
    )
    events: list[tuple[str, object]] = []
    staged_a = SimpleNamespace(
        run_dir=Path("C:/tmp/run-stage-a"),
        status_label="DONE",
        pipeline_mode="staged",
        row_count=14,
        done_count=0,
        backend="StageRunner",
        error_count=0,
        running_count=0,
        handoff_available=True,
        handoff_target_run_dir=Path("C:/tmp/run-coord-a"),
        handoff_preset_tag="ray/portfolio/q2",
        handoff_budget=84,
        handoff_seed_count=6,
        handoff_staged_rows_ok=9,
        handoff_promotable_rows=7,
        handoff_unique_param_candidates=6,
        handoff_selection_pool="promotable",
        handoff_fragment_count=4,
        handoff_has_full_ring=True,
        handoff_suite_family="auto_ring",
    )
    staged_b = SimpleNamespace(
        run_dir=Path("C:/tmp/run-stage-b"),
        status_label="DONE",
        pipeline_mode="staged",
        row_count=12,
        done_count=0,
        backend="StageRunner",
        error_count=0,
        running_count=0,
        handoff_available=True,
        handoff_target_run_dir=Path("C:/tmp/run-coord-b"),
        handoff_preset_tag="ray/q1",
        handoff_budget=60,
        handoff_seed_count=2,
        handoff_staged_rows_ok=8,
        handoff_promotable_rows=2,
        handoff_unique_param_candidates=5,
        handoff_selection_pool="ok_rows",
        handoff_fragment_count=2,
        handoff_has_full_ring=False,
        handoff_suite_family="auto_ring",
    )

    render_workspace_run_history_block(
        st,
        workspace_dir=Path("C:/tmp/workspace"),
        active_job=None,
        session_state={"opt_objectives": "comfort\nroll", "opt_penalty_key": "penalty_total"},
        start_handoff_fn=lambda run_dir: events.append(("handoff_start", run_dir)) or True,
        current_problem_hash="ph_current_ui_scope",
        current_problem_hash_mode="legacy",
        default_objectives=("comfort", "roll", "energy"),
        objectives_text_fn=lambda values: "\n".join(values),
        penalty_key_default="penalty_total",
        current_penalty_tol=0.0,
        load_log_text=lambda _path: "",
        rerun_fn=lambda _st: events.append(("rerun", None)),
        discover_runs_fn=lambda *_args, **_kwargs: [staged_a, staged_b],
        format_run_choice_fn=lambda item: item.run_dir.name,
        render_details_fn=lambda _st, item, **kwargs: events.append(("details", item.run_dir.name)),
        render_pointer_actions_fn=lambda _st, item, **kwargs: events.append(("actions", item.run_dir.name)),
    )

    assert ("handoff_start", Path("C:/tmp/run-stage-a").resolve()) in events
    assert st.session_state["__opt_history_selected_run_dir"] == str(Path("C:/tmp/run-coord-a").resolve())


def test_workspace_history_ui_prefers_active_pending_job_placeholder_when_selected() -> None:
    pending_run = Path("C:/tmp/run-coord-pending").resolve()
    st = _FakeStreamlit(
        select_values={"Выберите run для разбора": str(pending_run)},
    )
    st.session_state["__opt_history_selected_run_dir"] = str(pending_run)
    events: list[tuple[str, object]] = []
    staged = SimpleNamespace(
        run_dir=Path("C:/tmp/run-stage-a"),
        status_label="DONE",
        pipeline_mode="staged",
        row_count=14,
        done_count=0,
        backend="StageRunner",
        error_count=0,
        running_count=0,
        handoff_available=True,
        handoff_target_run_dir=pending_run,
        handoff_preset_tag="ray/portfolio/q2",
        handoff_budget=84,
        handoff_seed_count=6,
        handoff_staged_rows_ok=9,
        handoff_promotable_rows=7,
        handoff_unique_param_candidates=6,
        handoff_selection_pool="promotable",
        handoff_fragment_count=4,
        handoff_has_full_ring=True,
        handoff_suite_family="auto_ring",
    )
    active_job = SimpleNamespace(
        run_dir=pending_run,
        started_ts=123.0,
        log_path=pending_run / "coordinator.log",
        backend="Handoff/ray/portfolio/q2",
        pipeline_mode="coordinator",
    )

    enriched = with_active_job_placeholder([staged], active_job=active_job)
    assert enriched[0].run_dir == pending_run
    assert enriched[0].status_label == "RUNNING"

    render_workspace_run_history_block(
        st,
        workspace_dir=Path("C:/tmp/workspace"),
        active_job=active_job,
        session_state={"opt_objectives": "comfort\nroll", "opt_penalty_key": "penalty_total"},
        start_handoff_fn=None,
        current_problem_hash="ph_current_ui_scope",
        current_problem_hash_mode="legacy",
        default_objectives=("comfort", "roll", "energy"),
        objectives_text_fn=lambda values: "\n".join(values),
        penalty_key_default="penalty_total",
        current_penalty_tol=0.0,
        load_log_text=lambda _path: "",
        rerun_fn=lambda _st: None,
        discover_runs_fn=lambda *_args, **_kwargs: [staged],
        format_run_choice_fn=lambda item: item.run_dir.name,
        render_handoff_overview_fn=None,
        render_details_fn=lambda _st, item, **kwargs: events.append(
            ("details", item.run_dir.name, item.pipeline_mode, item.status_label)
        ),
        render_pointer_actions_fn=lambda _st, item, **kwargs: events.append(("actions", item.run_dir.name)),
    )

    assert ("details", "run-coord-pending", "coordinator", "RUNNING") in events
    assert ("metric", ("Статус", "RUNNING")) in st.calls
    assert ("metric", ("DONE", 0)) in st.calls
    assert ("metric", ("RUNNING", 1)) in st.calls
