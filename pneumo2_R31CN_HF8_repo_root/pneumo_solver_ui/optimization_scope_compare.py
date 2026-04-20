from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .optimization_problem_hash_mode import normalize_problem_hash_mode
from .optimization_problem_scope import problem_hash_short_label

_SCOPE_SPLIT_RE = re.compile(r"[\n,;]+")
_SCOPE_COMPARE_FIELDS = (
    "problem_hash",
    "problem_hash_mode",
    "objective_keys",
    "penalty_key",
    "penalty_tol",
)
_HARD_SCOPE_MISMATCH_FIELDS = {"problem_hash", "problem_hash_mode"}
_SCOPE_PROGRESS_KEYS = (
    "status",
    "completed",
    "in_flight",
    "cached_hits",
    "duplicates_skipped",
    "run_id",
    "backend",
    "created_by",
)


def _safe_json_loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return None


def _collect_scope_items(raw: Any, out: list[str]) -> None:
    if raw is None:
        return
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return
        if text[:1] in {"[", '"'}:
            parsed = _safe_json_loads(text)
            if parsed is not None and parsed is not raw:
                _collect_scope_items(parsed, out)
                return
        for piece in _SCOPE_SPLIT_RE.split(text):
            item = str(piece or "").strip()
            if item and item not in out:
                out.append(item)
        return
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        for item in raw:
            _collect_scope_items(item, out)


def _normalize_scope_list(raw: Any) -> list[str]:
    out: list[str] = []
    _collect_scope_items(raw, out)
    return out


