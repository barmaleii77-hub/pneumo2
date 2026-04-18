#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_send_bundle.py

R53: Валидация send bundle ZIP (quality gate)
=============================================

Зачем
-----
Send Bundle — это "единый артефакт" для отправки в чат после закрытия UI.
Чтобы повышать надёжность, недостаточно просто *создать* ZIP: нужно автоматически
проверить, что он:

- содержит обязательные файлы (meta/manifest/summary),
- содержит triage (или хотя бы файл с ошибкой triage),
- не содержит битого JSON,
- не имеет несоответствий SHA256/size для файлов из manifest,
- не теряет anim_latest reload diagnostics в финальном bundle.

Скрипт делает best-effort валидацию и генерирует:
- validation_report.json (машиночитаемо)
- validation_report.md   (человекочитаемо)

Результат используется:
- из make_send_bundle.py (автоматически кладётся в ZIP и пишется рядом как latest_*),
- вручную при расследовании.

Запуск
------
  python -m pneumo_solver_ui.tools.validate_send_bundle --zip send_bundles/latest_send_bundle.zip --print_summary

"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pneumo_solver_ui.optimization_scope_compare import (
    compare_optimizer_scope_sources,
    evaluate_optimizer_scope_gate,
    extract_optimizer_scope_from_health,
    extract_optimizer_scope_from_run_scope,
    extract_optimizer_scope_from_triage,
    optimizer_scope_export_source_name,
)

from .send_bundle_contract import (
    ANIM_DIAG_JSON,
    ANIM_DIAG_MD,
    ANIM_GLOBAL_POINTER,
    ANIM_LOCAL_NPZ,
    ANIM_LOCAL_POINTER,
    BROWSER_PERF_FLAT_FIELDS,
    RING_META_FLAT_FIELDS,
    annotate_anim_source_for_bundle,
    choose_anim_snapshot,
    extract_anim_snapshot,
)
from .send_bundle_evidence import (
    ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME,
    ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME,
    EVIDENCE_MANIFEST_ARCNAME,
    EVIDENCE_MANIFEST_SIDECAR_NAME,
    GEOMETRY_REFERENCE_EVIDENCE_ARCNAME,
    GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME,
    build_latest_integrity_proof,
    evidence_manifest_release_errors,
    evidence_manifest_warnings,
    load_evidence_manifest_from_zip,
    summarize_engineering_analysis_evidence,
    summarize_geometry_reference_evidence,
)


try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _safe_json_load_bytes(b: bytes) -> Any:
    try:
        return json.loads(b.decode("utf-8", errors="replace"))
    except Exception:
        return None


def _safe_json_load_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _browser_perf_default_value(key: str) -> Any:
    if key.endswith(("_exists", "_ready", "_changed", "_match")):
        return None
    if key.endswith(("_count", "_wakeups", "_guard_hits", "_idle_poll_ms")):
        return 0
    return ""


