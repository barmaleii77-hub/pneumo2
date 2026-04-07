from __future__ import annotations

"""Best-effort audit helpers for staged seed/promotion policy.

Why this module exists:
- live UI readers need one normalized place for the staged seed-selection audit contract;
- some runtime trees may only contain ``promotion_policy_decisions.csv`` and
  ``seed_points_manifest.json`` without a precomputed rich audit JSON;
- missing or partial audit data must degrade to a deterministic fallback instead
  of breaking the current-screen progress UI.

This module intentionally stays dependency-light and fail-soft.
"""

from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import json

AUDIT_JSON_NAME = "seed_selection_audit.json"


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if out != out or out in (float("inf"), float("-inf")):
        return float(default)
    return float(out)


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return bool(value)
    try:
        if value is not None and not isinstance(value, str):
            return bool(int(value))
    except Exception:
        pass
    txt = str(value or "").strip().lower()
    return txt in {"1", "true", "yes", "y", "on"}


def _count_rows(rows: Sequence[Mapping[str, Any]], key: str, *, empty_label: str = "unknown") -> Dict[str, int]:
    out: Dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or "").strip() or str(empty_label)
        out[label] = int(out.get(label, 0) + 1)
    return dict(sorted(out.items(), key=lambda kv: (-int(kv[1]), kv[0])))


def _top_reason(counts: Mapping[str, Any] | None) -> str:
    if not isinstance(counts, Mapping):
        return ""
    best_key = ""
    best_val = -1
    for key, value in counts.items():
        sval = str(key or "").strip()
        ival = _safe_int(value, 0)
        if not sval or ival <= 0:
            continue
        if ival > best_val or (ival == best_val and sval < best_key):
            best_key = sval
            best_val = ival
    return best_key


