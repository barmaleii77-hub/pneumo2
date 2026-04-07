from __future__ import annotations

from typing import Any, Dict, Iterable, List

NON_DESIGN_RANGE_KEYS: tuple[str, ...] = (
    "vx0_м_с",
    "world_road_vmin_м_с",
    "world_road_yaw_rate_limit_рад_с",
)

STAGE_RUNTIME_ROLE_DESCRIPTIONS: dict[str, str] = {
    "stage0_relevance": "Быстрый relevance-screen: только дешёвые проверки, грубая fidelity, 1 nominal scenario.",
    "stage1_long": "Длинные дорожные/манёвренные проверки: средняя fidelity, nominal + heavy scenarios.",
    "stage2_final": "Финальная robustness-стадия: полная fidelity, расширенный набор сценариев и финальный отбор.",
}

_STAGE0_TYPE_PREFIXES: tuple[str, ...] = (
    "инерция",
    "микро",
    "комбо",
)

_STAGE1_EXPLICIT_TYPES: set[str] = {
    "worldroad",
    "road_profile_csv",
    "maneuver_csv",
}


def _to_float_or_none(v: Any) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:
            return None
        return float(f)
    except Exception:
        return None


def _to_int_or_none(v: Any) -> int | None:
    try:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        return int(float(s))
    except Exception:
        return None


def _bool_enabled(rec: Dict[str, Any]) -> bool:
    v = rec.get("включен", rec.get("enabled", True))
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        try:
            return float(v) != 0.0
        except Exception:
            return True
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"0", "false", "no", "off", "нет"}:
            return False
        if s in {"1", "true", "yes", "on", "да"}:
            return True
    return bool(v)


def _normalize_stage_value_for_runtime(v: Any) -> int | None:
    stg = _to_int_or_none(v)
    if stg is None:
        return None
    return max(0, int(stg))


def infer_suite_stage(rec: Dict[str, Any] | None) -> int:
    """Return canonical suite stage for one suite row.

    Contract:
    - stage numbering is always 0-based;
    - explicit negative values are clamped to 0;
    - missing/NaN stage values are inferred from the test type so that UI/editor,
      autosave and staged optimization all talk about the same stage.
    """
    if not isinstance(rec, dict):
        return 0

    explicit = _normalize_stage_value_for_runtime(rec.get("стадия"))
    if explicit is not None:
        return int(explicit)

    typ = str(rec.get("тип", "") or "").strip().lower()
    if typ.startswith(_STAGE0_TYPE_PREFIXES):
        return 0
    if typ in _STAGE1_EXPLICIT_TYPES:
        return 1
    if rec.get("road_surface") or rec.get("road_csv") or rec.get("axay_csv"):
        return 1
    return 1


def describe_runtime_stage(name: Any) -> str:
    key = str(name or "").strip()
    return STAGE_RUNTIME_ROLE_DESCRIPTIONS.get(key, "Промежуточная стадия staged optimization.")


def summarize_enabled_stage_distribution(suite: Iterable[Dict[str, Any]] | None) -> Dict[str, Any]:
    counts: Dict[int, int] = {}
    for rec in suite or []:
        if not isinstance(rec, dict):
            continue
        if not _bool_enabled(rec):
            continue
        stg = infer_suite_stage(rec)
        counts[int(stg)] = counts.get(int(stg), 0) + 1
    return {
        "enabled_stage_counts": {str(k): int(v) for k, v in sorted(counts.items())},
        "enabled_total": int(sum(counts.values())),
    }


def normalize_suite_stage_numbers(suite: List[Dict[str, Any]] | None) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Normalize suite stages without rewriting explicit user-authored ordering.

    Current contract:
    - explicit non-negative ``стадия`` is authoritative and must be preserved as-is;
    - negative stages are invalid and are clamped to 0 with ``_meta_stage_original``;
    - missing/NaN stages are inferred explicitly from the test type.

    IMPORTANT:
    Automatic global bias rebasing (e.g. ``1 -> 0`` when there is no enabled stage 0)
    is intentionally disabled. That heuristic rewrote valid editor input and made a test
    explicitly assigned to stage 1 silently migrate to stage 0 in autosave/runtime.
    Empty earlier stages must be handled by the stage runner, not by rewriting suite data.
    """
    raw = [dict(x) for x in (suite or []) if isinstance(x, dict)]
    clamped_negative_rows = 0
    inferred_missing_rows = 0

    for rec in raw:
        stg_raw = _to_int_or_none(rec.get("стадия"))
        if stg_raw is not None and int(stg_raw) < 0:
            rec["_meta_stage_original"] = int(stg_raw)
            rec["стадия"] = 0
            clamped_negative_rows += 1
        elif stg_raw is None:
            rec["стадия"] = int(infer_suite_stage(rec))
            inferred_missing_rows += 1
        else:
            rec["стадия"] = int(max(0, int(stg_raw)))

    audit = {
        "stage_bias_applied": 0,
        "normalized_rows": 0,
        "legacy_bias_rebase_disabled": True,
        "clamped_negative_rows": int(clamped_negative_rows),
        "inferred_missing_rows": int(inferred_missing_rows),
        "before": summarize_enabled_stage_distribution(suite or []),
        "after": summarize_enabled_stage_distribution(raw),
    }
    return raw, audit


def sanitize_ranges_for_optimization(base: Dict[str, Any] | None, ranges: Dict[str, Any] | None) -> tuple[Dict[str, Any], Dict[str, Any]]:
    base = dict(base or {})
    ranges = dict(ranges or {})
    out: Dict[str, Any] = {}
    removed: Dict[str, Any] = {}
    widened: Dict[str, Dict[str, Any]] = {}
    for key, value in ranges.items():
        if key in NON_DESIGN_RANGE_KEYS:
            removed[key] = value
            continue
        if isinstance(value, (list, tuple)) and len(value) == 2:
            lo = _to_float_or_none(value[0])
            hi = _to_float_or_none(value[1])
            if lo is None or hi is None:
                out[str(key)] = value
                continue
            if lo > hi:
                lo, hi = hi, lo
            orig = [float(lo), float(hi)]
            base_v = _to_float_or_none(base.get(key))
            if base_v is not None:
                if base_v < lo:
                    lo = float(base_v)
                if base_v > hi:
                    hi = float(base_v)
                if [float(lo), float(hi)] != orig:
                    widened[str(key)] = {"base": float(base_v), "from": orig, "to": [float(lo), float(hi)]}
            out[str(key)] = [float(lo), float(hi)]
        else:
            out[str(key)] = value
    audit = {
        "removed_non_design_keys": {k: removed[k] for k in sorted(removed)},
        "widened_to_include_base": widened,
        "range_count_before": int(len(ranges)),
        "range_count_after": int(len(out)),
    }
    return out, audit


def sanitize_optimization_inputs(base: Dict[str, Any] | None, ranges: Dict[str, Any] | None, suite: List[Dict[str, Any]] | None) -> tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    base_out = dict(base or {})
    ranges_out, ranges_audit = sanitize_ranges_for_optimization(base_out, ranges)
    suite_out, suite_audit = normalize_suite_stage_numbers(suite)
    return base_out, ranges_out, suite_out, {"ranges": ranges_audit, "suite_stage": suite_audit}
