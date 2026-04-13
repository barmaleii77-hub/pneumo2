from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pneumo_solver_ui.desktop_optimizer_panels import HandoffTreePanel, TextReportPanel
from pneumo_solver_ui.optimization_workspace_history_ui import HANDOFF_SORT_OPTIONS


class DesktopOptimizerHandoffTab(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: object) -> None:
        super().__init__(master)
        self.controller = controller
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.handoff_panel = HandoffTreePanel(self, on_select=controller.on_handoff_selection_changed)
        self.handoff_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        actions = ttk.Frame(right)
        actions.grid(row=0, column=0, sticky="ew")
        ttk.Button(actions, text="Обновить handoff", command=controller.refresh_handoff).pack(side="left")
        ttk.Button(actions, text="Открыть run dir", command=controller.open_selected_run_dir).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Handoff plan", command=controller.open_selected_handoff_plan).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Apply contract", command=controller.apply_selected_run_contract).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Make latest pointer", command=controller.make_selected_run_latest_pointer).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Start handoff", command=controller.start_selected_handoff).pack(side="left", padx=(8, 0))

        filters = ttk.LabelFrame(right, text="Handoff candidate filters", padding=8)
        filters.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(filters, text="Ranking").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            filters,
            textvariable=controller.var("opt_handoff_sort_mode"),
            values=list(HANDOFF_SORT_OPTIONS),
            state="readonly",
            width=28,
        ).grid(row=0, column=1, sticky="w", padx=(8, 12))
        ttk.Label(filters, text="Min seeds").grid(row=0, column=2, sticky="w")
        ttk.Entry(
            filters,
            textvariable=controller.var("opt_handoff_min_seeds"),
            width=8,
        ).grid(row=0, column=3, sticky="w", padx=(8, 12))
        ttk.Checkbutton(
            filters,
            text="Full ring only",
            variable=controller.var("opt_handoff_full_ring_only"),
            command=controller.refresh_handoff,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            filters,
            text="DONE only",
            variable=controller.var("opt_handoff_done_only"),
            command=controller.refresh_handoff,
        ).grid(row=1, column=2, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(
            filters,
            text="Apply handoff filters",
            command=controller.refresh_handoff,
        ).grid(row=0, column=4, rowspan=2, sticky="e")

        self.overview_panel = TextReportPanel(right, text="Handoff overview", height=8)
        self.overview_panel.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.ranking_panel = TextReportPanel(right, text="Continuation ranking", height=10)
        self.ranking_panel.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.selected_panel = TextReportPanel(right, text="Selected handoff candidate", height=10)
        self.selected_panel.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.runtime_panel = TextReportPanel(right, text="Live handoff runtime", height=8)
        self.runtime_panel.grid(row=5, column=0, sticky="ew", pady=(10, 0))

    def set_handoff_rows(self, rows: list[dict[str, str]], *, selected_key: str = "") -> None:
        self.handoff_panel.set_rows(rows, selected_key=selected_key)

    def selected_run_dir(self) -> str:
        return self.handoff_panel.selected_key()

    def render_details(
        self,
        *,
        overview_text: str,
        ranking_text: str,
        selected_text: str,
        runtime_text: str,
    ) -> None:
        self.overview_panel.set_text(overview_text)
        self.ranking_panel.set_text(ranking_text)
        self.selected_panel.set_text(selected_text)
        self.runtime_panel.set_text(runtime_text)


__all__ = ["DesktopOptimizerHandoffTab"]
