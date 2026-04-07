# -*- coding: utf-8 -*-
"""
config_profile.py

Unified configuration profile for the Pneumo Solver UI.

Goal
----
Provide a *single* JSON artifact that captures:
- base parameters (including non-numeric modes/flags and structured lists),
- optimization ranges,
- test suite (baseline/long-suite),

so that runs are reproducible and easy to share.

Design principles
-----------------
- Strict validation (JSON Schema) with a forgiving "doctor" step:
  we validate, then coerce obvious types (e.g., "true"/"1" -> True),
  clamp/repair invalid ranges, and drop unknown junk safely.
- No pickle, no code execution; JSON only.
- Backward compatible: profile_version field.

This module is intentionally dependency-light: jsonschema is optional.
If it's absent, UI still works (validation becomes best-effort).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple, Union

PROFILE_VERSION = 1

# JSON Schema (draft-07). Kept permissive for forward compatibility.
PROFILE_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "PneumoSolverProfile",
    "type": "object",
    "required": ["profile_version", "base", "ranges", "suite"],
    "properties": {
        "profile_version": {"type": "integer", "minimum": 1},
        "app_release": {"type": "string"},
        "created_at": {"type": "string"},
        "notes": {"type": "string"},
        "base": {"type": "object"},
        "ranges": {
            "type": "object",
            "additionalProperties": {
                "oneOf": [
                    # [min,max]
                    {"type": "array", "minItems": 2, "maxItems": 2},
                    # {"min":..,"max":..}
                    {
                        "type": "object",
                        "required": ["min", "max"],
                        "properties": {"min": {}, "max": {}},
                        "additionalProperties": True,
                    },
                ]
            },
        },
        "suite": {"type": "array", "items": {"type": "object"}},
    },
    "additionalProperties": True,
}


def profile_fingerprint(profile: Dict[str, Any]) -> str:
    """Short stable fingerprint for UI."""
    try:
        b = json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8")
    except Exception:
        b = repr(profile).encode("utf-8", errors="replace")
    return hashlib.sha256(b).hexdigest()[:12]


def load_profile_bytes(data: Union[bytes, str]) -> Dict[str, Any]:
    if isinstance(data, bytes):
        s = data.decode("utf-8", errors="strict")
    else:
        s = str(data)
    obj = json.loads(s)
    if not isinstance(obj, dict):
        raise ValueError("profile.json должен быть объектом (dict).")
    return obj


def validate_profile(profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate profile against schema. Returns (ok, warnings/errors list)."""
    errors: List[str] = []
    ok = True
    try:
        import jsonschema  # type: ignore

        try:
            jsonschema.validate(instance=profile, schema=PROFILE_SCHEMA)
        except jsonschema.ValidationError as e:  # type: ignore
            ok = False
            errors.append(str(e).strip())
        except Exception as e:
            ok = False
            errors.append(f"jsonschema.validate failed: {e}")
    except Exception:
        # No jsonschema installed -> best effort
        ok = True
        errors.append("jsonschema не установлен: строгая валидация пропущена (best-effort).")
    return ok, errors


def _to_bool(v: Any) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1, 0.0, 1.0):
        return bool(int(v))
    if isinstance(v, str):
        vv = v.strip().lower()
        if vv in ("true", "1", "yes", "y", "да"):
            return True
        if vv in ("false", "0", "no", "n", "нет", ""):
            return False
    return None


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        vv = v.strip().replace(",", ".")
        if vv == "":
            return None
        try:
            return float(vv)
        except Exception:
            return None
    return None


def _to_list_of_floats(v: Any) -> Optional[List[float]]:
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        out: List[float] = []
        for x in v:
            fx = _to_float(x)
            if fx is None:
                return None
            out.append(float(fx))
        return out
    return None


