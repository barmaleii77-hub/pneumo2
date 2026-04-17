# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


LATEST_DESKTOP_DIAGNOSTICS_RUN_JSON = "latest_desktop_diagnostics_run.json"
LATEST_DESKTOP_DIAGNOSTICS_RUN_LOG = "latest_desktop_diagnostics_run.log"
LATEST_DESKTOP_DIAGNOSTICS_CENTER_JSON = "latest_desktop_diagnostics_center_state.json"
LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD = "latest_desktop_diagnostics_summary.md"
LATEST_SEND_BUNDLE_INSPECTION_JSON = "latest_send_bundle_inspection.json"
LATEST_SEND_BUNDLE_INSPECTION_MD = "latest_send_bundle_inspection.md"


def now_local_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def path_str(path: Optional[Path | str]) -> str:
    if not path:
        return ""
    try:
        return str(Path(path).expanduser().resolve())
    except Exception:
        return str(path)


@dataclass(slots=True)
class DesktopDiagnosticsRequest:
    level: str = "standard"
    skip_ui_smoke: bool = False
    no_zip: bool = False
    run_opt_smoke: bool = False
    opt_minutes: int = 2
    opt_jobs: int = 2
    osc_dir: str = ""
    out_root: str = ""

    def resolved_out_root(self, repo_root: Path) -> Path:
        raw = str(self.out_root or "").strip()
        if not raw:
            return (repo_root / "diagnostics").resolve()
        try:
            path = Path(raw).expanduser()
            if path.is_absolute():
                return path.resolve()
        except Exception:
            return Path(raw)
        return (repo_root / raw).resolve()


@dataclass(slots=True)
class DesktopDiagnosticsRunRecord:
    ok: bool
    started_at: str
    finished_at: str = ""
    status: str = ""
    command: list[str] = field(default_factory=list)
    returncode: Optional[int] = None
    run_dir: str = ""
    zip_path: str = ""
    out_root: str = ""
    log_path: str = ""
    state_path: str = ""
    last_message: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema"] = "desktop_diagnostics_run_state"
        payload["schema_version"] = "1.0.0"
        return payload


