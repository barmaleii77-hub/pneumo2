from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

from PySide6 import QtCore, QtWidgets

from pneumo_solver_ui.desktop_diagnostics_model import (
    DesktopDiagnosticsBundleRecord,
    DesktopDiagnosticsRequest,
    DesktopDiagnosticsRunRecord,
    build_run_full_diagnostics_command,
    now_local_iso,
    parse_run_full_diagnostics_output_line,
    path_str,
)
from pneumo_solver_ui.desktop_diagnostics_runtime import (
    append_desktop_diagnostics_run_log,
    load_desktop_diagnostics_bundle_record,
    load_last_desktop_diagnostics_center_state,
    load_last_desktop_diagnostics_run_log_text,
    load_last_desktop_diagnostics_run_record,
    persist_desktop_diagnostics_run,
    refresh_desktop_diagnostics_bundle_record,
    write_desktop_diagnostics_center_state,
    write_desktop_diagnostics_summary_md,
)
from pneumo_solver_ui.desktop_shell.external_launch import spawn_module
from pneumo_solver_ui.optimization_baseline_source import baseline_center_evidence_payload

from .catalogs import get_tooltip, get_ui_element
from .contracts import DesktopWorkspaceSpec
from .help_registry import _operator_text
from .v16_guidance_widgets import build_v16_visibility_priority_box
from .v19_guidance_widgets import build_v19_action_feedback_box
from .workspace_runtime import build_diagnostics_workspace_summary


def _guess_python_exe(repo_root: Path) -> Path:
    if sys.platform.startswith("win"):
        venv = repo_root / ".venv" / "Scripts"
        pyw = venv / "pythonw.exe"
        py = venv / "python.exe"
        if pyw.exists():
            return pyw
        if py.exists():
            return py
    return Path(sys.executable)


def _open_in_explorer(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])  # noqa: S603,S607
        else:
            subprocess.Popen(["xdg-open", str(path)])  # noqa: S603,S607
    except Exception:
        pass


def _apply_action_contract(widget: QtWidgets.QWidget, element_id: str) -> None:
    element = get_ui_element(element_id)
    if element is None:
        return
    widget.setObjectName(element.automation_id or element.element_id)
    widget.setAccessibleName(element.title)
    tooltip = get_tooltip(element.tooltip_id)
    if tooltip is not None and tooltip.text:
        widget.setToolTip(_operator_text(tooltip.text))


def _safe_path_text(path: str) -> str:
    text = str(path or "").strip()
    return text if text else "нет данных"


