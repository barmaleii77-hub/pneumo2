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


def _turn_label(value: object) -> str:
    mapping = {
        "STRAIGHT": "Прямо",
        "LEFT": "Влево",
        "RIGHT": "Вправо",
    }
    return mapping.get(str(value or "").upper(), str(value or ""))


def _road_mode_label(value: object) -> str:
    mapping = {
        "ISO8608": "ISO 8608",
        "SINE": "Синусоида",
    }
    return mapping.get(str(value or "").upper(), str(value or ""))


def _closure_policy_label(value: object) -> str:
    mapping = {
        "closed_c1_periodic": "гладкое замыкание",
        "closed_exact": "точное замыкание без коррекции",
        "strict_exact": "строгое совпадение",
        "preview_open_only": "открытый preview",
    }
    return mapping.get(str(value or "").strip(), str(value or ""))


def _event_side_label(value: object) -> str:
    mapping = {
        "left": "Левый",
        "right": "Правый",
        "both": "Оба",
    }
    return mapping.get(str(value or "").lower(), str(value or ""))


def _opt_kind_label(value: object) -> str:
    mapping = {
        "seed": "базовый сценарий",
        "fragment": "характерный фрагмент",
        "full": "полный прогон",
    }
    return mapping.get(str(value or "").strip().lower(), str(value or ""))


def _humanize_opt_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    exact = {
        "ring_auto_full": "полный круг",
        "микро_pitch": "микро тангаж",
        "микро_diagonal": "микро диагональ",
    }
    if text in exact:
        return exact[text]
    text = text.replace("pitch", "тангаж")
    text = text.replace("diagonal", "диагональ")
    text = text.replace("_", " ")
    return " ".join(text.split())


