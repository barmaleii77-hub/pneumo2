from __future__ import annotations

from types import SimpleNamespace

from pneumo_solver_ui.optimization_last_pointer_ui import (
    render_last_optimization_pointer_summary,
)


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def info(self, text: str) -> None:
        self.calls.append(("info", text))

    def success(self, text: str) -> None:
        self.calls.append(("success", text))

    def write(self, text: str) -> None:
        self.calls.append(("write", text))

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


def test_render_last_pointer_summary_handles_missing_pointer() -> None:
    st = _FakeStreamlit()

    rendered = render_last_optimization_pointer_summary(
        st,
        {},
        missing_message="missing",
    )

    assert rendered is False
    assert ("info", "missing") in st.calls
    assert any(
        kind == "markdown" and "Политика отбора и продвижения" in text and "текущая стадия" in text
        for kind, text in st.calls
    )


def test_render_last_pointer_summary_renders_shared_sections() -> None:
    st = _FakeStreamlit()
    packaging_snapshot = SimpleNamespace(
        rows_with_packaging=4,
        packaging_truth_ready_rows=3,
        packaging_verification_pass_rows=2,
        runtime_fallback_rows=1,
        spring_host_interference_rows=0,
        spring_pair_interference_rows=1,
        status_counts=[("complete", 3), ("partial", 1)],
    )
    snap = {
        "raw": {"updated_at": "2026-04-08T15:00:00Z", "run_dir": "C:/tmp/run"},
        "meta": {
            "backend": "ray",
            "ts": "2026-04-08T15:00:00Z",
            "objective_keys": ["a", "b"],
            "penalty_key": "penalty_total",
            "penalty_tol": 0.25,
        },
        "run_dir": "C:/tmp/run",
        "mode_label": "StageRunner",
        "sp_payload": {"status": "ok", "ts": "2026-04-08T15:01:00Z"},
        "live_policy": {
            "available": True,
            "requested_mode": "adaptive",
            "effective_mode": "adaptive",
            "policy_name": "stage2_focus",
            "summary_line": "focus candidates only",
        },
        "opt_summary": SimpleNamespace(
            result_path="C:/tmp/run/results_all.csv",
            problem_hash="ph_scope_demo_123456",
            problem_hash_mode="legacy",
            baseline_source_kind="scoped",
            baseline_source_label="scoped baseline",
            baseline_source_path="C:/tmp/workspace/baselines/by_problem/p_demo/baseline_best.json",
            handoff_preset_tag="ray/portfolio/q2",
            handoff_budget=84,
            handoff_seed_count=6,
            handoff_suite_family="auto_ring",
            handoff_requires_full_ring_validation=True,
            handoff_reason_lines=(
                "Почему этот preset: ring-fragments=4, full-ring=yes; seed-bridge взял 6 кандидатов.",
                "Источник handoff-профиля: staged_then_coordinator; proposer=portfolio (auto_tuner), q=2 (auto_tuner), budget=84.",
            ),
        ),
        "packaging_snapshot": packaging_snapshot,
    }

    rendered = render_last_optimization_pointer_summary(
        st,
        snap,
        current_problem_hash="ph_scope_demo_123456",
        current_problem_hash_mode="legacy",
        missing_message="missing",
        success_message="ok",
    )

    assert rendered is True
    assert ("success", "ok") in st.calls
    assert ("write", "**Набор целей оптимизации:** a, b") in st.calls
    assert ("write", "**Жёсткий порог по штрафу:** `penalty_total` (tol=0.25)") in st.calls
    assert ("write", "**Baseline source:** scoped baseline") in st.calls
    assert ("write", "**Problem scope:** `ph_scope_dem`") in st.calls
    assert any(kind == "caption" and "Hash mode:" in text and "legacy" in text for kind, text in st.calls)
    assert any(
        kind == "caption"
        and "Baseline override at launch:" in text
        and "baseline_best.json" in text
        for kind, text in st.calls
    )
    assert any(kind == "caption" and "matches current launch contract" in text for kind, text in st.calls)
    assert any(kind == "caption" and "Hash mode matches current launch contract" in text for kind, text in st.calls)
    assert ("write", "**Coordinator handoff:** ray/portfolio/q2") in st.calls
    assert any(kind == "caption" and "budget=84" in text and "seed-candidates=6" in text for kind, text in st.calls)
    assert any(kind == "caption" and "seed-bridge взял 6 кандидатов" in text for kind, text in st.calls)
    assert ("markdown", "**Сводка по геометрии узлов (последний run)**") in st.calls
    assert any(kind == "warning" for kind, _ in st.calls)