def _operator_message_text(raw: str) -> str:
    text = str(raw or "").strip()
    replacements = (
        ("Clipboard status is stale for the current latest bundle:", "Буфер обмена устарел для текущего последнего архива:"),
        ("Clipboard updated for latest bundle:", "Буфер обмена обновлён для последнего архива:"),
        ("no clipboard activity", "буфер обмена не использовался"),
        ("inspection", "проверка состава"),
        ("health", "состояние проекта"),
        ("validation", "проверка результата"),
        ("triage", "разбор предупреждений"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _bool_marker(value: bool | None) -> str:
    if value is None:
        return "нет данных"
    return "да" if value else "нет"


def _state_text(raw: Any, *, fallback: str = "нет данных") -> str:
    text = " ".join(str(raw or "").replace("_", " ").split()).strip()
    if not text:
        return fallback
    labels = {
        "current": "актуален",
        "historical mismatch": "расходится с историей",
        "missing": "не найден",
        "none": "нет расхождений",
        "ok": "готово",
        "ready": "готово",
        "running": "выполняется",
        "failed": "ошибка",
        "completed": "завершено",
    }
    return labels.get(text.casefold(), text)


def _request_level_text(raw: Any) -> str:
    labels = {
        "minimal": "минимальная",
        "standard": "обычная",
        "full": "полная",
    }
    text = str(raw or "").strip().lower()
    return labels.get(text, "обычная")


def _baseline_attention_required(evidence: dict[str, Any]) -> bool:
    active = dict(evidence.get("active_baseline") or {})
    active_state = str(active.get("state") or "").strip()
    mismatch = dict(evidence.get("mismatch_state") or {})
    return bool(
        evidence.get("send_bundle_should_include", False)
        or active_state != "current"
        or str(mismatch.get("state") or "") == "historical_mismatch"
    )


def _baseline_status_text(evidence: dict[str, Any]) -> str:
    if not evidence:
        return "Сведения об опорном прогоне недоступны."
    active = dict(evidence.get("active_baseline") or {})
    banner = dict(evidence.get("banner_state") or {})
    mismatch = dict(evidence.get("mismatch_state") or {})
    active_state = _state_text(active.get("state") or banner.get("active_state"), fallback="не найден")
    active_hash = str(active.get("active_baseline_hash") or "")
    mismatch_state = _state_text(mismatch.get("state") or banner.get("selected_compare_state"), fallback="нет расхождений")
    banner_text = str(banner.get("banner") or active.get("banner") or "")
    lines = [
        f"Опорный прогон {active_state}.",
        (
            f"Метка прогона - {active_hash[:12]}."
            if active_hash
            else "Метка прогона пока отсутствует."
        ),
        f"Сверка истории: {mismatch_state}. Добавить сведения в архив: {_bool_marker(bool(evidence.get('send_bundle_should_include', False)))}.",
        "Молчаливая подмена запрещена.",
    ]
    if banner_text:
        lines.append(f"Причина: {banner_text}")
    return "\n".join(lines)


def _restore_request_from_center_state(
    repo_root: Path,
    bundle: DesktopDiagnosticsBundleRecord,
) -> DesktopDiagnosticsRequest:
    state = load_last_desktop_diagnostics_center_state(bundle.out_dir)
    ui = state.get("ui") if isinstance(state.get("ui"), dict) else state
    ui = ui if isinstance(ui, dict) else {}

    def _bool(name: str, default: bool) -> bool:
        value = ui.get(name)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "y", "on"}:
                return True
            if lowered in {"0", "false", "no", "n", "off"}:
                return False
        return default

    def _int(name: str, default: int) -> int:
        try:
            return int(ui.get(name))
        except Exception:
            return default

    level = str(ui.get("level") or "full").strip().lower()
    if level not in {"minimal", "standard", "full"}:
        level = "full"
    elif level == "standard":
        # The hosted GUI-spec lane runs the full diagnostics contract by default.
        # Older Tk center state may persist "standard"; do not let that downgrade
        # the always-visible diagnostics workspace.
        level = "full"

    osc_dir = str(ui.get("osc_dir") or "").strip()
    if osc_dir:
        try:
            if not Path(osc_dir).expanduser().exists():
                osc_dir = ""
        except Exception:
            osc_dir = ""

    out_root = str(ui.get("out_root") or "").strip()
    if not out_root:
        out_root = path_str((repo_root / "diagnostics").resolve())

    return DesktopDiagnosticsRequest(
        level=level,
        skip_ui_smoke=_bool("skip_ui_smoke", False),
        no_zip=_bool("no_zip", False),
        run_opt_smoke=_bool("run_opt_smoke", False),
        opt_minutes=max(1, _int("opt_minutes", 2)),
        opt_jobs=max(1, _int("opt_jobs", 2)),
        osc_dir=osc_dir,
        out_root=out_root,
    )


@dataclass(slots=True)
class DiagnosticsWorkspaceSnapshot:
    bundle: DesktopDiagnosticsBundleRecord
    run_record: DesktopDiagnosticsRunRecord | None
    run_log_text: str
    request: DesktopDiagnosticsRequest
    request_source: str
    summary_headline: str
    summary_detail: str
    summary_lines: tuple[str, ...]
    center_state_path: str
    summary_md_path: str
    recommended_next_step: str
    baseline_evidence: dict[str, Any]
    baseline_attention_required: bool
    baseline_status_text: str
    is_busy: bool
    status_text: str


class DiagnosticsShellController(QtCore.QObject):
    snapshot_changed = QtCore.Signal(object)
    shell_status_changed = QtCore.Signal(str, bool)

    def __init__(
        self,
        repo_root: Path,
        *,
        spawn_module_fn: Callable[[str], object] = spawn_module,
        open_path_fn: Callable[[Path], None] = _open_in_explorer,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.repo_root = Path(repo_root).resolve()
        self.tools_dir = self.repo_root / "pneumo_solver_ui" / "tools"
        self.spawn_module_fn = spawn_module_fn
        self.open_path_fn = open_path_fn
        self._process = QtCore.QProcess(self)
        self._process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_ready_read)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_process_error)

        self._buffered_log = ""
        self._current_request: DesktopDiagnosticsRequest | None = None
        self._current_run_record: DesktopDiagnosticsRunRecord | None = None
        self._current_bundle: DesktopDiagnosticsBundleRecord | None = None
        self._current_snapshot: DiagnosticsWorkspaceSnapshot | None = None
        self._status_text = "Готово. Проверка проекта и архив доступны в текущем рабочем шаге."

    @property
    def current_snapshot(self) -> DiagnosticsWorkspaceSnapshot | None:
        return self._current_snapshot

    def is_busy(self) -> bool:
        return self._process.state() != QtCore.QProcess.NotRunning

    def refresh(self, *, regenerate_reports: bool = False) -> DiagnosticsWorkspaceSnapshot:
        bundle = (
            refresh_desktop_diagnostics_bundle_record(self.repo_root)
            if regenerate_reports
            else load_desktop_diagnostics_bundle_record(self.repo_root)
        )
        request = _restore_request_from_center_state(self.repo_root, bundle)
        run_record = load_last_desktop_diagnostics_run_record(request.resolved_out_root(self.repo_root))
        run_log_text = load_last_desktop_diagnostics_run_log_text(request.resolved_out_root(self.repo_root))
        summary = build_diagnostics_workspace_summary(self.repo_root)
        try:
            baseline_evidence = baseline_center_evidence_payload(repo_root=self.repo_root)
        except Exception as exc:
            baseline_evidence = {
                "schema": "baseline_center_evidence",
                "error": str(exc),
                "active_baseline": {"state": "invalid"},
                "send_bundle_should_include": True,
                "silent_rebinding_allowed": False,
            }
        baseline_attention = _baseline_attention_required(baseline_evidence)

        self._current_bundle = bundle
        self._current_request = request
        if run_record is not None:
            self._current_run_record = run_record

        snapshot = DiagnosticsWorkspaceSnapshot(
            bundle=bundle,
            run_record=run_record,
            run_log_text=run_log_text,
            request=request,
            request_source="desktop_diagnostics_runtime + desktop_diagnostics_model",
            summary_headline=summary.headline,
            summary_detail=summary.detail,
            summary_lines=tuple(summary.evidence_lines),
            center_state_path=path_str(Path(bundle.out_dir) / "latest_desktop_diagnostics_center_state.json"),
            summary_md_path=path_str(Path(bundle.out_dir) / "latest_desktop_diagnostics_summary.md"),
            recommended_next_step=(
                "Проверьте базовый прогон перед копированием архива."
                if baseline_attention
                else "Если архив проекта уже сохранён, проверьте состав и состояние, затем скопируйте его вручную."
                if bundle.latest_zip_path
                else "Сначала сохраните архив проекта, чтобы получить свежую проверку состава и состояния."
            ),
            baseline_evidence=baseline_evidence,
            baseline_attention_required=baseline_attention,
            baseline_status_text=_baseline_status_text(baseline_evidence),
            is_busy=self.is_busy(),
            status_text=self._status_text,
        )
        self._current_snapshot = snapshot
        self._persist_center_state(snapshot)
        self.snapshot_changed.emit(snapshot)
        return snapshot

    def handle_command(self, command_id: str) -> None:
        if command_id == "diagnostics.collect_bundle":
            self.start_collect()
            return
        if command_id == "diagnostics.verify_bundle":
            self.verify_bundle()
            return
        if command_id == "diagnostics.send_results":
            self.send_results()
            return
        if command_id == "diagnostics.legacy_center.open":
            self.open_legacy_center()
            return

    def start_collect(self) -> None:
        if self.is_busy():
            self._set_status("Сохранение архива проекта уже выполняется.", busy=True)
            return

        bundle = self._current_bundle or load_desktop_diagnostics_bundle_record(self.repo_root)
        request = _restore_request_from_center_state(self.repo_root, bundle)
        cmd = build_run_full_diagnostics_command(
            str(_guess_python_exe(self.repo_root)),
            self.tools_dir / "run_full_diagnostics.py",
            request,
        )
        out_root = request.resolved_out_root(self.repo_root)
        append_desktop_diagnostics_run_log(out_root, "")
        started_at = now_local_iso()
        record = DesktopDiagnosticsRunRecord(
            ok=False,
            started_at=started_at,
            finished_at="",
            status="running",
            command=[str(x) for x in cmd],
            returncode=None,
            run_dir="",
            zip_path="",
            out_root=path_str(out_root),
            last_message="started",
        )
        self._current_request = request
        self._current_run_record = persist_desktop_diagnostics_run(out_root, record, log_text="")
        self._buffered_log = ""

        self._process.setWorkingDirectory(str(self.repo_root))
        self._process.setProgram(cmd[0])
        self._process.setArguments(cmd[1:])
        self._process.start()
        self._set_status("Идёт сохранение архива проекта...", busy=True)
        self.refresh(regenerate_reports=False)

    def verify_bundle(self) -> None:
        bundle = self._current_bundle or load_desktop_diagnostics_bundle_record(self.repo_root)
        if not bundle.latest_zip_path:
            self._set_status("Проверка архива недоступна: сначала сохраните архив проекта.", busy=False)
            self.refresh(regenerate_reports=False)
            return
        self._set_status("Обновляю проверку состава и состояния архива проекта...", busy=True)
        self.refresh(regenerate_reports=True)
        self._set_status("Проверка архива проекта обновлена.", busy=False)

    def send_results(self) -> None:
        bundle = self._current_bundle or load_desktop_diagnostics_bundle_record(self.repo_root)
        if not bundle.latest_zip_path:
            self._set_status("Копирование архива недоступно: архив проекта ещё не сохранён.", busy=False)
            self.refresh(regenerate_reports=False)
            return
        self.spawn_module_fn("pneumo_solver_ui.tools.send_results_gui")
        self._set_status("Копирование архива открыто.", busy=False)
        self.refresh(regenerate_reports=False)

    def open_bundle_folder(self) -> None:
        bundle = self._current_bundle or load_desktop_diagnostics_bundle_record(self.repo_root)
        self.open_path_fn(Path(bundle.out_dir).expanduser().resolve())
        self._set_status("Открыта папка архива проекта.", busy=False)

    def open_legacy_center(self) -> None:
        self.spawn_module_fn("pneumo_solver_ui.tools.desktop_diagnostics_center")
        self._set_status("Расширенная проверка проекта открыта.", busy=False)

    def _set_status(self, text: str, *, busy: bool) -> None:
        self._status_text = text
        self.shell_status_changed.emit(text, busy)

    def _on_ready_read(self) -> None:
        text = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if not text:
            return
        self._buffered_log += text
        if self._current_request is not None:
            out_root = self._current_request.resolved_out_root(self.repo_root)
            append_desktop_diagnostics_run_log(out_root, text)

        if self._current_run_record is not None:
            for raw_line in text.splitlines():
                updates = parse_run_full_diagnostics_output_line(raw_line)
                if not updates:
                    continue
                self._current_run_record = persist_desktop_diagnostics_run(
                    Path(self._current_run_record.out_root or out_root),
                    DesktopDiagnosticsRunRecord(
                        ok=False,
                        started_at=self._current_run_record.started_at,
                        finished_at="",
                        status="running",
                        command=[str(x) for x in (self._current_run_record.command or [])],
                        returncode=None,
                        run_dir=updates.get("run_dir", self._current_run_record.run_dir),
                        zip_path=updates.get("zip_path", self._current_run_record.zip_path),
                        out_root=self._current_run_record.out_root,
                        log_path=self._current_run_record.log_path,
                        state_path=self._current_run_record.state_path,
                        last_message=raw_line.strip(),
                    ),
                    log_text="",
                )
        self.refresh(regenerate_reports=False)

    def _on_finished(self, exit_code: int, _exit_status: QtCore.QProcess.ExitStatus) -> None:
        request = self._current_request
        if request is None:
            self._set_status("Сохранение архива проекта завершилось, но сведения о запуске не найдены.", busy=False)
            self.refresh(regenerate_reports=False)
            return

        out_root = request.resolved_out_root(self.repo_root)
        run_record = self._current_run_record or load_last_desktop_diagnostics_run_record(out_root)
        started_at = run_record.started_at if run_record is not None else now_local_iso()
        self._current_run_record = persist_desktop_diagnostics_run(
            out_root,
            DesktopDiagnosticsRunRecord(
                ok=exit_code == 0,
                started_at=started_at,
                finished_at=now_local_iso(),
                status="done" if exit_code == 0 else "failed",
                command=[str(x) for x in (run_record.command if run_record else [])],
                returncode=int(exit_code),
                run_dir=run_record.run_dir if run_record else "",
                zip_path=run_record.zip_path if run_record else "",
                out_root=path_str(out_root),
                log_path=run_record.log_path if run_record else "",
                state_path=run_record.state_path if run_record else "",
                last_message="завершено" if exit_code == 0 else "ошибка",
            ),
            log_text="",
        )
        self._set_status(
            "Архив проекта сохранён." if exit_code == 0 else f"Сохранение архива проекта завершилось с кодом {exit_code}.",
            busy=False,
        )
        self.refresh(regenerate_reports=exit_code == 0)

    def _on_process_error(self, error: QtCore.QProcess.ProcessError) -> None:
        if self.is_busy():
            return
        self._set_status(f"Ошибка запуска сохранения архива проекта: {error!s}", busy=False)
        self.refresh(regenerate_reports=False)

    def _persist_center_state(self, snapshot: DiagnosticsWorkspaceSnapshot) -> None:
        summary_text = "\n".join(
            [
                "# Сводка проверки проекта и архива",
                "",
                f"- Состояние: {snapshot.status_text}",
                f"- Архив проекта: {_safe_path_text(snapshot.bundle.latest_zip_path)}",
                f"- Состав архива: {_safe_path_text(snapshot.bundle.latest_inspection_md_path)}",
                f"- Состояние проекта: {_safe_path_text(snapshot.bundle.latest_health_md_path)}",
                f"- Проверка результата: {_safe_path_text(snapshot.bundle.latest_validation_md_path)}",
                f"- Разбор предупреждений: {_safe_path_text(snapshot.bundle.latest_triage_md_path)}",
                (
                    "- Материал анимации для проверки: "
                    f"{_safe_path_text(snapshot.bundle.latest_animation_diagnostics_handoff_path)}"
                ),
                f"- Сцена анимации: {_safe_path_text(snapshot.bundle.animation_diagnostics_scene_npz_path)}",
                (
                    "- Данные проигрывания: "
                    f"{_safe_path_text(snapshot.bundle.animation_diagnostics_pointer_json_path)}"
                ),
            ]
        )
        summary_md_path = write_desktop_diagnostics_summary_md(snapshot.bundle.out_dir, summary_text)
        write_desktop_diagnostics_center_state(
            Path(snapshot.bundle.out_dir),
            bundle_record=snapshot.bundle,
            run_record=snapshot.run_record,
            summary_md_path=summary_md_path,
            ui_state={
                "selected_tab": "diagnostics",
                "status_text": snapshot.status_text,
                "diagnostics_running": snapshot.is_busy,
                "level": snapshot.request.level,
                "skip_ui_smoke": snapshot.request.skip_ui_smoke,
                "no_zip": snapshot.request.no_zip,
                "run_opt_smoke": snapshot.request.run_opt_smoke,
                "opt_minutes": snapshot.request.opt_minutes,
                "opt_jobs": snapshot.request.opt_jobs,
                "osc_dir": snapshot.request.osc_dir,
                "out_root": snapshot.request.out_root,
                "active_bundle_out_dir": snapshot.bundle.out_dir,
                "active_run_out_root": path_str(snapshot.request.resolved_out_root(self.repo_root)),
                "clipboard_ok": snapshot.bundle.clipboard_ok,
                "worker_error": "" if snapshot.run_record is None else snapshot.run_record.last_message,
                "baseline_attention_required": snapshot.baseline_attention_required,
                "baseline_status_text": snapshot.baseline_status_text,
                "baseline_open_command": "baseline.center.open",
            },
        )


