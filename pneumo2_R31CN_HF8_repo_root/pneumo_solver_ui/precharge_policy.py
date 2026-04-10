from __future__ import annotations

import math
from typing import Any, Callable, Mapping

import numpy as np


CORNER_ORDER = ("ЛП", "ПП", "ЛЗ", "ПЗ")
CORNER_INDEX = {name: idx for idx, name in enumerate(CORNER_ORDER)}

_CORNER_ALIAS_GROUPS = (
    ("ЛП", "lp", "LP", "лп", "ЛП"),
    ("ПП", "pp", "PP", "пп", "ПП"),
    ("ЛЗ", "lz", "LZ", "лз", "ЛЗ"),
    ("ПЗ", "pz", "PZ", "пз", "ПЗ"),
)

_CYL_ALIASES = {
    "c1": "C1",
    "ц1": "C1",
    "1": "C1",
    "c2": "C2",
    "ц2": "C2",
    "2": "C2",
}

_CHAMBER_ALIASES = {
    "cap": "CAP",
    "бп": "CAP",
    "rod": "ROD",
    "шп": "ROD",
}

_GROUP_KEY_ALIASES = {
    "c1_cap": ("C1", "CAP"),
    "c1_bp": ("C1", "CAP"),
    "ц1_бп": ("C1", "CAP"),
    "ц1_cap": ("C1", "CAP"),
    "c1_rod": ("C1", "ROD"),
    "c1_shp": ("C1", "ROD"),
    "ц1_шп": ("C1", "ROD"),
    "ц1_rod": ("C1", "ROD"),
    "c2_cap": ("C2", "CAP"),
    "c2_bp": ("C2", "CAP"),
    "ц2_бп": ("C2", "CAP"),
    "ц2_cap": ("C2", "CAP"),
    "c2_rod": ("C2", "ROD"),
    "c2_shp": ("C2", "ROD"),
    "ц2_шп": ("C2", "ROD"),
    "ц2_rod": ("C2", "ROD"),
}


def _finite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def _norm_key(key: Any) -> str:
    return (
        str(key)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(".", "_")
        .replace(" ", "_")
    )


def _merge_corner_values(dst: np.ndarray, src: np.ndarray) -> np.ndarray:
    out = np.asarray(dst, dtype=float).copy()
    src = np.asarray(src, dtype=float).reshape(4,)
    mask = np.isfinite(src)
    out[mask] = src[mask]
    return out


def _parse_group_key(key: Any) -> tuple[str, str] | None:
    return _GROUP_KEY_ALIASES.get(_norm_key(key))


def _parse_cyl_key(key: Any) -> str | None:
    return _CYL_ALIASES.get(_norm_key(key))


def _parse_chamber_key(key: Any) -> str | None:
    return _CHAMBER_ALIASES.get(_norm_key(key))


