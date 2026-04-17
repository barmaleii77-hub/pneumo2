from __future__ import annotations

"""Evidence manifest helpers for WS-DIAGNOSTICS SEND bundles."""

import fnmatch
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from pneumo_solver_ui.optimization_baseline_source import (
    compare_active_and_historical_baseline,
    describe_active_baseline_state,
)


EVIDENCE_MANIFEST_ARCNAME = "diagnostics/evidence_manifest.json"
EVIDENCE_MANIFEST_SIDECAR_NAME = "latest_evidence_manifest.json"
ANALYSIS_EVIDENCE_SIDECAR_NAME = "latest_analysis_evidence_manifest.json"
ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME = "workspace/exports/analysis_evidence_manifest.json"
ANALYSIS_EVIDENCE_FALLBACK_ARCNAME = "exports/analysis_evidence_manifest.json"
ANALYSIS_EVIDENCE_HANDOFF_ID = "HO-009"
ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME = "latest_engineering_analysis_evidence_manifest.json"
ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME = "analysis/engineering_analysis_evidence_manifest.json"
ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME = "workspace/exports/engineering_analysis_evidence_manifest.json"
GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME = "latest_geometry_reference_evidence.json"
GEOMETRY_REFERENCE_EVIDENCE_ARCNAME = "geometry/geometry_reference_evidence.json"
GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME = "workspace/exports/geometry_reference_evidence.json"
GEOMETRY_REFERENCE_EVIDENCE_FALLBACK_ARCNAME = "exports/geometry_reference_evidence.json"
GEOMETRY_REFERENCE_PRODUCER_EVIDENCE_OWNER = "producer_export"
GEOMETRY_REFERENCE_REQUIRED_PRODUCER_ARTIFACTS = (
    "workspace/_pointers/anim_latest.json or workspace/exports/anim_latest.json",
    "workspace/exports/anim_latest.npz",
    "workspace/exports/CYLINDER_PACKAGING_PASSPORT.json",
    "workspace/exports/geometry_acceptance_report.json",
)
GEOMETRY_REFERENCE_PRODUCER_NEXT_ACTION = (
    "Run producer/solver anim_latest export so NPZ meta.geometry/meta.packaging, "
    "CYLINDER_PACKAGING_PASSPORT.json and geometry_acceptance_report.json are written; "
    "Reference Center must not fabricate producer geometry evidence."
)
_ANALYSIS_CONTEXT_STATES = {"CURRENT", "HISTORICAL", "STALE", "MISSING"}
PB002_REQUIRED_EVIDENCE_IDS = frozenset({"BND-001", "BND-002", "BND-003", "BND-004", "BND-005", "BND-006"})
DEFAULT_FINALIZATION_ORDER = (
    "collect",
    "final_triage",
    "validation",
    "dashboard",
    "health",
    "evidence_manifest",
    "latest_zip_sha",
    "inspection_proof",
)

REQUIRED_PROVENANCE_FIELDS = (
    "python_executable",
    "python_prefix",
    "python_base_prefix",
    "venv_active",
    "preferred_cli_python",
    "effective_workspace",
)

