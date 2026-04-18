from __future__ import annotations

"""Russian operator-facing text for Desktop Animator.

This module is presentation-only: it does not change contracts, hashes or
artifact payloads. Machine-readable provenance stays in tooltips/JSON; primary
status strings stay short and readable for the operator.
"""

from pathlib import Path
from typing import Any, Mapping, Sequence


TRUTH_STATE_OPERATOR_LABELS: dict[str, str] = {
    "solver_confirmed": "Расчётно подтверждено",
    "source_data_confirmed": "По исходным данным",
    "approximate_inferred_with_warning": "Условно по неполным данным",
    "unavailable": "Недоступно",
}

HO008_STATUS_OPERATOR_LABELS: dict[str, str] = {
    "READY": "Контекст анализа готов",
    "BLOCKED": "Контекст анализа заблокирован",
    "MISSING": "Контекст анализа отсутствует",
    "INVALID": "Контекст анализа повреждён",
    "DEGRADED": "Контекст анализа неполный",
    "UNKNOWN": "Состояние контекста анализа неизвестно",
}

HIDDEN_ELEMENT_OPERATOR_LABELS: dict[str, str] = {
    "body": "корпус",
    "rod": "шток",
    "piston": "поршень",
    "chamber": "полость",
    "chrome": "хром",
    "glass": "прозрачность",
    "bloom": "свечение",
    "rings": "кольца",
    "glints": "блики",
    "caustics": "каустика",
}

