from __future__ import annotations

from pneumo_solver_ui.optimization_contract_summary_ui import (
    compare_objective_contract_to_current,
    format_hard_gate,
    normalize_objective_keys,
    render_objective_contract_drift_warning,
    render_objective_contract_summary,
)


class _FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def write(self, text: str) -> None:
        self.calls.append(("write", text))

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def info(self, text: str) -> None:
        self.calls.append(("info", text))


def test_contract_summary_helpers_format_and_compare_contracts() -> None:
    assert normalize_objective_keys([" a ", "", "b"]) == ["a", "b"]
    assert normalize_objective_keys(" comfort,\nroll ; energy ") == ["comfort", "roll", "energy"]
    assert format_hard_gate("penalty_total", 0.5) == "`penalty_total` (tol=0.5)"
    assert compare_objective_contract_to_current(
        objective_keys="a,\nb",
        penalty_key="penalty_total",
        penalty_tol=0.5,
        current_objective_keys=["a", "c"],
        current_penalty_key="penalty_other",
        current_penalty_tol=0.0,
    ) == ["objective stack", "penalty key", "penalty tol"]


def test_contract_summary_helpers_render_summary_and_warning() -> None:
    st = _FakeStreamlit()

    rendered = render_objective_contract_summary(
        st,
        objective_keys="comfort,\nroll",
        penalty_key="penalty_total",
        penalty_tol=0.25,
        objective_contract_path="C:/tmp/objective_contract.json",
    )
    warned = render_objective_contract_drift_warning(
        st,
        ["objective stack", "penalty key"],
    )

    assert rendered is True
    assert warned is True
    assert ("write", "**Objective stack:** comfort, roll") in st.calls
    assert ("write", "**Hard gate:** `penalty_total` (tol=0.25)") in st.calls
    assert ("caption", "Objective contract artifact: C:/tmp/objective_contract.json") in st.calls
    assert any(kind == "info" and "objective stack, penalty key" in text for kind, text in st.calls)
