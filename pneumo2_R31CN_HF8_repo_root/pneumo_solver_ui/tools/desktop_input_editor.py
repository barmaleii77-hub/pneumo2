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
    build_desktop_section_change_cards,
    build_desktop_section_field_search_items,
    build_desktop_section_issue_cards,
    build_desktop_section_summary_cards,
    build_desktop_preview_surface,
    build_desktop_profile_diff,
    delete_desktop_profile,
    describe_desktop_run_mode,
    desktop_section_status_label,
    desktop_profile_dir_path,
    desktop_profile_display_name,
    desktop_run_summary_path,
    desktop_runs_dir_path,
    desktop_snapshot_dir_path,
    desktop_snapshot_display_name,
    default_base_json_path,
    default_ranges_json_path,
    default_suite_json_path,
    default_working_copy_path,
    evaluate_desktop_section_readiness,
    field_spec_map,
    find_desktop_field_matches,
    load_base_defaults,
    list_desktop_profile_paths,
    list_desktop_run_dirs,
    list_desktop_snapshot_paths,
    load_base_with_defaults,
    load_desktop_profile,
    load_desktop_run_summary,
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
from pneumo_solver_ui.desktop_input_graphics import DesktopInputGraphicPanel
from pneumo_solver_ui.desktop_ui_core import ScrollableFrame, build_scrolled_text, build_scrolled_treeview
from pneumo_solver_ui.desktop_ui_help import attach_tooltip, show_help_dialog
from pneumo_solver_ui.desktop_run_setup_model import (
    DESKTOP_RUN_CACHE_POLICY_OPTIONS,
    DESKTOP_RUN_PROFILE_OPTIONS,
    DESKTOP_RUN_RUNTIME_POLICY_OPTIONS,
    describe_latest_preview_summary,
    describe_run_launch_outlook,
    describe_run_launch_recommendation,
    describe_run_launch_route,
    describe_selfcheck_gate_status,
    describe_latest_selfcheck_summary,
    apply_run_setup_profile,
    cache_policy_description,
    cache_policy_label,
    describe_latest_run_summary,
    describe_run_setup_snapshot,
    run_profile_description,
    run_profile_label,
    runtime_policy_description,
    runtime_policy_label,
)
from pneumo_solver_ui.desktop_run_setup_runtime import (
    append_subprocess_log,
    build_selfcheck_subject_signature,
    build_run_log_path,
    desktop_run_setup_cache_root,
    desktop_run_setup_log_root,
    desktop_single_run_cache_dir,
    write_json_report_from_stdout,
)


try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


class ScrollableSection(ScrollableFrame):
    pass


