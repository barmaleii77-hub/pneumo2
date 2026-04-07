from __future__ import annotations

"""Helpers for explicit browser-performance snapshot/trace artifacts.

This module keeps browser-side perf evidence machine-checkable and bundle-friendly.

Current phase goals:
- persist an explicit snapshot of the browser perf registry exported from the
  playhead component into ``workspace/exports``;
- surface whether a heavier browser trace file is present next to the snapshot;
- avoid vague "CPU feels high" claims by writing a canonical JSON sidecar with
  summary counters and artifact references.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import json

BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME = "browser_perf_registry_snapshot.json"
BROWSER_PERF_CONTRACT_JSON_NAME = "browser_perf_contract.json"
BROWSER_PERF_TRACE_CANDIDATE_NAMES: tuple[str, ...] = (
    "browser_perf_trace.trace",
    "browser_perf_trace.json",
    "browser_perf_trace.cpuprofile",
    "browser_performance_trace.trace",
    "browser_performance_trace.json",
    "perf_trace.trace",
    "perf_trace.json",
)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _normalize_snapshot_summary(components: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    component_count = _safe_int(summary.get("component_count"), len(components))
    if component_count <= 0:
        component_count = len(components)

    def _sum_counter(key: str) -> int:
        total = 0
        for obj in components.values():
            if isinstance(obj, Mapping):
                total += _safe_int(obj.get(key), 0)
        return total

    def _count_state(state: str) -> int:
        total = 0
        for obj in components.values():
            if isinstance(obj, Mapping) and _safe_str(obj.get("viewport_state")) == state:
                total += 1
        return total

    return {
        "component_count": component_count,
        "visible_count": _safe_int(summary.get("visible_count"), _count_state("visible")),
        "hidden_count": _safe_int(summary.get("hidden_count"), _count_state("hidden")),
        "offscreen_count": _safe_int(summary.get("offscreen_count"), _count_state("offscreen")),
        "zero_size_count": _safe_int(summary.get("zero_size_count"), _count_state("zero_size")),
        "css_hidden_count": _safe_int(summary.get("css_hidden_count"), _count_state("css_hidden")),
        "total_wakeups": _safe_int(summary.get("total_wakeups"), _sum_counter("wakeups")),
        "total_duplicate_guard_hits": _safe_int(summary.get("total_duplicate_guard_hits"), _sum_counter("duplicate_guard_hits")),
        "total_render_count": _safe_int(summary.get("total_render_count"), _sum_counter("render_count")),
        "total_schedule_raf": _safe_int(summary.get("total_schedule_raf"), _sum_counter("schedule_raf_count")),
        "total_schedule_timeout": _safe_int(summary.get("total_schedule_timeout"), _sum_counter("schedule_timeout_count")),
        "max_idle_poll_ms": _safe_int(summary.get("max_idle_poll_ms"), 0),
    }


def normalize_browser_perf_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    src = _as_dict(snapshot)
    components = {
        _safe_str(name): _as_dict(payload)
        for name, payload in _as_dict(src.get("components")).items()
        if _safe_str(name).strip()
    }
    summary = _normalize_snapshot_summary(components, _as_dict(src.get("summary")))
    return {
        "schema": "browser_perf_registry_snapshot_v1",
        "updated_utc": _safe_str(src.get("updated_utc") or src.get("ts_iso") or _utc_iso()),
        "dataset_id": _safe_str(src.get("dataset_id")),
        "source_component": _safe_str(src.get("source_component") or "playhead_ctrl"),
        "components": components,
        "summary": summary,
    }


def _trace_candidate_path(exports_dir: Path) -> tuple[str, str, bool]:
    for name in BROWSER_PERF_TRACE_CANDIDATE_NAMES:
        p = exports_dir / name
        try:
            if p.exists() and p.is_file():
                return name, str(p.resolve()), True
        except Exception:
            continue
    return "", "", False


def _contract_level(snapshot_exists: bool, trace_exists: bool, component_count: int) -> tuple[str, str, str]:
    if trace_exists:
        return "PASS", "trace_present", "Browser performance trace artifact is present."
    if snapshot_exists and component_count > 0:
        return "WARN", "snapshot_only", (
            "Browser perf registry snapshot is present, but a heavier browser trace artifact "
            "is still missing."
        )
    if snapshot_exists:
        return "WARN", "snapshot_empty", "Browser perf snapshot exists but does not contain component data."
    return "WARN", "missing", "Browser perf artifacts are missing."


def write_browser_perf_artifacts(
    exports_dir: Path,
    snapshot: Mapping[str, Any] | None,
    *,
    updated_utc: str | None = None,
) -> dict[str, Any]:
    exports_dir = Path(exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    snap_norm = normalize_browser_perf_snapshot(snapshot)
    if updated_utc:
        snap_norm["updated_utc"] = _safe_str(updated_utc)

    snapshot_path = exports_dir / BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME
    snapshot_path.write_text(json.dumps(snap_norm, ensure_ascii=False, indent=2), encoding="utf-8")

    trace_ref, trace_path, trace_exists = _trace_candidate_path(exports_dir)
    component_count = _safe_int(_as_dict(snap_norm.get("summary")).get("component_count"), 0)
    level, status, message = _contract_level(True, trace_exists, component_count)

    contract = {
        "schema": "browser_perf_contract_v1",
        "updated_utc": _safe_str(updated_utc or snap_norm.get("updated_utc") or _utc_iso()),
        "snapshot_ref": BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME,
        "snapshot_exists": True,
        "trace_ref": trace_ref,
        "trace_exists": bool(trace_exists),
        "level": level,
        "status": status,
        "message": message,
        "dataset_id": _safe_str(snap_norm.get("dataset_id")),
        "source_component": _safe_str(snap_norm.get("source_component") or "playhead_ctrl"),
        "summary": dict(_as_dict(snap_norm.get("summary"))),
    }
    contract_path = exports_dir / BROWSER_PERF_CONTRACT_JSON_NAME
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "browser_perf_registry_snapshot": {
            "ref": BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME,
            "path": str(snapshot_path.resolve()),
            "exists": True,
            "summary": dict(_as_dict(snap_norm.get("summary"))),
        },
        "browser_perf_contract": {
            "ref": BROWSER_PERF_CONTRACT_JSON_NAME,
            "path": str(contract_path.resolve()),
            "exists": True,
            "level": level,
            "status": status,
            "message": message,
        },
        "browser_perf_trace": {
            "ref": trace_ref,
            "path": trace_path,
            "exists": bool(trace_exists),
        },
    }


def collect_browser_perf_artifacts_summary(exports_dir: Path) -> dict[str, Any]:
    exports_dir = Path(exports_dir)
    snapshot_path = exports_dir / BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME
    contract_path = exports_dir / BROWSER_PERF_CONTRACT_JSON_NAME
    trace_ref, trace_path, trace_exists = _trace_candidate_path(exports_dir)

    snapshot_exists = False
    snapshot_summary: dict[str, Any] = {}
    snapshot_dataset_id = ""
    snapshot_source_component = ""
    if snapshot_path.exists():
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            payload = normalize_browser_perf_snapshot(payload if isinstance(payload, Mapping) else {})
            snapshot_exists = True
            snapshot_summary = dict(_as_dict(payload.get("summary")))
            snapshot_dataset_id = _safe_str(payload.get("dataset_id"))
            snapshot_source_component = _safe_str(payload.get("source_component"))
        except Exception:
            snapshot_exists = True

    contract_exists = False
    contract_level = ""
    contract_status = ""
    contract_message = ""
    if contract_path.exists():
        try:
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                contract_exists = True
                contract_level = _safe_str(payload.get("level"))
                contract_status = _safe_str(payload.get("status"))
                contract_message = _safe_str(payload.get("message"))
                if not snapshot_summary:
                    snapshot_summary = dict(_as_dict(payload.get("summary")))
                if not snapshot_dataset_id:
                    snapshot_dataset_id = _safe_str(payload.get("dataset_id"))
                if not snapshot_source_component:
                    snapshot_source_component = _safe_str(payload.get("source_component"))
        except Exception:
            contract_exists = True

    if not contract_level:
        component_count = _safe_int(snapshot_summary.get("component_count"), 0)
        contract_level, contract_status, contract_message = _contract_level(snapshot_exists, trace_exists, component_count)

    return {
        "browser_perf_registry_snapshot_ref": BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME if snapshot_exists else "",
        "browser_perf_registry_snapshot_path": str(snapshot_path.resolve()) if snapshot_path.exists() else "",
        "browser_perf_registry_snapshot_exists": snapshot_exists,
        "browser_perf_contract_ref": BROWSER_PERF_CONTRACT_JSON_NAME if contract_path.exists() else "",
        "browser_perf_contract_path": str(contract_path.resolve()) if contract_path.exists() else "",
        "browser_perf_contract_exists": contract_exists,
        "browser_perf_trace_ref": trace_ref,
        "browser_perf_trace_path": trace_path,
        "browser_perf_trace_exists": bool(trace_exists),
        "browser_perf_level": contract_level,
        "browser_perf_status": contract_status,
        "browser_perf_message": contract_message,
        "browser_perf_dataset_id": snapshot_dataset_id,
        "browser_perf_source_component": snapshot_source_component,
        "browser_perf_summary": snapshot_summary,
        "browser_perf_component_count": _safe_int(snapshot_summary.get("component_count"), 0),
        "browser_perf_total_wakeups": _safe_int(snapshot_summary.get("total_wakeups"), 0),
        "browser_perf_total_duplicate_guard_hits": _safe_int(snapshot_summary.get("total_duplicate_guard_hits"), 0),
        "browser_perf_max_idle_poll_ms": _safe_int(snapshot_summary.get("max_idle_poll_ms"), 0),
    }


def persist_browser_perf_snapshot_event(
    evt: Mapping[str, Any] | None,
    exports_dir: Path,
) -> dict[str, Any] | None:
    evt_dict = _as_dict(evt)
    if _safe_str(evt_dict.get("kind")) != "browser_perf_snapshot":
        return None
    snapshot = evt_dict.get("snapshot")
    if not isinstance(snapshot, Mapping):
        return None
    updated_utc = _safe_str(evt_dict.get("updated_utc") or evt_dict.get("ts_iso") or _utc_iso())
    src = dict(snapshot)
    src.setdefault("dataset_id", _safe_str(evt_dict.get("dataset_id")))
    src.setdefault("source_component", _safe_str(evt_dict.get("source_component") or "playhead_ctrl"))
    write_browser_perf_artifacts(exports_dir=exports_dir, snapshot=src, updated_utc=updated_utc)
    return collect_browser_perf_artifacts_summary(exports_dir)
