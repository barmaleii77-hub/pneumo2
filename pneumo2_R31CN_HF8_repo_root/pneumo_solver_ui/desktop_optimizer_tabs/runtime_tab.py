from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pneumo_solver_ui.desktop_optimizer_model import (
    DASK_LOCAL_MODE,
    RAY_LOCAL_MODE,
    launch_profile_label,
)
from pneumo_solver_ui.desktop_optimizer_panels import ScrollableFrame, TextReportPanel


class DesktopOptimizerRuntimeTab(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: object) -> None:
        super().__init__(master)
        self.controller = controller
        self.scrollable = ScrollableFrame(self)
        self.scrollable.pack(fill="both", expand=True)
        body = self.scrollable.body

        ttk.Label(
            body,
            text="Optimization runtime",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text=(
                "Здесь видны active mode, baseline/runtime contract, stage policy, distributed knobs, live log и запуск StageRunner / coordinator без WEB."
            ),
            wraplength=980,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 10))

        self.profile_var = tk.StringVar(
            value=launch_profile_label(str(controller.var("opt_launch_profile").get() or ""))
        )
        self.mode_var = tk.StringVar(
            value="staged" if bool(controller.var("opt_use_staged").get()) else "distributed"
        )
        profile_frame = ttk.LabelFrame(body, text="Профили запуска", padding=10)
        profile_frame.grid(row=2, column=0, sticky="ew")
        profile_frame.columnconfigure(1, weight=1)
        ttk.Label(profile_frame, text="Готовый профиль").grid(row=0, column=0, sticky="w")
        self.profile_combo = ttk.Combobox(
            profile_frame,
            textvariable=self.profile_var,
            values=list(controller.profile_labels_for_active_mode()),
            state="readonly",
            width=34,
        )
        self.profile_combo.grid(row=0, column=1, sticky="ew", padx=(8, 12))
        ttk.Button(
            profile_frame,
            text="Применить профиль",
            command=lambda: controller.apply_launch_profile_label(self.selected_profile_label()),
        ).grid(row=0, column=2, sticky="e")
        ttk.Label(
            profile_frame,
            text=(
                "Profiles быстро перенастраивают runtime knobs, но список ограничен только активным режимом запуска."
            ),
            foreground="#555555",
            wraplength=920,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        self.profile_panel = TextReportPanel(body, text="Пояснение по профилю", height=7)
        self.profile_panel.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        self.readiness_panel = TextReportPanel(body, text="Готовность к запуску", height=10)
        self.readiness_panel.grid(row=4, column=0, sticky="ew", pady=(10, 0))

        self.contract_panel = TextReportPanel(
            body,
            text="Baseline, objective stack и hard gate",
            height=7,
        )
        self.contract_panel.grid(row=5, column=0, sticky="ew", pady=(10, 0))

        mode_frame = ttk.LabelFrame(body, text="Режим запуска", padding=10)
        mode_frame.grid(row=6, column=0, sticky="ew")
        ttk.Radiobutton(
            mode_frame,
            text="Рекомендуемый: Поэтапный запуск",
            variable=self.mode_var,
            value="staged",
            command=lambda: controller.set_active_mode(self.mode_var.get()),
        ).pack(side="left")
        ttk.Radiobutton(
            mode_frame,
            text="Расширенный: Распределённая координация",
            variable=self.mode_var,
            value="distributed",
            command=lambda: controller.set_active_mode(self.mode_var.get()),
        ).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(
            mode_frame,
            text="Продолжить стадии",
            variable=controller.var("opt_stage_resume"),
        ).pack(side="left", padx=(18, 0))
        ttk.Checkbutton(
            mode_frame,
            text="Продолжить координатор",
            variable=controller.var("opt_resume"),
        ).pack(side="left", padx=(12, 0))
        ttk.Label(
            mode_frame,
            text="На экране видны только relevant controls выбранного режима.",
            foreground="#555555",
        ).pack(side="left", padx=(18, 0))

        staged_frame = ttk.LabelFrame(body, text="Параметры поэтапного запуска", padding=10)
        staged_frame.grid(row=7, column=0, sticky="ew", pady=(10, 0))
        for col in range(6):
            staged_frame.columnconfigure(col, weight=1)
        self._add_entry(staged_frame, row=0, col=0, label="Бюджет, мин", var_name="ui_opt_minutes")
        self._add_entry(staged_frame, row=0, col=2, label="Задач", var_name="ui_jobs")
        self._add_entry(staged_frame, row=0, col=4, label="Seed candidates", var_name="ui_seed_candidates")
        self._add_entry(staged_frame, row=1, col=0, label="Seed conditions", var_name="ui_seed_conditions")
        self._add_entry(staged_frame, row=1, col=2, label="Influence eps", var_name="influence_eps_rel")
        self._add_entry(staged_frame, row=1, col=4, label="Warmstart", var_name="warmstart_mode")
        self._add_entry(staged_frame, row=2, col=0, label="Surrogate samples", var_name="surrogate_samples")
        self._add_entry(staged_frame, row=2, col=2, label="Surrogate top-k", var_name="surrogate_top_k")
        self._add_entry(staged_frame, row=2, col=4, label="Stage policy", var_name="stage_policy_mode")
        self._add_entry(staged_frame, row=3, col=0, label="Hard gate s1", var_name="stop_pen_stage1")
        self._add_entry(staged_frame, row=3, col=2, label="Hard gate s2", var_name="stop_pen_stage2")
        ttk.Checkbutton(
            staged_frame,
            text="Adaptive influence eps",
            variable=controller.var("adaptive_influence_eps"),
        ).grid(row=3, column=4, columnspan=2, sticky="w")
        ttk.Checkbutton(
            staged_frame,
            text="Автообновлять baseline",
            variable=controller.var("opt_autoupdate_baseline"),
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Checkbutton(
            staged_frame,
            text="Sort tests by cost",
            variable=controller.var("sort_tests_by_cost"),
        ).grid(row=4, column=2, columnspan=2, sticky="w", pady=(6, 0))

        dist_frame = ttk.LabelFrame(body, text="Параметры распределённой координации", padding=10)
        dist_frame.grid(row=8, column=0, sticky="ew", pady=(10, 0))
        for col in range(6):
            dist_frame.columnconfigure(col, weight=1)
        self._add_entry(dist_frame, row=0, col=0, label="Backend", var_name="opt_backend")
        self._add_entry(dist_frame, row=0, col=2, label="Budget", var_name="opt_budget")
        self._add_entry(dist_frame, row=0, col=4, label="Seed", var_name="opt_seed")
        self._add_entry(dist_frame, row=1, col=0, label="Max inflight", var_name="opt_max_inflight")
        self._add_entry(dist_frame, row=1, col=2, label="Proposer", var_name="opt_proposer")
        self._add_entry(dist_frame, row=1, col=4, label="q", var_name="opt_q")
        self._add_entry(dist_frame, row=2, col=0, label="Device", var_name="opt_device")
        self._add_entry(dist_frame, row=2, col=2, label="DB engine", var_name="opt_db_engine")
        self._add_entry(dist_frame, row=2, col=4, label="DB path", var_name="opt_db_path")
        self._add_entry(dist_frame, row=3, col=0, label="Export every", var_name="opt_export_every")
        self._add_entry(dist_frame, row=3, col=2, label="Dask mode", var_name="dask_mode")
        self._add_entry(dist_frame, row=3, col=4, label="Ray mode", var_name="ray_mode")
        self._add_entry(dist_frame, row=4, col=0, label="Dask workers", var_name="dask_workers")
        self._add_entry(dist_frame, row=4, col=2, label="Dask threads", var_name="dask_threads_per_worker")
        self._add_entry(dist_frame, row=4, col=4, label="Dask dashboard", var_name="dask_dashboard_address")
        self._add_entry(dist_frame, row=5, col=0, label="Ray address", var_name="ray_address")
        self._add_entry(dist_frame, row=5, col=2, label="Ray evaluators", var_name="ray_num_evaluators")
        self._add_entry(dist_frame, row=5, col=4, label="Ray proposers", var_name="ray_num_proposers")
        self._add_entry(dist_frame, row=6, col=0, label="CPUs / evaluator", var_name="ray_cpus_per_evaluator")
        self._add_entry(dist_frame, row=6, col=2, label="GPUs / proposer", var_name="ray_gpus_per_proposer")
        self._add_entry(dist_frame, row=6, col=4, label="Buffer", var_name="proposer_buffer")
        ttk.Checkbutton(
            dist_frame,
            text="Журнал гиперобъёма",
            variable=controller.var("opt_hv_log"),
        ).grid(row=7, column=0, sticky="w", pady=(6, 0))
        ttk.Checkbutton(
            dist_frame,
            text="Нормализовать цели BoTorch",
            variable=controller.var("opt_botorch_normalize_objectives"),
        ).grid(row=7, column=2, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(
            dist_frame,
            text=f"Dask local mode: {DASK_LOCAL_MODE} | Ray local mode: {RAY_LOCAL_MODE}",
            foreground="#555555",
        ).grid(row=7, column=4, columnspan=2, sticky="e", pady=(6, 0))

        botorch_frame = ttk.LabelFrame(body, text="BoTorch: дополнительные параметры", padding=10)
        botorch_frame.grid(row=9, column=0, sticky="ew", pady=(10, 0))
        for col in range(6):
            botorch_frame.columnconfigure(col, weight=1)
        self._add_entry(botorch_frame, row=0, col=0, label="n-init", var_name="opt_botorch_n_init")
        self._add_entry(botorch_frame, row=0, col=2, label="min feasible", var_name="opt_botorch_min_feasible")
        self._add_entry(botorch_frame, row=0, col=4, label="restarts", var_name="opt_botorch_num_restarts")
        self._add_entry(botorch_frame, row=1, col=0, label="raw samples", var_name="opt_botorch_raw_samples")
        self._add_entry(botorch_frame, row=1, col=2, label="maxiter", var_name="opt_botorch_maxiter")
        self._add_entry(botorch_frame, row=1, col=4, label="ref margin", var_name="opt_botorch_ref_margin")

        launch_frame = ttk.LabelFrame(body, text="Команды запуска", padding=10)
        launch_frame.grid(row=10, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(launch_frame, text="Обновить preview", command=controller.refresh_all).pack(side="left")
        ttk.Button(
            launch_frame,
            text="Следующий рекомендуемый шаг",
            command=controller.follow_launch_readiness_next_action,
        ).pack(side="left", padx=(8, 0))
        self.launch_button = ttk.Button(
            launch_frame,
            textvariable=controller.launch_button_text_var,
            command=controller.launch_job,
        )
        self.launch_button.pack(side="left", padx=(8, 0))
        ttk.Button(launch_frame, text="Мягкая остановка", command=controller.soft_stop_job).pack(side="left", padx=(8, 0))
        ttk.Button(launch_frame, text="Жёсткая остановка", command=controller.hard_stop_job).pack(side="left", padx=(8, 0))
        ttk.Button(launch_frame, text="Очистить статус", command=controller.clear_job_status).pack(side="left", padx=(8, 0))

        self.resume_panel = TextReportPanel(body, text="Источник продолжения", height=6)
        self.resume_panel.grid(row=11, column=0, sticky="ew", pady=(10, 0))
        self.status_panel = TextReportPanel(body, text="Текущее состояние", height=8)
        self.status_panel.grid(row=12, column=0, sticky="ew", pady=(10, 0))
        self.stage_runtime_panel = TextReportPanel(body, text="Ход стадий", height=8)
        self.stage_runtime_panel.grid(row=13, column=0, sticky="ew", pady=(10, 0))
        self.command_panel = TextReportPanel(body, text="Предпросмотр команды", height=8, wrap="none")
        self.command_panel.grid(row=14, column=0, sticky="ew", pady=(10, 0))
        self.log_panel = TextReportPanel(body, text="Последние строки журнала", height=14, wrap="none")
        self.log_panel.grid(row=15, column=0, sticky="ew", pady=(10, 0))

    def _add_entry(
        self,
        parent: tk.Misc,
        *,
        row: int,
        col: int,
        label: str,
        var_name: str,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", pady=3, padx=(0, 6))
        ttk.Entry(parent, textvariable=self.controller.var(var_name)).grid(
            row=row,
            column=col + 1,
            sticky="ew",
            pady=3,
            padx=(0, 12),
        )

    def selected_profile_label(self) -> str:
        return str(self.profile_var.get() or "").strip()

    def render(
        self,
        *,
        profile_key: str,
        profile_text: str,
        readiness_text: str,
        contract_text: str,
        preview_text: str,
        resume_text: str,
        status_text: str,
        stage_policy_text: str,
        log_text: str,
    ) -> None:
        self.mode_var.set("staged" if self.controller._active_mode_key() == "staged" else "distributed")
        self.profile_var.set(launch_profile_label(profile_key))
        self.profile_panel.set_text(profile_text)
        self.readiness_panel.set_text(readiness_text)
        self.contract_panel.set_text(contract_text)
        allowed_profiles = self.controller.profile_labels_for_active_mode()
        if allowed_profiles:
            self.profile_combo.configure(values=list(allowed_profiles))
            if self.profile_var.get() not in allowed_profiles:
                self.profile_var.set(allowed_profiles[0])
        self.command_panel.set_text(preview_text)
        self.resume_panel.set_text(resume_text)
        self.status_panel.set_text(status_text)
        self.stage_runtime_panel.set_text(stage_policy_text)
        self.log_panel.set_text(log_text)


__all__ = ["DesktopOptimizerRuntimeTab"]
