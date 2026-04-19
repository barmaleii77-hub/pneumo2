from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from .contracts import DesktopShellToolSpec


@dataclass(frozen=True)
class ShellCommandSearchEntry:
    label: str
    location: str
    summary: str
    action_kind: str
    action_value: str
    keywords: tuple[str, ...] = ()


def _normalize_search_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def build_shell_command_search_entries(
    specs: Iterable[DesktopShellToolSpec],
) -> tuple[ShellCommandSearchEntry, ...]:
    entries: list[ShellCommandSearchEntry] = [
        ShellCommandSearchEntry(
            label="Панель проекта",
            location="Главное окно / Панель проекта",
            summary="Показывает панель проекта с основным порядком работы и быстрыми переходами.",
            action_kind="home",
            action_value="home",
            keywords=("панель проекта", "главная", "порядок работы", "рабочее место"),
        ),
        ShellCommandSearchEntry(
            label="Показать список рабочих окон",
            location="Главное окно / Список рабочих окон",
            summary="Переводит фокус в левый список проекта, порядка работы и результатов.",
            action_kind="focus",
            action_value="project_tree",
            keywords=("проект", "список", "рабочие окна", "панель проекта", "навигация", "порядок работы"),
        ),
        ShellCommandSearchEntry(
            label="Собрать диагностику",
            location="Главное окно / Быстрые действия",
            summary="Показывает диагностику и отправку для проверки состояния и подготовки архива.",
            action_kind="tool",
            action_value="desktop_diagnostics_center",
            keywords=("диагностика", "архив диагностики", "отправка", "состояние", "проверка"),
        ),
        ShellCommandSearchEntry(
            label="Показать в аниматоре",
            location="Главное окно / Быстрые действия",
            summary="Запускает аниматор для результатов расчёта и текущих настроек.",
            action_kind="tool",
            action_value="desktop_animator",
            keywords=("трёхмерная анимация", "анимация", "визуализация", "движение подвески", "ориентация модели"),
        ),
        ShellCommandSearchEntry(
            label="Проверить подготовку анимации",
            location="Анимация / Подготовка",
            summary="Показывает, какие результаты расчёта будет использовать аниматор.",
            action_kind="open_artifact",
            action_value="animator.analysis_context",
            keywords=("подготовка анимации", "файл анимации", "результаты расчёта", "проверенный результат"),
        ),
        ShellCommandSearchEntry(
            label="Проверить связь с аниматором",
            location="Анимация / Подготовка",
            summary="Показывает, готовы ли результаты расчёта для окна анимации.",
            action_kind="open_artifact",
            action_value="animator.animator_link_contract",
            keywords=("связь с аниматором", "подготовка анимации", "результаты расчёта"),
        ),
        ShellCommandSearchEntry(
            label="Показать результаты расчёта",
            location="Анимация / Результаты расчёта",
            summary="Показывает файл результатов расчёта.",
            action_kind="open_artifact",
            action_value="animator.selected_result_artifact_pointer",
            keywords=("результаты расчёта", "расчётный результат", "файл результата", "результат анализа"),
        ),
        ShellCommandSearchEntry(
            label="Загрузить файл анимации",
            location="Анимация / Результаты расчёта",
            summary="Открывает аниматор и загружает результаты расчёта для просмотра.",
            action_kind="tool",
            action_value="desktop_animator",
            keywords=("файл анимации", "последняя анимация", "просмотр анимации", "результат для аниматора"),
        ),
        ShellCommandSearchEntry(
            label="Показать сохранение анимации",
            location="Анимация / Сохранение",
            summary="Показывает запись сохранения выбранной анимации.",
            action_kind="open_artifact",
            action_value="animator.capture_export_manifest",
            keywords=(
                "сохранение анимации",
                "запись сохранения",
                "сохранённая анимация",
                "подготовка анимации",
            ),
        ),
        ShellCommandSearchEntry(
            label="Сравнить прогоны",
            location="Главное окно / Быстрые действия",
            summary="Запускает окно сравнения результатов.",
            action_kind="tool",
            action_value="compare_viewer",
            keywords=("сравнение", "сравнение прогонов", "сравнение результатов", "анализ результатов"),
        ),
    ]
    for spec in specs:
        label = spec.title
        location = f"{spec.menu_section} / {spec.title}"
        summary = spec.details or spec.description
        keywords = tuple(
            sorted(
                {
                    spec.title,
                    spec.description,
                    spec.details,
                    spec.effective_help_topic,
                    spec.effective_tooltip,
                    spec.menu_section,
                    spec.nav_section,
                    spec.effective_workspace_role,
                    spec.effective_source_of_truth_role,
                    spec.effective_runtime_kind,
                    *spec.capability_ids,
                    *spec.launch_contexts,
                    *spec.effective_search_aliases,
                }
            )
        )
        entries.append(
            ShellCommandSearchEntry(
                label=label,
                location=location,
                summary=summary,
                action_kind="tool",
                action_value=spec.key,
                keywords=keywords,
            )
        )
    return tuple(entries)


def rank_shell_command_search_entries(
    query: str,
    entries: Iterable[ShellCommandSearchEntry],
) -> tuple[ShellCommandSearchEntry, ...]:
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return tuple(entries)

    scored: list[tuple[float, ShellCommandSearchEntry]] = []
    query_tokens = tuple(token for token in normalized_query.split(" ") if token)
    for entry in entries:
        label_text = _normalize_search_text(entry.label)
        location_text = _normalize_search_text(entry.location)
        summary_text = _normalize_search_text(entry.summary)
        keyword_text = _normalize_search_text(" ".join(entry.keywords))
        haystack = " ".join(
            part for part in (label_text, location_text, summary_text, keyword_text) if part
        )
        if not haystack:
            continue
        score = 0.0
        if normalized_query == label_text:
            score += 1000.0
        if normalized_query in label_text:
            score += 250.0
        if normalized_query in keyword_text:
            score += 170.0
        if normalized_query in location_text:
            score += 120.0
        if normalized_query in summary_text:
            score += 80.0
        token_hits = sum(1 for token in query_tokens if token in haystack)
        if token_hits:
            score += float(token_hits * 24)
        score += SequenceMatcher(None, normalized_query, label_text).ratio() * 40.0
        score += SequenceMatcher(None, normalized_query, haystack).ratio() * 10.0
        if score <= 0.0:
            continue
        scored.append((score, entry))

    scored.sort(
        key=lambda item: (
            -item[0],
            len(item[1].label),
            item[1].label.lower(),
        )
    )
    return tuple(entry for _score, entry in scored)


__all__ = [
    "ShellCommandSearchEntry",
    "build_shell_command_search_entries",
    "rank_shell_command_search_entries",
]
