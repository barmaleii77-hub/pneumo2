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
DEFAULT_CLOSE_BUDGET_S = 1.0


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
        f"- close_s: {timings.get('close_s', '-')}",
        f"- startup_budget_s: {proof.get('startup_budget_s', '-')}",
        f"- close_budget_s: {proof.get('close_budget_s', '-')}",
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
            "- It also closes the window through Qt and verifies that local Desktop Mnemo timers stop.",
            "- It does not claim final Windows visual/runtime acceptance.",
            "- Real user-visible open, no-overlap inspection and hang reproduction remain operator/runtime checks.",
        ]
    )
    manual = [str(item) for item in list(proof.get("manual_verification_required") or [])]
    if manual:
        lines.extend(["", "## Manual Verification Still Required", ""])
        lines.extend(f"- {item}" for item in manual)
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
    closed_in_proof = False
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
        window_rect = window.geometry()
        native_canvas = window.mnemo_view.native_canvas
        native_canvas_size = native_canvas.size()
        status_text = window.status_text.text() if hasattr(window, "status_text") else ""
        truth_text = window.truth_text.text() if hasattr(window, "truth_text") else ""
        status_label_visible = bool(hasattr(window, "status_text") and window.status_text.isVisible())
        truth_label_visible = bool(hasattr(window, "truth_text") and window.truth_text.isVisible())
        path_label_visible = bool(hasattr(window, "path_text") and window.path_text.isVisible())
        blocking_modal_dialogs = [
            str(widget.objectName() or widget.windowTitle() or type(widget).__name__)
            for widget in app.topLevelWidgets()
            if isinstance(widget, QtWidgets.QDialog)
            and widget.isVisible()
            and widget.windowModality() != QtCore.Qt.NonModal
        ]

        close_start = time.perf_counter()
        window.close()
        closed_in_proof = True
        for _ in range(8):
            app.processEvents()
        close_s = time.perf_counter() - close_start
        play_timer_active_after_close = bool(
            hasattr(window, "play_timer") and window.play_timer is not None and window.play_timer.isActive()
        )
        pointer_watcher = getattr(window, "pointer_watcher", None)
        pointer_timer = getattr(pointer_watcher, "_timer", None)
        pointer_timer_active_after_close = bool(pointer_timer is not None and pointer_timer.isActive())
        window_visible_after_close = bool(window.isVisible())
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
            "visible_window_geometry": bool(window_rect.width() > 0 and window_rect.height() > 0),
            "native_canvas_size_present": bool(native_canvas_size.width() > 0 and native_canvas_size.height() > 0),
            "status_truth_text_visible": bool(status_label_visible and truth_label_visible and truth_text),
            "blank_startup_unavailable_truth_visible": effective_npz is not None
            or (window.dataset is None and truth_text == "Mnemo: unavailable pressure/state" and truth_label_visible),
            "blank_startup_does_not_claim_confirmed_truth": effective_npz is not None
            or truth_text != "Mnemo: confirmed",
            "no_blocking_modal_visible": not blocking_modal_dialogs,
            "pointer_path_resolved": bool(str(effective_pointer)),
            "first_event_cycle_under_budget": first_event_cycle_s <= float(startup_budget_s),
            "close_returns_control_under_budget": close_s <= DEFAULT_CLOSE_BUDGET_S,
            "window_hidden_after_close": not window_visible_after_close,
            "playback_timer_stopped_after_close": not play_timer_active_after_close,
            "pointer_watcher_stopped_after_close": not pointer_timer_active_after_close,
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
            "close_budget_s": DEFAULT_CLOSE_BUDGET_S,
            "timings_s": {
                "constructor_s": round(float(constructor_s), 6),
                "first_event_cycle_s": round(float(first_event_cycle_s), 6),
                "close_s": round(float(close_s), 6),
            },
            "launch_contract": launch_contract,
            "window_object_name": window.objectName(),
            "window_title": window.windowTitle(),
            "window_geometry": {
                "x": int(window_rect.x()),
                "y": int(window_rect.y()),
                "width": int(window_rect.width()),
                "height": int(window_rect.height()),
            },
            "native_canvas_size": {
                "width": int(native_canvas_size.width()),
                "height": int(native_canvas_size.height()),
            },
            "dock_object_names": dock_object_names,
            "menu_labels": menu_labels,
            "toolbar_actions": toolbar_actions,
            "status_text": status_text,
            "truth_text": truth_text,
            "status_strip_visibility": {
                "status_text_visible": status_label_visible,
                "truth_text_visible": truth_label_visible,
                "path_text_visible": path_label_visible,
            },
            "dataset_loaded": window.dataset is not None,
            "follow_enabled": bool(window.follow_enabled),
            "pointer_path": str(effective_pointer),
            "npz_path": str(effective_npz) if effective_npz is not None else "",
            "layout_contract": layout_contract,
            "blocking_modal_dialogs": blocking_modal_dialogs,
            "close_state": {
                "window_visible_after_close": window_visible_after_close,
                "playback_timer_active_after_close": play_timer_active_after_close,
                "pointer_watcher_timer_active_after_close": pointer_timer_active_after_close,
            },
            "checks": checks,
            "status": automated_status,
            "release_readiness": "PENDING_REAL_WINDOWS_VISUAL_CHECK" if automated_status == "PASS" else "FAIL",
            "manual_verification_required": [
                "real_windows_open_does_not_hang",
                "real_windows_resize_no_overlap",
                "windows_snap_restore",
                "mnemo_dock_overlap_inspection",
                "mnemo_scheme_readability",
                "unavailable_truth_state_visible",
                "mnemo_visual_no_overlap",
                "mnemo_close_returns_control",
                "second_monitor_if_available",
                "mixed_dpi_if_available",
                "long_running_follow_playback_stability",
            ],
            "non_closure": [
                "final_windows_visual_acceptance_without_manual_evidence",
                "snap_layouts_second_monitor_mixed_dpi_long_running_stability",
                "producer_truth_geometry_packaging_animator_compare_shell_diagnostics_send",
                "OG-001_through_OG-006",
            ],
        }
        return proof
    finally:
        if not closed_in_proof:
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
        "visible_window_geometry",
        "native_canvas_size_present",
        "status_truth_text_visible",
        "blank_startup_unavailable_truth_visible",
        "blank_startup_does_not_claim_confirmed_truth",
        "no_blocking_modal_visible",
        "pointer_path_resolved",
        "first_event_cycle_under_budget",
        "close_returns_control_under_budget",
        "window_hidden_after_close",
        "playback_timer_stopped_after_close",
        "pointer_watcher_stopped_after_close",
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
    try:
        close_s = float(timings.get("close_s"))
        close_budget_s = float(proof.get("close_budget_s"))
    except Exception:
        errors.append("runtime proof close timing values must be numeric")
        close_s = 0.0
        close_budget_s = 0.0
    if close_budget_s > 0 and close_s > close_budget_s:
        errors.append(f"close_s {close_s:.3f} exceeds close_budget_s {close_budget_s:.3f}")

    manual_required = {str(item) for item in list(proof.get("manual_verification_required") or [])}
    required_manual = {
        "real_windows_open_does_not_hang",
        "real_windows_resize_no_overlap",
        "windows_snap_restore",
        "mnemo_dock_overlap_inspection",
        "mnemo_scheme_readability",
        "unavailable_truth_state_visible",
        "mnemo_visual_no_overlap",
        "mnemo_close_returns_control",
        "second_monitor_if_available",
        "mixed_dpi_if_available",
        "long_running_follow_playback_stability",
    }
    missing_manual = sorted(required_manual - manual_required)
    if missing_manual:
        errors.append(f"runtime proof missing manual verification item(s): {', '.join(missing_manual)}")

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
        "missing_manual_verification": missing_manual,
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
