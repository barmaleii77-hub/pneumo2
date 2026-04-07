# -*- coding: utf-8 -*-
"""param_contract.py

Contract-based type safety for parameters.

Problem
-------
The UI has two groups of parameters:
- numeric scalars (edited in a big table)
- non-numeric (bool flags, string modes, structured tables)

If a JSON export/import or a previous session corrupts types (e.g. string mode becomes 0/1),
Streamlit may push such keys into the numeric table and produce errors like:
"Параметр 'термодинамика': пустое/некорректное базовое значение."

Solution
--------
Use the canonical defaults (default_base.json) as a contract:
- expected types are derived from defaults
- base and ranges are normalized/coerced
- numeric editor excludes bool/string keys regardless of current runtime value

This module is intentionally dependency-free.
"""

from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _to_float(x: Any) -> Optional[float]:
    if _is_num(x):
        return float(x)
    if isinstance(x, str):
        try:
            v = float(x.strip().replace(",", "."))
            if math.isfinite(v):
                return v
        except Exception:
            return None
    return None


def _to_bool(x: Any) -> Optional[bool]:
    if isinstance(x, bool):
        return bool(x)
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        if float(x) in (0.0, 1.0):
            return bool(int(x))
    if isinstance(x, str):
        v = x.strip().lower()
        if v in ("1", "true", "yes", "y", "да", "on"):
            return True
        if v in ("0", "false", "no", "n", "нет", "off", ""):
            return False
    return None


def _to_str(x: Any) -> Optional[str]:
    if isinstance(x, str):
        s = x.strip()
        return s if s else None
    return None


@dataclass
class Contract:
    defaults: Dict[str, Any]
    num_keys: Set[str]
    bool_keys: Set[str]
    str_keys: Set[str]
    struct_keys: Set[str]


@dataclass
class DoctorReport:
    coerced: List[str]
    filled_defaults: List[str]
    dropped_ranges: List[str]
    fixed_ranges: List[str]
    notes: List[str]


def load_defaults(path: Path) -> Dict[str, Any]:
    p = Path(path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"default_base must be an object: {p}")
    return obj


def make_contract(defaults: Dict[str, Any]) -> Contract:
    num: Set[str] = set()
    boo: Set[str] = set()
    st: Set[str] = set()
    struct: Set[str] = set()

    for k, v in defaults.items():
        ks = str(k)
        if isinstance(v, bool):
            boo.add(ks)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            num.add(ks)
        elif isinstance(v, str):
            st.add(ks)
        elif isinstance(v, (list, dict)):
            struct.add(ks)
        else:
            # None / other types are treated as "not enforced".
            pass

    return Contract(defaults=dict(defaults), num_keys=num, bool_keys=boo, str_keys=st, struct_keys=struct)


def doctor_base_and_ranges(
    base: Dict[str, Any],
    ranges: Dict[str, Any],
    contract: Contract,
    *,
    enum_overrides: Optional[Dict[str, Set[str]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Tuple[float, float]], DoctorReport]:
    """Normalize base and ranges according to contract.

    Returns:
      base2: normalized base (types fixed / defaults filled)
      ranges2: sanitized ranges (only numeric keys, finite floats, lo<hi)
      report: what was changed
    """

    enum_overrides = enum_overrides or {}

    base2: Dict[str, Any] = dict(base or {})
    ranges2: Dict[str, Tuple[float, float]] = {}

    rep = DoctorReport(coerced=[], filled_defaults=[], dropped_ranges=[], fixed_ranges=[], notes=[])

    # 1) Ensure all contract keys exist with correct types
    for k, dv in contract.defaults.items():
        ks = str(k)
        cur = base2.get(ks, None)

        if ks in contract.bool_keys:
            bv = _to_bool(cur)
            if bv is None:
                # fill default
                base2[ks] = bool(dv)
                rep.filled_defaults.append(ks)
            else:
                if cur is not bv:
                    rep.coerced.append(ks)
                base2[ks] = bool(bv)
            continue

        if ks in contract.str_keys:
            sv = _to_str(cur)
            if sv is None:
                base2[ks] = str(dv)
                rep.filled_defaults.append(ks)
            else:
                # optional enum validation
                allowed = enum_overrides.get(ks)
                if allowed and sv not in allowed:
                    base2[ks] = str(dv)
                    rep.coerced.append(ks)
                else:
                    base2[ks] = sv
            continue

        if ks in contract.num_keys:
            fv = _to_float(cur)
            if fv is None:
                base2[ks] = float(dv) if _is_num(dv) else 0.0
                rep.filled_defaults.append(ks)
            else:
                base2[ks] = float(fv)
                if not _is_num(cur):
                    rep.coerced.append(ks)
            continue

        if ks in contract.struct_keys:
            if isinstance(cur, type(dv)):
                # ok
                continue
            # deep copy to avoid shared lists
            base2[ks] = copy.deepcopy(dv)
            rep.filled_defaults.append(ks)

    # 2) Sanitize ranges
    for k, rr in (ranges or {}).items():
        ks = str(k)
        if ks not in contract.num_keys:
            rep.dropped_ranges.append(ks)
            continue
        if not (isinstance(rr, (list, tuple)) and len(rr) == 2):
            rep.dropped_ranges.append(ks)
            continue
        lo = _to_float(rr[0])
        hi = _to_float(rr[1])
        if lo is None or hi is None:
            rep.dropped_ranges.append(ks)
            continue
        if lo == hi:
            rep.dropped_ranges.append(ks)
            continue
        if lo > hi:
            lo, hi = hi, lo
            rep.fixed_ranges.append(ks)
        ranges2[ks] = (float(lo), float(hi))

    # 3) Ensure base is numeric for range keys (midpoint fallback)
    for ks, (lo, hi) in ranges2.items():
        if ks not in base2 or not _is_num(base2.get(ks)):
            base2[ks] = float(0.5 * (lo + hi))
            rep.notes.append(f"base[{ks}] set to midpoint because it was missing/non-numeric")

    return base2, ranges2, rep
