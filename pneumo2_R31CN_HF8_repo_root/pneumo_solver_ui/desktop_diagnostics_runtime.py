# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Optional

from pneumo_solver_ui.diagnostics_entrypoint import (
    load_diagnostics_config,
    read_last_meta_from_out_dir,
    summarize_last_bundle_meta,
)
from pneumo_solver_ui.tools.clipboard_file import copy_file_to_clipboard
from pneumo_solver_ui.tools.health_report import build_health_report
from pneumo_solver_ui.tools.inspect_send_bundle import inspect_send_bundle, render_inspection_md
from pneumo_solver_ui.tools.send_bundle_contract import (
    ANIM_DIAG_SIDECAR_JSON,
    format_anim_dashboard_brief_lines,
    load_latest_send_bundle_anim_dashboard,
)
from pneumo_solver_ui.tools.send_bundle_evidence import (
    ANALYSIS_EVIDENCE_SIDECAR_NAME,
    ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME,
    ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME,
    EVIDENCE_MANIFEST_SIDECAR_NAME,
    GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME,
    GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME,
    build_latest_integrity_proof,
    load_evidence_manifest_from_zip,
    summarize_analysis_evidence_manifest,
    summarize_engineering_analysis_evidence,
    summarize_geometry_reference_evidence,
)

from .desktop_results_runtime import ANIMATION_DIAGNOSTICS_HANDOFF_JSON
from .desktop_diagnostics_model import (
    LATEST_DESKTOP_DIAGNOSTICS_CENTER_JSON,
    LATEST_DESKTOP_DIAGNOSTICS_RUN_JSON,
    LATEST_DESKTOP_DIAGNOSTICS_RUN_LOG,
    LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD,
    LATEST_SEND_BUNDLE_INSPECTION_JSON,
    LATEST_SEND_BUNDLE_INSPECTION_MD,
    DesktopDiagnosticsBundleRecord,
    DesktopDiagnosticsRunRecord,
    now_local_iso,
    path_str,
)


