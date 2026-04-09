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
BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME = "browser_perf_previous_snapshot.json"
BROWSER_PERF_CONTRACT_JSON_NAME = "browser_perf_contract.json"
BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME = "browser_perf_evidence_report.json"
BROWSER_PERF_EVIDENCE_REPORT_MD_NAME = "browser_perf_evidence_report.md"
BROWSER_PERF_COMPARISON_REPORT_JSON_NAME = "browser_perf_comparison_report.json"
BROWSER_PERF_COMPARISON_REPORT_MD_NAME = "browser_perf_comparison_report.md"
BROWSER_PERF_TRACE_CANDIDATE_NAMES: tuple[str, ...] = (
    "browser_perf_trace.trace",
    "browser_perf_trace.json",
    "browser_perf_trace.cpuprofile",
    "browser_performance_trace.trace",
    "browser_performance_trace.json",
    "perf_trace.trace",
    "perf_trace.json",
)
_SUMMARY_COMPARE_KEYS: tuple[str, ...] = (
    "component_count",
    "visible_count",
    "hidden_count",
    "offscreen_count",
    "zero_size_count",
    "css_hidden_count",
    "total_wakeups",
    "total_duplicate_guard_hits",
    "total_render_count",
    "total_schedule_raf",
    "total_schedule_timeout",
    "max_idle_poll_ms",
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


def _copy_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _copy_json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_copy_json_value(v) for v in value]
    return value


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


def _normalized_summary_compare_payload(summary: Mapping[str, Any] | None) -> dict[str, int]:
    src = _as_dict(summary)
    return {key: _safe_int(src.get(key), 0) for key in _SUMMARY_COMPARE_KEYS}


def _build_browser_perf_evidence_report(
    *,
    updated_utc: str,
    snapshot_ref: str,
    snapshot_path: str,
    snapshot_exists: bool,
    snapshot_payload: Mapping[str, Any] | None,
    contract_ref: str,
    contract_path: str,
    contract_exists: bool,
    contract_payload: Mapping[str, Any] | None,
    trace_ref: str,
    trace_path: str,
    trace_exists: bool,
) -> dict[str, Any]:
    snap_payload = _as_dict(snapshot_payload)
    contract_obj = _as_dict(contract_payload)
    snapshot_summary = _normalized_summary_compare_payload(snap_payload.get("summary"))
    contract_summary = _normalized_summary_compare_payload(contract_obj.get("summary"))
    component_count = _safe_int(snapshot_summary.get("component_count"), 0)

    snapshot_contract_match: bool | None = None
    if snapshot_exists and contract_exists:
        snapshot_contract_match = snapshot_summary == contract_summary

    bundle_ready = bool(
        snapshot_exists
        and contract_exists
        and trace_exists
        and component_count > 0
        and snapshot_contract_match is not False
    )

    if snapshot_contract_match is False:
        level = "WARN"
        status = "summary_mismatch"
        message = "Browser perf snapshot and contract summaries disagree; regenerate perf artifacts before acceptance."
        recommendation = "Re-export browser perf snapshot/contract from the same detail-run before relying on this evidence."
    elif trace_exists and snapshot_exists and contract_exists and component_count > 0:
        level = "PASS"
        status = "trace_bundle_ready"
        message = "Browser perf snapshot, contract and heavier trace are present; evidence is ready for bundle-side review."
        recommendation = "Use this bundle for measured Windows/browser perf acceptance and compare it against the previous run."
    elif snapshot_exists and contract_exists and component_count > 0:
        level = "WARN"
        status = "snapshot_only"
        message = "Browser perf snapshot/contract are present, but the heavier trace artifact is still missing."
        recommendation = "Capture a live browser_perf_trace from a detail-run to close measured acceptance."
    elif snapshot_exists and contract_exists:
        level = "WARN"
        status = "snapshot_empty"
        message = "Browser perf snapshot/contract exist, but the snapshot does not contain component data."
        recommendation = "Reproduce the run with browser perf export enabled and verify component counters are populated."
    elif snapshot_exists:
        level = "WARN"
        status = "missing_contract"
        message = "Browser perf snapshot exists without the matching contract sidecar."
        recommendation = "Regenerate browser perf artifacts so snapshot and contract are exported together."
    elif contract_exists:
        level = "WARN"
        status = "missing_snapshot"
        message = "Browser perf contract exists without the underlying snapshot."
        recommendation = "Regenerate browser perf artifacts so the snapshot is present next to the contract."
    else:
        level = "WARN"
        status = "missing"
        message = "Browser perf evidence artifacts are missing."
        recommendation = "Run a detail scenario with browser perf export enabled before collecting acceptance evidence."

    return {
        "schema": "browser_perf_evidence_report_v1",
        "updated_utc": _safe_str(updated_utc or _utc_iso()),
        "dataset_id": _safe_str(snap_payload.get("dataset_id") or contract_obj.get("dataset_id")),
        "source_component": _safe_str(
            snap_payload.get("source_component") or contract_obj.get("source_component") or "playhead_ctrl"
        ),
        "snapshot_ref": _safe_str(snapshot_ref),
        "snapshot_path": _safe_str(snapshot_path),
        "snapshot_exists": bool(snapshot_exists),
        "contract_ref": _safe_str(contract_ref),
        "contract_path": _safe_str(contract_path),
        "contract_exists": bool(contract_exists),
        "trace_ref": _safe_str(trace_ref),
        "trace_path": _safe_str(trace_path),
        "trace_exists": bool(trace_exists),
        "snapshot_summary": snapshot_summary,
        "contract_summary": contract_summary,
        "snapshot_contract_match": snapshot_contract_match,
        "bundle_ready": bundle_ready,
        "level": level,
        "status": status,
        "message": message,
        "recommendation": recommendation,
    }


