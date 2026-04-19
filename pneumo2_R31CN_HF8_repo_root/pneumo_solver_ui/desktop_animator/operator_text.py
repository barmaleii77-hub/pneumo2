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
    "READY": "готова",
    "BLOCKED": "заблокирована",
    "MISSING": "отсутствует",
    "INVALID": "повреждена",
    "DEGRADED": "неполная",
    "UNKNOWN": "неизвестно",
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
    ("no --npz and follow mode is off", "не выбран файл анимации"),
    ("pointer json does not contain", "файл последней анимации не содержит путь к данным"),
    ("pointer json is not an object", "файл последней анимации имеет неверный формат"),
    ("pointer json could not be read", "файл последней анимации не читается"),
    ("pointer target is missing", "файл анимации из последней записи не найден"),
    ("pointer missing", "файл последней анимации не найден"),
    ("npz missing", "файл анимации не найден"),
    ("no loadable NPZ", "нет загружаемой анимационной выгрузки"),
    ("truth_absent", "достоверные данные отсутствуют"),
    ("missing analysis context", "файл связи с анализом не найден"),
    ("analysis context hash mismatch", "метка связи с анализом не совпадает"),
    ("selected result artifact pointer sha256 mismatch", "метка результатов расчёта не совпадает"),
    ("selected result artifact pointer missing", "результаты расчёта не найдены"),
    ("selected result artifact is not animator-loadable", "результаты расчёта нельзя загрузить в аниматор"),
    ("missing selected result artifact pointer", "нет ссылки на результаты расчёта"),
    ("missing selected result artifact pointer path", "нет пути к результатам расчёта"),
    ("missing animator link contract", "нет данных для перехода в аниматор"),
    ("animator link contract schema mismatch", "формат перехода в аниматор не совпадает"),
    ("animator link contract handoff_id mismatch", "проверка перехода в аниматор не совпадает"),
    ("HO-008 BLOCKED", "связь с анализом заблокирована"),
    ("HO-008 INVALID", "связь с анализом повреждена"),
    ("HO-008 MISSING", "связь с анализом отсутствует"),
    ("HO-008 DEGRADED", "связь с анализом неполная"),
    ("BLOCKED", "связь с анализом заблокирована"),
    ("INVALID", "связь с анализом повреждена"),
    ("MISSING", "связь с анализом отсутствует"),
    ("DEGRADED", "связь с анализом неполная"),
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
    return HO008_STATUS_OPERATOR_LABELS.get(key, f"состояние {key}")


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
        return "Связь с анализом: отсутствует | файл связи не найден"
    data = dict(lineage or {})
    parts = [
        f"Связь с анализом: {ho008_status_label(status)}",
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
        parts.append(f"метка связи {_short(analysis_context_hash, length=12)}")
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
    source = "по результатам расчёта" if bool(context_ready) else "без связи с анализом"
    truth = f" | режим графики: {truth_state_label(truth_state)}" if _text(truth_state) else ""
    return f"Загружено {source}: {_name(path)}{truth}"


def format_loading_status(path: Any) -> str:
    return f"Загрузка анимационной выгрузки: {_name(path)}"


def format_queued_reload_status(path: Any) -> str:
    return f"Перезагрузка поставлена в очередь: {_name(path)}"


def format_load_failed_status(message: Any) -> str:
    return f"Не удалось загрузить файл анимации: {_text(message) or 'неизвестная ошибка'}"


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
        f"проверок={int(self_check_count)} "
        f"задач по пружинам={int(spring_todo_count)} | {_name(path)}"
    )


def format_playback_status(*, t_s: float, speed_mps: float, file_name: Any, cadence_warning: bool = False) -> str:
    prefix = "Предупреждение валидации: просадка кадров, вторичные панели ограничены | " if bool(cadence_warning) else ""
    return f"{prefix}время={float(t_s):.3f} с, скорость={float(speed_mps):.2f} м/с, файл={_name(file_name)}"


def format_direct_context_banner(path: Any = "") -> str:
    name = _name(path)
    suffix = f" | файл {name}" if name != "-" else ""
    return f"Связь с анализом: не загружена | файл открыт напрямую{suffix}"