class DesktopInputEditor:
    def __init__(self, host: tk.Misc | None = None, *, hosted: bool = False) -> None:
        self._owns_root = host is None
        self._hosted = bool(hosted or not self._owns_root)
        self.root = host if host is not None else tk.Tk()
        if self._owns_root:
            self.root.title(f"Данные машины ({RELEASE})")
            self.root.geometry("1160x860")
            self.root.minsize(1020, 760)
        self.ui_style = ttk.Style(self.root)

        self.current_source_path: Path = default_base_json_path()
        self.current_payload = load_base_with_defaults()
        self.source_reference_payload = load_base_with_defaults()
        self.default_payload = load_base_defaults()
        self.vars: dict[str, tk.Variable] = {}
        self._widget_handles: dict[str, tuple[DesktopInputFieldSpec, ttk.Label]] = {}
        self._field_frames: dict[str, ttk.Frame] = {}
        self._field_row_by_key: dict[str, int] = {}
        self._field_tabs_by_key: dict[str, ScrollableSection] = {}
        self._section_tree_ids: dict[str, str] = {}
        self._section_title_by_key = {
            spec.key: section.title
            for section in DESKTOP_INPUT_SECTIONS
            for spec in section.fields
        }
        self.section_titles = [section.title for section in DESKTOP_INPUT_SECTIONS]
        self.section_title_to_index = {
            title: idx for idx, title in enumerate(self.section_titles)
        }
        self.section_by_title = {
            section.title: section for section in DESKTOP_INPUT_SECTIONS
        }
        self.current_section_title_var = tk.StringVar(
            value=self.section_titles[0] if self.section_titles else "Раздел"
        )
        self.current_section_summary_var = tk.StringVar(
            value="Выберите раздел слева и редактируйте параметры в рабочей области."
        )
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
        self.latest_preview_summary_var = tk.StringVar()
        self.active_preview_report_path: Path | None = None
        self.active_preview_log_path: Path | None = None
        self.latest_selfcheck_summary_var = tk.StringVar()
        self.active_selfcheck_report_path: Path | None = None
        self.active_selfcheck_log_path: Path | None = None
        self.latest_run_summary_var = tk.StringVar()
        self.active_run_dir: Path | None = None
        self.active_run_summary_path: Path | None = None
        self.active_run_log_path: Path | None = None
        self.active_run_cache_dir: Path | None = None
        self.active_run_saved_files: dict[str, str] = {}
        self.compare_summary_var = tk.StringVar()
        self.compare_target_path: Path | None = None
        self.compare_diffs_by_key: dict[str, dict[str, object]] = {}
        self.source_reference_diffs_by_key: dict[str, dict[str, object]] = {}
        self.config_summary_var = tk.StringVar()
        self.run_context_var = tk.StringVar()
        self.quick_preset_hint_var = tk.StringVar(
            value="Быстрые пресеты меняют только часть параметров и подходят для черновой инженерной настройки."
        )
        self.undo_hint_var = tk.StringVar(
            value="История безопасных действий пока пуста."
        )
        self.route_summary_var = tk.StringVar()
        self.section_summary_vars: dict[str, tk.StringVar] = {}
        self.section_summary_labels: dict[str, ttk.Label] = {}
        self.section_issue_buttons: dict[str, ttk.Button] = {}
        self.section_restore_buttons: dict[str, ttk.Button] = {}
        self.section_search_buttons: dict[str, ttk.Button] = {}
        self.section_issue_focus_by_title: dict[str, str] = {}
        self.section_change_focus_by_title: dict[str, str] = {}
        self.field_restore_buttons: dict[str, ttk.Button] = {}
        self._safe_action_history: list[dict[str, object]] = []
        self.route_buttons: dict[str, ttk.Button] = {}
        self.section_graphics_panels: dict[str, DesktopInputGraphicPanel] = {}
        self.show_advanced_var = tk.BooleanVar(value=False)
        self.inspector_title_var = tk.StringVar(value="Параметр не выбран")
        self.inspector_section_var = tk.StringVar(value="Раздел: —")
        self.inspector_unit_var = tk.StringVar(value="Единица: —")
        self.inspector_range_var = tk.StringVar(value="Диапазон: —")
        self.inspector_context_var = tk.StringVar(value="Контекст: —")
        self.inspector_help_var = tk.StringVar(value="Выберите параметр слева или в форме, чтобы увидеть пояснение.")
        self.inspector_related_summary_var = tk.StringVar(value="Связанные параметры появятся после выбора поля.")
        self._inspector_related_field_keys: dict[str, str] = {}
        self._selected_field_key = ""
        self._selected_field_spec: DesktopInputFieldSpec | None = None
        self.field_search_var = tk.StringVar()
        self.field_search_choice_var = tk.StringVar(value="—")
        self.field_search_summary_var = tk.StringVar(
            value="Введите часть названия, единицы измерения или описания параметра."
        )
        self.field_search_mode = "idle"
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
        self.run_profile_var = tk.StringVar(value="detail")
        self.run_dt_var = tk.DoubleVar(value=0.003)
        self.run_t_end_var = tk.DoubleVar(value=1.6)
        self.run_record_full_var = tk.BooleanVar(value=False)
        self.run_primary_value_var = tk.DoubleVar(value=3.0)
        self.run_secondary_value_var = tk.DoubleVar(value=0.4)
        self.run_cache_policy_var = tk.StringVar(value="reuse")
        self.run_export_csv_var = tk.BooleanVar(value=True)
        self.run_export_npz_var = tk.BooleanVar(value=False)
        self.run_auto_check_var = tk.BooleanVar(value=True)
        self.run_log_to_file_var = tk.BooleanVar(value=True)
        self.run_runtime_policy_var = tk.StringVar(value="balanced")
        self.run_primary_label_var = tk.StringVar()
        self.run_secondary_label_var = tk.StringVar()
        self.run_summary_var = tk.StringVar()
        self.run_profile_hint_var = tk.StringVar()
        self.run_cache_hint_var = tk.StringVar()
        self.run_runtime_policy_hint_var = tk.StringVar()
        self.run_mode_summary_var = tk.StringVar()
        self.run_mode_cost_var = tk.StringVar()
        self.run_mode_advice_var = tk.StringVar()
        self.run_mode_usage_var = tk.StringVar()
        self.run_launch_summary_var = tk.StringVar()
        self.run_preset_hint_var = tk.StringVar(
            value="Пресеты запуска меняют только режим расчёта: шаг, длительность и расширенный лог."
        )
        self.run_launch_label: ttk.Label | None = None
        self.preview_surface_primary_spin: ttk.Spinbox | None = None
        self.preview_surface_secondary_spin: ttk.Spinbox | None = None
        self.preview_surface_start_spin: ttk.Spinbox | None = None
        self.preview_surface_angle_spin: ttk.Spinbox | None = None
        self.preview_surface_shape_spin: ttk.Spinbox | None = None
        self.run_primary_spin: ttk.Spinbox | None = None
        self.run_secondary_spin: ttk.Spinbox | None = None
        self._run_setup_center = None
        self._geometry_reference_center = None
        self._diagnostics_center = None
        self._service_container: ttk.Frame | None = None
        self._service_toggle_anchor: ttk.Frame | None = None
        self._service_panels_visible = False
        self.service_toggle_text_var = tk.StringVar(value="Показать файлы и сервис")
        self.status_var = tk.StringVar()
        self.path_var = tk.StringVar()
        self._task_running = False
        self._host_closed = False
        self._set_status("Готово. Открыт черновик на основе default_base.json.")
        self._configure_launch_summary_styles()
        self._configure_route_button_styles()
        self._build_ui()
        self._bind_summary_var_traces()
        self._refresh_safe_action_history_view()
        self._refresh_section_route_summary()
        self._refresh_preview_surface_controls()
        self._refresh_run_scenario_controls()
        self._refresh_run_profile_hint()
        self._refresh_run_policy_hints()
        self._refresh_profile_list()
        self._refresh_snapshot_list()
        self._load_into_vars(
            self.current_payload,
            self.current_source_path,
            refresh_source_reference=True,
        )
        self._refresh_latest_preview_summary()
        self._refresh_latest_selfcheck_summary()
        self._refresh_latest_run_summary()

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _set_service_panels_visible(self, visible: bool) -> None:
        container = self._service_container
        if container is None:
            return
        self._service_panels_visible = bool(visible)
        if self._service_panels_visible:
            pack_kwargs: dict[str, object] = {"fill": "x"}
            anchor = self._service_toggle_anchor
            if anchor is not None:
                pack_kwargs["after"] = anchor
            if not container.winfo_manager():
                container.pack(**pack_kwargs)
            self.service_toggle_text_var.set("Скрыть файлы и сервис")
            self._set_status("Открыт сервисный слой: файлы, профили, история и запуск.")
            return
        if container.winfo_manager():
            container.pack_forget()
        self.service_toggle_text_var.set("Показать файлы и сервис")

    def _toggle_service_panels(self) -> None:
        self._set_service_panels_visible(not self._service_panels_visible)

    def _configure_launch_summary_styles(self) -> None:
        self.ui_style.configure("DesktopLaunchFast.TLabel", foreground="#4f6b7a")
        self.ui_style.configure("DesktopLaunchBalanced.TLabel", foreground="#334455")
        self.ui_style.configure("DesktopLaunchDetailed.TLabel", foreground="#7a4f01")

    def _configure_route_button_styles(self) -> None:
        self.ui_style.configure("DesktopRoute.TButton", padding=(8, 4))
        self.ui_style.configure(
            "DesktopRouteCurrent.TButton",
            padding=(8, 4),
            foreground="#113355",
        )
        self.ui_style.configure(
            "DesktopRouteWarn.TButton",
            padding=(8, 4),
            foreground="#8a4b00",
        )
        self.ui_style.configure(
            "DesktopRouteChanged.TButton",
            padding=(8, 4),
            foreground="#16507a",
        )
        self.ui_style.configure(
            "DesktopRouteWarnChanged.TButton",
            padding=(8, 4),
            foreground="#7a3f00",
        )
        self.ui_style.configure(
            "DesktopRouteCurrentWarn.TButton",
            padding=(8, 4),
            foreground="#8a3b00",
        )
        self.ui_style.configure(
            "DesktopRouteCurrentChanged.TButton",
            padding=(8, 4),
            foreground="#0f426a",
        )
        self.ui_style.configure(
            "DesktopRouteCurrentWarnChanged.TButton",
            padding=(8, 4),
            foreground="#733100",
        )
        try:
            self.ui_style.layout("InputEditor.TNotebook.Tab", [])
        except Exception:
            pass

    def _route_button_style_for_state(
        self,
        *,
        is_current: bool,
        status_key: str,
        changed_count: int,
    ) -> str:
        has_warn = str(status_key or "").strip().lower() == "warn"
        has_changes = int(changed_count) > 0
        if is_current and has_warn and has_changes:
            return "DesktopRouteCurrentWarnChanged.TButton"
        if is_current and has_warn:
            return "DesktopRouteCurrentWarn.TButton"
        if is_current and has_changes:
            return "DesktopRouteCurrentChanged.TButton"
        if is_current:
            return "DesktopRouteCurrent.TButton"
        if has_warn and has_changes:
            return "DesktopRouteWarnChanged.TButton"
        if has_warn:
            return "DesktopRouteWarn.TButton"
        if has_changes:
            return "DesktopRouteChanged.TButton"
        return "DesktopRoute.TButton"

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

    def _current_section_title(self) -> str:
        if not self.section_titles:
            return ""
        index = self._current_section_index()
        if 0 <= index < len(self.section_titles):
            return self.section_titles[index]
        return self.section_titles[0]

    def _field_search_tracks_current_section(self) -> bool:
        return str(self.field_search_mode or "idle").strip().lower() in {
            "current_section",
            "current_section_attention",
            "current_section_changed",
        }

    def _select_section_index(self, index: int) -> None:
        if not self.section_titles:
            return
        safe_index = max(0, min(int(index), len(self.section_titles) - 1))
        self.section_notebook.select(safe_index)
        self.current_section_title_var.set(self.section_titles[safe_index])
        if hasattr(self, "section_tree"):
            item_id = self._section_tree_ids.get(self.section_titles[safe_index])
            if item_id:
                self.section_tree.selection_set(item_id)
                self.section_tree.focus(item_id)
                self.section_tree.see(item_id)
        self._refresh_section_route_summary()
        if self._field_search_tracks_current_section():
            self._refresh_active_field_search_view()
        self._refresh_selected_section_graphics()

    def _select_section_by_title(self, section_title: str) -> None:
        target_index = self.section_title_to_index.get(str(section_title or "").strip())
        if target_index is None:
            return
        self._select_section_index(target_index)

    def _on_section_tab_changed(self, _event: object | None = None) -> None:
        self._refresh_section_route_summary()
        if self._field_search_tracks_current_section():
            self._refresh_active_field_search_view()
        self._refresh_selected_section_graphics()

    def _on_section_tree_selected(self, _event: object | None = None) -> None:
        if not hasattr(self, "section_tree"):
            return
        selected = self.section_tree.selection()
        if not selected:
            return
        item_id = str(selected[0])
        for index, title in enumerate(self.section_titles):
            if self._section_tree_ids.get(title) == item_id:
                self._select_section_index(index)
                return

    def _refresh_selected_section_graphics(self) -> None:
        section_title = self._current_section_title()
        payload = self._gather_payload()
        selected_spec = self._selected_field_spec
        if selected_spec is not None and self._section_title_by_key.get(selected_spec.key) != section_title:
            selected_spec = None
        self._refresh_graphics_for_section(
            section_title=section_title,
            payload=payload,
            spec=selected_spec,
        )
        self.inspector_section_var.set(f"Раздел: {section_title}")

    def _refresh_graphics_for_section(
        self,
        *,
        section_title: str,
        payload: dict[str, object],
        spec: DesktopInputFieldSpec | None = None,
    ) -> None:
        refresh_kwargs = {
            "section_title": section_title,
            "payload": payload,
            "field_label": spec.label if spec is not None else "",
            "unit_label": spec.unit_label if spec is not None else "",
            "field_key": spec.key if spec is not None else "",
            "graphic_context": spec.effective_graphic_context if spec is not None else "",
        }
        graphics_by_title = getattr(self, "section_graphics_panels", {})
        graphic_panel = graphics_by_title.get(section_title)
        if graphic_panel is not None:
            graphic_panel.refresh(**refresh_kwargs)
        if hasattr(self, "graphics_panel"):
            self.graphics_panel.refresh(**refresh_kwargs)

    def _graphic_context_title(self, context_key: str) -> str:
        context = str(context_key or "").strip()
        if not context:
            return ""
        return DesktopInputGraphicPanel.CONTEXT_TITLES.get(context, context.replace("_", " "))

    def _build_related_field_items(self, spec: DesktopInputFieldSpec) -> list[tuple[str, str]]:
        same_section = [
            candidate
            for candidate in field_spec_map().values()
            if candidate.key != spec.key
            and self._section_title_by_key.get(candidate.key) == self._section_title_by_key.get(spec.key)
        ]
        same_context = [
            candidate
            for candidate in same_section
            if spec.effective_graphic_context
            and candidate.effective_graphic_context == spec.effective_graphic_context
        ]
        items: list[tuple[str, str]] = []
        seen: set[str] = set()
        for candidate, relation in (
            *[(candidate, "тот же контекст") for candidate in same_context],
            *[(candidate, "тот же раздел") for candidate in same_section],
        ):
            if candidate.key in seen:
                continue
            seen.add(candidate.key)
            items.append((f"{candidate.label} · {relation}", candidate.key))
        return items[:10]

    def _refresh_inspector_related_fields(self, spec: DesktopInputFieldSpec) -> None:
        if not hasattr(self, "inspector_related_tree"):
            return
        self._inspector_related_field_keys = {}
        for item_id in self.inspector_related_tree.get_children(""):
            self.inspector_related_tree.delete(item_id)
        items = self._build_related_field_items(spec)
        if not items:
            self.inspector_related_summary_var.set("Для этого поля нет близких соседних параметров.")
            return
        for index, (label, key) in enumerate(items):
            item_id = f"related::{index}"
            self._inspector_related_field_keys[item_id] = key
            self.inspector_related_tree.insert("", "end", iid=item_id, text=label)
        first = next(iter(self._inspector_related_field_keys), "")
        if first:
            self.inspector_related_tree.selection_set(first)
            self.inspector_related_tree.focus(first)
        self.inspector_related_summary_var.set(
            f"Связанных параметров: {len(items)}. Быстрый переход доступен из правой панели."
        )

    def _jump_to_inspector_related_field(self) -> None:
        if not hasattr(self, "inspector_related_tree"):
            return
        selected = self.inspector_related_tree.selection()
        if not selected:
            return
        key = self._inspector_related_field_keys.get(str(selected[0]))
        if key:
            self._jump_to_field(key)

    def _go_prev_section(self) -> None:
        self._select_section_index(self._current_section_index() - 1)

    def _go_next_section(self) -> None:
        self._select_section_index(self._current_section_index() + 1)

    def _build_section_route_state(
        self,
    ) -> tuple[
        list[dict[str, object]],
        dict[str, dict[str, object]],
        list[dict[str, object]],
        dict[str, dict[str, object]],
    ]:
        current_payload = self._gather_payload()
        readiness_rows = evaluate_desktop_section_readiness(current_payload)
        change_cards = build_desktop_section_change_cards(
            current_payload,
            self.source_reference_payload,
        )
        readiness_by_title = {
            str(row.get("title") or ""): row for row in readiness_rows
        }
        change_by_title = {
            str(card.get("title") or ""): card for card in change_cards
        }
        return readiness_rows, readiness_by_title, change_cards, change_by_title

    def _find_next_section_title(
        self,
        predicate: object,
    ) -> str | None:
        if not self.section_titles:
            return None
        checker = predicate if callable(predicate) else None
        if checker is None:
            return None
        start_index = self._current_section_index()
        for offset in range(1, len(self.section_titles)):
            title = self.section_titles[(start_index + offset) % len(self.section_titles)]
            try:
                if bool(checker(title)):
                    return title
            except Exception:
                continue
        return None

    def _go_next_attention_section(self) -> None:
        _rows, readiness_by_title, _change_cards, _change_by_title = self._build_section_route_state()
        title = self._find_next_section_title(
            lambda section_title: str(
                readiness_by_title.get(section_title, {}).get("status") or ""
            ).strip().lower() == "warn"
        )
        if not title:
            self._set_status("Следующих шагов с замечаниями сейчас нет.")
            return
        self._select_section_by_title(title)
        self._set_status(f"Открыт следующий шаг с замечанием: {title}")

    def _go_next_changed_section(self) -> None:
        _rows, _readiness_by_title, _change_cards, change_by_title = self._build_section_route_state()
        title = self._find_next_section_title(
            lambda section_title: int(
                change_by_title.get(section_title, {}).get("changed_count") or 0
            ) > 0
        )
        if not title:
            self._set_status("Следующих изменённых шагов сейчас нет.")
            return
        self._select_section_by_title(title)
        self._set_status(f"Открыт следующий изменённый шаг: {title}")

    def _refresh_section_route_summary(self) -> None:
        if not self.section_titles:
            self.route_summary_var.set("Шаги настройки пока недоступны.")
            return
        readiness_rows, readiness_by_title, change_cards, change_by_title = (
            self._build_section_route_state()
        )
        issue_cards = build_desktop_section_issue_cards(self._gather_payload())
        issue_by_title = {
            str(card.get("title") or "").strip(): card for card in issue_cards
        }
        current_index = self._current_section_index()
        for idx, title in enumerate(self.section_titles):
            button = self.route_buttons.get(title)
            if button is None:
                continue
            row = readiness_by_title.get(title, {})
            issue_card = issue_by_title.get(title, {})
            change_card = change_by_title.get(title, {})
            status_key = str(row.get("status") or "")
            status_text = desktop_section_status_label(status_key)
            issue_count = int(issue_card.get("issue_count") or 0)
            changed_count = int(change_card.get("changed_count") or 0)
            issue_badge = f" · {issue_count} зам." if issue_count > 0 else ""
            change_badge = f" · {changed_count} изм." if changed_count > 0 else ""
            button.configure(
                text=f"{idx + 1}. {title} · {status_text}{issue_badge}{change_badge}",
                style=self._route_button_style_for_state(
                    is_current=idx == current_index,
                    status_key=status_key,
                    changed_count=changed_count,
                ),
            )
        index = current_index
        current_title = self.section_titles[index]
        previous_title = self.section_titles[index - 1] if index > 0 else "—"
        next_title = self.section_titles[index + 1] if index + 1 < len(self.section_titles) else "Готово к запуску"
        current_row = readiness_by_title.get(current_title, {})
        current_issue_card = issue_by_title.get(current_title, {})
        current_change_card = change_by_title.get(current_title, {})
        ok_count = sum(1 for row in readiness_rows if str(row.get("status") or "") == "ok")
        warn_count = sum(1 for row in readiness_rows if str(row.get("status") or "") == "warn")
        changed_sections = sum(
            1 for card in change_cards if int(card.get("changed_count") or 0) > 0
        )
        issue_sections = sum(
            1 for card in issue_cards if int(card.get("issue_count") or 0) > 0
        )
        current_issue_count = int(current_issue_card.get("issue_count") or 0)
        next_attention_title = self._find_next_section_title(
            lambda title: str(readiness_by_title.get(title, {}).get("status") or "").strip().lower() == "warn"
        )
        next_changed_title = self._find_next_section_title(
            lambda title: int(change_by_title.get(title, {}).get("changed_count") or 0) > 0
        )
        self.route_summary_var.set(
            f"Сейчас шаг {index + 1} из {len(self.section_titles)}: {current_title}. "
            f"Предыдущий: {previous_title}. Следующий: {next_title}. "
            f"Готово шагов: {ok_count}; требуют внимания: {warn_count}. "
            f"Шагов с замечаниями: {issue_sections}. "
            f"Изменено шагов: {changed_sections}. "
            f"Следующий шаг с замечанием: {next_attention_title or 'не найден'}. "
            f"Следующий изменённый шаг: {next_changed_title or 'не найден'}. "
            f"Статус шага: {desktop_section_status_label(str(current_row.get('status') or ''))}. "
            f"Замечаний шага: {current_issue_count}. "
            f"Замечания шага: {str(current_issue_card.get('summary') or 'замечаний нет').strip()}. "
            f"{str(current_row.get('summary') or '').strip()} "
            f"Изменения шага: {str(current_change_card.get('summary') or 'без изменений').strip()}."
        )

        self.current_section_title_var.set(current_title)
        self.current_section_summary_var.set(
            f"{desktop_section_status_label(str(current_row.get('status') or ''))}. "
            f"Замечаний: {current_issue_count}. "
            f"Изменено: {int(current_change_card.get('changed_count') or 0)}."
        )
        if hasattr(self, "section_tree"):
            for idx, title in enumerate(self.section_titles):
                item_id = self._section_tree_ids.get(title)
                if not item_id:
                    continue
                row = readiness_by_title.get(title, {})
                issue_card = issue_by_title.get(title, {})
                change_card = change_by_title.get(title, {})
                status_text = desktop_section_status_label(str(row.get("status") or ""))
                issue_count = int(issue_card.get("issue_count") or 0)
                changed_count = int(change_card.get("changed_count") or 0)
                badges: list[str] = [status_text]
                if issue_count > 0:
                    badges.append(f"зам. {issue_count}")
                if changed_count > 0:
                    badges.append(f"изм. {changed_count}")
                self.section_tree.item(item_id, text=f"{idx + 1}. {title} · " + " · ".join(badges))

    def _refresh_section_header_summaries(self) -> None:
        current_payload = self._gather_payload()
        cards = build_desktop_section_summary_cards(current_payload)
        issue_cards = build_desktop_section_issue_cards(current_payload)
        change_cards = build_desktop_section_change_cards(
            current_payload,
            self.source_reference_payload,
        )
        issue_by_title = {
            str(card.get("title") or "").strip(): card for card in issue_cards
        }
        change_by_title = {
            str(card.get("title") or "").strip(): card for card in change_cards
        }
        for card in cards:
            title = str(card.get("title") or "").strip()
            if not title:
                continue
            var = self.section_summary_vars.get(title)
            label = self.section_summary_labels.get(title)
            issue_button = self.section_issue_buttons.get(title)
            restore_button = self.section_restore_buttons.get(title)
            search_button = self.section_search_buttons.get(title)
            issue_card = issue_by_title.get(title, {})
            change_card = change_by_title.get(title, {})
            if var is None:
                continue
            status_key = str(card.get("status") or "").strip().lower()
            status_text = desktop_section_status_label(status_key)
            headline = str(card.get("headline") or "").strip()
            details = str(card.get("details") or "").strip()
            focus_key = str(card.get("focus_key") or "").strip()
            focus_label = str(card.get("focus_label") or "").strip()
            focus_reason = str(card.get("focus_reason") or "").strip()
            change_summary = (
                str(change_card.get("summary") or "").strip() or "без изменений"
            )
            changed_count = int(change_card.get("changed_count") or 0)
            issue_count = int(issue_card.get("issue_count") or 0)
            change_focus_key = str(change_card.get("focus_key") or "").strip()
            change_focus_label = str(change_card.get("focus_label") or "").strip()
            text = headline
            if details:
                text = f"{headline}\nСтатус кластера: {status_text}. {details}"
            elif headline:
                text = f"{headline}\nСтатус кластера: {status_text}."
            else:
                text = f"Статус кластера: {status_text}."
            text = f"{text}\nИзменено от рабочей точки: {change_summary}."
            if focus_reason:
                text = f"{text}\nПервое замечание: {focus_reason}"
            elif change_focus_label:
                text = f"{text}\nПервое изменение: {change_focus_label}."
            var.set(text)
            if label is not None:
                if status_key == "ok":
                    label.configure(foreground="#1f5d50")
                elif status_key == "warn":
                    label.configure(foreground="#7a4f01")
                else:
                    label.configure(foreground="#555555")
            if focus_key:
                self.section_issue_focus_by_title[title] = focus_key
            else:
                self.section_issue_focus_by_title.pop(title, None)
            if change_focus_key:
                self.section_change_focus_by_title[title] = change_focus_key
            else:
                self.section_change_focus_by_title.pop(title, None)
            if issue_button is not None:
                if focus_key:
                    button_label = focus_label or "замечанию"
                    issue_button.configure(
                        text=f"Перейти к замечанию: {button_label}",
                        state="normal",
                    )
                elif change_focus_key:
                    button_label = change_focus_label or "изменению"
                    issue_button.configure(
                        text=f"Перейти к изменению: {button_label}",
                        state="normal",
                    )
                else:
                    issue_button.configure(
                        text="Кластер в норме",
                        state="disabled",
                    )
            if restore_button is not None:
                if changed_count > 0:
                    restore_button.configure(
                        text="Вернуть к рабочей точке",
                        state="normal",
                    )
                else:
                    restore_button.configure(
                        text="Совпадает с рабочей точкой",
                        state="disabled",
                    )
            if search_button is not None:
                if issue_count > 0:
                    search_button.configure(
                        text=f"Показать замечания кластера: {issue_count}",
                        state="normal",
                    )
                elif changed_count > 0:
                    search_button.configure(
                        text=f"Показать изменения кластера: {changed_count}",
                        state="normal",
                    )
                else:
                    search_button.configure(
                        text="Показать параметры кластера",
                        state="normal",
                    )
            tab_index = self.section_title_to_index.get(title)
            if tab_index is not None:
                tab_caption = title if changed_count <= 0 else f"{title} · {changed_count} изм."
                self.section_notebook.tab(tab_index, text=tab_caption)

    def _jump_to_section_issue(self, section_title: str) -> None:
        title = str(section_title or "").strip()
        if not title:
            return
        self._select_section_by_title(title)
        focus_key = str(self.section_issue_focus_by_title.get(title) or "").strip()
        if not focus_key:
            focus_key = str(self.section_change_focus_by_title.get(title) or "").strip()
        if not focus_key:
            self._set_status(f"Кластер «{title}» выглядит согласованным.")
            return
        self._jump_to_field(focus_key)

    def _reset_section_to_source_reference(self, section: object) -> None:
        title = getattr(section, "title", "Раздел")
        fields = tuple(getattr(section, "fields", ()) or ())
        if not fields:
            return
        before_payload = self._gather_payload()
        change_cards = build_desktop_section_change_cards(
            before_payload,
            self.source_reference_payload,
        )
        change_by_title = {
            str(card.get("title") or "").strip(): card for card in change_cards
        }
        change_card = change_by_title.get(str(title or "").strip(), {})
        changed_keys = {
            str(key or "").strip()
            for key in (change_card.get("changed_keys") or ())
            if str(key or "").strip()
        }
        if not changed_keys:
            self._set_status(f"Раздел «{title}» уже совпадает с рабочей точкой.")
            return
        if not messagebox.askyesno(
            "Desktop Input Editor",
            f"Вернуть раздел «{title}» к рабочей точке?",
        ):
            return
        restored_count = 0
        for spec in fields:
            if not isinstance(spec, DesktopInputFieldSpec) or spec.key not in changed_keys:
                continue
            var = self.vars.get(spec.key)
            if var is None:
                continue
            reference_value = self.source_reference_payload.get(spec.key)
            try:
                var.set(spec.to_ui(reference_value))
                restored_count += 1
            except Exception:
                continue
            self._refresh_value_label(spec.key)
        self._remember_safe_action(
            f"Возврат раздела к рабочей точке: {title}",
            before_payload,
            changed_count=restored_count,
        )
        self._refresh_config_summary()
        self._refresh_profile_comparison()
        self._refresh_section_header_summaries()
        self._set_status(f"Раздел «{title}» возвращён к рабочей точке.")
        self._append_run_log(
            f"[section-restore] Раздел «{title}» возвращён к рабочей точке; полей: {restored_count}"
        )

    def _restore_field_to_source_reference(self, key: str) -> None:
        clean_key = str(key or "").strip()
        handle = self._widget_handles.get(clean_key)
        var = self.vars.get(clean_key)
        if handle is None or var is None:
            return
        spec, _label = handle
        if clean_key not in self.source_reference_diffs_by_key:
            self._set_status(f"Параметр «{spec.label}» уже совпадает с рабочей точкой.")
            return
        before_payload = self._gather_payload()
        reference_value = self.source_reference_payload.get(clean_key)
        try:
            var.set(spec.to_ui(reference_value))
        except Exception as exc:
            messagebox.showerror(
                "Desktop Input Editor",
                f"Не удалось вернуть параметр «{spec.label}» к рабочей точке:\n{exc}",
            )
            return
        self._remember_safe_action(
            f"Возврат параметра к рабочей точке: {spec.label}",
            before_payload,
            changed_count=1,
        )
        self._set_status(f"Параметр «{spec.label}» возвращён к рабочей точке.")
        self._append_run_log(
            f"[field-restore] Параметр «{spec.label}» возвращён к рабочей точке."
        )

    def _selected_field_search_key(self) -> str | None:
        selected = str(self.field_search_choice_var.get() or "").strip()
        if not selected or selected == "—":
            return None
        return self._field_search_display_to_key.get(selected)

    def _apply_field_search_items(
        self,
        items: list[dict[str, str]],
        *,
        summary_text: str,
        empty_text: str,
    ) -> None:
        display_values: list[str] = []
        display_to_key: dict[str, str] = {}
        for item in items:
            display = str(item.get("display") or "").strip()
            key = str(item.get("key") or "").strip()
            if not display or not key or display in display_to_key:
                continue
            display_values.append(display)
            display_to_key[display] = key
        self._field_search_display_to_key = display_to_key
        self.field_search_combo.configure(values=display_values)
        if display_values:
            self.field_search_choice_var.set(display_values[0])
            self.field_search_summary_var.set(summary_text)
            return
        self.field_search_choice_var.set("—")
        self.field_search_summary_var.set(empty_text)

    def _field_search_badges_for_key(
        self,
        key: str,
        *,
        extra_badges: tuple[str, ...] = (),
    ) -> list[str]:
        clean_key = str(key or "").strip()
        section_title = self._section_title_by_key.get(clean_key, "")
        badges: list[str] = []
        if clean_key in self.source_reference_diffs_by_key:
            badges.append("изм. от рабочей точки")
        if clean_key in self.compare_diffs_by_key:
            badges.append("отличается от профиля")
        if str(self.section_issue_focus_by_title.get(section_title) or "").strip() == clean_key:
            badges.append("первое замечание секции")
        for badge in extra_badges:
            badge_text = str(badge or "").strip()
            if badge_text and badge_text not in badges:
                badges.append(badge_text)
        return badges

    def _build_field_search_item(
        self,
        *,
        key: str,
        label: str,
        section_title: str,
        extra_badges: tuple[str, ...] = (),
    ) -> dict[str, str]:
        clean_key = str(key or "").strip()
        clean_label = str(label or clean_key).strip() or clean_key
        clean_section_title = str(section_title or "").strip()
        display = f"{clean_label} — {clean_section_title or '—'}"
        badges = self._field_search_badges_for_key(
            clean_key,
            extra_badges=extra_badges,
        )
        if badges:
            display = f"{display} · {' · '.join(badges)}"
        return {
            "key": clean_key,
            "label": clean_label,
            "section_title": clean_section_title,
            "display": display,
        }

    def _refresh_active_field_search_view(self) -> None:
        mode = str(self.field_search_mode or "idle").strip().lower()
        if mode == "text":
            if str(self.field_search_var.get() or "").strip():
                self._refresh_field_search_results()
                return
            self.field_search_mode = "idle"
            return
        if mode == "changed":
            self._show_changed_fields_in_search()
            return
        if mode == "attention":
            self._show_attention_fields_in_search()
            return
        if mode == "current_section":
            self._show_current_section_fields_in_search(announce=False)
            return
        if mode == "current_section_attention":
            self._show_current_section_attention_fields_in_search(announce=False)
            return
        if mode == "current_section_changed":
            self._show_current_section_changed_fields_in_search(announce=False)
            return
        if mode == "profile_diff":
            self._show_profile_diff_fields_in_search()
            return

    def _refresh_field_search_results(self) -> None:
        query = str(self.field_search_var.get() or "").strip()
        if not query:
            self.field_search_mode = "idle"
            self._field_search_display_to_key = {}
            self.field_search_combo.configure(values=[])
            self.field_search_choice_var.set("—")
            self.field_search_summary_var.set(
                "Введите часть названия, единицы измерения или описания параметра."
            )
            return
        self.field_search_mode = "text"
        matches = find_desktop_field_matches(query, limit=12)
        items = [
            self._build_field_search_item(
                key=str(match.get("key") or "").strip(),
                label=str(match.get("label") or "").strip(),
                section_title=str(match.get("section_title") or "").strip(),
            )
            for match in matches
            if str(match.get("key") or "").strip()
        ]
        first_match = items[0] if items else {}
        changed_count = sum(
            1 for item in items if str(item.get("key") or "").strip() in self.source_reference_diffs_by_key
        )
        profile_diff_count = sum(
            1 for item in items if str(item.get("key") or "").strip() in self.compare_diffs_by_key
        )
        attention_count = sum(
            1
            for item in items
            if str(
                self.section_issue_focus_by_title.get(
                    str(item.get("section_title") or "").strip(),
                )
                or ""
            ).strip()
            == str(item.get("key") or "").strip()
        )
        self._apply_field_search_items(
            items,
            summary_text=(
                f"Найдено параметров: {len(items)}. "
                f"Из них: {changed_count} изменено от рабочей точки; "
                f"{profile_diff_count} отличается от профиля; "
                f"{attention_count} совпадает с первыми замечаниями. "
                f"Первый результат: {str(first_match.get('label') or '').strip()} "
                f"в секции «{str(first_match.get('section_title') or '').strip()}»."
            ),
            empty_text=(
                f"По запросу «{query}» ничего не найдено. Попробуйте часть названия или описание параметра."
            ),
        )

    def _clear_field_search(self) -> None:
        self.field_search_mode = "idle"
        self.field_search_var.set("")
        self.field_search_choice_var.set("—")
        self._field_search_display_to_key = {}
        self.field_search_combo.configure(values=[])
        self.field_search_summary_var.set(
            "Введите часть названия, единицы измерения или описания параметра."
        )
        self._set_status("Поиск параметров очищен.")

    def _show_changed_fields_in_search(self) -> None:
        self.field_search_mode = "changed"
        items: list[dict[str, str]] = []
        for section in DESKTOP_INPUT_SECTIONS:
            for spec in section.fields:
                if spec.key not in self.source_reference_diffs_by_key:
                    continue
                items.append(
                    self._build_field_search_item(
                        key=spec.key,
                        label=spec.label,
                        section_title=section.title,
                    )
                )
        first_item = items[0] if items else {}
        self._apply_field_search_items(
            items,
            summary_text=(
                f"Изменено от рабочей точки: {len(items)} параметров. "
                f"Первый: {str(first_item.get('label') or '').strip()} "
                f"в секции «{str(first_item.get('section_title') or '').strip()}»."
            ),
            empty_text="Отличий от рабочей точки по полям сейчас нет.",
        )
        if items:
            self._set_status("Показаны параметры, изменённые от рабочей точки.")
        else:
            self._set_status("Изменённых от рабочей точки параметров сейчас нет.")

    def _show_attention_fields_in_search(self) -> None:
        self.field_search_mode = "attention"
        items: list[dict[str, str]] = []
        cards = build_desktop_section_summary_cards(self._gather_payload())
        for card in cards:
            if str(card.get("status") or "").strip().lower() != "warn":
                continue
            key = str(card.get("focus_key") or "").strip()
            if not key:
                continue
            section_title = str(card.get("title") or "").strip()
            handle = self._widget_handles.get(key)
            spec = handle[0] if handle is not None else None
            label = (
                str(getattr(spec, "label", "") or "").strip()
                or str(card.get("focus_label") or "").strip()
                or key
            )
            items.append(
                self._build_field_search_item(
                    key=key,
                    label=label,
                    section_title=section_title,
                )
            )
        first_item = items[0] if items else {}
        self._apply_field_search_items(
            items,
            summary_text=(
                f"Шагов с замечаниями: {len(items)}. "
                f"Первое замечание: {str(first_item.get('label') or '').strip()} "
                f"в секции «{str(first_item.get('section_title') or '').strip()}»."
            ),
            empty_text="Секций с замечаниями сейчас нет.",
        )
        if items:
            self._set_status("Показаны первые замечания по кластерам.")
        else:
            self._set_status("Секций с замечаниями сейчас нет.")

    def _show_current_section_attention_fields_in_search(self, *, announce: bool = True) -> None:
        self.field_search_mode = "current_section_attention"
        section_title = self._current_section_title()
        if not section_title:
            self._apply_field_search_items(
                [],
                summary_text="Текущий кластер пока недоступен.",
                empty_text="Текущий кластер пока недоступен.",
            )
            if announce:
                self._set_status("Текущий кластер пока недоступен.")
            return
        issue_cards = build_desktop_section_issue_cards(self._gather_payload())
        issue_by_title = {
            str(card.get("title") or "").strip(): card for card in issue_cards
        }
        issue_card = issue_by_title.get(section_title, {})
        issue_keys = [
            str(key or "").strip()
            for key in (issue_card.get("issue_keys") or ())
            if str(key or "").strip()
        ]
        issue_labels = [
            str(label or "").strip()
            for label in (issue_card.get("issue_labels") or ())
            if str(label or "").strip()
        ]
        items = [
            self._build_field_search_item(
                key=key,
                label=issue_labels[idx] if idx < len(issue_labels) else key,
                section_title=section_title,
            )
            for idx, key in enumerate(issue_keys)
        ]
        first_item = items[0] if items else {}
        changed_count = sum(
            1 for item in items if str(item.get("key") or "").strip() in self.source_reference_diffs_by_key
        )
        profile_diff_count = sum(
            1 for item in items if str(item.get("key") or "").strip() in self.compare_diffs_by_key
        )
        self._apply_field_search_items(
            items,
            summary_text=(
                f"Замечания текущего кластера «{section_title}»: {len(items)}. "
                f"Из них: {changed_count} изменено от рабочей точки; "
                f"{profile_diff_count} отличается от профиля. "
                f"Первое замечание: {str(first_item.get('label') or '').strip()} "
                f"в секции «{str(first_item.get('section_title') or section_title).strip()}»."
            ),
            empty_text=f"В текущем кластере «{section_title}» замечаний сейчас нет.",
        )
        if not announce:
            return
        if items:
            self._set_status(f"Показаны замечания текущего кластера: {section_title}")
        else:
            self._set_status(f"В текущем кластере «{section_title}» замечаний сейчас нет.")

    def _show_current_section_fields_in_search(self, *, announce: bool = True) -> None:
        self.field_search_mode = "current_section"
        section_title = self._current_section_title()
        if not section_title:
            self._apply_field_search_items(
                [],
                summary_text="Текущий кластер пока недоступен.",
                empty_text="Текущий кластер пока недоступен.",
            )
            if announce:
                self._set_status("Текущий кластер пока недоступен.")
            return
        items = [
            self._build_field_search_item(
                key=str(item.get("key") or "").strip(),
                label=str(item.get("label") or "").strip(),
                section_title=str(item.get("section_title") or "").strip(),
            )
            for item in build_desktop_section_field_search_items(section_title)
            if str(item.get("key") or "").strip()
        ]
        first_item = items[0] if items else {}
        changed_count = sum(
            1 for item in items if str(item.get("key") or "").strip() in self.source_reference_diffs_by_key
        )
        profile_diff_count = sum(
            1 for item in items if str(item.get("key") or "").strip() in self.compare_diffs_by_key
        )
        attention_count = sum(
            1
            for item in items
            if str(
                self.section_issue_focus_by_title.get(
                    str(item.get("section_title") or "").strip(),
                )
                or ""
            ).strip()
            == str(item.get("key") or "").strip()
        )
        self._apply_field_search_items(
            items,
            summary_text=(
                f"Текущий кластер «{section_title}»: {len(items)} параметров. "
                f"Из них: {changed_count} изменено от рабочей точки; "
                f"{profile_diff_count} отличается от профиля; "
                f"{attention_count} совпадает с первым замечанием кластера. "
                f"Первый: {str(first_item.get('label') or '').strip()} "
                f"в секции «{str(first_item.get('section_title') or section_title).strip()}»."
            ),
            empty_text=f"В кластере «{section_title}» доступных параметров сейчас нет.",
        )
        if not announce:
            return
        if items:
            self._set_status(f"Показаны параметры текущего кластера: {section_title}")
        else:
            self._set_status(f"В кластере «{section_title}» доступных параметров сейчас нет.")

    def _show_current_section_changed_fields_in_search(self, *, announce: bool = True) -> None:
        self.field_search_mode = "current_section_changed"
        section_title = self._current_section_title()
        if not section_title:
            self._apply_field_search_items(
                [],
                summary_text="Текущий кластер пока недоступен.",
                empty_text="Текущий кластер пока недоступен.",
            )
            if announce:
                self._set_status("Текущий кластер пока недоступен.")
            return
        items = [
            self._build_field_search_item(
                key=str(item.get("key") or "").strip(),
                label=str(item.get("label") or "").strip(),
                section_title=str(item.get("section_title") or "").strip(),
            )
            for item in build_desktop_section_field_search_items(section_title)
            if str(item.get("key") or "").strip() in self.source_reference_diffs_by_key
        ]
        first_item = items[0] if items else {}
        profile_diff_count = sum(
            1 for item in items if str(item.get("key") or "").strip() in self.compare_diffs_by_key
        )
        attention_count = sum(
            1
            for item in items
            if str(
                self.section_issue_focus_by_title.get(
                    str(item.get("section_title") or "").strip(),
                )
                or ""
            ).strip()
            == str(item.get("key") or "").strip()
        )
        self._apply_field_search_items(
            items,
            summary_text=(
                f"Изменения текущего кластера «{section_title}»: {len(items)} параметров. "
                f"Из них: {profile_diff_count} отличается от профиля; "
                f"{attention_count} совпадает с первым замечанием кластера. "
                f"Первое изменение: {str(first_item.get('label') or '').strip()} "
                f"в секции «{str(first_item.get('section_title') or section_title).strip()}»."
            ),
            empty_text=f"В текущем кластере «{section_title}» изменений от рабочей точки нет.",
        )
        if not announce:
            return
        if items:
            self._set_status(f"Показаны изменения текущего кластера: {section_title}")
        else:
            self._set_status(f"В текущем кластере «{section_title}» изменений от рабочей точки нет.")

    def _show_section_search_from_summary(self, section_title: str) -> None:
        title = str(section_title or "").strip()
        if not title:
            return
        self._select_section_by_title(title)
        issue_cards = build_desktop_section_issue_cards(self._gather_payload())
        issue_by_title = {
            str(card.get("title") or "").strip(): card for card in issue_cards
        }
        change_cards = build_desktop_section_change_cards(
            self._gather_payload(),
            self.source_reference_payload,
        )
        change_by_title = {
            str(card.get("title") or "").strip(): card for card in change_cards
        }
        if int(issue_by_title.get(title, {}).get("issue_count") or 0) > 0:
            self._show_current_section_attention_fields_in_search()
            return
        if int(change_by_title.get(title, {}).get("changed_count") or 0) > 0:
            self._show_current_section_changed_fields_in_search()
            return
        self._show_current_section_fields_in_search()

    def _show_profile_diff_fields_in_search(self) -> None:
        self.field_search_mode = "profile_diff"
        target = self.compare_target_path
        if target is None:
            self._apply_field_search_items(
                [],
                summary_text="Сравнение с профилем выключено.",
                empty_text="Сравнение с профилем выключено.",
            )
            self._set_status("Сравнение с профилем выключено.")
            return
        profile_name = desktop_profile_display_name(target)
        items: list[dict[str, str]] = []
        for section in DESKTOP_INPUT_SECTIONS:
            for spec in section.fields:
                if spec.key not in self.compare_diffs_by_key:
                    continue
                items.append(
                    self._build_field_search_item(
                        key=spec.key,
                        label=spec.label,
                        section_title=section.title,
                    )
                )
        first_item = items[0] if items else {}
        self._apply_field_search_items(
            items,
            summary_text=(
                f"Отличия с профилем «{profile_name}»: {len(items)} параметров. "
                f"Первый: {str(first_item.get('label') or '').strip()} "
                f"в секции «{str(first_item.get('section_title') or '').strip()}»."
            ),
            empty_text=f"Отличий с профилем «{profile_name}» сейчас нет.",
        )
        if items:
            self._set_status(f"Показаны отличия с профилем: {profile_name}")
        else:
            self._set_status(f"Отличий с профилем «{profile_name}» сейчас нет.")

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

        quick_actions = ttk.Frame(outer)
        quick_actions.pack(fill="x", pady=(0, 10))
        ttk.Label(
            quick_actions,
            text="Данные машины",
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left")
        ttk.Button(quick_actions, text="Загрузить данные...", command=self._load_json).pack(side="left")
        ttk.Button(quick_actions, text="Сохранить рабочую копию", command=self._save_working_copy).pack(side="left", padx=(8, 0))
        ttk.Button(
            quick_actions,
            textvariable=self.service_toggle_text_var,
            command=self._toggle_service_panels,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(quick_actions, text="Настроить расчёт", command=self._open_run_setup_center).pack(side="left", padx=(8, 0))
        ttk.Button(quick_actions, text="Справочники и геометрия", command=self._open_geometry_reference_center).pack(
            side="left",
            padx=(8, 0),
        )
        ttk.Button(quick_actions, text="Диагностика и отправка", command=self._open_diagnostics_center).pack(
            side="left",
            padx=(8, 0),
        )
        ttk.Checkbutton(
            quick_actions,
            text="Показать дополнительные параметры",
            variable=self.show_advanced_var,
            command=self._refresh_field_visibility,
        ).pack(side="right")
        ttk.Label(
            quick_actions,
            textvariable=self.path_var,
            foreground="#455a64",
            width=34,
            anchor="e",
        ).pack(side="right", padx=(0, 14))
        self._service_toggle_anchor = quick_actions
        self._service_container = ttk.Frame(outer)
        self._service_container.pack(fill="x")
        service_notebook = ttk.Notebook(self._service_container)
        service_notebook.pack(fill="x")
        files_service_tab = ScrollableSection(service_notebook)
        profiles_service_tab = ScrollableSection(service_notebook)
        actions_service_tab = ScrollableSection(service_notebook)
        tools_service_tab = ScrollableSection(service_notebook)
        for host, title in (
            (files_service_tab, "Файлы"),
            (profiles_service_tab, "Профили и снимки"),
            (actions_service_tab, "Расчёт и действия"),
            (tools_service_tab, "Навигация и поиск"),
        ):
            host.body.columnconfigure(0, weight=1)
            service_notebook.add(host, text=title)

        overview_frame = ttk.LabelFrame(outer, text="Главное сейчас", padding=10)
        overview_frame.pack(fill="x", pady=(0, 12))
        overview_frame.pack_forget()
        overview_frame.columnconfigure(1, weight=1)
        ttk.Label(overview_frame, text="Источник данных:").grid(row=0, column=0, sticky="w")
        ttk.Label(
            overview_frame,
            textvariable=self.path_var,
            foreground="#2f4f4f",
            wraplength=920,
            justify="left",
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(
            overview_frame,
            textvariable=self.config_summary_var,
            wraplength=1040,
            justify="left",
            foreground="#334455",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Label(
            overview_frame,
            textvariable=self.run_launch_summary_var,
            wraplength=1040,
            justify="left",
            foreground="#355c7d",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(
            overview_frame,
            text=(
                "Здесь остаются только параметры машины, навигация, поиск и графическое сопровождение. "
                "Файлы, профили, история, пресеты, проверка, запуск и артефакты открываются по кнопке слева."
            ),
            wraplength=1040,
            justify="left",
            foreground="#555555",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        toolbar = ttk.LabelFrame(files_service_tab.body, text="Файл параметров", padding=10)
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

        profiles_workspace = ttk.Panedwindow(profiles_service_tab.body, orient="horizontal")
        profiles_workspace.pack(fill="both", expand=True, pady=(12, 0))
        profiles_left_col = ttk.Frame(profiles_workspace, padding=(0, 0, 8, 0))
        profiles_right_col = ttk.Frame(profiles_workspace, padding=(8, 0, 0, 0))
        profiles_workspace.add(profiles_left_col, weight=1)
        profiles_workspace.add(profiles_right_col, weight=1)

        profiles = ttk.LabelFrame(profiles_left_col, text="Рабочие профили", padding=10)
        profiles.pack(fill="x")
        profiles.columnconfigure(5, weight=1)

        ttk.Label(profiles, text="Сохранить как профиль").grid(row=0, column=0, sticky="w")
        ttk.Entry(profiles, textvariable=self.profile_name_var, width=28).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(8, 0),
        )
        ttk.Button(profiles, text="Сохранить профиль", command=self._save_named_profile).grid(
            row=0,
            column=2,
            sticky="w",
            padx=(10, 0),
        )

        ttk.Label(profiles, text="Доступные профили").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.profile_combo = ttk.Combobox(
            profiles,
            textvariable=self.profile_choice_var,
            values=[],
            state="readonly",
            width=28,
        )
        self.profile_combo.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Button(profiles, text="Обновить список", command=self._refresh_profile_list).grid(
            row=1,
            column=2,
            sticky="w",
            padx=(10, 0),
            pady=(10, 0),
        )
        ttk.Button(profiles, text="Загрузить профиль", command=self._load_selected_profile).grid(
            row=1,
            column=3,
            sticky="w",
            padx=(10, 0),
            pady=(10, 0),
        )
        ttk.Button(profiles, text="Удалить профиль", command=self._delete_selected_profile).grid(
            row=1,
            column=4,
            sticky="w",
            padx=(10, 0),
            pady=(10, 0),
        )
        ttk.Button(profiles, text="Открыть папку профилей", command=self._open_profile_dir).grid(
            row=1,
            column=5,
            sticky="e",
            pady=(10, 0),
        )

        ttk.Button(profiles, text="Сравнить с текущим", command=self._compare_selected_profile).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(10, 0),
        )
        ttk.Button(profiles, text="Сбросить сравнение", command=self._clear_profile_comparison).grid(
            row=2,
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
        ).grid(row=2, column=2, columnspan=4, sticky="w", padx=(16, 0), pady=(10, 0))

        ttk.Label(
            profiles,
            textvariable=self.profile_hint_var,
            foreground="#555555",
            wraplength=1040,
            justify="left",
        ).grid(row=3, column=0, columnspan=6, sticky="w", pady=(10, 0))

        profile_details_notebook = ttk.Notebook(profiles_right_col)
        profile_details_notebook.pack(fill="both", expand=True)

        snapshots = ttk.Frame(profile_details_notebook, padding=10)
        profile_details_notebook.add(snapshots, text="Снимки")
        snapshots.columnconfigure(5, weight=1)

        ttk.Checkbutton(
            snapshots,
            text="Автоматически сохранять снимок перед запуском",
            variable=self.snapshot_before_run_var,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

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

        diff_frame = ttk.Frame(profile_details_notebook, padding=8)
        profile_details_notebook.add(diff_frame, text="Сравнение")
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

        actions_workspace = ttk.Panedwindow(actions_service_tab.body, orient="horizontal")
        actions_workspace.pack(fill="both", expand=True, pady=(12, 0))
        actions_left_col = ttk.Frame(actions_workspace, padding=(0, 0, 8, 0))
        actions_right_col = ttk.Frame(actions_workspace, padding=(8, 0, 0, 0))
        actions_workspace.add(actions_left_col, weight=1)
        actions_workspace.add(actions_right_col, weight=2)

        config_frame = ttk.LabelFrame(actions_left_col, text="Сводка конфигурации перед запуском", padding=10)
        config_frame.pack(fill="x")
        ttk.Label(
            config_frame,
            textvariable=self.config_summary_var,
            wraplength=1040,
            justify="left",
            foreground="#334455",
        ).pack(anchor="w")

        preset_frame = ttk.LabelFrame(actions_left_col, text="Быстрые пресеты", padding=10)
        preset_frame.pack(fill="x", pady=(12, 0))
        for col in range(3):
            preset_frame.columnconfigure(col, weight=1)

        for idx, (preset_key, preset_label_text, _preset_desc) in enumerate(DESKTOP_QUICK_PRESET_OPTIONS):
            row = idx // 3
            col = idx % 3
            ttk.Button(
                preset_frame,
                text=preset_label_text,
                command=lambda key=preset_key: self._apply_quick_preset(key),
            ).grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0), pady=(0 if row == 0 else 10, 0))

        ttk.Label(
            preset_frame,
            textvariable=self.quick_preset_hint_var,
            foreground="#555555",
            wraplength=1040,
            justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

        history_frame = ttk.LabelFrame(actions_left_col, text="История последних действий", padding=10)
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

        actions = ttk.LabelFrame(actions_right_col, text="Проверка и расчёт", padding=10)
        actions.pack(fill="x")

        run_setup_frame = ttk.LabelFrame(actions, text="Отдельный run setup", padding=10)
        run_setup_frame.grid(row=0, column=0, columnspan=6, sticky="ew")
        ttk.Label(
            run_setup_frame,
            textvariable=self.run_profile_hint_var,
            foreground="#555555",
            wraplength=1040,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(
            run_setup_frame,
            textvariable=self.run_mode_summary_var,
            foreground="#334455",
            wraplength=1040,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            run_setup_frame,
            textvariable=self.run_cache_hint_var,
            foreground="#6b4d00",
            wraplength=1040,
            justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            run_setup_frame,
            textvariable=self.run_runtime_policy_hint_var,
            foreground="#355c7d",
            wraplength=1040,
            justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(
            run_setup_frame,
            text="Открыть отдельное окно настройки расчёта",
            command=self._open_run_setup_center,
        ).grid(row=4, column=0, sticky="w", pady=(10, 0))

        context_frame = ttk.LabelFrame(actions, text="Текущая рабочая точка", padding=10)
        context_frame.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(12, 0))
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
        launch_frame.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        self.run_launch_label = ttk.Label(
            launch_frame,
            textvariable=self.run_launch_summary_var,
            style="DesktopLaunchBalanced.TLabel",
            wraplength=1040,
            justify="left",
        )
        self.run_launch_label.pack(anchor="w")

        ttk.Button(actions, text="Проверить конфигурацию", command=self._run_config_check).grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Button(actions, text="Быстрый расчёт", command=self._run_quick_preview).grid(row=3, column=2, columnspan=2, sticky="w", padx=(12, 0), pady=(12, 0))
        ttk.Button(actions, text="Запустить подробный расчёт", command=self._run_single_desktop_run).grid(row=3, column=4, columnspan=2, sticky="w", padx=(12, 0), pady=(12, 0))

        artifacts_notebook = ttk.Notebook(actions)
        artifacts_notebook.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        latest_preview_frame = ttk.Frame(artifacts_notebook, padding=10)
        artifacts_notebook.add(latest_preview_frame, text="Preview")
        latest_preview_frame.columnconfigure(0, weight=1)
        ttk.Label(
            latest_preview_frame,
            textvariable=self.latest_preview_summary_var,
            wraplength=1040,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Button(
            latest_preview_frame,
            text="Обновить preview-сводку",
            command=self._refresh_latest_preview_summary,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            latest_preview_frame,
            text="Открыть preview_report.json",
            command=self._open_latest_preview_report_json,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            latest_preview_frame,
            text="Открыть preview-лог",
            command=self._open_latest_preview_log,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))

        latest_selfcheck_frame = ttk.Frame(artifacts_notebook, padding=10)
        artifacts_notebook.add(latest_selfcheck_frame, text="Самопроверка")
        latest_selfcheck_frame.columnconfigure(0, weight=1)
        ttk.Label(
            latest_selfcheck_frame,
            textvariable=self.latest_selfcheck_summary_var,
            wraplength=1040,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Button(
            latest_selfcheck_frame,
            text="Обновить selfcheck-сводку",
            command=self._refresh_latest_selfcheck_summary,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            latest_selfcheck_frame,
            text="Открыть selfcheck_report.json",
            command=self._open_latest_selfcheck_report_json,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            latest_selfcheck_frame,
            text="Открыть selfcheck-лог",
            command=self._open_latest_selfcheck_log,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))

        latest_run_frame = ttk.Frame(artifacts_notebook, padding=10)
        artifacts_notebook.add(latest_run_frame, text="Подробный расчёт")
        latest_run_frame.columnconfigure(0, weight=1)
        ttk.Label(
            latest_run_frame,
            textvariable=self.latest_run_summary_var,
            wraplength=1040,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, columnspan=5, sticky="w")
        ttk.Button(
            latest_run_frame,
            text="Обновить сводку",
            command=self._refresh_latest_run_summary,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            latest_run_frame,
            text="Открыть папку запуска",
            command=self._open_latest_run_dir,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            latest_run_frame,
            text="Открыть run_summary.json",
            command=self._open_latest_run_summary_json,
        ).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            latest_run_frame,
            text="Открыть run-лог",
            command=self._open_latest_run_log,
        ).grid(row=1, column=3, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            latest_run_frame,
            text="Открыть папку всех запусков",
            command=self._open_desktop_runs_dir,
        ).grid(row=1, column=4, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            latest_run_frame,
            text="Открыть df_main.csv",
            command=self._open_latest_df_main_csv,
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Button(
            latest_run_frame,
            text="Открыть NPZ bundle",
            command=self._open_latest_npz_bundle,
        ).grid(row=2, column=1, sticky="w", padx=(12, 0), pady=(10, 0))
        ttk.Button(
            latest_run_frame,
            text="Открыть cache entry",
            command=self._open_latest_run_cache_dir,
        ).grid(row=2, column=2, sticky="w", padx=(12, 0), pady=(10, 0))

        ttk.Label(
            actions,
            text="Для полного маршрута запуска и артефактов используйте отдельный run setup.",
            foreground="#555555",
        ).grid(row=5, column=0, columnspan=6, sticky="w", pady=(12, 0))

        route_frame = ttk.LabelFrame(tools_service_tab.body, text="Пошаговый маршрут настройки", padding=10)
        route_frame.pack(fill="x", pady=(12, 0))
        route_col_count = max(4, len(self.section_titles))
        for col in range(route_col_count):
            route_frame.columnconfigure(col, weight=1)
        ttk.Label(
            route_frame,
            text=(
                "Быстрый маршрут помогает идти по кластерам: сначала геометрия, затем пневматика, "
                "механика, статическая настройка, компоненты и справочные данные. "
                "Это только навигация по текущему editor "
                "и не дублирует отдельные окна Animator, Compare Viewer или Mnemo."
            ),
            wraplength=1040,
            justify="left",
        ).grid(row=0, column=0, columnspan=route_col_count, sticky="w")
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
        ttk.Button(
            route_frame,
            text="К следующему замечанию",
            command=self._go_next_attention_section,
        ).grid(row=2, column=2, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Button(
            route_frame,
            text="К следующему изменению",
            command=self._go_next_changed_section,
        ).grid(row=2, column=3, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Label(
            route_frame,
            textvariable=self.route_summary_var,
            foreground="#555555",
            wraplength=840,
            justify="left",
        ).grid(
            row=3,
            column=0,
            columnspan=route_col_count,
            sticky="w",
            padx=(0, 0),
            pady=(10, 0),
        )

        search_frame = ttk.LabelFrame(tools_service_tab.body, text="Быстрый поиск по параметрам", padding=10)
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
        ttk.Button(
            search_frame,
            text="Показать изменённые",
            command=self._show_changed_fields_in_search,
        ).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Button(
            search_frame,
            text="Показать замечания",
            command=self._show_attention_fields_in_search,
        ).grid(row=2, column=2, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Button(
            search_frame,
            text="Показать текущий кластер",
            command=self._show_current_section_fields_in_search,
        ).grid(row=2, column=3, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Button(
            search_frame,
            text="Показать отличия с профилем",
            command=self._show_profile_diff_fields_in_search,
        ).grid(row=2, column=4, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Label(
            search_frame,
            textvariable=self.field_search_summary_var,
            foreground="#555555",
            wraplength=940,
            justify="left",
        ).grid(row=3, column=0, columnspan=5, sticky="w", pady=(10, 0))
        search_entry.bind("<Return>", lambda _event: self._jump_to_selected_field())
        self.field_search_combo.bind("<<ComboboxSelected>>", lambda _event: self._jump_to_selected_field())

        work_area = ttk.Panedwindow(outer, orient="horizontal")
        work_area.pack(fill="both", expand=True, pady=(12, 0))

        section_nav = ttk.LabelFrame(work_area, text="Дерево разделов", padding=10)
        section_nav.columnconfigure(0, weight=1)
        section_nav.rowconfigure(0, weight=1)
        tree_host, self.section_tree = build_scrolled_treeview(
            section_nav,
            show="tree",
            selectmode="browse",
            height=max(len(self.section_titles), 8),
        )
        tree_host.grid(row=0, column=0, sticky="nsew")
        for idx, title in enumerate(self.section_titles):
            item_id = f"section::{idx}"
            self._section_tree_ids[title] = item_id
            self.section_tree.insert("", "end", iid=item_id, text=f"{idx + 1}. {title}")
        if self.section_titles:
            first_item = self._section_tree_ids.get(self.section_titles[0])
            if first_item:
                self.section_tree.selection_set(first_item)
                self.section_tree.focus(first_item)
        self.section_tree.bind("<<TreeviewSelect>>", self._on_section_tree_selected)
        nav_actions = ttk.Frame(section_nav)
        nav_actions.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        nav_actions.columnconfigure(0, weight=1)
        nav_actions.columnconfigure(1, weight=1)
        nav_actions.columnconfigure(2, weight=1)
        ttk.Button(
            nav_actions,
            text="Поля",
            command=self._show_current_section_fields_in_search,
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            nav_actions,
            text="Замечание",
            command=self._show_current_section_attention_fields_in_search,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ttk.Button(
            nav_actions,
            text="Изменения",
            command=self._show_current_section_changed_fields_in_search,
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ttk.Label(
            section_nav,
            textvariable=self.current_section_summary_var,
            wraplength=220,
            justify="left",
            foreground="#555555",
        ).grid(row=2, column=0, sticky="ew", pady=(8, 0))
        work_area.add(section_nav, weight=0)

        center_panel = ttk.Frame(work_area)
        center_panel.columnconfigure(0, weight=1)
        center_panel.rowconfigure(1, weight=1)
        work_area.add(center_panel, weight=1)
        center_header = ttk.Frame(center_panel)
        center_header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        center_header.columnconfigure(2, weight=1)
        center_header.columnconfigure(3, weight=1)
        ttk.Label(
            center_header,
            textvariable=self.current_section_title_var,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(center_header, text="Поиск").grid(row=0, column=1, sticky="e", padx=(12, 6))
        search_entry_compact = ttk.Entry(center_header, textvariable=self.field_search_var, width=28)
        search_entry_compact.grid(row=0, column=2, sticky="ew")
        self.field_search_combo = ttk.Combobox(
            center_header,
            textvariable=self.field_search_choice_var,
            values=[],
            state="readonly",
            width=30,
        )
        self.field_search_combo.grid(row=0, column=3, sticky="ew", padx=(8, 0))
        ttk.Button(
            center_header,
            text="Перейти",
            command=self._jump_to_selected_field,
        ).grid(row=0, column=4, sticky="e", padx=(8, 0))
        ttk.Button(
            center_header,
            text="Очистить",
            command=self._clear_field_search,
        ).grid(row=0, column=5, sticky="e", padx=(8, 0))
        search_entry_compact.bind("<Return>", lambda _event: self._jump_to_selected_field())
        self.field_search_combo.bind("<<ComboboxSelected>>", lambda _event: self._jump_to_selected_field())

        inspector_panel = ttk.LabelFrame(work_area, text="Свойства и связи", padding=10)
        inspector_panel.columnconfigure(0, weight=1)
        inspector_panel.rowconfigure(3, weight=1)
        header_row = ttk.Frame(inspector_panel)
        header_row.grid(row=0, column=0, sticky="ew")
        header_row.columnconfigure(0, weight=1)
        ttk.Label(
            header_row,
            textvariable=self.inspector_title_var,
            font=("Segoe UI", 11, "bold"),
            wraplength=280,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            header_row,
            text="?",
            width=3,
            command=self._show_selected_field_help,
        ).grid(row=0, column=1, sticky="ne", padx=(8, 0))
        facts_box = ttk.LabelFrame(inspector_panel, text="Текущее поле", padding=8)
        facts_box.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        facts_box.columnconfigure(0, weight=1)
        ttk.Label(
            facts_box,
            textvariable=self.inspector_section_var,
            foreground="#355c7d",
            wraplength=280,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Label(
            facts_box,
            textvariable=self.inspector_unit_var,
            wraplength=280,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(
            facts_box,
            textvariable=self.inspector_range_var,
            wraplength=280,
            justify="left",
        ).grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(
            facts_box,
            textvariable=self.inspector_context_var,
            wraplength=280,
            justify="left",
        ).grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(
            facts_box,
            textvariable=self.inspector_help_var,
            wraplength=280,
            justify="left",
            foreground="#4b5563",
        ).grid(row=4, column=0, sticky="ew", pady=(8, 0))
        related_box = ttk.LabelFrame(inspector_panel, text="Связанные параметры", padding=8)
        related_box.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        related_box.columnconfigure(0, weight=1)
        related_box.rowconfigure(0, weight=1)
        related_tree_host, self.inspector_related_tree = build_scrolled_treeview(
            related_box,
            show="tree",
            selectmode="browse",
            height=6,
        )
        related_tree_host.grid(row=0, column=0, sticky="nsew")
        self.inspector_related_tree.bind("<Double-1>", lambda _event: self._jump_to_inspector_related_field())
        ttk.Label(
            related_box,
            textvariable=self.inspector_related_summary_var,
            wraplength=260,
            justify="left",
            foreground="#555555",
        ).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        related_actions = ttk.Frame(related_box)
        related_actions.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        related_actions.columnconfigure(0, weight=1)
        related_actions.columnconfigure(1, weight=1)
        ttk.Button(
            related_actions,
            text="Перейти к полю",
            command=self._jump_to_inspector_related_field,
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            related_actions,
            text="Поля раздела",
            command=self._show_current_section_fields_in_search,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.graphics_panel = DesktopInputGraphicPanel(inspector_panel)
        self.graphics_panel.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        work_area.add(inspector_panel, weight=0)

        notebook = ttk.Notebook(center_panel, style="InputEditor.TNotebook")
        notebook.grid(row=1, column=0, sticky="nsew")
        self.section_notebook = notebook
        self.section_notebook.bind("<<NotebookTabChanged>>", self._on_section_tab_changed)

        for section in DESKTOP_INPUT_SECTIONS:
            tab = ScrollableSection(notebook)
            notebook.add(tab, text=section.title)
            tab.body.columnconfigure(0, weight=1)
            section_desc_label = ttk.Label(
                tab.body,
                text=section.description,
                wraplength=1000,
                justify="left",
            )
            section_desc_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 10))
            section_desc_label.grid_remove()
            section_actions = ttk.Frame(tab.body)
            section_actions.grid(row=0, column=1, sticky="e", padx=12, pady=(12, 10))
            restore_button = ttk.Button(
                section_actions,
                text="Вернуть к рабочей точке",
                state="disabled",
                command=lambda sec=section: self._reset_section_to_source_reference(sec),
            )
            restore_button.grid(row=0, column=0, sticky="e")
            ttk.Button(
                section_actions,
                text="Вернуть раздел к значениям по умолчанию",
                command=lambda sec=section: self._reset_section_to_defaults(sec),
            ).grid(row=0, column=1, sticky="e", padx=(8, 0))

            summary_frame = ttk.LabelFrame(
                tab.body,
                text="Сводка по текущему кластеру",
                padding=8,
            )
            summary_frame.grid(
                row=1,
                column=0,
                columnspan=2,
                sticky="ew",
                padx=12,
                pady=(0, 10),
            )
            summary_frame.columnconfigure(0, weight=1)
            summary_var = tk.StringVar(
                value="Сводка кластера обновляется по текущим значениям."
            )
            summary_label = ttk.Label(
                summary_frame,
                textvariable=summary_var,
                wraplength=980,
                justify="left",
                foreground="#355c7d",
            )
            summary_label.grid(row=0, column=0, sticky="w")
            issue_button = ttk.Button(
                summary_frame,
                text="Перейти к замечанию",
                state="disabled",
                command=lambda section_title=section.title: self._jump_to_section_issue(section_title),
            )
            issue_button.grid(row=0, column=1, sticky="ne", padx=(12, 0))
            search_button = ttk.Button(
                summary_frame,
                text="Показать параметры кластера",
                command=lambda section_title=section.title: self._show_section_search_from_summary(section_title),
            )
            search_button.grid(row=0, column=2, sticky="ne", padx=(8, 0))
            summary_frame.grid_remove()
            self.section_summary_vars[section.title] = summary_var
            self.section_summary_labels[section.title] = summary_label
            self.section_issue_buttons[section.title] = issue_button
            self.section_restore_buttons[section.title] = restore_button
            self.section_search_buttons[section.title] = search_button
            graphic_panel = DesktopInputGraphicPanel(tab.body)
            graphic_panel.grid(
                row=2,
                column=0,
                columnspan=2,
                sticky="ew",
                padx=12,
                pady=(0, 10),
            )
            graphic_panel.grid_remove()
            if not hasattr(self, "section_graphics_panels"):
                self.section_graphics_panels = {}
            self.section_graphics_panels[section.title] = graphic_panel

            for idx, spec in enumerate(section.fields, start=3):
                field_row = ttk.Frame(tab.body, padding=(8, 4))
                field_row.grid(row=idx, column=0, sticky="ew", padx=10, pady=(4, 0))
                field_row.columnconfigure(1, weight=1)
                self._field_frames[spec.key] = field_row
                self._field_row_by_key[spec.key] = idx
                self._field_tabs_by_key[spec.key] = tab
                name_label = ttk.Label(
                    field_row,
                    text=spec.label,
                    width=28,
                    justify="left",
                    anchor="nw",
                    wraplength=220,
                )
                name_label.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 12))
                self._build_field_controls(field_row, spec)
                self._decorate_field_frame(field_row, spec)

        self._refresh_field_visibility()
        self._refresh_selected_section_graphics()

        log_frame = ttk.LabelFrame(actions_service_tab.body, text="Журнал проверки и расчёта", padding=8)
        log_frame.pack(fill="both", expand=False, pady=(12, 0))
        log_body, self.run_log = build_scrolled_text(log_frame, height=12, wrap="word")
        log_body.pack(fill="both", expand=True)
        self.run_log.configure(state="disabled")
        self._append_run_log("Editor готов. Можно менять исходные данные и сразу запускать проверку или preview-расчёт.")
        self._set_service_panels_visible(False)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side="left", anchor="w")
        ttk.Label(
            footer,
            text="Подсказка: default_base.json не перезаписывается автоматически.",
            foreground="#555555",
        ).pack(side="right", anchor="e")
        ttk.Sizegrip(footer).pack(side="right", anchor="se", padx=(12, 0))

    def _build_field_restore_button(
        self,
        frame: ttk.Frame,
        spec: DesktopInputFieldSpec,
    ) -> None:
        button = ttk.Button(
            frame,
            text="Совпадает",
            state="disabled",
            command=lambda key=spec.key: self._restore_field_to_source_reference(key),
        )
        button.grid(row=1, column=6, sticky="e", padx=(10, 0), pady=(4, 0))
        self.field_restore_buttons[spec.key] = button

    def _build_field_controls(self, frame: ttk.Frame, spec: DesktopInputFieldSpec) -> None:
        if spec.control == "bool":
            var = tk.BooleanVar(value=False)
            ttk.Checkbutton(frame, text="Включить", variable=var).grid(row=0, column=1, sticky="w")
            value_label = ttk.Label(frame, text="")
            value_label.grid(row=1, column=1, columnspan=5, sticky="w", pady=(4, 0))
            self.vars[spec.key] = var
            self._widget_handles[spec.key] = (spec, value_label)
            self._build_field_restore_button(frame, spec)
            var.trace_add("write", lambda *_args, key=spec.key: self._on_field_var_changed(key))
            return

        if spec.control == "choice":
            var = tk.StringVar(value=spec.to_ui(spec.choices[0] if spec.choices else ""))
            combo = ttk.Combobox(
                frame,
                textvariable=var,
                values=list(spec.display_choices or spec.choices),
                state="readonly",
                width=28,
            )
            combo.grid(row=0, column=1, columnspan=2, sticky="ew")
            value_label = ttk.Label(frame, text="")
            value_label.grid(row=1, column=1, columnspan=5, sticky="w", pady=(4, 0))
            self.vars[spec.key] = var
            self._widget_handles[spec.key] = (spec, value_label)
            self._build_field_restore_button(frame, spec)
            var.trace_add("write", lambda *_args, key=spec.key: self._on_field_var_changed(key))
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
            scale.grid(row=0, column=1, sticky="ew")
            spin = ttk.Spinbox(
                frame,
                from_=int(spec.min_value or 0),
                to=int(spec.max_value or 100),
                increment=int(spec.step or 1),
                textvariable=var,
                width=12,
            )
            spin.grid(row=0, column=2, sticky="w", padx=(10, 0))
            value_label = ttk.Label(frame, text="")
            value_label.grid(row=1, column=1, columnspan=5, sticky="w", pady=(4, 0))
            self.vars[spec.key] = var
            self._widget_handles[spec.key] = (spec, value_label)
            self._build_field_restore_button(frame, spec)
            var.trace_add("write", lambda *_args, key=spec.key: self._on_field_var_changed(key))
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
        scale.grid(row=0, column=1, sticky="ew")
        spin = ttk.Spinbox(
            frame,
            from_=float(spec.min_value or 0.0),
            to=float(spec.max_value or 1.0),
            increment=float(spec.step or 0.01),
            textvariable=var,
            width=12,
            format=f"%.{int(spec.digits)}f",
        )
        spin.grid(row=0, column=2, sticky="w", padx=(10, 0))
        value_label = ttk.Label(frame, text="")
        value_label.grid(row=1, column=1, columnspan=5, sticky="w", pady=(4, 0))
        self.vars[spec.key] = var
        self._widget_handles[spec.key] = (spec, value_label)
        self._build_field_restore_button(frame, spec)
        var.trace_add("write", lambda *_args, key=spec.key: self._on_field_var_changed(key))

    def _decorate_field_frame(self, frame: ttk.Frame, spec: DesktopInputFieldSpec) -> None:
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        attach_tooltip(frame, spec.effective_tooltip_text)
        if str(spec.unit_label or "").strip():
            unit_label = ttk.Label(
                frame,
                text=spec.unit_label,
                foreground="#355c7d",
            )
            unit_label.grid(row=0, column=3, sticky="w", padx=(10, 0))
        help_button = ttk.Button(
            frame,
            text="?",
            width=3,
            command=lambda current_spec=spec: self._show_field_help(current_spec),
        )
        help_button.grid(row=0, column=5, sticky="e", padx=(10, 0))
        attach_tooltip(help_button, spec.effective_tooltip_text)
        ttk.Separator(frame, orient="horizontal").grid(
            row=2,
            column=0,
            columnspan=7,
            sticky="ew",
            pady=(6, 0),
        )
        for child in frame.winfo_children():
            attach_tooltip(child, spec.effective_tooltip_text)
            try:
                child.bind("<Button-1>", lambda _event, key=spec.key: self._select_field(key), add="+")
                child.bind("<FocusIn>", lambda _event, key=spec.key: self._select_field(key), add="+")
            except Exception:
                continue

    def _show_field_help(self, spec: DesktopInputFieldSpec) -> None:
        show_help_dialog(
            self.root,
            title=spec.effective_help_title or spec.label,
            headline=f"{spec.label} ({spec.unit_label or 'безразмерно'})",
            body=spec.effective_help_body,
        )

    def _show_selected_field_help(self) -> None:
        if self._selected_field_spec is None:
            return
        self._show_field_help(self._selected_field_spec)

    def _select_field(self, key: str) -> None:
        handle = self._widget_handles.get(str(key))
        if handle is None:
            return
        spec, _label = handle
        self._selected_field_key = spec.key
        self._selected_field_spec = spec
        section_title = self._section_title_by_key.get(spec.key, "—")
        self.inspector_title_var.set(spec.label)
        self.inspector_section_var.set(f"Раздел: {section_title}")
        self.inspector_unit_var.set(f"Единица: {spec.unit_label or 'безразмерно'}")
        self.inspector_range_var.set(f"Диапазон: {spec.range_text}")
        self.inspector_context_var.set(
            f"Контекст: {self._graphic_context_title(spec.effective_graphic_context) or 'общий'}"
        )
        self.inspector_help_var.set(spec.effective_tooltip_text or spec.description)
        self._refresh_inspector_related_fields(spec)
        payload = self._gather_payload()
        self._refresh_graphics_for_section(
            section_title=section_title,
            payload=payload,
            spec=spec,
        )

    def _refresh_field_visibility(self) -> None:
        show_advanced = bool(self.show_advanced_var.get())
        for spec in field_spec_map().values():
            frame = self._field_frames.get(spec.key)
            row = self._field_row_by_key.get(spec.key)
            if frame is None or row is None:
                continue
            should_show = show_advanced or spec.effective_user_level != "advanced"
            if should_show:
                frame.grid()
            else:
                frame.grid_remove()

    def _refresh_source_reference_diff_state(self) -> None:
        diffs = build_desktop_profile_diff(
            self._gather_payload(),
            self.source_reference_payload,
        )
        self.source_reference_diffs_by_key = {
            str(item.get("key") or ""): item for item in diffs
        }

    def _on_field_var_changed(self, key: str) -> None:
        self._refresh_source_reference_diff_state()
        self._refresh_value_label(key)
        self._refresh_config_summary()
        self._refresh_section_route_summary()
        self._refresh_section_header_summaries()
        self._select_field(key)
        if self.compare_target_path is not None:
            self._refresh_profile_comparison()
        else:
            self._refresh_active_field_search_view()

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
        run_profile_key = self._selected_run_profile_key()
        self.run_context_var.set(
            "\n".join(
                (
                    f"Источник параметров: {self._display_source_name()}",
                    f"Активный профиль: {active_profile}",
                    f"Последний снимок: {active_snapshot}",
                    f"Сравнение с профилем: {compare_profile}",
                    f"Автоснимок перед запуском: {snapshot_policy}",
                    f"Run setup: {run_profile_label(run_profile_key)}; cache {cache_policy_label(str(self.run_cache_policy_var.get() or 'reuse'))}; runtime policy {runtime_policy_label(str(self.run_runtime_policy_var.get() or 'balanced'))}.",
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
        info = describe_run_setup_snapshot(
            self._gather_run_settings_snapshot(),
            scenario_label=self._selected_run_scenario_label(),
            preview_surface_label=preview_surface_label(self._selected_preview_surface_key()),
            snapshot_enabled=bool(self.snapshot_before_run_var.get()),
            snapshot_name=str(self.snapshot_name_var.get() or "").strip() or "перед_запуском",
        )
        selfcheck_report_path = self._runtime_selfcheck_report_path()
        selfcheck_report_exists = selfcheck_report_path.exists()
        selfcheck_report = self._load_selfcheck_report(selfcheck_report_path)
        selfcheck_modified_at = ""
        if selfcheck_report_exists:
            try:
                selfcheck_modified_at = datetime.fromtimestamp(
                    selfcheck_report_path.stat().st_mtime
                ).strftime("%Y-%m-%d %H:%M")
            except Exception:
                selfcheck_modified_at = ""
        selfcheck_has_signature, selfcheck_is_stale = self._selfcheck_freshness_state(
            selfcheck_report
        )
        selfcheck_line = describe_selfcheck_gate_status(
            selfcheck_report,
            report_exists=selfcheck_report_exists,
            modified_at=selfcheck_modified_at,
            has_signature=selfcheck_has_signature,
            is_stale=selfcheck_is_stale,
        )
        launch_route_line = describe_run_launch_route(
            auto_check_enabled=bool(self.run_auto_check_var.get()),
            runtime_policy_key=str(self.run_runtime_policy_var.get() or "balanced"),
            summary=selfcheck_report,
            report_exists=selfcheck_report_exists,
            has_signature=selfcheck_has_signature,
            is_stale=selfcheck_is_stale,
        )
        launch_outlook_line = describe_run_launch_outlook(
            auto_check_enabled=bool(self.run_auto_check_var.get()),
            runtime_policy_key=str(self.run_runtime_policy_var.get() or "balanced"),
            summary=selfcheck_report,
            report_exists=selfcheck_report_exists,
            has_signature=selfcheck_has_signature,
            is_stale=selfcheck_is_stale,
        )
        launch_recommendation_line = describe_run_launch_recommendation(
            auto_check_enabled=bool(self.run_auto_check_var.get()),
            runtime_policy_key=str(self.run_runtime_policy_var.get() or "balanced"),
            summary=selfcheck_report,
            report_exists=selfcheck_report_exists,
            has_signature=selfcheck_has_signature,
            is_stale=selfcheck_is_stale,
        )
        self.run_launch_summary_var.set(
            "\n".join(
                (
                    str(info.get("headline") or "").strip(),
                    str(info.get("preview_line") or "").strip(),
                    str(info.get("detail_line") or "").strip(),
                    str(info.get("runtime_line") or "").strip(),
                    selfcheck_line,
                    launch_route_line,
                    launch_outlook_line,
                    launch_recommendation_line,
                )
            ).strip()
        )

    def _current_latest_run_dir(self) -> Path | None:
        if self.active_run_dir is not None and self.active_run_dir.exists():
            return self.active_run_dir.resolve()
        run_dirs = list_desktop_run_dirs()
        if not run_dirs:
            self.active_run_dir = None
            self.active_run_summary_path = None
            self.active_run_log_path = None
            self.active_run_cache_dir = None
            self.active_run_saved_files = {}
            return None
        latest = run_dirs[0].resolve()
        self.active_run_dir = latest
        self.active_run_summary_path = desktop_run_summary_path(latest)
        return latest

    def _latest_run_log_path_from_summary(self, summary: dict[str, object] | None) -> Path | None:
        raw = str(dict(summary or {}).get("ui_subprocess_log") or "").strip()
        if not raw:
            return None
        try:
            return Path(raw).resolve()
        except Exception:
            return None

    def _latest_run_cache_dir_from_summary(self, summary: dict[str, object] | None) -> Path | None:
        current = dict(summary or {})
        raw = str(current.get("cache_dir") or "").strip()
        if not raw:
            cache_policy = str(current.get("cache_policy") or "off").strip().lower() or "off"
            cache_key = str(current.get("cache_key") or "").strip()
            if cache_policy != "off" and cache_key:
                try:
                    return desktop_single_run_cache_dir(cache_key)
                except Exception:
                    return None
            return None
        try:
            return Path(raw).resolve()
        except Exception:
            return None

    def _latest_run_saved_files_from_summary(self, summary: dict[str, object] | None) -> dict[str, str]:
        raw = dict(summary or {}).get("saved_files")
        if not isinstance(raw, dict):
            return {}
        saved: dict[str, str] = {}
        for key, value in raw.items():
            text = str(value or "").strip()
            if not text:
                continue
            try:
                saved[str(key)] = str(Path(text).resolve())
            except Exception:
                saved[str(key)] = text
        return saved

    def _latest_saved_file_path(self, key: str) -> Path | None:
        raw = str(self.active_run_saved_files.get(str(key), "")).strip()
        if not raw:
            return None
        try:
            return Path(raw).resolve()
        except Exception:
            return None

    def _refresh_latest_run_summary(self) -> None:
        latest_dir = self._current_latest_run_dir()
        if latest_dir is None:
            self.active_run_log_path = None
            self.active_run_cache_dir = None
            self.active_run_saved_files = {}
            self.latest_run_summary_var.set(
                f"Подробные расчёты ещё не запускались.\nПапка запусков: {desktop_runs_dir_path()}"
            )
            return

        summary_path = desktop_run_summary_path(latest_dir)
        self.active_run_dir = latest_dir
        self.active_run_summary_path = summary_path
        if not summary_path.exists():
            self.active_run_log_path = None
            self.active_run_cache_dir = None
            self.active_run_saved_files = {}
            self.latest_run_summary_var.set(
                "\n".join(
                    (
                        f"Последний запуск: {latest_dir.name}",
                        "run_summary.json пока не найден.",
                        f"Папка запуска: {latest_dir}",
                    )
                )
            )
            return

        try:
            summary = load_desktop_run_summary(summary_path)
        except Exception as exc:
            self.active_run_log_path = None
            self.active_run_cache_dir = None
            self.active_run_saved_files = {}
            self.latest_run_summary_var.set(
                "\n".join(
                    (
                        f"Последний запуск: {latest_dir.name}",
                        f"Не удалось прочитать run_summary.json: {exc}",
                        f"Путь к summary: {summary_path}",
                    )
                )
            )
            return

        self.active_run_log_path = self._latest_run_log_path_from_summary(summary)
        self.active_run_cache_dir = self._latest_run_cache_dir_from_summary(summary)
        self.active_run_saved_files = self._latest_run_saved_files_from_summary(summary)
        info = describe_latest_run_summary(
            summary,
            latest_run_name=latest_dir.name,
            latest_run_dir=str(latest_dir),
        )
        artifact_line = str(info.get("artifact_line") or "").strip()
        if not artifact_line:
            artifact_line = f"Папка артефактов: {summary.get('outdir') or latest_dir}"
        self.latest_run_summary_var.set(
            "\n".join(
                (
                    str(info.get("headline") or "").strip(),
                    str(info.get("scenario_line") or "").strip(),
                    str(info.get("runtime_line") or "").strip(),
                    str(info.get("mode_line") or "").strip(),
                    str(info.get("health_line") or "").strip(),
                    str(info.get("artifact_state_line") or "").strip(),
                    str(info.get("cache_line") or "").strip(),
                    str(info.get("log_line") or "").strip(),
                    artifact_line,
                )
            )
        )

    def _refresh_value_label(self, key: str) -> None:
        handle = self._widget_handles.get(key)
        var = self.vars.get(key)
        if handle is None or var is None:
            return
        spec, label = handle
        restore_button = self.field_restore_buttons.get(key)
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
        compare_diff = key in self.compare_diffs_by_key
        source_diff = key in self.source_reference_diffs_by_key
        if compare_diff and source_diff:
            label.configure(
                text=f"{text} · изменено и от рабочей точки",
                foreground="#8a4b00",
            )
        elif compare_diff:
            label.configure(text=f"{text} · изменено", foreground="#a05a00")
        elif source_diff:
            label.configure(
                text=f"{text} · изменено от рабочей точки",
                foreground="#16507a",
            )
        else:
            label.configure(text=text, foreground="#2f4f4f")
        if restore_button is not None:
            if source_diff:
                restore_button.configure(text="К рабочей точке", state="normal")
            else:
                restore_button.configure(text="Совпадает", state="disabled")

    def _bind_summary_var_traces(self) -> None:
        tracked_vars = (
            self.preview_surface_var,
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
            self.run_profile_var,
            self.run_scenario_var,
            self.run_dt_var,
            self.run_t_end_var,
            self.run_record_full_var,
            self.run_primary_value_var,
            self.run_secondary_value_var,
            self.run_cache_policy_var,
            self.run_export_csv_var,
            self.run_export_npz_var,
            self.run_auto_check_var,
            self.run_log_to_file_var,
            self.run_runtime_policy_var,
        )
        for var in tracked_vars:
            var.trace_add("write", lambda *_args: self._refresh_config_summary())
            var.trace_add("write", lambda *_args: self._refresh_run_context_summary())
            var.trace_add("write", lambda *_args: self._refresh_run_mode_summary())
            var.trace_add("write", lambda *_args: self._refresh_run_launch_summary())
            var.trace_add("write", lambda *_args: self._refresh_run_profile_hint())
            var.trace_add("write", lambda *_args: self._refresh_run_policy_hints())
        self.preview_surface_var.trace_add(
            "write",
            lambda *_args: self._refresh_preview_surface_controls(),
        )
        self.run_scenario_var.trace_add(
            "write",
            lambda *_args: self._refresh_run_scenario_controls(),
        )

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

    def _selected_run_profile_key(self) -> str:
        key = str(self.run_profile_var.get() or "").strip().lower()
        known = {name for name, _label, _desc in DESKTOP_RUN_PROFILE_OPTIONS}
        return key if key in known else "detail"

    def _refresh_run_profile_hint(self) -> None:
        profile_key = self._selected_run_profile_key()
        label = run_profile_label(profile_key)
        description = run_profile_description(profile_key)
        self.run_profile_hint_var.set(
            f"Профиль запуска: {label}. {description}"
        )

    def _refresh_run_policy_hints(self) -> None:
        cache_key = str(self.run_cache_policy_var.get() or "").strip().lower() or "reuse"
        runtime_policy_key = str(self.run_runtime_policy_var.get() or "").strip().lower() or "balanced"
        self.run_cache_hint_var.set(
            f"Cache: {cache_policy_label(cache_key)}. {cache_policy_description(cache_key)}"
        )
        self.run_runtime_policy_hint_var.set(
            f"Runtime policy: {runtime_policy_label(runtime_policy_key)}. {runtime_policy_description(runtime_policy_key)}"
        )

    def _apply_run_setup_profile(self, profile_key: str) -> None:
        before_payload = self._gather_payload()
        before_run = self._gather_run_settings_snapshot()
        updated, changed_keys = apply_run_setup_profile(
            before_run,
            profile_key,
            scenario_key=self._selected_run_scenario_key(),
        )
        label = run_profile_label(profile_key)
        description = run_profile_description(profile_key)
        if not changed_keys:
            self.run_profile_var.set(str(updated.get("launch_profile") or profile_key))
            self.run_preset_hint_var.set(
                f"Профиль запуска «{label}» уже активен."
            )
            self._set_status(f"Профиль запуска «{label}» уже применён.")
            return
        self._remember_safe_action(
            f"Профиль запуска: {label}",
            before_payload,
            changed_count=len(changed_keys),
            run_settings_snapshot=before_run,
        )
        self._restore_run_settings_snapshot(updated)
        self.run_preset_hint_var.set(
            f"Профиль запуска «{label}» применён. {description} Изменено runtime-настроек: {len(changed_keys)}."
        )
        self._set_status(f"Применён профиль запуска: {label}")
        self._append_run_log(
            f"[run-profile] {label}: изменено runtime-настроек {len(changed_keys)}"
        )

    def _open_run_setup_center(self) -> None:
        existing = self._run_setup_center
        try:
            if existing is not None:
                existing.focus()
                return
        except Exception:
            self._run_setup_center = None
        from pneumo_solver_ui.tools.desktop_run_setup_center import DesktopRunSetupCenter

        self._run_setup_center = DesktopRunSetupCenter(self)

    def _focus_toplevel_controller(self, controller: object) -> bool:
        root = getattr(controller, "root", None)
        if root is None:
            return False
        try:
            root.deiconify()
            root.lift()
            root.focus_force()
            return True
        except Exception:
            return False

    def _open_geometry_reference_center(self) -> None:
        existing = self._geometry_reference_center
        try:
            if existing is not None and self._focus_toplevel_controller(existing):
                self._set_status("Открыт справочный центр геометрии и каталогов.")
                return
        except Exception:
            pass
        self._geometry_reference_center = None
        from pneumo_solver_ui.tools.desktop_geometry_reference_center import (
            DesktopGeometryReferenceCenter,
        )

        window = tk.Toplevel(self.root)
        self._geometry_reference_center = DesktopGeometryReferenceCenter(window, hosted=True)
        self._set_status("Открыт справочный центр геометрии и каталогов.")

    def _open_diagnostics_center(self) -> None:
        existing = self._diagnostics_center
        try:
            if existing is not None and self._focus_toplevel_controller(existing):
                self._set_status("Открыт центр диагностики и отправки.")
                return
        except Exception:
            pass
        self._diagnostics_center = None
        from pneumo_solver_ui.tools.desktop_diagnostics_center import DesktopDiagnosticsCenter

        window = tk.Toplevel(self.root)
        self._diagnostics_center = DesktopDiagnosticsCenter(window, hosted=True, initial_tab="restore")
        self._set_status("Открыт центр диагностики и отправки.")

    def _notify_run_setup_center_closed(self) -> None:
        self._run_setup_center = None

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
            (
                f"Run setup: {run_profile_label(self._selected_run_profile_key())}; "
                f"cache={cache_policy_label(str(self.run_cache_policy_var.get() or 'reuse'))}; "
                f"NPZ={'да' if bool(self.run_export_npz_var.get()) else 'нет'}; "
                f"auto-check={'да' if bool(self.run_auto_check_var.get()) else 'нет'}."
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
            "launch_profile": self._selected_run_profile_key(),
            "scenario_key": self._selected_run_scenario_key(),
            "preview_dt": float(self.preview_dt_var.get()),
            "preview_t_end": float(self.preview_t_end_var.get()),
            "preview_road_len_m": float(self.preview_road_len_var.get()),
            "preview_surface_key": self._selected_preview_surface_key(),
            "preview_primary_value": float(self.preview_surface_primary_value_var.get()),
            "preview_secondary_value": float(self.preview_surface_secondary_value_var.get()),
            "preview_start_value": float(self.preview_surface_start_var.get()),
            "preview_angle_value": float(self.preview_surface_angle_var.get()),
            "preview_shape_value": float(self.preview_surface_shape_var.get()),
            "dt": float(self.run_dt_var.get()),
            "t_end": float(self.run_t_end_var.get()),
            "record_full": bool(self.run_record_full_var.get()),
            "primary_value": float(self.run_primary_value_var.get()),
            "secondary_value": float(self.run_secondary_value_var.get()),
            "cache_policy": str(self.run_cache_policy_var.get() or "reuse"),
            "export_csv": bool(self.run_export_csv_var.get()),
            "export_npz": bool(self.run_export_npz_var.get()),
            "auto_check": bool(self.run_auto_check_var.get()),
            "write_log_file": bool(self.run_log_to_file_var.get()),
            "runtime_policy": str(self.run_runtime_policy_var.get() or "balanced"),
        }

    def _restore_run_settings_snapshot(self, snapshot: dict[str, object] | None) -> None:
        if not snapshot:
            return
        profile_key = str(snapshot.get("launch_profile") or "").strip().lower()
        if profile_key:
            self.run_profile_var.set(profile_key)
        scenario_key = str(snapshot.get("scenario_key") or "").strip()
        if scenario_key and scenario_key in self.run_scenario_key_to_label:
            self.run_scenario_var.set(self.run_scenario_key_to_label[scenario_key])
        preview_surface_key = str(snapshot.get("preview_surface_key") or "").strip()
        if preview_surface_key and preview_surface_key in self.preview_surface_key_to_label:
            self.preview_surface_var.set(self.preview_surface_key_to_label[preview_surface_key])
        elif preview_surface_key and preview_surface_key in self.preview_surface_label_to_key:
            self.preview_surface_var.set(preview_surface_key)
        try:
            self.preview_dt_var.set(float(snapshot.get("preview_dt", self.preview_dt_var.get())))
        except Exception:
            pass
        try:
            self.preview_t_end_var.set(float(snapshot.get("preview_t_end", self.preview_t_end_var.get())))
        except Exception:
            pass
        try:
            self.preview_road_len_var.set(float(snapshot.get("preview_road_len_m", self.preview_road_len_var.get())))
        except Exception:
            pass
        try:
            self.preview_surface_primary_value_var.set(float(snapshot.get("preview_primary_value", self.preview_surface_primary_value_var.get())))
        except Exception:
            pass
        try:
            self.preview_surface_secondary_value_var.set(float(snapshot.get("preview_secondary_value", self.preview_surface_secondary_value_var.get())))
        except Exception:
            pass
        try:
            self.preview_surface_start_var.set(float(snapshot.get("preview_start_value", self.preview_surface_start_var.get())))
        except Exception:
            pass
        try:
            self.preview_surface_angle_var.set(float(snapshot.get("preview_angle_value", self.preview_surface_angle_var.get())))
        except Exception:
            pass
        try:
            self.preview_surface_shape_var.set(float(snapshot.get("preview_shape_value", self.preview_surface_shape_var.get())))
        except Exception:
            pass
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
        try:
            self.run_cache_policy_var.set(str(snapshot.get("cache_policy", self.run_cache_policy_var.get()) or "reuse"))
        except Exception:
            pass
        try:
            self.run_export_csv_var.set(bool(snapshot.get("export_csv", self.run_export_csv_var.get())))
        except Exception:
            pass
        try:
            self.run_export_npz_var.set(bool(snapshot.get("export_npz", self.run_export_npz_var.get())))
        except Exception:
            pass
        try:
            self.run_auto_check_var.set(bool(snapshot.get("auto_check", self.run_auto_check_var.get())))
        except Exception:
            pass
        try:
            self.run_log_to_file_var.set(bool(snapshot.get("write_log_file", self.run_log_to_file_var.get())))
        except Exception:
            pass
        try:
            self.run_runtime_policy_var.set(str(snapshot.get("runtime_policy", self.run_runtime_policy_var.get()) or "balanced"))
        except Exception:
            pass
        self._refresh_preview_surface_controls()
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
            self._load_into_vars(
                merged,
                self.current_source_path,
                refresh_source_reference=True,
            )
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

    def _open_path(self, target: Path, *, success_text: str, error_title: str) -> bool:
        try:
            if os.name == "nt":
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
            self._set_status(success_text)
            return True
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"{error_title}:\n{exc}")
            return False

    def _open_latest_run_dir(self) -> None:
        latest_dir = self._current_latest_run_dir()
        if latest_dir is None:
            messagebox.showinfo("Desktop Input Editor", "Папка последнего запуска пока не найдена.")
            return
        self._open_path(
            latest_dir,
            success_text=f"Открыта папка запуска: {latest_dir}",
            error_title="Не удалось открыть папку запуска",
        )

    def _open_latest_preview_report_json(self) -> None:
        report_path = self._runtime_preview_report_path()
        self.active_preview_report_path = report_path
        if not report_path.exists():
            messagebox.showinfo("Desktop Input Editor", "preview_report.json пока не найден.")
            return
        self._open_path(
            report_path,
            success_text=f"Открыт preview_report.json: {report_path}",
            error_title="Не удалось открыть preview_report.json",
        )

    def _open_latest_selfcheck_report_json(self) -> None:
        report_path = self._runtime_selfcheck_report_path()
        self.active_selfcheck_report_path = report_path
        if not report_path.exists():
            messagebox.showinfo("Desktop Input Editor", "selfcheck_report.json пока не найден.")
            return
        self._open_path(
            report_path,
            success_text=f"Открыт selfcheck_report.json: {report_path}",
            error_title="Не удалось открыть selfcheck_report.json",
        )

    def _open_latest_selfcheck_log(self) -> None:
        report_path = self._runtime_selfcheck_report_path()
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                if isinstance(report, dict):
                    self.active_selfcheck_log_path = self._selfcheck_log_path_from_report(report)
            except Exception:
                pass
        log_path = self.active_selfcheck_log_path
        if log_path is None:
            messagebox.showinfo("Desktop Input Editor", "Лог последнего selfcheck пока не найден.")
            return
        if not log_path.exists():
            messagebox.showinfo(
                "Desktop Input Editor",
                f"Файл лога последнего selfcheck не найден:\n{log_path}",
            )
            return
        self._open_path(
            log_path,
            success_text=f"Открыт selfcheck-лог: {log_path}",
            error_title="Не удалось открыть selfcheck-лог",
        )

    def _open_latest_preview_log(self) -> None:
        report_path = self._runtime_preview_report_path()
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                if isinstance(report, dict):
                    self.active_preview_log_path = self._preview_log_path_from_report(report)
            except Exception:
                pass
        log_path = self.active_preview_log_path
        if log_path is None:
            messagebox.showinfo("Desktop Input Editor", "Лог последнего preview пока не найден.")
            return
        if not log_path.exists():
            messagebox.showinfo(
                "Desktop Input Editor",
                f"Файл лога последнего preview не найден:\n{log_path}",
            )
            return
        self._open_path(
            log_path,
            success_text=f"Открыт preview-лог: {log_path}",
            error_title="Не удалось открыть preview-лог",
        )

    def _open_run_setup_cache_root(self) -> None:
        root = desktop_run_setup_cache_root()
        root.mkdir(parents=True, exist_ok=True)
        self._open_path(
            root,
            success_text=f"Открыта папка runtime-cache: {root}",
            error_title="Не удалось открыть папку runtime-cache",
        )

    def _open_run_setup_log_root(self) -> None:
        root = desktop_run_setup_log_root()
        root.mkdir(parents=True, exist_ok=True)
        self._open_path(
            root,
            success_text=f"Открыта папка runtime-логов: {root}",
            error_title="Не удалось открыть папку runtime-логов",
        )

    def _open_latest_run_summary_json(self) -> None:
        latest_dir = self._current_latest_run_dir()
        if latest_dir is None:
            messagebox.showinfo("Desktop Input Editor", "run_summary.json пока не найден.")
            return
        summary_path = desktop_run_summary_path(latest_dir)
        if not summary_path.exists():
            messagebox.showinfo("Desktop Input Editor", "run_summary.json пока не найден.")
            return
        self._open_path(
            summary_path,
            success_text=f"Открыт run_summary.json: {summary_path}",
            error_title="Не удалось открыть run_summary.json",
        )

    def _open_latest_run_log(self) -> None:
        if self.active_run_summary_path is not None and self.active_run_summary_path.exists():
            try:
                summary = load_desktop_run_summary(self.active_run_summary_path)
                self.active_run_log_path = self._latest_run_log_path_from_summary(summary)
                self.active_run_cache_dir = self._latest_run_cache_dir_from_summary(summary)
                self.active_run_saved_files = self._latest_run_saved_files_from_summary(summary)
            except Exception:
                pass
        log_path = self.active_run_log_path
        if log_path is None:
            messagebox.showinfo("Desktop Input Editor", "Лог последнего запуска пока не найден.")
            return
        if not log_path.exists():
            messagebox.showinfo(
                "Desktop Input Editor",
                f"Файл лога последнего запуска не найден:\n{log_path}",
            )
            return
        self._open_path(
            log_path,
            success_text=f"Открыт run-лог: {log_path}",
            error_title="Не удалось открыть run-лог",
        )

    def _open_latest_run_cache_dir(self) -> None:
        if self.active_run_summary_path is not None and self.active_run_summary_path.exists():
            try:
                summary = load_desktop_run_summary(self.active_run_summary_path)
                self.active_run_cache_dir = self._latest_run_cache_dir_from_summary(summary)
                self.active_run_saved_files = self._latest_run_saved_files_from_summary(summary)
            except Exception:
                pass
        cache_dir = self.active_run_cache_dir
        if cache_dir is None:
            messagebox.showinfo("Desktop Input Editor", "Cache entry последнего запуска пока не найден.")
            return
        if not cache_dir.exists():
            messagebox.showinfo(
                "Desktop Input Editor",
                f"Папка cache entry последнего запуска не найдена:\n{cache_dir}",
            )
            return
        self._open_path(
            cache_dir,
            success_text=f"Открыта папка cache entry: {cache_dir}",
            error_title="Не удалось открыть папку cache entry",
        )

    def _open_latest_saved_file(self, key: str, *, label: str) -> None:
        if self.active_run_summary_path is not None and self.active_run_summary_path.exists():
            try:
                summary = load_desktop_run_summary(self.active_run_summary_path)
                self.active_run_cache_dir = self._latest_run_cache_dir_from_summary(summary)
                self.active_run_saved_files = self._latest_run_saved_files_from_summary(summary)
            except Exception:
                pass
        target = self._latest_saved_file_path(key)
        if target is None:
            messagebox.showinfo("Desktop Input Editor", f"{label} последнего запуска пока не найден.")
            return
        if not target.exists():
            messagebox.showinfo(
                "Desktop Input Editor",
                f"Файл {label} последнего запуска не найден:\n{target}",
            )
            return
        self._open_path(
            target,
            success_text=f"Открыт {label}: {target}",
            error_title=f"Не удалось открыть {label}",
        )

    def _open_latest_df_main_csv(self) -> None:
        self._open_latest_saved_file("df_main", label="df_main.csv")

    def _open_latest_npz_bundle(self) -> None:
        self._open_latest_saved_file("npz_bundle", label="NPZ bundle")

    def _open_desktop_runs_dir(self) -> None:
        root = desktop_runs_dir_path()
        root.mkdir(parents=True, exist_ok=True)
        self._open_path(
            root,
            success_text=f"Открыта папка запусков: {root}",
            error_title="Не удалось открыть папку запусков",
        )

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
            self._refresh_active_field_search_view()
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
            self._refresh_active_field_search_view()
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
        self._refresh_active_field_search_view()

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

    def _set_spinbox_state(self, widget: ttk.Spinbox | None, enabled: bool) -> None:
        if widget is None:
            return
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

    def _load_into_vars(
        self,
        payload: dict[str, object],
        source_path: Path,
        *,
        refresh_source_reference: bool = False,
    ) -> None:
        self.current_payload = dict(payload)
        self.current_source_path = source_path.resolve()
        if refresh_source_reference:
            self.source_reference_payload = dict(payload)
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
        self._refresh_source_reference_diff_state()
        for key in self._widget_handles:
            self._refresh_value_label(key)
        self._refresh_config_summary()
        self._refresh_run_context_summary()
        self._refresh_run_mode_summary()
        self._refresh_run_launch_summary()
        self._refresh_section_route_summary()
        self._refresh_section_header_summaries()
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
            self._load_into_vars(payload, target, refresh_source_reference=True)
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
            self._load_into_vars(merged, target, refresh_source_reference=True)
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
            self._load_into_vars(
                payload,
                default_base_json_path(),
                refresh_source_reference=True,
            )
            self._set_status("Загружены значения по умолчанию из default_base.json.")
        except Exception as exc:
            messagebox.showerror("Desktop Input Editor", f"Не удалось загрузить default_base.json:\n{exc}")

    def _save_working_copy(self) -> None:
        target = default_working_copy_path()
        try:
            payload = self._gather_payload()
            save_base_payload(target, payload)
            self.source_reference_payload = dict(payload)
            self.current_payload = dict(payload)
            self._refresh_source_reference_diff_state()
            self.current_source_path = target
            self.path_var.set(str(target))
            self._refresh_run_context_summary()
            for key in self._widget_handles:
                self._refresh_value_label(key)
            self._refresh_section_header_summaries()
            self._refresh_active_field_search_view()
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
        return desktop_runs_dir_path()

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
        log_file_path: Path | None = None,
        persist_stdout_json: bool = False,
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
                    if self._host_closed:
                        self._task_running = False
                        return
                    self._task_running = False
                    if stdout.strip():
                        self._append_run_log("[stdout]")
                        self._append_run_log(stdout.strip())
                    if stderr.strip():
                        self._append_run_log("[stderr]")
                        self._append_run_log(stderr.strip())
                    if log_file_path is not None:
                        try:
                            append_subprocess_log(
                                log_file_path,
                                title=title,
                                cmd=cmd,
                                returncode=int(proc.returncode),
                                stdout=stdout,
                                stderr=stderr,
                            )
                            self._append_run_log(f"[log] subprocess-лог сохранён: {log_file_path}")
                        except Exception as exc:
                            self._append_run_log(f"[warn] Не удалось записать subprocess-лог: {exc}")
                    if proc.returncode == 0:
                        if persist_stdout_json and result_path is not None:
                            saved = write_json_report_from_stdout(stdout, result_path)
                            if saved is None:
                                self._append_run_log("[warn] Не удалось выделить JSON из stdout команды.")
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
                    if self._host_closed:
                        self._task_running = False
                        return
                    self._task_running = False
                    self._set_status(f"Ошибка запуска: {title}")
                    self._append_run_log(f"[error] {exc}")
                    messagebox.showerror("Desktop Input Editor", f"Не удалось запустить команду:\n{exc}")

                self.root.after(0, _fail)

        threading.Thread(target=_worker, daemon=True).start()

    def _summarize_selfcheck_report(
        self,
        report_path: Path | None,
        *,
        log_file_path: Path | None = None,
    ) -> None:
        if report_path is None or not report_path.exists():
            self._append_run_log("[warn] report_json не найден после проверки конфигурации.")
            return
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("selfcheck_report.json должен содержать JSON object")
            report["ui_subject_signature"] = self._current_selfcheck_subject_signature()
            if log_file_path is not None:
                report["ui_subprocess_log"] = str(log_file_path.resolve())
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.active_selfcheck_report_path = report_path.resolve()
            self.active_selfcheck_log_path = self._selfcheck_log_path_from_report(report)
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
            self.active_selfcheck_log_path = None
            self._append_run_log(f"[warn] Не удалось разобрать report_json: {exc}")
        self._refresh_latest_selfcheck_summary()

    def _preview_log_path_from_report(self, report: dict[str, object] | None) -> Path | None:
        raw = str(dict(report or {}).get("ui_subprocess_log") or "").strip()
        if not raw:
            return None
        try:
            return Path(raw).resolve()
        except Exception:
            return None

    def _selfcheck_log_path_from_report(self, report: dict[str, object] | None) -> Path | None:
        raw = str(dict(report or {}).get("ui_subprocess_log") or "").strip()
        if not raw:
            return None
        try:
            return Path(raw).resolve()
        except Exception:
            return None

    def _refresh_latest_selfcheck_summary(self) -> None:
        report_path = self._runtime_selfcheck_report_path()
        self.active_selfcheck_report_path = report_path
        if not report_path.exists():
            self.active_selfcheck_log_path = None
            self.latest_selfcheck_summary_var.set(
                "\n".join(
                    (
                        "Auto-check / selfcheck ещё не запускался.",
                        f"Ожидаемый JSON отчёт: {report_path}",
                    )
                )
            )
            self._refresh_run_launch_summary()
            return
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("selfcheck_report.json должен содержать JSON object")
        except Exception as exc:
            self.active_selfcheck_log_path = None
            self.latest_selfcheck_summary_var.set(
                "\n".join(
                    (
                        "Последний auto-check найден, но отчёт не читается.",
                        f"Не удалось прочитать selfcheck_report.json: {exc}",
                        f"Путь к отчёту: {report_path}",
                    )
                )
            )
            self._refresh_run_launch_summary()
            return
        self.active_selfcheck_log_path = self._selfcheck_log_path_from_report(report)
        has_signature, is_stale = self._selfcheck_freshness_state(report)
        info = describe_latest_selfcheck_summary(
            report,
            report_path=str(report_path),
            has_signature=has_signature,
            is_stale=is_stale,
        )
        lines = [
            str(info.get("headline") or "").strip(),
            str(info.get("status_line") or "").strip(),
            str(info.get("freshness_line") or "").strip(),
            str(info.get("checks_line") or "").strip(),
            str(info.get("log_line") or "").strip(),
            str(info.get("report_line") or "").strip(),
            str(info.get("note_line") or "").strip(),
        ]
        self.latest_selfcheck_summary_var.set("\n".join(line for line in lines if line))
        self._refresh_run_launch_summary()

    def _refresh_latest_preview_summary(self) -> None:
        report_path = self._runtime_preview_report_path()
        self.active_preview_report_path = report_path
        if not report_path.exists():
            self.active_preview_log_path = None
            self.latest_preview_summary_var.set(
                "\n".join(
                    (
                        "Preview ещё не запускался.",
                        f"Ожидаемый JSON отчёт: {report_path}",
                    )
                )
            )
            return
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("preview_report.json должен содержать JSON object")
        except Exception as exc:
            self.active_preview_log_path = None
            self.latest_preview_summary_var.set(
                "\n".join(
                    (
                        "Последний preview найден, но отчёт не читается.",
                        f"Не удалось прочитать preview_report.json: {exc}",
                        f"Путь к отчёту: {report_path}",
                    )
                )
            )
            return
        self.active_preview_log_path = self._preview_log_path_from_report(report)
        info = describe_latest_preview_summary(report, report_path=str(report_path))
        lines = [
            str(info.get("headline") or "").strip(),
            str(info.get("surface_line") or "").strip(),
            str(info.get("metrics_line") or "").strip(),
            str(info.get("pressure_line") or "").strip(),
            str(info.get("log_line") or "").strip(),
            str(info.get("report_line") or "").strip(),
        ]
        note_line = str(info.get("note_line") or "").strip()
        if note_line:
            lines.append(note_line)
        self.latest_preview_summary_var.set("\n".join(line for line in lines if line))

    def _summarize_preview_report(
        self,
        report_path: Path | None,
        *,
        log_file_path: Path | None = None,
    ) -> None:
        if report_path is None or not report_path.exists():
            self._append_run_log("[warn] JSON preview-расчёта не найден.")
            return
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("preview_report.json должен содержать JSON object")
            report["preview_surface_key"] = self._selected_preview_surface_key()
            report["preview_surface_label"] = preview_surface_label(self._selected_preview_surface_key())
            report["preview_road_len_m"] = float(self.preview_road_len_var.get())
            if log_file_path is not None:
                report["ui_subprocess_log"] = str(log_file_path.resolve())
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.active_preview_report_path = report_path.resolve()
            self.active_preview_log_path = self._preview_log_path_from_report(report)
            self._append_run_log(
                "[summary] "
                f"roll_max={float(report.get('max_abs_phi_deg', 0.0)):.2f} deg; "
                f"pitch_max={float(report.get('max_abs_theta_deg', 0.0)):.2f} deg; "
                f"min_tire_Fz={float(report.get('min_tire_Fz_N', 0.0)):.1f} N; "
                f"max_tire_pen={float(report.get('max_tire_pen_m', 0.0)):.4f} m"
            )
            self._append_run_log(
                "[summary] "
                f"preview={report.get('preview_surface_label') or '—'}; "
                f"dt={float(report.get('dt_s', 0.0) or 0.0):.3f} с; "
                f"t_end={float(report.get('t_end_s', 0.0) or 0.0):.1f} с; "
                f"steps={int(report.get('n_steps', 0) or 0)}"
            )
            if self.active_preview_log_path is not None:
                self._append_run_log(f"[summary] UI preview-лог: {self.active_preview_log_path}")
        except Exception as exc:
            self.active_preview_log_path = None
            self._append_run_log(f"[warn] Не удалось разобрать JSON preview-расчёта: {exc}")
        self._refresh_latest_preview_summary()

    def _summarize_single_run_report(
        self,
        report_path: Path | None,
        *,
        log_file_path: Path | None = None,
    ) -> None:
        if report_path is None or not report_path.exists():
            self._append_run_log("[warn] JSON подробного расчёта не найден.")
            return
        self.active_run_summary_path = report_path.resolve()
        self.active_run_dir = report_path.resolve().parent
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("run_summary.json должен содержать JSON object")
            if log_file_path is not None:
                report["ui_subprocess_log"] = str(log_file_path.resolve())
                report_path.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            self.active_run_log_path = self._latest_run_log_path_from_summary(report)
            self.active_run_cache_dir = self._latest_run_cache_dir_from_summary(report)
            self._append_run_log(
                "[summary] "
                f"сценарий={report.get('scenario_name') or '—'}; "
                f"тип={report.get('scenario_type') or '—'}; "
                f"строк df_main={int(report.get('df_main_rows') or 0)}; "
                f"крен_peak={float(report.get('roll_peak_deg') or 0.0):.2f} град; "
                f"тангаж_peak={float(report.get('pitch_peak_deg') or 0.0):.2f} град"
            )
            self._append_run_log(
                "[summary] "
                f"профиль={run_profile_label(str(report.get('run_profile') or 'detail'))}; "
                f"cache={cache_policy_label(str(report.get('cache_policy') or 'off'))}; "
                f"cache-hit={'да' if bool(report.get('cache_hit')) else 'нет'}; "
                f"CSV={'да' if bool(report.get('export_csv', True)) else 'нет'}; "
                f"NPZ={'да' if bool(report.get('export_npz', False)) else 'нет'}"
            )
            mech_ok = report.get("mech_selfcheck_ok")
            mech_msg = str(report.get("mech_selfcheck_msg") or "").strip()
            if mech_ok is not None:
                self._append_run_log(
                    f"[summary] Самопроверка механики: {'в норме' if bool(mech_ok) else 'требует внимания'}"
                )
            if mech_msg:
                self._append_run_log(f"[summary] Сообщение: {mech_msg}")
            if self.active_run_log_path is not None:
                self._append_run_log(f"[summary] UI subprocess-лог: {self.active_run_log_path}")
            if self.active_run_cache_dir is not None:
                self._append_run_log(f"[summary] Cache entry: {self.active_run_cache_dir}")
            outdir = str(report.get("outdir") or "").strip()
            if outdir:
                self._append_run_log(f"[summary] Артефакты расчёта: {outdir}")
        except Exception as exc:
            self.active_run_log_path = None
            self.active_run_cache_dir = None
            self._append_run_log(f"[warn] Не удалось разобрать JSON подробного расчёта: {exc}")
        self._refresh_latest_run_summary()

    def _build_action_log_path(self, action_label: str) -> Path | None:
        if not bool(self.run_log_to_file_var.get()):
            return None
        try:
            return build_run_log_path(action_label)
        except Exception as exc:
            self._append_run_log(f"[warn] Не удалось подготовить путь для subprocess-лога: {exc}")
            return None

    def _current_selfcheck_subject_signature(self) -> str:
        return build_selfcheck_subject_signature(
            payload=self._gather_payload(),
            run_settings=self._gather_run_settings_snapshot(),
        )

    def _selfcheck_signature_from_report(self, report: dict[str, object] | None) -> str:
        return str(dict(report or {}).get("ui_subject_signature") or "").strip()

    def _selfcheck_freshness_state(self, report: dict[str, object] | None) -> tuple[bool, bool]:
        signature = self._selfcheck_signature_from_report(report)
        if not signature:
            return False, True
        return True, signature != self._current_selfcheck_subject_signature()

    def _load_selfcheck_report(self, report_path: Path | None) -> dict[str, object] | None:
        if report_path is None or not report_path.exists():
            return None
        try:
            raw = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return raw if isinstance(raw, dict) else None

    def _stored_selfcheck_allows_launch(self, run_label: str) -> bool:
        runtime_policy = str(self.run_runtime_policy_var.get() or "balanced").strip().lower() or "balanced"
        report_path = self._runtime_selfcheck_report_path()
        report = self._load_selfcheck_report(report_path)
        if report is None:
            issue_text = "последний сохранённый auto-check не найден"
            if runtime_policy == "force":
                self._append_run_log(
                    f"[auto-check] {run_label}: {issue_text}, продолжаем без повторной проверки по policy=force."
                )
                return True
            if runtime_policy == "strict":
                self._append_run_log(
                    f"[auto-check] {run_label}: {issue_text}, запуск остановлен по policy=strict."
                )
                self._set_status(f"Запуск остановлен: {run_label}")
                messagebox.showwarning(
                    "Desktop Input Editor",
                    (
                        f"Автоматический auto-check перед «{run_label}» выключен.\n\n"
                        "Последний сохранённый auto-check не найден.\n\n"
                        "Режим strict блокирует запуск без актуальной проверки. "
                        "Сначала выполните «Проверить конфигурацию»."
                    ),
                )
                return False
            if messagebox.askyesno(
                "Desktop Input Editor",
                (
                    f"Автоматический auto-check перед «{run_label}» выключен.\n\n"
                    "Последний сохранённый auto-check не найден.\n\n"
                    "Продолжить запуск без повторной проверки?"
                ),
            ):
                self._append_run_log(
                    f"[auto-check] {run_label}: запуск подтверждён без сохранённого auto-check."
                )
                return True
            self._append_run_log(
                f"[auto-check] {run_label}: запуск отменён пользователем без сохранённого auto-check."
            )
            self._set_status(f"Запуск отменён: {run_label}")
            return False

        has_signature, is_stale = self._selfcheck_freshness_state(report)
        if not has_signature or is_stale:
            issue_text = (
                "последний сохранённый auto-check устарел для текущих настроек"
                if is_stale
                else "последний сохранённый auto-check не привязан к текущей конфигурации"
            )
            if runtime_policy == "force":
                self._append_run_log(
                    f"[auto-check] {run_label}: {issue_text}, продолжаем без повторной проверки по policy=force."
                )
                return True
            if runtime_policy == "strict":
                self._append_run_log(
                    f"[auto-check] {run_label}: {issue_text}, запуск остановлен по policy=strict."
                )
                self._set_status(f"Запуск остановлен: {run_label}")
                messagebox.showwarning(
                    "Desktop Input Editor",
                    (
                        f"Автоматический auto-check перед «{run_label}» выключен.\n\n"
                        f"{issue_text.capitalize()}.\n\n"
                        "Режим strict блокирует запуск без актуальной проверки. "
                        "Сначала выполните «Проверить конфигурацию»."
                    ),
                )
                return False
            if messagebox.askyesno(
                "Desktop Input Editor",
                (
                    f"Автоматический auto-check перед «{run_label}» выключен.\n\n"
                    f"{issue_text.capitalize()}.\n\n"
                    "Продолжить запуск без повторной проверки?"
                ),
            ):
                self._append_run_log(
                    f"[auto-check] {run_label}: запуск подтверждён несмотря на то, что {issue_text}."
                )
                return True
            self._append_run_log(
                f"[auto-check] {run_label}: запуск отменён пользователем, потому что {issue_text}."
            )
            self._set_status(f"Запуск отменён: {run_label}")
            return False

        ok = bool(report.get("ok", False))
        errors = list(report.get("errors") or [])
        warnings = list(report.get("warnings") or [])
        if ok:
            self._append_run_log(
                f"[auto-check] {run_label}: используем актуальный сохранённый selfcheck; warnings={len(warnings)}."
            )
            return True

        if runtime_policy == "force":
            self._append_run_log(
                f"[auto-check] {run_label}: актуальный сохранённый selfcheck содержит ошибки, продолжаем по policy=force."
            )
            return True
        if runtime_policy == "strict":
            self._append_run_log(
                f"[auto-check] {run_label}: актуальный сохранённый selfcheck содержит ошибки, запуск остановлен по policy=strict."
            )
            self._set_status(f"Запуск остановлен: {run_label}")
            preview_errors = "\n".join(f"- {msg}" for msg in errors[:4]) or "- Без деталей"
            messagebox.showwarning(
                "Desktop Input Editor",
                (
                    f"Автоматический auto-check перед «{run_label}» выключен, но есть актуальный selfcheck с ошибками.\n\n"
                    + preview_errors
                    + "\n\nРежим strict блокирует запуск, пока проблемы не будут исправлены."
                ),
            )
            return False

        preview_errors = "\n".join(f"- {msg}" for msg in errors[:4]) or "- Без деталей"
        if messagebox.askyesno(
            "Desktop Input Editor",
            (
                f"Автоматический auto-check перед «{run_label}» выключен, "
                "но актуальный сохранённый selfcheck нашёл проблемы:\n\n"
                f"{preview_errors}\n\n"
                "Продолжить запуск без повторной проверки?"
            ),
        ):
            self._append_run_log(
                f"[auto-check] {run_label}: запуск подтверждён несмотря на ошибки в актуальном сохранённом selfcheck."
            )
            return True
        self._append_run_log(
            f"[auto-check] {run_label}: запуск отменён пользователем после чтения актуального сохранённого selfcheck."
        )
        self._set_status(f"Запуск отменён: {run_label}")
        return False

    def _auto_check_allows_launch(self, report_path: Path | None, run_label: str) -> bool:
        runtime_policy = str(self.run_runtime_policy_var.get() or "balanced").strip().lower() or "balanced"
        report = self._load_selfcheck_report(report_path)
        if report is None:
            if runtime_policy == "force":
                self._append_run_log(f"[auto-check] {run_label}: отчёт недоступен, продолжаем по policy=force.")
                return True
            if runtime_policy == "strict":
                self._append_run_log(f"[auto-check] {run_label}: отчёт недоступен, запуск остановлен по policy=strict.")
                self._set_status(f"Запуск остановлен: {run_label}")
                return False
            return messagebox.askyesno(
                "Desktop Input Editor",
                f"Отчёт auto-check для «{run_label}» не найден.\n\nПродолжить запуск?",
            )

        ok = bool(report.get("ok", False))
        errors = list(report.get("errors") or [])
        warnings = list(report.get("warnings") or [])
        if ok:
            self._append_run_log(
                f"[auto-check] {run_label}: отчёт OK; warnings={len(warnings)}."
            )
            return True

        if runtime_policy == "force":
            self._append_run_log(
                f"[auto-check] {run_label}: продолжаем несмотря на ошибки по policy=force."
            )
            return True
        if runtime_policy == "strict":
            self._append_run_log(
                f"[auto-check] {run_label}: запуск остановлен по policy=strict; errors={len(errors)}."
            )
            self._set_status(f"Запуск остановлен: {run_label}")
            return False

        preview_errors = "\n".join(f"- {msg}" for msg in errors[:4]) or "- Без деталей"
        return messagebox.askyesno(
            "Desktop Input Editor",
            (
                f"Auto-check перед «{run_label}» нашёл проблемы:\n\n"
                f"{preview_errors}\n\n"
                "Продолжить запуск?"
            ),
        )

    def _launch_with_optional_auto_check(
        self,
        run_label: str,
        launch_callback: callable,
        *,
        log_file_path: Path | None = None,
    ) -> None:
        if not self._soft_preflight_before_run(run_label):
            return
        if not bool(self.run_auto_check_var.get()):
            if self._stored_selfcheck_allows_launch(run_label):
                launch_callback(log_file_path)
            return

        def _after_check(report_path: Path | None) -> None:
            if self._auto_check_allows_launch(report_path, run_label):
                launch_callback(log_file_path)
            else:
                self._append_run_log(f"[auto-check] {run_label}: запуск отменён после auto-check.")

        self._run_config_check(
            title=f"Auto-check перед «{run_label}»",
            on_success=_after_check,
            log_file_path=log_file_path,
        )

    def _soft_preflight_before_run(self, run_label: str, *, runtime_policy: str | None = None) -> bool:
        readiness_rows = evaluate_desktop_section_readiness(self._gather_payload())
        warn_rows = [
            row for row in readiness_rows if str(row.get("status") or "").strip().lower() == "warn"
        ]
        if not warn_rows:
            self._append_run_log(f"[preflight] {run_label}: проблемных шагов не найдено.")
            return True

        policy_key = str(runtime_policy or self.run_runtime_policy_var.get() or "balanced").strip().lower() or "balanced"

        detail_lines = [
            f"- {str(row.get('title') or 'Раздел')}: {str(row.get('summary') or '').strip()}"
            for row in warn_rows[:4]
        ]
        if len(warn_rows) > 4:
            detail_lines.append(f"- И ещё разделов с замечаниями: {len(warn_rows) - 4}")
        if policy_key == "force":
            self._append_run_log(
                f"[preflight] {run_label}: найдены предупреждения, но policy=force разрешает запуск."
            )
            return True
        if policy_key == "strict":
            self._append_run_log(
                f"[preflight] {run_label}: запуск остановлен по policy=strict."
            )
            self._set_status(f"Запуск остановлен: {run_label}")
            messagebox.showwarning(
                "Desktop Input Editor",
                (
                    f"Перед запуском «{run_label}» есть шаги, требующие внимания:\n\n"
                    + "\n".join(detail_lines)
                    + "\n\nРежим strict блокирует запуск, пока проблемы не будут исправлены."
                ),
            )
            return False

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

    def _run_config_check(
        self,
        *,
        title: str = "Проверить конфигурацию",
        on_success: callable | None = None,
        log_file_path: Path | None = None,
    ) -> None:
        if log_file_path is None:
            log_file_path = self._build_action_log_path("config_check")
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

        def _finish_selfcheck(path: Path | None) -> None:
            self._summarize_selfcheck_report(path, log_file_path=log_file_path)
            if callable(on_success):
                on_success(path)

        self._run_command_async(
            title,
            cmd,
            result_path=report_path,
            on_success=_finish_selfcheck,
            log_file_path=log_file_path,
        )

    def _run_quick_preview(self, *, prechecked: bool = False) -> None:
        log_file_path = self._build_action_log_path("quick_preview")

        def _launch(log_path: Path | None) -> None:
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
            ]
            self._run_command_async(
                "Быстрый расчёт",
                cmd,
                result_path=report_path,
                on_success=lambda path, current_log_path=log_path: self._summarize_preview_report(
                    path,
                    log_file_path=current_log_path,
                ),
                log_file_path=log_path,
                persist_stdout_json=True,
            )

        if prechecked:
            _launch(log_file_path)
            return

        self._launch_with_optional_auto_check(
            "Быстрый расчёт",
            _launch,
            log_file_path=log_file_path,
        )

    def _run_single_desktop_run(self, *, prechecked: bool = False) -> None:
        log_file_path = self._build_action_log_path("detail_run")

        def _launch(log_path: Path | None) -> None:
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
                "--cache_policy",
                str(self.run_cache_policy_var.get() or "reuse"),
                "--run_profile",
                self._selected_run_profile_key(),
            ]
            if bool(self.run_record_full_var.get()):
                cmd.append("--record_full")
            if bool(self.run_export_npz_var.get()):
                cmd.append("--export_npz")
            if not bool(self.run_export_csv_var.get()):
                cmd.append("--no_export_csv")
            self._run_command_async(
                "Запустить подробный расчёт",
                cmd,
                result_path=report_path,
                on_success=lambda path, current_log_path=log_path: self._summarize_single_run_report(
                    path,
                    log_file_path=current_log_path,
                ),
                log_file_path=log_path,
            )

        if prechecked:
            _launch(log_file_path)
            return

        self._launch_with_optional_auto_check(
            "Запустить подробный расчёт",
            _launch,
            log_file_path=log_file_path,
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
            self.source_reference_payload = dict(payload)
            self.current_payload = dict(payload)
            self._refresh_source_reference_diff_state()
            self.current_source_path = target
            self.path_var.set(str(target))
            self._refresh_run_context_summary()
            for key in self._widget_handles:
                self._refresh_value_label(key)
            self._refresh_section_header_summaries()
            self._refresh_active_field_search_view()
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
        if self._owns_root:
            self.root.mainloop()

    def on_host_close(self) -> None:
        self._host_closed = True
        try:
            if self._run_setup_center is not None:
                self._run_setup_center.on_host_close()
            if self._geometry_reference_center is not None:
                self._geometry_reference_center.on_host_close()
            if self._diagnostics_center is not None:
                self._diagnostics_center.on_host_close()
        except Exception:
            return


def main() -> int:
    app = DesktopInputEditor()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
