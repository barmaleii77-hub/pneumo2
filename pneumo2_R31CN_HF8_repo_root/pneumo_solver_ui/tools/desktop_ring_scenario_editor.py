from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from pneumo_solver_ui.desktop_ring_editor_model import (
    add_event_to_selected_segment,
    add_segment_after_selection,
    apply_ring_preset,
    apply_segment_preset_to_selected,
    build_blank_event,
    build_default_ring_spec,
    build_segment_flow_rows,
    build_segment_label,
    clone_selected_segment,
    create_editor_state,
    delete_selected_event,
    delete_selected_segment,
    ensure_road_defaults,
    find_selected_segment_index,
    get_selected_segment,
    insert_segment_preset_after_selection,
    list_ring_preset_names,
    list_segment_preset_names,
    load_spec_from_path,
    move_selected_segment,
    normalize_spec,
    replace_selected_event,
    RING_PRESET_DEFAULT,
    SEGMENT_PRESET_DEFAULT,
    resolve_ring_inputs_handoff,
    safe_float,
    safe_int,
    save_spec_to_path,
    select_segment_by_index,
)
from pneumo_solver_ui.desktop_ring_editor_panels import (
    DiagnosticsPanel,
    EventsPanel,
    ExportPanel,
    MotionPanel,
    PreviewPanel,
    RoadPanel,
    ScrollablePanel,
    SegmentListPanel,
)
from pneumo_solver_ui.desktop_ring_editor_runtime import (
    build_ring_bundle_optimization_preview,
    build_ring_bundle_optimization_suite_preview,
    RingEditorDiagnostics,
    build_ring_editor_diagnostics,
    export_ring_scenario_bundle,
    materialize_ring_bundle_optimization_suite,
    mirror_ring_bundle_to_anim_latest_exports,
)

try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"

EDITOR_DIALOG_TITLE = "Редактор кольцевых сценариев"


TURN_DIRECTION_TO_UI = {
    "STRAIGHT": "Прямо",
    "LEFT": "Влево",
    "RIGHT": "Вправо",
}
TURN_DIRECTION_FROM_UI = {value: key for key, value in TURN_DIRECTION_TO_UI.items()}

ROAD_MODE_TO_UI = {
    "ISO8608": "ISO 8608",
    "SINE": "Синусоида",
}
ROAD_MODE_FROM_UI = {value: key for key, value in ROAD_MODE_TO_UI.items()}

GD_PICK_TO_UI = {
    "lower": "нижний",
    "mid": "средний",
    "upper": "верхний",
}
GD_PICK_FROM_UI = {value: key for key, value in GD_PICK_TO_UI.items()}

SIDE_TO_UI = {
    "left": "Левый",
    "right": "Правый",
    "both": "Оба",
}
SIDE_FROM_UI = {value: key for key, value in SIDE_TO_UI.items()}

CLOSURE_POLICY_TO_UI = {
    "closed_c1_periodic": "Гладкое замыкание",
    "closed_exact": "Строгое совпадение",
    "strict_exact": "Строгое совпадение",
    "preview_open_only": "Открытый preview",
}
CLOSURE_POLICY_FROM_UI = {
    "Гладкое замыкание": "closed_c1_periodic",
    "Строгое совпадение": "closed_exact",
    "Открытый preview": "preview_open_only",
}

PASSAGE_MODE_TO_UI = {
    "steady": "Постоянный",
    "accel": "Разгон",
    "brake": "Торможение",
    "custom": "Пользовательский",
}
PASSAGE_MODE_FROM_UI = {value: key for key, value in PASSAGE_MODE_TO_UI.items()}


def _open_path(path: str | Path) -> None:
    target = Path(path)
    if target.is_file():
        target = target.parent
    _open_file_path(target)


def _open_file_path(path: str | Path) -> None:
    target = Path(path)
    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        os.system(f'open "{target}"')
        return
    os.system(f'xdg-open "{target}"')