def _normalize_penalty_tol(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    return out if math.isfinite(out) else None


def _has_scope_signal(payload: Mapping[str, Any] | None) -> bool:
    if not isinstance(payload, Mapping):
        return False
    for key in _SCOPE_COMPARE_FIELDS:
        value = payload.get(key)
        if value not in (None, "", []):
            return True
    return False


def normalize_optimizer_scope_payload(
    raw: Any,
    *,
    source: str = "",
    source_path: str = "",
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    payload = dict(raw)
    objective_contract = (
        dict(payload.get("objective_contract") or {})
        if isinstance(payload.get("objective_contract"), Mapping)
        else {}
    )

    problem_hash = str(payload.get("problem_hash") or objective_contract.get("problem_hash") or "").strip()
    problem_hash_short = str(payload.get("problem_hash_short") or "").strip()
    if problem_hash and not problem_hash_short:
        problem_hash_short = problem_hash_short_label(problem_hash)

    problem_hash_mode = normalize_problem_hash_mode(
        payload.get("problem_hash_mode") or objective_contract.get("problem_hash_mode"),
        default="",
    )

    objective_keys_raw = payload.get("objective_keys")
    if objective_keys_raw in (None, "", []):
        objective_keys_raw = objective_contract.get("objective_keys")
    objective_keys = _normalize_scope_list(objective_keys_raw)

    penalty_key = str(payload.get("penalty_key") or objective_contract.get("penalty_key") or "").strip()

    penalty_tol = payload.get("penalty_tol")
    if penalty_tol in (None, "") and "penalty_tol" in objective_contract:
        penalty_tol = objective_contract.get("penalty_tol")
    penalty_tol_norm = _normalize_penalty_tol(penalty_tol)

    out: Dict[str, Any] = {}
    if source:
        out["source"] = source
    if source_path:
        out["source_path"] = source_path
    if problem_hash:
        out["problem_hash"] = problem_hash
        out["problem_hash_short"] = problem_hash_short or problem_hash_short_label(problem_hash)
    if problem_hash_mode:
        out["problem_hash_mode"] = problem_hash_mode
    if objective_keys:
        out["objective_keys"] = list(objective_keys)
    if penalty_key:
        out["penalty_key"] = penalty_key
    if penalty_tol_norm is not None:
        out["penalty_tol"] = float(penalty_tol_norm)
    if objective_contract:
        out["objective_contract"] = dict(objective_contract)

    for key in _SCOPE_PROGRESS_KEYS:
        value = payload.get(key)
        if value not in (None, "", []):
            out[key] = value

    return out if _has_scope_signal(out) else {}


def extract_optimizer_scope_from_triage(
    raw: Any,
    *,
    source: str = "triage",
    source_path: str = "triage/triage_report.json",
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    scope = raw.get("dist_progress")
    if not isinstance(scope, Mapping):
        scope = raw.get("optimizer_scope")
    return normalize_optimizer_scope_payload(scope, source=source, source_path=source_path)


def extract_optimizer_scope_from_validation(
    raw: Any,
    *,
    source: str = "validation",
    source_path: str = "validation/validation_report.json",
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    return normalize_optimizer_scope_payload(raw.get("optimizer_scope"), source=source, source_path=source_path)


def extract_optimizer_scope_from_dashboard(
    raw: Any,
    *,
    source: str = "dashboard",
    source_path: str = "dashboard/dashboard.json",
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    return normalize_optimizer_scope_payload(raw.get("optimizer_scope"), source=source, source_path=source_path)


def extract_optimizer_scope_from_health(
    raw: Any,
    *,
    source: str = "health",
    source_path: str = "health/health_report.json",
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    signals = dict(raw.get("signals") or {}) if isinstance(raw.get("signals"), Mapping) else {}
    return normalize_optimizer_scope_payload(signals.get("optimizer_scope"), source=source, source_path=source_path)


def extract_optimizer_scope_from_run_scope(
    raw: Any,
    *,
    source: str,
    source_path: str,
) -> Dict[str, Any]:
    return normalize_optimizer_scope_payload(raw, source=source, source_path=source_path)


def optimizer_scope_export_source_name(source_path: str) -> str:
    path = Path(str(source_path or ""))
    parts = list(path.parts)
    if len(parts) >= 3 and parts[-1] == "run_scope.json" and parts[-2] == "export":
        return f"export:{parts[-3]}"
    if path.stem:
        return f"export:{path.stem}"
    return "export"


def _compare_value(field: str, payload: Mapping[str, Any]) -> Any:
    if field == "objective_keys":
        return tuple(str(x).strip() for x in (payload.get("objective_keys") or []) if str(x).strip())
    if field == "penalty_tol":
        return _normalize_penalty_tol(payload.get("penalty_tol"))
    return str(payload.get(field) or "").strip()


def _display_value(field: str, payload: Mapping[str, Any]) -> str:
    value = payload.get(field)
    if field == "objective_keys":
        return json.dumps(list(payload.get("objective_keys") or []), ensure_ascii=False)
    if field == "penalty_tol":
        norm = _normalize_penalty_tol(value)
        return "null" if norm is None else str(norm)
    text = str(value or "").strip()
    return text or "—"


def _source_sort_key(source_name: str, preferred_order: Sequence[str]) -> tuple[int, str]:
    label = str(source_name or "")
    for idx, preferred in enumerate(preferred_order):
        pref = str(preferred or "")
        if label == pref or label.startswith(pref + ":"):
            return idx, label
    return len(preferred_order), label


def compare_optimizer_scope_sources(
    sources: Mapping[str, Any] | None,
    *,
    preferred_order: Sequence[str] = ("triage", "health", "validation", "dashboard", "export"),
) -> Dict[str, Any]:
    normalized_sources: Dict[str, Dict[str, Any]] = {}
    for source_name, raw_payload in dict(sources or {}).items():
        if isinstance(raw_payload, Mapping):
            source = str(raw_payload.get("source") or source_name or "").strip()
            source_path = str(raw_payload.get("source_path") or "").strip()
            norm = normalize_optimizer_scope_payload(raw_payload, source=source, source_path=source_path)
        else:
            norm = {}
        if norm:
            normalized_sources[str(norm.get("source") or source_name or "")] = norm

    if not normalized_sources:
        return {}

    canonical_name = sorted(
        normalized_sources,
        key=lambda item: _source_sort_key(item, preferred_order),
    )[0]
    canonical = dict(normalized_sources.get(canonical_name) or {})

    issues: list[str] = []
    mismatch_fields: list[str] = []
    compared_fields: list[str] = []
    for field in _SCOPE_COMPARE_FIELDS:
        present: Dict[str, Any] = {}
        for source_name, payload in normalized_sources.items():
            cmp_value = _compare_value(field, payload)
            if cmp_value not in (None, "", ()):
                present[source_name] = cmp_value
        if len(present) < 2:
            continue
        compared_fields.append(field)
        unique_values = {value for value in present.values()}
        if len(unique_values) <= 1:
            continue
        parts = ", ".join(
            f"{source_name}={_display_value(field, normalized_sources[source_name])}"
            for source_name in sorted(present, key=lambda item: _source_sort_key(item, preferred_order))
        )
        issues.append(f"область оптимизации: поле {field} отличается между источниками: {parts}")
        mismatch_fields.append(field)

    canonical["available"] = True
    canonical["canonical_source"] = canonical_name
    canonical["source_count"] = len(normalized_sources)
    canonical["sources"] = normalized_sources
    canonical["compared_fields"] = list(compared_fields)
    canonical["mismatch_fields"] = list(dict.fromkeys(mismatch_fields))
    canonical["issues"] = list(issues)
    canonical["scope_sync_ok"] = False if issues else (True if compared_fields else None)
    return canonical


def evaluate_optimizer_scope_gate(scope_summary: Mapping[str, Any] | None) -> Dict[str, Any]:
    scope = dict(scope_summary or {}) if isinstance(scope_summary, Mapping) else {}
    source_count = 0
    try:
        source_count = int(scope.get("source_count") or 0)
    except Exception:
        source_count = 0
    mismatch_fields = [
        str(field).strip()
        for field in (scope.get("mismatch_fields") or [])
        if str(field).strip()
    ]
    if not source_count:
        source_count = len(dict(scope.get("sources") or {}))
    if not mismatch_fields:
        mismatch_fields = [
            str(field).strip()
            for field in _SCOPE_COMPARE_FIELDS
            if any(
                f"optimizer scope {field} mismatch" in str(issue)
                or f"область оптимизации: поле {field} отличается" in str(issue)
                for issue in (scope.get("issues") or [])
            )
        ]

    gate: Dict[str, Any] = {
        "release_gate": "MISSING",
        "release_gate_reason": "данные области оптимизации отсутствуют",
        "dominant_kind": "missing",
        "release_risk": False,
        "canonical_source": str(scope.get("canonical_source") or ""),
        "source_count": int(source_count or 0),
        "scope_sync_ok": scope.get("scope_sync_ok"),
        "mismatch_fields": list(mismatch_fields),
    }

    if not scope:
        return gate

    if mismatch_fields:
        gate["release_risk"] = True
        gate["dominant_kind"] = "hard_mismatch" if any(field in _HARD_SCOPE_MISMATCH_FIELDS for field in mismatch_fields) else "soft_mismatch"
        gate["release_gate"] = "FAIL" if gate["dominant_kind"] == "hard_mismatch" else "WARN"
        gate["release_gate_reason"] = (
            f"область оптимизации отличается между источниками ({int(source_count or 0)}): {', '.join(mismatch_fields)}"
        )
        return gate

    if scope.get("scope_sync_ok") is True:
        gate["release_gate"] = "PASS"
        gate["release_gate_reason"] = f"область оптимизации согласована между источниками ({int(source_count or 0)})"
        gate["dominant_kind"] = "pass"
        return gate

    if source_count > 0:
        gate["release_gate"] = "MISSING"
        gate["release_gate_reason"] = f"синхронизацию области оптимизации нельзя проверить по {int(source_count)} источнику(ам)"
        gate["dominant_kind"] = "single_source"
        return gate

    return gate


__all__ = [
    "evaluate_optimizer_scope_gate",
    "compare_optimizer_scope_sources",
    "extract_optimizer_scope_from_dashboard",
    "extract_optimizer_scope_from_health",
    "extract_optimizer_scope_from_run_scope",
    "extract_optimizer_scope_from_triage",
    "extract_optimizer_scope_from_validation",
    "normalize_optimizer_scope_payload",
    "optimizer_scope_export_source_name",
]
