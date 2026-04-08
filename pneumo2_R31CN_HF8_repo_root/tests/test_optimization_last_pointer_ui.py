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
    assert ("markdown", "**Seed/promotion policy (текущая стадия)**") in st.calls


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
        "opt_summary": SimpleNamespace(result_path="C:/tmp/run/results_all.csv"),
        "packaging_snapshot": packaging_snapshot,
    }

    rendered = render_last_optimization_pointer_summary(
        st,
        snap,
        missing_message="missing",
        success_message="ok",
    )

    assert rendered is True
    assert ("success", "ok") in st.calls
    assert ("write", "**Objective stack:** a, b") in st.calls
    assert ("write", "**Hard gate:** `penalty_total` (tol=0.25)") in st.calls
    assert ("markdown", "**Packaging snapshot (last run)**") in st.calls
    assert any(kind == "warning" and "spring↔spring=1" in text for kind, text in st.calls)