EXPECTED_EVIDENCE: tuple[dict[str, Any], ...] = (
    {
        "evidence_id": "BND-001",
        "path_patterns": ("bundle/meta.json",),
        "required_when": "always",
        "release_blocking_if_missing": True,
        "hash_required": True,
        "expected_provenance_fields": REQUIRED_PROVENANCE_FIELDS,
        "notes": "Bundle meta and helper runtime provenance.",
    },
    {
        "evidence_id": "BND-002",
        "path_patterns": ("health/health_report.json",),
        "required_when": "always",
        "release_blocking_if_missing": True,
        "hash_required": False,
        "expected_provenance_fields": ("inspection_status", "geometry_acceptance", "bundle_freshness"),
        "notes": "Final health artifact after triage rewrite.",
    },
    {
        "evidence_id": "BND-003",
        "path_patterns": ("health/health_report.md",),
        "required_when": "always",
        "release_blocking_if_missing": True,
        "hash_required": False,
        "expected_provenance_fields": ("human-readable summary",),
        "notes": "Human-readable health summary.",
    },
    {
        "evidence_id": "BND-004",
        "path_patterns": ("triage/triage_report.json",),
        "required_when": "always",
        "release_blocking_if_missing": True,
        "hash_required": False,
        "expected_provenance_fields": ("triage_status", "error_classes", "freshness"),
        "notes": "Final triage artifact.",
    },
    {
        "evidence_id": "BND-005",
        "path_patterns": ("triage/triage_report.md",),
        "required_when": "always",
        "release_blocking_if_missing": True,
        "hash_required": False,
        "expected_provenance_fields": ("human-readable triage",),
        "notes": "Human-readable triage summary.",
    },
    {
        "evidence_id": "BND-006",
        "path_patterns": (EVIDENCE_MANIFEST_ARCNAME,),
        "required_when": "diagnostics bundle built",
        "release_blocking_if_missing": True,
        "hash_required": False,
        "expected_provenance_fields": ("evidence_manifest_hash", "selected_run_hash"),
        "notes": "Merged evidence manifest.",
    },
    {
        "evidence_id": "BND-007",
        "path_patterns": ("workspace/exports/ring_source_of_truth.json", "exports/ring_source_of_truth.json"),
        "required_when": "if scenario exists",
        "release_blocking_if_missing": True,
        "hash_required": "optional",
        "expected_provenance_fields": ("ring_source_hash", "segment_meta_hash"),
        "notes": "Canonical scenario source.",
    },
    {
        "evidence_id": "BND-008",
        "path_patterns": ("workspace/exports/segment_meta.json", "exports/segment_meta.json"),
        "required_when": "if scenario exists",
        "release_blocking_if_missing": True,
        "hash_required": "optional",
        "expected_provenance_fields": ("segment_id lineage",),
        "notes": "Segment metadata.",
    },
    {
        "evidence_id": "BND-009",
        "path_patterns": ("workspace/*validated_suite_snapshot.json", "suite/validated_suite_snapshot.json"),
        "required_when": "if baseline or optimization ran",
        "release_blocking_if_missing": True,
        "hash_required": "optional",
        "expected_provenance_fields": ("suite_snapshot_hash", "scenario_lineage_hash"),
        "notes": "Frozen validated suite snapshot.",
    },
    {
        "evidence_id": "BND-010",
        "path_patterns": ("workspace/*active_baseline_contract.json", "baseline/active_baseline_contract.json"),
        "required_when": "if baseline exists",
        "release_blocking_if_missing": True,
        "hash_required": "optional",
        "expected_provenance_fields": ("active_baseline_hash", "suite_snapshot_hash"),
        "notes": "Active baseline contract.",
    },
    {
        "evidence_id": "BND-020",
        "path_patterns": ("workspace/*baseline_history.jsonl", "baseline/baseline_history.jsonl"),
        "required_when": "if baseline exists",
        "release_blocking_if_missing": False,
        "hash_required": "optional",
        "expected_provenance_fields": ("history_id", "active_baseline_hash", "mismatch_state", "banner_state"),
        "notes": "Baseline history excerpt and active/historical mismatch evidence.",
    },
    {
        "evidence_id": "BND-011",
        "path_patterns": ("workspace/opt_runs/*objective_contract.json", "optimization/objective_contract.json"),
        "required_when": "if optimization exists",
        "release_blocking_if_missing": True,
        "hash_required": "optional",
        "expected_provenance_fields": ("objective_contract_hash", "hard_gate_key", "hard_gate_tolerance"),
        "notes": "Optimization objective contract.",
    },
    {
        "evidence_id": "BND-012",
        "path_patterns": ("workspace/opt_runs/*run_contract*.json", "optimization/run_contract*.json"),
        "required_when": "if optimization exists",
        "release_blocking_if_missing": True,
        "hash_required": "optional",
        "expected_provenance_fields": ("run_contract_hash", "scenario_lineage_hash"),
        "notes": "Selected or historical optimization run contract.",
    },
    {
        "evidence_id": "BND-013",
        "path_patterns": ("analysis/compare_contract*.json", "workspace/*compare_contract*.json"),
        "required_when": "if compare mode used",
        "release_blocking_if_missing": False,
        "hash_required": "optional",
        "expected_provenance_fields": ("compare_contract_hash",),
        "notes": "Explicit compare contract.",
    },
    {
        "evidence_id": "BND-021",
        "path_patterns": (
            ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME,
            ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME,
        ),
        "required_when": "if engineering analysis used",
        "release_blocking_if_missing": False,
        "hash_required": "optional",
        "expected_provenance_fields": ("evidence_manifest_hash", "sensitivity_summary", "unit_catalog"),
        "notes": "Engineering analysis, calibration, influence and sensitivity evidence manifest.",
    },
    {
        "evidence_id": "BND-014",
        "path_patterns": ("animator/capture_provenance*.json", "workspace/exports/*capture*provenance*.json"),
        "required_when": "if capture/export used",
        "release_blocking_if_missing": False,
        "hash_required": "optional",
        "expected_provenance_fields": ("capture_export_hash", "truth_warning"),
        "notes": "Animator capture provenance.",
    },
    {
        "evidence_id": "BND-015",
        "path_patterns": ("perf/browser_perf_trace*.json", "workspace/exports/browser_perf_trace*.json"),
        "required_when": "if perf acceptance claimed",
        "release_blocking_if_missing": False,
        "hash_required": "optional",
        "expected_provenance_fields": ("trace session id",),
        "notes": "Measured browser trace evidence.",
    },
    {
        "evidence_id": "BND-016",
        "path_patterns": ("perf/viewport_gating*.json", "workspace/exports/viewport_gating*.json"),
        "required_when": "if viewport gating claimed",
        "release_blocking_if_missing": False,
        "hash_required": "optional",
        "expected_provenance_fields": ("gating mode", "hidden surfaces"),
        "notes": "Hidden surface gating evidence.",
    },
    {
        "evidence_id": "BND-017",
        "path_patterns": ("perf/animator_frame_budget*.json", "workspace/exports/animator_frame_budget*.json"),
        "required_when": "if animator perf claimed",
        "release_blocking_if_missing": False,
        "hash_required": "optional",
        "expected_provenance_fields": ("frame budget stats",),
        "notes": "Animator performance evidence.",
    },
    {
        "evidence_id": "BND-018",
        "path_patterns": (
            GEOMETRY_REFERENCE_EVIDENCE_ARCNAME,
            "geometry/geometry_acceptance*.json",
            GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME,
            "workspace/exports/*geometry_acceptance*.json",
        ),
        "required_when": "if graphics truth used",
        "release_blocking_if_missing": True,
        "hash_required": "optional",
        "expected_provenance_fields": (
            "artifact_freshness_status",
            "artifact_freshness_relation",
            "geometry_acceptance_gate",
            "road_width_status",
            "packaging_contract_hash",
            "producer_artifact_status",
            "component_passport",
        ),
        "notes": "Geometry acceptance and Reference Center handoff evidence.",
    },
    {
        "evidence_id": "BND-019",
        "path_patterns": ("runtime/windows_runtime_proof*.json", "workspace/exports/windows_runtime_proof*.json"),
        "required_when": "if Windows runtime acceptance claimed",
        "release_blocking_if_missing": False,
        "hash_required": "optional",
        "expected_provenance_fields": ("snap", "DPI", "second monitor", "path budget"),
        "notes": "Windows desktop shell acceptance proof.",
    },
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def classify_collection_mode(trigger: Any) -> str:
    text = str(trigger or "").strip().lower()
    if not text:
        return "manual"
    if "watchdog" in text:
        return "watchdog"
    crash_tokens = ("crash", "excepthook", "unraisablehook", "fatal", "threading.")
    if any(token in text for token in crash_tokens):
        return "crash"
    if "exit" in text or "atexit" in text:
        return "exit"
    return "manual"


def helper_runtime_provenance(meta: Mapping[str, Any]) -> Dict[str, Any]:
    effective_workspace = (
        meta.get("effective_workspace")
        or meta.get("effective_workspace_path")
        or meta.get("repo_local_workspace_path")
        or ""
    )
    out = {
        "python_executable": str(meta.get("python_executable") or ""),
        "python_prefix": str(meta.get("python_prefix") or ""),
        "python_base_prefix": str(meta.get("python_base_prefix") or ""),
        "venv_active": bool(meta.get("venv_active")),
        "preferred_cli_python": str(meta.get("preferred_cli_python") or ""),
        "effective_workspace": str(effective_workspace or ""),
        "python_executable_current": str(meta.get("python_executable_current") or ""),
        "python_runtime_source": str(meta.get("python_runtime_source") or ""),
        "effective_workspace_source": str(meta.get("effective_workspace_source") or ""),
    }
    out["missing_fields"] = [
        field for field in REQUIRED_PROVENANCE_FIELDS if out.get(field) in (None, "", [], {})
    ]
    out["provenance_complete"] = not out["missing_fields"]
    return out


def _load_json_from_zip(zf: Any, name: str) -> Dict[str, Any]:
    try:
        obj = json.loads(zf.read(name).decode("utf-8", errors="replace"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def _load_json_from_file(path: Path) -> tuple[Dict[str, Any], str]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {}, (
            f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} manifest is not readable: "
            f"{type(exc).__name__}: {exc!s}"
        )
    if not isinstance(obj, dict):
        return {}, f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} manifest is not a JSON object."
    return dict(obj), ""


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalize_analysis_context_state(value: Any) -> str:
    state = str(value or "").strip().upper()
    return state if state in _ANALYSIS_CONTEXT_STATES else "MISSING"


def _analysis_effective_workspace_from_meta(meta: Mapping[str, Any]) -> Path | None:
    for key in (
        "effective_workspace",
        "effective_workspace_path",
        "repo_local_workspace_path",
    ):
        raw = str(meta.get(key) or "").strip()
        if not raw:
            continue
        try:
            return Path(raw).expanduser().resolve()
        except Exception:
            return Path(raw).expanduser()
    return None


def _analysis_manifest_source(
    *,
    zip_path: Path | str,
    name_set: set[str],
    meta: Mapping[str, Any],
    json_sources: Mapping[str, Dict[str, Any]],
) -> tuple[Dict[str, Any], str, list[str]]:
    warnings: list[str] = []
    try:
        sidecar = Path(zip_path).expanduser().resolve().parent / ANALYSIS_EVIDENCE_SIDECAR_NAME
    except Exception:
        sidecar = Path(str(zip_path)).parent / ANALYSIS_EVIDENCE_SIDECAR_NAME
    if sidecar.exists():
        payload, warning = _load_json_from_file(sidecar)
        if warning:
            warnings.append(warning)
        return payload, str(sidecar), warnings

    for arcname in (ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME, ANALYSIS_EVIDENCE_FALLBACK_ARCNAME):
        if arcname in json_sources:
            return dict(json_sources.get(arcname) or {}), arcname, warnings
        if arcname in name_set:
            warnings.append(
                f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} manifest is present but not valid JSON: "
                f"{arcname}"
            )
            return {}, arcname, warnings

    workspace = _analysis_effective_workspace_from_meta(meta)
    if workspace is not None:
        manifest_path = workspace / "exports" / "analysis_evidence_manifest.json"
        if manifest_path.exists():
            payload, warning = _load_json_from_file(manifest_path)
            if warning:
                warnings.append(warning)
            return payload, str(manifest_path), warnings

    return {}, "", warnings


