from __future__ import annotations

"""Runtime evidence writers and hard-fail validators for v32 gates.

The helpers in this module are intentionally adapter-only: they validate measured
artifact presence and runtime proof files, but they do not infer or redesign any
domain screen behavior.
"""

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


WINDOWS_RUNTIME_PROOF_JSON_NAME = "windows_runtime_proof.json"
WINDOWS_RUNTIME_PROOF_MD_NAME = "windows_runtime_proof.md"
ANIMATOR_FRAME_BUDGET_EVIDENCE_JSON_NAME = "animator_frame_budget_evidence.json"

_WINDOWS_REQUIRED_CHECKS: tuple[str, ...] = (
    "native_titlebar_system_menu",
    "snap_half_third_quarter",
    "docking_undocking_floating",
    "second_monitor_workflow",
    "mixed_dpi_or_pmv2",
    "keyboard_f6_focus",
    "resize_affordances",
    "portable_path_budget",
    "send_bundle_latest_pointer",
)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return _safe_str(value)


def _stable_hash(payload: Any) -> str:
    blob = json.dumps(_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def _find_paths(root: Path, patterns: Iterable[str]) -> list[Path]:
    root = Path(root)
    found: list[Path] = []
    for pattern in patterns:
        try:
            found.extend(p for p in root.glob(pattern) if p.is_file())
        except Exception:
            continue
    return sorted(set(found), key=lambda p: str(p).lower())


def build_windows_path_budget(root: Path | str, *, max_path_chars: int = 240) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve(strict=False)
    longest_full_path = ""
    longest_relative_path = ""
    max_full_path_chars = 0
    over_budget: list[dict[str, Any]] = []
    file_count = 0
    try:
        candidates = [p for p in root_path.rglob("*") if p.is_file()]
    except Exception:
        candidates = []
    for path in candidates:
        file_count += 1
        full = str(path.resolve(strict=False))
        rel = _safe_str(path.relative_to(root_path)) if path.is_relative_to(root_path) else full
        full_len = len(full)
        if full_len > max_full_path_chars:
            max_full_path_chars = full_len
            longest_full_path = full
            longest_relative_path = rel
        if full_len > int(max_path_chars):
            over_budget.append({"path": full, "path_chars": full_len})
    if over_budget:
        status = "FAIL"
        message = "One or more bundled files exceed the Windows path budget."
    elif file_count <= 0:
        status = "WARN"
        message = "No files were available for Windows path-budget proof."
    else:
        status = "PASS"
        message = "All discovered files are within the Windows path budget."
    return {
        "schema": "windows_path_budget.v1",
        "root": str(root_path),
        "max_path_chars": int(max_path_chars),
        "file_count": int(file_count),
        "max_full_path_chars": int(max_full_path_chars),
        "longest_full_path": longest_full_path,
        "longest_relative_path": longest_relative_path,
        "over_budget_count": int(len(over_budget)),
        "over_budget": over_budget[:25],
        "status": status,
        "message": message,
    }


def build_windows_runtime_proof(
    *,
    checks: Mapping[str, Any] | None = None,
    layout_profiles: Any = None,
    monitors: Any = None,
    dpi: Mapping[str, Any] | None = None,
    path_budget: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Any] | None = None,
    updated_utc: str = "",
) -> dict[str, Any]:
    check_map = {key: _as_dict(checks).get(key) for key in _WINDOWS_REQUIRED_CHECKS}
    missing_checks = [key for key, value in check_map.items() if value in (None, "")]
    failed_checks = [key for key, value in check_map.items() if value is False]
    budget = _as_dict(path_budget)
    if budget and budget.get("status") == "FAIL" and "portable_path_budget" not in failed_checks:
        failed_checks.append("portable_path_budget")
    if budget and budget.get("status") == "WARN" and "portable_path_budget" not in missing_checks:
        missing_checks.append("portable_path_budget")
    if failed_checks:
        level = "FAIL"
        status = "failed_required_checks"
        release_gate = "FAIL"
        hard_fail = True
        message = "Windows desktop runtime acceptance has failing required checks."
    elif missing_checks:
        level = "WARN"
        status = "incomplete_required_checks"
        release_gate = "WARN"
        hard_fail = False
        message = "Windows desktop runtime proof is incomplete."
    else:
        level = "PASS"
        status = "windows_runtime_proved"
        release_gate = "PASS"
        hard_fail = False
        message = "Windows desktop runtime acceptance proof is complete."
    proof = {
        "schema": "windows_runtime_proof.v1",
        "playbook_id": "PB-005",
        "open_gap_id": "OG-005",
        "canon_id": "17_WINDOWS_DESKTOP_CAD_GUI_CANON",
        "release_gates": ["RGH-009", "RGH-010", "RGH-017"],
        "updated_utc": _safe_str(updated_utc or _utc_iso()),
        "checks": check_map,
        "missing_checks": missing_checks,
        "failed_checks": failed_checks,
        "layout_profiles": _jsonable(layout_profiles or []),
        "monitors": _jsonable(monitors or []),
        "dpi": _jsonable(_as_dict(dpi)),
        "path_budget": _jsonable(budget),
        "artifacts": _jsonable(_as_dict(artifacts)),
        "level": level,
        "status": status,
        "release_gate": release_gate,
        "hard_fail": bool(hard_fail),
        "message": message,
    }
    proof["evidence_hash"] = _stable_hash(proof)
    return proof


