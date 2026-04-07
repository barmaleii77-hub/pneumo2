from __future__ import annotations

"""Stage-specific influence summaries and seed/promotion policy.

Why this module exists:
- StageRunner already differentiates runtime stages by suite coverage and parameter
  ranges, but that alone does not say *which* parameters deserve priority when we
  promote candidates to the next stage.
- The restored optimization control plane needs a small, machine-checkable layer
  that can be reused by both the UI and CLI without importing heavy modules.
- Later stages should become progressively more focused instead of behaving like a
  pure re-run with only wider suites / longer time horizons.

Contract:
- ``build_stage_specific_influence_summary`` turns a System Influence report into a
  compact per-stage summary restricted to the stage-active parameters.
- ``build_stage_seed_budget_plan`` splits the per-stage seed cap into exploratory
  and influence-focused budgets.
- ``compute_stage_alignment`` / ``promotion_sort_key`` let StageRunner prefer
  candidates whose parameter deltas align with the next stage priorities.
"""

from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

import math

DEFAULT_STAGE_POLICY_MODE: str = "influence_weighted"
_STAGE_POLICY_MODES: tuple[str, str] = ("influence_weighted", "static")

# Later stages become progressively more focused:
# - stage0: broad relevance scan, a lot of exploration, wide priority tail;
# - stage1: mixed mode, still respects score progression but already biases toward
#           the parameters that matter for long tests;
# - stage2: strictest alignment, smallest top-k, least exploratory budget.
_STAGE_POLICY_SPECS: dict[str, dict[str, Any]] = {
    "stage0_relevance": {
        "policy_name": "broad_relevance",
        "top_k": 16,
        "explore_frac": 0.60,
        "alpha": 0.70,
    },
    "stage1_long": {
        "policy_name": "focused_progress",
        "top_k": 10,
        "explore_frac": 0.35,
        "alpha": 1.00,
    },
    "stage2_final": {
        "policy_name": "strict_alignment",
        "top_k": 6,
        "explore_frac": 0.15,
        "alpha": 1.30,
    },
}


def stage_policy_modes() -> tuple[str, ...]:
    return _STAGE_POLICY_MODES


def stage_policy_spec(stage_name: str) -> dict[str, Any]:
    key = str(stage_name or "").strip() or "stage1_long"
    return dict(_STAGE_POLICY_SPECS.get(key, _STAGE_POLICY_SPECS["stage1_long"]))


def stage_seed_policy_summary_text() -> str:
    parts: list[str] = []
    for stage_name in ("stage0_relevance", "stage1_long", "stage2_final"):
        spec = stage_policy_spec(stage_name)
        parts.append(
            f"{stage_name}: top{int(spec['top_k'])}/explore{int(round(float(spec['explore_frac']) * 100.0))}% [{spec['policy_name']}]"
        )
    return " · ".join(parts)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not math.isfinite(out):
        return float(default)
    return float(out)


def _influence_scores(payload: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None) -> dict[str, float]:
    """Extract per-parameter influence scores from a System Influence payload.

    Supports both current record-list schema:
      {"params": [{"param": "...", "score": ...}, ...]}
    and the older mapping style:
      {"params": {"name": {"score": ...}, ...}}
    """

    if payload is None:
        return {}

    params_obj: Any = payload
    if isinstance(payload, Mapping):
        params_obj = payload.get("params", payload)

    out: dict[str, float] = {}

    if isinstance(params_obj, Mapping):
        for raw_name, raw_val in params_obj.items():
            name = str(raw_name or "").strip()
            if not name:
                continue
            if isinstance(raw_val, Mapping):
                score = _safe_float(raw_val.get("score"), 0.0)
            else:
                score = _safe_float(raw_val, 0.0)
            out[name] = max(0.0, float(score))
        return out

    if isinstance(params_obj, Sequence) and not isinstance(params_obj, (str, bytes)):
        for rec in params_obj:
            if not isinstance(rec, Mapping):
                continue
            name = str(rec.get("param") or rec.get("name") or "").strip()
            if not name:
                continue
            out[name] = max(0.0, _safe_float(rec.get("score"), 0.0))
    return out


