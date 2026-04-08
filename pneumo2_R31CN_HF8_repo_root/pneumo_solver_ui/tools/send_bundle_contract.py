from __future__ import annotations

"""Shared send-bundle contract helpers.

This module keeps anim_latest contract constants and normalization logic in one
place so validation, health-report and dashboard surfaces interpret the same
bundle payload identically.
"""

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


ANIM_DIAG_JSON = "triage/latest_anim_pointer_diagnostics.json"
ANIM_DIAG_MD = "triage/latest_anim_pointer_diagnostics.md"
ANIM_DIAG_SIDECAR_JSON = Path(ANIM_DIAG_JSON).name
ANIM_DIAG_SIDECAR_MD = Path(ANIM_DIAG_MD).name
ANIM_LOCAL_POINTER = "workspace/exports/anim_latest.json"
ANIM_LOCAL_NPZ = "workspace/exports/anim_latest.npz"
ANIM_GLOBAL_POINTER = "workspace/_pointers/anim_latest.json"

ANIM_LATEST_REGISTRY_EVENT_FIELDS = (
    "anim_latest_available",
    "anim_latest_global_pointer_json",
    "anim_latest_pointer_json",
    "anim_latest_npz_path",
    "anim_latest_visual_cache_token",
    "anim_latest_visual_reload_inputs",
    "anim_latest_visual_cache_dependencies",
    "anim_latest_updated_utc",
    "anim_latest_pointer_json_exists",
    "anim_latest_npz_exists",
    "anim_latest_pointer_json_in_workspace",
    "anim_latest_npz_in_workspace",
    "anim_latest_usable",
    "anim_latest_issues",
)

ANIM_LATEST_INDEX_FIELDS = (
    "anim_latest_available",
    "anim_latest_global_pointer_json",
    "anim_latest_pointer_json",
    "anim_latest_npz_path",
    "anim_latest_visual_cache_token",
    "anim_latest_visual_reload_inputs",
    "anim_latest_updated_utc",
    "anim_latest_pointer_json_exists",
    "anim_latest_npz_exists",
    "anim_latest_pointer_json_in_workspace",
    "anim_latest_npz_in_workspace",
    "anim_latest_usable",
    "anim_latest_issues",
)


def normalize_reload_inputs(value: Any) -> List[str]:
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


