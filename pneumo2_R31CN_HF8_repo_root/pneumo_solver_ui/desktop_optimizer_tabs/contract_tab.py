from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pneumo_solver_ui.desktop_optimizer_panels import (
    KeyValueGridPanel,
    ScrollableFrame,
    TextReportPanel,
    replace_text,
)
from pneumo_solver_ui.optimization_contract_summary_ui import format_hard_gate


class DesktopOptimizerContractTab(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: object) -> None:
        super().__init__(master)
        self.controller = controller
        self.scrollable = ScrollableFrame(self)
        self.scrollable.pack(fill="both", expand=True)
        body = self.scrollable.body

        ttk.Label(
            body,
            text="Baseline и контракт запуска",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text=(
                "Desktop center показывает честный scope текущего контракта запуска: "
                "baseline source-of-truth, objective stack, hard gate, canonical model/base/ranges/suite и problem hash."
            ),
            wraplength=980,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 10))

        self.summary_panel = KeyValueGridPanel(body, text="Снимок области и пространства поиска")
        self.summary_panel.grid(row=2, column=0, sticky="ew")

        self.paths_panel = KeyValueGridPanel(body, text="Подготовленные артефакты")
        self.paths_panel.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        objective_frame = ttk.LabelFrame(body, text="Контракт целей", padding=10)
        objective_frame.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        objective_frame.columnconfigure(1, weight=1)
        objective_frame.columnconfigure(3, weight=1)

        ttk.Label(objective_frame, text="Цели оптимизации").grid(row=0, column=0, sticky="nw", padx=(0, 8))
        self.objective_text = tk.Text(objective_frame, height=5, wrap="word")
        self.objective_text.grid(row=0, column=1, columnspan=3, sticky="ew")

        ttk.Label(objective_frame, text="Ключ штрафа").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(
            objective_frame,
            textvariable=controller.var("opt_penalty_key"),
        ).grid(row=1, column=1, sticky="ew", pady=(8, 0))

        ttk.Label(objective_frame, text="Допуск штрафа").grid(row=1, column=2, sticky="w", padx=(12, 8), pady=(8, 0))
        ttk.Entry(
            objective_frame,
            textvariable=controller.var("opt_penalty_tol"),
            width=14,
        ).grid(row=1, column=3, sticky="w", pady=(8, 0))

        ttk.Label(objective_frame, text="Режим хэша задачи").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            objective_frame,
            textvariable=controller.var("settings_opt_problem_hash_mode"),
            values=("stable", "legacy"),
            state="readonly",
            width=18,
        ).grid(row=2, column=1, sticky="w", pady=(8, 0))

        actions = ttk.Frame(objective_frame)
        actions.grid(row=2, column=2, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(
            actions,
            text="Обновить snapshot",
            command=controller.refresh_all,
        ).pack(side="right")

        self.stage_policy_panel = TextReportPanel(
            body,
            text="План стадий",
            height=8,
        )
        self.stage_policy_panel.grid(row=5, column=0, sticky="ew", pady=(10, 0))

        self.drift_panel = TextReportPanel(
            body,
            text="Расхождение выбранного прогона с текущим запуском",
            height=10,
        )
        self.drift_panel.grid(row=6, column=0, sticky="ew", pady=(10, 0))

        selection_frame = ttk.LabelFrame(body, text="Действия по выбранному прогону", padding=10)
        selection_frame.grid(row=7, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(
            selection_frame,
            text="Применить контракт",
            command=controller.apply_selected_run_contract,
        ).pack(side="left")
        ttk.Button(
            selection_frame,
            text="Открыть контракт целей",
            command=controller.open_selected_objective_contract,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            selection_frame,
            text="История",
            command=controller.show_history_tab,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            selection_frame,
            text="Обзор",
            command=controller.show_dashboard_tab,
        ).pack(side="left", padx=(8, 0))

        open_frame = ttk.LabelFrame(body, text="Быстрые действия", padding=10)
        open_frame.grid(row=8, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(
            open_frame,
            text="Открыть base.json",
            command=lambda: controller.open_current_artifact("base_json_path"),
        ).pack(side="left")
        ttk.Button(
            open_frame,
            text="Открыть ranges.json",
            command=lambda: controller.open_current_artifact("ranges_json_path"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            open_frame,
            text="Открыть suite.json",
            command=lambda: controller.open_current_artifact("suite_json_path"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            open_frame,
            text="Открыть рабочую область",
            command=lambda: controller.open_current_artifact("workspace_dir"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            open_frame,
            text="Открыть Baseline Center",
            command=controller.open_baseline_center,
        ).pack(side="left", padx=(8, 0))

    def set_objectives_text(self, text: str) -> None:
        replace_text(self.objective_text, text)

    def objectives_text(self) -> str:
        return self.objective_text.get("1.0", "end").strip()

    def render(
        self,
        *,
        snapshot: object,
        stage_policy_text: str,
        drift_text: str,
    ) -> None:
        stage_counts = ", ".join(
            f"{key}={value}" for key, value in dict(getattr(snapshot, "enabled_stage_counts", {}) or {}).items()
        ) or "нет enabled stages"
        sample_params = ", ".join(tuple(getattr(snapshot, "sample_search_params", ()) or ())) or "—"
        self.summary_panel.set_rows(
            [
                ("Рабочая область", str(getattr(snapshot, "workspace_dir", ""))),
                ("Objective stack", ", ".join(tuple(getattr(snapshot, "objective_keys", ()) or ())) or "—"),
                (
                    "Hard gate",
                    format_hard_gate(
                        getattr(snapshot, "penalty_key", ""),
                        getattr(snapshot, "penalty_tol", None),
                    )
                    or "—",
                ),
                ("Problem hash", str(getattr(snapshot, "problem_hash", "")) or "—"),
                ("Hash mode", str(getattr(snapshot, "problem_hash_mode", "")) or "—"),
                (
                    "Baseline source",
                    str(getattr(snapshot, "baseline_source_label", "")) or "default_base.json only",
                ),
                (
                    "HO-006 active baseline",
                    (
                        f"{str(getattr(snapshot, 'active_baseline_state', '') or 'missing')} / "
                        f"{'current' if bool(getattr(snapshot, 'optimizer_baseline_can_consume', False)) else 'blocked'}"
                    ),
                ),
                (
                    "active_baseline_hash",
                    str(getattr(snapshot, "active_baseline_hash", "") or "—")[:12],
                ),
                (
                    "Автообновление baseline",
                    "включено" if bool(self.controller.var("opt_autoupdate_baseline").get()) else "выключено",
                ),
                (
                    "Search-space",
                    f"base params={int(getattr(snapshot, 'base_param_count', 0) or 0)}, "
                    f"design params={int(getattr(snapshot, 'search_param_count', 0) or 0)}, "
                    f"removed runtime knobs={int(getattr(snapshot, 'removed_runtime_knob_count', 0) or 0)}, "
                    f"widened={int(getattr(snapshot, 'widened_range_count', 0) or 0)}",
                ),
                (
                    "Suite coverage",
                    f"rows={int(getattr(snapshot, 'suite_row_count', 0) or 0)}, "
                    f"enabled={int(getattr(snapshot, 'enabled_suite_total', 0) or 0)}, "
                    f"stages: {stage_counts}",
                ),
                ("Sample search params", sample_params),
            ]
        )
        self.paths_panel.set_rows(
            [
                ("Model", str(getattr(snapshot, "model_path", ""))),
                ("Worker", str(getattr(snapshot, "worker_path", ""))),
                ("Base JSON", str(getattr(snapshot, "base_json_path", ""))),
                ("Ranges JSON", str(getattr(snapshot, "ranges_json_path", ""))),
                ("Suite JSON", str(getattr(snapshot, "suite_json_path", ""))),
                (
                    "Stage tuner JSON",
                    str(getattr(snapshot, "stage_tuner_json_path", "") or "not materialized"),
                ),
                (
                    "Scoped baseline",
                    str(getattr(snapshot, "baseline_path", "") or "not found"),
                ),
                (
                    "HO-006 contract",
                    str(getattr(snapshot, "active_baseline_contract_path", "") or "not found"),
                ),
            ]
        )
        self.stage_policy_panel.set_text(stage_policy_text)
        self.drift_panel.set_text(drift_text)


__all__ = ["DesktopOptimizerContractTab"]
