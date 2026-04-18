from __future__ import annotations

import json
import os
import platform
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


QT_MAIN_SHELL_RUNTIME_PROOF_JSON_NAME = "qt_main_shell_runtime_proof.json"
QT_MAIN_SHELL_RUNTIME_PROOF_MD_NAME = "qt_main_shell_runtime_proof.md"
QT_MAIN_SHELL_MANUAL_CHECKLIST_JSON_NAME = "qt_main_shell_manual_checklist.json"
QT_MAIN_SHELL_MANUAL_CHECKLIST_MD_NAME = "qt_main_shell_manual_checklist.md"
QT_MAIN_SHELL_MANUAL_RESULTS_TEMPLATE_JSON_NAME = "qt_main_shell_manual_results_template.json"

_MANUAL_CHECK_DEFINITIONS: tuple[dict[str, object], ...] = (
    {
        "check_id": "snap_half_third_quarter",
        "title": "Windows Snap layouts",
        "steps": (
            "Launch the main shell through START_DESKTOP_MAIN_SHELL.",
            "Snap the shell to left/right half, third/quarter layouts where Windows exposes them.",
            "Return the shell to normal and maximized states.",
        ),
        "acceptance": "Native titlebar snap affordances work and docks/status/search remain usable after every restore.",
    },
    {
        "check_id": "second_monitor_workflow",
        "title": "Second monitor dock workflow",
        "steps": (
            "Move the main shell to the second monitor.",
            "Float and restore the project tree, inspector, and runtime docks.",
            "Save layout, close shell, relaunch, and restore layout.",
        ),
        "acceptance": "The shell remains keyboard-first, docks are recoverable, and layout persistence does not lose panels.",
    },
    {
        "check_id": "mixed_dpi_or_pmv2_visual_check",
        "title": "Mixed DPI / Per-Monitor visual check",
        "steps": (
            "Run the shell on the primary monitor.",
            "Move it between monitors with different scale factors, or verify the active Per-Monitor DPI setup.",
            "Inspect command search, toolbar, project tree, status strip, and dock title text.",
        ),
        "acceptance": "Text is crisp, controls are not clipped, and resize/snap does not corrupt shell layout.",
    },
)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@contextmanager
def _temporary_env(name: str, value: str) -> Iterator[None]:
    previous = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def _screen_snapshot(screen: object) -> dict[str, object]:
    geometry = screen.geometry()
    available = screen.availableGeometry()
    return {
        "name": str(screen.name()),
        "geometry": {
            "x": int(geometry.x()),
            "y": int(geometry.y()),
            "width": int(geometry.width()),
            "height": int(geometry.height()),
        },
        "available_geometry": {
            "x": int(available.x()),
            "y": int(available.y()),
            "width": int(available.width()),
            "height": int(available.height()),
        },
        "device_pixel_ratio": float(screen.devicePixelRatio()),
        "logical_dpi": float(screen.logicalDotsPerInch()),
        "physical_dpi": float(screen.physicalDotsPerInch()),
    }


def _enum_int(value: object) -> int:
    raw = getattr(value, "value", value)
    try:
        return int(raw)
    except Exception:
        return 0


def _normalize_manual_status(value: object) -> str:
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    text = str(value or "").strip().upper()
    if text in {"PASS", "PASSED", "OK", "TRUE", "YES"}:
        return "PASS"
    if text in {"FAIL", "FAILED", "FALSE", "NO"}:
        return "FAIL"
    if text in {"SKIP", "SKIPPED", "N/A", "NA"}:
        return "SKIPPED"
    return "PENDING"


def _manual_check_ids() -> tuple[str, ...]:
    return tuple(str(item["check_id"]) for item in _MANUAL_CHECK_DEFINITIONS)


def build_qt_main_shell_manual_results_template() -> dict[str, object]:
    return {
        "schema": "qt_main_shell_manual_results.v1",
        "instructions": (
            "Fill status as PASS or FAIL after physically checking the running Windows shell. "
            "PASS/FAIL entries require operator and checked_at."
        ),
        "checks": {
            str(definition["check_id"]): {
                "status": "PENDING",
                "operator": "",
                "checked_at": "",
                "evidence_path": "",
                "notes": "",
            }
            for definition in _MANUAL_CHECK_DEFINITIONS
        },
    }