@dataclass(slots=True)
class DesktopDiagnosticsBundleRecord:
    out_dir: str
    latest_zip_path: str = ""
    latest_zip_name: str = ""
    latest_path_pointer_path: str = ""
    latest_sha_path: str = ""
    latest_bundle_meta_path: str = ""
    latest_inspection_json_path: str = ""
    latest_inspection_md_path: str = ""
    latest_health_json_path: str = ""
    latest_health_md_path: str = ""
    latest_validation_json_path: str = ""
    latest_validation_md_path: str = ""
    latest_triage_md_path: str = ""
    latest_evidence_manifest_path: str = ""
    latest_analysis_evidence_manifest_path: str = ""
    analysis_evidence_manifest_hash: str = ""
    analysis_evidence_status: str = "MISSING"
    analysis_evidence_handoff_id: str = ""
    analysis_evidence_context_state: str = "MISSING"
    analysis_context_status: str = ""
    analysis_context_action: str = ""
    analysis_animator_link_contract_hash: str = ""
    analysis_selected_run_contract_hash: str = ""
    analysis_selected_test_id: str = ""
    analysis_selected_npz_path: str = ""
    analysis_capture_export_manifest_status: str = "MISSING"
    analysis_capture_export_manifest_handoff_id: str = ""
    analysis_capture_hash: str = ""
    analysis_truth_mode_hash: str = ""
    analysis_evidence_run_id: str = ""
    analysis_evidence_run_contract_hash: str = ""
    analysis_evidence_compare_contract_id: str = ""
    analysis_evidence_artifact_count: int = 0
    analysis_evidence_mismatch_count: int = 0
    analysis_evidence_warnings: list[str] = field(default_factory=list)
    analysis_evidence_action: str = ""
    latest_engineering_analysis_evidence_manifest_path: str = ""
    engineering_analysis_evidence_manifest_hash: str = ""
    engineering_analysis_evidence_status: str = "MISSING"
    engineering_analysis_evidence_schema: str = ""
    engineering_analysis_validation_status: str = "MISSING"
    engineering_analysis_candidate_count: int = 0
    engineering_analysis_ready_candidate_count: int = 0
    engineering_analysis_missing_inputs_candidate_count: int = 0
    engineering_analysis_failed_candidate_count: int = 0
    engineering_analysis_candidate_unique_missing_inputs: list[str] = field(default_factory=list)
    engineering_analysis_candidate_ready_run_dirs: list[str] = field(default_factory=list)
    engineering_analysis_evidence_warnings: list[str] = field(default_factory=list)
    engineering_analysis_evidence_action: str = ""
    latest_geometry_reference_evidence_path: str = ""
    geometry_reference_status: str = "MISSING"
    geometry_reference_artifact_status: str = "missing"
    geometry_reference_artifact_freshness_status: str = "missing"
    geometry_reference_artifact_freshness_relation: str = "missing"
    geometry_reference_artifact_freshness_reason: str = ""
    geometry_reference_latest_artifact_status: str = ""
    geometry_reference_road_width_status: str = "missing"
    geometry_reference_road_width_source: str = ""
    geometry_reference_packaging_status: str = "missing"
    geometry_reference_packaging_mismatch_status: str = "missing"
    geometry_reference_packaging_contract_hash: str = ""
    geometry_reference_acceptance_gate: str = "MISSING"
    geometry_reference_producer_artifact_status: str = "missing"
    geometry_reference_producer_readiness_reasons: list[str] = field(default_factory=list)
    geometry_reference_producer_evidence_owner: str = "producer_export"
    geometry_reference_producer_required_artifacts: list[str] = field(default_factory=list)
    geometry_reference_producer_next_action: str = ""
    geometry_reference_consumer_may_fabricate_geometry: bool = False
    geometry_reference_component_passport_needs_data: int = 0
    geometry_reference_evidence_missing: list[str] = field(default_factory=list)
    geometry_reference_warnings: list[str] = field(default_factory=list)
    geometry_reference_action: str = ""
    latest_clipboard_status_path: str = ""
    anim_pointer_diagnostics_path: str = ""
    summary_lines: list[str] = field(default_factory=list)
    clipboard_ok: Optional[bool] = None
    clipboard_message: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema"] = "desktop_diagnostics_bundle_state"
        payload["schema_version"] = "1.0.0"
        return payload


def build_run_full_diagnostics_command(
    python_exe: str,
    script_path: Path,
    request: DesktopDiagnosticsRequest,
) -> list[str]:
    cmd = [str(python_exe), str(script_path), "--level", str(request.level)]
    if request.skip_ui_smoke:
        cmd.append("--skip_ui_smoke")
    if request.no_zip:
        cmd.append("--no_zip")
    if request.run_opt_smoke:
        cmd += [
            "--run_opt_smoke",
            "--opt_minutes",
            str(int(request.opt_minutes)),
            "--opt_jobs",
            str(int(request.opt_jobs)),
        ]
    osc_dir = str(request.osc_dir or "").strip()
    if osc_dir:
        cmd += ["--osc_dir", osc_dir]
    cmd += ["--out_root", str(request.out_root or "")]
    return cmd


def parse_run_full_diagnostics_output_line(line: str) -> dict[str, str]:
    text = str(line or "").strip()
    updates: dict[str, str] = {}
    if text.startswith("Run dir:"):
        updates["run_dir"] = text.split("Run dir:", 1)[1].strip()
    elif text.startswith("Zip:"):
        updates["zip_path"] = text.split("Zip:", 1)[1].strip()
    elif text.startswith("Diagnostics written to:"):
        updates["run_dir"] = text.split("Diagnostics written to:", 1)[1].strip()
    return updates
