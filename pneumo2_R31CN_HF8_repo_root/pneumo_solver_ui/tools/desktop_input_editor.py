# -*- coding: utf-8 -*-
"""Desktop editor for source input data and calculation settings."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from pneumo_solver_ui.desktop_input_model import (
    DESKTOP_QUICK_PRESET_OPTIONS,
    DESKTOP_RUN_PRESET_OPTIONS,
    DESKTOP_PREVIEW_SURFACE_OPTIONS,
    DESKTOP_INPUT_SECTIONS,
    DesktopInputFieldSpec,
    apply_desktop_quick_preset,
    apply_desktop_run_preset,
    build_desktop_preview_surface,
    build_desktop_profile_diff,
    delete_desktop_profile,
    describe_desktop_run_mode,
    desktop_section_status_label,
    desktop_profile_dir_path,
    desktop_profile_display_name,
    desktop_snapshot_dir_path,
    desktop_snapshot_display_name,
    default_base_json_path,
    default_ranges_json_path,
    default_suite_json_path,
    default_working_copy_path,
    evaluate_desktop_section_readiness,
    find_desktop_field_matches,
    load_base_defaults,
    list_desktop_profile_paths,
    list_desktop_snapshot_paths,
    load_base_with_defaults,
    load_desktop_profile,
    load_desktop_snapshot,
    preview_surface_label,
    quick_preset_description,
    quick_preset_label,
    repo_root,
    run_preset_description,
    run_preset_label,
    save_desktop_profile,
    save_desktop_snapshot,
    save_base_payload,
)


try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


class ScrollableSection(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas)
        self.body.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self.window, width=e.width),
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")


class DesktopInputEditor:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"Pneumo Input Editor — {RELEASE}")
        self.root.geometry("1160x860")
        self.root.minsize(1020, 760)
        self.ui_style = ttk.Style(self.root)

        self.current_source_path: Path = default_base_json_path()
        self.current_payload = load_base_with_defaults()
        self.default_payload = load_base_defaults()
        self.vars: dict[str, tk.Variable] = {}
        self._widget_handles: dict[str, tuple[DesktopInputFieldSpec, ttk.Label]] = {}
        self._field_frames: dict[str, ttk.LabelFrame] = {}
        self._field_tabs_by_key: dict[str, ScrollableSection] = {}
        self._section_title_by_key = {
            spec.key: section.title
            for section in DESKTOP_INPUT_SECTIONS
            for spec in section.fields
        }
        self.section_titles = [section.title for section in DESKTOP_INPUT_SECTIONS]
        self.section_title_to_index = {
            title: idx for idx, title in enumerate(self.section_titles)
        }
        self.preview_dt_var = tk.DoubleVar(value=0.01)
        self.preview_t_end_var = tk.DoubleVar(value=3.0)
        self.preview_road_len_var = tk.DoubleVar(value=60.0)
        self.preview_surface_key_to_label = dict(DESKTOP_PREVIEW_SURFACE_OPTIONS)
        self.preview_surface_label_to_key = {
            label: key for key, label in DESKTOP_PREVIEW_SURFACE_OPTIONS
        }
        self.preview_surface_var = tk.StringVar(
            value=self.preview_surface_key_to_label.get("flat", "Ровная дорога")
        )
        self.preview_surface_primary_value_var = tk.DoubleVar(value=0.02)
        self.preview_surface_secondary_value_var = tk.DoubleVar(value=2.0)
        self.preview_surface_start_var = tk.DoubleVar(value=5.0)
        self.preview_surface_angle_var = tk.DoubleVar(value=35.0)
        self.preview_surface_shape_var = tk.DoubleVar(value=1.5)
        self.preview_surface_primary_label_var = tk.StringVar()
        self.preview_surface_secondary_label_var = tk.StringVar()
        self.preview_surface_summary_var = tk.StringVar()
        self.profile_choice_var = tk.StringVar(value="—")
        self.profile_name_var = tk.StringVar(value="рабочий_вариант")
        self.profile_hint_var = tk.StringVar()
        self.active_profile_path: Path | None = None
        self.snapshot_before_run_var = tk.BooleanVar(value=True)
        self.snapshot_choice_var = tk.StringVar(value="—")
        self.snapshot_name_var = tk.StringVar(value="перед_запуском")
        self.snapshot_hint_var = tk.StringVar()
        self.active_snapshot_path: Path | None = None
        self.compare_summary_var = tk.StringVar()
        self.compare_target_path: Path | None = None
        self.compare_diffs_by_key: dict[str, dict[str, object]] = {}
        self.config_summary_var = tk.StringVar()
        self.run_context_var = tk.StringVar()
        self.quick_preset_hint_var = tk.StringVar(
            value="Быстрые пресеты меняют только часть параметров и подходят для черновой инженерной настройки."
        )
        self.undo_hint_var = tk.StringVar(
            value="История безопасных действий пока пуста."
        )
        self.route_summary_var = tk.StringVar()
        self._safe_action_history: list[dict[str, object]] = []
        self.route_buttons: dict[str, ttk.Button] = {}
        self.field_search_var = tk.StringVar()
        self.field_search_choice_var = tk.StringVar(value="—")
        self.field_search_summary_var = tk.StringVar(
            value="Введите часть названия, единицы измерения или описания параметра."
        )
        self._field_search_display_to_key: dict[str, str] = {}
        self.run_scenario_key_to_label = {
            "worldroad": "Дорога: текущий профиль preview",
            "roll": "Инерция: крен",
            "pitch": "Инерция: тангаж",
            "micro_sync": "Микро: синфаза",
        }
        self.run_scenario_label_to_key = {
            label: key for key, label in self.run_scenario_key_to_label.items()
        }
        self.run_scenario_var = tk.StringVar(
            value=self.run_scenario_key_to_label["worldroad"]
        )
        self.run_dt_var = tk.DoubleVar(value=0.003)
        self.run_t_end_var = tk.DoubleVar(value=1.6)
        self.run_record_full_var = tk.BooleanVar(value=True)
        self.run_primary_value_var = tk.DoubleVar(value=3.0)
        self.run_secondary_value_var = tk.DoubleVar(value=0.4)
        self.run_primary_label_var = tk.StringVar()
        self.run_secondary_label_var = tk.StringVar()
        self.run_summary_var = tk.StringVar()
        self.run_mode_summary_var = tk.StringVar()
        self.run_mode_cost_var = tk.StringVar()
        self.run_mode_advice_var = tk.StringVar()
        self.run_mode_usage_var = tk.StringVar()
        self.run_launch_summary_var = tk.StringVar()
        self.run_preset_hint_var = tk.StringVar(
            value="Пресеты запуска меняют только режим расчёта: шаг, длительность и расширенный лог."
        )
        self.run_launch_label: ttk.Label | None = None
        self.status_var = tk.StringVar()
        self.path_var = tk.StringVar()
        self._task_running = False
        self._set_status("Готово. Открыт черновик на основе default_base.json.")
        self._configure_launch_summary_styles()
        self._build_ui()
        self._bind_summary_var_traces()
        self._refresh_safe_action_history_view()
        self._refresh_section_route_summary()
        self._refresh_preview_surface_controls()
        self._refresh_run_scenario_controls()
        self._refresh_profile_list()
        self._refresh_snapshot_list()
        self._load_into_vars(self.current_payload, self.current_source_path)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _configure_launch_summary_styles(self) -> None:
        self.ui_style.configure("DesktopLaunchFast.TLabel", foreground="#4f6b7a")
        self.ui_style.configure("DesktopLaunchBalanced.TLabel", foreground="#334455")
        self.ui_style.configure("DesktopLaunchDetailed.TLabel", foreground="#7a4f01")

    def _launch_summary_style_for_mode(self, mode_key: str) -> str:
        key = str(mode_key or "").strip().lower()
        if key == "fast":
            return "DesktopLaunchFast.TLabel"
        if key == "detailed":
            return "DesktopLaunchDetailed.TLabel"
        return "DesktopLaunchBalanced.TLabel"

    def _apply_run_launch_style(self, mode_key: str) -> None:
        if self.run_launch_label is None:
            return
        self.run_launch_label.configure(style=self._launch_summary_style_for_mode(mode_key))

    def _current_section_index(self) -> int:
        try:
            return int(self.section_notebook.index(self.section_notebook.select()))
        except Exception:
            return 0

    def _select_section_index(self, index: int) -> None:
        if not self.section_titles:
            return
        safe_index = max(0, min(int(index), len(self.section_titles) - 1))
        self.section_notebook.select(safe_index)
        self._refresh_section_route_summary()

    def _select_section_by_title(self, section_title: str) -> None:
        target_index = self.section_title_to_index.get(str(section_title or "").strip())
        if target_index is None:
            return
        self._select_section_index(target_index)

    def _go_prev_section(self) -> None:
        self._select_section_index(self._current_section_index() - 1)

    def _go_next_section(self) -> None:
        self._select_section_index(self._current_section_index() + 1)

    def _refresh_section_route_summary(self) -> None:
        if not self.section_titles:
            self.route_summary_var.set("Шаги настройки пока недоступны.")
            return
        readiness_rows = evaluate_desktop_section_readiness(self._gather_payload())
        readiness_by_title = {str(row.get("title") or ""): row for row in readiness_rows}
        for idx, title in enumerate(self.section_titles):
            button = self.route_buttons.get(title)
            if button is None:
                continue
            row = readiness_by_title.get(title, {})
            status_text = desktop_section_status_label(str(row.get("status") or ""))
            button.configure(text=f"{idx + 1}. {title} · {status_text}")
        index = self._current_section_index()
        current_title = self.section_titles[index]
        previous_title = self.section_titles[index - 1] if index > 0 else "—"
        next_title = self.section_titles[index + 1] if index + 1 < len(self.section_titles) else "Готово к запуску"
        current_row = readiness_by_title.get(current_title, {})
        ok_count = sum(1 for row in readiness_rows if str(row.get("status") or "") == "ok")
        warn_count = sum(1 for row in readiness_rows if str(row.get("status") or "") == "warn")
        self.route_summary_var.set(
            f"Сейчас шаг {index + 1} из {len(self.section_titles)}: {current_title}. "
            f"Предыдущий: {previous_title}. Следующий: {next_title}. "
            f"Готово шагов: {ok_count}; требуют внимания: {warn_count}. "
            f"Статус шага: {desktop_section_status_label(str(current_row.get('status') or ''))}. "
            f"{str(current_row.get('summary') or '').strip()}"
        )

    def _selected_field_search_key(self) -> str | None:
        selected = str(self.field_search_choice_var.get() or "").strip()
        if not selected or selected == "—":
            return None
        return self._field_search_display_to_key.get(selected)

    def _refresh_field_search_results(self) -> None:
        query = str(self.field_search_var.get() or "").strip()
        if not query:
            self._field_search_display_to_key = {}
            self.field_search_combo.configure(values=[])
            self.field_search_choice_var.set("—")
            self.field_search_summary_var.set(
                "Введите часть названия, единицы измерения или описания параметра."
            )
            return
        matches = find_desktop_field_matches(query, limit=12)
        display_values = [str(item.get("display") or "").strip() for item in matches if str(item.get("display") or "").strip()]
        self._field_search_display_to_key = {
            str(item.get("display") or "").strip(): str(item.get("key") or "").strip()
            for item in matches
            if str(item.get("display") or "").strip() and str(item.get("key") or "").strip()
        }
        self.field_search_combo.configure(values=display_values)
        if display_values:
            self.field_search_choice_var.set(display_values[0])
            first_match = matches[0]
            self.field_search_summary_var.set(
                f"Найдено параметров: {len(matches)}. "
                f"Первый результат: {str(first_match.get('label') or '').strip()} "
                f"в секции «{str(first_match.get('section_title') or '').strip()}»."
            )
            return
        self.field_search_choice_var.set("—")
        self.field_search_summary_var.set(
            f"По запросу «{query}» ничего не найдено. Попробуйте часть названия или описание параметра."
        )

    def _clear_field_search(self) -> None:
        self.field_search_var.set("")
        self.field_search_choice_var.set("—")
        self._field_search_display_to_key = {}
        self.field_search_combo.configure(values=[])
        self.field_search_summary_var.set(
            "Введите часть названия, единицы измерения или описания параметра."
        )
        self._set_status("Поиск параметров очищен.")

    def _scroll_to_field(self, key: str) -> None:
        frame = self._field_frames.get(key)
        tab = self._field_tabs_by_key.get(key)
        if frame is None or tab is None:
            return

        def _do_scroll() -> None:
            try:
                tab.canvas.update_idletasks()
                tab.body.update_idletasks()
                body_height = max(int(tab.body.winfo_height()), int(tab.body.winfo_reqheight()), 1)
                target_y = max(int(frame.winfo_y()) - 12, 0)
                tab.canvas.yview_moveto(min(1.0, max(0.0, target_y / body_height)))
                frame.focus_set()
            except Exception:
                return

        self.root.after(20, _do_scroll)

    def _jump_to_field(self, key: str) -> None:
        clean_key = str(key or "").strip()
        if not clean_key:
            return
        section_title = self._section_title_by_key.get(clean_key)
        if section_title:
            self._select_section_by_title(section_title)
        self._scroll_to_field(clean_key)
        spec, _label = self._widget_handles.get(clean_key, (None, None))
        if spec is not None:
            self.field_search_summary_var.set(
                f"Переход к параметру «{spec.label}» в секции «{section_title or '—'}»."
            )
            self._set_status(f"Открыт параметр: {spec.label}")

    def _jump_to_selected_field(self) -> None:
        key = self._selected_field_search_key()
        if key is None:
            if str(self.field_search_var.get() or "").strip():
                self._refresh_field_search_results()
                key = self._selected_field_search_key()
        if key is None:
            messagebox.showinfo(
                "Desktop Input Editor",
                "Сначала введите запрос и выберите параметр для перехода.",
            )
            return
        self._jump_to_field(key)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Ввод исходных данных",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Desktop-редактор для исходных параметров модели. "
                "Здесь редактируются основные размеры, пневматика, механика и настройки расчёта "
                "без WEB UI и без изменения Desktop Mnemo."
            ),
            wraplength=1080,
            justify="left",
        ).pack(anchor="w", pady=(6, 12))

        toolbar = ttk.LabelFrame(outer, text="Файл параметров", padding=10)
        toolbar.pack(fill="x")

        ttk.Label(toolbar, text="Текущий источник:").grid(row=0, column=0, sticky="w")
        ttk.Label(toolbar, textvariable=self.path_var, foreground="#2f4f4f").grid(
            row=0,
            column=1,
            columnspan=4,
            sticky="w",
            padx=(8, 0),
        )

        ttk.Button(toolbar, text="Загрузить JSON...", command=self._load_json).grid(row=1, column=0, pady=(10, 0), sticky="w")
        ttk.Button(toolbar, text="Вернуть default_base.json", command=self._reset_to_default).grid(row=1, column=1, pady=(10, 0), sticky="w", padx=(8, 0))
        ttk.Button(toolbar, text="Сохранить рабочую копию", command=self._save_working_copy).grid(row=1, column=2, pady=(10, 0), sticky="w", padx=(8, 0))
        ttk.Button(toolbar, text="Сохранить как...", command=self._save_as).grid(row=1, column=3, pady=(10, 0), sticky="w", padx=(8, 0))
        ttk.Button(toolbar, text="Открыть папку проекта", command=self._open_repo_root).grid(row=1, column=4, pady=(10, 0), sticky="e", padx=(8, 0))

        profiles = ttk.LabelFrame(outer, text="Рабочие профили", padding=10)
        profiles.pack(fill="x", pady=(12, 0))
        profiles.columnconfigure(5, weight=1)

        ttk.Label(
            profiles,
            text=(
                "Профили позволяют держать несколько рабочих наборов исходных данных "
                "и быстро переключаться между ними перед расчётом."
            ),
            wraplength=1040,
            justify="left",
        ).grid(row=0, column=0, columnspan=6, sticky="w")

        ttk.Label(profiles, text="Сохранить как профиль").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(profiles, textvariable=self.profile_name_var, width=28).grid(
            row=1,
            column=1,
            sticky="w",
            padx=(8, 0),
            pady=(10, 0),
        )
        ttk.Button(profiles, text="Сохранить профиль", command=self._save_named_profile).grid(
            row=1,
            column=2,
            sticky="w",
            padx=(10, 0),
            pady=(10, 0),
        )

        ttk.Label(profiles, text="Доступные профили").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.profile_combo = ttk.Combobox(
            profiles,
            textvariable=self.profile_choice_var,
            values=[],
            state="readonly",
            width=28,
        )
        self.profile_combo.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Button(profiles, text="Обновить список", command=self._refresh_profile_list).grid(
            row=2,
            column=2,
            sticky="w",
            padx=(10, 0),
            pady=(10, 0),
        )
        ttk.Button(profiles, text="Загрузить профиль", command=self._load_selected_profile).grid(
            row=2,
            column=3,
            sticky="w",
            padx=(10, 0),
            pady=(10, 0),
        )
        ttk.Button(profiles, text="Удалить профиль", command=self._delete_selected_profile).grid(
            row=2,
            column=4,
            sticky="w",
            padx=(10, 0),
            pady=(10, 0),
        )
        ttk.Button(profiles, text="Открыть папку профилей", command=self._open_profile_dir).grid(
            row=2,
            column=5,
            sticky="e",
            pady=(10, 0),
        )

        ttk.Button(profiles, text="Сравнить с текущим", command=self._compare_selected_profile).grid(
            row=3,
            column=0,
            sticky="w",
            pady=(10, 0),
        )
        ttk.Button(profiles, text="Сбросить сравнение", command=self._clear_profile_comparison).grid(
            row=3,
            column=1,
            sticky="w",
            padx=(8, 0),
            pady=(10, 0),
        )
        ttk.Label(
            profiles,
            textvariable=self.compare_summary_var,
            foreground="#7a4f01",
            wraplength=760,
            justify="left",
        ).grid(row=3, column=2, columnspan=4, sticky="w", padx=(16, 0), pady=(10, 0))

        ttk.Label(
            profiles,
            textvariable=self.profile_hint_var,
            foreground="#555555",
            wraplength=1040,
            justify="left",
        ).grid(row=4, column=0, columnspan=6, sticky="w", pady=(10, 0))

        snapshots = ttk.LabelFrame(profiles, text="Снимки перед запуском", padding=10)
        snapshots.grid(row=5, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        snapshots.columnconfigure(5, weight=1)

        ttk.Checkbutton(
            snapshots,
            text="Автоматически сохранять снимок перед запуском",
            variable=self.snapshot_before_run_var,
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(
            snapshots,
            text=(
                "Снимок — это отдельная сохранённая точка текущей конфигурации перед quick/detail run. "
                "Она не заменяет профиль и не зависит от короткой undo-истории."
            ),
            wraplength=760,
            justify="left",
        ).grid(row=0, column=3, columnspan=3, sticky="w", padx=(16, 0))

        ttk.Label(snapshots, text="Имя снимка").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(snapshots, textvariable=self.snapshot_name_var, width=28).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0)
        )
        ttk.Button(snapshots, text="Сохранить снимок", command=self._save_named_snapshot).grid(
            row=1, column=2, sticky="w", padx=(10, 0), pady=(10, 0)
        )

        ttk.Label(snapshots, text="Доступные снимки").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.snapshot_combo = ttk.Combobox(
            snapshots,
            textvariable=self.snapshot_choice_var,
            values=[],
            state="readonly",
            width=36,
        )
        self.snapshot_combo.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Button(snapshots, text="Обновить список", command=self._refresh_snapshot_list).grid(
            row=2, column=2, sticky="w", padx=(10, 0), pady=(10, 0)
        )
        ttk.Button(snapshots, text="Загрузить снимок", command=self._load_selected_snapshot).grid(
            row=2, column=3, sticky="w", padx=(10, 0), pady=(10, 0)
        )
        ttk.Button(snapshots, text="Открыть папку снимков", command=self._open_snapshot_dir).grid(
            row=2, column=5, sticky="e", pady=(10, 0)
        )

        ttk.Label(
            snapshots,
            textvariable=self.snapshot_hint_var,
            foreground="#555555",
            wraplength=1040,
            justify="left",
        ).grid(row=3, column=0, columnspan=6, sticky="w", pady=(10, 0))

        diff_frame = ttk.LabelFrame(profiles, text="Что изменилось по секциям", padding=8)
        diff_frame.grid(row=6, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        diff_frame.columnconfigure(0, weight=1)
        diff_frame.rowconfigure(0, weight=1)

        self.compare_tree = ttk.Treeview(
            diff_frame,
            columns=("current", "reference"),
            show="tree headings",
            height=7,
        )
        self.compare_tree.heading("#0", text="Параметр")
        self.compare_tree.heading("current", text="Текущее")
        self.compare_tree.heading("reference", text="Профиль")
        self.compare_tree.column("#0", width=360, stretch=True)
        self.compare_tree.column("current", width=180, stretch=True, anchor="w")
        self.compare_tree.column("reference", width=180, stretch=True, anchor="w")
        self.compare_tree.grid(row=0, column=0, sticky="nsew")

        compare_scroll = ttk.Scrollbar(
            diff_frame,
            orient="vertical",
            command=self.compare_tree.yview,
        )
        compare_scroll.grid(row=0, column=1, sticky="ns")
        self.compare_tree.configure(yscrollcommand=compare_scroll.set)

        config_frame = ttk.LabelFrame(outer, text="Сводка конфигурации перед запуском", padding=10)
        config_frame.pack(fill="x", pady=(12, 0))
        ttk.Label(
            config_frame,
            textvariable=self.config_summary_var,
            wraplength=1040,
            justify="left",
            foreground="#334455",
        ).pack(anchor="w")

        preset_frame = ttk.LabelFrame(outer, text="Быстрые пресеты", padding=10)
        preset_frame.pack(fill="x", pady=(12, 0))
        for col in range(3):
            preset_frame.columnconfigure(col, weight=1)
        ttk.Label(
            preset_frame,
            text=(
                "Это быстрые инженерные сдвиги в один клик. Они не заменяют точную настройку, "
                "но помогают быстро сделать систему мягче, жёстче или изменить расчётный режим."
            ),
            wraplength=1040,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        for idx, (preset_key, preset_label_text, _preset_desc) in enumerate(DESKTOP_QUICK_PRESET_OPTIONS):
            row = 1 + idx // 3
            col = idx % 3
            ttk.Button(
                preset_frame,
                text=preset_label_text,
                command=lambda key=preset_key: self._apply_quick_preset(key),
            ).grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0), pady=(10, 0))

        ttk.Label(
            preset_frame,
            textvariable=self.quick_preset_hint_var,
            foreground="#555555",
            wraplength=1040,
            justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        history_frame = ttk.LabelFrame(outer, text="История последних действий", padding=10)
        history_frame.pack(fill="x", pady=(12, 0))
        history_frame.columnconfigure(0, weight=1)
        history_frame.columnconfigure(1, weight=0)

        self.history_listbox = tk.Listbox(history_frame, height=4, activestyle="none")
        self.history_listbox.grid(row=0, column=0, sticky="ew")
        history_scroll = ttk.Scrollbar(
            history_frame,
            orient="vertical",
            command=self.history_listbox.yview,
        )
        history_scroll.grid(row=0, column=1, sticky="ns")
        self.history_listbox.configure(yscrollcommand=history_scroll.set)

        ttk.Button(
            history_frame,
            text="Отменить последнее действие",
            command=self._undo_last_safe_action,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Label(
            history_frame,
            textvariable=self.undo_hint_var,
            foreground="#555555",
            wraplength=1040,
            justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        actions = ttk.LabelFrame(outer, text="Проверка и расчёт", padding=10)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Label(
            actions,
            text=(
                "Здесь можно сразу проверить конфигурацию и сделать короткий preview-расчёт "
                "по текущим исходным данным, не переходя в WEB UI. "
                "Профиль preview-дороги выбирается прямо здесь."
            ),
            wraplength=1040,
            justify="left",
        ).grid(row=0, column=0, columnspan=6, sticky="w")
        ttk.Label(actions, text="Шаг preview dt, с").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Spinbox(actions, from_=0.001, to=0.1, increment=0.001, textvariable=self.preview_dt_var, width=10, format="%.3f").grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Label(actions, text="Длительность preview, с").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(10, 0))
        ttk.Spinbox(actions, from_=0.2, to=60.0, increment=0.1, textvariable=self.preview_t_end_var, width=10, format="%.1f").grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Label(actions, text="Длина участка, м").grid(row=1, column=4, sticky="w", padx=(16, 0), pady=(10, 0))
        ttk.Spinbox(actions, from_=5.0, to=5000.0, increment=1.0, textvariable=self.preview_road_len_var, width=10, format="%.1f").grid(row=1, column=5, sticky="w", padx=(8, 0), pady=(10, 0))

        surface_frame = ttk.LabelFrame(actions, text="Профиль preview-дороги", padding=10)
        surface_frame.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        surface_frame.columnconfigure(5, weight=1)

        ttk.Label(surface_frame, text="Тип профиля").grid(row=0, column=0, sticky="w")
        preview_combo = ttk.Combobox(
            surface_frame,
            textvariable=self.preview_surface_var,
            values=[label for _key, label in DESKTOP_PREVIEW_SURFACE_OPTIONS],
            state="readonly",
            width=28,
        )
        preview_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.preview_surface_var.trace_add(
            "write",
            lambda *_args: self._refresh_preview_surface_controls(),
        )
        ttk.Label(
            surface_frame,
            textvariable=self.preview_surface_summary_var,
            foreground="#555555",
            wraplength=760,
            justify="left",
        ).grid(row=0, column=2, columnspan=4, sticky="w", padx=(16, 0))

        ttk.Label(surface_frame, textvariable=self.preview_surface_primary_label_var).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(10, 0),
        )
        self.preview_surface_primary_spin = ttk.Spinbox(
            surface_frame,
            from_=0.0,
            to=2.0,
            increment=0.005,
            textvariable=self.preview_surface_primary_value_var,
            width=10,
            format="%.3f",
        )
        self.preview_surface_primary_spin.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(surface_frame, textvariable=self.preview_surface_secondary_label_var).grid(
            row=1,
            column=2,
            sticky="w",
            padx=(16, 0),
            pady=(10, 0),
        )
        self.preview_surface_secondary_spin = ttk.Spinbox(
            surface_frame,
            from_=0.01,
            to=50.0,
            increment=0.05,
            textvariable=self.preview_surface_secondary_value_var,
            width=10,
            format="%.3f",
        )
        self.preview_surface_secondary_spin.grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(surface_frame, text="Начало профиля, м").grid(
            row=1,
            column=4,
            sticky="w",
            padx=(16, 0),
            pady=(10, 0),
        )
        self.preview_surface_start_spin = ttk.Spinbox(
            surface_frame,
            from_=0.0,
            to=500.0,
            increment=0.1,
            textvariable=self.preview_surface_start_var,
            width=10,
            format="%.2f",
        )
        self.preview_surface_start_spin.grid(row=1, column=5, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(surface_frame, text="Угол гребня, град").grid(
            row=2,
            column=0,
            sticky="w",
            pady=(10, 0),
        )
        self.preview_surface_angle_spin = ttk.Spinbox(
            surface_frame,
            from_=-90.0,
            to=90.0,
            increment=1.0,
            textvariable=self.preview_surface_angle_var,
            width=10,
            format="%.1f",
        )
        self.preview_surface_angle_spin.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(surface_frame, text="Коэффициент формы").grid(
            row=2,
            column=2,
            sticky="w",
            padx=(16, 0),
            pady=(10, 0),
        )
        self.preview_surface_shape_spin = ttk.Spinbox(
            surface_frame,
            from_=0.1,
            to=10.0,
            increment=0.1,
            textvariable=self.preview_surface_shape_var,
            width=10,
            format="%.2f",
        )
        self.preview_surface_shape_spin.grid(row=2, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        run_frame = ttk.LabelFrame(actions, text="Настройки запуска расчёта", padding=10)
        run_frame.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        run_frame.columnconfigure(5, weight=1)

        ttk.Label(run_frame, text="Сценарий").grid(row=0, column=0, sticky="w")
        run_combo = ttk.Combobox(
            run_frame,
            textvariable=self.run_scenario_var,
            values=list(self.run_scenario_key_to_label.values()),
            state="readonly",
            width=30,
        )
        run_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.run_scenario_var.trace_add(
            "write",
            lambda *_args: self._refresh_run_scenario_controls(),
        )
        ttk.Label(
            run_frame,
            textvariable=self.run_summary_var,
            foreground="#555555",
            wraplength=740,
            justify="left",
        ).grid(row=0, column=2, columnspan=4, sticky="w", padx=(16, 0))

        ttk.Label(run_frame, text="Шаг dt, с").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Spinbox(
            run_frame,
            from_=0.001,
            to=0.1,
            increment=0.001,
            textvariable=self.run_dt_var,
            width=10,
            format="%.3f",
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(run_frame, text="Длительность, с").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(10, 0))
        ttk.Spinbox(
            run_frame,
            from_=0.2,
            to=60.0,
            increment=0.1,
            textvariable=self.run_t_end_var,
            width=10,
            format="%.1f",
        ).grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Checkbutton(
            run_frame,
            text="Сохранять расширенный лог (давления и потоки)",
            variable=self.run_record_full_var,
        ).grid(row=1, column=4, columnspan=2, sticky="w", padx=(16, 0), pady=(10, 0))

        ttk.Label(run_frame, textvariable=self.run_primary_label_var).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(10, 0),
        )
        self.run_primary_spin = ttk.Spinbox(
            run_frame,
            from_=0.0,
            to=50.0,
            increment=0.1,
            textvariable=self.run_primary_value_var,
            width=10,
            format="%.3f",
        )
        self.run_primary_spin.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(run_frame, textvariable=self.run_secondary_label_var).grid(
            row=2,
            column=2,
            sticky="w",
            padx=(16, 0),
            pady=(10, 0),
        )
        self.run_secondary_spin = ttk.Spinbox(
            run_frame,
            from_=0.0,
            to=50.0,
            increment=0.1,
            textvariable=self.run_secondary_value_var,
            width=10,
            format="%.3f",
        )
        self.run_secondary_spin.grid(row=2, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        run_preset_frame = ttk.LabelFrame(run_frame, text="Пресеты запуска", padding=10)
        run_preset_frame.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        for col in range(3):
            run_preset_frame.columnconfigure(col, weight=1)
        for idx, (preset_key, preset_label_text, _preset_desc) in enumerate(DESKTOP_RUN_PRESET_OPTIONS):
            ttk.Button(
                run_preset_frame,
                text=preset_label_text,
                command=lambda key=preset_key: self._apply_run_preset(key),
            ).grid(
                row=0,
                column=idx,
                sticky="ew",
                padx=(0 if idx == 0 else 8, 0),
            )
        ttk.Label(
            run_preset_frame,
            textvariable=self.run_mode_summary_var,
            foreground="#334455",
            wraplength=1040,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(
            run_preset_frame,
            textvariable=self.run_mode_cost_var,
            foreground="#6b4d00",
            wraplength=1040,
            justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            run_preset_frame,
            textvariable=self.run_mode_advice_var,
            foreground="#1f5d50",
            wraplength=1040,
            justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            run_preset_frame,
            textvariable=self.run_mode_usage_var,
            foreground="#355c7d",
            wraplength=1040,
            justify="left",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            run_preset_frame,
            textvariable=self.run_preset_hint_var,
            foreground="#555555",
            wraplength=1040,
            justify="left",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

        context_frame = ttk.LabelFrame(actions, text="Текущая рабочая точка", padding=10)
        context_frame.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        ttk.Label(
            context_frame,
            textvariable=self.run_context_var,
            wraplength=1040,
            justify="left",
            foreground="#334455",
        ).pack(anchor="w")
        context_actions = ttk.Frame(context_frame)
        context_actions.pack(fill="x", pady=(10, 0))
        ttk.Label(context_actions, text="Имя профиля для рабочей точки").grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Entry(context_actions, textvariable=self.profile_name_var, width=28).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(8, 0),
        )
        ttk.Button(
            context_actions,
            text="Сохранить рабочую точку как профиль",
            command=self._save_run_context_profile,
        ).grid(row=0, column=2, sticky="w", padx=(12, 0))

        launch_frame = ttk.LabelFrame(actions, text="Будет запущено сейчас", padding=10)
        launch_frame.grid(row=5, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        self.run_launch_label = ttk.Label(
            launch_frame,
            textvariable=self.run_launch_summary_var,
            style="DesktopLaunchBalanced.TLabel",
            wraplength=1040,
            justify="left",
        )
        self.run_launch_label.pack(anchor="w")

        ttk.Button(actions, text="Проверить конфигурацию", command=self._run_config_check).grid(row=6, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Button(actions, text="Быстрый расчёт", command=self._run_quick_preview).grid(row=6, column=2, columnspan=2, sticky="w", padx=(12, 0), pady=(12, 0))
        ttk.Button(actions, text="Запустить подробный расчёт", command=self._run_single_desktop_run).grid(row=6, column=4, columnspan=2, sticky="w", padx=(12, 0), pady=(12, 0))
        ttk.Label(
            actions,
            text="Preview использует временный worldroad-сценарий с текущей скоростью из раздела «Настройки расчёта».",
            foreground="#555555",
        ).grid(row=7, column=0, columnspan=6, sticky="w", pady=(12, 0))

        route_frame = ttk.LabelFrame(outer, text="Пошаговый маршрут настройки", padding=10)
        route_frame.pack(fill="x", pady=(12, 0))
        for col in range(4):
            route_frame.columnconfigure(col, weight=1)
        ttk.Label(
            route_frame,
            text=(
                "Быстрый маршрут помогает идти по шагам: сначала геометрия, затем пневматика, "
                "механика и в конце настройки расчёта. Это только навигация по текущему editor "
                "и не дублирует отдельные окна Animator, Compare Viewer или Mnemo."
            ),
            wraplength=1040,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w")
        for idx, title in enumerate(self.section_titles):
            button = ttk.Button(
                route_frame,
                text=f"{idx + 1}. {title}",
                command=lambda section_title=title: self._select_section_by_title(section_title),
            )
            button.grid(row=1, column=idx, sticky="ew", padx=(0 if idx == 0 else 8, 0), pady=(10, 0))
            self.route_buttons[title] = button
        ttk.Button(
            route_frame,
            text="Назад",
            command=self._go_prev_section,
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            route_frame,
            text="Далее",
            command=self._go_next_section,
        ).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Label(
            route_frame,
            textvariable=self.route_summary_var,
            foreground="#555555",
            wraplength=840,
            justify="left",
        ).grid(row=2, column=2, columnspan=2, sticky="w", padx=(16, 0), pady=(10, 0))

        search_frame = ttk.LabelFrame(outer, text="Быстрый поиск по параметрам", padding=10)
        search_frame.pack(fill="x", pady=(12, 0))
        search_frame.columnconfigure(1, weight=1)
        search_frame.columnconfigure(3, weight=1)
        ttk.Label(
            search_frame,
            text=(
                "Поиск помогает быстро перейти к нужному параметру по названию, единице измерения "
                "или описанию, не прокручивая всю форму вручную."
            ),
            wraplength=1040,
            justify="left",
        ).grid(row=0, column=0, columnspan=5, sticky="w")
        ttk.Label(search_frame, text="Найти параметр").grid(row=1, column=0, sticky="w", pady=(10, 0))
        search_entry = ttk.Entry(search_frame, textvariable=self.field_search_var, width=34)
        search_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(10, 0))
        self.field_search_var.trace_add(
            "write",
            lambda *_args: self._refresh_field_search_results(),
        )
        ttk.Label(search_frame, text="Подходящие параметры").grid(
            row=1,
            column=2,
            sticky="w",
            padx=(16, 0),
            pady=(10, 0),
        )
        self.field_search_combo = ttk.Combobox(
            search_frame,
            textvariable=self.field_search_choice_var,
            values=[],
            state="readonly",
            width=42,
        )
        self.field_search_combo.grid(row=1, column=3, sticky="ew", padx=(8, 0), pady=(10, 0))
        ttk.Button(
            search_frame,
            text="Перейти к параметру",
            command=self._jump_to_selected_field,
        ).grid(row=1, column=4, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            search_frame,
            text="Очистить поиск",
            command=self._clear_field_search,
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Label(
            search_frame,
            textvariable=self.field_search_summary_var,
            foreground="#555555",
            wraplength=940,
            justify="left",
        ).grid(row=2, column=1, columnspan=4, sticky="w", padx=(8, 0), pady=(10, 0))
        search_entry.bind("<Return>", lambda _event: self._jump_to_selected_field())
        self.field_search_combo.bind("<<ComboboxSelected>>", lambda _event: self._jump_to_selected_field())

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True, pady=(12, 0))
        self.section_notebook = notebook
        self.section_notebook.bind("<<NotebookTabChanged>>", lambda _event: self._refresh_section_route_summary())

        for section in DESKTOP_INPUT_SECTIONS:
            tab = ScrollableSection(notebook)
            notebook.add(tab, text=section.title)
            tab.body.columnconfigure(0, weight=1)
            ttk.Label(
                tab.body,
                text=section.description,
                wraplength=1000,
                justify="left",
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 10))
            ttk.Button(
                tab.body,
                text="Вернуть раздел к значениям по умолчанию",
                command=lambda sec=section: self._reset_section_to_defaults(sec),
            ).grid(row=0, column=1, sticky="e", padx=12, pady=(12, 10))

            for idx, spec in enumerate(section.fields, start=1):
                frame = ttk.LabelFrame(tab.body, text=spec.label, padding=10)
                frame.grid(row=idx, column=0, sticky="ew", padx=12, pady=8)
                frame.columnconfigure(1, weight=1)
                self._field_frames[spec.key] = frame
                self._field_tabs_by_key[spec.key] = tab
                ttk.Label(
                    frame,
                    text=spec.description,
                    wraplength=980,
                    justify="left",
                ).grid(row=0, column=0, columnspan=4, sticky="w")
                self._build_field_controls(frame, spec)

        log_frame = ttk.LabelFrame(outer, text="Журнал проверки и расчёта", padding=8)
        log_frame.pack(fill="both", expand=False, pady=(12, 0))
        self.run_log = tk.Text(log_frame, height=12, wrap="word")
        self.run_log.pack(fill="both", expand=True)
        self.run_log.configure(state="disabled")
        self._append_run_log("Editor готов. Можно менять исходные данные и сразу запускать проверку или preview-расчёт.")

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side="left", anchor="w")
        ttk.Label(
            footer,
            text="Подсказка: default_base.json не перезаписывается автоматически.",
            foreground="#555555",
        ).pack(side="right", anchor="e")

    def _build_field_controls(self, frame: ttk.LabelFrame, spec: DesktopInputFieldSpec) -> None:
        if spec.control == "bool":
            var = tk.BooleanVar(value=False)
            ttk.Checkbutton(frame, text="Включить", variable=var).grid(row=1, column=0, sticky="w", pady=(8, 0))
            value_label = ttk.Label(frame, text="")
            value_label.grid(row=1, column=3, sticky="e", pady=(8, 0))
            self.vars[spec.key] = var
            self._widget_handles[spec.key] = (spec, value_label)
            var.trace_add("write", lambda *_args, key=spec.key: self._on_field_var_changed(key))
            return

        if spec.control == "choice":
            var = tk.StringVar(value=spec.choices[0] if spec.choices else "")
            combo = ttk.Combobox(frame, textvariable=var, values=list(spec.choices), state="readonly", width=28)
            combo.grid(row=1, column=0, sticky="w", pady=(8, 0))
            value_label = ttk.Label(frame, text="")
            value_label.grid(row=1, column=3, sticky="e", pady=(8, 0))
            self.vars[spec.key] = var
            self._widget_handles[spec.key] = (spec, value_label)
            var.trace_add("write", lambda *_args, key=spec.key: self._refresh_value_label(key))
            return

        if spec.control == "int":
            var = tk.IntVar(value=int(spec.min_value or 0))
            scale = tk.Scale(
                frame,
                from_=int(spec.min_value or 0),
                to=int(spec.max_value or 100),
                resolution=int(spec.step or 1),
                orient="horizontal",
                variable=var,
                showvalue=False,
            )
            scale.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
            spin = ttk.Spinbox(
                frame,
                from_=int(spec.min_value or 0),
                to=int(spec.max_value or 100),
                increment=int(spec.step or 1),
                textvariable=var,
                width=12,
            )
            spin.grid(row=1, column=2, sticky="w", padx=(10, 0), pady=(8, 0))
            value_label = ttk.Label(frame, text="")
            value_label.grid(row=1, column=3, sticky="e", pady=(8, 0))
            self.vars[spec.key] = var
            self._widget_handles[spec.key] = (spec, value_label)
            var.trace_add("write", lambda *_args, key=spec.key: self._refresh_value_label(key))
            return

        var = tk.DoubleVar(value=float(spec.min_value or 0.0))
        scale = tk.Scale(
            frame,
            from_=float(spec.min_value or 0.0),
            to=float(spec.max_value or 1.0),
            resolution=float(spec.step or 0.01),
            orient="horizontal",
            variable=var,
            showvalue=False,
        )
        scale.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        spin = ttk.Spinbox(
            frame,
            from_=float(spec.min_value or 0.0),
            to=float(spec.max_value or 1.0),
            increment=float(spec.step or 0.01),
            textvariable=var,
            width=12,
            format=f"%.{int(spec.digits)}f",
        )
        spin.grid(row=1, column=2, sticky="w", padx=(10, 0), pady=(8, 0))
        value_label = ttk.Label(frame, text="")
        value_label.grid(row=1, column=3, sticky="e", pady=(8, 0))
        self.vars[spec.key] = var
        self._widget_handles[spec.key] = (spec, value_label)
        var.trace_add("write", lambda *_args, key=spec.key: self._on_field_var_changed(key))

    def _on_field_var_changed(self, key: str) -> None:
        self._refresh_value_label(key)
        self._refresh_config_summary()
        self._refresh_section_route_summary()
        if self.compare_target_path is not None:
            self._refresh_profile_comparison()

    def _display_source_name(self) -> str:
        path = self.current_source_path
        try:
            return path.name or str(path)
        except Exception:
            return str(path)

    def _refresh_run_context_summary(self) -> None:
        active_profile = (
            desktop_profile_display_name(self.active_profile_path)
            if self.active_profile_path is not None and self.active_profile_path.exists()
            else "не выбран"
        )
        active_snapshot = (
            desktop_snapshot_display_name(self.active_snapshot_path)
            if self.active_snapshot_path is not None and self.active_snapshot_path.exists()
            else "ещё не сохранён"
        )
        compare_profile = (
            desktop_profile_display_name(self.compare_target_path)
            if self.compare_target_path is not None and self.compare_target_path.exists()
            else "выключено"
        )
        snapshot_policy = (
            f"включён ({str(self.snapshot_name_var.get() or '').strip() or 'перед_запуском'})"
            if bool(self.snapshot_before_run_var.get())
            else "выключен"
        )
        self.run_context_var.set(
            "\n".join(
                (
                    f"Источник параметров: {self._display_source_name()}",
                    f"Активный профиль: {active_profile}",
                    f"Последний снимок: {active_snapshot}",
                    f"Сравнение с профилем: {compare_profile}",
                    f"Автоснимок перед запуском: {snapshot_policy}",
                )
            )
        )

    def _refresh_run_mode_summary(self) -> None:
        mode_info = describe_desktop_run_mode(self._gather_run_settings_snapshot())
        self.run_mode_summary_var.set(str(mode_info.get("summary") or "").strip())
        self.run_mode_cost_var.set(str(mode_info.get("cost_summary") or "").strip())
        self.run_mode_advice_var.set(str(mode_info.get("advice_summary") or "").strip())
        self.run_mode_usage_var.set(str(mode_info.get("usage_summary") or "").strip())

    def _refresh_run_launch_summary(self) -> None:
        snapshot_enabled = bool(self.snapshot_before_run_var.get())
        snapshot_base_name = str(self.snapshot_name_var.get() or "").strip() or "перед_запуском"
        snapshot_summary = (
            f"автоснимок включён ({snapshot_base_name})"
            if snapshot_enabled
            else "автоснимок выключен"
        )
        quick_surface = preview_surface_label(self._selected_preview_surface_key())
        quick_summary = (
            f"Быстрый расчёт: дорожный preview «{quick_surface}», "
            f"dt={float(self.preview_dt_var.get()):.3f} с, "
            f"длительность={float(self.preview_t_end_var.get()):.1f} с, "
            f"участок={float(self.preview_road_len_var.get()):.1f} м, {snapshot_summary}."
        )
        run_mode = describe_desktop_run_mode(self._gather_run_settings_snapshot())
        scenario_label = self._selected_run_scenario_label()
        road_part = ""
        if self._selected_run_scenario_key() == "worldroad":
            road_part = f", профиль дороги «{quick_surface}»"
        detail_summary = (
            f"Подробный расчёт: {scenario_label}{road_part}, "
            f"режим {str(run_mode.get('mode_label') or '').strip()}, "
            f"{str(run_mode.get('cost_label') or '').strip()}, {snapshot_summary}."
        )
        self.run_launch_summary_var.set(f"{quick_summary}\n{detail_summary}")

    def _refresh_value_label(self, key: str) -> None:
        handle = self._widget_handles.get(key)
        var = self.vars.get(key)
        if handle is None or var is None:
            return
        spec, label = handle
        try:
            value = var.get()
        except Exception:
            value = ""
        if spec.control == "bool":
            text = "включено" if bool(value) else "выключено"
        elif spec.control == "choice":
            text = f"{value}"
        elif spec.control == "int":
            text = f"{int(value)} {spec.unit_label}".strip()
        else:
            text = f"{float(value):.{int(spec.digits)}f} {spec.unit_label}".strip()
        if key in self.compare_diffs_by_key:
            label.configure(text=f"{text} · изменено", foreground="#a05a00")
        else:
            label.configure(text=text, foreground="#2f4f4f")

    def _bind_summary_var_traces(self) -> None:
        tracked_vars = (
            self.preview_dt_var,
            self.preview_t_end_var,
            self.preview_road_len_var,
            self.snapshot_before_run_var,
            self.snapshot_name_var,
            self.preview_surface_primary_value_var,
            self.preview_surface_secondary_value_var,
            self.preview_surface_start_var,
            self.preview_surface_angle_var,
            self.preview_surface_shape_var,
            self.run_dt_var,
            self.run_t_end_var,
            self.run_record_full_var,
            self.run_primary_value_var,
            self.run_secondary_value_var,
        )
        for var in tracked_vars:
            var.trace_add("write", lambda *_args: self._refresh_config_summary())
            var.trace_add("write", lambda *_args: self._refresh_run_context_summary())
            var.trace_add("write", lambda *_args: self._refresh_run_mode_summary())
            var.trace_add("write", lambda *_args: self._refresh_run_launch_summary())

    def _safe_current_base_float(self, key: str, default: float = 0.0) -> float:
        spec_var = self.vars.get(key)
        spec_handle = self._widget_handles.get(key)
        if spec_var is None or spec_handle is None:
            return float(default)
        spec, _label = spec_handle
        try:
            return float(spec.to_base(spec_var.get()))
        except Exception:
            return float(default)

    def _selected_run_scenario_label(self) -> str:
        return self.run_scenario_key_to_label.get(
            self._selected_run_scenario_key(),
            self._selected_run_scenario_key(),
        )

    def _refresh_config_summary(self) -> None:
        mass_frame = self._safe_current_base_float("масса_рамы")
        mass_unsprung = self._safe_current_base_float("масса_неподрессоренная_на_угол")
        stroke_m = self._safe_current_base_float("ход_штока")
        wheel_radius_m = self._safe_current_base_float("радиус_колеса_м")
        vx0 = self._safe_current_base_float("vx0_м_с")
        pressure_keys = (
            "начальное_давление_Ресивер1",
            "начальное_давление_Ресивер2",
            "начальное_давление_Ресивер3",
            "начальное_давление_аккумулятора",
        )
        pressures_kpa = [
            self._safe_current_base_float(key) * 0.001
            for key in pressure_keys
        ]
        preview_label = preview_surface_label(self._selected_preview_surface_key())
        run_label = self._selected_run_scenario_label()
        lines = [
            (
                f"Массы: рама {mass_frame:.1f} кг; неподрессоренная масса на угол {mass_unsprung:.1f} кг."
            ),
            (
                "Давления на старте: "
                f"Р1 {pressures_kpa[0]:.1f} кПа, "
                f"Р2 {pressures_kpa[1]:.1f} кПа, "
                f"Р3 {pressures_kpa[2]:.1f} кПа, "
                f"аккумулятор {pressures_kpa[3]:.1f} кПа."
            ),
            (
                f"Ход штока {stroke_m * 1000.0:.0f} мм; "
                f"радиус колеса {wheel_radius_m * 1000.0:.0f} мм; "
                f"начальная скорость {vx0:.2f} м/с."
            ),
            (
                f"Preview: {preview_label}; dt={float(self.preview_dt_var.get()):.3f} с; "
                f"длительность={float(self.preview_t_end_var.get()):.1f} с; "
                f"длина участка={float(self.preview_road_len_var.get()):.1f} м."
            ),
            (
                f"Подробный расчёт: {run_label}; dt={float(self.run_dt_var.get()):.3f} с; "
                f"длительность={float(self.run_t_end_var.get()):.1f} с; "
                f"расширенный лог={'включён' if bool(self.run_record_full_var.get()) else 'выключен'}."
            ),
        ]
        self.config_summary_var.set("\n".join(lines))

    def _append_run_log(self, text: str) -> None:
        self.run_log.configure(state="normal")
        self.run_log.insert("end", text.rstrip() + "\n")
        self.run_log.see("end")
        self.run_log.configure(state="disabled")

    def _refresh_safe_action_history_view(self) -> None:
        self.history_listbox.delete(0, "end")
        if not self._safe_action_history:
            self.history_listbox.insert("end", "История пока пуста.")
            return
        for item in reversed(self._safe_action_history[-6:]):
            label = str(item.get("label") or "Без названия")
            changed_count = int(item.get("changed_count") or 0)
            if changed_count > 0:
                self.history_listbox.insert(
                    "end",
                    f"{label} · изменено параметров: {changed_count}",
                )
            else:
                self.history_listbox.insert("end", label)

    def _gather_run_settings_snapshot(self) -> dict[str, object]:
        return {
            "scenario_key": self._selected_run_scenario_key(),
            "dt": float(self.run_dt_var.get()),
            "t_end": float(self.run_t_end_var.get()),
            "record_full": bool(self.run_record_full_var.get()),
            "primary_value": float(self.run_primary_value_var.get()),
            "secondary_value": float(self.run_secondary_value_var.get()),
        }

    def _restore_run_settings_snapshot(self, snapshot: dict[str, object] | None) -> None:
        if not snapshot:
            return
        scenario_key = str(snapshot.get("scenario_key") or "").strip()
        if scenario_key and scenario_key in self.run_scenario_key_to_label:
            self.run_scenario_var.set(self.run_scenario_key_to_label[scenario_key])
        try:
            self.run_dt_var.set(float(snapshot.get("dt", self.run_dt_var.get())))
        except Exception:
            pass
        try:
            self.run_t_end_var.set(float(snapshot.get("t_end", self.run_t_end_var.get())))
        except Exception:
            pass
        try:
            self.run_record_full_var.set(bool(snapshot.get("record_full", self.run_record_full_var.get())))
        except Exception:
            pass
        try:
            self.run_primary_value_var.set(float(snapshot.get("primary_value", self.run_primary_value_var.get())))
        except Exception:
            pass
        try:
            self.run_secondary_value_var.set(float(snapshot.get("secondary_value", self.run_secondary_value_var.get())))
        except Exception:
            pass
        self._refresh_run_scenario_controls()

    def _remember_safe_action(
        self,
        label: str,
        payload_snapshot: dict[str, object],
        *,
        changed_count: int = 0,
        run_settings_snapshot: dict[str, object] | None = None,
    ) -> None:
        self._safe_action_history.append(
            {
                "label": str(label or "Без названия"),
                "payload": dict(payload_snapshot or {}),
                "run_settings": dict(run_settings_snapshot or self._gather_run_settings_snapshot()),
                "changed_count": int(changed_count),
            }
        )
        if len(self._safe_action_history) > 12:
            self._safe_action_history = self._safe_action_history[-12:]
        self.undo_hint_var.set(
            f"Можно отменить: {label}"
            + (
                f" (изменено параметров: {int(changed_count)})"
                if int(changed_count) > 0
                else ""
            )
        )
        self._refresh_safe_action_history_view()

    def _undo_last_safe_action(self) -> None:
        if not self._safe_action_history:
            messagebox.showinfo(
                "Desktop Input Editor",
                "В истории пока нет безопасных действий для отмены.",
            )
            return
        action = self._safe_action_history.pop()
        payload = dict(action.get("payload") or {})
        run_settings = dict(action.get("run_settings") or {})
        label = str(action.get("label") or "последнее действие")
        self._load_into_vars(payload, self.current_source_path)
        self._restore_run_settings_snapshot(run_settings)
        if self._safe_action_history:
            last_label = str(self._safe_action_history[-1].get("label") or "").strip()
            self.undo_hint_var.set(
                f"Последнее действие отменено: {label}."
                + (f" Следующим можно отменить: {last_label}" if last_label else "")
            )
        else:
            self.undo_hint_var.set(
                f"Последнее действие отменено: {label}. История безопасных действий пуста."
            )
        self._refresh_safe_action_history_view()
        self._set_status(f"Отменено действие: {label}")
        self._append_run_log(f"[undo] Отменено действие: {label}")

    def _apply_quick_preset(self, preset_key: str) -> None:
        before_payload = self._gather_payload()
        updated, changed_keys = apply_desktop_quick_preset(before_payload, preset_key)
        label = quick_preset_label(preset_key)
        description = quick_preset_description(preset_key)
        if not changed_keys:
            self.quick_preset_hint_var.set(
                f"Пресет «{label}» не изменил ни одного параметра."
            )
            self._set_status(f"Пресет «{label}» не внёс изменений.")
            return
        self._remember_safe_action(
            f"Пресет: {label}",
            before_payload,
            changed_count=len(changed_keys),
        )
        for key in changed_keys:
            handle = self._widget_handles.get(key)
            var = self.vars.get(key)
            if handle is None or var is None:
                continue
            spec, _label = handle
            try:
                var.set(spec.to_ui(updated.get(key)))
            except Exception:
                continue
            self._refresh_value_label(key)
        self.current_payload = dict(updated)
        self._refresh_config_summary()
        self._refresh_profile_comparison()
        self.quick_preset_hint_var.set(
            f"Пресет «{label}» применён. {description} Изменено параметров: {len(changed_keys)}."
        )
        self._set_status(f"Применён быстрый пресет: {label}")
        self._append_run_log(
            f"[quick-preset] {label}: изменено параметров {len(changed_keys)}"
        )

    def _apply_run_preset(self, preset_key: str) -> None:
        before_payload = self._gather_payload()
        before_run = self._gather_run_settings_snapshot()
        updated, changed_keys = apply_desktop_run_preset(
            before_run,
            preset_key,
            scenario_key=self._selected_run_scenario_key(),
        )
        label = run_preset_label(preset_key)
        description = run_preset_description(preset_key)
        if not changed_keys:
            self.run_preset_hint_var.set(
                f"Пресет запуска «{label}» не изменил настройки расчёта."
            )
            self._set_status(f"Пресет запуска «{label}» не внёс изменений.")
            return
        self._remember_safe_action(
            f"Пресет запуска: {label}",
            before_payload,
            changed_count=len(changed_keys),
            run_settings_snapshot=before_run,
        )
        self.run_dt_var.set(float(updated.get("dt", self.run_dt_var.get())))
        self.run_t_end_var.set(float(updated.get("t_end", self.run_t_end_var.get())))
        self.run_record_full_var.set(bool(updated.get("record_full", self.run_record_full_var.get())))
        self._refresh_config_summary()
        self.run_preset_hint_var.set(
            f"Пресет запуска «{label}» применён. {description} Изменено настроек: {len(changed_keys)}."
        )
        self._set_status(f"Применён пресет запуска: {label}")
        self._append_run_log(
            f"[run-preset] {label}: изменено настроек расчёта {len(changed_keys)}"
        )

    def _profile_paths_by_label(self) -> dict[str, Path]:
        return {
            desktop_profile_display_name(path): path
            for path in list_desktop_profile_paths()
        }

    def _snapshot_paths_by_label(self) -> dict[str, Path]:
        return {
            desktop_snapshot_display_name(path): path
            for path in list_desktop_snapshot_paths()
        }

    def _refresh_profile_list(self) -> None:
        paths_by_label = self._profile_paths_by_label()
        labels = sorted(paths_by_label.keys(), key=str.lower)
        self.profile_combo.configure(values=labels if labels else ["—"])
        current = str(self.profile_choice_var.get() or "").strip()
        if labels:
            self.profile_choice_var.set(current if current in labels else labels[0])
            self.profile_hint_var.set(
                f"Папка профилей: {desktop_profile_dir_path()} | доступно профилей: {len(labels)}"
            )
        else:
            self.profile_choice_var.set("—")
            self.profile_hint_var.set(
                f"Папка профилей: {desktop_profile_dir_path()} | пока нет сохранённых профилей."
            )
        if self.active_profile_path is not None and not self.active_profile_path.exists():
            self.active_profile_path = None
        if self.compare_target_path is not None and not self.compare_target_path.exists():
            self._clear_profile_comparison()
        self._refresh_run_context_summary()

    def _selected_profile_path(self) -> Path | None:
        label = str(self.profile_choice_var.get() or "").strip()
        if not label or label == "—":
            return None
        return self._profile_paths_by_label().get(label)

    def _refresh_snapshot_list(self) -> None:
        paths_by_label = self._snapshot_paths_by_label()
        labels = list(paths_by_label.keys())
        self.snapshot_combo.configure(values=labels if labels else ["—"])
        current = str(self.snapshot_choice_var.get() or "").strip()
        if labels:
            self.snapshot_choice_var.set(current if current in labels else labels[0])
            self.snapshot_hint_var.set(
                f"Папка снимков: {desktop_snapshot_dir_path()} | доступно снимков: {len(labels)}"
            )
        else:
            self.snapshot_choice_var.set("—")
            self.snapshot_hint_var.set(
                f"Папка снимков: {desktop_snapshot_dir_path()} | снимков пока нет."
            )
        if self.active_snapshot_path is not None and not self.active_snapshot_path.exists():
            self.active_snapshot_path = None
        self._refresh_run_context_summary()

    def _selected_snapshot_path(self) -> Path | None:
        label = str(self.snapshot_choice_var.get() or "").strip()
        if not label or label == "—":
            return None
        return self._snapshot_paths_by_label().get(label)

    def _suggest_run_context_profile_name(self) -> str:
        raw_name = str(self.profile_name_var.get() or "").strip()
        if raw_name:
            return raw_name
        if self.active_snapshot_path is not None:
            snapshot_stem = self.active_snapshot_path.stem
            return snapshot_stem.split("__", 1)[-1] or "рабочая_точка"
        if self.active_profile_path is not None:
            return self.active_profile_path.stem or "рабочая_точка"
        source_stem = str(self.current_source_path.stem or "").strip()
        return source_stem or "рабочая_точка"

    def _save_profile_payload(self, raw_name: str) -> Path:
        payload = self._gather_payload()
        target = save_desktop_profile(raw_name, payload)
        self.active_profile_path = target.resolve()
        self._refresh_profile_list()
        self.profile_choice_var.set(desktop_profile_display_name(target))
        self._refresh_run_context_summary()
        return target

    def _save_snapshot(self, base_name: str) -> Path:
        payload = self._gather_payload()
        target = save_desktop_snapshot(base_name, payload)
        self.active_snapshot_path = target.resolve()
        self._refresh_snapshot_list()
        self.snapshot_choice_var.set(desktop_snapshot_display_name(target))
        self.snapshot_name_var.set(base_name)
        self._append_run_log(f"[snapshot] Сохранён снимок: {target}")
        self._refresh_run_context_summary()
        return target

    def _save_named_snapshot(self) -> None:
        raw_name = str(self.snapshot_name_var.get() or "").strip()
        if not raw_name:
            messagebox.showinfo("Desktop Input Editor", "Введите имя снимка перед сохранением.")
            return
        try:
            target = self._save_snapshot(raw_name)
            self._set_status(f"Снимок сохранён: {target.name}")
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось сохранить снимок:\n{exc}")

    def _load_selected_snapshot(self) -> None:
        target = self._selected_snapshot_path()
        if target is None:
            messagebox.showinfo("Desktop Input Editor", "Сначала выберите снимок для загрузки.")
            return
        try:
            payload = load_desktop_snapshot(target)
            merged = load_base_with_defaults()
            merged.update(payload)
            self.active_snapshot_path = target.resolve()
            self._load_into_vars(merged, self.current_source_path)
            self.snapshot_name_var.set(target.stem.split("__", 1)[-1])
            self._set_status(f"Загружен снимок: {target.name}")
            self._append_run_log(f"[snapshot] Загружен снимок: {target}")
            self._refresh_run_context_summary()
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось загрузить снимок:\n{exc}")

    def _open_snapshot_dir(self) -> None:
        root = desktop_snapshot_dir_path()
        root.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(root))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(root)])
            else:
                subprocess.Popen(["xdg-open", str(root)])
            self._set_status(f"Открыта папка снимков: {root}")
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось открыть папку снимков:\n{exc}")

    def _autosave_snapshot_before_run(self, run_label: str) -> None:
        if not bool(self.snapshot_before_run_var.get()):
            return
        base_name = str(self.snapshot_name_var.get() or "").strip() or "перед_запуском"
        try:
            target = self._save_snapshot(f"{base_name}_{run_label}")
            self._set_status(f"Снимок сохранён перед запуском: {target.name}")
        except Exception as exc:
            self._append_run_log(f"[snapshot] Не удалось сохранить снимок перед запуском: {exc}")

    def _profile_payload_with_defaults(self, path: Path) -> dict[str, object]:
        payload = load_base_with_defaults()
        payload.update(load_desktop_profile(path))
        return payload

    def _clear_profile_diff_tree(self) -> None:
        for item_id in self.compare_tree.get_children():
            self.compare_tree.delete(item_id)

    def _format_compare_base_value(self, spec: DesktopInputFieldSpec, base_value: object) -> str:
        try:
            ui_value = spec.to_ui(base_value)
        except Exception:
            ui_value = base_value
        try:
            if spec.control == "bool":
                return "включено" if bool(ui_value) else "выключено"
            if spec.control == "choice":
                return str(ui_value or "—")
            if spec.control == "int":
                return f"{int(ui_value)} {spec.unit_label}".strip()
            return f"{float(ui_value):.{int(spec.digits)}f} {spec.unit_label}".strip()
        except Exception:
            text = str(base_value).strip()
            return text or "—"

    def _refresh_profile_diff_tree(self) -> None:
        self._clear_profile_diff_tree()
        if not self.compare_diffs_by_key:
            self.compare_tree.insert(
                "",
                "end",
                text="Сравнение не активно или отличий нет",
                values=("—", "—"),
            )
            return

        section_nodes: dict[str, str] = {}
        for diff in self.compare_diffs_by_key.values():
            key = str(diff.get("key") or "")
            handle = self._widget_handles.get(key)
            if handle is None:
                continue
            spec, _label = handle
            section_title = self._section_title_by_key.get(key, "Прочее")
            parent_id = section_nodes.get(section_title)
            if parent_id is None:
                parent_id = self.compare_tree.insert(
                    "",
                    "end",
                    text=section_title,
                    values=(f"{sum(1 for item in self.compare_diffs_by_key.values() if self._section_title_by_key.get(str(item.get('key') or ''), 'Прочее') == section_title)} отличий", ""),
                    open=True,
                )
                section_nodes[section_title] = parent_id
            self.compare_tree.insert(
                parent_id,
                "end",
                text=str(diff.get("label") or key),
                values=(
                    self._format_compare_base_value(spec, diff.get("current")),
                    self._format_compare_base_value(spec, diff.get("reference")),
                ),
            )

    def _refresh_profile_comparison(self) -> None:
        target = self.compare_target_path
        if target is None:
            self.compare_diffs_by_key = {}
            self.compare_summary_var.set("Сравнение с профилем выключено.")
            self._refresh_profile_diff_tree()
            for key in self._widget_handles:
                self._refresh_value_label(key)
            self._refresh_run_context_summary()
            return
        try:
            reference_payload = self._profile_payload_with_defaults(target)
        except Exception as exc:
            self.compare_diffs_by_key = {}
            self.compare_summary_var.set(f"Не удалось прочитать профиль для сравнения: {exc}")
            self._refresh_profile_diff_tree()
            for key in self._widget_handles:
                self._refresh_value_label(key)
            self._refresh_run_context_summary()
            return

        diffs = build_desktop_profile_diff(self._gather_payload(), reference_payload)
        self.compare_diffs_by_key = {str(item.get('key') or ''): item for item in diffs}
        display_name = desktop_profile_display_name(target)
        if diffs:
            preview_names = ", ".join(str(item.get("label") or "") for item in diffs[:4]).strip(", ")
            suffix = "" if len(diffs) <= 4 else f" и ещё {len(diffs) - 4}"
            self.compare_summary_var.set(
                f"Сравнение с профилем «{display_name}»: изменено параметров: {len(diffs)}"
                + (f" ({preview_names}{suffix})." if preview_names else ".")
            )
        else:
            self.compare_summary_var.set(
                f"Сравнение с профилем «{display_name}»: отличий нет."
            )
        self._refresh_profile_diff_tree()
        for key in self._widget_handles:
            self._refresh_value_label(key)
        self._refresh_run_context_summary()

    def _compare_selected_profile(self) -> None:
        target = self._selected_profile_path()
        if target is None:
            messagebox.showinfo("Desktop Input Editor", "Сначала выберите профиль для сравнения.")
            return
        self.compare_target_path = target.resolve()
        self._refresh_profile_comparison()
        self._set_status(f"Включено сравнение с профилем: {target.name}")

    def _clear_profile_comparison(self) -> None:
        self.compare_target_path = None
        self._refresh_profile_comparison()
        self._set_status("Сравнение с профилем отключено.")

    def _selected_preview_surface_key(self) -> str:
        raw_value = str(self.preview_surface_var.get() or "").strip()
        if raw_value in self.preview_surface_label_to_key:
            return self.preview_surface_label_to_key[raw_value]
        if raw_value in self.preview_surface_key_to_label:
            return raw_value
        return "flat"

    def _set_spinbox_state(self, widget: ttk.Spinbox, enabled: bool) -> None:
        widget.configure(state="normal" if enabled else "disabled")

    def _refresh_preview_surface_controls(self) -> None:
        surface_key = self._selected_preview_surface_key()
        if surface_key == "sine_x":
            self.preview_surface_primary_label_var.set("Амплитуда, м")
            self.preview_surface_secondary_label_var.set("Длина волны, м")
            self.preview_surface_summary_var.set(
                "Синусоидальная неровность вдоль движения. Удобно для быстрой проверки резонансов и плавности хода."
            )
            self._set_spinbox_state(self.preview_surface_primary_spin, True)
            self._set_spinbox_state(self.preview_surface_secondary_spin, True)
            self._set_spinbox_state(self.preview_surface_start_spin, False)
            self._set_spinbox_state(self.preview_surface_angle_spin, False)
            self._set_spinbox_state(self.preview_surface_shape_spin, False)
            self._refresh_config_summary()
            return
        if surface_key == "bump":
            self.preview_surface_primary_label_var.set("Высота, м")
            self.preview_surface_secondary_label_var.set("Ширина, м")
            self.preview_surface_summary_var.set(
                "Одиночный бугор на заданной позиции. Подходит для локальной проверки удара и хода подвески."
            )
            self._set_spinbox_state(self.preview_surface_primary_spin, True)
            self._set_spinbox_state(self.preview_surface_secondary_spin, True)
            self._set_spinbox_state(self.preview_surface_start_spin, True)
            self._set_spinbox_state(self.preview_surface_angle_spin, False)
            self._set_spinbox_state(self.preview_surface_shape_spin, False)
            self._refresh_config_summary()
            return
        if surface_key == "ridge_cosine_bump":
            self.preview_surface_primary_label_var.set("Высота, м")
            self.preview_surface_secondary_label_var.set("Ширина, м")
            self.preview_surface_summary_var.set(
                "Косинусный бугор под углом. Удобен для оценки диагональной нагрузки и мягкости входа на препятствие."
            )
            self._set_spinbox_state(self.preview_surface_primary_spin, True)
            self._set_spinbox_state(self.preview_surface_secondary_spin, True)
            self._set_spinbox_state(self.preview_surface_start_spin, True)
            self._set_spinbox_state(self.preview_surface_angle_spin, True)
            self._set_spinbox_state(self.preview_surface_shape_spin, True)
            self._refresh_config_summary()
            return
        self.preview_surface_primary_label_var.set("Высота профиля, м")
        self.preview_surface_secondary_label_var.set("Ширина/шаг, м")
        self.preview_surface_summary_var.set(
            "Ровная дорога без дополнительных неровностей. Подходит для быстрой проверки исходной конфигурации."
        )
        self._set_spinbox_state(self.preview_surface_primary_spin, False)
        self._set_spinbox_state(self.preview_surface_secondary_spin, False)
        self._set_spinbox_state(self.preview_surface_start_spin, False)
        self._set_spinbox_state(self.preview_surface_angle_spin, False)
        self._set_spinbox_state(self.preview_surface_shape_spin, False)
        self._refresh_config_summary()

    def _selected_run_scenario_key(self) -> str:
        raw_value = str(self.run_scenario_var.get() or "").strip()
        if raw_value in self.run_scenario_label_to_key:
            return self.run_scenario_label_to_key[raw_value]
        if raw_value in self.run_scenario_key_to_label:
            return raw_value
        return "worldroad"

    def _refresh_run_scenario_controls(self) -> None:
        scenario_key = self._selected_run_scenario_key()
        if scenario_key == "roll":
            self.run_primary_label_var.set("Боковое ускорение ay, м/с²")
            self.run_secondary_label_var.set("Момент ступени, с")
            self.run_summary_var.set(
                "Проверка крена на ступенчатом боковом ускорении. Удобно для оценки устойчивости и загрузки по углам."
            )
            self._set_spinbox_state(self.run_primary_spin, True)
            self._set_spinbox_state(self.run_secondary_spin, True)
            self._refresh_run_mode_summary()
            self._refresh_config_summary()
            return
        if scenario_key == "pitch":
            self.run_primary_label_var.set("Продольное ускорение ax, м/с²")
            self.run_secondary_label_var.set("Момент ступени, с")
            self.run_summary_var.set(
                "Проверка тангажа на продольном ускорении. Удобно для оценки разгона, торможения и перераспределения нагрузки."
            )
            self._set_spinbox_state(self.run_primary_spin, True)
            self._set_spinbox_state(self.run_secondary_spin, True)
            self._refresh_run_mode_summary()
            self._refresh_config_summary()
            return
        if scenario_key == "micro_sync":
            self.run_primary_label_var.set("Амплитуда, м")
            self.run_secondary_label_var.set("Частота, Гц")
            self.run_summary_var.set(
                "Микровозбуждение в синфазе на всех колёсах. Удобно для оценки вертикальной жёсткости и фильтрации мелких неровностей."
            )
            self._set_spinbox_state(self.run_primary_spin, True)
            self._set_spinbox_state(self.run_secondary_spin, True)
            self._refresh_run_mode_summary()
            self._refresh_config_summary()
            return
        self.run_primary_label_var.set("Доп. параметр не нужен")
        self.run_secondary_label_var.set("Доп. параметр не нужен")
        self.run_summary_var.set(
            "Запуск одного дорожного сценария с текущим профилем preview. Подходит для полного расчёта с сохранением таблиц."
        )
        self._set_spinbox_state(self.run_primary_spin, False)
        self._set_spinbox_state(self.run_secondary_spin, False)
        self._refresh_run_mode_summary()
        self._refresh_config_summary()

    def _load_into_vars(self, payload: dict[str, object], source_path: Path) -> None:
        self.current_payload = dict(payload)
        self.current_source_path = source_path.resolve()
        self.path_var.set(str(self.current_source_path))
        if source_path.name.endswith(".json"):
            self.profile_name_var.set(source_path.stem)
        for section in DESKTOP_INPUT_SECTIONS:
            for spec in section.fields:
                var = self.vars.get(spec.key)
                if var is None:
                    continue
                try:
                    ui_value = spec.to_ui(payload.get(spec.key))
                    var.set(ui_value)
                except Exception:
                    pass
                self._refresh_value_label(spec.key)
        self._refresh_config_summary()
        self._refresh_run_context_summary()
        self._refresh_run_mode_summary()
        self._refresh_run_launch_summary()
        self._refresh_section_route_summary()
        self._refresh_profile_comparison()

    def _reset_section_to_defaults(self, section: object) -> None:
        title = getattr(section, "title", "Раздел")
        fields = tuple(getattr(section, "fields", ()) or ())
        if not fields:
            return
        if not messagebox.askyesno(
            "Desktop Input Editor",
            f"Вернуть раздел «{title}» к значениям по умолчанию?",
        ):
            return
        before_payload = self._gather_payload()
        self.default_payload = load_base_defaults()
        changed_count = 0
        for spec in fields:
            if not isinstance(spec, DesktopInputFieldSpec):
                continue
            var = self.vars.get(spec.key)
            if var is None:
                continue
            default_value = self.default_payload.get(spec.key)
            try:
                var.set(spec.to_ui(default_value))
                changed_count += 1
            except Exception:
                continue
            self._refresh_value_label(spec.key)
        self._remember_safe_action(
            f"Сброс раздела: {title}",
            before_payload,
            changed_count=changed_count,
        )
        self._refresh_config_summary()
        self._refresh_profile_comparison()
        self._set_status(f"Раздел «{title}» возвращён к значениям по умолчанию.")
        self._append_run_log(
            f"[section-reset] Раздел «{title}» сброшен к default_base.json; полей: {changed_count}"
        )

    def _gather_payload(self) -> dict[str, object]:
        payload = load_base_with_defaults(self.current_source_path)
        for section in DESKTOP_INPUT_SECTIONS:
            for spec in section.fields:
                var = self.vars.get(spec.key)
                if var is None:
                    continue
                payload[spec.key] = spec.to_base(var.get())
        return payload

    def _load_json(self) -> None:
        path = filedialog.askopenfilename(
            title="Открыть JSON параметров",
            initialdir=str(repo_root()),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        target = Path(path).resolve()
        try:
            payload = load_base_with_defaults(target)
            self.active_profile_path = None
            self.active_snapshot_path = None
            self._load_into_vars(payload, target)
            self._set_status(f"Загружен файл параметров: {target.name}")
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось открыть JSON:\n{exc}")

    def _save_named_profile(self) -> None:
        raw_name = str(self.profile_name_var.get() or "").strip()
        if not raw_name:
            messagebox.showinfo("Desktop Input Editor", "Введите имя профиля перед сохранением.")
            return
        try:
            target = self._save_profile_payload(raw_name)
            self._set_status(f"Профиль сохранён: {target.name}")
            self._append_run_log(f"[profile] Сохранён профиль: {target}")
            self._refresh_profile_comparison()
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось сохранить профиль:\n{exc}")

    def _save_run_context_profile(self) -> None:
        raw_name = self._suggest_run_context_profile_name()
        self.profile_name_var.set(raw_name)
        try:
            target = self._save_profile_payload(raw_name)
            self._set_status(f"Рабочая точка сохранена как профиль: {target.name}")
            self._append_run_log(f"[run-context] Рабочая точка сохранена как профиль: {target}")
            self._refresh_profile_comparison()
        except Exception as exc:
            messagebox.showerror(
                "Desktop Input Editor",
                f"Не удалось сохранить рабочую точку как профиль:\n{exc}",
            )

    def _load_selected_profile(self) -> None:
        target = self._selected_profile_path()
        if target is None:
            messagebox.showinfo("Desktop Input Editor", "Сначала выберите профиль для загрузки.")
            return
        try:
            payload = load_desktop_profile(target)
            merged = load_base_with_defaults()
            merged.update(payload)
            self.active_profile_path = target.resolve()
            self._load_into_vars(merged, target)
            self._set_status(f"Загружен профиль: {target.name}")
            self._append_run_log(f"[profile] Загружен профиль: {target}")
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось загрузить профиль:\n{exc}")

    def _delete_selected_profile(self) -> None:
        target = self._selected_profile_path()
        if target is None:
            messagebox.showinfo("Desktop Input Editor", "Сначала выберите профиль для удаления.")
            return
        if not messagebox.askyesno(
            "Desktop Input Editor",
            f"Удалить профиль?\n{target.name}",
        ):
            return
        try:
            delete_desktop_profile(target)
            if self.active_profile_path is not None and self.active_profile_path == target.resolve():
                self.active_profile_path = None
            self._refresh_profile_list()
            self._set_status(f"Профиль удалён: {target.name}")
            self._append_run_log(f"[profile] Удалён профиль: {target}")
            self._refresh_run_context_summary()
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось удалить профиль:\n{exc}")

    def _reset_to_default(self) -> None:
        try:
            payload = load_base_with_defaults()
            self.active_profile_path = None
            self.active_snapshot_path = None
            self._load_into_vars(payload, default_base_json_path())
            self._set_status("Загружены значения по умолчанию из default_base.json.")
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось загрузить default_base.json:\n{exc}")

    def _save_working_copy(self) -> None:
        target = default_working_copy_path()
        try:
            payload = self._gather_payload()
            save_base_payload(target, payload)
            self.current_source_path = target
            self.path_var.set(str(target))
            self._refresh_run_context_summary()
            self._set_status(f"Рабочая копия сохранена: {target}")
            messagebox.showinfo("Desktop Input Editor", f"Рабочая копия сохранена:\n{target}")
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось сохранить рабочую копию:\n{exc}")

    def _runtime_base_path(self) -> Path:
        return (repo_root() / "workspace" / "ui_state" / "desktop_input_runtime_base.json").resolve()

    def _runtime_preview_suite_path(self) -> Path:
        return (repo_root() / "workspace" / "ui_state" / "desktop_input_preview_suite.json").resolve()

    def _runtime_selfcheck_report_path(self) -> Path:
        return (repo_root() / "workspace" / "ui_state" / "desktop_input_selfcheck_report.json").resolve()

    def _runtime_preview_report_path(self) -> Path:
        return (repo_root() / "workspace" / "ui_state" / "desktop_input_preview_report.json").resolve()

    def _runtime_single_run_root(self) -> Path:
        return (repo_root() / "workspace" / "desktop_runs").resolve()

    def _new_runtime_single_run_dir(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return (self._runtime_single_run_root() / f"desktop_input_run_{stamp}").resolve()

    def _save_runtime_base_snapshot(self) -> Path:
        payload = self._gather_payload()
        target = self._runtime_base_path()
        save_base_payload(target, payload)
        return target

    def _build_preview_suite(self) -> list[dict[str, object]]:
        payload = self._gather_payload()
        try:
            vx0 = float(payload.get("vx0_м_с", 0.0) or 0.0)
        except Exception:
            vx0 = 0.0
        surface_key = self._selected_preview_surface_key()
        surface_label = preview_surface_label(surface_key)
        road_surface = build_desktop_preview_surface(
            surface_type=surface_key,
            amplitude_m=float(self.preview_surface_primary_value_var.get()),
            wavelength_or_width_m=float(self.preview_surface_secondary_value_var.get()),
            start_m=float(self.preview_surface_start_var.get()),
            angle_deg=float(self.preview_surface_angle_var.get()),
            shape_k=float(self.preview_surface_shape_var.get()),
        )
        return [
            {
                "имя": f"desktop_preview_{surface_key}",
                "включен": True,
                "тип": "worldroad",
                "dt": float(self.preview_dt_var.get()),
                "t_end": float(self.preview_t_end_var.get()),
                "road_len_m": float(self.preview_road_len_var.get()),
                "auto_t_end_from_len": False,
                "road_surface": road_surface,
                "vx0_м_с": float(vx0),
                "описание": f"Временный desktop preview-сценарий: {surface_label}.",
            }
        ]

    def _build_single_run_suite(self) -> list[dict[str, object]]:
        payload = self._gather_payload()
        try:
            vx0 = float(payload.get("vx0_м_с", 0.0) or 0.0)
        except Exception:
            vx0 = 0.0

        scenario_key = self._selected_run_scenario_key()
        dt = float(self.run_dt_var.get())
        t_end = float(self.run_t_end_var.get())
        primary = float(self.run_primary_value_var.get())
        secondary = float(self.run_secondary_value_var.get())

        if scenario_key == "roll":
            return [
                {
                    "имя": "desktop_run_roll",
                    "включен": True,
                    "тип": "инерция_крен",
                    "dt": dt,
                    "t_end": t_end,
                    "t_step": secondary,
                    "ay": primary,
                    "описание": "Desktop single-run: инерция по крену.",
                }
            ]
        if scenario_key == "pitch":
            return [
                {
                    "имя": "desktop_run_pitch",
                    "включен": True,
                    "тип": "инерция_тангаж",
                    "dt": dt,
                    "t_end": t_end,
                    "t_step": secondary,
                    "ax": primary,
                    "описание": "Desktop single-run: инерция по тангажу.",
                }
            ]
        if scenario_key == "micro_sync":
            return [
                {
                    "имя": "desktop_run_micro_sync",
                    "включен": True,
                    "тип": "микро_синфаза",
                    "dt": dt,
                    "t_end": t_end,
                    "A": primary,
                    "f": secondary,
                    "описание": "Desktop single-run: микро-синфаза.",
                }
            ]

        surface_key = self._selected_preview_surface_key()
        road_surface = build_desktop_preview_surface(
            surface_type=surface_key,
            amplitude_m=float(self.preview_surface_primary_value_var.get()),
            wavelength_or_width_m=float(self.preview_surface_secondary_value_var.get()),
            start_m=float(self.preview_surface_start_var.get()),
            angle_deg=float(self.preview_surface_angle_var.get()),
            shape_k=float(self.preview_surface_shape_var.get()),
        )
        return [
            {
                "имя": f"desktop_run_{surface_key}",
                "включен": True,
                "тип": "worldroad",
                "dt": dt,
                "t_end": t_end,
                "road_len_m": float(self.preview_road_len_var.get()),
                "auto_t_end_from_len": False,
                "road_surface": road_surface,
                "vx0_м_с": float(vx0),
                "описание": f"Desktop single-run: {preview_surface_label(surface_key)}.",
            }
        ]

    def _python_cli_exe(self) -> str:
        root = repo_root()
        cand_win = root / ".venv" / "Scripts" / "python.exe"
        if cand_win.exists():
            return str(cand_win)
        cand_posix = root / ".venv" / "bin" / "python"
        if cand_posix.exists():
            return str(cand_posix)
        return sys.executable or "python"

    def _run_command_async(
        self,
        title: str,
        cmd: list[str],
        *,
        result_path: Path | None = None,
        on_success: callable | None = None,
    ) -> None:
        if self._task_running:
            messagebox.showinfo("Desktop Input Editor", "Дождитесь завершения текущей проверки или расчёта.")
            return

        self._task_running = True
        self._set_status(f"Выполняется: {title}")
        self._append_run_log(f"[start] {title}")
        self._append_run_log("  " + " ".join(cmd))

        def _worker() -> None:
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(repo_root()),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
                )
                stdout = proc.stdout or ""
                stderr = proc.stderr or ""

                def _finish() -> None:
                    self._task_running = False
                    if stdout.strip():
                        self._append_run_log("[stdout]")
                        self._append_run_log(stdout.strip())
                    if stderr.strip():
                        self._append_run_log("[stderr]")
                        self._append_run_log(stderr.strip())
                    if proc.returncode == 0:
                        self._set_status(f"Готово: {title}")
                        if callable(on_success):
                            try:
                                on_success(result_path)
                            except Exception as exc:
                                self._append_run_log(f"[warn] post-process failed: {exc}")
                    else:
                        self._set_status(f"Ошибка: {title}")
                        messagebox.showerror(
                            "Desktop Input Editor",
                            f"Команда завершилась с ошибкой ({proc.returncode}):\n{title}",
                        )

                self.root.after(0, _finish)
            except Exception as exc:
                def _fail() -> None:
                    self._task_running = False
                    self._set_status(f"Ошибка запуска: {title}")
                    self._append_run_log(f"[error] {exc}")
                    messagebox.showerror("Desktop Input Editor", f"Не удалось запустить команду:\n{exc}")

                self.root.after(0, _fail)

        threading.Thread(target=_worker, daemon=True).start()

    def _summarize_selfcheck_report(self, report_path: Path | None) -> None:
        if report_path is None or not report_path.exists():
            self._append_run_log("[warn] report_json не найден после проверки конфигурации.")
            return
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            ok = bool(report.get("ok", False))
            errors = list(report.get("errors") or [])
            warnings = list(report.get("warnings") or [])
            self._append_run_log(
                f"[summary] Проверка конфигурации: {'OK' if ok else 'FAIL'}; "
                f"errors={len(errors)}; warnings={len(warnings)}"
            )
            for msg in errors[:5]:
                self._append_run_log(f"  error: {msg}")
            for msg in warnings[:5]:
                self._append_run_log(f"  warn: {msg}")
        except Exception as exc:
            self._append_run_log(f"[warn] Не удалось разобрать report_json: {exc}")

    def _summarize_preview_report(self, report_path: Path | None) -> None:
        if report_path is None or not report_path.exists():
            self._append_run_log("[warn] JSON preview-расчёта не найден.")
            return
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self._append_run_log(
                "[summary] "
                f"roll_max={float(report.get('max_abs_phi_deg', 0.0)):.2f} deg; "
                f"pitch_max={float(report.get('max_abs_theta_deg', 0.0)):.2f} deg; "
                f"min_tire_Fz={float(report.get('min_tire_Fz_N', 0.0)):.1f} N; "
                f"max_tire_pen={float(report.get('max_tire_pen_m', 0.0)):.4f} m"
            )
        except Exception as exc:
            self._append_run_log(f"[warn] Не удалось разобрать JSON preview-расчёта: {exc}")

    def _summarize_single_run_report(self, report_path: Path | None) -> None:
        if report_path is None or not report_path.exists():
            self._append_run_log("[warn] JSON подробного расчёта не найден.")
            return
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self._append_run_log(
                "[summary] "
                f"сценарий={report.get('scenario_name') or '—'}; "
                f"тип={report.get('scenario_type') or '—'}; "
                f"строк df_main={int(report.get('df_main_rows') or 0)}; "
                f"крен_peak={float(report.get('roll_peak_deg') or 0.0):.2f} град; "
                f"тангаж_peak={float(report.get('pitch_peak_deg') or 0.0):.2f} град"
            )
            mech_ok = report.get("mech_selfcheck_ok")
            mech_msg = str(report.get("mech_selfcheck_msg") or "").strip()
            if mech_ok is not None:
                self._append_run_log(
                    f"[summary] Самопроверка механики: {'в норме' if bool(mech_ok) else 'требует внимания'}"
                )
            if mech_msg:
                self._append_run_log(f"[summary] Сообщение: {mech_msg}")
            outdir = str(report.get("outdir") or "").strip()
            if outdir:
                self._append_run_log(f"[summary] Артефакты расчёта: {outdir}")
        except Exception as exc:
            self._append_run_log(f"[warn] Не удалось разобрать JSON подробного расчёта: {exc}")

    def _soft_preflight_before_run(self, run_label: str) -> bool:
        readiness_rows = evaluate_desktop_section_readiness(self._gather_payload())
        warn_rows = [
            row for row in readiness_rows if str(row.get("status") or "").strip().lower() == "warn"
        ]
        if not warn_rows:
            self._append_run_log(f"[preflight] {run_label}: проблемных шагов не найдено.")
            return True

        detail_lines = [
            f"- {str(row.get('title') or 'Раздел')}: {str(row.get('summary') or '').strip()}"
            for row in warn_rows[:4]
        ]
        if len(warn_rows) > 4:
            detail_lines.append(f"- И ещё разделов с замечаниями: {len(warn_rows) - 4}")
        prompt = (
            f"Перед запуском «{run_label}» есть шаги, требующие внимания:\n\n"
            + "\n".join(detail_lines)
            + "\n\nЗапустить всё равно?"
        )
        if messagebox.askyesno("Desktop Input Editor", prompt):
            self._append_run_log(
                f"[preflight] {run_label}: запуск подтверждён несмотря на предупреждения."
            )
            return True

        self._append_run_log(
            f"[preflight] {run_label}: запуск отменён пользователем после предупреждения."
        )
        self._set_status(f"Запуск отменён: {run_label}")
        return False

    def _run_config_check(self) -> None:
        base_path = self._save_runtime_base_snapshot()
        report_path = self._runtime_selfcheck_report_path()
        cmd = [
            self._python_cli_exe(),
            "-m",
            "pneumo_solver_ui.opt_selfcheck_v1",
            "--model",
            str((repo_root() / "pneumo_solver_ui" / "model_pneumo_v9_mech_doublewishbone_worldroad.py").resolve()),
            "--worker",
            str((repo_root() / "pneumo_solver_ui" / "opt_worker_v3_margins_energy.py").resolve()),
            "--base_json",
            str(base_path),
            "--ranges_json",
            str(default_ranges_json_path()),
            "--suite_json",
            str(default_suite_json_path()),
            "--report_json",
            str(report_path),
            "--mode",
            "fast",
        ]
        self._run_command_async(
            "Проверить конфигурацию",
            cmd,
            result_path=report_path,
            on_success=self._summarize_selfcheck_report,
        )

    def _run_quick_preview(self) -> None:
        if not self._soft_preflight_before_run("Быстрый расчёт"):
            return
        self._autosave_snapshot_before_run("quick_preview")
        base_path = self._save_runtime_base_snapshot()
        suite_path = self._runtime_preview_suite_path()
        report_path = self._runtime_preview_report_path()
        save_base_payload(suite_path, self._build_preview_suite())
        self._append_run_log(
            f"[preview] Профиль дороги: {preview_surface_label(self._selected_preview_surface_key())}"
        )
        cmd = [
            self._python_cli_exe(),
            "-m",
            "pneumo_solver_ui.tools.worldroad_compile_only_demo",
            "--params",
            str(base_path),
            "--test",
            str(suite_path),
            "--test_index",
            "0",
            "--dt",
            str(float(self.preview_dt_var.get())),
            "--t_end",
            str(float(self.preview_t_end_var.get())),
            "--json-out",
            str(report_path),
        ]
        self._run_command_async(
            "Быстрый расчёт",
            cmd,
            result_path=report_path,
            on_success=self._summarize_preview_report,
        )

    def _run_single_desktop_run(self) -> None:
        if not self._soft_preflight_before_run("Запустить подробный расчёт"):
            return
        self._autosave_snapshot_before_run("detail_run")
        base_path = self._save_runtime_base_snapshot()
        suite_path = self._runtime_preview_suite_path().with_name("desktop_input_single_run_suite.json")
        save_base_payload(suite_path, self._build_single_run_suite())
        run_dir = self._new_runtime_single_run_dir()
        report_path = run_dir / "run_summary.json"
        scenario_label = self.run_scenario_key_to_label.get(
            self._selected_run_scenario_key(),
            self._selected_run_scenario_key(),
        )
        self._append_run_log(f"[run] Сценарий расчёта: {scenario_label}")
        cmd = [
            self._python_cli_exe(),
            "-m",
            "pneumo_solver_ui.tools.desktop_single_run",
            "--params",
            str(base_path),
            "--test",
            str(suite_path),
            "--test_index",
            "0",
            "--dt",
            str(float(self.run_dt_var.get())),
            "--t_end",
            str(float(self.run_t_end_var.get())),
            "--outdir",
            str(run_dir),
        ]
        if bool(self.run_record_full_var.get()):
            cmd.append("--record_full")
        self._run_command_async(
            "Запустить подробный расчёт",
            cmd,
            result_path=report_path,
            on_success=self._summarize_single_run_report,
        )

    def _save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Сохранить параметры как",
            initialdir=str(repo_root()),
            initialfile="desktop_input_base.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        target = Path(path).resolve()
        try:
            payload = self._gather_payload()
            save_base_payload(target, payload)
            self.current_source_path = target
            self.path_var.set(str(target))
            self._refresh_run_context_summary()
            self._set_status(f"Параметры сохранены: {target}")
            messagebox.showinfo("Desktop Input Editor", f"Параметры сохранены:\n{target}")
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось сохранить JSON:\n{exc}")

    def _open_repo_root(self) -> None:
        root = repo_root()
        try:
            if os.name == "nt":
                os.startfile(str(root))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess

                subprocess.Popen(["open", str(root)])
            else:
                import subprocess

                subprocess.Popen(["xdg-open", str(root)])
            self._set_status(f"Открыта папка проекта: {root}")
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось открыть папку проекта:\n{exc}")

    def _open_profile_dir(self) -> None:
        root = desktop_profile_dir_path()
        root.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(root))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(root)])
            else:
                subprocess.Popen(["xdg-open", str(root)])
            self._set_status(f"Открыта папка профилей: {root}")
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось открыть папку профилей:\n{exc}")

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    app = DesktopInputEditor()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