def _render_browser_perf_evidence_report_md(report: Mapping[str, Any]) -> str:
    rep = _as_dict(report)
    snapshot_summary = _normalized_summary_compare_payload(rep.get("snapshot_summary"))
    lines = [
        "# Browser Perf Evidence Report",
        "",
        f"- status: {rep.get('status') or '—'} / level={rep.get('level') or '—'}",
        f"- bundle_ready: {rep.get('bundle_ready')}",
        f"- snapshot_contract_match: {rep.get('snapshot_contract_match')}",
        f"- snapshot_ref: {rep.get('snapshot_ref') or '—'}",
        f"- contract_ref: {rep.get('contract_ref') or '—'}",
        f"- trace_ref: {rep.get('trace_ref') or '—'}",
        f"- component_count: {snapshot_summary.get('component_count', 0)}",
        f"- total_wakeups: {snapshot_summary.get('total_wakeups', 0)}",
        f"- total_duplicate_guard_hits: {snapshot_summary.get('total_duplicate_guard_hits', 0)}",
        f"- total_render_count: {snapshot_summary.get('total_render_count', 0)}",
        f"- max_idle_poll_ms: {snapshot_summary.get('max_idle_poll_ms', 0)}",
        f"- message: {rep.get('message') or '—'}",
        f"- recommendation: {rep.get('recommendation') or '—'}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _build_browser_perf_comparison_report(
    *,
    updated_utc: str,
    current_snapshot_ref: str,
    current_snapshot_path: str,
    current_snapshot_payload: Mapping[str, Any] | None,
    current_trace_exists: bool,
    reference_snapshot_ref: str,
    reference_snapshot_path: str,
    reference_snapshot_payload: Mapping[str, Any] | None,
    reference_trace_exists: bool | None,
) -> dict[str, Any]:
    current_payload = _as_dict(current_snapshot_payload)
    reference_payload = _as_dict(reference_snapshot_payload)
    current_summary = _normalized_summary_compare_payload(current_payload.get("summary"))
    reference_summary = _normalized_summary_compare_payload(reference_payload.get("summary"))
    reference_exists = bool(reference_payload)
    comparison_ready = bool(reference_exists)
    delta_summary = {
        key: int(current_summary.get(key, 0)) - int(reference_summary.get(key, 0))
        for key in _SUMMARY_COMPARE_KEYS
    }
    changed_keys = [key for key, value in delta_summary.items() if int(value) != 0]
    comparison_changed: bool | None = bool(changed_keys) if comparison_ready else None

    if not comparison_ready:
        level = "WARN"
        status = "no_reference"
        message = "No previous browser perf snapshot is available for comparison yet."
        recommendation = "Capture at least one more measured run to get a comparison report between snapshots."
    elif comparison_changed:
        level = "PASS"
        status = "changed"
        message = "Current browser perf snapshot differs from the previous exported snapshot."
        recommendation = "Review delta counters before measured acceptance and confirm the change is expected."
    else:
        level = "PASS"
        status = "unchanged"
        message = "Current browser perf snapshot matches the previous exported snapshot."
        recommendation = "Use the matching snapshots as stable evidence when preparing measured acceptance."

    return {
        "schema": "browser_perf_comparison_report_v1",
        "updated_utc": _safe_str(updated_utc or _utc_iso()),
        "current_snapshot_ref": _safe_str(current_snapshot_ref),
        "current_snapshot_path": _safe_str(current_snapshot_path),
        "current_updated_utc": _safe_str(current_payload.get("updated_utc")),
        "current_dataset_id": _safe_str(current_payload.get("dataset_id")),
        "current_trace_exists": bool(current_trace_exists),
        "current_summary": current_summary,
        "reference_snapshot_ref": _safe_str(reference_snapshot_ref),
        "reference_snapshot_path": _safe_str(reference_snapshot_path),
        "reference_snapshot_exists": comparison_ready,
        "reference_updated_utc": _safe_str(reference_payload.get("updated_utc")),
        "reference_dataset_id": _safe_str(reference_payload.get("dataset_id")),
        "reference_trace_exists": reference_trace_exists,
        "reference_summary": reference_summary,
        "delta_summary": delta_summary,
        "changed_keys": changed_keys,
        "comparison_ready": comparison_ready,
        "comparison_changed": comparison_changed,
        "level": level,
        "status": status,
        "message": message,
        "recommendation": recommendation,
    }


