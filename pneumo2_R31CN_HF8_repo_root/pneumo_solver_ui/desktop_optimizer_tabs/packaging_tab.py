from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pneumo_solver_ui.desktop_optimizer_model import PACKAGING_SORT_OPTIONS
from pneumo_solver_ui.desktop_optimizer_panels import PackagingTreePanel, TextReportPanel


class DesktopOptimizerPackagingTab(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: object) -> None:
        super().__init__(master)
        self.controller = controller
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.packaging_panel = PackagingTreePanel(self, on_select=controller.on_packaging_selection_changed)
        self.packaging_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        actions = ttk.Frame(right)
        actions.grid(row=0, column=0, sticky="ew")
        ttk.Button(actions, text="Обновить выпуск", command=controller.refresh_packaging).pack(side="left")
        ttk.Button(actions, text="Открыть папку прогона", command=controller.open_selected_run_dir).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Открыть результаты", command=controller.open_selected_results).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Открыть журнал", command=controller.open_selected_log).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Паспорт целей", command=controller.open_selected_objective_contract).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Передать в анализ", command=controller.make_selected_run_latest_pointer).pack(side="left", padx=(8, 0))

        filters = ttk.LabelFrame(right, text="Фильтры выпуска", padding=8)
        filters.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(filters, text="Ранжирование").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            filters,
            textvariable=controller.var("opt_packaging_sort_mode"),
            values=list(PACKAGING_SORT_OPTIONS),
            state="readonly",
            width=26,
        ).grid(row=0, column=1, sticky="w", padx=(8, 12))
        ttk.Checkbutton(
            filters,
            text="Только завершённые",
            variable=controller.var("opt_packaging_done_only"),
            command=controller.refresh_packaging,
        ).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(
            filters,
            text="Только готовые",
            variable=controller.var("opt_packaging_truth_ready_only"),
            command=controller.refresh_packaging,
        ).grid(row=0, column=3, sticky="w", padx=(12, 0))
        ttk.Checkbutton(
            filters,
            text="Только с проверкой",
            variable=controller.var("opt_packaging_verification_only"),
            command=controller.refresh_packaging,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            filters,
            text="Только без пересечений",
            variable=controller.var("opt_packaging_zero_interference_only"),
            command=controller.refresh_packaging,
        ).grid(row=1, column=1, columnspan=2, sticky="w", pady=(8, 0), padx=(8, 0))
        ttk.Button(
            filters,
            text="Применить фильтры",
            command=controller.refresh_packaging,
        ).grid(row=0, column=4, rowspan=2, sticky="e", padx=(16, 0))

        self.overview_panel = TextReportPanel(right, text="Сводка по выпуску", height=8)
        self.overview_panel.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.ranking_panel = TextReportPanel(right, text="Ранжирование по готовности", height=10)
        self.ranking_panel.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.snapshot_panel = TextReportPanel(right, text="Снимок выпуска выбранного прогона", height=10)
        self.snapshot_panel.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.contract_panel = TextReportPanel(right, text="Паспорт выпуска выбранного прогона", height=9)
        self.contract_panel.grid(row=5, column=0, sticky="ew", pady=(10, 0))

    def set_packaging_rows(self, rows: list[dict[str, str]], *, selected_key: str = "") -> None:
        self.packaging_panel.set_rows(rows, selected_key=selected_key)

    def selected_run_dir(self) -> str:
        return self.packaging_panel.selected_key()

    def render_details(
        self,
        *,
        overview_text: str,
        ranking_text: str,
        snapshot_text: str,
        contract_text: str,
    ) -> None:
        self.overview_panel.set_text(overview_text)
        self.ranking_panel.set_text(ranking_text)
        self.snapshot_panel.set_text(snapshot_text)
        self.contract_panel.set_text(contract_text)


__all__ = ["DesktopOptimizerPackagingTab"]
