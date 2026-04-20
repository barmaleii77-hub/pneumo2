from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from pneumo_solver_ui.desktop_results_model import (
    DesktopResultsArtifact,
    DesktopResultsOverviewRow,
    DesktopResultsSessionHandoff,
    DesktopResultsSnapshot,
    format_npz_summary,
    format_optimizer_gate_summary,
    format_recent_runs_summary,
    format_result_context_summary,
    format_triage_summary,
    format_validation_summary,
)
from pneumo_solver_ui.desktop_results_runtime import DesktopResultsRuntime
from pneumo_solver_ui.desktop_ui_core import ScrollableFrame, build_scrolled_text, build_scrolled_treeview
from pneumo_solver_ui.release_info import get_release


def _open_path(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def _button_text(prefix: str, text: str, *, limit: int = 58) -> str:
    raw = " ".join(_operator_text(text).split())
    if not raw:
        return prefix
    if len(raw) > limit:
        raw = raw[: max(0, limit - 3)].rstrip() + "..."
    return f"{prefix}: {raw}"


def _operator_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    replacements = {
        "Open Desktop Animator first and inspect Mnemo red flags before send.": (
            "Сначала откройте аниматор и проверьте красные флаги мнемосхемы перед сохранением архива проекта."
        ),
        "rc=": "код завершения ",
        "duration=": "длительность ",
        "ZIP": "архив",
        "Autotest:": "Автотест:",
        "Diagnostics:": "Проверка проекта:",
        "Action completed:": "Действие выполнено:",
        "Opened:": "Открыт файл:",
        "Pinned current run.": "Текущий прогон закреплён.",
        "Open Desktop Animator first": "Сначала откройте аниматор",
        "Then inspect Compare Viewer": "Затем проверьте сравнение прогонов",
        "Open Compare Viewer next": "Перейдите к сравнению прогонов",
        "Открыть Compare Viewer " "следующим шагом": "Перейти к сравнению прогонов",
        "Desktop Mnemo recent:": "Недавнее событие мнемосхемы:",
        "Pointer drift": "Расхождение данных сопровождения",
        "Compare Viewer": "сравнение прогонов",
        "Desktop Animator": "аниматор",
        "Desktop Mnemo": "мнемосхема",
        "Open browser perf evidence": "Открыть материалы производительности интерфейса",
        "Browser perf artifacts are missing.": "Материалы производительности интерфейса не найдены.",
        "browser perf artifacts are missing": "материалы производительности интерфейса не найдены",
        "browser perf evidence": "материалы производительности интерфейса",
        "optimizer scope artifacts are missing": "материалы области оптимизации не найдены",
        "optimizer scope": "область оптимизации",
        "artifacts are missing": "материалы не найдены",
        "frozen context": "закреплёнными данными",
        "hash=": "метка ",
        "path=": "файл ",
        "current=": "текущее ",
        "selected=": "выбранное ",
        "FAIL": "ошибка",
        "PASS": "норма",
        "WARN": "предупреждение",
        "MISSING": "нет данных",
        "READY": "готово",
        "HO-009": "",
        "HO-010": "",
        "handoff": "передача данных",
        "manifest": "описание файлов",
        "selected_run_contract.json": "файл выбранного прогона",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _short_value(value: object, *, limit: int = 28) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"
    return text if len(text) <= limit else text[: max(0, limit - 3)].rstrip() + "..."


def _action_label(action_key: str) -> str:
    labels = {
        "open_artifact": "открыт материал",
        "open_compare_viewer": "открыто сравнение прогонов",
        "open_animator": "открыт аниматор",
        "open_animator_follow": "открыта анимация результатов расчёта",
        "open_diagnostics_gui": "открыта проверка проекта",
        "open_send_center": "открыто копирование архива",
        "open_send_bundles": "открыта папка архивов проекта",
        "export_diagnostics_evidence": "сохранены материалы проверки проекта",
    }
    return labels.get(str(action_key or "").strip(), "действие выполнено")


def _artifact_matches_filters(
    artifact: DesktopResultsArtifact,
    *,
    category: str,
    query: str,
) -> bool:
    target_category = str(category or "").strip().lower()
    if target_category and target_category != "all":
        if str(artifact.category or "").strip().lower() != target_category:
            return False

    raw_query = " ".join(str(query or "").split()).strip().lower()
    if not raw_query:
        return True

    haystack = " ".join(
        [
            str(artifact.title or ""),
            str(artifact.category or ""),
            str(artifact.path or ""),
            str(artifact.detail or ""),
        ]
    ).lower()
    return all(token in haystack for token in raw_query.split(" ") if token)


_BROWSE_CATEGORY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("all", "Все материалы"),
    ("validation", "Проверка"),
    ("triage", "Разбор замечаний"),
    ("results", "Результаты"),
    ("anim_latest", "Визуализация"),
    ("evidence", "Материалы проверки проекта"),
    ("runs", "Прогоны"),
    ("bundle", "Архив проекта"),
)

_STATUS_LABELS: dict[str, str] = {
    "PASS": "Норма",
    "FAIL": "Ошибка",
    "WARN": "Предупреждение",
    "READY": "Готово",
    "MISSING": "Нет данных",
    "BLOCKED": "Заблокировано",
    "CRITICAL": "Критично",
    "PARTIAL": "Частично",
    "INFO": "Справка",
    "CURRENT": "Текущий",
    "HISTORICAL": "Исторический",
    "STALE": "Устарел",
    "UNKNOWN": "Не определён",
    "N/A": "Нет данных",
}


def _browse_category_key(value: str) -> str:
    text = str(value or "").strip()
    for key, label in _BROWSE_CATEGORY_OPTIONS:
        if text == key or text == label:
            return key
    return "all"


def _browse_category_label(value: str) -> str:
    key = _browse_category_key(value)
    for option_key, label in _BROWSE_CATEGORY_OPTIONS:
        if option_key == key:
            return label
    return key


def _status_label(value: str) -> str:
    raw = str(value or "").strip()
    return _STATUS_LABELS.get(raw.upper(), raw or "—")


class DesktopResultsCenter(ttk.Frame):
    _CURRENT_RUN_GROUP_IID = "current_run_group"
    _LATEST_ARTIFACTS_GROUP_IID = "latest_artifacts_group"

    def __init__(
        self,
        master: tk.Misc,
        *,
        runtime: DesktopResultsRuntime,
    ) -> None:
        super().__init__(master, padding=10)
        self.runtime = runtime
        self.snapshot_state: DesktopResultsSnapshot | None = None
        self.session_handoff_state: DesktopResultsSessionHandoff | None = None
        self._artifact_by_iid: dict[str, DesktopResultsArtifact] = {}
        self._overview_by_iid: dict[str, DesktopResultsOverviewRow] = {}

        self.validation_var = tk.StringVar(master=self, value="Проверка: результаты пока недоступны.")
        self.optimizer_var = tk.StringVar(master=self, value="Оптимизация: шлюз оценки пока не собран")
        self.triage_var = tk.StringVar(master=self, value="Разбор замечаний: критичных: 0; предупреждений: 0; справочных: 0; красных флагов: 0")
        self.npz_var = tk.StringVar(master=self, value="Последний файл анимации: пока недоступен.")
        self.runs_var = tk.StringVar(master=self, value="Последние прогоны: автотест: —; проверка проекта: —")
        self.context_var = tk.StringVar(master=self, value="Результаты расчёта: не определены")
        self.context_banner_var = tk.StringVar(master=self, value="Результаты расчёта пока не определены.")
        self.evidence_manifest_var = tk.StringVar(master=self, value="Материалы проверки проекта: пока не сохранены.")
        self.next_step_var = tk.StringVar(master=self, value="Рекомендация: дождитесь первого снимка проверки и результатов.")
        self.next_detail_var = tk.StringVar(master=self, value="Свежие материалы проверки и результатов пока не появились.")
        self.handoff_summary_var = tk.StringVar(master=self, value="Последний прогон: материалы пока не подготовлены.")
        self.handoff_detail_var = tk.StringVar(master=self, value="Запустите проверки на первой вкладке, чтобы закрепить текущий прогон в анализе результатов.")
        self.handoff_steps_var = tk.StringVar(master=self, value="")
        self.show_current_run_only = tk.BooleanVar(master=self, value=False)
        self.browse_category_var = tk.StringVar(master=self, value=_browse_category_label("all"))
        self.browse_query_var = tk.StringVar(master=self, value="")
        self.status_var = tk.StringVar(master=self, value="Анализ результатов готов.")

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(
            title_box,
            text="Результаты и анализ",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            textvariable=self.validation_var,
            justify="left",
            wraplength=760,
        ).pack(anchor="w", pady=(2, 0))

        actions = ttk.Frame(header)
        actions.pack(side="right", anchor="ne")
        ttk.Button(actions, text="Обновить результаты", command=self.refresh).pack(side="left")
        self.btn_open_selected = ttk.Button(actions, text="Открыть материал", command=self._open_selected)
        self.btn_open_selected.pack(side="left", padx=(8, 0))
        self.btn_diagnostics = ttk.Button(actions, text="Сохранить архив проекта", command=self._launch_full_diagnostics_gui)
        self.btn_diagnostics.pack(side="left", padx=(8, 0))
        self.btn_export_evidence = ttk.Button(actions, text="Сохранить материалы", command=self._export_diagnostics_evidence)
        self.btn_export_evidence.pack(side="left", padx=(8, 0))
        self.btn_compare = ttk.Button(actions, text="Сравнить в отдельном окне", command=self._launch_compare_viewer)
        self.btn_compare.pack(side="left", padx=(8, 0))
        self.btn_animator = ttk.Button(actions, text="Аниматор", command=self._launch_animator)
        self.btn_animator.pack(side="left", padx=(8, 0))
        self.btn_animator_follow = ttk.Button(
            actions,
            text="Аниматор по результату",
            command=self._launch_animator_follow,
        )
        self.btn_animator_follow.pack(side="left", padx=(8, 0))

        workspace = ttk.Panedwindow(self, orient="horizontal")
        workspace.pack(fill="both", expand=True)

        left_column = ttk.Frame(workspace)
        left_pane = ttk.Panedwindow(left_column, orient="vertical")
        left_pane.pack(fill="both", expand=True)

        right_column = ttk.Frame(workspace)
        right_pane = ttk.Panedwindow(right_column, orient="vertical")
        right_pane.pack(fill="both", expand=True)

        summary_host = ScrollableFrame(right_pane)
        summary_body = ttk.Frame(summary_host.body, padding=4)
        summary_body.pack(fill="both", expand=True)
        summary_body.columnconfigure(0, weight=1)

        summary = ttk.LabelFrame(summary_body, text="Сводка", padding=10)
        summary.pack(fill="x")
        ttk.Label(summary, textvariable=self.validation_var, wraplength=420, justify="left").pack(anchor="w")
        ttk.Label(summary, textvariable=self.optimizer_var, wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.triage_var, wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.npz_var, wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.runs_var, wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.context_var, wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.context_banner_var, wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.evidence_manifest_var, wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))

        handoff = ttk.LabelFrame(summary_body, text="Рекомендация", padding=10)
        handoff.pack(fill="x", pady=(10, 0))
        ttk.Label(
            handoff,
            textvariable=self.next_step_var,
            font=("Segoe UI", 10, "bold"),
            wraplength=420,
            justify="left",
        ).pack(anchor="w")
        ttk.Label(
            handoff,
            textvariable=self.next_detail_var,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        handoff_actions = ttk.Frame(handoff)
        handoff_actions.pack(fill="x", pady=(8, 0))
        self.btn_run_next_step = ttk.Button(
            handoff_actions,
            text="Выполнить рекомендуемое действие",
            command=self._run_suggested_next_step,
        )
        self.btn_run_next_step.pack(side="left")

        run_handoff = ttk.LabelFrame(summary_body, text="Материалы последнего прогона", padding=10)
        run_handoff.pack(fill="x", pady=(10, 0))
        ttk.Label(
            run_handoff,
            textvariable=self.handoff_summary_var,
            font=("Segoe UI", 10, "bold"),
            wraplength=420,
            justify="left",
        ).pack(anchor="w")
        ttk.Label(
            run_handoff,
            textvariable=self.handoff_detail_var,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        ttk.Label(
            run_handoff,
            textvariable=self.handoff_steps_var,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        run_handoff_actions = ttk.Frame(run_handoff)
        run_handoff_actions.pack(fill="x", pady=(8, 0))
        self.btn_open_handoff_zip = ttk.Button(
            run_handoff_actions,
            text="Открыть последний архив",
            command=self._open_handoff_zip,
        )
        self.btn_open_handoff_zip.pack(side="left")
        self.btn_open_handoff_autotest = ttk.Button(
            run_handoff_actions,
            text="Открыть последний автотест",
            command=self._open_handoff_autotest_run,
        )
        self.btn_open_handoff_autotest.pack(side="left", padx=(8, 0))
        self.btn_open_handoff_diagnostics = ttk.Button(
            run_handoff_actions,
            text="Открыть последнюю проверку",
            command=self._open_handoff_diagnostics_run,
        )
        self.btn_open_handoff_diagnostics.pack(side="left", padx=(8, 0))
        self.btn_focus_suggested = ttk.Button(
            run_handoff_actions,
            text="Перейти к рекомендованной проверке",
            command=self._focus_suggested_branch,
        )
        self.btn_focus_suggested.pack(side="left", padx=(8, 0))
        run_handoff_shortcuts = ttk.Frame(run_handoff)
        run_handoff_shortcuts.pack(fill="x", pady=(8, 0))
        self.btn_handoff_validation = ttk.Button(
            run_handoff_shortcuts,
            text="Открыть текущую проверку",
            command=self._open_handoff_validation,
        )
        self.btn_handoff_validation.pack(side="left")
        self.btn_handoff_triage = ttk.Button(
            run_handoff_shortcuts,
            text="Открыть текущий разбор замечаний",
            command=self._open_handoff_triage,
        )
        self.btn_handoff_triage.pack(side="left", padx=(8, 0))
        self.btn_handoff_compare = ttk.Button(
            run_handoff_shortcuts,
            text="Сравнить текущий прогон в отдельном окне",
            command=self._branch_handoff_compare,
        )
        self.btn_handoff_compare.pack(side="left", padx=(8, 0))
        self.btn_handoff_animator = ttk.Button(
            run_handoff_shortcuts,
            text="Открыть текущую анимацию",
            command=self._branch_handoff_animator,
        )
        self.btn_handoff_animator.pack(side="left", padx=(8, 0))

        tools = ttk.LabelFrame(summary_body, text="Инструменты", padding=10)
        tools.pack(fill="x", pady=(10, 0))
        ttk.Button(tools, text="Открыть папку архивов", command=self._open_send_bundles).pack(fill="x")
        ttk.Button(tools, text="Сохранить архив проекта", command=self._launch_full_diagnostics_gui).pack(fill="x", pady=(6, 0))
        ttk.Button(tools, text="Сохранить материалы проверки проекта", command=self._export_diagnostics_evidence).pack(fill="x", pady=(6, 0))
        ttk.Button(tools, text="Скопировать архив", command=self._launch_send_results_gui).pack(fill="x", pady=(6, 0))

        overview = ttk.LabelFrame(left_pane, text="Обзор проверок", padding=8)
        overview_tree_frame, self.overview_tree = build_scrolled_treeview(
            overview,
            columns=("status", "detail", "next_action", "evidence"),
            show="tree headings",
            height=6,
        )
        self.overview_tree.heading("#0", text="Проверка")
        self.overview_tree.heading("status", text="Состояние")
        self.overview_tree.heading("detail", text="Пояснение")
        self.overview_tree.heading("next_action", text="Следующее действие")
        self.overview_tree.heading("evidence", text="Материал")
        self.overview_tree.column("#0", width=220, anchor="w")
        self.overview_tree.column("status", width=110, anchor="w")
        self.overview_tree.column("detail", width=340, anchor="w")
        self.overview_tree.column("next_action", width=220, anchor="w")
        self.overview_tree.column("evidence", width=340, anchor="w")
        overview_tree_frame.pack(fill="both", expand=True)
        self.overview_tree.bind("<<TreeviewSelect>>", self._on_overview_select)
        self.overview_tree.bind("<Double-1>", self._on_overview_open)
        overview_actions = ttk.Frame(overview)
        overview_actions.pack(fill="x", pady=(8, 0))
        self.btn_overview_action = ttk.Button(
            overview_actions,
            text="Выполнить действие по выбранной проверке",
            command=self._run_selected_overview_action,
        )
        self.btn_overview_action.pack(side="left")
        left_pane.add(overview, weight=2)

        browse = ttk.LabelFrame(left_pane, text="Материалы", padding=8)

        browse_controls = ttk.Frame(browse)
        browse_controls.pack(fill="x", pady=(0, 8))
        self.chk_current_run_only = ttk.Checkbutton(
            browse_controls,
            text="Только текущий прогон",
            variable=self.show_current_run_only,
            command=self._on_browse_scope_changed,
        )
        self.chk_current_run_only.pack(side="left")
        ttk.Label(browse_controls, text="Раздел:").pack(side="left", padx=(12, 4))
        self.cmb_browse_category = ttk.Combobox(
            browse_controls,
            textvariable=self.browse_category_var,
            values=[label for _key, label in _BROWSE_CATEGORY_OPTIONS],
            width=14,
            state="readonly",
        )
        self.cmb_browse_category.pack(side="left")
        self.cmb_browse_category.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_browse_scope_changed(),
        )
        ttk.Label(browse_controls, text="Поиск:").pack(side="left", padx=(12, 4))
        self.entry_browse_query = ttk.Entry(
            browse_controls,
            textvariable=self.browse_query_var,
            width=28,
        )
        self.entry_browse_query.pack(side="left")
        self.entry_browse_query.bind(
            "<KeyRelease>",
            lambda _event: self._on_browse_scope_changed(),
        )
        self.btn_clear_browse_query = ttk.Button(
            browse_controls,
            text="Очистить",
            command=self._clear_browse_query,
        )
        self.btn_clear_browse_query.pack(side="left", padx=(8, 0))

        artifact_tree_frame, self.tree = build_scrolled_treeview(
            browse,
            columns=("category", "path"),
            show="tree headings",
            height=16,
        )
        self.tree.heading("#0", text="Материал")
        self.tree.heading("category", text="Раздел")
        self.tree.heading("path", text="Путь")
        self.tree.column("#0", width=240, anchor="w")
        self.tree.column("category", width=120, anchor="w")
        self.tree.column("path", width=420, anchor="w")
        artifact_tree_frame.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_open_selected)
        left_pane.add(browse, weight=3)

        details = ttk.LabelFrame(right_pane, text="Подробности", padding=8)
        details_body, self.details = build_scrolled_text(details, wrap="word", height=16)
        details_body.pack(fill="both", expand=True)
        self.details.configure(state="disabled")
        right_pane.add(details, weight=4)
        right_pane.add(summary_host, weight=3)
        workspace.add(left_column, weight=3)
        workspace.add(right_column, weight=4)

        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        ttk.Sizegrip(footer).pack(side="right")

    def refresh(self) -> None:
        self.snapshot_state = self.runtime.snapshot()
        snapshot = self.snapshot_state
        self.validation_var.set(format_validation_summary(snapshot))
        self.optimizer_var.set(format_optimizer_gate_summary(snapshot))
        self.triage_var.set(format_triage_summary(snapshot))
        self.npz_var.set(format_npz_summary(snapshot))
        self.runs_var.set(format_recent_runs_summary(snapshot))
        self.context_var.set(format_result_context_summary(snapshot))
        self.context_banner_var.set(_operator_text(snapshot.result_context_banner))
        manifest_label = (
            str(snapshot.diagnostics_evidence_manifest_path)
            if snapshot.diagnostics_evidence_manifest_path is not None
            else "пока не сохранены"
        )
        self.evidence_manifest_var.set(
            "Материалы проверки проекта: "
            + f"{_status_label(snapshot.diagnostics_evidence_manifest_status)}; "
            + manifest_label
        )
        if snapshot.selected_run_contract_path is not None:
            self.context_banner_var.set(
                _operator_text(snapshot.result_context_banner)
                + "\nВыбранный расчёт для анализа: "
                + f"состояние: {_status_label(snapshot.selected_run_contract_status)}; "
                + f"файл: {snapshot.selected_run_contract_path}"
            )
        self.next_step_var.set("Рекомендация: " + _operator_text(snapshot.suggested_next_step))
        self.next_detail_var.set("Причина: " + _operator_text(snapshot.suggested_next_detail))
        self._render_overview(snapshot)
        self._render_artifacts(snapshot)
        self._select_initial_overview(snapshot)
        self._render_session_handoff()
        self._render_details()
        self._refresh_action_states(snapshot)
        self.status_var.set("Обзор результатов обновлён.")

    def set_session_handoff(self, handoff: DesktopResultsSessionHandoff | None) -> None:
        self.session_handoff_state = handoff
        if self.snapshot_state is not None:
            self._render_artifacts(self.snapshot_state)
            self._select_initial_overview(self.snapshot_state)
        self._render_session_handoff()
        self._render_details()
        if self.snapshot_state is not None:
            self._refresh_action_states(self.snapshot_state)

    def _refresh_action_states(self, snapshot: DesktopResultsSnapshot) -> None:
        artifact = self._selected_artifact()
        row = self._selected_overview_row()
        row_artifact = self.runtime.preferred_overview_evidence_artifact(
            snapshot,
            row,
            handoff=self.session_handoff_state,
        )
        compare_target = self.runtime.compare_viewer_path(snapshot, artifact=artifact)
        animator_npz, animator_pointer = self.runtime.animator_target_paths(
            snapshot,
            artifact=artifact,
        )
        self.btn_open_selected.configure(
            state="normal" if bool(self._artifact_by_iid) else "disabled"
        )
        self.btn_compare.configure(
            state="normal" if compare_target is not None else "disabled"
        )
        self.btn_animator.configure(
            state="normal"
            if (animator_npz is not None or animator_pointer is not None)
            else "disabled"
        )
        self.btn_animator_follow.configure(
            state="normal"
            if (animator_pointer is not None or animator_npz is not None)
            else "disabled"
        )
        self.btn_export_evidence.configure(state="normal")
        self.btn_run_next_step.configure(
            text=_button_text("Выполнить рекомендацию", snapshot.suggested_next_step),
            state=(
                "normal"
                if self._can_run_action(
                    snapshot,
                    snapshot.suggested_next_action_key,
                    artifact=self.runtime.preferred_artifact_by_key(
                        snapshot,
                        snapshot.suggested_next_artifact_key,
                        handoff=self.session_handoff_state,
                    ),
                )
                else "disabled"
            ),
        )
        handoff = self.session_handoff_state
        has_session_artifacts = self._has_session_artifacts(snapshot)
        if not has_session_artifacts and self.show_current_run_only.get():
            self.show_current_run_only.set(False)
        self.chk_current_run_only.configure(
            state="normal" if has_session_artifacts else "disabled"
        )
        self.cmb_browse_category.configure(
            state="readonly"
        )
        self.btn_clear_browse_query.configure(
            state="normal" if str(self.browse_query_var.get() or "").strip() else "disabled"
        )
        self.btn_open_handoff_zip.configure(
            state=(
                "normal"
                if handoff is not None and handoff.zip_path is not None
                else "disabled"
            )
        )
        self.btn_open_handoff_autotest.configure(
            state=(
                "normal"
                if handoff is not None and handoff.autotest_run_dir is not None
                else "disabled"
            )
        )
        self.btn_open_handoff_diagnostics.configure(
            state=(
                "normal"
                if handoff is not None and handoff.diagnostics_run_dir is not None
                else "disabled"
            )
        )
        current_validation_artifact = self._preferred_handoff_artifact("validation_json")
        current_triage_artifact = self._preferred_handoff_artifact("triage_json")
        current_compare_artifact = self._preferred_handoff_artifact("latest_npz")
        current_animator_artifact = (
            self._preferred_handoff_artifact("latest_pointer")
            or self._preferred_handoff_artifact("latest_npz")
        )
        self.btn_handoff_validation.configure(
            state="normal" if current_validation_artifact is not None else "disabled"
        )
        self.btn_handoff_triage.configure(
            state="normal" if current_triage_artifact is not None else "disabled"
        )
        self.btn_handoff_compare.configure(
            state=(
                "normal"
                if self._can_run_action(
                    snapshot,
                    "open_compare_viewer",
                    artifact=current_compare_artifact,
                )
                else "disabled"
            )
        )
        self.btn_handoff_animator.configure(
            state=(
                "normal"
                if self._can_run_action(
                    snapshot,
                    "open_animator_follow",
                    artifact=current_animator_artifact,
                )
                else "disabled"
            )
        )
        self.btn_focus_suggested.configure(
            state="normal" if bool(snapshot.validation_overview_rows) else "disabled"
        )
        overview_action_label = row.next_action if row is not None else ""
        self.btn_overview_action.configure(
            text=_button_text("Выполнить действие по проверке", overview_action_label),
            state=(
                "normal"
                if (
                    row is not None
                    and self._can_run_action(
                        snapshot,
                        row.action_key,
                        artifact=row_artifact,
                        path=row.evidence_path,
                    )
                )
                else "disabled"
            ),
        )

    def _render_artifacts(self, snapshot: DesktopResultsSnapshot) -> None:
        selected_artifact = self._selected_artifact()
        selected_key = selected_artifact.key if selected_artifact is not None else ""
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._artifact_by_iid.clear()
        session_artifacts = list(
            self.runtime.session_artifacts(snapshot, self.session_handoff_state)
        )
        latest_artifacts = list(snapshot.recent_artifacts)
        session_artifacts = [
            artifact for artifact in session_artifacts if self._artifact_matches_browse_filter(artifact)
        ]
        latest_artifacts = [
            artifact for artifact in latest_artifacts if self._artifact_matches_browse_filter(artifact)
        ]
        show_current_only = self.show_current_run_only.get() and bool(session_artifacts)

        if session_artifacts:
            self.tree.insert(
                "",
                "end",
                iid=self._CURRENT_RUN_GROUP_IID,
                text="Текущий прогон (закреплён)",
                values=("Раздел", f"{len(session_artifacts)} материалов"),
                open=True,
            )
            for artifact in session_artifacts:
                iid = artifact.key
                self._artifact_by_iid[iid] = artifact
                self.tree.insert(
                    self._CURRENT_RUN_GROUP_IID,
                    "end",
                    iid=iid,
                    text=artifact.title,
                    values=(_browse_category_label(artifact.category), str(artifact.path)),
                )

        if latest_artifacts and not show_current_only:
            self.tree.insert(
                "",
                "end",
                iid=self._LATEST_ARTIFACTS_GROUP_IID,
                text="Последние материалы рабочей области",
                values=("Раздел", f"{len(latest_artifacts)} материалов"),
                open=True,
            )
            for artifact in latest_artifacts:
                iid = artifact.key
                self._artifact_by_iid[iid] = artifact
                self.tree.insert(
                    self._LATEST_ARTIFACTS_GROUP_IID,
                    "end",
                    iid=iid,
                    text=artifact.title,
                    values=(_browse_category_label(artifact.category), str(artifact.path)),
                )

        artifacts = session_artifacts if show_current_only else session_artifacts + latest_artifacts
        if artifacts:
            target_key = selected_key if selected_key in self._artifact_by_iid else artifacts[0].key
            self.tree.selection_set(target_key)
            self.tree.focus(target_key)
            self.tree.see(target_key)

    def _render_overview(self, snapshot: DesktopResultsSnapshot) -> None:
        for iid in self.overview_tree.get_children():
            self.overview_tree.delete(iid)
        self._overview_by_iid.clear()
        for row in snapshot.validation_overview_rows:
            self._overview_by_iid[row.key] = row
            self.overview_tree.insert(
                "",
                "end",
                iid=row.key,
                text=row.title,
                values=(
                    _status_label(row.status),
                    _operator_text(row.detail),
                    _operator_text(row.next_action),
                    str(row.evidence_path) if row.evidence_path is not None else "",
                ),
            )

    def _selected_artifact(self) -> DesktopResultsArtifact | None:
        selected = list(self.tree.selection())
        if not selected:
            return None
        return self._artifact_by_iid.get(selected[0])

    def _selected_overview_row(self) -> DesktopResultsOverviewRow | None:
        selected = list(self.overview_tree.selection())
        if not selected:
            return None
        return self._overview_by_iid.get(selected[0])

    def _select_artifact(self, artifact: DesktopResultsArtifact | None) -> None:
        if artifact is None or artifact.key not in self._artifact_by_iid:
            return
        self.tree.selection_set(artifact.key)
        self.tree.focus(artifact.key)
        self.tree.see(artifact.key)

    def _select_initial_overview(self, snapshot: DesktopResultsSnapshot) -> None:
        if not snapshot.validation_overview_rows:
            return
        target_row = None
        if snapshot.suggested_next_artifact_key:
            for row in snapshot.validation_overview_rows:
                if row.artifact_key == snapshot.suggested_next_artifact_key:
                    target_row = row
                    break
        if target_row is None:
            target_row = snapshot.validation_overview_rows[0]
        self.overview_tree.selection_set(target_row.key)
        self.overview_tree.focus(target_row.key)
        self.overview_tree.see(target_row.key)
        self._select_artifact(
            self.runtime.preferred_overview_evidence_artifact(
                snapshot,
                target_row,
                handoff=self.session_handoff_state,
            )
        )

    def _render_session_handoff(self) -> None:
        handoff = self.session_handoff_state
        if handoff is None:
            self.handoff_summary_var.set("Последний прогон: материалы пока не подготовлены.")
            self.handoff_detail_var.set(
                "Запустите проверки с первой вкладки, чтобы закрепить текущую сессию в анализе результатов."
            )
            self.handoff_steps_var.set("")
            return
        self.handoff_summary_var.set("Последний прогон: " + _operator_text(handoff.summary))
        self.handoff_detail_var.set(_operator_text(handoff.detail))
        self.handoff_steps_var.set(
            "Шаги: "
            + " | ".join(
                _operator_text(item) for item in handoff.step_lines if str(item).strip()
            )
            if handoff.step_lines
            else ""
        )

    def _preferred_handoff_artifact(
        self,
        artifact_key: str,
    ) -> DesktopResultsArtifact | None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return None
        return self.runtime.preferred_artifact_by_key(
            snapshot,
            artifact_key,
            handoff=self.session_handoff_state,
        )

    def _has_session_artifacts(self, snapshot: DesktopResultsSnapshot) -> bool:
        return bool(self.runtime.session_artifacts(snapshot, self.session_handoff_state))

    def _artifact_matches_browse_filter(self, artifact: DesktopResultsArtifact) -> bool:
        return _artifact_matches_filters(
            artifact,
            category=_browse_category_key(self.browse_category_var.get()),
            query=self.browse_query_var.get(),
        )

    def _browse_scope_summary(self) -> str:
        scope = (
            "только текущий прогон"
            if self.show_current_run_only.get()
            else "текущий прогон и последние материалы"
        )
        category = _browse_category_label(self.browse_category_var.get() or "all")
        query = " ".join(str(self.browse_query_var.get() or "").split()).strip()
        return f"{scope}; раздел: {category}; запрос: {query or '—'}"

    def _clear_browse_query(self) -> None:
        if not str(self.browse_query_var.get() or "").strip():
            return
        self.browse_query_var.set("")
        self._on_browse_scope_changed()

    def _on_browse_scope_changed(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        if self.show_current_run_only.get() and not self._has_session_artifacts(snapshot):
            self.show_current_run_only.set(False)
        self._render_artifacts(snapshot)
        self._render_details()
        self._refresh_action_states(snapshot)
        self.status_var.set("Область просмотра обновлена: " + self._browse_scope_summary())

    def _can_run_action(
        self,
        snapshot: DesktopResultsSnapshot,
        action_key: str,
        *,
        artifact: DesktopResultsArtifact | None = None,
        path: Path | None = None,
    ) -> bool:
        action = str(action_key or "").strip()
        if not action:
            return False
        if action == "open_artifact":
            return artifact is not None or path is not None
        if action == "open_compare_viewer":
            return self.runtime.compare_viewer_path(snapshot, artifact=artifact) is not None
        if action == "open_animator":
            npz_path, pointer_path = self.runtime.animator_target_paths(
                snapshot,
                artifact=artifact,
            )
            return npz_path is not None or pointer_path is not None
        if action == "open_animator_follow":
            args = self.runtime.animator_args(
                snapshot,
                follow=True,
                artifact=artifact,
            )
            return bool(args)
        if action in {
            "open_diagnostics_gui",
            "open_send_center",
            "open_send_bundles",
            "export_diagnostics_evidence",
        }:
            return True
        return False

    def _render_details(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        artifact = self._selected_artifact()
        row = self._selected_overview_row()
        handoff = self.session_handoff_state
        selected_run_line = (
            "Выбранный расчёт для анализа: "
            f"состояние: {_status_label(snapshot.selected_run_contract_status)}; "
            f"метка: {_short_value(snapshot.selected_run_contract_hash)}; "
            f"файл: {snapshot.selected_run_contract_path or '—'}"
        )
        lines = [
            format_validation_summary(snapshot),
            format_optimizer_gate_summary(snapshot),
            format_triage_summary(snapshot),
            format_npz_summary(snapshot),
            format_recent_runs_summary(snapshot),
            format_result_context_summary(snapshot),
            _operator_text(snapshot.result_context_banner),
            selected_run_line,
            _operator_text(snapshot.selected_run_contract_banner),
            f"Материалы проверки проекта: {snapshot.diagnostics_evidence_manifest_path or '—'}",
            "Область просмотра: " + self._browse_scope_summary(),
            "",
            "Рекомендуемый следующий шаг:",
            _operator_text(snapshot.suggested_next_step),
            f"Почему сейчас: {_operator_text(snapshot.suggested_next_detail)}",
        ]
        if snapshot.result_context_detail:
            lines.append("Детали расчёта: " + _operator_text(snapshot.result_context_detail))
        if snapshot.result_context_action:
            lines.append("Действие по результату: " + _operator_text(snapshot.result_context_action))
        if snapshot.result_context_fields:
            lines.extend(["", "Поля результатов расчёта:"])
            for field in snapshot.result_context_fields[:12]:
                lines.append(
                    "- "
                    + f"{field.title}: {_status_label(field.status)} | "
                    + f"текущее: {field.current_value or '—'}; выбранное: {field.selected_value or '—'}"
                )
        if handoff is not None:
            lines.extend(
                [
                    "",
                    "Материалы последнего прогона:",
                    _operator_text(handoff.summary),
                ]
            )
            if handoff.detail:
                lines.append(_operator_text(handoff.detail))
            if handoff.step_lines:
                lines.extend(f"- {_operator_text(item)}" for item in handoff.step_lines)
        if row is not None:
            lines.extend(
                [
                    "",
                    f"Выбранная проверка: {row.title}",
                    f"Состояние проверки: {_status_label(row.status)}",
                    f"Пояснение проверки: {_operator_text(row.detail)}",
                ]
            )
            if row.next_action:
                lines.append(f"Следующее действие: {_operator_text(row.next_action)}")
            if row.evidence_path is not None:
                lines.append(f"Материал проверки: {row.evidence_path}")
        if snapshot.mnemo_current_mode:
            lines.append(f"Режим мнемосхемы: {snapshot.mnemo_current_mode}")
        if snapshot.mnemo_recent_titles:
            lines.append(
                "Последние события мнемосхемы: "
                + " | ".join(_operator_text(item) for item in snapshot.mnemo_recent_titles[:3])
            )
        if snapshot.optimizer_scope_gate_reason:
            lines.append(
                "Причина ограничения оптимизации: "
                + _operator_text(snapshot.optimizer_scope_gate_reason)
            )
        if artifact is not None:
            lines.extend(
                [
                    "",
                    f"Выбранный материал: {artifact.title}",
                    f"Раздел: {_browse_category_label(artifact.category)}",
                    f"Файл: {artifact.path}",
                ]
            )
            try:
                st = artifact.path.stat()
                changed_at = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"Изменён: {changed_at}")
                if artifact.path.is_file():
                    lines.append(f"Размер файла: {int(st.st_size)} байт")
            except Exception:
                pass
            if artifact.detail:
                lines.append(f"Примечание: {_operator_text(artifact.detail)}")
            compare_target = self.runtime.compare_viewer_path(snapshot, artifact=artifact)
            animator_npz, animator_pointer = self.runtime.animator_target_paths(
                snapshot,
                artifact=artifact,
            )
            if compare_target is not None:
                lines.append(f"Файл для сравнения: {compare_target}")
            if animator_pointer is not None:
                lines.append(f"Данные для аниматора: {animator_pointer}")
            elif animator_npz is not None:
                lines.append(f"Файл анимации: {animator_npz}")
            preview_lines = self.runtime.artifact_preview_lines(artifact)
            if preview_lines:
                lines.extend(["", "Предпросмотр:"])
                lines.extend(f"- {_operator_text(line)}" for line in preview_lines)
        if snapshot.validation_errors:
            lines.extend(["", "Ошибки проверки:"])
            lines.extend(f"- {_operator_text(item)}" for item in snapshot.validation_errors[:5])
        if snapshot.validation_warnings:
            lines.extend(["", "Предупреждения проверки:"])
            lines.extend(f"- {_operator_text(item)}" for item in snapshot.validation_warnings[:5])
        if snapshot.triage_red_flags:
            lines.extend(["", "Красные флаги разбора замечаний:"])
            lines.extend(f"- {_operator_text(item)}" for item in snapshot.triage_red_flags[:5])
        if snapshot.anim_summary_lines:
            lines.extend(["", "Сводка по последней визуализации:"])
            lines.extend(f"- {_operator_text(line)}" for line in snapshot.anim_summary_lines)
        if snapshot.operator_recommendations:
            lines.extend(["", "Рекомендуемые действия по ветвям:"])
            lines.extend(
                f"{idx}. {_operator_text(item)}"
                for idx, item in enumerate(snapshot.operator_recommendations, start=1)
            )

        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", "\n".join(lines))
        self.details.configure(state="disabled")

    def _on_select(self, _event=None) -> None:
        self._render_details()
        if self.snapshot_state is not None:
            self._refresh_action_states(self.snapshot_state)

    def _on_overview_select(self, _event=None) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        row = self._selected_overview_row()
        if row is not None:
            self._select_artifact(
                self.runtime.preferred_overview_evidence_artifact(
                    snapshot,
                    row,
                    handoff=self.session_handoff_state,
                )
            )
        self._render_details()
        self._refresh_action_states(snapshot)

    def _on_overview_open(self, _event=None) -> None:
        self._run_selected_overview_action()

    def _on_open_selected(self, _event=None) -> None:
        self._open_selected()

    def _open_selected(self) -> None:
        artifact = self._selected_artifact()
        if artifact is None:
            return
        self._run_action("open_artifact", artifact=artifact, success_message=f"Открыт материал: {artifact.title}")

    def _run_action(
        self,
        action_key: str,
        *,
        artifact: DesktopResultsArtifact | None = None,
        path: Path | None = None,
        success_message: str = "",
    ) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        try:
            action = str(action_key or "").strip()
            if action == "open_artifact":
                target_path = artifact.path if artifact is not None else path
                if target_path is None:
                    return
                _open_path(target_path)
            elif action == "open_compare_viewer":
                self.runtime.launch_compare_viewer(snapshot, artifact=artifact)
            elif action == "open_animator":
                self.runtime.launch_animator(snapshot, follow=False, artifact=artifact)
            elif action == "open_animator_follow":
                self.runtime.launch_animator(snapshot, follow=True, artifact=artifact)
            elif action == "open_diagnostics_gui":
                self.runtime.launch_full_diagnostics_gui()
            elif action == "open_send_center":
                self.runtime.write_diagnostics_evidence_manifest(
                    snapshot,
                    handoff=self.session_handoff_state,
                )
                self.runtime.launch_send_results_gui()
            elif action == "open_send_bundles":
                self.runtime.send_bundles_dir.mkdir(parents=True, exist_ok=True)
                _open_path(self.runtime.send_bundles_dir)
            elif action == "export_diagnostics_evidence":
                manifest_path = self.runtime.write_diagnostics_evidence_manifest(
                    snapshot,
                    handoff=self.session_handoff_state,
                )
                self.refresh()
                artifact = self.runtime.artifact_by_key(
                    self.snapshot_state or snapshot,
                    "diagnostics_evidence_manifest",
                )
                self._select_artifact(artifact)
                self.status_var.set(f"Материалы проверки проекта сохранены: {manifest_path}")
                return
            else:
                return
            message = success_message or f"Действие выполнено: {_action_label(action)}"
            self.status_var.set(_operator_text(message))
        except Exception as exc:
            messagebox.showerror("Результаты и анализ", f"Не удалось выполнить действие:\n{exc}")

    def _run_suggested_next_step(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        artifact = self.runtime.preferred_artifact_by_key(
            snapshot,
            snapshot.suggested_next_artifact_key,
            handoff=self.session_handoff_state,
        )
        self._run_action(
            snapshot.suggested_next_action_key,
            artifact=artifact,
            success_message="Рекомендованное действие запущено.",
        )

    def _run_selected_overview_action(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        row = self._selected_overview_row()
        if row is None:
            return
        artifact = self.runtime.preferred_overview_evidence_artifact(
            snapshot,
            row,
            handoff=self.session_handoff_state,
        )
        self._run_action(
            row.action_key,
            artifact=artifact,
            path=row.evidence_path,
            success_message=f"Действие по проверке запущено: {row.title}",
        )

    def _focus_suggested_branch(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        self._select_initial_overview(snapshot)
        self._render_details()
        self._refresh_action_states(snapshot)
        self.status_var.set("Показан рекомендованный раздел результатов.")

    def _open_handoff_zip(self) -> None:
        handoff = self.session_handoff_state
        if handoff is None or handoff.zip_path is None:
            return
        self._run_action(
            "open_artifact",
            path=handoff.zip_path,
            success_message=f"Открыт архив: {handoff.zip_path}",
        )

    def _open_handoff_validation(self) -> None:
        artifact = self._preferred_handoff_artifact("validation_json")
        if artifact is None:
            return
        self._run_action(
            "open_artifact",
            artifact=artifact,
            success_message="Открыта проверка текущего прогона.",
        )

    def _open_handoff_triage(self) -> None:
        artifact = self._preferred_handoff_artifact("triage_json")
        if artifact is None:
            return
        self._run_action(
            "open_artifact",
            artifact=artifact,
            success_message="Открыт разбор замечаний текущего прогона.",
        )

    def _branch_handoff_compare(self) -> None:
        artifact = self._preferred_handoff_artifact("latest_npz")
        if artifact is None:
            return
        self._run_action(
            "open_compare_viewer",
            artifact=artifact,
            success_message="Открыто сравнение текущего прогона.",
        )

    def _branch_handoff_animator(self) -> None:
        artifact = self._preferred_handoff_artifact("latest_pointer")
        if artifact is None:
            artifact = self._preferred_handoff_artifact("latest_npz")
        if artifact is None:
            return
        self._run_action(
            "open_animator_follow",
            artifact=artifact,
            success_message="Открыта анимация текущего прогона.",
        )

    def _open_handoff_autotest_run(self) -> None:
        handoff = self.session_handoff_state
        if handoff is None or handoff.autotest_run_dir is None:
            return
        self._run_action(
            "open_artifact",
            path=handoff.autotest_run_dir,
            success_message=f"Открыт каталог автотеста: {handoff.autotest_run_dir}",
        )

    def _open_handoff_diagnostics_run(self) -> None:
        handoff = self.session_handoff_state
        if handoff is None or handoff.diagnostics_run_dir is None:
            return
        self._run_action(
            "open_artifact",
            path=handoff.diagnostics_run_dir,
            success_message=f"Открыт каталог проверки проекта: {handoff.diagnostics_run_dir}",
        )

    def _open_send_bundles(self) -> None:
        self._run_action(
            "open_send_bundles",
            success_message=f"Открыта папка архивов: {self.runtime.send_bundles_dir}",
        )

    def _export_diagnostics_evidence(self) -> None:
        self._run_action(
            "export_diagnostics_evidence",
            success_message="Материалы проверки проекта сохранены.",
        )

    def _launch_compare_viewer(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        self._run_action(
            "open_compare_viewer",
            artifact=self._selected_artifact(),
            success_message="Открыто окно сравнения для результатов расчёта.",
        )

    def _launch_animator(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        self._run_action(
            "open_animator",
            artifact=self._selected_artifact(),
            success_message="Открыт аниматор для последних результатов расчёта.",
        )

    def _launch_animator_follow(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        self._run_action(
            "open_animator_follow",
            artifact=self._selected_artifact(),
            success_message="Открыта анимация результатов расчёта.",
        )

    def _launch_full_diagnostics_gui(self) -> None:
        self._run_action(
            "open_diagnostics_gui",
            success_message="Открыта проверка проекта.",
        )

    def _launch_send_results_gui(self) -> None:
        self._run_action(
            "open_send_center",
            success_message="Открыто копирование архива.",
        )


def main() -> int:
    root = tk.Tk()
    root.title(f"Результаты и анализ ({get_release()})")
    root.geometry("1460x960")
    root.minsize(1180, 760)
    runtime = DesktopResultsRuntime(
        repo_root=Path(__file__).resolve().parents[2],
        python_executable=sys.executable,
    )
    frame = DesktopResultsCenter(root, runtime=runtime)
    frame.pack(fill="both", expand=True)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DesktopResultsCenter", "main"]