def summarize_analysis_evidence_manifest(
    payload: Mapping[str, Any] | None,
    *,
    source_path: str = "",
    read_warnings: Iterable[str] = (),
) -> Dict[str, Any]:
    obj = dict(payload or {})
    source = str(source_path or "").strip()
    warnings = [str(item).strip() for item in read_warnings if str(item).strip()]
    handoff_id = str(obj.get("handoff_id") or ANALYSIS_EVIDENCE_HANDOFF_ID).strip() or ANALYSIS_EVIDENCE_HANDOFF_ID

    selected_artifacts = obj.get("selected_artifact_list") or []
    if not isinstance(selected_artifacts, list):
        selected_artifacts = []
    mismatch_summary = _mapping(obj.get("mismatch_summary"))
    result_context = _mapping(obj.get("result_context"))
    selected_context = _mapping(result_context.get("selected"))
    mismatches = mismatch_summary.get("mismatches") or []
    if not isinstance(mismatches, list):
        mismatches = []

    evidence_hash = str(obj.get("evidence_manifest_hash") or "").strip()
    analysis_context_status = str(
        selected_context.get("analysis_context_status")
        or result_context.get("analysis_context_status")
        or obj.get("analysis_context_status")
        or ""
    ).strip().upper()
    context_state = _normalize_analysis_context_state(
        result_context.get("state") or mismatch_summary.get("state")
    )
    status = "READY"

    if not source:
        status = "MISSING"
        context_state = "MISSING"
        warnings.append(
            f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} missing; "
            "export evidence manifest from Results Center before SEND."
        )
    else:
        schema = str(obj.get("schema") or "").strip()
        if not obj:
            warnings.append(
                f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} manifest is empty or unreadable."
            )
        if schema != "desktop_results_evidence_manifest":
            warnings.append(
                f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} has unexpected schema: {schema or 'missing'}."
            )
        if handoff_id != ANALYSIS_EVIDENCE_HANDOFF_ID:
            warnings.append(
                f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} has unexpected handoff_id: {handoff_id}."
            )
        if not evidence_hash:
            warnings.append(
                f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} is missing evidence_manifest_hash."
            )
        if context_state == "MISSING":
            warnings.append(
                f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} context state is missing."
            )
        elif context_state in {"HISTORICAL", "STALE"}:
            warnings.append(
                f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} context is {context_state}."
            )
        if mismatches:
            warnings.append(
                f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} reports {len(mismatches)} context mismatch(es)."
            )
        if analysis_context_status in {"MISSING", "BLOCKED", "INVALID"}:
            warnings.append(
                f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} reports HO-008 analysis context is {analysis_context_status}."
            )
        elif analysis_context_status == "DEGRADED":
            warnings.append(
                f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} reports HO-008 analysis context is DEGRADED."
            )
        if warnings:
            status = "WARN"

    return {
        "handoff_id": handoff_id,
        "status": status,
        "source_path": source,
        "evidence_manifest_hash": evidence_hash,
        "result_context_state": context_state,
        "analysis_context_status": analysis_context_status,
        "animator_link_contract_hash": str(selected_context.get("animator_link_contract_hash") or "").strip(),
        "selected_run_contract_hash": str(selected_context.get("selected_run_contract_hash") or "").strip(),
        "selected_test_id": str(selected_context.get("selected_test_id") or "").strip(),
        "selected_npz_path": str(selected_context.get("selected_npz_path") or "").strip(),
        "capture_export_manifest_handoff_id": str(
            selected_context.get("capture_export_manifest_handoff_id") or ""
        ).strip(),
        "capture_hash": str(selected_context.get("capture_hash") or "").strip(),
        "truth_mode_hash": str(selected_context.get("truth_mode_hash") or "").strip(),
        "run_id": str(obj.get("run_id") or "").strip(),
        "run_contract_hash": str(obj.get("run_contract_hash") or "").strip(),
        "compare_contract_id": str(obj.get("compare_contract_id") or obj.get("compare_contract_hash") or "").strip(),
        "artifact_count": len(selected_artifacts),
        "mismatch_count": len(mismatches),
        "warnings": list(dict.fromkeys(warnings)),
    }


