from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def _cmd_arg_value(cmd_args: list[str], flag: str) -> str:
    if flag not in cmd_args:
        return ""
    idx = cmd_args.index(flag) + 1
    if idx >= len(cmd_args):
        return ""
    return str(cmd_args[idx] or "").strip()


def handoff_preset_tag(summary: Mapping[str, Any] | dict[str, Any]) -> str:
    backend = str(summary.get("backend") or "coordinator").strip() or "coordinator"
    proposer = str(summary.get("proposer") or "auto").strip() or "auto"
    q_eff = max(1, int(summary.get("q", 1) or 1))
    bits = [backend]
    if proposer and proposer != "auto":
        bits.append(proposer)
    if q_eff > 1:
        bits.append(f"q{q_eff}")
    return "/".join(bits)


def recommended_handoff_button_label(summary: Mapping[str, Any] | dict[str, Any]) -> str:
    return f"Запустить рекомендованный full-ring coordinator ({handoff_preset_tag(summary)})"


def recommended_handoff_button_help(summary: Mapping[str, Any] | dict[str, Any]) -> str:
    budget = int(summary.get("budget", 0) or 0)
    seed_count = int(summary.get("seed_count", 0) or 0)
    return (
        "Запустить seeded coordinator handoff с уже подобранным профилем full-ring проверки: "
        f"{handoff_preset_tag(summary)}, budget={budget}, seed-candidates={seed_count}."
    )


def handoff_recommendation_reason_lines(summary: Mapping[str, Any] | dict[str, Any]) -> list[str]:
    reason = dict(summary.get("recommendation_reason") or {})
    if not reason:
        return []

    fragment_count = int(reason.get("fragment_count", 0) or 0)
    has_full_ring = bool(reason.get("has_full_ring", False))
    seed_bridge = dict(reason.get("seed_bridge") or {})
    staged_rows_ok = int(seed_bridge.get("staged_rows_ok", 0) or 0)
    promotable_rows = int(seed_bridge.get("promotable_rows", 0) or 0)
    unique_param_candidates = int(seed_bridge.get("unique_param_candidates", 0) or 0)
    selection_pool = str(seed_bridge.get("selection_pool") or "none")
    seed_count = int(seed_bridge.get("seed_count", summary.get("seed_count", 0)) or 0)
    budget = int(summary.get("budget", 0) or 0)
    proposer = str(summary.get("proposer") or "auto")
    q_eff = max(1, int(summary.get("q", 1) or 1))
    pipeline_hint = str(reason.get("pipeline_hint") or "").strip()
    budget_formula = dict(reason.get("budget_formula") or {})
    base = int(budget_formula.get("base", 40) or 40)
    per_fragment = int(budget_formula.get("per_fragment", 4) or 4)
    per_seed = int(budget_formula.get("per_seed", 2) or 2)
    full_ring_bonus = int(budget_formula.get("full_ring_bonus", 0) or 0)
    proposer_source = str(reason.get("proposer_source") or "default")
    q_source = str(reason.get("q_source") or "default")

    ring_shape_bits = [f"ring-fragments={fragment_count}"]
    if has_full_ring:
        ring_shape_bits.append("full-ring=yes")
    line1 = (
        "Почему этот preset: "
        + ", ".join(ring_shape_bits)
        + "; seed-bridge взял "
        + f"{seed_count} кандидатов из {unique_param_candidates} уникальных "
        + f"({promotable_rows} promotable / {staged_rows_ok} valid staged rows, pool={selection_pool})."
    )

    budget_expr = f"{base} + {per_fragment}*fragments + {per_seed}*seeds"
    if full_ring_bonus > 0:
        budget_expr += f" + {full_ring_bonus}(full-ring)"
    line2 = (
        f"Источник handoff-профиля: {pipeline_hint or 'staged_then_manual'}; "
        f"proposer={proposer} ({proposer_source}), q={q_eff} ({q_source}), "
        f"budget={budget} по эвристике {budget_expr}."
    )
    return [line1, line2]


def summarize_handoff_payload(
    payload: Mapping[str, Any] | None,
    *,
    source_run_dir: Path | str | None = None,
    plan_path: Path | str | None = None,
) -> dict[str, Any]:
    payload_map = dict(payload or {})
    cmd_args = [str(item) for item in list(payload_map.get("cmd_args") or [])]
    proposer = _cmd_arg_value(cmd_args, "--proposer")
    target_run_dir_raw = _cmd_arg_value(cmd_args, "--run-dir")
    target_run_dir = Path(target_run_dir_raw).resolve() if target_run_dir_raw else None
    source_run = Path(source_run_dir).resolve() if source_run_dir is not None else None
    plan = Path(plan_path).resolve() if plan_path is not None else None
    summary = {
        "available": bool(payload_map),
        "source_run_dir": source_run,
        "plan_path": plan,
        "target_run_dir": target_run_dir,
        "backend": str(payload_map.get("recommended_backend") or ""),
        "budget": int(payload_map.get("recommended_budget", 0) or 0),
        "q": max(1, int(payload_map.get("recommended_q", 1) or 1)),
        "seed_count": int(payload_map.get("seed_count", 0) or 0),
        "suite_family": str((payload_map.get("suite_analysis") or {}).get("family") or ""),
        "proposer": str(payload_map.get("recommended_proposer") or proposer or ""),
        "requires_full_ring_validation": bool(payload_map.get("requires_full_ring_validation", False)),
        "recommendation_reason": dict(payload_map.get("recommendation_reason") or {}),
        "payload": payload_map,
    }
    summary["preset_tag"] = handoff_preset_tag(summary)
    summary["reason_lines"] = tuple(handoff_recommendation_reason_lines(summary))
    return summary


__all__ = [
    "handoff_preset_tag",
    "handoff_recommendation_reason_lines",
    "recommended_handoff_button_help",
    "recommended_handoff_button_label",
    "summarize_handoff_payload",
]
