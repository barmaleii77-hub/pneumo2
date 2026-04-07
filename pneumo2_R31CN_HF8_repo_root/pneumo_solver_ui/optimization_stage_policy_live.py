from __future__ import annotations

"""Helpers to surface staged seed/promotion policy on the current UI screen.

Why:
- stage-specific influence summaries and budget plans already exist on disk,
  but without a thin live reader the main UI cannot explain *why* a stage is
  currently focusing on certain parameters;
- long staged runs must show their real policy/evidence on the visible screen,
  not only inside JSON/CSV artifacts;
- later stages may intentionally underfill due to strict promotion gates, so the
  live UI also needs a compact explanation of why the budget was not filled.

The live reader is intentionally fail-soft:
- it works with the richer audit produced directly by ``collect_seed_points``;
- it also normalizes older/minimal audit payloads into the same UI-facing shape;
- missing files should degrade to an empty summary rather than crash progress UI.
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pneumo_solver_ui.optimization_runtime_paths import stage_fs_name
from pneumo_solver_ui.optimization_stage_policy_audit import (
    AUDIT_JSON_NAME,
    build_seed_selection_audit,
)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_csv_rows(path: Path) -> List[Dict[str, Any]]:
    try:
        if not path.exists() or path.stat().st_size <= 0:
            return []
    except Exception:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            return [dict(row) for row in csv.DictReader(f)]
    except Exception:
        return []


def _as_seed_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(x) for x in payload if isinstance(x, Mapping)]
    if isinstance(payload, Mapping):
        rows = payload.get("seeds")
        if isinstance(rows, list):
            return [dict(x) for x in rows if isinstance(x, Mapping)]
    return []


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
    s = str(value or "").strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def _normalize_count_map(value: Any) -> Dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    out: Dict[str, int] = {}
    for k, v in value.items():
        key = str(k or "").strip()
        if not key:
            continue
        out[key] = _safe_int(v, 0)
    return out


def _count_rows(rows: Sequence[Mapping[str, Any]], key: str, *, empty_label: str = "unknown") -> Dict[str, int]:
    out: Dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or "").strip() or str(empty_label)
        out[label] = int(out.get(label, 0) + 1)
    return dict(sorted(out.items(), key=lambda kv: (-int(kv[1]), kv[0])))


def _top_items(counts: Mapping[str, Any] | None, *, limit: int = 4) -> List[Tuple[str, int]]:
    items = []
    for key, value in _normalize_count_map(counts).items():
        if value <= 0:
            continue
        items.append((str(key), int(value)))
    items.sort(key=lambda kv: (-int(kv[1]), kv[0]))
    return items[: max(0, int(limit))]


def _format_reason_counts(counts: Mapping[str, Any] | None, *, limit: int = 4) -> str:
    items = _top_items(counts, limit=limit)
    if not items:
        return ""
    parts: List[str] = []
    for key, value in items:
        if int(value) == 1:
            parts.append(str(key))
        else:
            parts.append(f"{key}×{int(value)}")
    return ", ".join(parts)


def _pick_first_map(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _selected_seed_rows(
    *,
    seed_rows: Sequence[Mapping[str, Any]],
    promotion_rows: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    if seed_rows:
        return [dict(x) for x in seed_rows if isinstance(x, Mapping)]
    return [dict(r) for r in promotion_rows if isinstance(r, Mapping) and _boolish(r.get("selected"))]


def _selected_counts_from_rows(rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    bucket_counts = _count_rows(rows, "selected_bucket", empty_label="selected")
    source_counts = _count_rows(rows, "source", empty_label="unknown")
    out: Dict[str, int] = {
        "total": int(len(rows)),
        "focus": int(bucket_counts.get("focus", 0) or 0),
        "explore": int(bucket_counts.get("explore", 0) or 0),
        "static_backfill": int(bucket_counts.get("static_backfill", 0) or 0),
        "static": int(bucket_counts.get("static", 0) or 0),
        "prev": int(source_counts.get("prev", 0) or 0),
        "archive": int(source_counts.get("archive", 0) or 0),
    }
    return out


def _legacy_candidate_counts(
    fallback_audit: Mapping[str, Any],
    *,
    promotion_rows: Sequence[Mapping[str, Any]],
    seed_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, int]:
    source_counts = _count_rows(promotion_rows, "source", empty_label="unknown")
    return {
        "all": _safe_int(fallback_audit.get("candidate_count"), len(promotion_rows)),
        "prev": _safe_int(source_counts.get("prev"), 0),
        "archive": _safe_int(source_counts.get("archive"), 0),
        "unique_param_hashes": max(
            _safe_int(fallback_audit.get("candidate_count"), len(promotion_rows)),
            len({str(r.get("param_hash") or "") for r in promotion_rows if str(r.get("param_hash") or "")}),
            len({str(r.get("param_hash") or "") for r in seed_rows if str(r.get("param_hash") or "")}),
        ),
    }


def _legacy_eligibility_counts(
    fallback_audit: Mapping[str, Any],
    *,
    promotion_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, int]:
    candidate_count = max(_safe_int(fallback_audit.get("candidate_count"), len(promotion_rows)), len(promotion_rows))
    focus_eligible = _safe_int(
        fallback_audit.get("focus_eligible_count"),
        sum(1 for row in promotion_rows if _boolish(row.get("focus_eligible", True))),
    )
    promotion_eligible = _safe_int(
        fallback_audit.get("promotion_eligible_count"),
        sum(1 for row in promotion_rows if _boolish(row.get("promotion_eligible", True))),
    )
    pure_off_axis = _safe_int(
        fallback_audit.get("pure_off_axis_count"),
        sum(1 for row in promotion_rows if _boolish(row.get("pure_off_axis", False))),
    )
    return {
        "focus_eligible": int(focus_eligible),
        "focus_blocked": int(max(0, candidate_count - focus_eligible)),
        "promotion_eligible": int(promotion_eligible),
        "promotion_blocked": int(max(0, candidate_count - promotion_eligible)),
        "pure_off_axis": int(pure_off_axis),
        "alignment_positive": int(sum(1 for row in promotion_rows if _safe_float(row.get("influence_alignment"), 0.0) > 0.0)),
    }


def _legacy_selected_counts(
    fallback_audit: Mapping[str, Any],
    *,
    selected_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, int]:
    bucket_counts = _normalize_count_map(fallback_audit.get("selected_bucket_counts"))
    source_counts = _normalize_count_map(fallback_audit.get("selected_source_counts"))
    if not bucket_counts and not source_counts:
        return _selected_counts_from_rows(selected_rows)
    return {
        "total": _safe_int(fallback_audit.get("selected_count"), len(selected_rows)),
        "focus": _safe_int(bucket_counts.get("focus"), 0),
        "explore": _safe_int(bucket_counts.get("explore"), 0),
        "static_backfill": _safe_int(bucket_counts.get("static_backfill"), 0),
        "static": _safe_int(bucket_counts.get("static"), 0),
        "prev": _safe_int(source_counts.get("prev"), 0),
        "archive": _safe_int(source_counts.get("archive"), 0),
    }


def _legacy_underfill(
    fallback_audit: Mapping[str, Any],
    *,
    target_seed_count: int,
    focus_budget: int,
    explore_budget: int,
    selected_counts: Mapping[str, Any],
) -> Dict[str, Any]:
    selected_total = _safe_int(selected_counts.get("total"), 0)
    missing_total = _safe_int(fallback_audit.get("missing_seed_count"), max(0, target_seed_count - selected_total))
    explore_like_selected = (
        _safe_int(selected_counts.get("explore"), 0)
        + _safe_int(selected_counts.get("static_backfill"), 0)
        + _safe_int(selected_counts.get("static"), 0)
    )
    reason = str(fallback_audit.get("underfill_reason") or ("ok" if missing_total <= 0 else "underfilled")).strip()
    if not reason:
        reason = "ok" if missing_total <= 0 else "underfilled"
    return {
        "missing_total": int(missing_total),
        "focus_missing": int(max(0, int(focus_budget) - _safe_int(selected_counts.get("focus"), 0))),
        "explore_missing": int(max(0, int(explore_budget) - explore_like_selected)),
        "reason": str(reason),
        "top_focus_blocked_reason": "",
        "top_promotion_blocked_reason": "",
    }


def _normalize_runtime_audit(
    *,
    audit: Mapping[str, Any],
    plan: Mapping[str, Any],
    promotion_rows: Sequence[Mapping[str, Any]],
    seed_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    audit_map = _as_dict(audit)
    plan_map = _as_dict(plan)
    selected_rows = _selected_seed_rows(seed_rows=seed_rows, promotion_rows=promotion_rows)
    fallback_audit = build_seed_selection_audit(plan_map, promotion_rows=promotion_rows, seed_rows=seed_rows)

    candidate_counts = _normalize_count_map(audit_map.get("candidate_counts"))
    if not candidate_counts:
        candidate_counts = _normalize_count_map(plan_map.get("candidate_counts"))
    if not candidate_counts:
        candidate_counts = _legacy_candidate_counts(fallback_audit, promotion_rows=promotion_rows, seed_rows=seed_rows)

    eligibility_counts = _normalize_count_map(audit_map.get("eligibility_counts"))
    if not eligibility_counts:
        eligibility_counts = _normalize_count_map(plan_map.get("eligibility_counts"))
    if not eligibility_counts:
        eligibility_counts = _legacy_eligibility_counts(fallback_audit, promotion_rows=promotion_rows)

    selected_counts = _normalize_count_map(audit_map.get("selected_counts"))
    if not selected_counts:
        selected_counts = _normalize_count_map(plan_map.get("seed_bucket_counts"))
    if not selected_counts:
        selected_counts = _legacy_selected_counts(fallback_audit, selected_rows=selected_rows)

    source_counts = _normalize_count_map(audit_map.get("source_counts"))
    if not source_counts:
        source_counts = _count_rows(promotion_rows, "source", empty_label="unknown")

    selected_source_counts = _normalize_count_map(audit_map.get("selected_source_counts"))
    if not selected_source_counts:
        selected_source_counts = _normalize_count_map(fallback_audit.get("selected_source_counts"))
    if not selected_source_counts:
        selected_source_counts = _count_rows(selected_rows, "source", empty_label="unknown")

    gate_reason_counts = _normalize_count_map(audit_map.get("gate_reason_counts"))
    if not gate_reason_counts:
        gate_reason_counts = _normalize_count_map(plan_map.get("gate_reason_counts"))
    if not gate_reason_counts:
        gate_reason_counts = _normalize_count_map(fallback_audit.get("blocked_reason_counts"))

    focus_blocked_reason_counts = _normalize_count_map(audit_map.get("focus_blocked_reason_counts"))
    if not focus_blocked_reason_counts:
        focus_blocked_reason_counts = _normalize_count_map(fallback_audit.get("focus_block_reason_counts"))

    promotion_blocked_reason_counts = _normalize_count_map(audit_map.get("promotion_blocked_reason_counts"))
    if not promotion_blocked_reason_counts:
        promotion_blocked_reason_counts = _normalize_count_map(fallback_audit.get("promotion_block_reason_counts"))

    selected_gate_reason_counts = _normalize_count_map(audit_map.get("selected_gate_reason_counts"))

    target_seed_count = _safe_int(
        audit_map.get("target_total"),
        _safe_int(
            audit_map.get("target_seed_count"),
            _safe_int(
                plan_map.get("seed_cap"),
                _safe_int(plan_map.get("total_seed_cap"), _safe_int(selected_counts.get("total"), len(selected_rows))),
            ),
        ),
    )
    if target_seed_count <= 0:
        target_seed_count = max(_safe_int(selected_counts.get("total"), len(selected_rows)), len(selected_rows))

    focus_budget = _safe_int(plan_map.get("focus_budget"), _safe_int(audit_map.get("focus_budget"), 0))
    explore_budget = _safe_int(plan_map.get("explore_budget"), _safe_int(audit_map.get("explore_budget"), target_seed_count))

    underfill = _as_dict(audit_map.get("underfill"))
    if not underfill:
        underfill = _as_dict(plan_map.get("underfill"))
    if not underfill:
        underfill = _legacy_underfill(
            fallback_audit,
            target_seed_count=target_seed_count,
            focus_budget=focus_budget,
            explore_budget=explore_budget,
            selected_counts=selected_counts,
        )
    else:
        underfill = {
            "missing_total": _safe_int(underfill.get("missing_total"), 0),
            "focus_missing": _safe_int(underfill.get("focus_missing"), 0),
            "explore_missing": _safe_int(underfill.get("explore_missing"), 0),
            "reason": str(underfill.get("reason") or "").strip(),
            "top_focus_blocked_reason": str(underfill.get("top_focus_blocked_reason") or "").strip(),
            "top_promotion_blocked_reason": str(underfill.get("top_promotion_blocked_reason") or "").strip(),
        }

    selected_total = max(_safe_int(selected_counts.get("total"), len(selected_rows)), len(selected_rows))
    missing_seed_count = max(0, _safe_int(underfill.get("missing_total"), max(0, target_seed_count - selected_total)))
    fill_ratio = float(selected_total / target_seed_count) if target_seed_count > 0 else 1.0
    underfilled = bool(missing_seed_count > 0)

    underfill_reasons = list(audit_map.get("underfill_reasons") or [])
    if not underfill_reasons:
        raw_reason = str(underfill.get("reason") or "").strip()
        if raw_reason:
            underfill_reasons = [raw_reason]
        elif underfilled:
            underfill_reasons = ["underfilled"]
        else:
            underfill_reasons = ["ok"]

    summary_line = str(audit_map.get("summary_line") or fallback_audit.get("summary_line") or "").strip()
    if not summary_line:
        if underfilled:
            summary_line = f"selected {selected_total}/{target_seed_count} seeds; missing {missing_seed_count}; reason={underfill.get('reason') or 'underfilled'}"
        else:
            summary_line = f"selected {selected_total}/{target_seed_count} seeds; fill ratio {fill_ratio:.2f}"

    selected_alignment_mean = _safe_float(audit_map.get("selected_alignment_mean"), 0.0)
    if selected_alignment_mean <= 0.0:
        selected_alignment_mean = _safe_float(fallback_audit.get("selected_alignment_mean"), 0.0)
    if selected_alignment_mean <= 0.0 and selected_rows:
        vals = [_safe_float(row.get("influence_alignment"), 0.0) for row in selected_rows]
        vals = [v for v in vals if v > 0.0]
        if vals:
            selected_alignment_mean = float(sum(vals) / len(vals))

    return {
        "candidate_counts": dict(candidate_counts),
        "eligibility_counts": dict(eligibility_counts),
        "selected_counts": dict(selected_counts),
        "source_counts": dict(source_counts),
        "selected_source_counts": dict(selected_source_counts),
        "gate_reason_counts": dict(gate_reason_counts),
        "focus_blocked_reason_counts": dict(focus_blocked_reason_counts),
        "promotion_blocked_reason_counts": dict(promotion_blocked_reason_counts),
        "selected_gate_reason_counts": dict(selected_gate_reason_counts),
        "target_seed_count": int(target_seed_count),
        "missing_seed_count": int(missing_seed_count),
        "fill_ratio": float(fill_ratio),
        "underfilled": bool(underfilled),
        "underfill_reason": str((underfill.get("reason") or "").strip()),
        "underfill_reasons": list(underfill_reasons),
        "underfill": dict(underfill),
        "focus_budget": int(focus_budget),
        "explore_budget": int(explore_budget),
        "focus_eligible_count": int(eligibility_counts.get("focus_eligible", 0) or 0),
        "promotion_eligible_count": int(eligibility_counts.get("promotion_eligible", 0) or 0),
        "pure_off_axis_count": int(eligibility_counts.get("pure_off_axis", 0) or 0),
        "selected_alignment_mean": float(selected_alignment_mean),
        "summary_line": str(summary_line),
    }


def _seed_preview_rows(rows: Sequence[Mapping[str, Any]], *, limit: int) -> List[Dict[str, Any]]:
    preview: List[Dict[str, Any]] = []
    for row in rows:
        bucket = str(row.get("selected_bucket") or "").strip() or "unknown"
        dominant = row.get("dominant_stage_params") or []
        if isinstance(dominant, list):
            dominant_text = "|".join(str(x) for x in dominant if str(x))
        else:
            dominant_text = str(dominant or "")
        preview.append({
            "seed_order": _safe_int(row.get("seed_order"), 0),
            "bucket": bucket,
            "source": str(row.get("source") or ""),
            "row_id": row.get("row_id"),
            "alignment": _safe_float(row.get("influence_alignment"), 0.0),
            "coverage": _safe_float(row.get("coverage"), 0.0),
            "dominant_stage_params": dominant_text,
        })
        if len(preview) >= max(1, int(limit)):
            break
    return preview


def summarize_stage_policy_runtime(
    run_dir: Optional[Path],
    *,
    stage_idx: int,
    stage_name: str,
    preview_limit: int = 6,
) -> Dict[str, Any]:
    """Return a concise UI-friendly stage policy summary."""
    out: Dict[str, Any] = {
        "available": False,
        "stage_name": str(stage_name or "").strip(),
        "stage_idx": int(stage_idx),
        "stage_dir": "",
        "summary_status": "",
        "requested_mode": "",
        "effective_mode": "",
        "policy_name": "",
        "priority_params": [],
        "priority_mass": {},
        "explore_budget": 0,
        "focus_budget": 0,
        "seed_count": 0,
        "seed_bucket_counts": {},
        "seed_preview": [],
        "promotion_selected_count": 0,
        "promotion_selected_focus_count": 0,
        "promotion_selected_explore_count": 0,
        "seed_manifest_json": "",
        "seed_manifest_csv": "",
        "promotion_log_csv": "",
        "seed_selection_audit_json": "",
        "target_seed_count": 0,
        "missing_seed_count": 0,
        "fill_ratio": 1.0,
        "underfilled": False,
        "underfill_reason": "",
        "underfill_reasons": [],
        "blocked_reason_counts": {},
        "focus_eligible_count": 0,
        "promotion_eligible_count": 0,
        "pure_off_axis_count": 0,
        "selected_alignment_mean": 0.0,
        "summary_line": "",
        "candidate_counts": {},
        "eligibility_counts": {},
        "selected_counts": {},
        "source_counts": {},
        "selected_source_counts": {},
        "gate_reason_counts": {},
        "focus_blocked_reason_counts": {},
        "promotion_blocked_reason_counts": {},
        "selected_gate_reason_counts": {},
        "underfill": {},
        "gate_reason_preview": "",
        "focus_blocked_reason_preview": "",
        "promotion_blocked_reason_preview": "",
        "underfill_message": "",
    }
    if run_dir is None:
        return out
    try:
        stage_dir = Path(run_dir) / stage_fs_name(stage_idx, stage_name)
    except Exception:
        return out
    out["stage_dir"] = str(stage_dir)

    summary = _as_dict(_load_json(stage_dir / "stage_influence_summary.json"))
    plan = _as_dict(_load_json(stage_dir / "seed_budget_plan.json"))
    seed_manifest_json = stage_dir / "seed_points_manifest.json"
    seed_manifest_csv = stage_dir / "seed_points_manifest.csv"
    promotion_log_csv = stage_dir / "promotion_policy_decisions.csv"
    audit_json = stage_dir / AUDIT_JSON_NAME
    seed_rows = _as_seed_rows(_load_json(seed_manifest_json))
    promotion_rows = _load_csv_rows(promotion_log_csv)
    audit = _as_dict(_load_json(audit_json))

    if not (summary or plan or seed_rows or promotion_rows or audit):
        return out

    normalized = _normalize_runtime_audit(
        audit=audit,
        plan=plan,
        promotion_rows=promotion_rows,
        seed_rows=seed_rows,
    )

    selected_rows = _selected_seed_rows(seed_rows=seed_rows, promotion_rows=promotion_rows)
    selected_rows_sorted = sorted(
        selected_rows,
        key=lambda row: (
            _safe_int(row.get("seed_order"), 0) if _safe_int(row.get("seed_order"), 0) > 0 else 10**9,
            str(row.get("source") or ""),
            _safe_int(row.get("row_id"), 0),
        ),
    )
    bucket_counts_from_rows = _count_rows(selected_rows_sorted, "selected_bucket", empty_label="selected")

    policy_name = str(plan.get("policy_name") or normalized.get("policy_name") or summary.get("policy_name") or audit.get("policy_name") or "")
    requested_mode = str(plan.get("requested_mode") or audit.get("requested_mode") or "")
    effective_mode = str(plan.get("effective_mode") or audit.get("effective_mode") or requested_mode)
    summary_status = str(summary.get("summary_status") or plan.get("influence_summary_status") or "")
    priority_params = list(plan.get("priority_params") or summary.get("top_params") or [])
    priority_mass = _pick_first_map(summary.get("priority_mass"), plan.get("priority_mass"))

    out.update({
        "available": True,
        "summary_status": summary_status,
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "policy_name": policy_name,
        "priority_params": priority_params,
        "priority_mass": priority_mass,
        "explore_budget": int(normalized.get("explore_budget", _safe_int(plan.get("explore_budget"), 0)) or 0),
        "focus_budget": int(normalized.get("focus_budget", _safe_int(plan.get("focus_budget"), 0)) or 0),
        "seed_manifest_json": str(seed_manifest_json) if seed_manifest_json.exists() else "",
        "seed_manifest_csv": str(seed_manifest_csv) if seed_manifest_csv.exists() else "",
        "promotion_log_csv": str(promotion_log_csv) if promotion_log_csv.exists() else "",
        "seed_selection_audit_json": str(audit_json) if audit_json.exists() else "",
        "target_seed_count": int(normalized.get("target_seed_count", 0) or 0),
        "missing_seed_count": int(normalized.get("missing_seed_count", 0) or 0),
        "fill_ratio": float(normalized.get("fill_ratio", 1.0) or 1.0),
        "underfilled": bool(normalized.get("underfilled", False)),
        "underfill_reason": str(normalized.get("underfill_reason") or ""),
        "underfill_reasons": list(normalized.get("underfill_reasons") or []),
        "blocked_reason_counts": dict(normalized.get("gate_reason_counts") or {}),
        "focus_eligible_count": int(normalized.get("focus_eligible_count", 0) or 0),
        "promotion_eligible_count": int(normalized.get("promotion_eligible_count", 0) or 0),
        "pure_off_axis_count": int(normalized.get("pure_off_axis_count", 0) or 0),
        "selected_alignment_mean": float(normalized.get("selected_alignment_mean", 0.0) or 0.0),
        "summary_line": str(normalized.get("summary_line") or ""),
        "candidate_counts": dict(normalized.get("candidate_counts") or {}),
        "eligibility_counts": dict(normalized.get("eligibility_counts") or {}),
        "selected_counts": dict(normalized.get("selected_counts") or {}),
        "source_counts": dict(normalized.get("source_counts") or {}),
        "selected_source_counts": dict(normalized.get("selected_source_counts") or {}),
        "gate_reason_counts": dict(normalized.get("gate_reason_counts") or {}),
        "focus_blocked_reason_counts": dict(normalized.get("focus_blocked_reason_counts") or {}),
        "promotion_blocked_reason_counts": dict(normalized.get("promotion_blocked_reason_counts") or {}),
        "selected_gate_reason_counts": dict(normalized.get("selected_gate_reason_counts") or {}),
        "underfill": dict(normalized.get("underfill") or {}),
    })

    out["seed_count"] = int(max(len(selected_rows_sorted), _safe_int(out["selected_counts"].get("total"), 0)))
    out["seed_bucket_counts"] = dict(bucket_counts_from_rows or out["selected_counts"] or {})
    out["seed_preview"] = _seed_preview_rows(selected_rows_sorted, limit=preview_limit)

    selected_promotions = [dict(r) for r in promotion_rows if _boolish(r.get("selected"))]
    if selected_promotions:
        out["promotion_selected_count"] = int(len(selected_promotions))
        out["promotion_selected_focus_count"] = int(sum(1 for r in selected_promotions if str(r.get("selected_bucket") or "") == "focus"))
        out["promotion_selected_explore_count"] = int(sum(1 for r in selected_promotions if str(r.get("selected_bucket") or "") == "explore"))
    else:
        out["promotion_selected_count"] = int(out["selected_counts"].get("total", out["seed_count"]) or out["seed_count"])
        out["promotion_selected_focus_count"] = int(out["selected_counts"].get("focus", 0) or 0)
        out["promotion_selected_explore_count"] = int(out["selected_counts"].get("explore", 0) or 0)

    out["gate_reason_preview"] = _format_reason_counts(out.get("gate_reason_counts"), limit=4)
    out["focus_blocked_reason_preview"] = _format_reason_counts(out.get("focus_blocked_reason_counts"), limit=4)
    out["promotion_blocked_reason_preview"] = _format_reason_counts(out.get("promotion_blocked_reason_counts"), limit=4)

    underfill = _as_dict(out.get("underfill"))
    missing_total = _safe_int(underfill.get("missing_total"), 0)
    reason = str(underfill.get("reason") or "").strip()
    if missing_total > 0:
        out["underfill_message"] = f"missing {missing_total} vs target; reason={reason or 'underfilled'}"
    elif reason:
        out["underfill_message"] = f"reason={reason}"
    else:
        out["underfill_message"] = ""

    return out


__all__ = ["summarize_stage_policy_runtime"]
