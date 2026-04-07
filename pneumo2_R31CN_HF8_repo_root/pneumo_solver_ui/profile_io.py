# -*- coding: utf-8 -*-
"""
profile_io.py

Профиль = переносимый JSON со всем, что нужно для воспроизведения расчёта/оптимизации:
- base (база параметров, SI-значения)
- ranges (диапазоны оптимизации, SI-значения)
- suite (таблица тест-набора, список dict)
- meta (произвольные метаданные: время, версия, комментарий)

Зачем:
- безопасное сохранение/перенос конфигурации между сессиями и машинами
- включение в send-bundle (workspace/exports уже попадает в bundle)
"""
from __future__ import annotations

import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

# Optional dependency (declared in requirements.txt)
try:
    from jsonschema import Draft202012Validator  # type: ignore
except Exception:  # pragma: no cover
    Draft202012Validator = None  # type: ignore


PROFILE_SCHEMA_V1: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schema", "version", "base", "ranges", "suite"],
    "properties": {
        "schema": {"type": "string", "const": "pneumo-profile"},
        "version": {"type": "integer", "const": 1},
        "meta": {"type": "object"},
        "base": {
            "type": "object",
            "additionalProperties": {"type": ["number", "string", "boolean", "array", "object", "null"]},
        },
        "ranges": {
            "type": "object",
            "additionalProperties": {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
                "items": {"type": "number"},
            },
        },
        "suite": {"type": "array", "items": {"type": "object"}},
    },
    "additionalProperties": True,
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(str(tmp), str(path))


def normalize_ranges(ranges: Dict[str, Any]) -> Dict[str, List[float]]:
    """Convert {k: (mn,mx)} or {k:[mn,mx]} into JSON-safe {k:[float,float]}."""
    out: Dict[str, List[float]] = {}
    for k, v in (ranges or {}).items():
        try:
            if isinstance(v, (list, tuple)) and len(v) == 2:
                out[str(k)] = [float(v[0]), float(v[1])]
        except Exception:
            continue
    return out


def validate_profile(profile: Any) -> List[str]:
    """Return list of human-readable validation errors (empty => ok)."""
    errs: List[str] = []
    if not isinstance(profile, dict):
        return ["profile: expected object/dict"]
    if profile.get("schema") != "pneumo-profile":
        errs.append("profile.schema must be 'pneumo-profile'")
    if profile.get("version") != 1:
        errs.append("profile.version must be 1")

    if Draft202012Validator is not None:
        try:
            v = Draft202012Validator(PROFILE_SCHEMA_V1)
            for e in v.iter_errors(profile):
                path = "/".join(str(p) for p in e.path) if e.path else "<root>"
                errs.append(f"{path}: {e.message}")
        except Exception as e:  # pragma: no cover
            errs.append(f"jsonschema validator failed: {e!r}")
    else:
        # Minimal fallback checks
        for key in ("base", "ranges", "suite"):
            if key not in profile:
                errs.append(f"profile missing '{key}'")
        if "ranges" in profile and not isinstance(profile.get("ranges"), dict):
            errs.append("profile.ranges must be object")
        if "suite" in profile and not isinstance(profile.get("suite"), list):
            errs.append("profile.suite must be array")
    return errs


def make_profile(
    base: Dict[str, Any],
    ranges: Dict[str, Any],
    suite: List[Dict[str, Any]],
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    p: Dict[str, Any] = {
        "schema": "pneumo-profile",
        "version": 1,
        "meta": dict(meta or {}),
        "base": dict(base or {}),
        "ranges": normalize_ranges(ranges or {}),
        "suite": list(suite or []),
    }
    p["meta"].setdefault("created_at", now_iso())
    return p


def read_profile(path: Path) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("profile JSON must be an object")
    return data


def write_profile(path: Path, profile: Dict[str, Any]) -> str:
    """Write profile JSON atomically. Returns sha256 of the JSON bytes."""
    b = json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    atomic_write_text(Path(path), b.decode("utf-8"), encoding="utf-8")
    return sha256_bytes(b)