_REASON_LABELS: tuple[tuple[str, str], ...] = (
    ("no --npz and follow mode is off", "не выбран артефакт анимации"),
    ("pointer json does not contain", "указатель не содержит путь к NPZ"),
    ("pointer json is not an object", "указатель имеет неверный формат"),
    ("pointer json could not be read", "указатель не читается"),
    ("pointer target is missing", "цель указателя не найдена"),
    ("pointer missing", "указатель anim_latest не найден"),
    ("npz missing", "NPZ-файл не найден"),
    ("no loadable NPZ", "нет загружаемой анимационной выгрузки"),
    ("truth_absent", "достоверные данные отсутствуют"),
    ("missing analysis context", "файл контекста анализа не найден"),
    ("analysis context hash mismatch", "хэш контекста анализа не совпадает"),
    ("selected result artifact pointer sha256 mismatch", "хэш выбранного артефакта не совпадает"),
    ("selected result artifact pointer missing", "указанный артефакт результата не найден"),
    ("selected result artifact is not animator-loadable", "выбранный артефакт не является NPZ для анимации"),
    ("missing selected result artifact pointer", "нет указателя на выбранный артефакт"),
    ("missing selected result artifact pointer path", "нет пути к выбранному артефакту"),
    ("missing animator link contract", "нет контракта перехода в аниматор"),
    ("animator link contract schema mismatch", "схема контракта перехода не совпадает"),
    ("animator link contract handoff_id mismatch", "идентификатор перехода HO-008 не совпадает"),
    ("HO-008 BLOCKED", "контекст анализа HO-008 заблокирован"),
    ("HO-008 INVALID", "контекст анализа HO-008 повреждён"),
    ("HO-008 MISSING", "контекст анализа HO-008 отсутствует"),
    ("HO-008 DEGRADED", "контекст анализа HO-008 неполный"),
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _short(value: Any, *, length: int = 10) -> str:
    text = _text(value)
    return text[: max(1, int(length))] if text else "-"


def _name(value: Any) -> str:
    text = _text(value)
    if not text:
        return "-"
    try:
        return Path(text).name or text
    except Exception:
        return text


def truth_state_label(state: Any) -> str:
    key = _text(state)
    return TRUTH_STATE_OPERATOR_LABELS.get(key, key or TRUTH_STATE_OPERATOR_LABELS["unavailable"])


def ho008_status_label(status: Any) -> str:
    key = _text(status).upper() or "UNKNOWN"
    return HO008_STATUS_OPERATOR_LABELS.get(key, f"Контекст анализа: {key}")


def operator_reason_label(reason: Any) -> str:
    text = _text(reason)
    if not text:
        return "причина не указана"
    text_lower = text.lower()
    for needle, label in _REASON_LABELS:
        if needle.lower() in text_lower:
            if ":" in text:
                return f"{label}: {_name(text.split(':', 1)[1])}"
            return label
    return text


def operator_reasons_join(items: Sequence[Any], *, limit: int = 3) -> str:
    labels = [operator_reason_label(item) for item in list(items or [])[: max(0, int(limit))]]
    return "; ".join(label for label in labels if label)


def hidden_elements_label(elements: Sequence[Any]) -> str:
    labels = [
        HIDDEN_ELEMENT_OPERATOR_LABELS.get(_text(item), _text(item))
        for item in list(elements or [])
        if _text(item)
    ]
    return ", ".join(dict.fromkeys(labels)) if labels else "-"


def format_analysis_context_banner(
    *,
    exists: bool,
    status: Any,
    lineage: Mapping[str, Any] | None,
    analysis_context_hash: Any = "",
    blocking_states: Sequence[Any] = (),
    warnings: Sequence[Any] = (),
) -> str:
    if not exists:
        return "HO-008: Контекст анализа отсутствует | analysis_context.json не найден"
    data = dict(lineage or {})
    parts = [
        f"HO-008: {ho008_status_label(status)}",
        f"прогон {_text(data.get('run_id')) or '-'}",
        f"тест {_text(data.get('selected_test_id')) or '-'}",
        f"сегмент {_text(data.get('selected_segment_id')) or '-'}",
        f"цель {_short(data.get('objective_contract_hash'))}",
        f"набор {_short(data.get('suite_snapshot_hash'))}",
        f"задача {_short(data.get('problem_hash'))}",
    ]
    if blocking_states:
        parts.append("причина: " + operator_reasons_join(blocking_states, limit=3))
    elif warnings:
        parts.append("предупреждение: " + operator_reasons_join(warnings, limit=2))
    if _text(analysis_context_hash):
        parts.append(f"хэш контекста {_short(analysis_context_hash, length=12)}")
    return " | ".join(parts)


def format_startup_degraded_status(reason: Any, *, detail: Any = "") -> str:
    reason_text = operator_reason_label(reason)
    detail_text = operator_reasons_join(str(detail).split(";"), limit=3) if _text(detail) else ""
    out = (
        f"Недоступно: {reason_text}. "
        "Оси по solver-points и геометрия цилиндров включаются только после явной достоверной выгрузки."
    )
    if detail_text:
        out = f"{out} Детали: {detail_text}."
    return out


def format_startup_canvas_lines(reason: Any) -> list[str]:
    reason_text = operator_reason_label(reason)
    return [
        f"Достоверные данные отсутствуют: {reason_text}",
        "Без подмены геометрии: оси и цилиндры ждут явных solver/export данных.",
    ]


def format_truth_warning_line(truth_state: Any, warning_count: int = 0) -> str:
    suffix = f"; предупреждений: {int(warning_count)}" if int(warning_count) > 0 else ""
    return f"Режим графики: {truth_state_label(truth_state)}{suffix}"


def format_cylinder_limit_line(count: int) -> str:
    return f"Ограничение цилиндров: полный корпус/шток/поршень скрыт, доступна только честная ось ({int(count)})"


def format_loaded_status(path: Any, *, context_ready: bool, truth_state: Any = "") -> str:
    source = "из контекста анализа HO-008" if bool(context_ready) else "вне HO-008 контекста"
    truth = f" | режим графики: {truth_state_label(truth_state)}" if _text(truth_state) else ""
    return f"Загружено {source}: {_name(path)}{truth}"


def format_loading_status(path: Any) -> str:
    return f"Загрузка анимационной выгрузки: {_name(path)}"


def format_queued_reload_status(path: Any) -> str:
    return f"Перезагрузка поставлена в очередь: {_name(path)}"


def format_load_failed_status(message: Any) -> str:
    return f"Не удалось загрузить NPZ: {_text(message) or 'неизвестная ошибка'}"


def format_validation_warning_status(
    *,
    fallback_count: int,
    self_check_count: int,
    spring_todo_count: int,
    path: Any,
) -> str:
    return (
        "Предупреждение валидации: "
        f"резервных путей={int(fallback_count)} "
        f"самопроверок={int(self_check_count)} "
        f"задач по пружинам={int(spring_todo_count)} | {_name(path)}"
    )


def format_playback_status(*, t_s: float, speed_mps: float, file_name: Any, cadence_warning: bool = False) -> str:
    prefix = "Предупреждение валидации: просадка кадров, вторичные панели ограничены | " if bool(cadence_warning) else ""
    return f"{prefix}время={float(t_s):.3f} с, скорость={float(speed_mps):.2f} м/с, файл={_name(file_name)}"


def format_direct_context_banner(path: Any = "") -> str:
    name = _name(path)
    suffix = f" | артефакт {name}" if name != "-" else ""
    return f"HO-008: Контекст анализа не загружен | прямая выгрузка вне HO-008{suffix}"
