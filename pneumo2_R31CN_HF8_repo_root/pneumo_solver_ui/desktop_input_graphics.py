from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk
from pathlib import Path


class DesktopInputGraphicPanel(ttk.LabelFrame):
    """Compact engineering view for the input editor.

    The panel keeps a stable CAD-like layout instead of section-specific
    decorative cards. It follows the same core geometry contract that the
    desktop animator expects: wheelbase, track, frame, wheel radius, stroke
    and CG-related inputs.
    """

    CANVAS_WIDTH = 680
    CANVAS_HEIGHT = 380
    SCHEME_X0 = 16
    SCHEME_Y0 = 64
    SCHEME_X1 = 410
    SCHEME_Y1 = 280
    METRICS_X0 = 432
    METRICS_Y0 = 64
    METRICS_X1 = CANVAS_WIDTH - 16
    METRICS_Y1 = CANVAS_HEIGHT - 24
    _MECH_SCHEME_PATH = Path(__file__).resolve().parent / "assets" / "mech_scheme.png"
    _PNEUMO_SCHEME_PATH = Path(__file__).resolve().parents[1] / "tmp_pneumo_scheme_render.png"

    CONTEXT_TITLES: dict[str, str] = {
        "frame_dimensions": "Габариты рамы",
        "track": "Колея",
        "cg_height": "Высота центра масс",
        "wheel": "Колесо",
        "stroke": "Ход штока",
        "pressure": "Давления в контурах",
        "volume": "Объёмы воздуха",
        "piston": "Поршни",
        "rod": "Штоки",
        "mass_sprung": "Подрессоренная масса",
        "mass_unsprung": "Неподрессоренная масса",
        "tyre_stiffness": "Жёсткость шины",
        "tyre_damping": "Демпфирование шины",
        "spring": "Пружина",
        "stabilizer": "Стабилизаторы",
        "speed": "Начальная скорость",
        "cg_plan": "Положение центра масс",
        "load_distribution": "Распределение массы",
        "trim_mode": "Режим посадки",
        "trim_target": "Целевое положение по ходу",
        "kinematics": "Кинематика",
        "compatibility": "Совместимость",
        "spring_link": "Привязка пружины",
        "gas_model": "Газовая модель",
        "temperature": "Температура",
        "integration": "Интегрирование",
        "checks": "Проверки",
        "reference_limits": "Справочные лимиты",
    }

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Инженерная схема", padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.summary_var = tk.StringVar(master=self, value="Выберите параметр или раздел.")
        self.source_marker_var = tk.StringVar(
            master=self,
            value="источник: текущие исходные данные · состояние: актуально · режим: По исходным данным",
        )
        ttk.Label(
            self,
            textvariable=self.summary_var,
            wraplength=520,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Label(
            self,
            textvariable=self.source_marker_var,
            wraplength=520,
            justify="left",
            foreground="#5b6770",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.canvas = tk.Canvas(
            self,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            background="#f7f8fa",
            highlightthickness=1,
            highlightbackground="#d6dbe1",
        )
        self.canvas.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        self._scheme_images: dict[str, tk.PhotoImage | None] = {
            "mech": self._load_scheme_image(self._MECH_SCHEME_PATH, max_width=340, max_height=190),
            "pneumo": self._load_scheme_image(self._PNEUMO_SCHEME_PATH, max_width=340, max_height=190),
        }

    def refresh(
        self,
        *,
        section_title: str,
        payload: dict[str, object],
        field_label: str = "",
        unit_label: str = "",
        field_key: str = "",
        graphic_context: str = "",
        source_marker: str = "",
    ) -> None:
        self.canvas.delete("all")
        active_context = self._resolve_active_context(
            section_title=section_title,
            field_key=field_key,
            field_label=field_label,
            graphic_context=graphic_context,
        )
        geom = self._geometry_from_payload(payload)
        self.summary_var.set(self._build_summary(section_title, field_label, unit_label, active_context))
        marker = self._operator_source_marker(source_marker)
        self.source_marker_var.set(f"{marker} · режим: По исходным данным")
        self._draw_reference_scheme(section_title, field_label, active_context, geom)
        self._draw_metrics(section_title, payload, geom, active_context, unit_label)

    @staticmethod
    def _operator_source_marker(source_marker: str | None) -> str:
        raw = str(source_marker or "").strip()
        if not raw:
            return "источник: исходный шаблон · состояние: актуально"

        legacy_source_prefix = "source" + ":"
        legacy_state_prefix = "state" + ":"
        legacy_default = "default_base" + ".json"
        source_label = ""
        state_label = ""
        passthrough: list[str] = []
        for part in raw.split("·"):
            item = part.strip()
            lowered = item.lower()
            if lowered.startswith(legacy_source_prefix):
                source_value = item.split(":", 1)[1].strip()
                source_label = "исходный шаблон" if source_value == legacy_default else source_value
            elif lowered.startswith(legacy_state_prefix):
                state_value = item.split(":", 1)[1].strip().lower()
                state_label = {
                    "current": "актуально",
                    "dirty": "изменено",
                    "stale": "устарело",
                    "invalid": "ошибка",
                }.get(state_value, state_value)
            elif "WS-INPUTS" not in item:
                passthrough.append(item)

        if source_label or state_label:
            normalized = []
            if source_label:
                normalized.append(f"источник: {source_label}")
            if state_label:
                normalized.append(f"состояние: {state_label}")
            normalized.extend(passthrough)
            return " · ".join(part for part in normalized if part)
        return raw

    def _load_scheme_image(
        self,
        path: Path,
        *,
        max_width: int,
        max_height: int,
    ) -> tk.PhotoImage | None:
        try:
            if not path.exists():
                return None
            image = tk.PhotoImage(master=self, file=str(path))
            width = max(1, int(image.width()))
            height = max(1, int(image.height()))
            factor = max(1, int(math.ceil(max(width / max_width, height / max_height))))
            return image.subsample(factor, factor)
        except Exception:
            return None

    def _scheme_image_for_section(self, section_title: str) -> tk.PhotoImage | None:
        if str(section_title or "").strip() == "Пневматика":
            return self._scheme_images.get("pneumo") or self._scheme_images.get("mech")
        return self._scheme_images.get("mech")

    def _draw_reference_scheme(
        self,
        section_title: str,
        field_label: str,
        active_context: str,
        geom: dict[str, float],
    ) -> None:
        self.canvas.create_rectangle(10, 10, self.CANVAS_WIDTH - 10, self.CANVAS_HEIGHT - 10, outline="#e1e6ec", width=1)
        panel_title = "Пневмосхема проекта" if str(section_title or "").strip() == "Пневматика" else "Схема подвески проекта"
        self.canvas.create_text(18, 20, anchor="w", text=panel_title, font=("Segoe UI", 9, "bold"))
        context_title = self._context_title(active_context) or str(field_label or "").strip() or str(section_title or "").strip()
        self.canvas.create_text(18, 38, anchor="w", text=f"Показано: {context_title}", font=("Segoe UI", 8), fill="#355070")

        scheme_x0 = self.SCHEME_X0
        scheme_y0 = self.SCHEME_Y0
        scheme_x1 = self.SCHEME_X1
        scheme_y1 = self.SCHEME_Y1
        metrics_x0 = self.METRICS_X0
        metrics_y0 = self.METRICS_Y0
        metrics_x1 = self.METRICS_X1
        metrics_y1 = self.METRICS_Y1
        self.canvas.create_rectangle(scheme_x0, scheme_y0, scheme_x1, scheme_y1, outline="#d6dbe1", fill="#ffffff")
        self.canvas.create_rectangle(metrics_x0, metrics_y0, metrics_x1, metrics_y1, outline="#d6dbe1", fill="#fbfcfd")
        self.canvas.create_line(metrics_x0 - 10, scheme_y0, metrics_x0 - 10, metrics_y1, fill="#eef2f6")
        image = self._scheme_image_for_section(section_title)
        if image is not None:
            self.canvas.create_image(
                (scheme_x0 + scheme_x1) / 2,
                (scheme_y0 + scheme_y1) / 2,
                image=image,
            )
        self.canvas.create_rectangle(scheme_x0 + 4, scheme_y0 + 4, scheme_x1 - 4, scheme_y1 - 4, outline="", fill="#ffffff")
        if str(section_title or "").strip() == "Пневматика":
            self._draw_pneumatic_overlay(scheme_x0, scheme_y0, scheme_x1, scheme_y1, active_context)
        else:
            self._draw_suspension_overlay(scheme_x0, scheme_y0, scheme_x1, scheme_y1, geom, active_context)

        dimension_y = scheme_y1 + 20
        self.canvas.create_line(scheme_x0 + 18, dimension_y, scheme_x1 - 18, dimension_y, fill="#718096", arrow=tk.BOTH)
        self.canvas.create_text(
            (scheme_x0 + scheme_x1) / 2,
            dimension_y + 13,
            text=f"База {geom['wheelbase']:.2f} м",
            font=("Segoe UI", 8),
            fill="#264653",
        )
        self.canvas.create_line(scheme_x1 - 20, scheme_y0 + 24, scheme_x1 - 20, scheme_y1 - 24, fill="#718096", arrow=tk.BOTH)
        self.canvas.create_text(
            scheme_x1 - 36,
            (scheme_y0 + scheme_y1) / 2,
            text=f"Колея {geom['track']:.2f} м",
            angle=90,
            font=("Segoe UI", 8),
            fill="#264653",
        )

    def _draw_suspension_overlay(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        geom: dict[str, float],
        active_context: str,
    ) -> None:
        frame_left = x0 + 82
        frame_right = x1 - 82
        frame_top = y0 + 54
        frame_bottom = y1 - 58
        frame_color = self._stroke_color(active_context, "frame_dimensions", "track", "cg_height")
        wheel_color = self._stroke_color(active_context, "wheel", "track")
        cyl_color = self._stroke_color(active_context, "stroke", "trim_target")
        self.canvas.create_rectangle(
            frame_left,
            frame_top,
            frame_right,
            frame_bottom,
            outline=frame_color,
            width=4,
            fill="#edf4fb",
        )
        wheel_w = 46
        wheel_h = 38
        wheel_positions = (
            (x0 + 30, frame_top - 8),
            (x1 - 76, frame_top - 8),
            (x0 + 30, frame_bottom - wheel_h + 8),
            (x1 - 76, frame_bottom - wheel_h + 8),
        )
        for wx, wy in wheel_positions:
            self.canvas.create_rectangle(wx, wy, wx + wheel_w, wy + wheel_h, outline=wheel_color, width=3, fill="#dbe6f2")
            self.canvas.create_line(wx + wheel_w / 2, wy + wheel_h, wx + wheel_w / 2, frame_bottom + 18, fill=cyl_color, width=3)
        cg_x = (frame_left + frame_right) / 2
        cg_y = frame_top + (frame_bottom - frame_top) * 0.46
        self.canvas.create_oval(cg_x - 9, cg_y - 9, cg_x + 9, cg_y + 9, fill="#d62828", outline="#9b1d20")
        self.canvas.create_text(cg_x + 14, cg_y - 2, anchor="w", text="ЦМ", font=("Segoe UI", 9, "bold"), fill="#9b1d20")
        self.canvas.create_text(
            x0 + 16,
            y0 + 18,
            anchor="w",
            text=f"Рама {geom['frame_length']:.2f} x {geom['frame_width']:.2f} м",
            font=("Segoe UI", 9, "bold"),
            fill="#264653",
        )
        self.canvas.create_text(
            x0 + 16,
            y1 - 22,
            anchor="w",
            text=f"Ход штока {geom['stroke']:.2f} м · колесо R {geom['wheel_radius']:.2f} м",
            font=("Segoe UI", 9),
            fill="#355070",
        )

    def _draw_pneumatic_overlay(self, x0: int, y0: int, x1: int, y1: int, active_context: str) -> None:
        line_color = self._stroke_color(active_context, "pressure", "volume", "piston", "rod")
        accent = self._stroke_color(active_context, "pressure")
        top_y = y0 + 50
        mid_y = y0 + 110
        bottom_y = y0 + 170
        left_x = x0 + 48
        right_x = x1 - 48
        center_x = (x0 + x1) / 2
        self.canvas.create_line(left_x, mid_y, right_x, mid_y, fill=line_color, width=4)
        self.canvas.create_line(center_x, top_y, center_x, bottom_y, fill=line_color, width=4)
        for idx, (cx, cy, label) in enumerate(
            (
                (left_x + 28, top_y, "Р1"),
                (center_x, top_y, "Р2"),
                (right_x - 28, top_y, "Р3"),
                (left_x + 28, bottom_y, "Ц1"),
                (center_x, bottom_y, "Ц2"),
                (right_x - 28, bottom_y, "Акк."),
            )
        ):
            fill = "#e7f1ff" if idx < 3 else "#f4f7fb"
            self.canvas.create_oval(cx - 28, cy - 20, cx + 28, cy + 20, outline=accent, width=3, fill=fill)
            self.canvas.create_text(cx, cy, text=label, font=("Segoe UI", 9, "bold"), fill="#264653")
            self.canvas.create_line(cx, cy + 20 if cy < mid_y else cy - 20, cx, mid_y, fill=line_color, width=3)
        self.canvas.create_text(
            x0 + 16,
            y0 + 18,
            anchor="w",
            text="Контуры, ресиверы и исполнительные цилиндры",
            font=("Segoe UI", 9, "bold"),
            fill="#264653",
        )
        self.canvas.create_text(
            x0 + 16,
            y1 - 22,
            anchor="w",
            text="Схема показывает связи; расчётные значения справа.",
            font=("Segoe UI", 9),
            fill="#355070",
        )

    def _build_summary(
        self,
        section_title: str,
        field_label: str,
        unit_label: str,
        active_context: str,
    ) -> str:
        focus = str(field_label or "").strip()
        context = self._context_title(active_context)
        if focus and unit_label:
            return f"{section_title}: {focus} [{unit_label}]"
        if focus:
            return f"{section_title}: {focus}"
        if context:
            return f"{section_title}: {context}"
        return f"{section_title}: рабочая схема и основные размеры"

    def _safe_float(self, payload: dict[str, object], key: str, default: float = 0.0) -> float:
        try:
            return float(payload.get(key, default) or default)
        except Exception:
            return float(default)

    def _resolve_active_context(
        self,
        *,
        section_title: str,
        field_key: str,
        field_label: str,
        graphic_context: str,
    ) -> str:
        clean_context = str(graphic_context or "").strip()
        if clean_context:
            return clean_context
        key = str(field_key or "").strip().lower()
        if "давлен" in key:
            return "pressure"
        if "объ" in key or "обьем" in key:
            return "volume"
        if "порш" in key:
            return "piston"
        if "шток" in key:
            return "stroke"
        if "колея" in key:
            return "track"
        if "база" in key or "рама" in key:
            return "frame_dimensions"
        if "масса" in key:
            return "mass_sprung"
        if "trim" in key or "ход" in key:
            return "trim_target"
        if "температур" in key:
            return "temperature"
        if "пружин" in key:
            return "spring"
        if str(section_title or "").strip() == "Пневматика":
            return "pressure"
        if str(section_title or "").strip() == "Массы":
            return "mass_sprung"
        if str(section_title or "").strip() == "Механика":
            return "spring"
        if str(section_title or "").strip() == "Статическая настройка":
            return "trim_target"
        if str(section_title or "").strip() == "Справочные данные":
            return "gas_model"
        if str(section_title or "").strip() in {"Численные настройки", "Расчётные настройки"}:
            return "integration"
        return ""

    def _context_title(self, context_key: str) -> str:
        return self.CONTEXT_TITLES.get(str(context_key or "").strip(), "")

    def _geometry_from_payload(self, payload: dict[str, object]) -> dict[str, float]:
        wheelbase = max(0.1, self._safe_float(payload, "база", 2.6))
        track = max(0.1, self._safe_float(payload, "колея", 1.65))
        frame_length = max(wheelbase * 1.05, self._safe_float(payload, "длина_рамы", wheelbase * 1.1))
        frame_width = max(track * 0.72, self._safe_float(payload, "ширина_рамы", track * 0.78))
        frame_height = max(0.08, self._safe_float(payload, "высота_рамы", 0.22))
        wheel_radius = max(0.08, self._safe_float(payload, "радиус_колеса_м", 0.33))
        wheel_width = max(0.06, self._safe_float(payload, "wheel_width_m", 0.22))
        stroke = max(0.02, self._safe_float(payload, "ход_штока", 0.18))
        cg_height = max(0.05, self._safe_float(payload, "высота_центра_масс", 0.58))
        trim_target = min(1.0, max(0.0, self._safe_float(payload, "zero_pose_target_stroke_frac", 0.55)))
        trim_tol = min(0.5, max(0.0, self._safe_float(payload, "zero_pose_tol_stroke_frac", 0.06)))
        return {
            "wheelbase": wheelbase,
            "track": track,
            "frame_length": frame_length,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "wheel_radius": wheel_radius,
            "wheel_width": wheel_width,
            "stroke": stroke,
            "cg_height": cg_height,
            "trim_target": trim_target,
            "trim_tol": trim_tol,
        }

    def _draw_workspace_guides(self) -> None:
        self.canvas.create_rectangle(10, 10, 410, 290, outline="#e1e6ec", width=1)
        self.canvas.create_line(210, 18, 210, 282, fill="#eef2f6")
        self.canvas.create_line(18, 152, 402, 152, fill="#eef2f6")

    def _draw_header(self, section_title: str, field_label: str, active_context: str) -> None:
        self.canvas.create_text(18, 22, anchor="w", text="Вид сверху", font=("Segoe UI", 9, "bold"))
        self.canvas.create_text(18, 160, anchor="w", text="Вид сбоку", font=("Segoe UI", 9, "bold"))
        right_title = self._context_title(active_context) or str(field_label or "").strip() or section_title
        self.canvas.create_text(256, 22, anchor="w", text=right_title, font=("Segoe UI", 9, "bold"), fill="#264653")

    def _stroke_color(self, active_context: str, *contexts: str) -> str:
        if active_context and active_context in contexts:
            return "#c85a17"
        return "#3d5875"

    def _draw_top_projection(self, geom: dict[str, float], active_context: str) -> None:
        x0, y0, x1, y1 = 22, 34, 198, 138
        frame_pad = 22
        wheel_pad = 8
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="#d8dde4", fill="#ffffff")
        frame_left = x0 + frame_pad
        frame_right = x1 - frame_pad
        frame_top = y0 + 26
        frame_bottom = y1 - 26
        self.canvas.create_rectangle(
            frame_left,
            frame_top,
            frame_right,
            frame_bottom,
            outline=self._stroke_color(active_context, "frame_dimensions", "track"),
            width=2,
            fill="#edf4fb",
        )
        wheel_color = self._stroke_color(active_context, "wheel", "track")
        wheel_w = 14
        wheel_h = 24
        wheel_positions = (
            (frame_left - wheel_w - wheel_pad, frame_top + 2),
            (frame_right + wheel_pad, frame_top + 2),
            (frame_left - wheel_w - wheel_pad, frame_bottom - wheel_h - 2),
            (frame_right + wheel_pad, frame_bottom - wheel_h - 2),
        )
        for wx, wy in wheel_positions:
            self.canvas.create_rectangle(wx, wy, wx + wheel_w, wy + wheel_h, outline=wheel_color, fill="#dbe6f2")
        self.canvas.create_line(frame_left, y1 - 8, frame_right, y1 - 8, fill="#718096", arrow=tk.BOTH)
        self.canvas.create_text(
            (frame_left + frame_right) / 2,
            y1 - 18,
            text=f"База {geom['wheelbase']:.2f} м",
            font=("Segoe UI", 8),
        )
        self.canvas.create_line(x1 - 8, frame_top, x1 - 8, frame_bottom, fill="#718096", arrow=tk.BOTH)
        self.canvas.create_text(
            x1 - 26,
            (frame_top + frame_bottom) / 2,
            text=f"Колея {geom['track']:.2f} м",
            angle=90,
            font=("Segoe UI", 8),
        )

    def _draw_side_projection(self, geom: dict[str, float], payload: dict[str, object], active_context: str) -> None:
        x0, y0, x1, y1 = 22, 172, 198, 276
        baseline = y1 - 16
        wheel_radius_px = 22
        wheel_left = x0 + 34
        wheel_right = x1 - 34
        frame_bottom = baseline - wheel_radius_px - 18
        frame_top = frame_bottom - 18
        self.canvas.create_line(x0, baseline, x1, baseline, fill="#8d99ae", width=2)
        for center_x in (wheel_left, wheel_right):
            self.canvas.create_oval(
                center_x - wheel_radius_px,
                baseline - 2 * wheel_radius_px,
                center_x + wheel_radius_px,
                baseline,
                outline=self._stroke_color(active_context, "wheel"),
                width=2,
                fill="#f4f7fb",
            )
        self.canvas.create_rectangle(
            wheel_left - 12,
            frame_top,
            wheel_right + 12,
            frame_bottom,
            outline=self._stroke_color(active_context, "frame_dimensions", "cg_height"),
            width=2,
            fill="#e8eff7",
        )
        cg_u = min(1.0, max(0.0, 0.5 + self._safe_float(payload, "cg_x_м", 0.0) / max(0.1, geom["wheelbase"])))
        cg_x = (wheel_left - 12) + (wheel_right - wheel_left + 24) * cg_u
        cg_y = frame_bottom - min(24, 28 * geom["cg_height"] / max(0.2, geom["frame_height"]))
        self.canvas.create_oval(cg_x - 5, cg_y - 5, cg_x + 5, cg_y + 5, fill="#d62828", outline="")
        self.canvas.create_text(cg_x + 10, cg_y - 2, anchor="w", text="ЦМ", font=("Segoe UI", 8, "bold"))
        cyl_color = self._stroke_color(active_context, "stroke", "trim_target")
        for center_x in (wheel_left, wheel_right):
            self.canvas.create_line(center_x, frame_bottom, center_x, baseline - wheel_radius_px, fill=cyl_color, width=3)
        trim_text = f"Цель по ходу {geom['trim_target']:.2f} ± {geom['trim_tol']:.2f}"
        self.canvas.create_text(x0, y0 + 10, anchor="w", text=trim_text, font=("Segoe UI", 8), fill="#355070")

    def _draw_metrics(
        self,
        section_title: str,
        payload: dict[str, object],
        geom: dict[str, float],
        active_context: str,
        unit_label: str,
    ) -> None:
        x = self.METRICS_X0 + 12
        y = self.METRICS_Y0 + 12
        metrics_width = self.METRICS_X1 - self.METRICS_X0 - 24
        lines = self._metric_lines(section_title, payload, geom)
        if unit_label:
            lines.insert(0, f"Единица: {unit_label}")
        if active_context:
            lines.insert(0, f"Показано: {self._context_title(active_context)}")
        for idx, text in enumerate(lines[:8]):
            self.canvas.create_text(
                x,
                y + idx * 18,
                anchor="nw",
                width=metrics_width,
                text=text,
                font=("Segoe UI", 8),
                fill="#264653" if idx == 0 else "#495057",
            )

    def _metric_lines(
        self,
        section_title: str,
        payload: dict[str, object],
        geom: dict[str, float],
    ) -> list[str]:
        section = str(section_title or "").strip()
        if section == "Пневматика":
            total_volume = sum(
                self._safe_float(payload, key, 0.0)
                for key in ("объём_ресивера_1", "объём_ресивера_2", "объём_ресивера_3")
            )
            return [
                f"Ресивер 1: {self._safe_float(payload, 'начальное_давление_Ресивер1', 0.0):.0f} кПа",
                f"Ресивер 2: {self._safe_float(payload, 'начальное_давление_Ресивер2', 0.0):.0f} кПа",
                f"Ресивер 3: {self._safe_float(payload, 'начальное_давление_Ресивер3', 0.0):.0f} кПа",
                f"Аккумулятор: {self._safe_float(payload, 'начальное_давление_аккумулятора', 0.0):.0f} кПа",
                f"Суммарный объём: {total_volume:.1f} л",
                f"Диаметр поршня C1: {1000.0 * self._safe_float(payload, 'диаметр_поршня_Ц1', 0.0):.0f} мм",
                f"Диаметр штока C1: {1000.0 * self._safe_float(payload, 'диаметр_штока_Ц1', 0.0):.0f} мм",
            ]
        if section == "Массы":
            return [
                f"Масса рамы: {self._safe_float(payload, 'масса_рамы', 0.0):.0f} кг",
                f"Неподрессоренная масса: {self._safe_float(payload, 'масса_неподрессоренная_на_угол', 0.0):.0f} кг",
                f"Высота ЦМ: {self._safe_float(payload, 'высота_центра_масс', 0.0):.3f} м",
                f"ЦМ X: {self._safe_float(payload, 'cg_x_м', 0.0):.3f} м",
                f"ЦМ Y: {self._safe_float(payload, 'cg_y_м', 0.0):.3f} м",
                f"Распределение: {str(payload.get('corner_loads_mode') or '—')}",
            ]
        if section == "Механика":
            return [
                f"Жёсткость шины: {self._safe_float(payload, 'жёсткость_шины', 0.0):.0f} Н/м",
                f"Демпфирование шины: {self._safe_float(payload, 'демпфирование_шины', 0.0):.0f} Н·с/м",
                f"Свободная длина пружины: {1000.0 * self._safe_float(payload, 'пружина_длина_свободная_м', 0.0):.0f} мм",
                f"Масштаб пружины: {self._safe_float(payload, 'пружина_масштаб', 0.0):.2f}",
                f"Стабилизатор перед: {self._safe_float(payload, 'стабилизатор_перед_жесткость_Н_м', 0.0):.0f} Н/м",
                f"Стабилизатор зад: {self._safe_float(payload, 'стабилизатор_зад_жесткость_Н_м', 0.0):.0f} Н/м",
            ]
        if section == "Статическая настройка":
            return [
                f"Цель по ходу: {geom['trim_target']:.2f} доли хода",
                f"Допуск: {geom['trim_tol']:.2f} доли хода",
                f"Начальная скорость: {self._safe_float(payload, 'vx0_м_с', 0.0):.2f} м/с",
                f"ЦМ X: {self._safe_float(payload, 'cg_x_м', 0.0):.3f} м",
                f"ЦМ Y: {self._safe_float(payload, 'cg_y_м', 0.0):.3f} м",
            ]
        if section == "Компоненты":
            return [
                f"Паспорт компонентов: {'включён' if bool(payload.get('использовать_паспорт_компонентов')) else 'выключен'}",
                f"Только Camozzi: {'да' if bool(payload.get('enforce_camozzi_only')) else 'нет'}",
                f"Контроль схемы: {'включён' if bool(payload.get('enforce_scheme_integrity')) else 'выключен'}",
                f"Привязка пружины: {'по цилиндру' if bool(payload.get('пружина_по_цилиндру')) else 'отдельно'}",
            ]
        if section == "Справочные данные":
            return [
                f"Температура воздуха: {self._safe_float(payload, 'температура_окр_К', 0.0):.1f} К",
                f"Начальная T воздуха: {self._safe_float(payload, 'T_AIR_К', 0.0):.1f} К",
                f"Термодинамика: {str(payload.get('термодинамика') or '—')}",
                f"Теплоёмкость: {str(payload.get('газ_модель_теплоемкости') or '—')}",
                f"Сомкнутая длина пружины: {1000.0 * self._safe_float(payload, 'пружина_длина_солид_м', 0.0):.0f} мм",
                f"Запас до смыкания витков: {1000.0 * self._safe_float(payload, 'пружина_запас_до_coil_bind_минимум_м', 0.0):.0f} мм",
            ]
        if section in {"Численные настройки", "Расчётные настройки"}:
            return [
                f"Шаг интегрирования: {self._safe_float(payload, 'макс_шаг_интегрирования_с', 0.0):.4f} с",
                f"Внутренних шагов: {self._safe_float(payload, 'макс_число_внутренних_шагов_на_dt', 0.0):.0f}",
                f"Проверка: {'включён' if bool(payload.get('autoverif_enable')) else 'выключен'}",
                f"Проверка механики: {'включён' if bool(payload.get('mechanics_selfcheck')) else 'выключен'}",
            ]
        return [
            f"База: {geom['wheelbase']:.2f} м",
            f"Колея: {geom['track']:.2f} м",
            f"Длина рамы: {geom['frame_length']:.2f} м",
            f"Ширина рамы: {geom['frame_width']:.2f} м",
            f"Высота рамы: {geom['frame_height']:.2f} м",
            f"Радиус колеса: {geom['wheel_radius']:.2f} м",
            f"Ход штока: {geom['stroke']:.2f} м",
        ]


__all__ = ["DesktopInputGraphicPanel"]