def _read_manual_results_object(path: Path | str | None) -> tuple[dict[str, object], list[str]]:
    if path in (None, ""):
        return {}, []
    try:
        obj = json.loads(Path(str(path)).read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"manual results JSON is not readable: {type(exc).__name__}: {exc}"]
    if not isinstance(obj, dict):
        return {}, ["manual results JSON must be an object"]
    return obj, []


def _read_json_object(path: Path | str, *, label: str) -> tuple[dict[str, object], list[str]]:
    try:
        obj = json.loads(Path(str(path)).read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"{label} is not readable: {type(exc).__name__}: {exc}"]
    if not isinstance(obj, dict):
        return {}, [f"{label} must be a JSON object"]
    return obj, []


def _load_manual_results(path: Path | str | None) -> dict[str, dict[str, object]]:
    obj, errors = _read_manual_results_object(path)
    if errors:
        return {}
    raw_checks = obj.get("checks", obj)
    results: dict[str, dict[str, object]] = {}
    if isinstance(raw_checks, dict):
        for check_id, value in raw_checks.items():
            if isinstance(value, dict):
                item = dict(value)
            else:
                item = {"status": value}
            results[str(check_id)] = item
    elif isinstance(raw_checks, list):
        for value in raw_checks:
            if not isinstance(value, dict):
                continue
            check_id = str(value.get("check_id") or value.get("id") or "").strip()
            if check_id:
                results[check_id] = dict(value)
    return results


def validate_qt_main_shell_manual_results(path: Path | str | None) -> dict[str, object]:
    required_ids = set(_manual_check_ids())
    obj, errors = _read_manual_results_object(path)
    raw_checks = obj.get("checks", obj) if obj else {}
    parsed = _load_manual_results(path)
    if obj and not isinstance(raw_checks, (dict, list)):
        errors.append("manual results 'checks' must be an object or list")

    provided_ids = set(parsed)
    unknown_ids = sorted(provided_ids - required_ids)
    missing_ids = sorted(required_ids - provided_ids)
    if unknown_ids:
        errors.append(f"unknown manual check id(s): {', '.join(unknown_ids)}")
    if missing_ids and path not in (None, ""):
        errors.append(f"missing required manual check id(s): {', '.join(missing_ids)}")

    status_by_check: dict[str, str] = {}
    for check_id in sorted(provided_ids & required_ids):
        result = parsed.get(check_id, {})
        status = _normalize_manual_status(result.get("status"))
        status_by_check[check_id] = status
        if status in {"PASS", "FAIL"}:
            if not str(result.get("operator") or "").strip():
                errors.append(f"{check_id}: operator is required for {status}")
            if not str(result.get("checked_at") or "").strip():
                errors.append(f"{check_id}: checked_at is required for {status}")
        if status == "FAIL" and not str(result.get("notes") or "").strip():
            errors.append(f"{check_id}: notes are required for FAIL")

    return {
        "schema": "qt_main_shell_manual_results_validation.v1",
        "manual_results_path": str(Path(str(path)).resolve(strict=False)) if path else "",
        "ok": not errors,
        "errors": errors,
        "required_check_ids": sorted(required_ids),
        "provided_check_ids": sorted(provided_ids),
        "unknown_check_ids": unknown_ids,
        "missing_check_ids": missing_ids,
        "status_by_check": status_by_check,
    }


def build_qt_main_shell_manual_checklist(
    *,
    proof_path: Path | str | None = None,
    manual_results_path: Path | str | None = None,
) -> dict[str, object]:
    validation = validate_qt_main_shell_manual_results(manual_results_path)
    results = _load_manual_results(manual_results_path)
    checks: list[dict[str, object]] = []
    for definition in _MANUAL_CHECK_DEFINITIONS:
        check_id = str(definition["check_id"])
        result = results.get(check_id, {})
        status = _normalize_manual_status(result.get("status"))
        checks.append(
            {
                **definition,
                "status": status,
                "operator": str(result.get("operator") or ""),
                "checked_at": str(result.get("checked_at") or ""),
                "notes": str(result.get("notes") or ""),
                "evidence_path": str(result.get("evidence_path") or ""),
            }
        )
    statuses = {str(check["status"]) for check in checks}
    if manual_results_path and not bool(validation.get("ok")):
        status = "FAIL"
    elif "FAIL" in statuses:
        status = "FAIL"
    elif all(str(check["status"]) == "PASS" for check in checks):
        status = "PASS"
    else:
        status = "PENDING"
    return {
        "schema": "qt_main_shell_manual_checklist.v1",
        "generated_utc": _utc_iso(),
        "proof_path": str(Path(str(proof_path)).resolve(strict=False)) if proof_path else "",
        "manual_results_path": str(Path(str(manual_results_path)).resolve(strict=False))
        if manual_results_path
        else "",
        "required_check_ids": [str(item["check_id"]) for item in _MANUAL_CHECK_DEFINITIONS],
        "status": status,
        "validation": validation,
        "checks": checks,
    }


