from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, Mapping, MutableMapping

AXLES: tuple[str, ...] = ("перед", "зад")
CYLINDERS: tuple[str, ...] = ("Ц1", "Ц2")
FAMILY_ORDER: tuple[tuple[str, str], ...] = (
    ("Ц1", "перед"),
    ("Ц2", "перед"),
    ("Ц1", "зад"),
    ("Ц2", "зад"),
)

SPRING_STATIC_MODE_KEY = "пружина_режим_настройки_в_статике"
SPRING_STATIC_MODE_MANUAL = "manual"
SPRING_STATIC_MODE_AUTO_MIDSTROKE = "auto_midstroke_static"

_SPRING_GENERIC_SUFFIXES: tuple[str, ...] = (
    "масштаб",
    "длина_свободная_м",
    "длина_солид_м",
    "верхний_отступ_от_крышки_м",
    "запас_до_coil_bind_минимум_м",
    "преднатяг_на_отбое_минимум_м",
    "геом_диаметр_проволоки_м",
    "геом_диаметр_средний_м",
    "геом_число_витков_активных",
    "геом_число_витков_полное",
    "геом_шаг_витка_м",
    "геом_G_Па",
)

_CYLINDER_FIELD_LABELS: dict[str, str] = {
    "bore": "Диаметр поршня",
    "rod": "Диаметр штока",
    "stroke": "Полный ход штока",
}
_AXLE_LABELS: dict[str, str] = {"перед": "спереди", "зад": "сзади"}
_SPRING_SUFFIX_LABELS: dict[str, tuple[str, str, str]] = {
    "масштаб": (
        "Масштаб силы пружины",
        "коэф.",
        "raw",
    ),
    "длина_свободная_м": (
        "Свободная длина пружины",
        "мм",
        "length_mm",
    ),
    "длина_солид_м": (
        "Длина пружины в solid",
        "мм",
        "length_mm",
    ),
    "верхний_отступ_от_крышки_м": (
        "Верхний отступ пружины от крышки цилиндра",
        "мм",
        "length_mm",
    ),
    "запас_до_coil_bind_минимум_м": (
        "Минимальный запас до coil-bind",
        "мм",
        "length_mm",
    ),
    "преднатяг_на_отбое_минимум_м": (
        "Минимальный преднатяг на полном отбое",
        "мм",
        "length_mm",
    ),
    "геом_диаметр_проволоки_м": (
        "Диаметр проволоки пружины",
        "мм",
        "length_mm",
    ),
    "геом_диаметр_средний_м": (
        "Средний диаметр витка пружины",
        "мм",
        "length_mm",
    ),
    "геом_число_витков_активных": (
        "Активные витки пружины",
        "витки",
        "raw",
    ),
    "геом_число_витков_полное": (
        "Полные витки пружины",
        "витки",
        "raw",
    ),
    "геом_шаг_витка_м": (
        "Шаг витка пружины",
        "мм",
        "length_mm",
    ),
    "геом_G_Па": (
        "Модуль сдвига материала пружины",
        "Па",
        "raw",
    ),
}

_CYLINDER_RE = re.compile(r"^(диаметр_поршня|диаметр_штока|ход_штока)_(Ц[12])_(перед|зад)(?:_м)?$")
_SPRING_RE = re.compile(r"^пружина_(Ц[12])_(перед|зад)_(.+)$")


def cylinder_family_key(field: str, cyl: str, axle: str) -> str:
    cyl = str(cyl).strip().upper()
    axle = str(axle).strip().lower()
    if field == "bore":
        return f"диаметр_поршня_{cyl}_{axle}_м"
    if field == "rod":
        return f"диаметр_штока_{cyl}_{axle}_м"
    if field == "stroke":
        return f"ход_штока_{cyl}_{axle}_м"
    raise KeyError(field)


