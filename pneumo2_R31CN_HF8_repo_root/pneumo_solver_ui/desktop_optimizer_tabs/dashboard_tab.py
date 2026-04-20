from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pneumo_solver_ui.desktop_optimizer_panels import ScrollableFrame, TextReportPanel


class DesktopOptimizerDashboardTab(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: object) -> None:
        super().__init__(master)
        self.controller = controller
        self.scrollable = ScrollableFrame(self)
        self.scrollable.pack(fill="both", expand=True)
        body = self.scrollable.body

        ttk.Label(
            body,
            text="Обзор автоматизированной оптимизации",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text=(
                "Единая сводка для оператора: какие параметры оптимизируются, где заданы диапазоны поиска, "
                "какая цель выбрана, что выполняется сейчас и какой прогон готов к передаче."
            ),
            wraplength=980,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 10))

        actions = ttk.LabelFrame(body, text="Быстрые переходы", padding=10)
        actions.grid(row=2, column=0, sticky="ew")
        ttk.Button(actions, text="Обновить всё", command=controller.refresh_all).pack(side="left")
        ttk.Button(actions, text="Следующий шаг готовности", command=controller.follow_launch_readiness_next_action).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Перейти по рекомендации", command=controller.follow_selected_run_next_step).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Текущий прогон анализа", command=controller.open_latest_optimization_pointer).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Рабочая папка", command=lambda: controller.open_current_artifact("workspace_dir")).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Параметры оптимизации", command=controller.show_contract_tab).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Выполнение", command=controller.show_runtime_tab).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="История", command=controller.show_history_tab).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Готовые прогоны", command=controller.show_finished_tab).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Передача", command=controller.show_handoff_tab).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Выпуск", command=controller.show_packaging_tab).pack(side="left", padx=(8, 0))

        self.workspace_panel = TextReportPanel(body, text="Состояние рабочей области", height=8)
        self.workspace_panel.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.runtime_panel = TextReportPanel(body, text="Активное выполнение", height=8)
        self.runtime_panel.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.readiness_panel = TextReportPanel(body, text="Готовность к запуску", height=10)
        self.readiness_panel.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        self.pointer_panel = TextReportPanel(body, text="Текущий прогон для анализа", height=8)
        self.pointer_panel.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        self.finished_panel = TextReportPanel(body, text="Готовность завершённых прогонов", height=8)
        self.finished_panel.grid(row=7, column=0, sticky="ew", pady=(10, 0))
        self.handoff_panel = TextReportPanel(body, text="Лучший кандидат на передачу", height=8)
        self.handoff_panel.grid(row=8, column=0, sticky="ew", pady=(10, 0))
        self.packaging_panel = TextReportPanel(body, text="Лучший прогон для выпуска", height=8)
        self.packaging_panel.grid(row=9, column=0, sticky="ew", pady=(10, 0))
        self.selection_panel = TextReportPanel(body, text="Выбранный прогон", height=8)
        self.selection_panel.grid(row=10, column=0, sticky="ew", pady=(10, 0))
        self.next_step_panel = TextReportPanel(body, text="Рекомендация по выбранному прогону", height=10)
        self.next_step_panel.grid(row=11, column=0, sticky="ew", pady=(10, 0))

    def render(
        self,
        *,
        workspace_text: str,
        runtime_text: str,
        readiness_text: str,
        pointer_text: str,
        finished_text: str,
        handoff_text: str,
        packaging_text: str,
        selection_text: str,
        next_step_text: str,
    ) -> None:
        self.workspace_panel.set_text(workspace_text)
        self.runtime_panel.set_text(runtime_text)
        self.readiness_panel.set_text(readiness_text)
        self.pointer_panel.set_text(pointer_text)
        self.finished_panel.set_text(finished_text)
        self.handoff_panel.set_text(handoff_text)
        self.packaging_panel.set_text(packaging_text)
        self.selection_panel.set_text(selection_text)
        self.next_step_panel.set_text(next_step_text)


__all__ = ["DesktopOptimizerDashboardTab"]