def _humanize_opt_summary_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "Набор оптимизации ещё не подготовлен."
    replacements = {
        "stage0 seeds": "базовых сценариев стадии 0",
        "stage1 seeds": "базовых сценариев стадии 1",
        "fragments": "характерных фрагментов",
        "stage2 full": "полных прогонов стадии 2",
        "total": "всего строк",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _short_turn_label(value: object) -> str:
    mapping = {
        "STRAIGHT": "прямо",
        "LEFT": "влево",
        "RIGHT": "вправо",
    }
    return mapping.get(str(value or "").upper(), str(value or ""))


def _short_road_mode_label(value: object) -> str:
    mapping = {
        "ISO8608": "ISO 8608",
        "SINE": "синус",
    }
    return mapping.get(str(value or "").upper(), str(value or ""))


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


class ScrollablePanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        self.body = ttk.Frame(self.canvas)
        self.body.columnconfigure(0, weight=1)
        self._body_window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_body_configure(self, _event: object) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: object) -> None:
        width = int(getattr(event, "width", 0) or self.canvas.winfo_width())
        self.canvas.itemconfigure(self._body_window, width=width)

    def scroll_to_top(self) -> None:
        self.canvas.yview_moveto(0.0)


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
        super().__init__(parent, text="Сегменты", padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(self)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(list_frame, exportselection=False, height=18)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(list_frame, orient="horizontal", command=self.listbox.xview)
        x_scroll.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.listbox.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
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
        super().__init__(parent, text="Развёрнутый циклический preview", padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        metrics = ttk.Frame(self)
        metrics.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for col in range(4):
            metrics.columnconfigure(col, weight=1)

        self.length_var = tk.StringVar(value="Длина кольца примерно 0.0 м")
        self.time_var = tk.StringVar(value="Длительность круга 0.0 с")
        self.speed_var = tk.StringVar(value="Скорость 0.0→0.0 км/ч")
        self.seam_var = tk.StringVar(value="Шов 0.0 мм")
        self.amp_var = tk.StringVar(value="Профиль всего кольца: амплитуда (A) левого/правого следа, мм 0.0 / 0.0")
        self.p2p_var = tk.StringVar(value="Профиль всего кольца: полный размах левого/правого следа, мм 0.0 / 0.0")
        ttk.Label(metrics, textvariable=self.length_var).grid(row=0, column=0, sticky="w")
        ttk.Label(metrics, textvariable=self.time_var).grid(row=0, column=1, sticky="w")
        ttk.Label(metrics, textvariable=self.speed_var).grid(row=0, column=2, sticky="w")
        ttk.Label(metrics, textvariable=self.seam_var).grid(row=0, column=3, sticky="w")
        ttk.Label(metrics, textvariable=self.amp_var).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(metrics, textvariable=self.p2p_var).grid(row=1, column=1, sticky="w", pady=(4, 0), columnspan=2)

        self.canvas = tk.Canvas(self, height=280, background="#0f172a", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self._redraw())

        self.footer_var = tk.StringVar(value="Выберите сегмент, чтобы редактировать движение, дорогу и события.")
        ttk.Label(self, textvariable=self.footer_var, wraplength=760, justify="left").grid(row=2, column=0, sticky="ew", pady=(8, 0))

        self._diagnostics: RingEditorDiagnostics | None = None
        self._selected_index = 0

    def render(self, diagnostics: RingEditorDiagnostics, selected_index: int) -> None:
        self._diagnostics = diagnostics
        self._selected_index = int(selected_index)
        metrics = diagnostics.metrics
        self.length_var.set(f"Длина кольца примерно {float(metrics.get('ring_length_m', 0.0) or 0.0):.2f} м")
        self.time_var.set(
            f"Круг {float(metrics.get('lap_time_s', 0.0) or 0.0):.2f} с, всего {float(metrics.get('total_time_s', 0.0) or 0.0):.2f} с"
        )
        self.speed_var.set(
            f"Скорость {float(metrics.get('start_speed_kph', 0.0) or 0.0):.1f}→{float(metrics.get('end_speed_kph', 0.0) or 0.0):.1f} км/ч"
        )
        self.seam_var.set(
            f"Шов замыкания слева/справа {float(metrics.get('seam_left_mm', 0.0) or 0.0):.1f}/{float(metrics.get('seam_right_mm', 0.0) or 0.0):.1f} мм | "
            f"{_closure_policy_label(metrics.get('closure_policy', ''))}"
        )
        self.amp_var.set(
            "Профиль всего кольца: амплитуда (A) левого/правого следа, мм "
            f"{float(metrics.get('ring_amp_left_mm', 0.0) or 0.0):.1f} / {float(metrics.get('ring_amp_right_mm', 0.0) or 0.0):.1f}"
        )
        self.p2p_var.set(
            "Профиль всего кольца: полный размах левого/правого следа, мм "
            f"{float(metrics.get('ring_p2p_left_mm', 0.0) or 0.0):.1f} / {float(metrics.get('ring_p2p_right_mm', 0.0) or 0.0):.1f}"
        )
        local_summary = self._local_segment_summary(diagnostics, selected_index)
        if diagnostics.errors:
            self.footer_var.set(
                "Есть ошибки в сценарии. Предпросмотр показывает последнюю доступную оценку, экспорт сначала лучше починить."
                + (f"\n{local_summary}" if local_summary else "")
            )
        elif diagnostics.warnings:
            self.footer_var.set(
                "Предпросмотр собран. Есть предупреждения: проверьте диагностику перед генерацией артефактов."
                + (f"\n{local_summary}" if local_summary else "")
            )
        else:
            self.footer_var.set(
                "Предпросмотр собран по каноническим правилам кольцевого сценария."
                + (f"\n{local_summary}" if local_summary else "")
            )
        self._redraw()

    def _local_segment_summary(self, diagnostics: RingEditorDiagnostics, selected_index: int) -> str:
        if not (0 <= int(selected_index) < len(diagnostics.segment_rows)):
            return ""
        row = diagnostics.segment_rows[int(selected_index)]
        name = str(row.get("name", f"S{int(selected_index) + 1}"))
        turn = _turn_label(row.get("turn_direction", "STRAIGHT"))
        road = _road_mode_label(row.get("road_mode", "ISO8608"))
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
                    ", заданная амплитуда (A) "
                    f"{_format_float_or_dash(req_left)}/{_format_float_or_dash(req_right)} мм"
                )
            return (
                f"Выбранный сегмент: {name} | {turn} | {road} | "
                f"Локальная амплитуда (A) левого/правого следа {left_amp:.1f}/{right_amp:.1f} мм | "
                f"Локальный полный размах левого/правого следа {left_p2p:.1f}/{right_p2p:.1f} мм{req_text}"
            )
        return (
            f"Выбранный сегмент: {name} | {turn} | {road} | "
            f"Скорость {float(row.get('speed_start_kph', 0.0) or 0.0):.1f}->{float(row.get('speed_end_kph', 0.0) or 0.0):.1f} км/ч | "
            f"Длина {float(row.get('length_m', 0.0) or 0.0):.2f} м"
        )

    def _redraw(self) -> None:
        self.canvas.delete("all")
        diagnostics = self._diagnostics
        if diagnostics is None:
            return
        width = max(80, int(self.canvas.winfo_width()))
        height = max(80, int(self.canvas.winfo_height()))

        segments = diagnostics.preview_segments or []
        if not segments:
            self.canvas.create_text(
                width / 2.0,
                height / 2.0,
                text="Нет данных для развёрнутого preview",
                fill="#e2e8f0",
                font=("Segoe UI", 14, "bold"),
            )
            return

        left_pad = 56.0
        right_pad = 42.0
        top = 74.0
        bar_h = 54.0
        axis_y = top + bar_h + 36.0
        usable_w = max(40.0, width - left_pad - right_pad)
        self.canvas.create_text(
            left_pad,
            24,
            text="Один круг показан как развёрнутая дистанция 0 → L. Повтор справа — только seam-preview, не геометрическое кольцо.",
            fill="#e2e8f0",
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        )
        self.canvas.create_line(left_pad, axis_y, left_pad + usable_w, axis_y, fill="#475569", width=2)
        for tick in range(5):
            x = left_pad + usable_w * tick / 4.0
            self.canvas.create_line(x, axis_y - 7, x, axis_y + 7, fill="#64748b", width=1)
            self.canvas.create_text(x, axis_y + 20, text=f"{tick * 25}%", fill="#cbd5e1", font=("Segoe UI", 9))

        for segment in segments:
            self._draw_segment_bar(segment, left_pad=left_pad, top=top, usable_w=usable_w, height=bar_h)

        seam_x = left_pad + usable_w
        self.canvas.create_line(seam_x, top - 16, seam_x, axis_y + 12, fill="#f97316", width=2, dash=(4, 3))
        self.canvas.create_text(seam_x, top - 24, text="шов L→0", fill="#fed7aa", font=("Segoe UI", 9, "bold"))

        ghost_w = min(140.0, usable_w * 0.18)
        ghost_left = min(width - right_pad - ghost_w, seam_x + 12.0)
        if ghost_left > seam_x + 2.0:
            self.canvas.create_rectangle(ghost_left, top, ghost_left + ghost_w, top + bar_h, outline="#334155", fill="#111827", width=1)
            self.canvas.create_text(
                ghost_left + ghost_w / 2.0,
                top + bar_h / 2.0,
                text="начало\nслед. круга",
                fill="#94a3b8",
                font=("Segoe UI", 9),
                justify="center",
            )

    def _draw_segment_bar(
        self,
        segment: RingPreviewSegment,
        *,
        left_pad: float,
        top: float,
        usable_w: float,
        height: float,
    ) -> None:
        x0 = left_pad + usable_w * max(0.0, min(1.0, float(segment.start_fraction)))
        x1 = left_pad + usable_w * max(0.0, min(1.0, float(segment.end_fraction)))
        if x1 <= x0:
            x1 = x0 + 2.0
        outline = "#ffffff" if segment.index == self._selected_index else "#1e293b"
        line_w = 3 if segment.index == self._selected_index else 1
        self.canvas.create_rectangle(x0, top, x1, top + height, fill=segment.color, outline=outline, width=line_w)
        mid_x = 0.5 * (x0 + x1)
        turn_text = _short_turn_label(segment.turn_direction)
        road_text = _short_road_mode_label(segment.road_mode)
        event_suffix = f" • {segment.event_count} соб." if int(segment.event_count) > 0 else ""
        self.canvas.create_text(
            mid_x,
            top + height / 2.0,
            text=f"{segment.index + 1}: {turn_text} / {road_text}{event_suffix}",
            fill="#cbd5e1" if segment.index != self._selected_index else "#ffffff",
            font=("Segoe UI", 9, "bold" if segment.index == self._selected_index else "normal"),
            width=max(40, int(x1 - x0 - 6)),
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
        self.closure_policy_var = tk.StringVar(value="Гладкое замыкание")

        self.general_widgets: list[tk.Misc] = [
            _add_entry(general, row=0, column=0, label="Начальная скорость, км/ч", variable=self.v0_var),
            _add_entry(general, row=0, column=2, label="Зерно генерации", variable=self.seed_var),
            _add_entry(general, row=0, column=4, label="Шаг профиля, м", variable=self.dx_var),
            _add_entry(general, row=0, column=6, label="Шаг времени, с", variable=self.dt_var),
            _add_entry(general, row=1, column=0, label="Число кругов", variable=self.n_laps_var),
            _add_entry(general, row=1, column=2, label="Колёсная база, м", variable=self.wheelbase_var),
            _add_entry(general, row=1, column=4, label="Колея, м", variable=self.track_var),
        ]
        ttk.Label(general, text="Замыкание кольца").grid(row=1, column=6, sticky="w", padx=(0, 6), pady=3)
        self.closure_combo = ttk.Combobox(
            general,
            textvariable=self.closure_policy_var,
            values=("Гладкое замыкание", "Строгое совпадение", "Открытый preview"),
            state="readonly",
            width=20,
        )
        self.closure_combo.grid(row=1, column=7, sticky="ew", pady=3)
        self.general_widgets.append(self.closure_combo)

        segment = ttk.LabelFrame(self, text="Движение и сегмент", padding=8)
        segment.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        for col in (1, 3, 5):
            segment.columnconfigure(col, weight=1)

        self.segment_name_var = tk.StringVar()
        self.duration_var = tk.StringVar()
        self.turn_direction_var = tk.StringVar(value="Прямо")
        self.passage_mode_var = tk.StringVar(value="Постоянный")
        self.speed_end_var = tk.StringVar()
        self.turn_radius_var = tk.StringVar()
        self.start_speed_var = tk.StringVar(value="Стартовая скорость: 0.0 км/ч")
        self.length_var = tk.StringVar(value="Длина сегмента: 0.0 м")
        self.delta_v_var = tk.StringVar(value="Изменение скорости: 0.0 км/ч")

        self.segment_widgets: list[tk.Misc] = [
            _add_entry(segment, row=0, column=0, label="Имя", variable=self.segment_name_var, width=20),
            _add_entry(segment, row=0, column=2, label="Длительность, с", variable=self.duration_var),
            _add_entry(segment, row=1, column=2, label="Скорость в конце, км/ч", variable=self.speed_end_var),
            _add_entry(segment, row=2, column=2, label="Радиус поворота, м", variable=self.turn_radius_var),
        ]
        ttk.Label(segment, text="Направление").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        self.turn_combo = ttk.Combobox(
            segment,
            textvariable=self.turn_direction_var,
            values=("Прямо", "Влево", "Вправо"),
            state="readonly",
            width=18,
        )
        self.turn_combo.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=3)
        self.segment_widgets.append(self.turn_combo)
        ttk.Label(segment, text="Режим прохождения").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=3)
        self.passage_combo = ttk.Combobox(
            segment,
            textvariable=self.passage_mode_var,
            values=("Постоянный", "Разгон", "Торможение", "Пользовательский"),
            state="readonly",
            width=18,
        )
        self.passage_combo.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=3)
        self.segment_widgets.append(self.passage_combo)

        status = ttk.Frame(segment)
        status.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        status.columnconfigure((0, 1, 2), weight=1)
        ttk.Label(status, textvariable=self.start_speed_var).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.length_var).grid(row=0, column=1, sticky="w")
        ttk.Label(status, textvariable=self.delta_v_var).grid(row=0, column=2, sticky="w")

    def set_segment_enabled(self, enabled: bool) -> None:
        _set_many_states(self.segment_widgets, "normal" if enabled else "disabled")
        if enabled:
            _set_widget_state(self.turn_combo, "readonly")
            _set_widget_state(self.passage_combo, "readonly")


class RoadPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=8)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        state_box = ttk.LabelFrame(self, text="Параметры дороги", padding=8)
        state_box.grid(row=0, column=0, sticky="ew")
        for col in (1, 3, 5, 7):
            state_box.columnconfigure(col, weight=1)

        self.mode_var = tk.StringVar(value="ISO 8608")
        self.center_start_var = tk.StringVar(value="0.0")
        self.center_end_var = tk.StringVar(value="0.0")
        self.cross_start_var = tk.StringVar(value="0.0")
        self.cross_end_var = tk.StringVar(value="0.0")

        ttk.Label(state_box, text="Тип профиля").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        self.mode_combo = ttk.Combobox(
            state_box,
            textvariable=self.mode_var,
            values=("ISO 8608", "Синусоида"),
            state="readonly",
            width=14,
        )
        self.mode_combo.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=3)
        self.state_widgets: list[tk.Misc] = [self.mode_combo]
        self.center_start_entry = _add_entry(state_box, row=0, column=2, label="Центр в начале, мм", variable=self.center_start_var)
        self.center_end_entry = _add_entry(state_box, row=0, column=4, label="Центр в конце, мм", variable=self.center_end_var)
        self.cross_start_entry = _add_entry(state_box, row=1, column=0, label="Поперечный уклон в начале, %", variable=self.cross_start_var)
        self.cross_end_entry = _add_entry(state_box, row=1, column=2, label="Поперечный уклон в конце, %", variable=self.cross_end_var)
        self.state_widgets.extend(
            [
                self.center_start_entry,
                self.center_end_entry,
                self.cross_start_entry,
                self.cross_end_entry,
            ]
        )

        self.iso_box = ttk.LabelFrame(self, text="Профиль ISO 8608", padding=8)
        self.iso_box.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for col in (1, 3, 5):
            self.iso_box.columnconfigure(col, weight=1)

        self.iso_class_var = tk.StringVar(value="E")
        self.gd_pick_var = tk.StringVar(value="средний")
        self.gd_scale_var = tk.StringVar(value="1.0")
        self.waviness_var = tk.StringVar(value="2.0")
        self.coherence_var = tk.StringVar(value="0.5")
        self.road_seed_var = tk.StringVar(value="12345")

        ttk.Label(self.iso_box, text="Класс ISO").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        self.iso_combo = ttk.Combobox(self.iso_box, textvariable=self.iso_class_var, values=tuple("ABCDEFGH"), state="readonly", width=12)
        self.iso_combo.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=3)
        ttk.Label(self.iso_box, text="Уровень шероховатости").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=3)
        self.gd_combo = ttk.Combobox(self.iso_box, textvariable=self.gd_pick_var, values=("нижний", "средний", "верхний"), state="readonly", width=12)
        self.gd_combo.grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=3)
        self.iso_widgets: list[tk.Misc] = [
            self.iso_combo,
            self.gd_combo,
            _add_entry(self.iso_box, row=0, column=4, label="Масштаб Gd(n0)", variable=self.gd_scale_var),
            _add_entry(self.iso_box, row=1, column=0, label="Извилистость w", variable=self.waviness_var),
            _add_entry(self.iso_box, row=1, column=2, label="Связность Л/П", variable=self.coherence_var),
            _add_entry(self.iso_box, row=1, column=4, label="Зерно", variable=self.road_seed_var),
        ]

        self.sine_box = ttk.LabelFrame(self, text="Синусоидальный профиль", padding=8)
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
            _add_entry(self.sine_box, row=0, column=0, label="Амплитуда слева, мм", variable=self.aL_var),
            _add_entry(self.sine_box, row=0, column=2, label="Амплитуда справа, мм", variable=self.aR_var),
            _add_entry(self.sine_box, row=0, column=4, label="Длина волны слева, м", variable=self.lambdaL_var),
            _add_entry(self.sine_box, row=1, column=0, label="Длина волны справа, м", variable=self.lambdaR_var),
            _add_entry(self.sine_box, row=1, column=2, label="Фаза слева, °", variable=self.phaseL_var),
            _add_entry(self.sine_box, row=1, column=4, label="Фаза справа, °", variable=self.phaseR_var),
        ]

        random_box = ttk.LabelFrame(self.sine_box, text="Случайная вариация", padding=8)
        random_box.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        for col in (1, 3, 5, 7):
            random_box.columnconfigure(col, weight=1)

        check = ttk.Checkbutton(random_box, text="Случайная A слева", variable=self.rand_aL_var)
        check.grid(row=0, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=0, column=1, label="Вероятность", variable=self.rand_aL_p_var, width=8),
                _add_entry(random_box, row=0, column=3, label="Мин", variable=self.rand_aL_lo_var, width=8),
                _add_entry(random_box, row=0, column=5, label="Макс", variable=self.rand_aL_hi_var, width=8),
            ]
        )

        check = ttk.Checkbutton(random_box, text="Случайная A справа", variable=self.rand_aR_var)
        check.grid(row=1, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=1, column=1, label="Вероятность", variable=self.rand_aR_p_var, width=8),
                _add_entry(random_box, row=1, column=3, label="Мин", variable=self.rand_aR_lo_var, width=8),
                _add_entry(random_box, row=1, column=5, label="Макс", variable=self.rand_aR_hi_var, width=8),
            ]
        )

        check = ttk.Checkbutton(random_box, text="Случайная длина волны слева", variable=self.rand_lL_var)
        check.grid(row=2, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=2, column=1, label="Вероятность", variable=self.rand_lL_p_var, width=8),
                _add_entry(random_box, row=2, column=3, label="Мин", variable=self.rand_lL_lo_var, width=8),
                _add_entry(random_box, row=2, column=5, label="Макс", variable=self.rand_lL_hi_var, width=8),
            ]
        )

        check = ttk.Checkbutton(random_box, text="Случайная длина волны справа", variable=self.rand_lR_var)
        check.grid(row=3, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=3, column=1, label="Вероятность", variable=self.rand_lR_p_var, width=8),
                _add_entry(random_box, row=3, column=3, label="Мин", variable=self.rand_lR_lo_var, width=8),
                _add_entry(random_box, row=3, column=5, label="Макс", variable=self.rand_lR_hi_var, width=8),
            ]
        )

        check = ttk.Checkbutton(random_box, text="Случайная фаза слева", variable=self.rand_pL_var)
        check.grid(row=4, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=4, column=1, label="Вероятность", variable=self.rand_pL_p_var, width=8),
                _add_entry(random_box, row=4, column=3, label="Мин", variable=self.rand_pL_lo_var, width=8),
                _add_entry(random_box, row=4, column=5, label="Макс", variable=self.rand_pL_hi_var, width=8),
            ]
        )

        check = ttk.Checkbutton(random_box, text="Случайная фаза справа", variable=self.rand_pR_var)
        check.grid(row=5, column=0, sticky="w", pady=2)
        self.sine_widgets.append(check)
        self.sine_widgets.extend(
            [
                _add_entry(random_box, row=5, column=1, label="Вероятность", variable=self.rand_pR_p_var, width=8),
                _add_entry(random_box, row=5, column=3, label="Мин", variable=self.rand_pR_lo_var, width=8),
                _add_entry(random_box, row=5, column=5, label="Макс", variable=self.rand_pR_hi_var, width=8),
            ]
        )

        preview_box = ttk.LabelFrame(self, text="Профиль дороги", padding=8)
        preview_box.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=(10, 0))
        preview_box.columnconfigure(0, weight=1)
        preview_box.rowconfigure(2, weight=1)

        self.profile_title_var = tk.StringVar(value="Профиль дороги появится после сборки кольца без ошибок.")
        self.profile_stats_var = tk.StringVar(value="Линии Л/П покажут общий профиль кольца и выбранный сегмент.")
        self.profile_hint_var = tk.StringVar(
            value="Сверху будет весь круг, снизу — локальный профиль выбранного сегмента. Высота всегда в мм."
        )
        ttk.Label(preview_box, textvariable=self.profile_title_var, justify="left", wraplength=860).grid(
            row=0,
            column=0,
            sticky="ew",
        )
        ttk.Label(preview_box, textvariable=self.profile_stats_var, justify="left", wraplength=860).grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(4, 8),
        )
        self.profile_canvas = tk.Canvas(preview_box, height=300, background="#0f172a", highlightthickness=0)
        self.profile_canvas.grid(row=2, column=0, sticky="nsew")
        self.profile_canvas.bind("<Configure>", lambda _event: self._redraw_profile())
        ttk.Label(preview_box, textvariable=self.profile_hint_var, justify="left", wraplength=860).grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(8, 0),
        )

        self._diagnostics: RingEditorDiagnostics | None = None
        self._selected_index = 0

        self.update_mode_visibility("ISO8608")

    def set_boundary_editability(self, *, start_editable: bool, end_editable: bool) -> None:
        _set_widget_state(self.center_start_entry, "normal" if start_editable else "disabled")
        _set_widget_state(self.cross_start_entry, "normal" if start_editable else "disabled")
        _set_widget_state(self.center_end_entry, "normal" if end_editable else "disabled")
        _set_widget_state(self.cross_end_entry, "normal" if end_editable else "disabled")

    def update_mode_visibility(self, mode: str) -> None:
        normalized = str(mode or "ISO8608").upper().replace(" ", "")
        if normalized == "SINE" or "СИНУС" in normalized:
            _set_many_states(self.iso_widgets, "disabled")
            _set_many_states(self.sine_widgets, "normal")
        else:
            _set_many_states(self.iso_widgets, "normal")
            _set_widget_state(self.iso_combo, "readonly")
            _set_widget_state(self.gd_combo, "readonly")
            _set_many_states(self.sine_widgets, "disabled")
        _set_widget_state(self.mode_combo, "readonly")

    def render(self, diagnostics: RingEditorDiagnostics, selected_index: int) -> None:
        self._diagnostics = diagnostics
        self._selected_index = int(selected_index)
        row = self._selected_row(diagnostics, selected_index)
        road_mode = str((row or {}).get("road_mode") or self.mode_var.get() or "ISO8608").upper()
        name = str((row or {}).get("name") or f"S{int(selected_index) + 1}")
        self.profile_title_var.set(f"Профиль дороги: {name} | режим {road_mode}")
        if row is None:
            self.profile_stats_var.set("Выберите сегмент, чтобы увидеть локальный профиль и его метрики.")
        else:
            left_amp = _format_float_or_dash(row.get("L_amp_mm"), digits=1)
            right_amp = _format_float_or_dash(row.get("R_amp_mm"), digits=1)
            left_p2p = _format_float_or_dash(row.get("L_p2p_mm"), digits=1)
            right_p2p = _format_float_or_dash(row.get("R_p2p_mm"), digits=1)
            length_m = _format_float_or_dash(row.get("length_m"), digits=2)
            self.profile_stats_var.set(
                "Профиль кольца L/R: "
                f"A {float(diagnostics.metrics.get('ring_amp_left_mm', 0.0) or 0.0):.1f}/"
                f"{float(diagnostics.metrics.get('ring_amp_right_mm', 0.0) or 0.0):.1f} мм, "
                f"p-p {float(diagnostics.metrics.get('ring_p2p_left_mm', 0.0) or 0.0):.1f}/"
                f"{float(diagnostics.metrics.get('ring_p2p_right_mm', 0.0) or 0.0):.1f} мм. "
                f"Выбранный сегмент: L={length_m} м, локально A {left_amp}/{right_amp} мм, "
                f"локально p-p {left_p2p}/{right_p2p} мм."
            )
        if diagnostics.road_profile is None:
            if diagnostics.errors:
                self.profile_hint_var.set("Профиль дороги не собран: сначала исправьте ошибки сценария.")
            else:
                self.profile_hint_var.set("Профиль дороги временно недоступен для текущей конфигурации.")
        else:
            self.profile_hint_var.set(
                "Сверху показан весь круг с подсветкой выбранного сегмента, снизу — увеличенный локальный профиль. "
                "Синий — левый след, оранжевый — правый след, шкала по высоте всегда в мм."
            )
        self._redraw_profile()

    def _selected_row(self, diagnostics: RingEditorDiagnostics, selected_index: int) -> dict[str, object] | None:
        if not (0 <= int(selected_index) < len(diagnostics.segment_rows)):
            return None
        row = diagnostics.segment_rows[int(selected_index)]
        return row if isinstance(row, dict) else None

    def _slice_profile_for_selected_segment(
        self,
        diagnostics: RingEditorDiagnostics,
    ) -> tuple[list[float], list[float], list[float]]:
        profile = diagnostics.road_profile
        if profile is None:
            return [], [], []
        row = self._selected_row(diagnostics, self._selected_index)
        x_values = [float(value) for value in profile.x_m]
        left_values = [float(value) for value in profile.left_mm]
        right_values = [float(value) for value in profile.right_mm]
        if row is None:
            return x_values, left_values, right_values
        x0 = float(row.get("x_start_m", x_values[0] if x_values else 0.0) or 0.0)
        x1 = float(row.get("x_end_m", x_values[-1] if x_values else 0.0) or 0.0)
        picked = [
            (x, left, right)
            for x, left, right in zip(x_values, left_values, right_values)
            if x0 <= x <= x1
        ]
        if len(picked) < 2 and x_values:
            picked = [
                (x, left, right)
                for x, left, right in zip(x_values, left_values, right_values)
                if (x0 - 0.2) <= x <= (x1 + 0.2)
            ]
        if not picked:
            return x_values, left_values, right_values
        local_x0 = float(picked[0][0])
        return (
            [float(x - local_x0) for x, _, _ in picked],
            [float(left) for _, left, _ in picked],
            [float(right) for _, _, right in picked],
        )

    def _redraw_profile(self) -> None:
        canvas = self.profile_canvas
        canvas.delete("all")
        diagnostics = self._diagnostics
        width = max(120, int(canvas.winfo_width() or 0))
        height = max(120, int(canvas.winfo_height() or 0))
        if diagnostics is None or diagnostics.road_profile is None:
            canvas.create_text(
                width / 2.0,
                height / 2.0,
                text="Профиль дороги\nещё не собран",
                fill="#e2e8f0",
                font=("Segoe UI", 14, "bold"),
                justify="center",
            )
            return

        whole_top = 26.0
        region_height = max(76.0, (height - 72.0) / 2.0)
        local_top = whole_top + region_height + 22.0
        self._draw_profile_region(
            x_values=[float(value) for value in diagnostics.road_profile.x_m],
            left_values=[float(value) for value in diagnostics.road_profile.left_mm],
            right_values=[float(value) for value in diagnostics.road_profile.right_mm],
            top=whole_top,
            height=region_height,
            title="Профиль кольца",
            selected_row=self._selected_row(diagnostics, self._selected_index),
        )
        local_x, local_left, local_right = self._slice_profile_for_selected_segment(diagnostics)
        local_row = self._selected_row(diagnostics, self._selected_index)
        local_name = str((local_row or {}).get("name") or f"S{int(self._selected_index) + 1}")
        self._draw_profile_region(
            x_values=local_x,
            left_values=local_left,
            right_values=local_right,
            top=local_top,
            height=region_height,
            title=f"Выбранный сегмент: {local_name}",
            selected_row=None,
        )
        canvas.create_text(
            width - 18,
            12,
            text="мм",
            fill="#cbd5e1",
            anchor="e",
            font=("Segoe UI", 9, "bold"),
        )
        canvas.create_rectangle(20, 10, 32, 18, fill="#38bdf8", outline="")
        canvas.create_text(38, 14, text="Левый след", fill="#cbd5e1", anchor="w", font=("Segoe UI", 9))
        canvas.create_rectangle(120, 10, 132, 18, fill="#f97316", outline="")
        canvas.create_text(138, 14, text="Правый след", fill="#cbd5e1", anchor="w", font=("Segoe UI", 9))

    def _draw_profile_region(
        self,
        *,
        x_values: list[float],
        left_values: list[float],
        right_values: list[float],
        top: float,
        height: float,
        title: str,
        selected_row: dict[str, object] | None,
    ) -> None:
        canvas = self.profile_canvas
        width = max(120, int(canvas.winfo_width() or 0))
        left_pad = 58.0
        right_pad = 20.0
        bottom = top + height
        canvas.create_rectangle(left_pad, top, width - right_pad, bottom, outline="#334155", width=1)
        canvas.create_text(left_pad, top - 8, text=title, fill="#e2e8f0", anchor="w", font=("Segoe UI", 10, "bold"))
        if len(x_values) < 2 or len(left_values) != len(x_values) or len(right_values) != len(x_values):
            canvas.create_text(
                (left_pad + width - right_pad) / 2.0,
                top + height / 2.0,
                text="Нет данных профиля",
                fill="#94a3b8",
                font=("Segoe UI", 10),
            )
            return

        x_min = float(min(x_values))
        x_max = float(max(x_values))
        x_span = max(1e-9, x_max - x_min)
        max_abs = max(max(abs(value) for value in left_values), max(abs(value) for value in right_values), 1.0)
        mid_y = top + height / 2.0
        scale_y = (height * 0.38) / max_abs

        canvas.create_line(left_pad, mid_y, width - right_pad, mid_y, fill="#475569", dash=(4, 4))
        canvas.create_text(left_pad - 8, top + 8, text=f"+{max_abs:.0f}", fill="#94a3b8", anchor="e", font=("Segoe UI", 8))
        canvas.create_text(left_pad - 8, bottom - 8, text=f"-{max_abs:.0f}", fill="#94a3b8", anchor="e", font=("Segoe UI", 8))
        canvas.create_text(left_pad - 8, mid_y, text="0", fill="#94a3b8", anchor="e", font=("Segoe UI", 8))
        canvas.create_text(width - right_pad, bottom + 12, text=f"{x_span:.2f} м", fill="#94a3b8", anchor="e", font=("Segoe UI", 8))

        if selected_row is not None:
            x0 = float(selected_row.get("x_start_m", x_min) or x_min)
            x1 = float(selected_row.get("x_end_m", x_max) or x_max)
            sx0 = left_pad + ((x0 - x_min) / x_span) * (width - right_pad - left_pad)
            sx1 = left_pad + ((x1 - x_min) / x_span) * (width - right_pad - left_pad)
            if sx1 > sx0:
                canvas.create_rectangle(sx0, top + 1, sx1, bottom - 1, fill="#1d4ed8", stipple="gray25", outline="")

        def _coords(values_x: list[float], values_y: list[float]) -> list[float]:
            out: list[float] = []
            for current_x, current_y in zip(values_x, values_y):
                px = left_pad + ((float(current_x) - x_min) / x_span) * (width - right_pad - left_pad)
                py = mid_y - float(current_y) * scale_y
                out.extend((px, py))
            return out

        left_coords = _coords(x_values, left_values)
        right_coords = _coords(x_values, right_values)
        if len(left_coords) >= 4:
            canvas.create_line(*left_coords, fill="#38bdf8", width=2, smooth=True)
        if len(right_coords) >= 4:
            canvas.create_line(*right_coords, fill="#f97316", width=2, smooth=True)


class EventsPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc, *, on_select: callable, on_add: callable, on_update: callable, on_delete: callable) -> None:
        super().__init__(parent, padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        columns = ("kind", "side", "start", "length", "depth", "ramp")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=8)
        headers = {
            "kind": "Тип",
            "side": "Сторона",
            "start": "Старт, м",
            "length": "Длина, м",
            "depth": "Глубина, мм",
            "ramp": "Сход, м",
        }
        widths = {"kind": 90, "side": 80, "start": 80, "length": 80, "depth": 90, "ramp": 80}
        for key in columns:
            self.tree.heading(key, text=headers[key])
            self.tree.column(key, width=widths[key], anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        x_scroll.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: on_select())

        form = ttk.LabelFrame(self, text="Редактор событий", padding=8)
        form.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for col in (1, 3, 5):
            form.columnconfigure(col, weight=1)

        self.kind_var = tk.StringVar(value="яма")
        self.side_var = tk.StringVar(value="Левый")
        self.start_var = tk.StringVar(value="0.0")
        self.length_var = tk.StringVar(value="0.4")
        self.depth_var = tk.StringVar(value="-25.0")
        self.ramp_var = tk.StringVar(value="0.1")

        ttk.Label(form, text="Тип").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        self.kind_combo = ttk.Combobox(form, textvariable=self.kind_var, values=("яма", "препятствие"), state="readonly", width=14)
        self.kind_combo.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=3)
        ttk.Label(form, text="Сторона").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=3)
        self.side_combo = ttk.Combobox(form, textvariable=self.side_var, values=("Левый", "Правый", "Оба"), state="readonly", width=12)
        self.side_combo.grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=3)
        _add_entry(form, row=0, column=4, label="Начало, м", variable=self.start_var)
        _add_entry(form, row=1, column=0, label="Длина, м", variable=self.length_var)
        _add_entry(form, row=1, column=2, label="Глубина, мм", variable=self.depth_var)
        _add_entry(form, row=1, column=4, label="Сход, м", variable=self.ramp_var)

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
                    _event_side_label(event.get("side", "")),
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

        self.summary_var = tk.StringVar(value="Диагностика ещё не собрана.")
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

        table_frame = ttk.LabelFrame(self, text="Диагностика сегментов", padding=6)
        table_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(1, weight=1)

        ttk.Label(
            table_frame,
            text=(
                "Сводка ниже специально разделяет амплитуду A (полуразмах) и полный размах max-min. "
                "Сводка ниже специально разделяет амплитуду (A) и полный размах профиля. "
                "Для синусоиды полный размах равен удвоенной амплитуде, поэтому эти величины нельзя смешивать."
            ),
            justify="left",
            wraplength=860,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        columns = ("seg", "name", "turn", "v0", "v1", "len", "road", "events", "l_a", "l_p2p", "r_a", "r_p2p")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
        headers = {
            "seg": "#",
            "name": "Сегмент",
            "turn": "Поворот",
            "v0": "Старт, км/ч",
            "v1": "Финиш, км/ч",
            "len": "Длина, м",
            "road": "Профиль",
            "events": "События",
            "l_a": "Амплитуда слева, мм",
            "l_p2p": "Размах слева, мм",
            "r_a": "Амплитуда справа, мм",
            "r_p2p": "Размах справа, мм",
        }
        widths = {
            "seg": 48,
            "name": 180,
            "turn": 96,
            "v0": 96,
            "v1": 96,
            "len": 82,
            "road": 88,
            "events": 62,
            "l_a": 122,
            "l_p2p": 122,
            "r_a": 122,
            "r_p2p": 122,
        }
        for key in columns:
            self.tree.heading(key, text=headers[key])
            self.tree.column(key, width=widths[key], anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew")
        table_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        table_scroll.grid(row=1, column=1, sticky="ns")
        table_x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        table_x_scroll.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.tree.configure(yscrollcommand=table_scroll.set, xscrollcommand=table_x_scroll.set)

        opt_frame = ttk.LabelFrame(self, text="Окна оптимизации", padding=6)
        opt_frame.grid(row=5, column=0, sticky="nsew", pady=(8, 0))
        opt_frame.columnconfigure(0, weight=1)
        opt_frame.rowconfigure(1, weight=1)

        self.opt_summary_var = tk.StringVar(value="Набор оптимизации ещё не подготовлен.")
        ttk.Label(opt_frame, textvariable=self.opt_summary_var, justify="left", wraplength=880).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        opt_columns = ("id", "label", "t0", "t1", "dt", "peak", "segments")
        self.opt_tree = ttk.Treeview(opt_frame, columns=opt_columns, show="headings", height=6)
        opt_headers = {
            "id": "Фрагмент",
            "label": "Описание",
            "t0": "Начало, с",
            "t1": "Конец, с",
            "dt": "Длительность, с",
            "peak": "Пик",
            "segments": "Сегменты",
        }
        opt_widths = {"id": 120, "label": 190, "t0": 90, "t1": 90, "dt": 110, "peak": 90, "segments": 300}
        for key in opt_columns:
            self.opt_tree.heading(key, text=opt_headers[key])
            self.opt_tree.column(key, width=opt_widths[key], anchor="center")
        self.opt_tree.grid(row=1, column=0, sticky="nsew")
        opt_scroll = ttk.Scrollbar(opt_frame, orient="vertical", command=self.opt_tree.yview)
        opt_scroll.grid(row=1, column=1, sticky="ns")
        opt_x_scroll = ttk.Scrollbar(opt_frame, orient="horizontal", command=self.opt_tree.xview)
        opt_x_scroll.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.opt_tree.configure(yscrollcommand=opt_scroll.set, xscrollcommand=opt_x_scroll.set)

        opt_suite_frame = ttk.LabelFrame(self, text="Строки набора оптимизации", padding=6)
        opt_suite_frame.grid(row=7, column=0, sticky="nsew", pady=(8, 0))
        opt_suite_frame.columnconfigure(0, weight=1)
        opt_suite_frame.rowconfigure(0, weight=1)

        opt_suite_columns = ("stage", "name", "kind", "label")
        self.opt_suite_tree = ttk.Treeview(opt_suite_frame, columns=opt_suite_columns, show="headings", height=6)
        opt_suite_headers = {
            "stage": "Стадия",
            "name": "Имя",
            "kind": "Тип",
            "label": "Описание",
        }
        opt_suite_widths = {"stage": 80, "name": 220, "kind": 160, "label": 260}
        for key in opt_suite_columns:
            self.opt_suite_tree.heading(key, text=opt_suite_headers[key])
            self.opt_suite_tree.column(key, width=opt_suite_widths[key], anchor="center")
        self.opt_suite_tree.grid(row=0, column=0, sticky="nsew")
        opt_suite_scroll = ttk.Scrollbar(opt_suite_frame, orient="vertical", command=self.opt_suite_tree.yview)
        opt_suite_scroll.grid(row=0, column=1, sticky="ns")
        opt_suite_x_scroll = ttk.Scrollbar(opt_suite_frame, orient="horizontal", command=self.opt_suite_tree.xview)
        opt_suite_x_scroll.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.opt_suite_tree.configure(yscrollcommand=opt_suite_scroll.set, xscrollcommand=opt_suite_x_scroll.set)

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
                    _turn_label(row.get("turn_direction", "")),
                    f"{float(row.get('speed_start_kph', 0.0) or 0.0):.1f}",
                    f"{float(row.get('speed_end_kph', 0.0) or 0.0):.1f}",
                    f"{float(row.get('length_m', 0.0) or 0.0):.2f}",
                    _road_mode_label(row.get("road_mode", "")),
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
                    _humanize_opt_text(row.get("id", "")),
                    _humanize_opt_text(row.get("label", "")),
                    f"{float(row.get('t_start_s', 0.0) or 0.0):.2f}",
                    f"{float(row.get('t_end_s', 0.0) or 0.0):.2f}",
                    f"{float(row.get('duration_s', 0.0) or 0.0):.2f}",
                    f"{float(row.get('peak_value', 0.0) or 0.0):.3f}",
                    row.get("segments_text", ""),
                ),
            )

    def set_opt_fragment_summary(self, text: str) -> None:
        self.opt_summary_var.set(_humanize_opt_summary_text(text))

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
                    _humanize_opt_text(row.get("name", "")),
                    _opt_kind_label(row.get("kind", "")),
                    _humanize_opt_text(row.get("label", "")),
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
        on_open_last_meta: callable,
        on_open_ring_source: callable,
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

        ttk.Label(top, text="Каталог выгрузки").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(top, textvariable=self.output_dir_var).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Button(top, text="Выбрать", command=on_choose_dir).grid(row=0, column=2, sticky="ew", padx=(8, 0), pady=3)

        ttk.Label(top, text="Тег файлов").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(top, textvariable=self.tag_var, width=20).grid(row=1, column=1, sticky="w", pady=3)

        opt_box = ttk.LabelFrame(self, text="Передача в оптимизацию", padding=8)
        opt_box.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        opt_box.columnconfigure(1, weight=1)

        self.opt_workspace_var = tk.StringVar()
        self.opt_window_var = tk.StringVar(value="4.0")
        self.inputs_handoff_var = tk.StringVar(
            value=(
                "HO-002 inputs_snapshot ещё не проверен. "
                "WS-RING читает только frozen ref/hash из WS-INPUTS."
            )
        )

        inputs_box = ttk.LabelFrame(self, text="Inputs handoff / HO-002", padding=8)
        inputs_box.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        inputs_box.columnconfigure(0, weight=1)
        ttk.Label(
            inputs_box,
            textvariable=self.inputs_handoff_var,
            wraplength=880,
            justify="left",
            foreground="#334455",
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(opt_box, text="Каталог оптимизации").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(opt_box, textvariable=self.opt_workspace_var).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Button(opt_box, text="Выбрать", command=on_choose_opt_workspace).grid(row=0, column=2, sticky="ew", padx=(8, 0), pady=3)
        ttk.Label(opt_box, text="Окно фрагмента, с").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(opt_box, textvariable=self.opt_window_var, width=12).grid(row=1, column=1, sticky="w", pady=3)
        opt_actions = ttk.Frame(opt_box)
        opt_actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        opt_actions.columnconfigure((0, 1), weight=1)
        ttk.Button(opt_actions, text="Открыть каталог оптимизации", command=on_open_opt_workspace).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(opt_actions, text="Открыть последний набор", command=on_open_opt_suite).grid(row=0, column=1, sticky="ew")

        artifact_box = ttk.LabelFrame(self, text="Последние артефакты", padding=8)
        artifact_box.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        artifact_box.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        ttk.Button(artifact_box, text="Открыть последний сценарий", command=on_open_last_spec).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(artifact_box, text="Открыть последнюю дорогу", command=on_open_last_road).grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ttk.Button(artifact_box, text="Открыть последний файл ускорений", command=on_open_last_axay).grid(row=0, column=2, sticky="ew", padx=(0, 4))
        ttk.Button(artifact_box, text="Открыть meta HO-004", command=on_open_last_meta).grid(row=0, column=3, sticky="ew", padx=(0, 4))
        ttk.Button(artifact_box, text="Открыть source WS-RING", command=on_open_ring_source).grid(row=0, column=4, sticky="ew", padx=(0, 4))
        ttk.Button(artifact_box, text="Открыть папку для анимации", command=on_open_anim_latest).grid(row=0, column=5, sticky="ew")

        buttons = ttk.Frame(self)
        buttons.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        buttons.columnconfigure((0, 1, 2, 3, 4), weight=1)
        ttk.Button(buttons, text="Загрузить сценарий", command=on_load_spec).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Сохранить сценарий", command=on_save_spec).grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Собрать файлы сценария", command=on_generate_bundle).grid(row=0, column=2, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Построить набор оптимизации", command=on_build_auto_suite).grid(row=0, column=3, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Открыть каталог выгрузки", command=on_open_output).grid(row=0, column=4, sticky="ew")

        ttk.Label(self, textvariable=self.last_export_var, wraplength=880, justify="left").grid(row=5, column=0, sticky="ew", pady=(10, 0))