def _coerce_corner_pressure4(
    raw: Any,
    *,
    parse_abs_pressure: Callable[[Any], float],
) -> np.ndarray:
    if raw is None:
        return np.full(4, float("nan"), dtype=float)

    if isinstance(raw, Mapping):
        norm_keys = {_norm_key(key) for key in raw.keys()}
        explicit_pressure_keys = {
            "abs_pa",
            "p_abs_pa",
            "gauge_pa",
            "p_gauge_pa",
            "abs_bar",
            "p_abs_bar",
            "gauge_bar",
            "p_gauge_bar",
            "bara",
            "barg",
            "abs_kpa",
            "p_abs_kpa",
            "gauge_kpa",
            "p_gauge_kpa",
            "kpag",
            "abs_mpa",
            "p_abs_mpa",
            "gauge_mpa",
            "p_gauge_mpa",
            "mpag",
            "abs_atm",
            "p_abs_atm",
            "gauge_atm",
            "p_gauge_atm",
            "atmg",
            "unit",
            "units",
        }
        axis_keys = {
            "value",
            "all",
            "target",
            "front",
            "rear",
            "rear_axle",
            "перед",
            "зад",
        }
        axis_keys.update(_norm_key(alias) for aliases in _CORNER_ALIAS_GROUPS for alias in aliases)

        if norm_keys & explicit_pressure_keys:
            try:
                abs_scalar = float(parse_abs_pressure(raw))
            except Exception:
                abs_scalar = float("nan")
            if _finite(abs_scalar):
                return np.full(4, abs_scalar, dtype=float)

        out = np.full(4, float("nan"), dtype=float)
        shared_keys = ("value", "all", "target")
        for shared_key in shared_keys:
            if shared_key in raw:
                try:
                    out[:] = float(parse_abs_pressure(raw[shared_key]))
                except Exception:
                    pass
                break

        front_val = raw.get("front", raw.get("перед", None))
        rear_val = raw.get("rear", raw.get("зад", raw.get("rear_axle", None)))
        if front_val is not None:
            try:
                out[0:2] = float(parse_abs_pressure(front_val))
            except Exception:
                pass
        if rear_val is not None:
            try:
                out[2:4] = float(parse_abs_pressure(rear_val))
            except Exception:
                pass

        for idx, aliases in enumerate(_CORNER_ALIAS_GROUPS):
            for alias in aliases:
                if alias in raw:
                    try:
                        out[idx] = float(parse_abs_pressure(raw[alias]))
                    except Exception:
                        pass
                    break
        if np.any(np.isfinite(out)) or (norm_keys & axis_keys):
            return out

        try:
            abs_scalar = float(parse_abs_pressure(raw))
        except Exception:
            abs_scalar = float("nan")
        if _finite(abs_scalar):
            return np.full(4, abs_scalar, dtype=float)
        return out

    if isinstance(raw, (list, tuple, np.ndarray)):
        arr = np.asarray(raw, dtype=object).reshape(-1)
        out = np.full(4, float("nan"), dtype=float)
        if arr.size == 1:
            try:
                scalar = float(parse_abs_pressure(arr[0]))
            except Exception:
                scalar = float("nan")
            if _finite(scalar):
                out[:] = scalar
            return out
        if arr.size == 2:
            vals = []
            for item in arr[:2]:
                try:
                    vals.append(float(parse_abs_pressure(item)))
                except Exception:
                    vals.append(float("nan"))
            out[0:2] = vals[0]
            out[2:4] = vals[1]
            return out
        if arr.size >= 4:
            for idx in range(4):
                try:
                    out[idx] = float(parse_abs_pressure(arr[idx]))
                except Exception:
                    out[idx] = float("nan")
            return out
        return out

    try:
        abs_scalar = float(parse_abs_pressure(raw))
    except Exception:
        abs_scalar = float("nan")
    if _finite(abs_scalar):
        return np.full(4, abs_scalar, dtype=float)

    return np.full(4, float("nan"), dtype=float)


def _policy_from_group_arrays(group_arrays: Mapping[tuple[str, str], np.ndarray]) -> dict[str, dict[str, dict[str, float]]]:
    out: dict[str, dict[str, dict[str, float]]] = {}
    for (cyl, chamber), values in group_arrays.items():
        vals = np.asarray(values, dtype=float).reshape(4,)
        if not np.any(np.isfinite(vals)):
            continue
        out.setdefault(str(cyl), {})[str(chamber)] = {
            corner: float(vals[idx])
            for idx, corner in enumerate(CORNER_ORDER)
            if _finite(vals[idx])
        }
    return out


