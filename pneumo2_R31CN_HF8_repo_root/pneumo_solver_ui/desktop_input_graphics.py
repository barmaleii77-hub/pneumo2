from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class DesktopInputGraphicPanel(ttk.LabelFrame):
    CANVAS_WIDTH = 360
    CANVAS_HEIGHT = 320

    CONTEXT_TITLES: dict[str, str] = {
        "frame_dimensions": "Габариты и база",
        "track": "Колея и поперечный размер",
        "cg_height": "Высота центра масс",
        "wheel": "Колесо и пятно контакта",
        "stroke": "Ход цилиндра",
        "pressure": "Давления и контуры",
        "volume": "Объёмы и запасы воздуха",
        "piston": "Диаметры поршней",
        "rod": "Диаметры штоков",
        "mass_sprung": "Подрессоренная масса",
        "mass_unsprung": "Неподрессоренная масса",
        "tyre_stiffness": "Жёсткость шины",
        "tyre_damping": "Демпфирование шины",
        "spring": "Пружина и её масштаб",
        "stabilizer": "Баланс стабилизаторов",
        "speed": "Начальная скорость",
        "cg_plan": "Положение центра масс",
        "load_distribution": "Распределение веса",
        "trim_mode": "Режим статической посадки",
        "trim_target": "Посадка по ходу",
        "kinematics": "Кинематика и колесо",
        "compatibility": "Совместимость компонентов",
        "spring_link": "Привязка пружины",
        "gas_model": "Газовая модель",
        "temperature": "Температурный режим",
        "integration": "Параметры интегрирования",
        "checks": "Автопроверки",
        "reference_limits": "Справочные ограничения",
    }

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Графическая подсказка", padding=10)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.summary_var = tk.StringVar(master=self, value="Выберите параметр или раздел.")
        ttk.Label(
            self,
            textvariable=self.summary_var,
            wraplength=360,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")
        self.canvas = tk.Canvas(
            self,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            background="#fbfbfb",
            highlightthickness=1,
            highlightbackground="#d8d8d8",
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

    def refresh(
        self,
        *,
        section_title: str,
        payload: dict[str, object],
        field_label: str = "",
        unit_label: str = "",
        field_key: str = "",
        graphic_context: str = "",
    ) -> None:
        self.canvas.delete("all")
        section = str(section_title or "").strip()
        active_context = self._resolve_active_context(
            section_title=section,
            field_key=field_key,
            field_label=field_label,
            graphic_context=graphic_context,
        )
        if section == "Геометрия":
            self._draw_geometry(payload=payload, field_label=field_label, active_context=active_context)
        elif section == "Пневматика":
            self._draw_pneumatics(payload=payload, field_label=field_label, active_context=active_context)
        elif section == "Механика":
            self._draw_mechanics(payload=payload, field_label=field_label, active_context=active_context)
        elif section == "Статическая настройка":
            self._draw_static_trim(payload=payload, field_label=field_label, active_context=active_context)
        elif section == "Компоненты":
            self._draw_components(payload=payload, field_label=field_label, active_context=active_context)
        else:
            self._draw_reference(
                payload=payload,
                field_label=field_label,
                unit_label=unit_label,
                active_context=active_context,
            )

    def _safe_float(self, payload: dict[str, object], key: str, default: float = 0.0) -> float:
        try:
            return float(payload.get(key, default) or default)
        except Exception:
            return float(default)

    def _safe_bool(self, payload: dict[str, object], key: str) -> bool:
        return bool(payload.get(key, False))

    def _safe_text(self, payload: dict[str, object], key: str, default: str = "—") -> str:
        value = str(payload.get(key, default) or default).strip()
        return value or default

    def _resolve_active_context(
        self,
        *,
        section_title: str,
        field_key: str,
        field_label: str,
        graphic_context: str,
    ) -> str:
        if str(graphic_context or "").strip():
            return str(graphic_context).strip()
        key = str(field_key or "").strip().lower()
        mapping = {
            "база": "frame_dimensions",
            "длина_рамы": "frame_dimensions",
            "ширина_рамы": "frame_dimensions",
            "высота_рамы": "frame_dimensions",
            "колея": "track",
            "высота_центра_масс": "cg_height",
            "радиус_колеса_м": "wheel",
            "wheel_width_m": "wheel",
            "ход_штока": "stroke",
            "масса_рамы": "mass_sprung",
            "масса_неподрессоренная_на_угол": "mass_unsprung",
            "жёсткость_шины": "tyre_stiffness",
            "демпфирование_шины": "tyre_damping",
            "пружина_длина_свободная_м": "spring",
            "пружина_масштаб": "spring",
            "стабилизатор_вкл": "stabilizer",
            "стабилизатор_перед_жесткость_Н_м": "stabilizer",
            "стабилизатор_зад_жесткость_Н_м": "stabilizer",
            "vx0_м_с": "speed",
            "cg_x_м": "cg_plan",
            "cg_y_м": "cg_plan",
            "corner_loads_mode": "load_distribution",
            "static_trim_enable": "trim_mode",
            "static_trim_force": "trim_mode",
            "static_trim_pneumo_mode": "trim_mode",
            "zero_pose_target_stroke_frac": "trim_target",
            "zero_pose_tol_stroke_frac": "trim_target",
            "механика_кинематика": "kinematics",
            "колесо_координата": "kinematics",
            "использовать_паспорт_компонентов": "compatibility",
            "enforce_camozzi_only": "compatibility",
            "enforce_scheme_integrity": "compatibility",
            "пружина_по_цилиндру": "spring_link",
            "пружина_геометрия_согласовать_с_цилиндром": "spring_link",
            "термодинамика": "gas_model",
            "газ_модель_теплоемкости": "gas_model",
            "температура_окр_к": "temperature",
            "t_air_к": "temperature",
            "макс_шаг_интегрирования_с": "integration",
            "макс_число_внутренних_шагов_на_dt": "integration",
            "autoverif_enable": "checks",
            "mechanics_selfcheck": "checks",
            "пружина_длина_солид_м": "reference_limits",
            "пружина_запас_до_coil_bind_минимум_м": "reference_limits",
        }
        if "давление" in key:
            return "pressure"
        if "объём" in key:
            return "volume"
        if "поршня" in key:
            return "piston"
        if "штока" in key:
            return "rod"
        if key in mapping:
            return mapping[key]
        if str(section_title or "").strip() == "Справочные данные" and "температур" in str(field_label or "").lower():
            return "temperature"
        return ""

    def _context_title(self, context_key: str) -> str:
        return self.CONTEXT_TITLES.get(str(context_key or "").strip(), "")

    def _active_text(self, field_label: str, fallback: str) -> str:
        label = str(field_label or "").strip()
        return f"Активно: {label}" if label else fallback

    def _is_active(self, active_context: str, *contexts: str) -> bool:
        clean_active = str(active_context or "").strip()
        if not clean_active:
            return False
        return clean_active in {str(item or "").strip() for item in contexts if str(item or "").strip()}

    def _draw_header(self, title: str, *, active_text: str = "", context_text: str = "") -> None:
        self.canvas.create_text(16, 18, anchor="w", text=title, font=("Segoe UI", 10, "bold"))
        if active_text:
            self.canvas.create_text(16, 38, anchor="w", text=active_text, font=("Segoe UI", 8), fill="#5c677d")
        if context_text:
            self.canvas.create_text(
                16,
                54,
                anchor="w",
                text=f"Контекст: {context_text}",
                font=("Segoe UI", 8, "bold"),
                fill="#9a3412",
            )

    def _draw_chip(
        self,
        x: int,
        y: int,
        text: str,
        *,
        fill: str = "#edf2f4",
        outline: str = "#adb5bd",
        text_fill: str = "#1f2933",
        active: bool = False,
    ) -> None:
        width = max(54, min(156, 12 + len(text) * 6))
        self.canvas.create_rectangle(
            x,
            y,
            x + width,
            y + 24,
            fill=fill,
            outline="#c2410c" if active else outline,
            width=2 if active else 1,
        )
        self.canvas.create_text(
            x + width / 2,
            y + 12,
            text=text,
            font=("Segoe UI", 8, "bold" if active else "normal"),
            fill="#7c2d12" if active else text_fill,
        )

    def _draw_horizontal_bars(
        self,
        *,
        title: str,
        x: int,
        y: int,
        items: list[tuple[str, float, str, str]],
        unit_label: str,
        active_context: str = "",
        max_width: int = 168,
        row_gap: int = 24,
    ) -> None:
        self.canvas.create_text(x, y, anchor="w", text=title, font=("Segoe UI", 9, "bold"))
        max_value = max([abs(value) for _label, value, _color, _context in items] + [1.0])
        for idx, (label, value, color, item_context) in enumerate(items):
            top = y + 16 + idx * row_gap
            is_active = self._is_active(active_context, item_context)
            self.canvas.create_text(
                x,
                top + 6,
                anchor="w",
                text=label,
                font=("Segoe UI", 8, "bold" if is_active else "normal"),
                fill="#7c2d12" if is_active else "#111827",
            )
            self.canvas.create_rectangle(x + 98, top, x + 98 + max_width, top + 12, fill="#edf2f7", outline="#e2e8f0")
            bar_width = int(max_width * abs(value) / max_value)
            self.canvas.create_rectangle(
                x + 98,
                top,
                x + 98 + max(bar_width, 2),
                top + 12,
                fill=color,
                outline="#c2410c" if is_active else color,
                width=2 if is_active else 1,
            )
            self.canvas.create_text(
                x + 98 + max_width,
                top + 6,
                anchor="e",
                text=f"{value:.1f} {unit_label}",
                font=("Segoe UI", 8, "bold" if is_active else "normal"),
                fill="#7c2d12" if is_active else "#111827",
            )

    def _draw_vertical_bars(
        self,
        *,
        title: str,
        x: int,
        y_base: int,
        items: list[tuple[str, float, str, str]],
        unit_label: str,
        active_context: str = "",
        max_height: int = 72,
        slot_width: int = 76,
        bar_width: int = 34,
    ) -> None:
        self.canvas.create_text(x, y_base - max_height - 24, anchor="w", text=title, font=("Segoe UI", 9, "bold"))
        self.canvas.create_line(x, y_base, x + slot_width * max(1, len(items)) - 16, y_base, fill="#a0aec0")
        max_value = max([abs(value) for _label, value, _color, _context in items] + [1.0])
        for idx, (label, value, color, item_context) in enumerate(items):
            x0 = x + idx * slot_width
            bar_height = int(max_height * abs(value) / max_value)
            is_active = self._is_active(active_context, item_context)
            self.canvas.create_rectangle(
                x0,
                y_base - bar_height,
                x0 + bar_width,
                y_base,
                fill=color,
                outline="#c2410c" if is_active else color,
                width=2 if is_active else 1,
            )
            self.canvas.create_text(x0 + bar_width / 2, y_base + 12, text=label, font=("Segoe UI", 8, "bold" if is_active else "normal"))
            self.canvas.create_text(
                x0 + bar_width / 2,
                y_base - bar_height - 10,
                text=f"{value:.1f}",
                font=("Segoe UI", 8, "bold" if is_active else "normal"),
                fill="#7c2d12" if is_active else "#111827",
            )
        self.canvas.create_text(
            x + slot_width * max(1, len(items)) - 18,
            y_base - max_height - 10,
            text=unit_label,
            anchor="e",
            font=("Segoe UI", 8),
            fill="#52606d",
        )

    def _draw_geometry(self, *, payload: dict[str, object], field_label: str, active_context: str) -> None:
        base = self._safe_float(payload, "база", 1.5)
        track = self._safe_float(payload, "колея", 1.0)
        frame_length = self._safe_float(payload, "длина_рамы", max(base, 2.2))
        frame_height = self._safe_float(payload, "высота_рамы", 0.7)
        cg_height = self._safe_float(payload, "высота_центра_масс", 0.55)
        wheel_radius_mm = self._safe_float(payload, "радиус_колеса_м", 0.35) * 1000.0
        stroke_mm = self._safe_float(payload, "ход_штока", 0.18) * 1000.0
        frame_active = self._is_active(active_context, "frame_dimensions", "track")
        wheel_active = self._is_active(active_context, "wheel")
        stroke_active = self._is_active(active_context, "stroke")
        cg_active = self._is_active(active_context, "cg_height")
        self.summary_var.set(
            f"Геометрия показывает базу, колею, габариты, высоту центра масс, радиус колеса и полный ход штока. "
            f"База {base:.3f} м, колея {track:.3f} м, ЦТ {cg_height:.3f} м, ход {stroke_mm:.0f} мм."
        )
        self._draw_header(
            "Схема подвески и габаритов",
            active_text=self._active_text(field_label, "Сравнение габаритов и ходов"),
            context_text=self._context_title(active_context),
        )
        c = self.canvas
        c.create_rectangle(66, 82, 294, 116, outline="#c2410c" if frame_active else "#38598b", width=2)
        c.create_rectangle(88, 116, 112, 176, fill="#d1495b", outline="#c2410c" if stroke_active else "#c1121f", width=2 if stroke_active else 1)
        c.create_rectangle(248, 116, 272, 176, fill="#d1495b", outline="#c2410c" if stroke_active else "#c1121f", width=2 if stroke_active else 1)
        c.create_oval(40, 168, 120, 246, outline="#c2410c" if wheel_active else "#1f2d3d", width=3 if wheel_active else 2)
        c.create_oval(240, 168, 320, 246, outline="#c2410c" if wheel_active else "#1f2d3d", width=3 if wheel_active else 2)
        cg_y = 116 - max(8, min(48, int(cg_height / max(frame_height, 0.2) * 44)))
        c.create_oval(172, cg_y - 6, 184, cg_y + 6, fill="#f4a261", outline="#c2410c" if cg_active else "#bc6c25", width=2 if cg_active else 1)
        c.create_text(192, cg_y, anchor="w", text=f"ЦТ {cg_height:.2f} м", font=("Segoe UI", 8, "bold" if cg_active else "normal"))
        c.create_text(180, 68, text=f"База: {base:.3f} м", font=("Segoe UI", 9))
        c.create_text(180, 132, text=f"Колея: {track:.3f} м", font=("Segoe UI", 9))
        c.create_text(180, 150, text=f"Длина рамы: {frame_length:.3f} м", font=("Segoe UI", 8))
        c.create_text(180, 164, text=f"Высота рамы: {frame_height:.3f} м", font=("Segoe UI", 8))
        self._draw_horizontal_bars(
            title="Продольные размеры",
            x=16,
            y=202,
            items=[
                ("Колёсная база", base, "#457b9d", "frame_dimensions"),
                ("Длина рамы", frame_length, "#1d3557", "frame_dimensions"),
            ],
            unit_label="м",
            active_context=active_context,
            max_width=120,
        )
        self._draw_horizontal_bars(
            title="Поперечные и вертикальные",
            x=184,
            y=202,
            items=[
                ("Колея", track, "#6d597a", "track"),
                ("Высота рамы", frame_height, "#2a9d8f", "frame_dimensions"),
                ("Центр масс", cg_height, "#f4a261", "cg_height"),
            ],
            unit_label="м",
            active_context=active_context,
            max_width=110,
        )
        self._draw_chip(16, 52, f"R колеса {wheel_radius_mm:.0f} мм", fill="#e3f2fd", outline="#90caf9", active=wheel_active)
        self._draw_chip(172, 52, f"Ход штока {stroke_mm:.0f} мм", fill="#fde2e4", outline="#f28482", active=stroke_active)

    def _draw_pneumatics(self, *, payload: dict[str, object], field_label: str, active_context: str) -> None:
        pressures = [
            ("Р1", self._safe_float(payload, "начальное_давление_Ресивер1", 0.0) * 0.001, "#457b9d", "pressure"),
            ("Р2", self._safe_float(payload, "начальное_давление_Ресивер2", 0.0) * 0.001, "#1d3557", "pressure"),
            ("Р3", self._safe_float(payload, "начальное_давление_Ресивер3", 0.0) * 0.001, "#6d597a", "pressure"),
            ("Акк", self._safe_float(payload, "начальное_давление_аккумулятора", 0.0) * 0.001, "#b56576", "pressure"),
        ]
        volumes = [
            ("Ресивер 1", self._safe_float(payload, "объём_ресивера_1", 0.0) * 1000.0, "#a8dadc", "volume"),
            ("Ресивер 2", self._safe_float(payload, "объём_ресивера_2", 0.0) * 1000.0, "#8ecae6", "volume"),
            ("Ресивер 3", self._safe_float(payload, "объём_ресивера_3", 0.0) * 1000.0, "#219ebc", "volume"),
            ("Аккумулятор", self._safe_float(payload, "объём_аккумулятора", 0.0) * 1000.0, "#ffb703", "volume"),
        ]
        pistons = [
            ("Поршень Ц1", self._safe_float(payload, "диаметр_поршня_Ц1", 0.0) * 1000.0, "#2a9d8f", "piston"),
            ("Поршень Ц2", self._safe_float(payload, "диаметр_поршня_Ц2", 0.0) * 1000.0, "#52b788", "piston"),
        ]
        rods = [
            ("Шток Ц1", self._safe_float(payload, "диаметр_штока_Ц1", 0.0) * 1000.0, "#f4a261", "rod"),
            ("Шток Ц2", self._safe_float(payload, "диаметр_штока_Ц2", 0.0) * 1000.0, "#e76f51", "rod"),
        ]
        spread = max(value for _label, value, _color, _context in pressures) - min(value for _label, value, _color, _context in pressures)
        self.summary_var.set(
            f"Пневматика показывает стартовые давления, полезные объёмы и размеры цилиндров. "
            f"Разброс стартовых давлений {spread:.0f} кПа (абс.), объёмы подписаны в литрах."
        )
        self._draw_header(
            "Пневматика: сравнение контуров",
            active_text=self._active_text(field_label, "Сравнение давлений, объёмов и диаметров"),
            context_text=self._context_title(active_context),
        )
        self._draw_vertical_bars(
            title="Стартовые давления",
            x=16,
            y_base=138,
            items=pressures,
            unit_label="кПа (абс.)",
            active_context=active_context,
        )
        self._draw_horizontal_bars(
            title="Полезные объёмы",
            x=16,
            y=166,
            items=volumes,
            unit_label="л",
            active_context=active_context,
            max_width=144,
            row_gap=22,
        )
        self._draw_horizontal_bars(
            title="Диаметры поршней",
            x=16,
            y=264,
            items=pistons,
            unit_label="мм",
            active_context=active_context,
            max_width=126,
            row_gap=20,
        )
        self._draw_horizontal_bars(
            title="Диаметры штоков",
            x=190,
            y=264,
            items=rods,
            unit_label="мм",
            active_context=active_context,
            max_width=126,
            row_gap=20,
        )

    def _draw_mechanics(self, *, payload: dict[str, object], field_label: str, active_context: str) -> None:
        frame_mass = self._safe_float(payload, "масса_рамы", 0.0)
        unsprung_corner = self._safe_float(payload, "масса_неподрессоренная_на_угол", 0.0)
        unsprung_total = unsprung_corner * 4.0
        tyre = self._safe_float(payload, "жёсткость_шины", 0.0)
        damping = self._safe_float(payload, "демпфирование_шины", 0.0)
        spring_scale = self._safe_float(payload, "пружина_масштаб", 1.0)
        front_stab = self._safe_float(payload, "стабилизатор_перед_жесткость_Н_м", 0.0)
        rear_stab = self._safe_float(payload, "стабилизатор_зад_жесткость_Н_м", 0.0)
        stabilizer_active = self._is_active(active_context, "stabilizer")
        self.summary_var.set(
            f"Механика сравнивает подрессоренную и неподрессоренную массу, жёсткость шины, демпфирование и баланс стабилизаторов. "
            f"Масса рамы {frame_mass:.0f} кг, неподрессоренная масса суммарно {unsprung_total:.0f} кг."
        )
        self._draw_header(
            "Массы, шины и стабилизаторы",
            active_text=self._active_text(field_label, "Сравнение масс и жёсткостей"),
            context_text=self._context_title(active_context),
        )
        self._draw_horizontal_bars(
            title="Массы",
            x=16,
            y=58,
            items=[
                ("Рама", frame_mass, "#2a9d8f", "mass_sprung"),
                ("Неподрессоренная x4", unsprung_total, "#e9c46a", "mass_unsprung"),
            ],
            unit_label="кг",
            active_context=active_context,
            max_width=156,
            row_gap=24,
        )
        self._draw_horizontal_bars(
            title="Жёсткость шины",
            x=16,
            y=132,
            items=[("Шина", tyre, "#457b9d", "tyre_stiffness")],
            unit_label="Н/м",
            active_context=active_context,
            max_width=156,
            row_gap=24,
        )
        self._draw_horizontal_bars(
            title="Демпфирование",
            x=16,
            y=188,
            items=[("Шина", damping, "#f4a261", "tyre_damping")],
            unit_label="Н·с/м",
            active_context=active_context,
            max_width=156,
            row_gap=24,
        )
        self.canvas.create_text(192, 148, anchor="w", text="Стабилизаторы", font=("Segoe UI", 9, "bold"))
        self.canvas.create_rectangle(192, 162, 330, 174, fill="#edf2f7", outline="#e2e8f0")
        self.canvas.create_rectangle(
            192,
            162,
            192 + max(2, int(138 * front_stab / max(front_stab, rear_stab, 1.0))),
            174,
            fill="#6d597a",
            outline="#c2410c" if stabilizer_active else "#6d597a",
            width=2 if stabilizer_active else 1,
        )
        self.canvas.create_text(192, 156, anchor="w", text=f"Перед: {front_stab:.0f} Н/м", font=("Segoe UI", 8, "bold" if stabilizer_active else "normal"))
        self.canvas.create_rectangle(192, 192, 330, 204, fill="#edf2f7", outline="#e2e8f0")
        self.canvas.create_rectangle(
            192,
            192,
            192 + max(2, int(138 * rear_stab / max(front_stab, rear_stab, 1.0))),
            204,
            fill="#b56576",
            outline="#c2410c" if stabilizer_active else "#b56576",
            width=2 if stabilizer_active else 1,
        )
        self.canvas.create_text(192, 186, anchor="w", text=f"Зад: {rear_stab:.0f} Н/м", font=("Segoe UI", 8, "bold" if stabilizer_active else "normal"))
        self._draw_chip(192, 222, f"Масштаб пружины {spring_scale:.2f}", fill="#e8f5e9", outline="#81c784", active=self._is_active(active_context, "spring"))
        self._draw_chip(192, 252, f"Шина {tyre:.0f} Н/м", fill="#e3f2fd", outline="#64b5f6", active=self._is_active(active_context, "tyre_stiffness"))
        self._draw_chip(192, 282, f"Демпфирование {damping:.0f} Н·с/м", fill="#fff3e0", outline="#ffb74d", active=self._is_active(active_context, "tyre_damping"))

    def _draw_static_trim(self, *, payload: dict[str, object], field_label: str, active_context: str) -> None:
        target = max(0.0, min(1.0, self._safe_float(payload, "zero_pose_target_stroke_frac", 0.5)))
        tol = max(0.0, min(0.5, self._safe_float(payload, "zero_pose_tol_stroke_frac", 0.05)))
        speed = self._safe_float(payload, "vx0_м_с", 0.0)
        cg_x = self._safe_float(payload, "cg_x_м", 0.0)
        cg_y = self._safe_float(payload, "cg_y_м", 0.0)
        trim_enabled = self._safe_bool(payload, "static_trim_enable")
        trim_mode = self._safe_text(payload, "static_trim_pneumo_mode")
        loads_mode = self._safe_text(payload, "corner_loads_mode")
        trim_target_active = self._is_active(active_context, "trim_target")
        cg_active = self._is_active(active_context, "cg_plan")
        self.summary_var.set(
            f"Статическая настройка показывает целевую долю хода, допуск, смещение центра масс и стартовую скорость. "
            f"Цель {target:.2f} доли хода, допуск ±{tol:.2f}, скорость {speed:.2f} м/с."
        )
        self._draw_header(
            "Посадка и распределение массы",
            active_text=self._active_text(field_label, "Посадка, ЦТ и целевой ход"),
            context_text=self._context_title(active_context),
        )
        c = self.canvas
        c.create_rectangle(42, 62, 92, 228, outline="#c2410c" if trim_target_active else "#555555", width=2)
        band_center = 228 - int(target * 166)
        band_half = int(tol * 166)
        c.create_rectangle(30, band_center - band_half, 104, band_center + band_half, fill="#d8f3dc", outline="#c2410c" if trim_target_active else "", width=2 if trim_target_active else 1)
        c.create_rectangle(46, band_center - 5, 88, band_center + 5, fill="#d1495b", outline="#c2410c" if trim_target_active else "#9d0208", width=2 if trim_target_active else 1)
        c.create_text(42, 240, anchor="w", text="0.00 доли", font=("Segoe UI", 8))
        c.create_text(42, 50, anchor="w", text="1.00 доли", font=("Segoe UI", 8))
        c.create_text(122, 76, anchor="w", text=f"Цель: {target:.2f} доли хода", font=("Segoe UI", 8, "bold" if trim_target_active else "normal"))
        c.create_text(122, 100, anchor="w", text=f"Допуск: ±{tol:.2f}", font=("Segoe UI", 8, "bold" if trim_target_active else "normal"))
        self._draw_chip(122, 116, f"Скорость {speed:.2f} м/с", fill="#e3f2fd", outline="#64b5f6", active=self._is_active(active_context, "speed"))
        self._draw_chip(122, 146, f"Режим посадки: {trim_mode}", fill="#fef3c7", outline="#f59e0b", active=self._is_active(active_context, "trim_mode"))
        self._draw_chip(122, 176, f"Вес по углам: {loads_mode}", fill="#eef2ff", outline="#a5b4fc", active=self._is_active(active_context, "load_distribution"))
        self._draw_chip(
            122,
            206,
            "Поиск посадки включён" if trim_enabled else "Поиск посадки выключен",
            fill="#e8f5e9" if trim_enabled else "#f1f5f9",
            outline="#81c784" if trim_enabled else "#cbd5e1",
            active=self._is_active(active_context, "trim_mode"),
        )
        c.create_text(204, 62, anchor="w", text="Положение ЦТ в плане", font=("Segoe UI", 9, "bold"))
        c.create_rectangle(206, 84, 336, 204, outline="#c2410c" if cg_active else "#94a3b8", width=2)
        c.create_line(271, 84, 271, 204, fill="#cbd5e1", dash=(2, 2))
        c.create_line(206, 144, 336, 144, fill="#cbd5e1", dash=(2, 2))
        cg_x_px = 271 + max(-52, min(52, int(cg_y * 52)))
        cg_y_px = 144 - max(-44, min(44, int(cg_x * 44)))
        c.create_oval(cg_x_px - 6, cg_y_px - 6, cg_x_px + 6, cg_y_px + 6, fill="#f77f00", outline="#c2410c" if cg_active else "#d97706", width=2 if cg_active else 1)
        c.create_text(206, 214, anchor="w", text=f"CG X: {cg_x:+.3f} м", font=("Segoe UI", 8, "bold" if cg_active else "normal"))
        c.create_text(206, 230, anchor="w", text=f"CG Y: {cg_y:+.3f} м", font=("Segoe UI", 8, "bold" if cg_active else "normal"))
        self._draw_horizontal_bars(
            title="Смещение ЦТ",
            x=122,
            y=254,
            items=[
                ("По базе", abs(cg_x), "#577590", "cg_plan"),
                ("По колее", abs(cg_y), "#43aa8b", "cg_plan"),
            ],
            unit_label="м",
            active_context=active_context,
            max_width=160,
            row_gap=22,
        )

    def _draw_components(self, *, payload: dict[str, object], field_label: str, active_context: str) -> None:
        kin = self._safe_text(payload, "механика_кинематика")
        wheel_coord = self._safe_text(payload, "колесо_координата")
        spring_ref = self._safe_text(payload, "пружина_по_цилиндру")
        use_passport = self._safe_bool(payload, "использовать_паспорт_компонентов")
        camozzi_only = self._safe_bool(payload, "enforce_camozzi_only")
        scheme_integrity = self._safe_bool(payload, "enforce_scheme_integrity")
        kinematics_active = self._is_active(active_context, "kinematics")
        spring_link_active = self._is_active(active_context, "spring_link")
        compatibility_active = self._is_active(active_context, "compatibility")
        self.summary_var.set(
            "Компоненты показывают активную кинематику подвески, режим координаты колеса, опорный цилиндр пружины "
            "и флаги контроля совместимости."
        )
        self._draw_header(
            "Схема компонентов и связей",
            active_text=self._active_text(field_label, "Кинематика, паспорт и контроль схемы"),
            context_text=self._context_title(active_context),
        )
        c = self.canvas
        c.create_rectangle(20, 78, 142, 118, fill="#d8e2dc", outline="#c2410c" if kinematics_active else "#52796f", width=2)
        c.create_text(81, 98, text=f"Кинематика\n{kin}", font=("Segoe UI", 8, "bold" if kinematics_active else "normal"))
        c.create_rectangle(20, 146, 142, 186, fill="#ffe8d6", outline="#c2410c" if kinematics_active else "#bc6c25", width=2)
        c.create_text(81, 166, text=f"Колесо\n{wheel_coord}", font=("Segoe UI", 8, "bold" if kinematics_active else "normal"))
        c.create_rectangle(218, 112, 340, 152, fill="#e9ecef", outline="#c2410c" if spring_link_active else "#495057", width=2)
        c.create_text(279, 132, text=f"Пружина\nпо {spring_ref}", font=("Segoe UI", 8, "bold" if spring_link_active else "normal"))
        c.create_line(142, 98, 218, 132, arrow="last", fill="#c2410c" if spring_link_active else "#6c757d", width=2)
        c.create_line(142, 166, 218, 132, arrow="last", fill="#c2410c" if spring_link_active else "#6c757d", width=2)
        self._draw_chip(
            20,
            214,
            "Паспорт компонентов" if use_passport else "Без паспорта",
            fill="#e8f5e9" if use_passport else "#f8fafc",
            outline="#81c784" if use_passport else "#cbd5e1",
            active=compatibility_active,
        )
        self._draw_chip(
            20,
            244,
            "Только Camozzi" if camozzi_only else "Camozzi не обязателен",
            fill="#eef2ff" if camozzi_only else "#f8fafc",
            outline="#a5b4fc" if camozzi_only else "#cbd5e1",
            active=compatibility_active,
        )
        self._draw_chip(
            20,
            274,
            "Контроль схемы включён" if scheme_integrity else "Контроль схемы выключен",
            fill="#fff7ed" if scheme_integrity else "#f8fafc",
            outline="#fdba74" if scheme_integrity else "#cbd5e1",
            active=compatibility_active,
        )

    def _draw_reference(
        self,
        *,
        payload: dict[str, object],
        field_label: str,
        unit_label: str,
        active_context: str,
    ) -> None:
        temp = self._safe_float(payload, "температура_окр_К", 293.0)
        air = self._safe_float(payload, "T_AIR_К", 293.0)
        max_step_ms = self._safe_float(payload, "макс_шаг_интегрирования_с", 0.001) * 1000.0
        max_inner_steps = self._safe_float(payload, "макс_число_внутренних_шагов_на_dt", 0.0)
        thermodynamics = self._safe_text(payload, "термодинамика")
        heat_model = self._safe_text(payload, "газ_модель_теплоемкости")
        autoverif = self._safe_bool(payload, "autoverif_enable")
        mechanics_check = self._safe_bool(payload, "mechanics_selfcheck")
        solid_length_mm = self._safe_float(payload, "пружина_длина_солид_м", 0.0) * 1000.0
        coil_bind_margin_mm = self._safe_float(payload, "пружина_запас_до_coil_bind_минимум_м", 0.0) * 1000.0
        active_name = field_label or "Справочные данные"
        active_unit = unit_label or "безразмерно"
        self.summary_var.set(
            f"Справочные данные показывают температуры, численные ограничения, проверки и инженерные лимиты. "
            f"Температура среды {temp:.1f} К, воздуха {air:.1f} К, шаг интегрирования {max_step_ms:.2f} мс."
        )
        self._draw_header(
            "Справочные режимы и численные лимиты",
            active_text=f"Активно: {active_name}",
            context_text=self._context_title(active_context),
        )
        self._draw_horizontal_bars(
            title="Температуры",
            x=16,
            y=58,
            items=[
                ("Среда", temp, "#457b9d", "temperature"),
                ("Воздух", air, "#1d3557", "temperature"),
            ],
            unit_label="К",
            active_context=active_context,
            max_width=160,
            row_gap=24,
        )
        self._draw_horizontal_bars(
            title="Численные лимиты",
            x=16,
            y=132,
            items=[
                ("Шаг интегрирования", max_step_ms, "#f4a261", "integration"),
                ("Внутренние шаги / dt", max_inner_steps, "#e76f51", "integration"),
            ],
            unit_label="мс",
            active_context=active_context,
            max_width=160,
            row_gap=24,
        )
        self._draw_chip(204, 74, f"Термодинамика: {thermodynamics}", fill="#e0f2fe", outline="#7dd3fc", active=self._is_active(active_context, "gas_model"))
        self._draw_chip(204, 106, f"Теплоёмкость: {heat_model}", fill="#ede9fe", outline="#c4b5fd", active=self._is_active(active_context, "gas_model"))
        self._draw_chip(
            204,
            138,
            "Автопроверка включена" if autoverif else "Автопроверка выключена",
            fill="#ecfccb" if autoverif else "#f8fafc",
            outline="#bef264" if autoverif else "#cbd5e1",
            active=self._is_active(active_context, "checks"),
        )
        self._draw_chip(
            204,
            170,
            "Самопроверка механики" if mechanics_check else "Без самопроверки механики",
            fill="#fff7ed" if mechanics_check else "#f8fafc",
            outline="#fdba74" if mechanics_check else "#cbd5e1",
            active=self._is_active(active_context, "checks"),
        )
        self._draw_chip(
            204,
            202,
            f"Solid length {solid_length_mm:.0f} мм",
            fill="#fef2f2",
            outline="#fca5a5",
            active=self._is_active(active_context, "reference_limits"),
        )
        self._draw_chip(
            204,
            234,
            f"Запас до coil bind {coil_bind_margin_mm:.0f} мм",
            fill="#fff7ed",
            outline="#fdba74",
            active=self._is_active(active_context, "reference_limits"),
        )
        self.canvas.create_rectangle(16, 258, 338, 304, outline="#adb5bd")
        self.canvas.create_text(24, 270, anchor="w", text=f"Активное поле: {active_name}", font=("Segoe UI", 8))
        self.canvas.create_text(24, 286, anchor="w", text=f"Единица: {active_unit}", font=("Segoe UI", 8))
        self.canvas.create_text(24, 300, anchor="w", text="Числа без единиц здесь считаются ошибкой интерфейса.", font=("Segoe UI", 8), fill="#52606d")


__all__ = ["DesktopInputGraphicPanel"]