def cylinder_generic_key(field: str, cyl: str) -> str:
    cyl = str(cyl).strip().upper()
    if field == "bore":
        return f"диаметр_поршня_{cyl}"
    if field == "rod":
        return f"диаметр_штока_{cyl}"
    raise KeyError(field)


def spring_family_key(suffix: str, cyl: str, axle: str) -> str:
    return f"пружина_{str(cyl).strip().upper()}_{str(axle).strip().lower()}_{str(suffix).strip()}"


def normalize_spring_static_mode(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"", "auto", "auto_midstroke", "auto_midstroke_static", "midstroke", "middle", "middle_static"}:
        return SPRING_STATIC_MODE_AUTO_MIDSTROKE
    if raw in {"manual", "ручной", "manual_static"}:
        return SPRING_STATIC_MODE_MANUAL
    return SPRING_STATIC_MODE_AUTO_MIDSTROKE


def spring_static_mode_description(mode: str | None = None) -> str:
    normalized = normalize_spring_static_mode(mode)
    if normalized == SPRING_STATIC_MODE_MANUAL:
        return (
            "Ручной режим: инженер сам задаёт семейства пружин и их геометрию. "
            "Оптимизация не должна молча подменять эти параметры."
        )
    return (
        "Автоматический режим: параметры пружины подбираются так, чтобы при стоянке "
        "на ровной площадке и текущей массе штоки оставались примерно около середины хода."
    )


def family_name(cyl: str, axle: str) -> str:
    return f"{str(cyl).strip().upper()} {str(axle).strip().lower()}"


def iter_family_names() -> Iterable[str]:
    for cyl, axle in FAMILY_ORDER:
        yield family_name(cyl, axle)


def family_param_meta(name: str) -> Dict[str, str] | None:
    raw = str(name or "").strip()
    if not raw:
        return None
    if raw == SPRING_STATIC_MODE_KEY:
        return {
            "группа": "Пружины по семействам",
            "ед": "режим",
            "kind": "raw",
            "описание": (
                "Канонический режим настройки пружин. "
                + spring_static_mode_description(SPRING_STATIC_MODE_AUTO_MIDSTROKE)
                + " Для manual пользователь задаёт семейства полностью вручную."
            ),
        }

    m_cyl = _CYLINDER_RE.match(raw)
    if m_cyl:
        prefix, cyl, axle = m_cyl.groups()
        field = "bore" if prefix == "диаметр_поршня" else "rod" if prefix == "диаметр_штока" else "stroke"
        label = _CYLINDER_FIELD_LABELS[field]
        return {
            "группа": "Цилиндры по семействам",
            "ед": "мм",
            "kind": "length_mm",
            "описание": (
                f"{label} семейства {cyl} {_AXLE_LABELS.get(axle, axle)}. "
                "Это независимый тип для одной стороны; левая и правая стороны используют его симметрично вдоль машины."
            ),
        }

    m_spring = _SPRING_RE.match(raw)
    if m_spring:
        cyl, axle, suffix = m_spring.groups()
        spec = _SPRING_SUFFIX_LABELS.get(suffix)
        if spec is None:
            return None
        label, unit, kind = spec
        return {
            "группа": "Пружины по семействам",
            "ед": unit,
            "kind": kind,
            "описание": (
                f"{label} для семейства {cyl} {_AXLE_LABELS.get(axle, axle)}. "
                "Поле отделено по семействам, чтобы перед/зад и Ц1/Ц2 могли различаться без потери продольной симметрии."
            ),
        }
    return None


def family_param_description(name: str) -> str:
    meta = family_param_meta(name)
    if isinstance(meta, dict):
        return str(meta.get("описание") or "")
    return ""


def _is_finite_scalar(value: Any) -> bool:
    try:
        out = float(value)
    except Exception:
        return False
    return math.isfinite(out)


def _copy_missing_numeric(target: MutableMapping[str, Any], key: str, value: Any, seeded: list[str]) -> None:
    if key in target:
        return
    if not _is_finite_scalar(value):
        return
    target[key] = float(value)
    seeded.append(key)


