from __future__ import annotations

"""Truth/provenance helpers shared by Desktop Animator and anim_latest export.

The helpers here deliberately do not import Qt.  They turn the v32 honesty rules
into small JSON-friendly objects that tests, diagnostics, and the UI can all read.
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .cylinder_truth_gate import (
    ALLOWED_GRAPHICS_TRUTH_STATES,
    TRUTH_STATE_APPROXIMATE,
    TRUTH_STATE_SOLVER_CONFIRMED,
    TRUTH_STATE_SOURCE_DATA_CONFIRMED,
    TRUTH_STATE_UNAVAILABLE,
    evaluate_all_cylinder_truth_gates,
    render_cylinder_truth_gate_message,
)


CAPTURE_EXPORT_MANIFEST_JSON_NAME = "capture_export_manifest.json"
ANIMATOR_FRAME_BUDGET_EVIDENCE_JSON_NAME = "animator_frame_budget_evidence.json"
CAPTURE_EXPORT_HANDOFF_ID = "HO-010"

TRUTH_STATE_LABELS: dict[str, str] = {
    TRUTH_STATE_SOLVER_CONFIRMED: "solver-confirmed",
    TRUTH_STATE_SOURCE_DATA_CONFIRMED: "source-data",
    TRUTH_STATE_APPROXIMATE: "approximate",
    TRUTH_STATE_UNAVAILABLE: "unavailable",
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    return out if math.isfinite(out) else None


def _round_or_none(value: float | None, ndigits: int = 6) -> float | None:
    return round(float(value), ndigits) if value is not None and math.isfinite(float(value)) else None


def stable_contract_hash(payload: Any) -> str:
    blob = json.dumps(
        _jsonable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def file_sha256(path: str | Path | None) -> str:
    if path in (None, ""):
        return ""
    try:
        p = Path(str(path)).expanduser().resolve(strict=False)
        if not p.exists() or not p.is_file():
            return ""
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def _artifact_presence_state(block: Mapping[str, Any], *, ready: bool = False) -> str:
    if not block:
        return TRUTH_STATE_UNAVAILABLE
    return TRUTH_STATE_SOLVER_CONFIRMED if ready else TRUTH_STATE_SOURCE_DATA_CONFIRMED


def _overall_truth_state(states: Mapping[str, str]) -> str:
    values = [str(v) for v in states.values() if str(v)]
    if not values:
        return TRUTH_STATE_UNAVAILABLE
    if TRUTH_STATE_UNAVAILABLE in values:
        return TRUTH_STATE_APPROXIMATE if any(v != TRUTH_STATE_UNAVAILABLE for v in values) else TRUTH_STATE_UNAVAILABLE
    if TRUTH_STATE_APPROXIMATE in values:
        return TRUTH_STATE_APPROXIMATE
    if all(v in {TRUTH_STATE_SOLVER_CONFIRMED, TRUTH_STATE_SOURCE_DATA_CONFIRMED} for v in values):
        return TRUTH_STATE_SOLVER_CONFIRMED
    return TRUTH_STATE_APPROXIMATE


def build_animator_truth_summary(
    meta: Mapping[str, Any] | None,
    *,
    cylinder_gates: Mapping[str, Mapping[str, Any]] | None = None,
    updated_utc: str = "",
) -> dict[str, Any]:
    """Return v32 graphics truth badges and warnings for an anim_latest meta block."""
    meta_dict = _as_mapping(meta)
    solver_points = _as_mapping(meta_dict.get("solver_points"))
    hardpoints = _as_mapping(meta_dict.get("hardpoints"))
    packaging = _as_mapping(meta_dict.get("packaging"))
    validation = _as_mapping(meta_dict.get("anim_export_validation"))
    validation_level = str(validation.get("validation_level") or validation.get("level") or "")
    gates = {
        str(k): _as_mapping(v)
        for k, v in (cylinder_gates or evaluate_all_cylinder_truth_gates(meta_dict)).items()
    }

    cylinder_states = {
        name: str(gate.get("truth_state") or TRUTH_STATE_UNAVAILABLE)
        for name, gate in sorted(gates.items())
    }
    if gates and all(bool(gate.get("enabled")) for gate in gates.values()):
        cylinder_state = TRUTH_STATE_SOLVER_CONFIRMED
    elif packaging:
        cylinder_state = TRUTH_STATE_APPROXIMATE
    else:
        cylinder_state = TRUTH_STATE_UNAVAILABLE

    hardpoint_families = _as_mapping(hardpoints.get("families"))
    hardpoints_ready = bool(hardpoint_families) and not bool(validation.get("visible_missing_families"))
    hardpoints_state = (
        TRUTH_STATE_UNAVAILABLE
        if not hardpoints
        else (TRUTH_STATE_SOURCE_DATA_CONFIRMED if hardpoints_ready else TRUTH_STATE_APPROXIMATE)
    )
    states = {
        "solver_points": _artifact_presence_state(solver_points, ready=True),
        "hardpoints": hardpoints_state,
        "cylinder_packaging": cylinder_state,
    }
    if validation_level and validation_level != "PASS":
        states["contract_validation"] = TRUTH_STATE_APPROXIMATE
    elif validation_level == "PASS":
        states["contract_validation"] = TRUTH_STATE_SOLVER_CONFIRMED

    warnings: list[str] = []
    if not solver_points:
        warnings.append("meta.solver_points is unavailable; solver-confirmed point truth cannot be shown.")
    if not hardpoints:
        warnings.append("meta.hardpoints is unavailable; hardpoint graphics must stay unavailable.")
    elif not hardpoints_ready:
        warnings.append("meta.hardpoints is incomplete; missing hardpoints must stay unavailable with warning.")
    if not packaging:
        warnings.append("meta.packaging is unavailable; cylinder body/rod/piston meshes are disabled.")
    for gate in gates.values():
        if not bool(gate.get("enabled")):
            warnings.append(render_cylinder_truth_gate_message(gate))
    if validation_level and validation_level != "PASS":
        warnings.append(f"anim_export_validation is {validation_level}; graphics require visible warning.")

    overall = _overall_truth_state(states)
    if overall != TRUTH_STATE_SOLVER_CONFIRMED:
        warnings.append("Truth incomplete: show approximate/unavailable warning and do not fabricate geometry.")

    badges = [
        {
            "surface": surface,
            "truth_state": state if state in ALLOWED_GRAPHICS_TRUTH_STATES else TRUTH_STATE_UNAVAILABLE,
            "label": TRUTH_STATE_LABELS.get(state, "unavailable"),
            "warning": state in {TRUTH_STATE_APPROXIMATE, TRUTH_STATE_UNAVAILABLE},
        }
        for surface, state in sorted(states.items())
    ]

    summary = {
        "schema": "desktop_animator.truth_summary.v1",
        "updated_utc": str(updated_utc or meta_dict.get("updated_utc") or _utc_iso()),
        "allowed_truth_states": list(ALLOWED_GRAPHICS_TRUTH_STATES),
        "overall_truth_state": overall,
        "truth_badges": badges,
        "states": states,
        "cylinder_states": cylinder_states,
        "cylinder_gates": gates,
        "validation_level": validation_level,
        "warnings": list(dict.fromkeys(str(x) for x in warnings if str(x).strip())),
        "artifact_refs": _as_mapping(meta_dict.get("anim_export_contract_artifacts")),
    }
    summary["truth_mode_hash"] = stable_contract_hash(
        {
            "overall_truth_state": summary["overall_truth_state"],
            "states": summary["states"],
            "cylinder_states": summary["cylinder_states"],
            "warnings": summary["warnings"],
        }
    )
    return summary


def extract_analysis_optimizer_artifact_refs(meta: Mapping[str, Any] | None) -> dict[str, Any]:
    meta_dict = _as_mapping(meta)
    analysis_keys = (
        "analysis_context",
        "analysis_context_hash",
        "analysis_context_path",
        "analysis_context_status",
        "animator_link_contract_hash",
        "animator_link_contract_path",
        "analysis_report_path",
        "analysis_artifacts",
        "compare_contract_hash",
        "compare_contract_path",
        "compare_session_id",
        "selected_result_artifact_pointer",
        "selected_npz_path",
        "selected_test_id",
        "selected_segment_id",
        "selected_time_window",
    )
    optimizer_keys = (
        "optimizer_artifact_refs",
        "optimizer_run_dir",
        "optimization_run_dir",
        "optimization_artifacts",
        "optimization_summary_path",
        "run_id",
        "selected_run_contract",
        "selected_run_contract_hash",
        "run_contract_hash",
        "objective_contract_hash",
        "active_baseline_hash",
        "suite_snapshot_hash",
        "hard_gate_key",
        "hard_gate_tolerance",
        "optimizer_scope",
        "problem_hash",
    )
    analysis = {k: _jsonable(meta_dict.get(k)) for k in analysis_keys if meta_dict.get(k) not in (None, "", [], {})}
    optimizer = {k: _jsonable(meta_dict.get(k)) for k in optimizer_keys if meta_dict.get(k) not in (None, "", [], {})}
    artifacts = _as_mapping(meta_dict.get("artifacts"))
    for key, value in artifacts.items():
        key_s = str(key)
        if "analysis" in key_s or "compare" in key_s:
            analysis.setdefault(key_s, _jsonable(value))
        if "opt" in key_s or "objective" in key_s or "problem_hash" in key_s:
            optimizer.setdefault(key_s, _jsonable(value))
    return {"analysis": analysis, "optimizer": optimizer}


def build_frame_budget_evidence(
    *,
    panels: Mapping[str, Any] | None,
    visible_aux: int,
    total_aux_docks: int,
    playing: bool,
    many_visible_budget: bool,
    window_s: float,
    source_dt_s: float | None = None,
    frame_budget_active: bool | None = None,
    frame_cadence: Mapping[str, Any] | None = None,
    updated_utc: str = "",
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    panel_map = {str(k): _as_mapping(v) for k, v in _as_mapping(panels).items()}
    hidden_panel_updates = [
        name
        for name, info in panel_map.items()
        if not bool(info.get("visible")) and int(info.get("count") or 0) > 0
    ]
    hidden_aux = max(0, int(total_aux_docks) - int(visible_aux))
    budget_active = bool(frame_budget_active) if frame_budget_active is not None else bool(many_visible_budget)
    cadence_in = _as_mapping(frame_cadence)
    target_interval_ms = _safe_float(cadence_in.get("target_interval_ms") or cadence_in.get("interval_ms"))
    target_hz = _safe_float(cadence_in.get("target_hz") or cadence_in.get("display_hz"))
    if target_hz is None and target_interval_ms is not None and target_interval_ms > 1e-6:
        target_hz = 1000.0 / target_interval_ms
    if target_interval_ms is None and target_hz is not None and target_hz > 1e-6:
        target_interval_ms = 1000.0 / target_hz
    measured_present_hz = _safe_float(cadence_in.get("measured_present_hz") or cadence_in.get("present_hz_ema"))
    present_dt_ema_ms = _safe_float(cadence_in.get("present_dt_ema_ms"))
    if present_dt_ema_ms is None:
        present_dt_ema_s = _safe_float(cadence_in.get("present_dt_ema_s"))
        if present_dt_ema_s is not None:
            present_dt_ema_ms = present_dt_ema_s * 1000.0
    if present_dt_ema_ms is None and measured_present_hz is not None and measured_present_hz > 1e-6:
        present_dt_ema_ms = 1000.0 / measured_present_hz
    cadence_measured = bool(measured_present_hz is not None or present_dt_ema_ms is not None)
    cadence_budget_raw = cadence_in.get("cadence_budget_ok")
    if cadence_budget_raw is None:
        if cadence_measured and measured_present_hz is not None and target_hz is not None:
            cadence_budget_ok: bool | None = measured_present_hz >= max(5.0, target_hz * 0.45)
        elif cadence_measured:
            cadence_budget_ok = True
        else:
            cadence_budget_ok = None
    else:
        cadence_budget_ok = bool(cadence_budget_raw)
    cadence_block = {
        "target_interval_ms": _round_or_none(target_interval_ms, 3),
        "target_hz": _round_or_none(target_hz, 3),
        "measured_present_hz": _round_or_none(measured_present_hz, 3),
        "present_dt_ema_ms": _round_or_none(present_dt_ema_ms, 3),
        "pending_present": bool(cadence_in.get("pending_present")) if "pending_present" in cadence_in else None,
        "sample_count": int(cadence_in.get("sample_count") or cadence_in.get("present_sample_count") or 0),
        "display_hz_source": str(cadence_in.get("display_hz_source") or ""),
        "cadence_measured": bool(cadence_measured),
        "cadence_budget_ok": cadence_budget_ok,
    }
    hidden_gated = not bool(hidden_panel_updates)
    if not panel_map:
        release_level = "WARN"
        release_status = "missing_panel_samples"
        hard_fail = False
    elif not hidden_gated or cadence_budget_ok is False:
        release_level = "FAIL"
        release_status = "frame_budget_failed"
        hard_fail = True
    elif cadence_budget_ok is True:
        release_level = "PASS"
        release_status = "frame_budget_measured"
        hard_fail = False
    else:
        release_level = "WARN"
        release_status = "missing_frame_cadence"
        hard_fail = False
    base = {
        "schema": "animator_frame_budget_evidence.v1",
        "handoff_id": CAPTURE_EXPORT_HANDOFF_ID,
        "updated_utc": str(updated_utc or _utc_iso()),
        "evidence_state": "measured" if panel_map else TRUTH_STATE_UNAVAILABLE,
        "frame_budget": {
            "playing": bool(playing),
            "many_visible_budget": bool(many_visible_budget),
            "frame_budget_active": budget_active,
            "source_dt_s": source_dt_s,
            "window_s": round(float(max(0.0, window_s)), 6),
            "panel_sample_count": int(len(panel_map)),
            "frame_cadence": cadence_block,
        },
        "frame_cadence": cadence_block,
        "hidden_dock_gating": {
            "total_aux_docks": int(max(0, total_aux_docks)),
            "visible_aux": int(max(0, visible_aux)),
            "hidden_aux_docks": int(hidden_aux),
            "hidden_panel_updates": hidden_panel_updates,
            "gated": hidden_gated,
        },
        "panels": panel_map,
        "provenance": _as_mapping(provenance),
        "release_gate": {
            "playbook_id": "PB-006",
            "open_gap_id": "OG-003/OG-004",
            "release_gates": ["RGH-012", "RGH-019"],
            "level": release_level,
            "status": release_status,
            "hard_fail": bool(hard_fail),
        },
    }
    base["evidence_hash"] = stable_contract_hash(base)
    return base


def build_capture_export_manifest(
    *,
    meta: Mapping[str, Any] | None,
    updated_utc: str = "",
    npz_path: str | Path | None = None,
    pointer_path: str | Path | None = None,
    artifact_refs: Mapping[str, Any] | None = None,
    analysis_context_refs: Mapping[str, Any] | None = None,
    frame_budget_evidence_ref: str = ANIMATOR_FRAME_BUDGET_EVIDENCE_JSON_NAME,
    truth_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    meta_dict = _as_mapping(meta)
    truth = _as_mapping(truth_summary) or build_animator_truth_summary(meta_dict, updated_utc=updated_utc)
    refs = _as_mapping(artifact_refs) or _as_mapping(meta_dict.get("anim_export_contract_artifacts"))
    refs.setdefault("frame_budget_evidence", str(frame_budget_evidence_ref or ""))

    npz_sha = file_sha256(npz_path)
    pointer_sha = file_sha256(pointer_path)
    capture_refs = {
        "anim_latest_npz": {"path": str(npz_path or ""), "sha256": npz_sha},
        "anim_latest_pointer": {"path": str(pointer_path or ""), "sha256": pointer_sha},
    }
    artifact_groups = extract_analysis_optimizer_artifact_refs(meta_dict)
    explicit_analysis_context_refs = {
        str(k): _jsonable(v)
        for k, v in _as_mapping(analysis_context_refs).items()
        if v not in (None, "", [], {})
    }
    if explicit_analysis_context_refs:
        explicit_groups = extract_analysis_optimizer_artifact_refs(explicit_analysis_context_refs)
        artifact_groups["analysis"] = {
            **_as_mapping(artifact_groups.get("analysis")),
            **_as_mapping(explicit_groups.get("analysis")),
        }
        artifact_groups["optimizer"] = {
            **_as_mapping(artifact_groups.get("optimizer")),
            **_as_mapping(explicit_groups.get("optimizer")),
        }
    analysis_context_hash = str(
        explicit_analysis_context_refs.get("analysis_context_hash")
        or meta_dict.get("analysis_context_hash")
        or ""
    ).strip()
    if not analysis_context_hash:
        analysis_context_hash = stable_contract_hash(artifact_groups.get("analysis") or {})
    analysis_context_status = str(
        explicit_analysis_context_refs.get("analysis_context_status")
        or meta_dict.get("analysis_context_status")
        or ""
    ).strip()
    truth_mode_hash = str(truth.get("truth_mode_hash") or stable_contract_hash(truth))
    capture_hash = stable_contract_hash(capture_refs) if (npz_sha or pointer_sha) else ""

    blocking_states: list[str] = []
    if not capture_hash:
        blocking_states.append("missing_capture_ref")
    if str(truth.get("overall_truth_state") or "") != TRUTH_STATE_SOLVER_CONFIRMED:
        blocking_states.append("truth_warning_required")
    states = _as_mapping(truth.get("states"))
    if states.get("solver_points") == TRUTH_STATE_UNAVAILABLE:
        blocking_states.append("missing_solver_points_truth")
    if states.get("hardpoints") == TRUTH_STATE_UNAVAILABLE:
        blocking_states.append("missing_hardpoints_truth")
    if states.get("cylinder_packaging") == TRUTH_STATE_UNAVAILABLE:
        blocking_states.append("missing_cylinder_packaging_truth")
    if analysis_context_status in {"BLOCKED", "INVALID", "MISSING"}:
        blocking_states.append("analysis_context_blocked")
    elif analysis_context_status == "DEGRADED":
        blocking_states.append("analysis_context_degraded")

    manifest = {
        "schema": "capture_export_manifest.v1",
        "handoff_id": CAPTURE_EXPORT_HANDOFF_ID,
        "from_workspace": "WS-ANIMATOR",
        "to_workspace": "WS-DIAGNOSTICS",
        "updated_utc": str(updated_utc or _utc_iso()),
        "capture_hash": capture_hash,
        "analysis_context_hash": analysis_context_hash,
        "analysis_context_status": analysis_context_status,
        "animator_link_contract_hash": str(
            explicit_analysis_context_refs.get("animator_link_contract_hash")
            or meta_dict.get("animator_link_contract_hash")
            or ""
        ),
        "selected_run_contract_hash": str(
            explicit_analysis_context_refs.get("selected_run_contract_hash")
            or meta_dict.get("selected_run_contract_hash")
            or ""
        ),
        "truth_mode_hash": truth_mode_hash,
        "capture_refs": capture_refs,
        "artifact_refs": refs,
        "analysis_context_refs": explicit_analysis_context_refs,
        "analysis_artifact_refs": _as_mapping(artifact_groups.get("analysis")),
        "optimizer_artifact_refs": _as_mapping(artifact_groups.get("optimizer")),
        "truth_summary": truth,
        "blocking_states": list(dict.fromkeys(blocking_states)),
        "provenance": {
            "producer": "anim_latest export",
            "indicator": "capture provenance banner",
            "truth_warning_required": bool(str(truth.get("overall_truth_state") or "") != TRUTH_STATE_SOLVER_CONFIRMED),
        },
    }
    return manifest


def write_json_artifact(path: str | Path, payload: Mapping[str, Any]) -> Path:
    out = Path(path).expanduser().resolve(strict=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    return out


__all__ = [
    "ANIMATOR_FRAME_BUDGET_EVIDENCE_JSON_NAME",
    "CAPTURE_EXPORT_HANDOFF_ID",
    "CAPTURE_EXPORT_MANIFEST_JSON_NAME",
    "TRUTH_STATE_LABELS",
    "build_animator_truth_summary",
    "build_capture_export_manifest",
    "build_frame_budget_evidence",
    "extract_analysis_optimizer_artifact_refs",
    "file_sha256",
    "stable_contract_hash",
    "write_json_artifact",
]