def _render_browser_perf_comparison_report_md(report: Mapping[str, Any]) -> str:
    rep = _as_dict(report)
    delta_summary = _normalized_summary_compare_payload(rep.get("delta_summary"))
    changed_keys = [str(x) for x in (rep.get("changed_keys") or []) if str(x).strip()]
    lines = [
        "# Browser Perf Comparison Report",
        "",
        f"- status: {rep.get('status') or '—'} / level={rep.get('level') or '—'}",
        f"- comparison_ready: {rep.get('comparison_ready')}",
        f"- comparison_changed: {rep.get('comparison_changed')}",
        f"- current_snapshot_ref: {rep.get('current_snapshot_ref') or '—'}",
        f"- reference_snapshot_ref: {rep.get('reference_snapshot_ref') or '—'}",
        f"- current_updated_utc: {rep.get('current_updated_utc') or '—'}",
        f"- reference_updated_utc: {rep.get('reference_updated_utc') or '—'}",
        f"- delta_total_wakeups: {delta_summary.get('total_wakeups', 0)}",
        f"- delta_total_duplicate_guard_hits: {delta_summary.get('total_duplicate_guard_hits', 0)}",
        f"- delta_total_render_count: {delta_summary.get('total_render_count', 0)}",
        f"- delta_max_idle_poll_ms: {delta_summary.get('max_idle_poll_ms', 0)}",
        f"- changed_keys: {', '.join(changed_keys) if changed_keys else '—'}",
        f"- message: {rep.get('message') or '—'}",
        f"- recommendation: {rep.get('recommendation') or '—'}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_browser_perf_artifacts(
    exports_dir: Path,
    snapshot: Mapping[str, Any] | None,
    *,
    updated_utc: str | None = None,
) -> dict[str, Any]:
    exports_dir = Path(exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = exports_dir / BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME
    previous_snapshot_path = exports_dir / BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME
    contract_path = exports_dir / BROWSER_PERF_CONTRACT_JSON_NAME
    evidence_report_path = exports_dir / BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME
    evidence_report_md_path = exports_dir / BROWSER_PERF_EVIDENCE_REPORT_MD_NAME
    comparison_report_path = exports_dir / BROWSER_PERF_COMPARISON_REPORT_JSON_NAME
    comparison_report_md_path = exports_dir / BROWSER_PERF_COMPARISON_REPORT_MD_NAME

    previous_snapshot_payload: dict[str, Any] = {}
    previous_trace_exists: bool | None = None
    if snapshot_path.exists():
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            previous_snapshot_payload = normalize_browser_perf_snapshot(payload if isinstance(payload, Mapping) else {})
        except Exception:
            previous_snapshot_payload = {}
    if evidence_report_path.exists():
        try:
            payload = json.loads(evidence_report_path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping) and "trace_exists" in payload:
                previous_trace_exists = bool(payload.get("trace_exists"))
        except Exception:
            previous_trace_exists = None

    snap_norm = normalize_browser_perf_snapshot(snapshot)
    if updated_utc:
        snap_norm["updated_utc"] = _safe_str(updated_utc)

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
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

    evidence_report = _build_browser_perf_evidence_report(
        updated_utc=_safe_str(updated_utc or snap_norm.get("updated_utc") or _utc_iso()),
        snapshot_ref=BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME,
        snapshot_path=str(snapshot_path.resolve()),
        snapshot_exists=True,
        snapshot_payload=snap_norm,
        contract_ref=BROWSER_PERF_CONTRACT_JSON_NAME,
        contract_path=str(contract_path.resolve()),
        contract_exists=True,
        contract_payload=contract,
        trace_ref=trace_ref,
        trace_path=trace_path,
        trace_exists=bool(trace_exists),
    )
    evidence_report_path.write_text(json.dumps(evidence_report, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence_report_md_path.write_text(_render_browser_perf_evidence_report_md(evidence_report), encoding="utf-8")

    if previous_snapshot_payload:
        previous_snapshot_path.write_text(
            json.dumps(_copy_json_value(previous_snapshot_payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        try:
            previous_snapshot_path.unlink(missing_ok=True)
        except Exception:
            pass

    comparison_report = _build_browser_perf_comparison_report(
        updated_utc=_safe_str(updated_utc or snap_norm.get("updated_utc") or _utc_iso()),
        current_snapshot_ref=BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME,
        current_snapshot_path=str(snapshot_path.resolve()),
        current_snapshot_payload=snap_norm,
        current_trace_exists=bool(trace_exists),
        reference_snapshot_ref=BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME if previous_snapshot_payload else "",
        reference_snapshot_path=str(previous_snapshot_path.resolve()) if previous_snapshot_payload else "",
        reference_snapshot_payload=previous_snapshot_payload,
        reference_trace_exists=previous_trace_exists,
    )
    comparison_report_path.write_text(json.dumps(comparison_report, ensure_ascii=False, indent=2), encoding="utf-8")
    comparison_report_md_path.write_text(_render_browser_perf_comparison_report_md(comparison_report), encoding="utf-8")

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
        "browser_perf_evidence_report": {
            "ref": BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME,
            "path": str(evidence_report_path.resolve()),
            "exists": True,
            "level": _safe_str(evidence_report.get("level")),
            "status": _safe_str(evidence_report.get("status")),
            "message": _safe_str(evidence_report.get("message")),
            "bundle_ready": bool(evidence_report.get("bundle_ready")),
            "snapshot_contract_match": evidence_report.get("snapshot_contract_match"),
        },
        "browser_perf_previous_snapshot": {
            "ref": BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME if previous_snapshot_payload else "",
            "path": str(previous_snapshot_path.resolve()) if previous_snapshot_payload else "",
            "exists": bool(previous_snapshot_payload),
        },
        "browser_perf_comparison_report": {
            "ref": BROWSER_PERF_COMPARISON_REPORT_JSON_NAME,
            "path": str(comparison_report_path.resolve()),
            "exists": True,
            "level": _safe_str(comparison_report.get("level")),
            "status": _safe_str(comparison_report.get("status")),
            "message": _safe_str(comparison_report.get("message")),
            "comparison_ready": bool(comparison_report.get("comparison_ready")),
            "comparison_changed": comparison_report.get("comparison_changed"),
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
    previous_snapshot_path = exports_dir / BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME
    contract_path = exports_dir / BROWSER_PERF_CONTRACT_JSON_NAME
    evidence_report_path = exports_dir / BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME
    comparison_report_path = exports_dir / BROWSER_PERF_COMPARISON_REPORT_JSON_NAME
    trace_ref, trace_path, trace_exists = _trace_candidate_path(exports_dir)

    snapshot_exists = False
    snapshot_summary: dict[str, Any] = {}
    snapshot_dataset_id = ""
    snapshot_source_component = ""
    snapshot_payload: dict[str, Any] = {}
    if snapshot_path.exists():
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            payload = normalize_browser_perf_snapshot(payload if isinstance(payload, Mapping) else {})
            snapshot_exists = True
            snapshot_payload = dict(payload)
            snapshot_summary = dict(_as_dict(payload.get("summary")))
            snapshot_dataset_id = _safe_str(payload.get("dataset_id"))
            snapshot_source_component = _safe_str(payload.get("source_component"))
        except Exception:
            snapshot_exists = True

    contract_exists = False
    contract_level = ""
    contract_status = ""
    contract_message = ""
    contract_payload: dict[str, Any] = {}
    if contract_path.exists():
        try:
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                contract_exists = True
                contract_payload = dict(payload)
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

    report_exists = False
    report_level = ""
    report_status = ""
    report_message = ""
    report_bundle_ready = False
    report_snapshot_contract_match: bool | None = None
    if evidence_report_path.exists():
        try:
            payload = json.loads(evidence_report_path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                report_exists = True
                report_level = _safe_str(payload.get("level"))
                report_status = _safe_str(payload.get("status"))
                report_message = _safe_str(payload.get("message"))
                report_bundle_ready = bool(payload.get("bundle_ready"))
                if "snapshot_contract_match" in payload:
                    report_snapshot_contract_match = payload.get("snapshot_contract_match")  # type: ignore[assignment]
        except Exception:
            report_exists = True

    if not report_level:
        report_payload = _build_browser_perf_evidence_report(
            updated_utc=_safe_str(
                (snapshot_payload or {}).get("updated_utc")
                or (contract_payload or {}).get("updated_utc")
                or _utc_iso()
            ),
            snapshot_ref=BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME if snapshot_exists else "",
            snapshot_path=str(snapshot_path.resolve()) if snapshot_path.exists() else "",
            snapshot_exists=snapshot_exists,
            snapshot_payload=snapshot_payload,
            contract_ref=BROWSER_PERF_CONTRACT_JSON_NAME if contract_path.exists() else "",
            contract_path=str(contract_path.resolve()) if contract_path.exists() else "",
            contract_exists=contract_exists,
            contract_payload=contract_payload,
            trace_ref=trace_ref,
            trace_path=trace_path,
            trace_exists=bool(trace_exists),
        )
        report_level = _safe_str(report_payload.get("level"))
        report_status = _safe_str(report_payload.get("status"))
        report_message = _safe_str(report_payload.get("message"))
        report_bundle_ready = bool(report_payload.get("bundle_ready"))
        report_snapshot_contract_match = report_payload.get("snapshot_contract_match")  # type: ignore[assignment]

    previous_snapshot_exists = False
    previous_snapshot_payload: dict[str, Any] = {}
    if previous_snapshot_path.exists():
        try:
            payload = json.loads(previous_snapshot_path.read_text(encoding="utf-8"))
            previous_snapshot_payload = normalize_browser_perf_snapshot(payload if isinstance(payload, Mapping) else {})
            previous_snapshot_exists = bool(previous_snapshot_payload)
        except Exception:
            previous_snapshot_exists = True

    comparison_exists = False
    comparison_level = ""
    comparison_status = ""
    comparison_message = ""
    comparison_ready = False
    comparison_changed: bool | None = None
    comparison_reference_updated_utc = ""
    comparison_current_updated_utc = ""
    comparison_reference_trace_exists: bool | None = None
    comparison_current_trace_exists: bool | None = None
    comparison_delta_total_wakeups = 0
    comparison_delta_total_duplicate_guard_hits = 0
    comparison_delta_total_render_count = 0
    comparison_delta_max_idle_poll_ms = 0
    if comparison_report_path.exists():
        try:
            payload = json.loads(comparison_report_path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                comparison_exists = True
                comparison_level = _safe_str(payload.get("level"))
                comparison_status = _safe_str(payload.get("status"))
                comparison_message = _safe_str(payload.get("message"))
                comparison_ready = bool(payload.get("comparison_ready"))
                if "comparison_changed" in payload:
                    comparison_changed = payload.get("comparison_changed")  # type: ignore[assignment]
                comparison_reference_updated_utc = _safe_str(payload.get("reference_updated_utc"))
                comparison_current_updated_utc = _safe_str(payload.get("current_updated_utc"))
                if "reference_trace_exists" in payload:
                    comparison_reference_trace_exists = payload.get("reference_trace_exists")  # type: ignore[assignment]
                if "current_trace_exists" in payload:
                    comparison_current_trace_exists = payload.get("current_trace_exists")  # type: ignore[assignment]
                delta_summary = _normalized_summary_compare_payload(payload.get("delta_summary"))
                comparison_delta_total_wakeups = int(delta_summary.get("total_wakeups", 0))
                comparison_delta_total_duplicate_guard_hits = int(delta_summary.get("total_duplicate_guard_hits", 0))
                comparison_delta_total_render_count = int(delta_summary.get("total_render_count", 0))
                comparison_delta_max_idle_poll_ms = int(delta_summary.get("max_idle_poll_ms", 0))
        except Exception:
            comparison_exists = True

    if not comparison_level:
        comparison_payload = _build_browser_perf_comparison_report(
            updated_utc=_safe_str(
                (snapshot_payload or {}).get("updated_utc")
                or (contract_payload or {}).get("updated_utc")
                or _utc_iso()
            ),
            current_snapshot_ref=BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME if snapshot_exists else "",
            current_snapshot_path=str(snapshot_path.resolve()) if snapshot_path.exists() else "",
            current_snapshot_payload=snapshot_payload,
            current_trace_exists=bool(trace_exists),
            reference_snapshot_ref=BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME if previous_snapshot_payload else "",
            reference_snapshot_path=str(previous_snapshot_path.resolve()) if previous_snapshot_path.exists() else "",
            reference_snapshot_payload=previous_snapshot_payload,
            reference_trace_exists=None,
        )
        comparison_level = _safe_str(comparison_payload.get("level"))
        comparison_status = _safe_str(comparison_payload.get("status"))
        comparison_message = _safe_str(comparison_payload.get("message"))
        comparison_ready = bool(comparison_payload.get("comparison_ready"))
        comparison_changed = comparison_payload.get("comparison_changed")  # type: ignore[assignment]
        comparison_reference_updated_utc = _safe_str(comparison_payload.get("reference_updated_utc"))
        comparison_current_updated_utc = _safe_str(comparison_payload.get("current_updated_utc"))
        comparison_reference_trace_exists = comparison_payload.get("reference_trace_exists")  # type: ignore[assignment]
        comparison_current_trace_exists = comparison_payload.get("current_trace_exists")  # type: ignore[assignment]
        delta_summary = _normalized_summary_compare_payload(comparison_payload.get("delta_summary"))
        comparison_delta_total_wakeups = int(delta_summary.get("total_wakeups", 0))
        comparison_delta_total_duplicate_guard_hits = int(delta_summary.get("total_duplicate_guard_hits", 0))
        comparison_delta_total_render_count = int(delta_summary.get("total_render_count", 0))
        comparison_delta_max_idle_poll_ms = int(delta_summary.get("max_idle_poll_ms", 0))

    return {
        "browser_perf_registry_snapshot_ref": BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME if snapshot_exists else "",
        "browser_perf_registry_snapshot_path": str(snapshot_path.resolve()) if snapshot_path.exists() else "",
        "browser_perf_registry_snapshot_exists": snapshot_exists,
        "browser_perf_previous_snapshot_ref": BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME if previous_snapshot_exists else "",
        "browser_perf_previous_snapshot_path": str(previous_snapshot_path.resolve()) if previous_snapshot_path.exists() else "",
        "browser_perf_previous_snapshot_exists": previous_snapshot_exists,
        "browser_perf_contract_ref": BROWSER_PERF_CONTRACT_JSON_NAME if contract_path.exists() else "",
        "browser_perf_contract_path": str(contract_path.resolve()) if contract_path.exists() else "",
        "browser_perf_contract_exists": contract_exists,
        "browser_perf_evidence_report_ref": BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME if evidence_report_path.exists() else "",
        "browser_perf_evidence_report_path": str(evidence_report_path.resolve()) if evidence_report_path.exists() else "",
        "browser_perf_evidence_report_exists": report_exists,
        "browser_perf_comparison_report_ref": BROWSER_PERF_COMPARISON_REPORT_JSON_NAME if comparison_report_path.exists() else "",
        "browser_perf_comparison_report_path": str(comparison_report_path.resolve()) if comparison_report_path.exists() else "",
        "browser_perf_comparison_report_exists": comparison_exists,
        "browser_perf_trace_ref": trace_ref,
        "browser_perf_trace_path": trace_path,
        "browser_perf_trace_exists": bool(trace_exists),
        "browser_perf_level": contract_level,
        "browser_perf_status": contract_status,
        "browser_perf_message": contract_message,
        "browser_perf_evidence_level": report_level,
        "browser_perf_evidence_status": report_status,
        "browser_perf_evidence_message": report_message,
        "browser_perf_bundle_ready": bool(report_bundle_ready),
        "browser_perf_snapshot_contract_match": report_snapshot_contract_match,
        "browser_perf_comparison_level": comparison_level,
        "browser_perf_comparison_status": comparison_status,
        "browser_perf_comparison_message": comparison_message,
        "browser_perf_comparison_ready": bool(comparison_ready),
        "browser_perf_comparison_changed": comparison_changed,
        "browser_perf_comparison_reference_updated_utc": comparison_reference_updated_utc,
        "browser_perf_comparison_current_updated_utc": comparison_current_updated_utc,
        "browser_perf_comparison_reference_trace_exists": comparison_reference_trace_exists,
        "browser_perf_comparison_current_trace_exists": comparison_current_trace_exists,
        "browser_perf_comparison_delta_total_wakeups": comparison_delta_total_wakeups,
        "browser_perf_comparison_delta_total_duplicate_guard_hits": comparison_delta_total_duplicate_guard_hits,
        "browser_perf_comparison_delta_total_render_count": comparison_delta_total_render_count,
        "browser_perf_comparison_delta_max_idle_poll_ms": comparison_delta_max_idle_poll_ms,
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
