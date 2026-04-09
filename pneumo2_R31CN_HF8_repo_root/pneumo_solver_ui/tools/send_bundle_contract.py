from __future__ import annotations

"""Shared send-bundle contract helpers.

This module keeps anim_latest contract constants and normalization logic in one
place so validation, health-report and dashboard surfaces interpret the same
bundle payload identically.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


ANIM_DIAG_JSON = "triage/latest_anim_pointer_diagnostics.json"
ANIM_DIAG_MD = "triage/latest_anim_pointer_diagnostics.md"
ANIM_DIAG_SIDECAR_JSON = Path(ANIM_DIAG_JSON).name
ANIM_DIAG_SIDECAR_MD = Path(ANIM_DIAG_MD).name
ANIM_LOCAL_POINTER = "workspace/exports/anim_latest.json"
ANIM_LOCAL_NPZ = "workspace/exports/anim_latest.npz"
ANIM_GLOBAL_POINTER = "workspace/_pointers/anim_latest.json"
LATEST_SEND_BUNDLE_VALIDATION_JSON = "latest_send_bundle_validation.json"
BROWSER_PERF_FLAT_FIELDS = (
    "browser_perf_registry_snapshot_ref",
    "browser_perf_registry_snapshot_path",
    "browser_perf_registry_snapshot_exists",
    "browser_perf_registry_snapshot_in_bundle",
    "browser_perf_previous_snapshot_ref",
    "browser_perf_previous_snapshot_path",
    "browser_perf_previous_snapshot_exists",
    "browser_perf_previous_snapshot_in_bundle",
    "browser_perf_contract_ref",
    "browser_perf_contract_path",
    "browser_perf_contract_exists",
    "browser_perf_contract_in_bundle",
    "browser_perf_evidence_report_ref",
    "browser_perf_evidence_report_path",
    "browser_perf_evidence_report_exists",
    "browser_perf_evidence_report_in_bundle",
    "browser_perf_comparison_report_ref",
    "browser_perf_comparison_report_path",
    "browser_perf_comparison_report_exists",
    "browser_perf_comparison_report_in_bundle",
    "browser_perf_trace_ref",
    "browser_perf_trace_path",
    "browser_perf_trace_exists",
    "browser_perf_trace_in_bundle",
    "browser_perf_status",
    "browser_perf_level",
    "browser_perf_message",
    "browser_perf_evidence_status",
    "browser_perf_evidence_level",
    "browser_perf_evidence_message",
    "browser_perf_bundle_ready",
    "browser_perf_snapshot_contract_match",
    "browser_perf_comparison_status",
    "browser_perf_comparison_level",
    "browser_perf_comparison_message",
    "browser_perf_comparison_ready",
    "browser_perf_comparison_changed",
    "browser_perf_comparison_reference_updated_utc",
    "browser_perf_comparison_current_updated_utc",
    "browser_perf_comparison_reference_trace_exists",
    "browser_perf_comparison_current_trace_exists",
    "browser_perf_comparison_delta_total_wakeups",
    "browser_perf_comparison_delta_total_duplicate_guard_hits",
    "browser_perf_comparison_delta_total_render_count",
    "browser_perf_comparison_delta_max_idle_poll_ms",
    "browser_perf_component_count",
    "browser_perf_total_wakeups",
    "browser_perf_total_duplicate_guard_hits",
    "browser_perf_max_idle_poll_ms",
)

MNEMO_EVENT_FLAT_FIELDS = (
    "anim_latest_mnemo_event_log_ref",
    "anim_latest_mnemo_event_log_path",
    "anim_latest_mnemo_event_log_exists",
    "anim_latest_mnemo_event_log_schema_version",
    "anim_latest_mnemo_event_log_updated_utc",
    "anim_latest_mnemo_event_log_current_mode",
    "anim_latest_mnemo_event_log_event_count",
    "anim_latest_mnemo_event_log_active_latch_count",
    "anim_latest_mnemo_event_log_acknowledged_latch_count",
    "anim_latest_mnemo_event_log_recent_titles",
)

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
    "anim_latest_mnemo_event_log_ref",
    "anim_latest_mnemo_event_log_path",
    "anim_latest_mnemo_event_log_exists",
    "anim_latest_mnemo_event_log_schema_version",
    "anim_latest_mnemo_event_log_updated_utc",
    "anim_latest_mnemo_event_log_current_mode",
    "anim_latest_mnemo_event_log_event_count",
    "anim_latest_mnemo_event_log_active_latch_count",
    "anim_latest_mnemo_event_log_acknowledged_latch_count",
    "anim_latest_mnemo_event_log_recent_titles",
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
    "anim_latest_mnemo_event_log_ref",
    "anim_latest_mnemo_event_log_exists",
    "anim_latest_mnemo_event_log_schema_version",
    "anim_latest_mnemo_event_log_updated_utc",
    "anim_latest_mnemo_event_log_current_mode",
    "anim_latest_mnemo_event_log_event_count",
    "anim_latest_mnemo_event_log_active_latch_count",
    "anim_latest_mnemo_event_log_acknowledged_latch_count",
    "anim_latest_mnemo_event_log_recent_titles",
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


def _int_or_none(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


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

    out = {
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
    for key in BROWSER_PERF_FLAT_FIELDS + MNEMO_EVENT_FLAT_FIELDS:
        if key in obj:
            value = obj.get(key)
            if isinstance(value, dict):
                out[key] = dict(value)
            elif isinstance(value, list):
                out[key] = list(value)
            else:
                out[key] = value
    return out


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

    for key in BROWSER_PERF_FLAT_FIELDS + MNEMO_EVENT_FLAT_FIELDS:
        cur = chosen.get(key)
        if key in chosen and cur not in (None, "", [], {}):
            continue
        for src_key in ordered_keys:
            snap = sources.get(src_key)
            if not isinstance(snap, dict):
                continue
            value = snap.get(key)
            if value in (None, "", [], {}):
                continue
            if isinstance(value, dict):
                chosen[key] = dict(value)
            elif isinstance(value, list):
                chosen[key] = list(value)
            else:
                chosen[key] = value
            break

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


def summarize_mnemo_event_log(anim: Any) -> Dict[str, Any]:
    norm = normalize_anim_dashboard_obj(anim)
    if not norm:
        return {
            "exists": None,
            "ref": "",
            "path": "",
            "schema_version": "",
            "updated_utc": "",
            "current_mode": "",
            "event_count": None,
            "active_latch_count": None,
            "acknowledged_latch_count": None,
            "recent_titles": [],
            "severity": "missing",
            "headline": "Desktop Mnemo event-log not available",
            "red_flags": [],
        }

    exists = norm.get("anim_latest_mnemo_event_log_exists")
    ref = str(norm.get("anim_latest_mnemo_event_log_ref") or "")
    path = str(norm.get("anim_latest_mnemo_event_log_path") or "")
    schema_version = str(norm.get("anim_latest_mnemo_event_log_schema_version") or "")
    updated_utc = str(norm.get("anim_latest_mnemo_event_log_updated_utc") or "")
    current_mode = str(norm.get("anim_latest_mnemo_event_log_current_mode") or "")
    event_count = _int_or_none(norm.get("anim_latest_mnemo_event_log_event_count"))
    active_latch_count = _int_or_none(norm.get("anim_latest_mnemo_event_log_active_latch_count"))
    acknowledged_latch_count = _int_or_none(norm.get("anim_latest_mnemo_event_log_acknowledged_latch_count"))
    recent_titles = [str(x) for x in (norm.get("anim_latest_mnemo_event_log_recent_titles") or []) if str(x).strip()]
    red_flags: List[str] = []

    if (active_latch_count or 0) > 0:
        severity = "critical"
        headline = (
            f"Desktop Mnemo reports {active_latch_count} active latched event(s)"
            + (f" in mode {current_mode}" if current_mode else "")
        )
        red_flags.append(headline)
    elif (acknowledged_latch_count or 0) > 0:
        severity = "warn"
        headline = (
            f"Desktop Mnemo retains {acknowledged_latch_count} acknowledged latch(es)"
            + (f" after mode {current_mode}" if current_mode else "")
        )
    elif recent_titles:
        severity = "warn"
        headline = "Desktop Mnemo recorded recent events"
    elif exists:
        severity = "ok"
        headline = "Desktop Mnemo event-log available"
    else:
        severity = "missing"
        headline = "Desktop Mnemo event-log not available"

    if recent_titles and severity == "critical":
        red_flags.append("Desktop Mnemo recent: " + " | ".join(recent_titles[:3]))

    return {
        "exists": exists,
        "ref": ref,
        "path": path,
        "schema_version": schema_version,
        "updated_utc": updated_utc,
        "current_mode": current_mode,
        "event_count": event_count,
        "active_latch_count": active_latch_count,
        "acknowledged_latch_count": acknowledged_latch_count,
        "recent_titles": recent_titles,
        "severity": severity,
        "headline": headline,
        "red_flags": red_flags,
    }


def build_anim_operator_recommendations(anim: Any) -> List[str]:
    norm = normalize_anim_dashboard_obj(anim)
    if not norm:
        return []

    mnemo = summarize_mnemo_event_log(norm)
    recommendations: List[str] = []
    current_mode = str(mnemo.get("current_mode") or "").strip()
    current_mode_text = f" in mode {current_mode}" if current_mode else ""

    if str(mnemo.get("severity") or "") == "critical":
        recommendations.append(
            f"Open Desktop Mnemo first and inspect active latched events{current_mode_text} before ACK/reset."
        )
    elif str(mnemo.get("severity") or "") == "warn":
        recommendations.append(
            f"Review Desktop Mnemo acknowledged/recent events{current_mode_text} before closing pneumatic triage."
        )
    elif norm.get("available") and mnemo.get("exists") is not True:
        recommendations.append(
            "Generate a Desktop Mnemo event-log from the current anim_latest run so pneumatic history is present in triage."
        )

    perf_evidence_status = str(norm.get("browser_perf_evidence_status") or "").strip()
    perf_evidence_level = str(norm.get("browser_perf_evidence_level") or "").strip()
    perf_bundle_ready = norm.get("browser_perf_bundle_ready")
    if perf_evidence_status and perf_evidence_status != "trace_bundle_ready":
        recommendations.append(
            f"Open browser perf evidence artifacts and refresh the trace; current evidence status is {perf_evidence_status}"
            + (f" ({perf_evidence_level})" if perf_evidence_level else "")
            + f", bundle_ready={perf_bundle_ready}."
        )

    perf_compare_status = str(norm.get("browser_perf_comparison_status") or "").strip()
    perf_compare_level = str(norm.get("browser_perf_comparison_level") or "").strip()
    perf_compare_ready = norm.get("browser_perf_comparison_ready")
    perf_compare_changed = norm.get("browser_perf_comparison_changed")
    if perf_compare_status == "no_reference":
        recommendations.append(
            "Create or refresh a browser perf reference snapshot before marking performance review complete."
        )
    elif (
        perf_compare_status
        and (
            perf_compare_ready is False
            or perf_compare_changed is True
            or perf_compare_level not in ("", "PASS", "OK")
        )
    ):
        recommendations.append(
            f"Review the browser perf comparison report before sign-off; status={perf_compare_status}"
            + (f", level={perf_compare_level}" if perf_compare_level else "")
            + f", ready={perf_compare_ready}, changed={perf_compare_changed}."
        )

    if norm.get("pointer_sync_ok") is False:
        recommendations.append(
            "Re-export anim_latest from the current workspace to resync pointer/token state across diagnostics sources."
        )
    if norm.get("usable_from_bundle") is False:
        recommendations.append(
            "Rebuild the send-bundle after re-export so anim_latest is reproducible directly from the archive."
        )

    deduped: List[str] = []
    for item in recommendations:
        text = str(item).strip()
        if text and text not in deduped:
            deduped.append(text)
    return deduped


def _safe_read_json_dict(path: Path) -> Dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def load_latest_send_bundle_anim_dashboard(out_dir: Path) -> Dict[str, Any]:
    root = Path(out_dir).expanduser()
    sources: Dict[str, Dict[str, Any]] = {}

    diag_obj = _safe_read_json_dict(root / ANIM_DIAG_SIDECAR_JSON)
    if diag_obj:
        diag_norm = normalize_anim_dashboard_obj(diag_obj)
        if diag_norm.get("visual_cache_token") or diag_norm.get("available") or diag_norm.get("npz_path"):
            sources["diagnostics"] = diag_norm

    validation_obj = _safe_read_json_dict(root / LATEST_SEND_BUNDLE_VALIDATION_JSON)
    validation_anim = validation_obj.get("anim_latest")
    if isinstance(validation_anim, dict):
        validation_norm = normalize_anim_dashboard_obj(validation_anim)
        if validation_norm.get("visual_cache_token") or validation_norm.get("available") or validation_norm.get("npz_path") or any(
            validation_norm.get(key) not in (None, "", [], {})
            for key in BROWSER_PERF_FLAT_FIELDS + MNEMO_EVENT_FLAT_FIELDS
        ):
            sources["validation"] = validation_norm

    if not sources:
        return {}
    chosen = choose_anim_snapshot(sources, preferred_order=("diagnostics", "validation"))
    return normalize_anim_dashboard_obj(chosen)


def format_anim_dashboard_brief_lines(anim: Any) -> List[str]:
    norm = normalize_anim_dashboard_obj(anim)
    if not norm:
        return []

    lines: List[str] = []
    token = str(norm.get("visual_cache_token") or "")
    reload_inputs = list(norm.get("visual_reload_inputs") or [])
    perf_evidence_status = str(norm.get("browser_perf_evidence_status") or "")
    perf_evidence_level = str(norm.get("browser_perf_evidence_level") or "")
    perf_compare_status = str(norm.get("browser_perf_comparison_status") or "")
    perf_compare_level = str(norm.get("browser_perf_comparison_level") or "")
    perf_bundle_ready = norm.get("browser_perf_bundle_ready")
    perf_compare_ready = norm.get("browser_perf_comparison_ready")
    mnemo_event_exists = norm.get("anim_latest_mnemo_event_log_exists")
    mnemo_event_total = norm.get("anim_latest_mnemo_event_log_event_count")
    mnemo_event_active = norm.get("anim_latest_mnemo_event_log_active_latch_count")
    mnemo_event_ack = norm.get("anim_latest_mnemo_event_log_acknowledged_latch_count")
    mnemo_event_mode = str(norm.get("anim_latest_mnemo_event_log_current_mode") or "")
    mnemo_event_recent = [str(x) for x in (norm.get("anim_latest_mnemo_event_log_recent_titles") or []) if str(x).strip()]

    if token:
        lines.append(f"Anim latest token: {token}")
    if reload_inputs:
        lines.append("Anim reload inputs: " + ", ".join(str(x) for x in reload_inputs))
    if any(value not in (None, "", []) for value in (mnemo_event_exists, mnemo_event_total, mnemo_event_active, mnemo_event_ack, mnemo_event_mode)):
        lines.append(
            "Desktop Mnemo events: "
            f"exists={mnemo_event_exists}"
            f" / total={mnemo_event_total if mnemo_event_total is not None else '—'}"
            f" / active={mnemo_event_active if mnemo_event_active is not None else '—'}"
            f" / acked={mnemo_event_ack if mnemo_event_ack is not None else '—'}"
            f" / mode={mnemo_event_mode or '—'}"
        )
    if mnemo_event_recent:
        lines.append("Desktop Mnemo recent: " + " | ".join(mnemo_event_recent[:3]))
    if perf_evidence_status or perf_evidence_level:
        lines.append(
            "Browser perf evidence: "
            f"{perf_evidence_status or '—'}"
            f"{' / ' + perf_evidence_level if perf_evidence_level else ''}"
            f" / bundle_ready={perf_bundle_ready}"
        )
    if perf_compare_status or perf_compare_level:
        lines.append(
            "Browser perf comparison: "
            f"{perf_compare_status or '—'}"
            f"{' / ' + perf_compare_level if perf_compare_level else ''}"
            f" / ready={perf_compare_ready}"
        )

    bundle_bits = []
    for label, key in (
        ("snapshot", "browser_perf_registry_snapshot_in_bundle"),
        ("previous", "browser_perf_previous_snapshot_in_bundle"),
        ("contract", "browser_perf_contract_in_bundle"),
        ("evidence", "browser_perf_evidence_report_in_bundle"),
        ("comparison", "browser_perf_comparison_report_in_bundle"),
        ("trace", "browser_perf_trace_in_bundle"),
    ):
        value = norm.get(key)
        if value is not None:
            bundle_bits.append(f"{label}={value}")
    if bundle_bits:
        lines.append("Browser perf bundle artifacts: " + ", ".join(bundle_bits))

    return lines


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
    if any(
        norm.get(key) not in (None, "", [], {})
        for key in (
            "anim_latest_mnemo_event_log_ref",
            "anim_latest_mnemo_event_log_exists",
            "anim_latest_mnemo_event_log_current_mode",
            "anim_latest_mnemo_event_log_event_count",
            "anim_latest_mnemo_event_log_active_latch_count",
            "anim_latest_mnemo_event_log_acknowledged_latch_count",
        )
    ):
        lines.append(
            f"- mnemo_event_log: {norm.get('anim_latest_mnemo_event_log_ref') or '—'} / exists={norm.get('anim_latest_mnemo_event_log_exists')} / schema={norm.get('anim_latest_mnemo_event_log_schema_version') or '—'} / updated_utc={norm.get('anim_latest_mnemo_event_log_updated_utc') or '—'}"
        )
        lines.append(
            f"- mnemo_event_log_state: mode={norm.get('anim_latest_mnemo_event_log_current_mode') or '—'} / total={norm.get('anim_latest_mnemo_event_log_event_count')} / active={norm.get('anim_latest_mnemo_event_log_active_latch_count')} / acked={norm.get('anim_latest_mnemo_event_log_acknowledged_latch_count')}"
        )
        recent_titles = [str(x) for x in (norm.get("anim_latest_mnemo_event_log_recent_titles") or []) if str(x).strip()]
        if recent_titles:
            lines.append(f"- mnemo_event_log_recent: {' | '.join(recent_titles[:3])}")
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
    if norm.get("browser_perf_status") or norm.get("browser_perf_level"):
        lines.append(
            f"- browser_perf_status: {norm.get('browser_perf_status') or '—'} / level={norm.get('browser_perf_level') or '—'}"
        )
    if norm.get("browser_perf_evidence_status") or norm.get("browser_perf_evidence_level"):
        lines.append(
            f"- browser_perf_evidence_status: {norm.get('browser_perf_evidence_status') or '—'} / level={norm.get('browser_perf_evidence_level') or '—'} / bundle_ready={norm.get('browser_perf_bundle_ready')} / snapshot_contract_match={norm.get('browser_perf_snapshot_contract_match')}"
        )
    if any(
        norm.get(key) not in (None, "", [], {})
        for key in (
            "browser_perf_registry_snapshot_ref",
            "browser_perf_contract_ref",
            "browser_perf_evidence_report_ref",
            "browser_perf_comparison_report_ref",
            "browser_perf_trace_ref",
            "browser_perf_registry_snapshot_in_bundle",
            "browser_perf_contract_in_bundle",
            "browser_perf_evidence_report_in_bundle",
            "browser_perf_comparison_report_in_bundle",
            "browser_perf_trace_in_bundle",
        )
    ):
        lines.append(
            f"- browser_perf_artifacts_primary: snapshot={norm.get('browser_perf_registry_snapshot_ref') or '—'} / exists={norm.get('browser_perf_registry_snapshot_exists')} / in_bundle={norm.get('browser_perf_registry_snapshot_in_bundle')} ; contract={norm.get('browser_perf_contract_ref') or '—'} / exists={norm.get('browser_perf_contract_exists')} / in_bundle={norm.get('browser_perf_contract_in_bundle')}"
        )
        lines.append(
            f"- browser_perf_artifacts_secondary: previous={norm.get('browser_perf_previous_snapshot_ref') or '—'} / exists={norm.get('browser_perf_previous_snapshot_exists')} / in_bundle={norm.get('browser_perf_previous_snapshot_in_bundle')} ; evidence={norm.get('browser_perf_evidence_report_ref') or '—'} / exists={norm.get('browser_perf_evidence_report_exists')} / in_bundle={norm.get('browser_perf_evidence_report_in_bundle')} ; comparison={norm.get('browser_perf_comparison_report_ref') or '—'} / exists={norm.get('browser_perf_comparison_report_exists')} / in_bundle={norm.get('browser_perf_comparison_report_in_bundle')} ; trace={norm.get('browser_perf_trace_ref') or '—'} / exists={norm.get('browser_perf_trace_exists')} / in_bundle={norm.get('browser_perf_trace_in_bundle')}"
        )
    if norm.get("browser_perf_component_count") is not None:
        lines.append(
            f"- browser_perf_component_count: {norm.get('browser_perf_component_count')} / total_wakeups={norm.get('browser_perf_total_wakeups')} / total_duplicate_guard_hits={norm.get('browser_perf_total_duplicate_guard_hits')} / max_idle_poll_ms={norm.get('browser_perf_max_idle_poll_ms')}"
        )
    if norm.get("browser_perf_comparison_status") or norm.get("browser_perf_comparison_level"):
        lines.append(
            f"- browser_perf_comparison_status: {norm.get('browser_perf_comparison_status') or '—'} / level={norm.get('browser_perf_comparison_level') or '—'} / ready={norm.get('browser_perf_comparison_ready')} / changed={norm.get('browser_perf_comparison_changed')}"
        )
        lines.append(
            f"- browser_perf_comparison_delta: wakeups={norm.get('browser_perf_comparison_delta_total_wakeups')} / dup={norm.get('browser_perf_comparison_delta_total_duplicate_guard_hits')} / render={norm.get('browser_perf_comparison_delta_total_render_count')} / max_idle_poll_ms={norm.get('browser_perf_comparison_delta_max_idle_poll_ms')}"
        )
    issues = [str(x) for x in (norm.get("issues") or []) if str(x).strip()]
    if issues:
        lines.extend(["", "## Issues", *[f"- {x}" for x in issues]])
    return "\n".join(lines).rstrip() + "\n"
