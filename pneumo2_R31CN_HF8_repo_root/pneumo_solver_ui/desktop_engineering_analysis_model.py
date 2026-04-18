from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from pneumo_solver_ui.compare_influence import (
    rank_features_by_max_abs_corr,
    top_cells,
)


ENGINEERING_ANALYSIS_SCHEMA = "desktop_engineering_analysis"
ENGINEERING_ANALYSIS_SCHEMA_VERSION = "1.0.0"
ENGINEERING_ANALYSIS_EVIDENCE_SCHEMA = "desktop_engineering_analysis_evidence_manifest"
ENGINEERING_ANALYSIS_EVIDENCE_SCHEMA_VERSION = "1.0.0"
ENGINEERING_ANALYSIS_HANDOFF_ID = "HO-009"
ENGINEERING_ANALYSIS_PRODUCED_BY = "WS-ANALYSIS"
ENGINEERING_ANALYSIS_CONSUMED_BY = "WS-DIAGNOSTICS"
SELECTED_RUN_CONTRACT_SCHEMA_VERSION = "selected_run_contract_v1"
SELECTED_RUN_CONTRACT_FILENAME = "selected_run_contract.json"
SELECTED_RUN_HANDOFF_ID = "HO-007"
SELECTED_RUN_PRODUCED_BY = "WS-OPTIMIZATION"
SELECTED_RUN_CONSUMED_BY = "WS-ANALYSIS"
ANALYSIS_TO_ANIMATOR_HANDOFF_ID = "HO-008"
ANALYSIS_CONTEXT_FILENAME = "analysis_context.json"
ANIMATOR_LINK_CONTRACT_FILENAME = "animator_link_contract.json"
ANALYSIS_WORKSPACE_ID = "WS-ANALYSIS"
ANIMATOR_WORKSPACE_ID = "WS-ANIMATOR"


SYSTEM_INFLUENCE_UNIT_CATALOG: dict[str, str] = {
    "score": "dimensionless",
    "eps_rel_used": "dimensionless",
    "adaptive_stability_loss": "dimensionless",
    "p_up_ref": "Pa",
    "p_dn_ref": "Pa",
    "min_bottleneck_mdot": "kg/s",
    "avg_bottleneck_mdot": "kg/s",
    "wheelbase": "m",
    "track": "m",
    "h_cg": "m",
    "z_static": "m",
    "phi_crit_rad": "rad",
    "theta_crit_rad": "rad",
    "phi_crit_deg": "deg",
    "theta_crit_deg": "deg",
    "k_tire": "N/m",
    "k_spring": "N/m",
    "k_pneumo": "N/m",
    "k_corner": "N/m",
    "Kphi": "N*m/rad",
    "Ktheta": "N*m/rad",
    "f_roll": "Hz",
    "f_pitch": "Hz",
    "static_trim_body_height_err_max_m": "m",
    "static_trim_max_abs_res": "model residual",
    "static_trim_pressure_trim_max_abs_scale_delta": "dimensionless",
    "static_trim_pressure_trim_enable": "bool",
    "static_trim_pressure_trim_bootstrap_applied": "bool",
    "static_trim_pressure_trim_mode": "enum",
    "static_trim_pressure_trim_precharge_override_json": "json",
    "static_trim_success": "bool",
}


@dataclass(frozen=True)
class SelectedRunContext:
    run_id: str
    mode: str
    status: str
    run_dir: str
    objective_contract_hash: str
    hard_gate_key: str
    hard_gate_tolerance: Any
    active_baseline_hash: str
    suite_snapshot_hash: str
    problem_hash: str = ""
    run_contract_hash: str = ""
    selected_run_contract_hash: str = ""
    selected_run_contract_path: str = ""
    started_at_utc: str = ""
    finished_at_utc: str = ""
    results_csv_path: str = ""
    artifact_dir: str = ""
    selected_best_candidate_ref: str = ""
    results_artifact_index: Mapping[str, Any] = field(default_factory=dict)
    objective_stack: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["objective_stack"] = list(self.objective_stack)
        payload["results_artifact_index"] = dict(self.results_artifact_index or {})
        return payload

    def compare_ref(self, *, label: str = "") -> dict[str, Any]:
        return {
            "label": str(label or self.run_id or "selected_run"),
            "source_path": str(self.results_csv_path or self.artifact_dir or self.run_dir),
            "run_id": self.run_id,
            "run_contract_hash": self.run_contract_hash or self.selected_run_contract_hash,
            "objective_contract_hash": self.objective_contract_hash,
            "hard_gate_key": self.hard_gate_key,
            "hard_gate_tolerance": self.hard_gate_tolerance,
            "active_baseline_hash": self.active_baseline_hash,
            "suite_snapshot_hash": self.suite_snapshot_hash,
            "problem_hash": self.problem_hash,
            "baseline_ref": {
                "active_baseline_hash": self.active_baseline_hash,
                "suite_snapshot_hash": self.suite_snapshot_hash,
            },
            "objective_ref": {
                "objective_contract_hash": self.objective_contract_hash,
                "objective_keys": list(self.objective_stack),
                "hard_gate_key": self.hard_gate_key,
                "hard_gate_tolerance": self.hard_gate_tolerance,
            },
        }