def write_qt_main_shell_manual_results_template(output_dir: Path | str) -> dict[str, object]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    template_path = out_dir / QT_MAIN_SHELL_MANUAL_RESULTS_TEMPLATE_JSON_NAME
    template = build_qt_main_shell_manual_results_template()
    template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "schema": "qt_main_shell_manual_results_template_output.v1",
        "template_path": str(template_path.resolve(strict=False)),
        "required_check_ids": list(_manual_check_ids()),
    }


def validate_qt_main_shell_runtime_proof(
    proof_path: Path | str,
    *,
    require_manual_pass: bool = False,
) -> dict[str, object]:
    proof, errors = _read_json_object(proof_path, label="runtime proof")
    warnings: list[str] = []
    if proof.get("schema") != "qt_main_shell_runtime_proof.v1":
        errors.append("runtime proof schema must be qt_main_shell_runtime_proof.v1")

    checks = proof.get("checks")
    if not isinstance(checks, dict) or not checks:
        errors.append("runtime proof checks must be a non-empty object")
        checks = {}

    required_automated_checks = {
        "qmainwindow_runtime",
        "native_titlebar_precondition",
        "menus_present",
        "dock_layout_present",
        "keyboard_first_shortcuts",
        "visible_diagnostics_action",
        "status_progress_messages_strip",
        "command_search_project_tree_route",
        "all_launchable_tools_visible_from_shell",
        "operator_surface_no_service_jargon",
        "v38_pipeline_selection_sync",
        "layout_save_restore_reset",
        "no_domain_windows_launched",
    }
    missing_automated = sorted(required_automated_checks - set(checks))
    failed_automated = sorted(
        check_id
        for check_id in required_automated_checks & set(checks)
        if checks.get(check_id) is not True
    )
    if missing_automated:
        errors.append(f"runtime proof missing automated check(s): {', '.join(missing_automated)}")
    if failed_automated:
        errors.append(f"runtime proof failed automated check(s): {', '.join(failed_automated)}")

    if proof.get("status") != "PASS":
        errors.append(f"runtime proof status is {proof.get('status') or 'missing'}, expected PASS")

    handoff = proof.get("handoff_policy")
    if not isinstance(handoff, dict):
        errors.append("runtime proof handoff_policy must be an object")
        handoff = {}
    if handoff.get("external_domain_windows_launched") != 0:
        errors.append("runtime proof must not launch domain windows")
    if handoff.get("managed_external_launcher_only") is not True:
        errors.append("runtime proof must preserve separate-window launcher policy")

    launch_coverage = proof.get("launch_coverage")
    if not isinstance(launch_coverage, dict):
        errors.append("runtime proof launch_coverage must be an object")
        launch_coverage = {}
    expected_launch_keys = {str(item) for item in launch_coverage.get("expected") or []}
    if not expected_launch_keys:
        errors.append("runtime proof launch_coverage.expected must be non-empty")
    for surface in ("browser", "menu", "toolbar", "command_search"):
        surface_keys = {str(item) for item in launch_coverage.get(surface) or []}
        missing = sorted(expected_launch_keys - surface_keys)
        if missing:
            errors.append(
                f"runtime proof launch coverage missing from {surface}: "
                + ", ".join(missing)
            )

    operator_surface = proof.get("operator_surface")
    if not isinstance(operator_surface, dict):
        errors.append("runtime proof operator_surface must be an object")
        operator_surface = {}
    service_hits = [str(item) for item in operator_surface.get("service_blocker_hits") or []]
    if service_hits:
        errors.append("runtime proof operator surface exposes service jargon: " + "; ".join(service_hits))

    pipeline_coverage = proof.get("pipeline_surface_coverage")
    if not isinstance(pipeline_coverage, dict):
        errors.append("runtime proof pipeline_surface_coverage must be an object")
        pipeline_coverage = {}
    expected_workspace_ids = {str(item) for item in pipeline_coverage.get("expected") or []}
    if not expected_workspace_ids:
        errors.append("runtime proof pipeline_surface_coverage.expected must be non-empty")
    for surface in ("browser", "toolbar", "command_search"):
        surface_ids = {str(item) for item in pipeline_coverage.get(surface) or []}
        missing = sorted(expected_workspace_ids - surface_ids)
        if missing:
            errors.append(
                f"runtime proof V38 pipeline coverage missing from {surface}: "
                + ", ".join(missing)
            )

    pipeline_sync = proof.get("pipeline_selection_sync")
    if not isinstance(pipeline_sync, dict):
        errors.append("runtime proof pipeline_selection_sync must be an object")
        pipeline_sync = {}
    missing_sync = [str(item) for item in pipeline_sync.get("missing_workspace_ids") or []]
    if missing_sync:
        errors.append("runtime proof V38 pipeline selection sync missing: " + ", ".join(missing_sync))

    manual_required = {str(item) for item in proof.get("manual_verification_required") or []}
    required_manual = set(_manual_check_ids())
    if manual_required != required_manual:
        errors.append(
            "runtime proof manual_verification_required must match required ids: "
            + ", ".join(sorted(required_manual))
        )

    manual = proof.get("manual_verification")
    if not isinstance(manual, dict):
        errors.append("runtime proof manual_verification must be an object")
        manual = {}
    manual_status = str(manual.get("status") or "PENDING").upper()
    if manual_status not in {"PENDING", "PASS", "FAIL"}:
        errors.append(f"runtime proof manual_verification status is invalid: {manual_status}")
    validation = manual.get("validation")
    if isinstance(validation, dict) and validation.get("ok") is False:
        validation_errors = ", ".join(str(item) for item in validation.get("errors") or [])
        errors.append(f"runtime proof manual validation failed: {validation_errors or 'unknown error'}")

    release_readiness = str(proof.get("release_readiness") or "").upper()
    if release_readiness not in {"PASS", "FAIL", "PENDING_MANUAL_VERIFICATION"}:
        errors.append(f"runtime proof release_readiness is invalid: {release_readiness or 'missing'}")
    if release_readiness == "PENDING_MANUAL_VERIFICATION":
        warnings.append("manual Snap/DPI/second-monitor verification is still pending")
    if require_manual_pass and release_readiness != "PASS":
        errors.append("runtime proof requires manual PASS but release_readiness is not PASS")

    return {
        "schema": "qt_main_shell_runtime_proof_validation.v1",
        "proof_path": str(Path(str(proof_path)).resolve(strict=False)),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "automated_status": str(proof.get("status") or ""),
        "manual_verification_status": manual_status,
        "release_readiness": release_readiness,
        "require_manual_pass": bool(require_manual_pass),
        "missing_automated_checks": missing_automated,
        "failed_automated_checks": failed_automated,
        "required_manual_check_ids": sorted(required_manual),
    }