def doctor_profile(profile: Dict[str, Any], default_base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Coerce obvious types, fix ranges, drop invalid entries.

    This is intentionally conservative: we do NOT invent unknown keys,
    and we do not clamp physics values here (that's model-side).
    """
    prof = dict(profile)  # shallow copy

    # Ensure required keys exist
    prof.setdefault("profile_version", PROFILE_VERSION)
    prof.setdefault("base", {})
    prof.setdefault("ranges", {})
    prof.setdefault("suite", [])

    base_in = prof.get("base")
    if not isinstance(base_in, dict):
        base_in = {}
    ranges_in = prof.get("ranges")
    if not isinstance(ranges_in, dict):
        ranges_in = {}
    suite_in = prof.get("suite")
    if not isinstance(suite_in, list):
        suite_in = []

    base_out: Dict[str, Any] = {}
    # Use default_base as a type oracle when available
    type_oracle: Dict[str, Any] = default_base if isinstance(default_base, dict) else {}

    for k, v in base_in.items():
        kk = str(k)
        if kk in type_oracle:
            dv = type_oracle.get(kk)
            # list parameters (e.g. spring tables)
            if isinstance(dv, (list, tuple)):
                lv = _to_list_of_floats(v)
                if lv is not None:
                    base_out[kk] = lv
                continue
            # bool parameters
            if isinstance(dv, bool):
                bv = _to_bool(v)
                if bv is not None:
                    base_out[kk] = bool(bv)
                continue
            # string parameters
            if isinstance(dv, str):
                base_out[kk] = str(v) if v is not None else ""
                continue
            # numeric parameters
            fv = _to_float(v)
            if fv is not None:
                base_out[kk] = float(fv)
            continue

        # Unknown key: keep only safe JSON-native types
        if isinstance(v, (str, bool, int, float, list, dict)) or v is None:
            base_out[kk] = v

    # Ranges: accept [min,max] or {"min":..,"max":..}
    ranges_out: Dict[str, Tuple[float, float]] = {}
    for k, v in ranges_in.items():
        kk = str(k)
        mn = mx = None
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            mn = _to_float(v[0])
            mx = _to_float(v[1])
        elif isinstance(v, dict):
            mn = _to_float(v.get("min"))
            mx = _to_float(v.get("max"))
        if mn is None or mx is None:
            continue
        # Repair inverted ranges
        if mn == mx:
            continue
        if mn > mx:
            mn, mx = mx, mn
        ranges_out[kk] = (float(mn), float(mx))

    # Suite: keep dict rows only
    suite_out: List[Dict[str, Any]] = []
    for row in suite_in:
        if isinstance(row, dict):
            # keep as-is; UI will validate required fields later
            suite_out.append({str(k): v for k, v in row.items()})
    prof["base"] = base_out
    prof["ranges"] = ranges_out
    prof["suite"] = suite_out
    prof["profile_version"] = int(prof.get("profile_version") or PROFILE_VERSION)
    return prof


def build_profile(
    base: Dict[str, Any],
    ranges: Dict[str, Any],
    suite: List[Dict[str, Any]],
    app_release: str = "",
    notes: str = "",
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    if created_at is None:
        # ISO-like without timezone (UI local)
        import datetime as _dt

        created_at = _dt.datetime.now().isoformat(timespec="seconds")

    # Convert ranges tuples to lists (JSON friendly)
    ranges_out: Dict[str, Any] = {}
    for k, v in (ranges or {}).items():
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            try:
                ranges_out[str(k)] = [float(v[0]), float(v[1])]
            except Exception:
                continue
        elif isinstance(v, dict) and "min" in v and "max" in v:
            ranges_out[str(k)] = {"min": v.get("min"), "max": v.get("max")}
        else:
            # ignore garbage
            continue

    prof: Dict[str, Any] = {
        "profile_version": PROFILE_VERSION,
        "app_release": str(app_release),
        "created_at": str(created_at),
        "notes": str(notes),
        "base": dict(base or {}),
        "ranges": ranges_out,
        "suite": list(suite or []),
    }
    return prof


def profile_to_json_bytes(profile: Dict[str, Any]) -> bytes:
    return json.dumps(profile, ensure_ascii=False, indent=2).encode("utf-8")
