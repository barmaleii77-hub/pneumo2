from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from .desktop_ring_editor_runtime import RingEditorDiagnostics, RingPreviewSegment


def _set_widget_state(widget: tk.Misc, state: str) -> None:
    try:
        widget.configure(state=state)
    except tk.TclError:
        return


def _set_many_states(widgets: list[tk.Misc], state: str) -> None:
    for widget in widgets:
        _set_widget_state(widget, state)


def _format_float_or_dash(value: object, *, digits: int = 1) -> str:
    try:
        number = float(value)
    except Exception:
        return "—"
    if not math.isfinite(number):
        return "—"
    return f"{number:.{digits}f}"


def _add_entry(
    parent: tk.Misc,
    *,
    row: int,
    column: int,
    label: str,
    variable: tk.Variable,
    width: int = 12,
    sticky: str = "ew",
) -> ttk.Entry:
    ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=(0, 6), pady=3)
    entry = ttk.Entry(parent, textvariable=variable, width=width)
    entry.grid(row=row, column=column + 1, sticky=sticky, padx=(0, 12), pady=3)
    return entry


class SegmentListPanel(ttk.LabelFrame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_select: callable,
        on_add: callable,
        on_clone: callable,
        on_delete: callable,
        on_move_up: callable,
        on_move_down: callable,
    ) -> None:
        super().__init__(parent, text="Segments", padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(self)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(list_frame, exportselection=False, height=18)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.bind("<<ListboxSelect>>", lambda _event: on_select())

        buttons_top = ttk.Frame(self)
        buttons_top.grid(row=1, column=0, sticky="ew", pady=(8, 4))
        buttons_top.columnconfigure((0, 1), weight=1)
        ttk.Button(buttons_top, text="Добавить", command=on_add).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons_top, text="Клон", command=on_clone).grid(row=0, column=1, sticky="ew")

        buttons_bottom = ttk.Frame(self)
        buttons_bottom.grid(row=2, column=0, sticky="ew")
        buttons_bottom.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(buttons_bottom, text="Вверх", command=on_move_up).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons_bottom, text="Вниз", command=on_move_down).grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ttk.Button(buttons_bottom, text="Удалить", command=on_delete).grid(row=0, column=2, sticky="ew")

    def set_segments(self, items: list[str], selected_index: int) -> None:
        self.listbox.delete(0, "end")
        for item in items:
            self.listbox.insert("end", item)
        if items:
            safe_index = max(0, min(int(selected_index), len(items) - 1))
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(safe_index)
            self.listbox.activate(safe_index)
            self.listbox.see(safe_index)

    def selected_index(self) -> int:
        selection = self.listbox.curselection()
        return int(selection[0]) if selection else 0