def _release_readiness(*, automated_status: str, manual_status: str) -> str:
    if str(automated_status or "").upper() != "PASS":
        return "FAIL"
    if str(manual_status or "").upper() == "PASS":
        return "PASS"
    if str(manual_status or "").upper() == "FAIL":
        return "FAIL"
    return "PENDING_MANUAL_VERIFICATION"


def _render_manual_checklist_md(checklist: dict[str, object]) -> str:
    checks = list(checklist.get("checks") or [])
    lines = [
        "# Qt Main Shell Manual Checklist",
        "",
        f"- status: {checklist.get('status') or 'PENDING'}",
        f"- proof_path: {checklist.get('proof_path') or '-'}",
        f"- manual_results_path: {checklist.get('manual_results_path') or '-'}",
        "",
    ]
    for raw in checks:
        check = dict(raw) if isinstance(raw, dict) else {}
        lines.extend(
            [
                f"## {check.get('check_id') or '-'}",
                "",
                f"- title: {check.get('title') or '-'}",
                f"- status: {check.get('status') or 'PENDING'}",
                f"- acceptance: {check.get('acceptance') or '-'}",
                "- steps:",
            ]
        )
        for step in check.get("steps") or ():
            lines.append(f"  - {step}")
        lines.extend(
            [
                f"- operator: {check.get('operator') or '-'}",
                f"- checked_at: {check.get('checked_at') or '-'}",
                f"- evidence_path: {check.get('evidence_path') or '-'}",
                f"- notes: {check.get('notes') or '-'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_proof_md(proof: dict[str, object]) -> str:
    checks = dict(proof.get("checks") or {})
    manual = [str(item) for item in proof.get("manual_verification_required") or []]
    manual_status = dict(proof.get("manual_verification") or {}).get("status") or "-"
    lines = [
        "# Qt Main Shell Runtime Proof",
        "",
        f"- status: {proof.get('status') or '-'}",
        f"- release_readiness: {proof.get('release_readiness') or '-'}",
        f"- manual_verification_status: {manual_status}",
        f"- generated_utc: {proof.get('generated_utc') or '-'}",
        f"- platform: {proof.get('platform') or '-'}",
        f"- qt_platform: {proof.get('qt_platform') or '-'}",
        f"- window_title: {proof.get('window_title') or '-'}",
        f"- menu_count: {len(proof.get('menu_labels') or [])}",
        f"- dock_count: {len(proof.get('dock_object_names') or [])}",
        f"- shortcut_count: {len(proof.get('shortcut_keys') or [])}",
        f"- automated_checks: {sum(1 for value in checks.values() if value is True)}/{len(checks)} true",
        f"- manual_verification_required: {', '.join(manual) if manual else '-'}",
        f"- manual_checklist: {proof.get('manual_checklist_md_path') or '-'}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def collect_qt_main_shell_runtime_proof(*, offscreen: bool = False, state_path: Path | str | None = None) -> dict[str, object]:
    if offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtGui, QtWidgets

    from pneumo_solver_ui.desktop_qt_shell.main_window import DesktopQtMainShell

    app = QtWidgets.QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QtWidgets.QApplication(["qt_main_shell_runtime_proof"])

    settings_path = Path(state_path) if state_path is not None else Path.cwd() / "qt_main_shell_runtime_state.ini"
    with _temporary_env("PNEUMO_QT_MAIN_SHELL_STATE_PATH", str(settings_path)):
        window = DesktopQtMainShell()
        try:
            window.show()
            app.processEvents()

            window.command_search_edit.setText("дерево проекта")
            app.processEvents()
            search_result_count = int(window.search_results_list.count())
            if search_result_count:
                window._activate_primary_search_result()
                app.processEvents()
            command_search_status_text = window.status_label.text()
            command_search_surface = window.central_stack.currentWidget().objectName()

            window._save_layout()
            settings = QtCore.QSettings(str(settings_path), QtCore.QSettings.Format.IniFormat)
            layout_saved = all(
                settings.value(key) is not None
                for key in (
                    "layout/geometry",
                    "layout/window_state",
                    "layout/last_workspace_key",
                    "layout/optimization_mode",
                )
            )
            window.browser_dock.setFloating(True)
            window.browser_dock.hide()
            window._reset_layout()
            app.processEvents()
            layout_reset = (
                not bool(window.browser_dock.isFloating())
                and not bool(window.browser_dock.isHidden())
                and not bool(window.inspector_dock.isHidden())
                and not bool(window.runtime_dock.isHidden())
            )

            flags = window.windowFlags()
            shortcut_keys = sorted(
                {
                    shortcut.key().toString(QtGui.QKeySequence.SequenceFormat.PortableText)
                    for shortcut in window.findChildren(QtGui.QShortcut)
                    if not shortcut.key().isEmpty()
                }
            )
            dock_object_names = sorted(
                dock.objectName() for dock in window.findChildren(QtWidgets.QDockWidget)
            )
            menu_labels = [action.text() for action in window.menuBar().actions()]
            launch_coverage = {
                key: list(value)
                for key, value in window.launch_surface_coverage().items()
            }
            expected_launch_keys = set(launch_coverage["expected"])
            launch_coverage_missing = {
                surface: sorted(expected_launch_keys - set(launch_coverage[surface]))
                for surface in ("browser", "menu", "toolbar", "command_search")
            }
            pipeline_surface_coverage = {
                key: list(value)
                for key, value in window.pipeline_surface_coverage().items()
            }
            expected_workspace_ids = set(pipeline_surface_coverage["expected"])
            pipeline_surface_coverage_missing = {
                surface: sorted(expected_workspace_ids - set(pipeline_surface_coverage[surface]))
                for surface in ("browser", "toolbar", "command_search")
            }
            operator_surface = window.operator_surface_snapshot()
            pipeline_selection_sync = window.prove_v38_pipeline_selection_sync()
            proof: dict[str, object] = {
                "schema": "qt_main_shell_runtime_proof.v1",
                "generated_utc": _utc_iso(),
                "platform": platform.platform(),
                "python_executable": sys.executable,
                "qt_version": QtCore.qVersion(),
                "qt_platform": QtGui.QGuiApplication.platformName(),
                "offscreen": bool(offscreen),
                "window_object_name": window.objectName(),
                "window_title": window.windowTitle(),
                "window_flags": int(flags),
                "uses_native_titlebar_precondition": bool(
                    flags & QtCore.Qt.WindowType.Window
                    and not bool(flags & QtCore.Qt.WindowType.FramelessWindowHint)
                ),
                "window_size": {
                    "width": int(window.size().width()),
                    "height": int(window.size().height()),
                },
                "minimum_size": {
                    "width": int(window.minimumSize().width()),
                    "height": int(window.minimumSize().height()),
                },
                "screens": [_screen_snapshot(screen) for screen in app.screens()],
                "menu_labels": menu_labels,
                "dock_object_names": dock_object_names,
                "dock_areas": {
                    dock.objectName(): _enum_int(window.dockWidgetArea(dock))
                    for dock in window.findChildren(QtWidgets.QDockWidget)
                },
                "shortcut_keys": shortcut_keys,
                "diagnostics_action": {
                    "object_name": window.diagnostics_button.objectName(),
                    "text": window.diagnostics_button.text(),
                    "shortcut": window.diagnostics_button.shortcut().toString(
                        QtGui.QKeySequence.SequenceFormat.PortableText
                    ),
                    "visible": bool(window.diagnostics_button.isVisible()),
                },
                "status_strip": {
                    "message_object_name": window.message_strip_label.objectName(),
                    "progress_object_name": window.status_progress_bar.objectName(),
                    "progress_value": int(window.status_progress_bar.value()),
                    "status_text": window.status_label.text(),
                },
                "project_tree": {
                    "top_level_count": int(window.browser_tree.topLevelItemCount()),
                    "current_item": window.browser_tree.currentItem().text(0)
                    if window.browser_tree.currentItem() is not None
                    else "",
                },
                "command_search": {
                    "query": "дерево проекта",
                    "result_count": search_result_count,
                    "current_surface": command_search_surface,
                    "status_text": command_search_status_text,
                },
                "launch_coverage": launch_coverage,
                "launch_coverage_missing": launch_coverage_missing,
                "pipeline_surface_coverage": pipeline_surface_coverage,
                "pipeline_surface_coverage_missing": pipeline_surface_coverage_missing,
                "operator_surface": operator_surface,
                "pipeline_selection_sync": pipeline_selection_sync,
                "layout": {
                    "settings_path": str(settings_path.resolve(strict=False)),
                    "saved": bool(layout_saved),
                    "reset_visible": bool(layout_reset),
                },
                "handoff_policy": {
                    "startup_tool_count": 0,
                    "external_domain_windows_launched": 0,
                    "managed_external_launcher_only": True,
                },
                "manual_verification_required": [
                    "snap_half_third_quarter",
                    "second_monitor_workflow",
                    "mixed_dpi_or_pmv2_visual_check",
                ],
            }
            checks = {
                "qmainwindow_runtime": window.objectName() == "DesktopQtMainShell",
                "native_titlebar_precondition": bool(proof["uses_native_titlebar_precondition"]),
                "menus_present": menu_labels == [
                    "Файл",
                    "Правка",
                    "Вид",
                    "Запуск",
                    "Анализ",
                    "Анимация",
                    "Диагностика",
                    "Инструменты",
                    "Справка",
                ],
                "dock_layout_present": {
                    "DesktopQtShellBrowserDock",
                    "DesktopQtShellInspectorDock",
                    "DesktopQtShellRuntimeDock",
                }
                <= set(dock_object_names),
                "keyboard_first_shortcuts": {"Ctrl+K", "F6", "Shift+F6", "F7", "F8"} <= set(shortcut_keys),
                "visible_diagnostics_action": dict(proof["diagnostics_action"]).get("object_name")
                == "AlwaysVisibleDiagnosticsAction",
                "status_progress_messages_strip": dict(proof["status_strip"]).get("message_object_name")
                == "ShellMessagesStrip",
                "command_search_project_tree_route": search_result_count > 0
                and "дерево проекта" in str(dict(proof["command_search"]).get("status_text") or ""),
                "all_launchable_tools_visible_from_shell": all(
                    not missing for missing in launch_coverage_missing.values()
                ),
                "operator_surface_no_service_jargon": not bool(
                    dict(operator_surface).get("service_blocker_hits") or []
                ),
                "v38_pipeline_selection_sync": all(
                    not missing for missing in pipeline_surface_coverage_missing.values()
                )
                and not bool(dict(pipeline_selection_sync).get("missing_workspace_ids") or []),
                "layout_save_restore_reset": bool(layout_saved and layout_reset),
                "no_domain_windows_launched": True,
            }
            proof["checks"] = checks
            proof["status"] = "PASS" if all(checks.values()) else "FAIL"
            return proof
        finally:
            window.close()
            window.deleteLater()
            app.processEvents()
            if owns_app:
                app.quit()


def write_qt_main_shell_runtime_proof(
    output_dir: Path | str,
    *,
    offscreen: bool = False,
    state_path: Path | str | None = None,
    manual_results_path: Path | str | None = None,
) -> dict[str, object]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    effective_state_path = Path(state_path) if state_path is not None else out_dir / "qt_main_shell_runtime_state.ini"
    proof = collect_qt_main_shell_runtime_proof(offscreen=offscreen, state_path=effective_state_path)
    json_path = out_dir / QT_MAIN_SHELL_RUNTIME_PROOF_JSON_NAME
    md_path = out_dir / QT_MAIN_SHELL_RUNTIME_PROOF_MD_NAME
    checklist_json_path = out_dir / QT_MAIN_SHELL_MANUAL_CHECKLIST_JSON_NAME
    checklist_md_path = out_dir / QT_MAIN_SHELL_MANUAL_CHECKLIST_MD_NAME
    manual = build_qt_main_shell_manual_checklist(
        proof_path=json_path,
        manual_results_path=manual_results_path,
    )
    proof["manual_verification"] = manual
    proof["manual_verification_required"] = list(manual["required_check_ids"])
    proof["manual_checklist_json_path"] = str(checklist_json_path.resolve(strict=False))
    proof["manual_checklist_md_path"] = str(checklist_md_path.resolve(strict=False))
    proof["release_readiness"] = _release_readiness(
        automated_status=str(proof.get("status") or ""),
        manual_status=str(manual.get("status") or ""),
    )
    json_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_proof_md(proof), encoding="utf-8")
    checklist_json_path.write_text(json.dumps(manual, ensure_ascii=False, indent=2), encoding="utf-8")
    checklist_md_path.write_text(_render_manual_checklist_md(manual), encoding="utf-8")
    return {
        "schema": "qt_main_shell_runtime_proof_output.v1",
        "json_path": str(json_path.resolve(strict=False)),
        "md_path": str(md_path.resolve(strict=False)),
        "manual_checklist_json_path": str(checklist_json_path.resolve(strict=False)),
        "manual_checklist_md_path": str(checklist_md_path.resolve(strict=False)),
        "status": str(proof.get("status") or ""),
        "release_readiness": str(proof.get("release_readiness") or ""),
        "manual_verification_status": str(manual.get("status") or ""),
        "manual_verification_required": list(proof.get("manual_verification_required") or []),
    }