@dataclass(frozen=True)
class SelectedRunContractSnapshot:
    path: Path | None
    exists: bool
    status: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    selected_run_context: SelectedRunContext | None = None
    selected_run_contract_hash: str = ""
    computed_contract_hash: str = ""
    missing_fields: tuple[str, ...] = ()
    blocking_states: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    mismatch_summary: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "path": str(self.path or ""),
            "exists": bool(self.exists),
            "status": self.status,
            "selected_run_contract_hash": self.selected_run_contract_hash,
            "computed_contract_hash": self.computed_contract_hash,
            "missing_fields": list(self.missing_fields),
            "blocking_states": list(self.blocking_states),
            "warnings": list(self.warnings),
            "mismatch_summary": dict(self.mismatch_summary or {}),
            "selected_run_context": (
                self.selected_run_context.to_payload()
                if self.selected_run_context is not None
                else {}
            ),
        }


@dataclass(frozen=True)
class EngineeringAnalysisArtifact:
    key: str
    title: str
    category: str
    path: Path
    status: str = "READY"
    required: bool = False
    detail: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = str(self.path)
        return payload


@dataclass(frozen=True)
class EngineeringSensitivityRow:
    param: str
    group: str
    score: float
    status: str
    eps_rel_used: float | None
    strongest_metric: str
    strongest_elasticity: float

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EngineeringAnalysisPipelineRow:
    key: str
    section: str
    title: str
    status: str
    detail: str = ""
    path: Path | None = None
    units: Mapping[str, str] = field(default_factory=dict)
    metrics: Mapping[str, Any] = field(default_factory=dict)
    source: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": str(self.key),
            "section": str(self.section),
            "title": str(self.title),
            "status": str(self.status),
            "detail": str(self.detail or ""),
            "path": str(self.path or ""),
            "units": dict(self.units or {}),
            "metrics": dict(self.metrics or {}),
            "source": str(self.source or ""),
        }


@dataclass(frozen=True)
class EngineeringAnalysisSnapshot:
    run_dir: Path | None
    status: str
    influence_status: str
    calibration_status: str
    compare_status: str
    artifacts: tuple[EngineeringAnalysisArtifact, ...]
    sensitivity_rows: tuple[EngineeringSensitivityRow, ...]
    unit_catalog: Mapping[str, str]
    diagnostics_evidence_manifest_path: Path | None = None
    diagnostics_evidence_manifest_hash: str = ""
    diagnostics_evidence_manifest_status: str = "MISSING"
    selected_run_context: SelectedRunContext | None = None
    selected_run_contract_path: Path | None = None
    selected_run_contract_hash: str = ""
    contract_status: str = "MISSING"
    mismatch_summary: Mapping[str, Any] = field(default_factory=dict)
    blocking_states: tuple[str, ...] = ()

    def artifact_by_key(self, key: str) -> EngineeringAnalysisArtifact | None:
        wanted = str(key)
        for artifact in self.artifacts:
            if artifact.key == wanted:
                return artifact
        return None