def analysis_handoff_for_evidence_manifest(
    *,
    zip_path: Path | str,
    name_set: set[str],
    meta: Mapping[str, Any],
    json_sources: Mapping[str, Dict[str, Any]],
) -> Dict[str, Any]:
    payload, source_path, read_warnings = _analysis_manifest_source(
        zip_path=zip_path,
        name_set=name_set,
        meta=meta,
        json_sources=json_sources,
    )
    return summarize_analysis_evidence_manifest(
        payload,
        source_path=source_path,
        read_warnings=read_warnings,
    )


def _load_geometry_reference_json_from_file(path: Path) -> tuple[Dict[str, Any], str]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {}, f"Geometry reference evidence is not readable: {type(exc).__name__}: {exc!s}"
    if not isinstance(obj, dict):
        return {}, "Geometry reference evidence is not a JSON object."
    return dict(obj), ""


def _geometry_reference_manifest_source(
    *,
    zip_path: Path | str,
    name_set: set[str],
    meta: Mapping[str, Any],
    json_sources: Mapping[str, Dict[str, Any]],
) -> tuple[Dict[str, Any], str, list[str]]:
    warnings: list[str] = []
    try:
        sidecar = Path(zip_path).expanduser().resolve().parent / GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME
    except Exception:
        sidecar = Path(str(zip_path)).parent / GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME
    if sidecar.exists():
        payload, warning = _load_geometry_reference_json_from_file(sidecar)
        if warning:
            warnings.append(warning)
        return payload, str(sidecar), warnings

    for arcname in (
        GEOMETRY_REFERENCE_EVIDENCE_ARCNAME,
        GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME,
        GEOMETRY_REFERENCE_EVIDENCE_FALLBACK_ARCNAME,
    ):
        if arcname in json_sources:
            return dict(json_sources.get(arcname) or {}), arcname, warnings
        if arcname in name_set:
            warnings.append(f"Geometry reference evidence is present but not valid JSON: {arcname}")
            return {}, arcname, warnings

    workspace = _analysis_effective_workspace_from_meta(meta)
    if workspace is not None:
        manifest_path = workspace / "exports" / Path(GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME).name
        if manifest_path.exists():
            payload, warning = _load_geometry_reference_json_from_file(manifest_path)
            if warning:
                warnings.append(warning)
            return payload, str(manifest_path), warnings

    return {}, "", warnings


