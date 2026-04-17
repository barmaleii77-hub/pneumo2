#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_send_bundle.py

Цель
----
Сделать *один* ZIP-файл, который можно отправить в чат после закрытия приложения.

Это "сборщик контекста" для отладки и воспроизводимости:

- логи UI (JSONL + .log) из `pneumo_solver_ui/logs/`
- артефакты `workspace/exports` (если есть)
- последние прогоны автономных тестов:
  - `pneumo_solver_ui/autotest_runs/`
  - `diagnostics_runs/` (full diagnostics runner)
- снимок окружения: `pip freeze`, `pip check`, версии Python/OS
- манифест целостности: SHA256 по добавленным файлам + список пропусков

ВАЖНО
-----
Скрипт старается быть "best effort": если каких-то папок нет — не падает.

Запуск
------
  python -m pneumo_solver_ui.tools.make_send_bundle --print_path

Рекомендуемый сценарий (Windows, max reliability):
  - Запускаете UI через RUN_WINDOWS_SILENT.bat (wrapper + postmortem watchdog)
  - Закрываете UI (Ctrl+C в консоли)
  - Скрипт создаёт bundle автоматически и открывает "копировщик" ZIP (см. send_results_gui)

"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .send_bundle_contract import (
    ANIM_DIAG_JSON,
    ANIM_DIAG_MD,
    ANIM_DIAG_SIDECAR_JSON,
    ANIM_DIAG_SIDECAR_MD,
    build_anim_operator_recommendations,
    extract_anim_snapshot,
)
from .send_bundle_evidence import (
    ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME,
    ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME,
    ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME,
    EVIDENCE_MANIFEST_ARCNAME,
    EVIDENCE_MANIFEST_SIDECAR_NAME,
    GEOMETRY_REFERENCE_EVIDENCE_ARCNAME,
    GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME,
    GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME,
    build_evidence_manifest,
    classify_collection_mode,
    helper_runtime_provenance,
    read_manifest_inputs_from_zip,
)


try:
    from pneumo_solver_ui.release_info import get_release
    RELEASE = get_release(default="UNIFIED_v6_40")
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_40") or "UNIFIED_v6_40"


def _atomic_write_text(path: Path, text: str) -> None:
    """Atomically write a text file using temp + os.replace().

    Why: 'latest_*' sidecar files should never be half-written if multiple
    processes try to update them.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", errors="replace")
    os.replace(str(tmp), str(path))


def _atomic_copy_file(src: Path, dst: Path) -> None:
    """Atomically copy file to dst using temp + os.replace()."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    shutil.copy2(src, tmp)
    os.replace(str(tmp), str(dst))


@dataclass
class AddResult:
    added_files: int = 0
    added_bytes: int = 0
    skipped_files: int = 0
    skipped_bytes: int = 0


def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _sanitize_tag(tag: Optional[str], *, max_len: int = 48) -> str:
    """Filesystem-safe tag suffix for ZIP names.

    Allowed: A-Z a-z 0-9 . _ -
    Spaces -> underscore, everything else removed.
    """
    if not tag:
        return ""
    s = str(tag).strip()
    if not s:
        return ""
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9._-]+", "", s)
    s = s.strip("._-")
    if len(s) > max_len:
        s = s[:max_len]
    return s


