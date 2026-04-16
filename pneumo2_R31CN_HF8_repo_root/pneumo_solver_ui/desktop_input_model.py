# -*- coding: utf-8 -*-
"""Curated desktop input model for operator-friendly source data editing.

This module intentionally exposes a *small but practical* subset of the full
base contract. The goal is to give operators a clear desktop-first editor with
sections and sliders, without forcing them through the large WEB UI.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


DESKTOP_ADVANCED_FIELD_KEYS: frozenset[str] = frozenset(
    {
        "corner_loads_mode",
        "static_trim_force",
        "static_trim_pneumo_mode",
        "использовать_паспорт_компонентов",
        "enforce_camozzi_only",
        "enforce_scheme_integrity",
        "пружина_геометрия_согласовать_с_цилиндром",
        "газ_модель_теплоемкости",
        "макс_шаг_интегрирования_с",
        "макс_число_внутренних_шагов_на_dt",
        "autoverif_enable",
        "mechanics_selfcheck",
        "пружина_длина_solid_м",
        "пружина_запас_до_coil_bind_минимум_м",
    }
)


DESKTOP_HELP_OVERRIDES: dict[str, dict[str, str]] = {
    "база": {
        "tooltip": "Расстояние между передней и задней осями. Влияет на продольную устойчивость, посадку и кинематику.",
        "help_title": "Колёсная база",
        "help_body": (
            "Колёсная база задаёт расстояние между осями.\n\n"
            "Единица: метры.\n"
            "Влияет на распределение масс, геометрию подвески и реакцию машины на продольные возмущения.\n"
            "Обычно меняется редко и соответствует геометрии конкретного шасси."
        ),
    },
    "колея": {
        "tooltip": "Расстояние между левым и правым колесом на оси. Влияет на поперечную устойчивость.",
        "help_title": "Колея",
        "help_body": (
            "Колея задаёт поперечный размер оси.\n\n"
            "Единица: метры.\n"
            "Используется в расчёте поперечной устойчивости, крена и распределения нагрузки."
        ),
    },
    "ход_штока": {
        "tooltip": "Полный рабочий ход цилиндра. Для этого поля важны и миллиметры, и визуальный контроль положения в ходе.",
        "help_title": "Полный ход штока",
        "help_body": (
            "Полный ход штока определяет доступный диапазон перемещения цилиндра.\n\n"
            "Единица: миллиметры.\n"
            "Используется в статической посадке, в аниматоре и при контроле выхода в отбой или сжатие."
        ),
    },
    "zero_pose_target_stroke_frac": {
        "tooltip": "Целевое положение штока в статике как доля полного хода.",
        "help_title": "Целевая доля хода",
        "help_body": (
            "Показывает, где должен находиться шток в нулевой позе.\n\n"
            "Единица: доля полного хода.\n"
            "Значение 0.50 означает середину хода, 0.30 ближе к отбою, 0.70 ближе к сжатию."
        ),
    },
}


DESKTOP_GRAPHIC_CONTEXT_OVERRIDES: dict[str, str] = {
    **{
        key: "frame_dimensions"
        for key in (
            "база",
            "длина_рамы",
            "ширина_рамы",
            "высота_рамы",
        )
    },
    "колея": "track",
    "высота_центра_масс": "cg_height",
    **{
        key: "wheel"
        for key in (
            "радиус_колеса_м",
            "wheel_width_m",
        )
    },
    "ход_штока": "stroke",
    **{
        key: "pressure"
        for key in (
            "начальное_давление_Ресивер1",
            "начальное_давление_Ресивер2",
            "начальное_давление_Ресивер3",
            "начальное_давление_аккумулятора",
        )
    },
    **{
        key: "volume"
        for key in (
            "объём_ресивера_1",
            "объём_ресивера_2",
            "объём_ресивера_3",
            "объём_аккумулятора",
        )
    },
    **{
        key: "piston"
        for key in (
            "диаметр_поршня_Ц1",
            "диаметр_поршня_Ц2",
        )
    },
    **{
        key: "rod"
        for key in (
            "диаметр_штока_Ц1",
            "диаметр_штока_Ц2",
        )
    },
    "масса_рамы": "mass_sprung",
    "масса_неподрессоренная_на_угол": "mass_unsprung",
    "жёсткость_шины": "tyre_stiffness",
    "демпфирование_шины": "tyre_damping",
    **{
        key: "spring"
        for key in (
            "пружина_длина_свободная_м",
            "пружина_масштаб",
        )
    },
    **{
        key: "stabilizer"
        for key in (
            "стабилизатор_вкл",
            "стабилизатор_перед_жесткость_Н_м",
            "стабилизатор_зад_жесткость_Н_м",
        )
    },
    "vx0_м_с": "speed",
    **{
        key: "cg_plan"
        for key in (
            "cg_x_м",
            "cg_y_м",
        )
    },
    "corner_loads_mode": "load_distribution",
    **{
        key: "trim_mode"
        for key in (
            "static_trim_enable",
            "static_trim_force",
            "static_trim_pneumo_mode",
        )
    },
    **{
        key: "trim_target"
        for key in (
            "zero_pose_target_stroke_frac",
            "zero_pose_tol_stroke_frac",
        )
    },
    **{
        key: "kinematics"
        for key in (
            "механика_кинематика",
            "колесо_координата",
        )
    },
    **{
        key: "compatibility"
        for key in (
            "использовать_паспорт_компонентов",
            "enforce_camozzi_only",
            "enforce_scheme_integrity",
        )
    },
    **{
        key: "spring_link"
        for key in (
            "пружина_по_цилиндру",
            "пружина_геометрия_согласовать_с_цилиндром",
        )
    },
    **{
        key: "gas_model"
        for key in (
            "термодинамика",
            "газ_модель_теплоемкости",
        )
    },
    **{
        key: "temperature"
        for key in (
            "температура_окр_К",
            "T_AIR_К",
        )
    },
    **{
        key: "integration"
        for key in (
            "макс_шаг_интегрирования_с",
            "макс_число_внутренних_шагов_на_dt",
        )
    },
    **{
        key: "checks"
        for key in (
            "autoverif_enable",
            "mechanics_selfcheck",
        )
    },
    **{
        key: "reference_limits"
        for key in (
            "пружина_длина_солид_м",
            "пружина_запас_до_coil_bind_минимум_м",
        )
    },
}


@dataclass(frozen=True)
class DesktopInputFieldSpec:
    key: str
    label: str
    unit_label: str
    description: str
    control: str = "slider"
    min_value: float | int | None = None
    max_value: float | int | None = None
    step: float | int | None = None
    ui_scale: float = 1.0
    ui_offset: float = 0.0
    digits: int = 3
    choices: tuple[str, ...] = ()
    choice_labels: tuple[tuple[str, str], ...] = ()
    tooltip_text: str = ""
    help_title: str = ""
    help_body: str = ""
    user_level: str = "basic"
    graphic_context: str = ""

    def to_ui(self, base_value: Any) -> Any:
        if self.control == "bool":
            return bool(base_value)
        if self.control == "choice":
            raw_value = str(base_value or (self.choices[0] if self.choices else ""))
            return self.choice_label_map.get(raw_value, raw_value)
        if self.control == "int":
            try:
                return int(round((float(base_value) + float(self.ui_offset)) * float(self.ui_scale)))
            except Exception:
                return int(self.min_value or 0)
        try:
            return (float(base_value) + float(self.ui_offset)) * float(self.ui_scale)
        except Exception:
            if self.min_value is not None:
                return float(self.min_value)
            return 0.0

    def to_base(self, ui_value: Any) -> Any:
        if self.control == "bool":
            return bool(ui_value)
        if self.control == "choice":
            raw_value = str(ui_value or "").strip()
            return self.choice_value_map.get(raw_value, raw_value)
        if self.control == "int":
            try:
                return int(round(float(ui_value) / float(self.ui_scale) - float(self.ui_offset)))
            except Exception:
                return int(self.min_value or 0)
        try:
            return float(ui_value) / float(self.ui_scale) - float(self.ui_offset)
        except Exception:
            return 0.0

    @property
    def effective_user_level(self) -> str:
        if str(self.user_level or "").strip():
            if self.user_level != "basic":
                return self.user_level
        if self.key in DESKTOP_ADVANCED_FIELD_KEYS:
            return "advanced"
        return "basic"

    @property
    def effective_tooltip_text(self) -> str:
        override = DESKTOP_HELP_OVERRIDES.get(self.key, {})
        value = str(self.tooltip_text or override.get("tooltip") or self.description or "").strip()
        return value

    @property
    def effective_help_title(self) -> str:
        override = DESKTOP_HELP_OVERRIDES.get(self.key, {})
        value = str(self.help_title or override.get("help_title") or self.label or "").strip()
        return value

    @property
    def effective_help_body(self) -> str:
        override = DESKTOP_HELP_OVERRIDES.get(self.key, {})
        body = str(self.help_body or override.get("help_body") or self.description or "").strip()
        if self.unit_label:
            unit_line = f"Единица измерения: {self.unit_label}."
            if unit_line not in body:
                body = f"{body}\n\n{unit_line}"
        if self.min_value is not None or self.max_value is not None:
            range_line = f"Рабочий диапазон: {self.range_text}."
            if range_line not in body:
                body = f"{body}\n{range_line}"
        return body.strip()

    @property
    def effective_graphic_context(self) -> str:
        return str(
            self.graphic_context
            or DESKTOP_GRAPHIC_CONTEXT_OVERRIDES.get(self.key, "")
            or ""
        ).strip()

    @property
    def range_text(self) -> str:
        if self.min_value is None and self.max_value is None:
            return "не задан"
        if self.min_value is None:
            return f"до {self.max_value}"
        if self.max_value is None:
            return f"от {self.min_value}"
        return f"от {self.min_value} до {self.max_value}"

    @property
    def choice_label_map(self) -> dict[str, str]:
        return {str(key): str(label) for key, label in self.choice_labels}

    @property
    def choice_value_map(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for key, label in self.choice_labels:
            mapping[str(label)] = str(key)
        for raw_choice in self.choices:
            mapping.setdefault(str(raw_choice), str(raw_choice))
        return mapping

    @property
    def display_choices(self) -> tuple[str, ...]:
        if self.control != "choice":
            return ()
        return tuple(self.choice_label_map.get(choice, choice) for choice in self.choices)


@dataclass(frozen=True)
class DesktopInputSection:
    title: str
    description: str
    fields: tuple[DesktopInputFieldSpec, ...] = field(default_factory=tuple)


DESKTOP_INPUT_SECTIONS: tuple[DesktopInputSection, ...] = (
    DesktopInputSection(
        title="Геометрия",
        description="Базовые размеры кузова, колёс и ходов, которые задают общую посадку и рабочую геометрию.",
        fields=(
            DesktopInputFieldSpec("база", "Колёсная база", "м", "Расстояние между передней и задней осями.", min_value=0.8, max_value=4.0, step=0.01, digits=3),
            DesktopInputFieldSpec("колея", "Колея", "м", "Расстояние между левым и правым колесом на оси.", min_value=0.6, max_value=3.0, step=0.01, digits=3),
            DesktopInputFieldSpec("длина_рамы", "Длина рамы", "м", "Габаритная длина кузова/рамы для модели и визуализации.", min_value=1.0, max_value=6.0, step=0.01, digits=3),
            DesktopInputFieldSpec("ширина_рамы", "Ширина рамы", "м", "Габаритная ширина кузова/рамы.", min_value=0.2, max_value=3.0, step=0.01, digits=3),
            DesktopInputFieldSpec("высота_рамы", "Высота рамы", "м", "Габаритная высота кузова/рамы.", min_value=0.1, max_value=2.5, step=0.01, digits=3),
            DesktopInputFieldSpec("высота_центра_масс", "Высота центра масс", "м", "Высота центра масс относительно дорожного уровня.", min_value=0.05, max_value=1.5, step=0.005, digits=3),
            DesktopInputFieldSpec("радиус_колеса_м", "Радиус колеса", "м", "Радиус колеса для кинематики и контакта с дорогой.", min_value=0.15, max_value=0.8, step=0.005, digits=3),
            DesktopInputFieldSpec("wheel_width_m", "Ширина колеса", "мм", "Физическая ширина колеса/шины.", min_value=120.0, max_value=420.0, step=1.0, ui_scale=1000.0, digits=0),
            DesktopInputFieldSpec("ход_штока", "Полный ход штока", "мм", "Полный рабочий ход цилиндра.", min_value=50.0, max_value=500.0, step=1.0, ui_scale=1000.0, digits=0),
        ),
    ),
    DesktopInputSection(
        title="Пневматика",
        description="Стартовые давления, полезные объёмы и габариты пневмоцилиндров.",
        fields=(
            DesktopInputFieldSpec("начальное_давление_Ресивер1", "Начальное давление ресивера 1", "кПа (абс.)", "Стартовое абсолютное давление в ресивере 1.", min_value=100.0, max_value=1200.0, step=5.0, ui_scale=0.001, digits=1),
            DesktopInputFieldSpec("начальное_давление_Ресивер2", "Начальное давление ресивера 2", "кПа (абс.)", "Стартовое абсолютное давление в ресивере 2.", min_value=100.0, max_value=1200.0, step=5.0, ui_scale=0.001, digits=1),
            DesktopInputFieldSpec("начальное_давление_Ресивер3", "Начальное давление ресивера 3", "кПа (абс.)", "Стартовое абсолютное давление в ресивере 3.", min_value=100.0, max_value=1200.0, step=5.0, ui_scale=0.001, digits=1),
            DesktopInputFieldSpec("начальное_давление_аккумулятора", "Начальное давление аккумулятора", "кПа (абс.)", "Стартовое абсолютное давление в пневмоаккумуляторе.", min_value=100.0, max_value=1200.0, step=5.0, ui_scale=0.001, digits=1),
            DesktopInputFieldSpec("объём_ресивера_1", "Объём ресивера 1", "л", "Полезный объём ресивера 1.", min_value=0.1, max_value=20.0, step=0.1, ui_scale=1000.0, digits=2),
            DesktopInputFieldSpec("объём_ресивера_2", "Объём ресивера 2", "л", "Полезный объём ресивера 2.", min_value=0.1, max_value=20.0, step=0.1, ui_scale=1000.0, digits=2),
            DesktopInputFieldSpec("объём_ресивера_3", "Объём ресивера 3", "л", "Полезный объём ресивера 3.", min_value=0.1, max_value=20.0, step=0.1, ui_scale=1000.0, digits=2),
            DesktopInputFieldSpec("объём_аккумулятора", "Объём аккумулятора", "л", "Полезный объём пневмоаккумулятора.", min_value=0.1, max_value=20.0, step=0.1, ui_scale=1000.0, digits=2),
            DesktopInputFieldSpec("диаметр_поршня_Ц1", "Диаметр поршня Ц1", "мм", "Наружный диаметр рабочего поршня цилиндра Ц1.", min_value=10.0, max_value=120.0, step=1.0, ui_scale=1000.0, digits=0),
            DesktopInputFieldSpec("диаметр_поршня_Ц2", "Диаметр поршня Ц2", "мм", "Наружный диаметр рабочего поршня цилиндра Ц2.", min_value=10.0, max_value=120.0, step=1.0, ui_scale=1000.0, digits=0),
            DesktopInputFieldSpec("диаметр_штока_Ц1", "Диаметр штока Ц1", "мм", "Диаметр штока цилиндра Ц1.", min_value=5.0, max_value=60.0, step=1.0, ui_scale=1000.0, digits=0),
            DesktopInputFieldSpec("диаметр_штока_Ц2", "Диаметр штока Ц2", "мм", "Диаметр штока цилиндра Ц2.", min_value=5.0, max_value=60.0, step=1.0, ui_scale=1000.0, digits=0),
        ),
    ),
    DesktopInputSection(
        title="Механика",
        description="Массы, шины, пружина и стабилизаторы, которые формируют механический отклик подвески.",
        fields=(
            DesktopInputFieldSpec("масса_рамы", "Масса рамы", "кг", "Подрессоренная масса кузова/рамы.", min_value=50.0, max_value=5000.0, step=10.0, digits=1),
            DesktopInputFieldSpec("масса_неподрессоренная_на_угол", "Неподрессоренная масса на угол", "кг", "Масса колеса, ступицы и рычагов на один угол.", min_value=1.0, max_value=250.0, step=1.0, digits=1),
            DesktopInputFieldSpec("жёсткость_шины", "Жёсткость шины", "Н/м", "Вертикальная жёсткость шины.", min_value=10000.0, max_value=1000000.0, step=1000.0, digits=0),
            DesktopInputFieldSpec("демпфирование_шины", "Демпфирование шины", "Н·с/м", "Вертикальное демпфирование шины.", min_value=100.0, max_value=50000.0, step=100.0, digits=0),
            DesktopInputFieldSpec("пружина_длина_свободная_м", "Свободная длина пружины", "мм", "Исходная свободная длина пружины до сжатия.", min_value=100.0, max_value=1500.0, step=1.0, ui_scale=1000.0, digits=0),
            DesktopInputFieldSpec("пружина_масштаб", "Масштаб пружины", "коэф.", "Масштабирует табличную характеристику пружины.", min_value=0.05, max_value=3.0, step=0.01, digits=2),
            DesktopInputFieldSpec("стабилизатор_вкл", "Стабилизатор включён", "", "Включает учёт стабилизатора в модели.", control="bool"),
            DesktopInputFieldSpec("стабилизатор_перед_жесткость_Н_м", "Жёсткость переднего стабилизатора", "Н/м", "Эквивалентная жёсткость переднего стабилизатора.", min_value=0.0, max_value=500000.0, step=1000.0, digits=0),
            DesktopInputFieldSpec("стабилизатор_зад_жесткость_Н_м", "Жёсткость заднего стабилизатора", "Н/м", "Эквивалентная жёсткость заднего стабилизатора.", min_value=0.0, max_value=500000.0, step=1000.0, digits=0),
        ),
    ),
    DesktopInputSection(
        title="Статическая настройка",
        description="Стартовое состояние, распределение веса и режим поиска статической посадки.",
        fields=(
            DesktopInputFieldSpec("vx0_м_с", "Начальная скорость", "м/с", "Начальная продольная скорость модели.", min_value=0.0, max_value=80.0, step=0.1, digits=2),
            DesktopInputFieldSpec("cg_x_м", "Смещение ЦТ по базе", "м", "Продольное смещение центра тяжести относительно середины базы.", min_value=-1.5, max_value=1.5, step=0.005, digits=3),
            DesktopInputFieldSpec("cg_y_м", "Смещение ЦТ по колее", "м", "Поперечное смещение центра тяжести относительно продольной оси.", min_value=-1.0, max_value=1.0, step=0.005, digits=3),
            DesktopInputFieldSpec("corner_loads_mode", "Режим распределения веса по углам", "", "Как распределять вес по углам при инициализации: через ЦТ или через эффективные жёсткости.", control="choice", choices=("cg", "stiffness"), choice_labels=(("cg", "Через центр тяжести"), ("stiffness", "Через жёсткости"))),
            DesktopInputFieldSpec("static_trim_enable", "Искать статическую посадку", "", "Перед основным расчётом подобрать статическое равновесие.", control="bool"),
            DesktopInputFieldSpec("static_trim_force", "Форсировать статическую посадку", "", "Принудительно выполнять static trim даже при существующем состоянии.", control="bool"),
            DesktopInputFieldSpec("static_trim_pneumo_mode", "Режим static trim по пневматике", "", "Как корректировать пневматику при поиске посадки: давлением, массой или политропой.", control="choice", choices=("pressure", "mass", "polytropic"), choice_labels=(("pressure", "Коррекция давлением"), ("mass", "Коррекция массой"), ("polytropic", "Политропная коррекция"))),
            DesktopInputFieldSpec("zero_pose_target_stroke_frac", "Целевая доля хода в нуле", "доля", "Желаемое положение штока в статике как доля полного хода.", min_value=0.0, max_value=1.0, step=0.01, digits=2),
            DesktopInputFieldSpec("zero_pose_tol_stroke_frac", "Допуск по доле хода", "доля", "Разрешённое отклонение от целевого положения штока в статике.", min_value=0.0, max_value=0.5, step=0.01, digits=2),
        ),
    ),
    DesktopInputSection(
        title="Компоненты",
        description="Выбор активной кинематики, привязки пружины и правил работы с паспортом компонентов.",
        fields=(
            DesktopInputFieldSpec("механика_кинематика", "Кинематика подвески", "", "Активный вариант кинематики в модели.", control="choice", choices=("dw2d", "dw2d_mounts", "mr", "table"), choice_labels=(("dw2d", "Двухрычажная 2D"), ("dw2d_mounts", "2D с точками крепления"), ("mr", "Через передаточное отношение"), ("table", "По табличной характеристике"))),
            DesktopInputFieldSpec("колесо_координата", "Режим колесо_координата", "", "Как интерпретируется координата колеса: центр колеса или пятно контакта.", control="choice", choices=("center", "contact"), choice_labels=(("center", "Центр колеса"), ("contact", "Пятно контакта"))),
            DesktopInputFieldSpec("использовать_паспорт_компонентов", "Использовать паспорт компонентов", "", "Подтягивать параметры компонентов из component passport.", control="bool"),
            DesktopInputFieldSpec("enforce_camozzi_only", "Только Camozzi-коды", "", "Контролировать, что схема использует только Camozzi-коды из паспорта компонентов.", control="bool"),
            DesktopInputFieldSpec("enforce_scheme_integrity", "Контроль целостности схемы", "", "Следить за fingerprint схемы и не терять инженерную целостность конфигурации.", control="bool"),
            DesktopInputFieldSpec("пружина_по_цилиндру", "Опорный цилиндр для пружины", "", "К какому цилиндру привязывать пружину в механической модели.", control="choice", choices=("C1", "C2", "DELTA"), choice_labels=(("C1", "Цилиндр C1"), ("C2", "Цилиндр C2"), ("DELTA", "Разность C1-C2"))),
            DesktopInputFieldSpec("пружина_геометрия_согласовать_с_цилиндром", "Согласовывать геометрию пружины с цилиндром", "", "Поддерживать совместимость геометрии пружины с выбранным цилиндром.", control="bool"),
        ),
    ),
    DesktopInputSection(
        title="Справочные данные",
        description="Режимы газа, температурные reference-параметры и служебные инженерные проверки.",
        fields=(
            DesktopInputFieldSpec("термодинамика", "Режим термодинамики", "", "Модель газа: изотерма, адиабата или тепловой режим со стенкой.", control="choice", choices=("thermal", "isothermal", "adiabatic"), choice_labels=(("thermal", "Теплообмен со стенкой"), ("isothermal", "Изотермический"), ("adiabatic", "Адиабатический"))),
            DesktopInputFieldSpec("газ_модель_теплоемкости", "Модель теплоёмкости воздуха", "", "Постоянные теплоёмкости или T-зависимая reference-модель nist_air.", control="choice", choices=("constant", "nist_air"), choice_labels=(("constant", "Постоянные теплоёмкости"), ("nist_air", "Справочная модель воздуха NIST"))),
            DesktopInputFieldSpec("температура_окр_К", "Температура окружающей среды", "К", "Температура среды, в которой работает система.", min_value=200.0, max_value=400.0, step=1.0, digits=1),
            DesktopInputFieldSpec("T_AIR_К", "Начальная температура воздуха", "К", "Базовая температура воздуха для начального состояния газа.", min_value=200.0, max_value=400.0, step=1.0, digits=1),
            DesktopInputFieldSpec("макс_шаг_интегрирования_с", "Максимальный шаг интегрирования", "мс", "Ограничение шага интегратора.", min_value=0.01, max_value=10.0, step=0.01, ui_scale=1000.0, digits=2),
            DesktopInputFieldSpec("макс_число_внутренних_шагов_на_dt", "Макс. внутренних шагов на dt", "шагов", "Защита от зависания интегратора на одном шаге dt.", control="int", min_value=1000, max_value=1000000, step=1000, digits=0),
            DesktopInputFieldSpec("autoverif_enable", "Включить автопроверку", "", "Проверять физические и численные ограничения после расчёта.", control="bool"),
            DesktopInputFieldSpec("mechanics_selfcheck", "Включить самопроверку механики", "", "Проверять кинематику и механические ограничения.", control="bool"),
            DesktopInputFieldSpec("пружина_длина_солид_м", "Сомкнутая длина пружины", "мм", "Справочная длина пружины в полностью сомкнутом состоянии.", min_value=0.0, max_value=400.0, step=1.0, ui_scale=1000.0, digits=0),
            DesktopInputFieldSpec("пружина_запас_до_coil_bind_минимум_м", "Минимальный запас до смыкания витков", "мм", "Допустимый минимальный запас до смыкания витков для справочных проверок.", min_value=0.0, max_value=120.0, step=1.0, ui_scale=1000.0, digits=0),
        ),
    ),
)


DESKTOP_PREVIEW_SURFACE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("flat", "Ровная дорога"),
    ("sine_x", "Синус вдоль"),
    ("bump", "Бугор"),
    ("ridge_cosine_bump", "Косинусный бугор"),
)

DESKTOP_QUICK_PRESET_OPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "soft_ride",
        "Подвеска мягче",
        "Чуть снижает жёсткость пружины, шин и стабилизаторов для более мягкой реакции.",
    ),
    (
        "firm_ride",
        "Подвеска жёстче",
        "Чуть повышает жёсткость пружины, шин и стабилизаторов для более собранной реакции.",
    ),
    (
        "pressure_up",
        "Выше давление",
        "Поднимает стартовые давления в пневмосистеме без изменения геометрии.",
    ),
    (
        "pressure_down",
        "Ниже давление",
        "Уменьшает стартовые давления в пневмосистеме для мягкого exploratory-сдвига.",
    ),
    (
        "draft_calc",
        "Черновой расчёт",
        "Делает интегрирование грубее, чтобы быстрее пройти предварительную проверку.",
    ),
    (
        "precise_calc",
        "Точнее интегрирование",
        "Уменьшает шаг интегрирования и увеличивает лимит внутренних шагов.",
    ),
)

DESKTOP_RUN_PRESET_OPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "sanity_check",
        "Быстрый sanity-check",
        "Короткий проверочный прогон без расширенного лога, чтобы быстро убедиться, что конфигурация ведёт себя ожидаемо.",
    ),
    (
        "draft_run",
        "Черновой запуск",
        "Умеренно быстрый рабочий режим для большинства предварительных прогонов.",
    ),
    (
        "precise_run",
        "Точнее",
        "Более подробный запуск с меньшим шагом и включённым расширенным логом.",
    ),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_base_json_path() -> Path:
    return (Path(__file__).resolve().parent / "default_base.json").resolve()


def default_working_copy_path() -> Path:
    return (repo_root() / "workspace" / "ui_state" / "desktop_input_base.json").resolve()


def desktop_profile_dir_path() -> Path:
    return (repo_root() / "workspace" / "ui_state" / "desktop_input_profiles").resolve()


def desktop_snapshot_dir_path() -> Path:
    return (repo_root() / "workspace" / "ui_state" / "desktop_input_snapshots").resolve()


def desktop_runs_dir_path() -> Path:
    return (repo_root() / "workspace" / "desktop_runs").resolve()


def default_ranges_json_path() -> Path:
    return (Path(__file__).resolve().parent / "default_ranges.json").resolve()


def default_suite_json_path() -> Path:
    return (Path(__file__).resolve().parent / "default_suite.json").resolve()


def describe_desktop_inputs_handoff_for_workspace(
    target_workspace: str,
    *,
    workspace_dir: Path | str | None = None,
    snapshot_path: Path | str | None = None,
    snapshot: dict[str, Any] | None = None,
    current_payload_hash: str = "",
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve() if workspace_dir is not None else (repo_root() / "workspace").resolve()
    target = Path(snapshot_path) if snapshot_path is not None else workspace / "handoffs" / "WS-INPUTS" / "inputs_snapshot.json"
    loaded = dict(snapshot or {}) if isinstance(snapshot, dict) else {}
    if not loaded and target.exists():
        try:
            obj = json.loads(target.read_text(encoding="utf-8"))
            loaded = dict(obj) if isinstance(obj, dict) else {}
        except Exception:
            loaded = {}
    if not loaded:
        return {
            "state": "missing",
            "is_stale": True,
            "path": str(target),
            "current_payload_hash": str(current_payload_hash or ""),
            "snapshot_payload_hash": "",
            "banner": "Frozen inputs_snapshot не найден для downstream handoff.",
        }
    target_workspaces = tuple(str(item) for item in loaded.get("target_workspaces") or ())
    handoff_ids = dict(loaded.get("handoff_ids") or {})
    clean_target = str(target_workspace or "").strip()
    snapshot_hash = str(loaded.get("payload_hash") or loaded.get("snapshot_hash") or "").strip()
    if clean_target and target_workspaces and clean_target not in target_workspaces:
        return {
            "state": "invalid",
            "is_stale": True,
            "path": str(target),
            "current_payload_hash": str(current_payload_hash or ""),
            "snapshot_payload_hash": snapshot_hash,
            "banner": f"Frozen inputs_snapshot is not addressed to {clean_target}.",
        }
    if clean_target and handoff_ids and clean_target not in handoff_ids:
        return {
            "state": "invalid",
            "is_stale": True,
            "path": str(target),
            "current_payload_hash": str(current_payload_hash or ""),
            "snapshot_payload_hash": snapshot_hash,
            "banner": f"Frozen inputs_snapshot missing handoff_id for {clean_target}.",
        }
    is_stale = bool(current_payload_hash and snapshot_hash and snapshot_hash != str(current_payload_hash))
    return {
        "state": "stale" if is_stale else "current",
        "is_stale": is_stale,
        "path": str(target),
        "current_payload_hash": str(current_payload_hash or ""),
        "snapshot_payload_hash": snapshot_hash,
        "banner": (
            "Frozen inputs_snapshot устарел относительно текущего inputs hash."
            if is_stale
            else "Frozen inputs_snapshot доступен для downstream handoff."
        ),
    }


def flatten_field_specs() -> tuple[DesktopInputFieldSpec, ...]:
    fields: list[DesktopInputFieldSpec] = []
    for section in DESKTOP_INPUT_SECTIONS:
        fields.extend(section.fields)
    return tuple(fields)


def field_spec_map() -> dict[str, DesktopInputFieldSpec]:
    return {spec.key: spec for spec in flatten_field_specs()}


def desktop_field_section_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for section in DESKTOP_INPUT_SECTIONS:
        for spec in section.fields:
            mapping[spec.key] = section.title
    return mapping


def desktop_field_search_display_name(
    spec: DesktopInputFieldSpec,
    section_title: str,
) -> str:
    unit_suffix = f" ({spec.unit_label})" if str(spec.unit_label or "").strip() else ""
    return f"{spec.label}{unit_suffix} — {section_title}"


def build_desktop_section_field_search_items(section_title: str) -> list[dict[str, str]]:
    clean_section_title = str(section_title or "").strip()
    if not clean_section_title:
        return []
    for section in DESKTOP_INPUT_SECTIONS:
        if str(section.title or "").strip() != clean_section_title:
            continue
        return [
            {
                "key": spec.key,
                "label": spec.label,
                "section_title": section.title,
                "description": spec.description,
                "display": desktop_field_search_display_name(spec, section.title),
            }
            for spec in section.fields
            if str(spec.key or "").strip()
        ]
    return []


def _normalize_search_text(value: Any) -> str:
    raw = str(value or "").strip().lower()
    raw = raw.replace("ё", "е").replace("_", " ")
    raw = re.sub(r"\s+", " ", raw)
    return raw


def _desktop_field_search_aliases(spec: DesktopInputFieldSpec) -> tuple[str, ...]:
    key = str(spec.key or "").strip().lower()
    aliases: list[str] = []
    if key.startswith("static_trim"):
        aliases.extend(("статическая посадка", "static trim"))
    if key == "corner_loads_mode":
        aliases.extend(("распределение веса", "corner loads"))
    if key == "макс_число_внутренних_шагов_на_dt":
        aliases.append("лимит внутренних шагов")
    if key == "макс_шаг_интегрирования_с":
        aliases.append("шаг интегрирования")
    if key == "autoverif_enable":
        aliases.append("автопроверка")
    if key == "mechanics_selfcheck":
        aliases.append("самопроверка механики")
    if key == "механика_кинематика":
        aliases.append("кинематика подвески")
    if key == "использовать_паспорт_компонентов":
        aliases.extend(("component passport", "паспорт camozzi"))
    if key == "колесо_координата":
        aliases.extend(("режим колеса", "wheel coord"))
    if key == "газ_модель_теплоемкости":
        aliases.extend(("теплоемкость воздуха", "nist air"))
    if key == "пружина_по_цилиндру":
        aliases.extend(("опорный цилиндр", "spring cylinder"))
    return tuple(aliases)


def find_desktop_field_matches(
    query: str,
    *,
    limit: int = 12,
) -> list[dict[str, str]]:
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return []
    tokens = tuple(token for token in normalized_query.split(" ") if token)
    if not tokens:
        return []

    matches: list[tuple[int, str, dict[str, str]]] = []
    for section in DESKTOP_INPUT_SECTIONS:
        for spec in section.fields:
            label_text = _normalize_search_text(spec.label)
            section_text = _normalize_search_text(section.title)
            key_text = _normalize_search_text(spec.key)
            unit_text = _normalize_search_text(spec.unit_label)
            description_text = _normalize_search_text(spec.description)
            alias_text = _normalize_search_text(" ".join(_desktop_field_search_aliases(spec)))
            haystack = " ".join(
                (label_text, section_text, key_text, unit_text, description_text, alias_text)
            )
            if not all(token in haystack for token in tokens):
                continue
            score = 3
            if all(token in label_text for token in tokens):
                score = 0
            elif all(token in section_text for token in tokens):
                score = 1
            elif all(token in description_text for token in tokens):
                score = 2
            display = desktop_field_search_display_name(spec, section.title)
            matches.append(
                (
                    score,
                    display,
                    {
                        "key": spec.key,
                        "label": spec.label,
                        "section_title": section.title,
                        "description": spec.description,
                        "display": display,
                    },
                )
            )

    matches.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in matches[: max(1, int(limit))]]


def preview_surface_label_map() -> dict[str, str]:
    return dict(DESKTOP_PREVIEW_SURFACE_OPTIONS)


def preview_surface_label(surface_type: str) -> str:
    key = str(surface_type or "flat")
    return preview_surface_label_map().get(key, key)


def quick_preset_label_map() -> dict[str, str]:
    return {key: label for key, label, _desc in DESKTOP_QUICK_PRESET_OPTIONS}


def quick_preset_description_map() -> dict[str, str]:
    return {key: desc for key, _label, desc in DESKTOP_QUICK_PRESET_OPTIONS}


def quick_preset_label(preset_key: str) -> str:
    key = str(preset_key or "").strip()
    return quick_preset_label_map().get(key, key)


def quick_preset_description(preset_key: str) -> str:
    key = str(preset_key or "").strip()
    return quick_preset_description_map().get(key, "")


def run_preset_label_map() -> dict[str, str]:
    return {key: label for key, label, _desc in DESKTOP_RUN_PRESET_OPTIONS}


def run_preset_description_map() -> dict[str, str]:
    return {key: desc for key, _label, desc in DESKTOP_RUN_PRESET_OPTIONS}


def run_preset_label(preset_key: str) -> str:
    key = str(preset_key or "").strip()
    return run_preset_label_map().get(key, key)


def run_preset_description(preset_key: str) -> str:
    key = str(preset_key or "").strip()
    return run_preset_description_map().get(key, "")


def describe_desktop_run_mode(run_config: dict[str, Any]) -> dict[str, str]:
    current = dict(run_config or {})
    dt = max(0.0001, _safe_float(current, "dt", 0.003))
    t_end = max(0.1, _safe_float(current, "t_end", 1.6))
    record_full = _safe_bool(current, "record_full", False)

    if record_full or dt <= 0.0018 or t_end >= 2.2:
        mode_key = "detailed"
        mode_label = "подробно"
        note = "подходит для более внимательной проверки отклика и сохранения расширенного лога"
        cost_label = "дольше, но подробнее"
        cost_note = "времени и данных потребуется больше обычного"
        advice_label = "берите для финальной проверки"
        advice_note = "уместен перед сохранением результатов и разбором сложного поведения системы"
    elif dt <= 0.0035 and t_end <= 2.0:
        mode_key = "balanced"
        mode_label = "сбалансировано"
        note = "подходит для обычного рабочего прогона без лишней тяжести"
        cost_label = "рабочий баланс"
        cost_note = "затраты по времени и объёму данных остаются умеренными"
        advice_label = "берите для основной работы"
        advice_note = "это хороший режим по умолчанию для большинства инженерных проверок"
    else:
        mode_key = "fast"
        mode_label = "быстро"
        note = "подходит для короткой проверки перед более полным расчётом"
        cost_label = "быстро и легко"
        cost_note = "запуск обычно проходит быстрее и даёт меньше служебных данных"
        advice_label = "берите для первого sanity-check"
        advice_note = "удобно, когда нужно быстро понять, что конфигурация в целом живая"

    log_label = "включён" if record_full else "выключен"
    summary = (
        f"Ожидаемый режим: {mode_label}. "
        f"dt={dt:.4f} с; длительность={t_end:.1f} с; расширенный лог {log_label}; {note}."
    )
    cost_summary = f"Цена запуска: {cost_label}. {cost_note}."
    advice_summary = f"Совет: {advice_label}. {advice_note}."
    usage_summary = (
        f"Когда запускать: {advice_label}. "
        f"{advice_note}."
    )
    return {
        "mode_key": mode_key,
        "mode_label": mode_label,
        "cost_label": cost_label,
        "cost_summary": cost_summary,
        "advice_label": advice_label,
        "advice_summary": advice_summary,
        "usage_summary": usage_summary,
        "summary": summary,
    }


def desktop_section_status_label(status: str) -> str:
    key = str(status or "").strip().lower()
    if key == "ok":
        return "в норме"
    if key == "warn":
        return "требует внимания"
    return key or "—"


def _safe_float(payload: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(payload.get(key, default))
    except Exception:
        return float(default)


def _safe_bool(payload: dict[str, Any], key: str, default: bool = False) -> bool:
    try:
        return bool(payload.get(key, default))
    except Exception:
        return bool(default)


def _safe_choice(payload: dict[str, Any], key: str, default: str = "") -> str:
    try:
        return str(payload.get(key, default) or "").strip()
    except Exception:
        return str(default or "")


def evaluate_desktop_section_readiness(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    current = load_base_defaults()
    current.update(dict(payload or {}))
    rows: list[dict[str, Any]] = []

    geometry_issues: list[str] = []
    if _safe_float(current, "база") <= 0.0:
        geometry_issues.append("база")
    if _safe_float(current, "колея") <= 0.0:
        geometry_issues.append("колея")
    if _safe_float(current, "радиус_колеса_м") <= 0.0:
        geometry_issues.append("радиус колеса")
    if _safe_float(current, "wheel_width_m") <= 0.0:
        geometry_issues.append("ширина колеса")
    if _safe_float(current, "ход_штока") <= 0.0:
        geometry_issues.append("ход штока")
    if min(
        _safe_float(current, "длина_рамы"),
        _safe_float(current, "ширина_рамы"),
        _safe_float(current, "высота_рамы"),
    ) <= 0.0:
        geometry_issues.append("габариты рамы")
    rows.append(
        {
            "title": "Геометрия",
            "status": "warn" if geometry_issues else "ok",
            "summary": (
                "Проверьте: " + ", ".join(geometry_issues) + "."
                if geometry_issues
                else "Базовые размеры кузова, колёс и ходов заданы."
            ),
            "issues": geometry_issues,
        }
    )

    pneumatic_issues: list[str] = []
    if _safe_float(current, "объём_ресивера_1") <= 0.0 or _safe_float(current, "объём_ресивера_2") <= 0.0 or _safe_float(current, "объём_ресивера_3") <= 0.0:
        pneumatic_issues.append("объёмы ресиверов")
    if _safe_float(current, "объём_аккумулятора") <= 0.0:
        pneumatic_issues.append("объём аккумулятора")
    if min(
        _safe_float(current, "начальное_давление_Ресивер1"),
        _safe_float(current, "начальное_давление_Ресивер2"),
        _safe_float(current, "начальное_давление_Ресивер3"),
        _safe_float(current, "начальное_давление_аккумулятора"),
    ) <= 0.0:
        pneumatic_issues.append("стартовые давления")
    if _safe_float(current, "диаметр_штока_Ц1") >= _safe_float(current, "диаметр_поршня_Ц1"):
        pneumatic_issues.append("Ц1: шток не должен быть больше поршня")
    if _safe_float(current, "диаметр_штока_Ц2") >= _safe_float(current, "диаметр_поршня_Ц2"):
        pneumatic_issues.append("Ц2: шток не должен быть больше поршня")
    rows.append(
        {
            "title": "Пневматика",
            "status": "warn" if pneumatic_issues else "ok",
            "summary": (
                "Проверьте: " + ", ".join(pneumatic_issues) + "."
                if pneumatic_issues
                else "Давления, объёмы и размеры цилиндров выглядят согласованно."
            ),
            "issues": pneumatic_issues,
        }
    )

    mechanics_issues: list[str] = []
    if _safe_float(current, "масса_рамы") <= 0.0:
        mechanics_issues.append("масса рамы")
    if _safe_float(current, "масса_неподрессоренная_на_угол") <= 0.0:
        mechanics_issues.append("неподрессоренная масса")
    if _safe_float(current, "жёсткость_шины") <= 0.0:
        mechanics_issues.append("жёсткость шины")
    if _safe_float(current, "демпфирование_шины") <= 0.0:
        mechanics_issues.append("демпфирование шины")
    if _safe_float(current, "пружина_длина_свободная_м") <= 0.0:
        mechanics_issues.append("свободная длина пружины")
    if _safe_float(current, "пружина_масштаб") <= 0.0:
        mechanics_issues.append("масштаб пружины")
    if _safe_bool(current, "стабилизатор_вкл") and (
        _safe_float(current, "стабилизатор_перед_жесткость_Н_м") <= 0.0
        and _safe_float(current, "стабилизатор_зад_жесткость_Н_м") <= 0.0
    ):
        mechanics_issues.append("включён стабилизатор без жёсткости")
    rows.append(
        {
            "title": "Механика",
            "status": "warn" if mechanics_issues else "ok",
            "summary": (
                "Проверьте: " + ", ".join(mechanics_issues) + "."
                if mechanics_issues
                else "Массы, шины, пружина и стабилизаторы выглядят готовыми к запуску."
            ),
            "issues": mechanics_issues,
        }
    )

    static_issues: list[str] = []
    if _safe_float(current, "vx0_м_с") < 0.0:
        static_issues.append("начальная скорость")
    if _safe_choice(current, "corner_loads_mode") not in {"cg", "stiffness"}:
        static_issues.append("режим распределения веса")
    if _safe_bool(current, "static_trim_force") and not _safe_bool(current, "static_trim_enable"):
        static_issues.append("форсированный static trim без включённого поиска посадки")
    if _safe_choice(current, "static_trim_pneumo_mode") not in {"pressure", "mass", "polytropic"}:
        static_issues.append("режим static trim по пневматике")
    target_stroke = _safe_float(current, "zero_pose_target_stroke_frac", 0.5)
    if not (0.0 <= target_stroke <= 1.0):
        static_issues.append("целевая доля хода")
    tol_stroke = _safe_float(current, "zero_pose_tol_stroke_frac", 0.2)
    if not (0.0 <= tol_stroke <= 1.0):
        static_issues.append("допуск по доле хода")
    rows.append(
        {
            "title": "Статическая настройка",
            "status": "warn" if static_issues else "ok",
            "summary": (
                "Проверьте: " + ", ".join(static_issues) + "."
                if static_issues
                else "Стартовое состояние и статическая посадка выглядят согласованно."
            ),
            "issues": static_issues,
        }
    )

    component_issues: list[str] = []
    if _safe_choice(current, "механика_кинематика") not in {"dw2d", "dw2d_mounts", "mr", "table"}:
        component_issues.append("кинематика подвески")
    if _safe_choice(current, "колесо_координата") not in {"center", "contact"}:
        component_issues.append("режим колесо_координата")
    if _safe_choice(current, "пружина_по_цилиндру").upper() not in {"C1", "C2", "DELTA"}:
        component_issues.append("опорный цилиндр пружины")
    if _safe_bool(current, "enforce_camozzi_only") and not _safe_bool(current, "использовать_паспорт_компонентов"):
        component_issues.append("Camozzi-only контроль без паспорта компонентов")
    rows.append(
        {
            "title": "Компоненты",
            "status": "warn" if component_issues else "ok",
            "summary": (
                "Проверьте: " + ", ".join(component_issues) + "."
                if component_issues
                else "Кинематика, привязка пружины и паспорт компонентов согласованы."
            ),
            "issues": component_issues,
        }
    )

    reference_issues: list[str] = []
    if _safe_choice(current, "термодинамика") not in {"thermal", "isothermal", "adiabatic"}:
        reference_issues.append("режим термодинамики")
    if _safe_choice(current, "газ_модель_теплоемкости") not in {"constant", "nist_air"}:
        reference_issues.append("модель теплоёмкости воздуха")
    if min(
        _safe_float(current, "температура_окр_К"),
        _safe_float(current, "T_AIR_К"),
    ) <= 0.0:
        reference_issues.append("температурные reference-данные")
    if _safe_float(current, "макс_шаг_интегрирования_с") <= 0.0:
        reference_issues.append("максимальный шаг интегрирования")
    if _safe_float(current, "макс_число_внутренних_шагов_на_dt") < 1000.0:
        reference_issues.append("лимит внутренних шагов")
    if _safe_float(current, "пружина_длина_солид_м") < 0.0:
        reference_issues.append("сомкнутая длина пружины")
    if _safe_float(current, "пружина_запас_до_coil_bind_минимум_м") < 0.0:
        reference_issues.append("запас до смыкания витков")
    if (not _safe_bool(current, "autoverif_enable")) and (not _safe_bool(current, "mechanics_selfcheck")):
        reference_issues.append("выключены все инженерные проверки")
    rows.append(
        {
            "title": "Справочные данные",
            "status": "warn" if reference_issues else "ok",
            "summary": (
                "Проверьте: " + ", ".join(reference_issues) + "."
                if reference_issues
                else "Reference-режимы, температуры и инженерные проверки выглядят согласованно."
            ),
            "issues": reference_issues,
        }
    )

    return rows


def _fmt_mm_from_m(value_m: Any) -> str:
    try:
        return f"{float(value_m) * 1000.0:.0f} мм"
    except Exception:
        return "—"


def _fmt_m(value_m: Any, digits: int = 2) -> str:
    try:
        return f"{float(value_m):.{int(digits)}f} м"
    except Exception:
        return "—"


def _fmt_signed_m(value_m: Any, digits: int = 3) -> str:
    try:
        return f"{float(value_m):+.{int(digits)}f} м"
    except Exception:
        return "—"


def _fmt_liters(value_m3: Any) -> str:
    try:
        return f"{float(value_m3) * 1000.0:.1f} л"
    except Exception:
        return "—"


def _fmt_kpa(value_pa: Any) -> str:
    try:
        return f"{float(value_pa) * 0.001:.0f} кПа"
    except Exception:
        return "—"


def _fmt_temperature_k(value_k: Any) -> str:
    try:
        return f"{float(value_k):.0f} К"
    except Exception:
        return "—"


def _fmt_ms(value_s: Any) -> str:
    try:
        return f"{float(value_s) * 1000.0:.2f} мс"
    except Exception:
        return "—"


def _fmt_bool_flag(value: Any, true_label: str = "да", false_label: str = "нет") -> str:
    return true_label if bool(value) else false_label


def _issue_focus_entry(key: str, label: str, reason: str) -> dict[str, str]:
    return {
        "focus_key": str(key or "").strip(),
        "focus_label": str(label or "").strip(),
        "focus_reason": str(reason or "").strip(),
    }


_SECTION_DEFAULT_FOCUS_KEY = {
    section.title: (section.fields[0].key if section.fields else "")
    for section in DESKTOP_INPUT_SECTIONS
}


_SECTION_ISSUE_FOCUS_MAP = {
    "Геометрия": {
        "база": _issue_focus_entry(
            "база",
            "База",
            "База не задана или меньше нуля.",
        ),
        "колея": _issue_focus_entry(
            "колея",
            "Колея",
            "Колея не задана или меньше нуля.",
        ),
        "радиус колеса": _issue_focus_entry(
            "радиус_колеса_м",
            "Радиус колеса",
            "Радиус колеса должен быть положительным.",
        ),
        "ширина колеса": _issue_focus_entry(
            "wheel_width_m",
            "Ширина колеса",
            "Ширина колеса должна быть положительной.",
        ),
        "ход штока": _issue_focus_entry(
            "ход_штока",
            "Ход штока",
            "Ход штока должен быть положительным.",
        ),
        "габариты рамы": _issue_focus_entry(
            "длина_рамы",
            "Габариты рамы",
            "Хотя бы один из габаритов рамы не заполнен.",
        ),
    },
    "Пневматика": {
        "объёмы ресиверов": _issue_focus_entry(
            "объём_ресивера_1",
            "Объёмы ресиверов",
            "Хотя бы один ресивер имеет нулевой или отрицательный объём.",
        ),
        "объём аккумулятора": _issue_focus_entry(
            "объём_аккумулятора",
            "Объём аккумулятора",
            "Объём аккумулятора должен быть положительным.",
        ),
        "стартовые давления": _issue_focus_entry(
            "начальное_давление_Ресивер1",
            "Стартовые давления",
            "Хотя бы одно стартовое давление не задано.",
        ),
        "Ц1: шток не должен быть больше поршня": _issue_focus_entry(
            "диаметр_штока_Ц1",
            "Геометрия цилиндра Ц1",
            "Диаметр штока Ц1 не должен быть больше или равен диаметру поршня.",
        ),
        "Ц2: шток не должен быть больше поршня": _issue_focus_entry(
            "диаметр_штока_Ц2",
            "Геометрия цилиндра Ц2",
            "Диаметр штока Ц2 не должен быть больше или равен диаметру поршня.",
        ),
    },
    "Механика": {
        "масса рамы": _issue_focus_entry(
            "масса_рамы",
            "Масса рамы",
            "Масса рамы должна быть положительной.",
        ),
        "неподрессоренная масса": _issue_focus_entry(
            "масса_неподрессоренная_на_угол",
            "Неподрессоренная масса",
            "Неподрессоренная масса на угол должна быть положительной.",
        ),
        "жёсткость шины": _issue_focus_entry(
            "жёсткость_шины",
            "Жёсткость шины",
            "Жёсткость шины должна быть положительной.",
        ),
        "демпфирование шины": _issue_focus_entry(
            "демпфирование_шины",
            "Демпфирование шины",
            "Демпфирование шины должно быть положительным.",
        ),
        "свободная длина пружины": _issue_focus_entry(
            "пружина_длина_свободная_м",
            "Свободная длина пружины",
            "Свободная длина пружины должна быть положительной.",
        ),
        "масштаб пружины": _issue_focus_entry(
            "пружина_масштаб",
            "Масштаб пружины",
            "Масштаб пружины должен быть больше нуля.",
        ),
        "включён стабилизатор без жёсткости": _issue_focus_entry(
            "стабилизатор_перед_жесткость_Н_м",
            "Жёсткость стабилизатора",
            "Стабилизатор включён, но жёсткость не задана ни спереди, ни сзади.",
        ),
    },
    "Статическая настройка": {
        "начальная скорость": _issue_focus_entry(
            "vx0_м_с",
            "Начальная скорость",
            "Начальная скорость не может быть отрицательной.",
        ),
        "режим распределения веса": _issue_focus_entry(
            "corner_loads_mode",
            "Распределение веса по углам",
            "Нужно выбрать допустимый режим распределения веса.",
        ),
        "форсированный static trim без включённого поиска посадки": _issue_focus_entry(
            "static_trim_enable",
            "Static trim",
            "Форсирование static trim включено без основного режима поиска посадки.",
        ),
        "режим static trim по пневматике": _issue_focus_entry(
            "static_trim_pneumo_mode",
            "Режим static trim",
            "Нужно выбрать допустимый режим коррекции пневматики.",
        ),
        "целевая доля хода": _issue_focus_entry(
            "zero_pose_target_stroke_frac",
            "Целевая доля хода",
            "Целевая доля хода должна быть в диапазоне от 0 до 1.",
        ),
        "допуск по доле хода": _issue_focus_entry(
            "zero_pose_tol_stroke_frac",
            "Допуск по доле хода",
            "Допуск по доле хода должен быть в диапазоне от 0 до 1.",
        ),
    },
    "Компоненты": {
        "кинематика подвески": _issue_focus_entry(
            "механика_кинематика",
            "Кинематика подвески",
            "Нужно выбрать поддерживаемый режим кинематики.",
        ),
        "режим колесо_координата": _issue_focus_entry(
            "колесо_координата",
            "Режим колесо_координата",
            "Нужно выбрать допустимую интерпретацию координаты колеса.",
        ),
        "опорный цилиндр пружины": _issue_focus_entry(
            "пружина_по_цилиндру",
            "Опорный цилиндр пружины",
            "Пружина должна быть привязана к допустимому цилиндру.",
        ),
        "Camozzi-only контроль без паспорта компонентов": _issue_focus_entry(
            "использовать_паспорт_компонентов",
            "Паспорт компонентов",
            "Camozzi-only контроль требует включённого паспорта компонентов.",
        ),
    },
    "Справочные данные": {
        "режим термодинамики": _issue_focus_entry(
            "термодинамика",
            "Режим термодинамики",
            "Нужно выбрать поддерживаемый режим термодинамики.",
        ),
        "модель теплоёмкости воздуха": _issue_focus_entry(
            "газ_модель_теплоемкости",
            "Модель теплоёмкости",
            "Нужно выбрать поддерживаемую модель теплоёмкости воздуха.",
        ),
        "температурные reference-данные": _issue_focus_entry(
            "температура_окр_К",
            "Температуры reference-данных",
            "Температуры воздуха и окружения должны быть положительными.",
        ),
        "максимальный шаг интегрирования": _issue_focus_entry(
            "макс_шаг_интегрирования_с",
            "Максимальный шаг интегрирования",
            "Максимальный шаг интегрирования должен быть положительным.",
        ),
        "лимит внутренних шагов": _issue_focus_entry(
            "макс_число_внутренних_шагов_на_dt",
            "Лимит внутренних шагов",
            "Лимит внутренних шагов слишком мал для устойчивого расчёта.",
        ),
        "сомкнутая длина пружины": _issue_focus_entry(
            "пружина_длина_солид_м",
            "Сомкнутая длина пружины",
            "Сомкнутая длина пружины не может быть отрицательной.",
        ),
        "запас до смыкания витков": _issue_focus_entry(
            "пружина_запас_до_coil_bind_минимум_м",
            "Запас до смыкания витков",
            "Запас до смыкания витков не может быть отрицательным.",
        ),
        "выключены все инженерные проверки": _issue_focus_entry(
            "autoverif_enable",
            "Инженерные проверки",
            "Хотя бы одна инженерная проверка должна оставаться включённой.",
        ),
    },
}


def _desktop_section_issue_focus(
    title: str,
    issues: Any,
) -> dict[str, str]:
    section_title = str(title or "").strip()
    section_map = _SECTION_ISSUE_FOCUS_MAP.get(section_title, {})
    default_focus_key = str(_SECTION_DEFAULT_FOCUS_KEY.get(section_title) or "").strip()
    issue_list = [
        str(item or "").strip()
        for item in (issues if isinstance(issues, (list, tuple)) else ())
        if str(item or "").strip()
    ]
    for issue in issue_list:
        focus = section_map.get(issue)
        if focus:
            return dict(focus)
    if issue_list:
        first_issue = issue_list[0]
        return _issue_focus_entry(
            default_focus_key,
            first_issue,
            f"Проверьте пункт: {first_issue}.",
        )
    return _issue_focus_entry("", "", "")


def _desktop_section_issue_entries(
    title: str,
    issues: Any,
) -> list[dict[str, str]]:
    section_title = str(title or "").strip()
    section_map = _SECTION_ISSUE_FOCUS_MAP.get(section_title, {})
    default_focus_key = str(_SECTION_DEFAULT_FOCUS_KEY.get(section_title) or "").strip()
    issue_list = [
        str(item or "").strip()
        for item in (issues if isinstance(issues, (list, tuple)) else ())
        if str(item or "").strip()
    ]
    entries: list[dict[str, str]] = []
    for issue in issue_list:
        focus = section_map.get(issue)
        if focus:
            entries.append(dict(focus))
            continue
        entries.append(
            _issue_focus_entry(
                default_focus_key,
                issue,
                f"Проверьте пункт: {issue}.",
            )
        )
    return entries


def build_desktop_section_summary_cards(
    payload: dict[str, Any],
) -> list[dict[str, object]]:
    current = load_base_defaults()
    current.update(dict(payload or {}))
    readiness_rows = evaluate_desktop_section_readiness(current)
    readiness_by_title = {
        str(row.get("title") or ""): row for row in readiness_rows
    }

    def _status_and_detail(title: str) -> tuple[str, str]:
        row = readiness_by_title.get(title, {})
        return (
            str(row.get("status") or ""),
            str(row.get("summary") or "").strip(),
        )

    def _focus(title: str) -> dict[str, str]:
        row = readiness_by_title.get(title, {})
        return _desktop_section_issue_focus(title, row.get("issues"))

    geometry_status, geometry_detail = _status_and_detail("Геометрия")
    pneumatic_status, pneumatic_detail = _status_and_detail("Пневматика")
    mechanics_status, mechanics_detail = _status_and_detail("Механика")
    static_status, static_detail = _status_and_detail("Статическая настройка")
    components_status, components_detail = _status_and_detail("Компоненты")
    reference_status, reference_detail = _status_and_detail("Справочные данные")
    geometry_focus = _focus("Геометрия")
    pneumatic_focus = _focus("Пневматика")
    mechanics_focus = _focus("Механика")
    static_focus = _focus("Статическая настройка")
    components_focus = _focus("Компоненты")
    reference_focus = _focus("Справочные данные")

    return [
        {
            "title": "Геометрия",
            "status": geometry_status,
            "headline": (
                f"База {_fmt_m(current.get('база'))}; колея {_fmt_m(current.get('колея'))}; "
                f"ход {_fmt_mm_from_m(current.get('ход_штока'))}; "
                f"колесо R{_fmt_mm_from_m(current.get('радиус_колеса_м'))} / {_fmt_mm_from_m(current.get('wheel_width_m'))}."
            ),
            "details": geometry_detail,
            **geometry_focus,
        },
        {
            "title": "Пневматика",
            "status": pneumatic_status,
            "headline": (
                f"Р1 {_fmt_kpa(current.get('начальное_давление_Ресивер1'))}; "
                f"Р2 {_fmt_kpa(current.get('начальное_давление_Ресивер2'))}; "
                f"Р3 {_fmt_kpa(current.get('начальное_давление_Ресивер3'))}; "
                f"аккум {_fmt_kpa(current.get('начальное_давление_аккумулятора'))}."
            ),
            "details": (
                f"Объёмы: {_fmt_liters(current.get('объём_ресивера_1'))}, "
                f"{_fmt_liters(current.get('объём_ресивера_2'))}, "
                f"{_fmt_liters(current.get('объём_ресивера_3'))}, "
                f"{_fmt_liters(current.get('объём_аккумулятора'))}. {pneumatic_detail}"
            ),
            **pneumatic_focus,
        },
        {
            "title": "Механика",
            "status": mechanics_status,
            "headline": (
                f"Рама {_safe_float(current, 'масса_рамы'):.0f} кг; "
                f"угол {_safe_float(current, 'масса_неподрессоренная_на_угол'):.0f} кг; "
                f"шина {_safe_float(current, 'жёсткость_шины'):.0f} Н/м; "
                f"пружина {_fmt_mm_from_m(current.get('пружина_длина_свободная_м'))}."
            ),
            "details": (
                f"Стабилизатор {_fmt_bool_flag(current.get('стабилизатор_вкл'), 'включён', 'выключен')}; "
                f"масштаб пружины {_safe_float(current, 'пружина_масштаб', 0.0):.2f}. "
                f"{mechanics_detail}"
            ),
            **mechanics_focus,
        },
        {
            "title": "Статическая настройка",
            "status": static_status,
            "headline": (
                f"vx0 {_safe_float(current, 'vx0_м_с', 0.0):.2f} м/с; "
                f"CG X {_fmt_signed_m(current.get('cg_x_м'))}; "
                f"CG Y {_fmt_signed_m(current.get('cg_y_м'))}; "
                f"corner loads {str(current.get('corner_loads_mode') or '—')}."
            ),
            "details": (
                f"Static trim {_fmt_bool_flag(current.get('static_trim_enable'), 'включён', 'выключен')}; "
                f"pneumo mode {str(current.get('static_trim_pneumo_mode') or '—')}; "
                f"цель {float(_safe_float(current, 'zero_pose_target_stroke_frac', 0.0)):.2f} "
                f"+/- {float(_safe_float(current, 'zero_pose_tol_stroke_frac', 0.0)):.2f}. "
                f"{static_detail}"
            ),
            **static_focus,
        },
        {
            "title": "Компоненты",
            "status": components_status,
            "headline": (
                f"Кинематика {str(current.get('механика_кинематика') or '—')}; "
                f"колесо_координата {str(current.get('колесо_координата') or '—')}; "
                f"паспорт {_fmt_bool_flag(current.get('использовать_паспорт_компонентов'))}; "
                f"Camozzi-only {_fmt_bool_flag(current.get('enforce_camozzi_only'))}."
            ),
            "details": (
                f"Пружина привязана к {str(current.get('пружина_по_цилиндру') or '—')}; "
                f"согласование с цилиндром {_fmt_bool_flag(current.get('пружина_геометрия_согласовать_с_цилиндром'))}. "
                f"{components_detail}"
            ),
            **components_focus,
        },
        {
            "title": "Справочные данные",
            "status": reference_status,
            "headline": (
                f"Термо {str(current.get('термодинамика') or '—')} / "
                f"{str(current.get('газ_модель_теплоемкости') or '—')}; "
                f"T_air {_fmt_temperature_k(current.get('T_AIR_К'))}; "
                f"T_окр {_fmt_temperature_k(current.get('температура_окр_К'))}; "
                f"dt_max {_fmt_ms(current.get('макс_шаг_интегрирования_с'))}."
            ),
            "details": (
                f"Autoverif {_fmt_bool_flag(current.get('autoverif_enable'))}; "
                f"mech selfcheck {_fmt_bool_flag(current.get('mechanics_selfcheck'))}; "
                f"запас до смыкания {_fmt_mm_from_m(current.get('пружина_запас_до_coil_bind_минимум_м'))}. "
                f"{reference_detail}"
            ),
            **reference_focus,
        },
    ]


def _coerce_spec_base_value(spec: DesktopInputFieldSpec, base_value: Any) -> Any:
    if spec.control == "bool":
        return bool(base_value)
    if spec.control == "choice":
        raw = str(base_value or "").strip()
        if spec.choices and raw not in spec.choices:
            return spec.choices[0]
        return raw
    if spec.control == "int":
        min_base = spec.to_base(spec.min_value) if spec.min_value is not None else None
        max_base = spec.to_base(spec.max_value) if spec.max_value is not None else None
        try:
            value = int(round(float(base_value)))
        except Exception:
            value = int(round(float(min_base or 0)))
        if min_base is not None:
            value = max(value, int(round(float(min_base))))
        if max_base is not None:
            value = min(value, int(round(float(max_base))))
        return value
    min_base = spec.to_base(spec.min_value) if spec.min_value is not None else None
    max_base = spec.to_base(spec.max_value) if spec.max_value is not None else None
    try:
        value = float(base_value)
    except Exception:
        value = float(min_base or 0.0)
    if min_base is not None:
        value = max(value, float(min_base))
    if max_base is not None:
        value = min(value, float(max_base))
    return value


def _scaled_payload_value(payload: dict[str, Any], key: str, factor: float) -> Any:
    specs = field_spec_map()
    spec = specs[key]
    base_value = payload.get(key)
    try:
        current = float(base_value)
    except Exception:
        current = float(spec.min_value or 0.0)
    return _coerce_spec_base_value(spec, current * float(factor))


def apply_desktop_quick_preset(
    payload: dict[str, Any],
    preset_key: str,
) -> tuple[dict[str, Any], list[str]]:
    current = dict(payload or {})
    updated = dict(current)
    changed_keys: list[str] = []

    def _set_scaled(key: str, factor: float) -> None:
        new_value = _scaled_payload_value(updated, key, factor)
        if updated.get(key) != new_value:
            updated[key] = new_value
            changed_keys.append(key)

    key = str(preset_key or "").strip()
    if key == "soft_ride":
        _set_scaled("пружина_масштаб", 0.90)
        _set_scaled("жёсткость_шины", 0.92)
        _set_scaled("демпфирование_шины", 0.95)
        _set_scaled("стабилизатор_перед_жесткость_Н_м", 0.80)
        _set_scaled("стабилизатор_зад_жесткость_Н_м", 0.80)
        return updated, changed_keys
    if key == "firm_ride":
        _set_scaled("пружина_масштаб", 1.10)
        _set_scaled("жёсткость_шины", 1.08)
        _set_scaled("демпфирование_шины", 1.05)
        _set_scaled("стабилизатор_перед_жесткость_Н_м", 1.20)
        _set_scaled("стабилизатор_зад_жесткость_Н_м", 1.20)
        return updated, changed_keys
    if key == "pressure_up":
        for pressure_key in (
            "начальное_давление_Ресивер1",
            "начальное_давление_Ресивер2",
            "начальное_давление_Ресивер3",
            "начальное_давление_аккумулятора",
        ):
            _set_scaled(pressure_key, 1.08)
        return updated, changed_keys
    if key == "pressure_down":
        for pressure_key in (
            "начальное_давление_Ресивер1",
            "начальное_давление_Ресивер2",
            "начальное_давление_Ресивер3",
            "начальное_давление_аккумулятора",
        ):
            _set_scaled(pressure_key, 0.92)
        return updated, changed_keys
    if key == "draft_calc":
        _set_scaled("макс_шаг_интегрирования_с", 1.25)
        _set_scaled("макс_число_внутренних_шагов_на_dt", 0.75)
        return updated, changed_keys
    if key == "precise_calc":
        _set_scaled("макс_шаг_интегрирования_с", 0.80)
        _set_scaled("макс_число_внутренних_шагов_на_dt", 1.25)
        return updated, changed_keys
    return updated, changed_keys


def apply_desktop_run_preset(
    run_config: dict[str, Any],
    preset_key: str,
    *,
    scenario_key: str = "worldroad",
) -> tuple[dict[str, Any], list[str]]:
    current = dict(run_config or {})
    updated = dict(current)
    changed_keys: list[str] = []

    def _set_value(key: str, value: Any) -> None:
        if updated.get(key) != value:
            updated[key] = value
            changed_keys.append(key)

    scenario = str(scenario_key or "worldroad").strip().lower() or "worldroad"
    key = str(preset_key or "").strip()
    if key == "sanity_check":
        _set_value("dt", 0.006)
        _set_value("t_end", 0.8 if scenario == "worldroad" else 1.0)
        _set_value("record_full", False)
        return updated, changed_keys
    if key == "draft_run":
        _set_value("dt", 0.003)
        _set_value("t_end", 1.6 if scenario == "worldroad" else 1.8)
        _set_value("record_full", False)
        return updated, changed_keys
    if key == "precise_run":
        _set_value("dt", 0.0015)
        _set_value("t_end", 2.4 if scenario == "worldroad" else 2.0)
        _set_value("record_full", True)
        return updated, changed_keys
    return updated, changed_keys


def build_desktop_preview_surface(
    *,
    surface_type: str,
    amplitude_m: float = 0.02,
    wavelength_or_width_m: float = 2.0,
    start_m: float = 5.0,
    angle_deg: float = 0.0,
    shape_k: float = 1.0,
) -> str | dict[str, Any]:
    key = str(surface_type or "flat").strip().lower() or "flat"
    amplitude = max(0.0, float(amplitude_m))
    span = max(0.01, float(wavelength_or_width_m))
    start = float(start_m)
    angle = float(angle_deg)
    shape = max(0.1, float(shape_k))

    if key == "flat":
        return "flat"
    if key == "sine_x":
        return {
            "type": "sine_x",
            "A": amplitude,
            "wavelength": span,
        }
    if key == "bump":
        return {
            "type": "bump",
            "h": amplitude,
            "w": span,
            "x0": start,
        }
    if key == "ridge_cosine_bump":
        return {
            "type": "ridge_cosine_bump",
            "h": amplitude,
            "w": span,
            "u0": start,
            "angle_deg": angle,
            "k": shape,
        }
    return "flat"


def desktop_field_values_match(
    spec: DesktopInputFieldSpec,
    current_value: Any,
    reference_value: Any,
) -> bool:
    try:
        if spec.control == "bool":
            return bool(current_value) is bool(reference_value)
        if spec.control == "choice":
            return str(current_value or "") == str(reference_value or "")
        if spec.control == "int":
            return int(round(float(current_value))) == int(round(float(reference_value)))
        cur = float(current_value)
        ref = float(reference_value)
        tol = max(float(spec.step or 0.0) * 0.5, 1e-12)
        return abs(cur - ref) <= tol
    except Exception:
        return current_value == reference_value


def build_desktop_profile_diff(
    current_payload: dict[str, Any],
    reference_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    current_obj = dict(current_payload or {})
    reference_obj = dict(reference_payload or {})
    for spec in flatten_field_specs():
        current_value = current_obj.get(spec.key)
        reference_value = reference_obj.get(spec.key)
        if desktop_field_values_match(spec, current_value, reference_value):
            continue
        diffs.append(
            {
                "key": spec.key,
                "label": spec.label,
                "unit_label": spec.unit_label,
                "current": current_value,
                "reference": reference_value,
            }
        )
    return diffs


def _format_issue_count(count: int) -> str:
    value = max(0, int(count))
    tail10 = value % 10
    tail100 = value % 100
    if tail10 == 1 and tail100 != 11:
        return f"{value} замечание"
    if tail10 in {2, 3, 4} and tail100 not in {12, 13, 14}:
        return f"{value} замечания"
    return f"{value} замечаний"


def build_desktop_section_issue_cards(
    payload: dict[str, Any],
) -> list[dict[str, object]]:
    current = load_base_defaults()
    current.update(dict(payload or {}))
    readiness_rows = evaluate_desktop_section_readiness(current)
    readiness_by_title = {
        str(row.get("title") or "").strip(): row for row in readiness_rows
    }

    cards: list[dict[str, object]] = []
    for section in DESKTOP_INPUT_SECTIONS:
        row = readiness_by_title.get(section.title, {})
        entries = _desktop_section_issue_entries(section.title, row.get("issues"))
        issue_labels: list[str] = []
        issue_keys: list[str] = []
        issue_reasons: list[str] = []
        for entry in entries:
            label = str(entry.get("focus_label") or "").strip()
            key = str(entry.get("focus_key") or "").strip()
            reason = str(entry.get("focus_reason") or "").strip()
            if label and label not in issue_labels:
                issue_labels.append(label)
            if key and key not in issue_keys:
                issue_keys.append(key)
            if reason and reason not in issue_reasons:
                issue_reasons.append(reason)
        issue_count = len(entries)
        if issue_count <= 0:
            summary = "замечаний нет"
        else:
            preview = ", ".join(issue_labels[:2]).strip(", ")
            suffix = f" и ещё {issue_count - 2}" if issue_count > 2 else ""
            summary = f"{_format_issue_count(issue_count)}: {preview}{suffix}".strip(": ")
        cards.append(
            {
                "title": section.title,
                "issue_count": issue_count,
                "issue_keys": issue_keys,
                "issue_labels": issue_labels,
                "issue_reasons": issue_reasons,
                "focus_key": issue_keys[0] if issue_keys else "",
                "focus_label": issue_labels[0] if issue_labels else "",
                "focus_reason": issue_reasons[0] if issue_reasons else "",
                "summary": summary,
                "status": "warn" if issue_count > 0 else "ok",
            }
        )
    return cards


def _format_changed_params_count(count: int) -> str:
    value = max(0, int(count))
    tail10 = value % 10
    tail100 = value % 100
    if tail10 == 1 and tail100 != 11:
        return f"{value} параметр"
    if tail10 in {2, 3, 4} and tail100 not in {12, 13, 14}:
        return f"{value} параметра"
    return f"{value} параметров"


def build_desktop_section_change_cards(
    current_payload: dict[str, Any],
    reference_payload: dict[str, Any],
) -> list[dict[str, object]]:
    current_obj = load_base_defaults()
    current_obj.update(dict(current_payload or {}))
    reference_obj = load_base_defaults()
    reference_obj.update(dict(reference_payload or {}))

    section_map = desktop_field_section_map()
    grouped: dict[str, list[dict[str, Any]]] = {
        section.title: [] for section in DESKTOP_INPUT_SECTIONS
    }
    for diff in build_desktop_profile_diff(current_obj, reference_obj):
        section_title = section_map.get(str(diff.get("key") or "").strip())
        if not section_title:
            continue
        grouped.setdefault(section_title, []).append(diff)

    cards: list[dict[str, object]] = []
    for section in DESKTOP_INPUT_SECTIONS:
        items = grouped.get(section.title, [])
        labels: list[str] = []
        keys: list[str] = []
        for item in items:
            label = str(item.get("label") or item.get("key") or "").strip()
            key = str(item.get("key") or "").strip()
            if label and label not in labels:
                labels.append(label)
            if key and key not in keys:
                keys.append(key)
        changed_count = len(keys)
        if changed_count <= 0:
            summary = "без изменений"
        else:
            preview = ", ".join(labels[:2]).strip(", ")
            suffix = f" и ещё {changed_count - 2}" if changed_count > 2 else ""
            summary = f"{_format_changed_params_count(changed_count)}: {preview}{suffix}".strip(": ")
        cards.append(
            {
                "title": section.title,
                "changed_count": changed_count,
                "changed_keys": keys,
                "changed_labels": labels,
                "focus_key": keys[0] if keys else "",
                "focus_label": labels[0] if labels else "",
                "summary": summary,
                "status": "changed" if changed_count > 0 else "clean",
            }
        )
    return cards


def sanitize_desktop_profile_name(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return "desktop_profile"
    safe = re.sub(r'[<>:"/\\\\|?*]+', "_", raw)
    safe = re.sub(r"\s+", "_", safe)
    safe = re.sub(r"_+", "_", safe).strip("._ ")
    return safe or "desktop_profile"


def desktop_profile_path(name: str) -> Path:
    safe = sanitize_desktop_profile_name(name)
    return (desktop_profile_dir_path() / f"{safe}.json").resolve()


def list_desktop_profile_paths() -> list[Path]:
    root = desktop_profile_dir_path()
    if not root.exists():
        return []
    return sorted(
        [path.resolve() for path in root.glob("*.json") if path.is_file()],
        key=lambda path: path.name.lower(),
    )


def desktop_profile_display_name(path: Path | str) -> str:
    target = Path(path)
    return target.stem.replace("_", " ").strip() or target.stem


def desktop_snapshot_display_name(path: Path | str) -> str:
    target = Path(path)
    stem = target.stem
    parts = stem.split("__", 1)
    if len(parts) == 2:
        stamp, label = parts
        return f"{stamp} · {label.replace('_', ' ').strip()}"
    return stem.replace("_", " ").strip() or stem


def desktop_snapshot_path(name: str, *, stamp: str | None = None) -> Path:
    safe = sanitize_desktop_profile_name(name)
    stamp_value = str(stamp or datetime.now().strftime("%Y%m%d_%H%M%S")).strip() or datetime.now().strftime("%Y%m%d_%H%M%S")
    return (desktop_snapshot_dir_path() / f"{stamp_value}__{safe}.json").resolve()


def list_desktop_snapshot_paths() -> list[Path]:
    root = desktop_snapshot_dir_path()
    if not root.exists():
        return []
    return sorted(
        [path.resolve() for path in root.glob("*.json") if path.is_file()],
        key=lambda path: path.name.lower(),
        reverse=True,
    )


def save_desktop_profile(name: str, payload: dict[str, Any]) -> Path:
    target = desktop_profile_path(name)
    return save_base_payload(target, payload)


def save_desktop_snapshot(name: str, payload: dict[str, Any]) -> Path:
    target = desktop_snapshot_path(name)
    return save_base_payload(target, payload)


def desktop_run_summary_path(path: Path | str) -> Path:
    target = Path(path).resolve()
    if target.suffix.lower() == ".json":
        return target
    return (target / "run_summary.json").resolve()


def list_desktop_run_dirs() -> list[Path]:
    root = desktop_runs_dir_path()
    if not root.exists():
        return []
    return sorted(
        [path.resolve() for path in root.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def load_desktop_run_summary(path: Path | str) -> dict[str, Any]:
    target = desktop_run_summary_path(path)
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Desktop run summary must contain a JSON object: {target}")
    return raw


def load_desktop_profile(path: Path | str) -> dict[str, Any]:
    target = Path(path).resolve()
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Desktop profile must contain a JSON object: {target}")
    return raw


def load_desktop_snapshot(path: Path | str) -> dict[str, Any]:
    target = Path(path).resolve()
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Desktop snapshot must contain a JSON object: {target}")
    return raw


def delete_desktop_profile(path: Path | str) -> Path:
    target = Path(path).resolve()
    if target.exists():
        target.unlink()
    return target


def load_base_defaults() -> dict[str, Any]:
    return json.loads(default_base_json_path().read_text(encoding="utf-8"))


def load_base_with_defaults(path: Path | None = None) -> dict[str, Any]:
    base = load_base_defaults()
    target = Path(path).resolve() if path else default_base_json_path()
    if target != default_base_json_path() and target.exists():
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                base.update(raw)
        except Exception:
            pass
    return base


def save_base_payload(path: Path, payload: dict[str, Any]) -> Path:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


__all__ = [
    "DESKTOP_INPUT_SECTIONS",
    "DesktopInputFieldSpec",
    "DesktopInputSection",
    "DESKTOP_PREVIEW_SURFACE_OPTIONS",
    "DESKTOP_QUICK_PRESET_OPTIONS",
    "DESKTOP_RUN_PRESET_OPTIONS",
    "apply_desktop_quick_preset",
    "apply_desktop_run_preset",
    "build_desktop_preview_surface",
    "build_desktop_profile_diff",
    "build_desktop_section_issue_cards",
    "build_desktop_section_field_search_items",
    "build_desktop_section_change_cards",
    "delete_desktop_profile",
    "desktop_section_status_label",
    "build_desktop_section_summary_cards",
    "desktop_field_values_match",
    "desktop_profile_dir_path",
    "desktop_profile_display_name",
    "desktop_profile_path",
    "desktop_snapshot_dir_path",
    "desktop_snapshot_display_name",
    "desktop_snapshot_path",
    "describe_desktop_inputs_handoff_for_workspace",
    "evaluate_desktop_section_readiness",
    "default_base_json_path",
    "default_ranges_json_path",
    "default_suite_json_path",
    "default_working_copy_path",
    "desktop_field_search_display_name",
    "desktop_field_section_map",
    "describe_desktop_run_mode",
    "field_spec_map",
    "find_desktop_field_matches",
    "flatten_field_specs",
    "list_desktop_profile_paths",
    "list_desktop_snapshot_paths",
    "load_base_defaults",
    "load_desktop_profile",
    "load_desktop_snapshot",
    "load_base_with_defaults",
    "preview_surface_label",
    "preview_surface_label_map",
    "quick_preset_description",
    "quick_preset_description_map",
    "quick_preset_label",
    "quick_preset_label_map",
    "run_preset_description",
    "run_preset_description_map",
    "run_preset_label",
    "run_preset_label_map",
    "repo_root",
    "sanitize_desktop_profile_name",
    "save_desktop_profile",
    "save_desktop_snapshot",
    "save_base_payload",
]
