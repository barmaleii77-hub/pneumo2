# -*- coding: utf-8 -*-
from __future__ import annotations

import json
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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")


def _resolve_bundle_out_dir(repo_root: Path, out_dir: Optional[Path | str] = None) -> Path:
    if out_dir is not None:
        return Path(out_dir).expanduser().resolve()
    try:
        cfg = load_diagnostics_config(repo_root)
        return cfg.resolved_out_dir(repo_root)
    except Exception:
        return (repo_root / "send_bundles").resolve()


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

    latest_zip = Path(summary["zip_path"]).expanduser() if summary.get("zip_path") else None
    if latest_zip and latest_zip.exists():
        latest_zip = latest_zip.resolve()
    else:
        latest_zip = _pick_latest_bundle_candidate(resolved_out_dir)

    dashboard = load_latest_send_bundle_anim_dashboard(resolved_out_dir)
    summary_lines = [str(x) for x in (summary.get("summary_lines") or []) if str(x).strip()]
    if not summary_lines:
        summary_lines = [str(x) for x in format_anim_dashboard_brief_lines(dashboard) if str(x).strip()]

    clipboard_path = resolved_out_dir / "latest_send_bundle_clipboard_status.json"
    clipboard_status = _safe_read_json_dict(clipboard_path) if clipboard_path.exists() else {}

    return DesktopDiagnosticsBundleRecord(
        out_dir=path_str(resolved_out_dir),
        latest_zip_path=path_str(latest_zip),
        latest_zip_name=latest_zip.name if latest_zip else "",
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
        latest_clipboard_status_path=path_str(clipboard_path if clipboard_path.exists() else ""),
        anim_pointer_diagnostics_path=path_str(
            (resolved_out_dir / ANIM_DIAG_SIDECAR_JSON)
            if (resolved_out_dir / ANIM_DIAG_SIDECAR_JSON).exists()
            else summary.get("anim_pointer_diagnostics_path") or ""
        ),
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
            "latest_bundle_meta_json": bundle_record.latest_bundle_meta_path,
            "latest_bundle_inspection_json": bundle_record.latest_inspection_json_path,
            "latest_bundle_inspection_md": bundle_record.latest_inspection_md_path,
            "latest_health_report_json": bundle_record.latest_health_json_path,
            "latest_health_report_md": bundle_record.latest_health_md_path,
            "latest_validation_json": bundle_record.latest_validation_json_path,
            "latest_validation_md": bundle_record.latest_validation_md_path,
            "latest_triage_md": bundle_record.latest_triage_md_path,
            "latest_clipboard_status_json": bundle_record.latest_clipboard_status_path,
            "anim_pointer_diagnostics_json": bundle_record.anim_pointer_diagnostics_path,
            "latest_run_state_json": run_record.state_path if run_record is not None else "",
            "latest_run_log": run_record.log_path if run_record is not None else "",
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