def pick_anim_latest_fields(
    source: Mapping[str, Any],
    *,
    fields: Sequence[str] = ANIM_LATEST_REGISTRY_EVENT_FIELDS,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in fields:
        if key not in source:
            continue
        value = source.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            out[key] = dict(value)
        elif isinstance(value, list):
            out[key] = list(value)
        else:
            out[key] = value
    return out


def _basename_or_empty(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return Path(str(value)).name
    except Exception:
        return ""


def extract_anim_snapshot(obj: Any, *, source: str) -> Optional[Dict[str, Any]]:
    if not isinstance(obj, dict):
        return None

    available = bool(
        obj.get("anim_latest_available")
        if "anim_latest_available" in obj
        else (
            obj.get("available")
            or obj.get("pointer_json")
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

    issues_src = obj.get("issues") or obj.get("anim_latest_issues") or []
    issues = list(issues_src) if isinstance(issues_src, list) else []

    return {
        "source": str(source),
        "available": available,
        "pointer_json": str(obj.get("anim_latest_pointer_json") or obj.get("pointer_json") or obj.get("anim_latest_json") or ""),
        "global_pointer_json": str(obj.get("anim_latest_global_pointer_json") or obj.get("global_pointer_json") or ""),
        "npz_path": str(obj.get("anim_latest_npz_path") or obj.get("npz_path") or obj.get("anim_latest_npz") or ""),
        "visual_cache_token": str(obj.get("anim_latest_visual_cache_token") or obj.get("visual_cache_token") or ""),
        "visual_reload_inputs": normalize_reload_inputs(
            obj.get("anim_latest_visual_reload_inputs") if "anim_latest_visual_reload_inputs" in obj else obj.get("visual_reload_inputs")
        ),
        "visual_cache_dependencies": dict(deps_obj or {}) if isinstance(deps_obj, dict) else {},
        "updated_utc": str(obj.get("anim_latest_updated_utc") or obj.get("updated_utc") or obj.get("updated_at") or ""),
        "meta": dict(meta_obj or {}) if isinstance(meta_obj, dict) else {},
        "pointer_sync_ok": obj.get("pointer_sync_ok"),
        "reload_inputs_sync_ok": obj.get("reload_inputs_sync_ok"),
        "npz_path_sync_ok": obj.get("npz_path_sync_ok"),
        "usable_from_bundle": obj.get("usable_from_bundle") if "usable_from_bundle" in obj else obj.get("anim_latest_usable"),
        "pointer_json_in_bundle": obj.get("pointer_json_in_bundle"),
        "npz_path_in_bundle": obj.get("npz_path_in_bundle"),
        "issues": issues,
    }


def annotate_anim_source_for_bundle(state: Optional[Dict[str, Any]], *, name_set: set[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(state, dict):
        return None
    out = dict(state)
    pointer_json = str(out.get("pointer_json") or "")
    npz_path = str(out.get("npz_path") or "")
    pointer_in_bundle = bool(
        pointer_json
        and ANIM_LOCAL_POINTER in name_set
        and _basename_or_empty(pointer_json) == Path(ANIM_LOCAL_POINTER).name
    )
    npz_in_bundle = bool(
        npz_path
        and ANIM_LOCAL_NPZ in name_set
        and _basename_or_empty(npz_path) == Path(ANIM_LOCAL_NPZ).name
    )
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


def choose_anim_snapshot(
    sources: Mapping[str, Dict[str, Any]],
    *,
    preferred_order: Sequence[str],
) -> Dict[str, Any]:
    if not sources:
        return {
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
            "source": "",
            "sources_present": [],
            "sources": {},
        }

    ordered_keys = list(preferred_order) + [k for k in sources.keys() if k not in preferred_order]
    chosen: Dict[str, Any] | None = None
    for key in ordered_keys:
        snap = sources.get(key)
        if isinstance(snap, dict) and (snap.get("visual_cache_token") or snap.get("available")):
            chosen = dict(snap)
            chosen["source"] = key
            break
    if chosen is None:
        first_key = next(iter(sources.keys()))
        chosen = dict(sources[first_key])
        chosen["source"] = first_key

    chosen["sources_present"] = list(sources.keys())
    chosen["sources"] = {k: dict(v) for k, v in sources.items()}

    issues: List[str] = []
    token_map = {k: str(v.get("visual_cache_token") or "") for k, v in sources.items() if str(v.get("visual_cache_token") or "")}
    reload_map = {
        k: tuple(normalize_reload_inputs(v.get("visual_reload_inputs")))
        for k, v in sources.items()
        if normalize_reload_inputs(v.get("visual_reload_inputs"))
    }
    npz_map = {k: str(v.get("npz_path") or "") for k, v in sources.items() if str(v.get("npz_path") or "")}

    if len(set(token_map.values())) > 1:
        parts = ", ".join(f"{k}={v}" for k, v in token_map.items())
        issues.append(f"anim_latest visual_cache_token mismatch between sources: {parts}")
    if len(set(reload_map.values())) > 1:
        parts = ", ".join(f"{k}={list(v)}" for k, v in reload_map.items())
        issues.append(f"anim_latest visual_reload_inputs mismatch between sources: {parts}")
    if len(set(npz_map.values())) > 1:
        parts = ", ".join(f"{k}={v}" for k, v in npz_map.items())
        issues.append(f"anim_latest npz_path mismatch between sources: {parts}")

    for snap in sources.values():
        for msg in list(snap.get("issues") or []):
            smsg = str(msg).strip()
            if smsg and smsg not in issues:
                issues.append(smsg)

    if chosen.get("available") and not str(chosen.get("visual_cache_token") or ""):
        issues.append("anim_latest is marked available but visual_cache_token is empty")
    if chosen.get("available") and chosen.get("usable_from_bundle") is False:
        issues.append("anim_latest diagnostics exist but are not reproducible from this bundle")

    chosen["issues"] = list(dict.fromkeys(issues))
    if chosen.get("pointer_sync_ok") is None:
        chosen["pointer_sync_ok"] = None if len(token_map) <= 1 else (len(set(token_map.values())) == 1)
    if chosen.get("reload_inputs_sync_ok") is None:
        chosen["reload_inputs_sync_ok"] = None if len(reload_map) <= 1 else (len(set(reload_map.values())) == 1)
    if chosen.get("npz_path_sync_ok") is None:
        chosen["npz_path_sync_ok"] = None if len(npz_map) <= 1 else (len(set(npz_map.values())) == 1)
    return chosen


def normalize_anim_dashboard_obj(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        return {}
    out = dict(obj)
    snap = extract_anim_snapshot(obj, source="dashboard")
    if isinstance(snap, dict):
        out.update(snap)
    if "sources" not in out and isinstance(obj.get("sources"), dict):
        out["sources"] = dict(obj.get("sources") or {})
    return out


def anim_has_signal(anim: Any) -> bool:
    if not isinstance(anim, dict):
        return False
    norm = normalize_anim_dashboard_obj(anim)
    return bool(
        norm.get("visual_cache_token")
        or norm.get("available")
        or norm.get("npz_path")
    )


def render_anim_latest_md(anim: Any) -> str:
    if not isinstance(anim, dict):
        return "(anim_latest diagnostics not found)"
    norm = normalize_anim_dashboard_obj(anim)
    lines = [
        "# Anim latest diagnostics",
        "",
        f"- available: {bool(norm.get('available'))}",
        f"- visual_cache_token: {norm.get('visual_cache_token') or '—'}",
        f"- visual_reload_inputs: {', '.join(str(x) for x in (norm.get('visual_reload_inputs') or [])) or '—'}",
        f"- pointer_json: {norm.get('pointer_json') or '—'}",
        f"- global_pointer_json: {norm.get('global_pointer_json') or '—'}",
        f"- npz_path: {norm.get('npz_path') or '—'}",
        f"- updated_utc: {norm.get('updated_utc') or '—'}",
    ]
    if norm.get("usable_from_bundle") is not None:
        lines.append(f"- usable_from_bundle: {norm.get('usable_from_bundle')}")
    if norm.get("pointer_json_in_bundle") is not None:
        lines.append(f"- pointer_json_in_bundle: {norm.get('pointer_json_in_bundle')}")
    if norm.get("npz_path_in_bundle") is not None:
        lines.append(f"- npz_path_in_bundle: {norm.get('npz_path_in_bundle')}")
    if norm.get("pointer_sync_ok") is not None:
        lines.append(f"- pointer_sync_ok: {norm.get('pointer_sync_ok')}")
    if norm.get("reload_inputs_sync_ok") is not None:
        lines.append(f"- reload_inputs_sync_ok: {norm.get('reload_inputs_sync_ok')}")
    if norm.get("npz_path_sync_ok") is not None:
        lines.append(f"- npz_path_sync_ok: {norm.get('npz_path_sync_ok')}")
    issues = [str(x) for x in (norm.get("issues") or []) if str(x).strip()]
    if issues:
        lines.extend(["", "## Issues", *[f"- {x}" for x in issues]])
    return "\n".join(lines).rstrip() + "\n"
