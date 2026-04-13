from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_run_history_details_ui import (
    render_optimization_run_log_tail,
    render_selected_optimization_run_details,
)


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def write(self, text: str) -> None:
        self.calls.append(("write", text))

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def warning(self, text: str) -> None:
        self.calls.append(("warning", text))

    def info(self, text: str) -> None:
        self.calls.append(("info", text))

    def markdown(self, text: str) -> None:
        self.calls.append(("markdown", text))

    def metric(self, label: str, value) -> None:
        self.calls.append(("metric", f"{label}={value}"))

    def code(self, text: str) -> None:
        self.calls.append(("code", text))

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]


def test_run_history_log_tail_renderer_handles_empty_log() -> None:
    st = _FakeStreamlit()

    rendered = render_optimization_run_log_tail(
        st,
        Path("C:/tmp/run.log"),
        load_log_text=lambda _: "",
    )

    assert rendered is False
    assert any(kind == "caption" and "Лог-файл существует, но сейчас пуст" in text for kind, text in st.calls)


def test_selected_run_details_renderer_surfaces_contract_packaging_and_log() -> None:
    st = _FakeStreamlit()
    summary = SimpleNamespace(
        backend="ray",
        run_dir=Path("C:/tmp/run"),
        result_path=None,
        started_at="2026-04-08 20:00:00",
        note="note text",
        last_error="error text",
        problem_hash="ph_history_scope_987654",
        problem_hash_mode="legacy",
        baseline_source_label="scoped baseline",
        baseline_source_path=Path("C:/tmp/workspace/baselines/by_problem/p_demo/baseline_best.json"),
        objective_keys=("comfort", "roll"),
        penalty_key="penalty_total",
        penalty_tol=0.25,
        objective_contract_path=Path("C:/tmp/objective_contract.json"),
        log_path=Path("C:/tmp/run.log"),
        handoff_preset_tag="ray/portfolio/q2",
        handoff_budget=84,
        handoff_seed_count=6,
        handoff_suite_family="auto_ring",
        handoff_requires_full_ring_validation=True,
        handoff_reason_lines=(
            "Почему этот preset: ring-fragments=4, full-ring=yes; seed-bridge взял 6 кандидатов.",
            "Источник handoff-профиля: staged_then_coordinator; proposer=portfolio (auto_tuner), q=2 (auto_tuner), budget=84.",
        ),
        handoff_plan_path=Path("C:/tmp/run/coordinator_handoff/coordinator_handoff_plan.json"),
        runtime_summary={
            "done": 12,
            "budget": 84,
            "trial_health": {"done": 12, "running": 0, "error": 1},
            "penalty_gate": {
                "infeasible_done": 2,
                "penalty_key": "penalty_total",
                "penalty_tol": 0.25,
                "last_penalty": 0.9,
                "objective_drift": {"comfort": 0.5, "roll": 1.2},
            },
            "recent_errors": ["bad physics"],
        },
    )

    render_selected_optimization_run_details(
        st,
        summary,
        current_problem_hash="ph_current_scope_123456",
        current_objective_keys=("comfort", "pitch"),
        current_penalty_key="other_penalty",
        current_penalty_tol=0.0,
        current_problem_hash_mode="stable",
        load_log_text=lambda _: "line1\nline2",
    )

    assert ("write", "**Pipeline:** ray") in st.calls
    assert ("caption", "note text") in st.calls
    assert ("warning", "Последняя ошибка из артефактов: error text") in st.calls
    assert ("write", "**Problem scope:** `ph_history_s`") in st.calls
    assert any(kind == "caption" and "Hash mode:" in text and "legacy" in text for kind, text in st.calls)
    assert ("write", "**Baseline source:** scoped baseline") in st.calls
    assert ("caption", r"Baseline override at launch: `C:\tmp\workspace\baselines\by_problem\p_demo\baseline_best.json`") in st.calls
    assert any(kind == "warning" and "different optimization problem" in text for kind, text in st.calls)
    assert any(kind == "warning" and "Hash mode differs from current launch contract" in text for kind, text in st.calls)
    assert ("write", "**Coordinator handoff:** ray/portfolio/q2") in st.calls
    assert any(kind == "caption" and "budget=84" in text and "seed-candidates=6" in text for kind, text in st.calls)
    assert any(kind == "caption" and "seed-bridge взял 6 кандидатов" in text for kind, text in st.calls)
    assert any(kind == "caption" and "Handoff plan:" in text for kind, text in st.calls)
    assert ("write", "**Набор целей оптимизации:** comfort, roll") in st.calls
    assert ("write", "**Жёсткий порог по штрафу:** `penalty_total` (tol=0.25)") in st.calls
    assert any(kind == "info" and "набор целей, ключ штрафа, допуск по штрафу" in text for kind, text in st.calls)
    assert ("write", "**Final runtime diagnostics**") in st.calls
    assert any(kind == "caption" and "Final run progress:" in text and "done=12 / 84" in text for kind, text in st.calls)
    assert any(kind == "caption" and "Final run trial health:" in text and "DONE=12, RUNNING=0, ERROR=1" in text for kind, text in st.calls)
    assert any(
        kind == "caption"
        and "Final run penalty gate:" in text
        and "infeasible DONE=2" in text
        and "`penalty_total`=0.9 > 0.25" in text
        and "comfort +0.5" in text
        and "roll +1.2" in text
        for kind, text in st.calls
    )
    assert any(kind == "caption" and "Recent run errors:" in text and "bad physics" in text for kind, text in st.calls)
    assert ("code", "line1\nline2") in st.calls


