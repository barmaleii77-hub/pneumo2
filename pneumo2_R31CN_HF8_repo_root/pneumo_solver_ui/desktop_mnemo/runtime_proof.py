from __future__ import annotations

import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


DESKTOP_MNEMO_RUNTIME_PROOF_JSON_NAME = "desktop_mnemo_runtime_proof.json"
DESKTOP_MNEMO_RUNTIME_PROOF_MD_NAME = "desktop_mnemo_runtime_proof.md"
DEFAULT_STARTUP_BUDGET_S = 3.0


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_path(path: Path | str | None) -> str:
    return str(Path(str(path)).expanduser().resolve(strict=False)) if path not in (None, "") else ""


def _read_json_object(path: Path | str, *, label: str) -> tuple[dict[str, object], list[str]]:
    try:
        obj = json.loads(Path(str(path)).read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"{label} is not readable: {type(exc).__name__}: {exc}"]
    if not isinstance(obj, dict):
        return {}, [f"{label} must be a JSON object"]
    return obj, []


def _render_proof_md(proof: dict[str, object]) -> str:
    checks = dict(proof.get("checks") or {})
    timings = dict(proof.get("timings_s") or {})
    lines = [
        "# Desktop Mnemo Runtime Proof",
        "",
        f"- status: {proof.get('status') or '-'}",
        f"- release_readiness: {proof.get('release_readiness') or '-'}",
        f"- generated_utc: {proof.get('generated_utc') or '-'}",
        f"- qt_platform: {proof.get('qt_platform') or '-'}",
        f"- offscreen: {proof.get('offscreen')}",
        f"- window_title: {proof.get('window_title') or '-'}",
        f"- dock_count: {len(proof.get('dock_object_names') or [])}",
        f"- constructor_s: {timings.get('constructor_s', '-')}",
        f"- first_event_cycle_s: {timings.get('first_event_cycle_s', '-')}",
        f"- startup_budget_s: {proof.get('startup_budget_s', '-')}",
        f"- automated_checks: {sum(1 for value in checks.values() if value is True)}/{len(checks)} true",
        "",
        "## Checks",
        "",
    ]
    for key in sorted(checks):
        lines.append(f"- {key}: {checks[key]}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This proof instantiates Desktop Mnemo and processes the first Qt event cycle.",
            "- It does not claim final Windows visual/runtime acceptance.",
            "- Real user-visible open, no-overlap inspection and hang reproduction remain operator/runtime checks.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def collect_desktop_mnemo_runtime_proof(
    *,
    npz_path: Path | str | None = None,
    follow: bool = False,
    pointer_path: Path | str | None = None,
    theme: str = "dark",
    offscreen: bool = False,
    startup_budget_s: float = DEFAULT_STARTUP_BUDGET_S,
) -> dict[str, object]:
    if offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtGui, QtWidgets

    from pneumo_solver_ui.desktop_mnemo.app import MnemoMainWindow
    from pneumo_solver_ui.desktop_mnemo.main import _default_pointer, build_desktop_mnemo_launch_contract

    app = QtWidgets.QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QtWidgets.QApplication(["desktop_mnemo_runtime_proof"])
    app.setApplicationName("DesktopMnemoRuntimeProof")
    app.setOrganizationName("UnifiedPneumoApp")

    effective_pointer = Path(str(pointer_path)).expanduser().resolve(strict=False) if pointer_path else _default_pointer()
    effective_npz = Path(str(npz_path)).expanduser().resolve(strict=False) if npz_path else None
    argv: list[str] = ["--pointer", str(effective_pointer), "--theme", str(theme)]
    if effective_npz is not None:
        argv.extend(["--npz", str(effective_npz)])
    if follow:
        argv.append("--follow")
    launch_contract = build_desktop_mnemo_launch_contract(argv)

    start = time.perf_counter()
    window = MnemoMainWindow(
        npz_path=effective_npz,
        follow=bool(follow),
        pointer_path=effective_pointer,
        theme=str(theme),
        startup_preset="runtime-proof",
        startup_title="Desktop Mnemo runtime proof",
        startup_reason="Automated startup probe without app.exec().",
        startup_view_mode="",
        startup_time_s=None,
        startup_time_label="",
        startup_edge="",
        startup_node="",
        startup_event_title="",
        startup_time_ref_npz="",
        startup_checklist=["Instantiate QMainWindow", "Process first Qt event cycle", "Close without app.exec()"],
    )
    constructor_s = time.perf_counter() - start
    try:
        window.show()
        for _ in range(8):
            app.processEvents()
        first_event_cycle_s = time.perf_counter() - start

        dock_widgets = window.findChildren(QtWidgets.QDockWidget)
        dock_object_names = sorted(dock.objectName() for dock in dock_widgets)
        menu_labels = [action.text() for action in window.menuBar().actions()]
        toolbar_actions = [
            action.text()
            for toolbar in window.findChildren(QtWidgets.QToolBar)
            for action in toolbar.actions()
            if action.text()
        ]
        layout_contract = window._build_window_layout_contract()
        expected_docks = {
            "dock_overview",
            "dock_snapshot",
            "dock_selection",
            "dock_guide",
            "dock_events",
            "dock_trends",
        }
        checks = {
            "qmainwindow_runtime": isinstance(window, QtWidgets.QMainWindow),
            "window_identity": window.objectName() == "desktop_mnemo_main_window"
            and "Мнемосхема" in window.windowTitle(),
            "launch_contract_specialized_window": launch_contract.get("window_kind")
            == "desktop_mnemo_specialized_window"
            and launch_contract.get("separate_specialized_window") is True,
            "no_domain_duplication": all(bool(value) for value in dict(launch_contract.get("does_not_duplicate") or {}).values()),
            "dock_layout_present": expected_docks.issubset(set(dock_object_names)),
            "menus_present": {"Файл", "Вид", "Анимация", "События"}.issubset(set(menu_labels)),
            "toolbar_actions_present": {"Открыть NPZ", "Следить", "Пуск"}.issubset(set(toolbar_actions)),
            "status_strip_present": hasattr(window, "status_text")
            and hasattr(window, "truth_text")
            and hasattr(window, "path_text"),
            "blank_startup_does_not_require_dataset": effective_npz is not None or window.dataset is None,
            "pointer_path_resolved": bool(str(effective_pointer)),
            "first_event_cycle_under_budget": first_event_cycle_s <= float(startup_budget_s),
            "no_event_loop_exec_required": True,
        }
        automated_status = "PASS" if all(checks.values()) else "FAIL"
        proof: dict[str, object] = {
            "schema": "desktop_mnemo_runtime_proof.v1",
            "generated_utc": _utc_iso(),
            "platform": platform.platform(),
            "python_executable": sys.executable,
            "qt_version": QtCore.qVersion(),
            "qt_platform": QtGui.QGuiApplication.platformName(),
            "offscreen": bool(offscreen),
            "startup_budget_s": float(startup_budget_s),
            "timings_s": {
                "constructor_s": round(float(constructor_s), 6),
                "first_event_cycle_s": round(float(first_event_cycle_s), 6),
            },
            "launch_contract": launch_contract,
            "window_object_name": window.objectName(),
            "window_title": window.windowTitle(),
            "dock_object_names": dock_object_names,
            "menu_labels": menu_labels,
            "toolbar_actions": toolbar_actions,
            "status_text": window.status_text.text() if hasattr(window, "status_text") else "",
            "truth_text": window.truth_text.text() if hasattr(window, "truth_text") else "",
            "dataset_loaded": window.dataset is not None,
            "follow_enabled": bool(window.follow_enabled),
            "pointer_path": str(effective_pointer),
            "npz_path": str(effective_npz) if effective_npz is not None else "",
            "layout_contract": layout_contract,
            "checks": checks,
            "status": automated_status,
            "release_readiness": "PENDING_REAL_WINDOWS_VISUAL_CHECK" if automated_status == "PASS" else "FAIL",
            "manual_verification_required": [
                "real_windows_open_does_not_hang",
                "mnemo_visual_no_overlap",
                "mnemo_close_returns_control",
            ],
        }
        return proof
    finally:
        window.close()
        app.processEvents()
        if owns_app:
            app.quit()