def _copy_browser_perf_fields(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for key in BROWSER_PERF_FLAT_FIELDS:
        if key not in src:
            continue
        value = src.get(key)
        if key.endswith(("_count", "_wakeups", "_guard_hits", "_idle_poll_ms")):
            dst[key] = int(value or 0)
        elif key.endswith(("_exists", "_ready", "_changed", "_match")):
            dst[key] = value
        else:
            dst[key] = str(value or "")


def _copy_ring_meta_fields(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for key in RING_META_FLAT_FIELDS:
        if key not in src:
            continue
        value = src.get(key)
        if isinstance(value, dict):
            dst[key] = dict(value)
        elif isinstance(value, list):
            dst[key] = list(value)
        elif key in {"ring_closure_applied", "ring_seam_open"}:
            dst[key] = value
        elif key in {
            "ring_v0_kph",
            "ring_v0_mps",
            "ring_nominal_speed_min_mps",
            "ring_nominal_speed_max_mps",
            "ring_nominal_speed_mean_mps",
            "ring_seam_max_jump_m",
            "ring_raw_seam_max_jump_m",
        }:
            if value in (None, ""):
                dst[key] = None
            else:
                try:
                    dst[key] = float(value)
                except Exception:
                    dst[key] = value
        else:
            dst[key] = str(value or "")


def _ref_present_in_bundle(ref: Any, bundle_basenames: set[str]) -> Optional[bool]:
    ref_text = str(ref or "").strip()
    if not ref_text:
        return None
    return Path(ref_text).name in bundle_basenames


def _anim_snapshot_requires_bundle_contract(snapshot: dict[str, Any] | None) -> bool:
    if not isinstance(snapshot, dict):
        return False
    return bool(
        snapshot.get("available")
        or snapshot.get("visual_cache_token")
        or snapshot.get("pointer_json")
        or snapshot.get("npz_path")
        or snapshot.get("visual_reload_inputs")
    )


def _md_list(items: List[str]) -> str:
    if not items:
        return "- (нет)"
    return "\n".join([f"- {x}" for x in items])


def _ui_state_payload_names(name_set: set[str], prefix: str) -> List[str]:
    out: List[str] = []
    for n in sorted(name_set):
        if n.startswith(prefix) and n.lower().endswith('.json'):
            out.append(n)
    return out


def _ui_state_marker_names(name_set: set[str], prefix: str) -> List[str]:
    out: List[str] = []
    for n in sorted(name_set):
        if n.startswith(prefix) and n.endswith('_EMPTY_OR_MISSING.txt'):
            out.append(n)
    return out


@dataclass
class ValidationResult:
    ok: bool
    report_json: Dict[str, Any]
    report_md: str



def validate_send_bundle(zip_path: Path, *, max_manifest_files: int = 50_000) -> ValidationResult:
    """Validate a send bundle ZIP.

    Notes:
      - We validate only files tracked by bundle/manifest.json.
      - z.writestr()-based files (meta/triage/...) are validated by presence+JSON parse.
      - anim_latest diagnostics are best-effort but must be surfaced explicitly.
    """
    zp = Path(zip_path).expanduser().resolve()
    t0 = time.time()

    rep: Dict[str, Any] = {
        "schema": "send_bundle_validation",
        "schema_version": "1.0.0",
        "release": RELEASE,
        "checked_at": _now_iso(),
        "zip_path": str(zp),
        "ok": True,
        "errors": [],
        "warnings": [],
        "release_risks": [],
        "stats": {},
        "anim_latest": {},
        "evidence_manifest": {},
        "latest_integrity_proof": {},
        "engineering_analysis_evidence": {},
        "geometry_reference_evidence": {},
        "optimizer_scope": {},
        "optimizer_scope_gate": {},
    }

    errors: List[str] = []
    warnings: List[str] = []

    if not zp.exists() or not zp.is_file():
        errors.append(f"ZIP not found: {zp}")
        rep["ok"] = False
        rep["errors"] = errors
        rep["warnings"] = warnings
        md = _render_md(rep)
        return ValidationResult(ok=False, report_json=rep, report_md=md)

    required = [
        "bundle/meta.json",
        "bundle/manifest.json",
        "bundle/summary.json",
        "bundle/skips.json",
        "bundle/README_SEND_BUNDLE.txt",
    ]

    recommended_any = [
        "triage/triage_report.md",
        "triage/triage_report_pre.md",
        "triage/triage_failed.txt",
    ]

    names: List[str] = []
    meta_obj: Any = None
    summary_obj: Any = None
    manifest_obj: Any = None
    skips_obj: Any = None
    anim_latest: Dict[str, Any] = {
        "diagnostics_json_present": False,
        "diagnostics_md_present": False,
        "local_pointer_present": False,
        "global_pointer_present": False,
        "diagnostics_json_valid": None,
        "local_pointer_valid": None,
        "global_pointer_valid": None,
        "available": False,
        "visual_cache_token": "",
        "visual_reload_inputs": [],
        "pointer_json": "",
        "global_pointer_json": "",
        "npz_path": "",
        "updated_utc": "",
        "pointer_sync_ok": None,
        "reload_inputs_sync_ok": None,
        "npz_path_sync_ok": None,
        "usable_from_bundle": None,
        "pointer_json_in_bundle": None,
        "npz_path_in_bundle": None,
        "browser_perf_registry_snapshot_in_bundle": None,
        "browser_perf_previous_snapshot_in_bundle": None,
        "browser_perf_contract_in_bundle": None,
        "browser_perf_evidence_report_in_bundle": None,
        "browser_perf_comparison_report_in_bundle": None,
        "browser_perf_trace_in_bundle": None,
        "issues": [],
        "sources": {},
    }
    anim_latest.update({key: _browser_perf_default_value(key) for key in BROWSER_PERF_FLAT_FIELDS})
    ui_autosave: Dict[str, Any] = {
        "persistent_state_json_present": False,
        "workspace_ui_state_json_present": False,
        "persistent_state_json_files": [],
        "workspace_ui_state_json_files": [],
        "persistent_state_marker_files": [],
        "workspace_ui_state_marker_files": [],
        "issues": [],
    }

    try:
        with zipfile.ZipFile(zp, "r") as z:
            names = z.namelist()
            name_set = set(names)
            bundle_basenames = {Path(name).name for name in name_set}

            missing_required = [p for p in required if p not in name_set]
            if missing_required:
                errors.append("Missing required files: " + ", ".join(missing_required))

            # R59 contract: UI autosave state must be included in the bundle.
            # Honest payload means JSON autosave files; marker files alone are not enough.
            ps_json = _ui_state_payload_names(name_set, "persistent_state/")
            ui_json = _ui_state_payload_names(name_set, "workspace/ui_state/")
            ps_markers = _ui_state_marker_names(name_set, "persistent_state/")
            ui_markers = _ui_state_marker_names(name_set, "workspace/ui_state/")
            ui_autosave["persistent_state_json_present"] = bool(ps_json)
            ui_autosave["workspace_ui_state_json_present"] = bool(ui_json)
            ui_autosave["persistent_state_json_files"] = ps_json[:12]
            ui_autosave["workspace_ui_state_json_files"] = ui_json[:12]
            ui_autosave["persistent_state_marker_files"] = ps_markers[:12]
            ui_autosave["workspace_ui_state_marker_files"] = ui_markers[:12]
            if not (ps_json or ui_json):
                msg = "Missing UI autosave state JSON (expected persistent_state/*.json or workspace/ui_state/*.json)"
                if ps_markers or ui_markers:
                    msg += "; bundle contains only empty/missing markers"
                errors.append(msg)
                ui_autosave["issues"].append(msg)

            # R59 contract v1.1: required folders for reproducibility.
            required_prefixes = [
                ("ui_logs/", "ui_logs/* (UI logs)"),
                ("workspace/exports/", "workspace/exports/*"),
                ("workspace/uploads/", "workspace/uploads/*"),
                ("workspace/road_profiles/", "workspace/road_profiles/*"),
                ("workspace/maneuvers/", "workspace/maneuvers/*"),
                ("workspace/opt_runs/", "workspace/opt_runs/*"),
            ]
            for pref, label in required_prefixes:
                if not any(n.startswith(pref) for n in name_set):
                    errors.append(f"Missing {label} (required by diagnostics bundle contract)")

            # Convenience/compat: root MANIFEST.json is expected (bundle/manifest.json is canonical).
            if "MANIFEST.json" not in name_set and "manifest.json" not in name_set:
                warnings.append("Missing MANIFEST.json at ZIP root (bundle/manifest.json is present)")

            if not any(p in name_set for p in recommended_any):
                warnings.append("Missing triage report files (triage_report*.md or triage_failed.txt)")

            def _read_json(path: str) -> Any:
                try:
                    b = z.read(path)
                except Exception:
                    return None
                return _safe_json_load_bytes(b)

            meta_obj = _read_json("bundle/meta.json")
            if meta_obj is None:
                errors.append("bundle/meta.json is not valid JSON")

            summary_obj = _read_json("bundle/summary.json")
            if summary_obj is None:
                errors.append("bundle/summary.json is not valid JSON")

            skips_obj = _read_json("bundle/skips.json")
            if skips_obj is None:
                errors.append("bundle/skips.json is not valid JSON")

            manifest_obj = _read_json("bundle/manifest.json")
            if not isinstance(manifest_obj, dict):
                errors.append("bundle/manifest.json is not a JSON object")
                manifest_obj = {}

            evidence_obj = load_evidence_manifest_from_zip(z)
            if evidence_obj:
                rep["evidence_manifest"] = dict(evidence_obj)
                for msg in evidence_manifest_warnings(evidence_obj):
                    if msg not in warnings:
                        warnings.append(msg)
                for msg in evidence_manifest_release_errors(evidence_obj):
                    if msg not in errors:
                        errors.append(msg)
            else:
                warnings.append(f"Missing {EVIDENCE_MANIFEST_ARCNAME} (merged diagnostics evidence manifest)")

            engineering_name = ""
            if ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME in name_set:
                engineering_name = ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME
            elif ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME in name_set:
                engineering_name = ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME
            if engineering_name:
                engineering_obj = _read_json(engineering_name)
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
                rep["engineering_analysis_evidence"] = engineering_summary
                for item in engineering_summary.get("warnings") or []:
                    msg = str(item).strip()
                    if msg and msg not in warnings:
                        warnings.append(msg)

            geometry_reference_name = ""
            if GEOMETRY_REFERENCE_EVIDENCE_ARCNAME in name_set:
                geometry_reference_name = GEOMETRY_REFERENCE_EVIDENCE_ARCNAME
            elif GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME in name_set:
                geometry_reference_name = GEOMETRY_REFERENCE_EVIDENCE_WORKSPACE_ARCNAME
            if geometry_reference_name:
                geometry_reference_obj = _read_json(geometry_reference_name)
                if isinstance(geometry_reference_obj, dict):
                    geometry_summary = summarize_geometry_reference_evidence(
                        geometry_reference_obj,
                        source_path=geometry_reference_name,
                    )
                    rep["geometry_reference_evidence"] = geometry_summary
                    for item in geometry_summary.get("warnings") or []:
                        msg = str(item).strip()
                        if msg and msg not in warnings:
                            warnings.append(msg)
                else:
                    warnings.append(f"{geometry_reference_name} is not valid JSON")

            optimizer_scope_sources: Dict[str, Dict[str, Any]] = {}
            triage_scope = extract_optimizer_scope_from_triage(_read_json("triage/triage_report.json"))
            if triage_scope:
                optimizer_scope_sources[str(triage_scope.get("source") or "triage")] = triage_scope

            health_scope = extract_optimizer_scope_from_health(_read_json("health/health_report.json"))
            if health_scope:
                optimizer_scope_sources[str(health_scope.get("source") or "health")] = health_scope

            for arcname in sorted(
                n
                for n in name_set
                if n == "run_scope.json" or n.endswith("/export/run_scope.json")
            ):
                export_scope = extract_optimizer_scope_from_run_scope(
                    _read_json(arcname),
                    source=optimizer_scope_export_source_name(arcname),
                    source_path=arcname,
                )
                if export_scope:
                    optimizer_scope_sources[str(export_scope.get("source") or arcname)] = export_scope

            optimizer_scope = compare_optimizer_scope_sources(
                optimizer_scope_sources,
                preferred_order=("triage", "health", "export"),
            )
            if optimizer_scope:
                rep["optimizer_scope"] = optimizer_scope
                for issue in optimizer_scope.get("issues") or []:
                    msg = str(issue).strip()
                    if msg:
                        warnings.append(msg)
            optimizer_scope_gate = evaluate_optimizer_scope_gate(rep.get("optimizer_scope"))
            if optimizer_scope_gate:
                rep["optimizer_scope_gate"] = optimizer_scope_gate
                if optimizer_scope_gate.get("release_risk"):
                    risk_msg = (
                        "optimizer scope release risk: "
                        f"{optimizer_scope_gate.get('release_gate_reason') or 'mismatch detected'}"
                    )
                    rep["release_risks"].append(risk_msg)
                    if risk_msg not in warnings:
                        warnings.append(risk_msg)

            # anim_latest diagnostics / pointer consistency (best effort, warning-only)
            anim_latest["diagnostics_json_present"] = ANIM_DIAG_JSON in name_set
            anim_latest["diagnostics_md_present"] = ANIM_DIAG_MD in name_set
            anim_latest["local_pointer_present"] = ANIM_LOCAL_POINTER in name_set
            anim_latest["global_pointer_present"] = ANIM_GLOBAL_POINTER in name_set

            diag_obj = _read_json(ANIM_DIAG_JSON) if anim_latest["diagnostics_json_present"] else None
            local_obj = _read_json(ANIM_LOCAL_POINTER) if anim_latest["local_pointer_present"] else None
            global_obj = _read_json(ANIM_GLOBAL_POINTER) if anim_latest["global_pointer_present"] else None

            anim_latest["diagnostics_json_valid"] = isinstance(diag_obj, dict) if anim_latest["diagnostics_json_present"] else None
            anim_latest["local_pointer_valid"] = isinstance(local_obj, dict) if anim_latest["local_pointer_present"] else None
            anim_latest["global_pointer_valid"] = isinstance(global_obj, dict) if anim_latest["global_pointer_present"] else None

            if anim_latest["diagnostics_json_present"] and not isinstance(diag_obj, dict):
                warnings.append(f"{ANIM_DIAG_JSON} is not valid JSON")
            if anim_latest["local_pointer_present"] and not isinstance(local_obj, dict):
                warnings.append(f"{ANIM_LOCAL_POINTER} is not valid JSON")
            if anim_latest["global_pointer_present"] and not isinstance(global_obj, dict):
                warnings.append(f"{ANIM_GLOBAL_POINTER} is not valid JSON")

            source_states = {
                "diagnostics": annotate_anim_source_for_bundle(
                    extract_anim_snapshot(diag_obj, source="diagnostics") if isinstance(diag_obj, dict) else None,
                    name_set=name_set,
                ),
                "local_pointer": annotate_anim_source_for_bundle(
                    extract_anim_snapshot(local_obj, source="local_pointer") if isinstance(local_obj, dict) else None,
                    name_set=name_set,
                ),
                "global_pointer": annotate_anim_source_for_bundle(
                    extract_anim_snapshot(global_obj, source="global_pointer") if isinstance(global_obj, dict) else None,
                    name_set=name_set,
                ),
            }
            anim_latest["sources"] = {k: v for k, v in source_states.items() if isinstance(v, dict)}
            anim_latest_expected = any(
                _anim_snapshot_requires_bundle_contract(state)
                for state in source_states.values()
                if isinstance(state, dict)
            )
            anim_latest["contract_expected"] = anim_latest_expected

            if not anim_latest["diagnostics_json_present"] and anim_latest_expected:
                warnings.append(f"Missing {ANIM_DIAG_JSON} (anim_latest diagnostics sidecar)")
            if not anim_latest["diagnostics_md_present"] and anim_latest_expected:
                warnings.append(f"Missing {ANIM_DIAG_MD} (anim_latest diagnostics sidecar)")
            if not anim_latest["global_pointer_present"] and anim_latest_expected:
                warnings.append(f"Missing {ANIM_GLOBAL_POINTER} (global anim_latest pointer)")
            if not anim_latest["local_pointer_present"] and anim_latest_expected:
                warnings.append(f"Missing {ANIM_LOCAL_POINTER} (local anim_latest pointer)")

            canonical = choose_anim_snapshot(
                {k: v for k, v in source_states.items() if isinstance(v, dict)},
                preferred_order=("diagnostics", "local_pointer", "global_pointer"),
            )

            if canonical:
                anim_latest["available"] = bool(
                    canonical.get("available")
                    or canonical.get("pointer_json")
                    or canonical.get("npz_path")
                    or canonical.get("visual_cache_token")
                )
                anim_latest["visual_cache_token"] = str(canonical.get("visual_cache_token") or "")
                anim_latest["visual_reload_inputs"] = list(canonical.get("visual_reload_inputs") or [])
                anim_latest["pointer_json"] = str(canonical.get("pointer_json") or "")
                anim_latest["global_pointer_json"] = str(canonical.get("global_pointer_json") or "")
                anim_latest["npz_path"] = str(canonical.get("npz_path") or "")
                anim_latest["updated_utc"] = str(canonical.get("updated_utc") or "")
                anim_latest["usable_from_bundle"] = canonical.get("usable_from_bundle")
                anim_latest["pointer_json_in_bundle"] = canonical.get("pointer_json_in_bundle")
                anim_latest["npz_path_in_bundle"] = canonical.get("npz_path_in_bundle")
                anim_latest["pointer_sync_ok"] = canonical.get("pointer_sync_ok")
                anim_latest["reload_inputs_sync_ok"] = canonical.get("reload_inputs_sync_ok")
                anim_latest["npz_path_sync_ok"] = canonical.get("npz_path_sync_ok")
                _copy_browser_perf_fields(anim_latest, canonical)
                _copy_ring_meta_fields(anim_latest, canonical)
                anim_latest["browser_perf_registry_snapshot_in_bundle"] = _ref_present_in_bundle(
                    anim_latest.get("browser_perf_registry_snapshot_ref") or anim_latest.get("browser_perf_registry_snapshot_path"),
                    bundle_basenames,
                )
                anim_latest["browser_perf_previous_snapshot_in_bundle"] = _ref_present_in_bundle(
                    anim_latest.get("browser_perf_previous_snapshot_ref") or anim_latest.get("browser_perf_previous_snapshot_path"),
                    bundle_basenames,
                )
                anim_latest["browser_perf_contract_in_bundle"] = _ref_present_in_bundle(
                    anim_latest.get("browser_perf_contract_ref") or anim_latest.get("browser_perf_contract_path"),
                    bundle_basenames,
                )
                anim_latest["browser_perf_evidence_report_in_bundle"] = _ref_present_in_bundle(
                    anim_latest.get("browser_perf_evidence_report_ref") or anim_latest.get("browser_perf_evidence_report_path"),
                    bundle_basenames,
                )
                anim_latest["browser_perf_comparison_report_in_bundle"] = _ref_present_in_bundle(
                    anim_latest.get("browser_perf_comparison_report_ref") or anim_latest.get("browser_perf_comparison_report_path"),
                    bundle_basenames,
                )
                anim_latest["browser_perf_trace_in_bundle"] = _ref_present_in_bundle(
                    anim_latest.get("browser_perf_trace_ref") or anim_latest.get("browser_perf_trace_path"),
                    bundle_basenames,
                )

            issues: List[str] = [str(x).strip() for x in (canonical.get("issues") or []) if str(x).strip()]

            for label, ref_key, path_key, exists_key, in_bundle_key in (
                (
                    "browser_perf_registry_snapshot",
                    "browser_perf_registry_snapshot_ref",
                    "browser_perf_registry_snapshot_path",
                    "browser_perf_registry_snapshot_exists",
                    "browser_perf_registry_snapshot_in_bundle",
                ),
                (
                    "browser_perf_contract",
                    "browser_perf_contract_ref",
                    "browser_perf_contract_path",
                    "browser_perf_contract_exists",
                    "browser_perf_contract_in_bundle",
                ),
                (
                    "browser_perf_evidence_report",
                    "browser_perf_evidence_report_ref",
                    "browser_perf_evidence_report_path",
                    "browser_perf_evidence_report_exists",
                    "browser_perf_evidence_report_in_bundle",
                ),
                (
                    "browser_perf_comparison_report",
                    "browser_perf_comparison_report_ref",
                    "browser_perf_comparison_report_path",
                    "browser_perf_comparison_report_exists",
                    "browser_perf_comparison_report_in_bundle",
                ),
            ):
                ref_text = str(anim_latest.get(ref_key) or anim_latest.get(path_key) or "").strip()
                should_exist = anim_latest.get(exists_key)
                in_bundle = anim_latest.get(in_bundle_key)
                if ref_text and should_exist and in_bundle is False:
                    msg = f"{label} referenced by anim_latest diagnostics but missing in bundle: {Path(ref_text).name}"
                    warnings.append(msg)
                    issues.append(msg)

            token_values = {
                src: str(state.get("visual_cache_token") or "")
                for src, state in source_states.items()
                if isinstance(state, dict) and str(state.get("visual_cache_token") or "")
            }
            if len(set(token_values.values())) > 1:
                parts = ", ".join(f"{src}={tok}" for src, tok in token_values.items())
                msg = f"anim_latest visual_cache_token mismatch between sources: {parts}"
                warnings.append(msg)
                issues.append(msg)
                anim_latest["pointer_sync_ok"] = False
            elif len(token_values) >= 2:
                anim_latest["pointer_sync_ok"] = True

            reload_values = {
                src: list(state.get("visual_reload_inputs") or [])
                for src, state in source_states.items()
                if isinstance(state, dict) and list(state.get("visual_reload_inputs") or [])
            }
            reload_sets = {tuple(v) for v in reload_values.values()}
            if len(reload_sets) > 1:
                parts = ", ".join(f"{src}={vals}" for src, vals in reload_values.items())
                msg = f"anim_latest visual_reload_inputs mismatch between sources: {parts}"
                warnings.append(msg)
                issues.append(msg)
                anim_latest["reload_inputs_sync_ok"] = False
                if anim_latest["pointer_sync_ok"] is None:
                    anim_latest["pointer_sync_ok"] = False
            elif len(reload_values) >= 2:
                anim_latest["reload_inputs_sync_ok"] = True

            npz_values = {
                src: str(state.get("npz_path") or "")
                for src, state in source_states.items()
                if isinstance(state, dict) and str(state.get("npz_path") or "")
            }
            if len(set(npz_values.values())) > 1:
                parts = ", ".join(f"{src}={path}" for src, path in npz_values.items())
                msg = f"anim_latest npz_path mismatch between sources: {parts}"
                warnings.append(msg)
                issues.append(msg)
                anim_latest["npz_path_sync_ok"] = False
            elif len(npz_values) >= 2:
                anim_latest["npz_path_sync_ok"] = True

            if anim_latest["available"] and not anim_latest["visual_cache_token"]:
                msg = "anim_latest is marked available but visual_cache_token is empty"
                warnings.append(msg)
                issues.append(msg)
            if anim_latest["available"] and not anim_latest["npz_path"]:
                msg = "anim_latest is marked available but npz_path is empty"
                warnings.append(msg)
                issues.append(msg)
            if anim_latest["available"] and not anim_latest["visual_reload_inputs"]:
                msg = "anim_latest is marked available but visual_reload_inputs are empty"
                warnings.append(msg)
                issues.append(msg)
            if anim_latest["available"] and anim_latest.get("usable_from_bundle") is False:
                msg = "anim_latest diagnostics exist but are not reproducible from this bundle"
                warnings.append(msg)
                issues.append(msg)

            anim_latest["issues"] = list(dict.fromkeys(issues))

            # validate manifest integrity
            checked = 0
            mismatched = 0
            missing_in_zip = 0
            size_mismatch = 0

            if len(manifest_obj) > int(max_manifest_files):
                warnings.append(
                    f"manifest has too many entries ({len(manifest_obj)}), integrity check truncated to {max_manifest_files}"
                )

            for arcname, info in list(manifest_obj.items())[: int(max_manifest_files)]:
                checked += 1
                if arcname not in name_set:
                    missing_in_zip += 1
                    errors.append(f"manifest entry missing in ZIP: {arcname}")
                    continue

                try:
                    b = z.read(arcname)
                except Exception:
                    errors.append(f"failed to read from ZIP: {arcname}")
                    mismatched += 1
                    continue

                sha = _sha256_bytes(b)
                exp_sha = None
                exp_size = None
                if isinstance(info, dict):
                    exp_sha = info.get("sha256")
                    exp_size = info.get("size_bytes")

                if exp_sha and str(exp_sha) != sha:
                    mismatched += 1
                    errors.append(f"sha256 mismatch: {arcname} expected={exp_sha} got={sha}")
                if exp_size is not None:
                    try:
                        exp_size_i = int(exp_size)
                        if exp_size_i != len(b):
                            size_mismatch += 1
                            errors.append(f"size mismatch: {arcname} expected={exp_size_i} got={len(b)}")
                    except Exception:
                        warnings.append(f"invalid size_bytes for {arcname}: {exp_size}")

            rep["stats"] = {
                "zip_entries": len(names),
                "manifest_entries": len(manifest_obj) if isinstance(manifest_obj, dict) else None,
                "manifest_checked": checked,
                "manifest_missing_in_zip": missing_in_zip,
                "manifest_sha_mismatch": mismatched,
                "manifest_size_mismatch": size_mismatch,
                "duration_s": round(max(0.0, time.time() - t0), 3),
            }

    except zipfile.BadZipFile:
        errors.append("BadZipFile: archive is corrupted or not a zip")
    except Exception as e:
        errors.append(f"Exception while validating zip: {e}")

    if zp.name == "latest_send_bundle.zip":
        latest_evidence_path = zp.parent / EVIDENCE_MANIFEST_SIDECAR_NAME
        if latest_evidence_path.exists():
            latest_evidence_obj = _safe_json_load_file(latest_evidence_path)
            if isinstance(latest_evidence_obj, dict):
                proof = build_latest_integrity_proof(
                    zip_path=zp,
                    latest_zip_path=zp,
                    original_zip_path=latest_evidence_obj.get("zip_path") or zp,
                    latest_sha_path=zp.parent / "latest_send_bundle.sha256",
                    latest_pointer_path=zp.parent / "latest_send_bundle_path.txt",
                    evidence_manifest=latest_evidence_obj,
                    embedded_manifest=rep.get("evidence_manifest") if isinstance(rep.get("evidence_manifest"), dict) else {},
                )
                rep["latest_integrity_proof"] = proof
                if proof.get("final_latest_zip_sha256_matches_actual") is False:
                    msg = (
                        "latest integrity error: latest_evidence_manifest.json final_latest_zip_sha256 "
                        "does not match latest_send_bundle.zip bytes"
                    )
                    if msg not in errors:
                        errors.append(msg)
                if (proof.get("final_latest_sha256_sidecar") or "") and proof.get("latest_sha_sidecar_matches") is False:
                    msg = "latest integrity error: latest_send_bundle.sha256 does not match latest_send_bundle.zip bytes"
                    if msg not in errors:
                        errors.append(msg)
                for item in proof.get("warnings") or []:
                    msg = str(item).strip()
                    if msg and msg not in warnings and not msg.startswith("latest_send_bundle.sha256 mismatch"):
                        warnings.append(msg)
            else:
                warnings.append(f"{EVIDENCE_MANIFEST_SIDECAR_NAME} is not valid JSON")

    rep["errors"] = errors
    rep["warnings"] = warnings
    rep["ok"] = len(errors) == 0
    rep["meta"] = meta_obj
    rep["summary"] = summary_obj
    rep["anim_latest"] = anim_latest
    rep["ui_autosave"] = ui_autosave

    md = _render_md(rep)
    return ValidationResult(ok=rep["ok"], report_json=rep, report_md=md)



def _render_md(rep: Dict[str, Any]) -> str:
    ok = bool(rep.get("ok"))
    stats = rep.get("stats") or {}
    errors = rep.get("errors") or []
    warnings = rep.get("warnings") or []
    release_risks = rep.get("release_risks") or []
    anim = rep.get("anim_latest") or {}
    evidence = rep.get("evidence_manifest") or {}
    engineering = rep.get("engineering_analysis_evidence") or {}
    analysis_handoff = evidence.get("analysis_handoff") or {}
    optimizer_scope = rep.get("optimizer_scope") or {}
    optimizer_scope_gate = rep.get("optimizer_scope_gate") or {}
    ui_autosave = rep.get("ui_autosave") or {}
    latest_proof = rep.get("latest_integrity_proof") or {}

    title = "✅ SEND BUNDLE VALIDATION: OK" if ok else "❌ SEND BUNDLE VALIDATION: FAIL"

    lines = [
        "# " + title,
        "",
        f"- checked_at: `{rep.get('checked_at')}`",
        f"- zip_path: `{rep.get('zip_path')}`",
        f"- release: `{rep.get('release')}`",
        "",
        "## Evidence manifest",
        "",
        f"- present: `{bool(evidence)}`",
        f"- collection_mode: `{evidence.get('collection_mode') or 'n/a'}`",
        f"- finalization_stage: `{evidence.get('finalization_stage') or 'n/a'}`",
        f"- zip_sha256: `{evidence.get('zip_sha256') or 'n/a'}`",
        f"- pb002_missing_required_count: `{evidence.get('pb002_missing_required_count')}`",
        f"- missing_required_count: `{evidence.get('missing_required_count')}`",
        f"- missing_optional_count: `{evidence.get('missing_optional_count')}`",
        f"- analysis_handoff: `{analysis_handoff.get('status') or 'MISSING'}` / context=`{analysis_handoff.get('result_context_state') or 'MISSING'}` / run=`{analysis_handoff.get('run_id') or '-'}`",
        f"- analysis_handoff_mismatches: `{analysis_handoff.get('mismatch_count') or 0}`",
        "",
        "## Latest integrity proof",
        "",
        f"- present: `{bool(latest_proof)}`",
        f"- status: `{latest_proof.get('status') or 'n/a'}`",
        f"- final_latest_zip_sha256: `{latest_proof.get('final_latest_zip_sha256') or 'n/a'}`",
        f"- final_original_zip_sha256: `{latest_proof.get('final_original_zip_sha256') or 'n/a'}`",
        f"- latest_sha_sidecar_matches: `{latest_proof.get('latest_sha_sidecar_matches')}`",
        f"- latest_pointer_matches_original: `{latest_proof.get('latest_pointer_matches_original')}`",
        f"- embedded_manifest_zip_sha256_scope: `{latest_proof.get('embedded_manifest_zip_sha256_scope') or 'n/a'}`",
        f"- embedded_manifest_stage: `{latest_proof.get('embedded_manifest_stage') or 'n/a'}`",
        f"- producer_warning_count: `{latest_proof.get('producer_warning_count')}`",
        f"- warning_only_gaps_present: `{latest_proof.get('warning_only_gaps_present')}`",
        f"- no_release_closure_claim: `{latest_proof.get('no_release_closure_claim')}`",
        "",
        "### Latest integrity warnings",
        "",
        _md_list([str(x) for x in (latest_proof.get('warnings') or [])]),
        "",
        "### Missing evidence warnings",
        "",
        _md_list([str(x) for x in (evidence.get('missing_warnings') or [])]),
        "",
        "## Stats",
        "",
        "```json",
        json.dumps(stats, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Engineering analysis evidence",
        "",
        f"- present: `{bool(engineering)}`",
        f"- status: `{engineering.get('status') or 'MISSING'}`",
        f"- source_path: `{engineering.get('source_path') or '-'}`",
        f"- evidence_manifest_hash: `{engineering.get('evidence_manifest_hash') or '-'}`",
        f"- influence_status: `{engineering.get('influence_status') or '-'}`",
        f"- calibration_status: `{engineering.get('calibration_status') or '-'}`",
        f"- sensitivity_row_count: `{engineering.get('sensitivity_row_count')}`",
        f"- validated_artifacts_status: `{engineering.get('validated_artifacts_status') or '-'}`",
        f"- required_artifact_count: `{engineering.get('required_artifact_count')}`",
        f"- ready_required_artifact_count: `{engineering.get('ready_required_artifact_count')}`",
        f"- missing_required_artifact_count: `{engineering.get('missing_required_artifact_count')}`",
        f"- missing_required_artifacts: `{', '.join(str(x) for x in (engineering.get('missing_required_artifact_keys') or [])) or '-'}`",
        f"- handoff_contract_status: `{dict(engineering.get('handoff_requirements') or {}).get('contract_status') or '-'}`",
        f"- handoff_required_path: `{dict(engineering.get('handoff_requirements') or {}).get('required_contract_path') or '-'}`",
        f"- selected_run_candidate_count: `{engineering.get('selected_run_candidate_count')}`",
        f"- selected_run_ready_candidate_count: `{engineering.get('selected_run_ready_candidate_count')}`",
        f"- selected_run_missing_inputs_candidate_count: `{engineering.get('selected_run_missing_inputs_candidate_count')}`",
        "",
        "## Optimizer scope",
        "",
        f"- available: `{optimizer_scope.get('available')}`",
        f"- release_gate: `{optimizer_scope_gate.get('release_gate') or 'n/a'}`",
        f"- release_gate_reason: `{optimizer_scope_gate.get('release_gate_reason') or 'n/a'}`",
        f"- release_risk: `{optimizer_scope_gate.get('release_risk')}`",
        f"- canonical_source: `{optimizer_scope.get('canonical_source') or '-'}`",
        f"- scope_sync_ok: `{optimizer_scope.get('scope_sync_ok')}`",
        f"- Problem scope: `{optimizer_scope.get('problem_hash_short') or optimizer_scope.get('problem_hash') or '-'}`",
        f"- Hash mode: `{optimizer_scope.get('problem_hash_mode') or '-'}`",
        f"- objective_keys: `{', '.join(str(x) for x in (optimizer_scope.get('objective_keys') or [])) or '-'}`",
        f"- penalty_key: `{optimizer_scope.get('penalty_key') or '-'}`",
        f"- penalty_tol: `{optimizer_scope.get('penalty_tol')}`",
        "",
        "### Optimizer scope issues",
        "",
        _md_list([str(x) for x in (optimizer_scope.get('issues') or [])]),
        "",
        "### Optimizer scope sources",
        "",
        "```json",
        json.dumps(optimizer_scope.get("sources") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Anim latest diagnostics",
        "",
        f"- available: `{anim.get('available')}`",
        f"- visual_cache_token: `{anim.get('visual_cache_token') or '—'}`",
        f"- visual_reload_inputs: `{', '.join(str(x) for x in (anim.get('visual_reload_inputs') or [])) or '—'}`",
        f"- pointer_json: `{anim.get('pointer_json') or '—'}`",
        f"- global_pointer_json: `{anim.get('global_pointer_json') or '—'}`",
        f"- npz_path: `{anim.get('npz_path') or '—'}`",
        f"- updated_utc: `{anim.get('updated_utc') or '—'}`",
        f"- usable_from_bundle: `{anim.get('usable_from_bundle')}`",
        f"- pointer_json_in_bundle: `{anim.get('pointer_json_in_bundle')}`",
        f"- npz_path_in_bundle: `{anim.get('npz_path_in_bundle')}`",
        f"- pointer_sync_ok: `{anim.get('pointer_sync_ok')}`",
        f"- reload_inputs_sync_ok: `{anim.get('reload_inputs_sync_ok')}`",
        f"- npz_path_sync_ok: `{anim.get('npz_path_sync_ok')}`",
        f"- browser_perf_status: `{anim.get('browser_perf_status') or '—'}` / level=`{anim.get('browser_perf_level') or '—'}`",
        f"- browser_perf_artifacts_primary: snapshot=`{anim.get('browser_perf_registry_snapshot_ref') or '—'}` / exists=`{anim.get('browser_perf_registry_snapshot_exists')}` / in_bundle=`{anim.get('browser_perf_registry_snapshot_in_bundle')}` ; contract=`{anim.get('browser_perf_contract_ref') or '—'}` / exists=`{anim.get('browser_perf_contract_exists')}` / in_bundle=`{anim.get('browser_perf_contract_in_bundle')}`",
        f"- browser_perf_artifacts_secondary: evidence=`{anim.get('browser_perf_evidence_report_ref') or '—'}` / exists=`{anim.get('browser_perf_evidence_report_exists')}` / in_bundle=`{anim.get('browser_perf_evidence_report_in_bundle')}` ; comparison=`{anim.get('browser_perf_comparison_report_ref') or '—'}` / exists=`{anim.get('browser_perf_comparison_report_exists')}` / in_bundle=`{anim.get('browser_perf_comparison_report_in_bundle')}` ; trace=`{anim.get('browser_perf_trace_ref') or '—'}` / exists=`{anim.get('browser_perf_trace_exists')}` / in_bundle=`{anim.get('browser_perf_trace_in_bundle')}`",
        f"- browser_perf_evidence_status: `{anim.get('browser_perf_evidence_status') or '—'}` / level=`{anim.get('browser_perf_evidence_level') or '—'}` / bundle_ready=`{anim.get('browser_perf_bundle_ready')}` / snapshot_contract_match=`{anim.get('browser_perf_snapshot_contract_match')}`",
        f"- browser_perf_comparison_status: `{anim.get('browser_perf_comparison_status') or '—'}` / level=`{anim.get('browser_perf_comparison_level') or '—'}` / ready=`{anim.get('browser_perf_comparison_ready')}` / changed=`{anim.get('browser_perf_comparison_changed')}`",
        f"- browser_perf_comparison_delta: wakeups=`{anim.get('browser_perf_comparison_delta_total_wakeups')}` / dup=`{anim.get('browser_perf_comparison_delta_total_duplicate_guard_hits')}` / render=`{anim.get('browser_perf_comparison_delta_total_render_count')}` / max_idle_poll_ms=`{anim.get('browser_perf_comparison_delta_max_idle_poll_ms')}`",
        "",
        "### Anim latest issues",
        "",
        _md_list([str(x) for x in (anim.get('issues') or [])]),
        "",
        "### Anim latest sources",
        "",
        "```json",
        json.dumps(anim.get("sources") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## UI autosave state",
        "",
        f"- persistent_state_json_present: `{ui_autosave.get('persistent_state_json_present')}`",
        f"- workspace_ui_state_json_present: `{ui_autosave.get('workspace_ui_state_json_present')}`",
        f"- persistent_state_json_files: `{', '.join(ui_autosave.get('persistent_state_json_files') or []) or '—'}`",
        f"- workspace_ui_state_json_files: `{', '.join(ui_autosave.get('workspace_ui_state_json_files') or []) or '—'}`",
        f"- persistent_state_marker_files: `{', '.join(ui_autosave.get('persistent_state_marker_files') or []) or '—'}`",
        f"- workspace_ui_state_marker_files: `{', '.join(ui_autosave.get('workspace_ui_state_marker_files') or []) or '—'}`",
        "",
        "### UI autosave issues",
        "",
        _md_list([str(x) for x in (ui_autosave.get('issues') or [])]),
        "",
        "## Errors",
        "",
        _md_list([str(x) for x in errors]),
        "",
        "## Release risks",
        "",
        _md_list([str(x) for x in release_risks]),
        "",
        "## Warnings",
        "",
        _md_list([str(x) for x in warnings]),
        "",
        "## Notes",
        "",
        "- Manifest integrity is checked by sha256/size of decompressed bytes for files listed in bundle/manifest.json.",
        "- Files written via z.writestr (meta/triage/etc) are checked by presence and JSON parse (when applicable).",
        "- anim_latest diagnostics are compared across triage sidecar, local pointer and global pointer when these sources are present.",
        "- optimizer scope is compared across triage/health/export surfaces when scope artifacts are present in the bundle.",
    ]
    return "\n".join(lines) + "\n"



def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a SEND bundle zip and produce a report")
    ap.add_argument("--zip", required=True, help="Path to send bundle zip")
    ap.add_argument("--out_dir", default=None, help="Write reports to this directory (optional)")
    ap.add_argument("--print_summary", action="store_true", help="Print OK/FAIL + counts")
    ns = ap.parse_args()

    res = validate_send_bundle(Path(ns.zip))

    if ns.out_dir:
        out = Path(ns.out_dir).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        (out / "send_bundle_validation_report.json").write_text(
            json.dumps(res.report_json, ensure_ascii=False, indent=2), encoding="utf-8", errors="replace"
        )
        (out / "send_bundle_validation_report.md").write_text(res.report_md, encoding="utf-8", errors="replace")

    if ns.print_summary:
        st = res.report_json.get("stats") or {}
        print(
            ("OK" if res.ok else "FAIL"),
            "errors=", len(res.report_json.get("errors") or []),
            "warnings=", len(res.report_json.get("warnings") or []),
            "zip_entries=", st.get("zip_entries"),
            "manifest_checked=", st.get("manifest_checked"),
        )

    return 0 if res.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