def summarize_geometry_reference_evidence(
    payload: Mapping[str, Any] | None,
    *,
    source_path: str = "",
    read_warnings: Iterable[str] = (),
) -> Dict[str, Any]:
    obj = dict(payload or {})
    source = str(source_path or "").strip()
    warnings = [str(item).strip() for item in read_warnings if str(item).strip()]
    schema = str(obj.get("schema") or "").strip()
    evidence_missing = [
        str(item).strip()
        for item in (obj.get("evidence_missing") or [])
        if str(item).strip()
    ]
    artifact_status = str(obj.get("artifact_status") or "").strip().lower() or "missing"
    freshness_status = str(obj.get("artifact_freshness_status") or "").strip().lower() or artifact_status
    freshness_relation = str(obj.get("artifact_freshness_relation") or "").strip().lower() or "unknown"
    road_width_status = str(obj.get("road_width_status") or "").strip().lower() or "missing"
    packaging_mismatch = str(obj.get("packaging_mismatch_status") or "").strip().lower() or "missing"
    acceptance_gate = str(obj.get("geometry_acceptance_gate") or "").strip().upper() or "MISSING"
    producer_evidence_owner = (
        str(obj.get("producer_evidence_owner") or "").strip() or GEOMETRY_REFERENCE_PRODUCER_EVIDENCE_OWNER
    )
    producer_required_artifacts = [
        str(item).strip()
        for item in (obj.get("producer_required_artifacts") or GEOMETRY_REFERENCE_REQUIRED_PRODUCER_ARTIFACTS)
        if str(item).strip()
    ]
    producer_next_action = str(obj.get("producer_next_action") or GEOMETRY_REFERENCE_PRODUCER_NEXT_ACTION).strip()
    consumer_may_fabricate_geometry = bool(obj.get("consumer_may_fabricate_geometry", False))
    raw_producer_artifact_status = str(obj.get("producer_artifact_status") or "").strip().lower()
    if raw_producer_artifact_status:
        producer_artifact_status = raw_producer_artifact_status
    elif (
        artifact_status not in {"missing", "stale"}
        and freshness_status not in {"missing", "stale"}
        and road_width_status != "missing"
        and packaging_mismatch not in {"missing", "mismatch"}
        and acceptance_gate == "PASS"
    ):
        producer_artifact_status = "ready"
    elif artifact_status == "stale" or freshness_status == "stale":
        producer_artifact_status = "stale"
    elif artifact_status == "missing" or freshness_status == "missing":
        producer_artifact_status = "missing"
    else:
        producer_artifact_status = "partial"

    def _safe_int_field(key: str) -> int:
        try:
            return int(obj.get(key) or 0)
        except Exception:
            return 0

    if not source:
        return {
            "status": "MISSING",
            "source_path": "",
            "schema": schema,
            "artifact_status": "missing",
            "artifact_freshness_status": "missing",
            "artifact_freshness_relation": "missing",
            "artifact_freshness_reason": "",
            "artifact_source_label": "",
            "road_width_status": "missing",
            "road_width_source": "",
            "packaging_status": "missing",
            "packaging_mismatch_status": "missing",
            "packaging_contract_hash": "",
            "geometry_acceptance_gate": "MISSING",
            "producer_artifact_status": "missing",
            "producer_evidence_owner": GEOMETRY_REFERENCE_PRODUCER_EVIDENCE_OWNER,
            "producer_required_artifacts": list(GEOMETRY_REFERENCE_REQUIRED_PRODUCER_ARTIFACTS),
            "producer_next_action": GEOMETRY_REFERENCE_PRODUCER_NEXT_ACTION,
            "consumer_may_fabricate_geometry": False,
            "component_passport_components": 0,
            "component_passport_needs_data": 0,
            "evidence_missing": [],
            "warnings": [],
        }

    if schema != "geometry_reference_evidence.v1":
        warnings.append(f"Geometry reference evidence has unexpected schema: {schema or 'missing'}.")
    if bool(obj.get("producer_owned")):
        warnings.append("Geometry reference evidence claims producer ownership; Reference Center must remain a reader.")
    if obj.get("does_not_render_animator_meshes") is False:
        warnings.append("Geometry reference evidence claims animator mesh rendering; this adapter must stay read-only.")
    if consumer_may_fabricate_geometry:
        warnings.append("Geometry reference evidence allows consumer geometry fabrication; producer export must own it.")
    if producer_artifact_status in {"missing", "partial", "stale"}:
        warnings.append(
            f"Geometry reference producer artifact handoff is {producer_artifact_status}: {producer_next_action}"
        )
    if evidence_missing:
        warnings.append(f"Geometry reference evidence reports missing item(s): {', '.join(evidence_missing)}.")
    if artifact_status in {"missing", "stale"}:
        warnings.append(f"Geometry reference artifact context is {artifact_status}.")
    if freshness_status in {"missing", "stale"}:
        warnings.append(f"Geometry reference artifact freshness is {freshness_status}.")
    if freshness_relation in {"differs_from_latest", "selected_without_latest", "selected_unavailable"}:
        warnings.append(f"Geometry reference selected/latest relation is {freshness_relation}.")
    if road_width_status == "missing":
        warnings.append("Geometry reference road_width_m evidence is missing; GAP-008 remains open.")
    if packaging_mismatch in {"missing", "mismatch"}:
        warnings.append(f"Geometry reference packaging passport state is {packaging_mismatch}.")
    if acceptance_gate != "PASS":
        warnings.append(f"Geometry acceptance gate is {acceptance_gate}.")

    return {
        "status": "WARN" if warnings else "READY",
        "source_path": source,
        "schema": schema,
        "artifact_status": artifact_status,
        "artifact_freshness_status": freshness_status,
        "artifact_freshness_relation": freshness_relation,
        "artifact_freshness_reason": str(obj.get("artifact_freshness_reason") or ""),
        "latest_artifact_status": str(obj.get("latest_artifact_status") or ""),
        "artifact_source_label": str(obj.get("artifact_source_label") or ""),
        "road_width_status": road_width_status,
        "road_width_source": str(obj.get("road_width_source") or ""),
        "packaging_status": str(obj.get("packaging_status") or ""),
        "packaging_mismatch_status": packaging_mismatch,
        "packaging_contract_hash": str(obj.get("packaging_contract_hash") or ""),
        "geometry_acceptance_gate": acceptance_gate,
        "producer_artifact_status": producer_artifact_status,
        "producer_evidence_owner": producer_evidence_owner,
        "producer_required_artifacts": list(dict.fromkeys(producer_required_artifacts)),
        "producer_next_action": producer_next_action,
        "consumer_may_fabricate_geometry": consumer_may_fabricate_geometry,
        "component_passport_components": _safe_int_field("component_passport_components"),
        "component_passport_needs_data": _safe_int_field("component_passport_needs_data"),
        "evidence_missing": list(dict.fromkeys(evidence_missing)),
        "warnings": list(dict.fromkeys(warnings)),
    }


def geometry_reference_handoff_for_evidence_manifest(
    *,
    zip_path: Path | str,
    name_set: set[str],
    meta: Mapping[str, Any],
    json_sources: Mapping[str, Dict[str, Any]],
) -> Dict[str, Any]:
    payload, source_path, read_warnings = _geometry_reference_manifest_source(
        zip_path=zip_path,
        name_set=name_set,
        meta=meta,
        json_sources=json_sources,
    )
    return summarize_geometry_reference_evidence(
        payload,
        source_path=source_path,
        read_warnings=read_warnings,
    )


def _match_names(name_set: set[str], patterns: Sequence[str], planned_paths: set[str]) -> tuple[list[str], list[str]]:
    present: list[str] = []
    planned: list[str] = []
    for pattern in patterns:
        if pattern in planned_paths:
            planned.append(pattern)
        for name in sorted(name_set):
            if fnmatch.fnmatchcase(name, pattern):
                present.append(name)
    return sorted(set(present)), sorted(set(planned))


def _has_any(name_set: set[str], *patterns: str) -> bool:
    for pattern in patterns:
        for name in name_set:
            if fnmatch.fnmatchcase(name, pattern):
                return True
    return False


def _anim_summary_from_sources(name_set: set[str], json_by_name: Mapping[str, Dict[str, Any]]) -> Dict[str, Any]:
    diag = json_by_name.get("triage/latest_anim_pointer_diagnostics.json") or {}
    local = json_by_name.get("workspace/exports/anim_latest.json") or {}
    global_ptr = json_by_name.get("workspace/_pointers/anim_latest.json") or {}
    for obj in (diag, local, global_ptr):
        if obj:
            return dict(obj)
    if _has_any(name_set, "workspace/exports/anim_latest.npz"):
        return {"anim_latest_available": True}
    return {}


def _first_json_source(
    json_by_name: Mapping[str, Dict[str, Any]],
    *patterns: str,
) -> tuple[str, dict[str, Any]]:
    for name in sorted(json_by_name):
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns):
            return name, dict(json_by_name.get(name) or {})
    return "", {}