class DiagnosticsWorkspacePage(QtWidgets.QWidget):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        *,
        repo_root: Path,
        on_shell_status: Callable[[str, bool], None] | None = None,
        on_command: Callable[[str], None] | None = None,
        spawn_module_fn: Callable[[str], object] = spawn_module,
        open_path_fn: Callable[[Path], None] = _open_in_explorer,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.on_shell_status = on_shell_status
        self.on_command = on_command
        self.controller = DiagnosticsShellController(
            Path(repo_root).resolve(),
            spawn_module_fn=spawn_module_fn,
            open_path_fn=open_path_fn,
            parent=self,
        )
        self.controller.snapshot_changed.connect(self._apply_snapshot)
        self.controller.shell_status_changed.connect(self._on_controller_status)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        scroll.setWidget(inner)
        layout = QtWidgets.QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QtWidgets.QLabel(workspace.title)
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 5)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        summary = QtWidgets.QLabel(workspace.summary)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        self.status_label = QtWidgets.QLabel("Готово.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("padding: 8px; background: #f4f7fb; border: 1px solid #d7e3f4;")
        layout.addWidget(self.status_label)

        progress_box = QtWidgets.QGroupBox("Ход действия")
        progress_layout = QtWidgets.QVBoxLayout(progress_box)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Готово")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_note = QtWidgets.QLabel("Длительные действия показываются здесь же, в проверке проекта и архива.")
        self.progress_note.setWordWrap(True)
        self.progress_note.setStyleSheet("color: #405060;")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_note)
        layout.addWidget(progress_box)

        self.source_label = QtWidgets.QLabel(
            "Данные берутся из состояния проверки проекта и сохранения архива проекта."
        )
        self.source_label.setWordWrap(True)
        self.source_label.setStyleSheet("color: #405060;")
        layout.addWidget(self.source_label)

        v16_box = build_v16_visibility_priority_box(workspace)
        if v16_box is not None:
            layout.addWidget(v16_box)

        v19_box = build_v19_action_feedback_box(workspace)
        if v19_box is not None:
            layout.addWidget(v19_box)

        self.bundle_box = QtWidgets.QGroupBox("Текущее состояние архива проекта")
        bundle_layout = QtWidgets.QFormLayout(self.bundle_box)
        self.bundle_zip_value = QtWidgets.QLabel("")
        self.bundle_out_dir_value = QtWidgets.QLabel("")
        self.bundle_clipboard_value = QtWidgets.QLabel("")
        self.bundle_paths_value = QtWidgets.QLabel("")
        for label in (
            self.bundle_zip_value,
            self.bundle_out_dir_value,
            self.bundle_clipboard_value,
            self.bundle_paths_value,
        ):
            label.setWordWrap(True)
        bundle_layout.addRow("Последний архив", self.bundle_zip_value)
        bundle_layout.addRow("Папка архива проекта", self.bundle_out_dir_value)
        bundle_layout.addRow("Буфер обмена", self.bundle_clipboard_value)
        bundle_layout.addRow("Связанные пути", self.bundle_paths_value)
        layout.addWidget(self.bundle_box)

        self.run_box = QtWidgets.QGroupBox("Последнее сохранение архива")
        run_layout = QtWidgets.QFormLayout(self.run_box)
        self.run_state_value = QtWidgets.QLabel("")
        self.run_started_value = QtWidgets.QLabel("")
        self.run_finished_value = QtWidgets.QLabel("")
        self.run_dir_value = QtWidgets.QLabel("")
        self.request_value = QtWidgets.QLabel("")
        for label in (
            self.run_state_value,
            self.run_started_value,
            self.run_finished_value,
            self.run_dir_value,
            self.request_value,
        ):
            label.setWordWrap(True)
        run_layout.addRow("Состояние", self.run_state_value)
        run_layout.addRow("Запущен", self.run_started_value)
        run_layout.addRow("Завершён", self.run_finished_value)
        run_layout.addRow("Каталог прогона", self.run_dir_value)
        run_layout.addRow("Параметры запуска", self.request_value)
        layout.addWidget(self.run_box)

        self.check_box = QtWidgets.QGroupBox("Проверка архива проекта")
        check_layout = QtWidgets.QFormLayout(self.check_box)
        self.inspection_value = QtWidgets.QLabel("")
        self.health_value = QtWidgets.QLabel("")
        self.validation_value = QtWidgets.QLabel("")
        self.triage_value = QtWidgets.QLabel("")
        self.next_step_value = QtWidgets.QLabel("")
        for label in (
            self.inspection_value,
            self.health_value,
            self.validation_value,
            self.triage_value,
            self.next_step_value,
        ):
            label.setWordWrap(True)
        check_layout.addRow("Состав архива", self.inspection_value)
        check_layout.addRow("Состояние проекта", self.health_value)
        check_layout.addRow("Проверка результата", self.validation_value)
        check_layout.addRow("Разбор предупреждений", self.triage_value)
        check_layout.addRow("Рекомендуемый шаг", self.next_step_value)
        layout.addWidget(self.check_box)

        self.animation_handoff_box = QtWidgets.QGroupBox("Материал анимации для проверки")
        self.animation_handoff_box.setObjectName("DG-ANIMATION-HANDOFF")
        animation_layout = QtWidgets.QFormLayout(self.animation_handoff_box)
        self.animation_handoff_source_value = QtWidgets.QLabel("")
        self.animation_handoff_scene_value = QtWidgets.QLabel("")
        self.animation_handoff_pointer_value = QtWidgets.QLabel("")
        self.animation_handoff_next_value = QtWidgets.QLabel("")
        for label in (
            self.animation_handoff_source_value,
            self.animation_handoff_scene_value,
            self.animation_handoff_pointer_value,
            self.animation_handoff_next_value,
        ):
            label.setWordWrap(True)
        animation_layout.addRow("Источник", self.animation_handoff_source_value)
        animation_layout.addRow("Сцена", self.animation_handoff_scene_value)
        animation_layout.addRow("Данные проигрывания", self.animation_handoff_pointer_value)
        animation_layout.addRow("Следующий шаг", self.animation_handoff_next_value)
        layout.addWidget(self.animation_handoff_box)

        self.baseline_box = QtWidgets.QGroupBox("Опорный прогон")
        baseline_layout = QtWidgets.QVBoxLayout(self.baseline_box)
        self.baseline_status_value = QtWidgets.QLabel("")
        self.baseline_status_value.setObjectName("DG-BASELINE-STATUS")
        self.baseline_status_value.setWordWrap(True)
        self.open_baseline_center_button = QtWidgets.QPushButton("Перейти к базовому прогону")
        self.open_baseline_center_button.setObjectName("DG-BTN-OPEN-BASELINE")
        self.open_baseline_center_button.clicked.connect(self.open_baseline_center)
        baseline_layout.addWidget(self.baseline_status_value)
        baseline_layout.addWidget(self.open_baseline_center_button)
        layout.addWidget(self.baseline_box)

        self.actions_box = QtWidgets.QGroupBox("Действия")
        actions_layout = QtWidgets.QGridLayout(self.actions_box)
        self.collect_button = QtWidgets.QPushButton("Сохранить архив проекта")
        self.verify_button = QtWidgets.QPushButton("Проверить архив проекта")
        self.send_button = QtWidgets.QPushButton("Скопировать архив")
        self.open_dir_button = QtWidgets.QPushButton("Открыть каталог")
        self.refresh_button = QtWidgets.QPushButton("Обновить состояние")
        self.legacy_button = QtWidgets.QPushButton("Расширенная проверка проекта")
        _apply_action_contract(self.collect_button, "DG-BTN-COLLECT")
        self.collect_button.clicked.connect(lambda: self.handle_command("diagnostics.collect_bundle"))
        self.verify_button.clicked.connect(lambda: self.handle_command("diagnostics.verify_bundle"))
        self.send_button.clicked.connect(lambda: self.handle_command("diagnostics.send_results"))
        self.open_dir_button.clicked.connect(self.controller.open_bundle_folder)
        self.refresh_button.clicked.connect(self.refresh_view)
        self.legacy_button.clicked.connect(lambda: self.handle_command("diagnostics.legacy_center.open"))
        actions_layout.addWidget(self.collect_button, 0, 0)
        actions_layout.addWidget(self.verify_button, 0, 1)
        actions_layout.addWidget(self.send_button, 0, 2)
        actions_layout.addWidget(self.open_dir_button, 1, 0)
        actions_layout.addWidget(self.refresh_button, 1, 1)
        actions_layout.addWidget(self.legacy_button, 1, 2)
        layout.addWidget(self.actions_box)

        self.log_box = QtWidgets.QGroupBox("Журнал / последние сообщения")
        log_layout = QtWidgets.QVBoxLayout(self.log_box)
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(240)
        log_layout.addWidget(self.log_view)
        layout.addWidget(self.log_box, 1)
        layout.addStretch(1)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setInterval(10000)
        self._refresh_timer.timeout.connect(self.refresh_view)
        self._refresh_timer.start()
        self.refresh_view()

    def refresh_view(self) -> None:
        self.controller.refresh(regenerate_reports=False)

    def handle_command(self, command_id: str) -> None:
        self.controller.handle_command(command_id)

    def open_baseline_center(self) -> None:
        if self.on_command is not None:
            self.on_command("baseline.center.open")
            self.status_label.setText("Переход к базовому прогону выполнен из проверки проекта и архива.")
            return
        self.status_label.setText("Базовый прогон доступен из рабочего места инженера.")

    def _on_controller_status(self, text: str, busy: bool) -> None:
        self.status_label.setText(text)
        self._set_progress_state(busy=busy, status_text=text)
        if self.on_shell_status is not None:
            self.on_shell_status(text, busy)

    def _set_progress_state(self, *, busy: bool, status_text: str) -> None:
        if busy:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat("Выполняется")
            self.progress_note.setText(status_text)
            return
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Готово")
        self.progress_note.setText(status_text or "Готово к следующему действию.")

    def _apply_snapshot(self, payload: object) -> None:
        snapshot = payload if isinstance(payload, DiagnosticsWorkspaceSnapshot) else None
        if snapshot is None:
            return

        self.status_label.setText(snapshot.status_text)
        self._set_progress_state(busy=snapshot.is_busy, status_text=snapshot.status_text)
        self.bundle_zip_value.setText(_safe_path_text(snapshot.bundle.latest_zip_path))
        self.bundle_out_dir_value.setText(_safe_path_text(snapshot.bundle.out_dir))
        self.bundle_clipboard_value.setText(
            f"Буфер обмена готов - {_bool_marker(snapshot.bundle.clipboard_ok)}. {_operator_message_text(snapshot.bundle.clipboard_message) or 'Буфер обмена не использовался.'}"
        )
        self.bundle_paths_value.setText(
            "\n".join(
                [
                    f"Описание архива сохранено в файле {_safe_path_text(snapshot.bundle.latest_bundle_meta_path)}",
                    f"Настройки проверки сохранены в файле {_safe_path_text(snapshot.center_state_path)}",
                    f"Сводка проверки сохранена в файле {_safe_path_text(snapshot.summary_md_path)}",
                ]
            )
        )

        run_record = snapshot.run_record
        if run_record is None:
            self.run_state_value.setText("Архив проекта ещё не сохранялся в текущей папке.")
            self.run_started_value.setText("нет данных")
            self.run_finished_value.setText("нет данных")
            self.run_dir_value.setText("нет данных")
        else:
            self.run_state_value.setText(
                f"Состояние запуска - {_state_text(run_record.status, fallback='нет данных')}. Успешно завершён - {_bool_marker(bool(run_record.ok))}. Код завершения - {run_record.returncode}."
            )
            self.run_started_value.setText(run_record.started_at or "нет данных")
            self.run_finished_value.setText(run_record.finished_at or "нет данных")
            self.run_dir_value.setText(_safe_path_text(run_record.run_dir))
        self.request_value.setText(
            f"Объём проверки - {_request_level_text(snapshot.request.level)}. "
            f"Проверка окна будет {'пропущена' if snapshot.request.skip_ui_smoke else 'выполнена'}. "
            f"Архив проекта будет {'не сохранён' if snapshot.request.no_zip else 'сохранён'}. "
            f"Проверка оптимизации будет {'выполнена' if snapshot.request.run_opt_smoke else 'пропущена'}. "
            f"Лимит проверки оптимизации {snapshot.request.opt_minutes} мин. Задач {snapshot.request.opt_jobs}."
        )

        self.inspection_value.setText(_safe_path_text(snapshot.bundle.latest_inspection_md_path))
        self.health_value.setText(_safe_path_text(snapshot.bundle.latest_health_md_path))
        self.validation_value.setText(_safe_path_text(snapshot.bundle.latest_validation_md_path))
        self.triage_value.setText(_safe_path_text(snapshot.bundle.latest_triage_md_path))
        self.next_step_value.setText(snapshot.recommended_next_step)
        animation_status = str(snapshot.bundle.animation_diagnostics_handoff_status or "").upper()
        if snapshot.bundle.latest_animation_diagnostics_handoff_path:
            self.animation_handoff_source_value.setText(
                snapshot.bundle.animation_diagnostics_selected_title
                or snapshot.bundle.animation_diagnostics_selected_path
                or "Материал передан из анимации."
            )
            self.animation_handoff_scene_value.setText(
                _safe_path_text(snapshot.bundle.animation_diagnostics_scene_npz_path)
            )
            self.animation_handoff_pointer_value.setText(
                _safe_path_text(snapshot.bundle.animation_diagnostics_pointer_json_path)
            )
            self.animation_handoff_next_value.setText(
                snapshot.bundle.animation_diagnostics_next_step
                or (
                    "Проверьте материал анимации перед сохранением архива проекта."
                    if animation_status == "WARN"
                    else "Сохраните архив проекта с текущим материалом."
                )
            )
        else:
            self.animation_handoff_source_value.setText("Материал анимации ещё не передан.")
            self.animation_handoff_scene_value.setText("нет данных")
            self.animation_handoff_pointer_value.setText("нет данных")
            self.animation_handoff_next_value.setText(
                "Если нужно проверить визуальный результат, передайте материал из рабочего шага анимации."
            )
        self.baseline_status_value.setText(snapshot.baseline_status_text)
        if snapshot.baseline_attention_required:
            self.baseline_status_value.setStyleSheet(
                "background: #fff4e5; color: #6f4e00; padding: 8px; border: 1px solid #d9822b;"
            )
        else:
            self.baseline_status_value.setStyleSheet(
                "background: #e8f7ee; color: #1f5f3a; padding: 8px; border: 1px solid #64b883;"
            )
        self.open_baseline_center_button.setEnabled(not snapshot.is_busy)

        self.log_view.setPlainText(snapshot.run_log_text or "\n".join(snapshot.summary_lines))

        busy = snapshot.is_busy
        self.collect_button.setEnabled(not busy)
        self.verify_button.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.legacy_button.setEnabled(not busy)
