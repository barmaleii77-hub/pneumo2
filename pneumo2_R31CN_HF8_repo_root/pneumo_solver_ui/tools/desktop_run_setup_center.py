from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from pneumo_solver_ui.desktop_input_model import (
    DESKTOP_PREVIEW_SURFACE_OPTIONS,
    DESKTOP_RUN_PRESET_OPTIONS,
)
from pneumo_solver_ui.desktop_ui_core import (
    ScrollableFrame,
    build_scrolled_treeview,
    build_status_strip,
    create_scrollable_tab,
)
from pneumo_solver_ui.desktop_run_setup_model import (
    DESKTOP_RUN_CACHE_POLICY_OPTIONS,
    DESKTOP_RUN_PROFILE_OPTIONS,
    DESKTOP_RUN_RUNTIME_POLICY_OPTIONS,
    describe_plain_launch_availability,
    describe_run_launch_target,
    recommended_run_launch_action,
)


class _ScrollableBody(ScrollableFrame):
    pass


class DesktopRunSetupCenter:
    def __init__(self, editor: Any) -> None:
        self.editor = editor
        self.window = tk.Toplevel(editor.root)
        self.window.title("Настройка расчёта")
        self.window.geometry("1180x860")
        self.window.minsize(1020, 760)
        self.window.resizable(True, True)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        self._host_closed = False
        self._trace_tokens: list[str] = []
        self._section_tab_ids: dict[str, str] = {}
        self._tab_hosts: dict[str, ScrollableFrame] = {}
        self._syncing_tree = False
        self.section_tree: ttk.Treeview | None = None
        self.notebook: ttk.Notebook | None = None
        self.launch_action_hint_var = tk.StringVar()
        self.launch_with_check_button: ttk.Button | None = None
        self.launch_plain_button: ttk.Button | None = None
        self.suite_lineage_var = tk.StringVar(
            value=(
                "Состояние набора испытаний появится после проверки. "
                "Геометрия колец используется только для чтения."
            )
        )
        self.suite_tree: ttk.Treeview | None = None

        self._build_ui()
        self._bind_live_refreshes()
        self.editor._refresh_preview_surface_controls()
        self.editor._refresh_run_scenario_controls()
        self.editor._refresh_run_profile_hint()

    def focus(self) -> None:
        try:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
        except Exception:
            return

    def _on_close(self) -> None:
        self._unbind_live_refreshes()
        self._clear_widget_handles()
        try:
            self.window.destroy()
        finally:
            self.editor._notify_run_setup_center_closed()

    def on_host_close(self) -> None:
        self._host_closed = True
        try:
            self._on_close()
        except Exception:
            return

    def _clear_widget_handles(self) -> None:
        self.editor.preview_surface_primary_spin = None
        self.editor.preview_surface_secondary_spin = None
        self.editor.preview_surface_start_spin = None
        self.editor.preview_surface_angle_spin = None
        self.editor.preview_surface_shape_spin = None
        self.editor.run_primary_spin = None
        self.editor.run_secondary_spin = None

    def _build_ui(self) -> None:
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        outer = ttk.Frame(self.window, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        self._build_workspace_ui(outer)
        self.editor._refresh_run_policy_hints()
        self._refresh_runtime_summaries()
        self._select_section("profile")
        return

        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Настройка расчёта",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Настройки расчёта вынесены в отдельное окно: здесь находятся краткий "
                "предпросмотр, подробные режимы, шаг по времени, длительность, "
                "повторное использование расчётов, выгрузка, самопроверка и запись журналов. "
                "Физические параметры остаются в основном редакторе и не смешиваются с подготовкой запуска."
            ),
            wraplength=920,
            justify="left",
        ).pack(anchor="w", pady=(6, 12))

        scrollable = _ScrollableBody(outer)
        scrollable.pack(fill="both", expand=True)
        body = scrollable.body
        body.columnconfigure(0, weight=1)

        profile_frame = ttk.LabelFrame(body, text="Профиль запуска", padding=10)
        profile_frame.grid(row=0, column=0, sticky="ew")
        for idx, (profile_key, profile_label, _profile_desc) in enumerate(DESKTOP_RUN_PROFILE_OPTIONS):
            ttk.Radiobutton(
                profile_frame,
                text=profile_label,
                value=profile_key,
                variable=self.editor.run_profile_var,
                command=lambda key=profile_key: self.editor._apply_run_setup_profile(key),
            ).grid(row=0, column=idx, sticky="w", padx=(0 if idx == 0 else 12, 0))
        ttk.Label(
            profile_frame,
            textvariable=self.editor.run_profile_hint_var,
            wraplength=880,
            justify="left",
            foreground="#555555",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

        preview_frame = ttk.LabelFrame(body, text="Профиль дороги для предпросмотра", padding=10)
        preview_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        preview_frame.columnconfigure(5, weight=1)

        ttk.Label(preview_frame, text="Тип профиля").grid(row=0, column=0, sticky="w")
        preview_combo = ttk.Combobox(
            preview_frame,
            textvariable=self.editor.preview_surface_var,
            values=[label for _key, label in DESKTOP_PREVIEW_SURFACE_OPTIONS],
            state="readonly",
            width=28,
        )
        preview_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))
        preview_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.editor._refresh_preview_surface_controls(),
        )
        ttk.Label(
            preview_frame,
            textvariable=self.editor.preview_surface_summary_var,
            foreground="#555555",
            wraplength=620,
            justify="left",
        ).grid(row=0, column=2, columnspan=4, sticky="w", padx=(16, 0))

        ttk.Label(
            preview_frame,
            text="Шаг предпросмотра, с",
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Spinbox(
            preview_frame,
            from_=0.001,
            to=0.1,
            increment=0.001,
            textvariable=self.editor.preview_dt_var,
            width=10,
            format="%.3f",
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(preview_frame, text="Длительность предпросмотра, с").grid(
            row=1, column=2, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        ttk.Spinbox(
            preview_frame,
            from_=0.2,
            to=60.0,
            increment=0.1,
            textvariable=self.editor.preview_t_end_var,
            width=10,
            format="%.1f",
        ).grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(preview_frame, text="Длина участка, м").grid(
            row=1, column=4, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        ttk.Spinbox(
            preview_frame,
            from_=5.0,
            to=5000.0,
            increment=1.0,
            textvariable=self.editor.preview_road_len_var,
            width=10,
            format="%.1f",
        ).grid(row=1, column=5, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(preview_frame, textvariable=self.editor.preview_surface_primary_label_var).grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )
        self.editor.preview_surface_primary_spin = ttk.Spinbox(
            preview_frame,
            from_=0.0,
            to=2.0,
            increment=0.005,
            textvariable=self.editor.preview_surface_primary_value_var,
            width=10,
            format="%.3f",
        )
        self.editor.preview_surface_primary_spin.grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0)
        )

        ttk.Label(preview_frame, textvariable=self.editor.preview_surface_secondary_label_var).grid(
            row=2, column=2, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        self.editor.preview_surface_secondary_spin = ttk.Spinbox(
            preview_frame,
            from_=0.01,
            to=50.0,
            increment=0.05,
            textvariable=self.editor.preview_surface_secondary_value_var,
            width=10,
            format="%.3f",
        )
        self.editor.preview_surface_secondary_spin.grid(
            row=2, column=3, sticky="w", padx=(8, 0), pady=(10, 0)
        )

        ttk.Label(preview_frame, text="Начало профиля, м").grid(
            row=2, column=4, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        self.editor.preview_surface_start_spin = ttk.Spinbox(
            preview_frame,
            from_=0.0,
            to=500.0,
            increment=0.1,
            textvariable=self.editor.preview_surface_start_var,
            width=10,
            format="%.2f",
        )
        self.editor.preview_surface_start_spin.grid(
            row=2, column=5, sticky="w", padx=(8, 0), pady=(10, 0)
        )

        ttk.Label(preview_frame, text="Угол гребня, град").grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.editor.preview_surface_angle_spin = ttk.Spinbox(
            preview_frame,
            from_=-90.0,
            to=90.0,
            increment=1.0,
            textvariable=self.editor.preview_surface_angle_var,
            width=10,
            format="%.1f",
        )
        self.editor.preview_surface_angle_spin.grid(
            row=3, column=1, sticky="w", padx=(8, 0), pady=(10, 0)
        )

        ttk.Label(preview_frame, text="Коэффициент формы").grid(
            row=3, column=2, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        self.editor.preview_surface_shape_spin = ttk.Spinbox(
            preview_frame,
            from_=0.1,
            to=10.0,
            increment=0.1,
            textvariable=self.editor.preview_surface_shape_var,
            width=10,
            format="%.2f",
        )
        self.editor.preview_surface_shape_spin.grid(
            row=3, column=3, sticky="w", padx=(8, 0), pady=(10, 0)
        )

        detail_frame = ttk.LabelFrame(body, text="Настройки запуска расчёта", padding=10)
        detail_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        detail_frame.columnconfigure(5, weight=1)

        ttk.Label(detail_frame, text="Сценарий").grid(row=0, column=0, sticky="w")
        run_combo = ttk.Combobox(
            detail_frame,
            textvariable=self.editor.run_scenario_var,
            values=list(self.editor.run_scenario_key_to_label.values()),
            state="readonly",
            width=30,
        )
        run_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))
        run_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.editor._refresh_run_scenario_controls(),
        )
        ttk.Label(
            detail_frame,
            textvariable=self.editor.run_summary_var,
            foreground="#555555",
            wraplength=720,
            justify="left",
        ).grid(row=0, column=2, columnspan=4, sticky="w", padx=(16, 0))

        ttk.Label(detail_frame, text="Шаг dt, с").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Spinbox(
            detail_frame,
            from_=0.001,
            to=0.1,
            increment=0.001,
            textvariable=self.editor.run_dt_var,
            width=10,
            format="%.3f",
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(detail_frame, text="Длительность, с").grid(
            row=1, column=2, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        ttk.Spinbox(
            detail_frame,
            from_=0.2,
            to=60.0,
            increment=0.1,
            textvariable=self.editor.run_t_end_var,
            width=10,
            format="%.1f",
        ).grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Checkbutton(
            detail_frame,
            text="Сохранять расширенный журнал давления и потоков",
            variable=self.editor.run_record_full_var,
        ).grid(row=1, column=4, columnspan=2, sticky="w", padx=(16, 0), pady=(10, 0))

        ttk.Label(detail_frame, textvariable=self.editor.run_primary_label_var).grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )
        self.editor.run_primary_spin = ttk.Spinbox(
            detail_frame,
            from_=0.0,
            to=50.0,
            increment=0.1,
            textvariable=self.editor.run_primary_value_var,
            width=10,
            format="%.3f",
        )
        self.editor.run_primary_spin.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(detail_frame, textvariable=self.editor.run_secondary_label_var).grid(
            row=2, column=2, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        self.editor.run_secondary_spin = ttk.Spinbox(
            detail_frame,
            from_=0.0,
            to=50.0,
            increment=0.1,
            textvariable=self.editor.run_secondary_value_var,
            width=10,
            format="%.3f",
        )
        self.editor.run_secondary_spin.grid(row=2, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        run_preset_frame = ttk.LabelFrame(detail_frame, text="Пресеты запуска", padding=10)
        run_preset_frame.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        for idx, (preset_key, preset_label_text, _preset_desc) in enumerate(DESKTOP_RUN_PRESET_OPTIONS):
            ttk.Button(
                run_preset_frame,
                text=preset_label_text,
                command=lambda key=preset_key: self.editor._apply_run_preset(key),
            ).grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 8, 0))
            run_preset_frame.columnconfigure(idx, weight=1)

        ttk.Label(
            run_preset_frame,
            textvariable=self.editor.run_mode_summary_var,
            foreground="#334455",
            wraplength=860,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(
            run_preset_frame,
            textvariable=self.editor.run_mode_cost_var,
            foreground="#6b4d00",
            wraplength=860,
            justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            run_preset_frame,
            textvariable=self.editor.run_mode_advice_var,
            foreground="#1f5d50",
            wraplength=860,
            justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            run_preset_frame,
            textvariable=self.editor.run_mode_usage_var,
            foreground="#355c7d",
            wraplength=860,
            justify="left",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            run_preset_frame,
            textvariable=self.editor.run_preset_hint_var,
            foreground="#555555",
            wraplength=860,
            justify="left",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

        runtime_frame = ttk.LabelFrame(body, text="Повторное использование, выгрузка и режим выполнения", padding=10)
        runtime_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        runtime_frame.columnconfigure(0, weight=1)
        runtime_frame.columnconfigure(1, weight=1)

        cache_frame = ttk.LabelFrame(runtime_frame, text="Повторное использование расчётов", padding=8)
        cache_frame.grid(row=0, column=0, sticky="nsew")
        for idx, (policy_key, policy_label, _policy_desc) in enumerate(DESKTOP_RUN_CACHE_POLICY_OPTIONS):
            ttk.Radiobutton(
                cache_frame,
                text=policy_label,
                value=policy_key,
                variable=self.editor.run_cache_policy_var,
            ).grid(row=idx, column=0, sticky="w")
        ttk.Label(
            cache_frame,
            textvariable=self.editor.run_cache_hint_var,
            wraplength=380,
            justify="left",
            foreground="#555555",
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))

        runtime_policy_frame = ttk.LabelFrame(runtime_frame, text="Режим выполнения", padding=8)
        runtime_policy_frame.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        for idx, (policy_key, policy_label, _policy_desc) in enumerate(DESKTOP_RUN_RUNTIME_POLICY_OPTIONS):
            ttk.Radiobutton(
                runtime_policy_frame,
                text=policy_label,
                value=policy_key,
                variable=self.editor.run_runtime_policy_var,
            ).grid(row=idx, column=0, sticky="w")
        ttk.Label(
            runtime_policy_frame,
            textvariable=self.editor.run_runtime_policy_hint_var,
            wraplength=380,
            justify="left",
            foreground="#555555",
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))

        flags_frame = ttk.Frame(runtime_frame)
        flags_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Checkbutton(
            flags_frame,
            text="Сохранять таблицы результатов для подробных режимов",
            variable=self.editor.run_export_csv_var,
        ).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(
            flags_frame,
            text="Сохранять файл анимации для подробных режимов",
            variable=self.editor.run_export_npz_var,
        ).grid(row=0, column=1, sticky="w", padx=(16, 0))
        ttk.Checkbutton(
            flags_frame,
            text="Запускать самопроверку перед расчётом",
            variable=self.editor.run_auto_check_var,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            flags_frame,
            text="Сохранять журнал процесса в файл",
            variable=self.editor.run_log_to_file_var,
        ).grid(row=1, column=1, sticky="w", padx=(16, 0), pady=(8, 0))
        ttk.Label(
            flags_frame,
            text=(
                "Повторное использование и выгрузка важны для подробных режимов. "
                "Краткий предпросмотр всегда пишет короткую сводку, а самопроверка и журнал доступны для всех режимов."
            ),
            wraplength=860,
            justify="left",
            foreground="#555555",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        summary_frame = ttk.LabelFrame(body, text="Будет запущено сейчас", padding=10)
        summary_frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(
            summary_frame,
            textvariable=self.editor.run_launch_summary_var,
            wraplength=880,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Button(
            summary_frame,
            text="Проверить конфигурацию",
            command=self.editor._run_config_check,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.launch_with_check_button = ttk.Button(
            summary_frame,
            text="Проверить и запустить",
            command=self._run_selected_profile_with_check,
        )
        self.launch_with_check_button.grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        self.launch_plain_button = ttk.Button(
            summary_frame,
            text="Запустить расчёт",
            command=self._run_selected_profile,
        )
        self.launch_plain_button.grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            summary_frame,
            text="Открыть папку запусков",
            command=self.editor._open_desktop_runs_dir,
        ).grid(row=1, column=3, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Label(
            summary_frame,
            textvariable=self.launch_action_hint_var,
            wraplength=880,
            justify="left",
            foreground="#1f5d50",
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))

        recent_frame = ttk.LabelFrame(body, text="Последние результаты и журналы", padding=10)
        recent_frame.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        recent_frame.columnconfigure(0, weight=1)
        recent_frame.columnconfigure(1, weight=1)

        preview_recent_frame = ttk.LabelFrame(
            recent_frame,
            text="Последний предпросмотр",
            padding=8,
        )
        preview_recent_frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(
            preview_recent_frame,
            textvariable=self.editor.latest_preview_summary_var,
            wraplength=400,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Button(
            preview_recent_frame,
            text="Обновить сводку",
            command=self.editor._refresh_latest_preview_summary,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            preview_recent_frame,
            text="Открыть сводку",
            command=self.editor._open_latest_preview_report_json,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            preview_recent_frame,
            text="Открыть журнал",
            command=self.editor._open_latest_preview_log,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))

        check_recent_frame = ttk.LabelFrame(
            recent_frame,
            text="Последняя самопроверка",
            padding=8,
        )
        check_recent_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(
            check_recent_frame,
            textvariable=self.editor.latest_selfcheck_summary_var,
            wraplength=840,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Button(
            check_recent_frame,
            text="Обновить сводку",
            command=self.editor._refresh_latest_selfcheck_summary,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            check_recent_frame,
            text="Открыть сводку",
            command=self.editor._open_latest_selfcheck_report_json,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            check_recent_frame,
            text="Открыть журнал",
            command=self.editor._open_latest_selfcheck_log,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))

        run_recent_frame = ttk.LabelFrame(
            recent_frame,
            text="Последний подробный расчёт",
            padding=8,
        )
        run_recent_frame.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        ttk.Label(
            run_recent_frame,
            textvariable=self.editor.latest_run_summary_var,
            wraplength=400,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Button(
            run_recent_frame,
            text="Обновить сводку",
            command=self.editor._refresh_latest_run_summary,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть сводку",
            command=self.editor._open_latest_run_summary_json,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть журнал",
            command=self.editor._open_latest_run_log,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть основную таблицу результатов",
            command=self.editor._open_latest_df_main_csv,
        ).grid(row=1, column=3, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть файл анимации",
            command=self.editor._open_latest_npz_bundle,
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть готовый результат",
            command=self.editor._open_latest_run_cache_dir,
        ).grid(row=2, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть папку запусков",
            command=self.editor._open_desktop_runs_dir,
        ).grid(row=2, column=2, sticky="w", padx=(12, 0), pady=(10, 0))

        support_frame = ttk.LabelFrame(body, text="Папки и журналы расчёта", padding=10)
        support_frame.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(
            support_frame,
            text=(
                "Данные расчёта и журналы лежат отдельно от физических профилей. "
                "Если нужно проверить повторное использование, ручную выгрузку или детальный журнал процесса, "
                "открывайте эти папки здесь."
            ),
            wraplength=880,
            justify="left",
            foreground="#555555",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Button(
            support_frame,
            text="Открыть папку готовых результатов",
            command=self.editor._open_run_setup_cache_root,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            support_frame,
            text="Открыть папку журналов",
            command=self.editor._open_run_setup_log_root,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            support_frame,
            text="Обновить все сводки",
            command=self._refresh_runtime_summaries,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))

        footer = build_status_strip(
            outer,
            primary_var=self.launch_action_hint_var,
        )
        footer.pack(fill="x", pady=(10, 0))

        self.editor._refresh_run_policy_hints()
        self._refresh_runtime_summaries()

    def _build_workspace_ui(self, outer: ttk.Frame) -> None:
        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        title_box = ttk.Frame(header)
        title_box.grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_box,
            text="Расчёт",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            text="Режимы запуска, предпросмотр дороги, выгрузка и последние результаты.",
            foreground="#555555",
        ).pack(anchor="w", pady=(4, 0))

        header_actions = ttk.Frame(header)
        header_actions.grid(row=0, column=1, sticky="e")
        ttk.Button(
            header_actions,
            text="Проверить",
            command=self.editor._run_config_check,
        ).pack(side="left")
        self.launch_with_check_button = ttk.Button(
            header_actions,
            text="Проверить и запустить",
            command=self._run_selected_profile_with_check,
        )
        self.launch_with_check_button.pack(side="left", padx=(8, 0))
        self.launch_plain_button = ttk.Button(
            header_actions,
            text="Запустить",
            command=self._run_selected_profile,
        )
        self.launch_plain_button.pack(side="left", padx=(8, 0))
        ttk.Button(
            header_actions,
            text="Папка запусков",
            command=self.editor._open_desktop_runs_dir,
        ).pack(side="left", padx=(8, 0))

        workspace = ttk.Panedwindow(outer, orient="horizontal")
        workspace.grid(row=1, column=0, sticky="nsew", pady=(12, 0))

        sidebar = ttk.Frame(workspace, padding=(0, 0, 12, 0))
        sidebar.columnconfigure(0, weight=1)
        content = ttk.Frame(workspace)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        workspace.add(sidebar, weight=0)
        workspace.add(content, weight=1)

        context_box = ttk.LabelFrame(sidebar, text="Что выбрано", padding=8)
        context_box.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            context_box,
            textvariable=self.editor.run_summary_var,
            wraplength=260,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            context_box,
            textvariable=self.editor.preview_surface_summary_var,
            wraplength=260,
            justify="left",
            foreground="#555555",
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(
            context_box,
            textvariable=self.editor.run_mode_summary_var,
            wraplength=260,
            justify="left",
            foreground="#1f5d50",
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        nav_box = ttk.LabelFrame(sidebar, text="Настройки расчёта", padding=8)
        nav_box.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        sidebar.rowconfigure(1, weight=1)
        tree_host, self.section_tree = build_scrolled_treeview(
            nav_box,
            show="tree",
            selectmode="browse",
            height=8,
        )
        tree_host.pack(fill="both", expand=True)
        self.section_tree.bind("<<TreeviewSelect>>", self._on_section_tree_select, add="+")

        quick_box = ttk.LabelFrame(sidebar, text="Быстрые действия", padding=8)
        quick_box.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(
            quick_box,
            text="Профиль запуска",
            command=lambda: self._select_section("profile"),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            quick_box,
            text="Предпросмотр дороги",
            command=lambda: self._select_section("preview"),
        ).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(
            quick_box,
            text="Поведение и выгрузка",
            command=lambda: self._select_section("policy"),
        ).grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(
            quick_box,
            text="Набор испытаний",
            command=lambda: self._select_section("suite"),
        ).grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(
            quick_box,
            text="Обновить сводки",
            command=self._refresh_runtime_summaries,
        ).grid(row=4, column=0, sticky="ew", pady=(8, 0))
        quick_box.columnconfigure(0, weight=1)

        hint_box = ttk.LabelFrame(sidebar, text="Подсказка запуска", padding=8)
        hint_box.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(
            hint_box,
            textvariable=self.launch_action_hint_var,
            wraplength=260,
            justify="left",
            foreground="#355c7d",
        ).grid(row=0, column=0, sticky="w")

        self.notebook = ttk.Notebook(content)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self.notebook.bind("<<NotebookTabChanged>>", self._sync_section_tree_from_notebook, add="+")

        self._build_profile_tab()
        self._build_preview_tab()
        self._build_run_tab()
        self._build_policy_tab()
        self._build_suite_tab()
        self._build_launch_tab()
        self._build_artifacts_tab()
        self._populate_section_tree()

        footer = build_status_strip(
            outer,
            primary_var=self.launch_action_hint_var,
        )
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))

    def _create_tab(self, key: str, title: str) -> ttk.Frame:
        if self.notebook is None:
            raise RuntimeError("Notebook is not initialized")
        host, body = create_scrollable_tab(
            self.notebook,
            padding=12,
            yscroll=True,
            xscroll=False,
            fit_width=True,
        )
        body.columnconfigure(0, weight=1)
        self.notebook.add(host, text=title)
        self._section_tab_ids[key] = str(host)
        self._tab_hosts[key] = host
        return body

    def _populate_section_tree(self) -> None:
        if self.section_tree is None:
            return
        titles = {
            "profile": "Профиль запуска",
            "preview": "Предпросмотр дороги",
            "run": "Режим расчёта",
            "policy": "Поведение и выгрузка",
            "suite": "Набор испытаний",
            "launch": "Запуск",
            "artifacts": "Результаты и журналы",
        }
        for key, title in titles.items():
            self.section_tree.insert("", "end", iid=key, text=title)

    def _select_section(self, key: str) -> None:
        if self.notebook is not None:
            tab_id = self._section_tab_ids.get(key)
            if tab_id is not None:
                self.notebook.select(tab_id)
        if self.section_tree is not None:
            self._syncing_tree = True
            try:
                self.section_tree.selection_set(key)
                self.section_tree.focus(key)
                self.section_tree.see(key)
            finally:
                self._syncing_tree = False

    def _on_section_tree_select(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        if self._syncing_tree or self.section_tree is None or self.notebook is None:
            return
        selection = self.section_tree.selection()
        if not selection:
            return
        tab_id = self._section_tab_ids.get(selection[0])
        if tab_id is not None:
            self.notebook.select(tab_id)

    def _sync_section_tree_from_notebook(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        if self.section_tree is None or self.notebook is None:
            return
        active_tab = str(self.notebook.select())
        for key, tab_id in self._section_tab_ids.items():
            if tab_id == active_tab:
                self._syncing_tree = True
                try:
                    self.section_tree.selection_set(key)
                    self.section_tree.focus(key)
                    self.section_tree.see(key)
                finally:
                    self._syncing_tree = False
                return

    def _build_profile_tab(self) -> None:
        body = self._create_tab("profile", "Профиль запуска")
        profile_frame = ttk.LabelFrame(body, text="Профиль запуска", padding=10)
        profile_frame.grid(row=0, column=0, sticky="ew")
        for idx, (profile_key, profile_label, _profile_desc) in enumerate(DESKTOP_RUN_PROFILE_OPTIONS):
            ttk.Radiobutton(
                profile_frame,
                text=profile_label,
                value=profile_key,
                variable=self.editor.run_profile_var,
                command=lambda key=profile_key: self.editor._apply_run_setup_profile(key),
            ).grid(row=0, column=idx, sticky="w", padx=(0 if idx == 0 else 12, 0))
        ttk.Label(
            profile_frame,
            textvariable=self.editor.run_profile_hint_var,
            wraplength=860,
            justify="left",
            foreground="#555555",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def _build_preview_tab(self) -> None:
        body = self._create_tab("preview", "Предпросмотр дороги")
        preview_frame = ttk.LabelFrame(body, text="Предпросмотр дороги", padding=10)
        preview_frame.grid(row=0, column=0, sticky="ew")
        preview_frame.columnconfigure(5, weight=1)

        ttk.Label(preview_frame, text="Тип профиля").grid(row=0, column=0, sticky="w")
        preview_combo = ttk.Combobox(
            preview_frame,
            textvariable=self.editor.preview_surface_var,
            values=[label for _key, label in DESKTOP_PREVIEW_SURFACE_OPTIONS],
            state="readonly",
            width=28,
        )
        preview_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))
        preview_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.editor._refresh_preview_surface_controls(),
        )
        ttk.Label(
            preview_frame,
            textvariable=self.editor.preview_surface_summary_var,
            foreground="#555555",
            wraplength=620,
            justify="left",
        ).grid(row=0, column=2, columnspan=4, sticky="w", padx=(16, 0))

        ttk.Label(preview_frame, text="Шаг по времени, с").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Spinbox(
            preview_frame,
            from_=0.001,
            to=0.1,
            increment=0.001,
            textvariable=self.editor.preview_dt_var,
            width=10,
            format="%.3f",
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(preview_frame, text="Длительность, с").grid(
            row=1, column=2, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        ttk.Spinbox(
            preview_frame,
            from_=0.2,
            to=60.0,
            increment=0.1,
            textvariable=self.editor.preview_t_end_var,
            width=10,
            format="%.1f",
        ).grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(preview_frame, text="Длина участка, м").grid(
            row=1, column=4, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        ttk.Spinbox(
            preview_frame,
            from_=5.0,
            to=5000.0,
            increment=1.0,
            textvariable=self.editor.preview_road_len_var,
            width=10,
            format="%.1f",
        ).grid(row=1, column=5, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(preview_frame, textvariable=self.editor.preview_surface_primary_label_var).grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )
        self.editor.preview_surface_primary_spin = ttk.Spinbox(
            preview_frame,
            from_=0.0,
            to=2.0,
            increment=0.005,
            textvariable=self.editor.preview_surface_primary_value_var,
            width=10,
            format="%.3f",
        )
        self.editor.preview_surface_primary_spin.grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0)
        )

        ttk.Label(preview_frame, textvariable=self.editor.preview_surface_secondary_label_var).grid(
            row=2, column=2, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        self.editor.preview_surface_secondary_spin = ttk.Spinbox(
            preview_frame,
            from_=0.01,
            to=50.0,
            increment=0.05,
            textvariable=self.editor.preview_surface_secondary_value_var,
            width=10,
            format="%.3f",
        )
        self.editor.preview_surface_secondary_spin.grid(
            row=2, column=3, sticky="w", padx=(8, 0), pady=(10, 0)
        )

        ttk.Label(preview_frame, text="Начало профиля, м").grid(
            row=2, column=4, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        self.editor.preview_surface_start_spin = ttk.Spinbox(
            preview_frame,
            from_=0.0,
            to=500.0,
            increment=0.1,
            textvariable=self.editor.preview_surface_start_var,
            width=10,
            format="%.2f",
        )
        self.editor.preview_surface_start_spin.grid(
            row=2, column=5, sticky="w", padx=(8, 0), pady=(10, 0)
        )

        ttk.Label(preview_frame, text="Угол гребня, град").grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.editor.preview_surface_angle_spin = ttk.Spinbox(
            preview_frame,
            from_=-90.0,
            to=90.0,
            increment=1.0,
            textvariable=self.editor.preview_surface_angle_var,
            width=10,
            format="%.1f",
        )
        self.editor.preview_surface_angle_spin.grid(
            row=3, column=1, sticky="w", padx=(8, 0), pady=(10, 0)
        )

        ttk.Label(preview_frame, text="Коэффициент формы").grid(
            row=3, column=2, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        self.editor.preview_surface_shape_spin = ttk.Spinbox(
            preview_frame,
            from_=0.1,
            to=10.0,
            increment=0.1,
            textvariable=self.editor.preview_surface_shape_var,
            width=10,
            format="%.2f",
        )
        self.editor.preview_surface_shape_spin.grid(
            row=3, column=3, sticky="w", padx=(8, 0), pady=(10, 0)
        )

    def _build_run_tab(self) -> None:
        body = self._create_tab("run", "Режим расчёта")
        detail_frame = ttk.LabelFrame(body, text="Параметры запуска расчёта", padding=10)
        detail_frame.grid(row=0, column=0, sticky="ew")
        detail_frame.columnconfigure(5, weight=1)

        ttk.Label(detail_frame, text="Сценарий").grid(row=0, column=0, sticky="w")
        run_combo = ttk.Combobox(
            detail_frame,
            textvariable=self.editor.run_scenario_var,
            values=list(self.editor.run_scenario_key_to_label.values()),
            state="readonly",
            width=30,
        )
        run_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))
        run_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.editor._refresh_run_scenario_controls(),
        )
        ttk.Label(
            detail_frame,
            textvariable=self.editor.run_summary_var,
            foreground="#555555",
            wraplength=720,
            justify="left",
        ).grid(row=0, column=2, columnspan=4, sticky="w", padx=(16, 0))

        ttk.Label(detail_frame, text="Шаг по времени, с").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Spinbox(
            detail_frame,
            from_=0.001,
            to=0.1,
            increment=0.001,
            textvariable=self.editor.run_dt_var,
            width=10,
            format="%.3f",
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(detail_frame, text="Длительность, с").grid(
            row=1, column=2, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        ttk.Spinbox(
            detail_frame,
            from_=0.2,
            to=60.0,
            increment=0.1,
            textvariable=self.editor.run_t_end_var,
            width=10,
            format="%.1f",
        ).grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Checkbutton(
            detail_frame,
            text="Сохранять расширенный журнал давления и потоков",
            variable=self.editor.run_record_full_var,
        ).grid(row=1, column=4, columnspan=2, sticky="w", padx=(16, 0), pady=(10, 0))

        ttk.Label(detail_frame, textvariable=self.editor.run_primary_label_var).grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )
        self.editor.run_primary_spin = ttk.Spinbox(
            detail_frame,
            from_=0.0,
            to=50.0,
            increment=0.1,
            textvariable=self.editor.run_primary_value_var,
            width=10,
            format="%.3f",
        )
        self.editor.run_primary_spin.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(detail_frame, textvariable=self.editor.run_secondary_label_var).grid(
            row=2, column=2, sticky="w", padx=(16, 0), pady=(10, 0)
        )
        self.editor.run_secondary_spin = ttk.Spinbox(
            detail_frame,
            from_=0.0,
            to=50.0,
            increment=0.1,
            textvariable=self.editor.run_secondary_value_var,
            width=10,
            format="%.3f",
        )
        self.editor.run_secondary_spin.grid(row=2, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        preset_frame = ttk.LabelFrame(body, text="Быстрые пресеты", padding=10)
        preset_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        for idx, (preset_key, preset_label_text, _preset_desc) in enumerate(DESKTOP_RUN_PRESET_OPTIONS):
            ttk.Button(
                preset_frame,
                text=preset_label_text,
                command=lambda key=preset_key: self.editor._apply_run_preset(key),
            ).grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 8, 0))
            preset_frame.columnconfigure(idx, weight=1)

        ttk.Label(
            preset_frame,
            textvariable=self.editor.run_mode_summary_var,
            foreground="#334455",
            wraplength=860,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(
            preset_frame,
            textvariable=self.editor.run_mode_cost_var,
            foreground="#6b4d00",
            wraplength=860,
            justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            preset_frame,
            textvariable=self.editor.run_mode_advice_var,
            foreground="#1f5d50",
            wraplength=860,
            justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            preset_frame,
            textvariable=self.editor.run_mode_usage_var,
            foreground="#355c7d",
            wraplength=860,
            justify="left",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            preset_frame,
            textvariable=self.editor.run_preset_hint_var,
            foreground="#555555",
            wraplength=860,
            justify="left",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _build_policy_tab(self) -> None:
        body = self._create_tab("policy", "Поведение и выгрузка")
        runtime_frame = ttk.LabelFrame(body, text="Поведение расчёта и выгрузка", padding=10)
        runtime_frame.grid(row=0, column=0, sticky="ew")
        runtime_frame.columnconfigure(0, weight=1)
        runtime_frame.columnconfigure(1, weight=1)

        cache_frame = ttk.LabelFrame(runtime_frame, text="Повторное использование расчётов", padding=8)
        cache_frame.grid(row=0, column=0, sticky="nsew")
        for idx, (policy_key, policy_label, _policy_desc) in enumerate(DESKTOP_RUN_CACHE_POLICY_OPTIONS):
            ttk.Radiobutton(
                cache_frame,
                text=policy_label,
                value=policy_key,
                variable=self.editor.run_cache_policy_var,
            ).grid(row=idx, column=0, sticky="w")
        ttk.Label(
            cache_frame,
            textvariable=self.editor.run_cache_hint_var,
            wraplength=380,
            justify="left",
            foreground="#555555",
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))

        runtime_policy_frame = ttk.LabelFrame(runtime_frame, text="Поведение при предупреждениях", padding=8)
        runtime_policy_frame.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        for idx, (policy_key, policy_label, _policy_desc) in enumerate(DESKTOP_RUN_RUNTIME_POLICY_OPTIONS):
            ttk.Radiobutton(
                runtime_policy_frame,
                text=policy_label,
                value=policy_key,
                variable=self.editor.run_runtime_policy_var,
            ).grid(row=idx, column=0, sticky="w")
        ttk.Label(
            runtime_policy_frame,
            textvariable=self.editor.run_runtime_policy_hint_var,
            wraplength=380,
            justify="left",
            foreground="#555555",
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))

        flags_frame = ttk.LabelFrame(body, text="Что сохранять", padding=10)
        flags_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        ttk.Checkbutton(
            flags_frame,
            text="Сохранять таблицы результатов для подробных режимов",
            variable=self.editor.run_export_csv_var,
        ).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(
            flags_frame,
            text="Сохранять файл анимации для подробных режимов",
            variable=self.editor.run_export_npz_var,
        ).grid(row=0, column=1, sticky="w", padx=(16, 0))
        ttk.Checkbutton(
            flags_frame,
            text="Запускать самопроверку перед расчётом",
            variable=self.editor.run_auto_check_var,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            flags_frame,
            text="Сохранять журнал запуска в файл",
            variable=self.editor.run_log_to_file_var,
        ).grid(row=1, column=1, sticky="w", padx=(16, 0), pady=(8, 0))
        ttk.Label(
            flags_frame,
            text=(
                "Повторное использование и сохранение результатов важны для подробных режимов. "
                "Краткий предпросмотр всегда пишет короткую сводку, а самопроверка и журнал доступны для всех режимов."
            ),
            wraplength=860,
            justify="left",
            foreground="#555555",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _build_suite_tab(self) -> None:
        body = self._create_tab("suite", "Набор испытаний")
        body.rowconfigure(1, weight=1)

        status_frame = ttk.LabelFrame(body, text="Состояние набора испытаний", padding=10)
        status_frame.grid(row=0, column=0, sticky="ew")
        status_frame.columnconfigure(0, weight=1)
        ttk.Label(
            status_frame,
            textvariable=self.editor.suite_handoff_var,
            wraplength=880,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            status_frame,
            textvariable=self.suite_lineage_var,
            wraplength=880,
            justify="left",
            foreground="#334455",
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        matrix_frame = ttk.LabelFrame(body, text="Матрица испытаний", padding=10)
        matrix_frame.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        matrix_frame.columnconfigure(0, weight=1)
        matrix_frame.rowconfigure(0, weight=1)
        columns = ("enabled", "name", "stage", "type", "dt", "t_end", "refs", "hashes", "state")
        self.suite_tree = ttk.Treeview(matrix_frame, columns=columns, show="headings", height=10)
        headings = {
            "enabled": "вкл.",
            "name": "имя",
            "stage": "стадия",
            "type": "тип",
            "dt": "шаг, с",
            "t_end": "длительность, с",
            "refs": "исходные файлы",
            "hashes": "контрольные суммы",
            "state": "актуальность",
        }
        widths = {
            "enabled": 70,
            "name": 160,
            "stage": 65,
            "type": 120,
            "dt": 65,
            "t_end": 65,
            "refs": 210,
            "hashes": 180,
            "state": 230,
        }
        for column in columns:
            self.suite_tree.heading(column, text=headings[column])
            self.suite_tree.column(column, width=widths[column], stretch=(column in {"name", "refs", "state"}))
        yscroll = ttk.Scrollbar(matrix_frame, orient="vertical", command=self.suite_tree.yview)
        self.suite_tree.configure(yscrollcommand=yscroll.set)
        self.suite_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        command_frame = ttk.LabelFrame(body, text="Действия с набором", padding=10)
        command_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(
            command_frame,
            text="Проверить набор",
            command=self._refresh_suite_preview_table,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            command_frame,
            text="Зафиксировать набор",
            command=self._freeze_suite_handoff,
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Button(
            command_frame,
            text="Открыть снимок набора",
            command=self.editor._open_suite_handoff_snapshot,
        ).grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Button(
            command_frame,
            text="Открыть папку набора",
            command=self.editor._open_suite_handoff_dir,
        ).grid(row=0, column=3, sticky="w", padx=(12, 0))
        ttk.Button(
            command_frame,
            text="Сбросить ручные изменения",
            command=self._reset_suite_overrides,
        ).grid(row=0, column=4, sticky="w", padx=(12, 0))
        ttk.Label(
            command_frame,
            text=(
                "Данные, подготовленные редактором колец и вводом исходных данных, здесь "
                "только читаются. Для правки геометрии или сценариев откройте редактор "
                "и генератор сценариев колец."
            ),
            wraplength=880,
            justify="left",
            foreground="#555555",
        ).grid(row=1, column=0, columnspan=5, sticky="w", pady=(10, 0))
        self._refresh_suite_preview_table()

    def _build_launch_tab(self) -> None:
        body = self._create_tab("launch", "Запуск")
        summary_frame = ttk.LabelFrame(body, text="Что будет запущено", padding=10)
        summary_frame.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            summary_frame,
            textvariable=self.editor.run_launch_summary_var,
            wraplength=880,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Button(
            summary_frame,
            text="Проверить конфигурацию",
            command=self.editor._run_config_check,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            summary_frame,
            text="Проверить и запустить",
            command=self._run_selected_profile_with_check,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            summary_frame,
            text="Запустить расчёт",
            command=self._run_selected_profile,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            summary_frame,
            text="Открыть папку запусков",
            command=self.editor._open_desktop_runs_dir,
        ).grid(row=1, column=3, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Label(
            summary_frame,
            textvariable=self.launch_action_hint_var,
            wraplength=880,
            justify="left",
            foreground="#1f5d50",
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))

    def _build_artifacts_tab(self) -> None:
        body = self._create_tab("artifacts", "Результаты и журналы")
        recent_frame = ttk.LabelFrame(body, text="Последние результаты", padding=10)
        recent_frame.grid(row=0, column=0, sticky="ew")
        recent_frame.columnconfigure(0, weight=1)
        recent_frame.columnconfigure(1, weight=1)

        preview_recent_frame = ttk.LabelFrame(
            recent_frame,
            text="Последний предпросмотр",
            padding=8,
        )
        preview_recent_frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(
            preview_recent_frame,
            textvariable=self.editor.latest_preview_summary_var,
            wraplength=400,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Button(
            preview_recent_frame,
            text="Обновить сводку",
            command=self.editor._refresh_latest_preview_summary,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            preview_recent_frame,
            text="Открыть сводку",
            command=self.editor._open_latest_preview_report_json,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            preview_recent_frame,
            text="Открыть журнал",
            command=self.editor._open_latest_preview_log,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))

        run_recent_frame = ttk.LabelFrame(
            recent_frame,
            text="Последний подробный расчёт",
            padding=8,
        )
        run_recent_frame.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        ttk.Label(
            run_recent_frame,
            textvariable=self.editor.latest_run_summary_var,
            wraplength=400,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Button(
            run_recent_frame,
            text="Обновить сводку",
            command=self.editor._refresh_latest_run_summary,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть сводку",
            command=self.editor._open_latest_run_summary_json,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть журнал",
            command=self.editor._open_latest_run_log,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть основную таблицу результатов",
            command=self.editor._open_latest_df_main_csv,
        ).grid(row=1, column=3, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть файл анимации",
            command=self.editor._open_latest_npz_bundle,
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть готовый результат",
            command=self.editor._open_latest_run_cache_dir,
        ).grid(row=2, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            run_recent_frame,
            text="Открыть папку запусков",
            command=self.editor._open_desktop_runs_dir,
        ).grid(row=2, column=2, sticky="w", padx=(12, 0), pady=(10, 0))

        check_recent_frame = ttk.LabelFrame(
            body,
            text="Последняя самопроверка",
            padding=10,
        )
        check_recent_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(
            check_recent_frame,
            textvariable=self.editor.latest_selfcheck_summary_var,
            wraplength=860,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Button(
            check_recent_frame,
            text="Обновить сводку",
            command=self.editor._refresh_latest_selfcheck_summary,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            check_recent_frame,
            text="Открыть сводку",
            command=self.editor._open_latest_selfcheck_report_json,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            check_recent_frame,
            text="Открыть журнал",
            command=self.editor._open_latest_selfcheck_log,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))

        support_frame = ttk.LabelFrame(body, text="Папки и журналы расчёта", padding=10)
        support_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(
            support_frame,
            text=(
                "Здесь собраны папки расчёта. "
                "Открывайте их, когда нужно проверить повторное использование, журнал запуска или ручную выгрузку."
            ),
            wraplength=860,
            justify="left",
            foreground="#555555",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Button(
            support_frame,
            text="Открыть папку готовых результатов",
            command=self.editor._open_run_setup_cache_root,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            support_frame,
            text="Открыть папку журналов",
            command=self.editor._open_run_setup_log_root,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            support_frame,
            text="Обновить все сводки",
            command=self._refresh_runtime_summaries,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))

    def _bind_live_refreshes(self) -> None:
        self._trace_tokens.append(
            self.editor.run_launch_summary_var.trace_add(
                "write",
                lambda *_args: self._refresh_launch_action_hint(),
            )
        )

    def _unbind_live_refreshes(self) -> None:
        while self._trace_tokens:
            token = self._trace_tokens.pop()
            try:
                self.editor.run_launch_summary_var.trace_remove("write", token)
            except Exception:
                continue

    def _refresh_launch_action_hint(self) -> None:
        report_path = self.editor._runtime_selfcheck_report_path()
        report_exists = report_path.exists()
        report = self.editor._load_selfcheck_report(report_path)
        has_signature, is_stale = self.editor._selfcheck_freshness_state(report)
        action_key = recommended_run_launch_action(
            auto_check_enabled=bool(self.editor.run_auto_check_var.get()),
            summary=report,
            report_exists=report_exists,
            has_signature=has_signature,
            is_stale=is_stale,
        )
        launch_target = describe_run_launch_target(
            launch_profile_key=self.editor._selected_run_profile_key(),
            scenario_key=self.editor._selected_run_scenario_key(),
            scenario_label=self.editor._selected_run_scenario_label(),
        )
        plain_launch_state = describe_plain_launch_availability(
            auto_check_enabled=bool(self.editor.run_auto_check_var.get()),
            runtime_policy_key=str(self.editor.run_runtime_policy_var.get() or "balanced"),
            summary=report,
            report_exists=report_exists,
            has_signature=has_signature,
            is_stale=is_stale,
        )
        plain_enabled = bool(plain_launch_state.get("enabled", True))
        plain_detail = str(plain_launch_state.get("detail") or "").strip()
        check_text = str(launch_target.get("checked_button") or "Проверить и запустить").strip()
        plain_text = str(launch_target.get("plain_button") or "Запустить расчёт").strip()
        target_hint = str(launch_target.get("hint_line") or "").strip()
        if action_key == "check_then_launch":
            check_text += " (рекомендуется)"
            if not plain_enabled:
                plain_text += " (недоступно)"
                hint = (
                    f"{target_hint} "
                    "Рекомендуемая кнопка: Проверить и запустить. "
                    f"Обычный запуск сейчас недоступен: {plain_detail}."
                )
            else:
                hint = (
                    f"{target_hint} "
                    "Рекомендуемая кнопка: Проверить и запустить. "
                    f"Обычный запуск пока доступен, но {plain_detail}."
                )
        else:
            plain_text += " (рекомендуется)"
            hint = (
                f"{target_hint} "
                "Рекомендуемая кнопка: Запустить расчёт. "
                f"Обычный запуск доступен: {plain_detail}."
            )
        if self.launch_with_check_button is not None:
            self.launch_with_check_button.configure(text=check_text)
        if self.launch_plain_button is not None:
            self.launch_plain_button.configure(
                text=plain_text,
                state=("normal" if plain_enabled else "disabled"),
            )
        self.launch_action_hint_var.set(hint)

    def _run_selected_profile(self) -> None:
        profile_key = self.editor._selected_run_profile_key()
        if profile_key == "baseline" and self.editor._selected_run_scenario_key() == "worldroad":
            self.editor._run_quick_preview()
            return
        self.editor._run_single_desktop_run()

    def _run_selected_profile_with_check(self) -> None:
        run_label = "Запустить расчёт"
        if not self.editor._soft_preflight_before_run(run_label):
            return

        def _launch_selected_prechecked() -> None:
            profile_key = self.editor._selected_run_profile_key()
            if profile_key == "baseline" and self.editor._selected_run_scenario_key() == "worldroad":
                self.editor._run_quick_preview(prechecked=True)
                return
            self.editor._run_single_desktop_run(prechecked=True)

        def _after_check(report_path: object) -> None:
            if self.editor._auto_check_allows_launch(report_path, run_label):
                _launch_selected_prechecked()
                return
            self.editor._append_run_log(
                f"[самопроверка] {run_label}: запуск отменён после принудительной самопроверки."
            )

        self.editor._run_config_check(
            title=f"Самопроверка перед «{run_label}»",
            on_success=_after_check,
        )

    @staticmethod
    def _short_hash(value: object) -> str:
        text = str(value or "").strip()
        return text[:12] if text else "—"

    @staticmethod
    def _suite_lineage_status_text(context: dict[str, object] | None) -> str:
        current = dict(context or {})
        if not current:
            return (
                "Набор испытаний ещё не проверен. "
                "Геометрия колец используется только для чтения; правьте её в редакторе сценариев колец."
            )
        state_labels = {
            "current": "актуально",
            "missing": "не найдено",
            "stale": "устарело",
            "invalid": "ошибка",
        }
        reason_labels = {
            "ring_source_hash_changed": "изменился исходный сценарий",
            "ring_export_set_hash_changed": "изменилась выгрузка сценария",
            "suite_snapshot_hash_changed": "изменился набор испытаний",
            "inputs_snapshot_hash_changed": "изменились исходные данные",
            "missing_" + "validated_" + "suite_snapshot": "нет снимка набора",
            "unsupported_" + "validated_" + "suite_snapshot_schema": "неподдерживаемая версия снимка набора",
            "missing_ring_or_input_refs": "не хватает ссылок на исходные данные или сценарии",
            "missing_upstream_handoff_refs": "не хватает входных ссылок",
            "rejected_suite_overrides": "есть отклонённые ручные изменения",
            "suite_validation_failed": "проверка набора не пройдена",
        }

        def _state_label(value: object) -> str:
            raw = str(value or "missing").strip()
            return state_labels.get(raw, raw)

        def _reason_label(value: object) -> str:
            raw = str(value or "").strip()
            return reason_labels.get(raw, raw)

        snapshot = dict(current.get("snapshot") or {})
        inputs_context = dict(current.get("inputs_context") or {})
        ring_context = dict(current.get("ring_context") or {})
        current_state = dict(current.get("state") or {})
        existing_state = dict(current.get("existing_state") or {})
        source_ref = dict(ring_context.get("source_ref") or {})
        if not source_ref:
            source_ref = dict(dict(snapshot.get("upstream_refs") or {}).get("ring") or {}).get("source_ref") or {}
            source_ref = dict(source_ref) if isinstance(source_ref, dict) else {}
        ring_source_hash = (
            str(ring_context.get("source_hash") or "").strip()
            or str(dict(dict(snapshot.get("upstream_refs") or {}).get("ring") or {}).get("source_hash") or "").strip()
        )
        export_set_hash = str(
            source_ref.get("ring_export_set_hash_sha256")
            or source_ref.get("ring_export_set_hash_current_sha256")
            or ""
        ).strip()
        suite_hash = str(snapshot.get("suite_snapshot_hash") or "").strip()
        suite_state = str(existing_state.get("state") or current_state.get("state") or "missing")
        stale_reasons = list(existing_state.get("stale_reasons") or current_state.get("stale_reasons") or [])
        stale_row_names: list[str] = []
        stale_row_reasons: list[str] = []
        for idx, row in enumerate(list(snapshot.get("suite_rows") or [])):
            if not isinstance(row, dict) or not bool(row.get("ring_handoff_stale", False)):
                continue
            name = str(row.get("имя") or row.get("name") or row.get("id") or f"row_{idx + 1}")
            stale_row_names.append(name)
            stale_row_reasons.extend(str(item) for item in list(row.get("ring_stale_reasons") or []) if str(item).strip())
        lines = [
            (
                f"Исходные данные: {_state_label(inputs_context.get('state'))}; "
                f"сценарии колец: {_state_label(ring_context.get('state'))}; снимок набора: {_state_label(suite_state)}"
            ),
            (
                f"Снимок колец: {DesktopRunSetupCenter._short_hash(ring_source_hash)} | "
                f"Экспорт колец: {DesktopRunSetupCenter._short_hash(export_set_hash)} | "
                f"Снимок набора: {DesktopRunSetupCenter._short_hash(suite_hash)}"
            ),
            f"Устаревшие строки: {', '.join(stale_row_names) if stale_row_names else 'нет'}",
            (
                "Причины устаревания: "
                + ", ".join(_reason_label(item) for item in [*stale_reasons, *stale_row_reasons] if str(item).strip())
                if stale_reasons or stale_row_reasons
                else "Причины устаревания: нет"
            ),
            "Геометрия колец используется только для чтения; правьте её в редакторе сценариев колец.",
        ]
        return "\n".join(lines)

    @staticmethod
    def _suite_preview_rows(context: dict[str, object] | None) -> list[tuple[str, str, str, str, str, str, str, str, str]]:
        current = dict(context or {})
        snapshot = dict(current.get("snapshot") or {})
        validation = dict(snapshot.get("validation") or {})
        reason_labels = {
            "ring_source_hash_changed": "изменился исходный сценарий",
            "ring_export_set_hash_changed": "изменилась выгрузка сценария",
            "suite_snapshot_hash_changed": "изменился набор испытаний",
            "inputs_snapshot_hash_changed": "изменились исходные данные",
            "missing_ring_or_input_refs": "не хватает ссылок на исходные данные или сценарии",
        }
        missing_by_row: dict[str, int] = {}
        for item in list(validation.get("missing_refs") or []):
            if isinstance(item, dict):
                name = str(item.get("row") or "")
                missing_by_row[name] = missing_by_row.get(name, 0) + 1
        rows: list[tuple[str, str, str, str, str, str, str, str, str]] = []
        for idx, row in enumerate(list(snapshot.get("suite_rows") or [])):
            if not isinstance(row, dict):
                continue
            name = str(row.get("имя") or row.get("name") or row.get("id") or f"row_{idx + 1}")
            refs = ", ".join(
                key
                for key in (
                    "road_csv",
                    "axay_csv",
                    "scenario_json",
                    "road_csv_path",
                    "axay_csv_path",
                    "scenario_json_path",
                    "segment_meta_ref",
                )
                if str(row.get(key) or "").strip()
            )
            source_hash = str(row.get("ring_source_hash_sha256") or row.get("ring_source_hash") or "").strip()
            export_hash = str(row.get("ring_export_set_hash_sha256") or "").strip()
            stale_reasons = [
                reason_labels.get(str(item), str(item))
                for item in list(row.get("ring_stale_reasons") or [])
                if str(item).strip()
            ]
            if missing_by_row.get(name):
                stale_reasons.append(f"не хватает ссылок: {missing_by_row[name]}")
            stale_label = "устарело: да" if bool(row.get("ring_handoff_stale", False)) else "актуально"
            if stale_reasons:
                stale_label += "; " + ", ".join(stale_reasons)
            rows.append(
                (
                    "да" if bool(row.get("включен", row.get("enabled", True))) else "нет",
                    name,
                    str(row.get("стадия", row.get("stage", 0)) or 0),
                    str(row.get("тип", row.get("type", "")) or ""),
                    str(row.get("dt", "")),
                    str(row.get("t_end", row.get("t_end_s", ""))),
                    refs or "—",
                    (
                        f"источник={DesktopRunSetupCenter._short_hash(source_hash)} | "
                        f"экспорт={DesktopRunSetupCenter._short_hash(export_hash)}"
                    ),
                    stale_label,
                )
            )
        return rows

    def _refresh_suite_preview_table(self) -> None:
        context = self.editor._refresh_suite_handoff_state()
        self.suite_lineage_var.set(self._suite_lineage_status_text(context))
        if self.suite_tree is None:
            return
        for item in self.suite_tree.get_children():
            self.suite_tree.delete(item)
        for idx, row in enumerate(self._suite_preview_rows(context)):
            self.suite_tree.insert("", "end", iid=f"suite_row_{idx}", values=row)

    def _freeze_suite_handoff(self) -> None:
        self.editor._freeze_suite_handoff_snapshot()
        self._refresh_suite_preview_table()

    def _reset_suite_overrides(self) -> None:
        self.editor._reset_suite_overrides()
        self._refresh_suite_preview_table()

    def _refresh_runtime_summaries(self) -> None:
        self.editor._refresh_latest_preview_summary()
        self.editor._refresh_latest_selfcheck_summary()
        self.editor._refresh_latest_run_summary()
        self._refresh_suite_preview_table()
        self._refresh_launch_action_hint()


__all__ = ["DesktopRunSetupCenter"]