def _baseline_summary_from_sources(
    name_set: set[str],
    json_by_name: Mapping[str, Dict[str, Any]],
) -> Dict[str, Any]:
    active_name, active = _first_json_source(
        json_by_name,
        "workspace/*active_baseline_contract.json",
        "baseline/active_baseline_contract.json",
    )
    suite_name, suite = _first_json_source(
        json_by_name,
        "workspace/*validated_suite_snapshot.json",
        "suite/validated_suite_snapshot.json",
    )
    history_name, history_payload = _first_json_source(
        json_by_name,
        "workspace/*baseline_history.jsonl",
        "baseline/baseline_history.jsonl",
    )
    history_rows = [
        dict(row)
        for row in (history_payload.get("rows") or [])
        if isinstance(row, dict)
    ][:5]
    upstream = dict(suite.get("upstream_refs") or {})
    inputs = dict(upstream.get("inputs") or {})
    ring = dict(upstream.get("ring") or {})
    state = describe_active_baseline_state(
        active if active else None,
        current_suite_snapshot_hash=str(suite.get("suite_snapshot_hash") or ""),
        current_inputs_snapshot_hash=str(inputs.get("snapshot_hash") or ""),
        current_ring_source_hash=str(ring.get("source_hash") or ""),
    )
    mismatch_rows: list[dict[str, Any]] = []
    for row in history_rows:
        compare = compare_active_and_historical_baseline(active if active else None, row)
        if str(compare.get("state") or "") in {"historical_mismatch", "historical_same_context"}:
            mismatch_rows.append(
                {
                    "history_id": str(row.get("history_id") or ""),
                    "state": str(compare.get("state") or ""),
                    "mismatch_fields": list(compare.get("mismatch_fields") or ()),
                    "banner_id": str(compare.get("banner_id") or ""),
                    "banner": str(compare.get("banner") or ""),
                }
            )
    baseline_exists = _has_any(
        name_set,
        "workspace/*active_baseline_contract.json",
        "baseline/active_baseline_contract.json",
        "workspace/*baseline_history.jsonl",
        "baseline/baseline_history.jsonl",
        "workspace/baselines/*",
    )
    return {
        "schema": "baseline_center_evidence_from_bundle",
        "schema_version": "1.0.0",
        "baseline_exists": bool(baseline_exists),
        "active_contract_path": active_name,
        "validated_suite_snapshot_path": suite_name,
        "history_path": history_name,
        "active_baseline_hash": str(active.get("active_baseline_hash") or ""),
        "suite_snapshot_hash": str(active.get("suite_snapshot_hash") or suite.get("suite_snapshot_hash") or ""),
        "inputs_snapshot_hash": str(active.get("inputs_snapshot_hash") or inputs.get("snapshot_hash") or ""),
        "ring_source_hash": str(active.get("ring_source_hash") or ring.get("source_hash") or ""),
        "policy_mode": str(dict(active.get("policy") or {}).get("mode") or ""),
        "source_run_dir": str(dict(active.get("baseline") or {}).get("source_run_dir") or ""),
        "created_at_utc": str(active.get("created_at_utc") or ""),
        "banner_state": {
            "state": str(state.get("state") or ""),
            "banner_id": str(state.get("banner_id") or ""),
            "banner": str(state.get("banner") or ""),
            "stale_reasons": list(state.get("stale_reasons") or ()),
            "optimizer_baseline_can_consume": bool(state.get("optimizer_can_consume", False)),
        },
        "mismatch_state": {
            "has_mismatch": bool(mismatch_rows),
            "rows": mismatch_rows,
        },
        "history_excerpt": history_rows,
        "silent_rebinding_allowed": False,
    }


def _required_for_row(
    row: Mapping[str, Any],
    *,
    name_set: set[str],
    anim: Mapping[str, Any],
) -> tuple[bool, str]:
    required_when = str(row.get("required_when") or "").strip().lower()
    evidence_id = str(row.get("evidence_id") or "")
    if required_when in {"always", "diagnostics bundle built"}:
        return True, required_when

    scenario_exists = bool(
        anim.get("scenario_kind")
        or anim.get("scenario_json")
        or (isinstance(anim.get("anim_latest_meta"), dict) and (
            anim.get("anim_latest_meta", {}).get("scenario_kind")
            or anim.get("anim_latest_meta", {}).get("scenario_json")
        ))
        or _has_any(name_set, "workspace/exports/scenario*.json", "workspace/exports/road*.csv")
    )
    opt_placeholder_names = {"keep.txt", "placeholder.txt", "_EMPTY_OR_MISSING.txt"}
    optimization_exists = (
        _has_any(
            name_set,
            "dist_runs/*",
            "optimization/objective_contract.json",
            "optimization/run_contract*.json",
        )
        or any(
            name.startswith("workspace/opt_runs/")
            and Path(name).name not in opt_placeholder_names
            for name in name_set
        )
    )
    baseline_exists = _has_any(
        name_set,
        "baseline/active_baseline_contract.json",
        "workspace/*active_baseline_contract.json",
        "workspace/baselines/*",
    )
    compare_used = _has_any(name_set, "analysis/compare_contract*.json", "workspace/*compare_contract*.json")
    engineering_analysis_used = _has_any(
        name_set,
        ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME,
        ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME,
    )
    anim_export_used = bool(
        anim.get("anim_latest_available")
        or anim.get("available")
        or anim.get("visual_cache_token")
        or anim.get("anim_latest_visual_cache_token")
        or _has_any(name_set, "workspace/exports/anim_latest.npz", "workspace/exports/anim_latest.json")
    )
    perf_claimed = bool(
        anim.get("browser_perf_evidence_status") == "trace_bundle_ready"
        or _has_any(name_set, "workspace/exports/browser_perf*.json", "perf/browser_perf*.json")
    )
    viewport_claimed = _has_any(name_set, "workspace/exports/viewport_gating*.json", "perf/viewport_gating*.json")
    animator_perf_claimed = _has_any(
        name_set,
        "workspace/exports/animator_frame_budget*.json",
        "perf/animator_frame_budget*.json",
    )
    windows_runtime_claimed = _has_any(
        name_set,
        "workspace/exports/windows_runtime_proof*.json",
        "runtime/windows_runtime_proof*.json",
        "workspace/exports/windows_runtime_claim*.json",
        "runtime/windows_runtime_claim*.json",
    )

    if evidence_id in {"BND-007", "BND-008"}:
        return scenario_exists, "scenario_exists" if scenario_exists else "no scenario evidence detected"
    if evidence_id == "BND-009":
        required = baseline_exists or optimization_exists
        return required, "baseline_or_optimization_exists" if required else "no baseline/optimization evidence detected"
    if evidence_id in {"BND-010", "BND-020"}:
        return baseline_exists, "baseline_exists" if baseline_exists else "no baseline evidence detected"
    if evidence_id in {"BND-011", "BND-012"}:
        return optimization_exists, "optimization_exists" if optimization_exists else "no optimization evidence detected"
    if evidence_id == "BND-013":
        return compare_used, "compare_used" if compare_used else "no compare evidence detected"
    if evidence_id == "BND-021":
        return (
            engineering_analysis_used,
            "engineering_analysis_used" if engineering_analysis_used else "no engineering analysis evidence detected",
        )
    if evidence_id == "BND-014":
        return anim_export_used, "anim_export_used" if anim_export_used else "no animator export evidence detected"
    if evidence_id == "BND-015":
        return perf_claimed, "perf_claimed" if perf_claimed else "no perf acceptance claim detected"
    if evidence_id == "BND-016":
        return viewport_claimed, "viewport_claimed" if viewport_claimed else "no viewport gating claim detected"
    if evidence_id == "BND-017":
        return animator_perf_claimed, "animator_perf_claimed" if animator_perf_claimed else "no animator perf claim detected"
    if evidence_id == "BND-018":
        return anim_export_used, "graphics_truth_used" if anim_export_used else "no graphics truth evidence detected"
    if evidence_id == "BND-019":
        return (
            windows_runtime_claimed,
            "windows_runtime_claimed" if windows_runtime_claimed else "no Windows runtime acceptance claim detected",
        )
    return False, "not_applicable"