class DesktopRingScenarioEditor:
    def __init__(self, host: tk.Misc | None = None, *, hosted: bool = False) -> None:
        self._owns_root = host is None
        self._hosted = bool(hosted or not self._owns_root)
        self.root = host if host is not None else tk.Tk()
        if self._owns_root:
            self.root.title(f"Редактор кольцевых сценариев ({RELEASE})")
            self.root.geometry("1560x980")
            self.root.minsize(1320, 820)

        self.repo_root = Path(__file__).resolve().parents[2]
        self.state = create_editor_state(output_dir=str(self.repo_root / "runs" / "ring_editor"))
        self.state.export.opt_workspace_dir = self._default_opt_workspace_dir()
        self._loading_ui = False
        self._queued_refresh: str | None = None
        self._selected_event_index: int | None = None
        self._host_closed = False
        self._last_diagnostics: RingEditorDiagnostics | None = None

        self.ring_preset_var = tk.StringVar(value=RING_PRESET_DEFAULT)
        self.segment_preset_var = tk.StringVar(value=SEGMENT_PRESET_DEFAULT)
        self.status_var = tk.StringVar(value="Готово. Можно редактировать кольцевой сценарий.")
        self._latest_inputs_handoff_state: dict[str, object] = {}

        self._build_ui()
        self._install_window_bindings()
        self._bind_variable_traces()
        self._refresh_from_state()

    def _window_title_text(self) -> str:
        dirty = " *" if self.state.dirty else ""
        return f"Редактор кольцевых сценариев{dirty} ({RELEASE})"

    def _update_window_title(self) -> None:
        if self._owns_root:
            self.root.title(self._window_title_text())

    def _mark_dirty(self, message: str | None = None) -> None:
        self.state.dirty = True
        self.state.export.artifacts_stale = True
        self.state.export.opt_suite_stale = True
        if message:
            self.state.status_message = message
        self._update_window_title()

    def _mark_clean(self, *, message: str | None = None, spec_path: str | None = None) -> None:
        self.state.dirty = False
        if spec_path is not None:
            self.state.spec_path = str(spec_path or "")
        if message:
            self.state.status_message = message
        self._update_window_title()

    def _confirm_discard_dirty(self, action_label: str) -> bool:
        if not self.state.dirty:
            return True
        return bool(
            messagebox.askyesno(
                EDITOR_DIALOG_TITLE,
                "Есть несохранённые изменения сценария.\n\n"
                f"Продолжить и {action_label}?\n"
                "Текущие ручные правки будут потеряны.",
            )
        )

    def _install_window_bindings(self) -> None:
        if not self._owns_root:
            return
        self.root.protocol("WM_DELETE_WINDOW", self._request_close)
        self.root.bind("<Control-s>", self._on_shortcut_save)
        self.root.bind("<Control-o>", self._on_shortcut_open)
        self.root.bind("<F5>", self._on_shortcut_refresh)

    def _on_shortcut_save(self, _event: object | None = None) -> str:
        self._save_spec()
        return "break"

    def _on_shortcut_open(self, _event: object | None = None) -> str:
        self._load_spec_dialog()
        return "break"

    def _on_shortcut_refresh(self, _event: object | None = None) -> str:
        self._force_refresh()
        return "break"

    def _request_close(self) -> None:
        if not self._confirm_discard_dirty("закрыть окно"):
            return
        self.on_host_close()
        if self._owns_root and int(self.root.winfo_exists()):
            self.root.destroy()

    def _default_opt_workspace_dir(self) -> str:
        env_path = str(os.environ.get("PNEUMO_WORKSPACE_DIR", "") or "").strip()
        if env_path:
            return env_path
        return str(self.repo_root / "pneumo_solver_ui" / "workspace")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(1, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Редактор кольцевых сценариев", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text=(
                "Отдельное окно для настройки кольцевого сценария: сегменты, профиль дороги, события, "
                "диагностика, предпросмотр кольца и подготовка файлов сценария. "
                "Быстрые действия: Ctrl+S сохранить, Ctrl+O загрузить, F5 пересчитать диагностику."
            ),
            wraplength=1200,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        actions = ttk.Frame(header)
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(4, weight=1)
        ttk.Label(actions, text="Пресет кольца").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            actions,
            textvariable=self.ring_preset_var,
            values=list_ring_preset_names(),
            state="readonly",
            width=26,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 6))
        ttk.Button(actions, text="Применить", command=self._apply_ring_preset).grid(row=0, column=2, padx=(0, 6))

        ttk.Label(actions, text="Пресет сегмента").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            actions,
            textvariable=self.segment_preset_var,
            values=list_segment_preset_names(),
            state="readonly",
            width=26,
        ).grid(row=1, column=1, sticky="ew", padx=(6, 6), pady=(6, 0))
        ttk.Button(actions, text="Применить", command=self._apply_segment_preset).grid(row=1, column=2, padx=(0, 6), pady=(6, 0))
        ttk.Button(actions, text="Вставить сегмент", command=self._insert_segment_preset).grid(row=1, column=3, padx=(0, 6), pady=(6, 0))
        ttk.Button(actions, text="Сбросить по умолчанию", command=self._reset_defaults).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(actions, text="Пересчитать диагностику", command=self._force_refresh).grid(row=0, column=4)

        for child in header.grid_slaves(row=1, column=0):
            child.grid_remove()
        self.segment_panel = SegmentListPanel(
            outer,
            on_select=self._on_segment_selected,
            on_add=self._on_add_segment,
            on_clone=self._on_clone_segment,
            on_delete=self._on_delete_segment,
            on_move_up=lambda: self._on_move_segment(-1),
            on_move_down=lambda: self._on_move_segment(1),
        )
        self.segment_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        right = ttk.Frame(outer)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.right_pane = ttk.PanedWindow(right, orient="vertical")
        self.right_pane.grid(row=0, column=0, sticky="nsew")

        self.preview_panel = PreviewPanel(self.right_pane)
        self.right_pane.add(self.preview_panel, weight=3)

        notebook_host = ttk.Frame(self.right_pane, padding=(0, 10, 0, 0))
        notebook_host.columnconfigure(0, weight=1)
        notebook_host.rowconfigure(0, weight=1)
        self.notebook = ttk.Notebook(notebook_host)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self.right_pane.add(notebook_host, weight=4)

        self.motion_tab_scroll = ScrollablePanel(self.notebook)
        self.motion_panel = MotionPanel(self.motion_tab_scroll.body)
        self.motion_panel.grid(row=0, column=0, sticky="ew")

        self.road_tab_scroll = ScrollablePanel(self.notebook)
        self.road_panel = RoadPanel(self.road_tab_scroll.body)
        self.road_panel.grid(row=0, column=0, sticky="ew")

        self.events_tab_scroll = ScrollablePanel(self.notebook)
        self.events_panel = EventsPanel(
            self.events_tab_scroll.body,
            on_select=self._on_event_selected,
            on_add=self._on_add_event,
            on_update=self._on_update_event,
            on_delete=self._on_delete_event,
        )
        self.events_panel.grid(row=0, column=0, sticky="ew")

        self.diagnostics_tab_scroll = ScrollablePanel(self.notebook)
        self.diagnostics_panel = DiagnosticsPanel(self.diagnostics_tab_scroll.body)
        self.diagnostics_panel.grid(row=0, column=0, sticky="ew")

        self.export_tab_scroll = ScrollablePanel(self.notebook)
        self.export_panel = ExportPanel(
            self.export_tab_scroll.body,
            on_choose_dir=self._choose_output_dir,
            on_choose_opt_workspace=self._choose_opt_workspace_dir,
            on_load_spec=self._load_spec_dialog,
            on_save_spec=self._save_spec_dialog,
            on_generate_bundle=self._generate_bundle,
            on_build_auto_suite=self._build_optimization_auto_suite,
            on_open_output=self._open_output_dir,
            on_open_opt_workspace=self._open_opt_workspace_dir,
            on_open_opt_suite=self._open_opt_suite_dir,
            on_open_last_spec=self._open_last_generated_spec,
            on_open_last_road=self._open_last_generated_road,
            on_open_last_axay=self._open_last_generated_axay,
            on_open_last_meta=self._open_last_generated_meta,
            on_open_ring_source=self._open_ring_source_of_truth,
            on_open_anim_latest=self._open_anim_latest_exports,
        )
        self.export_panel.grid(row=0, column=0, sticky="ew")

        self.notebook.add(self.motion_tab_scroll, text="Движение")
        self.notebook.add(self.road_tab_scroll, text="Дорога")
        self.notebook.add(self.events_tab_scroll, text="События")
        self.notebook.add(self.diagnostics_tab_scroll, text="Диагностика")
        self.notebook.add(self.export_tab_scroll, text="Экспорт")

        footer = ttk.Frame(outer)
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

    def _bind_variable_traces(self) -> None:
        variables = [
            self.motion_panel.v0_var,
            self.motion_panel.seed_var,
            self.motion_panel.dx_var,
            self.motion_panel.dt_var,
            self.motion_panel.n_laps_var,
            self.motion_panel.wheelbase_var,
            self.motion_panel.track_var,
            self.motion_panel.closure_policy_var,
            self.motion_panel.segment_name_var,
            self.motion_panel.duration_var,
            self.motion_panel.turn_direction_var,
            self.motion_panel.passage_mode_var,
            self.motion_panel.speed_end_var,
            self.motion_panel.turn_radius_var,
            self.road_panel.mode_var,
            self.road_panel.center_start_var,
            self.road_panel.center_end_var,
            self.road_panel.cross_start_var,
            self.road_panel.cross_end_var,
            self.road_panel.iso_class_var,
            self.road_panel.gd_pick_var,
            self.road_panel.gd_scale_var,
            self.road_panel.waviness_var,
            self.road_panel.coherence_var,
            self.road_panel.road_seed_var,
            self.road_panel.aL_var,
            self.road_panel.aR_var,
            self.road_panel.lambdaL_var,
            self.road_panel.lambdaR_var,
            self.road_panel.phaseL_var,
            self.road_panel.phaseR_var,
            self.road_panel.rand_aL_var,
            self.road_panel.rand_aL_p_var,
            self.road_panel.rand_aL_lo_var,
            self.road_panel.rand_aL_hi_var,
            self.road_panel.rand_aR_var,
            self.road_panel.rand_aR_p_var,
            self.road_panel.rand_aR_lo_var,
            self.road_panel.rand_aR_hi_var,
            self.road_panel.rand_lL_var,
            self.road_panel.rand_lL_p_var,
            self.road_panel.rand_lL_lo_var,
            self.road_panel.rand_lL_hi_var,
            self.road_panel.rand_lR_var,
            self.road_panel.rand_lR_p_var,
            self.road_panel.rand_lR_lo_var,
            self.road_panel.rand_lR_hi_var,
            self.road_panel.rand_pL_var,
            self.road_panel.rand_pL_p_var,
            self.road_panel.rand_pL_lo_var,
            self.road_panel.rand_pL_hi_var,
            self.road_panel.rand_pR_var,
            self.road_panel.rand_pR_p_var,
            self.road_panel.rand_pR_lo_var,
            self.road_panel.rand_pR_hi_var,
        ]
        for variable in variables:
            variable.trace_add("write", self._on_form_changed)

        self.export_panel.output_dir_var.trace_add("write", self._on_export_fields_changed)
        self.export_panel.tag_var.trace_add("write", self._on_export_fields_changed)
        self.export_panel.opt_workspace_var.trace_add("write", self._on_export_fields_changed)
        self.export_panel.opt_window_var.trace_add("write", self._on_export_fields_changed)

    def _on_export_fields_changed(self, *_args: object) -> None:
        if self._loading_ui:
            return
        new_output_dir = str(self.export_panel.output_dir_var.get() or "")
        new_tag = str(self.export_panel.tag_var.get() or "ring")
        new_opt_workspace = str(self.export_panel.opt_workspace_var.get() or "")
        new_opt_window = max(0.5, safe_float(self.export_panel.opt_window_var.get(), self.state.export.opt_window_s or 4.0))

        if new_output_dir != self.state.export.output_dir or new_tag != self.state.export.tag:
            self.state.export.artifacts_stale = True
            self.state.export.opt_suite_stale = True
        elif new_opt_workspace != self.state.export.opt_workspace_dir or abs(new_opt_window - float(self.state.export.opt_window_s or 4.0)) > 1e-12:
            self.state.export.opt_suite_stale = True

        self.state.export.output_dir = new_output_dir
        self.state.export.tag = new_tag
        self.state.export.opt_workspace_dir = new_opt_workspace
        self.state.export.opt_window_s = new_opt_window
        self._queue_refresh()

    def _on_form_changed(self, *_args: object) -> None:
        if self._loading_ui:
            return
        self._apply_form_to_state()
        self._mark_dirty("Есть несохранённые изменения сценария.")
        self.road_panel.update_mode_visibility(self.road_panel.mode_var.get())
        self._queue_refresh()

    def _queue_refresh(self) -> None:
        if self._host_closed:
            return
        if self._queued_refresh is not None:
            try:
                self.root.after_cancel(self._queued_refresh)
            except Exception:
                pass
        self._queued_refresh = self.root.after(120, self._refresh_from_state)

    def _force_refresh(self) -> None:
        self._apply_form_to_state()
        self._refresh_from_state()

    def _refresh_from_state(self) -> None:
        self._queued_refresh = None
        self.state.ensure_selection()
        self._loading_ui = True
        try:
            self._load_state_to_form()
        finally:
            self._loading_ui = False

        rows = build_segment_flow_rows(self.state.spec)
        self.segment_panel.set_segments([build_segment_label(row) for row in rows], find_selected_segment_index(self.state))
        self.motion_panel.set_segment_enabled(bool(rows))

        diagnostics = build_ring_editor_diagnostics(self.state.spec)
        self._last_diagnostics = diagnostics
        self._apply_diagnostics(diagnostics)
        self._refresh_inputs_handoff_state()
        dirty_label = "есть несохранённые изменения" if self.state.dirty else "сохранено"
        scenario_label = Path(self.state.spec_path).name if self.state.spec_path else "в памяти"
        artifacts_label = "требуется пересборка" if self.state.export.artifacts_stale else "актуально"
        opt_suite_label = "требуется пересборка" if self.state.export.opt_suite_stale else "актуально"
        self.status_var.set(
            f"Сохранение: {dirty_label} | Сценарий: {scenario_label} | "
            f"Сегментов: {len(rows)} | Ошибок: {len(diagnostics.errors)} | Предупреждений: {len(diagnostics.warnings)} | "
            f"Каталог выгрузки: {self.state.export.output_dir or 'не выбран'} | Файлы сценария: {artifacts_label} | "
            f"Набор оптимизации: {opt_suite_label}"
            + (f" | {self.state.status_message}" if self.state.status_message else "")
        )
        self._update_window_title()

    def _refresh_inputs_handoff_state(self) -> dict[str, object]:
        try:
            state = resolve_ring_inputs_handoff()
            self._latest_inputs_handoff_state = dict(state)
            banner = str(state.get("banner") or "").strip()
            path = str(state.get("snapshot_path") or "").strip()
            payload_hash = str(state.get("payload_hash") or "").strip()
            lines = [
                f"HO-002 inputs_snapshot: {state.get('state') or 'missing'}",
                f"payload_hash={payload_hash[:12] or '—'} | can_consume={bool(state.get('can_consume', False))}",
                banner,
                f"inputs_snapshot.json: {path}",
            ]
            self.export_panel.inputs_handoff_var.set("\n".join(line for line in lines if line).strip())
            return state
        except Exception as exc:
            self._latest_inputs_handoff_state = {}
            self.export_panel.inputs_handoff_var.set(f"Не удалось проверить HO-002 inputs_snapshot: {exc}")
            return {}

    def _load_state_to_form(self) -> None:
        spec = self.state.spec
        segment = get_selected_segment(self.state)
        road = ensure_road_defaults(segment) if isinstance(segment, dict) else {}

        self.motion_panel.v0_var.set(str(spec.get("v0_kph", 40.0)))
        self.motion_panel.seed_var.set(str(spec.get("seed", 123)))
        self.motion_panel.dx_var.set(str(spec.get("dx_m", 0.02)))
        self.motion_panel.dt_var.set(str(spec.get("dt_s", 0.01)))
        self.motion_panel.n_laps_var.set(str(spec.get("n_laps", 1)))
        self.motion_panel.wheelbase_var.set(str(spec.get("wheelbase_m", 1.5)))
        self.motion_panel.track_var.set(str(spec.get("track_m", 1.0)))
        self.motion_panel.closure_policy_var.set(
            CLOSURE_POLICY_TO_UI.get(str(spec.get("closure_policy", "closed_c1_periodic")), "Гладкое замыкание")
        )

        self.export_panel.output_dir_var.set(str(self.state.export.output_dir or ""))
        self.export_panel.tag_var.set(str(self.state.export.tag or "ring"))
        self.export_panel.opt_workspace_var.set(str(self.state.export.opt_workspace_dir or ""))
        self.export_panel.opt_window_var.set(str(self.state.export.opt_window_s or 4.0))

        if segment is None:
            self.motion_panel.segment_name_var.set("")
            self.motion_panel.duration_var.set("")
            self.motion_panel.turn_direction_var.set("Прямо")
            self.motion_panel.passage_mode_var.set("Постоянный")
            self.motion_panel.speed_end_var.set("")
            self.motion_panel.turn_radius_var.set("")
            self.events_panel.set_events([])
            self.road_panel.set_boundary_editability(start_editable=False, end_editable=False)
            return

        self.motion_panel.segment_name_var.set(str(segment.get("name", "")))
        self.motion_panel.duration_var.set(str(segment.get("duration_s", 0.0)))
        self.motion_panel.turn_direction_var.set(
            TURN_DIRECTION_TO_UI.get(str(segment.get("turn_direction", "STRAIGHT")).upper(), "Прямо")
        )
        self.motion_panel.passage_mode_var.set(
            PASSAGE_MODE_TO_UI.get(str(segment.get("passage_mode", "steady")).lower(), "Постоянный")
        )
        self.motion_panel.speed_end_var.set(str(segment.get("speed_end_kph", 0.0)))
        self.motion_panel.turn_radius_var.set(str(segment.get("turn_radius_m", 0.0)))

        selected_index = find_selected_segment_index(self.state)
        segments = list(self.state.spec.get("segments", []) or [])
        selected_row = None
        if self._last_diagnostics is not None and 0 <= selected_index < len(self._last_diagnostics.segment_rows):
            candidate = self._last_diagnostics.segment_rows[selected_index]
            selected_row = candidate if isinstance(candidate, dict) else None
        self.road_panel.mode_var.set(ROAD_MODE_TO_UI.get(str(road.get("mode", "ISO8608")).upper(), "ISO 8608"))
        self.road_panel.center_start_var.set(str((selected_row or {}).get("center_height_start_mm", road.get("center_height_start_mm", 0.0))))
        self.road_panel.center_end_var.set(str((selected_row or {}).get("center_height_end_mm", road.get("center_height_end_mm", 0.0))))
        self.road_panel.cross_start_var.set(str((selected_row or {}).get("cross_slope_start_pct", road.get("cross_slope_start_pct", 0.0))))
        self.road_panel.cross_end_var.set(str((selected_row or {}).get("cross_slope_end_pct", road.get("cross_slope_end_pct", 0.0))))
        self.road_panel.set_boundary_editability(
            start_editable=selected_index == 0,
            end_editable=not bool(segments and selected_index >= len(segments) - 1),
        )
        self.road_panel.iso_class_var.set(str(road.get("iso_class", "E")).upper())
        self.road_panel.gd_pick_var.set(GD_PICK_TO_UI.get(str(road.get("gd_pick", "mid")).lower(), "средний"))
        self.road_panel.gd_scale_var.set(str(road.get("gd_n0_scale", 1.0)))
        self.road_panel.waviness_var.set(str(road.get("waviness_w", 2.0)))
        self.road_panel.coherence_var.set(str(road.get("left_right_coherence", 0.5)))
        self.road_panel.road_seed_var.set(str(road.get("seed", 12345)))
        self.road_panel.aL_var.set(str(road.get("aL_mm", 50.0)))
        self.road_panel.aR_var.set(str(road.get("aR_mm", 50.0)))
        self.road_panel.lambdaL_var.set(str(road.get("lambdaL_m", 1.5)))
        self.road_panel.lambdaR_var.set(str(road.get("lambdaR_m", 1.5)))
        self.road_panel.phaseL_var.set(str(road.get("phaseL_deg", 0.0)))
        self.road_panel.phaseR_var.set(str(road.get("phaseR_deg", 180.0)))
        self.road_panel.rand_aL_var.set(bool(road.get("rand_aL", False)))
        self.road_panel.rand_aL_p_var.set(str(road.get("rand_aL_p", 0.5)))
        self.road_panel.rand_aL_lo_var.set(str(road.get("rand_aL_lo_mm", 4.0)))
        self.road_panel.rand_aL_hi_var.set(str(road.get("rand_aL_hi_mm", 4.0)))
        self.road_panel.rand_aR_var.set(bool(road.get("rand_aR", False)))
        self.road_panel.rand_aR_p_var.set(str(road.get("rand_aR_p", 0.5)))
        self.road_panel.rand_aR_lo_var.set(str(road.get("rand_aR_lo_mm", 4.0)))
        self.road_panel.rand_aR_hi_var.set(str(road.get("rand_aR_hi_mm", 4.0)))
        self.road_panel.rand_lL_var.set(bool(road.get("rand_lL", False)))
        self.road_panel.rand_lL_p_var.set(str(road.get("rand_lL_p", 0.5)))
        self.road_panel.rand_lL_lo_var.set(str(road.get("rand_lL_lo_m", 2.5)))
        self.road_panel.rand_lL_hi_var.set(str(road.get("rand_lL_hi_m", 2.5)))
        self.road_panel.rand_lR_var.set(bool(road.get("rand_lR", False)))
        self.road_panel.rand_lR_p_var.set(str(road.get("rand_lR_p", 0.5)))
        self.road_panel.rand_lR_lo_var.set(str(road.get("rand_lR_lo_m", 2.5)))
        self.road_panel.rand_lR_hi_var.set(str(road.get("rand_lR_hi_m", 2.5)))
        self.road_panel.rand_pL_var.set(bool(road.get("rand_pL", True)))
        self.road_panel.rand_pL_p_var.set(str(road.get("rand_pL_p", 0.5)))
        self.road_panel.rand_pL_lo_var.set(str(road.get("rand_pL_lo_deg", 0.0)))
        self.road_panel.rand_pL_hi_var.set(str(road.get("rand_pL_hi_deg", 360.0)))
        self.road_panel.rand_pR_var.set(bool(road.get("rand_pR", True)))
        self.road_panel.rand_pR_p_var.set(str(road.get("rand_pR_p", 0.5)))
        self.road_panel.rand_pR_lo_var.set(str(road.get("rand_pR_lo_deg", 0.0)))
        self.road_panel.rand_pR_hi_var.set(str(road.get("rand_pR_hi_deg", 360.0)))
        self.road_panel.update_mode_visibility(self.road_panel.mode_var.get())

        events = list(segment.get("events", []) or [])
        self.events_panel.set_events(events)
        self._selected_event_index = None
        self._load_event_to_form(build_blank_event())

    def _apply_form_to_state(self) -> None:
        spec = self.state.spec
        spec["v0_kph"] = safe_float(self.motion_panel.v0_var.get(), spec.get("v0_kph", 40.0))
        spec["seed"] = safe_int(self.motion_panel.seed_var.get(), spec.get("seed", 123))
        spec["dx_m"] = safe_float(self.motion_panel.dx_var.get(), spec.get("dx_m", 0.02))
        spec["dt_s"] = safe_float(self.motion_panel.dt_var.get(), spec.get("dt_s", 0.01))
        spec["n_laps"] = max(1, safe_int(self.motion_panel.n_laps_var.get(), spec.get("n_laps", 1)))
        spec["wheelbase_m"] = safe_float(self.motion_panel.wheelbase_var.get(), spec.get("wheelbase_m", 1.5))
        spec["track_m"] = safe_float(self.motion_panel.track_var.get(), spec.get("track_m", 1.0))
        spec["closure_policy"] = CLOSURE_POLICY_FROM_UI.get(
            str(self.motion_panel.closure_policy_var.get() or "Гладкое замыкание"),
            "closed_c1_periodic",
        )

        segment = get_selected_segment(self.state)
        if segment is None:
            return
        selected_index = find_selected_segment_index(self.state)
        segments = list(spec.get("segments", []) or [])
        is_last_segment = bool(segments and selected_index >= len(segments) - 1)
        segment["name"] = str(self.motion_panel.segment_name_var.get() or "Сегмент")
        segment["duration_s"] = safe_float(self.motion_panel.duration_var.get(), segment.get("duration_s", 3.0))
        segment["turn_direction"] = TURN_DIRECTION_FROM_UI.get(
            str(self.motion_panel.turn_direction_var.get() or "Прямо"),
            "STRAIGHT",
        )
        segment["passage_mode"] = PASSAGE_MODE_FROM_UI.get(
            str(self.motion_panel.passage_mode_var.get() or "Постоянный"),
            "steady",
        )
        if is_last_segment:
            segment["speed_end_kph"] = safe_float(spec.get("v0_kph", 40.0), 40.0)
        else:
            segment["speed_end_kph"] = safe_float(self.motion_panel.speed_end_var.get(), segment.get("speed_end_kph", 40.0))
        segment["turn_radius_m"] = safe_float(self.motion_panel.turn_radius_var.get(), segment.get("turn_radius_m", 0.0))

        road = ensure_road_defaults(segment)
        road["mode"] = ROAD_MODE_FROM_UI.get(str(self.road_panel.mode_var.get() or "ISO 8608"), "ISO8608")
        if selected_index == 0:
            road["center_height_start_mm"] = safe_float(self.road_panel.center_start_var.get(), road.get("center_height_start_mm", 0.0))
            road["cross_slope_start_pct"] = safe_float(self.road_panel.cross_start_var.get(), road.get("cross_slope_start_pct", 0.0))
        else:
            road.pop("center_height_start_mm", None)
            road.pop("cross_slope_start_pct", None)
        road["center_height_end_mm"] = safe_float(self.road_panel.center_end_var.get(), road.get("center_height_end_mm", 0.0))
        road["cross_slope_end_pct"] = safe_float(self.road_panel.cross_end_var.get(), road.get("cross_slope_end_pct", 0.0))
        if is_last_segment and segments:
            first_road = dict((segments[0] or {}).get("road", {}) or {})
            road["center_height_end_mm"] = safe_float(first_road.get("center_height_start_mm", 0.0), 0.0)
            road["cross_slope_end_pct"] = safe_float(first_road.get("cross_slope_start_pct", 0.0), 0.0)
        road["iso_class"] = str(self.road_panel.iso_class_var.get() or "E").upper()
        road["gd_pick"] = GD_PICK_FROM_UI.get(str(self.road_panel.gd_pick_var.get() or "средний"), "mid")
        road["gd_n0_scale"] = safe_float(self.road_panel.gd_scale_var.get(), road.get("gd_n0_scale", 1.0))
        road["waviness_w"] = safe_float(self.road_panel.waviness_var.get(), road.get("waviness_w", 2.0))
        road["left_right_coherence"] = safe_float(self.road_panel.coherence_var.get(), road.get("left_right_coherence", 0.5))
        road["seed"] = safe_int(self.road_panel.road_seed_var.get(), road.get("seed", 12345))
        road["aL_mm"] = safe_float(self.road_panel.aL_var.get(), road.get("aL_mm", 50.0))
        road["aR_mm"] = safe_float(self.road_panel.aR_var.get(), road.get("aR_mm", 50.0))
        road["lambdaL_m"] = safe_float(self.road_panel.lambdaL_var.get(), road.get("lambdaL_m", 1.5))
        road["lambdaR_m"] = safe_float(self.road_panel.lambdaR_var.get(), road.get("lambdaR_m", 1.5))
        road["phaseL_deg"] = safe_float(self.road_panel.phaseL_var.get(), road.get("phaseL_deg", 0.0))
        road["phaseR_deg"] = safe_float(self.road_panel.phaseR_var.get(), road.get("phaseR_deg", 180.0))
        road["rand_aL"] = bool(self.road_panel.rand_aL_var.get())
        road["rand_aL_p"] = safe_float(self.road_panel.rand_aL_p_var.get(), road.get("rand_aL_p", 0.5))
        road["rand_aL_lo_mm"] = safe_float(self.road_panel.rand_aL_lo_var.get(), road.get("rand_aL_lo_mm", 4.0))
        road["rand_aL_hi_mm"] = safe_float(self.road_panel.rand_aL_hi_var.get(), road.get("rand_aL_hi_mm", 4.0))
        road["rand_aR"] = bool(self.road_panel.rand_aR_var.get())
        road["rand_aR_p"] = safe_float(self.road_panel.rand_aR_p_var.get(), road.get("rand_aR_p", 0.5))
        road["rand_aR_lo_mm"] = safe_float(self.road_panel.rand_aR_lo_var.get(), road.get("rand_aR_lo_mm", 4.0))
        road["rand_aR_hi_mm"] = safe_float(self.road_panel.rand_aR_hi_var.get(), road.get("rand_aR_hi_mm", 4.0))
        road["rand_lL"] = bool(self.road_panel.rand_lL_var.get())
        road["rand_lL_p"] = safe_float(self.road_panel.rand_lL_p_var.get(), road.get("rand_lL_p", 0.5))
        road["rand_lL_lo_m"] = safe_float(self.road_panel.rand_lL_lo_var.get(), road.get("rand_lL_lo_m", 2.5))
        road["rand_lL_hi_m"] = safe_float(self.road_panel.rand_lL_hi_var.get(), road.get("rand_lL_hi_m", 2.5))
        road["rand_lR"] = bool(self.road_panel.rand_lR_var.get())
        road["rand_lR_p"] = safe_float(self.road_panel.rand_lR_p_var.get(), road.get("rand_lR_p", 0.5))
        road["rand_lR_lo_m"] = safe_float(self.road_panel.rand_lR_lo_var.get(), road.get("rand_lR_lo_m", 2.5))
        road["rand_lR_hi_m"] = safe_float(self.road_panel.rand_lR_hi_var.get(), road.get("rand_lR_hi_m", 2.5))
        road["rand_pL"] = bool(self.road_panel.rand_pL_var.get())
        road["rand_pL_p"] = safe_float(self.road_panel.rand_pL_p_var.get(), road.get("rand_pL_p", 0.5))
        road["rand_pL_lo_deg"] = safe_float(self.road_panel.rand_pL_lo_var.get(), road.get("rand_pL_lo_deg", 0.0))
        road["rand_pL_hi_deg"] = safe_float(self.road_panel.rand_pL_hi_var.get(), road.get("rand_pL_hi_deg", 360.0))
        road["rand_pR"] = bool(self.road_panel.rand_pR_var.get())
        road["rand_pR_p"] = safe_float(self.road_panel.rand_pR_p_var.get(), road.get("rand_pR_p", 0.5))
        road["rand_pR_lo_deg"] = safe_float(self.road_panel.rand_pR_lo_var.get(), road.get("rand_pR_lo_deg", 0.0))
        road["rand_pR_hi_deg"] = safe_float(self.road_panel.rand_pR_hi_var.get(), road.get("rand_pR_hi_deg", 360.0))

    def _apply_diagnostics(self, diagnostics: RingEditorDiagnostics) -> None:
        opt_preview_rows: list[dict[str, object]] = []
        opt_suite_rows: list[dict[str, object]] = []
        opt_preview_summary = "Сначала соберите файлы сценария, чтобы увидеть предварительный состав набора оптимизации."
        if self.state.export.last_bundle:
            try:
                opt_preview = build_ring_bundle_optimization_suite_preview(
                    self.state.export.last_bundle,
                    window_s=max(0.5, safe_float(self.state.export.opt_window_s, 4.0)),
                )
                opt_preview_rows = list(opt_preview.get("fragment_rows") or [])
                opt_suite_rows = list(opt_preview.get("suite_rows") or [])
                opt_preview_summary = str(opt_preview.get("summary_text") or opt_preview_summary)
            except Exception:
                opt_preview_rows = []
                opt_suite_rows = []
                opt_preview_summary = "Предварительный состав набора оптимизации временно недоступен для текущей выгрузки."
        self.diagnostics_panel.summary_var.set(
            f"Ошибок: {len(diagnostics.errors)} | Предупреждений: {len(diagnostics.warnings)} | "
            f"Режим замыкания: {CLOSURE_POLICY_TO_UI.get(str(diagnostics.metrics.get('closure_policy', '')), 'не задан')} | "
            f"Фрагментов оптимизации: {len(opt_preview_rows)} | Строк набора: {len(opt_suite_rows)}"
        )
        self.diagnostics_panel.set_messages(diagnostics.summary_text)
        self.diagnostics_panel.set_segment_rows(diagnostics.segment_rows)
        self.diagnostics_panel.set_opt_fragment_summary(opt_preview_summary)
        self.diagnostics_panel.set_opt_fragment_rows(opt_preview_rows)
        self.diagnostics_panel.set_opt_suite_rows(opt_suite_rows)
        selected_index = find_selected_segment_index(self.state)
        self.preview_panel.render(diagnostics, selected_index)
        self.road_panel.render(diagnostics, selected_index)
        row = diagnostics.segment_rows[selected_index] if 0 <= selected_index < len(diagnostics.segment_rows) else None
        if isinstance(row, dict):
            speed_start = float(row.get("speed_start_kph", 0.0) or 0.0)
            speed_end = float(row.get("speed_end_kph", 0.0) or 0.0)
            self.motion_panel.start_speed_var.set(f"Стартовая скорость: {speed_start:.2f} км/ч")
            self.motion_panel.length_var.set(f"Длина сегмента: {float(row.get('length_m', 0.0) or 0.0):.2f} м")
            self.motion_panel.delta_v_var.set(f"Изменение скорости: {speed_end - speed_start:+.2f} км/ч")

        if self.state.export.last_bundle:
            bundle = self.state.export.last_bundle
            artifacts_line = (
                "\nСостояние файлов сценария: требуется пересборка"
                if self.state.export.artifacts_stale
                else "\nСостояние файлов сценария: актуально"
            )
            opt_suite_line = (
                "\nСостояние набора оптимизации: требуется пересборка"
                if self.state.export.opt_suite_stale
                else "\nСостояние набора оптимизации: актуально"
            )
            meta_lines = ""
            meta = bundle.get("meta")
            if isinstance(meta, dict):
                meta_lines = (
                    f"\nДлина кольца: {float(meta.get('ring_length_m', 0.0) or 0.0):.2f} м"
                    f"\nДлительность круга: {float(meta.get('lap_time_s', 0.0) or 0.0):.2f} с"
                    f"\nЧисло отсчётов: {int(meta.get('n_samples', 0) or 0)}"
                    f"\nРежим замыкания: {CLOSURE_POLICY_TO_UI.get(str(meta.get('closure_policy', '')), 'не задан')}"
                    f"\nRaw seam до export-замыкания: {1000.0 * float(meta.get('raw_seam_max_jump_m', 0.0) or 0.0):.1f} мм"
                    f"\nМаксимальный шов после export-policy: {1000.0 * float(meta.get('seam_max_jump_m', 0.0) or 0.0):.1f} мм"
                )
                lineage = meta.get("lineage") if isinstance(meta.get("lineage"), dict) else {}
                if lineage:
                    meta_lines += (
                        f"\nRing source hash: {str(lineage.get('ring_source_hash_sha256', ''))[:16]}"
                        f"\nExport set hash: {str(lineage.get('ring_export_set_hash_sha256', ''))[:16]}"
                    )
            anim_latest_lines = ""
            if bundle.get("anim_latest_scenario_json"):
                anim_dir = str(Path(str(bundle.get("anim_latest_scenario_json", ""))).expanduser().parent)
                anim_latest_lines = (
                    f"\nПапка для анимации: {anim_dir}"
                    f"\nСценарий для анимации: {bundle.get('anim_latest_scenario_json', '')}"
                    f"\nПрофиль дороги для анимации: {bundle.get('anim_latest_road_csv', '')}"
                    f"\nФайл ускорений для анимации: {bundle.get('anim_latest_axay_csv', '')}"
                )
            suite_lines = ""
            if bundle.get("suite_json"):
                suite_lines = (
                    f"\nНабор оптимизации: {bundle.get('suite_json', '')}"
                    f"\nОписание набора: {bundle.get('suite_meta_json', '')}"
                    f"\nРабочая папка оптимизации: {bundle.get('workspace_dir', '')}"
                    f"\nОкно фрагмента: {bundle.get('window_s', 0.0)} с"
                    f"\nСтрок в наборе: {bundle.get('generated_row_count', 0)}"
                )
            self.export_panel.last_export_var.set(
                f"Последняя выгрузка:\n"
                f"Сценарий: {bundle.get('scenario_json', '')}\n"
                f"Профиль дороги: {bundle.get('road_csv', '')}\n"
                f"Файл ускорений: {bundle.get('axay_csv', '')}"
                f"\nMeta HO-004: {bundle.get('meta_json', '')}"
                f"\nSource-of-truth WS-RING: {bundle.get('ring_source_of_truth_json', '')}"
                f"{artifacts_line}"
                f"{opt_suite_line}"
                f"{meta_lines}"
                f"{anim_latest_lines}"
                f"{suite_lines}"
            )
        elif self.state.export.last_error:
            self.export_panel.last_export_var.set(f"Последняя ошибка экспорта: {self.state.export.last_error}")
        else:
            self.export_panel.last_export_var.set("Артефакты ещё не генерировались.")

    def _reset_defaults(self) -> None:
        if not self._confirm_discard_dirty("сбросить сценарий к исходному виду"):
            return
        self.state.spec = build_default_ring_spec()
        self.state.ensure_selection()
        self._selected_event_index = None
        self.state.spec_path = ""
        self._mark_dirty("Сценарий сброшен к исходному кольцу.")
        self._refresh_from_state()

    def _apply_ring_preset(self) -> None:
        self._apply_form_to_state()
        preset_name = str(self.ring_preset_var.get() or RING_PRESET_DEFAULT)
        if not self._confirm_discard_dirty(f"применить пресет кольца «{preset_name}»"):
            return
        try:
            apply_ring_preset(self.state, preset_name)
        except Exception as exc:
            messagebox.showerror(EDITOR_DIALOG_TITLE, f"Не удалось применить пресет кольца:\n{exc}")
            return
        self._selected_event_index = None
        self._mark_dirty(f"Применён пресет кольца: {preset_name}")
        self._refresh_from_state()

    def _apply_segment_preset(self) -> None:
        self._apply_form_to_state()
        preset_name = str(self.segment_preset_var.get() or SEGMENT_PRESET_DEFAULT)
        if not self._confirm_discard_dirty(f"заменить текущий сегмент пресетом «{preset_name}»"):
            return
        try:
            apply_segment_preset_to_selected(self.state, preset_name)
        except Exception as exc:
            messagebox.showerror(EDITOR_DIALOG_TITLE, f"Не удалось применить пресет сегмента:\n{exc}")
            return
        self._selected_event_index = None
        self._mark_dirty(f"Применён пресет к текущему сегменту: {preset_name}")
        self._refresh_from_state()

    def _insert_segment_preset(self) -> None:
        self._apply_form_to_state()
        preset_name = str(self.segment_preset_var.get() or SEGMENT_PRESET_DEFAULT)
        try:
            insert_segment_preset_after_selection(self.state, preset_name)
        except Exception as exc:
            messagebox.showerror(EDITOR_DIALOG_TITLE, f"Не удалось вставить пресет сегмента:\n{exc}")
            return
        self._selected_event_index = None
        self._mark_dirty(f"Вставлен новый сегмент из пресета: {preset_name}")
        self._refresh_from_state()

    def _on_segment_selected(self) -> None:
        select_segment_by_index(self.state, self.segment_panel.selected_index())
        self._selected_event_index = None
        self._refresh_from_state()

    def _on_add_segment(self) -> None:
        self._apply_form_to_state()
        add_segment_after_selection(self.state)
        self._selected_event_index = None
        self._mark_dirty("Добавлен новый сегмент.")
        self._refresh_from_state()

    def _on_clone_segment(self) -> None:
        self._apply_form_to_state()
        clone_selected_segment(self.state)
        self._selected_event_index = None
        self._mark_dirty("Сегмент клонирован.")
        self._refresh_from_state()

    def _on_delete_segment(self) -> None:
        if len(list(self.state.spec.get("segments", []) or [])) <= 1:
            messagebox.showwarning(EDITOR_DIALOG_TITLE, "В кольце должен остаться хотя бы один сегмент.")
            return
        self._apply_form_to_state()
        delete_selected_segment(self.state)
        self._selected_event_index = None
        self._mark_dirty("Сегмент удалён.")
        self._refresh_from_state()

    def _on_move_segment(self, delta: int) -> None:
        self._apply_form_to_state()
        move_selected_segment(self.state, delta)
        self._selected_event_index = None
        self._mark_dirty("Порядок сегментов изменён.")
        self._refresh_from_state()

    def _collect_event_from_form(self) -> dict[str, object]:
        return {
            "kind": str(self.events_panel.kind_var.get() or "яма"),
            "side": SIDE_FROM_UI.get(str(self.events_panel.side_var.get() or "Левый"), "left"),
            "start_m": safe_float(self.events_panel.start_var.get(), 0.0),
            "length_m": safe_float(self.events_panel.length_var.get(), 0.4),
            "depth_mm": safe_float(self.events_panel.depth_var.get(), -25.0),
            "ramp_m": safe_float(self.events_panel.ramp_var.get(), 0.1),
        }

    def _load_event_to_form(self, event: dict[str, object]) -> None:
        self.events_panel.kind_var.set(str(event.get("kind", "яма")))
        self.events_panel.side_var.set(SIDE_TO_UI.get(str(event.get("side", "left")), "Левый"))
        self.events_panel.start_var.set(str(event.get("start_m", 0.0)))
        self.events_panel.length_var.set(str(event.get("length_m", 0.4)))
        self.events_panel.depth_var.set(str(event.get("depth_mm", -25.0)))
        self.events_panel.ramp_var.set(str(event.get("ramp_m", 0.1)))

    def _on_event_selected(self) -> None:
        segment = get_selected_segment(self.state)
        if segment is None:
            return
        index = self.events_panel.selected_index()
        if index is None:
            return
        events = list(segment.get("events", []) or [])
        if 0 <= index < len(events):
            self._selected_event_index = index
            self._load_event_to_form(dict(events[index]))

    def _on_add_event(self) -> None:
        self._apply_form_to_state()
        add_event_to_selected_segment(self.state, self._collect_event_from_form())
        self._selected_event_index = None
        self._mark_dirty("Добавлено новое событие.")
        self._refresh_from_state()

    def _on_update_event(self) -> None:
        if self._selected_event_index is None:
            messagebox.showinfo(EDITOR_DIALOG_TITLE, "Сначала выберите событие в таблице.")
            return
        self._apply_form_to_state()
        replace_selected_event(self.state, self._selected_event_index, self._collect_event_from_form())
        self._mark_dirty("Событие обновлено.")
        self._refresh_from_state()
        self.events_panel.select_index(self._selected_event_index)

    def _on_delete_event(self) -> None:
        index = self.events_panel.selected_index()
        if index is None:
            messagebox.showinfo(EDITOR_DIALOG_TITLE, "Сначала выберите событие в таблице.")
            return
        delete_selected_event(self.state, index)
        self._selected_event_index = None
        self._mark_dirty("Событие удалено.")
        self._refresh_from_state()

    def _choose_output_dir(self) -> None:
        current = self.state.export.output_dir or str(self.repo_root / "runs" / "ring_editor")
        chosen = filedialog.askdirectory(title="Выберите папку для файлов сценария", initialdir=current)
        if not chosen:
            return
        self.state.export.output_dir = chosen
        self.export_panel.output_dir_var.set(chosen)

    def _choose_opt_workspace_dir(self) -> None:
        current = self.state.export.opt_workspace_dir or self._default_opt_workspace_dir()
        chosen = filedialog.askdirectory(title="Выберите рабочую папку оптимизации", initialdir=current)
        if not chosen:
            return
        self.state.export.opt_workspace_dir = chosen
        self.export_panel.opt_workspace_var.set(chosen)

    def _open_output_dir(self) -> None:
        target = self.state.export.output_dir or str(self.repo_root / "runs" / "ring_editor")
        Path(target).mkdir(parents=True, exist_ok=True)
        _open_path(target)

    def _open_opt_workspace_dir(self) -> None:
        target = self.state.export.opt_workspace_dir or self._default_opt_workspace_dir()
        Path(target).mkdir(parents=True, exist_ok=True)
        _open_path(target)

    def _open_opt_suite_dir(self) -> None:
        suite_path = str((self.state.export.last_bundle or {}).get("suite_json") or "").strip()
        if not suite_path:
            messagebox.showinfo(EDITOR_DIALOG_TITLE, "Набор оптимизации ещё не собран.")
            return
        _open_path(suite_path)

    def _open_last_generated_file(self, bundle_key: str, label: str) -> None:
        target = str((self.state.export.last_bundle or {}).get(bundle_key) or "").strip()
        if not target:
            messagebox.showinfo(EDITOR_DIALOG_TITLE, f"{label} ещё не подготовлен.")
            return
        path = Path(target).expanduser()
        if not path.exists():
            messagebox.showwarning(EDITOR_DIALOG_TITLE, f"{label} не найден на диске:\n{path}")
            return
        _open_file_path(path)

    def _open_last_generated_spec(self) -> None:
        self._open_last_generated_file("scenario_json", "Сценарий")

    def _open_last_generated_road(self) -> None:
        self._open_last_generated_file("road_csv", "Профиль дороги")

    def _open_last_generated_axay(self) -> None:
        self._open_last_generated_file("axay_csv", "Файл ускорений")

    def _open_last_generated_meta(self) -> None:
        self._open_last_generated_file("meta_json", "Meta HO-004")

    def _open_ring_source_of_truth(self) -> None:
        self._open_last_generated_file("ring_source_of_truth_json", "Source-of-truth WS-RING")

    def _open_anim_latest_exports(self) -> None:
        bundle = self.state.export.last_bundle or {}
        anim_latest_path = str(bundle.get("anim_latest_scenario_json") or "").strip()
        if anim_latest_path:
            path = Path(anim_latest_path).expanduser()
            if path.exists():
                _open_path(path)
                return
        exports_dir = Path(self.state.export.opt_workspace_dir or self._default_opt_workspace_dir()) / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        _open_path(exports_dir)

    def _default_spec_save_path(self) -> Path:
        if self.state.spec_path:
            return Path(self.state.spec_path)
        return Path(self.state.export.output_dir or (self.repo_root / "runs" / "ring_editor")) / f"scenario_{self.state.export.tag or 'ring'}_spec.json"

    def _save_spec(self, *, force_dialog: bool = False) -> str | None:
        self._apply_form_to_state()
        path = str(self.state.spec_path or "")
        if force_dialog or not path:
            default_path = self._default_spec_save_path()
            path = filedialog.asksaveasfilename(
                title="Сохранить сценарий кольца",
                defaultextension=".json",
                initialfile=default_path.name,
                initialdir=str(default_path.parent),
                filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            )
        if not path:
            return None
        try:
            save_spec_to_path(self.state.spec, path)
        except Exception as exc:
            messagebox.showerror(EDITOR_DIALOG_TITLE, f"Не удалось сохранить сценарий:\n{exc}")
            return None
        self._mark_clean(message=f"Сценарий сохранён: {path}", spec_path=path)
        self._refresh_from_state()
        return str(path)

    def _save_spec_dialog(self) -> None:
        self._save_spec(force_dialog=True)

    def _load_spec_dialog(self) -> None:
        if not self._confirm_discard_dirty("загрузить другой сценарий"):
            return
        initial_dir = self.state.export.output_dir or str(self.repo_root)
        path = filedialog.askopenfilename(
            title="Открыть сценарий кольца",
            initialdir=initial_dir,
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.state.spec = normalize_spec(load_spec_from_path(path))
            self.state.ensure_selection()
            self._selected_event_index = None
            self.state.export.artifacts_stale = True
            self.state.export.opt_suite_stale = True
            self._mark_clean(message=f"Сценарий загружен: {path}", spec_path=path)
            self._refresh_from_state()
        except Exception as exc:
            messagebox.showerror(EDITOR_DIALOG_TITLE, f"Не удалось загрузить сценарий:\n{exc}")

    def _generate_bundle(self, *, show_dialog: bool = True) -> dict[str, str] | None:
        self._apply_form_to_state()
        diagnostics = build_ring_editor_diagnostics(self.state.spec)
        if diagnostics.errors:
            if show_dialog:
                messagebox.showerror(EDITOR_DIALOG_TITLE, "Исправьте ошибки в диагностике перед подготовкой файлов сценария.")
            self._apply_diagnostics(diagnostics)
            return None

        output_dir = self.state.export.output_dir or str(self.repo_root / "runs" / "ring_editor")
        tag = self.state.export.tag or "ring"
        try:
            bundle = export_ring_scenario_bundle(self.state.spec, output_dir=output_dir, tag=tag)
            mirrored = mirror_ring_bundle_to_anim_latest_exports(bundle)
            self.state.export.output_dir = output_dir
            self.state.export.tag = tag
            self.state.export.artifacts_stale = False
            self.state.export.opt_suite_stale = True
            self.state.export.last_bundle = {
                **dict(bundle),
                "anim_latest_road_csv": mirrored.get("road_csv", ""),
                "anim_latest_axay_csv": mirrored.get("axay_csv", ""),
                "anim_latest_scenario_json": mirrored.get("scenario_json", ""),
            }
            self.state.export.last_error = ""
            self.state.status_message = "Файлы сценария подготовлены и копия для анимации обновлена."
            self._refresh_from_state()
            if show_dialog:
                messagebox.showinfo(
                    EDITOR_DIALOG_TITLE,
                    "Файлы сценария подготовлены.\n\n"
                    f"Сценарий: {bundle.get('scenario_json', '')}\n"
                    f"Профиль дороги: {bundle.get('road_csv', '')}\n"
                    f"Файл ускорений: {bundle.get('axay_csv', '')}\n"
                    f"Meta HO-004: {bundle.get('meta_json', '')}\n"
                    f"Source-of-truth WS-RING: {bundle.get('ring_source_of_truth_json', '')}\n\n"
                    "Копия для анимации:\n"
                    f"Сценарий: {mirrored.get('scenario_json', '')}\n"
                    f"Профиль дороги: {mirrored.get('road_csv', '')}\n"
                    f"Файл ускорений: {mirrored.get('axay_csv', '')}",
                )
            return dict(self.state.export.last_bundle)
        except Exception as exc:
            self.state.export.last_bundle = {}
            self.state.export.last_error = str(exc)
            self._refresh_from_state()
            if show_dialog:
                messagebox.showerror(EDITOR_DIALOG_TITLE, f"Не удалось подготовить файлы сценария:\n{exc}")
            return None

    def _build_optimization_auto_suite(self) -> None:
        self._apply_form_to_state()
        bundle = dict(self.state.export.last_bundle)
        if (
            self.state.export.artifacts_stale
            or not bundle.get("scenario_json")
            or not bundle.get("road_csv")
            or not bundle.get("axay_csv")
        ):
            bundle = self._generate_bundle(show_dialog=False) or {}
        if not bundle:
            return
        try:
            suite_info = materialize_ring_bundle_optimization_suite(
                bundle,
                workspace_dir=self.state.export.opt_workspace_dir or None,
                window_s=max(0.5, safe_float(self.state.export.opt_window_s, 4.0)),
            )
            self.state.export.last_bundle = {**bundle, **suite_info}
            self.state.export.last_error = ""
            self.state.export.opt_suite_stale = False
            self.state.status_message = "Набор оптимизации подготовлен в рабочей папке."
            self._refresh_from_state()
            messagebox.showinfo(
                EDITOR_DIALOG_TITLE,
                "Набор оптимизации готов.\n\n"
                f"Набор: {suite_info.get('suite_json', '')}\n"
                f"Описание: {suite_info.get('suite_meta_json', '')}\n"
                f"Рабочая папка: {suite_info.get('workspace_dir', '')}\n"
                f"Окно фрагмента: {suite_info.get('window_s', 0.0)} с\n"
                f"Строк в наборе: {suite_info.get('generated_row_count', 0)}",
            )
        except Exception as exc:
            self.state.export.last_error = str(exc)
            self._refresh_from_state()
            messagebox.showerror(EDITOR_DIALOG_TITLE, f"Не удалось собрать набор оптимизации:\n{exc}")

    def on_host_close(self) -> None:
        self._host_closed = True
        if self._queued_refresh is not None:
            try:
                self.root.after_cancel(self._queued_refresh)
            except Exception:
                pass
            self._queued_refresh = None

    def run(self) -> None:
        if self._owns_root:
            self.root.mainloop()


def main() -> int:
    app = DesktopRingScenarioEditor()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
