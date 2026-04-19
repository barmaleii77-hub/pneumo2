from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from pneumo_solver_ui.desktop_engineering_analysis_model import (
    EngineeringAnalysisArtifact,
    EngineeringAnalysisJobResult,
    EngineeringAnalysisSnapshot,
    EngineeringSensitivityRow,
)
from pneumo_solver_ui.desktop_engineering_analysis_runtime import DesktopEngineeringAnalysisRuntime
from pneumo_solver_ui.desktop_ui_core import build_scrolled_text, build_scrolled_treeview
from pneumo_solver_ui.release_info import get_release


ANALYSIS_COMMAND_OPEN_TARGETS: tuple[tuple[str, str], ...] = (
    ("selected_contract", "Открыть выбранный прогон"),
    ("run_dir", "Открыть папку прогона"),
    ("selected_artifact", "Открыть выбранный файл"),
    ("evidence_manifest", "Открыть материалы диагностики"),
    ("analysis_context", "Открыть данные для анимации"),
    ("animator_link", "Открыть связь анализа с аниматором"),
)


def _open_path(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def _status_text(value: str) -> str:
    labels = {
        "PASS": "готово",
        "READY": "готово",
        "PARTIAL": "частично",
        "MISSING": "нет данных",
        "BLOCKED": "заблокировано",
        "DEGRADED": "требует внимания",
        "FAILED": "ошибка",
        "INVALID": "некорректно",
        "STALE": "устарело",
        "AVAILABLE_NOT_RUN": "доступно, не запускалось",
        "FINISHED": "завершено",
        "MISSING_INPUTS": "нет входных данных",
        "UNKNOWN": "неизвестно",
        "UNPARSEABLE": "нужно проверить",
    }
    raw = str(value or "").strip()
    return labels.get(raw.upper(), raw or "-")


def _category_text(value: object) -> str:
    raw = str(value or "").strip()
    labels = {
        "run": "прогон",
        "contract": "выбранный прогон",
        "evidence": "диагностика",
        "validated_artifacts": "проверенные файлы",
        "missing_required_artifact": "не хватает файла",
        "v38_pipeline_section": "раздел",
        "analysis_previews": "просмотр",
        "analysis_chart_preview": "график",
        "analysis_table_preview": "таблица",
        "artifact_table_previews": "таблицы",
        "category": "группа",
        "ho007_candidates": "прогоны",
        "optimization_run": "прогон оптимизации",
        "compare_influence": "сравнение влияния",
        "selected_run": "выбранный прогон",
        "calibration": "калибровка",
        "influence": "влияние и сравнение",
        "sensitivity_uncertainty": "чувствительность",
        "handoffs_evidence": "аниматор и диагностика",
        "workspace": "рабочие данные",
    }
    return labels.get(raw, raw.replace("_", " ") if raw else "")


def _operator_issue_text(value: object) -> str:
    raw = str(value or "").strip()
    labels = {
        "missing selected run contract": "нет выбранного прогона",
        "selected run contract missing": "нет выбранного прогона",
        "missing diagnostics evidence manifest": "нет материалов диагностики",
    }
    return labels.get(raw.lower(), raw or "-")


def _operator_title_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    exact = {
        "Uncertainty/UQ artifacts": "Файлы чувствительности и неопределённости",
        "HO-008 Animator handoff": "Данные для аниматора",
        "HO-009 Diagnostics evidence manifest": "Материалы диагностики",
    }
    if text in exact:
        return exact[text]
    replacements = (
        ("Diagnostics evidence manifest", "Материалы диагностики"),
        ("diagnostics evidence manifest", "материалы диагностики"),
        ("Animator handoff", "Данные для аниматора"),
        ("animator handoff", "данные для аниматора"),
        ("selected run contract", "выбранный прогон"),
        ("Selected run contract", "Выбранный прогон"),
        ("Uncertainty/UQ", "Чувствительность и неопределённость"),
        ("artifacts", "файлы"),
        ("Artifacts", "Файлы"),
        ("artifact", "файл"),
        ("Artifact", "Файл"),
        ("manifest", "описание файлов"),
        ("Manifest", "Описание файлов"),
        ("handoff", "передача данных"),
        ("Handoff", "Передача данных"),
        ("compare_influence", "сравнение влияния"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def format_contract_banner(snapshot: EngineeringAnalysisSnapshot | None) -> str:
    if snapshot is None:
        return "Выбранный прогон: не загружен."
    parts = [f"состояние: {_status_text(snapshot.contract_status or 'MISSING')}"]
    if snapshot.selected_run_contract_path:
        parts.append("файл: найден" if snapshot.selected_run_contract_path.exists() else "файл: не найден")
    if snapshot.selected_run_contract_hash:
        parts.append(f"код: {snapshot.selected_run_contract_hash[:12]}")
    if snapshot.blocking_states:
        parts.append("замечания: " + "; ".join(_operator_issue_text(item) for item in snapshot.blocking_states))
    return "Выбранный прогон: " + " | ".join(parts)


def format_selected_run_summary(snapshot: EngineeringAnalysisSnapshot | None) -> str:
    if snapshot is None or snapshot.selected_run_context is None:
        return "Прогон: не выбран."
    context = snapshot.selected_run_context
    return (
        f"Прогон: {context.run_id or '-'} | режим: {context.mode or '-'} | "
        f"состояние: {_status_text(context.status or '')} | ограничение: {context.hard_gate_key or '-'} | "
        f"базовый прогон: {context.active_baseline_hash[:12] if context.active_baseline_hash else '-'}"
    )


class DesktopEngineeringAnalysisCenter(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        runtime: DesktopEngineeringAnalysisRuntime,
    ) -> None:
        super().__init__(master, padding=10)
        self.runtime = runtime
        self.snapshot_state: EngineeringAnalysisSnapshot | None = None
        self._artifact_by_iid: dict[str, EngineeringAnalysisArtifact] = {}
        self._path_by_iid: dict[str, Path] = {}
        self._candidate_by_iid: dict[str, dict] = {}
        self._sensitivity_by_iid: dict[str, EngineeringSensitivityRow] = {}
        self._pipeline_by_iid: dict[str, dict[str, Any]] = {}
        self._preview_by_iid: dict[str, dict[str, Any]] = {}
        self._worker_thread: threading.Thread | None = None

        self.release_var = tk.StringVar(master=self, value=f"Версия: {get_release(default='unknown')}")
        self.summary_var = tk.StringVar(master=self, value="Инженерный анализ: ожидание данных.")
        self.contract_var = tk.StringVar(master=self, value="Выбранный прогон: не загружен.")
        self.selected_run_var = tk.StringVar(master=self, value="Прогон: не выбран.")
        self.evidence_var = tk.StringVar(master=self, value="Материалы диагностики: не подготовлены.")
        self.status_var = tk.StringVar(master=self, value="Центр инженерного анализа готов.")
        self.candidate_ready_only_var = tk.BooleanVar(master=self, value=False)
        self.candidate_filter_summary_var = tk.StringVar(master=self, value="Кандидаты для анализа: не загружены.")
        self.command_var = tk.StringVar(master=self, value=ANALYSIS_COMMAND_OPEN_TARGETS[0][1])

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(
            title_box,
            text="Инженерный анализ, калибровка и влияние",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(title_box, textvariable=self.summary_var, justify="left", wraplength=760).pack(anchor="w", pady=(2, 0))
        ttk.Label(title_box, textvariable=self.release_var, justify="left").pack(anchor="w", pady=(2, 0))

        actions = ttk.Frame(header)
        actions.pack(side="right", anchor="ne")
        self.btn_refresh = ttk.Button(actions, text="Обновить", command=self.refresh)
        self.btn_refresh.pack(side="left")
        self.btn_open_selected = ttk.Button(actions, text="Открыть файл", command=self._open_selected)
        self.btn_open_selected.pack(side="left", padx=(8, 0))
        self.btn_export_ho007 = ttk.Button(actions, text="Зафиксировать прогон", command=self._export_selected_run_contract_bridge)
        self.btn_export_ho007.pack(side="left", padx=(8, 0))
        self.btn_export_evidence = ttk.Button(actions, text="Подготовить диагностику", command=self._export_diagnostics_evidence)
        self.btn_export_evidence.pack(side="left", padx=(8, 0))
        self.btn_open_evidence_manifest = ttk.Button(
            actions,
            text="Открыть диагностику",
            command=self._open_evidence_manifest,
        )
        self.btn_open_evidence_manifest.pack(side="left", padx=(8, 0))
        self.btn_animator_link = ttk.Button(actions, text="Связь с аниматором", command=self._export_animator_link)
        self.btn_animator_link.pack(side="left", padx=(8, 0))
        self.btn_system_influence = ttk.Button(actions, text="Влияние системы", command=self._run_system_influence)
        self.btn_system_influence.pack(side="left", padx=(8, 0))
        self.btn_full_report = ttk.Button(actions, text="Полный отчёт", command=self._run_full_report)
        self.btn_full_report.pack(side="left", padx=(8, 0))
        self.btn_param_staging = ttk.Button(actions, text="Диапазоны влияния", command=self._run_param_staging)
        self.btn_param_staging.pack(side="left", padx=(8, 0))
        self.btn_diagnostics = ttk.Button(actions, text="Собрать диагностику", command=self._launch_full_diagnostics_gui)
        self.btn_diagnostics.pack(side="left", padx=(8, 0))

        workspace = ttk.Panedwindow(self, orient="horizontal")
        workspace.pack(fill="both", expand=True)

        left_column = ttk.Frame(workspace)
        left_column.columnconfigure(0, weight=1)
        left_column.rowconfigure(0, weight=1)
        artifact_box = ttk.LabelFrame(left_column, text="Исследование и файлы", padding=8)
        artifact_box.grid(row=0, column=0, sticky="nsew")
        artifact_box.columnconfigure(0, weight=1)
        artifact_box.rowconfigure(2, weight=1)
        command_bar = ttk.Frame(artifact_box)
        command_bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        command_bar.columnconfigure(1, weight=1)
        ttk.Label(command_bar, text="Быстро открыть").grid(row=0, column=0, sticky="w")
        self.command_combo = ttk.Combobox(
            command_bar,
            textvariable=self.command_var,
            values=[label for _key, label in ANALYSIS_COMMAND_OPEN_TARGETS],
            state="readonly",
            width=44,
        )
        self.command_combo.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.btn_open_command = ttk.Button(
            command_bar,
            text="Открыть",
            command=self._run_command_surface_action,
        )
        self.btn_open_command.grid(row=0, column=2, sticky="e")
        candidate_filter_bar = ttk.Frame(artifact_box)
        candidate_filter_bar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Checkbutton(
            candidate_filter_bar,
            text="Только готовые",
            variable=self.candidate_ready_only_var,
            command=self._refresh_candidate_filter,
        ).pack(side="left")
        ttk.Label(
            candidate_filter_bar,
            textvariable=self.candidate_filter_summary_var,
        ).pack(side="left", padx=(10, 0))
        artifact_frame, self.artifact_tree = build_scrolled_treeview(
            artifact_box,
            columns=("status", "category", "path"),
            show="tree headings",
            height=18,
        )
        self.artifact_tree.heading("#0", text="Файл или раздел")
        self.artifact_tree.heading("status", text="Состояние")
        self.artifact_tree.heading("category", text="Категория")
        self.artifact_tree.heading("path", text="Путь")
        self.artifact_tree.column("#0", width=260, anchor="w")
        self.artifact_tree.column("status", width=110, anchor="w")
        self.artifact_tree.column("category", width=130, anchor="w")
        self.artifact_tree.column("path", width=380, anchor="w")
        artifact_frame.grid(row=2, column=0, sticky="nsew")
        self.artifact_tree.bind("<<TreeviewSelect>>", self._on_artifact_select)
        self.artifact_tree.bind("<Double-1>", lambda _event: self._open_selected())

        right_column = ttk.Frame(workspace)
        right_column.columnconfigure(0, weight=1)
        right_column.rowconfigure(0, weight=1)
        right_pane = ttk.Panedwindow(right_column, orient="vertical")
        right_pane.grid(row=0, column=0, sticky="nsew")

        report_box = ttk.Frame(right_pane)
        report_box.columnconfigure(0, weight=1)
        report_box.rowconfigure(1, weight=1)
        summary_box = ttk.LabelFrame(report_box, text="Сводка и происхождение", padding=8)
        summary_box.grid(row=0, column=0, sticky="ew")
        ttk.Label(summary_box, textvariable=self.contract_var, wraplength=720, justify="left").pack(anchor="w")
        ttk.Label(summary_box, textvariable=self.selected_run_var, wraplength=720, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(summary_box, textvariable=self.evidence_var, wraplength=720, justify="left").pack(anchor="w", pady=(4, 0))

        sensitivity_box = ttk.LabelFrame(report_box, text="Сводка чувствительности", padding=8)
        sensitivity_box.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        sensitivity_box.columnconfigure(0, weight=1)
        sensitivity_box.rowconfigure(0, weight=1)
        sens_frame, self.sensitivity_tree = build_scrolled_treeview(
            sensitivity_box,
            columns=("group", "score", "status", "metric", "elasticity", "eps"),
            show="headings",
            height=10,
        )
        for col, title, width in (
            ("group", "Группа", 120),
            ("score", "Оценка", 90),
            ("status", "Состояние", 90),
            ("metric", "Главная метрика", 180),
            ("elasticity", "Эластичность", 100),
            ("eps", "eps", 100),
        ):
            self.sensitivity_tree.heading(col, text=title)
            self.sensitivity_tree.column(col, width=width, anchor="w")
        sens_frame.grid(row=0, column=0, sticky="nsew")
        self.sensitivity_tree.bind("<<TreeviewSelect>>", self._on_sensitivity_select)

        details_box = ttk.LabelFrame(right_pane, text="Детали и журнал", padding=8)
        details_box.columnconfigure(0, weight=1)
        details_box.rowconfigure(0, weight=1)
        detail_frame, self.detail_text = build_scrolled_text(details_box, height=10, wrap="word")
        detail_frame.grid(row=0, column=0, sticky="nsew")
        log_frame, self.log_text = build_scrolled_text(details_box, height=8, wrap="word")
        log_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.detail_text.configure(state="disabled")
        self.log_text.configure(state="disabled")

        right_pane.add(report_box, weight=3)
        right_pane.add(details_box, weight=2)
        workspace.add(left_column, weight=2)
        workspace.add(right_column, weight=3)

        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(footer, mode="determinate", length=180)
        self.progress.pack(side="right", padx=(8, 8))
        ttk.Sizegrip(footer).pack(side="right")

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", str(text or ""))
        widget.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        if self.log_text.index("end-1c") != "1.0":
            self.log_text.insert("end", "\n")
        self.log_text.insert("end", str(text or ""))
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def refresh(self) -> None:
        try:
            snapshot = self.runtime.snapshot()
        except Exception as exc:
            self.status_var.set(f"Не удалось обновить данные: {type(exc).__name__}: {exc!s}")
            messagebox.showerror("Инженерный анализ", f"Не удалось обновить данные:\n{exc!s}")
            return
        self.snapshot_state = snapshot
        self._populate_snapshot(snapshot)
        self.status_var.set("Данные обновлены.")

    def _populate_snapshot(self, snapshot: EngineeringAnalysisSnapshot) -> None:
        self._artifact_by_iid.clear()
        self._path_by_iid.clear()
        self._candidate_by_iid.clear()
        self._sensitivity_by_iid.clear()
        self._pipeline_by_iid.clear()
        self._preview_by_iid.clear()
        self.artifact_tree.delete(*self.artifact_tree.get_children())
        self.sensitivity_tree.delete(*self.sensitivity_tree.get_children())
        pipeline_rows = self.runtime.analysis_workspace_pipeline_status(snapshot)
        runtime_gaps = self.runtime.analysis_workspace_runtime_gaps(snapshot)
        chart_table_preview = self.runtime.analysis_workspace_chart_table_preview(snapshot)

        self.summary_var.set(
            " | ".join(
                (
                    f"анализ: {_status_text(snapshot.status)}",
                    f"влияние: {_status_text(snapshot.influence_status)}",
                    f"калибровка: {_status_text(snapshot.calibration_status)}",
                    f"сравнение: {_status_text(snapshot.compare_status)}",
                    f"замечания: {len(runtime_gaps)}",
                )
            )
        )
        self.contract_var.set(format_contract_banner(snapshot))
        self.selected_run_var.set(format_selected_run_summary(snapshot))
        evidence_path = snapshot.diagnostics_evidence_manifest_path
        self.evidence_var.set(
            f"Материалы диагностики: {_status_text(snapshot.diagnostics_evidence_manifest_status)} | "
            f"код: {snapshot.diagnostics_evidence_manifest_hash[:12] or '-'} | "
            f"файл: {'найден' if evidence_path and evidence_path.exists() else 'не подготовлен'}"
        )

        run_label = snapshot.run_dir.name if snapshot.run_dir else "папка не выбрана"
        run_iid = self.artifact_tree.insert(
            "",
            "end",
            text=f"Прогон: {run_label}",
            values=(_status_text(snapshot.status), _category_text("run"), str(snapshot.run_dir or "")),
            open=True,
        )
        if snapshot.run_dir:
            self._path_by_iid[run_iid] = snapshot.run_dir
        if snapshot.selected_run_contract_path:
            iid = self.artifact_tree.insert(
                run_iid,
                "end",
                text="Выбранный прогон",
                values=(_status_text(snapshot.contract_status), _category_text("contract"), str(snapshot.selected_run_contract_path)),
            )
            self._path_by_iid[iid] = snapshot.selected_run_contract_path
        if snapshot.diagnostics_evidence_manifest_path:
            iid = self.artifact_tree.insert(
                run_iid,
                "end",
                text="Материалы инженерного анализа",
                values=(
                    _status_text(snapshot.diagnostics_evidence_manifest_status),
                    _category_text("evidence"),
                    str(snapshot.diagnostics_evidence_manifest_path),
                ),
            )
            self._path_by_iid[iid] = snapshot.diagnostics_evidence_manifest_path
        validated_artifacts = self.runtime.validated_artifacts_summary(snapshot)
        validated_iid = self.artifact_tree.insert(
            run_iid,
            "end",
            text="Проверенные файлы",
            values=(
                _status_text(str(validated_artifacts.get("status") or "MISSING")),
                _category_text("validated_artifacts"),
                (
                    f"готово {validated_artifacts.get('ready_required_artifact_count')}/"
                    f"{validated_artifacts.get('required_artifact_count')} | "
                    f"нет {validated_artifacts.get('missing_required_artifact_count')}"
                ),
            ),
            open=bool(validated_artifacts.get("missing_required_artifacts")),
        )
        missing_required_artifacts = list(validated_artifacts.get("missing_required_artifacts") or [])
        if missing_required_artifacts:
            for item in missing_required_artifacts:
                if not isinstance(item, dict):
                    continue
                raw_missing_path = str(item.get("path") or "").strip()
                missing_path = Path(raw_missing_path) if raw_missing_path else None
                iid = self.artifact_tree.insert(
                    validated_iid,
                    "end",
                    text=str(item.get("title") or item.get("key") or "Не хватает обязательного файла"),
                    values=(
                        _status_text(str(item.get("validation_status") or "MISSING")),
                        _category_text("missing_required_artifact"),
                        str(missing_path or ""),
                    ),
                )
                if missing_path is not None:
                    self._path_by_iid[iid] = missing_path
        else:
            self.artifact_tree.insert(
                validated_iid,
                "end",
                text="Обязательные файлы готовы",
                values=(_status_text("READY"), _category_text("validated_artifacts"), ""),
            )

        pipeline_iid = self.artifact_tree.insert(
            run_iid,
            "end",
            text="Порядок работы и замечания",
            values=(
                _status_text("READY" if not runtime_gaps else "PARTIAL"),
                "порядок работы",
                f"шагов: {len(pipeline_rows)} | замечаний: {len(runtime_gaps)}",
            ),
            open=True,
        )
        section_iids: dict[str, str] = {}
        section_labels = {
            "selected_run": "Выбранный прогон",
            "calibration": "Калибровка",
            "influence": "Влияние и сравнение",
            "sensitivity_uncertainty": "Чувствительность и неопределённость",
            "handoffs_evidence": "Аниматор и диагностика",
            "workspace": "Рабочие данные",
        }
        for row in pipeline_rows:
            section = str(row.section or "workspace")
            section_iid = section_iids.get(section)
            if section_iid is None:
                section_iid = self.artifact_tree.insert(
                    pipeline_iid,
                    "end",
                    text=section_labels.get(section, section),
                    values=("", _category_text("v38_pipeline_section"), ""),
                    open=True,
                )
                section_iids[section] = section_iid
            payload = row.to_payload()
            iid = self.artifact_tree.insert(
                section_iid,
                "end",
                text=_operator_title_text(row.title),
                values=(_status_text(row.status), _category_text(row.section), str(row.path or row.detail or "")),
            )
            self._pipeline_by_iid[iid] = payload
            if row.path is not None:
                self._path_by_iid[iid] = row.path

        preview_iid = self.artifact_tree.insert(
            run_iid,
            "end",
            text="Предпросмотр графиков и таблиц",
            values=(
                _status_text(str(chart_table_preview.get("status") or "MISSING")),
                _category_text("analysis_previews"),
                (
                    f"графики: {chart_table_preview.get('chart_count', 0)} | "
                    f"таблицы: {chart_table_preview.get('table_count', 0)} | "
                    f"строк: {chart_table_preview.get('max_rows', 0)}"
                ),
            ),
            open=True,
        )
        self._preview_by_iid[preview_iid] = dict(chart_table_preview)
        charts_iid = self.artifact_tree.insert(
            preview_iid,
            "end",
            text="Графики влияния",
            values=(
                _status_text("READY" if chart_table_preview.get("chart_count") else "MISSING"),
                _category_text("analysis_chart_preview"),
                f"количество: {chart_table_preview.get('chart_count', 0)}",
            ),
            open=True,
        )
        self._preview_by_iid[charts_iid] = {
            "kind": "compare_influence_charts",
            "charts": list(chart_table_preview.get("charts") or []),
        }
        for chart in chart_table_preview.get("charts") or []:
            if not isinstance(chart, dict):
                continue
            iid = self.artifact_tree.insert(
                charts_iid,
                "end",
                text=_operator_title_text(chart.get("title") or "compare_influence"),
                values=(
                    _status_text(str(chart.get("status") or "READY")),
                    _category_text("analysis_chart_preview"),
                    str(chart.get("source_path") or ""),
                ),
            )
            self._preview_by_iid[iid] = dict(chart)

        sensitivity_preview = dict(chart_table_preview.get("sensitivity_table") or {})
        sensitivity_iid = self.artifact_tree.insert(
            preview_iid,
            "end",
            text="Таблица чувствительности",
            values=(
                _status_text(str(sensitivity_preview.get("status") or "MISSING")),
                _category_text("analysis_table_preview"),
                f"строк: {sensitivity_preview.get('row_count', 0)}",
            ),
        )
        self._preview_by_iid[sensitivity_iid] = sensitivity_preview
        tables_iid = self.artifact_tree.insert(
            preview_iid,
            "end",
            text="Табличные файлы",
            values=(
                _status_text("READY" if chart_table_preview.get("table_count") else "MISSING"),
                _category_text("analysis_table_preview"),
                f"количество: {chart_table_preview.get('table_count', 0)}",
            ),
            open=True,
        )
        self._preview_by_iid[tables_iid] = {
            "kind": "artifact_table_previews",
            "tables": list(chart_table_preview.get("tables") or []),
        }
        for table in chart_table_preview.get("tables") or []:
            if not isinstance(table, dict):
                continue
            iid = self.artifact_tree.insert(
                tables_iid,
                "end",
                text=_operator_title_text(table.get("title") or table.get("key") or "CSV-таблица"),
                values=(
                    _status_text(str(table.get("status") or "MISSING")),
                    _category_text("analysis_table_preview"),
                    str(table.get("source_path") or ""),
                ),
            )
            self._preview_by_iid[iid] = dict(table)

        group_iids: dict[str, str] = {}
        for artifact in sorted(snapshot.artifacts, key=lambda item: (item.category, item.title)):
            group_iid = group_iids.get(artifact.category)
            if group_iid is None:
                group_iid = self.artifact_tree.insert(
                    run_iid,
                    "end",
                    text=_category_text(artifact.category),
                    values=("", _category_text("category"), ""),
                    open=True,
                )
                group_iids[artifact.category] = group_iid
            iid = self.artifact_tree.insert(
                group_iid,
                "end",
                text=_operator_title_text(artifact.title),
                values=(_status_text(artifact.status), _category_text(artifact.category), str(artifact.path)),
            )
            self._artifact_by_iid[iid] = artifact
            self._path_by_iid[iid] = artifact.path

        candidate_root = self.artifact_tree.insert(
            "",
            "end",
            text="Прогоны оптимизации для выбора",
            values=("", _category_text("ho007_candidates"), ""),
            open=not bool(snapshot.run_dir),
        )
        discovery_failed = False
        try:
            candidates = self.runtime.discover_selected_run_candidates(limit=25)
        except Exception as exc:
            discovery_failed = True
            self.artifact_tree.insert(
                candidate_root,
                "end",
                text="Не удалось найти прогоны",
                values=(_status_text("FAILED"), _category_text("optimization_run"), f"{type(exc).__name__}: {exc!s}"),
            )
            candidates = ()
        all_candidates = tuple(candidates)
        ready_only = bool(self.candidate_ready_only_var.get())
        filtered_candidates = tuple(
            candidate
            for candidate in all_candidates
            if not ready_only or str(candidate.get("bridge_status") or "") == "READY"
        )
        ready_count = sum(
            1
            for candidate in all_candidates
            if str(candidate.get("bridge_status") or "") == "READY"
        )
        self.candidate_filter_summary_var.set(
            f"Кандидаты: показано {len(filtered_candidates)}/{len(all_candidates)} | готово {ready_count}"
        )
        self.artifact_tree.item(
            candidate_root,
            text=f"Прогоны оптимизации для выбора ({len(filtered_candidates)}/{len(all_candidates)})",
        )
        if not filtered_candidates and not discovery_failed:
            self.artifact_tree.insert(
                candidate_root,
                "end",
                text="Готовые прогоны не найдены" if ready_only else "Прогоны оптимизации не найдены",
                values=(_status_text("MISSING"), _category_text("optimization_run"), ""),
            )
        for candidate in filtered_candidates:
            run_dir_text = str(candidate.get("run_dir") or "")
            bridge_status = str(candidate.get("bridge_status") or "UNKNOWN")
            status_label = str(candidate.get("status_label") or candidate.get("status") or "").strip()
            run_id = str(candidate.get("run_id") or candidate.get("run_name") or "прогон оптимизации")
            label = f"{run_id} [{_status_text(status_label or bridge_status)}]"
            iid = self.artifact_tree.insert(
                candidate_root,
                "end",
                text=label,
                values=(_status_text(bridge_status), _category_text("optimization_run"), run_dir_text),
            )
            if run_dir_text:
                self._path_by_iid[iid] = Path(run_dir_text)
            self._candidate_by_iid[iid] = dict(candidate)

        for idx, row in enumerate(snapshot.sensitivity_rows, start=1):
            iid = f"sens_{idx}"
            self.sensitivity_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    row.group,
                    f"{row.score:.6g}",
                    _status_text(row.status),
                    row.strongest_metric,
                    f"{row.strongest_elasticity:.6g}",
                    "" if row.eps_rel_used is None else f"{row.eps_rel_used:.6g}",
                ),
            )
            self._sensitivity_by_iid[iid] = row

        self._set_text(self.detail_text, self._snapshot_detail(snapshot))

    def _snapshot_detail(self, snapshot: EngineeringAnalysisSnapshot) -> str:
        compare_surfaces = self._compare_surface_details(snapshot)
        pipeline_rows = [
            row.to_payload()
            for row in self.runtime.analysis_workspace_pipeline_status(snapshot)
        ]
        payload = {
            "status": snapshot.status,
            "run_dir": str(snapshot.run_dir or ""),
            "influence_status": snapshot.influence_status,
            "calibration_status": snapshot.calibration_status,
            "compare_status": snapshot.compare_status,
            "contract_status": snapshot.contract_status,
            "blocking_states": list(snapshot.blocking_states),
            "artifact_count": len(snapshot.artifacts),
            "sensitivity_row_count": len(snapshot.sensitivity_rows),
            "compare_influence_surface_count": len(compare_surfaces),
            "compare_influence_diagnostics": {
                "surface_count": len(compare_surfaces),
                "source": "desktop_detail_auto_discovery",
                "titles": [str(surface.get("title") or "") for surface in compare_surfaces],
            },
            "compare_influence_surfaces": compare_surfaces,
            "unit_catalog": dict(snapshot.unit_catalog),
            "validated_artifacts": self.runtime.validated_artifacts_summary(snapshot),
            "handoff_requirements": self.runtime.selected_run_handoff_requirements(snapshot),
            "analysis_workspace_pipeline": pipeline_rows,
            "runtime_data_gaps": [
                dict(item)
                for item in self.runtime.analysis_workspace_runtime_gaps(snapshot)
            ],
            "analysis_chart_table_preview": self.runtime.analysis_workspace_chart_table_preview(snapshot),
            "compare_viewer_handoff_summary": self.runtime.analysis_compare_handoff_summary(snapshot),
            "results_center_boundary_summary": self.runtime.analysis_results_boundary_summary(snapshot),
            "animator_handoff_summary": self.runtime.analysis_animator_handoff_summary(snapshot),
        }
        return self._snapshot_operator_detail(snapshot, payload)

    def _snapshot_operator_detail(self, snapshot: EngineeringAnalysisSnapshot, payload: dict[str, Any]) -> str:
        validated = dict(payload.get("validated_artifacts") or {})
        runtime_gaps = list(payload.get("runtime_data_gaps") or [])
        preview = dict(payload.get("analysis_chart_table_preview") or {})
        handoff = dict(payload.get("animator_handoff_summary") or {})
        compare = dict(payload.get("compare_viewer_handoff_summary") or {})
        results = dict(payload.get("results_center_boundary_summary") or {})
        lines = [
            "Сводка инженерного анализа",
            f"Состояние анализа: {_status_text(snapshot.status)}",
            f"Влияние: {_status_text(snapshot.influence_status)}",
            f"Калибровка: {_status_text(snapshot.calibration_status)}",
            f"Сравнение: {_status_text(snapshot.compare_status)}",
            f"Выбранный прогон: {_status_text(snapshot.contract_status)}",
            (
                "Проверенные файлы: "
                f"{_status_text(str(validated.get('status') or 'MISSING'))}, "
                f"готово {validated.get('ready_required_artifact_count', 0)}/"
                f"{validated.get('required_artifact_count', 0)}"
            ),
            f"Замечания по данным: {len(runtime_gaps)}",
            (
                "Предпросмотр: "
                f"графиков {preview.get('chart_count', 0)}, "
                f"таблиц {preview.get('table_count', 0)}"
            ),
            (
                "Связь с аниматором: "
                f"{_status_text(str(handoff.get('status') or handoff.get('handoff_status') or 'MISSING'))}"
            ),
            (
                "Связь со сравнением: "
                f"{_status_text(str(compare.get('status') or compare.get('handoff_status') or 'MISSING'))}"
            ),
            (
                "Связь с результатами: "
                f"{_status_text(str(results.get('status') or results.get('boundary_status') or 'MISSING'))}"
            ),
            "",
            "Для подробностей выберите строку слева.",
        ]
        return "\n".join(lines)

    def _compare_surface_details(self, snapshot: EngineeringAnalysisSnapshot) -> list[dict]:
        try:
            surfaces = self.runtime.compare_influence_surfaces(snapshot, top_k=5)
        except Exception as exc:
            return [
                {
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}: {exc!s}",
                }
            ]
        return [
            {
                "title": str(surface.get("title") or "compare_influence"),
                "source": str(surface.get("source") or ""),
                "diagnostics": dict(surface.get("diagnostics") or {}),
                "top_cells": list(surface.get("top_cells") or [])[:5],
            }
            for surface in surfaces
        ]

    def _compare_surface_preview_for_artifact(self, artifact: EngineeringAnalysisArtifact) -> dict:
        try:
            surface = self.runtime.compare_influence_surface_for_artifact(artifact, top_k=5)
        except Exception as exc:
            return {
                "status": "FAILED",
                "error": f"{type(exc).__name__}: {exc!s}",
            }
        if surface is None:
            return {
                "status": "UNPARSEABLE",
                "warning": (
                    "compare_influence artifact exists, but no surface could be built; "
                    "expected prebuilt surface payload or corr/matrix plus feature and target axes."
                ),
            }
        return {
            "status": "READY",
            "title": str(surface.get("title") or "compare_influence"),
            "source": str(surface.get("source") or ""),
            "diagnostics": dict(surface.get("diagnostics") or {}),
            "top_cells": list(surface.get("top_cells") or [])[:5],
        }

    def _format_detail_value(self, key: str, value: Any) -> str:
        if value is None:
            return "-"
        if isinstance(value, bool):
            return "да" if value else "нет"
        if key in {"status", "bridge_status", "contract_status", "validation_status", "handoff_status"}:
            return _status_text(str(value))
        if key in {"category", "section", "kind"}:
            return _category_text(value) or "-"
        if key in {"title", "detail", "warning"}:
            return _operator_title_text(value)
        if isinstance(value, (list, tuple, set)):
            return f"{len(value)}"
        if isinstance(value, dict):
            return f"{len(value)}"
        return str(value) if str(value).strip() else "-"

    def _operator_payload_detail(self, title: str, payload: dict[str, Any]) -> str:
        labels = {
            "title": "Название",
            "run_id": "Прогон",
            "run_name": "Прогон",
            "status": "Состояние",
            "status_label": "Состояние",
            "bridge_status": "Состояние выбора",
            "contract_status": "Состояние выбранного прогона",
            "validation_status": "Состояние проверки",
            "category": "Категория",
            "section": "Раздел",
            "kind": "Тип данных",
            "group": "Группа",
            "score": "Оценка",
            "strongest_metric": "Главная метрика",
            "strongest_elasticity": "Эластичность",
            "eps_rel_used": "Относительный шаг",
            "path": "Файл",
            "source_path": "Файл",
            "run_dir": "Папка прогона",
            "detail": "Подробности",
            "exists": "Файл найден",
            "size_bytes": "Размер, байт",
            "chart_count": "Графики",
            "table_count": "Таблицы",
            "row_count": "Строки",
            "max_rows": "Строк в просмотре",
            "charts": "Графики",
            "tables": "Таблицы",
            "top_cells": "Значимые ячейки",
            "diagnostics": "Диагностические данные",
            "source": "Источник",
            "warning": "Замечание",
            "error": "Ошибка",
        }
        ordered_keys = (
            "title",
            "run_id",
            "run_name",
            "status",
            "status_label",
            "bridge_status",
            "contract_status",
            "validation_status",
            "category",
            "section",
            "kind",
            "group",
            "score",
            "strongest_metric",
            "strongest_elasticity",
            "eps_rel_used",
            "path",
            "source_path",
            "run_dir",
            "detail",
            "exists",
            "size_bytes",
            "chart_count",
            "table_count",
            "row_count",
            "max_rows",
            "charts",
            "tables",
            "top_cells",
            "diagnostics",
            "source",
            "warning",
            "error",
        )
        lines = [title]
        for key in ordered_keys:
            if key not in payload:
                continue
            lines.append(f"{labels[key]}: {self._format_detail_value(key, payload.get(key))}")
        if len(lines) == 1:
            lines.append("Подробности для этой строки пока не подготовлены.")
        return "\n".join(lines)

    def _refresh_candidate_filter(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            self.refresh()
            return
        self._populate_snapshot(snapshot)
        self.status_var.set(
            "Показаны только готовые кандидаты"
            if bool(self.candidate_ready_only_var.get())
            else "Показаны все кандидаты"
        )

    def _selected_tree_iid(self) -> str:
        selected = self.artifact_tree.selection()
        return str(selected[0]) if selected else ""

    def _selected_tree_path(self) -> Path | None:
        iid = self._selected_tree_iid()
        if iid:
            path = self._path_by_iid.get(iid)
            if path is not None:
                return path
        return None

    def _selected_candidate_run_dir(self) -> Path | None:
        iid = self._selected_tree_iid()
        if not iid:
            return None
        candidate = self._candidate_by_iid.get(iid)
        if not candidate:
            return None
        raw = str(candidate.get("run_dir") or "").strip()
        if not raw:
            return None
        path = Path(raw)
        return path if path.exists() and path.is_dir() else None

    def _open_selected(self) -> None:
        path = self._selected_tree_path()
        if path is None:
            messagebox.showinfo("Инженерный анализ", "Выберите файл, материалы диагностики или папку прогона.")
            return
        try:
            _open_path(path)
            self.status_var.set(f"Открыто: {path}")
        except Exception as exc:
            messagebox.showerror("Инженерный анализ", f"Не удалось открыть:\n{path}\n\n{exc!s}")

    def _command_key_from_label(self, label: str) -> str:
        for key, item_label in ANALYSIS_COMMAND_OPEN_TARGETS:
            if str(label or "") == item_label:
                return key
        return ANALYSIS_COMMAND_OPEN_TARGETS[0][0]

    def _command_surface_target(
        self,
        action_key: str,
        snapshot: EngineeringAnalysisSnapshot,
    ) -> Path | None:
        if action_key == "selected_contract":
            return snapshot.selected_run_contract_path
        if action_key == "run_dir":
            return snapshot.run_dir
        if action_key == "selected_artifact":
            return self._selected_tree_path()
        if action_key == "evidence_manifest":
            return snapshot.diagnostics_evidence_manifest_path
        if action_key == "analysis_context":
            return self.runtime.analysis_context_path()
        if action_key == "animator_link":
            return self.runtime.animator_link_contract_path()
        return None

    def _run_command_surface_action(self) -> None:
        snapshot = self.snapshot_state or self.runtime.snapshot()
        action_key = self._command_key_from_label(self.command_var.get())
        path = self._command_surface_target(action_key, snapshot)
        if path is None:
            messagebox.showinfo("Инженерный анализ", "Для выбранного действия пока нет готового файла.")
            return
        if not path.exists():
            self.status_var.set(f"Файл не найден: {path}")
            messagebox.showwarning("Инженерный анализ", f"Файл ещё не создан:\n{path}")
            return
        try:
            _open_path(path)
            self.status_var.set(f"Открыто: {path}")
        except Exception as exc:
            messagebox.showerror("Инженерный анализ", f"Не удалось открыть:\n{path}\n\n{exc!s}")

    def _open_evidence_manifest(self) -> None:
        snapshot = self.snapshot_state or self.runtime.snapshot()
        path = snapshot.diagnostics_evidence_manifest_path
        if path is None:
            self.status_var.set("Материалы диагностики ещё не подготовлены.")
            messagebox.showinfo(
                "Инженерный анализ",
                "Материалы диагностики ещё не созданы. Выполните «Подготовить диагностику», затем откройте их.",
            )
            return
        if not path.exists():
            self.status_var.set(f"Файл материалов диагностики не найден: {path}")
            messagebox.showwarning("Инженерный анализ", f"Материалы диагностики не найдены:\n{path}")
            return
        try:
            _open_path(path)
            self.status_var.set(f"Материалы диагностики открыты: {path}")
        except Exception as exc:
            messagebox.showerror("Инженерный анализ", f"Не удалось открыть материалы диагностики:\n{path}\n\n{exc!s}")

    def _on_artifact_select(self, _event: tk.Event | None = None) -> None:
        selected = self.artifact_tree.selection()
        if not selected:
            return
        iid = selected[0]
        artifact = self._artifact_by_iid.get(iid)
        if artifact is not None:
            payload = artifact.to_payload()
            path = artifact.path
            payload["exists"] = path.exists()
            payload["size_bytes"] = path.stat().st_size if path.exists() and path.is_file() else None
            if artifact.category == "compare_influence" and path.suffix.lower() == ".json":
                payload["compare_influence_surface_preview"] = self._compare_surface_preview_for_artifact(artifact)
            self._set_text(self.detail_text, self._operator_payload_detail("Файл инженерного анализа", payload))
            return
        candidate = self._candidate_by_iid.get(iid)
        if candidate is not None:
            self._set_text(self.detail_text, self._operator_payload_detail("Прогон оптимизации", candidate))
            return
        pipeline_row = self._pipeline_by_iid.get(iid)
        if pipeline_row is not None:
            self._set_text(self.detail_text, self._operator_payload_detail("Рабочий шаг", pipeline_row))
            return
        preview_payload = self._preview_by_iid.get(iid)
        if preview_payload is not None:
            self._set_text(self.detail_text, self._operator_payload_detail("Предпросмотр", preview_payload))
            return
        path = self._path_by_iid.get(iid)
        if path is not None:
            self._set_text(
                self.detail_text,
                self._operator_payload_detail("Файл или папка", {"path": str(path), "exists": path.exists()}),
            )

    def _on_sensitivity_select(self, _event: tk.Event | None = None) -> None:
        selected = self.sensitivity_tree.selection()
        if not selected:
            return
        row = self._sensitivity_by_iid.get(selected[0])
        if row is not None:
            self._set_text(
                self.detail_text,
                self._operator_payload_detail("Строка чувствительности", row.to_payload()),
            )

    def _current_run_dir(self) -> Path | None:
        if self.snapshot_state is None:
            self.snapshot_state = self.runtime.snapshot()
        return self.snapshot_state.run_dir if self.snapshot_state else None

    def _set_busy(self, busy: bool, label: str = "") -> None:
        buttons = (
            self.btn_refresh,
            self.btn_open_command,
            self.btn_export_ho007,
            self.btn_export_evidence,
            self.btn_open_evidence_manifest,
            self.btn_animator_link,
            self.btn_system_influence,
            self.btn_full_report,
            self.btn_param_staging,
            self.btn_diagnostics,
        )
        for button in buttons:
            button.configure(state="disabled" if busy else "normal")
        if busy:
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
            self.status_var.set(f"Выполняется: {label}")
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)

    def _run_job(
        self,
        label: str,
        worker: Callable[[Path], EngineeringAnalysisJobResult],
    ) -> None:
        existing = self._worker_thread
        if existing is not None and existing.is_alive():
            messagebox.showinfo("Инженерный анализ", "Дождитесь завершения текущего действия.")
            return
        run_dir = self._current_run_dir()
        if run_dir is None:
            messagebox.showwarning("Инженерный анализ", "Нет папки прогона для запуска действия.")
            return

        self._set_busy(True, label)
        self._append_log(f"Действие: {label}\nПапка прогона: {run_dir}")

        def _target() -> None:
            try:
                result = worker(run_dir)
            except Exception as exc:
                result = EngineeringAnalysisJobResult(
                    ok=False,
                    status="FAILED",
                    command=(),
                    returncode=None,
                    run_dir=run_dir,
                    artifacts=(),
                    log_text="",
                    error=f"{type(exc).__name__}: {exc!s}",
                )
            self.after(0, lambda: self._finish_job(label, result))

        self._worker_thread = threading.Thread(target=_target, name=f"engineering-analysis-{label}", daemon=True)
        self._worker_thread.start()

    def _finish_job(self, label: str, result: EngineeringAnalysisJobResult) -> None:
        self._set_busy(False)
        status = result.status or ("FINISHED" if result.ok else "FAILED")
        self.status_var.set(f"{label}: {_status_text(status)}")
        if result.command:
            self._append_log("Порядок запуска: " + " ".join(result.command))
        if result.log_text:
            self._append_log(result.log_text)
        if result.error:
            self._append_log("Ошибка: " + result.error)
        self.refresh()
        if label == "Зафиксировать выбранный прогон" and result.ok:
            self._auto_export_evidence_after_ho007()

    def _auto_export_evidence_after_ho007(self) -> None:
        snapshot = self.snapshot_state or self.runtime.snapshot()
        if snapshot.status == "BLOCKED" or snapshot.contract_status in {"MISSING", "INVALID", "BLOCKED"}:
            self._append_log("Автоподготовка диагностики пропущена: выбранный прогон не готов.")
            self.status_var.set("Выбранный прогон зафиксирован; диагностика не подготовлена.")
            return
        try:
            path = self.runtime.write_diagnostics_evidence_manifest(snapshot)
        except Exception as exc:
            self._append_log(f"Не удалось автоматически подготовить диагностику: {type(exc).__name__}: {exc!s}")
            self.status_var.set("Выбранный прогон зафиксирован; диагностика не подготовлена.")
            return
        self._append_log(f"Материалы диагностики подготовлены автоматически: {path}")
        self.status_var.set(f"Выбранный прогон зафиксирован; диагностика подготовлена: {path}")
        self.refresh()

    def _run_system_influence(self) -> None:
        self._run_job(
            "Влияние системы",
            lambda run_dir: self.runtime.run_system_influence(
                run_dir,
                adaptive_eps=True,
                stage_name="engineering_analysis_center",
            ),
        )

    def _run_full_report(self) -> None:
        self._run_job("Полный отчёт", lambda run_dir: self.runtime.run_full_report(run_dir, max_plots=12))

    def _run_param_staging(self) -> None:
        self._run_job("Диапазоны влияния", lambda run_dir: self.runtime.run_param_staging(run_dir))

    def _export_selected_run_contract_bridge(self) -> None:
        existing = self._worker_thread
        if existing is not None and existing.is_alive():
            messagebox.showinfo("Инженерный анализ", "Дождитесь завершения текущего действия.")
            return
        snapshot = self.snapshot_state or self.runtime.snapshot()
        run_dir = self._selected_candidate_run_dir()
        if run_dir is None:
            selected = self._selected_tree_path()
            initial_dir = selected if selected is not None and selected.is_dir() else snapshot.run_dir
            if initial_dir is None:
                initial_dir = self.runtime.repo_root
            chosen = filedialog.askdirectory(
                parent=self,
                title="Выберите папку завершенного прогона оптимизации",
                initialdir=str(initial_dir),
            )
            if not chosen:
                return
            run_dir = Path(chosen)
        self._set_busy(True, "Зафиксировать выбранный прогон")
        self._append_log(f"Действие: Зафиксировать выбранный прогон\nПапка прогона: {run_dir}")

        def _target() -> None:
            try:
                result = self.runtime.export_selected_run_contract_from_run_dir(
                    run_dir,
                    selected_from="desktop_engineering_analysis_center",
                )
            except Exception as exc:
                result = EngineeringAnalysisJobResult(
                    ok=False,
                    status="FAILED",
                    command=(),
                    returncode=None,
                    run_dir=run_dir,
                    artifacts=(),
                    log_text="",
                    error=f"{type(exc).__name__}: {exc!s}",
                )
            self.after(0, lambda: self._finish_job("Зафиксировать выбранный прогон", result))

        self._worker_thread = threading.Thread(
            target=_target,
            name="engineering-analysis-export-ho007",
            daemon=True,
        )
        self._worker_thread.start()

    def _export_diagnostics_evidence(self) -> None:
        snapshot = self.snapshot_state or self.runtime.snapshot()
        try:
            path = self.runtime.write_diagnostics_evidence_manifest(snapshot)
        except Exception as exc:
            messagebox.showerror("Инженерный анализ", f"Не удалось подготовить материалы диагностики:\n{exc!s}")
            self.status_var.set("Не удалось подготовить материалы диагностики.")
            return
        self._append_log(f"Материалы диагностики подготовлены: {path}")
        self.status_var.set(f"Материалы диагностики подготовлены: {path}")
        self.refresh()

    def _export_animator_link(self) -> None:
        snapshot = self.snapshot_state or self.runtime.snapshot()
        pointer = self._selected_tree_path()
        if pointer is None and snapshot.selected_run_context is not None:
            pointer_text = snapshot.selected_run_context.results_csv_path
            pointer = Path(pointer_text) if pointer_text else None
        if pointer is None:
            messagebox.showwarning("Инженерный анализ", "Выберите файл для передачи в аниматор.")
            return
        try:
            payload = self.runtime.export_analysis_to_animator_link_contract(
                snapshot,
                selected_result_artifact_pointer=pointer,
            )
        except Exception as exc:
            messagebox.showerror("Инженерный анализ", f"Не удалось подготовить связь с аниматором:\n{exc!s}")
            self.status_var.set("Не удалось подготовить связь с аниматором.")
            return
        self._append_log(
            "Связь с аниматором подготовлена: "
            + str(payload.get("animator_link_contract_path") or "")
        )
        self.status_var.set(
            "Связь с аниматором подготовлена: "
            + str(payload.get("analysis_context_path") or "")
        )

    def _launch_full_diagnostics_gui(self) -> None:
        command = [
            sys.executable,
            "-m",
            "pneumo_solver_ui.tools.desktop_diagnostics_center",
        ]
        try:
            proc = subprocess.Popen(command, cwd=str(self.runtime.repo_root))
        except Exception as exc:
            messagebox.showerror("Инженерный анализ", f"Не удалось запустить диагностику:\n{exc!s}")
            self.status_var.set("Не удалось запустить диагностику.")
            return
        self._append_log("Запущена диагностика.")
        self.status_var.set("Диагностика запущена в отдельном окне.")


def _default_runtime() -> DesktopEngineeringAnalysisRuntime:
    return DesktopEngineeringAnalysisRuntime(
        repo_root=Path(__file__).resolve().parents[2],
        python_executable=sys.executable,
    )


def main() -> int:
    root = tk.Tk()
    root.title("Инженерный анализ")
    root.geometry("1360x860")
    root.minsize(1120, 720)
    center = DesktopEngineeringAnalysisCenter(root, runtime=_default_runtime())
    center.pack(fill="both", expand=True)
    root.mainloop()
    return 0


__all__ = [
    "DesktopEngineeringAnalysisCenter",
    "format_contract_banner",
    "format_selected_run_summary",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
