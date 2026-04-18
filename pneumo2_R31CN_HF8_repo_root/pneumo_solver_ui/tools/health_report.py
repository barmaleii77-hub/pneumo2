# -*- coding: utf-8 -*-
"""pneumo_solver_ui.tools.health_report (Testy R639)

Сводный отчёт по "здоровью" send-bundle ZIP.
Цель: одним файлом дать быстрый ответ:
- валиден ли ZIP
- есть ли критичные проблемы в логах (loglint strict)
- прошли ли selfchecks
- не потеряны ли anim_latest reload diagnostics

Используется из make_send_bundle: после сборки/валидации ZIP создаём health_report.*
и добавляем его внутрь ZIP.

Best-effort: никогда не должен валить сборку.
"""

from __future__ import annotations

import importlib
import json
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pneumo_solver_ui.browser_perf_artifacts import (
    BROWSER_PERF_COMPARISON_REPORT_JSON_NAME,
    BROWSER_PERF_CONTRACT_JSON_NAME,
    BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME,
    BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME,
    BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME,
    BROWSER_PERF_TRACE_CANDIDATE_NAMES,
)
from pneumo_solver_ui.optimization_scope_compare import (
    compare_optimizer_scope_sources,
    evaluate_optimizer_scope_gate,
    extract_optimizer_scope_from_dashboard,
    extract_optimizer_scope_from_health,
    extract_optimizer_scope_from_run_scope,
    extract_optimizer_scope_from_triage,
    extract_optimizer_scope_from_validation,
    optimizer_scope_export_source_name,
)

from .send_bundle_contract import (
    ANIM_DIAG_JSON,
    ANIM_GLOBAL_POINTER,
    ANIM_LOCAL_NPZ,
    ANIM_LOCAL_POINTER,
    annotate_anim_source_for_bundle,
    build_anim_operator_recommendations,
    choose_anim_snapshot,
    extract_anim_snapshot,
    summarize_ring_closure,
    summarize_mnemo_event_log,
)
from .send_bundle_evidence import (
    ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME,
    ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME,
    EVIDENCE_MANIFEST_ARCNAME,
    EVIDENCE_MANIFEST_SIDECAR_NAME,
    build_evidence_manifest,
    build_latest_integrity_proof,
    evidence_manifest_warnings,
    load_evidence_manifest_from_zip,
    read_manifest_inputs_from_zip,
    summarize_engineering_analysis_evidence,
)


@dataclass
class HealthReport:
    schema: str
    schema_version: str
    created_at: str
    zip_path: str
    ok: bool
    signals: Dict[str, Any]
    notes: List[str]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_json_from_zip(z: zipfile.ZipFile, name: str) -> Optional[Dict[str, Any]]:
    try:
        with z.open(name, "r") as f:
            raw = f.read()
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None


def _read_json_file(path: Path) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return dict(obj) if isinstance(obj, dict) else None
    except Exception:
        return None


def _glob_zip_names(names: List[str], suffix: str) -> List[str]:
    return [n for n in names if n.endswith(suffix)]


def _safe_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return 0


def _summarize_self_check_silent_warnings_snapshot(
    report: Dict[str, Any] | None,
    *,
    source_path: str = "",
) -> Dict[str, Any]:
    if not report:
        return {
            "status": "MISSING",
            "source_path": str(source_path or ""),
            "snapshot_only": True,
            "does_not_close_producer_warnings": True,
            "rc": None,
            "fail_count": 0,
            "warn_count": 0,
            "generated_at_utc": "",
        }
    summary = dict(report.get("summary") or {}) if isinstance(report.get("summary"), dict) else {}
    fail_count = _safe_int(summary.get("fail_count"))
    warn_count = _safe_int(summary.get("warn_count"))
    if not fail_count:
        fail_count = len([item for item in (report.get("fails") or []) if isinstance(item, dict)])
    if not warn_count:
        warn_count = len([item for item in (report.get("warnings") or []) if isinstance(item, dict)])
    rc = report.get("rc")
    status = "READY"
    if fail_count or warn_count or (rc not in (None, 0, "0")):
        status = "WARN"
    return {
        "status": status,
        "source_path": str(source_path or ""),
        "snapshot_only": True,
        "does_not_close_producer_warnings": True,
        "rc": rc,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "generated_at_utc": str(report.get("generated_at_utc") or ""),
        "release": str(report.get("release") or ""),
        "version": str(report.get("version") or ""),
    }




