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
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .send_bundle_contract import (
    ANIM_DIAG_JSON,
    ANIM_DIAG_MD,
    ANIM_DIAG_SIDECAR_JSON,
    ANIM_DIAG_SIDECAR_MD,
    build_anim_operator_recommendations,
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
        diag = {
            "anim_latest_available": False,
            "error": repr(exc),
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
    diag = dict(anim_diag or {})
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
        f"- anim_latest_road_csv_ref: {road_ref}\n"
        f"- anim_latest_axay_csv_ref: {axay_ref}\n"
        f"- anim_latest_scenario_json_ref: {scenario_ref}\n"
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
) -> Path:
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    pneumo_dir = repo_root / "pneumo_solver_ui"

    stamp = _ts()
    tag_s = _sanitize_tag(tag)
    zip_path = out_dir / (f"SEND_{stamp}_{tag_s}_bundle.zip" if tag_s else f"SEND_{stamp}_bundle.zip")

    max_file_bytes = int(max_file_mb) * 1024 * 1024

    meta: Dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "release": RELEASE,
        "repo_root": str(repo_root),
        "pneumo_dir": str(pneumo_dir),
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

    try:
        anim_diag_event, anim_diag_md = _collect_anim_latest_bundle_diagnostics(out_dir)
    except Exception:
        anim_diag_event = {"anim_latest_available": False, "error": traceback.format_exc()}
        anim_diag_md = "# Anim Latest Pointer Diagnostics\n\nerror collecting diagnostics\n"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # --- meta & docs inside bundle ---
        z.writestr("bundle/meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

        readme = _build_send_bundle_readme(anim_diag_event)
        z.writestr("bundle/README_SEND_BUNDLE.txt", readme)

        # --- triage report (best-effort) ---
        try:
            from pneumo_solver_ui.tools.triage_report import generate_triage_report, write_triage_report

            triage_md, triage_json = generate_triage_report(
                repo_root,
                keep_last_n=int(keep_last_n),
                primary_session_dir=primary_session_dir,
            )
            z.writestr("triage/triage_report_pre.md", triage_md)
            z.writestr("triage/triage_report_pre.json", json.dumps(triage_json, ensure_ascii=False, indent=2))

            # Also keep a copy next to bundles (latest_triage_report.*) for quick access.
            try:
                write_triage_report(out_dir, triage_md, triage_json, stamp=stamp)
            except Exception:
                pass

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
        if p_env_ws is not None and str(p_env_ws) != str(effective_ws):
            meta["env_workspace_path"] = str(p_env_ws)
        meta["repo_local_workspace_path"] = str(default_ws)

        # Canonical bundle workspace must always mirror the effective runtime workspace.
        _add_workspace_dir(effective_ws, "workspace")

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
        # R59 contract: MANIFEST.json must exist (keep also legacy bundle/manifest.json).
        _mjson = json.dumps(manifest, ensure_ascii=False, indent=2)
        z.writestr("bundle/manifest.json", _mjson)
        # Convenience copies (some users/scripts expect these at ZIP root)
        z.writestr("MANIFEST.json", _mjson)
        z.writestr("manifest.json", _mjson)
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
    try:
        from pneumo_solver_ui.tools.validate_send_bundle import validate_send_bundle

        vres = validate_send_bundle(zip_path)
        validation_ok = bool(vres.ok)
        try:
            validation_errors = int(len(vres.report_json.get("errors") or []))
            validation_warnings = int(len(vres.report_json.get("warnings") or []))
        except Exception:
            validation_errors = 0
            validation_warnings = 0

        # Embed into the same ZIP (append mode).
        with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as z2:
            z2.writestr("validation/validation_report.md", vres.report_md)
            z2.writestr(
                "validation/validation_report.json",
                json.dumps(vres.report_json, ensure_ascii=False, indent=2),
            )

        # Sidecars for quick access (without opening ZIP)
        try:
            _safe_write_text(out_dir / "latest_send_bundle_validation.md", vres.report_md)
            _safe_write_text(
                out_dir / "latest_send_bundle_validation.json",
                json.dumps(vres.report_json, ensure_ascii=False, indent=2),
            )
        except Exception:
            pass

    except Exception:
        # best-effort: do not fail bundle creation
        try:
            with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as z2:
                z2.writestr("validation/validation_failed.txt", traceback.format_exc())
        except Exception:
            pass



    # ------------------------------------------------------------
    # R52: Unified HTML dashboard (triage + validation + sqlite metrics)
    # ------------------------------------------------------------
    dashboard_created: bool = False
    try:
        from pneumo_solver_ui.tools.dashboard_report import generate_dashboard_report, write_dashboard_sidecars

        dash_html, dash_json = generate_dashboard_report(
            repo_root,
            out_dir,
            zip_path=zip_path,
            keep_last_n=int(keep_last_n),
        )

        # Embed into the same ZIP (append mode).
        with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as z2:
            z2.writestr("dashboard/index.html", dash_html)
            z2.writestr(
                "dashboard/dashboard.json",
                json.dumps(dash_json, ensure_ascii=False, indent=2),
            )

        # Sidecars for quick access (without opening ZIP)
        try:
            write_dashboard_sidecars(out_dir, dash_html, dash_json, stamp=stamp)
        except Exception:
            pass

        dashboard_created = True

    except Exception:
        dashboard_created = False
        try:
            with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as z2:
                z2.writestr("dashboard/dashboard_failed.txt", traceback.format_exc())
        except Exception:
            pass

    # pointer to latest
    latest_zip = out_dir / "latest_send_bundle.zip"
    latest_txt = out_dir / "latest_send_bundle_path.txt"

    try:
        # R54: atomic update of latest pointers (avoid half-written files)
        _atomic_copy_file(zip_path, latest_zip)
        _safe_write_text(latest_txt, str(zip_path.resolve()))

        # Also write SHA256 for the *latest* bundle to simplify verification / sharing.
        try:
            sha = _sha256_file(latest_zip)
            _safe_write_text(out_dir / 'latest_send_bundle.sha256', sha + '  latest_send_bundle.zip\n')
        except Exception:
            pass

        # Maintain a small index.json for bundle history (best-effort, capped).
        try:
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

            rec = {
                'created_at': meta.get('created_at'),
                'release': meta.get('release'),
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
            }

            # Prepend, deduplicate by zip_name
            bundles = [b for b in bundles if not (isinstance(b, dict) and b.get('zip_name') == rec['zip_name'])]
            bundles.insert(0, rec)
            bundles = bundles[:50]

            idx['bundles'] = bundles
            idx['latest'] = {'zip_name': zip_path.name, 'latest_zip_path': str(latest_zip.resolve())}

            tmp = idx_path.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding='utf-8', errors='replace')
            tmp.replace(idx_path)
        except Exception:
            pass

    except Exception:
        # if copy fails, at least store path
        try:
            _safe_write_text(latest_txt, str(zip_path.resolve()))
        except Exception:
            pass





    # R68 retired in R32.
    # Final in-archive triage rewrite now happens *after* run-registry logging
    # (see the R32 block near the end of this function), so keeping the older
    # pre-registry rewrite would only create duplicate ZIP entries and stale
    # registry summaries.

    # R69: defer health report until after the final triage rewrite.
    # The final triage/registry pass appends triage files later in this function,
    # so building health here would inspect a stale ZIP and miss triage_report.*.

    # R69b: interim latest_send_bundle refresh before run-registry/final triage; final refresh happens after the final health rebuild.
    try:
        if zip_path.exists():
            _atomic_copy_file(zip_path, latest_zip)
            try:
                sha = _sha256_file(latest_zip)
                _safe_write_text(out_dir / 'latest_send_bundle.sha256', sha + '  latest_send_bundle.zip\n')
            except Exception:
                pass
    except Exception:
        pass

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
            dashboard_created=dashboard_created,
            dashboard_html_path=str((out_dir / "latest_dashboard.html").resolve()) if (out_dir / "latest_dashboard.html").exists() else None,
            env=env_context(),
            **anim_diag_event,
        )
    except Exception:
        pass

    # R32: after run-registry write, regenerate triage once more so the bundle
    # and latest sidecars can see the *current* send_bundle_created event instead
    # of a stale older one from a previous workspace/release.
    try:
        import re as _re3
        from pneumo_solver_ui.tools.triage_report import generate_triage_report as _generate_triage_report_final
        from pneumo_solver_ui.tools.triage_report import write_triage_report as _write_triage_report_final

        _latest_txt3 = out_dir / "latest_send_bundle_path.txt"
        _latest_md3 = out_dir / "latest_send_bundle_validation.md"
        _latest_json3 = out_dir / "latest_send_bundle_validation.json"
        _triage3_md, _triage3_json = _generate_triage_report_final(
            repo_root=repo_root,
            keep_last_n=keep_last_n,
            primary_session_dir=primary_session_dir,
        )
        _triage3_md = _re3.sub(
            r"(?m)^- Latest send bundle path:.*$",
            f"- Latest send bundle path: triage/{_latest_txt3.name} (inside this bundle)",
            _triage3_md,
        )
        _triage3_md = _re3.sub(
            r"(?m)^- Latest send bundle validation:.*$",
            f"- Latest send bundle validation: triage/{_latest_md3.name} (inside this bundle)",
            _triage3_md,
        )
        _triage3_md = _re3.sub(
            r"(?m)^- Latest anim diagnostics json:.*$",
            f"- Latest anim diagnostics json: {ANIM_DIAG_JSON} (inside this bundle)",
            _triage3_md,
        )
        _triage3_md = _re3.sub(
            r"(?m)^- Latest anim diagnostics md:.*$",
            f"- Latest anim diagnostics md: {ANIM_DIAG_MD} (inside this bundle)",
            _triage3_md,
        )
        with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as _z3:
            _z3.writestr("triage/triage_report.md", _triage3_md)
            _z3.writestr("triage/triage_report.json", json.dumps(_triage3_json, ensure_ascii=False, indent=2))
            for _p in (_latest_txt3, _latest_md3, _latest_json3):
                try:
                    if _p.exists():
                        _z3.write(_p, arcname=f"triage/{_p.name}")
                except Exception:
                    pass
        try:
            _write_triage_report_final(out_dir, _triage3_md, _triage3_json, stamp=stamp)
        except Exception:
            pass
    except Exception:
        pass

    # R69c: now that the run-registry event and final triage files are in place,
    # rebuild the health report against the final ZIP contents and refresh the
    # latest bundle copy/sha to match the post-triage archive.
    try:
        from pneumo_solver_ui.tools.health_report import build_health_report, add_health_report_to_zip

        _health_json, _health_md = build_health_report(zip_path, out_dir=out_dir)
        add_health_report_to_zip(zip_path, _health_json, _health_md)
    except Exception:
        _health_err = traceback.format_exc()
        try:
            _fallback_json, _fallback_md = _write_health_report_failure_stub(zip_path, out_dir, _health_err)
            with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as _z2:
                _z2.write(_fallback_json, arcname="health/health_report.json")
                _z2.write(_fallback_md, arcname="health/health_report.md")
                _z2.writestr("health/health_report_failed.txt", _health_err)
        except Exception:
            try:
                with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as _z2:
                    _z2.writestr("health/health_report_failed.txt", _health_err)
            except Exception:
                pass

    try:
        if zip_path.exists():
            _atomic_copy_file(zip_path, latest_zip)
            _safe_write_text(latest_txt, str(zip_path.resolve()))
            try:
                sha = _sha256_file(latest_zip)
                _safe_write_text(out_dir / 'latest_send_bundle.sha256', sha + '  latest_send_bundle.zip\n')
            except Exception:
                pass
    except Exception:
        pass

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
        )



def main() -> int:
    ap = argparse.ArgumentParser(description="Create a send-to-chat bundle ZIP (logs + test artifacts)")
    ap.add_argument("--out_dir", default="send_bundles", help="Куда складывать send bundle (относительно repo root)")
    ap.add_argument("--keep_last_n", type=int, default=3, help="Сколько последних прогонов autotest/diagnostics включать")
    ap.add_argument("--max_file_mb", type=int, default=80, help="Пропускать файлы больше этого размера (МБ)")
    ap.add_argument("--include_workspace_osc", action="store_true", help="Включать workspace/osc (может быть большим)")
    ap.add_argument("--primary_session_dir", default=None, help="Явно указать UI session dir (приоритетнее env PNEUMO_SESSION_DIR)")
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
    )

    if args.print_path:
        print(str(zip_path))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
