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


def _glob_zip_names(names: List[str], suffix: str) -> List[str]:
    return [n for n in names if n.endswith(suffix)]




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


def _format_geometry_acceptance_summary_lines_best_effort(geom: Dict[str, Any]) -> List[str]:
    try:
        mod = importlib.import_module("pneumo_solver_ui.geometry_acceptance_contract")
        fmt = getattr(mod, "format_geometry_acceptance_summary_lines")
        lines = fmt(geom)
        return [str(x) for x in lines]
    except Exception:
        gate = str(geom.get("release_gate") or geom.get("inspection_status") or "—")
        reason = str(geom.get("release_gate_reason") or geom.get("error") or "—")
        return [f"- gate: {gate}", f"- reason: {reason}"]


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
                "health_report_embedded": "health/health_report.json" in name_set or "health/health_report.md" in name_set,
                "browser_perf_registry_snapshot": f"workspace/exports/{BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME}" in name_set,
                "browser_perf_previous_snapshot": f"workspace/exports/{BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME}" in name_set,
                "browser_perf_contract": f"workspace/exports/{BROWSER_PERF_CONTRACT_JSON_NAME}" in name_set,
                "browser_perf_evidence_report": f"workspace/exports/{BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME}" in name_set,
                "browser_perf_comparison_report": f"workspace/exports/{BROWSER_PERF_COMPARISON_REPORT_JSON_NAME}" in name_set,
                "browser_perf_trace": any(f"workspace/exports/{name}" in name_set for name in BROWSER_PERF_TRACE_CANDIDATE_NAMES),
            }

            meta = _read_json_from_zip(z, "bundle/meta.json")
            if meta is not None:
                signals["meta"] = {
                    "release": meta.get("release"),
                    "run_id": meta.get("run_id"),
                    "created_at": meta.get("created_at"),
                }

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
            if ANIM_LOCAL_NPZ in name_set:
                try:
                    with z.open(ANIM_LOCAL_NPZ, "r") as f:
                        raw_npz = f.read()
                    geom_acc, geom_err = _collect_geometry_acceptance_best_effort(raw_npz)
                    if geom_acc is not None:
                        geom_acc = dict(geom_acc)
                        geom_acc["inspection_status"] = "ok"
                        ga_gate = str(geom_acc.get("release_gate") or "MISSING")
                        if ga_gate == "FAIL":
                            ok = False
                            notes.append(f"geometry acceptance gate=FAIL for anim_latest.npz: {geom_acc.get('release_gate_reason') or ''}")
                        elif ga_gate == "WARN":
                            notes.append(f"geometry acceptance gate=WARN for anim_latest.npz: {geom_acc.get('release_gate_reason') or ''}")
                    else:
                        geom_acc = {
                            "inspection_status": "unavailable",
                            "error": str(geom_err or "geometry acceptance helper unavailable"),
                        }
                        notes.append(str(geom_acc["error"]))
                    signals["geometry_acceptance"] = geom_acc
                    anim_summary["geometry_acceptance"] = geom_acc
                except Exception as e:
                    geom_acc = {
                        "inspection_status": "unavailable",
                        "error": f"failed to inspect anim_latest geometry acceptance: {type(e).__name__}: {e!s}",
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
        f"- health_report_embedded: {artifacts.get('health_report_embedded')}",
        f"- browser_perf_registry_snapshot: {artifacts.get('browser_perf_registry_snapshot')}",
        f"- browser_perf_previous_snapshot: {artifacts.get('browser_perf_previous_snapshot')}",
        f"- browser_perf_contract: {artifacts.get('browser_perf_contract')}",
        f"- browser_perf_evidence_report: {artifacts.get('browser_perf_evidence_report')}",
        f"- browser_perf_comparison_report: {artifacts.get('browser_perf_comparison_report')}",
        f"- browser_perf_trace: {artifacts.get('browser_perf_trace')}",
    ]

    if val:
        lines += [
            "",
            "## Validation",
            f"- ok: {val.get('ok')}",
            f"- errors_count: {val.get('errors_count')}",
            f"- warnings_count: {val.get('warnings_count')}",
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