def _selected_rows(
    *,
    promotion_rows: Sequence[Mapping[str, Any]],
    seed_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if seed_rows:
        return [dict(row) for row in seed_rows if isinstance(row, Mapping)]
    return [dict(row) for row in promotion_rows if isinstance(row, Mapping) and _boolish(row.get("selected"))]


def build_seed_selection_audit(
    plan: Mapping[str, Any] | None,
    *,
    promotion_rows: Sequence[Mapping[str, Any]] | None,
    seed_rows: Sequence[Mapping[str, Any]] | None,
) -> Dict[str, Any]:
    """Build a normalized fallback audit from live runtime rows.

    The result is intentionally compact but structured enough for
    ``optimization_stage_policy_live`` to expose current-stage seed gating on the UI.
    """

    plan_map = _as_dict(plan)
    promo = [dict(row) for row in (promotion_rows or []) if isinstance(row, Mapping)]
    seeds = _selected_rows(promotion_rows=promo, seed_rows=[dict(row) for row in (seed_rows or []) if isinstance(row, Mapping)])

    selected_counts = {
        "total": int(len(seeds)),
        "focus": int(sum(1 for row in seeds if str(row.get("selected_bucket") or "") == "focus")),
        "explore": int(sum(1 for row in seeds if str(row.get("selected_bucket") or "") == "explore")),
        "static_backfill": int(sum(1 for row in seeds if str(row.get("selected_bucket") or "") == "static_backfill")),
        "static": int(sum(1 for row in seeds if str(row.get("selected_bucket") or "") == "static")),
        "prev": int(sum(1 for row in seeds if str(row.get("source") or "") == "prev")),
        "archive": int(sum(1 for row in seeds if str(row.get("source") or "") == "archive")),
    }
    candidate_count = max(len(promo), len(seeds))
    focus_eligible_count = sum(1 for row in promo if _boolish(row.get("focus_eligible", True))) if promo else 0
    promotion_eligible_count = sum(1 for row in promo if _boolish(row.get("promotion_eligible", True))) if promo else 0
    pure_off_axis_count = sum(1 for row in promo if _boolish(row.get("pure_off_axis", False))) if promo else 0

    gate_reason_counts = _count_rows(promo, "gate_reason", empty_label="unknown")
    if gate_reason_counts == {"unknown": len(promo)}:
        gate_reason_counts = {}
    focus_block_reason_counts = _count_rows(promo, "focus_blocked_reason", empty_label="")
    if not focus_block_reason_counts:
        focus_block_reason_counts = _count_rows(promo, "focus_block_reason", empty_label="")
    focus_block_reason_counts = {k: v for k, v in focus_block_reason_counts.items() if k}
    promotion_block_reason_counts = _count_rows(promo, "promotion_blocked_reason", empty_label="")
    if not promotion_block_reason_counts:
        promotion_block_reason_counts = _count_rows(promo, "promotion_block_reason", empty_label="")
    promotion_block_reason_counts = {k: v for k, v in promotion_block_reason_counts.items() if k}

    selected_alignment_vals = [
        _safe_float(row.get("influence_alignment"), 0.0)
        for row in seeds
        if _safe_float(row.get("influence_alignment"), 0.0) > 0.0
    ]
    selected_alignment_mean = (
        float(sum(selected_alignment_vals) / len(selected_alignment_vals))
        if selected_alignment_vals
        else 0.0
    )

    target_seed_count = _safe_int(
        plan_map.get("seed_cap"),
        _safe_int(plan_map.get("total_seed_cap"), max(len(seeds), candidate_count)),
    )
    focus_budget = _safe_int(plan_map.get("focus_budget"), 0)
    explore_budget = _safe_int(plan_map.get("explore_budget"), max(0, target_seed_count))
    if target_seed_count <= 0:
        target_seed_count = max(len(seeds), candidate_count)
    missing_seed_count = max(0, int(target_seed_count) - int(len(seeds)))
    explore_like_selected = (
        int(selected_counts.get("explore", 0))
        + int(selected_counts.get("static_backfill", 0))
        + int(selected_counts.get("static", 0))
    )
    underfill = {
        "missing_total": int(missing_seed_count),
        "focus_missing": int(max(0, int(focus_budget) - int(selected_counts.get("focus", 0)))),
        "explore_missing": int(max(0, int(explore_budget) - int(explore_like_selected))),
        "reason": "ok" if missing_seed_count <= 0 else "underfilled",
        "top_focus_blocked_reason": _top_reason(focus_block_reason_counts),
        "top_promotion_blocked_reason": _top_reason(promotion_block_reason_counts),
    }
    fill_ratio = float(len(seeds) / target_seed_count) if target_seed_count > 0 else 1.0
    summary_line = (
        f"selected {len(seeds)}/{target_seed_count} seeds; fill ratio {fill_ratio:.2f}"
        if missing_seed_count <= 0
        else f"selected {len(seeds)}/{target_seed_count} seeds; missing {missing_seed_count}; reason={underfill['reason']}"
    )

    return {
        "requested_mode": str(plan_map.get("requested_mode") or ""),
        "effective_mode": str(plan_map.get("effective_mode") or ""),
        "policy_name": str(plan_map.get("policy_name") or ""),
        "target_total": int(target_seed_count),
        "target_seed_count": int(target_seed_count),
        "focus_budget": int(focus_budget),
        "explore_budget": int(explore_budget),
        "candidate_count": int(candidate_count),
        "candidate_counts": {
            "all": int(candidate_count),
            "prev": int(sum(1 for row in promo if str(row.get("source") or "") == "prev")),
            "archive": int(sum(1 for row in promo if str(row.get("source") or "") == "archive")),
            "unique_param_hashes": int(len({str(row.get("param_hash") or "") for row in (promo or seeds) if str(row.get("param_hash") or "")})),
        },
        "eligibility_counts": {
            "focus_eligible": int(focus_eligible_count),
            "focus_blocked": int(max(0, candidate_count - focus_eligible_count)),
            "promotion_eligible": int(promotion_eligible_count),
            "promotion_blocked": int(max(0, candidate_count - promotion_eligible_count)),
            "pure_off_axis": int(pure_off_axis_count),
            "alignment_positive": int(sum(1 for row in promo if _safe_float(row.get("influence_alignment"), 0.0) > 0.0)),
        },
        "selected_count": int(len(seeds)),
        "selected_counts": dict(selected_counts),
        "selected_focus_count": int(selected_counts.get("focus", 0)),
        "selected_explore_count": int(selected_counts.get("explore", 0)),
        "selected_source_counts": _count_rows(seeds, "source", empty_label="unknown"),
        "blocked_reason_counts": dict(gate_reason_counts),
        "focus_block_reason_counts": dict(focus_block_reason_counts),
        "promotion_block_reason_counts": dict(promotion_block_reason_counts),
        "underfill": dict(underfill),
        "underfill_reason": str(underfill.get("reason") or ""),
        "missing_seed_count": int(missing_seed_count),
        "selected_alignment_mean": float(selected_alignment_mean),
        "summary_line": str(summary_line),
    }


def write_seed_selection_audit(
    path: Path,
    plan: Mapping[str, Any] | None,
    *,
    promotion_rows: Sequence[Mapping[str, Any]] | None,
    seed_rows: Sequence[Mapping[str, Any]] | None,
) -> Dict[str, Any]:
    audit = build_seed_selection_audit(plan, promotion_rows=promotion_rows, seed_rows=seed_rows)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit
