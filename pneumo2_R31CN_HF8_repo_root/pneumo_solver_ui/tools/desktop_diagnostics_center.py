# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
import threading
import hashlib
from pathlib import Path

import tkinter as tk
from tkinter import Tk, StringVar, BooleanVar, IntVar
from tkinter import filedialog, messagebox, ttk

from pneumo_solver_ui.desktop_diagnostics_model import (
    DesktopDiagnosticsRequest,
    DesktopDiagnosticsRunRecord,
    LATEST_DESKTOP_DIAGNOSTICS_CENTER_JSON,
    LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD,
    build_run_full_diagnostics_command,
    now_local_iso,
    parse_run_full_diagnostics_output_line,
    path_str,
)
from pneumo_solver_ui.desktop_diagnostics_runtime import (
    append_desktop_diagnostics_run_log,
    copy_latest_bundle_to_clipboard,
    load_last_desktop_diagnostics_center_state,
    load_last_desktop_diagnostics_run_record,
    load_last_desktop_diagnostics_run_log_text,
    load_desktop_diagnostics_bundle_record,
    persist_desktop_diagnostics_run,
    refresh_desktop_diagnostics_bundle_record,
    write_desktop_diagnostics_summary_md,
    write_desktop_diagnostics_center_state,
)
from pneumo_solver_ui.desktop_ui_core import (
    build_scrolled_text,
    build_status_strip,
    create_scrollable_tab,
)
from pneumo_solver_ui.diagnostics_entrypoint import build_full_diagnostics_bundle

try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent


STATUS_LABELS_RU: dict[str, str] = {
    "READY": "готово",
    "CURRENT": "актуально",
    "WARN": "требует внимания",
    "WARNING": "требует внимания",
    "MISSING": "нет данных",
    "STALE": "устарело",
    "BLOCKED": "заблокировано",
    "INVALID": "ошибка данных",
    "DEGRADED": "неполные данные",
    "FAILED": "ошибка",
    "FINISHED": "завершено",
    "RUNNING": "выполняется",
    "STOPPING": "останавливается",
    "OPEN": "открыто",
    "CLEAR": "чисто",
    "PASS": "пройдено",
    "FAIL": "ошибка",
}


def _status_ru(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "нет данных"
    return STATUS_LABELS_RU.get(text.upper(), text)


def _bool_ru(value: object) -> str:
    if value is True:
        return "да"
    if value is False:
        return "нет"
    if value is None:
        return "нет данных"
    return str(value)


def _producer_owner_ru(value: object) -> str:
    text = str(value or "").strip()
    labels = {
        "producer_export": "экспорт расчёта",
        "producer": "источник расчёта",
        "source": "источник данных",
    }
    if not text:
        return "нет данных"
    return labels.get(text, text.replace("_", " "))


def _technical_message_ru(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "нет сообщения"
    replacements = {
        "running": "выполняется",
        "OK": "успешно",
        "terminate_requested": "запрошена остановка",
        "Copied file to clipboard (CF_HDROP)": "Файл скопирован в буфер обмена",
        "Copied file to clipboard": "Файл скопирован в буфер обмена",
        "Copied path as text": "Путь к архиву скопирован как текст",
        "stale": "буфер обмена указывает на старый архив",
        "Analysis evidence / HO-009 missing": "Нет данных анализа результатов",
        "Analysis evidence / HO-009 manifest is empty or unreadable": "Файл состава анализа результатов пустой или не читается",
        "manifest is empty or unreadable": "файл состава пустой или не читается",
        "context is STALE": "контекст устарел",
        "context mismatch": "контекст не совпадает",
        "HO-008 analysis context is BLOCKED": "связь с анимацией заблокирована",
        "Engineering Analysis evidence / HO-007 missing": "Нет данных инженерного анализа",
        "Engineering Analysis evidence / HO-007 manifest is empty or unreadable": (
            "Файл состава инженерного анализа пустой или не читается"
        ),
        "Engineering Analysis evidence / HO-007 validation status requires attention": (
            "Состояние проверки инженерного анализа требует внимания"
        ),
        "HO-007 selected-run readiness has no READY optimization candidates": (
            "Для выбранного расчёта нет готовых кандидатов оптимизации"
        ),
        "HO-009": "данных анализа результатов",
        "HO-008": "связи анализа с анимацией",
        "HO-007": "данных инженерного анализа",
        "HO-010": "захвата для анимации",
        "Geometry reference evidence is empty or unreadable": "Данные справочника геометрии пустые или не читаются",
        "Geometry Reference evidence": "Данные справочника геометрии",
        "Geometry reference evidence": "Данные справочника геометрии",
        "producer_export": "экспорт расчёта",
        "producer-owned": "данные поставщика",
        "Producer-owned": "Данные поставщика",
        "warning-only": "только предупреждение",
        "missing inputs": "не хватает входных данных",
        "missing_inputs": "не хватает входных данных",
        "Results Center": "анализ результатов",
        "Engineering Analysis Center": "инженерный анализ",
        "Reference Center": "справочник",
        "Open": "Откройте",
        "export evidence manifest": "экспортируйте файл состава данных",
        "evidence manifest": "файл состава данных",
        "before SEND": "перед отправкой",
        "SEND": "отправка",
        "READY optimization run": "готовый расчёт оптимизации",
        "READY optimization candidates": "готовые кандидаты оптимизации",
        "validation/status": "состояние проверки",
        "readiness": "готовность",
        "context state": "состояние контекста",
        "mismatches": "расхождения",
        "packaging": "упаковку",
        "road_width": "ширину дороги",
        "geometry acceptance warnings": "предупреждения по геометрии",
        "consumer_may_fabricate_geometry": "потребитель может создавать геометрию",
        "influence_status": "состояние влияния",
        "calibration_status": "состояние калибровки",
        "validated_artifacts_status": "состояние проверенных данных",
        "handoff_contract_status": "состояние передачи данных",
        ("Latest " + "integrity:"): "Целостность актуального архива:",
        "final_sha=": "SHA итогового архива=",
        "sha_sidecar=": "SHA-файл=",
        "pointer=": "ссылка=",
        "no_release_closure=": "нужна проверка пользователя=",
        ("Producer-owned warnings remain " + "warning-only"): (
            "Предупреждения источников данных остаются предупреждениями"
        ),
        "Self-check silent warnings snapshot:": "Тихие предупреждения проверки:",
        "fail=": "ошибки=",
        "warn=": "предупреждения=",
        ("Engineering Analysis / " + "HO-007 open gap:"): "Инженерный анализ: есть незакрытые вопросы:",
        "Optimizer scope gate:": "Готовность данных оптимизатора:",
        "release_risk=": "риск для передачи=",
        ("Browser " + "perf evidence missing"): "Нет данных проверки производительности",
        ("Browser " + "perf comparison:"): "Сравнение производительности:",
        "no reference": "нет эталона",
        "open gap(s)": "открытые вопросы",
        "open gaps": "открытые вопросы",
        "open gap": "открытый вопрос",
        "selected_run_contract_hash": "метка выбранного расчёта",
        "ready=": "готово=",
        "rc=": "код завершения ",
        "BLOCKED": "заблокировано",
        "DEGRADED": "частично",
        "READY": "готово",
        "WARN": "предупреждение",
        "MISSING": "не найдено",
        "False": "нет",
        "True": "да",
        "None": "нет данных",
    }
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


def _operator_preview_text(value: object) -> str:
    text = str(value or "")
    if not text.strip():
        return "(нет данных для просмотра)"
    replacements = {
        "# Send bundle inspection": "# Проверка архива для отправки",
        "# Health report": "# Отчёт о состоянии проекта",
        "## Evidence manifest": "## Файл состава данных",
        "## Engineering analysis evidence": "## Данные инженерного анализа",
        "## Anim latest diagnostics": "## Диагностика последней анимации",
        "## Anim latest": "## Последняя анимация",
        "## Ring closure": "## Замыкание кольца",
        "## Desktop Mnemo events": "## События мнемосхемы",
        "## Artifacts": "## Данные",
        "## Validation": "## Проверка",
        "- Created:": "- Создано:",
        "- OK:": "- Успешно:",
        "- Release:": "- Версия:",
        "- Embedded health report:": "- Вложенный отчёт о состоянии:",
        "- Validation report:": "- Отчёт проверки:",
        "- Dashboard report:": "- Отчёт панели:",
        "- Triage report:": "- Разбор замечаний:",
        "- Anim diagnostics:": "- Диагностика анимации:",
        "- Evidence manifest:": "- Файл состава данных:",
        "- Engineering analysis evidence:": "- Данные инженерного анализа:",
        ("- Browser " + "perf snapshot:"): "- Снимок производительности браузера:",
        ("- Browser " + "perf previous snapshot:"): "- Предыдущий снимок производительности браузера:",
        ("- Browser " + "perf contract:"): "- Проверка производительности браузера:",
        ("- Browser " + "perf evidence report:"): "- Отчёт данных производительности браузера:",
        ("- Browser " + "perf comparison report:"): "- Отчёт сравнения производительности браузера:",
        ("- Browser " + "perf trace:"): "- Трасса производительности браузера:",
        "- Geometry acceptance:": "- Приёмка геометрии:",
        "- Geometry acceptance gate:": "- Шлюз приёмки геометрии:",
        "- Geometry acceptance reason:": "- Причина приёмки геометрии:",
        "- collection_mode:": "- Режим сбора:",
        "- trigger:": "- Запуск:",
        "- finalization_stage:": "- Этап финализации:",
        "- stage:": "- Этап:",
        "- zip_sha256:": "- SHA256 архива:",
        "- missing_required_count:": "- Не хватает обязательных данных:",
        "- missing_optional_count:": "- Не хватает необязательных данных:",
        "- missing_evidence:": "- Нет данных:",
        "- status:": "- Состояние:",
        "- source_path:": "- Путь источника:",
        "- evidence_manifest_hash:": "- Метка состава данных:",
        "- influence_status:": "- Влияние:",
        "- calibration_status:": "- Калибровка:",
        "- analysis_status:": "- Анализ:",
        "- sensitivity_row_count:": "- Строк чувствительности:",
        "- handoff_contract_status:": "- Передача данных:",
        "- handoff_required_path:": "- Требуемый файл передачи:",
        "- handoff_missing_fields:": "- Не хватает полей передачи:",
        "- available:": "- Доступно:",
        "- visual_cache_token:": "- Метка визуальной проверки:",
        "- visual_reload_inputs:": "- Входные данные перезагрузки:",
        "- pointer_sync_ok:": "- Последняя анимация синхронизирована:",
        "- reload_inputs_sync_ok:": "- Входные данные синхронизированы:",
        "- npz_path_sync_ok:": "- Файл анимации синхронизирован:",
        "- npz_path:": "- Файл анимации:",
        "- updated_utc:": "- Обновлено UTC:",
        "- scenario_kind:": "- Тип сценария:",
        "- severity:": "- Важность:",
        "- summary:": "- Сводка:",
        "- policy:": "- Политика:",
        "- seam_jump_m:": "- Скачок шва, м:",
        "Analysis evidence / HO-009 context state is missing": "нет состояния контекста анализа результатов",
        "Geometry reference producer artifact handoff is missing": (
            "нет данных источника для справочника геометрии"
        ),
        "Run producer/solver anim_latest export": "выполните экспорт последней анимации из источника/решателя",
        "Reference Center must not fabricate producer geometry evidence": (
            "справочник не должен создавать данные геометрии за источник"
        ),
        "Reasons:": "Причины:",
        "Geometry reference evidence reports missing item(s)": "данные справочника геометрии сообщают о нехватке",
        "Geometry reference artifact context is missing": "нет описания данных справочника геометрии",
        "Geometry reference artifact freshness is missing": "нет отметки актуальности данных справочника геометрии",
        "Geometry reference packaging passport state is": "состояние паспорта упаковки справочника геометрии:",
        "Geometry acceptance gate is": "шлюз приёмки геометрии:",
        "Ring closure diagnostics not applicable": "диагностика замыкания кольца неприменима",
        "True": "да",
        "False": "нет",
        "None": "нет данных",
        "MISSING": "нет данных",
        "READY": "готово",
        "WARN": "требует внимания",
        "BLOCKED": "заблокировано",
        "missing": "нет данных",
    }
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    return _technical_message_ru(result)


def _operator_log_text(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    replacements = {
        "Run dir:": "Папка запуска:",
        "Zip:": "Архив для отправки:",
        "Traceback": "Сведения об ошибке",
        "Error:": "Ошибка:",
        "ERROR:": "Ошибка:",
        "WARNING:": "Предупреждение:",
        "WARN:": "Предупреждение:",
        "FAILED": "ошибка",
        "Failed": "ошибка",
        "SUCCESS": "успешно",
        "Success": "успешно",
        "finished": "завершено",
        "started": "запущено",
        "running": "выполняется",
        "returncode": "код завершения",
        "rc=": "код завершения ",
        "latest_send_bundle": "актуальный архив для отправки",
        "send bundle": "архив для отправки",
        "send-bundle": "архив для отправки",
    }
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    return _technical_message_ru(result)


def _guess_python_exe() -> Path:
    if sys.platform.startswith("win"):
        venv = ROOT / ".venv" / "Scripts"
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


def _sha256_file(path: Path, buf_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(buf_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class DesktopDiagnosticsCenter:
    def __init__(
        self,
        root: tk.Misc,
        *,
        hosted: bool = False,
        initial_tab: str = "diagnostics",
        auto_build_bundle: bool = False,
    ) -> None:
        self.root = root
        self._hosted = bool(hosted)
        if not self._hosted:
            self.root.title(f"Проверка проекта и отправка - {RELEASE}")
            self.root.geometry("1040x760")
            self.root.minsize(980, 720)

        self.repo_root = ROOT
        self.tools_dir = TOOLS_DIR

        self.level = StringVar(value="standard")
        self.skip_ui_smoke = BooleanVar(value=False)
        self.no_zip = BooleanVar(value=False)
        self.run_opt_smoke = BooleanVar(value=False)
        self.opt_minutes = IntVar(value=2)
        self.opt_jobs = IntVar(value=2)
        self.osc_dir = StringVar(value=str((ROOT / "workspace" / "osc").resolve()))
        self.out_root = StringVar(value=str((ROOT / "diagnostics").resolve()))

        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._host_closed = False
        self._last_zip: Path | None = None
        self._last_run_dir: Path | None = None
        self._last_run_record: DesktopDiagnosticsRunRecord | None = None
        self._last_bundle_record = None
        self._center_state_path: Path | None = None
        self._summary_md_path: Path | None = None
        self._bundle_worker: threading.Thread | None = None
        self._bundle_busy = False
        self._bundle_auto_copy_on_ready = False
        self._clipboard_attempted = False
        self._clipboard_ok = False
        self._clipboard_message = ""
        self._worker_done = True
        self._worker_exc: str | None = None
        self._current_run_lines: list[str] = []
        self._poll_after_id: str | None = None
        self._external_state_signature: tuple[str, ...] = ()
        self.zip_path: Path | None = None
        self.out_dir = Path(load_desktop_diagnostics_bundle_record(self.repo_root).out_dir)
        self._restored_center_state = load_last_desktop_diagnostics_center_state(self.out_dir)
        self.sha256 = ""
        self.size_mb = 0.0

        self.status_var = StringVar(value="Готово. Выберите действие слева или в верхней панели.")
        self.process_title_var = StringVar(value="Текущий процесс: нет активной операции")
        self.process_detail_var = StringVar(
            value="Прогресс проверки проекта и сборки архива всегда показывается здесь."
        )
        self.machine_state_var = StringVar(value="")
        self.context_summary_var = StringVar(
            value="Порядок работы: проверить проект, собрать архив для отправки и подготовить передачу."
        )
        self.send_title_var = StringVar(value="Архив для отправки в чат ещё не готов.")
        self.send_path_var = StringVar(value="(ещё не готово)")
        self.send_meta_var = StringVar(value="")
        self.analysis_evidence_status_var = StringVar(value="Данные анализа результатов: нет данных")
        self.engineering_analysis_status_var = StringVar(value="Данные инженерного анализа: нет данных")
        self.geometry_reference_status_var = StringVar(value="Справочник геометрии: нет данных")

        self._restore_bundle_state_from_last_center_state()
        self._restore_diagnostics_request_from_last_center_state()
        self._build_ui()
        self._select_initial_tab(initial_tab)
        self._last_run_record = load_last_desktop_diagnostics_run_record(self._active_run_out_root())
        self._refresh_bundle_views(regenerate_reports=False)
        self._schedule_poll()
        if auto_build_bundle:
            self._start_bundle_build(auto_copy_on_ready=True)

    def _active_bundle_out_dir(self) -> Path:
        try:
            return Path(self.out_dir).expanduser().resolve()
        except Exception:
            return Path(load_desktop_diagnostics_bundle_record(self.repo_root).out_dir).expanduser().resolve()

    def _active_run_out_root(self) -> Path:
        try:
            request = self._build_request()
            return request.resolved_out_root(self.repo_root)
        except Exception:
            return (self.repo_root / "diagnostics").resolve()

    def _state_signature_for_path(self, path: Path) -> str:
        try:
            if not path.exists():
                return f"{path}:missing"
            stat = path.stat()
            return f"{path}:{int(stat.st_mtime_ns)}:{int(stat.st_size)}"
        except Exception:
            return f"{path}:error"

    def _compute_external_state_signature(self) -> tuple[str, ...]:
        bundle_out_dir = self._active_bundle_out_dir()
        run_out_root = self._active_run_out_root()
        tracked_paths = [
            bundle_out_dir / "last_bundle_meta.json",
            bundle_out_dir / "latest_send_bundle_clipboard_status.json",
            bundle_out_dir / "latest_send_bundle_validation.json",
            bundle_out_dir / "latest_send_bundle_validation.md",
            bundle_out_dir / "latest_evidence_manifest.json",
            bundle_out_dir / "latest_analysis_evidence_manifest.json",
            bundle_out_dir / "latest_geometry_reference_evidence.json",
            bundle_out_dir / "latest_health_report.json",
            bundle_out_dir / "latest_health_report.md",
            bundle_out_dir / "latest_triage_report.md",
            bundle_out_dir / "latest_send_bundle_inspection.json",
            bundle_out_dir / "latest_send_bundle_inspection.md",
            bundle_out_dir / "latest_desktop_diagnostics_summary.md",
            bundle_out_dir / "latest_desktop_diagnostics_center_state.json",
            bundle_out_dir / "latest_send_bundle.zip",
            bundle_out_dir / "latest_send_bundle_path.txt",
            bundle_out_dir / "latest_send_bundle.sha256",
            run_out_root / "latest_desktop_diagnostics_run.json",
            run_out_root / "latest_desktop_diagnostics_run.log",
        ]
        raw_workspace = os.environ.get("PNEUMO_WORKSPACE_DIR", "").strip()
        try:
            workspace = Path(raw_workspace).expanduser().resolve() if raw_workspace else (
                self.repo_root / "pneumo_solver_ui" / "workspace"
            ).resolve()
            tracked_paths.append(workspace / "exports" / "analysis_evidence_manifest.json")
            tracked_paths.append(workspace / "exports" / "geometry_reference_evidence.json")
        except Exception:
            pass
        if self.zip_path is not None:
            tracked_paths.append(Path(self.zip_path).expanduser())
        return tuple(self._state_signature_for_path(path) for path in tracked_paths)

    def _schedule_poll(self) -> None:
        if self._host_closed:
            return
        self._poll_after_id = self.root.after(1000, self._poll_external_state)

    def _poll_external_state(self) -> None:
        self._poll_after_id = None
        if self._host_closed:
            return
        try:
            signature = self._compute_external_state_signature()
            if signature != self._external_state_signature:
                self._refresh_bundle_views(regenerate_reports=False)
        finally:
            self._schedule_poll()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 8))
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(
            title_box,
            text="Проверка проекта и отправка",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            textvariable=self.context_summary_var,
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        header_actions = ttk.Frame(header)
        header_actions.pack(side="right", anchor="ne")
        ttk.Button(header_actions, text="Настройки проверки", command=lambda: self.notebook.select(self.diag_tab)).pack(side="left")
        ttk.Button(header_actions, text="Состав архива", command=lambda: self.notebook.select(self.bundle_tab)).pack(side="left", padx=(8, 0))
        ttk.Button(header_actions, text="Отправка", command=lambda: self.notebook.select(self.send_tab)).pack(side="left", padx=(8, 0))
        ttk.Button(
            header_actions,
            text="Обновить сводку",
            command=lambda: self._refresh_bundle_views(regenerate_reports=False),
        ).pack(side="left", padx=(12, 0))

        process_box = ttk.LabelFrame(outer, text="Текущий процесс", padding=8)
        process_box.pack(fill="x", pady=(0, 10))
        ttk.Label(
            process_box,
            textvariable=self.process_title_var,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            process_box,
            textvariable=self.process_detail_var,
            wraplength=940,
            justify="left",
        ).pack(anchor="w", pady=(2, 6))
        self.process_progress = ttk.Progressbar(
            process_box,
            mode="determinate",
            maximum=100,
            value=0,
        )
        self.process_progress.pack(fill="x")

        workspace = ttk.Panedwindow(outer, orient="horizontal")
        workspace.pack(fill="both", expand=True)

        sidebar = ttk.Frame(workspace, padding=(0, 0, 8, 0))
        sidebar.columnconfigure(0, weight=1)
        context_box = ttk.LabelFrame(sidebar, text="Состояние", padding=8)
        context_box.pack(fill="x")
        ttk.Label(
            context_box,
            textvariable=self.machine_state_var,
            wraplength=260,
            justify="left",
        ).pack(anchor="w")
        quick_box = ttk.LabelFrame(sidebar, text="Основные действия", padding=8)
        quick_box.pack(fill="x", pady=(8, 0))
        ttk.Button(
            quick_box,
            text="1. Проверить проект",
            command=self._start_run,
        ).pack(fill="x")
        ttk.Button(
            quick_box,
            text="2. Собрать архив для отправки",
            command=lambda: self._start_bundle_build(auto_copy_on_ready=False),
        ).pack(fill="x", pady=(6, 0))
        ttk.Button(
            quick_box,
            text="Открыть последний архив",
            command=self._open_latest_bundle,
        ).pack(fill="x", pady=(6, 0))
        ttk.Button(
            quick_box,
            text="Открыть папку архивов",
            command=self._open_bundle_dir,
        ).pack(fill="x", pady=(6, 0))

        self.notebook = ttk.Notebook(workspace)

        self.diag_tab, self.diag_body = create_scrollable_tab(self.notebook, padding=8)
        self.bundle_tab, self.bundle_body = create_scrollable_tab(self.notebook, padding=8)
        self.send_tab, self.send_body = create_scrollable_tab(self.notebook, padding=8)
        self.notebook.add(self.diag_tab, text="1. Проверить проект")
        self.notebook.add(self.bundle_tab, text="2. Собрать архив")
        self.notebook.add(self.send_tab, text="3. Подготовить отправку")

        self._build_diag_tab()
        self._build_bundle_tab()
        self._build_send_tab()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed, add="+")
        workspace.add(sidebar, weight=1)
        workspace.add(self.notebook, weight=4)

        footer = build_status_strip(
            outer,
            primary_var=self.status_var,
            secondary_vars=(self.machine_state_var,),
        )
        footer.pack(fill="x", pady=(10, 0))

    def _build_diag_tab(self) -> None:
        pad = {"padx": 10, "pady": 6}

        level_box = ttk.LabelFrame(self.diag_body, text="Сколько проверять")
        level_box.pack(fill="x", **pad)
        for value, text in [
            ("minimal", "Минимально — быстро, только базовая проверка"),
            ("standard", "Стандартно — рекомендуется"),
            ("full", "Полностью — максимально подробно"),
        ]:
            ttk.Radiobutton(level_box, text=text, value=value, variable=self.level).pack(anchor="w", padx=10, pady=2)

        options_box = ttk.LabelFrame(self.diag_body, text="Дополнительные действия")
        options_box.pack(fill="x", **pad)
        ttk.Checkbutton(
            options_box,
            text="Пропустить быструю проверку окон приложения",
            variable=self.skip_ui_smoke,
        ).pack(anchor="w", padx=10, pady=2)
        ttk.Checkbutton(
            options_box,
            text="Не создавать архив (оставить папку как есть)",
            variable=self.no_zip,
        ).pack(anchor="w", padx=10, pady=2)

        opt_row = ttk.Frame(options_box)
        opt_row.pack(fill="x", padx=10, pady=4)
        ttk.Checkbutton(
            opt_row,
            text="Запустить быструю проверку оптимизации",
            variable=self.run_opt_smoke,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(opt_row, text="минуты:").grid(row=0, column=1, sticky="e", padx=(12, 2))
        ttk.Spinbox(opt_row, from_=1, to=60, textvariable=self.opt_minutes, width=6).grid(row=0, column=2, sticky="w")
        ttk.Label(opt_row, text="потоки:").grid(row=0, column=3, sticky="e", padx=(12, 2))
        ttk.Spinbox(opt_row, from_=1, to=32, textvariable=self.opt_jobs, width=6).grid(row=0, column=4, sticky="w")
        opt_row.columnconfigure(5, weight=1)

        path_box = ttk.LabelFrame(self.diag_body, text="Папки для проверки")
        path_box.pack(fill="x", **pad)

        osc_row = ttk.Frame(path_box)
        osc_row.pack(fill="x", padx=10, pady=4)
        ttk.Label(osc_row, text="Папка файлов анимации:").pack(side="left")
        ttk.Entry(osc_row, textvariable=self.osc_dir).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(osc_row, text="Выбрать", command=self._pick_osc_dir).pack(side="left")

        out_row = ttk.Frame(path_box)
        out_row.pack(fill="x", padx=10, pady=4)
        ttk.Label(out_row, text="Папка результатов:").pack(side="left")
        ttk.Entry(out_row, textvariable=self.out_root).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(out_row, text="Выбрать", command=self._pick_out_root).pack(side="left")

        ctrl = ttk.Frame(self.diag_body)
        ctrl.pack(fill="x", **pad)
        self.btn_run = ttk.Button(ctrl, text="Проверить проект", command=self._run)
        self.btn_run.pack(side="left")
        self.btn_stop = ttk.Button(ctrl, text="Остановить", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=8)
        self.btn_open = ttk.Button(ctrl, text="Открыть отчёт проверки", command=self._open_result, state="disabled")
        self.btn_open.pack(side="left", padx=8)
        ttk.Button(ctrl, text="Открыть папку результатов", command=self._open_diagnostics_out_root).pack(side="left", padx=8)

        log_box = ttk.LabelFrame(self.diag_body, text="Журнал проверки проекта")
        log_box.pack(fill="both", expand=True, **pad)
        log_body, self.txt = build_scrolled_text(log_box, wrap="word", height=16)
        log_body.pack(fill="both", expand=True)
        self._append("Готово. Здесь запускается проверка проекта и формируется подробный отчёт.\n")

    def _build_bundle_tab(self) -> None:
        top = ttk.Frame(self.bundle_body)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="Обновить сводку и проверки", command=lambda: self._refresh_bundle_views(regenerate_reports=True)).pack(side="left")
        ttk.Button(top, text="Собрать архив сейчас", command=lambda: self._start_bundle_build(auto_copy_on_ready=False)).pack(side="left", padx=(8, 0))
        self.btn_open_latest_zip = ttk.Button(top, text="Открыть архив", command=self._open_latest_bundle, state="disabled")
        self.btn_open_latest_zip.pack(side="left", padx=(8, 0))
        self.btn_open_analysis_evidence = ttk.Button(
            top,
            text="Открыть данные анализа",
            command=self._open_analysis_evidence,
            state="disabled",
        )
        self.btn_open_analysis_evidence.pack(side="left", padx=(8, 0))
        self.btn_open_geometry_reference_evidence = ttk.Button(
            top,
            text="Открыть геометрию",
            command=self._open_geometry_reference_evidence,
            state="disabled",
        )
        self.btn_open_geometry_reference_evidence.pack(side="left", padx=(8, 0))
        self.btn_open_engineering_analysis_evidence = ttk.Button(
            top,
            text="Открыть инженерный анализ",
            command=self._open_engineering_analysis_evidence,
            state="disabled",
        )
        self.btn_open_engineering_analysis_evidence.pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Открыть папку архивов", command=self._open_bundle_out_dir).pack(side="left", padx=(8, 0))

        summary_box = ttk.LabelFrame(self.bundle_body, text="Сводка и полезные файлы")
        summary_box.pack(fill="both", expand=False, pady=(0, 8))
        summary_body, self.summary_text = build_scrolled_text(summary_box, wrap="word", height=8)
        summary_body.pack(fill="both", expand=True)

        evidence_box = ttk.LabelFrame(self.bundle_body, text="Готовность данных для отправки")
        evidence_box.pack(fill="x", pady=(0, 8))
        evidence_box.columnconfigure(1, weight=1)
        ttk.Label(evidence_box, text="Анализ результатов").grid(row=0, column=0, sticky="w", padx=(10, 8), pady=(8, 4))
        ttk.Label(
            evidence_box,
            textvariable=self.analysis_evidence_status_var,
            wraplength=760,
            justify="left",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(8, 4))
        ttk.Label(evidence_box, text="Инженерный анализ").grid(
            row=1, column=0, sticky="w", padx=(10, 8), pady=(4, 4)
        )
        ttk.Label(
            evidence_box,
            textvariable=self.engineering_analysis_status_var,
            wraplength=760,
            justify="left",
        ).grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(4, 4))
        ttk.Label(evidence_box, text="Справочник геометрии").grid(row=2, column=0, sticky="w", padx=(10, 8), pady=(4, 8))
        ttk.Label(
            evidence_box,
            textvariable=self.geometry_reference_status_var,
            wraplength=760,
            justify="left",
        ).grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=(4, 8))

        preview_area = ttk.Frame(self.bundle_body)
        preview_area.pack(fill="both", expand=True)
        preview_area.columnconfigure(0, weight=1)
        preview_area.columnconfigure(1, weight=1)
        preview_area.rowconfigure(0, weight=1)
        inspect_box = ttk.LabelFrame(preview_area, text="Проверка архива", padding=6)
        inspect_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        health_box = ttk.LabelFrame(preview_area, text="Состояние проекта", padding=6)
        health_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        inspect_body, self.inspect_text = build_scrolled_text(inspect_box, wrap="word", height=10)
        inspect_body.pack(fill="both", expand=True)

        health_body, self.health_text = build_scrolled_text(health_box, wrap="word", height=10)
        health_body.pack(fill="both", expand=True)

    def _build_send_tab(self) -> None:
        frm = ttk.Frame(self.send_body, padding=14)
        frm.pack(fill="both", expand=True)

        self.lbl_title = ttk.Label(frm, textvariable=self.send_title_var, font=("Segoe UI", 12, "bold"))
        self.lbl_title.pack(anchor="w", pady=(0, 8))
        self.lbl_path_caption = ttk.Label(frm, text="Путь к архиву:")
        self.lbl_path_caption.pack(anchor="w")
        self.lbl_path = ttk.Label(frm, textvariable=self.send_path_var, wraplength=860)
        self.lbl_path.pack(anchor="w", pady=(2, 10))

        ttk.Label(
            frm,
            text=(
                "Архив для отправки собирается здесь. Прогресс любой длительной операции всегда показан "
                "в блоке «Текущий процесс» сверху, без переключения разделов."
            ),
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        self.lbl_meta = ttk.Label(frm, textvariable=self.send_meta_var, wraplength=860, justify="left")
        self.lbl_meta.pack(anchor="w", pady=(0, 10))

        btn_row = ttk.Frame(frm)
        btn_row.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_row, text="Собрать или обновить архив", command=lambda: self._start_bundle_build(auto_copy_on_ready=False)).pack(side="left")
        self.btn_copy = ttk.Button(btn_row, text="Скопировать архив в буфер обмена", command=self._copy)
        self.btn_copy.state(["disabled"])
        self.btn_copy.pack(side="left", padx=(8, 0), ipadx=10, ipady=6)
        ttk.Button(btn_row, text="Открыть папку архива", command=self._open_bundle_out_dir).pack(side="left", padx=(8, 0))

    def _select_initial_tab(self, initial_tab: str) -> None:
        lookup = {
            "diagnostics": self.diag_tab,
            "bundle": self.bundle_tab,
            "send": self.send_tab,
        }
        target = lookup.get(self._resolve_initial_tab_name(initial_tab), self.diag_tab)
        self.notebook.select(target)

    def _append(self, text: str) -> None:
        try:
            self.txt.insert("end", _operator_log_text(text))
            self.txt.see("end")
            self.txt.update_idletasks()
        except Exception:
            pass

    def _set_process_busy(self, title: str, detail: str) -> None:
        self.process_title_var.set(title)
        self.process_detail_var.set(detail)
        self.status_var.set(detail)
        if hasattr(self, "process_progress"):
            self.process_progress.configure(mode="indeterminate", maximum=100)
            self.process_progress.start(10)

    def _set_process_done(self, title: str, detail: str) -> None:
        self.process_title_var.set(title)
        self.process_detail_var.set(detail)
        self.status_var.set(detail)
        if hasattr(self, "process_progress"):
            self.process_progress.stop()
            self.process_progress.configure(mode="determinate", maximum=100, value=100)

    def _set_process_idle(self, detail: str | None = None) -> None:
        self.process_title_var.set("Текущий процесс: нет активной операции")
        self.process_detail_var.set(
            detail
            or "Прогресс проверки проекта и сборки архива всегда показывается здесь."
        )
        if hasattr(self, "process_progress"):
            self.process_progress.stop()
            self.process_progress.configure(mode="determinate", maximum=100, value=0)

    def _replace_log_text(self, text: str) -> None:
        try:
            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", text)
            self.txt.see("end")
            self.txt.update_idletasks()
        except Exception:
            pass

    def _set_text_widget(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.see("1.0")
        widget.configure(state="disabled")

    def _restored_ui_state(self) -> dict:
        payload = dict(self._restored_center_state or {})
        ui = payload.get("ui") if isinstance(payload.get("ui"), dict) else {}
        return dict(ui)

    def _coerce_bool(self, value, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off", ""}:
            return False
        return bool(default)

    def _coerce_int(self, value, default: int) -> int:
        try:
            if value in (None, ""):
                return int(default)
            return int(value)
        except Exception:
            return int(default)

    def _restore_bundle_state_from_last_center_state(self) -> None:
        ui = self._restored_ui_state()
        restored_bundle_out_dir = str(ui.get("active_bundle_out_dir") or "").strip()
        if not restored_bundle_out_dir:
            return
        try:
            self.out_dir = Path(restored_bundle_out_dir).expanduser().resolve()
        except Exception:
            self.out_dir = Path(restored_bundle_out_dir)
        reloaded_state = load_last_desktop_diagnostics_center_state(self.out_dir)
        if reloaded_state:
            self._restored_center_state = reloaded_state

    def _restore_diagnostics_request_from_last_center_state(self) -> None:
        ui = self._restored_ui_state()
        if not ui:
            return

        level = str(ui.get("level") or "").strip().lower()
        if level in {"minimal", "standard", "full"}:
            self.level.set(level)
        self.skip_ui_smoke.set(self._coerce_bool(ui.get("skip_ui_smoke"), bool(self.skip_ui_smoke.get())))
        self.no_zip.set(self._coerce_bool(ui.get("no_zip"), bool(self.no_zip.get())))
        self.run_opt_smoke.set(self._coerce_bool(ui.get("run_opt_smoke"), bool(self.run_opt_smoke.get())))
        self.opt_minutes.set(self._coerce_int(ui.get("opt_minutes"), int(self.opt_minutes.get())))
        self.opt_jobs.set(self._coerce_int(ui.get("opt_jobs"), int(self.opt_jobs.get())))

        osc_dir = str(ui.get("osc_dir") or "").strip()
        out_root = str(ui.get("out_root") or "").strip()
        status_text = str(ui.get("status_text") or "").strip()
        process_title_text = str(ui.get("process_title_text") or "").strip()
        process_detail_text = str(ui.get("process_detail_text") or "").strip()
        send_title_text = str(ui.get("send_title_text") or "").strip()
        send_path_text = str(ui.get("send_path_text") or "").strip()
        send_meta_text = str(ui.get("send_meta_text") or "")

        if osc_dir:
            self.osc_dir.set(osc_dir)
        if out_root:
            self.out_root.set(out_root)
        if status_text:
            self.status_var.set(status_text)
        if process_title_text:
            self.process_title_var.set(process_title_text)
        if process_detail_text:
            self.process_detail_var.set(process_detail_text)
        if send_title_text:
            self.send_title_var.set(send_title_text)
        if send_path_text:
            self.send_path_var.set(send_path_text)
        if send_meta_text:
            self.send_meta_var.set(send_meta_text)

    def _resolve_initial_tab_name(self, initial_tab: str) -> str:
        requested = str(initial_tab or "").strip().lower()
        restored = str(self._restored_ui_state().get("selected_tab") or "").strip().lower()
        valid = {"diagnostics", "bundle", "send"}
        if requested in valid:
            return requested
        if requested in {"restore", "last", "auto"} and restored in valid:
            return restored
        if not requested and restored in valid:
            return restored
        return "diagnostics"

    def _selected_tab_name(self) -> str:
        selected = str(self.notebook.select() or "")
        if selected == str(self.diag_tab):
            return "diagnostics"
        if selected == str(self.bundle_tab):
            return "bundle"
        if selected == str(self.send_tab):
            return "send"
        return "diagnostics"

    def _collect_ui_state_payload(self) -> dict[str, object]:
        return {
            "selected_tab": self._selected_tab_name(),
            "status_text": str(self.status_var.get() or ""),
            "process_title_text": str(self.process_title_var.get() or ""),
            "process_detail_text": str(self.process_detail_var.get() or ""),
            "machine_state_text": str(self.machine_state_var.get() or ""),
            "send_title_text": str(self.send_title_var.get() or ""),
            "send_path_text": str(self.send_path_var.get() or ""),
            "send_meta_text": str(self.send_meta_var.get() or ""),
            "bundle_busy": bool(self._bundle_busy),
            "diagnostics_running": bool(self._proc is not None),
            "clipboard_attempted": bool(self._clipboard_attempted),
            "clipboard_ok": bool(self._clipboard_ok),
            "worker_done": bool(self._worker_done),
            "worker_error": str(self._worker_exc or ""),
            "level": str(self.level.get() or "standard"),
            "skip_ui_smoke": bool(self.skip_ui_smoke.get()),
            "no_zip": bool(self.no_zip.get()),
            "run_opt_smoke": bool(self.run_opt_smoke.get()),
            "opt_minutes": int(self.opt_minutes.get()),
            "opt_jobs": int(self.opt_jobs.get()),
            "osc_dir": str(self.osc_dir.get() or ""),
            "out_root": str(self.out_root.get() or ""),
            "active_bundle_out_dir": path_str(self._active_bundle_out_dir()),
            "active_run_out_root": path_str(self._active_run_out_root()),
        }

    def _refresh_diagnostics_log_view(self) -> None:
        if self._proc is not None:
            return
        log_text = load_last_desktop_diagnostics_run_log_text(self._active_run_out_root())
        if not log_text and self._last_run_record and self._last_run_record.log_path:
            try:
                log_text = Path(self._last_run_record.log_path).read_text(encoding="utf-8", errors="replace")
            except Exception:
                log_text = ""
        if log_text.strip():
            self._replace_log_text(_operator_log_text(log_text))

    def _write_center_state_snapshot(self, bundle, *, summary_text: str) -> None:
        bundle_out_dir = Path(bundle.out_dir).expanduser().resolve()
        next_state_path = bundle_out_dir / LATEST_DESKTOP_DIAGNOSTICS_CENTER_JSON
        self.machine_state_var.set(f"Сводка обновлена. Папка архивов: {bundle_out_dir}")
        self._summary_md_path = write_desktop_diagnostics_summary_md(bundle_out_dir, summary_text)
        self._center_state_path = write_desktop_diagnostics_center_state(
            bundle_out_dir,
            bundle_record=bundle,
            run_record=self._last_run_record,
            summary_md_path=self._summary_md_path,
            ui_state=self._collect_ui_state_payload(),
        )
        self._external_state_signature = self._compute_external_state_signature()

    def _on_tab_changed(self, _event=None) -> None:
        try:
            current = self.notebook.tab(self.notebook.select(), "text")
        except Exception:
            current = ""
        if current:
            self.context_summary_var.set(
                f"Открыт шаг «{current}». Слева быстрые действия, справа рабочая область."
            )
        if self._last_bundle_record is None:
            return
        try:
            summary_text = str(self.summary_text.get("1.0", "end-1c"))
        except Exception:
            summary_text = self._render_summary_text(self._last_bundle_record, bundle_out_dir=self._active_bundle_out_dir())
        self._write_center_state_snapshot(self._last_bundle_record, summary_text=summary_text)

    def _start_run(self) -> None:
        self._run()

    def _open_bundle_dir(self) -> None:
        self._open_bundle_out_dir()

    def _pick_osc_dir(self) -> None:
        picked = filedialog.askdirectory(title="Выберите папку с файлами анимации")
        if picked:
            self.osc_dir.set(picked)

    def _pick_out_root(self) -> None:
        picked = filedialog.askdirectory(title="Выберите папку для отчётов проверки")
        if picked:
            self.out_root.set(picked)

    def _build_request(self) -> DesktopDiagnosticsRequest:
        osc_dir = str(self.osc_dir.get() or "").strip()
        if osc_dir:
            try:
                if not Path(osc_dir).expanduser().exists():
                    osc_dir = ""
            except Exception:
                osc_dir = ""
        return DesktopDiagnosticsRequest(
            level=str(self.level.get() or "standard").strip(),
            skip_ui_smoke=bool(self.skip_ui_smoke.get()),
            no_zip=bool(self.no_zip.get()),
            run_opt_smoke=bool(self.run_opt_smoke.get()),
            opt_minutes=int(self.opt_minutes.get()),
            opt_jobs=int(self.opt_jobs.get()),
            osc_dir=osc_dir,
            out_root=str(Path(self.out_root.get() or "").expanduser()),
        )

    def _build_cmd(self) -> list[str]:
        request = self._build_request()
        python_exe = _guess_python_exe()
        script = self.tools_dir / "run_full_diagnostics.py"
        return build_run_full_diagnostics_command(str(python_exe), script, request)

    def _run(self) -> None:
        if self._proc is not None:
            return

        request = self._build_request()
        cmd = self._build_cmd()
        self._current_run_lines = []
        self._append("\n=== Проверка проекта ===\nКоманда запуска сохранена в отчёте прогона.\n\n")
        self._set_process_busy(
            "Выполняется проверка проекта",
            "Идёт проверка проекта. Прогресс показан здесь; можно оставаться в текущем разделе.",
        )
        self.btn_run.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_open.configure(state="disabled")

        started_at = now_local_iso()
        out_root = request.resolved_out_root(self.repo_root)
        append_desktop_diagnostics_run_log(out_root, "")
        self._last_run_record = persist_desktop_diagnostics_run(
            out_root,
            DesktopDiagnosticsRunRecord(
                ok=False,
                started_at=started_at,
                finished_at="",
                status="running",
                command=[str(x) for x in cmd],
                returncode=None,
                run_dir="",
                zip_path="",
                out_root=path_str(out_root),
                last_message="running",
            ),
            log_text="",
        )
        self._refresh_bundle_views(regenerate_reports=False)

        def worker() -> None:
            rc = 125
            try:
                env = os.environ.copy()
                env.setdefault("PYTHONUTF8", "1")
                env.setdefault("PYTHONIOENCODING", "utf-8")

                self._proc = subprocess.Popen(
                    cmd,
                    cwd=str(self.repo_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    env=env,
                )
                assert self._proc.stdout is not None

                last_zip: Path | None = None
                last_run_dir: Path | None = None

                for line in self._proc.stdout:
                    self._current_run_lines.append(line)
                    append_desktop_diagnostics_run_log(out_root, line)
                    self.root.after(0, self._append, line)
                    updates = parse_run_full_diagnostics_output_line(line)
                    if updates.get("run_dir"):
                        try:
                            last_run_dir = Path(updates["run_dir"]).expanduser().resolve()
                        except Exception:
                            last_run_dir = Path(updates["run_dir"])
                    if updates.get("zip_path"):
                        try:
                            last_zip = Path(updates["zip_path"]).expanduser().resolve()
                        except Exception:
                            last_zip = Path(updates["zip_path"])
                    if updates.get("run_dir") or updates.get("zip_path"):
                        self._last_run_record = persist_desktop_diagnostics_run(
                            out_root,
                            DesktopDiagnosticsRunRecord(
                                ok=False,
                                started_at=started_at,
                                finished_at="",
                                status="running",
                                command=[str(x) for x in cmd],
                                returncode=None,
                                run_dir=path_str(last_run_dir),
                                zip_path=path_str(last_zip),
                                out_root=path_str(out_root),
                                last_message="running",
                            ),
                            log_text="",
                        )

                rc = int(self._proc.wait())
                self._proc = None
                self._last_zip = last_zip
                self._last_run_dir = last_run_dir

                last_message = "OK" if rc == 0 else f"код завершения {rc}"
                record = DesktopDiagnosticsRunRecord(
                    ok=bool(rc == 0),
                    started_at=started_at,
                    finished_at=now_local_iso(),
                    status="finished" if rc == 0 else "failed",
                    command=[str(x) for x in cmd],
                    returncode=rc,
                    run_dir=path_str(last_run_dir),
                    zip_path=path_str(last_zip),
                    out_root=path_str(out_root),
                    last_message=last_message,
                )
                self._last_run_record = persist_desktop_diagnostics_run(
                    out_root,
                    record,
                    log_text="".join(self._current_run_lines),
                )

                def done_ui() -> None:
                    if self._host_closed:
                        return
                    self.btn_run.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    self.btn_open.configure(state="normal" if (last_zip or last_run_dir) else "disabled")
                    self._set_process_done(
                        "Проверка проекта завершена" if rc == 0 else "Проверка проекта завершилась с ошибкой",
                        (
                            "Проверка проекта завершена успешно. Отчёт можно открыть кнопкой на вкладке проверки."
                            if rc == 0
                            else f"Проверка проекта завершилась с ошибкой. Код завершения {rc}. Отчёт можно открыть кнопкой на вкладке проверки."
                        ),
                    )
                    self._refresh_bundle_views(regenerate_reports=False)

                    msg = "Проверка проекта завершена успешно." if rc == 0 else f"Проверка проекта завершилась с ошибкой. Код завершения {rc}."
                    if last_zip:
                        msg += f"\n\nАрхив: {last_zip}"
                    if last_run_dir:
                        msg += f"\n\nПапка: {last_run_dir}"
                    if self._last_run_record and self._last_run_record.state_path:
                        msg += f"\n\nФайл состояния работы: {self._last_run_record.state_path}"
                    if rc == 0:
                        messagebox.showinfo("Проверка проекта", msg)
                    else:
                        messagebox.showwarning("Проверка проекта", msg)

                self.root.after(0, done_ui)
            except Exception as exc:
                self._proc = None
                record = DesktopDiagnosticsRunRecord(
                    ok=False,
                    started_at=started_at,
                    finished_at=now_local_iso(),
                    status="failed",
                    command=[str(x) for x in cmd],
                    returncode=rc,
                    run_dir="",
                    zip_path="",
                    out_root=path_str(out_root),
                    last_message=f"{type(exc).__name__}: {exc}",
                )
                self._last_run_record = persist_desktop_diagnostics_run(
                    out_root,
                    record,
                    log_text="".join(self._current_run_lines),
                )

                def err_ui() -> None:
                    if self._host_closed:
                        return
                    self.btn_run.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    self.btn_open.configure(state="disabled")
                    self._set_process_done(
                        "Ошибка запуска проверки проекта",
                        f"Проверка проекта не запустилась: {_technical_message_ru(exc)}",
                    )
                    self._refresh_bundle_views(regenerate_reports=False)
                    messagebox.showerror("Проверка проекта", f"Не удалось запустить проверку проекта:\n{_technical_message_ru(exc)}")

                self.root.after(0, err_ui)

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def _stop(self) -> None:
        if self._proc is None:
            return
        if self._last_run_record is not None:
            stop_out_root = self._last_run_record.out_root or path_str(self._active_run_out_root())
            self._last_run_record = persist_desktop_diagnostics_run(
                Path(stop_out_root),
                DesktopDiagnosticsRunRecord(
                    ok=False,
                    started_at=self._last_run_record.started_at,
                    finished_at="",
                    status="stopping",
                    command=[str(x) for x in (self._last_run_record.command or [])],
                    returncode=None,
                    run_dir=self._last_run_record.run_dir,
                    zip_path=self._last_run_record.zip_path,
                    out_root=self._last_run_record.out_root,
                    last_message="terminate_requested",
                ),
                log_text="",
            )
        try:
            self._proc.terminate()
            self._append("\n[Окно] Запрошена остановка процесса...\n")
            self._set_process_busy("Останавливаю проверку проекта", "Команда остановки отправлена. Жду завершения процесса.")
        except Exception:
            pass

    def _open_result(self) -> None:
        target = self._last_zip or self._last_run_dir
        if not target:
            return
        if target.is_file():
            _open_in_explorer(target.parent)
        else:
            _open_in_explorer(target)

    def _open_diagnostics_out_root(self) -> None:
        try:
            _open_in_explorer(Path(self.out_root.get()).expanduser().resolve())
        except Exception:
            pass

    def _open_bundle_out_dir(self) -> None:
        _open_in_explorer(self._active_bundle_out_dir())

    def _open_latest_bundle(self) -> None:
        bundle = load_desktop_diagnostics_bundle_record(self.repo_root, out_dir=self._active_bundle_out_dir())
        if not bundle.latest_zip_path:
            return
        _open_in_explorer(Path(bundle.latest_zip_path).expanduser().resolve().parent)

    def _open_analysis_evidence(self) -> None:
        bundle = load_desktop_diagnostics_bundle_record(self.repo_root, out_dir=self._active_bundle_out_dir())
        if not bundle.latest_analysis_evidence_manifest_path:
            return
        path = Path(bundle.latest_analysis_evidence_manifest_path).expanduser().resolve()
        if path.exists():
            _open_in_explorer(path)

    def _open_geometry_reference_evidence(self) -> None:
        bundle = load_desktop_diagnostics_bundle_record(self.repo_root, out_dir=self._active_bundle_out_dir())
        if not bundle.latest_geometry_reference_evidence_path:
            return
        path = Path(bundle.latest_geometry_reference_evidence_path).expanduser().resolve()
        if path.exists():
            _open_in_explorer(path)

    def _open_engineering_analysis_evidence(self) -> None:
        bundle = load_desktop_diagnostics_bundle_record(self.repo_root, out_dir=self._active_bundle_out_dir())
        if not bundle.latest_engineering_analysis_evidence_manifest_path:
            return
        path = Path(bundle.latest_engineering_analysis_evidence_manifest_path).expanduser().resolve()
        if path.exists():
            _open_in_explorer(path)

    def _latest_integrity_summary_lines(self, bundle) -> list[str]:
        status = str(getattr(bundle, "latest_integrity_status", "") or "MISSING").strip().upper()
        warnings = [
            str(item).strip()
            for item in (getattr(bundle, "latest_integrity_warnings", None) or [])
            if str(item).strip()
        ]
        lines = [
            "## Проверка актуального архива",
            f"- Состояние: {_status_ru(status)}",
            f"- SHA256 актуального архива: {getattr(bundle, 'latest_integrity_final_zip_sha256', '') or '—'}",
            (
                "- Актуальный архив совпадает с исходным: "
                f"{_bool_ru(getattr(bundle, 'latest_integrity_latest_zip_matches_original', None))}"
            ),
            f"- SHA-файл совпадает: {_bool_ru(getattr(bundle, 'latest_integrity_sha_sidecar_matches', None))}",
            f"- Ссылка на архив совпадает: {_bool_ru(getattr(bundle, 'latest_integrity_pointer_matches_original', None))}",
            f"- Файл подтверждения: {getattr(bundle, 'latest_integrity_evidence_sidecar_path', '') or '—'}",
            (
                "- Область SHA256 во вложенном файле состава: "
                f"{getattr(bundle, 'latest_integrity_embedded_manifest_zip_sha256_scope', '') or '—'}"
            ),
            (
                "- Этап во вложенном файле состава: "
                f"{getattr(bundle, 'latest_integrity_embedded_manifest_stage', '') or '—'} / "
                f"{getattr(bundle, 'latest_integrity_embedded_manifest_finalization_stage', '') or '—'}"
            ),
            (
                "- Запуск: "
                f"{getattr(bundle, 'latest_integrity_trigger', '') or '—'} / "
                f"сбор={getattr(bundle, 'latest_integrity_collection_mode', '') or '—'}"
            ),
            f"- Предупреждения от источников данных: {getattr(bundle, 'latest_integrity_producer_warning_count', 0)}",
            "- Предупреждения от источников данных остаются предупреждениями; окончательное решение остаётся за пользователем.",
            (
                "- Итоговое решение требует проверки пользователя: "
                f"{_bool_ru(getattr(bundle, 'latest_integrity_no_release_closure_claim', True))}"
            ),
        ]
        for warning in warnings[:5]:
            lines.append(f"- Предупреждение: {_technical_message_ru(warning)}")
        return lines

    def _self_check_silent_warnings_summary_lines(self, bundle) -> list[str]:
        return [
            "## Снимок скрытых предупреждений проверки",
            f"- Состояние: {_status_ru(getattr(bundle, 'self_check_silent_warnings_status', '') or 'MISSING')}",
            f"- Только снимок: {_bool_ru(getattr(bundle, 'self_check_silent_warnings_snapshot_only', True))}",
            f"- Файл подробностей: {getattr(bundle, 'self_check_silent_warnings_json_path', '') or '—'}",
            f"- Краткий отчёт: {getattr(bundle, 'self_check_silent_warnings_md_path', '') or '—'}",
            f"- Код завершения: {getattr(bundle, 'self_check_silent_warnings_rc', None)}",
            f"- Ошибки: {getattr(bundle, 'self_check_silent_warnings_fail_count', 0)}",
            f"- Предупреждения: {getattr(bundle, 'self_check_silent_warnings_warn_count', 0)}",
            "- Эта справка не отменяет предупреждения отправки или источников данных.",
        ]

    def _analysis_evidence_summary_lines(self, bundle) -> list[str]:
        status = str(getattr(bundle, "analysis_evidence_status", "") or "MISSING").strip().upper()
        context_state = str(getattr(bundle, "analysis_evidence_context_state", "") or "MISSING")
        warnings = [
            str(item).strip()
            for item in (getattr(bundle, "analysis_evidence_warnings", None) or [])
            if str(item).strip()
        ]
        lines = [
            "## Данные анализа результатов",
            f"- Состояние: {_status_ru(status)}",
            f"- Выбранные данные: {_status_ru(context_state)}",
            f"- Связь с анимацией: {_status_ru(getattr(bundle, 'analysis_context_status', '') or '—')}",
            f"- Метка расчёта: {getattr(bundle, 'analysis_evidence_run_id', '') or '—'}",
            f"- Метка правил расчёта: {getattr(bundle, 'analysis_evidence_run_contract_hash', '') or '—'}",
            f"- Правила сравнения: {getattr(bundle, 'analysis_evidence_compare_contract_id', '') or '—'}",
            f"- Файлы данных: {getattr(bundle, 'analysis_evidence_artifact_count', 0)}",
            f"- Расхождения: {getattr(bundle, 'analysis_evidence_mismatch_count', 0)}",
            f"- Файл состава: {getattr(bundle, 'latest_analysis_evidence_manifest_path', '') or '—'}",
        ]
        if getattr(bundle, "analysis_selected_test_id", ""):
            lines.append(f"- Выбранный тест: {bundle.analysis_selected_test_id}")
        if getattr(bundle, "analysis_selected_npz_path", ""):
            lines.append(f"- Файл анимации: {bundle.analysis_selected_npz_path}")
        capture_handoff = str(getattr(bundle, "analysis_capture_export_manifest_handoff_id", "") or "")
        capture_hash = str(getattr(bundle, "analysis_capture_hash", "") or "")
        capture_status = str(getattr(bundle, "analysis_capture_export_manifest_status", "") or "").strip().upper()
        if capture_status not in {"READY", "DEGRADED", "MISSING"}:
            if capture_handoff == "HO-010" and capture_hash:
                capture_status = "READY"
            elif capture_handoff or capture_hash:
                capture_status = "DEGRADED"
            else:
                capture_status = "MISSING"
        lines.append(
            "- Файлы для аниматора: "
            f"{_status_ru(capture_status)} | проверка={capture_hash or '—'}"
        )
        manifest_hash = str(getattr(bundle, "analysis_evidence_manifest_hash", "") or "")
        if manifest_hash:
            lines.append(f"- Метка состава данных: {manifest_hash}")
        action = str(getattr(bundle, "analysis_evidence_action", "") or "")
        if action:
            lines.append(f"- Что сделать: {_technical_message_ru(action)}")
        analysis_context_action = str(getattr(bundle, "analysis_context_action", "") or "")
        if analysis_context_action:
            lines.append(f"- Что сделать со связью с аниматором: {_technical_message_ru(analysis_context_action)}")
        for warning in warnings[:5]:
            lines.append(f"- Предупреждение: {_technical_message_ru(warning)}")
        return lines

    def _engineering_analysis_evidence_summary_lines(self, bundle) -> list[str]:
        status = str(getattr(bundle, "engineering_analysis_evidence_status", "") or "MISSING").strip().upper()
        readiness_status = str(getattr(bundle, "engineering_analysis_readiness_status", "") or status).strip().upper()
        open_gap_status = str(getattr(bundle, "engineering_analysis_open_gap_status", "") or "MISSING").strip().upper()
        open_gap_reasons = [
            str(item).strip()
            for item in (getattr(bundle, "engineering_analysis_open_gap_reasons", None) or [])
            if str(item).strip()
        ]
        validation_status = str(getattr(bundle, "engineering_analysis_validation_status", "") or "MISSING")
        candidate_count = int(getattr(bundle, "engineering_analysis_candidate_count", 0) or 0)
        ready_count = int(getattr(bundle, "engineering_analysis_ready_candidate_count", 0) or 0)
        missing_count = int(getattr(bundle, "engineering_analysis_missing_inputs_candidate_count", 0) or 0)
        failed_count = int(getattr(bundle, "engineering_analysis_failed_candidate_count", 0) or 0)
        missing_inputs = [
            str(item).strip()
            for item in (getattr(bundle, "engineering_analysis_candidate_unique_missing_inputs", None) or [])
            if str(item).strip()
        ]
        ready_run_dirs = [
            str(item).strip()
            for item in (getattr(bundle, "engineering_analysis_candidate_ready_run_dirs", None) or [])
            if str(item).strip()
        ]
        warnings = [
            str(item).strip()
            for item in (getattr(bundle, "engineering_analysis_evidence_warnings", None) or [])
            if str(item).strip()
        ]
        lines = [
            "## Данные инженерного анализа",
            f"- Состояние: {_status_ru(status)}",
            f"- Готовность: {_status_ru(readiness_status)}",
            f"- Незакрытые вопросы: {_status_ru(open_gap_status)}",
            (
                "- Итоговое решение требует проверки пользователя: "
                f"{_bool_ru(getattr(bundle, 'engineering_analysis_no_release_closure_claim', True))}"
            ),
            f"- Проверка: {_status_ru(validation_status)}",
            (
                "- Кандидаты расчёта: "
                f"готово={ready_count} / не хватает входных данных={missing_count} / "
                f"ошибки={failed_count} / всего={candidate_count}"
            ),
            f"- Файл состава: {getattr(bundle, 'latest_engineering_analysis_evidence_manifest_path', '') or '—'}",
        ]
        manifest_hash = str(getattr(bundle, "engineering_analysis_evidence_manifest_hash", "") or "")
        if manifest_hash:
            lines.append(f"- Метка состава данных: {manifest_hash}")
        if ready_run_dirs:
            lines.append(f"- Каталог готового расчёта: {ready_run_dirs[0]}")
        if missing_inputs:
            lines.append(f"- Не хватает входных данных: {', '.join(missing_inputs[:8])}")
        if open_gap_reasons:
            lines.append(f"- Причины незакрытых вопросов: {', '.join(_technical_message_ru(x) for x in open_gap_reasons[:8])}")
        action = str(getattr(bundle, "engineering_analysis_evidence_action", "") or "")
        if action:
            lines.append(f"- Что сделать: {_technical_message_ru(action)}")
        for warning in warnings[:5]:
            lines.append(f"- Предупреждение: {_technical_message_ru(warning)}")
        return lines

    def _analysis_evidence_status_text(self, bundle) -> str:
        status = str(getattr(bundle, "analysis_evidence_status", "") or "MISSING").strip().upper()
        context_state = str(getattr(bundle, "analysis_evidence_context_state", "") or "MISSING")
        run_id = str(getattr(bundle, "analysis_evidence_run_id", "") or "—")
        artifacts = int(getattr(bundle, "analysis_evidence_artifact_count", 0) or 0)
        mismatches = int(getattr(bundle, "analysis_evidence_mismatch_count", 0) or 0)
        action = str(getattr(bundle, "analysis_evidence_action", "") or "")
        analysis_context_status = str(getattr(bundle, "analysis_context_status", "") or "—")
        analysis_context_action = str(getattr(bundle, "analysis_context_action", "") or "")
        text = (
            f"{_status_ru(status)}; выбранные данные: {_status_ru(context_state)}; "
            f"связь с анимацией: {_status_ru(analysis_context_status)}; расчёт: {run_id}; "
            f"файлов данных: {artifacts}; расхождений: {mismatches}"
        )
        if analysis_context_action:
            text += f"\n{_technical_message_ru(analysis_context_action)}"
        if action and status != "READY":
            text += f"\n{_technical_message_ru(action)}"
        return text

    def _engineering_analysis_status_text(self, bundle) -> str:
        status = str(getattr(bundle, "engineering_analysis_evidence_status", "") or "MISSING").strip().upper()
        readiness_status = str(getattr(bundle, "engineering_analysis_readiness_status", "") or status).strip().upper()
        open_gap_status = str(getattr(bundle, "engineering_analysis_open_gap_status", "") or "MISSING").strip().upper()
        open_gap_reasons = [
            str(item).strip()
            for item in (getattr(bundle, "engineering_analysis_open_gap_reasons", None) or [])
            if str(item).strip()
        ]
        validation_status = str(getattr(bundle, "engineering_analysis_validation_status", "") or "MISSING")
        candidate_count = int(getattr(bundle, "engineering_analysis_candidate_count", 0) or 0)
        ready_count = int(getattr(bundle, "engineering_analysis_ready_candidate_count", 0) or 0)
        missing_count = int(getattr(bundle, "engineering_analysis_missing_inputs_candidate_count", 0) or 0)
        failed_count = int(getattr(bundle, "engineering_analysis_failed_candidate_count", 0) or 0)
        missing_inputs = [
            str(item).strip()
            for item in (getattr(bundle, "engineering_analysis_candidate_unique_missing_inputs", None) or [])
            if str(item).strip()
        ]
        action = str(getattr(bundle, "engineering_analysis_evidence_action", "") or "")
        text = (
            f"{_status_ru(status)}; готовность: {_status_ru(readiness_status)}; "
            f"открытые вопросы: {_status_ru(open_gap_status)}; проверка: {_status_ru(validation_status)}; "
            f"готовых кандидатов: {ready_count}/{candidate_count}; "
            f"кандидатов без входных данных: {missing_count}; ошибок: {failed_count}"
        )
        if missing_inputs:
            text += f"\nНе хватает входных данных: {', '.join(missing_inputs[:8])}"
        if open_gap_reasons:
            text += f"\nПричины незакрытых вопросов: {', '.join(_technical_message_ru(x) for x in open_gap_reasons[:6])}"
        if action and (status != "READY" or open_gap_status == "OPEN"):
            text += f"\n{_technical_message_ru(action)}"
        return text

    def _geometry_reference_evidence_summary_lines(self, bundle) -> list[str]:
        status = str(getattr(bundle, "geometry_reference_status", "") or "MISSING").strip().upper()
        warnings = [
            str(item).strip()
            for item in (getattr(bundle, "geometry_reference_warnings", None) or [])
            if str(item).strip()
        ]
        missing = [
            str(item).strip()
            for item in (getattr(bundle, "geometry_reference_evidence_missing", None) or [])
            if str(item).strip()
        ]
        lines = [
            "## Данные справочника геометрии",
            f"- Состояние: {_status_ru(status)}",
            f"- Данные: {_status_ru(getattr(bundle, 'geometry_reference_artifact_status', '') or 'missing')}",
            (
                "- Актуальность данных: "
                f"{_status_ru(getattr(bundle, 'geometry_reference_artifact_freshness_status', '') or 'missing')} / "
                f"связь={_status_ru(getattr(bundle, 'geometry_reference_artifact_freshness_relation', '') or 'missing')} / "
                f"последний={_status_ru(getattr(bundle, 'geometry_reference_latest_artifact_status', '') or '—')}"
            ),
            (
                "- Ширина дороги, м: "
                f"{_status_ru(getattr(bundle, 'geometry_reference_road_width_status', '') or 'missing')} / "
                f"источник={getattr(bundle, 'geometry_reference_road_width_source', '') or '—'}"
            ),
            (
                "- Упаковка данных: "
                f"{_status_ru(getattr(bundle, 'geometry_reference_packaging_status', '') or 'missing')} / "
                f"расхождения={_status_ru(getattr(bundle, 'geometry_reference_packaging_mismatch_status', '') or 'missing')}"
            ),
            f"- Метка правил упаковки: {getattr(bundle, 'geometry_reference_packaging_contract_hash', '') or '—'}",
            f"- Приёмка геометрии: {_status_ru(getattr(bundle, 'geometry_reference_acceptance_gate', '') or 'MISSING')}",
            (
                "- Данные источника: "
                f"{_status_ru(getattr(bundle, 'geometry_reference_producer_artifact_status', '') or 'missing')} / "
                f"источник={_producer_owner_ru(getattr(bundle, 'geometry_reference_producer_evidence_owner', '') or 'producer_export')}"
            ),
            (
                "- Автоматически добавлять недостающую геометрию: "
                f"{_bool_ru(bool(getattr(bundle, 'geometry_reference_consumer_may_fabricate_geometry', False)))}"
            ),
            (
                "- Паспорту компонентов нужны данные: "
                f"{getattr(bundle, 'geometry_reference_component_passport_needs_data', 0)}"
            ),
            f"- Файл данных: {getattr(bundle, 'latest_geometry_reference_evidence_path', '') or '—'}",
        ]
        action = str(getattr(bundle, "geometry_reference_action", "") or "")
        producer_readiness_reasons = [
            str(item).strip()
            for item in (getattr(bundle, "geometry_reference_producer_readiness_reasons", None) or [])
            if str(item).strip()
        ]
        required_artifacts = [
            str(item).strip()
            for item in (getattr(bundle, "geometry_reference_producer_required_artifacts", None) or [])
            if str(item).strip()
        ]
        if missing:
            lines.append(f"- Не хватает: {', '.join(missing)}")
        if producer_readiness_reasons:
            lines.append(f"- Причины неготовности источника: {', '.join(_technical_message_ru(x) for x in producer_readiness_reasons)}")
        if required_artifacts:
            lines.append(f"- Требуемые файлы источника: {', '.join(required_artifacts)}")
        if action:
            lines.append(f"- Что сделать: {_technical_message_ru(action)}")
        for warning in warnings[:5]:
            lines.append(f"- Предупреждение: {_technical_message_ru(warning)}")
        return lines

    def _geometry_reference_status_text(self, bundle) -> str:
        status = str(getattr(bundle, "geometry_reference_status", "") or "MISSING").strip().upper()
        artifact = str(getattr(bundle, "geometry_reference_artifact_status", "") or "missing")
        freshness = str(getattr(bundle, "geometry_reference_artifact_freshness_status", "") or "missing")
        relation = str(getattr(bundle, "geometry_reference_artifact_freshness_relation", "") or "missing")
        road = str(getattr(bundle, "geometry_reference_road_width_status", "") or "missing")
        packaging = str(getattr(bundle, "geometry_reference_packaging_mismatch_status", "") or "missing")
        gate = str(getattr(bundle, "geometry_reference_acceptance_gate", "") or "MISSING")
        producer = str(getattr(bundle, "geometry_reference_producer_artifact_status", "") or "missing")
        producer_readiness_reasons = [
            str(item).strip()
            for item in (getattr(bundle, "geometry_reference_producer_readiness_reasons", None) or [])
            if str(item).strip()
        ]
        missing = [
            str(item).strip()
            for item in (getattr(bundle, "geometry_reference_evidence_missing", None) or [])
            if str(item).strip()
        ]
        action = str(getattr(bundle, "geometry_reference_action", "") or "")
        text = (
            f"{_status_ru(status)} / данные={_status_ru(artifact)} / "
            f"актуальность={_status_ru(freshness)}:{_status_ru(relation)} / "
            f"ширина дороги={_status_ru(road)} / упаковка={_status_ru(packaging)} / "
            f"приёмка={_status_ru(gate)} / источник={_status_ru(producer)}"
        )
        if missing:
            text += f"\nНе хватает: {', '.join(missing)}"
        if producer_readiness_reasons:
            text += f"\nПричины неготовности источника: {', '.join(_technical_message_ru(x) for x in producer_readiness_reasons)}"
        if action and status != "READY":
            text += f"\n{_technical_message_ru(action)}"
        return text

    def _render_summary_text(self, bundle, *, bundle_out_dir: Path | None = None) -> str:
        bundle_out_dir = bundle_out_dir or self._active_bundle_out_dir()
        center_state_path = bundle_out_dir / LATEST_DESKTOP_DIAGNOSTICS_CENTER_JSON
        summary_md_path = bundle_out_dir / LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD
        lines = ["# Сводка диагностики и архива отправки", ""]
        if bundle.latest_zip_path:
            lines.append(f"- Последний архив: {bundle.latest_zip_path}")
        else:
            lines.append("- Последний архив: (ещё не готов)")
        if self._last_run_record is not None:
            lines.extend(
                [
                    "",
                    "## Последний прогон диагностики",
                    f"- Успех: {_bool_ru(self._last_run_record.ok)}",
                    f"- Состояние: {_status_ru(self._last_run_record.status or '—')}",
                    f"- Код завершения: {self._last_run_record.returncode}",
                    f"- Запущено: {self._last_run_record.started_at or '—'}",
                    f"- Завершено: {self._last_run_record.finished_at or '—'}",
                    f"- Папка последнего запуска: {self._last_run_record.run_dir or '—'}",
                    f"- Путь к архиву: {self._last_run_record.zip_path or '—'}",
                    f"- Файл состояния работы: {self._last_run_record.state_path or '—'}",
                    f"- Файл журнала: {self._last_run_record.log_path or '—'}",
                    f"- Сообщение: {_technical_message_ru(self._last_run_record.last_message or '—')}",
                ]
            )
        if bundle.summary_lines:
            lines.extend(["", "## Общая сводка"])
            lines.extend(f"- {_technical_message_ru(line)}" for line in bundle.summary_lines)
        lines.append("")
        lines.extend(self._latest_integrity_summary_lines(bundle))
        lines.append("")
        lines.extend(self._self_check_silent_warnings_summary_lines(bundle))
        lines.append("")
        lines.extend(self._analysis_evidence_summary_lines(bundle))
        lines.append("")
        lines.extend(self._engineering_analysis_evidence_summary_lines(bundle))
        lines.append("")
        lines.extend(self._geometry_reference_evidence_summary_lines(bundle))
        lines.extend(
            [
                "",
                "## Полезные файлы и отчёты",
                f"- Сохранённое состояние проверки: {path_str(center_state_path)}",
                f"- Последняя сводка Markdown: {path_str(summary_md_path)}",
                f"- Последний архив: {bundle.latest_zip_path or '—'}",
                f"- Ссылка на актуальный архив: {bundle.latest_path_pointer_path or '—'}",
                f"- SHA256 актуального архива: {bundle.latest_sha_path or '—'}",
                f"- Метаданные архива: {bundle.latest_bundle_meta_path or '—'}",
                f"- Проверка архива: {bundle.latest_inspection_json_path or '—'}",
                f"- Отчёт проверки архива: {bundle.latest_inspection_md_path or '—'}",
                f"- Отчёт о состоянии: {bundle.latest_health_json_path or '—'}",
                f"- Читаемый отчёт о состоянии: {bundle.latest_health_md_path or '—'}",
                f"- Проверка содержимого: {bundle.latest_validation_json_path or '—'}",
                f"- Читаемая проверка содержимого: {bundle.latest_validation_md_path or '—'}",
                f"- Разбор замечаний: {bundle.latest_triage_md_path or '—'}",
                f"- Файл состава данных: {bundle.latest_evidence_manifest_path or '—'}",
                f"- Подтверждение целостности актуального архива: {bundle.latest_integrity_evidence_sidecar_path or '—'}",
                f"- Предупреждения проверки: {bundle.self_check_silent_warnings_json_path or '—'}",
                f"- Читаемые предупреждения проверки: {bundle.self_check_silent_warnings_md_path or '—'}",
                f"- Данные анализа результатов: {bundle.latest_analysis_evidence_manifest_path or '—'}",
                (
                    "- Данные инженерного анализа: "
                    f"{bundle.latest_engineering_analysis_evidence_manifest_path or '—'}"
                ),
                f"- Данные справочника геометрии: {bundle.latest_geometry_reference_evidence_path or '—'}",
                f"- Состояние буфера обмена: {bundle.latest_clipboard_status_path or '—'}",
                f"- Диагностика последней анимации: {bundle.anim_pointer_diagnostics_path or '—'}",
                f"- Последний файл состояния прогона: {self._last_run_record.state_path if self._last_run_record else '—'}",
                f"- Последний журнал прогона: {self._last_run_record.log_path if self._last_run_record else '—'}",
            ]
        )
        return "\n".join(lines) + "\n"

    def _refresh_bundle_views(self, *, regenerate_reports: bool) -> None:
        bundle_out_dir = self._active_bundle_out_dir()
        self._last_run_record = load_last_desktop_diagnostics_run_record(self._active_run_out_root()) or self._last_run_record
        if self._last_run_record and self._last_run_record.run_dir:
            try:
                self._last_run_dir = Path(self._last_run_record.run_dir).expanduser().resolve()
            except Exception:
                self._last_run_dir = Path(self._last_run_record.run_dir)
        if self._last_run_record and self._last_run_record.zip_path:
            try:
                self._last_zip = Path(self._last_run_record.zip_path).expanduser().resolve()
            except Exception:
                self._last_zip = Path(self._last_run_record.zip_path)
        if regenerate_reports:
            bundle = refresh_desktop_diagnostics_bundle_record(self.repo_root, out_dir=bundle_out_dir, zip_path=self.zip_path)
        else:
            bundle = load_desktop_diagnostics_bundle_record(self.repo_root, out_dir=bundle_out_dir)

        self._last_bundle_record = bundle
        self.out_dir = Path(bundle.out_dir).expanduser().resolve()
        self._refresh_diagnostics_log_view()
        summary_text = self._render_summary_text(bundle, bundle_out_dir=self.out_dir)
        self._set_text_widget(self.summary_text, summary_text)
        inspect_md = "(проверка архива пока недоступна)"
        health_md = "(отчёт о состоянии пока недоступен)"
        if bundle.latest_inspection_md_path:
            inspect_md = _operator_preview_text(
                Path(bundle.latest_inspection_md_path).read_text(encoding="utf-8", errors="replace")
            )
        if bundle.latest_health_md_path:
            health_md = _operator_preview_text(
                Path(bundle.latest_health_md_path).read_text(encoding="utf-8", errors="replace")
            )
        self._set_text_widget(self.inspect_text, inspect_md)
        self._set_text_widget(self.health_text, health_md)

        self._last_zip = Path(bundle.latest_zip_path).expanduser().resolve() if bundle.latest_zip_path else self._last_zip
        self.zip_path = self._last_zip
        self.btn_open.configure(state="normal" if (self._last_zip or self._last_run_dir) else "disabled")
        self.btn_open_latest_zip.configure(state="normal" if bundle.latest_zip_path else "disabled")
        self.btn_open_analysis_evidence.configure(
            state="normal" if bundle.latest_analysis_evidence_manifest_path else "disabled"
        )
        self.btn_open_geometry_reference_evidence.configure(
            state="normal" if bundle.latest_geometry_reference_evidence_path else "disabled"
        )
        self.btn_open_engineering_analysis_evidence.configure(
            state="normal" if bundle.latest_engineering_analysis_evidence_manifest_path else "disabled"
        )
        self.send_path_var.set(bundle.latest_zip_path or "(ещё не готово)")
        if bundle.latest_zip_path:
            zip_path = Path(bundle.latest_zip_path)
            try:
                self.size_mb = zip_path.stat().st_size / (1024 * 1024)
                self.sha256 = _sha256_file(zip_path)
                meta_bits = [f"Размер: {self.size_mb:.2f} MB", f"SHA256: {self.sha256}"]
            except Exception:
                self.size_mb = 0.0
                self.sha256 = ""
                meta_bits = []
        else:
            self.size_mb = 0.0
            self.sha256 = ""
            meta_bits = []

        if bundle.summary_lines:
            meta_bits.append("Подробная сводка обновлена на вкладке «Собрать архив».")
        meta_bits.append(
            "Целостность актуального архива: "
            f"{_status_ru(bundle.latest_integrity_status)}; "
            f"SHA-файл: {_bool_ru(bundle.latest_integrity_sha_sidecar_matches)}; "
            f"ссылка: {_bool_ru(bundle.latest_integrity_pointer_matches_original)}; "
            f"нужна проверка пользователя: {_bool_ru(bundle.latest_integrity_no_release_closure_claim)}"
        )
        meta_bits.append(
            "Снимок скрытых предупреждений проверки: "
            f"{_status_ru(bundle.self_check_silent_warnings_status)}; "
            f"ошибок: {bundle.self_check_silent_warnings_fail_count}; "
            f"предупреждений: {bundle.self_check_silent_warnings_warn_count}; только снимок: да"
        )
        meta_bits.append("Предупреждения источников данных остаются предупреждениями; окончательное решение остаётся за пользователем.")
        self.analysis_evidence_status_var.set(
            "Данные анализа результатов: " + self._analysis_evidence_status_text(bundle)
        )
        self.engineering_analysis_status_var.set(
            "Данные инженерного анализа: " + self._engineering_analysis_status_text(bundle)
        )
        self.geometry_reference_status_var.set(
            "Данные справочника геометрии: " + self._geometry_reference_status_text(bundle)
        )
        meta_bits.append(str(self.analysis_evidence_status_var.get() or ""))
        meta_bits.append(str(self.engineering_analysis_status_var.get() or ""))
        meta_bits.append(str(self.geometry_reference_status_var.get() or ""))
        if bundle.anim_pointer_diagnostics_path:
            meta_bits.append(f"Диагностика последней анимации: {bundle.anim_pointer_diagnostics_path}")
        if bundle.clipboard_ok is not None:
            meta_bits.append(f"Буфер обмена: {_bool_ru(bundle.clipboard_ok)}; {_technical_message_ru(bundle.clipboard_message)}")
        self.send_meta_var.set("\n".join(meta_bits))

        self._clipboard_ok = bool(bundle.clipboard_ok) if bundle.clipboard_ok is not None else False
        self._clipboard_message = str(bundle.clipboard_message or "")
        if bundle.latest_zip_path:
            if self._clipboard_ok:
                self.send_title_var.set("Архив для отправки в чат готов и уже скопирован в буфер.")
                self.btn_copy.configure(text="Скопировать архив ещё раз")
            elif self._clipboard_message and "Путь к архиву скопирован как текст" in _technical_message_ru(self._clipboard_message):
                self.send_title_var.set("Архив готов. Путь к архиву скопирован как текст; файловый буфер обмена не подтвердился.")
                self.btn_copy.configure(text="Скопировать архив в буфер обмена")
            else:
                self.send_title_var.set("Архив для отправки в чат готов.")
                self.btn_copy.configure(text="Скопировать архив в буфер обмена")
            self.btn_copy.state(["!disabled"])
        else:
            self.send_title_var.set("Архив для отправки в чат ещё не готов.")
            self.btn_copy.state(["disabled"])

        self._write_center_state_snapshot(bundle, summary_text=summary_text)

    def _start_bundle_build(self, *, auto_copy_on_ready: bool) -> None:
        if self._bundle_busy:
            return

        self._bundle_busy = True
        self._worker_done = False
        self._worker_exc = None
        self._bundle_auto_copy_on_ready = bool(auto_copy_on_ready)
        if auto_copy_on_ready:
            self._clipboard_attempted = False
        self.send_title_var.set("Собираю архив для отправки...")
        self.send_path_var.set("(ещё не готово)")
        self.send_meta_var.set("")
        self.btn_copy.state(["disabled"])
        self._set_process_busy(
            "Собирается архив для отправки",
            "Идёт сборка архива для отправки. Прогресс показан здесь; можно оставаться в текущем разделе.",
        )

        def worker() -> None:
            trigger = str(os.environ.get("PNEUMO_SEND_BUNDLE_TRIGGER") or "desktop_diagnostics_center")
            result = build_full_diagnostics_bundle(
                trigger=trigger,
                repo_root=self.repo_root,
                open_folder=False,
            )
            self.root.after(0, self._on_bundle_build_finished, result.ok, path_str(result.zip_path), str(result.message or ""))

        self._bundle_worker = threading.Thread(target=worker, daemon=True)
        self._bundle_worker.start()

    def _on_bundle_build_finished(self, ok: bool, zip_path: str, message: str) -> None:
        self._bundle_busy = False
        self._worker_done = True
        self._worker_exc = None if ok else message
        if ok:
            self._set_process_done("Архив собран", "Диагностический архив обновлён и готов к проверке.")
        else:
            self._set_process_done(
                "Ошибка сборки архива",
                f"Не удалось собрать диагностический архив: {_technical_message_ru(message)}",
            )
        self._refresh_bundle_views(regenerate_reports=True)
        if zip_path:
            try:
                self._last_zip = Path(zip_path).expanduser().resolve()
            except Exception:
                self._last_zip = Path(zip_path)
        if self._bundle_auto_copy_on_ready:
            self._attempt_clipboard_copy_once()
        if not ok and not self._host_closed:
            messagebox.showerror("Архив отправки", _technical_message_ru(message) or "Не удалось собрать архив отправки.")

    def _attempt_clipboard_copy_once(self) -> None:
        if self._clipboard_attempted:
            return
        self._clipboard_attempted = True
        bundle, ok, message = copy_latest_bundle_to_clipboard(
            self.repo_root,
            out_dir=self._active_bundle_out_dir(),
            zip_path=self.zip_path,
        )
        self._clipboard_ok = bool(ok)
        self._clipboard_message = str(message)
        self._refresh_bundle_views(regenerate_reports=False)
        if bundle.latest_zip_path and not ok:
            self.status_var.set("Архив готов, но буфер обмена подтвердился не полностью.")

    def _copy(self) -> None:
        bundle, ok, message = copy_latest_bundle_to_clipboard(
            self.repo_root,
            out_dir=self._active_bundle_out_dir(),
            zip_path=self.zip_path,
        )
        self._clipboard_ok = bool(ok)
        self._clipboard_message = str(message)
        self._refresh_bundle_views(regenerate_reports=False)
        if not bundle.latest_zip_path:
            messagebox.showwarning("Отправка", "Архив ещё не готов.")
            return
        if ok:
            messagebox.showinfo("Отправка", _technical_message_ru(message))
        else:
            messagebox.showwarning("Отправка", _technical_message_ru(message))

    def on_close(self) -> None:
        try:
            self._stop()
        except Exception:
            pass
        if self._poll_after_id is not None:
            try:
                self.root.after_cancel(self._poll_after_id)
            except Exception:
                pass
            self._poll_after_id = None
        self.root.destroy()

    def on_host_close(self) -> None:
        self._host_closed = True
        if self._poll_after_id is not None:
            try:
                self.root.after_cancel(self._poll_after_id)
            except Exception:
                pass
            self._poll_after_id = None
        self._stop()


def main() -> int:
    root = Tk()
    app = DesktopDiagnosticsCenter(root, initial_tab="restore")
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
