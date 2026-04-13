from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pneumo_solver_ui.desktop_optimizer_panels import HistoryTreePanel, TextReportPanel
from pneumo_solver_ui.optimization_workspace_history_ui import HANDOFF_SORT_OPTIONS


class DesktopOptimizerHistoryTab(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: object) -> None:
        super().__init__(master)
        self.controller = controller
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.history_panel = HistoryTreePanel(self, on_select=controller.on_history_selection_changed)
        self.history_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        actions = ttk.Frame(right)
        actions.grid(row=0, column=0, sticky="ew")
        ttk.Button(actions, text="Обновить историю", command=controller.refresh_history).pack(side="left")
        ttk.Button(actions, text="Открыть каталог прогона", command=controller.open_selected_run_dir).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Открыть лог", command=controller.open_selected_log).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Открыть результаты", command=controller.open_selected_results).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Контракт целей", command=controller.open_selected_objective_contract).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Применить контракт", command=controller.apply_selected_run_contract).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Сделать текущим указателем", command=controller.make_selected_run_latest_pointer).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="План передачи", command=controller.open_selected_handoff_plan).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Начать передачу", command=controller.start_selected_handoff).pack(side="left", padx=(8, 0))

        handoff_filters = ttk.LabelFrame(right, text="Фильтры передачи", padding=8)
        handoff_filters.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(handoff_filters, text="Ранжирование").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            handoff_filters,
            textvariable=controller.var("opt_handoff_sort_mode"),
            values=list(HANDOFF_SORT_OPTIONS),
            state="readonly",
            width=28,
        ).grid(row=0, column=1, sticky="w", padx=(8, 12))
        ttk.Label(handoff_filters, text="Минимум зёрен").grid(row=0, column=2, sticky="w")
        ttk.Entry(
            handoff_filters,
            textvariable=controller.var("opt_handoff_min_seeds"),
            width=8,
        ).grid(row=0, column=3, sticky="w", padx=(8, 12))
        ttk.Checkbutton(
            handoff_filters,
            text="Только полное кольцо",
            variable=controller.var("opt_handoff_full_ring_only"),
            command=controller.refresh_history,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            handoff_filters,
            text="Только завершённые",
            variable=controller.var("opt_handoff_done_only"),
            command=controller.refresh_history,
        ).grid(row=1, column=2, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(
            handoff_filters,
            text="Применить фильтры",
            command=controller.refresh_history,
        ).grid(row=0, column=4, rowspan=2, sticky="e")

        self.handoff_panel = TextReportPanel(right, text="Сводка по передаче", height=8)
        self.handoff_panel.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.summary_panel = TextReportPanel(right, text="Сводка по выбранному прогону", height=8)
        self.summary_panel.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.contract_panel = TextReportPanel(right, text="Контракт целей и области", height=8)
        self.contract_panel.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.packaging_panel = TextReportPanel(right, text="Выпуск и готовность", height=7)
        self.packaging_panel.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        self.stage_policy_panel = TextReportPanel(right, text="Стадии и передача", height=10)
        self.stage_policy_panel.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        self.log_panel = TextReportPanel(right, text="Последние строки журнала", height=12, wrap="none")
        self.log_panel.grid(row=7, column=0, sticky="ew", pady=(10, 0))

    def set_history_rows(self, rows: list[dict[str, str]], *, selected_key: str = "") -> None:
        self.history_panel.set_rows(rows, selected_key=selected_key)

    def selected_run_dir(self) -> str:
        return self.history_panel.selected_key()

    def render_details(
        self,
        *,
        handoff_text: str,
        summary_text: str,
        contract_text: str,
        packaging_text: str,
        stage_policy_text: str,
        log_text: str,
    ) -> None:
        self.handoff_panel.set_text(handoff_text)
        self.summary_panel.set_text(summary_text)
        self.contract_panel.set_text(contract_text)
        self.packaging_panel.set_text(packaging_text)
        self.stage_policy_panel.set_text(stage_policy_text)
        self.log_panel.set_text(log_text)


__all__ = ["DesktopOptimizerHistoryTab"]
