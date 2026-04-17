# -*- coding: utf-8 -*-
"""Explicit compare contracts for Desktop Compare Viewer.

The helper is deliberately UI-agnostic: Compare Viewer consumes historical
NPZ/session refs and surfaces mismatch state, but it does not mutate optimizer
history or reinterpret animator truth.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


COMPARE_CONTRACT_VERSION = "compare_contract_v1"
COMPARE_CONTRACT_ID = "ANALYSIS-COMPARE-CONTRACT-V17"

MISMATCH_DIMENSIONS: tuple[str, ...] = (
    "objective_contract_hash",
    "hard_gate_key",
    "hard_gate_tolerance",
    "active_baseline_hash",
    "suite_snapshot_hash",
    "inputs_snapshot_hash",
    "scenario_lineage_hash",
    "ring_source_hash",
    "ring_context_hash_set",
)

BLOCKING_MISMATCH_DIMENSIONS: frozenset[str] = frozenset(
    {
        "objective_contract_hash",
        "hard_gate_key",
        "hard_gate_tolerance",
    }
)

WARNING_MISMATCH_DIMENSIONS: frozenset[str] = frozenset(
    {
        "active_baseline_hash",
        "suite_snapshot_hash",
        "inputs_snapshot_hash",
        "scenario_lineage_hash",
        "ring_source_hash",
        "ring_context_hash_set",
    }
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        _jsonable(dict(payload)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def compare_contract_hash(payload: Mapping[str, Any]) -> str:
    """Stable SHA256 for the explicit compare contract identity."""

    clean = dict(payload or {})
    clean.pop("compare_contract_hash", None)
    clean.pop("mismatch_banner", None)
    return hashlib.sha256(_canonical_json(clean).encode("utf-8")).hexdigest()


def save_compare_contract(path: str | Path, contract: Mapping[str, Any]) -> None:
    """Persist a compare contract JSON sidecar without mutating the source."""

    p = Path(path)
    payload = _jsonable(dict(contract or {}))
    if isinstance(payload, dict) and not str(payload.get("compare_contract_hash") or "").strip():
        payload["compare_contract_hash"] = compare_contract_hash(payload)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_compare_contract(path: str | Path) -> Dict[str, Any]:
    """Load a compare contract JSON sidecar, tolerating future fields."""

    p = Path(path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, Mapping):
        raise ValueError("Compare contract JSON must be an object")
    return dict(obj)


def _as_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _nested(meta: Mapping[str, Any], *keys: str) -> Dict[str, Any]:
    for key in keys:
        obj = meta.get(key)
        if isinstance(obj, Mapping):
            return dict(obj)
    return {}


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return ""


def _norm_compare_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set, frozenset)):
        return _canonical_json({"v": sorted(str(v).strip() for v in value if str(v).strip())})
    if isinstance(value, Mapping):
        return _canonical_json(value)
    return str(value).strip()


def _short(value: Any, n: int = 12) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    return text[: max(1, int(n))]


def extract_compare_run_ref(
    meta: Mapping[str, Any] | None,
    *,
    npz_path: str | Path | None = None,
    label: str = "",
) -> Dict[str, Any]:
    """Extract consumer-only compare refs from a loaded NPZ meta payload."""

    src = _as_mapping(meta)
    selected_run = _nested(src, "selected_run_contract", "run_contract", "optimization_run_contract")
    objective = _nested(src, "objective_contract")
    baseline = _nested(src, "active_baseline_contract", "baseline_contract")
    analysis = _nested(src, "analysis_context")
    compare = _nested(src, "compare_contract")

    source_path = ""
    if npz_path is not None:
        try:
            source_path = str(Path(npz_path).expanduser().resolve())
        except Exception:
            source_path = str(npz_path)

    hard_gate_key = _first_text(
        src.get("hard_gate_key"),
        selected_run.get("hard_gate_key"),
        objective.get("hard_gate_key"),
        objective.get("penalty_key"),
        src.get("penalty_key"),
    )
    hard_gate_tolerance = _first_value(
        src.get("hard_gate_tolerance"),
        selected_run.get("hard_gate_tolerance"),
        objective.get("hard_gate_tolerance"),
        objective.get("penalty_tol"),
        src.get("penalty_tol"),
    )

    ref: Dict[str, Any] = {
        "label": str(label or "").strip(),
        "source_path": source_path,
        "compare_contract_path": _first_text(
            src.get("compare_contract_path"),
            selected_run.get("compare_contract_path"),
            compare.get("compare_contract_path"),
            compare.get("contract_path"),
            analysis.get("compare_contract_path"),
        ),
        "run_id": _first_text(src.get("run_id"), selected_run.get("run_id"), analysis.get("run_id")),
        "run_contract_hash": _first_text(
            src.get("run_contract_hash"),
            selected_run.get("run_contract_hash"),
            compare.get("run_contract_hash"),
        ),
        "objective_contract_hash": _first_text(
            src.get("objective_contract_hash"),
            selected_run.get("objective_contract_hash"),
            objective.get("objective_contract_hash"),
            analysis.get("objective_contract_hash"),
        ),
        "hard_gate_key": hard_gate_key,
        "hard_gate_tolerance": hard_gate_tolerance,
        "active_baseline_hash": _first_text(
            src.get("active_baseline_hash"),
            selected_run.get("active_baseline_hash"),
            baseline.get("active_baseline_hash"),
            baseline.get("active_baseline_contract_hash"),
            baseline.get("baseline_contract_hash"),
            baseline.get("baseline_hash"),
        ),
        "suite_snapshot_hash": _first_text(
            src.get("suite_snapshot_hash"),
            selected_run.get("suite_snapshot_hash"),
            baseline.get("suite_snapshot_hash"),
            analysis.get("suite_snapshot_hash"),
        ),
        "inputs_snapshot_hash": _first_text(
            src.get("inputs_snapshot_hash"),
            selected_run.get("inputs_snapshot_hash"),
            analysis.get("inputs_snapshot_hash"),
        ),
        "scenario_lineage_hash": _first_text(
            src.get("scenario_lineage_hash"),
            selected_run.get("scenario_lineage_hash"),
            analysis.get("scenario_lineage_hash"),
        ),
        "ring_source_hash": _first_text(
            src.get("ring_source_hash"),
            selected_run.get("ring_source_hash"),
            analysis.get("ring_source_hash"),
        ),
        "ring_context_hash_set": _first_value(
            src.get("ring_context_hash_set"),
            selected_run.get("ring_context_hash_set"),
            analysis.get("ring_context_hash_set"),
        ),
        "problem_hash": _first_text(src.get("problem_hash"), selected_run.get("problem_hash")),
        "baseline_ref": {
            "active_baseline_hash": _first_text(
                src.get("active_baseline_hash"),
                selected_run.get("active_baseline_hash"),
                baseline.get("active_baseline_hash"),
                baseline.get("active_baseline_contract_hash"),
                baseline.get("baseline_contract_hash"),
                baseline.get("baseline_hash"),
            ),
            "suite_snapshot_hash": _first_text(
                src.get("suite_snapshot_hash"),
                selected_run.get("suite_snapshot_hash"),
                baseline.get("suite_snapshot_hash"),
            ),
            "contract_path": _first_text(
                src.get("active_baseline_contract_path"),
                selected_run.get("active_baseline_contract_path"),
                baseline.get("contract_path"),
            ),
        },
        "objective_ref": {
            "objective_contract_hash": _first_text(
                src.get("objective_contract_hash"),
                selected_run.get("objective_contract_hash"),
                objective.get("objective_contract_hash"),
            ),
            "objective_keys": _first_value(src.get("objective_keys"), objective.get("objective_keys")),
            "hard_gate_key": hard_gate_key,
            "hard_gate_tolerance": hard_gate_tolerance,
            "contract_path": _first_text(src.get("objective_contract_path"), objective.get("contract_path")),
        },
    }
    return _jsonable(ref)


def compare_ref_mismatches(
    left_ref: Mapping[str, Any] | None,
    right_ref: Mapping[str, Any] | None,
    *,
    fields: Sequence[str] = MISMATCH_DIMENSIONS,
    include_missing: bool = False,
) -> List[Dict[str, str]]:
    left = _as_mapping(left_ref)
    right = _as_mapping(right_ref)
    out: List[Dict[str, str]] = []
    for field in fields:
        left_value = _norm_compare_value(left.get(field))
        right_value = _norm_compare_value(right.get(field))
        if left_value and right_value and left_value != right_value:
            out.append(
                {
                    "dimension": str(field),
                    "left": left_value,
                    "right": right_value,
                    "severity": "error" if field in BLOCKING_MISMATCH_DIMENSIONS else "warning",
                }
            )
        elif include_missing and (left_value or right_value):
            out.append(
                {
                    "dimension": str(field),
                    "left": left_value,
                    "right": right_value,
                    "severity": "warning",
                }
            )
    return out


def current_vs_historical_mismatch(
    current_context_ref: Mapping[str, Any] | None,
    historical_run_ref: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    mismatches = compare_ref_mismatches(current_context_ref, historical_run_ref)
    severity = "info"
    banner_id = "BANNER-HIST-001"
    if any(str(item.get("severity")) == "error" for item in mismatches):
        severity = "warning"
        banner_id = "BANNER-HIST-002"
    elif mismatches:
        severity = "warning"
        banner_id = "BANNER-HIST-002"
    return {
        "banner_id": banner_id,
        "severity": severity,
        "scope": "current_vs_historical",
        "mismatch_dimensions": [str(item.get("dimension")) for item in mismatches],
        "mismatches": mismatches,
    }


def compare_contract_mismatch_summary(
    contract: Mapping[str, Any] | None,
    *,
    current_context_ref: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = _as_mapping(contract)
    run_refs = [
        _as_mapping(item)
        for item in list(payload.get("run_refs") or [])
        if isinstance(item, Mapping)
    ]
    current = _as_mapping(current_context_ref or payload.get("current_context_ref"))

    if not run_refs:
        return {
            "banner_id": "BANNER-HIST-003",
            "severity": "error",
            "scope": "missing_compare_contract",
            "mismatch_dimensions": ["artifact_missing"],
            "mismatches": [
                {
                    "dimension": "artifact_missing",
                    "left": "compare_contract",
                    "right": "",
                    "severity": "error",
                }
            ],
        }

    mismatches: List[Dict[str, str]] = []
    if current:
        for ref in run_refs:
            mismatches.extend(compare_ref_mismatches(current, ref))
    elif len(run_refs) >= 2:
        left = run_refs[0]
        for right in run_refs[1:]:
            mismatches.extend(compare_ref_mismatches(left, right))

    dimensions = sorted({str(item.get("dimension")) for item in mismatches if item.get("dimension")})
    if dimensions:
        severity = "warning"
        if any(str(item.get("severity")) == "error" for item in mismatches):
            severity = "warning"
        return {
            "banner_id": "BANNER-HIST-002",
            "severity": severity,
            "scope": "compare_mismatch",
            "mismatch_dimensions": dimensions,
            "mismatches": mismatches,
        }

    has_required_ref = any(
        _norm_compare_value(ref.get(field))
        for ref in run_refs
        for field in (
            "run_contract_hash",
            "objective_contract_hash",
            "active_baseline_hash",
            "suite_snapshot_hash",
            "scenario_lineage_hash",
        )
    )
    if not has_required_ref:
        return {
            "banner_id": "BANNER-HIST-003",
            "severity": "warning",
            "scope": "missing_compare_refs",
            "mismatch_dimensions": ["artifact_missing"],
            "mismatches": [
                {
                    "dimension": "artifact_missing",
                    "left": "baseline/objective/run refs",
                    "right": "",
                    "severity": "warning",
                }
            ],
        }

    return {
        "banner_id": "BANNER-HIST-001",
        "severity": "info",
        "scope": "historical_context",
        "mismatch_dimensions": [],
        "mismatches": [],
    }


def build_compare_contract(
    run_refs: Sequence[Mapping[str, Any]] | None,
    *,
    compare_mode: str = "run_vs_run",
    selected_table: str = "",
    selected_tests: Sequence[str] | None = None,
    selected_segments: Sequence[str] | None = None,
    selected_metrics: Sequence[str] | None = None,
    selected_time_window: Sequence[float] | None = None,
    unit_profile: Mapping[str, Any] | None = None,
    alignment_mode: str = "time_s",
    current_context_ref: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    refs = [_jsonable(dict(ref)) for ref in (run_refs or []) if isinstance(ref, Mapping)]
    metrics = [str(x) for x in (selected_metrics or []) if str(x).strip()]
    time_window: List[float] = []
    if selected_time_window is not None:
        try:
            vals = list(selected_time_window)
            if len(vals) >= 2:
                left = float(vals[0])
                right = float(vals[1])
                if math.isfinite(left) and math.isfinite(right):
                    time_window = [left, right]
        except Exception:
            time_window = []
    payload: Dict[str, Any] = {
        "version": COMPARE_CONTRACT_VERSION,
        "compare_contract_id": COMPARE_CONTRACT_ID,
        "compare_mode": str(compare_mode or "run_vs_run"),
        "left_ref": refs[0] if refs else {},
        "right_ref": refs[1] if len(refs) > 1 else _jsonable(dict(current_context_ref or {})),
        "run_refs": refs,
        "baseline_ref": _jsonable(dict(refs[0].get("baseline_ref") or {})) if refs and isinstance(refs[0], Mapping) else {},
        "objective_ref": _jsonable(dict(refs[0].get("objective_ref") or {})) if refs and isinstance(refs[0], Mapping) else {},
        "current_context_ref": _jsonable(dict(current_context_ref or {})),
        "selected_table": str(selected_table or ""),
        "selected_tests": [str(x) for x in (selected_tests or []) if str(x).strip()],
        "selected_segments": [str(x) for x in (selected_segments or []) if str(x).strip()],
        "selected_metrics": metrics,
        "selected_signals": metrics,
        "selected_time_window": time_window,
        "unit_profile": _jsonable(dict(unit_profile or {})),
        "alignment_mode": str(alignment_mode or "time_s"),
        "mismatch_policy": {
            "policy_id": "COMPARE-MISMATCH-POLICY-V24",
            "blocking_dimensions": sorted(BLOCKING_MISMATCH_DIMENSIONS),
            "warning_dimensions": sorted(WARNING_MISMATCH_DIMENSIONS),
            "missing_artifact_banner_id": "BANNER-HIST-003",
            "mismatch_banner_id": "BANNER-HIST-002",
        },
    }
    payload["compare_contract_hash"] = compare_contract_hash(payload)
    payload["mismatch_banner"] = compare_contract_mismatch_summary(payload)
    return payload


def format_compare_mismatch_banner(summary: Mapping[str, Any] | None) -> str:
    data = _as_mapping(summary)
    banner_id = str(data.get("banner_id") or "")
    dims = [str(x) for x in (data.get("mismatch_dimensions") or []) if str(x).strip()]
    if banner_id == "BANNER-HIST-002":
        suffix = ", ".join(dims[:6]) if dims else "contract refs"
        return (
            "Текущий/исторический контекст отличается: "
            f"{suffix}. Сравнение выполняется по зафиксированным NPZ refs; "
            "optimizer history не изменяется."
        )
    if banner_id == "BANNER-HIST-003":
        suffix = ", ".join(dims[:6]) if dims else "artifact refs"
        return (
            "Не хватает артефактов для полного compare contract: "
            f"{suffix}. Тихий fallback на текущий проект запрещен."
        )
    if banner_id == "BANNER-HIST-001":
        return "Открыт исторический compare context; refs совпадают с выбранным контекстом."
    return ""


def format_compare_contract_summary(contract: Mapping[str, Any] | None) -> str:
    payload = _as_mapping(contract)
    refs = [_as_mapping(item) for item in list(payload.get("run_refs") or []) if isinstance(item, Mapping)]
    if not refs:
        return "Compare contract: -"
    objective_hashes = sorted({_short(ref.get("objective_contract_hash")) for ref in refs if ref.get("objective_contract_hash")})
    baseline_hashes = sorted({_short(ref.get("active_baseline_hash")) for ref in refs if ref.get("active_baseline_hash")})
    run_hashes = sorted({_short(ref.get("run_contract_hash")) for ref in refs if ref.get("run_contract_hash")})
    banner = _as_mapping(payload.get("mismatch_banner"))
    dims = [str(x) for x in (banner.get("mismatch_dimensions") or []) if str(x).strip()]
    lines = [
        f"compare_contract_hash={_short(payload.get('compare_contract_hash'), 16)}",
        f"mode={payload.get('compare_mode') or '-'} runs={len(refs)}",
        f"run_refs={', '.join(run_hashes) if run_hashes else '-'}",
        f"objective={', '.join(objective_hashes) if objective_hashes else '-'}",
        f"baseline={', '.join(baseline_hashes) if baseline_hashes else '-'}",
    ]
    if dims:
        lines.append(f"mismatch={banner.get('banner_id') or '-'}: {', '.join(dims[:6])}")
    return "\n".join(lines)


__all__ = [
    "BLOCKING_MISMATCH_DIMENSIONS",
    "COMPARE_CONTRACT_ID",
    "COMPARE_CONTRACT_VERSION",
    "MISMATCH_DIMENSIONS",
    "WARNING_MISMATCH_DIMENSIONS",
    "build_compare_contract",
    "compare_contract_hash",
    "compare_contract_mismatch_summary",
    "compare_ref_mismatches",
    "current_vs_historical_mismatch",
    "extract_compare_run_ref",
    "format_compare_contract_summary",
    "format_compare_mismatch_banner",
    "load_compare_contract",
    "save_compare_contract",
]