def normalize_precharge_policy(
    policy: Any,
    *,
    parse_abs_pressure: Callable[[Any], float],
) -> tuple[dict[tuple[str, str], np.ndarray], dict[str, Any]]:
    group_arrays: dict[tuple[str, str], np.ndarray] = {}
    errors: list[dict[str, str]] = []

    def _assign(group_key: tuple[str, str], raw_value: Any) -> None:
        arr = _coerce_corner_pressure4(raw_value, parse_abs_pressure=parse_abs_pressure)
        if not np.any(np.isfinite(arr)):
            errors.append({"key": f"{group_key[0]}_{group_key[1]}", "error": "cannot_parse_pressure"})
            return
        prev = group_arrays.get(group_key, np.full(4, float("nan"), dtype=float))
        group_arrays[group_key] = _merge_corner_values(prev, arr)

    if isinstance(policy, Mapping):
        for key, raw_value in policy.items():
            group_key = _parse_group_key(key)
            if group_key is not None:
                _assign(group_key, raw_value)
                continue

            cyl_key = _parse_cyl_key(key)
            if cyl_key is not None and isinstance(raw_value, Mapping):
                for subkey, subvalue in raw_value.items():
                    chamber_key = _parse_chamber_key(subkey)
                    if chamber_key is None:
                        errors.append({"key": f"{key}.{subkey}", "error": "unknown_chamber"})
                        continue
                    _assign((cyl_key, chamber_key), subvalue)
                continue

            errors.append({"key": str(key), "error": "unknown_group"})

    normalized_policy = _policy_from_group_arrays(group_arrays)
    report = {
        "normalized_policy": normalized_policy,
        "errors": errors,
    }
    return group_arrays, report


def apply_precharge_policy_to_nodes(
    policy: Any,
    *,
    nodes: list[Any],
    parse_abs_pressure: Callable[[Any], float],
) -> tuple[dict[str, float], dict[str, Any], dict[str, Any]]:
    group_arrays, report = normalize_precharge_policy(
        policy,
        parse_abs_pressure=parse_abs_pressure,
    )
    node_override: dict[str, float] = {}
    applied: list[dict[str, Any]] = []

    for node in nodes:
        if getattr(node, "kind", None) != "chamber":
            continue
        group_key = (str(getattr(node, "cyl", "")), str(getattr(node, "chamber", "")))
        if group_key not in group_arrays:
            continue
        corner = str(getattr(node, "corner", ""))
        if corner not in CORNER_INDEX:
            continue
        p_abs = float(group_arrays[group_key][CORNER_INDEX[corner]])
        if not _finite(p_abs):
            continue
        node_override[str(node.name)] = p_abs
        applied.append({
            "node": str(node.name),
            "corner": corner,
            "cyl": group_key[0],
            "chamber": group_key[1],
            "p_Pa": p_abs,
        })

    report = dict(report)
    report["applied"] = applied
    return node_override, report.get("normalized_policy", {}), report


def build_precharge_policy_from_node_pressures(
    nodes: list[Any],
    node_pressures_abs_Pa: Mapping[str, Any],
) -> dict[str, dict[str, dict[str, float]]]:
    group_arrays: dict[tuple[str, str], np.ndarray] = {}
    pressure_map = {str(k): v for k, v in node_pressures_abs_Pa.items()}
    for node in nodes:
        if getattr(node, "kind", None) != "chamber":
            continue
        node_name = str(getattr(node, "name", ""))
        if node_name not in pressure_map:
            continue
        corner = str(getattr(node, "corner", ""))
        if corner not in CORNER_INDEX:
            continue
        cyl = str(getattr(node, "cyl", ""))
        chamber = str(getattr(node, "chamber", ""))
        group_key = (cyl, chamber)
        vals = group_arrays.setdefault(group_key, np.full(4, float("nan"), dtype=float))
        try:
            vals[CORNER_INDEX[corner]] = float(pressure_map[node_name])
        except Exception:
            continue
    return _policy_from_group_arrays(group_arrays)


def merge_nested_mapping(base: Any, override: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(base, Mapping):
        for key, value in base.items():
            if isinstance(value, Mapping):
                result[str(key)] = merge_nested_mapping(value, {})
            else:
                result[str(key)] = value
    if isinstance(override, Mapping):
        for key, value in override.items():
            skey = str(key)
            if isinstance(value, Mapping) and isinstance(result.get(skey), Mapping):
                result[skey] = merge_nested_mapping(result[skey], value)
            elif isinstance(value, Mapping):
                result[skey] = merge_nested_mapping({}, value)
            else:
                result[skey] = value
    return result