def _collect_geometry_acceptance_best_effort(raw_npz: bytes) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Best-effort geometry acceptance extraction without hard import-time dependency.

    Why:
    - send-bundle helpers can be launched from GUI/postmortem contexts where the
      interpreter path is not always obvious from logs;
    - health report must remain available even if heavy numerical deps are not
      importable in that specific helper process.

    Contract:
    - returns (report_dict, None) on success;
    - returns (None, human_readable_error) when helper import/execution is not
      available;
    - never raises.
    """
    try:
        mod = importlib.import_module("pneumo_solver_ui.geometry_acceptance_contract")
        collect = getattr(mod, "collect_geometry_acceptance_from_npz")
    except Exception as e:
        return None, f"geometry acceptance helper unavailable: {type(e).__name__}: {e!s}"

    try:
        rep = collect(raw_npz)
        if isinstance(rep, dict):
            return dict(rep), None
        return None, "geometry acceptance helper returned non-dict result"
    except Exception as e:
        return None, f"failed to inspect anim_latest geometry acceptance: {type(e).__name__}: {e!s}"


def _normalize_geometry_acceptance_payload(
    payload: Dict[str, Any],
    *,
    source_path: str = "",
    source_kind: str = "",
) -> Dict[str, Any]:
    """Normalize producer report or helper summary into one health surface."""
    obj = dict(payload or {})
    truth = dict(obj.get("truth_state_summary") or {}) if isinstance(obj.get("truth_state_summary"), dict) else {}
    summary = dict(obj.get("summary") or {}) if isinstance(obj.get("summary"), dict) else {}
    gate = str(
        truth.get("release_gate")
        or summary.get("release_gate")
        or obj.get("release_gate")
        or "MISSING"
    ).upper()
    reason = str(
        truth.get("release_gate_reason")
        or summary.get("release_gate_reason")
        or obj.get("release_gate_reason")
        or obj.get("error")
        or ""
    )
    available = truth.get("available", summary.get("available", obj.get("available", False)))
    ok_value = truth.get("ok", summary.get("ok", obj.get("ok", gate == "PASS")))
    inspection_status = str(obj.get("inspection_status") or "").strip()
    if not inspection_status:
        if gate == "PASS":
            inspection_status = "ok"
        elif gate == "WARN":
            inspection_status = "warning"
        elif gate == "FAIL":
            inspection_status = "fail"
        else:
            inspection_status = "missing"

    warnings = [str(x) for x in (obj.get("warnings") or []) if str(x).strip()]
    missing_fields = [str(x) for x in (obj.get("missing_fields") or summary.get("missing_triplets") or []) if str(x).strip()]
    normalized = dict(summary)
    normalized.update(obj)
    normalized.update(
        {
            "release_gate": gate,
            "release_gate_reason": reason,
            "available": bool(available),
            "ok": bool(ok_value),
            "inspection_status": inspection_status,
            "producer_owned": bool(truth.get("producer_owned", obj.get("producer_owned", False))),
            "no_synthetic_geometry": bool(truth.get("no_synthetic_geometry", obj.get("no_synthetic_geometry", False))),
            "graphics_truth_state": str(truth.get("graphics_truth_state") or obj.get("graphics_truth_state") or ""),
            "missing_fields": missing_fields,
            "warnings": warnings,
            "source_path": str(source_path or obj.get("source_path") or ""),
            "source_kind": str(source_kind or obj.get("source_kind") or ""),
        }
    )
    if truth:
        normalized["truth_state_summary"] = truth
    if summary:
        normalized["summary"] = summary
    return normalized


def _geometry_acceptance_note(geom: Dict[str, Any], *, source_label: str) -> tuple[bool, str]:
    gate = str(geom.get("release_gate") or "MISSING").upper()
    reason = str(geom.get("release_gate_reason") or "").strip()
    suffix = f": {reason}" if reason else ""
    if gate == "FAIL":
        return False, f"geometry acceptance gate=FAIL for {source_label}{suffix}"
    if gate == "WARN":
        return True, f"geometry acceptance gate=WARN for {source_label}{suffix}"
    if gate == "MISSING":
        return True, f"geometry acceptance gate=MISSING for {source_label}{suffix}"
    return True, ""


def _format_geometry_acceptance_summary_lines_best_effort(geom: Dict[str, Any]) -> List[str]:
    gate = str(geom.get("release_gate") or "MISSING")
    reason = str(geom.get("release_gate_reason") or geom.get("error") or "—")
    lines = [
        f"- inspection_status: {geom.get('inspection_status') or 'missing'}",
        f"- release_gate: {gate}",
        f"- release_gate_reason: {reason}",
        f"- producer_owned: {geom.get('producer_owned')}",
        f"- no_synthetic_geometry: {geom.get('no_synthetic_geometry')}",
    ]
    missing = [str(x) for x in (geom.get("missing_fields") or []) if str(x).strip()]
    if missing:
        lines.append(f"- missing_fields: {', '.join(missing[:8])}")
    warnings = [str(x) for x in (geom.get("warnings") or []) if str(x).strip()]
    for warning in warnings[:5]:
        lines.append(f"- warning: {warning}")
    try:
        mod = importlib.import_module("pneumo_solver_ui.geometry_acceptance_contract")
        fmt = getattr(mod, "format_geometry_acceptance_summary_lines")
        formatted = [str(x) for x in fmt(geom)]
        return lines + [x for x in formatted if x not in lines]
    except Exception:
        return lines


def collect_health_report(zip_path: Path) -> HealthReport:
    zip_path = Path(zip_path).resolve()
    created_at = _now_iso()
    signals: Dict[str, Any] = {}
    notes: List[str] = []
    ok = True

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            name_set = set(names)

            signals["artifacts"] = {
                "validation_report": "validation/validation_report.json" in name_set,
                "dashboard_report": "dashboard/dashboard.json" in name_set,
                "triage_report": "triage/triage_report.json" in name_set or "triage/triage_report.md" in name_set,
                "anim_diagnostics": ANIM_DIAG_JSON in name_set,
                "evidence_manifest": EVIDENCE_MANIFEST_ARCNAME in name_set,
                "engineering_analysis_evidence": ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME in name_set,
                "health_report_embedded": "health/health_report.json" in name_set or "health/health_report.md" in name_set,
                "browser_perf_registry_snapshot": f"workspace/exports/{BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME}" in name_set,
                "browser_perf_previous_snapshot": f"workspace/exports/{BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME}" in name_set,
                "browser_perf_contract": f"workspace/exports/{BROWSER_PERF_CONTRACT_JSON_NAME}" in name_set,
                "browser_perf_evidence_report": f"workspace/exports/{BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME}" in name_set,
                "browser_perf_comparison_report": f"workspace/exports/{BROWSER_PERF_COMPARISON_REPORT_JSON_NAME}" in name_set,
                "browser_perf_trace": any(f"workspace/exports/{name}" in name_set for name in BROWSER_PERF_TRACE_CANDIDATE_NAMES),
                "self_check_silent_warnings": "reports/SELF_CHECK_SILENT_WARNINGS.json" in name_set,
                "evidence_manifest": EVIDENCE_MANIFEST_ARCNAME in name_set,
            }

            meta = _read_json_from_zip(z, "bundle/meta.json")
            if meta is not None:
                signals["meta"] = {
                    "release": meta.get("release"),
                    "run_id": meta.get("run_id"),
                    "created_at": meta.get("created_at"),
                    "trigger": meta.get("trigger"),
                    "collection_mode": meta.get("collection_mode"),
                }

            try:
                evidence_obj = load_evidence_manifest_from_zip(z)
                if not evidence_obj:
                    evidence_meta, evidence_json_by_name = read_manifest_inputs_from_zip(z)
                    evidence_obj = build_evidence_manifest(
                        zip_path=zip_path,
                        names=names,
                        meta=evidence_meta or meta or {},
                        json_by_name=evidence_json_by_name,
                        planned_paths=(EVIDENCE_MANIFEST_ARCNAME, "health/health_report.json", "health/health_report.md"),
                        stage="health_report_collection",
                    )
                signals["evidence_manifest"] = dict(evidence_obj)
                for msg in evidence_manifest_warnings(evidence_obj):
                    if msg not in notes:
                        notes.append(msg)
            except Exception as exc:
                notes.append(f"failed to inspect evidence manifest: {type(exc).__name__}: {exc!s}")

            self_check_snapshot = _read_json_from_zip(z, "reports/SELF_CHECK_SILENT_WARNINGS.json")
            signals["self_check_silent_warnings"] = _summarize_self_check_silent_warnings_snapshot(
                self_check_snapshot,
                source_path="reports/SELF_CHECK_SILENT_WARNINGS.json" if self_check_snapshot else "",
            )
            if signals["self_check_silent_warnings"].get("status") == "WARN":
                notes.append(
                    "self_check silent warnings snapshot has WARN/FAIL entries; snapshot-only evidence does not close producer gaps."
                )

            if zip_path.name == "latest_send_bundle.zip":
                latest_evidence_path = zip_path.parent / EVIDENCE_MANIFEST_SIDECAR_NAME
                latest_evidence_obj = _read_json_file(latest_evidence_path) if latest_evidence_path.exists() else None
                if latest_evidence_obj is not None:
                    latest_proof = build_latest_integrity_proof(
                        zip_path=zip_path,
                        latest_zip_path=zip_path,
                        original_zip_path=latest_evidence_obj.get("zip_path") or zip_path,
                        latest_sha_path=zip_path.parent / "latest_send_bundle.sha256",
                        latest_pointer_path=zip_path.parent / "latest_send_bundle_path.txt",
                        evidence_manifest=latest_evidence_obj,
                        embedded_manifest=signals.get("evidence_manifest")
                        if isinstance(signals.get("evidence_manifest"), dict)
                        else {},
                    )
                    signals["latest_integrity_proof"] = latest_proof
                    if latest_proof.get("warning_only_gaps_present"):
                        ok = False
                    for msg in latest_proof.get("warnings") or []:
                        smsg = str(msg).strip()
                        if smsg and smsg not in notes:
                            notes.append(smsg)

            engineering_name = ""
            if ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME in name_set:
                engineering_name = ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME
            elif ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME in name_set:
                engineering_name = ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME
            if engineering_name:
                engineering_obj = _read_json_from_zip(z, engineering_name)
                if isinstance(engineering_obj, dict):
                    engineering_summary = summarize_engineering_analysis_evidence(
                        engineering_obj,
                        source_path=engineering_name,
                    )
                else:
                    engineering_summary = summarize_engineering_analysis_evidence(
                        {},
                        source_path=engineering_name,
                        read_warnings=(f"{engineering_name} is not valid JSON",),
                    )
                signals["engineering_analysis_evidence"] = engineering_summary
                for item in engineering_summary.get("warnings") or []:
                    msg = str(item).strip()
                    if msg and msg not in notes:
                        notes.append(msg)

            anim_sources: Dict[str, Dict[str, Any]] = {}
            optimizer_scope_sources: Dict[str, Dict[str, Any]] = {}

            embedded_health = _read_json_from_zip(z, "health/health_report.json")
            embedded_health_scope = extract_optimizer_scope_from_health(embedded_health)
            if embedded_health_scope:
                optimizer_scope_sources[str(embedded_health_scope.get("source") or "health")] = embedded_health_scope

            val = _read_json_from_zip(z, "validation/validation_report.json")
            if val is not None:
                val_errors = list(val.get("errors") or []) if isinstance(val.get("errors"), list) else []
                val_warnings = list(val.get("warnings") or []) if isinstance(val.get("warnings"), list) else []
                signals["validation"] = {
                    "ok": bool(val.get("ok", False)),
                    "errors_count": len(val_errors),
                    "warnings_count": len(val_warnings),
                    "errors_preview": val_errors[:5],
                    "warnings_preview": val_warnings[:5],
                }
                if not bool(val.get("ok", False)):
                    ok = False
                anim_snap = annotate_anim_source_for_bundle(
                    extract_anim_snapshot(val.get("anim_latest"), source="validation"),
                    name_set=name_set,
                )
                if anim_snap is not None:
                    anim_sources["validation"] = anim_snap
                    if anim_snap.get("issues"):
                        notes.extend(str(x) for x in anim_snap.get("issues") or [] if str(x).strip())
                val_scope = extract_optimizer_scope_from_validation(val)
                if val_scope:
                    optimizer_scope_sources[str(val_scope.get("source") or "validation")] = val_scope

            sc = _read_json_from_zip(z, "selfcheck/selfcheck_report.json")
            if sc is not None:
                signals["selfcheck"] = {
                    "ok": bool(sc.get("ok", False)),
                    "failed_steps": (sc.get("summary", {}) or {}).get("steps_failed", []),
                }
                if not bool(sc.get("ok", False)):
                    ok = False

            tri = _read_json_from_zip(z, "triage/triage_report.json")
            if tri is not None:
                sev = tri.get("severity_counts") or {}
                dist_progress = tri.get("dist_progress") or {}
                signals["triage"] = {
                    "severity_counts": sev,
                    "red_flags": tri.get("red_flags", []),
                }
                if isinstance(dist_progress, dict) and dist_progress:
                    signals["triage"]["dist_progress"] = dict(dist_progress)
                    triage_scope = extract_optimizer_scope_from_triage(tri)
                    if triage_scope:
                        optimizer_scope_sources[str(triage_scope.get("source") or "triage")] = triage_scope
                try:
                    if int(sev.get("critical", 0)) > 0:
                        notes.append("triage reports CRITICAL entries")
                except Exception:
                    pass

            dash = _read_json_from_zip(z, "dashboard/dashboard.json")
            if dash is not None:
                sections = list((dash.get("sections") or {}).keys()) if isinstance(dash.get("sections"), dict) else []
                signals["dashboard"] = {
                    "sections": sections,
                    "warnings": list(dash.get("warnings") or [])[:10],
                    "errors": list(dash.get("errors") or [])[:10],
                }
                anim_snap = annotate_anim_source_for_bundle(
                    extract_anim_snapshot(dash.get("anim_latest"), source="dashboard"),
                    name_set=name_set,
                )
                if anim_snap is not None:
                    anim_sources["dashboard"] = anim_snap
                dash_scope = extract_optimizer_scope_from_dashboard(dash)
                if dash_scope:
                    optimizer_scope_sources[str(dash_scope.get("source") or "dashboard")] = dash_scope

            for arcname in sorted(
                name
                for name in names
                if name == "run_scope.json" or name.endswith("/export/run_scope.json")
            ):
                export_scope = extract_optimizer_scope_from_run_scope(
                    _read_json_from_zip(z, arcname),
                    source=optimizer_scope_export_source_name(arcname),
                    source_path=arcname,
                )
                if export_scope:
                    optimizer_scope_sources[str(export_scope.get("source") or arcname)] = export_scope

            diag = _read_json_from_zip(z, ANIM_DIAG_JSON)
            if diag is not None:
                anim_snap = annotate_anim_source_for_bundle(
                    extract_anim_snapshot(diag, source="diagnostics"),
                    name_set=name_set,
                )
                if anim_snap is not None:
                    anim_sources["diagnostics"] = anim_snap

            local_ptr = _read_json_from_zip(z, ANIM_LOCAL_POINTER)
            if local_ptr is not None:
                anim_snap = annotate_anim_source_for_bundle(
                    extract_anim_snapshot(local_ptr, source="local_pointer"),
                    name_set=name_set,
                )
                if anim_snap is not None:
                    anim_sources["local_pointer"] = anim_snap

            global_ptr = _read_json_from_zip(z, ANIM_GLOBAL_POINTER)
            if global_ptr is not None:
                anim_snap = annotate_anim_source_for_bundle(
                    extract_anim_snapshot(global_ptr, source="global_pointer"),
                    name_set=name_set,
                )
                if anim_snap is not None:
                    anim_sources["global_pointer"] = anim_snap

            # Loglint strict (any source): collect totals and take worst.
            ll_names = _glob_zip_names(names, "/loglint_strict/loglint_report.json")
            if ll_names:
                totals = []
                for name in ll_names:
                    rep = _read_json_from_zip(z, name)
                    if not rep:
                        continue
                    totals.append(
                        {
                            "path": name,
                            "total_errors": int(rep.get("total_errors", 0) or 0),
                            "total_lines": int(rep.get("total_lines", 0) or 0),
                            "files_with_errors": int(rep.get("files_with_errors", 0) or 0),
                        }
                    )
                if totals:
                    worst = max(totals, key=lambda x: x.get("total_errors", 0))
                    signals["loglint_strict"] = {
                        "reports": totals,
                        "worst": worst,
                    }
                    if worst.get("total_errors", 0) > 0:
                        ok = False

            anim_summary = choose_anim_snapshot(
                anim_sources,
                preferred_order=("validation", "diagnostics", "local_pointer", "global_pointer", "dashboard"),
            )
            mnemo_event_log = summarize_mnemo_event_log(anim_summary)
            ring_closure = summarize_ring_closure(anim_summary)
            operator_recommendations = build_anim_operator_recommendations(anim_summary)
            anim_summary["mnemo_event_summary"] = dict(mnemo_event_log)
            anim_summary["ring_closure_summary"] = dict(ring_closure)
            optimizer_scope = compare_optimizer_scope_sources(
                optimizer_scope_sources,
                preferred_order=("triage", "health", "validation", "dashboard", "export"),
            )
            geometry_report_arc = "workspace/exports/geometry_acceptance_report.json"
            explicit_geometry_report = _read_json_from_zip(z, geometry_report_arc) if geometry_report_arc in name_set else None
            if explicit_geometry_report is not None:
                geom_acc = _normalize_geometry_acceptance_payload(
                    explicit_geometry_report,
                    source_path=geometry_report_arc,
                    source_kind="geometry_acceptance_report",
                )
                keep_ok, note = _geometry_acceptance_note(geom_acc, source_label=geometry_report_arc)
                ok = ok and keep_ok
                if note:
                    notes.append(note)
                signals["geometry_acceptance"] = geom_acc
                anim_summary["geometry_acceptance"] = geom_acc
            elif ANIM_LOCAL_NPZ in name_set:
                try:
                    with z.open(ANIM_LOCAL_NPZ, "r") as f:
                        raw_npz = f.read()
                    geom_acc, geom_err = _collect_geometry_acceptance_best_effort(raw_npz)
                    if geom_acc is not None:
                        geom_acc = _normalize_geometry_acceptance_payload(
                            dict(geom_acc),
                            source_path=ANIM_LOCAL_NPZ,
                            source_kind="npz_recomputed",
                        )
                        keep_ok, note = _geometry_acceptance_note(geom_acc, source_label="anim_latest.npz")
                        ok = ok and keep_ok
                        if note:
                            notes.append(note)
                    else:
                        geom_acc = {
                            "inspection_status": "missing",
                            "release_gate": "MISSING",
                            "release_gate_reason": str(geom_err or "geometry acceptance helper unavailable"),
                            "available": False,
                            "producer_owned": False,
                            "no_synthetic_geometry": False,
                            "error": str(geom_err or "geometry acceptance helper unavailable"),
                            "source_path": ANIM_LOCAL_NPZ,
                            "source_kind": "npz_recomputed",
                        }
                        notes.append(str(geom_acc["error"]))
                    signals["geometry_acceptance"] = geom_acc
                    anim_summary["geometry_acceptance"] = geom_acc
                except Exception as e:
                    geom_acc = {
                        "inspection_status": "missing",
                        "release_gate": "MISSING",
                        "release_gate_reason": f"failed to inspect anim_latest geometry acceptance: {type(e).__name__}: {e!s}",
                        "available": False,
                        "producer_owned": False,
                        "no_synthetic_geometry": False,
                        "error": f"failed to inspect anim_latest geometry acceptance: {type(e).__name__}: {e!s}",
                        "source_path": ANIM_LOCAL_NPZ,
                        "source_kind": "npz_recomputed",
                    }
                    signals["geometry_acceptance"] = geom_acc
                    anim_summary["geometry_acceptance"] = geom_acc
                    notes.append(str(geom_acc["error"]))
            if optimizer_scope:
                signals["optimizer_scope"] = dict(optimizer_scope)
                optimizer_scope_gate = evaluate_optimizer_scope_gate(optimizer_scope)
                signals["optimizer_scope_gate"] = dict(optimizer_scope_gate)
                for msg in optimizer_scope.get("issues") or []:
                    smsg = str(msg).strip()
                    if smsg and smsg not in notes:
                        notes.append(smsg)
                if optimizer_scope_gate.get("release_risk"):
                    risk_msg = (
                        "optimizer scope release risk: "
                        f"{optimizer_scope_gate.get('release_gate_reason') or 'mismatch detected'}"
                    )
                    if risk_msg not in notes:
                        notes.append(risk_msg)
            signals["anim_latest"] = anim_summary
            signals["mnemo_event_log"] = dict(mnemo_event_log)
            signals["ring_closure"] = dict(ring_closure)
            signals["operator_recommendations"] = list(operator_recommendations)
            perf_evidence_status = str(anim_summary.get("browser_perf_evidence_status") or "").strip()
            if perf_evidence_status and perf_evidence_status != "trace_bundle_ready":
                perf_note = (
                    "browser perf evidence is not trace_bundle_ready: "
                    f"{perf_evidence_status}"
                )
                if perf_note not in notes:
                    notes.append(perf_note)
            perf_compare_status = str(anim_summary.get("browser_perf_comparison_status") or "").strip()
            if perf_compare_status and perf_compare_status != "unchanged":
                perf_compare_note = (
                    "browser perf comparison status: "
                    f"{perf_compare_status}"
                )
                if perf_compare_note not in notes:
                    notes.append(perf_compare_note)
            for flag in mnemo_event_log.get("red_flags") or []:
                sflag = str(flag).strip()
                if sflag and sflag not in notes:
                    notes.append(sflag)
            if (
                str(mnemo_event_log.get("severity") or "") == "warn"
                and mnemo_event_log.get("headline")
            ):
                warn_note = str(mnemo_event_log.get("headline") or "").strip()
                if warn_note and warn_note not in notes:
                    notes.append(warn_note)
            for flag in ring_closure.get("red_flags") or []:
                sflag = str(flag).strip()
                if sflag and sflag not in notes:
                    notes.append(sflag)
            if (
                str(ring_closure.get("severity") or "") in ("warn", "critical")
                and ring_closure.get("headline")
            ):
                warn_note = str(ring_closure.get("headline") or "").strip()
                if warn_note and warn_note not in notes:
                    notes.append(warn_note)
            for msg in anim_summary.get("issues") or []:
                smsg = str(msg).strip()
                if smsg and smsg not in notes:
                    notes.append(smsg)

    except Exception as e:
        ok = False
        notes.append(f"failed to read zip: {type(e).__name__}: {e!s}")

    return HealthReport(
        schema="health_report",
        schema_version="1.5.0",
        created_at=created_at,
        zip_path=str(zip_path),
        ok=bool(ok),
        signals=signals,
        notes=notes,
    )


def render_health_report_md(rep: HealthReport) -> str:
    val = dict(rep.signals.get("validation") or {})
    anim = dict(rep.signals.get("anim_latest") or {})
    mnemo = dict(rep.signals.get("mnemo_event_log") or anim.get("mnemo_event_summary") or {})
    ring_closure = dict(rep.signals.get("ring_closure") or anim.get("ring_closure_summary") or {})
    operator_recommendations = [str(x) for x in (rep.signals.get("operator_recommendations") or []) if str(x).strip()]
    artifacts = dict(rep.signals.get("artifacts") or {})
    evidence_manifest = dict(rep.signals.get("evidence_manifest") or {})
    latest_proof = dict(rep.signals.get("latest_integrity_proof") or {})
    self_check_snapshot = dict(rep.signals.get("self_check_silent_warnings") or {})
    engineering = dict(rep.signals.get("engineering_analysis_evidence") or {})
    optimizer_scope = dict(rep.signals.get("optimizer_scope") or {})
    optimizer_scope_gate = dict(rep.signals.get("optimizer_scope_gate") or {})
    reload_inputs = list(anim.get("visual_reload_inputs") or [])
    lines = [
        "# Health report",
        "",
        f"- Created: {rep.created_at}",
        f"- ZIP: `{Path(rep.zip_path).name}`",
        f"- OK: **{rep.ok}**",
        "",
        "## Artifacts",
        f"- validation_report: {artifacts.get('validation_report')}",
        f"- dashboard_report: {artifacts.get('dashboard_report')}",
        f"- triage_report: {artifacts.get('triage_report')}",
        f"- anim_diagnostics: {artifacts.get('anim_diagnostics')}",
        f"- evidence_manifest: {artifacts.get('evidence_manifest')}",
        f"- engineering_analysis_evidence: {artifacts.get('engineering_analysis_evidence')}",
        f"- health_report_embedded: {artifacts.get('health_report_embedded')}",
        f"- browser_perf_registry_snapshot: {artifacts.get('browser_perf_registry_snapshot')}",
        f"- browser_perf_previous_snapshot: {artifacts.get('browser_perf_previous_snapshot')}",
        f"- browser_perf_contract: {artifacts.get('browser_perf_contract')}",
        f"- browser_perf_evidence_report: {artifacts.get('browser_perf_evidence_report')}",
        f"- browser_perf_comparison_report: {artifacts.get('browser_perf_comparison_report')}",
        f"- browser_perf_trace: {artifacts.get('browser_perf_trace')}",
        f"- self_check_silent_warnings: {artifacts.get('self_check_silent_warnings')}",
    ]

    if latest_proof:
        lines += [
            "",
            "## Latest integrity proof",
            f"- status: `{latest_proof.get('status') or 'MISSING'}`",
            f"- final_latest_zip_sha256: `{latest_proof.get('final_latest_zip_sha256') or '—'}`",
            f"- final_original_zip_sha256: `{latest_proof.get('final_original_zip_sha256') or '—'}`",
            f"- latest_sha_sidecar_matches: {latest_proof.get('latest_sha_sidecar_matches')}",
            f"- latest_pointer_matches_original: {latest_proof.get('latest_pointer_matches_original')}",
            f"- embedded_manifest_zip_sha256_scope: `{latest_proof.get('embedded_manifest_zip_sha256_scope') or '—'}`",
            f"- embedded_manifest_stage: `{latest_proof.get('embedded_manifest_stage') or '—'}`",
            f"- trigger: `{latest_proof.get('trigger') or '—'}`",
            f"- collection_mode: `{latest_proof.get('collection_mode') or '—'}`",
            f"- producer_warning_count: {latest_proof.get('producer_warning_count')}",
            f"- warning_only_gaps_present: {latest_proof.get('warning_only_gaps_present')}",
            f"- no_release_closure_claim: {latest_proof.get('no_release_closure_claim')}",
        ]
        for msg in [str(x) for x in (latest_proof.get("warnings") or []) if str(x).strip()][:5]:
            lines.append(f"- warning: {msg}")

    if self_check_snapshot:
        lines += [
            "",
            "## Self-check silent warnings snapshot",
            f"- status: `{self_check_snapshot.get('status') or 'MISSING'}`",
            f"- snapshot_only: {self_check_snapshot.get('snapshot_only')}",
            f"- does_not_close_producer_warnings: {self_check_snapshot.get('does_not_close_producer_warnings')}",
            f"- source_path: `{self_check_snapshot.get('source_path') or '—'}`",
            f"- rc: {self_check_snapshot.get('rc')}",
            f"- fail_count: {self_check_snapshot.get('fail_count')}",
            f"- warn_count: {self_check_snapshot.get('warn_count')}",
        ]

    if evidence_manifest:
        analysis_handoff = dict(evidence_manifest.get("analysis_handoff") or {})
        missing_warnings = [str(x) for x in (evidence_manifest.get("missing_warnings") or []) if str(x).strip()]
        lines += [
            "",
            "## Evidence manifest",
            f"- collection_mode: `{evidence_manifest.get('collection_mode') or '—'}`",
            f"- trigger: `{evidence_manifest.get('trigger') or '—'}`",
            f"- evidence_manifest_hash: `{evidence_manifest.get('evidence_manifest_hash') or '—'}`",
            f"- stage: `{evidence_manifest.get('finalization_stage') or evidence_manifest.get('stage') or '—'}`",
            f"- zip_sha256: `{evidence_manifest.get('zip_sha256') or '—'}`",
            f"- pb002_missing_required_count: `{evidence_manifest.get('pb002_missing_required_count')}`",
            f"- missing_required_count: `{evidence_manifest.get('missing_required_count')}`",
            f"- missing_optional_count: `{evidence_manifest.get('missing_optional_count')}`",
            f"- analysis_handoff: `{analysis_handoff.get('status') or 'MISSING'}` / context=`{analysis_handoff.get('result_context_state') or 'MISSING'}`",
        ]
        for msg in missing_warnings[:10]:
            lines.append(f"- missing_evidence: {msg}")

    if val:
        lines += [
            "",
            "## Validation",
            f"- ok: {val.get('ok')}",
            f"- errors_count: {val.get('errors_count')}",
            f"- warnings_count: {val.get('warnings_count')}",
        ]

    if engineering:
        lines += [
            "",
            "## Engineering analysis evidence",
            f"- status: {engineering.get('status') or 'MISSING'}",
            f"- source_path: {engineering.get('source_path') or '—'}",
            f"- evidence_manifest_hash: {engineering.get('evidence_manifest_hash') or '—'}",
            f"- analysis_status: {engineering.get('analysis_status') or '—'}",
            f"- influence_status: {engineering.get('influence_status') or '—'}",
            f"- calibration_status: {engineering.get('calibration_status') or '—'}",
            f"- sensitivity_row_count: {engineering.get('sensitivity_row_count')}",
        ]
        requirements = dict(engineering.get("handoff_requirements") or {})
        if requirements:
            lines += [
                f"- handoff_contract_status: {requirements.get('contract_status') or '—'}",
                f"- handoff_required_path: `{requirements.get('required_contract_path') or '—'}`",
                f"- handoff_missing_fields: {', '.join(str(x) for x in (requirements.get('missing_fields') or [])) or '—'}",
            ]
        readiness = dict(engineering.get("selected_run_candidate_readiness") or {})
        if readiness:
            lines += [
                f"- selected_run_candidate_count: {engineering.get('selected_run_candidate_count')}",
                f"- selected_run_ready_candidate_count: {engineering.get('selected_run_ready_candidate_count')}",
                f"- selected_run_missing_inputs_candidate_count: {engineering.get('selected_run_missing_inputs_candidate_count')}",
            ]

    if optimizer_scope:
        lines += [
            "",
            "## Distributed optimization",
            f"- status: {optimizer_scope.get('status') or '—'}",
            f"- scope_gate: `{optimizer_scope_gate.get('release_gate') or '—'}`",
            f"- scope_gate_reason: `{optimizer_scope_gate.get('release_gate_reason') or '—'}`",
            f"- scope_release_risk: `{optimizer_scope_gate.get('release_risk')}`",
            (
                f"- progress: completed={optimizer_scope.get('completed')} / in_flight={optimizer_scope.get('in_flight')} "
                f"/ cached={optimizer_scope.get('cached_hits')} / duplicates={optimizer_scope.get('duplicates_skipped')}"
            ),
            f"- Problem scope: `{optimizer_scope.get('problem_hash_short') or optimizer_scope.get('problem_hash') or '—'}`",
            f"- Hash mode: `{optimizer_scope.get('problem_hash_mode') or '—'}`",
        ]
        full_problem_hash = str(optimizer_scope.get("problem_hash") or "")
        short_problem_hash = str(optimizer_scope.get("problem_hash_short") or "")
        if full_problem_hash and short_problem_hash and full_problem_hash != short_problem_hash:
            lines.append(f"- problem_hash: `{full_problem_hash}`")
        lines.append(f"- scope_sync_ok: `{optimizer_scope.get('scope_sync_ok')}`")
        for issue in list(optimizer_scope.get("issues") or [])[:5]:
            lines.append(f"- scope_issue: {issue}")

    if anim:
        lines += [
            "",
            "## Anim latest diagnostics",
            f"- source: {anim.get('source') or '—'}",
            f"- available: {anim.get('available')}",
            f"- visual_cache_token: `{anim.get('visual_cache_token') or '—'}`",
            f"- visual_reload_inputs: {', '.join(str(x) for x in reload_inputs) if reload_inputs else '—'}",
            f"- pointer_sync_ok: {anim.get('pointer_sync_ok')}",
            f"- reload_inputs_sync_ok: {anim.get('reload_inputs_sync_ok')}",
            f"- npz_path_sync_ok: {anim.get('npz_path_sync_ok')}",
            f"- npz_path: `{anim.get('npz_path') or '—'}`",
            f"- updated_utc: {anim.get('updated_utc') or '—'}",
            f"- scenario_kind: {anim.get('scenario_kind') or '—'}",
            f"- ring_closure: policy={anim.get('ring_closure_policy') or '—'} / applied={anim.get('ring_closure_applied')} / seam_open={anim.get('ring_seam_open')} / seam_max_jump_m={anim.get('ring_seam_max_jump_m')} / raw_seam_max_jump_m={anim.get('ring_raw_seam_max_jump_m')}",
            f"- usable_from_bundle: {anim.get('usable_from_bundle')}",
            f"- pointer_json_in_bundle: {anim.get('pointer_json_in_bundle')}",
            f"- npz_path_in_bundle: {anim.get('npz_path_in_bundle')}",
            f"- browser_perf_status: {anim.get('browser_perf_status') or '—'} / level={anim.get('browser_perf_level') or '—'}",
            f"- browser_perf_evidence_status: {anim.get('browser_perf_evidence_status') or '—'} / level={anim.get('browser_perf_evidence_level') or '—'}",
            f"- browser_perf_bundle_ready: {anim.get('browser_perf_bundle_ready')}",
            f"- browser_perf_snapshot_contract_match: {anim.get('browser_perf_snapshot_contract_match')}",
            f"- browser_perf_comparison_status: {anim.get('browser_perf_comparison_status') or '—'} / level={anim.get('browser_perf_comparison_level') or '—'}",
            f"- browser_perf_comparison_ready: {anim.get('browser_perf_comparison_ready')}",
            f"- browser_perf_comparison_changed: {anim.get('browser_perf_comparison_changed')}",
            f"- browser_perf_comparison_delta_total_wakeups: {anim.get('browser_perf_comparison_delta_total_wakeups')}",
            f"- browser_perf_comparison_delta_total_duplicate_guard_hits: {anim.get('browser_perf_comparison_delta_total_duplicate_guard_hits')}",
        ]
        anim_issues = list(anim.get("issues") or [])
        if anim_issues:
            lines += ["", "### Anim latest issues"] + [f"- {x}" for x in anim_issues]
    if ring_closure:
        lines += [
            "",
            "## Ring closure",
            f"- severity: {ring_closure.get('severity') or 'missing'}",
            f"- summary: {ring_closure.get('headline') or '—'}",
            f"- policy: {ring_closure.get('closure_policy') or '—'} / applied={ring_closure.get('closure_applied')} / seam_open={ring_closure.get('seam_open')}",
            f"- seam_jump_m: cooked={ring_closure.get('seam_max_jump_m')} / raw={ring_closure.get('raw_seam_max_jump_m')}",
        ]
        for flag in list(ring_closure.get("red_flags") or [])[:3]:
            lines.append(f"- red_flag: {flag}")

    if mnemo:
        lines += [
            "",
            "## Desktop Mnemo events",
            f"- severity: {mnemo.get('severity') or 'missing'}",
            f"- summary: {mnemo.get('headline') or '—'}",
            f"- event_log: {mnemo.get('ref') or '—'} / exists={mnemo.get('exists')} / schema={mnemo.get('schema_version') or '—'} / updated_utc={mnemo.get('updated_utc') or '—'}",
            f"- current_mode: {mnemo.get('current_mode') or '—'}",
            f"- event_state: total={mnemo.get('event_count')} / active={mnemo.get('active_latch_count')} / acked={mnemo.get('acknowledged_latch_count')}",
        ]
        recent_titles = [str(x) for x in (mnemo.get("recent_titles") or []) if str(x).strip()]
        if recent_titles:
            lines.append(f"- recent_titles: {' | '.join(recent_titles[:3])}")
        for flag in list(mnemo.get("red_flags") or [])[:3]:
            lines.append(f"- red_flag: {flag}")

    if operator_recommendations:
        lines += ["", "## Recommended actions"] + [f"{idx}. {item}" for idx, item in enumerate(operator_recommendations, start=1)]

    geom = dict(rep.signals.get("geometry_acceptance") or {})
    if geom:
        lines += ["", "## Geometry acceptance"] + _format_geometry_acceptance_summary_lines_best_effort(geom)

    lines += [
        "",
        "## Signals",
        "```json",
        json.dumps(rep.signals, ensure_ascii=False, indent=2),
        "```",
    ]
    if rep.notes:
        lines += ["", "## Notes"] + [f"- {n}" for n in rep.notes]
    return "\n".join(lines) + "\n"


def build_health_report(
    zip_path: Path,
    *,
    out_dir: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[Path]]:
    zip_path = Path(zip_path).resolve()
    out_dir = Path(out_dir).resolve() if out_dir else zip_path.parent.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rep = collect_health_report(zip_path)

    json_path = out_dir / "latest_health_report.json"
    md_path = out_dir / "latest_health_report.md"

    try:
        json_path.write_text(json.dumps(asdict(rep), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        json_path = None

    try:
        md_path.write_text(render_health_report_md(rep), encoding="utf-8")
    except Exception:
        md_path = None

    return json_path, md_path


def add_health_report_to_zip(zip_path: Path, json_path: Optional[Path], md_path: Optional[Path]) -> None:
    """Append health report files into existing ZIP (best-effort)."""
    try:
        with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            if json_path and json_path.exists():
                z.write(json_path, arcname="health/health_report.json")
            if md_path and md_path.exists():
                z.write(md_path, arcname="health/health_report.md")
    except Exception:
        return