def validate_desktop_mnemo_runtime_proof(proof_path: Path | str) -> dict[str, object]:
    proof, errors = _read_json_object(proof_path, label="Desktop Mnemo runtime proof")
    warnings: list[str] = []
    if proof.get("schema") != "desktop_mnemo_runtime_proof.v1":
        errors.append("runtime proof schema must be desktop_mnemo_runtime_proof.v1")

    checks = proof.get("checks")
    if not isinstance(checks, dict) or not checks:
        errors.append("runtime proof checks must be a non-empty object")
        checks = {}

    required_checks = {
        "qmainwindow_runtime",
        "window_identity",
        "launch_contract_specialized_window",
        "no_domain_duplication",
        "dock_layout_present",
        "menus_present",
        "toolbar_actions_present",
        "status_strip_present",
        "blank_startup_does_not_require_dataset",
        "pointer_path_resolved",
        "first_event_cycle_under_budget",
        "no_event_loop_exec_required",
    }
    missing = sorted(required_checks - set(checks))
    failed = sorted(check_id for check_id in required_checks & set(checks) if checks.get(check_id) is not True)
    if missing:
        errors.append(f"runtime proof missing check(s): {', '.join(missing)}")
    if failed:
        errors.append(f"runtime proof failed check(s): {', '.join(failed)}")
    if proof.get("status") != "PASS":
        errors.append(f"runtime proof status is {proof.get('status') or 'missing'}, expected PASS")

    release_readiness = str(proof.get("release_readiness") or "").upper()
    if release_readiness not in {"PASS", "FAIL", "PENDING_REAL_WINDOWS_VISUAL_CHECK"}:
        errors.append(f"runtime proof release_readiness is invalid: {release_readiness or 'missing'}")
    if release_readiness == "PENDING_REAL_WINDOWS_VISUAL_CHECK":
        warnings.append("real Windows visual/no-hang verification is still pending")

    timings = proof.get("timings_s")
    if not isinstance(timings, dict):
        errors.append("runtime proof timings_s must be an object")
        timings = {}
    try:
        first_event_cycle_s = float(timings.get("first_event_cycle_s"))
        startup_budget_s = float(proof.get("startup_budget_s"))
    except Exception:
        errors.append("runtime proof startup timing values must be numeric")
        first_event_cycle_s = 0.0
        startup_budget_s = 0.0
    if startup_budget_s > 0 and first_event_cycle_s > startup_budget_s:
        errors.append(
            f"first_event_cycle_s {first_event_cycle_s:.3f} exceeds startup_budget_s {startup_budget_s:.3f}"
        )

    return {
        "schema": "desktop_mnemo_runtime_proof_validation.v1",
        "proof_path": _resolve_path(proof_path),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "automated_status": str(proof.get("status") or ""),
        "release_readiness": release_readiness,
        "missing_checks": missing,
        "failed_checks": failed,
    }


