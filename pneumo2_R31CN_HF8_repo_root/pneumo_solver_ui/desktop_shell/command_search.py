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
            label="Обзор рабочего места",
            location="Главное окно -> Обзор",
            summary="Открывает обзор shell с основным инженерным маршрутом и быстрыми переходами.",
            action_kind="home",
            action_value="home",
            keywords=("главная", "обзор", "маршрут", "рабочее место"),
        ),
        ShellCommandSearchEntry(
            label="Показать дерево проекта",
            location="Главное окно -> Обзор проекта",
            summary="Переводит фокус в левое дерево проекта, маршрута и артефактов.",
            action_kind="focus",
            action_value="project_tree",
            keywords=("проект", "дерево", "project", "browser", "navigator", "обзор проекта"),
        ),
        ShellCommandSearchEntry(
            label="Собрать диагностику",
            location="Главное окно -> Верхняя командная зона",
            summary="Открывает центр диагностики и отправки как главный глобальный путь для health-check и bundle.",
            action_kind="tool",
            action_value="desktop_diagnostics_center",
            keywords=("diagnostics", "bundle", "отправка", "health", "self-check"),
        ),
        ShellCommandSearchEntry(
            label="Открыть в аниматоре",
            location="Главное окно -> Верхняя командная зона",
            summary="Запускает Desktop Animator для текущего инженерного контекста.",
            action_kind="tool",
            action_value="desktop_animator",
            keywords=("3d", "анимация", "animation", "viewport", "viewcube"),
        ),
        ShellCommandSearchEntry(
            label="Открыть HO-008 analysis_context.json",
            location="Анимация -> HO-008 handoff",
            summary="Открывает frozen analysis context, который Desktop Animator использует как источник выбранного run.",
            action_kind="open_artifact",
            action_value="animator.analysis_context",
            keywords=("HO-008", "analysis_context", "analysis context", "frozen context", "animator handoff"),
        ),
        ShellCommandSearchEntry(
            label="Открыть HO-008 animator_link_contract.json",
            location="Анимация -> HO-008 handoff",
            summary="Открывает link contract от WS-ANALYSIS к WS-ANIMATOR для выбранного optimization run.",
            action_kind="open_artifact",
            action_value="animator.animator_link_contract",
            keywords=("HO-008", "animator_link_contract", "link contract", "analysis to animator"),
        ),
        ShellCommandSearchEntry(
            label="Открыть selected result artifact pointer",
            location="Анимация -> HO-008 selected artifact",
            summary="Открывает explicit selected result artifact pointer из frozen analysis context.",
            action_kind="open_artifact",
            action_value="animator.selected_result_artifact_pointer",
            keywords=("HO-008", "selected_result_artifact_pointer", "selected pointer", "artifact pointer"),
        ),
        ShellCommandSearchEntry(
            label="Открыть selected animation NPZ",
            location="Анимация -> HO-008 selected artifact",
            summary="Открывает resolved selected NPZ, переданный Animator через frozen analysis context.",
            action_kind="open_artifact",
            action_value="animator.selected_npz_path",
            keywords=("HO-008", "selected_npz_path", "npz", "animation npz", "anim_latest"),
        ),
        ShellCommandSearchEntry(
            label="Открыть HO-010 capture_export_manifest.json",
            location="Анимация -> HO-010 capture/export",
            summary="Открывает frozen capture/export manifest для выбранной анимации и её HO-008 lineage.",
            action_kind="open_artifact",
            action_value="animator.capture_export_manifest",
            keywords=(
                "HO-010",
                "capture_export_manifest",
                "capture export manifest",
                "capture_hash",
                "animator export",
                "analysis lineage",
            ),
        ),
        ShellCommandSearchEntry(
            label="Открыть сравнение прогонов",
            location="Главное окно -> Верхняя командная зона",
            summary="Запускает Compare Viewer для сравнения результатов и артефактов.",
            action_kind="tool",
            action_value="compare_viewer",
            keywords=("compare", "сравнение", "npz", "results"),
        ),
    ]
    for spec in specs:
        label = spec.title
        location = f"{spec.menu_section} -> {spec.title}"
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
                    spec.effective_migration_status,
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
