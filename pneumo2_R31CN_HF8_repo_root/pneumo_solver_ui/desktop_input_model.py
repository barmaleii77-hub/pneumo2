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

    def to_ui(self, base_value: Any) -> Any:
        if self.control == "bool":
            return bool(base_value)
        if self.control == "choice":
            return str(base_value or (self.choices[0] if self.choices else ""))
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
            return str(ui_value or "")
        if self.control == "int":
            try:
                return int(round(float(ui_value) / float(self.ui_scale) - float(self.ui_offset)))
            except Exception:
                return int(self.min_value or 0)
        try:
            return float(ui_value) / float(self.ui_scale) - float(self.ui_offset)
        except Exception:
            return 0.0


@dataclass(frozen=True)
class DesktopInputSection:
    title: str
    description: str
    fields: tuple[DesktopInputFieldSpec, ...] = field(default_factory=tuple)


DESKTOP_INPUT_SECTIONS: tuple[DesktopInputSection, ...] = (
    DesktopInputSection(
        title="Геометрия",
        description="Базовые размеры машины и посадка кузова.",
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
        description="Исходные давления, объёмы и размеры пневмоцилиндров.",
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
        description="Массы, шины, пружина и стабилизаторы.",
        fields=(
            DesktopInputFieldSpec("масса_рамы", "Масса рамы", "кг", "Подрессоренная масса кузова/рамы.", min_value=50.0, max_value=5000.0, step=10.0, digits=1),
            DesktopInputFieldSpec("масса_неподрессоренная_на_угол", "Неподрессоренная масса на угол", "кг", "Масса колеса, ступицы и рычагов на один угол.", min_value=1.0, max_value=250.0, step=1.0, digits=1),
            DesktopInputFieldSpec("жёсткость_шины", "Жёсткость шины", "Н/м", "Вертикальная жёсткость шины.", min_value=10000.0, max_value=1000000.0, step=1000.0, digits=0),
            DesktopInputFieldSpec("демпфирование_шины", "Демпфирование шины", "Н·с/м", "Вертикальное демпфирование шины.", min_value=100.0, max_value=50000.0, step=100.0, digits=0),
            DesktopInputFieldSpec("пружина_масштаб", "Масштаб пружины", "коэф.", "Масштабирует табличную характеристику пружины.", min_value=0.05, max_value=3.0, step=0.01, digits=2),
            DesktopInputFieldSpec("стабилизатор_вкл", "Стабилизатор включён", "", "Включает учёт стабилизатора в модели.", control="bool"),
            DesktopInputFieldSpec("стабилизатор_перед_жесткость_Н_м", "Жёсткость переднего стабилизатора", "Н/м", "Эквивалентная жёсткость переднего стабилизатора.", min_value=0.0, max_value=500000.0, step=1000.0, digits=0),
            DesktopInputFieldSpec("стабилизатор_зад_жесткость_Н_м", "Жёсткость заднего стабилизатора", "Н/м", "Эквивалентная жёсткость заднего стабилизатора.", min_value=0.0, max_value=500000.0, step=1000.0, digits=0),
        ),
    ),
    DesktopInputSection(
        title="Настройки расчёта",
        description="Скорость, интегрирование и служебные режимы модели.",
        fields=(
            DesktopInputFieldSpec("vx0_м_с", "Начальная скорость", "м/с", "Начальная продольная скорость модели.", min_value=0.0, max_value=80.0, step=0.1, digits=2),
            DesktopInputFieldSpec("макс_шаг_интегрирования_с", "Максимальный шаг интегрирования", "мс", "Ограничение шага интегратора.", min_value=0.01, max_value=10.0, step=0.01, ui_scale=1000.0, digits=2),
            DesktopInputFieldSpec("макс_число_внутренних_шагов_на_dt", "Макс. внутренних шагов на dt", "", "Защита от зависания интегратора на одном шаге dt.", control="int", min_value=1000, max_value=1000000, step=1000, digits=0),
            DesktopInputFieldSpec("static_trim_enable", "Искать статическую посадку", "", "Перед основным расчётом подобрать статическое равновесие.", control="bool"),
            DesktopInputFieldSpec("static_trim_force", "Форсировать статическую посадку", "", "Принудительно выполнять static trim даже при существующем состоянии.", control="bool"),
            DesktopInputFieldSpec("autoverif_enable", "Включить автопроверку", "", "Проверять физические и численные ограничения после расчёта.", control="bool"),
            DesktopInputFieldSpec("mechanics_selfcheck", "Включить самопроверку механики", "", "Проверять кинематику и механические ограничения.", control="bool"),
            DesktopInputFieldSpec("термодинамика", "Режим термодинамики", "", "Модель газа: упрощённая или тепловая.", control="choice", choices=("thermal", "isothermal")),
            DesktopInputFieldSpec("механика_кинематика", "Кинематика подвески", "", "Активный вариант кинематики в модели.", control="choice", choices=("dw2d", "mr")),
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


def default_ranges_json_path() -> Path:
    return (Path(__file__).resolve().parent / "default_ranges.json").resolve()


def default_suite_json_path() -> Path:
    return (Path(__file__).resolve().parent / "default_suite.json").resolve()


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
    if _safe_float(current, "ход_штока") <= 0.0:
        geometry_issues.append("ход штока")
    rows.append(
        {
            "title": "Геометрия",
            "status": "warn" if geometry_issues else "ok",
            "summary": (
                "Проверьте: " + ", ".join(geometry_issues) + "."
                if geometry_issues
                else "Основные размеры и ход заданы."
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
                else "Массы, шины и стабилизаторы выглядят готовыми к запуску."
            ),
            "issues": mechanics_issues,
        }
    )

    calc_issues: list[str] = []
    if _safe_float(current, "макс_шаг_интегрирования_с") <= 0.0:
        calc_issues.append("максимальный шаг интегрирования")
    if _safe_float(current, "макс_число_внутренних_шагов_на_dt") < 1000.0:
        calc_issues.append("лимит внутренних шагов")
    if _safe_bool(current, "static_trim_force") and not _safe_bool(current, "static_trim_enable"):
        calc_issues.append("форсированный static trim без включённого поиска посадки")
    if not _safe_choice(current, "термодинамика"):
        calc_issues.append("режим термодинамики")
    if not _safe_choice(current, "механика_кинематика"):
        calc_issues.append("кинематика подвески")
    rows.append(
        {
            "title": "Настройки расчёта",
            "status": "warn" if calc_issues else "ok",
            "summary": (
                "Проверьте: " + ", ".join(calc_issues) + "."
                if calc_issues
                else "Интегрирование и служебные режимы выглядят согласованно."
            ),
            "issues": calc_issues,
        }
    )

    return rows


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
    "delete_desktop_profile",
    "desktop_section_status_label",
    "desktop_field_values_match",
    "desktop_profile_dir_path",
    "desktop_profile_display_name",
    "desktop_profile_path",
    "desktop_snapshot_dir_path",
    "desktop_snapshot_display_name",
    "desktop_snapshot_path",
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