def build_stage_specific_influence_summary(
    stage_name: str,
    *,
    active_params: Sequence[str],
    influence_payload: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
    source_label: str = "base",
) -> dict[str, Any]:
    """Build a compact stage-specific influence summary.

    ``active_params`` should come from the stage ranges JSON (i.e. the parameters
    that are currently eligible for mutation/promotion on this runtime stage).
    """

    spec = stage_policy_spec(stage_name)
    top_k = int(max(1, int(spec["top_k"])))
    alpha = float(max(1e-6, float(spec["alpha"])))

    active = [str(p).strip() for p in active_params if str(p).strip()]
    active_unique: list[str] = []
    seen: set[str] = set()
    for p in active:
        if p in seen:
            continue
        seen.add(p)
        active_unique.append(p)

    score_map = _influence_scores(influence_payload)
    scored_active = {p: max(0.0, float(score_map.get(p, 0.0))) for p in active_unique}
    ordered = sorted(scored_active.items(), key=lambda kv: (-float(kv[1]), kv[0]))
    raw_top = {k: float(v) for k, v in ordered[:top_k] if float(v) > 0.0}

    summary_status = "ok"
    if not active_unique:
        summary_status = "no_active_params"
    elif not ordered:
        summary_status = "no_scores"

    total_positive = float(sum(float(v) for v in scored_active.values() if float(v) > 0.0))
    if total_positive <= 0.0 and active_unique:
        summary_status = "zero_signal"

    priority_mass: dict[str, float] = {}
    concentration = 0.0
    tail_mass = 0.0
    top_params: list[str] = []

    if total_positive > 0.0:
        top_params = list(raw_top.keys())
        weighted = {p: float(pow(max(v, 0.0), alpha)) for p, v in raw_top.items()}
        weight_sum = float(sum(weighted.values()))
        if weight_sum > 0.0:
            priority_mass = {p: float(weighted[p] / weight_sum) for p in top_params}
            # concentration is calculated in the full active space, not just within the top-k,
            # so later stages can be compared for how narrow their effective focus becomes.
            weighted_full = {p: float(pow(max(scored_active.get(p, 0.0), 0.0), alpha)) for p in active_unique}
            full_sum = float(sum(weighted_full.values()))
            if full_sum > 0.0:
                concentration = float(sum(weighted_full.get(p, 0.0) for p in top_params) / full_sum)
                tail_mass = float(max(0.0, 1.0 - concentration))

    return {
        "stage_name": str(stage_name or "").strip(),
        "source_label": str(source_label or "base"),
        "summary_status": str(summary_status),
        "policy_name": str(spec["policy_name"]),
        "top_k": int(top_k),
        "alpha": float(alpha),
        "explore_frac": float(spec["explore_frac"]),
        "active_params": list(active_unique),
        "active_param_count": int(len(active_unique)),
        "scored_param_count": int(sum(1 for _p, _v in ordered if float(_v) > 0.0)),
        "top_params": list(top_params),
        "raw_top_scores": dict(raw_top),
        "priority_mass": dict(priority_mass),
        "tail_mass": float(tail_mass),
        "concentration": float(concentration),
        "total_positive_score": float(total_positive),
    }


def _largest_remainder_allocation(total: int, weights: Mapping[str, float]) -> dict[str, int]:
    total_i = int(max(0, int(total)))
    keys = [str(k) for k in weights.keys() if str(k)]
    if total_i <= 0 or not keys:
        return {k: 0 for k in keys}

    raw = {k: max(0.0, _safe_float(weights.get(k), 0.0)) for k in keys}
    raw_sum = float(sum(raw.values()))
    if raw_sum <= 0.0:
        base = total_i // len(keys)
        rem = total_i - (base * len(keys))
        out = {k: int(base) for k in keys}
        for k in keys[:rem]:
            out[k] += 1
        return out

    scaled = {k: float(total_i) * (float(raw[k]) / raw_sum) for k in keys}
    out = {k: int(math.floor(v)) for k, v in scaled.items()}
    remainder = int(total_i - sum(out.values()))
    if remainder > 0:
        ranked = sorted(keys, key=lambda k: (-(scaled[k] - float(out[k])), k))
        for k in ranked[:remainder]:
            out[k] += 1
    return out