def _sha_for_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    raw = json.dumps(list(rows), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path | str) -> str:
    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return ""
        digest = hashlib.sha256()
        with p.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return ""


def _bundle_content_summary(
    *,
    name_set: set[str],
    planned_paths: set[str],
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    mandatory = {
        "meta": ("bundle/meta.json",),
        "triage": ("triage/triage_report.json", "triage/triage_report.md"),
        "health": ("health/health_report.json", "health/health_report.md"),
        "validation": ("validation/validation_report.json", "validation/validation_report.md"),
        "manifest": (EVIDENCE_MANIFEST_ARCNAME,),
    }
    classes: list[dict[str, Any]] = []
    for class_name, patterns in mandatory.items():
        present = sorted(
            name
            for name in name_set
            if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)
        )
        planned = sorted(
            pattern
            for pattern in patterns
            if pattern in planned_paths
        )
        status = "present" if present else ("planned_by_finalizer" if planned else "missing")
        classes.append(
            {
                "class": class_name,
                "required": True,
                "status": status,
                "path_patterns": list(patterns),
                "present_paths": present,
                "planned_paths": planned,
            }
        )

    row_status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        row_status_counts[status] = int(row_status_counts.get(status, 0)) + 1

    return {
        "mandatory_classes": classes,
        "missing_mandatory_classes": [row["class"] for row in classes if row["status"] == "missing"],
        "evidence_status_counts": row_status_counts,
        "zip_entry_count": len(name_set),
    }


def build_evidence_manifest(
    *,
    zip_path: Path | str,
    names: Iterable[str],
    meta: Mapping[str, Any] | None = None,
    json_by_name: Mapping[str, Dict[str, Any]] | None = None,
    planned_paths: Iterable[str] = (),
    stage: str = "final",
    finalized_at: str | None = None,
    finalization_stage: str | None = None,
    finalization_order: Sequence[str] | None = None,
    zip_sha256: str | None = None,
) -> Dict[str, Any]:
    meta_dict = dict(meta or {})
    name_set = {str(name) for name in names}
    planned = {str(path) for path in planned_paths}
    json_sources = dict(json_by_name or {})
    anim = _anim_summary_from_sources(name_set, json_sources)
    baseline = _baseline_summary_from_sources(name_set, json_sources)
    runtime = helper_runtime_provenance(meta_dict)
    trigger = str(meta_dict.get("trigger") or meta_dict.get("tag") or "").strip() or "manual"
    rows: list[dict[str, Any]] = []

    for row in EXPECTED_EVIDENCE:
        patterns = tuple(str(p) for p in row.get("path_patterns") or ())
        present, planned_matches = _match_names(name_set, patterns, planned)
        required, required_reason = _required_for_row(row, name_set=name_set, anim=anim)
        if present:
            status = "present"
        elif planned_matches:
            status = "planned_by_finalizer"
        elif required:
            status = "missing"
        else:
            status = "not_applicable"
        missing_warning = ""
        if status == "missing":
            missing_warning = (
                f"Missing evidence {row.get('evidence_id')}: expected one of "
                f"{', '.join(patterns)} ({row.get('required_when')})."
            )
        rows.append(
            {
                "evidence_id": str(row.get("evidence_id") or ""),
                "path_patterns": list(patterns),
                "required_when": str(row.get("required_when") or ""),
                "required": bool(required),
                "required_reason": required_reason,
                "release_blocking_if_missing": bool(row.get("release_blocking_if_missing")),
                "hash_required": row.get("hash_required"),
                "expected_provenance_fields": list(row.get("expected_provenance_fields") or ()),
                "status": status,
                "present_paths": present,
                "planned_paths": planned_matches,
                "missing_warning": missing_warning,
                "notes": str(row.get("notes") or ""),
            }
        )

    missing_required = [
        row for row in rows if row["status"] == "missing" and row["release_blocking_if_missing"]
    ]
    missing_optional = [
        row for row in rows if row["status"] == "missing" and not row["release_blocking_if_missing"]
    ]
    pb002_missing_required = [
        row for row in missing_required if str(row.get("evidence_id") or "") in PB002_REQUIRED_EVIDENCE_IDS
    ]
    manifest_hash = _sha_for_rows(rows)
    content_summary = _bundle_content_summary(name_set=name_set, planned_paths=planned, rows=rows)
    zip_digest = str(zip_sha256 or "").strip() or _sha256_file(zip_path)
    final_stage = str(finalization_stage or stage or "final")
    analysis_handoff = analysis_handoff_for_evidence_manifest(
        zip_path=zip_path,
        name_set=name_set,
        meta=meta_dict,
        json_sources=json_sources,
    )
    geometry_reference_handoff = geometry_reference_handoff_for_evidence_manifest(
        zip_path=zip_path,
        name_set=name_set,
        meta=meta_dict,
        json_sources=json_sources,
    )
    payload = {
        "schema": "diagnostics_evidence_manifest",
        "schema_version": "1.0.0",
        "created_at": now_iso(),
        "finalized_at": str(finalized_at or now_iso()),
        "finalization_stage": final_stage,
        "finalization_order": list(finalization_order or DEFAULT_FINALIZATION_ORDER),
        "workspace": "WS-DIAGNOSTICS",
        "handoff_ids": ["HO-009", "HO-010"],
        "playbook_id": "PB-002",
        "release_gates": ["RGH-006", "RGH-007", "RGH-016"],
        "zip_path": str(Path(zip_path)),
        "zip_name": Path(str(zip_path)).name,
        "zip_sha256": zip_digest,
        "zip_sha256_scope": "zip bytes at evidence manifest build time",
        "stage": str(stage or "final"),
        "trigger": trigger,
        "collection_mode": classify_collection_mode(trigger),
        "runtime_provenance": runtime,
        "helper_runtime_provenance": runtime,
        "baseline_center_evidence": baseline,
        "evidence_manifest_hash": manifest_hash,
        "analysis_handoff": analysis_handoff,
        "geometry_reference_handoff": geometry_reference_handoff,
        "bundle_contents_summary": content_summary,
        "evidence_classes": rows,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "missing_required_count": len(missing_required),
        "missing_optional_count": len(missing_optional),
        "pb002_missing_required": pb002_missing_required,
        "pb002_missing_required_count": len(pb002_missing_required),
        "missing_warnings": [],
        "source_policy": "adapters/evidence only; no domain calculations changed",
    }
    payload["missing_warnings"] = evidence_manifest_warnings(payload)
    return payload