def test_selected_run_details_renderer_marks_live_handoff_run() -> None:
    st = _FakeStreamlit()
    summary = SimpleNamespace(
        backend="Handoff/ray/portfolio/q2",
        run_dir=Path("C:/tmp/run_live"),
        result_path=None,
        started_at="",
        note="",
        last_error="",
        problem_hash="",
        problem_hash_mode="stable",
        baseline_source_label="",
        baseline_source_path=None,
        objective_keys=("comfort",),
        penalty_key="penalty_total",
        penalty_tol=0.0,
        objective_contract_path=None,
        log_path=Path("C:/tmp/run_live/coordinator.log"),
        pipeline_mode="coordinator",
        handoff_preset_tag="ray/portfolio/q2",
        handoff_budget=84,
        handoff_seed_count=6,
        handoff_suite_family="auto_ring",
        handoff_requires_full_ring_validation=True,
        handoff_reason_lines=(),
        handoff_plan_path=None,
    )

    render_selected_optimization_run_details(
        st,
        summary,
        current_problem_hash="",
        current_objective_keys=("comfort",),
        current_penalty_key="penalty_total",
        current_penalty_tol=0.0,
        current_problem_hash_mode="stable",
        load_log_text=lambda _: "live-log",
        active_run_dir=Path("C:/tmp/run_live"),
        active_launch_context={
            "kind": "handoff",
            "run_dir": str(Path("C:/tmp/run_live").resolve()),
            "source_run_dir": str(Path("C:/tmp/staged_seed_source").resolve()),
        },
        active_runtime_summary={
            "done": 5,
            "budget": 84,
            "tail_state": "trial=5 status=RUNNING",
            "trial_health": {"done": 5, "running": 2, "error": 1},
            "penalty_gate": {
                "infeasible_done": 1,
                "penalty_key": "penalty_total",
                "penalty_tol": 0.25,
                "last_penalty": 0.6,
                "objective_drift": {"comfort": 0.7, "energy": 3.5},
            },
            "recent_errors": ["bad physics", "solver diverged badly on wheel hop"],
            "handoff_provenance": {
                "source_run_name": "staged_seed_source",
                "selection_pool": "promotable",
                "seed_count": 6,
                "unique_param_candidates": 6,
                "promotable_rows": 7,
                "staged_rows_ok": 9,
                "pipeline_hint": "staged_then_coordinator",
                "fragment_count": 4,
                "has_full_ring": True,
            },
        },
    )

    assert any(
        kind == "info"
        and "LIVE NOW" in text
        and "seeded full-ring coordinator handoff" in text
        and "staged_seed_source" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "caption"
        and "done=5 / 84" in text
        and "trial=5 status=RUNNING" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "caption"
        and "DONE=5, RUNNING=2, ERROR=1" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "caption"
        and "Active handoff penalty gate:" in text
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
        and "solver diverged badly on wheel hop" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "caption"
        and "Handoff provenance:" in text
        and "source=staged_seed_source" in text
        and "pool=promotable" in text
        and "full-ring=yes" in text
        for kind, text in st.calls
    )


def test_selected_run_details_renderer_passes_handoff_callback_for_staged_run() -> None:
    st = _FakeStreamlit()
    events: list[tuple[str, object]] = []
    summary = SimpleNamespace(
        backend="stage",
        run_dir=Path("C:/tmp/staged_run"),
        result_path=None,
        started_at="2026-04-08 20:00:00",
        note="",
        last_error="",
        problem_hash="",
        problem_hash_mode="stable",
        baseline_source_label="",
        baseline_source_path=None,
        objective_keys=("comfort",),
        penalty_key="penalty_total",
        penalty_tol=0.0,
        objective_contract_path=None,
        log_path=Path("C:/tmp/run.log"),
        pipeline_mode="staged",
    )

    render_selected_optimization_run_details(
        st,
        summary,
        current_problem_hash="",
        current_objective_keys=("comfort",),
        current_penalty_key="penalty_total",
        current_penalty_tol=0.0,
        current_problem_hash_mode="stable",
        load_log_text=lambda _: "ok",
        start_handoff_fn=lambda run_dir: events.append(("start", run_dir)) or True,
        render_handoff_action_fn=lambda _st, **kwargs: events.append(
            (
                "handoff",
                kwargs["source_run_dir"],
                kwargs["start_handoff_fn"] is not None,
                kwargs["button_key"],
                kwargs.get("recommended_action", True),
                kwargs.get("button_label", ""),
            )
        ) or False,
    )

    assert (
        "handoff",
        Path("C:/tmp/staged_run"),
        True,
        "history_start_handoff_staged_run",
        True,
        "",
    ) in events