def build_stage_seed_budget_plan(
    stage_name: str,
    *,
    total_seed_cap: int,
    requested_mode: str,
    stage_influence_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    spec = stage_policy_spec(stage_name)
    requested = str(requested_mode or DEFAULT_STAGE_POLICY_MODE).strip() or DEFAULT_STAGE_POLICY_MODE
    if requested not in _STAGE_POLICY_MODES:
        requested = DEFAULT_STAGE_POLICY_MODE

    total_cap = int(max(0, int(total_seed_cap)))
    summary = dict(stage_influence_summary or {})
    summary_status = str(summary.get("summary_status") or "")
    priority_mass = dict(summary.get("priority_mass") or {}) if isinstance(summary.get("priority_mass"), Mapping) else {}

    effective_mode = requested
    fallback_reason = ""
    if requested == "influence_weighted":
        if total_cap <= 0:
            effective_mode = "influence_weighted"
        elif summary_status != "ok" or not priority_mass:
            effective_mode = "static"
            fallback_reason = f"stage influence summary unavailable ({summary_status or 'missing'})"
    else:
        effective_mode = "static"

    explore_budget = total_cap
    focus_budget = 0
    focus_param_budgets: dict[str, int] = {}

    if effective_mode == "influence_weighted" and total_cap > 0:
        explore_budget = int(math.ceil(float(total_cap) * float(spec["explore_frac"])))
        explore_budget = max(0, min(total_cap, explore_budget))
        if total_cap > 1 and explore_budget >= total_cap:
            explore_budget = int(total_cap - 1)
        focus_budget = int(max(0, total_cap - explore_budget))
        focus_param_budgets = _largest_remainder_allocation(focus_budget, priority_mass)
    
    return {
        "stage_name": str(stage_name or "").strip(),
        "requested_mode": requested,
        "effective_mode": effective_mode,
        "fallback_reason": str(fallback_reason),
        "policy_name": str(spec["policy_name"]),
        "top_k": int(spec["top_k"]),
        "explore_frac": float(spec["explore_frac"]),
        "alpha": float(spec["alpha"]),
        "total_seed_cap": int(total_cap),
        "explore_budget": int(explore_budget),
        "focus_budget": int(focus_budget),
        "focus_param_budgets": dict(focus_param_budgets),
        "priority_params": list(priority_mass.keys()),
    }


def compute_param_delta_norm(
    params: Mapping[str, Any] | None,
    *,
    base_params: Mapping[str, Any] | None,
    ranges: Mapping[str, Any] | None,
) -> dict[str, float]:
    """Normalized absolute delta for candidate parameters relative to base.

    Missing params are ignored instead of being treated as synthetic zeros.
    """

    out: dict[str, float] = {}
    params_map = dict(params or {})
    base_map = dict(base_params or {})
    ranges_map = dict(ranges or {})
    for name, bounds in ranges_map.items():
        if name not in params_map:
            continue
        if not isinstance(bounds, (list, tuple)) or len(bounds) < 2:
            continue
        lo = _safe_float(bounds[0], 0.0)
        hi = _safe_float(bounds[1], 0.0)
        span = float(hi - lo)
        if not math.isfinite(span) or span <= 0.0:
            continue
        cur = _safe_float(params_map.get(name), float("nan"))
        if not math.isfinite(cur):
            continue
        base = _safe_float(base_map.get(name), cur)
        delta = abs(float(cur) - float(base)) / span
        if delta <= 0.0 or not math.isfinite(delta):
            continue
        out[str(name)] = float(delta)
    return out


def compute_stage_alignment(
    stage_influence_summary: Mapping[str, Any] | None,
    delta_norm: Mapping[str, float] | None,
    *,
    dominant_top_k: int = 3,
) -> dict[str, Any]:
    summary = dict(stage_influence_summary or {})
    delta = {str(k): max(0.0, _safe_float(v, 0.0)) for k, v in dict(delta_norm or {}).items()}
    priority_mass = dict(summary.get("priority_mass") or {}) if isinstance(summary.get("priority_mass"), Mapping) else {}

    alignment = 0.0
    touched: list[tuple[str, float]] = []
    for name, mass in priority_mass.items():
        d = float(delta.get(name, 0.0))
        if d <= 0.0:
            continue
        m = max(0.0, _safe_float(mass, 0.0))
        contrib = float(d * m)
        alignment += contrib
        touched.append((name, contrib))

    off_axis = float(sum(v for k, v in delta.items() if k not in priority_mass and float(v) > 0.0))
    touched.sort(key=lambda kv: (-float(kv[1]), kv[0]))
    dominant = [name for name, _val in touched[: max(1, int(dominant_top_k))]]

    return {
        "alignment": float(alignment),
        "off_axis_sprawl": float(off_axis),
        "priority_touched_count": int(len(touched)),
        "dominant_stage_params": dominant,
    }


def promotion_sort_key(
    stage_name: str,
    *,
    score_tuple: Sequence[float],
    alignment: float,
    off_axis_sprawl: float,
) -> tuple[float, ...]:
    """Return deterministic stage-specific ordering for promotion seeds.

    The stage policy keeps the penalty gate first, but the remaining ordering must
    stay objective-contract agnostic: if the active objective stack changes, the
    promotion order should continue to respect that stack instead of silently
    hard-coding legacy ``obj1/obj2/energy`` positions.
    """

    pen = _safe_float(score_tuple[0] if len(score_tuple) > 0 else 0.0, float("inf"))
    objective_terms = tuple(
        _safe_float(score_tuple[idx], float("inf"))
        for idx in range(1, len(score_tuple))
    )
    align_term = -max(0.0, _safe_float(alignment, 0.0))
    off_axis = max(0.0, _safe_float(off_axis_sprawl, 0.0))
    policy_name = str(stage_policy_spec(stage_name).get("policy_name") or "broad_relevance")

    if policy_name == "strict_alignment":
        return (pen, align_term, *objective_terms, off_axis)
    if policy_name == "focused_progress":
        if objective_terms:
            return (pen, objective_terms[0], align_term, *objective_terms[1:], off_axis)
        return (pen, align_term, off_axis)
    return (pen, *objective_terms, align_term, off_axis)