def load_evidence_manifest_from_zip(zf: Any) -> Dict[str, Any]:
    return _load_json_from_zip(zf, EVIDENCE_MANIFEST_ARCNAME)


def evidence_manifest_warnings(manifest: Mapping[str, Any] | None) -> List[str]:
    obj = dict(manifest or {})
    rows = obj.get("evidence_classes") or []
    warnings: list[str] = []
    row_status_by_id: dict[str, str] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            evidence_id = str(row.get("evidence_id") or "")
            if evidence_id:
                row_status_by_id[evidence_id] = str(row.get("status") or "")
            msg = str(row.get("missing_warning") or "").strip()
            if msg:
                warnings.append(msg)

    analysis_handoff = obj.get("analysis_handoff")
    if isinstance(analysis_handoff, Mapping):
        for item in analysis_handoff.get("warnings") or []:
            msg = str(item or "").strip()
            if msg:
                warnings.append(msg)
        status = str(analysis_handoff.get("status") or "").strip().upper()
        if status == "MISSING" and not any("Analysis evidence" in msg for msg in warnings):
            warnings.append(
                f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} missing; "
                "export evidence manifest from Results Center before SEND."
            )
    else:
        warnings.append(
            f"Analysis evidence / {ANALYSIS_EVIDENCE_HANDOFF_ID} missing; "
            "export evidence manifest from Results Center before SEND."
        )

    geometry_reference = obj.get("geometry_reference_handoff")
    if isinstance(geometry_reference, Mapping):
        for item in geometry_reference.get("warnings") or []:
            msg = str(item or "").strip()
            if msg:
                warnings.append(msg)
        status = str(geometry_reference.get("status") or "").strip().upper()
        if status == "MISSING" and row_status_by_id.get("BND-018") == "missing":
            warnings.append(
                "Geometry reference evidence missing; open Reference Center or re-export anim_latest "
                "before claiming graphics truth."
            )
    return list(dict.fromkeys(warnings))


def evidence_manifest_release_errors(manifest: Mapping[str, Any] | None) -> List[str]:
    obj = dict(manifest or {})
    rows = obj.get("evidence_classes") or []
    errors: list[str] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            evidence_id = str(row.get("evidence_id") or "")
            if evidence_id not in PB002_REQUIRED_EVIDENCE_IDS:
                continue
            if str(row.get("status") or "") == "missing":
                errors.append(
                    f"Missing release-blocking PB-002 evidence {evidence_id}: "
                    f"{', '.join(str(x) for x in (row.get('path_patterns') or []))}"
                )
    summary = obj.get("bundle_contents_summary") or {}
    if isinstance(summary, dict):
        for class_name in summary.get("missing_mandatory_classes") or []:
            errors.append(f"Missing mandatory bundle content class: {class_name}")
    return list(dict.fromkeys(str(x) for x in errors if str(x).strip()))


def read_manifest_inputs_from_zip(zf: Any) -> tuple[dict[str, Any], dict[str, Dict[str, Any]]]:
    meta = _load_json_from_zip(zf, "bundle/meta.json")
    json_by_name: dict[str, Dict[str, Any]] = {}
    for name in (
        "triage/latest_anim_pointer_diagnostics.json",
        "workspace/exports/anim_latest.json",
        "workspace/_pointers/anim_latest.json",
        ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME,
        ANALYSIS_EVIDENCE_FALLBACK_ARCNAME,
        ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME,
        ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME,
        GEOMETRY_REFERENCE_EVIDENCE_ARCNAME,
        GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME,
        GEOMETRY_REFERENCE_EVIDENCE_FALLBACK_ARCNAME,
    ):
        obj = _load_json_from_zip(zf, name)
        if obj:
            json_by_name[name] = obj
    try:
        names = list(zf.namelist())
    except Exception:
        names = []
    for name in names:
        if any(
            fnmatch.fnmatchcase(name, pattern)
            for pattern in (
                "workspace/*active_baseline_contract.json",
                "baseline/active_baseline_contract.json",
                "workspace/*validated_suite_snapshot.json",
                "suite/validated_suite_snapshot.json",
            )
        ):
            obj = _load_json_from_zip(zf, name)
            if obj:
                json_by_name[name] = obj
        if any(
            fnmatch.fnmatchcase(name, pattern)
            for pattern in (
                "workspace/*baseline_history.jsonl",
                "baseline/baseline_history.jsonl",
            )
        ):
            rows: list[dict[str, Any]] = []
            try:
                text = zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                text = ""
            for line in text.splitlines():
                raw = line.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(dict(obj))
                if len(rows) >= 5:
                    break
            if rows:
                json_by_name[name] = {"rows": rows}
    return meta, json_by_name
