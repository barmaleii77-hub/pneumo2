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
    assert ("write", "**Набор целей оптимизации:** comfort, roll") in st.calls
    assert ("write", "**Жёсткий порог по штрафу:** `penalty_total` (tol=0.25)") in st.calls
    assert any(kind == "info" and "набор целей, ключ штрафа, допуск по штрафу" in text for kind, text in st.calls)
    assert ("code", "line1\nline2") in st.calls
