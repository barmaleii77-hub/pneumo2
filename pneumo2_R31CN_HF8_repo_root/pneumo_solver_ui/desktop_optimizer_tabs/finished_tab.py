from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pneumo_solver_ui.desktop_optimizer_model import FINISHED_JOB_SORT_OPTIONS
from pneumo_solver_ui.desktop_optimizer_panels import FinishedJobsTreePanel, TextReportPanel


class DesktopOptimizerFinishedTab(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: object) -> None:
        super().__init__(master)
        self.controller = controller
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.finished_panel = FinishedJobsTreePanel(self, on_select=controller.on_finished_selection_changed)
        self.finished_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        actions = ttk.Frame(right)
        actions.grid(row=0, column=0, sticky="ew")
        ttk.Button(actions, text="Обновить finished jobs", command=controller.refresh_finished_jobs).pack(side="left")
        ttk.Button(actions, text="Открыть run dir", command=controller.open_selected_run_dir).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Открыть results", command=controller.open_selected_results).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Открыть лог", command=controller.open_selected_log).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Objective contract", command=controller.open_selected_objective_contract).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Make latest pointer", command=controller.make_selected_run_latest_pointer).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Handoff plan", command=controller.open_selected_handoff_plan).pack(side="left", padx=(8, 0))

        filters = ttk.LabelFrame(right, text="Finished jobs filters", padding=8)
        filters.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(filters, text="Ranking").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            filters,
            textvariable=controller.var("opt_finished_sort_mode"),
            values=list(FINISHED_JOB_SORT_OPTIONS),
            state="readonly",
            width=26,
        ).grid(row=0, column=1, sticky="w", padx=(8, 12))
        ttk.Checkbutton(
            filters,
            text="DONE only",
            variable=controller.var("opt_finished_done_only"),
            command=controller.refresh_finished_jobs,
        ).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(
            filters,
            text="Truth-ready only",
            variable=controller.var("opt_finished_truth_ready_only"),
            command=controller.refresh_finished_jobs,
        ).grid(row=0, column=3, sticky="w", padx=(12, 0))
        ttk.Checkbutton(
            filters,
            text="Verification only",
            variable=controller.var("opt_finished_verification_only"),
            command=controller.refresh_finished_jobs,
        ).grid(row=0, column=4, sticky="w", padx=(12, 0))
        ttk.Button(
            filters,
            text="Apply finished filters",
            command=controller.refresh_finished_jobs,
        ).grid(row=0, column=5, sticky="e", padx=(16, 0))

        self.overview_panel = TextReportPanel(right, text="Finished jobs overview", height=8)
        self.overview_panel.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.ranking_panel = TextReportPanel(right, text="Packaging ranking", height=10)
        self.ranking_panel.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.packaging_panel = TextReportPanel(right, text="Selected packaging snapshot", height=10)
        self.packaging_panel.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.summary_panel = TextReportPanel(right, text="Selected finished job", height=10)
        self.summary_panel.grid(row=5, column=0, sticky="ew", pady=(10, 0))

    def set_finished_rows(self, rows: list[dict[str, str]], *, selected_key: str = "") -> None:
        self.finished_panel.set_rows(rows, selected_key=selected_key)

    def selected_run_dir(self) -> str:
        return self.finished_panel.selected_key()

    def render_details(
        self,
        *,
        overview_text: str,
        ranking_text: str,
        packaging_text: str,
        summary_text: str,
    ) -> None:
        self.overview_panel.set_text(overview_text)
        self.ranking_panel.set_text(ranking_text)
        self.packaging_panel.set_text(packaging_text)
        self.summary_panel.set_text(summary_text)


__all__ = ["DesktopOptimizerFinishedTab"]
