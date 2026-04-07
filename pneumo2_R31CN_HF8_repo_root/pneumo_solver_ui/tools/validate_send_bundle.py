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


try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


ANIM_DIAG_JSON = "triage/latest_anim_pointer_diagnostics.json"
ANIM_DIAG_MD = "triage/latest_anim_pointer_diagnostics.md"
ANIM_LOCAL_POINTER = "workspace/exports/anim_latest.json"
ANIM_LOCAL_NPZ = "workspace/exports/anim_latest.npz"
ANIM_GLOBAL_POINTER = "workspace/_pointers/anim_latest.json"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _safe_json_load_bytes(b: bytes) -> Any:
    try:
        return json.loads(b.decode("utf-8", errors="replace"))
    except Exception:
        return None


def _md_list(items: List[str]) -> str:
    if not items:
        return "- (нет)"
    return "\n".join([f"- {x}" for x in items])


def _normalize_reload_inputs(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        out: List[str] = []
        for x in value:
            sx = str(x).strip()
            if sx:
                out.append(sx)
        return out
    sx = str(value).strip()
    return [sx] if sx else []





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


def _basename_or_empty(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return Path(str(value)).name
    except Exception:
        return ""


def _annotate_anim_source_for_bundle(state: Optional[Dict[str, Any]], *, name_set: set[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(state, dict):
        return None
    out = dict(state)
    pointer_json = str(out.get("pointer_json") or "")
    npz_path = str(out.get("npz_path") or "")
    pointer_in_bundle = bool(pointer_json and ANIM_LOCAL_POINTER in name_set and _basename_or_empty(pointer_json) == Path(ANIM_LOCAL_POINTER).name)
    npz_in_bundle = bool(npz_path and ANIM_LOCAL_NPZ in name_set and _basename_or_empty(npz_path) == Path(ANIM_LOCAL_NPZ).name)
    out["pointer_json_in_bundle"] = pointer_in_bundle if pointer_json else None
    out["npz_path_in_bundle"] = npz_in_bundle if npz_path else None
    out["usable_from_bundle"] = bool(out.get("visual_cache_token") and npz_in_bundle)
    issues = [str(x) for x in (out.get("issues") or []) if str(x).strip()]
    src = str(out.get("source") or "source")
    if pointer_json and not pointer_in_bundle:
        issues.append(f"anim_latest {src} pointer_json is external / not mirrored in bundle: {pointer_json}")
    if npz_path and not npz_in_bundle:
        issues.append(f"anim_latest {src} npz_path is external / not mirrored in bundle: {npz_path}")
    if (out.get("available") or out.get("visual_cache_token")) and not out["usable_from_bundle"]:
        issues.append(f"anim_latest {src} is not usable from this bundle")
    out["issues"] = list(dict.fromkeys(issues))
    return out


def _extract_anim_snapshot(obj: Any, *, source: str) -> Optional[Dict[str, Any]]:
    if not isinstance(obj, dict):
        return None

    available = bool(
        obj.get("anim_latest_available")
        if "anim_latest_available" in obj
        else (
            obj.get("pointer_json")
            or obj.get("anim_latest_json")
            or obj.get("npz_path")
            or obj.get("anim_latest_npz")
            or obj.get("kind") == "anim_latest"
        )
    )

    meta_obj = obj.get("anim_latest_meta") if isinstance(obj.get("anim_latest_meta"), dict) else obj.get("meta")
    deps_obj = (
        obj.get("anim_latest_visual_cache_dependencies")
        if isinstance(obj.get("anim_latest_visual_cache_dependencies"), dict)
        else obj.get("visual_cache_dependencies")
    )

    return {
        "source": str(source),
        "available": available,
        "pointer_json": str(obj.get("anim_latest_pointer_json") or obj.get("pointer_json") or obj.get("anim_latest_json") or ""),
        "global_pointer_json": str(obj.get("anim_latest_global_pointer_json") or obj.get("global_pointer_json") or ""),
        "npz_path": str(obj.get("anim_latest_npz_path") or obj.get("npz_path") or obj.get("anim_latest_npz") or ""),
        "visual_cache_token": str(obj.get("anim_latest_visual_cache_token") or obj.get("visual_cache_token") or ""),
        "visual_reload_inputs": _normalize_reload_inputs(
            obj.get("anim_latest_visual_reload_inputs") if "anim_latest_visual_reload_inputs" in obj else obj.get("visual_reload_inputs")
        ),
        "visual_cache_dependencies": dict(deps_obj or {}),
        "updated_utc": str(obj.get("anim_latest_updated_utc") or obj.get("updated_utc") or obj.get("updated_at") or ""),
        "meta": dict(meta_obj or {}) if isinstance(meta_obj, dict) else {},
        "pointer_json_in_bundle": obj.get("pointer_json_in_bundle"),
        "npz_path_in_bundle": obj.get("npz_path_in_bundle"),
        "usable_from_bundle": obj.get("usable_from_bundle"),
        "issues": list(obj.get("issues") or []) if isinstance(obj.get("issues"), list) else [],
    }


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
        "stats": {},
        "anim_latest": {},
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
        "issues": [],
        "sources": {},
    }
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

            # anim_latest diagnostics / pointer consistency (best effort, warning-only)
            anim_latest["diagnostics_json_present"] = ANIM_DIAG_JSON in name_set
            anim_latest["diagnostics_md_present"] = ANIM_DIAG_MD in name_set
            anim_latest["local_pointer_present"] = ANIM_LOCAL_POINTER in name_set
            anim_latest["global_pointer_present"] = ANIM_GLOBAL_POINTER in name_set

            if not anim_latest["diagnostics_json_present"]:
                warnings.append(f"Missing {ANIM_DIAG_JSON} (anim_latest diagnostics sidecar)")
            if not anim_latest["diagnostics_md_present"]:
                warnings.append(f"Missing {ANIM_DIAG_MD} (anim_latest diagnostics sidecar)")
            if not anim_latest["global_pointer_present"]:
                warnings.append(f"Missing {ANIM_GLOBAL_POINTER} (global anim_latest pointer)")
            if not anim_latest["local_pointer_present"]:
                warnings.append(f"Missing {ANIM_LOCAL_POINTER} (local anim_latest pointer)")

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
                "diagnostics": _annotate_anim_source_for_bundle(
                    _extract_anim_snapshot(diag_obj, source="diagnostics") if isinstance(diag_obj, dict) else None,
                    name_set=name_set,
                ),
                "local_pointer": _annotate_anim_source_for_bundle(
                    _extract_anim_snapshot(local_obj, source="local_pointer") if isinstance(local_obj, dict) else None,
                    name_set=name_set,
                ),
                "global_pointer": _annotate_anim_source_for_bundle(
                    _extract_anim_snapshot(global_obj, source="global_pointer") if isinstance(global_obj, dict) else None,
                    name_set=name_set,
                ),
            }
            anim_latest["sources"] = {k: v for k, v in source_states.items() if isinstance(v, dict)}

            canonical: Dict[str, Any] = {}
            for key in ("diagnostics", "local_pointer", "global_pointer"):
                state = source_states.get(key)
                if isinstance(state, dict) and state.get("usable_from_bundle") is True:
                    canonical = state
                    break
            if not canonical:
                for key in ("diagnostics", "local_pointer", "global_pointer"):
                    state = source_states.get(key)
                    if isinstance(state, dict) and (state.get("visual_cache_token") or state.get("available")):
                        canonical = state
                        break
            if not canonical:
                for key in ("diagnostics", "local_pointer", "global_pointer"):
                    state = source_states.get(key)
                    if isinstance(state, dict):
                        canonical = state
                        break

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

            issues: List[str] = []
            for state in source_states.values():
                if isinstance(state, dict):
                    for msg in list(state.get("issues") or []):
                        smsg = str(msg).strip()
                        if smsg and smsg not in issues:
                            issues.append(smsg)

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
    anim = rep.get("anim_latest") or {}
    ui_autosave = rep.get("ui_autosave") or {}

    title = "✅ SEND BUNDLE VALIDATION: OK" if ok else "❌ SEND BUNDLE VALIDATION: FAIL"

    lines = [
        "# " + title,
        "",
        f"- checked_at: `{rep.get('checked_at')}`",
        f"- zip_path: `{rep.get('zip_path')}`",
        f"- release: `{rep.get('release')}`",
        "",
        "## Stats",
        "",
        "```json",
        json.dumps(stats, ensure_ascii=False, indent=2),
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
        "## Warnings",
        "",
        _md_list([str(x) for x in warnings]),
        "",
        "## Notes",
        "",
        "- Manifest integrity is checked by sha256/size of decompressed bytes for files listed in bundle/manifest.json.",
        "- Files written via z.writestr (meta/triage/etc) are checked by presence and JSON parse (when applicable).",
        "- anim_latest diagnostics are compared across triage sidecar, local pointer and global pointer when these sources are present.",
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