def _render_windows_runtime_proof_md(proof: Mapping[str, Any]) -> str:
    obj = _as_dict(proof)
    failed = [_safe_str(x) for x in obj.get("failed_checks") or []]
    missing = [_safe_str(x) for x in obj.get("missing_checks") or []]
    budget = _as_dict(obj.get("path_budget"))
    lines = [
        "# Windows Runtime Proof",
        "",
        f"- status: {obj.get('status') or '-'} / level={obj.get('level') or '-'} / release_gate={obj.get('release_gate') or '-'}",
        f"- playbook_id: {obj.get('playbook_id') or 'PB-005'}",
        f"- canon_id: {obj.get('canon_id') or '17_WINDOWS_DESKTOP_CAD_GUI_CANON'}",
        f"- failed_checks: {', '.join(failed) if failed else '-'}",
        f"- missing_checks: {', '.join(missing) if missing else '-'}",
        f"- path_budget_status: {budget.get('status') or '-'}",
        f"- max_full_path_chars: {budget.get('max_full_path_chars') or 0}",
        f"- message: {obj.get('message') or '-'}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_windows_runtime_proof(exports_dir: Path | str, proof: Mapping[str, Any]) -> dict[str, Any]:
    exports = Path(exports_dir)
    exports.mkdir(parents=True, exist_ok=True)
    payload = dict(proof)
    if payload.get("schema") != "windows_runtime_proof.v1":
        payload = build_windows_runtime_proof(checks=payload)
    json_path = exports / WINDOWS_RUNTIME_PROOF_JSON_NAME
    md_path = exports / WINDOWS_RUNTIME_PROOF_MD_NAME
    json_path.write_text(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_windows_runtime_proof_md(payload), encoding="utf-8")
    return {
        "ref": WINDOWS_RUNTIME_PROOF_JSON_NAME,
        "path": str(json_path.resolve()),
        "exists": True,
        "level": _safe_str(payload.get("level")),
        "status": _safe_str(payload.get("status")),
        "release_gate": _safe_str(payload.get("release_gate")),
        "hard_fail": bool(payload.get("hard_fail")),
    }


def collect_windows_runtime_proof(
    *,
    checks: Mapping[str, Any] | None = None,
    path_budget_root: Path | str | None = None,
    latest_send_bundle_path: Path | str | None = None,
    layout_profiles: Any = None,
    monitors: Any = None,
    dpi: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Any] | None = None,
    max_path_chars: int = 240,
    updated_utc: str = "",
) -> dict[str, Any]:
    check_map = dict(_as_dict(checks))
    budget: dict[str, Any] = {}
    if path_budget_root not in (None, ""):
        budget = build_windows_path_budget(Path(str(path_budget_root)), max_path_chars=int(max_path_chars))
        check_map.setdefault("portable_path_budget", budget.get("status") == "PASS")

    artifact_map = dict(_as_dict(artifacts))
    if latest_send_bundle_path not in (None, ""):
        latest_path = Path(str(latest_send_bundle_path)).expanduser().resolve(strict=False)
        artifact_map["send_bundle_latest_pointer"] = str(latest_path)
        artifact_map["send_bundle_latest_pointer_exists"] = latest_path.exists()
        check_map.setdefault("send_bundle_latest_pointer", latest_path.exists())

    dpi_map = dict(_as_dict(dpi))
    dpi_map.setdefault("os_name", platform.system())
    dpi_map.setdefault("platform", platform.platform())

    return build_windows_runtime_proof(
        checks=check_map,
        layout_profiles=layout_profiles,
        monitors=monitors,
        dpi=dpi_map,
        path_budget=budget,
        artifacts=artifact_map,
        updated_utc=updated_utc,
    )