def _copy_missing_range(
    target: MutableMapping[str, Any],
    key: str,
    value: Any,
    seeded: list[str],
) -> None:
    if key in target:
        return
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return
    try:
        lo = float(value[0])
        hi = float(value[1])
    except Exception:
        return
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return
    target[key] = [float(min(lo, hi)), float(max(lo, hi))]
    seeded.append(key)


def normalize_component_family_contract(
    base: Mapping[str, Any] | None,
    ranges: Mapping[str, Any] | None = None,
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    base_out: Dict[str, Any] = dict(base or {})
    ranges_out: Dict[str, Any] = dict(ranges or {})
    seeded_base_keys: list[str] = []
    seeded_range_keys: list[str] = []

    base_out[SPRING_STATIC_MODE_KEY] = normalize_spring_static_mode(base_out.get(SPRING_STATIC_MODE_KEY))

    for cyl in CYLINDERS:
        generic_bore = base_out.get(cylinder_generic_key("bore", cyl))
        generic_rod = base_out.get(cylinder_generic_key("rod", cyl))
        generic_bore_rng = ranges_out.get(cylinder_generic_key("bore", cyl))
        generic_rod_rng = ranges_out.get(cylinder_generic_key("rod", cyl))
        global_stroke = base_out.get("ход_штока")
        global_stroke_rng = ranges_out.get("ход_штока")
        for axle in AXLES:
            _copy_missing_numeric(
                base_out,
                cylinder_family_key("bore", cyl, axle),
                generic_bore,
                seeded_base_keys,
            )
            _copy_missing_numeric(
                base_out,
                cylinder_family_key("rod", cyl, axle),
                generic_rod,
                seeded_base_keys,
            )
            _copy_missing_numeric(
                base_out,
                cylinder_family_key("stroke", cyl, axle),
                base_out.get(cylinder_family_key("stroke", cyl, axle), global_stroke),
                seeded_base_keys,
            )
            _copy_missing_range(
                ranges_out,
                cylinder_family_key("bore", cyl, axle),
                generic_bore_rng,
                seeded_range_keys,
            )
            _copy_missing_range(
                ranges_out,
                cylinder_family_key("rod", cyl, axle),
                generic_rod_rng,
                seeded_range_keys,
            )
            _copy_missing_range(
                ranges_out,
                cylinder_family_key("stroke", cyl, axle),
                ranges_out.get(cylinder_family_key("stroke", cyl, axle), global_stroke_rng),
                seeded_range_keys,
            )

    for suffix in _SPRING_GENERIC_SUFFIXES:
        generic_key = f"пружина_{suffix}"
        generic_value = base_out.get(generic_key)
        generic_rng = ranges_out.get(generic_key)
        for cyl, axle in FAMILY_ORDER:
            fam_key = spring_family_key(suffix, cyl, axle)
            _copy_missing_numeric(base_out, fam_key, generic_value, seeded_base_keys)
            _copy_missing_range(ranges_out, fam_key, generic_rng, seeded_range_keys)

    return base_out, ranges_out, {
        "spring_static_mode": str(base_out.get(SPRING_STATIC_MODE_KEY) or SPRING_STATIC_MODE_AUTO_MIDSTROKE),
        "seeded_base_keys": seeded_base_keys,
        "seeded_range_keys": seeded_range_keys,
        "family_count": int(len(FAMILY_ORDER)),
    }


__all__ = [
    "AXLES",
    "CYLINDERS",
    "FAMILY_ORDER",
    "SPRING_STATIC_MODE_AUTO_MIDSTROKE",
    "SPRING_STATIC_MODE_KEY",
    "SPRING_STATIC_MODE_MANUAL",
    "cylinder_family_key",
    "cylinder_generic_key",
    "family_name",
    "family_param_description",
    "family_param_meta",
    "iter_family_names",
    "normalize_component_family_contract",
    "normalize_spring_static_mode",
    "spring_family_key",
    "spring_static_mode_description",
]
