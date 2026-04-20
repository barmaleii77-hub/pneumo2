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
        return None, f"проверка геометрии недоступна: {type(e).__name__}: {e!s}"

    try:
        rep = collect(raw_npz)
        if isinstance(rep, dict):
            return dict(rep), None
        return None, "проверка геометрии вернула неожиданный формат результата"
    except Exception as e:
        return None, f"не удалось проверить геометрию последней анимации: {type(e).__name__}: {e!s}"


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
        return False, f"проверка геометрии: FAIL для {source_label}{suffix}"
    if gate == "WARN":
        return True, f"проверка геометрии: WARN для {source_label}{suffix}"
    if gate == "MISSING":
        return True, f"проверка геометрии: MISSING для {source_label}{suffix}"
    return True, ""


def _format_geometry_acceptance_summary_lines_best_effort(geom: Dict[str, Any]) -> List[str]:
    gate = str(geom.get("release_gate") or "MISSING")
    reason = str(geom.get("release_gate_reason") or geom.get("error") or "—")
    lines = [
        f"- Состояние проверки: {geom.get('inspection_status') or 'missing'}",
        f"- Допуск геометрии: {gate}",
        f"- Причина допуска: {reason}",
        f"- Данные получены из расчёта: {geom.get('producer_owned')}",
        f"- Без синтетической геометрии: {geom.get('no_synthetic_geometry')}",
    ]
    missing = [str(x) for x in (geom.get("missing_fields") or []) if str(x).strip()]
    if missing:
        lines.append(f"- Не хватает полей: {', '.join(missing[:8])}")
    warnings = [str(x) for x in (geom.get("warnings") or []) if str(x).strip()]
    for warning in warnings[:5]:
        lines.append(f"- Предупреждение: {warning}")
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
                notes.append(f"не удалось проверить состав данных: {type(exc).__name__}: {exc!s}")

            self_check_snapshot = _read_json_from_zip(z, "reports/SELF_CHECK_SILENT_WARNINGS.json")
            signals["self_check_silent_warnings"] = _summarize_self_check_silent_warnings_snapshot(
                self_check_snapshot,
                source_path="reports/SELF_CHECK_SILENT_WARNINGS.json" if self_check_snapshot else "",
            )
            if signals["self_check_silent_warnings"].get("status") == "WARN":
                notes.append(
                    "Снимок тихих предупреждений самопроверки содержит WARN/FAIL; этого снимка недостаточно для закрытия предупреждений источника."
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
                        read_warnings=(f"{engineering_name}: некорректный JSON",),
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
                        notes.append("в разборе замечаний есть критические записи")
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
                            "release_gate_reason": str(geom_err or "проверка геометрии недоступна"),
                            "available": False,
                            "producer_owned": False,
                            "no_synthetic_geometry": False,
                            "error": str(geom_err or "проверка геометрии недоступна"),
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
                        "release_gate_reason": f"не удалось проверить геометрию последней анимации: {type(e).__name__}: {e!s}",
                        "available": False,
                        "producer_owned": False,
                        "no_synthetic_geometry": False,
                        "error": f"не удалось проверить геометрию последней анимации: {type(e).__name__}: {e!s}",
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
                        "риск выпуска по области оптимизации: "
                        f"{optimizer_scope_gate.get('release_gate_reason') or 'обнаружено расхождение'}"
                    )
                    if risk_msg not in notes:
                        notes.append(risk_msg)
            signals["anim_latest"] = anim_summary
            signals["mnemo_event_log"] = dict(mnemo_event_log)
            signals["ring_closure"] = dict(ring_closure)
            engineering_signal = dict(signals.get("engineering_analysis_evidence") or {})
            if str(engineering_signal.get("open_gap_status") or "").upper() == "OPEN":
                reasons = [
                    str(item).strip()
                    for item in (engineering_signal.get("open_gap_reasons") or [])
                    if str(item).strip()
                ]
                recommendation = (
                    "Закройте открытые вопросы инженерного анализа перед подтверждением готовности архива проекта: "
                    + (", ".join(reasons[:4]) if reasons else "готовность неясна")
                    + "."
                )
                if recommendation not in operator_recommendations:
                    operator_recommendations.append(recommendation)
            signals["operator_recommendations"] = list(operator_recommendations)
            perf_evidence_status = str(anim_summary.get("browser_perf_evidence_status") or "").strip()
            if perf_evidence_status and perf_evidence_status != "trace_bundle_ready":
                perf_note = (
                    "данные производительности анимации не готовы к восстановлению из архива: "
                    f"{perf_evidence_status}"
                )
                if perf_note not in notes:
                    notes.append(perf_note)
            perf_compare_status = str(anim_summary.get("browser_perf_comparison_status") or "").strip()
            if perf_compare_status and perf_compare_status != "unchanged":
                perf_compare_note = (
                    "состояние сравнения производительности анимации: "
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
        notes.append(f"не удалось прочитать ZIP: {type(e).__name__}: {e!s}")

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
        "# Отчёт о состоянии проекта",
        "",
        f"- Сформировано: {rep.created_at}",
        f"- Архив: `{Path(rep.zip_path).name}`",
        f"- Успешно: **{rep.ok}**",
        "",
        "## Состав архива",
        f"- Отчёт проверки: {artifacts.get('validation_report')}",
        f"- Сводный HTML-отчёт: {artifacts.get('dashboard_report')}",
        f"- Разбор замечаний: {artifacts.get('triage_report')}",
        f"- Данные последней анимации: {artifacts.get('anim_diagnostics')}",
        f"- Состав данных: {artifacts.get('evidence_manifest')}",
        f"- Данные инженерного анализа: {artifacts.get('engineering_analysis_evidence')}",
        f"- Отчёт состояния внутри архива: {artifacts.get('health_report_embedded')}",
        f"- Снимок производительности анимации: {artifacts.get('browser_perf_registry_snapshot')}",
        f"- Предыдущий снимок производительности: {artifacts.get('browser_perf_previous_snapshot')}",
        f"- Условия проверки производительности: {artifacts.get('browser_perf_contract')}",
        f"- Отчёт производительности: {artifacts.get('browser_perf_evidence_report')}",
        f"- Сравнение производительности: {artifacts.get('browser_perf_comparison_report')}",
        f"- Трасса производительности: {artifacts.get('browser_perf_trace')}",
        f"- Тихие предупреждения самопроверки: {artifacts.get('self_check_silent_warnings')}",
    ]

    if latest_proof:
        lines += [
            "",
            "## Проверка актуального архива",
            f"- Состояние: `{latest_proof.get('status') or 'MISSING'}`",
            f"- SHA актуального архива: `{latest_proof.get('final_latest_zip_sha256') or '—'}`",
            f"- SHA исходного архива: `{latest_proof.get('final_original_zip_sha256') or '—'}`",
            f"- SHA-файл совпадает: {latest_proof.get('latest_sha_sidecar_matches')}",
            f"- Указатель ведёт на исходный архив: {latest_proof.get('latest_pointer_matches_original')}",
            f"- Область SHA состава данных: `{latest_proof.get('embedded_manifest_zip_sha256_scope') or '—'}`",
            f"- Этап состава данных: `{latest_proof.get('embedded_manifest_stage') or '—'}`",
            f"- Причина запуска: `{latest_proof.get('trigger') or '—'}`",
            f"- Режим сбора: `{latest_proof.get('collection_mode') or '—'}`",
            f"- Предупреждений источников данных: {latest_proof.get('producer_warning_count')}",
            f"- Есть предупреждающие разрывы: {latest_proof.get('warning_only_gaps_present')}",
            f"- Финальное закрытие не заявлено: {latest_proof.get('no_release_closure_claim')}",
        ]
        for msg in [str(x) for x in (latest_proof.get("warnings") or []) if str(x).strip()][:5]:
            lines.append(f"- предупреждение: {msg}")

    if self_check_snapshot:
        lines += [
            "",
            "## Тихие предупреждения самопроверки",
            f"- Состояние: `{self_check_snapshot.get('status') or 'MISSING'}`",
            f"- Только снимок: {self_check_snapshot.get('snapshot_only')}",
            f"- Не закрывает предупреждения источников: {self_check_snapshot.get('does_not_close_producer_warnings')}",
            f"- Источник: `{self_check_snapshot.get('source_path') or '—'}`",
            f"- rc: {self_check_snapshot.get('rc')}",
            f"- Ошибок: {self_check_snapshot.get('fail_count')}",
            f"- Предупреждений: {self_check_snapshot.get('warn_count')}",
        ]

    if evidence_manifest:
        analysis_handoff = dict(evidence_manifest.get("analysis_handoff") or {})
        missing_warnings = [str(x) for x in (evidence_manifest.get("missing_warnings") or []) if str(x).strip()]
        lines += [
            "",
            "## Состав данных",
            f"- Режим сбора: `{evidence_manifest.get('collection_mode') or '—'}`",
            f"- Причина запуска: `{evidence_manifest.get('trigger') or '—'}`",
            f"- Метка состава данных: `{evidence_manifest.get('evidence_manifest_hash') or '—'}`",
            f"- Этап: `{evidence_manifest.get('finalization_stage') or evidence_manifest.get('stage') or '—'}`",
            f"- zip_sha256: `{evidence_manifest.get('zip_sha256') or '—'}`",
            f"- Не хватает обязательных данных PB002: `{evidence_manifest.get('pb002_missing_required_count')}`",
            f"- Не хватает обязательных данных: `{evidence_manifest.get('missing_required_count')}`",
            f"- Не хватает необязательных данных: `{evidence_manifest.get('missing_optional_count')}`",
            f"- Передача результата анализа: `{analysis_handoff.get('status') or 'MISSING'}` / данные=`{analysis_handoff.get('result_context_state') or 'MISSING'}`",
        ]
        for msg in missing_warnings[:10]:
            lines.append(f"- Нет данных: {msg}")

    if val:
        lines += [
            "",
            "## Проверка архива",
            f"- Успешно: {val.get('ok')}",
            f"- Ошибок: {val.get('errors_count')}",
            f"- Предупреждений: {val.get('warnings_count')}",
        ]

    if engineering:
        lines += [
            "",
            "## Данные инженерного анализа",
            f"- Состояние: {engineering.get('status') or 'MISSING'}",
            f"- Готовность: {engineering.get('readiness_status') or 'MISSING'}",
            f"- Открытые вопросы: {engineering.get('open_gap_status') or 'MISSING'}",
            f"- Финальное закрытие не заявлено: {engineering.get('no_release_closure_claim')}",
            f"- Источник: {engineering.get('source_path') or '—'}",
            f"- Метка состава данных: {engineering.get('evidence_manifest_hash') or '—'}",
            f"- Анализ: {engineering.get('analysis_status') or '—'}",
            f"- Влияние: {engineering.get('influence_status') or '—'}",
            f"- Калибровка: {engineering.get('calibration_status') or '—'}",
            f"- Строк чувствительности: {engineering.get('sensitivity_row_count')}",
        ]
        open_gap_reasons = [
            str(item).strip()
            for item in (engineering.get("open_gap_reasons") or [])
            if str(item).strip()
        ]
        if open_gap_reasons:
            lines.append(f"- Причины открытых вопросов: {', '.join(open_gap_reasons[:8])}")
        requirements = dict(engineering.get("handoff_requirements") or {})
        if requirements:
            lines += [
                f"- Состояние передачи данных: {requirements.get('contract_status') or '—'}",
                f"- Обязательный файл передачи: `{requirements.get('required_contract_path') or '—'}`",
                f"- Не хватает полей передачи: {', '.join(str(x) for x in (requirements.get('missing_fields') or [])) or '—'}",
            ]
        readiness = dict(engineering.get("selected_run_candidate_readiness") or {})
        if readiness:
            lines += [
                f"- Кандидатов выбранного запуска: {engineering.get('selected_run_candidate_count')}",
                f"- Готовых кандидатов: {engineering.get('selected_run_ready_candidate_count')}",
                f"- Кандидатов без входных данных: {engineering.get('selected_run_missing_inputs_candidate_count')}",
            ]

    if optimizer_scope:
        lines += [
            "",
            "## Оптимизация",
            f"- Состояние: {optimizer_scope.get('status') or '—'}",
            f"- Допуск области: `{optimizer_scope_gate.get('release_gate') or '—'}`",
            f"- Причина допуска: `{optimizer_scope_gate.get('release_gate_reason') or '—'}`",
            f"- Риск выпуска: `{optimizer_scope_gate.get('release_risk')}`",
            (
                f"- Ход расчёта: завершено={optimizer_scope.get('completed')} / выполняется={optimizer_scope.get('in_flight')} "
                f"/ из кэша={optimizer_scope.get('cached_hits')} / пропущено дублей={optimizer_scope.get('duplicates_skipped')}"
            ),
            f"- Область задачи: `{optimizer_scope.get('problem_hash_short') or optimizer_scope.get('problem_hash') or '—'}`",
            f"- Режим хэша: `{optimizer_scope.get('problem_hash_mode') or '—'}`",
        ]
        full_problem_hash = str(optimizer_scope.get("problem_hash") or "")
        short_problem_hash = str(optimizer_scope.get("problem_hash_short") or "")
        if full_problem_hash and short_problem_hash and full_problem_hash != short_problem_hash:
            lines.append(f"- Полный ключ области: `{full_problem_hash}`")
        lines.append(f"- Синхронизация области: `{optimizer_scope.get('scope_sync_ok')}`")
        for issue in list(optimizer_scope.get("issues") or [])[:5]:
            lines.append(f"- Замечание области: {issue}")

    if anim:
        lines += [
            "",
            "## Последняя анимация",
            f"- Источник: {anim.get('source') or '—'}",
            f"- Доступна: {anim.get('available')}",
            f"- Токен визуального кэша: `{anim.get('visual_cache_token') or '—'}`",
            f"- Входные данные перезагрузки: {', '.join(str(x) for x in reload_inputs) if reload_inputs else '—'}",
            f"- Указатель синхронизирован: {anim.get('pointer_sync_ok')}",
            f"- Входные данные синхронизированы: {anim.get('reload_inputs_sync_ok')}",
            f"- Файл анимации синхронизирован: {anim.get('npz_path_sync_ok')}",
            f"- Файл анимации: `{anim.get('npz_path') or '—'}`",
            f"- Обновлено UTC: {anim.get('updated_utc') or '—'}",
            f"- Тип сценария: {anim.get('scenario_kind') or '—'}",
            f"- Замыкание кольца: режим={anim.get('ring_closure_policy') or '—'} / применено={anim.get('ring_closure_applied')} / шов открыт={anim.get('ring_seam_open')} / скачок шва, м={anim.get('ring_seam_max_jump_m')} / исходный скачок, м={anim.get('ring_raw_seam_max_jump_m')}",
            f"- Восстанавливается из архива: {anim.get('usable_from_bundle')}",
            f"- Указатель есть в архиве: {anim.get('pointer_json_in_bundle')}",
            f"- Файл анимации есть в архиве: {anim.get('npz_path_in_bundle')}",
            f"- Состояние производительности: {anim.get('browser_perf_status') or '—'} / уровень={anim.get('browser_perf_level') or '—'}",
            f"- Данные производительности: {anim.get('browser_perf_evidence_status') or '—'} / уровень={anim.get('browser_perf_evidence_level') or '—'}",
            f"- Данные производительности в архиве: {anim.get('browser_perf_bundle_ready')}",
            f"- Снимок производительности совпадает с условиями: {anim.get('browser_perf_snapshot_contract_match')}",
            f"- Состояние сравнения производительности: {anim.get('browser_perf_comparison_status') or '—'} / уровень={anim.get('browser_perf_comparison_level') or '—'}",
            f"- Сравнение производительности готово: {anim.get('browser_perf_comparison_ready')}",
            f"- Сравнение изменилось: {anim.get('browser_perf_comparison_changed')}",
            f"- Изменение пробуждений: {anim.get('browser_perf_comparison_delta_total_wakeups')}",
            f"- Изменение защиты от дублей: {anim.get('browser_perf_comparison_delta_total_duplicate_guard_hits')}",
        ]
        anim_issues = list(anim.get("issues") or [])
        if anim_issues:
            lines += ["", "### Замечания по последней анимации"] + [f"- {x}" for x in anim_issues]
    if ring_closure:
        lines += [
            "",
            "## Замыкание кольца",
            f"- Важность: {ring_closure.get('severity') or 'missing'}",
            f"- Сводка: {ring_closure.get('headline') or '—'}",
            f"- Режим: {ring_closure.get('closure_policy') or '—'} / применено={ring_closure.get('closure_applied')} / шов открыт={ring_closure.get('seam_open')}",
            f"- Скачок шва, м: обработанный={ring_closure.get('seam_max_jump_m')} / исходный={ring_closure.get('raw_seam_max_jump_m')}",
        ]
        for flag in list(ring_closure.get("red_flags") or [])[:3]:
            lines.append(f"- Предупреждение: {flag}")

    if mnemo:
        lines += [
            "",
            "## События мнемосхемы",
            f"- Важность: {mnemo.get('severity') or 'missing'}",
            f"- Сводка: {mnemo.get('headline') or '—'}",
            f"- Журнал событий: {mnemo.get('ref') or '—'} / есть={mnemo.get('exists')} / схема={mnemo.get('schema_version') or '—'} / обновлено UTC={mnemo.get('updated_utc') or '—'}",
            f"- Текущий режим: {mnemo.get('current_mode') or '—'}",
            f"- Состояние событий: всего={mnemo.get('event_count')} / активно={mnemo.get('active_latch_count')} / принято={mnemo.get('acknowledged_latch_count')}",
        ]
        recent_titles = [str(x) for x in (mnemo.get("recent_titles") or []) if str(x).strip()]
        if recent_titles:
            lines.append(f"- Последние события: {' | '.join(recent_titles[:3])}")
        for flag in list(mnemo.get("red_flags") or [])[:3]:
            lines.append(f"- Предупреждение: {flag}")

    if operator_recommendations:
        lines += ["", "## Рекомендуемые действия"] + [f"{idx}. {item}" for idx, item in enumerate(operator_recommendations, start=1)]

    geom = dict(rep.signals.get("geometry_acceptance") or {})
    if geom:
        lines += ["", "## Проверка геометрии"] + _format_geometry_acceptance_summary_lines_best_effort(geom)

    lines += [
        "",
        "## Машиночитаемые данные",
        "```json",
        json.dumps(rep.signals, ensure_ascii=False, indent=2),
        "```",
    ]
    if rep.notes:
        lines += ["", "## Примечания"] + [f"- {n}" for n in rep.notes]
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