def write_desktop_mnemo_runtime_proof(
    output_dir: Path | str,
    *,
    npz_path: Path | str | None = None,
    follow: bool = False,
    pointer_path: Path | str | None = None,
    theme: str = "dark",
    offscreen: bool = False,
    startup_budget_s: float = DEFAULT_STARTUP_BUDGET_S,
) -> dict[str, object]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    proof = collect_desktop_mnemo_runtime_proof(
        npz_path=npz_path,
        follow=follow,
        pointer_path=pointer_path,
        theme=theme,
        offscreen=offscreen,
        startup_budget_s=startup_budget_s,
    )
    json_path = out_dir / DESKTOP_MNEMO_RUNTIME_PROOF_JSON_NAME
    md_path = out_dir / DESKTOP_MNEMO_RUNTIME_PROOF_MD_NAME
    proof["json_path"] = str(json_path.resolve(strict=False))
    proof["md_path"] = str(md_path.resolve(strict=False))
    json_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_proof_md(proof), encoding="utf-8")
    return {
        "schema": "desktop_mnemo_runtime_proof_output.v1",
        "json_path": str(json_path.resolve(strict=False)),
        "md_path": str(md_path.resolve(strict=False)),
        "status": str(proof.get("status") or ""),
        "release_readiness": str(proof.get("release_readiness") or ""),
        "timings_s": dict(proof.get("timings_s") or {}),
    }
