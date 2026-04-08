from __future__ import annotations

from pneumo_solver_ui.optimization_stage_policy_runtime_ui import (
    render_stage_policy_runtime_snapshot,
)


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def markdown(self, text: str) -> None:
        self.calls.append(("markdown", text))

    def metric(self, label: str, value) -> None:
        self.calls.append(("metric", f"{label}={value}"))

    def warning(self, text: str) -> None:
        self.calls.append(("warning", text))

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]


def test_stage_policy_runtime_ui_handles_missing_progress() -> None:
    st = _FakeStreamlit()

    rendered = render_stage_policy_runtime_snapshot(
        st,
        progress_payload={},
        staged_summary={},
        policy={},
    )

    assert rendered is False
    assert any(kind == "caption" and "StageRunner progress.json ещё не записан" in text for kind, text in st.calls)


def test_stage_policy_runtime_ui_renders_metrics_and_policy_details() -> None:
    st = _FakeStreamlit()

    rendered = render_stage_policy_runtime_snapshot(
        st,
        progress_payload={"stage": "stage1_long", "idx": 1},
        staged_summary={"stage_rows_current": 7, "total_rows_live": 15, "stage_elapsed_sec": 42.0},
        policy={
            "available": True,
            "requested_mode": "adaptive",
            "effective_mode": "adaptive",
            "policy_name": "stage1_focus",
            "summary_line": "focus first",
            "target_seed_count": 5,
            "selected_counts": {"total": 4},
            "focus_budget": 3,
            "explore_budget": 2,
            "priority_params": ["foo", "bar"],
            "underfilled": True,
            "underfill_message": "not enough feasible seeds",
            "gate_reason_preview": "penalty gate",
        },
    )

    assert rendered is True
    assert ("metric", "Стадия=stage1_long") in st.calls
    assert ("metric", "Stage rows=7") in st.calls
    assert ("metric", "Всего live rows=15") in st.calls
    assert ("metric", "Время стадии, с=42.0") in st.calls
    assert ("markdown", "**Seed/promotion policy (текущая стадия)**") in st.calls
    assert ("metric", "Target seeds=5") in st.calls
    assert ("metric", "Selected=4") in st.calls
    assert any(kind == "warning" and "Seed budget underfilled" in text for kind, text in st.calls)
    assert any(kind == "caption" and "Main gate reasons: penalty gate" in text for kind, text in st.calls)