def _maybe_run_selfcheck_suite(repo_root: Path) -> Optional[Path]:
    """Run preflight/self_check/property_invariants suite before building a bundle.

    Controlled via env:
      - PNEUMO_BUNDLE_RUN_SELFCHECK = 1/0 (default: 1)
      - PNEUMO_BUNDLE_SELFCHECK_LEVEL = quick|standard|full (default: standard)

    Writes machine-readable artifacts into diagnostics_runs/RUN_SELFCHECK_<ts>/
    so that the bundle always contains:
      - preflight_gate
      - property_invariants (via preflight)
      - self_check (via preflight)
      - selfcheck_report.json (from selfcheck_suite)
    """
    try:
        flag = (os.environ.get("PNEUMO_BUNDLE_RUN_SELFCHECK", "1") or "1").strip().lower()
        if flag in ("0", "false", "no", "off"):
            return None
        level = (os.environ.get("PNEUMO_BUNDLE_SELFCHECK_LEVEL", "standard") or "standard").strip().lower()
        if level not in ("quick", "standard", "full"):
            level = "standard"
        out_dir = repo_root / "diagnostics_runs" / f"RUN_SELFCHECK_{_ts()}"
        out_dir.mkdir(parents=True, exist_ok=True)
        # Record intent (even if the suite fails)
        intent = {
            "schema": "selfcheck_intent",
            "schema_version": "1.0.0",
            "release": RELEASE,
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": level,
            "env": {
                "PNEUMO_BUNDLE_RUN_SELFCHECK": os.environ.get("PNEUMO_BUNDLE_RUN_SELFCHECK", ""),
                "PNEUMO_BUNDLE_SELFCHECK_LEVEL": os.environ.get("PNEUMO_BUNDLE_SELFCHECK_LEVEL", ""),
            },
        }
        try:
            (out_dir / "selfcheck_intent.json").write_text(json.dumps(intent, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        # Run suite (best-effort)
        try:
            from pneumo_solver_ui.tools.selfcheck_suite import run_selfcheck_suite
            rep = run_selfcheck_suite(repo_root=repo_root, out_dir=out_dir, level=level)
            verdict = {
                "schema": "selfcheck_verdict",
                "schema_version": "1.0.0",
                "release": RELEASE,
                "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "ok": bool(getattr(rep, "ok", False)),
                "level": level,
            }
            try:
                (out_dir / "selfcheck_verdict.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        except Exception:
            try:
                (out_dir / "selfcheck_suite_exception.txt").write_text(traceback.format_exc(), encoding="utf-8")
            except Exception:
                pass
        return out_dir
    except Exception:
        return None


# ------------------------------------------------------------
# R53: Session-level marker to prevent duplicate bundles.
# Used by:
#   - send_results_gui (avoid creating multiple ZIPs for the same UI session)
#   - postmortem_watchdog (detect whether bundle was already created)
# ------------------------------------------------------------

def _session_marker_path(primary_session_dir: Path) -> Path:
    return Path(primary_session_dir) / "_send_bundle_done.json"


def _load_existing_from_marker(marker_path: Path) -> Optional[Path]:
    try:
        if marker_path.exists() and marker_path.is_file():
            j = json.loads(marker_path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(j, dict):
                zp = j.get("zip_path") or j.get("latest_zip_path")
                if zp:
                    p = Path(str(zp)).expanduser()
                    if p.exists() and p.is_file():
                        return p.resolve()
    except Exception:
        return None
    return None


def _write_session_marker(
    marker_path: Path,
    *,
    zip_path: Path,
    latest_zip_path: Optional[Path],
    meta: Dict[str, Any],
) -> None:
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        payload: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "release": RELEASE,
            "zip_path": str(Path(zip_path).resolve()),
            "latest_zip_path": str(Path(latest_zip_path).resolve()) if latest_zip_path else None,
            "primary_session_dir": meta.get("primary_session_dir"),
            "meta": {
                "created_at": meta.get("created_at"),
                "max_file_mb": meta.get("max_file_mb"),
                "keep_last_n": meta.get("keep_last_n"),
            },
        }
        tmp = marker_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", errors="replace")
        tmp.replace(marker_path)
    except Exception:
        # best-effort marker, ignore errors
        pass


def _safe_write_text(path: Path, text: str) -> None:
    """Best-effort safe text write.

    R54: write atomically (temp + os.replace) to avoid partial updates of
    'latest_*' sidecar files under concurrent writers.
    """
    try:
        _atomic_write_text(path, text)
        return
    except Exception:
        # Fallback to non-atomic direct write.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", errors="replace")


def _format_anim_diag_error(exc: BaseException) -> str:
    if isinstance(exc, ModuleNotFoundError):
        missing = str(getattr(exc, "name", "") or "").strip() or "unknown"
        return f"Отсутствует необязательная зависимость: {missing}"
    return repr(exc)


def _collect_anim_latest_bundle_diagnostics(out_dir: Path) -> Tuple[Dict[str, Any], str]:
    """Build sidecar diagnostics for the current global anim_latest pointer.

    The payload is shared between send-bundle sidecars, run-registry events and
    launcher diagnostics so that all three surfaces talk about the same active
    anim_latest bundle/token.
    """
    diag: Dict[str, Any]
    try:
        from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary

        diag = dict(collect_anim_latest_diagnostics_summary(include_meta=True) or {})
    except Exception as exc:
        friendly_error = _format_anim_diag_error(exc)
        diag = {
            "anim_latest_available": False,
            "error": friendly_error,
            "anim_latest_issues": [
                f"Не удалось собрать anim_latest diagnostics: {friendly_error}.",
            ],
        }

    deps = dict(diag.get("anim_latest_visual_cache_dependencies") or {})
    meta = dict(diag.get("anim_latest_meta") or {})
    try:
        from pneumo_solver_ui.anim_export_contract import summarize_anim_export_contract, summarize_anim_export_validation

        contract_summary = dict(summarize_anim_export_contract(meta) or {})
        validation_summary = dict(summarize_anim_export_validation(meta) or {})
    except Exception:
        contract_summary = {}
        validation_summary = {}

    def _resolve_sidecar(ref: Any, *, pointer_json: Any, fallback_path: Any = None) -> tuple[str, str, bool | None]:
        ref_s = str(ref or "").strip()
        if not ref_s and fallback_path not in (None, ""):
            ref_s = str(fallback_path or "").strip()
        if not ref_s:
            return "", "", None
        p = Path(ref_s)
        if not p.is_absolute():
            try:
                ptr = Path(str(pointer_json or "")).expanduser()
                if str(ptr):
                    p = (ptr.parent / p).resolve()
            except Exception:
                p = Path(ref_s)
        try:
            exists = bool(p.exists())
        except Exception:
            exists = None
        return str(ref_s), str(p), exists

    pointer_json = diag.get("anim_latest_pointer_json") or ""
    road_ref, road_path, road_exists = _resolve_sidecar(
        meta.get("road_csv"),
        pointer_json=pointer_json,
        fallback_path=(deps.get("road_csv") or {}).get("path") or deps.get("road_csv_path"),
    )
    axay_ref, axay_path, axay_exists = _resolve_sidecar(meta.get("axay_csv"), pointer_json=pointer_json)
    scenario_ref, scenario_path, scenario_exists = _resolve_sidecar(meta.get("scenario_json"), pointer_json=pointer_json)
    diag["anim_latest_road_csv_ref"] = road_ref
    diag["anim_latest_road_csv_path"] = road_path
    diag["anim_latest_road_csv_exists"] = road_exists
    diag["anim_latest_axay_csv_ref"] = axay_ref
    diag["anim_latest_axay_csv_path"] = axay_path
    diag["anim_latest_axay_csv_exists"] = axay_exists
    diag["anim_latest_scenario_json_ref"] = scenario_ref
    diag["anim_latest_scenario_json_path"] = scenario_path
    diag["anim_latest_scenario_json_exists"] = scenario_exists
    if contract_summary:
        diag.update({f"anim_latest_{k}": v for k, v in contract_summary.items()})
    if validation_summary:
        diag.update({f"anim_latest_{k}": v for k, v in validation_summary.items()})

    issues = [str(x) for x in (diag.get('anim_latest_issues') or []) if str(x).strip()]
    lines = ["# Anim Latest Pointer Diagnostics", ""]
    lines.append(f"- anim_latest_available: {bool(diag.get('anim_latest_available'))}")
    lines.append(f"- anim_latest_usable: {diag.get('anim_latest_usable')}")
    lines.append(f"- anim_latest_pointer_json_exists: {diag.get('anim_latest_pointer_json_exists')}")
    lines.append(f"- anim_latest_npz_exists: {diag.get('anim_latest_npz_exists')}")
    lines.append(f"- anim_latest_global_pointer_json: {diag.get('anim_latest_global_pointer_json') or '—'}")
    lines.append(f"- anim_latest_pointer_json: {diag.get('anim_latest_pointer_json') or '—'}")
    lines.append(f"- anim_latest_npz_path: {diag.get('anim_latest_npz_path') or '—'}")
    lines.append(f"- anim_latest_road_csv: {diag.get('anim_latest_road_csv_ref') or '—'} -> {diag.get('anim_latest_road_csv_path') or '—'} (exists={diag.get('anim_latest_road_csv_exists')})")
    lines.append(f"- anim_latest_axay_csv: {diag.get('anim_latest_axay_csv_ref') or '—'} -> {diag.get('anim_latest_axay_csv_path') or '—'} (exists={diag.get('anim_latest_axay_csv_exists')})")
    lines.append(f"- anim_latest_scenario_json: {diag.get('anim_latest_scenario_json_ref') or '—'} -> {diag.get('anim_latest_scenario_json_path') or '—'} (exists={diag.get('anim_latest_scenario_json_exists')})")
    lines.append(f"- anim_latest_contract_sidecar: {diag.get('anim_latest_contract_sidecar_ref') or '—'} -> {diag.get('anim_latest_contract_sidecar_path') or '—'} (exists={diag.get('anim_latest_contract_sidecar_exists')})")
    lines.append(f"- anim_latest_hardpoints_source_of_truth: {diag.get('anim_latest_hardpoints_source_of_truth_ref') or '—'} -> {diag.get('anim_latest_hardpoints_source_of_truth_path') or '—'} (exists={diag.get('anim_latest_hardpoints_source_of_truth_exists')})")
    lines.append(f"- anim_latest_cylinder_packaging_passport: {diag.get('anim_latest_cylinder_packaging_passport_ref') or '—'} -> {diag.get('anim_latest_cylinder_packaging_passport_path') or '—'} (exists={diag.get('anim_latest_cylinder_packaging_passport_exists')})")
    lines.append(f"- anim_latest_road_contract_web: {diag.get('anim_latest_road_contract_web_ref') or '—'} -> {diag.get('anim_latest_road_contract_web_path') or '—'} (exists={diag.get('anim_latest_road_contract_web_exists')})")
    lines.append(f"- anim_latest_road_contract_desktop: {diag.get('anim_latest_road_contract_desktop_ref') or '—'} -> {diag.get('anim_latest_road_contract_desktop_path') or '—'} (exists={diag.get('anim_latest_road_contract_desktop_exists')})")
    lines.append(
        f"- anim_latest_mnemo_event_log: {diag.get('anim_latest_mnemo_event_log_ref') or '—'} -> {diag.get('anim_latest_mnemo_event_log_path') or '—'} "
        f"(exists={diag.get('anim_latest_mnemo_event_log_exists')}, schema={diag.get('anim_latest_mnemo_event_log_schema_version') or '—'}, updated_utc={diag.get('anim_latest_mnemo_event_log_updated_utc') or '—'})"
    )
    lines.append(
        f"- anim_latest_mnemo_event_log_state: mode={diag.get('anim_latest_mnemo_event_log_current_mode') or '—'} / total={diag.get('anim_latest_mnemo_event_log_event_count')} / active={diag.get('anim_latest_mnemo_event_log_active_latch_count')} / acked={diag.get('anim_latest_mnemo_event_log_acknowledged_latch_count')}"
    )
    recent_titles = [str(x) for x in (diag.get("anim_latest_mnemo_event_log_recent_titles") or []) if str(x).strip()]
    if recent_titles:
        lines.append(f"- anim_latest_mnemo_event_log_recent: {' | '.join(recent_titles[:3])}")
    lines.append(f"- browser_perf_registry_snapshot: {diag.get('browser_perf_registry_snapshot_ref') or '—'} -> {diag.get('browser_perf_registry_snapshot_path') or '—'} (exists={diag.get('browser_perf_registry_snapshot_exists')}, in_bundle={diag.get('browser_perf_registry_snapshot_in_bundle')})")
    lines.append(f"- browser_perf_previous_snapshot: {diag.get('browser_perf_previous_snapshot_ref') or '—'} -> {diag.get('browser_perf_previous_snapshot_path') or '—'} (exists={diag.get('browser_perf_previous_snapshot_exists')}, in_bundle={diag.get('browser_perf_previous_snapshot_in_bundle')})")
    lines.append(f"- browser_perf_contract: {diag.get('browser_perf_contract_ref') or '—'} -> {diag.get('browser_perf_contract_path') or '—'} (exists={diag.get('browser_perf_contract_exists')}, in_bundle={diag.get('browser_perf_contract_in_bundle')})")
    lines.append(f"- browser_perf_evidence_report: {diag.get('browser_perf_evidence_report_ref') or '—'} -> {diag.get('browser_perf_evidence_report_path') or '—'} (exists={diag.get('browser_perf_evidence_report_exists')}, in_bundle={diag.get('browser_perf_evidence_report_in_bundle')})")
    lines.append(f"- browser_perf_comparison_report: {diag.get('browser_perf_comparison_report_ref') or '—'} -> {diag.get('browser_perf_comparison_report_path') or '—'} (exists={diag.get('browser_perf_comparison_report_exists')}, in_bundle={diag.get('browser_perf_comparison_report_in_bundle')})")
    lines.append(f"- browser_perf_trace: {diag.get('browser_perf_trace_ref') or '—'} -> {diag.get('browser_perf_trace_path') or '—'} (exists={diag.get('browser_perf_trace_exists')}, in_bundle={diag.get('browser_perf_trace_in_bundle')})")
    lines.append(f"- browser_perf_status: {diag.get('browser_perf_status') or '—'} / level={diag.get('browser_perf_level') or '—'}")
    lines.append(f"- browser_perf_evidence_status: {diag.get('browser_perf_evidence_status') or '—'} / level={diag.get('browser_perf_evidence_level') or '—'} / bundle_ready={diag.get('browser_perf_bundle_ready')} / snapshot_contract_match={diag.get('browser_perf_snapshot_contract_match')}")
    lines.append(f"- browser_perf_comparison_status: {diag.get('browser_perf_comparison_status') or '—'} / level={diag.get('browser_perf_comparison_level') or '—'} / ready={diag.get('browser_perf_comparison_ready')} / changed={diag.get('browser_perf_comparison_changed')}")
    lines.append(f"- browser_perf_comparison_delta: wakeups={diag.get('browser_perf_comparison_delta_total_wakeups')} / dup={diag.get('browser_perf_comparison_delta_total_duplicate_guard_hits')} / render={diag.get('browser_perf_comparison_delta_total_render_count')} / max_idle_poll_ms={diag.get('browser_perf_comparison_delta_max_idle_poll_ms')}")
    lines.append(f"- browser_perf_component_count: {diag.get('browser_perf_component_count')} / total_wakeups={diag.get('browser_perf_total_wakeups')} / total_duplicate_guard_hits={diag.get('browser_perf_total_duplicate_guard_hits')} / max_idle_poll_ms={diag.get('browser_perf_max_idle_poll_ms')}")
    lines.append(f"- anim_latest_visual_cache_token: {diag.get('anim_latest_visual_cache_token') or '—'}")
    reload_inputs = list(diag.get('anim_latest_visual_reload_inputs') or [])
    lines.append(f"- anim_latest_visual_reload_inputs: {', '.join(str(x) for x in reload_inputs) if reload_inputs else '—'}")
    lines.append(f"- anim_latest_updated_utc: {diag.get('anim_latest_updated_utc') or '—'}")
    if contract_summary:
        lines.append(f"- anim_latest_has_solver_points_block: {diag.get('anim_latest_has_solver_points_block')}")
        lines.append(f"- anim_latest_has_hardpoints_block: {diag.get('anim_latest_has_hardpoints_block')}")
        lines.append(f"- anim_latest_has_packaging_block: {diag.get('anim_latest_has_packaging_block')}")
        lines.append(f"- anim_latest_packaging_status: {diag.get('anim_latest_packaging_status') or '—'}")
        lines.append(f"- anim_latest_packaging_truth_ready: {diag.get('anim_latest_packaging_truth_ready')}")
    if validation_summary:
        lines.append(f"- anim_latest_validation_level: {diag.get('anim_latest_validation_level') or '—'}")
        lines.append(f"- anim_latest_validation_visible_present_family_count: {diag.get('anim_latest_validation_visible_present_family_count')} / {diag.get('anim_latest_validation_visible_required_family_count')}")
        lines.append(f"- anim_latest_validation_packaging_status: {diag.get('anim_latest_validation_packaging_status') or '—'}")
        lines.append(f"- anim_latest_validation_packaging_truth_ready: {diag.get('anim_latest_validation_packaging_truth_ready')}")
    if issues:
        lines.extend(["", "## anim_latest_issues", *[f"- {x}" for x in issues]])
    if deps:
        lines.extend(["", "## visual_cache_dependencies", "```json", json.dumps(deps, ensure_ascii=False, indent=2), "```"])
    if diag.get('anim_latest_meta'):
        lines.extend(["", "## anim_latest_meta", "```json", json.dumps(diag.get('anim_latest_meta'), ensure_ascii=False, indent=2), "```"])
    if diag.get('error'):
        lines.extend(["", f"error: {diag.get('error')}"])
    md = "\n".join(lines).rstrip() + "\n"

    try:
        _safe_write_text(out_dir / ANIM_DIAG_SIDECAR_JSON, json.dumps(diag, ensure_ascii=False, indent=2))
        _safe_write_text(out_dir / ANIM_DIAG_SIDECAR_MD, md)
    except Exception:
        pass
    return diag, md


def _build_send_bundle_readme(anim_diag: Optional[Dict[str, Any]] = None) -> str:
    """Human-readable README for the final send bundle.

    The README must expose the active anim_latest reload reason so the recipient
    does not need to open separate sidecars just to see which bundle/token was active.
    """
    diag_raw = dict(anim_diag or {})
    diag_snap = extract_anim_snapshot(diag_raw, source="send_bundle_readme")
    diag = dict(diag_raw)
    if isinstance(diag_snap, dict):
        for key, value in diag_snap.items():
            if diag.get(key) in (None, "", [], {}):
                diag[key] = value
    reload_inputs = list(diag.get("anim_latest_visual_reload_inputs") or [])
    issues = [str(x) for x in (diag.get("anim_latest_issues") or []) if str(x).strip()]
    operator_recommendations = build_anim_operator_recommendations(diag)
    issues_preview = "; ".join(issues[:3]) if issues else "—"
    recommendations_preview = (
        "".join(f"- {item}\n" for item in operator_recommendations[:5])
        if operator_recommendations
        else "- none\n"
    )
    road_ref = diag.get("anim_latest_road_csv_ref") or "—"
    axay_ref = diag.get("anim_latest_axay_csv_ref") or "—"
    scenario_ref = diag.get("anim_latest_scenario_json_ref") or "—"
    scenario_kind = diag.get("scenario_kind") or "—"
    ring_closure_policy = diag.get("ring_closure_policy") or "—"
    ring_closure_applied = diag.get("ring_closure_applied")
    ring_seam_open = diag.get("ring_seam_open")
    ring_seam_max = diag.get("ring_seam_max_jump_m")
    ring_raw_seam_max = diag.get("ring_raw_seam_max_jump_m")
    browser_perf_status = diag.get("browser_perf_status") or "—"
    browser_perf_level = diag.get("browser_perf_level") or "—"
    browser_perf_evidence_status = diag.get("browser_perf_evidence_status") or "—"
    browser_perf_evidence_level = diag.get("browser_perf_evidence_level") or "—"
    browser_perf_comparison_status = diag.get("browser_perf_comparison_status") or "—"
    browser_perf_comparison_level = diag.get("browser_perf_comparison_level") or "—"
    browser_perf_trace_ref = diag.get("browser_perf_trace_ref") or "—"
    browser_perf_snapshot_ref = diag.get("browser_perf_registry_snapshot_ref") or "—"
    browser_perf_prev_snapshot_ref = diag.get("browser_perf_previous_snapshot_ref") or "—"
    browser_perf_evidence_ref = diag.get("browser_perf_evidence_report_ref") or "—"
    browser_perf_comparison_ref = diag.get("browser_perf_comparison_report_ref") or "—"
    return (
        "SEND BUNDLE (for chat)\n"
        "======================\n\n"
        "Этот ZIP сформирован автоматически и предназначен для отправки в чат\n"
        "после закрытия приложения.\n\n"
        "Содержимое (best-effort):\n"
        "- triage/: короткий triage-отчёт (md+json) по последним запускам\n"
        "- health/: сводный health-report по bundle (json+md)\n"
        "- diagnostics/evidence_manifest.json: manifest of expected SEND evidence classes\n"
        "- ui_logs/: логи UI (jsonl + .log)\n- root_logs/: логи запуска Streamlit/скриптов (repo_root/logs, напр. streamlit.log)\n- reports/: отчёты качества логов (loglint/logstats, автогенерация)\n"
        "- autotest/: последние прогоны run_autotest (если запускались)\n"
        "- diagnostics_runs/: последние прогоны run_full_diagnostics (если запускались)\n- ui_sessions/: последние UI-сессии (runs/ui_sessions)\n- runs/: run_registry.jsonl и index.json (если есть)\n- workspace/: exports/uploads/road_profiles/maneuvers/opt_runs/ui_state (+ marker если пусто)\n"
        "- config/: default_*.json + component_passport.json\n"
        "- env/: pip_freeze / pip_check / версии\n"
        "- manifest.json: SHA256 по каждому добавленному файлу\n\n"
        "Anim latest diagnostics (canonical):\n"
        f"- anim_latest_available: {bool(diag.get('anim_latest_available'))}\n"
        f"- anim_latest_visual_cache_token: {diag.get('anim_latest_visual_cache_token') or '—'}\n"
        f"- anim_latest_visual_reload_inputs: {', '.join(str(x) for x in reload_inputs) if reload_inputs else '—'}\n"
        f"- anim_latest_usable: {diag.get('anim_latest_usable')}\n"
        f"- anim_latest_pointer_json_exists: {diag.get('anim_latest_pointer_json_exists')}\n"
        f"- anim_latest_npz_exists: {diag.get('anim_latest_npz_exists')}\n"
        f"- anim_latest_global_pointer_json: {diag.get('anim_latest_global_pointer_json') or '—'}\n"
        f"- anim_latest_pointer_json: {diag.get('anim_latest_pointer_json') or '—'}\n"
        f"- anim_latest_npz_path: {diag.get('anim_latest_npz_path') or '—'}\n"
        f"- scenario_kind: {scenario_kind}\n"
        f"- anim_latest_road_csv_ref: {road_ref}\n"
        f"- anim_latest_axay_csv_ref: {axay_ref}\n"
        f"- anim_latest_scenario_json_ref: {scenario_ref}\n"
        f"- ring_closure: policy={ring_closure_policy} / applied={ring_closure_applied} / seam_open={ring_seam_open} / seam_max_jump_m={ring_seam_max if ring_seam_max is not None else '—'} / raw_seam_max_jump_m={ring_raw_seam_max if ring_raw_seam_max is not None else '—'}\n"
        f"- anim_latest_contract_sidecar_ref: {diag.get('anim_latest_contract_sidecar_ref') or '—'}\n"
        f"- anim_latest_hardpoints_source_of_truth_ref: {diag.get('anim_latest_hardpoints_source_of_truth_ref') or '—'}\n"
        f"- anim_latest_cylinder_packaging_passport_ref: {diag.get('anim_latest_cylinder_packaging_passport_ref') or '—'}\n"
        f"- anim_latest_road_contract_web_ref: {diag.get('anim_latest_road_contract_web_ref') or '—'}\n"
        f"- anim_latest_road_contract_desktop_ref: {diag.get('anim_latest_road_contract_desktop_ref') or '—'}\n"
        f"- browser_perf_status: {browser_perf_status} / level={browser_perf_level}\n"
        f"- browser_perf_snapshot_ref: {browser_perf_snapshot_ref}\n"
        f"- browser_perf_previous_snapshot_ref: {browser_perf_prev_snapshot_ref}\n"
        f"- browser_perf_evidence_ref: {browser_perf_evidence_ref}\n"
        f"- browser_perf_evidence_status: {browser_perf_evidence_status} / level={browser_perf_evidence_level}\n"
        f"- browser_perf_comparison_ref: {browser_perf_comparison_ref}\n"
        f"- browser_perf_comparison_status: {browser_perf_comparison_status} / level={browser_perf_comparison_level}\n"
        f"- browser_perf_trace_ref: {browser_perf_trace_ref}\n"
        f"- anim_latest_updated_utc: {diag.get('anim_latest_updated_utc') or '—'}\n"
        f"- anim_latest_issues: {issues_preview}\n"
        "Recommended actions (operator-first):\n"
        f"{recommendations_preview}"
        f"- In bundle: {ANIM_DIAG_JSON}\n"
        f"- In bundle: {ANIM_DIAG_MD}\n"
        "- In bundle: health/health_report.json\n"
        "- In bundle: health/health_report.md\n\n"
        "Если каких-то папок нет, они не будут включены.\n"
    )


def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def _resolve_cli_python_executable() -> str:
    """Prefer a deterministic console interpreter for helper subprocesses.

    Resolution order:
    1) launcher-provided explicit shared venv python (if present),
    2) sibling ``python.exe`` for current ``pythonw.exe``,
    3) current interpreter as-is.
    """
    for env_key in ("PNEUMO_SHARED_VENV_PYTHON", "PNEUMO_VENV_PYTHON"):
        try:
            raw = str(os.environ.get(env_key) or "").strip()
            if raw:
                cand = Path(raw)
                if cand.exists():
                    return str(cand)
        except Exception:
            pass
    try:
        exe = Path(sys.executable)
        if exe.name.lower() == "pythonw.exe":
            cand = exe.with_name("python.exe")
            if cand.exists():
                return str(cand)
        return str(exe)
    except Exception:
        return str(sys.executable)


def _health_report_failure_payload(zip_path: Path, error_text: str) -> Dict[str, Any]:
    return {
        "schema": "health_report",
        "schema_version": "1.3.0",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "zip_path": str(zip_path),
        "ok": False,
        "signals": {
            "health_report_error": {
                "error": str(error_text),
                "python_executable": str(sys.executable),
                "python_prefix": str(getattr(sys, "prefix", "")),
                "python_base_prefix": str(getattr(sys, "base_prefix", getattr(sys, "prefix", ""))),
                "preferred_cli_python": _resolve_cli_python_executable(),
            }
        },
        "notes": [
            "health report generation failed; embedded fallback stub instead of dropping artifact",
            str(error_text),
        ],
    }


def _render_health_report_failure_md(payload: Dict[str, Any]) -> str:
    err = dict((payload.get("signals") or {}).get("health_report_error") or {})
    notes = [str(x) for x in (payload.get("notes") or [])]
    lines = [
        "# Health report",
        "",
        f"- Created: {payload.get('created_at')}",
        f"- ZIP: `{Path(str(payload.get('zip_path') or '')).name}`",
        f"- OK: **{payload.get('ok')}**",
        "",
        "## Error",
        f"- python_executable: `{err.get('python_executable') or '—'}`",
        f"- preferred_cli_python: `{err.get('preferred_cli_python') or '—'}`",
        f"- python_prefix: `{err.get('python_prefix') or '—'}`",
        f"- python_base_prefix: `{err.get('python_base_prefix') or '—'}`",
        f"- error: `{err.get('error') or '—'}`",
    ]
    if notes:
        lines += ["", "## Notes"] + [f"- {x}" for x in notes]
    return "\n".join(lines) + "\n"


def _write_health_report_failure_stub(zip_path: Path, out_dir: Path, error_text: str) -> Tuple[Path, Path]:
    payload = _health_report_failure_payload(zip_path, error_text)
    json_path = out_dir / "latest_health_report.json"
    md_path = out_dir / "latest_health_report.md"
    _atomic_write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2))
    _atomic_write_text(md_path, _render_health_report_failure_md(payload))
    return json_path, md_path


def _run(cmd: List[str], cwd: Optional[Path] = None, timeout_s: float = 120.0) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        return int(p.returncode), p.stdout, p.stderr
    except Exception as e:
        return 999, "", f"{e}\n{traceback.format_exc()}"


def _pick_latest_dirs(parent: Path, prefix: str, keep_last_n: int) -> List[Path]:
    if not parent.exists():
        return []
    items = [p for p in parent.iterdir() if p.is_dir() and p.name.startswith(prefix)]
    items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return items[: max(0, int(keep_last_n))]


def _pick_latest_zips(parent: Path, prefix: str, keep_last_n: int) -> List[Path]:
    if not parent.exists():
        return []
    items = [p for p in parent.iterdir() if p.is_file() and p.suffix.lower() == ".zip" and p.name.startswith(prefix)]
    items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return items[: max(0, int(keep_last_n))]


# --- Tail-sampling for huge logs (keep diagnostic value) ---
_TEXT_LIKE_EXTS = {
    ".log", ".txt", ".jsonl", ".json", ".md", ".csv", ".yaml", ".yml",
    ".ini", ".cfg", ".py", ".bat", ".cmd", ".ps1", ".sh"
}

def _is_text_like(path: Path) -> bool:
    try:
        return path.suffix.lower() in _TEXT_LIKE_EXTS
    except Exception:
        return False

def _read_file_tail_text(path: Path, tail_bytes: int) -> str:
    """Read last `tail_bytes` bytes and decode as UTF-8 (errors=replace)."""
    try:
        tail_bytes = max(1, int(tail_bytes))
        sz = int(path.stat().st_size)
        start = max(0, sz - tail_bytes)
        with open(path, "rb") as f:
            if start > 0:
                f.seek(start)
            b = f.read(tail_bytes)
        return b.decode("utf-8", errors="replace")
    except Exception:
        return ""




def _add_file(
    z: zipfile.ZipFile,
    src: Path,
    arcname: str,
    *,
    manifest: Dict[str, Any],
    skips: List[Dict[str, Any]],
    max_file_bytes: int,
) -> AddResult:
    """Add one file into ZIP (best-effort).

    If file is larger than max_file_bytes and looks like text, we include a *tail*
    sample instead of skipping it entirely, to preserve diagnostic value.
    """
    r = AddResult()
    try:
        if not src.exists() or not src.is_file():
            return r

        sz = int(src.stat().st_size)
        if sz > max_file_bytes:
            # Tail-sample text-ish files instead of dropping completely (best-effort).
            tail_disable = (os.environ.get("PNEUMO_BUNDLE_TAIL_DISABLE") or "").strip().lower() in {"1", "true", "yes"}
            if (not tail_disable) and _is_text_like(src):
                try:
                    tb_default = min(2_000_000, max_file_bytes)
                    tb = int(os.environ.get("PNEUMO_BUNDLE_TAIL_BYTES", str(tb_default)) or tb_default)
                    tb = max(4096, min(tb, max_file_bytes, sz))
                except Exception:
                    tb = max(4096, min(2_000_000, max_file_bytes, sz))

                tail_text = _read_file_tail_text(src, tb)
                if tail_text:
                    banner = (
                        "TRUNCATED_TAIL_SAMPLE\n"
                        f"original_path: {src}\n"
                        f"original_arcname: {arcname}\n"
                        f"original_size_bytes: {sz}\n"
                        f"kept_tail_bytes: {tb}\n"
                        "---TAIL---\n"
                    )
                    content = (banner + tail_text).encode("utf-8", errors="replace")
                    tail_arc = ("truncated/" + arcname + ".tail.txt").replace("\\", "/")
                    z.writestr(tail_arc, content)
                    sha = hashlib.sha256(content).hexdigest()
                    manifest[tail_arc] = {
                        "src": str(src),
                        "sha256": sha,
                        "size_bytes": int(len(content)),
                        "truncated": True,
                        "original_arcname": arcname,
                        "original_size_bytes": sz,
                        "tail_bytes": int(tb),
                    }
                    r.added_files += 1
                    r.added_bytes += int(len(content))

                    skips.append({
                        "path": str(src),
                        "arcname": arcname,
                        "reason": "too_large_truncated_tail",
                        "size_bytes": sz,
                        "max_file_bytes": max_file_bytes,
                        "tail_arcname": tail_arc,
                        "tail_bytes": int(tb),
                    })
                    r.skipped_files += 1
                    r.skipped_bytes += sz
                    return r

            # Default behavior: skip too large files
            skips.append(
                {
                    "path": str(src),
                    "arcname": arcname,
                    "reason": "too_large",
                    "size_bytes": sz,
                    "max_file_bytes": max_file_bytes,
                }
            )
            r.skipped_files += 1
            r.skipped_bytes += sz
            return r

        sha = _sha256_file(src)
        z.write(src, arcname)
        manifest[arcname] = {"src": str(src), "sha256": sha, "size_bytes": sz}
        r.added_files += 1
        r.added_bytes += sz
        return r

    except Exception as e:
        skips.append({"path": str(src), "arcname": arcname, "reason": f"exception: {e}"})
        try:
            r.skipped_files += 1
            r.skipped_bytes += int(src.stat().st_size) if src.exists() and src.is_file() else 0
        except Exception:
            pass
        return r



def _add_generated_text(
    z: zipfile.ZipFile,
    arcname: str,
    text: str,
    *,
    manifest: Dict[str, Any],
) -> AddResult:
    # Write a generated UTF-8 text entry into ZIP and track it in manifest.
    # Used for contract/placeholder markers so required paths are never silently absent.
    r = AddResult()
    try:
        arc = str(arcname).replace('\\\\', '/')
        b = (text or '').encode('utf-8', errors='replace')
        z.writestr(arc, b)
        sha = hashlib.sha256(b).hexdigest()
        manifest[arc] = {
            'src': '<generated>',
            'sha256': sha,
            'size_bytes': int(len(b)),
            'generated': True,
        }
        r.added_files = 1
        r.added_bytes = int(len(b))
    except Exception:
        return r
    return r


def _add_tree(
    z: zipfile.ZipFile,
    src_dir: Path,
    arc_prefix: str,
    *,
    manifest: Dict[str, Any],
    skips: List[Dict[str, Any]],
    max_file_bytes: int,
    ignore_names: Optional[set[str]] = None,
) -> AddResult:
    r = AddResult()
    if not src_dir.exists() or not src_dir.is_dir():
        return r

    ignore_names = ignore_names or set()

    for f in _iter_files(src_dir):
        if any(part in ignore_names for part in f.parts):
            continue
        rel = f.relative_to(src_dir)
        arcname = str(Path(arc_prefix) / rel).replace("\\", "/")
        rr = _add_file(
            z,
            f,
            arcname,
            manifest=manifest,
            skips=skips,
            max_file_bytes=max_file_bytes,
        )
        r.added_files += rr.added_files
        r.added_bytes += rr.added_bytes
        r.skipped_files += rr.skipped_files
        r.skipped_bytes += rr.skipped_bytes

    return r


def _make_send_bundle_inner(
    repo_root: Path,
    *,
    out_dir: Path,
    keep_last_n: int = 3,
    max_file_mb: int = 80,
    include_workspace_osc: bool = False,
    primary_session_dir: Optional[Path] = None,
    tag: Optional[str] = None,
    operator_note: Optional[str] = None,
    trigger: Optional[str] = None,
) -> Path:
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    pneumo_dir = repo_root / "pneumo_solver_ui"

    stamp = _ts()
    tag_s = _sanitize_tag(tag)
    zip_path = out_dir / (f"SEND_{stamp}_{tag_s}_bundle.zip" if tag_s else f"SEND_{stamp}_bundle.zip")

    max_file_bytes = int(max_file_mb) * 1024 * 1024

    raw_trigger = str(trigger or tag_s or os.environ.get("PNEUMO_SEND_BUNDLE_TRIGGER") or "manual").strip() or "manual"

    meta: Dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "release": RELEASE,
        "repo_root": str(repo_root),
        "pneumo_dir": str(pneumo_dir),
        "trigger": raw_trigger,
        "collection_mode": classify_collection_mode(raw_trigger),
        "platform": platform.platform(),
        "python": sys.version,
        "python_executable": str(sys.executable),
        "python_prefix": str(getattr(sys, "prefix", "")),
        "python_base_prefix": str(getattr(sys, "base_prefix", getattr(sys, "prefix", ""))),
        "venv_active": bool(str(getattr(sys, "prefix", "")) != str(getattr(sys, "base_prefix", getattr(sys, "prefix", ""))) or os.environ.get("VIRTUAL_ENV")),
        "preferred_cli_python": _resolve_cli_python_executable(),
        "argv": sys.argv,
        "max_file_mb": int(max_file_mb),
        "keep_last_n": int(keep_last_n),
        "include_workspace_osc": bool(include_workspace_osc),
        "tag": tag_s or None,
        "operator_note_present": bool((operator_note or "").strip()),
        "env": {
            k: os.environ.get(k)
            for k in [
                "PNEUMO_LOG_DIR",
                "PNEUMO_WORKSPACE_DIR",
                "PNEUMO_RUN_ID",
                "PNEUMO_TRACE_ID",
                "PNEUMO_SESSION_DIR",
                "PNEUMO_SHARED_VENV_PYTHON",
                "PNEUMO_VENV_PYTHON",
            ]
            if os.environ.get(k)
        },
    }
    meta.update(_runtime_python_truth_override())

    # R49: Ensure the *current* UI session is included in the bundle.
    # If the caller did not pass primary_session_dir explicitly, we try env PNEUMO_SESSION_DIR.
    if primary_session_dir is None:
        env_sd = os.environ.get("PNEUMO_SESSION_DIR")
        if env_sd:
            primary_session_dir = Path(env_sd)

    if primary_session_dir is not None:
        try:
            primary_session_dir = Path(primary_session_dir).expanduser().resolve()
            meta["primary_session_dir"] = str(primary_session_dir)
        except Exception:
            meta["primary_session_dir"] = str(primary_session_dir)
    else:
        meta["primary_session_dir"] = None

    anim_diag_event: Dict[str, Any] = {}
    anim_diag_md: str = ""

    # ------------------------------------------------------------
    # R53: idempotency via session marker (avoid duplicate bundles).
    # If we already built a bundle for the current UI session, reuse it.
    # ------------------------------------------------------------
    try:
        if primary_session_dir is not None:
            marker_path = _session_marker_path(primary_session_dir)
            existing = _load_existing_from_marker(marker_path)
            if existing is not None and existing.exists():
                # Ensure latest pointers exist for convenience (best-effort).
                try:
                    latest_zip = out_dir / 'latest_send_bundle.zip'
                    latest_txt = out_dir / 'latest_send_bundle_path.txt'
                    try:
                        if existing.resolve() != latest_zip.resolve():
                            _atomic_copy_file(existing, latest_zip)
                    except Exception:
                        pass
                    _safe_write_text(latest_txt, str(existing.resolve()))
                except Exception:
                    pass
                return existing
    except Exception:
        pass

    manifest: Dict[str, Any] = {}
    skips: List[Dict[str, Any]] = []

    res_total = AddResult()
    engineering_analysis_evidence_added = False
    geometry_reference_evidence_added = False

    try:
        anim_diag_event, anim_diag_md = _collect_anim_latest_bundle_diagnostics(out_dir, repo_root=repo_root)
    except Exception:
        anim_diag_event = {"anim_latest_available": False, "error": traceback.format_exc()}
        anim_diag_md = "# Anim Latest Pointer Diagnostics\n\nerror collecting diagnostics\n"

    def _generate_triage_report_payload() -> Tuple[str, Dict[str, Any], Any]:
        from pneumo_solver_ui.tools.triage_report import generate_triage_report, write_triage_report

        triage_md, triage_json = generate_triage_report(
            repo_root,
            keep_last_n=int(keep_last_n),
            primary_session_dir=primary_session_dir,
        )
        return str(triage_md), dict(triage_json or {}), write_triage_report

    def _write_triage_report_entries(
        zip_handle: zipfile.ZipFile,
        *,
        md_arcname: str,
        json_arcname: str,
        triage_md: str,
        triage_json: Dict[str, Any],
    ) -> None:
        zip_handle.writestr(md_arcname, triage_md)
        zip_handle.writestr(json_arcname, json.dumps(triage_json, ensure_ascii=False, indent=2))

    def _persist_triage_sidecars(triage_md: str, triage_json: Dict[str, Any], triage_writer: Any) -> None:
        triage_writer(out_dir, triage_md, triage_json, stamp=stamp)

    def _run_triage_pass(
        *,
        md_arcname: str,
        json_arcname: str,
        rewrite_bundle_refs: bool,
        zip_handle: Optional[zipfile.ZipFile] = None,
        extra_sidecar_paths: Iterable[Path] = (),
    ) -> None:
        _triage_md, _triage_json, _triage_writer = _generate_triage_report_payload()
        if rewrite_bundle_refs:
            _triage_md = _rewrite_triage_bundle_refs(_triage_md)
        if zip_handle is None:
            with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as _zt:
                _write_triage_report_entries(
                    _zt,
                    md_arcname=md_arcname,
                    json_arcname=json_arcname,
                    triage_md=_triage_md,
                    triage_json=_triage_json,
                )
        else:
            _write_triage_report_entries(
                zip_handle,
                md_arcname=md_arcname,
                json_arcname=json_arcname,
                triage_md=_triage_md,
                triage_json=_triage_json,
            )
        for _p in extra_sidecar_paths:
            _embed_triage_sidecars((_p,))
        try:
            _persist_triage_sidecars(_triage_md, _triage_json, _triage_writer)
        except Exception:
            pass

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        readme = _build_send_bundle_readme(anim_diag_event)
        z.writestr("bundle/README_SEND_BUNDLE.txt", readme)

        # --- triage report (best-effort) ---
        try:
            _run_triage_pass(
                md_arcname="triage/triage_report_pre.md",
                json_arcname="triage/triage_report_pre.json",
                rewrite_bundle_refs=False,
                zip_handle=z,
            )
        except Exception:
            # do not fail bundle generation
            z.writestr("triage/triage_failed.txt", traceback.format_exc())

        # --- environment snapshot ---
        env_dir = "env"
        z.writestr(f"{env_dir}/python.txt", sys.version)
        z.writestr(f"{env_dir}/platform.txt", platform.platform())

        # pip freeze/check (best effort)
        python_exe = _resolve_cli_python_executable()
        rc, out, err = _run([python_exe, "-m", "pip", "freeze"], cwd=repo_root)
        z.writestr(f"{env_dir}/pip_freeze.txt", out + ("\n\nSTDERR:\n" + err if err else ""))
        rc2, out2, err2 = _run([python_exe, "-m", "pip", "check"], cwd=repo_root)
        z.writestr(f"{env_dir}/pip_check.txt", out2 + ("\n\nSTDERR:\n" + err2 if err2 else ""))

        # --- configs ---
        cfg = [
            "default_base.json",
            "default_suite.json",
            "default_ranges.json",
            "component_passport.json",
        ]
        for fn in cfg:
            p = pneumo_dir / fn
            rr = _add_file(
                z,
                p,
                f"config/{fn}",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes

        # --- UI logs ---
        rr = _add_tree(
            z,
            pneumo_dir / "logs",
            "ui_logs",
            manifest=manifest,
            skips=skips,
            max_file_bytes=max_file_bytes,
            ignore_names={"__pycache__"},
        )
        res_total.added_files += rr.added_files
        res_total.added_bytes += rr.added_bytes
        res_total.skipped_files += rr.skipped_files
        res_total.skipped_bytes += rr.skipped_bytes
        # --- root logs (console output, e.g. logs/streamlit.log) ---
        root_logs_dir = (repo_root / "logs")
        if root_logs_dir.exists() and root_logs_dir.is_dir():
            rr = _add_tree(
                z,
                root_logs_dir,
                "root_logs",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
                ignore_names={"__pycache__"},
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes

        # --- postmortem watchdog log (best-effort) ---
        try:
            wdlog = out_dir / "_postmortem_watchdog.log"
            rr = _add_file(
                z,
                wdlog,
                "reports/postmortem_watchdog.log",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes
        except Exception:
            pass

        # --- env override logs/workspace (if user routed them via env) ---
        p_env_log: Optional[Path] = None
        env_log_dir = os.environ.get("PNEUMO_LOG_DIR")
        if env_log_dir:
            p_env_log = Path(env_log_dir).expanduser().resolve()
            # avoid duplicating the default logs directory
            if p_env_log.exists() and p_env_log.is_dir() and p_env_log != (pneumo_dir / "logs").resolve():
                rr = _add_tree(
                    z,
                    p_env_log,
                    "env_override/PNEUMO_LOG_DIR",
                    manifest=manifest,
                    skips=skips,
                    max_file_bytes=max_file_bytes,
                    ignore_names={"__pycache__"},
                )
                res_total.added_files += rr.added_files
                res_total.added_bytes += rr.added_bytes
                res_total.skipped_files += rr.skipped_files
                res_total.skipped_bytes += rr.skipped_bytes


        # --- persistent_state (Streamlit UI autosave) ---
        # R59 contract: diagnostics bundle must include persistent_state/**.
        try:
            from pneumo_solver_ui.ui_persistence import pick_state_dir

            p_state = pick_state_dir(app_here=pneumo_dir)
        except Exception:
            p_state = None

        try:
            if p_state is not None:
                p_state = Path(p_state).expanduser().resolve()
        except Exception:
            pass

        if p_state is not None and Path(p_state).exists() and Path(p_state).is_dir():
            rr = _add_tree(
                z,
                Path(p_state),
                "persistent_state",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
                ignore_names={"__pycache__"},
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes


        # --- log quality reports (loglint/logstats) ---
        try:
            reports_tmp = out_dir / f"_tmp_reports_{stamp}"
            if reports_tmp.exists():
                shutil.rmtree(reports_tmp, ignore_errors=True)

            tool_loglint = pneumo_dir / "tools" / "loglint.py"
            tool_logstats = pneumo_dir / "tools" / "logstats.py"

            sources: List[Tuple[str, Path]] = [("ui_logs", (pneumo_dir / "logs").resolve())]

            root_logs = (repo_root / "logs").resolve()
            if root_logs.exists() and root_logs.is_dir():
                sources.append(("root_logs", root_logs))
            if (p_env_log is not None) and p_env_log.exists() and p_env_log.is_dir() and p_env_log != (pneumo_dir / "logs").resolve():
                sources.append(("env_override_PNEUMO_LOG_DIR", p_env_log))

            for name, src in sources:
                base = reports_tmp / name
                base.mkdir(parents=True, exist_ok=True)

                rc_l, out_l, err_l = _run(
                    [
                        python_exe,
                        str(tool_loglint),
                        "--path",
                        str(src),
                        "--recursive",
                        "--schema",
                        "ui",
                        "--strict",
                        "--out_dir",
                        str(base / "loglint_strict"),
                    ],
                    cwd=repo_root,
                    timeout_s=180.0,
                )
                _safe_write_text(base / "loglint_stdout.txt", out_l)
                _safe_write_text(base / "loglint_stderr.txt", err_l)
                _safe_write_text(base / "loglint_rc.txt", str(rc_l))

                rc_s, out_s, err_s = _run(
                    [
                        python_exe,
                        str(tool_logstats),
                        "--path",
                        str(src),
                        "--recursive",
                        "--out_dir",
                        str(base / "logstats"),
                    ],
                    cwd=repo_root,
                    timeout_s=180.0,
                )
                _safe_write_text(base / "logstats_stdout.txt", out_s)
                _safe_write_text(base / "logstats_stderr.txt", err_s)
                _safe_write_text(base / "logstats_rc.txt", str(rc_s))



            # --- sqlite metrics (log2sqlite) ---
            # Converts JSONL logs into a single SQLite DB for fast RCA queries.
            try:
                tool_sqlite = pneumo_dir / "tools" / "log2sqlite.py"
                sql_dir = reports_tmp / "sqlite_metrics"
                sql_dir.mkdir(parents=True, exist_ok=True)
                db_path = sql_dir / "metrics.sqlite"

                # Build one DB across sources (ui_logs/root_logs/env_override)
                for i, (name, src) in enumerate(sources):
                    args_sql = [
                        python_exe,
                        str(tool_sqlite),
                        "--input",
                        str(src),
                        "--recursive",
                        "--db",
                        str(db_path),
                        "--source",
                        str(name),
                        "--max_errors",
                        "50",
                        "--commit_every",
                        "3000",
                    ]
                    if i > 0:
                        args_sql.append("--append")
                    rc_q, out_q, err_q = _run(args_sql, cwd=repo_root, timeout_s=420.0)
                    _safe_write_text(sql_dir / f"log2sqlite_{name}_stdout.txt", out_q)
                    _safe_write_text(sql_dir / f"log2sqlite_{name}_stderr.txt", err_q)
                    _safe_write_text(sql_dir / f"log2sqlite_{name}_rc.txt", str(rc_q))

                # Final aggregated report
                rc_r, out_r, err_r = _run(
                    [
                        python_exe,
                        str(tool_sqlite),
                        "--db",
                        str(db_path),
                        "--report_only",
                        "--out_dir",
                        str(sql_dir),
                    ],
                    cwd=repo_root,
                    timeout_s=120.0,
                )
                _safe_write_text(sql_dir / "log2sqlite_report_stdout.txt", out_r)
                _safe_write_text(sql_dir / "log2sqlite_report_stderr.txt", err_r)
                _safe_write_text(sql_dir / "log2sqlite_report_rc.txt", str(rc_r))

                # Try to checkpoint/vacuum to avoid -wal/-shm and keep DB compact
                try:
                    import sqlite3

                    conn = sqlite3.connect(str(db_path))
                    try:
                        conn.execute("PRAGMA wal_checkpoint(FULL);")
                    except Exception:
                        pass
                    try:
                        conn.execute("PRAGMA journal_mode=DELETE;")
                    except Exception:
                        pass
                    try:
                        conn.execute("VACUUM;")
                    except Exception:
                        pass
                    conn.close()
                except Exception:
                    pass

                # Sidecar copies next to send_bundles for quick GUI linking
                try:
                    rep_md = sql_dir / "sqlite_report.md"
                    rep_json = sql_dir / "sqlite_report.json"
                    if rep_md.exists():
                        shutil.copy2(rep_md, out_dir / "latest_sqlite_report.md")
                    if rep_json.exists():
                        shutil.copy2(rep_json, out_dir / "latest_sqlite_report.json")
                except Exception:
                    pass

            except Exception:
                _safe_write_text(reports_tmp / "sqlite_metrics_failed.txt", traceback.format_exc())

            rr = _add_tree(
                z,
                reports_tmp,
                "reports",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
                ignore_names={"__pycache__"},
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes

        except Exception:
            z.writestr("reports/reports_generation_failed.txt", traceback.format_exc())
        finally:
            try:
                if "reports_tmp" in locals() and isinstance(reports_tmp, Path) and reports_tmp.exists():
                    shutil.rmtree(reports_tmp, ignore_errors=True)
            except Exception:
                pass

        # --- workspace (contract v1.1: MUST INCLUDE) ---
        # Required for reproducibility: exports/uploads/road_profiles/maneuvers/opt_runs.
        # If a required folder is missing or empty, we still include a placeholder marker
        # so the bundle is "truthful" (no silent omission) and validators can enforce the contract.
        workspace_required = [
            ("exports", True),
            ("uploads", True),
            ("road_profiles", True),
            ("maneuvers", True),
            ("opt_runs", True),
            ("ui_state", True),
            # optional but useful
            ("_pointers", False),
            ("baselines", False),
            ("handoffs", False),
            ("opt_archive", False),
        ]

        def _add_workspace_dir(base: Path, arc_base: str) -> None:
            nonlocal res_total
            for ws_name, ws_required in workspace_required:
                src_dir = base / ws_name
                arc = f"{arc_base}/{ws_name}".replace('\\\\', '/')

                rr = _add_tree(
                    z,
                    src_dir,
                    arc,
                    manifest=manifest,
                    skips=skips,
                    max_file_bytes=max_file_bytes,
                    ignore_names={"__pycache__"},
                )
                res_total.added_files += rr.added_files
                res_total.added_bytes += rr.added_bytes
                res_total.skipped_files += rr.skipped_files
                res_total.skipped_bytes += rr.skipped_bytes

                if ws_required and rr.added_files == 0:
                    # record the omission explicitly
                    skips.append(
                        {
                            "path": str(src_dir),
                            "arcname": arc,
                            "reason": "missing_or_empty_required_dir",
                        }
                    )
                    _add_generated_text(
                        z,
                        f"{arc}/_EMPTY_OR_MISSING.txt",
                        (
                            "REQUIRED_WORKSPACE_DIR_IS_EMPTY_OR_MISSING\n"
                            f"expected_dir: {src_dir}\n"
                            "This folder is required by the diagnostics bundle contract.\n"
                            "If you expect files here, re-run the operation and collect diagnostics again.\n"
                        ),
                        manifest=manifest,
                    )

        # Effective workspace for bundle reproducibility.
        # When runtime uses PNEUMO_WORKSPACE_DIR, the root `workspace/` inside the
        # bundle must reflect that effective workspace, not the empty repo-local
        # fallback directory. Otherwise validation sees empty markers while the real
        # exports/ui_state/_pointers live only under env_override/... .
        default_ws = (pneumo_dir / "workspace").resolve()
        effective_ws = default_ws
        effective_ws_source = "repo_local"
        env_ws_dir = os.environ.get("PNEUMO_WORKSPACE_DIR")
        p_env_ws = None
        if env_ws_dir:
            try:
                p_env_ws = Path(env_ws_dir).expanduser().resolve()
            except Exception:
                p_env_ws = Path(env_ws_dir)
            if p_env_ws.exists() and p_env_ws.is_dir() and p_env_ws != default_ws:
                effective_ws = p_env_ws
                effective_ws_source = "env_override"

        meta["effective_workspace_source"] = effective_ws_source
        meta["effective_workspace_path"] = str(effective_ws)
        meta["effective_workspace"] = str(effective_ws)
        if p_env_ws is not None and str(p_env_ws) != str(effective_ws):
            meta["env_workspace_path"] = str(p_env_ws)
        meta["repo_local_workspace_path"] = str(default_ws)
        meta["helper_runtime_provenance"] = helper_runtime_provenance(meta)

        # Canonical bundle workspace must always mirror the effective runtime workspace.
        _add_workspace_dir(effective_ws, "workspace")

        def _add_engineering_analysis_evidence_sidecar() -> None:
            nonlocal engineering_analysis_evidence_added, res_total
            candidates = (
                out_dir / ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME,
                effective_ws / "exports" / Path(ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME).name,
                default_ws / "exports" / Path(ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME).name,
            )
            seen: set[str] = set()
            for src in candidates:
                try:
                    key = str(Path(src).expanduser().resolve())
                except Exception:
                    key = str(src)
                if key in seen:
                    continue
                seen.add(key)
                if not Path(src).exists() or not Path(src).is_file():
                    continue
                rr = _add_file(
                    z,
                    Path(src),
                    ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME,
                    manifest=manifest,
                    skips=skips,
                    max_file_bytes=max_file_bytes,
                )
                res_total.added_files += rr.added_files
                res_total.added_bytes += rr.added_bytes
                res_total.skipped_files += rr.skipped_files
                res_total.skipped_bytes += rr.skipped_bytes
                engineering_analysis_evidence_added = rr.added_files > 0
                return

        def _add_geometry_reference_evidence_sidecar() -> None:
            nonlocal geometry_reference_evidence_added, res_total
            sidecar_path = out_dir / GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME
            candidates = (
                sidecar_path,
                effective_ws / "exports" / Path(GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME).name,
                default_ws / "exports" / Path(GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME).name,
            )
            seen: set[str] = set()
            for src in candidates:
                try:
                    key = str(Path(src).expanduser().resolve())
                except Exception:
                    key = str(src)
                if key in seen:
                    continue
                seen.add(key)
                if not Path(src).exists() or not Path(src).is_file():
                    continue
                rr = _add_file(
                    z,
                    Path(src),
                    GEOMETRY_REFERENCE_EVIDENCE_ARCNAME,
                    manifest=manifest,
                    skips=skips,
                    max_file_bytes=max_file_bytes,
                )
                res_total.added_files += rr.added_files
                res_total.added_bytes += rr.added_bytes
                res_total.skipped_files += rr.skipped_files
                res_total.skipped_bytes += rr.skipped_bytes
                geometry_reference_evidence_added = rr.added_files > 0
                if geometry_reference_evidence_added and Path(src) != sidecar_path:
                    try:
                        _safe_write_text(sidecar_path, Path(src).read_text(encoding="utf-8", errors="replace"))
                    except Exception:
                        pass
                return

            try:
                from pneumo_solver_ui.desktop_geometry_reference_runtime import DesktopGeometryReferenceRuntime

                payload = DesktopGeometryReferenceRuntime().diagnostics_handoff_evidence()
            except Exception as exc:
                payload = {
                    "schema": "geometry_reference_evidence.v1",
                    "producer_owned": False,
                    "reference_center_role": "reader_and_evidence_surface",
                    "does_not_render_animator_meshes": True,
                    "artifact_status": "missing",
                    "road_width_status": "missing",
                    "packaging_mismatch_status": "missing",
                    "geometry_acceptance_gate": "MISSING",
                    "component_passport_components": 0,
                    "component_passport_needs_data": 0,
                    "evidence_missing": ["geometry_reference_runtime"],
                    "adapter_error": f"{type(exc).__name__}: {exc!s}",
                }
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            try:
                _safe_write_text(sidecar_path, text)
            except Exception:
                pass
            rr = _add_generated_text(
                z,
                GEOMETRY_REFERENCE_EVIDENCE_ARCNAME,
                text,
                manifest=manifest,
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            geometry_reference_evidence_added = rr.added_files > 0

        _add_engineering_analysis_evidence_sidecar()
        _add_geometry_reference_evidence_sidecar()

        # Preserve visibility of a distinct env override tree only when it is NOT the
        # effective workspace mirrored into `workspace/`.
        if p_env_ws is not None and p_env_ws.exists() and p_env_ws.is_dir() and p_env_ws != effective_ws:
            _add_workspace_dir(p_env_ws, "env_override/PNEUMO_WORKSPACE_DIR")

        # --- calibration runs (latest N) ---
        # Useful for debugging fitting/calibration; include only newest directories.
        try:
            calib_root = pneumo_dir / "calibration_runs"
            for d in _pick_latest_dirs(calib_root, "", keep_last_n):
                rr = _add_tree(
                    z,
                    d,
                    f"calibration/{d.name}",
                    manifest=manifest,
                    skips=skips,
                    max_file_bytes=max_file_bytes,
                    ignore_names={"__pycache__"},
                )
                res_total.added_files += rr.added_files
                res_total.added_bytes += rr.added_bytes
                res_total.skipped_files += rr.skipped_files
                res_total.skipped_bytes += rr.skipped_bytes

            # also check workspace override if provided
            env_ws_dir = os.environ.get("PNEUMO_WORKSPACE_DIR")
            if env_ws_dir:
                p_env_ws = Path(env_ws_dir).expanduser().resolve()
                calib2 = p_env_ws / "calibration_runs"
                if calib2.exists() and calib2.is_dir():
                    for d in _pick_latest_dirs(calib2, "", keep_last_n):
                        rr = _add_tree(
                            z,
                            d,
                            f"env_override/PNEUMO_WORKSPACE_DIR/calibration_runs/{d.name}",
                            manifest=manifest,
                            skips=skips,
                            max_file_bytes=max_file_bytes,
                            ignore_names={"__pycache__"},
                        )
                        res_total.added_files += rr.added_files
                        res_total.added_bytes += rr.added_bytes
                        res_total.skipped_files += rr.skipped_files
                        res_total.skipped_bytes += rr.skipped_bytes
        except Exception:
            pass

        # --- optional: workspace osc (can be huge) ---

        if include_workspace_osc:
            rr = _add_tree(
                z,
                pneumo_dir / "workspace" / "osc",
                "workspace/osc",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
                ignore_names={"__pycache__"},
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes

        # --- latest autotest runs ---
        at_root = pneumo_dir / "autotest_runs"
        for d in _pick_latest_dirs(at_root, "RUN_", keep_last_n):
            rr = _add_tree(
                z,
                d,
                f"autotest/{d.name}",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
                ignore_names={"__pycache__"},
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes

        # include matching zip files (faster to review)
        for zp in _pick_latest_zips(at_root, "RUN_", keep_last_n):
            rr = _add_file(
                z,
                zp,
                f"autotest/{zp.name}",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes

        # --- latest diagnostics runs (repo_root/diagnostics_runs) ---
        diag_root = repo_root / "diagnostics_runs"
        for d in _pick_latest_dirs(diag_root, "RUN_", keep_last_n):
            rr = _add_tree(
                z,
                d,
                f"diagnostics_runs/{d.name}",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
                ignore_names={"__pycache__"},
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes

        for zp in _pick_latest_zips(diag_root, "RUN_", keep_last_n):
            rr = _add_file(
                z,
                zp,
                f"diagnostics_runs/{zp.name}",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes


        # --- latest distributed optimization runs (repo_root/runs/dist_runs) ---
        dist_root = repo_root / "runs" / "dist_runs"
        for d in _pick_latest_dirs(dist_root, "DIST_", keep_last_n):
            rr = _add_tree(
                z,
                d,
                f"dist_runs/{d.name}",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
                ignore_names={"__pycache__"},
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes


        # --- latest UI sessions (repo_root/runs/ui_sessions) ---
        ui_root = repo_root / "runs" / "ui_sessions"

        # Start with the explicit session (if provided), then add last N sessions by mtime.
        ui_dirs: List[Path] = []
        try:
            if primary_session_dir is not None and Path(primary_session_dir).exists():
                ui_dirs.append(Path(primary_session_dir))
        except Exception:
            pass
        ui_dirs += _pick_latest_dirs(ui_root, "UI_", keep_last_n)

        # Deduplicate (same folder may appear twice).
        _seen: set[str] = set()
        uniq_dirs: List[Path] = []
        for _d in ui_dirs:
            try:
                key = str(_d.resolve())
            except Exception:
                key = str(_d)
            if key in _seen:
                continue
            _seen.add(key)
            if _d.exists() and _d.is_dir():
                uniq_dirs.append(_d)

        for d in uniq_dirs:
            rr = _add_tree(
                z,
                d,
                f"ui_sessions/{d.name}",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
                # don't bloat bundle with large osc captures unless explicitly requested
                ignore_names={"__pycache__", "osc"} if not include_workspace_osc else {"__pycache__"},
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes

        # include optional run registry/index if present
        runs_root = repo_root / "runs"
        for fn in ["run_registry.jsonl", "index.json", "README_RUNS.txt"]:
            p = runs_root / fn
            rr = _add_file(
                z,
                p,
                f"runs/{fn}",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes

        # --- anim_latest pointer diagnostics (global pointer / reload token) ---
        try:
            rr = _add_generated_text(
                z,
                ANIM_DIAG_MD,
                anim_diag_md,
                manifest=manifest,
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes

            rr = _add_generated_text(
                z,
                ANIM_DIAG_JSON,
                json.dumps(anim_diag_event, ensure_ascii=False, indent=2),
                manifest=manifest,
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes
        except Exception:
            z.writestr(f"{Path(ANIM_DIAG_JSON).parent.as_posix()}/latest_anim_pointer_diagnostics_failed.txt", traceback.format_exc())

        # --- self_check silent warnings snapshot (if present) ---
        reports_root = repo_root / "REPORTS"
        for fn in ["SELF_CHECK_SILENT_WARNINGS.json", "SELF_CHECK_SILENT_WARNINGS.md"]:
            p = reports_root / fn
            rr = _add_file(
                z,
                p,
                f"reports/{fn}",
                manifest=manifest,
                skips=skips,
                max_file_bytes=max_file_bytes,
            )
            res_total.added_files += rr.added_files
            res_total.added_bytes += rr.added_bytes
            res_total.skipped_files += rr.skipped_files
            res_total.skipped_bytes += rr.skipped_bytes

        # --- operator note (from UI) ---
        # Stored as a simple text file inside the bundle for support/triage.
        try:
            _note = (operator_note or "").strip()
            if _note:
                z.writestr("bundle/operator_note.txt", _note + "\n")
        except Exception:
            pass

        # --- final manifests ---
        z.writestr("bundle/meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

        # R59 contract: MANIFEST.json must exist (keep also legacy bundle/manifest.json).
        _mjson = json.dumps(manifest, ensure_ascii=False, indent=2)
        z.writestr("bundle/manifest.json", _mjson)
        # Keep only one root-level manifest name on Windows to avoid
        # case-insensitive extraction conflicts between MANIFEST.json
        # and manifest.json.
        z.writestr("MANIFEST.json", _mjson)
        z.writestr("bundle/skips.json", json.dumps(skips, ensure_ascii=False, indent=2))

        summary = {
            "added_files": res_total.added_files,
            "added_bytes": res_total.added_bytes,
            "skipped_files": res_total.skipped_files,
            "skipped_bytes": res_total.skipped_bytes,
        }
        z.writestr("bundle/summary.json", json.dumps(summary, ensure_ascii=False, indent=2))

    # ------------------------------------------------------------
    # R52: Validate the created bundle (quality gate) and embed the
    # validation report back into the ZIP + sidecar files.
    # ------------------------------------------------------------
    validation_ok: Optional[bool] = None
    validation_errors: int = 0
    validation_warnings: int = 0
    validation_release_risks: int = 0
    optimizer_scope_gate: Dict[str, Any] = {}
    optimizer_scope_summary: Dict[str, Any] = {}
    optimizer_scope_release_gate: str = ""
    optimizer_scope_release_risk: Optional[bool] = None
    optimizer_scope_release_gate_reason: str = ""
    optimizer_scope_problem_hash: str = ""
    optimizer_scope_problem_hash_short: str = ""
    optimizer_scope_problem_hash_mode: str = ""
    optimizer_scope_sync_ok: Any = None
    optimizer_scope_canonical_source: str = ""
    optimizer_scope_mismatch_fields: List[str] = []
    latest_validation_md = out_dir / "latest_send_bundle_validation.md"
    latest_validation_json = out_dir / "latest_send_bundle_validation.json"
    def _reset_validation_projection() -> None:
        nonlocal validation_errors, validation_warnings, validation_release_risks
        nonlocal optimizer_scope_gate, optimizer_scope_summary
        nonlocal optimizer_scope_release_gate, optimizer_scope_release_risk
        nonlocal optimizer_scope_release_gate_reason
        nonlocal optimizer_scope_problem_hash, optimizer_scope_problem_hash_short
        nonlocal optimizer_scope_problem_hash_mode, optimizer_scope_sync_ok
        nonlocal optimizer_scope_canonical_source, optimizer_scope_mismatch_fields

        validation_errors = 0
        validation_warnings = 0
        validation_release_risks = 0
        optimizer_scope_gate = {}
        optimizer_scope_summary = {}
        optimizer_scope_release_gate = ""
        optimizer_scope_release_risk = None
        optimizer_scope_release_gate_reason = ""
        optimizer_scope_problem_hash = ""
        optimizer_scope_problem_hash_short = ""
        optimizer_scope_problem_hash_mode = ""
        optimizer_scope_sync_ok = None
        optimizer_scope_canonical_source = ""
        optimizer_scope_mismatch_fields = []

    def _project_validation_report(report_json: Dict[str, Any]) -> None:
        nonlocal validation_errors, validation_warnings, validation_release_risks
        nonlocal optimizer_scope_gate, optimizer_scope_summary
        nonlocal optimizer_scope_release_gate, optimizer_scope_release_risk
        nonlocal optimizer_scope_release_gate_reason
        nonlocal optimizer_scope_problem_hash, optimizer_scope_problem_hash_short
        nonlocal optimizer_scope_problem_hash_mode, optimizer_scope_sync_ok
        nonlocal optimizer_scope_canonical_source, optimizer_scope_mismatch_fields

        validation_errors = int(len(report_json.get("errors") or []))
        validation_warnings = int(len(report_json.get("warnings") or []))
        validation_release_risks = int(len(report_json.get("release_risks") or []))
        optimizer_scope_gate = dict(report_json.get("optimizer_scope_gate") or {})
        optimizer_scope_raw = dict(report_json.get("optimizer_scope") or {})
        optimizer_scope_summary = {}
        optimizer_scope_release_gate = str(optimizer_scope_gate.get("release_gate") or "").strip().upper()
        optimizer_scope_release_risk = (
            bool(optimizer_scope_gate.get("release_risk")) if "release_risk" in optimizer_scope_gate else None
        )
        optimizer_scope_release_gate_reason = str(optimizer_scope_gate.get("release_gate_reason") or "").strip()
        optimizer_scope_problem_hash = str(optimizer_scope_raw.get("problem_hash") or "").strip()
        optimizer_scope_problem_hash_short = str(optimizer_scope_raw.get("problem_hash_short") or "").strip()
        optimizer_scope_problem_hash_mode = str(optimizer_scope_raw.get("problem_hash_mode") or "").strip()
        optimizer_scope_sync_ok = optimizer_scope_raw.get("scope_sync_ok")
        optimizer_scope_canonical_source = str(
            optimizer_scope_raw.get("canonical_source") or optimizer_scope_gate.get("canonical_source") or ""
        ).strip()
        optimizer_scope_mismatch_fields = [
            str(x).strip() for x in (optimizer_scope_gate.get("mismatch_fields") or []) if str(x).strip()
        ]
        for key in (
            "problem_hash",
            "problem_hash_short",
            "problem_hash_mode",
            "scope_sync_ok",
            "canonical_source",
            "source_count",
            "penalty_key",
            "penalty_tol",
        ):
            value = optimizer_scope_raw.get(key)
            if value not in (None, "", [], {}):
                optimizer_scope_summary[key] = value
        objective_keys = [str(x).strip() for x in (optimizer_scope_raw.get("objective_keys") or []) if str(x).strip()]
        if objective_keys:
            optimizer_scope_summary["objective_keys"] = objective_keys
        if optimizer_scope_mismatch_fields:
            optimizer_scope_summary["mismatch_fields"] = list(optimizer_scope_mismatch_fields)

    def _write_validation_sidecars(report_md: str, report_json: Dict[str, Any]) -> None:
        _safe_write_text(latest_validation_md, report_md)
        _safe_write_text(
            latest_validation_json,
            json.dumps(report_json, ensure_ascii=False, indent=2),
        )

    def _embed_triage_sidecars(paths: Iterable[Path]) -> None:
        entries: Dict[str, bytes] = {}
        for _p in paths:
            if _p.exists():
                entries[f"triage/{_p.name}"] = _p.read_bytes()
        if entries:
            _replace_zip_entries(entries)

    def _replace_zip_entries(entries: Mapping[str, str | bytes]) -> None:
        if not entries:
            return
        tmp_zip = zip_path.with_name(zip_path.name + ".rewrite.tmp")
        normalized: Dict[str, bytes] = {}
        for arcname, payload in entries.items():
            arc = str(arcname).replace("\\", "/")
            if isinstance(payload, bytes):
                normalized[arc] = payload
            else:
                normalized[arc] = str(payload).encode("utf-8", errors="replace")

        try:
            if tmp_zip.exists():
                tmp_zip.unlink()
        except Exception:
            pass

        seen_arcnames: set[str] = set()
        with zipfile.ZipFile(zip_path, "r") as _zin, zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as _zout:
            for _info in _zin.infolist():
                if _info.filename in normalized or _info.filename in seen_arcnames:
                    continue
                seen_arcnames.add(_info.filename)
                with _zin.open(_info, "r") as _src_fh:
                    _zout.writestr(_info, _src_fh.read())
            for _arcname, _payload in normalized.items():
                seen_arcnames.add(_arcname)
                _zout.writestr(_arcname, _payload)
        os.replace(str(tmp_zip), str(zip_path))

    def _embed_validation_report(report_md: str, report_json: Dict[str, Any]) -> None:
        _replace_zip_entries(
            {
                "validation/validation_report.md": report_md,
                "validation/validation_report.json": json.dumps(report_json, ensure_ascii=False, indent=2),
            }
        )

    def _embed_validation_sidecars_into_triage() -> None:
        _embed_triage_sidecars((latest_validation_md, latest_validation_json))

    def _run_validation_pass(*, embed_report: bool, embed_triage_sidecars: bool, failure_name: str) -> None:
        nonlocal validation_ok

        try:
            from pneumo_solver_ui.tools.validate_send_bundle import validate_send_bundle as _validate_send_bundle

            _vres = _validate_send_bundle(zip_path)
            validation_ok = bool(_vres.ok)
            try:
                _project_validation_report(dict(_vres.report_json or {}))
            except Exception:
                _reset_validation_projection()
            try:
                _write_validation_sidecars(_vres.report_md, dict(_vres.report_json or {}))
            except Exception:
                pass
            if embed_report:
                _embed_validation_report(_vres.report_md, dict(_vres.report_json or {}))
            if embed_triage_sidecars:
                try:
                    _embed_validation_sidecars_into_triage()
                except Exception:
                    pass
        except Exception:
            try:
                with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as z2:
                    z2.writestr(failure_name, traceback.format_exc())
            except Exception:
                pass

    _run_validation_pass(
        embed_report=False,
        embed_triage_sidecars=False,
        failure_name="validation/validation_failed.txt",
    )



    # ------------------------------------------------------------
    # R52: Unified HTML dashboard (triage + validation + sqlite metrics)
    # ------------------------------------------------------------
    dashboard_created: bool = False
    dashboard_html_cache: str = ""
    dashboard_json_cache: Dict[str, Any] = {}
    dashboard_error_trace: Optional[str] = None
    def _refresh_dashboard(*, embed_in_zip: bool) -> None:
        nonlocal dashboard_created, dashboard_html_cache, dashboard_json_cache, dashboard_error_trace

        _dashboard_refresh_error: Optional[str] = None
        _write_dashboard_sidecars = None
        try:
            from pneumo_solver_ui.tools.dashboard_report import generate_dashboard_report, write_dashboard_sidecars

            _write_dashboard_sidecars = write_dashboard_sidecars
            dash_html, dash_json = generate_dashboard_report(
                repo_root,
                out_dir,
                zip_path=zip_path,
                keep_last_n=int(keep_last_n),
            )
            dashboard_html_cache = str(dash_html)
            dashboard_json_cache = dict(dash_json or {})
            dashboard_created = True
            dashboard_error_trace = None
        except Exception:
            _dashboard_refresh_error = traceback.format_exc()
            if not dashboard_created or not dashboard_html_cache:
                dashboard_created = False
                dashboard_error_trace = _dashboard_refresh_error

        try:
            if dashboard_created and dashboard_html_cache:
                if embed_in_zip:
                    _replace_zip_entries(
                        {
                            "dashboard/index.html": dashboard_html_cache,
                            "dashboard/dashboard.json": json.dumps(
                                dashboard_json_cache,
                                ensure_ascii=False,
                                indent=2,
                            ),
                        }
                    )
                if _write_dashboard_sidecars is not None:
                    _write_dashboard_sidecars(out_dir, dashboard_html_cache, dashboard_json_cache, stamp=stamp)
            elif embed_in_zip and (_dashboard_refresh_error or dashboard_error_trace):
                with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as _zd:
                    _zd.writestr("dashboard/dashboard_failed.txt", _dashboard_refresh_error or dashboard_error_trace or "")
        except Exception:
            pass

    _refresh_dashboard(embed_in_zip=False)

    # pointer to latest
    latest_zip = out_dir / "latest_send_bundle.zip"
    latest_txt = out_dir / "latest_send_bundle_path.txt"
    latest_sha = out_dir / "latest_send_bundle.sha256"

    def _build_bundle_index_record() -> Dict[str, Any]:
        rec: Dict[str, Any] = {
            'created_at': meta.get('created_at'),
            'release': meta.get('release'),
            'trigger': meta.get('trigger'),
            'collection_mode': meta.get('collection_mode'),
            'zip_name': zip_path.name,
            'zip_path': str(zip_path.resolve()),
            'latest_zip_path': str(latest_zip.resolve()),
            'size_bytes': int(zip_path.stat().st_size) if zip_path.exists() else None,
            'sha256': _sha256_file(zip_path) if zip_path.exists() else None,
            'summary': {
                'added_files': res_total.added_files,
                'added_bytes': res_total.added_bytes,
                'skipped_files': res_total.skipped_files,
                'skipped_bytes': res_total.skipped_bytes,
            },
            'validation': {
                'ok': validation_ok,
                'errors': validation_errors,
                'warnings': validation_warnings,
                'release_risks': validation_release_risks,
            },
            'validation_release_risks': validation_release_risks,
        }
        if optimizer_scope_gate:
            rec['optimizer_scope_gate'] = dict(optimizer_scope_gate)
        if optimizer_scope_summary:
            rec['optimizer_scope'] = dict(optimizer_scope_summary)
        if optimizer_scope_release_gate:
            rec['optimizer_scope_release_gate'] = optimizer_scope_release_gate
        if optimizer_scope_release_risk is not None:
            rec['optimizer_scope_release_risk'] = optimizer_scope_release_risk
        if optimizer_scope_release_gate_reason:
            rec['optimizer_scope_release_gate_reason'] = optimizer_scope_release_gate_reason
        if optimizer_scope_problem_hash:
            rec['optimizer_scope_problem_hash'] = optimizer_scope_problem_hash
        if optimizer_scope_problem_hash_short:
            rec['optimizer_scope_problem_hash_short'] = optimizer_scope_problem_hash_short
        if optimizer_scope_problem_hash_mode:
            rec['optimizer_scope_problem_hash_mode'] = optimizer_scope_problem_hash_mode
        if optimizer_scope_sync_ok is not None:
            rec['optimizer_scope_sync_ok'] = optimizer_scope_sync_ok
        if optimizer_scope_canonical_source:
            rec['optimizer_scope_canonical_source'] = optimizer_scope_canonical_source
        if optimizer_scope_mismatch_fields:
            rec['optimizer_scope_mismatch_fields'] = list(optimizer_scope_mismatch_fields)
        return rec

    def _update_bundle_index() -> None:
        idx_path = out_dir / 'index.json'
        if idx_path.exists():
            try:
                idx = json.loads(idx_path.read_text(encoding='utf-8', errors='replace'))
            except Exception:
                idx = {}
        else:
            idx = {}

        bundles = idx.get('bundles')
        if not isinstance(bundles, list):
            bundles = []

        rec = _build_bundle_index_record()
        bundles = [b for b in bundles if not (isinstance(b, dict) and b.get('zip_name') == rec['zip_name'])]
        bundles.insert(0, rec)
        bundles = bundles[:50]

        idx['bundles'] = bundles
        idx['latest'] = {'zip_name': zip_path.name, 'latest_zip_path': str(latest_zip.resolve())}

        tmp = idx_path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding='utf-8', errors='replace')
        tmp.replace(idx_path)

    def _refresh_latest_bundle(
        *,
        write_path: bool,
        write_sha: bool,
        update_index: bool,
        path_on_copy_failure: bool = False,
    ) -> bool:
        if not zip_path.exists():
            if write_path and path_on_copy_failure:
                try:
                    _safe_write_text(latest_txt, str(zip_path.resolve()))
                except Exception:
                    pass
            return False

        _copied = False
        try:
            _atomic_copy_file(zip_path, latest_zip)
            _copied = True
        except Exception:
            _copied = False

        if write_path and (_copied or path_on_copy_failure):
            try:
                _safe_write_text(latest_txt, str(zip_path.resolve()))
            except Exception:
                pass

        if not _copied:
            return False

        if write_sha:
            try:
                sha = _sha256_file(latest_zip)
                _safe_write_text(latest_sha, sha + '  latest_send_bundle.zip\n')
            except Exception:
                pass

        if update_index:
            try:
                _update_bundle_index()
            except Exception:
                pass

        return True

    def _rewrite_triage_bundle_refs(triage_md: str) -> str:
        triage_md = re.sub(
            r"(?m)^- Latest send bundle path:.*$",
            f"- Latest send bundle path: triage/{latest_txt.name} (inside this bundle)",
            triage_md,
        )
        triage_md = re.sub(
            r"(?m)^- Latest send bundle validation:.*$",
            f"- Latest send bundle validation: triage/{latest_validation_md.name} (inside this bundle)",
            triage_md,
        )
        triage_md = re.sub(
            r"(?m)^- Latest anim diagnostics json:.*$",
            f"- Latest anim diagnostics json: {ANIM_DIAG_JSON} (inside this bundle)",
            triage_md,
        )
        triage_md = re.sub(
            r"(?m)^- Latest anim diagnostics md:.*$",
            f"- Latest anim diagnostics md: {ANIM_DIAG_MD} (inside this bundle)",
            triage_md,
        )
        return triage_md

    def _run_final_triage_pass() -> None:
        try:
            _run_triage_pass(
                md_arcname="triage/triage_report.md",
                json_arcname="triage/triage_report.json",
                rewrite_bundle_refs=True,
                extra_sidecar_paths=(latest_txt,),
            )
        except Exception:
            pass

    latest_evidence_json = out_dir / EVIDENCE_MANIFEST_SIDECAR_NAME

    def _append_evidence_manifest(*, stage: str, planned_paths: Iterable[str] = ()) -> None:
        try:
            with zipfile.ZipFile(zip_path, "r") as _zr:
                _names = list(_zr.namelist())
                _meta_from_zip, _json_by_name = read_manifest_inputs_from_zip(_zr)
            _manifest_meta = dict(meta)
            for _k, _v in dict(_meta_from_zip or {}).items():
                if _manifest_meta.get(_k) in (None, "", [], {}):
                    _manifest_meta[_k] = _v
            _payload = build_evidence_manifest(
                zip_path=zip_path,
                names=_names,
                meta=_manifest_meta,
                json_by_name=_json_by_name,
                planned_paths=planned_paths,
                stage=stage,
                finalization_stage=stage,
            )
            _text = json.dumps(_payload, ensure_ascii=False, indent=2)
            _safe_write_text(latest_evidence_json, _text)
            _replace_zip_entries({EVIDENCE_MANIFEST_ARCNAME: _text})
        except Exception:
            try:
                with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as _ze:
                    _ze.writestr("diagnostics/evidence_manifest_failed.txt", traceback.format_exc())
            except Exception:
                pass

    def _write_final_evidence_sidecar_proof() -> None:
        try:
            payload = json.loads(latest_evidence_json.read_text(encoding="utf-8", errors="replace"))
            if not isinstance(payload, dict):
                return
        except Exception:
            return
        try:
            latest_sha_text = latest_sha.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            latest_sha_text = ""
        latest_sha_value = latest_sha_text.split()[0] if latest_sha_text else ""
        try:
            payload["final_latest_zip_sha256"] = _sha256_file(latest_zip) if latest_zip.exists() else ""
            payload["final_original_zip_sha256"] = _sha256_file(zip_path) if zip_path.exists() else ""
            payload["final_latest_sha256_sidecar"] = latest_sha_value
            payload["latest_zip_matches_original"] = bool(
                payload.get("final_latest_zip_sha256")
                and payload.get("final_latest_zip_sha256") == payload.get("final_original_zip_sha256")
            )
            payload["latest_sha_sidecar_matches"] = bool(
                latest_sha_value and latest_sha_value == payload.get("final_latest_zip_sha256")
            )
            payload["latest_pointer_path"] = str(latest_txt.resolve())
            payload["latest_pointer_target"] = latest_txt.read_text(encoding="utf-8", errors="replace").strip() if latest_txt.exists() else ""
            payload["latest_pointer_matches_original"] = bool(
                payload.get("latest_pointer_target") == str(zip_path.resolve())
            )
            payload["finalized_at"] = datetime.now().isoformat(timespec="seconds")
            payload["finalization_stage"] = "latest_zip_sha_inspection_proof"
            payload["zip_sha256"] = payload.get("final_latest_zip_sha256") or payload.get("zip_sha256") or ""
            payload["zip_sha256_scope"] = "latest_send_bundle.zip final bytes"
            _safe_write_text(latest_evidence_json, json.dumps(payload, ensure_ascii=False, indent=2))
        except Exception:
            pass

    def _write_latest_inspection_sidecars() -> None:
        try:
            from pneumo_solver_ui.tools.inspect_send_bundle import inspect_send_bundle, render_inspection_md

            inspected_zip = latest_zip if latest_zip.exists() else zip_path
            inspection = inspect_send_bundle(inspected_zip)
            _safe_write_text(
                out_dir / "latest_send_bundle_inspection.json",
                json.dumps(inspection, ensure_ascii=False, indent=2),
            )
            _safe_write_text(
                out_dir / "latest_send_bundle_inspection.md",
                render_inspection_md(inspection),
            )
        except Exception:
            try:
                _safe_write_text(
                    out_dir / "latest_send_bundle_inspection_failed.txt",
                    traceback.format_exc(),
                )
            except Exception:
                pass

    def _run_health_pass(*, failure_name: str = "health/health_report_failed.txt") -> None:
        try:
            from pneumo_solver_ui.tools.health_report import build_health_report

            _health_json, _health_md = build_health_report(zip_path, out_dir=out_dir)
            _entries: Dict[str, bytes] = {}
            if _health_json and Path(_health_json).exists():
                _entries["health/health_report.json"] = Path(_health_json).read_bytes()
            if _health_md and Path(_health_md).exists():
                _entries["health/health_report.md"] = Path(_health_md).read_bytes()
            if _entries:
                _replace_zip_entries(_entries)
        except Exception:
            _health_err = traceback.format_exc()
            try:
                _fallback_json, _fallback_md = _write_health_report_failure_stub(zip_path, out_dir, _health_err)
                _entries = {}
                if _fallback_json.exists():
                    _entries["health/health_report.json"] = _fallback_json.read_bytes()
                if _fallback_md.exists():
                    _entries["health/health_report.md"] = _fallback_md.read_bytes()
                _entries[failure_name] = _health_err.encode("utf-8", errors="replace")
                _replace_zip_entries(_entries)
            except Exception:
                try:
                    _replace_zip_entries({failure_name: _health_err})
                except Exception:
                    pass

    def _planned_evidence_paths(*paths: str) -> tuple[str, ...]:
        planned = [str(path) for path in paths if str(path or "").strip()]
        if engineering_analysis_evidence_added:
            planned.append(ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME)
        if geometry_reference_evidence_added:
            planned.append(GEOMETRY_REFERENCE_EVIDENCE_ARCNAME)
        return tuple(dict.fromkeys(planned))

    _refresh_latest_bundle(
        write_path=True,
        write_sha=True,
        update_index=True,
        path_on_copy_failure=True,
    )





    # R68 retired in R32.
    # Final in-archive triage rewrite now happens *after* run-registry logging
    # (see the R32 block near the end of this function), so keeping the older
    # pre-registry rewrite would only create duplicate ZIP entries and stale
    # registry summaries.

    # R69: defer health report until after the final triage rewrite.
    # The final triage/registry pass appends triage files later in this function,
    # so building health here would inspect a stale ZIP and miss triage_report.*.

    # R69b: interim latest_send_bundle refresh before run-registry/final triage; final refresh happens after the final health rebuild.
    _refresh_latest_bundle(
        write_path=False,
        write_sha=True,
        update_index=False,
    )

    # R49: record bundle creation in run registry (best-effort).
    try:
        from pneumo_solver_ui.run_registry import env_context, log_send_bundle_created

        sha_created = _sha256_file(zip_path) if zip_path.exists() else None
        size_bytes = int(zip_path.stat().st_size) if zip_path.exists() else None

        log_send_bundle_created(
            zip_path=zip_path,
            latest_zip_path=latest_zip if latest_zip.exists() else None,
            sha256=sha_created,
            size_bytes=size_bytes,
            release=RELEASE,
            primary_session_dir=meta.get("primary_session_dir"),
            validation_ok=validation_ok,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            validation_release_risks=validation_release_risks,
            dashboard_created=dashboard_created,
            dashboard_html_path=str((out_dir / "latest_dashboard.html").resolve()) if (out_dir / "latest_dashboard.html").exists() else None,
            env=env_context(),
            optimizer_scope_release_gate=optimizer_scope_release_gate or None,
            optimizer_scope_release_risk=optimizer_scope_release_risk,
            optimizer_scope_release_gate_reason=optimizer_scope_release_gate_reason or None,
            optimizer_scope_problem_hash=optimizer_scope_problem_hash or None,
            optimizer_scope_problem_hash_short=optimizer_scope_problem_hash_short or None,
            optimizer_scope_problem_hash_mode=optimizer_scope_problem_hash_mode or None,
            optimizer_scope_sync_ok=optimizer_scope_sync_ok,
            optimizer_scope_canonical_source=optimizer_scope_canonical_source or None,
            optimizer_scope_mismatch_fields=optimizer_scope_mismatch_fields or None,
            **anim_diag_event,
        )
    except Exception:
        pass

    # R32: after run-registry write, regenerate triage once more so the bundle
    # and latest sidecars can see the *current* send_bundle_created event instead
    # of a stale older one from a previous workspace/release.
    _run_final_triage_pass()

    # Refresh validation after the final triage rewrite so bundle-level
    # contracts (including optimizer scope sync) reflect the finalized archive.
    _run_validation_pass(
        embed_report=True,
        embed_triage_sidecars=True,
        failure_name="validation/validation_failed_final.txt",
    )

    _append_evidence_manifest(
        stage="after_final_validation_before_health",
        planned_paths=_planned_evidence_paths(
            EVIDENCE_MANIFEST_ARCNAME,
            "health/health_report.json",
            "health/health_report.md",
        ),
    )

    # Re-run validation after evidence is embedded so both the latest sidecar
    # and in-bundle validation report see diagnostics/evidence_manifest.json.
    _run_validation_pass(
        embed_report=True,
        embed_triage_sidecars=True,
        failure_name="validation/validation_failed_after_evidence.txt",
    )

    # Refresh dashboard after final triage/validation so the embedded dashboard
    # and latest_dashboard sidecars reflect the finalized bundle state.
    _refresh_dashboard(embed_in_zip=True)

    # R69c: now that the run-registry event and final triage files are in place,
    # rebuild the health report against the final ZIP contents and refresh the
    # latest bundle copy/sha to match the post-triage archive.
    _run_health_pass()

    _append_evidence_manifest(
        stage="after_final_health_before_latest",
        planned_paths=_planned_evidence_paths(EVIDENCE_MANIFEST_ARCNAME),
    )

    # One final pass lets health/validation/dashboard report on the final
    # manifest without changing any domain calculations.
    _run_health_pass(failure_name="health/health_report_failed_after_evidence.txt")
    _run_validation_pass(
        embed_report=True,
        embed_triage_sidecars=True,
        failure_name="validation/validation_failed_release_ready.txt",
    )
    _refresh_dashboard(embed_in_zip=True)
    _append_evidence_manifest(
        stage="final_after_validation_dashboard",
        planned_paths=_planned_evidence_paths(EVIDENCE_MANIFEST_ARCNAME),
    )

    _refresh_latest_bundle(
        write_path=True,
        write_sha=True,
        update_index=True,
    )
    _write_final_evidence_sidecar_proof()
    _write_latest_inspection_sidecars()

    # ------------------------------------------------------------
    # R53: write session marker (for watchdog + idempotency).
    # ------------------------------------------------------------
    try:
        if primary_session_dir is not None:
            _write_session_marker(
                _session_marker_path(primary_session_dir),
                zip_path=zip_path,
                latest_zip_path=(latest_zip if latest_zip.exists() else None),
                meta=meta,
            )
    except Exception:
        pass

    return zip_path


def _repo_root_from_here_override() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalized_executable_path_override(raw: str | Path | None) -> str:
    try:
        return str(Path(raw or "").expanduser().resolve()).casefold()
    except Exception:
        return str(raw or "").casefold()


def _venv_truth_from_executable_override(executable: str | Path | None) -> Dict[str, Any]:
    exe_str = str(executable or "").strip()
    if not exe_str:
        return {
            "python_executable": "",
            "python_prefix": "",
            "python_base_prefix": "",
            "venv_active": False,
        }
    try:
        exe = Path(exe_str).expanduser().resolve()
    except Exception:
        exe = Path(exe_str)
    try:
        parent_name = exe.parent.name.lower()
    except Exception:
        parent_name = ""
    prefix_path = exe.parent.parent if parent_name in {"scripts", "bin"} else exe.parent
    prefix = str(prefix_path)
    base_prefix = prefix
    venv_active = False
    try:
        pyvenv_cfg = prefix_path / "pyvenv.cfg"
        if pyvenv_cfg.exists():
            venv_active = True
            for line in pyvenv_cfg.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if stripped.lower().startswith("home ="):
                    base_prefix = stripped.split("=", 1)[1].strip() or base_prefix
                    break
    except Exception:
        pass
    return {
        "python_executable": str(exe),
        "python_prefix": prefix,
        "python_base_prefix": base_prefix,
        "venv_active": bool(venv_active),
    }


def _runtime_python_truth_override() -> Dict[str, Any]:
    current_executable = str(sys.executable)
    current_prefix = str(getattr(sys, "prefix", ""))
    current_base_prefix = str(getattr(sys, "base_prefix", current_prefix))
    current_venv_active = bool(current_prefix != current_base_prefix or os.environ.get("VIRTUAL_ENV"))
    preferred_cli_python = _resolve_cli_python_executable()
    effective_executable = preferred_cli_python or current_executable
    effective_truth = _venv_truth_from_executable_override(effective_executable)
    return {
        "python_executable": str(effective_truth.get("python_executable") or current_executable),
        "python_prefix": str(effective_truth.get("python_prefix") or current_prefix),
        "python_base_prefix": str(effective_truth.get("python_base_prefix") or current_base_prefix),
        "venv_active": bool(effective_truth.get("venv_active") or current_venv_active),
        "preferred_cli_python": preferred_cli_python,
        "python_executable_current": current_executable,
        "python_prefix_current": current_prefix,
        "python_base_prefix_current": current_base_prefix,
        "venv_active_current": current_venv_active,
        "python_runtime_source": (
            "preferred_cli_python"
            if _normalized_executable_path_override(effective_executable)
            != _normalized_executable_path_override(current_executable)
            else "current_process"
        ),
    }


def _collect_anim_latest_diagnostics_via_cli_python_override(repo_root: Path, python_exe: str) -> Dict[str, Any]:
    code = (
        "import json\n"
        "from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary\n"
        "diag = dict(collect_anim_latest_diagnostics_summary(include_meta=True) or {})\n"
        "print(json.dumps(diag, ensure_ascii=False))\n"
    )
    rc, out, err = _run([str(python_exe), "-c", code], cwd=repo_root, timeout_s=90.0)
    if int(rc) != 0:
        raise RuntimeError((err or out or f"anim_latest diagnostics subprocess failed rc={rc}").strip())
    raw = str(out or "").strip()
    if not raw:
        raise RuntimeError("anim_latest diagnostics subprocess returned empty stdout")
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(
            f"anim_latest diagnostics subprocess returned invalid json: {exc!r}; raw={raw[:400]!r}"
        ) from exc
    return dict(parsed) if isinstance(parsed, dict) else {}


def _format_anim_diag_error(exc: BaseException) -> str:
    if isinstance(exc, ModuleNotFoundError):
        missing = str(getattr(exc, "name", "") or "").strip() or "unknown"
        return f"Отсутствует необязательная зависимость: {missing}"
    try:
        match = re.search(r"No module named ['\"]([^'\"]+)['\"]", str(exc))
        if match:
            return f"Отсутствует необязательная зависимость: {match.group(1)}"
    except Exception:
        pass
    return repr(exc)


def _collect_anim_latest_bundle_diagnostics(out_dir: Path, *, repo_root: Optional[Path] = None) -> Tuple[Dict[str, Any], str]:
    repo_root = (repo_root or _repo_root_from_here_override()).resolve()
    diag: Dict[str, Any]
    try:
        preferred_cli_python = str(_runtime_python_truth_override().get("preferred_cli_python") or "").strip()
        if preferred_cli_python and (
            _normalized_executable_path_override(preferred_cli_python)
            != _normalized_executable_path_override(sys.executable)
        ):
            diag = _collect_anim_latest_diagnostics_via_cli_python_override(repo_root, preferred_cli_python)
        else:
            from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary

            diag = dict(collect_anim_latest_diagnostics_summary(include_meta=True) or {})
    except Exception as exc:
        friendly_error = _format_anim_diag_error(exc)
        diag = {
            "anim_latest_available": False,
            "error": friendly_error,
            "anim_latest_issues": [
                f"Не удалось собрать anim_latest diagnostics: {friendly_error}.",
            ],
        }

    deps = dict(diag.get("anim_latest_visual_cache_dependencies") or {})
    meta = dict(diag.get("anim_latest_meta") or {})
    try:
        from pneumo_solver_ui.anim_export_contract import summarize_anim_export_contract, summarize_anim_export_validation

        contract_summary = dict(summarize_anim_export_contract(meta) or {})
        validation_summary = dict(summarize_anim_export_validation(meta) or {})
    except Exception:
        contract_summary = {}
        validation_summary = {}

    def _resolve_sidecar(ref: Any, *, pointer_json: Any, fallback_path: Any = None) -> tuple[str, str, bool | None]:
        ref_s = str(ref or "").strip()
        if not ref_s and fallback_path not in (None, ""):
            ref_s = str(fallback_path or "").strip()
        if not ref_s:
            return "", "", None
        p = Path(ref_s)
        if not p.is_absolute():
            try:
                ptr = Path(str(pointer_json or "")).expanduser()
                if str(ptr):
                    p = (ptr.parent / p).resolve()
            except Exception:
                p = Path(ref_s)
        try:
            exists = bool(p.exists())
        except Exception:
            exists = None
        return str(ref_s), str(p), exists

    pointer_json = diag.get("anim_latest_pointer_json") or ""
    road_ref, road_path, road_exists = _resolve_sidecar(
        meta.get("road_csv"),
        pointer_json=pointer_json,
        fallback_path=(deps.get("road_csv") or {}).get("path") or deps.get("road_csv_path"),
    )
    axay_ref, axay_path, axay_exists = _resolve_sidecar(meta.get("axay_csv"), pointer_json=pointer_json)
    scenario_ref, scenario_path, scenario_exists = _resolve_sidecar(meta.get("scenario_json"), pointer_json=pointer_json)
    diag["anim_latest_road_csv_ref"] = road_ref
    diag["anim_latest_road_csv_path"] = road_path
    diag["anim_latest_road_csv_exists"] = road_exists
    diag["anim_latest_axay_csv_ref"] = axay_ref
    diag["anim_latest_axay_csv_path"] = axay_path
    diag["anim_latest_axay_csv_exists"] = axay_exists
    diag["anim_latest_scenario_json_ref"] = scenario_ref
    diag["anim_latest_scenario_json_path"] = scenario_path
    diag["anim_latest_scenario_json_exists"] = scenario_exists
    if contract_summary:
        diag.update({f"anim_latest_{k}": v for k, v in contract_summary.items()})
    if validation_summary:
        diag.update({f"anim_latest_{k}": v for k, v in validation_summary.items()})

    issues = [str(x) for x in (diag.get("anim_latest_issues") or []) if str(x).strip()]
    lines = ["# Anim Latest Pointer Diagnostics", ""]
    lines.append(f"- anim_latest_available: {bool(diag.get('anim_latest_available'))}")
    lines.append(f"- anim_latest_usable: {diag.get('anim_latest_usable')}")
    lines.append(f"- anim_latest_pointer_json_exists: {diag.get('anim_latest_pointer_json_exists')}")
    lines.append(f"- anim_latest_npz_exists: {diag.get('anim_latest_npz_exists')}")
    lines.append(f"- anim_latest_global_pointer_json: {diag.get('anim_latest_global_pointer_json') or '—'}")
    lines.append(f"- anim_latest_pointer_json: {diag.get('anim_latest_pointer_json') or '—'}")
    lines.append(f"- anim_latest_npz_path: {diag.get('anim_latest_npz_path') or '—'}")
    lines.append(f"- anim_latest_road_csv: {diag.get('anim_latest_road_csv_ref') or '—'} -> {diag.get('anim_latest_road_csv_path') or '—'} (exists={diag.get('anim_latest_road_csv_exists')})")
    lines.append(f"- anim_latest_axay_csv: {diag.get('anim_latest_axay_csv_ref') or '—'} -> {diag.get('anim_latest_axay_csv_path') or '—'} (exists={diag.get('anim_latest_axay_csv_exists')})")
    lines.append(f"- anim_latest_scenario_json: {diag.get('anim_latest_scenario_json_ref') or '—'} -> {diag.get('anim_latest_scenario_json_path') or '—'} (exists={diag.get('anim_latest_scenario_json_exists')})")
    lines.append(f"- anim_latest_contract_sidecar: {diag.get('anim_latest_contract_sidecar_ref') or '—'} -> {diag.get('anim_latest_contract_sidecar_path') or '—'} (exists={diag.get('anim_latest_contract_sidecar_exists')})")
    lines.append(f"- anim_latest_hardpoints_source_of_truth: {diag.get('anim_latest_hardpoints_source_of_truth_ref') or '—'} -> {diag.get('anim_latest_hardpoints_source_of_truth_path') or '—'} (exists={diag.get('anim_latest_hardpoints_source_of_truth_exists')})")
    lines.append(f"- anim_latest_cylinder_packaging_passport: {diag.get('anim_latest_cylinder_packaging_passport_ref') or '—'} -> {diag.get('anim_latest_cylinder_packaging_passport_path') or '—'} (exists={diag.get('anim_latest_cylinder_packaging_passport_exists')})")
    lines.append(f"- anim_latest_road_contract_web: {diag.get('anim_latest_road_contract_web_ref') or '—'} -> {diag.get('anim_latest_road_contract_web_path') or '—'} (exists={diag.get('anim_latest_road_contract_web_exists')})")
    lines.append(f"- anim_latest_road_contract_desktop: {diag.get('anim_latest_road_contract_desktop_ref') or '—'} -> {diag.get('anim_latest_road_contract_desktop_path') or '—'} (exists={diag.get('anim_latest_road_contract_desktop_exists')})")
    lines.append(
        f"- anim_latest_mnemo_event_log: {diag.get('anim_latest_mnemo_event_log_ref') or '—'} -> {diag.get('anim_latest_mnemo_event_log_path') or '—'} "
        f"(exists={diag.get('anim_latest_mnemo_event_log_exists')}, schema={diag.get('anim_latest_mnemo_event_log_schema_version') or '—'}, updated_utc={diag.get('anim_latest_mnemo_event_log_updated_utc') or '—'})"
    )
    lines.append(
        f"- anim_latest_mnemo_event_log_state: mode={diag.get('anim_latest_mnemo_event_log_current_mode') or '—'} / total={diag.get('anim_latest_mnemo_event_log_event_count')} / active={diag.get('anim_latest_mnemo_event_log_active_latch_count')} / acked={diag.get('anim_latest_mnemo_event_log_acknowledged_latch_count')}"
    )
    recent_titles = [str(x) for x in (diag.get("anim_latest_mnemo_event_log_recent_titles") or []) if str(x).strip()]
    if recent_titles:
        lines.append(f"- anim_latest_mnemo_event_log_recent: {' | '.join(recent_titles[:3])}")
    lines.append(f"- browser_perf_registry_snapshot: {diag.get('browser_perf_registry_snapshot_ref') or '—'} -> {diag.get('browser_perf_registry_snapshot_path') or '—'} (exists={diag.get('browser_perf_registry_snapshot_exists')}, in_bundle={diag.get('browser_perf_registry_snapshot_in_bundle')})")
    lines.append(f"- browser_perf_previous_snapshot: {diag.get('browser_perf_previous_snapshot_ref') or '—'} -> {diag.get('browser_perf_previous_snapshot_path') or '—'} (exists={diag.get('browser_perf_previous_snapshot_exists')}, in_bundle={diag.get('browser_perf_previous_snapshot_in_bundle')})")
    lines.append(f"- browser_perf_contract: {diag.get('browser_perf_contract_ref') or '—'} -> {diag.get('browser_perf_contract_path') or '—'} (exists={diag.get('browser_perf_contract_exists')}, in_bundle={diag.get('browser_perf_contract_in_bundle')})")
    lines.append(f"- browser_perf_evidence_report: {diag.get('browser_perf_evidence_report_ref') or '—'} -> {diag.get('browser_perf_evidence_report_path') or '—'} (exists={diag.get('browser_perf_evidence_report_exists')}, in_bundle={diag.get('browser_perf_evidence_report_in_bundle')})")
    lines.append(f"- browser_perf_comparison_report: {diag.get('browser_perf_comparison_report_ref') or '—'} -> {diag.get('browser_perf_comparison_report_path') or '—'} (exists={diag.get('browser_perf_comparison_report_exists')}, in_bundle={diag.get('browser_perf_comparison_report_in_bundle')})")
    lines.append(f"- browser_perf_trace: {diag.get('browser_perf_trace_ref') or '—'} -> {diag.get('browser_perf_trace_path') or '—'} (exists={diag.get('browser_perf_trace_exists')}, in_bundle={diag.get('browser_perf_trace_in_bundle')})")
    lines.append(f"- browser_perf_status: {diag.get('browser_perf_status') or '—'} / level={diag.get('browser_perf_level') or '—'}")
    lines.append(f"- browser_perf_evidence_status: {diag.get('browser_perf_evidence_status') or '—'} / level={diag.get('browser_perf_evidence_level') or '—'} / bundle_ready={diag.get('browser_perf_bundle_ready')} / snapshot_contract_match={diag.get('browser_perf_snapshot_contract_match')}")
    lines.append(f"- browser_perf_comparison_status: {diag.get('browser_perf_comparison_status') or '—'} / level={diag.get('browser_perf_comparison_level') or '—'} / ready={diag.get('browser_perf_comparison_ready')} / changed={diag.get('browser_perf_comparison_changed')}")
    lines.append(f"- browser_perf_comparison_delta: wakeups={diag.get('browser_perf_comparison_delta_total_wakeups')} / dup={diag.get('browser_perf_comparison_delta_total_duplicate_guard_hits')} / render={diag.get('browser_perf_comparison_delta_total_render_count')} / max_idle_poll_ms={diag.get('browser_perf_comparison_delta_max_idle_poll_ms')}")
    lines.append(f"- browser_perf_component_count: {diag.get('browser_perf_component_count')} / total_wakeups={diag.get('browser_perf_total_wakeups')} / total_duplicate_guard_hits={diag.get('browser_perf_total_duplicate_guard_hits')} / max_idle_poll_ms={diag.get('browser_perf_max_idle_poll_ms')}")
    lines.append(f"- anim_latest_visual_cache_token: {diag.get('anim_latest_visual_cache_token') or '—'}")
    reload_inputs = list(diag.get("anim_latest_visual_reload_inputs") or [])
    lines.append(f"- anim_latest_visual_reload_inputs: {', '.join(str(x) for x in reload_inputs) if reload_inputs else '—'}")
    lines.append(f"- anim_latest_updated_utc: {diag.get('anim_latest_updated_utc') or '—'}")
    if contract_summary:
        lines.append(f"- anim_latest_has_solver_points_block: {diag.get('anim_latest_has_solver_points_block')}")
        lines.append(f"- anim_latest_has_hardpoints_block: {diag.get('anim_latest_has_hardpoints_block')}")
        lines.append(f"- anim_latest_has_packaging_block: {diag.get('anim_latest_has_packaging_block')}")
        lines.append(f"- anim_latest_packaging_status: {diag.get('anim_latest_packaging_status') or '—'}")
        lines.append(f"- anim_latest_packaging_truth_ready: {diag.get('anim_latest_packaging_truth_ready')}")
    if validation_summary:
        lines.append(f"- anim_latest_validation_level: {diag.get('anim_latest_validation_level') or '—'}")
        lines.append(f"- anim_latest_validation_visible_present_family_count: {diag.get('anim_latest_validation_visible_present_family_count')} / {diag.get('anim_latest_validation_visible_required_family_count')}")
        lines.append(f"- anim_latest_validation_packaging_status: {diag.get('anim_latest_validation_packaging_status') or '—'}")
        lines.append(f"- anim_latest_validation_packaging_truth_ready: {diag.get('anim_latest_validation_packaging_truth_ready')}")
    if issues:
        lines.extend(["", "## anim_latest_issues", *[f"- {x}" for x in issues]])
    if deps:
        lines.extend(["", "## visual_cache_dependencies", "```json", json.dumps(deps, ensure_ascii=False, indent=2), "```"])
    if diag.get("anim_latest_meta"):
        lines.extend(["", "## anim_latest_meta", "```json", json.dumps(diag.get("anim_latest_meta"), ensure_ascii=False, indent=2), "```"])
    if diag.get("error"):
        lines.extend(["", f"error: {diag.get('error')}"])
    md = "\n".join(lines).rstrip() + "\n"

    try:
        _safe_write_text(out_dir / ANIM_DIAG_SIDECAR_JSON, json.dumps(diag, ensure_ascii=False, indent=2))
        _safe_write_text(out_dir / ANIM_DIAG_SIDECAR_MD, md)
    except Exception:
        pass
    return diag, md


def _health_report_failure_payload(zip_path: Path, error_text: str) -> Dict[str, Any]:
    python_truth = _runtime_python_truth_override()
    return {
        "schema": "health_report",
        "schema_version": "1.3.0",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "zip_path": str(zip_path),
        "ok": False,
        "signals": {
            "health_report_error": {
                "error": str(error_text),
                "python_executable": python_truth["python_executable"],
                "python_prefix": python_truth["python_prefix"],
                "python_base_prefix": python_truth["python_base_prefix"],
                "venv_active": python_truth["venv_active"],
                "preferred_cli_python": python_truth["preferred_cli_python"],
                "python_executable_current": python_truth["python_executable_current"],
                "python_runtime_source": python_truth["python_runtime_source"],
            }
        },
        "notes": [
            "health report generation failed; embedded fallback stub instead of dropping artifact",
            str(error_text),
        ],
    }


def make_send_bundle(
    repo_root: Optional[Path] = None,
    *,
    out_dir: Path,
    keep_last_n: int = 3,
    max_file_mb: int = 80,
    include_workspace_osc: bool = False,
    primary_session_dir: Optional[Path] = None,
    project_root: Optional[Path] = None,
    tag: Optional[str] = None,
    operator_note: Optional[str] = None,
    trigger: Optional[str] = None,
) -> Path:
    """Thread/process-safe wrapper around the actual bundle builder.

    ⚠️ Backward compatibility
    -------------------------
    В некоторых сборках UI/лаунчер вызывали эту функцию как:

        make_send_bundle(project_root=ROOT, ...)

    А в коде упаковщика параметр назывался `repo_root`.

    Чтобы не ломать кнопку "Сохранить диагностический пакет" между версиями,
    мы поддерживаем оба имени аргумента: `repo_root` и legacy `project_root`.

    R54: Adds an inter-process lock to avoid race conditions when multiple
    triggers attempt to build a send bundle simultaneously.
    """

    if repo_root is None:
        repo_root = project_root
    if repo_root is None:
        raise TypeError("make_send_bundle() requires repo_root (positional) or project_root=...")

    repo_root = Path(repo_root).expanduser().resolve()
    out_dir = Path(out_dir).expanduser().resolve()
    lock_path = out_dir / ".send_bundle.lock"

    # Lock tuning via env (best-effort)
    def _env_f(name: str, default: float) -> float:
        try:
            return float(os.environ.get(name, str(default)) or str(default))
        except Exception:
            return float(default)

    timeout_s = _env_f("PNEUMO_SEND_BUNDLE_LOCK_TIMEOUT_S", 180.0)
    poll_s = _env_f("PNEUMO_SEND_BUNDLE_LOCK_POLL_S", 0.25)
    stale_ttl_s = _env_f("PNEUMO_SEND_BUNDLE_LOCK_STALE_TTL_S", 600.0)

    try:
        from pneumo_solver_ui.tools.bundle_lock import SendBundleLock

        with SendBundleLock(
            lock_path,
            timeout_s=timeout_s,
            poll_s=poll_s,
            stale_ttl_s=stale_ttl_s,
            release=RELEASE,
        ):
            _maybe_run_selfcheck_suite(repo_root)
            # NOTE: selfcheck suite output lands in diagnostics_runs/ and will be included into this bundle.
            return _make_send_bundle_inner(
                repo_root,
                out_dir=out_dir,
                keep_last_n=keep_last_n,
                max_file_mb=max_file_mb,
                include_workspace_osc=include_workspace_osc,
                primary_session_dir=primary_session_dir,
                tag=tag,
                operator_note=operator_note,
                trigger=trigger,
            )
    except Exception:
        # If lock fails for any reason, still attempt to build bundle (best-effort).
        _maybe_run_selfcheck_suite(repo_root)
        # NOTE: lock failure should not skip P0-TOOLS-001 checks.
        return _make_send_bundle_inner(
            repo_root,
            out_dir=out_dir,
            keep_last_n=keep_last_n,
            max_file_mb=max_file_mb,
            include_workspace_osc=include_workspace_osc,
            primary_session_dir=primary_session_dir,
            tag=tag,
            operator_note=operator_note,
            trigger=trigger,
        )



def main() -> int:
    ap = argparse.ArgumentParser(description="Create a send-to-chat bundle ZIP (logs + test artifacts)")
    ap.add_argument("--out_dir", default="send_bundles", help="Куда складывать send bundle (относительно repo root)")
    ap.add_argument("--keep_last_n", type=int, default=3, help="Сколько последних прогонов autotest/diagnostics включать")
    ap.add_argument("--max_file_mb", type=int, default=80, help="Пропускать файлы больше этого размера (МБ)")
    ap.add_argument("--include_workspace_osc", action="store_true", help="Включать workspace/osc (может быть большим)")
    ap.add_argument("--primary_session_dir", default=None, help="Явно указать UI session dir (приоритетнее env PNEUMO_SESSION_DIR)")
    ap.add_argument("--trigger", default="manual", help="Machine-readable bundle trigger/mode provenance")
    ap.add_argument("--print_path", action="store_true", help="Напечатать путь к созданному zip")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = (repo_root / str(args.out_dir)).resolve()

    zip_path = make_send_bundle(
        repo_root,
        out_dir=out_dir,
        keep_last_n=int(args.keep_last_n),
        max_file_mb=int(args.max_file_mb),
        include_workspace_osc=bool(args.include_workspace_osc),
        primary_session_dir=Path(args.primary_session_dir) if args.primary_session_dir else None,
        trigger=str(args.trigger or "manual"),
    )

    if args.print_path:
        print(str(zip_path))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