@dataclass(frozen=True)
class EngineeringAnalysisJobResult:
    ok: bool
    status: str
    command: tuple[str, ...]
    returncode: int | None
    run_dir: Path | None
    artifacts: tuple[EngineeringAnalysisArtifact, ...] = ()
    log_text: str = ""
    error: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "status": str(self.status or ""),
            "command": list(self.command),
            "returncode": self.returncode,
            "run_dir": str(self.run_dir or ""),
            "artifacts": [item.to_payload() for item in self.artifacts],
            "log_text": str(self.log_text or ""),
            "error": str(self.error or ""),
        }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _payload_hash(payload: Mapping[str, Any], *, hash_key: str) -> str:
    clean = dict(payload or {})
    clean.pop(hash_key, None)
    blob = json.dumps(
        _jsonable(clean),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8", errors="replace")
    return hashlib.sha256(blob).hexdigest()


def selected_run_context_from_payload(
    payload: Mapping[str, Any],
    *,
    contract_path: Path | str | None = None,
    contract_hash: str = "",
) -> SelectedRunContext:
    data = dict(payload or {})
    results_index = _mapping(data.get("results_artifact_index"))
    contract_hash_value = _text(
        contract_hash
        or data.get("selected_run_contract_hash")
        or data.get("run_contract_hash")
    )
    return SelectedRunContext(
        run_id=_text(data.get("run_id") or data.get("run_name")),
        mode=_text(data.get("mode") or data.get("active_mode") or data.get("pipeline_mode")),
        status=_text(data.get("status")),
        run_dir=_text(data.get("run_dir") or results_index.get("run_dir")),
        objective_contract_hash=_text(data.get("objective_contract_hash")),
        hard_gate_key=_text(data.get("hard_gate_key") or data.get("penalty_key")),
        hard_gate_tolerance=data.get("hard_gate_tolerance", data.get("penalty_tol", "")),
        active_baseline_hash=_text(data.get("active_baseline_hash")),
        suite_snapshot_hash=_text(data.get("suite_snapshot_hash")),
        problem_hash=_text(data.get("problem_hash")),
        run_contract_hash=_text(data.get("run_contract_hash") or contract_hash_value),
        selected_run_contract_hash=contract_hash_value,
        selected_run_contract_path=_text(contract_path),
        started_at_utc=_text(data.get("started_at_utc")),
        finished_at_utc=_text(data.get("finished_at_utc")),
        results_csv_path=_text(data.get("results_csv_path") or results_index.get("results_csv_path")),
        artifact_dir=_text(data.get("artifact_dir")),
        selected_best_candidate_ref=_text(
            data.get("selected_best_candidate_ref") or data.get("best_candidate_ref")
        ),
        results_artifact_index=results_index,
        objective_stack=tuple(str(item) for item in (data.get("objective_stack") or ()) if str(item).strip()),
    )


def selected_run_compare_ref(
    context: SelectedRunContext | Mapping[str, Any] | None,
    *,
    label: str = "",
) -> dict[str, Any]:
    if isinstance(context, SelectedRunContext):
        return context.compare_ref(label=label)
    if isinstance(context, Mapping):
        return selected_run_context_from_payload(context).compare_ref(label=label)
    return {}


def build_analysis_compare_contract(
    left_ref: Mapping[str, Any] | SelectedRunContext | None,
    right_ref: Mapping[str, Any] | SelectedRunContext | None,
    *,
    compare_mode: str = "baseline_vs_selected_run",
    selected_tests: Sequence[str] | None = None,
    selected_segments: Sequence[str] | None = None,
    selected_metrics: Sequence[str] | None = None,
    unit_profile: Mapping[str, Any] | None = None,
    alignment_mode: str = "time_s",
    results_source_kind: str = "selected_run_contract",
) -> dict[str, Any]:
    from pneumo_solver_ui.compare_contract import (
        build_compare_contract,
        compare_contract_mismatch_summary,
    )

    left = selected_run_compare_ref(left_ref, label="left")
    right = selected_run_compare_ref(right_ref, label="right")
    refs = [ref for ref in (left, right) if ref]
    if len(refs) < 2:
        summary = compare_contract_mismatch_summary({})
        return {
            "analysis_schema": ENGINEERING_ANALYSIS_SCHEMA,
            "analysis_schema_version": ENGINEERING_ANALYSIS_SCHEMA_VERSION,
            "compare_mode": str(compare_mode or "baseline_vs_selected_run"),
            "results_source_kind": str(results_source_kind or "selected_run_contract"),
            "left_ref": left,
            "right_ref": right,
            "run_refs": refs,
            "selected_tests": [str(item) for item in (selected_tests or ()) if str(item).strip()],
            "selected_segments": [str(item) for item in (selected_segments or ()) if str(item).strip()],
            "selected_metrics": [str(item) for item in (selected_metrics or ()) if str(item).strip()],
            "unit_profile": dict(unit_profile or {}),
            "alignment_mode": str(alignment_mode or "time_s"),
            "analysis_compare_ready_state": "blocked",
            "blocking_states": ("missing explicit compare refs",),
            "warnings": (),
            "mismatch_banner": summary,
        }

    payload = build_compare_contract(
        refs,
        compare_mode=compare_mode,
        selected_tests=selected_tests,
        selected_segments=selected_segments,
        selected_metrics=selected_metrics,
        unit_profile=unit_profile,
        alignment_mode=alignment_mode,
    )
    banner = dict(payload.get("mismatch_banner") or {})
    mismatches = [
        dict(item)
        for item in (banner.get("mismatches") or ())
        if isinstance(item, Mapping)
    ]
    blocking = tuple(
        str(item.get("dimension") or "")
        for item in mismatches
        if str(item.get("severity") or "") == "error" and str(item.get("dimension") or "").strip()
    )
    warnings = tuple(
        str(item.get("dimension") or "")
        for item in mismatches
        if str(item.get("severity") or "") != "error" and str(item.get("dimension") or "").strip()
    )
    payload.update(
        {
            "analysis_schema": ENGINEERING_ANALYSIS_SCHEMA,
            "analysis_schema_version": ENGINEERING_ANALYSIS_SCHEMA_VERSION,
            "results_source_kind": str(results_source_kind or "selected_run_contract"),
            "metric_labels": [str(item) for item in (selected_metrics or ()) if str(item).strip()],
            "metric_units": dict(unit_profile or {}),
            "analysis_compare_ready_state": "blocked" if blocking else ("warning" if warnings else "ready"),
            "blocking_states": blocking,
            "warnings": warnings,
        }
    )
    return payload


def build_analysis_to_animator_link_contract(
    selected_run_context: SelectedRunContext | Mapping[str, Any] | None,
    *,
    selected_result_artifact_pointer: Mapping[str, Any] | str | Path | None,
    selected_test_id: str = "",
    selected_segment_id: str = "",
    selected_time_window: Mapping[str, Any] | None = None,
    selected_best_candidate_ref: str = "",
    compare_contract: Mapping[str, Any] | None = None,
    analysis_context_path: str | Path | None = None,
    now_text: str = "",
    extra_blocking_states: Sequence[str] = (),
    extra_warnings: Sequence[str] = (),
) -> dict[str, Any]:
    if isinstance(selected_run_context, SelectedRunContext):
        context = selected_run_context
    elif isinstance(selected_run_context, Mapping):
        context = selected_run_context_from_payload(selected_run_context)
    else:
        context = None

    if isinstance(selected_result_artifact_pointer, Mapping):
        pointer = dict(selected_result_artifact_pointer)
    elif selected_result_artifact_pointer not in (None, ""):
        pointer = {"path": str(selected_result_artifact_pointer), "exists": False}
    else:
        pointer = {}

    pointer_path = _text(pointer.get("path"))
    test_id = _text(selected_test_id or pointer.get("test_id"))
    if not test_id and pointer_path:
        test_id = Path(pointer_path).stem
    segment_id = _text(selected_segment_id or pointer.get("segment_id") or "all")
    time_window = dict(selected_time_window or pointer.get("time_window") or {})
    if not time_window:
        time_window = {"mode": "full_artifact", "start_s": None, "end_s": None}

    compare_payload = dict(compare_contract or {})
    compare_hash = _text(compare_payload.get("compare_contract_hash"))
    run_contract_hash = (context.run_contract_hash or context.selected_run_contract_hash) if context else ""
    best_ref = _text(
        selected_best_candidate_ref
        or pointer.get("selected_best_candidate_ref")
        or (context.selected_best_candidate_ref if context else "")
    )

    blocking: list[str] = [str(item) for item in extra_blocking_states if str(item).strip()]
    warnings: list[str] = [str(item) for item in extra_warnings if str(item).strip()]
    if context is None:
        blocking.append("missing selected run context")
    else:
        for field_name, field_value in (
            ("run_id", context.run_id),
            ("run_contract_hash", run_contract_hash),
            ("objective_contract_hash", context.objective_contract_hash),
            ("suite_snapshot_hash", context.suite_snapshot_hash),
        ):
            if not _text(field_value):
                blocking.append(f"missing {field_name}")
    if not pointer_path:
        blocking.append("missing selected result artifact pointer")
    elif pointer.get("exists") is False:
        blocking.append("selected result artifact pointer missing")
    if not test_id:
        blocking.append("missing selected_test_id")
    if not segment_id:
        blocking.append("missing selected_segment_id")
    if not best_ref:
        warnings.append("selected_best_candidate_ref missing")

    ready_state = "blocked" if blocking else ("warning" if warnings else "ready")
    payload: dict[str, Any] = {
        "schema": "analysis_to_animator_link_contract.v1",
        "contract_id": "ANALYSIS-TO-ANIMATOR-LINK-V17",
        "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
        "producer_workspace": ANALYSIS_WORKSPACE_ID,
        "consumer_workspace": ANIMATOR_WORKSPACE_ID,
        "created_at_utc": _text(now_text),
        "analysis_context_path": _text(analysis_context_path),
        "run_id": context.run_id if context else "",
        "run_contract_hash": run_contract_hash,
        "selected_test_id": test_id,
        "selected_segment_id": segment_id,
        "selected_time_window": time_window,
        "selected_best_candidate_ref": best_ref,
        "selected_result_artifact_pointer": pointer,
        "objective_contract_hash": context.objective_contract_hash if context else "",
        "suite_snapshot_hash": context.suite_snapshot_hash if context else "",
        "compare_contract_hash": compare_hash,
        "problem_hash": context.problem_hash if context else "",
        "hard_gate_key": context.hard_gate_key if context else "",
        "hard_gate_tolerance": context.hard_gate_tolerance if context else "",
        "active_baseline_hash": context.active_baseline_hash if context else "",
        "ready_state": ready_state,
        "blocking_states": tuple(dict.fromkeys(blocking)),
        "warnings": tuple(dict.fromkeys(warnings)),
        "rules": (
            "WS-ANIMATOR receives only explicit artifact pointers, not live runtime-state.",
            "One active run and one active test context are exported per handoff.",
        ),
    }
    payload["animator_link_contract_hash"] = _payload_hash(
        payload,
        hash_key="animator_link_contract_hash",
    )
    return payload


def infer_engineering_unit(metric_key: str) -> str:
    key = str(metric_key or "").strip()
    if not key:
        return ""
    if key.startswith("elas_"):
        return "dimensionless"
    if key in SYSTEM_INFLUENCE_UNIT_CATALOG:
        return SYSTEM_INFLUENCE_UNIT_CATALOG[key]
    if key.endswith("_deg"):
        return "deg"
    if key.endswith("_rad"):
        return "rad"
    if key.endswith("_mdot"):
        return "kg/s"
    if key.endswith("_Pa") or key.endswith("_pressure"):
        return "Pa"
    if key.startswith("corr") or "corr" in key:
        return "dimensionless"
    if key in {"score", "loss", "rmse", "sse"}:
        return "model-report units"
    return ""


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _iter_param_records(system_influence_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    params = system_influence_payload.get("params")
    if isinstance(params, list):
        return [dict(item) for item in params if isinstance(item, Mapping)]
    if isinstance(params, Mapping):
        records: list[dict[str, Any]] = []
        for key, value in params.items():
            rec = dict(value) if isinstance(value, Mapping) else {}
            rec.setdefault("param", str(key))
            records.append(rec)
        return records
    return []


def build_sensitivity_summary(
    system_influence_payload: Mapping[str, Any],
    *,
    top_k: int = 25,
) -> tuple[EngineeringSensitivityRow, ...]:
    rows: list[EngineeringSensitivityRow] = []
    for rec in _iter_param_records(system_influence_payload):
        param = str(rec.get("param") or rec.get("name") or "").strip()
        if not param:
            continue
        elasticities: dict[str, float] = {}
        for key, value in rec.items():
            if not str(key).startswith("elas_"):
                continue
            val = _safe_float(value, default=float("nan"))
            if np.isfinite(val):
                elasticities[str(key)] = float(val)
        strongest_metric = ""
        strongest_elasticity = 0.0
        if elasticities:
            strongest_metric, strongest_elasticity = max(
                elasticities.items(),
                key=lambda item: abs(float(item[1])),
            )
        score = _safe_float(rec.get("score"), default=sum(abs(v) for v in elasticities.values()))
        eps_rel = rec.get("eps_rel_used")
        eps_rel_used = None if eps_rel in (None, "") else _safe_float(eps_rel, default=0.0)
        rows.append(
            EngineeringSensitivityRow(
                param=param,
                group=str(rec.get("group") or "other"),
                score=float(score),
                status=str(rec.get("status") or "UNKNOWN"),
                eps_rel_used=eps_rel_used,
                strongest_metric=strongest_metric,
                strongest_elasticity=float(strongest_elasticity),
            )
        )
    rows.sort(key=lambda row: abs(float(row.score)), reverse=True)
    if top_k and top_k > 0:
        rows = rows[: int(top_k)]
    return tuple(rows)


def build_compare_influence_surface(
    corr: Any,
    feature_names: Sequence[str],
    target_names: Sequence[str],
    *,
    title: str = "Compare influence surface",
    feature_units: Mapping[str, str] | None = None,
    target_units: Mapping[str, str] | None = None,
    top_k: int = 20,
    source: str = "compare_influence",
) -> dict[str, Any]:
    matrix = np.asarray(corr, dtype=float)
    features = [str(item) for item in feature_names]
    targets = [str(item) for item in target_names]
    if matrix.ndim != 2:
        matrix = np.zeros((0, 0), dtype=float)
    shape_ok = matrix.shape == (len(features), len(targets))
    if not shape_ok:
        matrix = np.zeros((len(features), len(targets)), dtype=float)
        matrix[:] = np.nan

    f_units = dict(feature_units or {})
    t_units = dict(target_units or {})
    finite = matrix[np.isfinite(matrix)]
    ranked_features = rank_features_by_max_abs_corr(matrix, features) if features else []
    cells = [
        {
            "feature": feature,
            "target": target,
            "corr": float(value),
            "abs_corr": abs(float(value)),
            "feature_unit": f_units.get(feature, infer_engineering_unit(feature)),
            "target_unit": t_units.get(target, infer_engineering_unit(target)),
        }
        for feature, target, value in top_cells(matrix, features, targets, top_k=top_k)
    ]
    return {
        "schema": ENGINEERING_ANALYSIS_SCHEMA,
        "schema_version": ENGINEERING_ANALYSIS_SCHEMA_VERSION,
        "surface_type": "compare_influence",
        "source": str(source),
        "title": str(title),
        "axes": {
            "features": [
                {"key": name, "unit": f_units.get(name, infer_engineering_unit(name))}
                for name in features
            ],
            "targets": [
                {"key": name, "unit": t_units.get(name, infer_engineering_unit(name))}
                for name in targets
            ],
        },
        "ranked_features": list(ranked_features),
        "top_cells": cells,
        "diagnostics": {
            "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
            "shape_matches_axes": bool(shape_ok),
            "finite_cell_count": int(finite.size),
            "max_abs_corr": float(np.max(np.abs(finite))) if finite.size else 0.0,
            "top_k": int(top_k),
        },
    }


__all__ = [
    "ANALYSIS_CONTEXT_FILENAME",
    "ANALYSIS_TO_ANIMATOR_HANDOFF_ID",
    "ANALYSIS_WORKSPACE_ID",
    "ANIMATOR_LINK_CONTRACT_FILENAME",
    "ANIMATOR_WORKSPACE_ID",
    "ENGINEERING_ANALYSIS_CONSUMED_BY",
    "ENGINEERING_ANALYSIS_EVIDENCE_SCHEMA",
    "ENGINEERING_ANALYSIS_EVIDENCE_SCHEMA_VERSION",
    "ENGINEERING_ANALYSIS_HANDOFF_ID",
    "ENGINEERING_ANALYSIS_PRODUCED_BY",
    "ENGINEERING_ANALYSIS_SCHEMA",
    "ENGINEERING_ANALYSIS_SCHEMA_VERSION",
    "EngineeringAnalysisArtifact",
    "EngineeringAnalysisJobResult",
    "EngineeringAnalysisPipelineRow",
    "EngineeringAnalysisSnapshot",
    "EngineeringSensitivityRow",
    "SELECTED_RUN_CONSUMED_BY",
    "SELECTED_RUN_CONTRACT_FILENAME",
    "SELECTED_RUN_CONTRACT_SCHEMA_VERSION",
    "SELECTED_RUN_HANDOFF_ID",
    "SELECTED_RUN_PRODUCED_BY",
    "SelectedRunContext",
    "SelectedRunContractSnapshot",
    "SYSTEM_INFLUENCE_UNIT_CATALOG",
    "build_analysis_compare_contract",
    "build_analysis_to_animator_link_contract",
    "build_compare_influence_surface",
    "build_sensitivity_summary",
    "infer_engineering_unit",
    "selected_run_compare_ref",
    "selected_run_context_from_payload",
]