def _safe_read_json_dict(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def _safe_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(path)
    except PermissionError:
        fallback_path = path.with_name(f"{path.stem}.write_failed{path.suffix}")
        try:
            fallback_path.write_text(text, encoding="utf-8")
        except OSError:
            # Diagnostics state is a UI cache. A locked cache file must not crash
            # the hosted diagnostics workspace.
            return
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass


def _safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")


def _safe_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return 0


def _same_path(left: object, right: object) -> bool:
    left_text = str(left or "").strip()
    right_text = str(right or "").strip()
    if not left_text or not right_text:
        return False
    try:
        return Path(left_text).expanduser().resolve() == Path(right_text).expanduser().resolve()
    except Exception:
        return left_text.casefold() == right_text.casefold()


def _clean_string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _bool_or_none(value: object) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return bool(value)


def _resolve_bundle_out_dir(repo_root: Path, out_dir: Optional[Path | str] = None) -> Path:
    if out_dir is not None:
        return Path(out_dir).expanduser().resolve()
    try:
        cfg = load_diagnostics_config(repo_root)
        return cfg.resolved_out_dir(repo_root)
    except Exception:
        return (repo_root / "send_bundles").resolve()


def _effective_workspace_dir(repo_root: Path) -> Path:
    raw = os.environ.get("PNEUMO_WORKSPACE_DIR", "").strip()
    if raw:
        try:
            return Path(raw).expanduser().resolve()
        except Exception:
            return Path(raw).expanduser()
    return (Path(repo_root) / "pneumo_solver_ui" / "workspace").resolve()


def _load_analysis_evidence_summary(repo_root: Path, out_dir: Path) -> dict:
    candidates = [
        out_dir / ANALYSIS_EVIDENCE_SIDECAR_NAME,
        _effective_workspace_dir(repo_root) / "exports" / "analysis_evidence_manifest.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        payload = _safe_read_json_dict(candidate)
        read_warnings = []
        if not payload:
            read_warnings.append("Analysis evidence / HO-009 manifest is empty or unreadable.")
        summary = summarize_analysis_evidence_manifest(
            payload,
            source_path=path_str(candidate),
            read_warnings=read_warnings,
        )
        break
    else:
        summary = summarize_analysis_evidence_manifest({}, source_path="")

    status = str(summary.get("status") or "MISSING").strip().upper()
    if status == "MISSING":
        action = "Откройте Results Center и выполните экспорт evidence manifest перед SEND."
    elif status == "WARN":
        action = "Проверьте HO-009 context state и mismatches перед отправкой."
    else:
        action = "HO-009 evidence готов к включению в diagnostics/SEND."
    analysis_context_status = str(summary.get("analysis_context_status") or "").strip().upper()
    if analysis_context_status in {"MISSING", "BLOCKED", "INVALID"}:
        summary["analysis_context_action"] = (
            "Откройте Engineering Analysis Center и переэкспортируйте HO-008 analysis context перед SEND."
        )
    elif analysis_context_status == "DEGRADED":
        summary["analysis_context_action"] = (
            "Проверьте данные анализа: доступные файлы видимы, но сравнение и анимация требуют внимания."
        )
    else:
        summary["analysis_context_action"] = ""
    summary["action"] = action
    return summary


def _summarize_engineering_analysis_evidence_manifest(
    payload: dict | None,
    *,
    source_path: str = "",
    read_warnings: list[str] | None = None,
) -> dict:
    summary = summarize_engineering_analysis_evidence(
        payload,
        source_path=source_path,
        read_warnings=read_warnings or [],
    )
    status = str(summary.get("status") or "MISSING")
    readiness_status = str(summary.get("readiness_status") or status)
    open_gap_status = str(summary.get("open_gap_status") or "MISSING")
    open_gap_reasons = _clean_string_list(summary.get("open_gap_reasons"))
    validation_status = str(summary.get("analysis_status") or "MISSING").strip().upper()
    candidate_count = _safe_int(summary.get("selected_run_candidate_count"))
    ready_candidate_count = _safe_int(summary.get("selected_run_ready_candidate_count"))

    if status == "MISSING":
        action = "Откройте Engineering Analysis Center и выполните экспорт evidence manifest перед SEND."
    elif open_gap_status == "OPEN":
        action = "Устраните HO-007 open gap(s) в Engineering Analysis Center перед SEND."
    elif candidate_count and not ready_candidate_count:
        action = "Выберите READY optimization run или устраните missing inputs в Engineering Analysis Center."
    elif status == "WARN":
        action = "Проверьте validation/status и HO-007 readiness перед отправкой."
    else:
        action = "Engineering Analysis evidence готов к включению в diagnostics/SEND."

    return {
        "source_path": str(summary.get("source_path") or ""),
        "status": status,
        "readiness_status": readiness_status,
        "open_gap_status": open_gap_status,
        "open_gap_reasons": open_gap_reasons,
        "no_release_closure_claim": bool(summary.get("no_release_closure_claim", True)),
        "schema": str(summary.get("schema") or ""),
        "evidence_manifest_hash": str(summary.get("evidence_manifest_hash") or ""),
        "validation_status": validation_status,
        "candidate_count": candidate_count,
        "ready_candidate_count": ready_candidate_count,
        "missing_inputs_candidate_count": _safe_int(summary.get("selected_run_missing_inputs_candidate_count")),
        "failed_candidate_count": _safe_int(
            dict(summary.get("selected_run_candidate_readiness") or {}).get("failed_candidate_count")
        ),
        "unique_missing_inputs": _clean_string_list(
            dict(summary.get("selected_run_candidate_readiness") or {}).get("unique_missing_inputs")
        ),
        "ready_run_dirs": _clean_string_list(
            dict(summary.get("selected_run_candidate_readiness") or {}).get("ready_run_dirs")
        ),
        "warnings": list(dict.fromkeys(str(item) for item in (summary.get("warnings") or []) if str(item).strip())),
        "action": action,
    }


def _load_engineering_analysis_evidence_summary(repo_root: Path, out_dir: Path) -> dict:
    candidates = [
        out_dir / ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME,
        _effective_workspace_dir(repo_root) / "exports" / Path(ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME).name,
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        payload = _safe_read_json_dict(candidate)
        read_warnings = []
        if not payload:
            read_warnings.append("Engineering Analysis evidence / HO-007 manifest is empty or unreadable.")
        return _summarize_engineering_analysis_evidence_manifest(
            payload,
            source_path=path_str(candidate),
            read_warnings=read_warnings,
        )
    return _summarize_engineering_analysis_evidence_manifest({}, source_path="")


def _load_geometry_reference_evidence_summary(repo_root: Path, out_dir: Path) -> dict:
    candidates = [
        out_dir / GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME,
        _effective_workspace_dir(repo_root) / "exports" / Path(GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME).name,
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        payload = _safe_read_json_dict(candidate)
        read_warnings = []
        if not payload:
            read_warnings.append("Geometry reference evidence is empty or unreadable.")
        summary = summarize_geometry_reference_evidence(
            payload,
            source_path=path_str(candidate),
            read_warnings=read_warnings,
        )
        break
    else:
        summary = summarize_geometry_reference_evidence({}, source_path="")

    status = str(summary.get("status") or "MISSING").strip().upper()
    producer_status = str(summary.get("producer_artifact_status") or "").strip().lower()
    producer_action = str(summary.get("producer_next_action") or "").strip()
    if producer_status in {"missing", "partial", "stale"} and producer_action:
        action = producer_action
    elif status == "MISSING":
        action = "Откройте Reference Center или соберите SEND bundle, чтобы создать geometry reference evidence."
    elif status == "WARN":
        action = "Проверьте packaging/road_width/geometry acceptance warnings перед отправкой."
    else:
        action = "Geometry Reference evidence готов к включению в diagnostics/SEND."
    summary["action"] = action
    return summary


def _load_animation_diagnostics_handoff_summary(repo_root: Path, out_dir: Path) -> dict:
    candidates = (
        out_dir / ANIMATION_DIAGNOSTICS_HANDOFF_JSON,
        repo_root / "send_bundles" / ANIMATION_DIAGNOSTICS_HANDOFF_JSON,
    )
    seen: set[str] = set()
    for candidate in candidates:
        try:
            path = Path(candidate).expanduser().resolve()
        except Exception:
            path = Path(candidate)
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if not path.exists() or not path.is_file():
            continue

        payload = _safe_read_json_dict(path)
        selected = dict(payload.get("selected_artifact") or {}) if payload else {}
        artifacts = dict(payload.get("artifacts") or {}) if payload else {}
        context = dict(payload.get("animation_context") or {}) if payload else {}
        warnings: list[str] = []
        schema = str(payload.get("schema") or "") if payload else ""
        status = "READY"
        if not payload:
            status = "WARN"
            warnings.append("Animation diagnostics handoff is present but unreadable.")
        elif schema != "desktop_animation_diagnostics_handoff":
            status = "WARN"
            warnings.append(f"Unexpected animation diagnostics handoff schema: {schema or 'missing'}.")
        scene_path = str(artifacts.get("scene_npz_path") or "").strip()
        pointer_path = str(artifacts.get("pointer_json_path") or "").strip()
        if payload and not scene_path and not pointer_path:
            status = "WARN"
            warnings.append("Animation diagnostics handoff has no scene or pointer artifact.")
        return {
            "status": status,
            "source_path": path_str(path),
            "schema": schema,
            "handoff_id": str(payload.get("handoff_id") or "") if payload else "",
            "handoff_hash": str(payload.get("handoff_hash") or "") if payload else "",
            "produced_by": str(payload.get("produced_by") or "") if payload else "",
            "consumed_by": str(payload.get("consumed_by") or "") if payload else "",
            "selected_title": str(selected.get("title") or ""),
            "selected_path": str(selected.get("path") or ""),
            "selected_key": str(selected.get("key") or ""),
            "scene_npz_path": scene_path,
            "pointer_json_path": pointer_path,
            "mnemo_event_log_path": str(artifacts.get("mnemo_event_log_path") or ""),
            "capture_export_manifest_path": str(artifacts.get("capture_export_manifest_path") or ""),
            "analysis_animation_handoff_path": str(artifacts.get("analysis_animation_handoff_path") or ""),
            "scene_ready": bool(context.get("scene_ready") or scene_path or pointer_path),
            "mnemo_ready": bool(context.get("mnemo_ready")),
            "capture_status": str(context.get("capture_status") or ""),
            "next_step": str(payload.get("next_step") or "") if payload else "",
            "warnings": warnings,
        }
    return {
        "status": "MISSING",
        "source_path": "",
        "schema": "",
        "handoff_id": "",
        "handoff_hash": "",
        "produced_by": "",
        "consumed_by": "",
        "selected_title": "",
        "selected_path": "",
        "selected_key": "",
        "scene_npz_path": "",
        "pointer_json_path": "",
        "mnemo_event_log_path": "",
        "capture_export_manifest_path": "",
        "analysis_animation_handoff_path": "",
        "scene_ready": False,
        "mnemo_ready": False,
        "capture_status": "",
        "next_step": "",
        "warnings": [],
    }


def _load_embedded_evidence_manifest(zip_path: Path | None) -> dict:
    if zip_path is None or not zip_path.exists():
        return {}
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            return load_evidence_manifest_from_zip(zf)
    except Exception:
        return {}


def _load_latest_integrity_proof(out_dir: Path, latest_zip: Path | None) -> dict:
    if latest_zip is None:
        return {}
    sidecar_path = out_dir / EVIDENCE_MANIFEST_SIDECAR_NAME
    sidecar = _safe_read_json_dict(sidecar_path) if sidecar_path.exists() else {}
    if latest_zip.name != "latest_send_bundle.zip" and not sidecar:
        return {}
    embedded = _load_embedded_evidence_manifest(latest_zip)
    return build_latest_integrity_proof(
        zip_path=latest_zip,
        latest_zip_path=latest_zip,
        original_zip_path=sidecar.get("zip_path") or latest_zip,
        latest_sha_path=out_dir / "latest_send_bundle.sha256",
        latest_pointer_path=out_dir / "latest_send_bundle_path.txt",
        evidence_manifest=sidecar,
        embedded_manifest=embedded,
    )


def _summarize_self_check_silent_warnings_snapshot(payload: dict, *, json_path: str, md_path: str = "") -> dict:
    if not payload:
        return {
            "status": "MISSING",
            "json_path": str(json_path or ""),
            "md_path": str(md_path or ""),
            "snapshot_only": True,
            "rc": None,
            "fail_count": 0,
            "warn_count": 0,
        }
    summary = dict(payload.get("summary") or {}) if isinstance(payload.get("summary"), dict) else {}
    fail_count = _safe_int(summary.get("fail_count"))
    warn_count = _safe_int(summary.get("warn_count"))
    if not fail_count:
        fail_count = len([item for item in (payload.get("fails") or []) if isinstance(item, dict)])
    if not warn_count:
        warn_count = len([item for item in (payload.get("warnings") or []) if isinstance(item, dict)])
    rc_value = payload.get("rc")
    status = "READY"
    if fail_count or warn_count or (rc_value not in (None, 0, "0")):
        status = "WARN"
    return {
        "status": status,
        "json_path": str(json_path or ""),
        "md_path": str(md_path or ""),
        "snapshot_only": True,
        "rc": rc_value,
        "fail_count": fail_count,
        "warn_count": warn_count,
    }


def _load_self_check_silent_warnings_snapshot(repo_root: Path, latest_zip: Path | None) -> dict:
    reports_dir = Path(repo_root) / "REPORTS"
    json_path = reports_dir / "SELF_CHECK_SILENT_WARNINGS.json"
    md_path = reports_dir / "SELF_CHECK_SILENT_WARNINGS.md"
    if json_path.exists():
        return _summarize_self_check_silent_warnings_snapshot(
            _safe_read_json_dict(json_path),
            json_path=path_str(json_path),
            md_path=path_str(md_path if md_path.exists() else ""),
        )
    if latest_zip is not None and latest_zip.exists():
        try:
            with zipfile.ZipFile(latest_zip, "r") as zf:
                with zf.open("reports/SELF_CHECK_SILENT_WARNINGS.json", "r") as handle:
                    obj = json.loads(handle.read().decode("utf-8", errors="replace"))
                payload = dict(obj) if isinstance(obj, dict) else {}
            return _summarize_self_check_silent_warnings_snapshot(
                payload,
                json_path=f"{path_str(latest_zip)}::reports/SELF_CHECK_SILENT_WARNINGS.json",
                md_path=f"{path_str(latest_zip)}::reports/SELF_CHECK_SILENT_WARNINGS.md",
            )
        except Exception:
            pass
    return _summarize_self_check_silent_warnings_snapshot({}, json_path=path_str(json_path), md_path=path_str(md_path))


def _pick_latest_bundle_candidate(out_dir: Path) -> Optional[Path]:
    latest = out_dir / "latest_send_bundle.zip"
    if latest.exists():
        return latest.resolve()

    latest_txt = out_dir / "latest_send_bundle_path.txt"
    if latest_txt.exists():
        raw = str(latest_txt.read_text(encoding="utf-8", errors="replace") or "").strip()
        if raw:
            cand = Path(raw).expanduser()
            if cand.exists():
                return cand.resolve()

    zips = sorted(out_dir.glob("SEND_*_bundle.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if zips:
        return zips[0].resolve()
    return None


def _is_full_file_clipboard_success(ok: bool, msg: str) -> bool:
    if not ok:
        return False
    text = str(msg or "")
    return "Copied path as text" not in text and "Fallback(text): Copied path as text" not in text


def write_send_bundle_clipboard_status(out_dir: Path, zip_path: Path, ok: bool, message: str) -> Path:
    path = out_dir / "latest_send_bundle_clipboard_status.json"
    payload = {
        "ok": bool(ok),
        "message": str(message),
        "zip_path": path_str(zip_path),
        "updated_at": now_local_iso(),
    }
    _safe_write_json(path, payload)
    return path


def load_desktop_diagnostics_bundle_record(
    repo_root: Path,
    *,
    out_dir: Optional[Path | str] = None,
) -> DesktopDiagnosticsBundleRecord:
    resolved_out_dir = _resolve_bundle_out_dir(repo_root, out_dir)
    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    meta_path = resolved_out_dir / "last_bundle_meta.json"
    meta = read_last_meta_from_out_dir(resolved_out_dir)
    summary = summarize_last_bundle_meta(meta)

    latest_zip = _pick_latest_bundle_candidate(resolved_out_dir)
    if latest_zip is None and summary.get("zip_path"):
        latest_zip = Path(summary["zip_path"]).expanduser()
        if latest_zip.exists():
            latest_zip = latest_zip.resolve()
        else:
            latest_zip = None

    dashboard = load_latest_send_bundle_anim_dashboard(resolved_out_dir)
    summary_lines = [str(x) for x in (summary.get("summary_lines") or []) if str(x).strip()]
    if not summary_lines:
        summary_lines = [str(x) for x in format_anim_dashboard_brief_lines(dashboard) if str(x).strip()]

    clipboard_path = resolved_out_dir / "latest_send_bundle_clipboard_status.json"
    clipboard_status = _safe_read_json_dict(clipboard_path) if clipboard_path.exists() else {}
    if clipboard_status and latest_zip is not None:
        clipboard_zip = str(clipboard_status.get("zip_path") or "").strip()
        if not _same_path(clipboard_zip, latest_zip):
            clipboard_status = {
                "ok": False,
                "message": (
                    "Clipboard status is stale for the current latest bundle: "
                    f"{clipboard_zip or 'no zip_path'}"
                ),
                "zip_path": clipboard_zip,
                "stale_for_latest_zip": path_str(latest_zip),
            }
    analysis = _load_analysis_evidence_summary(repo_root, resolved_out_dir)
    engineering_analysis = _load_engineering_analysis_evidence_summary(repo_root, resolved_out_dir)
    geometry_reference = _load_geometry_reference_evidence_summary(repo_root, resolved_out_dir)
    animation_handoff = _load_animation_diagnostics_handoff_summary(repo_root, resolved_out_dir)
    latest_integrity = _load_latest_integrity_proof(resolved_out_dir, latest_zip)
    self_check_snapshot = _load_self_check_silent_warnings_snapshot(repo_root, latest_zip)

    animation_handoff_summary_lines: list[str] = []
    if animation_handoff.get("source_path"):
        scene_name = Path(str(
            animation_handoff.get("scene_npz_path")
            or animation_handoff.get("pointer_json_path")
            or animation_handoff.get("selected_path")
            or animation_handoff.get("source_path")
        )).name
        animation_handoff_summary_lines.append(
            "Animation diagnostics handoff: "
            f"{animation_handoff.get('status') or 'MISSING'} "
            f"scene={scene_name or '—'} "
            f"sidecar={Path(str(animation_handoff.get('source_path') or '')).name}"
        )

    integrity_summary_lines: list[str] = []
    if latest_integrity:
        final_sha = str(latest_integrity.get("final_latest_zip_sha256") or "")
        embedded_scope = str(latest_integrity.get("embedded_manifest_zip_sha256_scope") or "—")
        integrity_summary_lines.append(
            "Latest integrity: "
            f"{latest_integrity.get('status') or 'MISSING'} "
            f"final_sha={final_sha[:12] or '—'} "
            f"sha_sidecar={latest_integrity.get('latest_sha_sidecar_matches')} "
            f"pointer={latest_integrity.get('latest_pointer_matches_original')} "
            f"embedded_scope={embedded_scope}"
        )
        integrity_summary_lines.append(
            "Producer-owned warnings remain warning-only; Diagnostics/SEND makes no release closure claim."
        )
    if self_check_snapshot:
        integrity_summary_lines.append(
            "Self-check silent warnings snapshot: "
            f"{self_check_snapshot.get('status') or 'MISSING'} "
            f"fail={self_check_snapshot.get('fail_count', 0)} "
            f"warn={self_check_snapshot.get('warn_count', 0)} "
            "snapshot_only=True"
        )
    if str(engineering_analysis.get("open_gap_status") or "").upper() == "OPEN":
        reasons = [
            str(item).strip()
            for item in (engineering_analysis.get("open_gap_reasons") or [])
            if str(item).strip()
        ]
        integrity_summary_lines.append(
            "Engineering Analysis / HO-007 open gaps remain warning-only: "
            + (", ".join(reasons[:4]) if reasons else "readiness is not clear")
        )
    if animation_handoff_summary_lines or integrity_summary_lines:
        summary_lines = list(
            dict.fromkeys(animation_handoff_summary_lines + integrity_summary_lines + summary_lines)
        )

    return DesktopDiagnosticsBundleRecord(
        out_dir=path_str(resolved_out_dir),
        latest_zip_path=path_str(latest_zip),
        latest_zip_name=latest_zip.name if latest_zip else "",
        latest_path_pointer_path=path_str(
            (resolved_out_dir / "latest_send_bundle_path.txt")
            if (resolved_out_dir / "latest_send_bundle_path.txt").exists()
            else ""
        ),
        latest_sha_path=path_str(
            (resolved_out_dir / "latest_send_bundle.sha256")
            if (resolved_out_dir / "latest_send_bundle.sha256").exists()
            else ""
        ),
        latest_bundle_meta_path=path_str(meta_path if meta_path.exists() else ""),
        latest_inspection_json_path=path_str(
            (resolved_out_dir / LATEST_SEND_BUNDLE_INSPECTION_JSON)
            if (resolved_out_dir / LATEST_SEND_BUNDLE_INSPECTION_JSON).exists()
            else ""
        ),
        latest_inspection_md_path=path_str(
            (resolved_out_dir / LATEST_SEND_BUNDLE_INSPECTION_MD)
            if (resolved_out_dir / LATEST_SEND_BUNDLE_INSPECTION_MD).exists()
            else ""
        ),
        latest_health_json_path=path_str(
            (resolved_out_dir / "latest_health_report.json")
            if (resolved_out_dir / "latest_health_report.json").exists()
            else ""
        ),
        latest_health_md_path=path_str(
            (resolved_out_dir / "latest_health_report.md")
            if (resolved_out_dir / "latest_health_report.md").exists()
            else ""
        ),
        latest_validation_json_path=path_str(
            (resolved_out_dir / "latest_send_bundle_validation.json")
            if (resolved_out_dir / "latest_send_bundle_validation.json").exists()
            else ""
        ),
        latest_validation_md_path=path_str(
            (resolved_out_dir / "latest_send_bundle_validation.md")
            if (resolved_out_dir / "latest_send_bundle_validation.md").exists()
            else ""
        ),
        latest_triage_md_path=path_str(
            (resolved_out_dir / "latest_triage_report.md")
            if (resolved_out_dir / "latest_triage_report.md").exists()
            else ""
        ),
        latest_evidence_manifest_path=path_str(
            (resolved_out_dir / EVIDENCE_MANIFEST_SIDECAR_NAME)
            if (resolved_out_dir / EVIDENCE_MANIFEST_SIDECAR_NAME).exists()
            else ""
        ),
        latest_integrity_status=str(latest_integrity.get("status") or "MISSING"),
        latest_integrity_final_zip_sha256=str(latest_integrity.get("final_latest_zip_sha256") or ""),
        latest_integrity_final_original_zip_sha256=str(latest_integrity.get("final_original_zip_sha256") or ""),
        latest_integrity_sha_sidecar_matches=_bool_or_none(latest_integrity.get("latest_sha_sidecar_matches")),
        latest_integrity_pointer_matches_original=_bool_or_none(
            latest_integrity.get("latest_pointer_matches_original")
        ),
        latest_integrity_latest_zip_matches_original=_bool_or_none(
            latest_integrity.get("latest_zip_matches_original")
        ),
        latest_integrity_evidence_sidecar_path=path_str(
            (resolved_out_dir / EVIDENCE_MANIFEST_SIDECAR_NAME)
            if (resolved_out_dir / EVIDENCE_MANIFEST_SIDECAR_NAME).exists()
            else ""
        ),
        latest_integrity_embedded_manifest_zip_sha256=str(
            latest_integrity.get("embedded_manifest_zip_sha256") or ""
        ),
        latest_integrity_embedded_manifest_zip_sha256_scope=str(
            latest_integrity.get("embedded_manifest_zip_sha256_scope") or ""
        ),
        latest_integrity_embedded_manifest_stage=str(latest_integrity.get("embedded_manifest_stage") or ""),
        latest_integrity_embedded_manifest_finalization_stage=str(
            latest_integrity.get("embedded_manifest_finalization_stage") or ""
        ),
        latest_integrity_trigger=str(latest_integrity.get("trigger") or ""),
        latest_integrity_collection_mode=str(latest_integrity.get("collection_mode") or ""),
        latest_integrity_producer_warning_count=_safe_int(latest_integrity.get("producer_warning_count")),
        latest_integrity_warning_only_gaps_present=bool(latest_integrity.get("warning_only_gaps_present")),
        latest_integrity_no_release_closure_claim=bool(latest_integrity.get("no_release_closure_claim", True)),
        latest_integrity_warnings=[str(item) for item in (latest_integrity.get("warnings") or []) if str(item).strip()],
        self_check_silent_warnings_status=str(self_check_snapshot.get("status") or "MISSING"),
        self_check_silent_warnings_json_path=str(self_check_snapshot.get("json_path") or ""),
        self_check_silent_warnings_md_path=str(self_check_snapshot.get("md_path") or ""),
        self_check_silent_warnings_rc=(
            _safe_int(self_check_snapshot.get("rc"))
            if self_check_snapshot.get("rc") not in (None, "")
            else None
        ),
        self_check_silent_warnings_fail_count=_safe_int(self_check_snapshot.get("fail_count")),
        self_check_silent_warnings_warn_count=_safe_int(self_check_snapshot.get("warn_count")),
        self_check_silent_warnings_snapshot_only=bool(self_check_snapshot.get("snapshot_only", True)),
        latest_analysis_evidence_manifest_path=str(analysis.get("source_path") or ""),
        analysis_evidence_manifest_hash=str(analysis.get("evidence_manifest_hash") or ""),
        analysis_evidence_status=str(analysis.get("status") or "MISSING"),
        analysis_evidence_handoff_id=str(analysis.get("handoff_id") or ""),
        analysis_evidence_context_state=str(analysis.get("result_context_state") or "MISSING"),
        analysis_context_status=str(analysis.get("analysis_context_status") or ""),
        analysis_context_action=str(analysis.get("analysis_context_action") or ""),
        analysis_animator_link_contract_hash=str(analysis.get("animator_link_contract_hash") or ""),
        analysis_selected_run_contract_hash=str(analysis.get("selected_run_contract_hash") or ""),
        analysis_selected_test_id=str(analysis.get("selected_test_id") or ""),
        analysis_selected_npz_path=str(analysis.get("selected_npz_path") or ""),
        analysis_capture_export_manifest_status=str(analysis.get("capture_export_manifest_status") or "MISSING"),
        analysis_capture_export_manifest_handoff_id=str(analysis.get("capture_export_manifest_handoff_id") or ""),
        analysis_capture_hash=str(analysis.get("capture_hash") or ""),
        analysis_truth_mode_hash=str(analysis.get("truth_mode_hash") or ""),
        analysis_evidence_run_id=str(analysis.get("run_id") or ""),
        analysis_evidence_run_contract_hash=str(analysis.get("run_contract_hash") or ""),
        analysis_evidence_compare_contract_id=str(analysis.get("compare_contract_id") or ""),
        analysis_evidence_artifact_count=int(analysis.get("artifact_count") or 0),
        analysis_evidence_mismatch_count=int(analysis.get("mismatch_count") or 0),
        analysis_evidence_warnings=[str(item) for item in (analysis.get("warnings") or []) if str(item).strip()],
        analysis_evidence_action=str(analysis.get("action") or ""),
        latest_engineering_analysis_evidence_manifest_path=str(engineering_analysis.get("source_path") or ""),
        engineering_analysis_evidence_manifest_hash=str(engineering_analysis.get("evidence_manifest_hash") or ""),
        engineering_analysis_evidence_status=str(engineering_analysis.get("status") or "MISSING"),
        engineering_analysis_readiness_status=str(
            engineering_analysis.get("readiness_status") or engineering_analysis.get("status") or "MISSING"
        ),
        engineering_analysis_open_gap_status=str(engineering_analysis.get("open_gap_status") or "MISSING"),
        engineering_analysis_open_gap_reasons=_clean_string_list(engineering_analysis.get("open_gap_reasons")),
        engineering_analysis_no_release_closure_claim=bool(
            engineering_analysis.get("no_release_closure_claim", True)
        ),
        engineering_analysis_evidence_schema=str(engineering_analysis.get("schema") or ""),
        engineering_analysis_validation_status=str(engineering_analysis.get("validation_status") or "MISSING"),
        engineering_analysis_candidate_count=_safe_int(engineering_analysis.get("candidate_count")),
        engineering_analysis_ready_candidate_count=_safe_int(engineering_analysis.get("ready_candidate_count")),
        engineering_analysis_missing_inputs_candidate_count=_safe_int(
            engineering_analysis.get("missing_inputs_candidate_count")
        ),
        engineering_analysis_failed_candidate_count=_safe_int(engineering_analysis.get("failed_candidate_count")),
        engineering_analysis_candidate_unique_missing_inputs=_clean_string_list(
            engineering_analysis.get("unique_missing_inputs")
        ),
        engineering_analysis_candidate_ready_run_dirs=_clean_string_list(engineering_analysis.get("ready_run_dirs")),
        engineering_analysis_evidence_warnings=[
            str(item) for item in (engineering_analysis.get("warnings") or []) if str(item).strip()
        ],
        engineering_analysis_evidence_action=str(engineering_analysis.get("action") or ""),
        latest_geometry_reference_evidence_path=str(geometry_reference.get("source_path") or ""),
        geometry_reference_status=str(geometry_reference.get("status") or "MISSING"),
        geometry_reference_artifact_status=str(geometry_reference.get("artifact_status") or "missing"),
        geometry_reference_artifact_freshness_status=str(
            geometry_reference.get("artifact_freshness_status") or "missing"
        ),
        geometry_reference_artifact_freshness_relation=str(
            geometry_reference.get("artifact_freshness_relation") or "missing"
        ),
        geometry_reference_artifact_freshness_reason=str(
            geometry_reference.get("artifact_freshness_reason") or ""
        ),
        geometry_reference_latest_artifact_status=str(geometry_reference.get("latest_artifact_status") or ""),
        geometry_reference_road_width_status=str(geometry_reference.get("road_width_status") or "missing"),
        geometry_reference_road_width_source=str(geometry_reference.get("road_width_source") or ""),
        geometry_reference_packaging_status=str(geometry_reference.get("packaging_status") or "missing"),
        geometry_reference_packaging_mismatch_status=str(
            geometry_reference.get("packaging_mismatch_status") or "missing"
        ),
        geometry_reference_packaging_contract_hash=str(geometry_reference.get("packaging_contract_hash") or ""),
        geometry_reference_acceptance_gate=str(geometry_reference.get("geometry_acceptance_gate") or "MISSING"),
        geometry_reference_producer_artifact_status=str(
            geometry_reference.get("producer_artifact_status") or "missing"
        ),
        geometry_reference_producer_readiness_reasons=_clean_string_list(
            geometry_reference.get("producer_readiness_reasons")
        ),
        geometry_reference_producer_evidence_owner=str(
            geometry_reference.get("producer_evidence_owner") or "producer_export"
        ),
        geometry_reference_producer_required_artifacts=_clean_string_list(
            geometry_reference.get("producer_required_artifacts")
        ),
        geometry_reference_producer_next_action=str(geometry_reference.get("producer_next_action") or ""),
        geometry_reference_consumer_may_fabricate_geometry=bool(
            geometry_reference.get("consumer_may_fabricate_geometry")
        ),
        geometry_reference_component_passport_needs_data=int(
            geometry_reference.get("component_passport_needs_data") or 0
        ),
        geometry_reference_evidence_missing=[
            str(item) for item in (geometry_reference.get("evidence_missing") or []) if str(item).strip()
        ],
        geometry_reference_warnings=[
            str(item) for item in (geometry_reference.get("warnings") or []) if str(item).strip()
        ],
        geometry_reference_action=str(geometry_reference.get("action") or ""),
        latest_clipboard_status_path=path_str(clipboard_path if clipboard_path.exists() else ""),
        anim_pointer_diagnostics_path=path_str(
            (resolved_out_dir / ANIM_DIAG_SIDECAR_JSON)
            if (resolved_out_dir / ANIM_DIAG_SIDECAR_JSON).exists()
            else summary.get("anim_pointer_diagnostics_path") or ""
        ),
        latest_animation_diagnostics_handoff_path=str(animation_handoff.get("source_path") or ""),
        animation_diagnostics_handoff_status=str(animation_handoff.get("status") or "MISSING"),
        animation_diagnostics_handoff_hash=str(animation_handoff.get("handoff_hash") or ""),
        animation_diagnostics_selected_title=str(animation_handoff.get("selected_title") or ""),
        animation_diagnostics_selected_path=str(animation_handoff.get("selected_path") or ""),
        animation_diagnostics_scene_npz_path=str(animation_handoff.get("scene_npz_path") or ""),
        animation_diagnostics_pointer_json_path=str(animation_handoff.get("pointer_json_path") or ""),
        animation_diagnostics_mnemo_event_log_path=str(animation_handoff.get("mnemo_event_log_path") or ""),
        animation_diagnostics_next_step=str(animation_handoff.get("next_step") or ""),
        summary_lines=summary_lines,
        clipboard_ok=(
            bool(clipboard_status.get("ok"))
            if "ok" in clipboard_status
            else None
        ),
        clipboard_message=str(clipboard_status.get("message") or ""),
    )


def refresh_desktop_diagnostics_bundle_record(
    repo_root: Path,
    *,
    out_dir: Optional[Path | str] = None,
    zip_path: Optional[Path | str] = None,
) -> DesktopDiagnosticsBundleRecord:
    bundle = load_desktop_diagnostics_bundle_record(repo_root, out_dir=out_dir)
    resolved_out_dir = Path(bundle.out_dir).expanduser().resolve()

    chosen_zip = Path(zip_path).expanduser().resolve() if zip_path else None
    if chosen_zip is None and bundle.latest_zip_path:
        chosen_zip = Path(bundle.latest_zip_path).expanduser().resolve()
    if chosen_zip is None or not chosen_zip.exists():
        return bundle

    try:
        inspection = inspect_send_bundle(chosen_zip)
        _safe_write_json(resolved_out_dir / LATEST_SEND_BUNDLE_INSPECTION_JSON, inspection)
        _safe_write_text(resolved_out_dir / LATEST_SEND_BUNDLE_INSPECTION_MD, render_inspection_md(inspection))
    except Exception:
        pass

    try:
        build_health_report(chosen_zip, out_dir=resolved_out_dir)
    except Exception:
        pass

    return load_desktop_diagnostics_bundle_record(repo_root, out_dir=resolved_out_dir)


def write_desktop_diagnostics_summary_md(out_dir: Path | str, summary_text: str) -> Path:
    resolved_out_dir = Path(out_dir).expanduser().resolve()
    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    path = resolved_out_dir / LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD
    _safe_write_text(path, str(summary_text or ""))
    return path


def append_desktop_diagnostics_run_log(out_root: Path | str, text: str) -> Path:
    resolved_out_root = Path(out_root).expanduser().resolve()
    resolved_out_root.mkdir(parents=True, exist_ok=True)

    log_path = resolved_out_root / LATEST_DESKTOP_DIAGNOSTICS_RUN_LOG
    with open(log_path, "a", encoding="utf-8", errors="replace") as fh:
        fh.write(str(text or ""))
    return log_path


def persist_desktop_diagnostics_run(
    out_root: Path,
    record: DesktopDiagnosticsRunRecord,
    *,
    log_text: str = "",
) -> DesktopDiagnosticsRunRecord:
    resolved_out_root = Path(out_root).expanduser().resolve()
    resolved_out_root.mkdir(parents=True, exist_ok=True)

    log_path = resolved_out_root / LATEST_DESKTOP_DIAGNOSTICS_RUN_LOG
    if log_text:
        _safe_write_text(log_path, log_text)

    state_path = resolved_out_root / LATEST_DESKTOP_DIAGNOSTICS_RUN_JSON
    updated = replace(
        record,
        finished_at=record.finished_at or now_local_iso(),
        out_root=path_str(resolved_out_root),
        log_path=path_str(log_path if log_path.exists() else ""),
        state_path=path_str(state_path),
    )
    _safe_write_json(state_path, updated.to_payload())
    return updated


def load_last_desktop_diagnostics_run_record(
    out_root: Path | str,
) -> Optional[DesktopDiagnosticsRunRecord]:
    resolved_out_root = Path(out_root).expanduser().resolve()
    state_path = resolved_out_root / LATEST_DESKTOP_DIAGNOSTICS_RUN_JSON
    payload = _safe_read_json_dict(state_path)
    if not payload:
        return None
    try:
        return DesktopDiagnosticsRunRecord(
            ok=bool(payload.get("ok")),
            started_at=str(payload.get("started_at") or ""),
            finished_at=str(payload.get("finished_at") or ""),
            status=str(payload.get("status") or ""),
            command=[str(x) for x in (payload.get("command") or [])],
            returncode=payload.get("returncode"),
            run_dir=str(payload.get("run_dir") or ""),
            zip_path=str(payload.get("zip_path") or ""),
            out_root=str(payload.get("out_root") or path_str(resolved_out_root)),
            log_path=str(payload.get("log_path") or ""),
            state_path=str(payload.get("state_path") or path_str(state_path)),
            last_message=str(payload.get("last_message") or ""),
        )
    except Exception:
        return None


def load_last_desktop_diagnostics_run_log_text(out_root: Path | str) -> str:
    resolved_out_root = Path(out_root).expanduser().resolve()
    log_path = resolved_out_root / LATEST_DESKTOP_DIAGNOSTICS_RUN_LOG
    try:
        return str(log_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return ""


def load_last_desktop_diagnostics_center_state(out_dir: Path | str) -> dict:
    resolved_out_dir = Path(out_dir).expanduser().resolve()
    path = resolved_out_dir / LATEST_DESKTOP_DIAGNOSTICS_CENTER_JSON
    payload = _safe_read_json_dict(path)
    return payload if payload else {}


def write_desktop_diagnostics_center_state(
    out_dir: Path,
    *,
    bundle_record: DesktopDiagnosticsBundleRecord,
    run_record: Optional[DesktopDiagnosticsRunRecord] = None,
    summary_md_path: Optional[Path | str] = None,
    ui_state: Optional[dict] = None,
) -> Path:
    resolved_out_dir = Path(out_dir).expanduser().resolve()
    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    path = resolved_out_dir / LATEST_DESKTOP_DIAGNOSTICS_CENTER_JSON
    resolved_summary_md_path = path_str(summary_md_path) if summary_md_path else path_str(
        (resolved_out_dir / LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD)
        if (resolved_out_dir / LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD).exists()
        else ""
    )
    payload = {
        "schema": "desktop_diagnostics_center_state",
        "schema_version": "1.0.0",
        "updated_at": now_local_iso(),
        "bundle": bundle_record.to_payload(),
        "run": run_record.to_payload() if run_record is not None else {},
        "ui": dict(ui_state or {}),
        "machine_paths": {
            "center_state_json": path_str(path),
            "latest_summary_md": resolved_summary_md_path,
            "latest_bundle_zip": bundle_record.latest_zip_path,
            "latest_bundle_path_txt": bundle_record.latest_path_pointer_path,
            "latest_bundle_sha256": bundle_record.latest_sha_path,
            "latest_bundle_meta_json": bundle_record.latest_bundle_meta_path,
            "latest_bundle_inspection_json": bundle_record.latest_inspection_json_path,
            "latest_bundle_inspection_md": bundle_record.latest_inspection_md_path,
            "latest_health_report_json": bundle_record.latest_health_json_path,
            "latest_health_report_md": bundle_record.latest_health_md_path,
            "latest_validation_json": bundle_record.latest_validation_json_path,
            "latest_validation_md": bundle_record.latest_validation_md_path,
            "latest_triage_md": bundle_record.latest_triage_md_path,
            "latest_evidence_manifest_json": bundle_record.latest_evidence_manifest_path,
            "latest_integrity_evidence_sidecar_json": bundle_record.latest_integrity_evidence_sidecar_path,
            "self_check_silent_warnings_json": bundle_record.self_check_silent_warnings_json_path,
            "self_check_silent_warnings_md": bundle_record.self_check_silent_warnings_md_path,
            "latest_analysis_evidence_manifest_json": bundle_record.latest_analysis_evidence_manifest_path,
            "latest_engineering_analysis_evidence_manifest_json": (
                bundle_record.latest_engineering_analysis_evidence_manifest_path
            ),
            "latest_geometry_reference_evidence_json": bundle_record.latest_geometry_reference_evidence_path,
            "latest_clipboard_status_json": bundle_record.latest_clipboard_status_path,
            "anim_pointer_diagnostics_json": bundle_record.anim_pointer_diagnostics_path,
            "latest_animation_diagnostics_handoff_json": (
                bundle_record.latest_animation_diagnostics_handoff_path
            ),
            "latest_run_state_json": run_record.state_path if run_record is not None else "",
            "latest_run_log": run_record.log_path if run_record is not None else "",
        },
        "latest_integrity_proof": {
            "status": bundle_record.latest_integrity_status,
            "final_latest_zip_sha256": bundle_record.latest_integrity_final_zip_sha256,
            "final_original_zip_sha256": bundle_record.latest_integrity_final_original_zip_sha256,
            "latest_sha_sidecar_matches": bundle_record.latest_integrity_sha_sidecar_matches,
            "latest_pointer_matches_original": bundle_record.latest_integrity_pointer_matches_original,
            "latest_zip_matches_original": bundle_record.latest_integrity_latest_zip_matches_original,
            "evidence_sidecar_path": bundle_record.latest_integrity_evidence_sidecar_path,
            "embedded_manifest_zip_sha256": bundle_record.latest_integrity_embedded_manifest_zip_sha256,
            "embedded_manifest_zip_sha256_scope": (
                bundle_record.latest_integrity_embedded_manifest_zip_sha256_scope
            ),
            "embedded_manifest_stage": bundle_record.latest_integrity_embedded_manifest_stage,
            "embedded_manifest_finalization_stage": (
                bundle_record.latest_integrity_embedded_manifest_finalization_stage
            ),
            "trigger": bundle_record.latest_integrity_trigger,
            "collection_mode": bundle_record.latest_integrity_collection_mode,
            "producer_warning_count": bundle_record.latest_integrity_producer_warning_count,
            "warning_only_gaps_present": bundle_record.latest_integrity_warning_only_gaps_present,
            "no_release_closure_claim": bundle_record.latest_integrity_no_release_closure_claim,
            "warnings": list(bundle_record.latest_integrity_warnings),
        },
        "self_check_silent_warnings": {
            "status": bundle_record.self_check_silent_warnings_status,
            "json_path": bundle_record.self_check_silent_warnings_json_path,
            "md_path": bundle_record.self_check_silent_warnings_md_path,
            "rc": bundle_record.self_check_silent_warnings_rc,
            "fail_count": bundle_record.self_check_silent_warnings_fail_count,
            "warn_count": bundle_record.self_check_silent_warnings_warn_count,
            "snapshot_only": bundle_record.self_check_silent_warnings_snapshot_only,
            "does_not_close_producer_warnings": True,
        },
        "analysis_evidence": {
            "status": bundle_record.analysis_evidence_status,
            "context_state": bundle_record.analysis_evidence_context_state,
            "analysis_context_status": bundle_record.analysis_context_status,
            "analysis_context_action": bundle_record.analysis_context_action,
            "animator_link_contract_hash": bundle_record.analysis_animator_link_contract_hash,
            "selected_run_contract_hash": bundle_record.analysis_selected_run_contract_hash,
            "selected_test_id": bundle_record.analysis_selected_test_id,
            "selected_npz_path": bundle_record.analysis_selected_npz_path,
            "capture_export_manifest_status": bundle_record.analysis_capture_export_manifest_status,
            "capture_export_manifest_handoff_id": bundle_record.analysis_capture_export_manifest_handoff_id,
            "capture_hash": bundle_record.analysis_capture_hash,
            "truth_mode_hash": bundle_record.analysis_truth_mode_hash,
            "manifest_hash": bundle_record.analysis_evidence_manifest_hash,
            "handoff_id": bundle_record.analysis_evidence_handoff_id,
            "run_id": bundle_record.analysis_evidence_run_id,
            "run_contract_hash": bundle_record.analysis_evidence_run_contract_hash,
            "compare_contract_id": bundle_record.analysis_evidence_compare_contract_id,
            "artifact_count": bundle_record.analysis_evidence_artifact_count,
            "mismatch_count": bundle_record.analysis_evidence_mismatch_count,
            "warnings": list(bundle_record.analysis_evidence_warnings),
            "action": bundle_record.analysis_evidence_action,
        },
        "engineering_analysis_evidence": {
            "status": bundle_record.engineering_analysis_evidence_status,
            "readiness_status": bundle_record.engineering_analysis_readiness_status,
            "open_gap_status": bundle_record.engineering_analysis_open_gap_status,
            "open_gap_reasons": list(bundle_record.engineering_analysis_open_gap_reasons),
            "no_release_closure_claim": bundle_record.engineering_analysis_no_release_closure_claim,
            "schema": bundle_record.engineering_analysis_evidence_schema,
            "manifest_hash": bundle_record.engineering_analysis_evidence_manifest_hash,
            "validation_status": bundle_record.engineering_analysis_validation_status,
            "selected_run_candidate_count": bundle_record.engineering_analysis_candidate_count,
            "selected_run_ready_candidate_count": bundle_record.engineering_analysis_ready_candidate_count,
            "selected_run_missing_inputs_candidate_count": (
                bundle_record.engineering_analysis_missing_inputs_candidate_count
            ),
            "selected_run_failed_candidate_count": bundle_record.engineering_analysis_failed_candidate_count,
            "selected_run_unique_missing_inputs": list(
                bundle_record.engineering_analysis_candidate_unique_missing_inputs
            ),
            "selected_run_ready_run_dirs": list(bundle_record.engineering_analysis_candidate_ready_run_dirs),
            "warnings": list(bundle_record.engineering_analysis_evidence_warnings),
            "action": bundle_record.engineering_analysis_evidence_action,
        },
        "geometry_reference_evidence": {
            "status": bundle_record.geometry_reference_status,
            "artifact_status": bundle_record.geometry_reference_artifact_status,
            "artifact_freshness_status": bundle_record.geometry_reference_artifact_freshness_status,
            "artifact_freshness_relation": bundle_record.geometry_reference_artifact_freshness_relation,
            "artifact_freshness_reason": bundle_record.geometry_reference_artifact_freshness_reason,
            "latest_artifact_status": bundle_record.geometry_reference_latest_artifact_status,
            "road_width_status": bundle_record.geometry_reference_road_width_status,
            "road_width_source": bundle_record.geometry_reference_road_width_source,
            "packaging_status": bundle_record.geometry_reference_packaging_status,
            "packaging_mismatch_status": bundle_record.geometry_reference_packaging_mismatch_status,
            "packaging_contract_hash": bundle_record.geometry_reference_packaging_contract_hash,
            "geometry_acceptance_gate": bundle_record.geometry_reference_acceptance_gate,
            "producer_artifact_status": bundle_record.geometry_reference_producer_artifact_status,
            "producer_readiness_reasons": list(bundle_record.geometry_reference_producer_readiness_reasons),
            "producer_evidence_owner": bundle_record.geometry_reference_producer_evidence_owner,
            "producer_required_artifacts": list(bundle_record.geometry_reference_producer_required_artifacts),
            "producer_next_action": bundle_record.geometry_reference_producer_next_action,
            "consumer_may_fabricate_geometry": bundle_record.geometry_reference_consumer_may_fabricate_geometry,
            "component_passport_needs_data": bundle_record.geometry_reference_component_passport_needs_data,
            "evidence_missing": list(bundle_record.geometry_reference_evidence_missing),
            "warnings": list(bundle_record.geometry_reference_warnings),
            "action": bundle_record.geometry_reference_action,
        },
        "animation_diagnostics_handoff": {
            "status": bundle_record.animation_diagnostics_handoff_status,
            "handoff_hash": bundle_record.animation_diagnostics_handoff_hash,
            "sidecar_path": bundle_record.latest_animation_diagnostics_handoff_path,
            "selected_title": bundle_record.animation_diagnostics_selected_title,
            "selected_path": bundle_record.animation_diagnostics_selected_path,
            "scene_npz_path": bundle_record.animation_diagnostics_scene_npz_path,
            "pointer_json_path": bundle_record.animation_diagnostics_pointer_json_path,
            "mnemo_event_log_path": bundle_record.animation_diagnostics_mnemo_event_log_path,
            "next_step": bundle_record.animation_diagnostics_next_step,
        },
    }
    _safe_write_json(path, payload)
    return path


def copy_latest_bundle_to_clipboard(
    repo_root: Path,
    *,
    out_dir: Optional[Path | str] = None,
    zip_path: Optional[Path | str] = None,
) -> tuple[DesktopDiagnosticsBundleRecord, bool, str]:
    bundle = load_desktop_diagnostics_bundle_record(repo_root, out_dir=out_dir)
    resolved_out_dir = Path(bundle.out_dir).expanduser().resolve()

    chosen_zip = Path(zip_path).expanduser().resolve() if zip_path else None
    if chosen_zip is None and bundle.latest_zip_path:
        chosen_zip = Path(bundle.latest_zip_path).expanduser().resolve()
    if chosen_zip is None or not chosen_zip.exists():
        return bundle, False, "ZIP ещё не готов."

    try:
        ok, message = copy_file_to_clipboard(chosen_zip)
    except Exception as exc:
        ok, message = False, f"{type(exc).__name__}: {exc}"

    full_ok = _is_full_file_clipboard_success(bool(ok), str(message))
    write_send_bundle_clipboard_status(resolved_out_dir, chosen_zip, full_ok, str(message))
    return load_desktop_diagnostics_bundle_record(repo_root, out_dir=resolved_out_dir), full_ok, str(message)
