from __future__ import annotations

from .catalogs import get_help_topic, get_tooltip, legacy_key_aliases
from .contracts import DesktopHelpTopicSpec
from .registry import build_workspace_map


_TEXT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Линейка шагов pipeline", "Последовательность работы"),
    ("Линейка шагов последовательность работы", "Последовательность работы"),
    ("Блок настроек StageRunner", "Настройки поэтапного запуска"),
    ("блок настроек StageRunner", "настройки поэтапного запуска"),
    ("Настройки рекомендуемого staged", "Настройки рекомендуемого поэтапного запуска"),
    ("рекомендуемого staged", "рекомендуемого поэтапного запуска"),
    ("staged последовательность", "поэтапная последовательность"),
    ("поэтапный последовательность", "поэтапная последовательность"),
    ("поэтапного запуска последовательность работы", "поэтапного запуска и последовательности работы"),
    ("поэтапный запуск.", "поэтапного запуска."),
    ("каноническом pipeline", "основной последовательности работы"),
    ("канонический pipeline", "основная последовательность работы"),
    ("source" "-of-truth", "источник данных"),
    ("Source" "-of-truth", "Источник данных"),
    ("source of truth", "источник данных"),
    ("Source of truth", "Источник данных"),
    ("pipeline", "последовательность работы"),
    ("Pipeline", "Последовательность работы"),
    ("preview", "предварительный вид"),
    ("Preview", "Предварительный вид"),
    ("В связанном предварительный вид", "В связанном предварительном виде"),
    ("в связанном предварительный вид", "в связанном предварительном виде"),
    ("Карточка контракта baseline", "Карточка опорного прогона"),
    ("карточка контракта baseline", "карточка опорного прогона"),
    ("Карточка предупреждений контракта", "Карточка предупреждений условий расчёта"),
    ("карточка предупреждений контракта", "карточка предупреждений условий расчёта"),
    ("Индикатор контракта целей и ограничений", "Индикатор целей и ограничений"),
    ("индикатор контракта целей и ограничений", "индикатор целей и ограничений"),
    ("suite", "набор испытаний"),
    ("Suite", "Набор испытаний"),
    ("objective stack", "цели расчёта"),
    ("Objective stack", "Цели расчёта"),
    ("baseline source", "источник опорного прогона"),
    ("objective contract", "цели расчёта"),
    ("hard gate", "обязательное условие"),
    ("Hard gate", "Обязательное условие"),
    ("active mode", "активный режим"),
    ("Active mode", "Активный режим"),
    ("estimated stage budgets", "оценка длительности этапов"),
    ("Estimated stage budgets", "Оценка длительности этапов"),
    ("Лидерборд запусков", "Таблица запусков"),
    ("лидерборд запусков", "таблица запусков"),
    ("KPI", "показателями"),
    ("Compare и validation", "Окно сравнения и проверка"),
    ("Compare", "Окно сравнения"),
    ("validation", "проверка"),
    ("run-ов", "запусков"),
    ("bundle_ready=False", "архив не готов"),
    ("bundle_ready=True", "архив готов"),
    ("bundle_ready", "архив готов"),
    ("legacy workspace surface", "отдельное рабочее окно"),
    ("Legacy workspace surface", "Отдельное рабочее окно"),
    ("contract", "контекст"),
    ("Contract", "Контекст"),
    ("контрактов", "условий"),
    ("Контрактов", "Условий"),
    ("контракта", "условий"),
    ("Контракта", "Условий"),
    ("контракт", "условия"),
    ("Контракт", "Условия"),
    ("StageRunner", "поэтапный запуск"),
    ("staged", "поэтапный"),
    ("Staged", "Поэтапный"),
    ("inspector", "панель свойств"),
    ("Inspector", "Панель свойств"),
    ("run-monitor", "мониторинг запуска"),
    ("Run-monitor", "Мониторинг запуска"),
    ("hosted", "встроенный"),
    ("Hosted", "Встроенный"),
    ("workspace", "окно"),
    ("Workspace", "Окно"),
    ("surface", "окно"),
    ("Surface", "Окно"),
    ("bundle", "архив для отправки"),
    ("Bundle", "Архив для отправки"),
    ("legacy", "отдельный"),
    ("Legacy", "Отдельный"),
    ("Baseline Center", "базовый прогон"),
    ("Baseline", "опорный прогон"),
    ("baseline", "опорный прогон"),
)