class PreviewPanel(ttk.LabelFrame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, text="Preview кольца", padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        metrics = ttk.Frame(self)
        metrics.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for col in range(4):
            metrics.columnconfigure(col, weight=1)

        self.length_var = tk.StringVar(value="L ≈ 0.0 м")
        self.time_var = tk.StringVar(value="lap 0.0 с")
        self.speed_var = tk.StringVar(value="v 0.0→0.0 км/ч")
        self.seam_var = tk.StringVar(value="seam 0.0 мм")
        self.amp_var = tk.StringVar(value="Профиль ВСЕГО кольца: амплитуда A L/R (служебно) 0.0 / 0.0 мм")
        self.p2p_var = tk.StringVar(value="Профиль ВСЕГО кольца: полный размах max-min L/R (не A) 0.0 / 0.0 мм")
        ttk.Label(metrics, textvariable=self.length_var).grid(row=0, column=0, sticky="w")
        ttk.Label(metrics, textvariable=self.time_var).grid(row=0, column=1, sticky="w")
        ttk.Label(metrics, textvariable=self.speed_var).grid(row=0, column=2, sticky="w")
        ttk.Label(metrics, textvariable=self.seam_var).grid(row=0, column=3, sticky="w")
        ttk.Label(metrics, textvariable=self.amp_var).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(metrics, textvariable=self.p2p_var).grid(row=1, column=1, sticky="w", pady=(4, 0), columnspan=2)

        self.canvas = tk.Canvas(self, height=280, background="#0f172a", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self._redraw())

        self.footer_var = tk.StringVar(value="Выберите сегмент, чтобы редактировать motion/road/events.")
        ttk.Label(self, textvariable=self.footer_var, wraplength=760, justify="left").grid(row=2, column=0, sticky="ew", pady=(8, 0))

        self._diagnostics: RingEditorDiagnostics | None = None
        self._selected_index = 0

    def render(self, diagnostics: RingEditorDiagnostics, selected_index: int) -> None:
        self._diagnostics = diagnostics
        self._selected_index = int(selected_index)
        metrics = diagnostics.metrics
        self.length_var.set(f"L ≈ {float(metrics.get('ring_length_m', 0.0) or 0.0):.2f} м")
        self.time_var.set(
            f"lap {float(metrics.get('lap_time_s', 0.0) or 0.0):.2f} с, total {float(metrics.get('total_time_s', 0.0) or 0.0):.2f} с"
        )
        self.speed_var.set(
            f"v {float(metrics.get('start_speed_kph', 0.0) or 0.0):.1f}→{float(metrics.get('end_speed_kph', 0.0) or 0.0):.1f} км/ч"
        )
        self.seam_var.set(
            f"seam {float(metrics.get('seam_left_mm', 0.0) or 0.0):.1f}/{float(metrics.get('seam_right_mm', 0.0) or 0.0):.1f} мм | {metrics.get('closure_policy', '')}"
        )
        self.amp_var.set(
            "Профиль ВСЕГО кольца: амплитуда A L/R (служебно) "
            f"{float(metrics.get('ring_amp_left_mm', 0.0) or 0.0):.1f} / {float(metrics.get('ring_amp_right_mm', 0.0) or 0.0):.1f} мм"
        )
        self.p2p_var.set(
            "Профиль ВСЕГО кольца: полный размах max-min L/R (не A) "
            f"{float(metrics.get('ring_p2p_left_mm', 0.0) or 0.0):.1f} / {float(metrics.get('ring_p2p_right_mm', 0.0) or 0.0):.1f} мм"
        )
        local_summary = self._local_segment_summary(diagnostics, selected_index)
        if diagnostics.errors:
            self.footer_var.set(
                "Есть ошибки в spec. Preview показывает последнюю доступную оценку, экспорт сначала лучше починить."
                + (f"\n{local_summary}" if local_summary else "")
            )
        elif diagnostics.warnings:
            self.footer_var.set(
                "Preview собран. Есть предупреждения: проверьте diagnostics перед генерацией артефактов."
                + (f"\n{local_summary}" if local_summary else "")
            )
        else:
            self.footer_var.set(
                "Preview собран по canonical backend из scenario_ring.py."
                + (f"\n{local_summary}" if local_summary else "")
            )
        self._redraw()

    def _local_segment_summary(self, diagnostics: RingEditorDiagnostics, selected_index: int) -> str:
        if not (0 <= int(selected_index) < len(diagnostics.segment_rows)):
            return ""
        row = diagnostics.segment_rows[int(selected_index)]
        name = str(row.get("name", f"S{int(selected_index) + 1}"))
        turn = str(row.get("turn_direction", "STRAIGHT"))
        road = str(row.get("road_mode", "ISO8608"))
        if "L_amp_mm" in row and "R_amp_mm" in row:
            left_amp = float(row.get("L_amp_mm", 0.0) or 0.0)
            right_amp = float(row.get("R_amp_mm", 0.0) or 0.0)
            left_p2p = float(row.get("L_p2p_mm", 0.0) or 0.0)
            right_p2p = float(row.get("R_p2p_mm", 0.0) or 0.0)
            req_left = row.get("aL_req_mm")
            req_right = row.get("aR_req_mm")
            req_text = ""
            if _format_float_or_dash(req_left) != "—" or _format_float_or_dash(req_right) != "—":
                req_text = (
                    ", req A "
                    f"{_format_float_or_dash(req_left)}/{_format_float_or_dash(req_right)} мм"
                )
            return (
                f"Выбранный сегмент: {name} | {turn} | {road} | "
                f"Локальная амплитуда A L/R {left_amp:.1f}/{right_amp:.1f} мм | "
                f"Локальный полный размах max-min L/R (не A) {left_p2p:.1f}/{right_p2p:.1f} мм{req_text}"
            )
        return (
            f"Выбранный сегмент: {name} | {turn} | {road} | "
            f"v {float(row.get('speed_start_kph', 0.0) or 0.0):.1f}->{float(row.get('speed_end_kph', 0.0) or 0.0):.1f} км/ч | "
            f"L {float(row.get('length_m', 0.0) or 0.0):.2f} м"
        )

    def _redraw(self) -> None:
        self.canvas.delete("all")
        diagnostics = self._diagnostics
        if diagnostics is None:
            return
        width = max(80, int(self.canvas.winfo_width()))
        height = max(80, int(self.canvas.winfo_height()))
        cx = width / 2.0
        cy = height / 2.0
        radius = max(40.0, min(width, height) * 0.32)
        lane_w = max(14.0, radius * 0.12)

        self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline="#334155", width=lane_w)
        self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline="#1e293b", width=2)
        self.canvas.create_oval(cx - radius + lane_w, cy - radius + lane_w, cx + radius - lane_w, cy + radius - lane_w, outline="#1e293b", width=2)

        segments = diagnostics.preview_segments or []
        if not segments:
            self.canvas.create_text(cx, cy, text="Нет данных\nдля preview", fill="#e2e8f0", font=("Segoe UI", 14, "bold"))
            return

        for segment in segments:
            self._draw_segment_arc(segment, cx=cx, cy=cy, radius=radius, width=lane_w)

        self.canvas.create_text(
            cx,
            cy,
            text="RING\nEDITOR",
            fill="#e2e8f0",
            font=("Segoe UI", 14, "bold"),
            justify="center",
        )

    def _draw_segment_arc(
        self,
        segment: RingPreviewSegment,
        *,
        cx: float,
        cy: float,
        radius: float,
        width: float,
    ) -> None:
        bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
        start_deg = 90.0 - 360.0 * float(segment.start_fraction)
        extent_deg = -360.0 * max(0.002, float(segment.end_fraction - segment.start_fraction))
        line_w = width + (8.0 if segment.index == self._selected_index else 0.0)
        self.canvas.create_arc(*bbox, start=start_deg, extent=extent_deg, style="arc", outline=segment.color, width=line_w)

        mid_fraction = (float(segment.start_fraction) + float(segment.end_fraction)) * 0.5
        theta = math.radians(90.0 - 360.0 * mid_fraction)
        label_radius = radius + width * 0.9
        x = cx + label_radius * math.cos(theta)
        y = cy - label_radius * math.sin(theta)
        turn_symbol = {"STRAIGHT": "=", "LEFT": "L", "RIGHT": "R"}.get(str(segment.turn_direction).upper(), "?")
        event_suffix = f" •{segment.event_count}" if int(segment.event_count) > 0 else ""
        self.canvas.create_text(
            x,
            y,
            text=f"{segment.index + 1}:{turn_symbol}/{str(segment.road_mode).upper()}{event_suffix}",
            fill="#cbd5e1" if segment.index != self._selected_index else "#ffffff",
            font=("Segoe UI", 9, "bold" if segment.index == self._selected_index else "normal"),
        )


class MotionPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=8)
        self.columnconfigure(0, weight=1)

        general = ttk.LabelFrame(self, text="Общие параметры кольца", padding=8)
        general.grid(row=0, column=0, sticky="ew")
        for col in (1, 3, 5, 7):
            general.columnconfigure(col, weight=1)

        self.v0_var = tk.StringVar(value="40.0")
        self.seed_var = tk.StringVar(value="123")
        self.dx_var = tk.StringVar(value="0.02")
        self.dt_var = tk.StringVar(value="0.01")
        self.n_laps_var = tk.StringVar(value="1")
        self.wheelbase_var = tk.StringVar(value="1.5")
        self.track_var = tk.StringVar(value="1.0")
        self.closure_policy_var = tk.StringVar(value="closed_c1_periodic")

        self.general_widgets: list[tk.Misc] = [
            _add_entry(general, row=0, column=0, label="v0, км/ч", variable=self.v0_var),
            _add_entry(general, row=0, column=2, label="seed", variable=self.seed_var),
            _add_entry(general, row=0, column=4, label="dx, м", variable=self.dx_var),
            _add_entry(general, row=0, column=6, label="dt, c", variable=self.dt_var),
            _add_entry(general, row=1, column=0, label="n_laps", variable=self.n_laps_var),
            _add_entry(general, row=1, column=2, label="wheelbase, м", variable=self.wheelbase_var),
            _add_entry(general, row=1, column=4, label="track, м", variable=self.track_var),
        ]
        ttk.Label(general, text="closure_policy").grid(row=1, column=6, sticky="w", padx=(0, 6), pady=3)
        self.closure_combo = ttk.Combobox(
            general,
            textvariable=self.closure_policy_var,
            values=("closed_c1_periodic", "strict_exact"),
            state="readonly",
            width=20,
        )
        self.closure_combo.grid(row=1, column=7, sticky="ew", pady=3)
        self.general_widgets.append(self.closure_combo)

        segment = ttk.LabelFrame(self, text="Motion / Segment", padding=8)
        segment.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        for col in (1, 3, 5):
            segment.columnconfigure(col, weight=1)

        self.segment_name_var = tk.StringVar()
        self.duration_var = tk.StringVar()
        self.turn_direction_var = tk.StringVar(value="STRAIGHT")
        self.speed_end_var = tk.StringVar()
        self.turn_radius_var = tk.StringVar()
        self.start_speed_var = tk.StringVar(value="Старт: 0.0 км/ч")
        self.length_var = tk.StringVar(value="L сегм.: 0.0 м")
        self.delta_v_var = tk.StringVar(value="Δv: 0.0 км/ч")

        self.segment_widgets: list[tk.Misc] = [
            _add_entry(segment, row=0, column=0, label="Имя", variable=self.segment_name_var, width=20),
            _add_entry(segment, row=0, column=2, label="duration, c", variable=self.duration_var),
            _add_entry(segment, row=1, column=2, label="speed_end, км/ч", variable=self.speed_end_var),
            _add_entry(segment, row=1, column=4, label="turn_radius, м", variable=self.turn_radius_var),
        ]
        ttk.Label(segment, text="turn_direction").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        self.turn_combo = ttk.Combobox(
            segment,
            textvariable=self.turn_direction_var,
            values=("STRAIGHT", "LEFT", "RIGHT"),
            state="readonly",
            width=18,
        )
        self.turn_combo.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=3)
        self.segment_widgets.append(self.turn_combo)

        status = ttk.Frame(segment)
        status.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        status.columnconfigure((0, 1, 2), weight=1)
        ttk.Label(status, textvariable=self.start_speed_var).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.length_var).grid(row=0, column=1, sticky="w")
        ttk.Label(status, textvariable=self.delta_v_var).grid(row=0, column=2, sticky="w")

    def set_segment_enabled(self, enabled: bool) -> None:
        _set_many_states(self.segment_widgets, "normal" if enabled else "disabled")
        if enabled:
            _set_widget_state(self.turn_combo, "readonly")


class RoadPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=8)
        self.columnconfigure(0, weight=1)

        state_box = ttk.LabelFrame(self, text="Road state", padding=8)
        state_box.grid(row=0, column=0, sticky="ew")
        for col in (1, 3, 5, 7):
            state_box.columnconfigure(col, weight=1)

        self.mode_var = tk.StringVar(value="ISO8608")
        self.center_start_var = tk.StringVar(value="0.0")
        self.center_end_var = tk.StringVar(value="0.0")
        self.cross_start_var = tk.StringVar(value="0.0")
        self.cross_end_var = tk.StringVar(value="0.0")

        ttk.Label(state_box, text="mode").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        self.mode_combo = ttk.Combobox(
            state_box,
            textvariable=self.mode_var,
            values=("ISO8608", "SINE"),
            state="readonly",
            width=14,
        )
        self.mode_combo.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=3)
        self.state_widgets: list[tk.Misc] = [self.mode_combo]
        self.state_widgets.extend(
            [
                _add_entry(state_box, row=0, column=2, label="center start, мм", variable=self.center_start_var),
                _add_entry(state_box, row=0, column=4, label="center end, мм", variable=self.center_end_var),
                _add_entry(state_box, row=1, column=0, label="cross start, %", variable=self.cross_start_var),
                _add_entry(state_box, row=1, column=2, label="cross end, %", variable=self.cross_end_var),
            ]
        )

        self.iso_box = ttk.LabelFrame(self, text="ISO 8608", padding=8)
        self.iso_box.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for col in (1, 3, 5):
            self.iso_box.columnconfigure(col, weight=1)

        self.iso_class_var = tk.StringVar(value="E")
        self.gd_pick_var = tk.StringVar(value="mid")
        self.gd_scale_var = tk.StringVar(value="1.0")
        self.waviness_var = tk.StringVar(value="2.0")
        self.coherence_var = tk.StringVar(value="0.5")
        self.road_seed_var = tk.StringVar(value="12345")

        ttk.Label(self.iso_box, text="iso_class").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        self.iso_combo = ttk.Combobox(self.iso_box, textvariable=self.iso_class_var, values=tuple("ABCDEFGH"), state="readonly", width=12)
        self.iso_combo.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=3)
        ttk.Label(self.iso_box, text="gd_pick").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=3)
        self.gd_combo = ttk.Combobox(self.iso_box, textvariable=self.gd_pick_var, values=("lower", "mid", "upper"), state="readonly", width=12)
        self.gd_combo.grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=3)
        self.iso_widgets: list[tk.Misc] = [
            self.iso_combo,
            self.gd_combo,
            _add_entry(self.iso_box, row=0, column=4, label="gd_n0_scale", variable=self.gd_scale_var),
            _add_entry(self.iso_box, row=1, column=0, label="waviness_w", variable=self.waviness_var),
            _add_entry(self.iso_box, row=1, column=2, label="L/R coherence", variable=self.coherence_var),
            _add_entry(self.iso_box, row=1, column=4, label="seed", variable=self.road_seed_var),
        ]

        self.sine_box = ttk.LabelFrame(self, text="SINE", padding=8)
        self.sine_box.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        for col in (1, 3, 5):
            self.sine_box.columnconfigure(col, weight=1)

        self.aL_var = tk.StringVar(value="50.0")
        self.aR_var = tk.StringVar(value="50.0")
        self.lambdaL_var = tk.StringVar(value="1.5")
        self.lambdaR_var = tk.StringVar(value="1.5")
        self.phaseL_var = tk.StringVar(value="0.0")
        self.phaseR_var = tk.StringVar(value="180.0")
        self.rand_aL_var = tk.BooleanVar(value=False)
        self.rand_aL_p_var = tk.StringVar(value="0.5")
        self.rand_aL_lo_var = tk.StringVar(value="4.0")
        self.rand_aL_hi_var = tk.StringVar(value="4.0")
        self.rand_aR_var = tk.BooleanVar(value=False)
        self.rand_aR_p_var = tk.StringVar(value="0.5")
        self.rand_aR_lo_var = tk.StringVar(value="4.0")
        self.rand_aR_hi_var = tk.StringVar(value="4.0")
        self.rand_lL_var = tk.BooleanVar(value=False)
        self.rand_lL_p_var = tk.StringVar(value="0.5")
        self.rand_lL_lo_var = tk.StringVar(value="2.5")
        self.rand_lL_hi_var = tk.StringVar(value="2.5")
        self.rand_lR_var = tk.BooleanVar(value=False)
        self.rand_lR_p_var = tk.StringVar(value="0.5")
        self.rand_lR_lo_var = tk.StringVar(value="2.5")
        self.rand_lR_hi_var = tk.StringVar(value="2.5")
        self.rand_pL_var = tk.BooleanVar(value=True)
        self.rand_pL_p_var = tk.StringVar(value="0.5")
        self.rand_pL_lo_var = tk.StringVar(value="0.0")
        self.rand_pL_hi_var = tk.StringVar(value="360.0")
        self.rand_pR_var = tk.BooleanVar(value=True)
        self.rand_pR_p_var = tk.StringVar(value="0.5")
        self.rand_pR_lo_var = tk.StringVar(value="0.0")
        self.rand_pR_hi_var = tk.StringVar(value="360.0")

        self.sine_widgets: list[tk.Misc] = [
            _add_entry(self.sine_box, row=0, column=0, label="aL, мм", variable=self.aL_var),
            _add_entry(self.sine_box, row=0, column=2, label="aR, мм", variable=self.aR_var),
            _add_entry(self.sine_box, row=0, column=4, label="lambdaL, м", variable=self.lambdaL_var),
            _add_entry(self.sine_box, row=1, column=0, label="lambdaR, м", variable=self.lambdaR_var),
            _add_entry(self.sine_box, row=1, column=2, label="phaseL, °", variable=self.phaseL_var),
            _add_entry(self.sine_box, row=1, column=4, label="phaseR, °", variable=self.phaseR_var),
        ]

        random_box = ttk.LabelFrame(self.sine_box, text="Randomization", padding=8)
        random_box.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        for col in (1, 3, 5, 7):
            random_box.columnconfigure(col, weight=1)

        check = ttk.Checkbutton(random_box, text="rand_aL", variable=self.rand_aL_var)
        check.grid(row=0, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=0, column=1, label="p", variable=self.rand_aL_p_var, width=8),
                _add_entry(random_box, row=0, column=3, label="lo", variable=self.rand_aL_lo_var, width=8),
                _add_entry(random_box, row=0, column=5, label="hi", variable=self.rand_aL_hi_var, width=8),
            ]
        )

        check = ttk.Checkbutton(random_box, text="rand_aR", variable=self.rand_aR_var)
        check.grid(row=1, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=1, column=1, label="p", variable=self.rand_aR_p_var, width=8),
                _add_entry(random_box, row=1, column=3, label="lo", variable=self.rand_aR_lo_var, width=8),
                _add_entry(random_box, row=1, column=5, label="hi", variable=self.rand_aR_hi_var, width=8),
            ]
        )

        check = ttk.Checkbutton(random_box, text="rand_lL", variable=self.rand_lL_var)
        check.grid(row=2, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=2, column=1, label="p", variable=self.rand_lL_p_var, width=8),
                _add_entry(random_box, row=2, column=3, label="lo", variable=self.rand_lL_lo_var, width=8),
                _add_entry(random_box, row=2, column=5, label="hi", variable=self.rand_lL_hi_var, width=8),
            ]
        )

        check = ttk.Checkbutton(random_box, text="rand_lR", variable=self.rand_lR_var)
        check.grid(row=3, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=3, column=1, label="p", variable=self.rand_lR_p_var, width=8),
                _add_entry(random_box, row=3, column=3, label="lo", variable=self.rand_lR_lo_var, width=8),
                _add_entry(random_box, row=3, column=5, label="hi", variable=self.rand_lR_hi_var, width=8),
            ]
        )

        check = ttk.Checkbutton(random_box, text="rand_pL", variable=self.rand_pL_var)
        check.grid(row=4, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=4, column=1, label="p", variable=self.rand_pL_p_var, width=8),
                _add_entry(random_box, row=4, column=3, label="lo", variable=self.rand_pL_lo_var, width=8),
                _add_entry(random_box, row=4, column=5, label="hi", variable=self.rand_pL_hi_var, width=8),
            ]
        )

        check = ttk.Checkbutton(random_box, text="rand_pR", variable=self.rand_pR_var)
        check.grid(row=5, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=5, column=1, label="p", variable=self.rand_pR_p_var, width=8),
                _add_entry(random_box, row=5, column=3, label="lo", variable=self.rand_pR_lo_var, width=8),
                _add_entry(random_box, row=5, column=5, label="hi", variable=self.rand_pR_hi_var, width=8),
            ]
        )

        self.update_mode_visibility("ISO8608")

    def update_mode_visibility(self, mode: str) -> None:
        normalized = str(mode or "ISO8608").upper()
        if normalized == "SINE":
            _set_many_states(self.iso_widgets, "disabled")
            _set_many_states(self.sine_widgets, "normal")
        else:
            _set_many_states(self.iso_widgets, "normal")
            _set_widget_state(self.iso_combo, "readonly")
            _set_widget_state(self.gd_combo, "readonly")
            _set_many_states(self.sine_widgets, "disabled")
        _set_widget_state(self.mode_combo, "readonly")


class EventsPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc, *, on_select: callable, on_add: callable, on_update: callable, on_delete: callable) -> None:
        super().__init__(parent, padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        columns = ("kind", "side", "start", "length", "depth", "ramp")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=8)
        headers = {
            "kind": "kind",
            "side": "side",
            "start": "start_m",
            "length": "length_m",
            "depth": "depth_mm",
            "ramp": "ramp_m",
        }
        widths = {"kind": 90, "side": 80, "start": 80, "length": 80, "depth": 90, "ramp": 80}
        for key in columns:
            self.tree.heading(key, text=headers[key])
            self.tree.column(key, width=widths[key], anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: on_select())

        form = ttk.LabelFrame(self, text="Event editor", padding=8)
        form.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for col in (1, 3, 5):
            form.columnconfigure(col, weight=1)

        self.kind_var = tk.StringVar(value="яма")
        self.side_var = tk.StringVar(value="left")
        self.start_var = tk.StringVar(value="0.0")
        self.length_var = tk.StringVar(value="0.4")
        self.depth_var = tk.StringVar(value="-25.0")
        self.ramp_var = tk.StringVar(value="0.1")

        ttk.Label(form, text="kind").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        self.kind_combo = ttk.Combobox(form, textvariable=self.kind_var, values=("яма", "препятствие"), state="readonly", width=14)
        self.kind_combo.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=3)
        ttk.Label(form, text="side").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=3)
        self.side_combo = ttk.Combobox(form, textvariable=self.side_var, values=("left", "right", "both"), state="readonly", width=12)
        self.side_combo.grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=3)
        _add_entry(form, row=0, column=4, label="start_m", variable=self.start_var)
        _add_entry(form, row=1, column=0, label="length_m", variable=self.length_var)
        _add_entry(form, row=1, column=2, label="depth_mm", variable=self.depth_var)
        _add_entry(form, row=1, column=4, label="ramp_m", variable=self.ramp_var)

        buttons = ttk.Frame(form)
        buttons.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        buttons.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(buttons, text="Добавить", command=on_add).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Обновить", command=on_update).grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Удалить", command=on_delete).grid(row=0, column=2, sticky="ew")

    def set_events(self, events: list[dict[str, object]]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, event in enumerate(events):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    event.get("kind", ""),
                    event.get("side", ""),
                    event.get("start_m", ""),
                    event.get("length_m", ""),
                    event.get("depth_mm", ""),
                    event.get("ramp_m", ""),
                ),
            )

    def selected_index(self) -> int | None:
        selected = self.tree.selection()
        if not selected:
            return None
        try:
            return int(selected[0])
        except Exception:
            return None

    def select_index(self, index: int | None) -> None:
        self.tree.selection_remove(*self.tree.selection())
        if index is None:
            return
        item_id = str(index)
        if item_id in self.tree.get_children():
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)
            self.tree.see(item_id)


class DiagnosticsPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)
        self.rowconfigure(5, weight=1)
        self.rowconfigure(7, weight=1)

        self.summary_var = tk.StringVar(value="Diagnostics не собраны.")
        ttk.Label(self, textvariable=self.summary_var, justify="left", wraplength=880).grid(row=0, column=0, sticky="ew")

        message_frame = ttk.LabelFrame(self, text="Сообщения", padding=6)
        message_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        message_frame.columnconfigure(0, weight=1)
        message_frame.rowconfigure(0, weight=1)
        self.messages = tk.Text(message_frame, height=10, wrap="word")
        self.messages.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(message_frame, orient="vertical", command=self.messages.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.messages.configure(yscrollcommand=scroll.set, state="disabled")

        table_frame = ttk.LabelFrame(self, text="Segment diagnostics", padding=6)
        table_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(1, weight=1)

        ttk.Label(
            table_frame,
            text=(
                "Сводка ниже специально разделяет амплитуду A (полуразмах) и полный размах max-min. "
                "Для синуса полный размах = 2A, поэтому его нельзя читать как амплитуду A."
            ),
            justify="left",
            wraplength=860,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        columns = ("seg", "name", "turn", "v0", "v1", "len", "road", "events", "l_a", "l_p2p", "r_a", "r_p2p")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
        headers = {
            "seg": "#",
            "name": "name",
            "turn": "turn",
            "v0": "v0",
            "v1": "v1",
            "len": "L, м",
            "road": "road",
            "events": "events",
            "l_a": "Л A",
            "l_p2p": "Л p-p",
            "r_a": "П A",
            "r_p2p": "П p-p",
        }
        widths = {
            "seg": 48,
            "name": 180,
            "turn": 90,
            "v0": 76,
            "v1": 76,
            "len": 76,
            "road": 88,
            "events": 62,
            "l_a": 74,
            "l_p2p": 80,
            "r_a": 74,
            "r_p2p": 80,
        }
        for key in columns:
            self.tree.heading(key, text=headers[key])
            self.tree.column(key, width=widths[key], anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew")
        table_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        table_scroll.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=table_scroll.set)

        opt_frame = ttk.LabelFrame(self, text="Optimization windows", padding=6)
        opt_frame.grid(row=5, column=0, sticky="nsew", pady=(8, 0))
        opt_frame.columnconfigure(0, weight=1)
        opt_frame.rowconfigure(1, weight=1)

        self.opt_summary_var = tk.StringVar(value="Optimization suite preview ещё не готов.")
        ttk.Label(opt_frame, textvariable=self.opt_summary_var, justify="left", wraplength=880).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        opt_columns = ("id", "label", "t0", "t1", "dt", "peak", "segments")
        self.opt_tree = ttk.Treeview(opt_frame, columns=opt_columns, show="headings", height=6)
        opt_headers = {
            "id": "id",
            "label": "label",
            "t0": "t0, s",
            "t1": "t1, s",
            "dt": "dt, s",
            "peak": "peak",
            "segments": "segments",
        }
        opt_widths = {"id": 120, "label": 110, "t0": 70, "t1": 70, "dt": 70, "peak": 80, "segments": 360}
        for key in opt_columns:
            self.opt_tree.heading(key, text=opt_headers[key])
            self.opt_tree.column(key, width=opt_widths[key], anchor="center")
        self.opt_tree.grid(row=1, column=0, sticky="nsew")
        opt_scroll = ttk.Scrollbar(opt_frame, orient="vertical", command=self.opt_tree.yview)
        opt_scroll.grid(row=1, column=1, sticky="ns")
        self.opt_tree.configure(yscrollcommand=opt_scroll.set)

        opt_suite_frame = ttk.LabelFrame(self, text="Optimization suite rows", padding=6)
        opt_suite_frame.grid(row=7, column=0, sticky="nsew", pady=(8, 0))
        opt_suite_frame.columnconfigure(0, weight=1)
        opt_suite_frame.rowconfigure(0, weight=1)

        opt_suite_columns = ("stage", "name", "kind", "label")
        self.opt_suite_tree = ttk.Treeview(opt_suite_frame, columns=opt_suite_columns, show="headings", height=6)
        opt_suite_headers = {
            "stage": "stage",
            "name": "name",
            "kind": "kind",
            "label": "label",
        }
        opt_suite_widths = {"stage": 70, "name": 200, "kind": 90, "label": 320}
        for key in opt_suite_columns:
            self.opt_suite_tree.heading(key, text=opt_suite_headers[key])
            self.opt_suite_tree.column(key, width=opt_suite_widths[key], anchor="center")
        self.opt_suite_tree.grid(row=0, column=0, sticky="nsew")
        opt_suite_scroll = ttk.Scrollbar(opt_suite_frame, orient="vertical", command=self.opt_suite_tree.yview)
        opt_suite_scroll.grid(row=0, column=1, sticky="ns")
        self.opt_suite_tree.configure(yscrollcommand=opt_suite_scroll.set)

    def set_messages(self, text: str) -> None:
        self.messages.configure(state="normal")
        self.messages.delete("1.0", "end")
        self.messages.insert("1.0", text)
        self.messages.configure(state="disabled")

    def set_segment_rows(self, rows: list[dict[str, object]]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, row in enumerate(rows):
            seg_number = int(row.get("seg_idx", row.get("index", index) or index))
            if "seg_idx" not in row:
                seg_number += 1
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    seg_number,
                    row.get("name", ""),
                    row.get("turn_direction", ""),
                    f"{float(row.get('speed_start_kph', 0.0) or 0.0):.1f}",
                    f"{float(row.get('speed_end_kph', 0.0) or 0.0):.1f}",
                    f"{float(row.get('length_m', 0.0) or 0.0):.2f}",
                    row.get("road_mode", ""),
                    int(row.get("event_count", 0) or 0),
                    _format_float_or_dash(row.get("L_amp_mm")),
                    _format_float_or_dash(row.get("L_p2p_mm")),
                    _format_float_or_dash(row.get("R_amp_mm")),
                    _format_float_or_dash(row.get("R_p2p_mm")),
                ),
            )

    def set_opt_fragment_rows(self, rows: list[dict[str, object]]) -> None:
        for item in self.opt_tree.get_children():
            self.opt_tree.delete(item)
        for index, row in enumerate(rows):
            self.opt_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    row.get("id", ""),
                    row.get("label", ""),
                    f"{float(row.get('t_start_s', 0.0) or 0.0):.2f}",
                    f"{float(row.get('t_end_s', 0.0) or 0.0):.2f}",
                    f"{float(row.get('duration_s', 0.0) or 0.0):.2f}",
                    f"{float(row.get('peak_value', 0.0) or 0.0):.3f}",
                    row.get("segments_text", ""),
                ),
            )

    def set_opt_fragment_summary(self, text: str) -> None:
        self.opt_summary_var.set(str(text or "Optimization suite preview ещё не готов."))

    def set_opt_suite_rows(self, rows: list[dict[str, object]]) -> None:
        for item in self.opt_suite_tree.get_children():
            self.opt_suite_tree.delete(item)
        for index, row in enumerate(rows):
            self.opt_suite_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    int(row.get("stage", 0) or 0),
                    row.get("name", ""),
                    row.get("kind", ""),
                    row.get("label", ""),
                ),
            )


class ExportPanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_choose_dir: callable,
        on_choose_opt_workspace: callable,
        on_load_spec: callable,
        on_save_spec: callable,
        on_generate_bundle: callable,
        on_build_auto_suite: callable,
        on_open_output: callable,
        on_open_opt_workspace: callable,
        on_open_opt_suite: callable,
        on_open_last_spec: callable,
        on_open_last_road: callable,
        on_open_last_axay: callable,
        on_open_anim_latest: callable,
    ) -> None:
        super().__init__(parent, padding=8)
        self.columnconfigure(0, weight=1)

        top = ttk.LabelFrame(self, text="Экспорт", padding=8)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        self.output_dir_var = tk.StringVar()
        self.tag_var = tk.StringVar(value="ring")
        self.last_export_var = tk.StringVar(value="Артефакты ещё не генерировались.")

        ttk.Label(top, text="output_dir").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(top, textvariable=self.output_dir_var).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Button(top, text="Выбрать", command=on_choose_dir).grid(row=0, column=2, sticky="ew", padx=(8, 0), pady=3)

        ttk.Label(top, text="tag").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(top, textvariable=self.tag_var, width=20).grid(row=1, column=1, sticky="w", pady=3)

        opt_box = ttk.LabelFrame(self, text="Optimization handoff", padding=8)
        opt_box.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        opt_box.columnconfigure(1, weight=1)

        self.opt_workspace_var = tk.StringVar()
        self.opt_window_var = tk.StringVar(value="4.0")

        ttk.Label(opt_box, text="workspace_dir").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(opt_box, textvariable=self.opt_workspace_var).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Button(opt_box, text="Выбрать", command=on_choose_opt_workspace).grid(row=0, column=2, sticky="ew", padx=(8, 0), pady=3)
        ttk.Label(opt_box, text="fragment_window_s").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(opt_box, textvariable=self.opt_window_var, width=12).grid(row=1, column=1, sticky="w", pady=3)
        opt_actions = ttk.Frame(opt_box)
        opt_actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        opt_actions.columnconfigure((0, 1), weight=1)
        ttk.Button(opt_actions, text="Open opt workspace", command=on_open_opt_workspace).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(opt_actions, text="Open last suite", command=on_open_opt_suite).grid(row=0, column=1, sticky="ew")

        artifact_box = ttk.LabelFrame(self, text="Quick open last artifacts", padding=8)
        artifact_box.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        artifact_box.columnconfigure((0, 1, 2, 3), weight=1)
        ttk.Button(artifact_box, text="Open last spec", command=on_open_last_spec).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(artifact_box, text="Open last road", command=on_open_last_road).grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ttk.Button(artifact_box, text="Open last axay", command=on_open_last_axay).grid(row=0, column=2, sticky="ew", padx=(0, 4))
        ttk.Button(artifact_box, text="Open anim_latest exports", command=on_open_anim_latest).grid(row=0, column=3, sticky="ew")

        buttons = ttk.Frame(self)
        buttons.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        buttons.columnconfigure((0, 1, 2, 3, 4), weight=1)
        ttk.Button(buttons, text="Load spec", command=on_load_spec).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Save spec", command=on_save_spec).grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Generate spec/road/axay", command=on_generate_bundle).grid(row=0, column=2, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Build opt suite", command=on_build_auto_suite).grid(row=0, column=3, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Открыть output", command=on_open_output).grid(row=0, column=4, sticky="ew")

        ttk.Label(self, textvariable=self.last_export_var, wraplength=880, justify="left").grid(row=4, column=0, sticky="ew", pady=(10, 0))