def write_collected_windows_runtime_proof(
    exports_dir: Path | str,
    *,
    checks: Mapping[str, Any] | None = None,
    path_budget_root: Path | str | None = None,
    latest_send_bundle_path: Path | str | None = None,
    layout_profiles: Any = None,
    monitors: Any = None,
    dpi: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Any] | None = None,
    max_path_chars: int = 240,
    updated_utc: str = "",
) -> dict[str, Any]:
    proof = collect_windows_runtime_proof(
        checks=checks,
        path_budget_root=path_budget_root,
        latest_send_bundle_path=latest_send_bundle_path,
        layout_profiles=layout_profiles,
        monitors=monitors,
        dpi=dpi,
        artifacts=artifacts,
        max_path_chars=int(max_path_chars),
        updated_utc=updated_utc,
    )
    return write_windows_runtime_proof(exports_dir, proof)


def validate_runtime_evidence_dir(
    evidence_dir: Path | str,
    *,
    require_browser_trace: bool = False,
    require_viewport_gating: bool = False,
    require_animator_frame_budget: bool = False,
    require_windows_runtime: bool = False,
) -> dict[str, Any]:
    root = Path(evidence_dir).expanduser().resolve(strict=False)
    checks: list[dict[str, Any]] = []
    hard_fails: list[dict[str, Any]] = []

    def add_check(name: str, ok: bool, message: str, *, path: Path | None = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "message": message, "path": str(path or "")})
        if not ok:
            hard_fails.append({"name": name, "message": message, "path": str(path or "")})

    if require_browser_trace:
        paths = _find_paths(
            root,
            (
                "browser_perf_trace*.json",
                "browser_perf_trace*.jsonl",
                "browser_perf_trace*.trace",
                "browser_perf_trace*.cpuprofile",
                "browser_perf_trace*.etl",
                "browser_perf_trace*.csv",
                "**/browser_perf_trace*.json",
                "**/browser_perf_trace*.jsonl",
                "**/browser_perf_trace*.trace",
                "**/browser_perf_trace*.cpuprofile",
                "**/browser_perf_trace*.etl",
                "**/browser_perf_trace*.csv",
            ),
        )
        add_check(
            "browser_perf_trace",
            bool(paths),
            "PB-006/RGH-011 requires a measured browser_perf_trace artifact.",
            path=paths[0] if paths else None,
        )

    if require_viewport_gating:
        paths = _find_paths(root, ("viewport_gating_report*.json", "viewport_gating*.json", "**/viewport_gating_report*.json", "**/viewport_gating*.json"))
        payload = _load_json(paths[0]) if paths else {}
        ok = bool(paths) and payload.get("release_gate") == "PASS" and not bool(payload.get("hard_fail"))
        if ok and _safe_int(payload.get("hidden_surface_update_count"), 0) > 0:
            ok = False
        add_check(
            "viewport_gating",
            ok,
            "PB-006/RGH-012 requires PASS viewport gating with zero hidden-surface updates.",
            path=paths[0] if paths else None,
        )

    if require_animator_frame_budget:
        paths = _find_paths(root, (ANIMATOR_FRAME_BUDGET_EVIDENCE_JSON_NAME, "animator_frame_budget*.json", "**/animator_frame_budget*.json"))
        payload = _load_json(paths[0]) if paths else {}
        hidden = _as_dict(payload.get("hidden_dock_gating"))
        frame_budget = _as_dict(payload.get("frame_budget"))
        cadence = _as_dict(payload.get("frame_cadence")) or _as_dict(frame_budget.get("frame_cadence"))
        release_gate = _as_dict(payload.get("release_gate"))
        ok = bool(paths) and payload.get("evidence_state") == "measured"
        ok = ok and bool(hidden.get("gated")) and _safe_int(len(hidden.get("hidden_panel_updates") or []), 0) == 0
        ok = ok and bool(cadence) and bool(cadence.get("cadence_measured")) and cadence.get("cadence_budget_ok") is True
        ok = ok and _safe_str(release_gate.get("status") or payload.get("release_gate")) != "FAIL"
        add_check(
            "animator_frame_budget",
            ok,
            "PB-006/RGH-019 requires measured animator frame-budget evidence, frame cadence, and gated hidden panes.",
            path=paths[0] if paths else None,
        )

    if require_windows_runtime:
        paths = _find_paths(root, (WINDOWS_RUNTIME_PROOF_JSON_NAME, "windows_runtime_proof*.json", "**/windows_runtime_proof*.json"))
        payload = _load_json(paths[0]) if paths else {}
        ok = bool(paths) and payload.get("release_gate") == "PASS" and not bool(payload.get("hard_fail"))
        add_check(
            "windows_runtime_proof",
            ok,
            "PB-005 requires PASS Windows snap/DPI/second-monitor/path-budget/SEND-bundle proof.",
            path=paths[0] if paths else None,
        )

    return {
        "schema": "runtime_evidence_validation.v1",
        "evidence_dir": str(root),
        "updated_utc": _utc_iso(),
        "ok": not hard_fails,
        "hard_fail_count": int(len(hard_fails)),
        "hard_fails": hard_fails,
        "checks": checks,
    }
