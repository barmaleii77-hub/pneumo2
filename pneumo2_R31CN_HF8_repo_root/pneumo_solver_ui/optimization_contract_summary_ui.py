from __future__ import annotations

from typing import Any, Iterable


def normalize_objective_keys(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def format_hard_gate(penalty_key: Any, penalty_tol: Any = None) -> str:
    key = str(penalty_key or "").strip()
    if not key:
        return ""
    hard_gate = f"`{key}`"
    try:
        if penalty_tol is not None:
            hard_gate += f" (tol={float(penalty_tol):g})"
    except Exception:
        pass
    return hard_gate


def render_objective_contract_summary(
    st: Any,
    *,
    objective_keys: Any,
    penalty_key: Any,
    penalty_tol: Any = None,
    objective_contract_path: Any = None,
) -> bool:
    rendered = False
    normalized_objectives = normalize_objective_keys(objective_keys)
    if normalized_objectives:
        st.write("**Objective stack:** " + ", ".join(normalized_objectives))
        rendered = True

    hard_gate = format_hard_gate(penalty_key, penalty_tol)
    if hard_gate:
        st.write(f"**Hard gate:** {hard_gate}")
        rendered = True

    if objective_contract_path is not None:
        st.caption(f"Objective contract artifact: {objective_contract_path}")
        rendered = True

    return rendered


def compare_objective_contract_to_current(
    *,
    objective_keys: Any,
    penalty_key: Any,
    penalty_tol: Any,
    current_objective_keys: Iterable[Any],
    current_penalty_key: Any,
    current_penalty_tol: Any,
) -> list[str]:
    diff_bits: list[str] = []
    normalized_objectives = tuple(normalize_objective_keys(objective_keys))
    normalized_current_objectives = tuple(str(x).strip() for x in current_objective_keys if str(x).strip())

    if normalized_objectives and normalized_objectives != normalized_current_objectives:
        diff_bits.append("objective stack")

    normalized_penalty_key = str(penalty_key or "").strip()
    normalized_current_penalty_key = str(current_penalty_key or "").strip()
    if normalized_penalty_key and normalized_penalty_key != normalized_current_penalty_key:
        diff_bits.append("penalty key")

    try:
        if penalty_tol is not None and float(penalty_tol) != float(current_penalty_tol):
            diff_bits.append("penalty tol")
    except Exception:
        pass

    return diff_bits


def render_objective_contract_drift_warning(
    st: Any,
    diff_bits: Iterable[str],
    *,
    subject: str = "Выбранный run",
    against: str = "текущие поля UI",
) -> bool:
    normalized = [str(x).strip() for x in diff_bits if str(x).strip()]
    if not normalized:
        return False
    st.info(
        f"{subject} собран на другом objective-contract, чем {against} ("
        + ", ".join(normalized)
        + "). Это нормально для честного сравнения исторических запусков; "
        "в HF8 coordinator resume/cache уже различает такие контракты по problem_hash."
    )
    return True


__all__ = [
    "compare_objective_contract_to_current",
    "format_hard_gate",
    "normalize_objective_keys",
    "render_objective_contract_drift_warning",
    "render_objective_contract_summary",
]