def _operator_text(raw: str) -> str:
    text = " ".join(str(raw or "").split()).strip()
    for old, new in _TEXT_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def _payload_text(payload: dict[str, object], keys: tuple[str, ...], fallback: str) -> str:
    for key in keys:
        value = " ".join(str(payload.get(key) or "").split()).strip()
        if value:
            return _operator_text(value)
    return _operator_text(fallback)


def _looks_like_generic_help(raw: str) -> bool:
    text = _operator_text(raw).casefold()
    generic_fragments = (
        "элемент участвует в основной последовательности работы",
        "берутся из источник данных",
        "берутся из источника данных",
        "в связанном предварительном виде",
        "не должен быть скрытым способом доступа",
    )
    return any(fragment in text for fragment in generic_fragments)


def _workspace_specific_result_location(workspace_title: str) -> str:
    return (
        f"Результат виден в рабочем шаге «{workspace_title}» и в связанных окнах, "
        "которые открываются из главного окна."
    )


def build_help_registry() -> dict[str, DesktopHelpTopicSpec]:
    registry: dict[str, DesktopHelpTopicSpec] = {}
    for workspace in build_workspace_map().values():
        catalog_help = get_help_topic(workspace.help_id or workspace.workspace_id)
        tooltip = get_tooltip(workspace.tooltip_id)
        payload = catalog_help.payload if catalog_help is not None else {}
        title = _operator_text(
            (catalog_help.title or workspace.title) if catalog_help is not None else workspace.title
        )
        summary = ". ".join(
            part
            for part in (
                _payload_text(payload, legacy_key_aliases("что_это"), workspace.summary),
                _payload_text(payload, legacy_key_aliases("зачем_нужно"), workspace.details or workspace.summary),
            )
            if part
        )
        units_policy = _payload_text(
            payload,
            legacy_key_aliases("единицы_измерения_если_применимо"),
            workspace.units_policy
            or "Единицы и смысл должны быть видимы рядом с действием пользователя.",
        )
        if _looks_like_generic_help(units_policy):
            units_policy = _operator_text(
                workspace.units_policy
                or "Единицы, подписи и смысл показываются рядом с соответствующим полем."
            )
        why_it_matters = _payload_text(
            payload,
            legacy_key_aliases("как_влияет_на_поток"),
            workspace.details or workspace.summary,
        )
        if _looks_like_generic_help(why_it_matters):
            why_it_matters = _operator_text(workspace.details or workspace.summary)
        result_location = _payload_text(
            payload,
            legacy_key_aliases("где_пользователь_видит_результат"),
            workspace.next_step,
        )
        if _looks_like_generic_help(result_location):
            result_location = _workspace_specific_result_location(workspace.title)
        hard_gate = _payload_text(
            payload,
            legacy_key_aliases("ограничения_и_валидация"),
            workspace.hard_gate,
        )
        if _looks_like_generic_help(hard_gate):
            hard_gate = _operator_text(workspace.hard_gate)
        registry[workspace.workspace_id] = DesktopHelpTopicSpec(
            topic_id=workspace.workspace_id,
            title=title,
            summary=summary,
            source_of_truth=_operator_text(workspace.source_of_truth),
            units_policy=units_policy,
            next_step=_operator_text(workspace.next_step),
            hard_gate=hard_gate,
            graphics_policy=_operator_text(workspace.graphics_policy)
            or "Производное представление обязано показывать происхождение данных и уровень достоверности.",
            tooltip_text=_operator_text(tooltip.text if tooltip is not None else ""),
            why_it_matters=why_it_matters,
            result_location=result_location,
        )
    return registry
