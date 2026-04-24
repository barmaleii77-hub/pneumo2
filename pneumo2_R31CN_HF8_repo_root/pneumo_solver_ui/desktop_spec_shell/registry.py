from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from .catalogs import (
    get_ui_element,
    legacy_key_aliases,
    migration_hints_by_workspace_code,
    v16_search_hints_by_workspace_code,
    v19_search_hints_by_workspace_code,
)
from .contracts import DesktopShellCommandSpec, DesktopWorkspaceSpec


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


PARITY_MAP_PATH = _repo_root() / "docs" / "context" / "desktop_web_parity_map.json"

SHELL_WORKSPACE_CODE = "WS-SHELL"

WORKSPACE_CODE_BY_ID: dict[str, tuple[str, ...]] = {
    "overview": ("WS-PROJECT",),
    "input_data": ("WS-INPUTS",),
    "ring_editor": ("WS-RING",),
    "test_matrix": ("WS-SUITE",),
    "baseline_run": ("WS-BASELINE",),
    "optimization": ("WS-OPTIMIZATION",),
    "results_analysis": ("WS-ANALYSIS",),
    "animation": ("WS-ANIMATOR",),
    "diagnostics": ("WS-DIAGNOSTICS",),
    "app_settings": ("WS-SETTINGS",),
    "tools": ("WS-TOOLS",),
}

WORKSPACE_CATALOG_ALIAS_CODES_BY_ID: dict[str, tuple[str, ...]] = {
    "overview": ("SHELL", "WS-PROJECT", "общие_регионы"),
    "results_analysis": (
        "WS-RESULTS",
        "WS-ANALYTICS",
        "рабочее_пространство.Анализ_результатов",
    ),
    "animation": ("рабочее_пространство.Анимация",),
    "diagnostics": ("рабочее_пространство.Проверка_проекта",),
    "optimization": ("рабочее_пространство.Оптимизация",),
    "ring_editor": ("рабочее_пространство.Сценарии_и_редактор_кольца",),
}

WORKSPACE_ELEMENT_BY_ID: dict[str, str] = {
    "overview": "PJ-STEP-BAR",
    "input_data": "ID-PARAM-TABLE",
    "ring_editor": "RG-PLAN-VIEW",
    "test_matrix": "TS-TABLE",
    "baseline_run": "BL-CONTRACT-CARD",
    "optimization": "OP-STAGERUNNER-BLOCK",
    "results_analysis": "RS-LEADERBOARD",
    "animation": "AM-VIEWPORT",
    "diagnostics": "DG-LAST-BUNDLE",
}

COMMAND_ELEMENT_BY_ID: dict[str, str] = {
    "input.editor.open": "ID-PARAM-TABLE",
    "ring.editor.open": "RG-SEGMENT-LIST",
    "test.center.open": "TS-TABLE",
    "test.selection.show": "TS-BTN-DETAIL",
    "test.validation.show": "TS-BTN-VALIDATION-DOCK",
    "test.snapshot.show": "TS-BTN-SNAPSHOT-DOCK",
    "test.autotest.run": "TS-BTN-AUTOTEST-RUN",
    "diagnostics.collect_bundle": "DG-BTN-COLLECT",
    "baseline.center.open": "BL-BTN-RUN",
    "baseline.run.execute": "BL-BTN-RUN-EXECUTE",
    "baseline.run.cancel": "BL-BTN-RUN-CANCEL",
    "baseline.run.open_log": "BL-BTN-RUN-OPEN-LOG",
    "baseline.run.open_result": "BL-BTN-RUN-OPEN-RESULT",
    "baseline.run.road_preview": "BL-BTN-RUN-ROAD-PREVIEW",
    "baseline.run.warnings": "BL-BTN-RUN-WARNINGS",
    "baseline.optimization_handoff.show": "BL-BTN-HANDOFF-OPTIMIZATION",
    "baseline.review": "BL-BTN-REVIEW",
    "baseline.adopt": "BL-BTN-ADOPT",
    "baseline.restore": "BL-BTN-RESTORE",
    "optimization.center.open": "OP-BTN-LAUNCH",
    "optimization.primary_launch.execute": "OP-BTN-EXECUTE",
    "optimization.primary_launch.soft_stop": "OP-BTN-SOFT-STOP",
    "optimization.primary_launch.hard_stop": "OP-BTN-HARD-STOP",
    "optimization.primary_launch.open_log": "OP-BTN-OPEN-LOG",
    "optimization.primary_launch.open_run_dir": "OP-BTN-OPEN-RUN-DIR",
    "optimization.history.show": "OP-BTN-HISTORY",
    "optimization.finished.show": "OP-BTN-FINISHED",
    "optimization.handoff.show": "OP-BTN-HANDOFF",
    "optimization.packaging.show": "OP-BTN-PACKAGING",
    "results.center.open": "RS-BTN-OPEN-ANALYTICS",
    "results.compare.prepare": "RS-COMPARE-PICKER",
    "results.run_materials.show": "RS-BTN-RUN-MATERIALS",
    "results.selected_material.show": "RS-BTN-SELECTED-MATERIAL",
    "results.chart_detail.show": "RS-BTN-CHART-DETAIL",
    "results.engineering_qa.show": "RS-BTN-ENGINEERING-QA",
    "results.engineering_candidates.show": "RS-BTN-ENGINEERING-CANDIDATES",
    "results.engineering_run.pin": "RS-BTN-ENGINEERING-PIN-RUN",
    "results.engineering_influence.run": "RS-BTN-ENGINEERING-INFLUENCE-RUN",
    "results.engineering_full_report.run": "RS-BTN-ENGINEERING-FULL-REPORT-RUN",
    "results.engineering_param_staging.run": "RS-BTN-ENGINEERING-PARAM-STAGING-RUN",
    "results.influence_review.show": "RS-BTN-INFLUENCE-REVIEW",
    "results.compare_influence.show": "RS-BTN-COMPARE-INFLUENCE",
    "results.engineering_evidence.export": "RS-BTN-ENGINEERING-EVIDENCE",
    "results.engineering_animation_link.export": "RS-BTN-ENGINEERING-ANIMATION-LINK",
    "results.compare.open": "RS-BTN-OPEN-COMPARE",
    "results.compare.target.next": "RS-BTN-COMPARE-NEXT-TARGET",
    "results.compare.signal.next": "RS-BTN-COMPARE-NEXT-SIGNAL",
    "results.compare.playhead.next": "RS-BTN-COMPARE-NEXT-PLAYHEAD",
    "results.compare.window.next": "RS-BTN-COMPARE-NEXT-WINDOW",
    "results.evidence.prepare": "RS-BTN-PREPARE-EVIDENCE",
    "results.animation.prepare": "RS-BTN-HANDOFF-ANIMATION",
    "animation.animator.open": "AN-BTN-OPEN-ANIMATOR",
    "animation.animator.launch": "AM-DETACH",
    "animation.mnemo.launch": "AM-BTN-DETACH-MNEMO",
    "animation.diagnostics.prepare": "AM-BTN-HANDOFF-DIAGNOSTICS",
    "diagnostics.full_check.run": "DG-BTN-FULL-CHECK",
    "diagnostics.send_review.show": "DG-BTN-SEND-REVIEW",
    "workspace.animation.open": "AM-VIEWPORT",
}

ROUTE_QUICK_ACTIONS_BY_WORKSPACE: dict[str, tuple[str, ...]] = {
    "input_data": ("input.editor.open", "workspace.ring_editor.open", "workspace.test_matrix.open"),
    "ring_editor": ("ring.editor.open", "workspace.test_matrix.open"),
    "test_matrix": ("test.center.open", "test.selection.show", "test.validation.show", "test.snapshot.show", "test.autotest.run", "workspace.baseline_run.open", "workspace.ring_editor.open"),
    "baseline_run": ("baseline.run_setup.open", "baseline.run.road_preview", "baseline.run.warnings", "baseline.run.execute", "baseline.run.open_log", "baseline.run.open_result", "baseline.optimization_handoff.show", "baseline.review", "baseline.adopt", "baseline.restore", "workspace.optimization.open", "workspace.results_analysis.open"),
    "optimization": ("workspace.baseline_run.open", "optimization.center.open", "optimization.history.show", "optimization.finished.show", "optimization.handoff.show", "optimization.packaging.show", "optimization.primary_launch.execute", "optimization.primary_launch.soft_stop", "workspace.results_analysis.open", "workspace.diagnostics.open"),
    "results_analysis": ("results.center.open", "results.run_materials.show", "results.selected_material.show", "results.chart_detail.show", "results.engineering_qa.show", "results.engineering_candidates.show", "results.engineering_run.pin", "results.engineering_influence.run", "results.engineering_full_report.run", "results.engineering_param_staging.run", "results.influence_review.show", "results.compare_influence.show", "results.engineering_evidence.export", "results.engineering_animation_link.export", "results.compare.prepare", "results.compare.open", "results.compare.target.next", "results.compare.signal.next", "results.compare.playhead.next", "results.compare.window.next", "results.animation.prepare", "results.evidence.prepare", "workspace.animation.open", "workspace.diagnostics.open"),
    "animation": ("animation.animator.open", "animation.animator.launch", "animation.mnemo.open", "animation.mnemo.launch", "animation.diagnostics.prepare", "workspace.results_analysis.open", "workspace.diagnostics.open"),
    "diagnostics": ("diagnostics.full_check.run", "diagnostics.send_review.show", "diagnostics.verify_bundle", "diagnostics.send_results", "diagnostics.collect_bundle"),
}


def _dedupe(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        text = " ".join(str(raw or "").split()).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return tuple(ordered)


_VISIBLE_ALIAS_BLOCKLIST = (
    "artifact",
    "bundle",
    "compare pages",
    "contract",
    "csv",
    "diagnostics",
    "export",
    "health report",
    "hub",
    "json",
    "kpi",
    "legacy",
    "master-copy",
    "npz",
    "payload",
    "pipeline",
    "preflight",
    "result viewers",
    "selfcheck",
    "send " "bundle",
    "source-of-truth",
    "workspace",
    "артефакт",
    "контракт",
    "диагност",
    "рабочее пространство",
    "рабочие пространства",
    "самопровер",
    "статус " "мигра" "ции",
)


def _sanitize_visible_aliases(values: object) -> tuple[str, ...]:
    if isinstance(values, str):
        raw_values = (values,)
    else:
        raw_values = tuple(values) if isinstance(values, (list, tuple)) else ()

    aliases: list[str] = []
    for raw in raw_values:
        text = str(raw or "").replace("поиск:", "")
        for chunk in text.replace("/", "\n").replace(";", "\n").splitlines():
            alias = " ".join(chunk.split()).strip(" .")
            folded = alias.casefold()
            if not alias or len(alias) > 72:
                continue
            if any(block in folded for block in _VISIBLE_ALIAS_BLOCKLIST):
                continue
            aliases.append(alias)
    return _dedupe(aliases)


def _load_parity_aliases() -> dict[str, tuple[str, ...]]:
    if not PARITY_MAP_PATH.exists():
        return {}
    try:
        rows = json.loads(PARITY_MAP_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    aliases: dict[str, tuple[str, ...]] = {}
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, dict):
            continue
        capability_id = str(row.get("capability_id") or "").strip()
        if not capability_id:
            continue
        hints = ()
        for key in legacy_key_aliases("как_найти_через_поиск_команд"):
            hints = row.get(key) or ()
            if hints:
                break
        aliases[capability_id] = _sanitize_visible_aliases(hints)
    return aliases


def _aliases_for_capabilities(capability_ids: tuple[str, ...], *base: str) -> tuple[str, ...]:
    parity_aliases = _load_parity_aliases()
    values: list[str] = list(base)
    for capability_id in capability_ids:
        values.extend(parity_aliases.get(capability_id, ()))
    return _dedupe(values)


def _migration_aliases_for_workspace(workspace_id: str) -> tuple[str, ...]:
    hints_by_code = migration_hints_by_workspace_code()
    values: list[str] = []
    codes = _dedupe(
        [
            *WORKSPACE_CODE_BY_ID.get(workspace_id, ()),
            *WORKSPACE_CATALOG_ALIAS_CODES_BY_ID.get(workspace_id, ()),
        ]
    )
    for code in codes:
        values.extend(hints_by_code.get(code, ()))
    return _sanitize_visible_aliases(values)


def _sanitize_v19_search_aliases(values: object) -> tuple[str, ...]:
    if isinstance(values, str):
        raw_values = (values,)
    else:
        raw_values = tuple(values) if isinstance(values, (list, tuple)) else ()

    aliases: list[str] = []
    for raw in raw_values:
        alias = " ".join(str(raw or "").split()).strip(" .")
        folded = alias.casefold()
        if not alias:
            continue
        if any(block in folded for block in _VISIBLE_ALIAS_BLOCKLIST):
            continue
        aliases.append(alias)
    return _dedupe(aliases)


def _v19_aliases_for_workspace(workspace_id: str) -> tuple[str, ...]:
    hints_by_code = v19_search_hints_by_workspace_code()
    values: list[str] = []
    codes = _dedupe(
        [
            *WORKSPACE_CODE_BY_ID.get(workspace_id, ()),
            *WORKSPACE_CATALOG_ALIAS_CODES_BY_ID.get(workspace_id, ()),
        ]
    )
    for code in codes:
        values.extend(hints_by_code.get(code, ()))
    return _sanitize_v19_search_aliases(values)


def _v16_aliases_for_workspace(workspace_id: str) -> tuple[str, ...]:
    hints_by_code = v16_search_hints_by_workspace_code()
    values: list[str] = []
    codes = _dedupe(
        [
            *WORKSPACE_CODE_BY_ID.get(workspace_id, ()),
            *WORKSPACE_CATALOG_ALIAS_CODES_BY_ID.get(workspace_id, ()),
        ]
    )
    for code in codes:
        values.extend(hints_by_code.get(code, ()))
    return _sanitize_v19_search_aliases(values)


def _bind_workspace_catalog(spec: DesktopWorkspaceSpec) -> DesktopWorkspaceSpec:
    element = get_ui_element(WORKSPACE_ELEMENT_BY_ID.get(spec.workspace_id))
    return replace(
        spec,
        workspace_owner="; ".join(WORKSPACE_CODE_BY_ID.get(spec.workspace_id, ())),
        catalog_owner_aliases=WORKSPACE_CATALOG_ALIAS_CODES_BY_ID.get(spec.workspace_id, ()),
        region=element.region if element is not None else spec.region,
        automation_id=(element.automation_id if element is not None else spec.automation_id),
        tooltip_id=(element.tooltip_id if element is not None else spec.tooltip_id),
        help_id=(element.help_id if element is not None else spec.help_id or spec.workspace_id),
        availability=(element.availability if element is not None else spec.availability),
        access_key=(element.access_key if element is not None else spec.access_key),
        hotkey=(element.hotkey if element is not None else spec.hotkey),
        tab_index=(element.tab_index if element is not None else spec.tab_index),
        search_aliases=_dedupe(
            [
                *spec.search_aliases,
                *_migration_aliases_for_workspace(spec.workspace_id),
                *_v19_aliases_for_workspace(spec.workspace_id),
                *_v16_aliases_for_workspace(spec.workspace_id),
            ]
        ),
        quick_action_ids=ROUTE_QUICK_ACTIONS_BY_WORKSPACE.get(spec.workspace_id, spec.quick_action_ids),
    )


def _bind_command_catalog(spec: DesktopShellCommandSpec) -> DesktopShellCommandSpec:
    element = get_ui_element(COMMAND_ELEMENT_BY_ID.get(spec.command_id))
    return replace(
        spec,
        automation_id=(element.automation_id if element is not None else spec.automation_id),
        tooltip_id=(element.tooltip_id if element is not None else spec.tooltip_id),
        help_topic_id=(element.help_id if element is not None else spec.help_topic_id),
        availability=(element.availability if element is not None else spec.availability),
        access_key=(element.access_key if element is not None else spec.access_key),
        hotkey=(element.hotkey if element is not None else spec.hotkey),
    )


def build_shell_workspaces() -> tuple[DesktopWorkspaceSpec, ...]:
    workspaces = (
        DesktopWorkspaceSpec(
            workspace_id="overview",
            title="Панель проекта",
            group="Основная последовательность",
            route_order=10,
            kind="main",
            summary="Главная инженерная сводка проекта, опорный прогон, цели оптимизации, результаты, проверка проекта и архив.",
            source_of_truth="Панель проекта показывает производную сводку над проектом и последними файлами расчёта.",
            launch_surface="workspace",
            next_step="Выберите следующий шаг по основной последовательности и откройте связанное рабочее окно.",
            hard_gate="Панель проекта не заменяет исходные данные; она только сводит состояние проекта.",
            details="Здесь находятся быстрые действия, сводка проверки и видимое состояние опорного прогона, оптимизации и архива проекта.",
            units_policy="Единицы на панели проекта только поясняют состояние файлов и не подменяют рабочие экраны.",
            graphics_policy="Карточки панели проекта обязаны честно показывать, это расчётный файл, производная сводка или незаполненное место.",
            search_aliases=("главная", "проект", "обзор"),
            quick_action_ids=(
                "workspace.input_data.open",
                "workspace.ring_editor.open",
                "workspace.test_matrix.open",
                "workspace.baseline_run.open",
                "workspace.optimization.open",
                "workspace.results_analysis.open",
                "workspace.animation.open",
                "workspace.diagnostics.open",
            ),
        ),
        DesktopWorkspaceSpec(
            workspace_id="input_data",
            title="Исходные данные",
            group="Основная последовательность",
            route_order=20,
            kind="main",
            summary="Основная редактируемая копия параметров машины, геометрии, пневматики, механики и базовой готовности проекта.",
            source_of_truth="Только рабочий шаг исходных данных задаёт исходную инженерную конфигурацию.",
            launch_surface="workspace",
            next_step="После правки данных переходите в сценарии, затем в набор испытаний и опорный прогон.",
            hard_gate="До готовности исходных данных опорный прогон и оптимизация не считаются достоверными.",
            details="Рабочий шаг показывает рабочую копию, эталон и готовность групп прямо в главном окне; отдельный редактор остаётся доступен для детального редактирования.",
            units_policy="Все поля должны показывать величину и единицу; безымянные значения запрещены.",
            graphics_policy="Геометрия и предварительный вид обязаны быть двусторонне связаны с числовым вводом.",
            capability_ids=("input.project_entry_and_setup",),
            search_aliases=_aliases_for_capabilities(("input.project_entry_and_setup",), "исходные данные", "параметры машины", "геометрия"),
            quick_action_ids=(
                "input.editor.open",
                "workspace.ring_editor.open",
                "workspace.test_matrix.open",
            ),
        ),
        DesktopWorkspaceSpec(
            workspace_id="ring_editor",
            title="Редактор циклического сценария",
            group="Основная последовательность",
            route_order=30,
            kind="main",
            summary="Единственное место редактирования циклического сценария, дороги, сегментов, шва и производных файлов сценария.",
            source_of_truth="Редактор циклического сценария задаёт сценарий и дорогу; остальные окна только используют готовые файлы.",
            launch_surface="workspace",
            next_step="После подготовки циклического сценария откройте набор испытаний и свяжите сценарии с матрицей испытаний.",
            hard_gate="Сценарии не должны редактироваться в других местах, кроме редактора циклического сценария.",
            details="Рабочее место показывает native WS-RING сводку, provenance и безопасный переход к набору испытаний; старый редактор остаётся fallback-действием для детального редактирования.",
            units_policy="Параметры дороги и манёвра обязаны иметь единицы, диапазоны и справку.",
            graphics_policy="Профиль дороги и производные файлы обязаны быть связаны с числовыми параметрами.",
            search_aliases=("редактор циклического сценария", "циклический сценарий", "редактор кольца", "сценарии", "дорога"),
            quick_action_ids=("ring.editor.open", "workspace.test_matrix.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="test_matrix",
            title="Набор испытаний",
            group="Основная последовательность",
            route_order=40,
            kind="main",
            summary="Единый набор испытаний, стадий, расчётных настроек и связей со сценариями.",
            source_of_truth="Матрица испытаний хранит состав, порядок и параметры проверок.",
            launch_surface="workspace",
            next_step="После настройки набора испытаний переходите к расчёту, проверке или оптимизации.",
            hard_gate="Без актуального снимка набора испытаний нельзя запускать расчёт и оптимизацию.",
            details="Рабочее место показывает таблицу набора, проверку связей с редактором сценария и сохранение проверенного снимка для базового прогона; старый центр остаётся расширенным инструментом настройки.",
            units_policy="Времена, шаги интегрирования и метки этапов должны быть показаны явно.",
            graphics_policy="Линия времени и сводка этапов являются производными представлениями над матрицей испытаний.",
            capability_ids=("calculation.validation_and_prechecks",),
            search_aliases=_aliases_for_capabilities(
                ("calculation.validation_and_prechecks",),
                "набор испытаний",
                "испытания",
                "матрица испытаний",
                "снимок набора",
                "контроль набора",
                "зафиксировать набор",
            ),
            quick_action_ids=("test.center.open", "test.selection.show", "test.validation.show", "test.snapshot.show", "test.autotest.run", "workspace.baseline_run.open", "workspace.ring_editor.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="baseline_run",
            title="Базовый прогон",
            group="Основная последовательность",
            route_order=50,
            kind="main",
            summary="Источник данных по опорному прогону, его истории и передаче в оптимизацию.",
            source_of_truth="Этот рабочий шаг отвечает за происхождение опорного прогона и явное принятие результата.",
            launch_surface="workspace",
            next_step="Запустите опорный прогон и затем переходите к оптимизации только после принятия опорного результата.",
            hard_gate="Без происхождения опорного прогона цели оптимизации и история запусков считаются неполными.",
            details="Рабочий шаг показывает условия запуска, прогресс и происхождение результата прямо в главном рабочем месте.",
            units_policy="Временные и расчётные настройки должны быть видимы вместе с происхождением опорного прогона.",
            graphics_policy="Сводка опорного прогона в главном окне всегда производная и обязана указывать источник данных.",
            search_aliases=("базовый прогон", "опорный прогон", "активный опорный прогон", "история прогона", "настройка расчёта"),
            quick_action_ids=("baseline.run_setup.open", "baseline.run.road_preview", "baseline.run.warnings", "baseline.run.execute", "baseline.run.open_log", "baseline.run.open_result", "baseline.optimization_handoff.show", "baseline.review", "baseline.adopt", "baseline.restore", "workspace.optimization.open", "workspace.results_analysis.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="optimization",
            title="Оптимизация",
            group="Основная последовательность",
            route_order=60,
            kind="main",
            summary="Цели расчёта, ограничения, история и ход выполнения оптимизации.",
            source_of_truth="Окно оптимизации держит активный способ запуска и условия выполнения.",
            launch_surface="workspace",
            next_step="Открывайте оптимизацию только после опорного прогона и держите один активный способ запуска.",
            hard_gate="Поэтапный запуск является основным режимом; распределённая координация разрешена только как расширенный режим той же последовательности.",
        details="Рабочее место обязано показывать цели расчёта, обязательные ограничения и происхождение опорного прогона рядом со входом в оптимизацию.",
            units_policy="Целевые показатели и ограничения обязаны показывать смысл и единицы в справке и происхождении данных.",
            graphics_policy="Любой ход выполнения должен честно показывать активный режим и источник опорного прогона.",
            capability_ids=("optimization.orchestration_and_databases",),
            search_aliases=_aliases_for_capabilities(("optimization.orchestration_and_databases",), "оптимизация", "поэтапный запуск", "решатель"),
            quick_action_ids=("workspace.baseline_run.open", "optimization.center.open", "optimization.history.show", "optimization.finished.show", "optimization.handoff.show", "optimization.packaging.show", "optimization.primary_launch.execute", "optimization.primary_launch.soft_stop", "workspace.results_analysis.open", "workspace.diagnostics.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="results_analysis",
            title="Анализ результатов",
            group="Основная последовательность",
            route_order=70,
            kind="main",
            summary="Графики, проверки, сравнение и анализ файлов после прогонов.",
            source_of_truth="Анализ результатов и окна сравнения являются производными представлениями над файлами прогонов.",
            launch_surface="workspace",
            next_step="Переходите сюда из опорного прогона или оптимизации и работайте от конкретного выбранного прогона.",
            hard_gate="Результаты и проверки не должны жить отдельными потерянными страницами вне выбранного прогона.",
            details="Рабочее место показывает анализ результатов, подготовку сравнения и передачу в анимацию без промежуточного окна-хаба.",
            units_policy="Графики и таблицы обязаны показывать единицы и источник данных.",
            graphics_policy="Окно сравнения и проверка обязаны помечать источник данных и время построения.",
            capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"),
            search_aliases=_aliases_for_capabilities(("results.compare_and_review", "analysis.influence_and_exploration"), "анализ", "результаты", "сравнение"),
            quick_action_ids=("results.center.open", "results.run_materials.show", "results.selected_material.show", "results.chart_detail.show", "results.engineering_qa.show", "results.engineering_candidates.show", "results.engineering_run.pin", "results.engineering_influence.run", "results.engineering_full_report.run", "results.engineering_param_staging.run", "results.influence_review.show", "results.compare_influence.show", "results.engineering_evidence.export", "results.engineering_animation_link.export", "results.compare.prepare", "results.compare.open", "results.compare.target.next", "results.compare.signal.next", "results.compare.playhead.next", "results.compare.window.next", "results.evidence.prepare", "results.animation.prepare", "workspace.animation.open", "workspace.diagnostics.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="animation",
            title="Анимация",
            group="Основная последовательность",
            route_order=80,
            kind="main",
            summary="Визуальная проверка через аниматор и мнемосхему с честными режимами достоверности.",
            source_of_truth="Аниматор и мнемосхема остаются специализированными рабочими окнами, запускаемыми после выбора результата.",
            launch_surface="workspace",
            next_step="Переходите к анимации после выбора результата и возвращайтесь к источнику изменения после визуальной проверки.",
            hard_gate="Нельзя показывать расчётно подтверждённую графику там, где данных недостаточно.",
            details="Рабочее место удерживает последовательность работы и показывает готовность анимации в главном маршруте; отдельные просмотры разрешены только как вторичная графическая проверка.",
            units_policy="Наложения и панель свойств обязаны показывать единицы и статус достоверности.",
            graphics_policy="Всегда показывайте маркер достоверности: расчётно подтверждённый, по исходным данным или условный.",
            capability_ids=("visualization.animator_and_mnemo",),
            search_aliases=_aliases_for_capabilities(("visualization.animator_and_mnemo",), "анимация", "аниматор", "мнемосхема"),
            quick_action_ids=("animation.animator.open", "animation.mnemo.open", "animation.diagnostics.prepare"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="diagnostics",
            title="Проверка проекта",
            group="Основная последовательность",
            route_order=90,
            kind="main",
            summary="Проверка проекта, сохранение архива проекта и копирование архива вручную.",
            source_of_truth="Проверка проекта и архив являются основным рабочим шагом и доступны из любого места приложения.",
            launch_surface="workspace",
            next_step="Сохраняйте архив проекта главной кнопкой или проверяйте проект перед ручной передачей файлов.",
            hard_gate="Проверку проекта и архив нельзя прятать за второстепенными меню или неочевидными обходными путями.",
            details="Главная кнопка, быстрый поиск и карточка панели проекта обязаны вести в проверку проекта без обходных путей; расширенная проверка остаётся инструментом восстановления.",
            units_policy="Поля проверки показывают источник, время и тип материала, а не инженерные единицы.",
            graphics_policy="Сводка архива проекта и состояние проекта обязаны честно показывать готовность и недостающие файлы.",
            capability_ids=("tools.diagnostics_and_bundle",),
            search_aliases=_aliases_for_capabilities(("tools.diagnostics_and_bundle",), "проверка проекта", "архив проекта", "сохранить архив"),
            quick_action_ids=("diagnostics.full_check.run", "diagnostics.send_review.show", "diagnostics.collect_bundle", "diagnostics.verify_bundle", "diagnostics.send_results"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="app_settings",
            title="Параметры приложения",
            group="Поддержка",
            route_order=100,
            kind="support",
            summary="Редкие настройки рабочего места и окружения, не влияющие на главную инженерную последовательность напрямую.",
            source_of_truth="Параметры приложения не должны смешиваться с исходными данными и условиями опорного прогона.",
            launch_surface="workspace",
        next_step="Используйте только для редких глобальных настроек или когда рабочее место явно советует это сделать.",
            hard_gate="Настройки не должны подменять рабочие шаги и не должны ломать происхождение данных.",
            details="Панель настроек остаётся доступной, даже если часть экранов ещё в разработке.",
            units_policy="Настройки обязаны честно помечаться как параметры приложения, а не как инженерные параметры.",
            graphics_policy="Настройки не имеют права маскировать источник достоверности графики.",
            search_aliases=("параметры приложения", "настройки", "settings"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="tools",
            title="Инструменты",
            group="Поддержка",
            route_order=110,
            kind="support",
            summary="Вспомогательные, справочные и сервисные профессиональные окна вне основной последовательности.",
            source_of_truth="Инструменты дополняют работу, но не подменяют основные рабочие шаги.",
            launch_surface="tooling",
            next_step="Используйте справочник геометрии, проверки и связанные инструменты только рядом с понятной рабочей задачей.",
            hard_gate="Вспомогательные инструменты не должны становиться скрытым главным входом в основную последовательность.",
            details="Окно инструментов собирает справочные и специализированные окна без потери обнаруживаемости.",
            units_policy="Окна инструментов обязаны сохранять те же правила названий, единиц и справки.",
            graphics_policy="Любой инструмент обязан честно маркировать, это справочный вид, производный результат или окно проверки.",
            search_aliases=("инструменты", "справочник", "reference"),
            quick_action_ids=(
                "tools.geometry_reference.open",
                "tools.autotest.open",
            ),
        ),
    )
    return tuple(
        _bind_workspace_catalog(item)
        for item in sorted(workspaces, key=lambda item: item.route_order)
    )


def build_shell_commands() -> tuple[DesktopShellCommandSpec, ...]:
    commands = (
        DesktopShellCommandSpec("workspace.overview.open", "Перейти к панели проекта", "Показать инженерную сводку, опорный прогон, проверку проекта, архив и быстрые действия.", "overview", "open_workspace", "Окна -> Панель проекта", target_workspace_id="overview", search_aliases=("обзор", "главная"), help_topic_id="overview"),
        DesktopShellCommandSpec("workspace.input_data.open", "Перейти к исходным данным", "Перейти к исходным данным и открыть основную редактируемую копию проекта в главной последовательности.", "input_data", "open_workspace", "Окна -> Исходные данные", target_workspace_id="input_data", capability_ids=("input.project_entry_and_setup",), help_topic_id="input_data"),
        DesktopShellCommandSpec("input.editor.open", "Редактировать исходные данные", "Работать с редактируемой копией исходных данных прямо в рабочем шаге.", "input_data", "hosted_action", "Окна -> Исходные данные -> Редактор исходных данных", capability_ids=("input.project_entry_and_setup",), launch_surface="workspace", status_label="Рабочий раздел", help_topic_id="input_data", search_aliases=("редактировать исходные данные", "таблица параметров", "рабочая копия исходных данных", "снимок исходных данных")),
        DesktopShellCommandSpec("input.legacy_editor.open", "Сервисный редактор исходных данных", "Открыть прежний редактор исходных данных только для восстановления или сравнения поведения.", "input_data", "launch_module", "Сервис -> Старые окна -> Исходные данные", module="pneumo_solver_ui.tools.desktop_input_editor", capability_ids=("input.project_entry_and_setup",), launch_surface="legacy_bridge", status_label="Сервисный fallback", help_topic_id="input_data", availability="support_fallback"),
        DesktopShellCommandSpec("workspace.ring_editor.open", "Перейти к редактору циклического сценария", "Перейти к сценарию, дороге, сегментам и производным файлам.", "ring_editor", "open_workspace", "Окна -> Редактор циклического сценария", target_workspace_id="ring_editor", help_topic_id="ring_editor"),
        DesktopShellCommandSpec("ring.editor.open", "Редактировать циклический сценарий", "Работать со сценарием, дорогой, сегментами и производными файлами прямо в рабочем шаге.", "ring_editor", "hosted_action", "Окна -> Редактор циклического сценария -> Редактор", capability_ids=("simulation.scenario_ring",), launch_surface="workspace", status_label="Рабочий раздел", help_topic_id="ring_editor", search_aliases=("редактор циклического сценария", "циклический сценарий", "редактор кольца", "сценарии", "генерация дороги")),
        DesktopShellCommandSpec("ring.legacy_editor.open", "Сервисный редактор сценария", "Открыть прежний редактор сценария только для восстановления или сравнения поведения.", "ring_editor", "launch_module", "Сервис -> Старые окна -> Сценарий", module="pneumo_solver_ui.tools.desktop_ring_scenario_editor", capability_ids=("simulation.scenario_ring",), launch_surface="legacy_bridge", status_label="Сервисный fallback", help_topic_id="ring_editor", availability="support_fallback"),
        DesktopShellCommandSpec("workspace.test_matrix.open", "Перейти к набору испытаний", "Перейти к матрице испытаний, стадиям, ручным изменениям и снимку набора.", "test_matrix", "open_workspace", "Окна -> Набор испытаний", target_workspace_id="test_matrix", capability_ids=("calculation.validation_and_prechecks",), help_topic_id="test_matrix", search_aliases=("матрица испытаний", "снимок набора", "контроль набора", "зафиксировать набор")),
        DesktopShellCommandSpec("test.center.open", "Проверить набор испытаний", "Подготовить, проверить и зафиксировать снимок набора перед расчётом прямо в рабочем шаге.", "test_matrix", "hosted_action", "Окна -> Набор испытаний -> Проверка набора", capability_ids=("calculation.validation_and_prechecks",), launch_surface="workspace", status_label="Рабочий раздел", help_topic_id="test_matrix", search_aliases=("набор испытаний", "снимок набора", "контроль набора", "проверка набора")),
        DesktopShellCommandSpec("test.selection.show", "Открыть карточку испытания", "Открыть карточку текущего испытания, режим включения, длительность и связанные файлы в дочерней dock-панели.", "test_matrix", "hosted_action", "Окна -> Набор испытаний -> Карточка испытания", capability_ids=("calculation.validation_and_prechecks",), launch_surface="workspace", status_label="Карточка испытания", help_topic_id="test_matrix", automation_id="TS-BTN-DETAIL", search_aliases=("карточка испытания", "текущее испытание", "параметры испытания")),
        DesktopShellCommandSpec("test.validation.show", "Показать проверку набора", "Показать результат проверки набора, связи с исходными данными и сценарием в дочерней dock-панели.", "test_matrix", "hosted_action", "Окна -> Набор испытаний -> Проверка", capability_ids=("calculation.validation_and_prechecks",), launch_surface="workspace", status_label="Проверка набора", help_topic_id="test_matrix", automation_id="TS-BTN-VALIDATION-DOCK", search_aliases=("проверка набора", "готовность набора", "контроль испытаний")),
        DesktopShellCommandSpec("test.snapshot.show", "Показать снимок набора", "Показать состояние снимка набора для базового прогона в дочерней dock-панели.", "test_matrix", "hosted_action", "Окна -> Набор испытаний -> Снимок", capability_ids=("calculation.validation_and_prechecks",), launch_surface="workspace", status_label="Снимок набора", help_topic_id="test_matrix", automation_id="TS-BTN-SNAPSHOT-DOCK", search_aliases=("снимок набора", "зафиксировать набор", "передача в базовый прогон")),
        DesktopShellCommandSpec("test.autotest.run", "Запустить автономную проверку", "Запустить автономные проверки проекта из рабочего шага набора испытаний, показать лог и папку артефактов без старого test center.", "test_matrix", "hosted_action", "Окна -> Набор испытаний -> Автономная проверка", capability_ids=("calculation.validation_and_prechecks", "tools.diagnostics_and_bundle"), launch_surface="workspace", status_label="Автономная проверка", help_topic_id="test_matrix", automation_id="TS-BTN-AUTOTEST-RUN", search_aliases=("автотест", "autotest", "автономная проверка", "проверки проекта", "run_autotest")),
        DesktopShellCommandSpec("test.legacy_center.open", "Сервисный центр набора испытаний", "Открыть прежний центр набора испытаний только для восстановления или сравнения поведения.", "test_matrix", "launch_module", "Сервис -> Старые окна -> Набор испытаний", module="pneumo_solver_ui.tools.test_center_gui", capability_ids=("calculation.validation_and_prechecks",), launch_surface="legacy_bridge", status_label="Сервисный fallback", help_topic_id="test_matrix", availability="support_fallback"),
        DesktopShellCommandSpec("workspace.baseline_run.open", "Перейти к базовому прогону", "Перейти к истории опорного прогона и передаче результата в оптимизацию.", "baseline_run", "open_workspace", "Окна -> Базовый прогон", target_workspace_id="baseline_run", help_topic_id="baseline_run", search_aliases=("опорный прогон", "базовый прогон", "история прогона", "настройка расчёта")),
        DesktopShellCommandSpec("baseline.run_setup.open", "Настроить базовый прогон", "Открыть настройку профиля, режима выполнения и проверки набора испытаний прямо в рабочем шаге базового прогона.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Настройка запуска", capability_ids=("calculation.run_setup", "calculation.baseline_run", "calculation.launch"), launch_surface="workspace", status_label="Рабочий раздел", help_topic_id="baseline_run", search_aliases=("базовый прогон", "опорный прогон", "настройка расчёта", "запуск расчёта", "предпросмотр дороги")),
        DesktopShellCommandSpec("baseline.run_setup.verify", "Проверить готовность базового прогона", "Проверить, что снимок набора испытаний готов для базового прогона.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Проверка готовности", capability_ids=("calculation.run_setup", "calculation.validation_and_prechecks"), launch_surface="workspace", status_label="Проверка готовности", help_topic_id="baseline_run", automation_id="BL-BTN-RUN-CHECK", search_aliases=("проверить базовый прогон", "готовность набора", "проверка перед запуском")),
        DesktopShellCommandSpec("baseline.run_setup.prepare_checked", "Проверить и подготовить запуск", "Проверить готовность и подготовить запуск базового прогона без ухода из основного маршрута.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Проверить и подготовить запуск", capability_ids=("calculation.run_setup", "calculation.baseline_run", "calculation.launch"), launch_surface="workspace", status_label="Проверка перед запуском", help_topic_id="baseline_run", automation_id="BL-BTN-RUN-CHECKED", search_aliases=("проверить и запустить", "подготовить запуск", "запуск базового прогона")),
        DesktopShellCommandSpec("baseline.run_setup.prepare", "Подготовить запуск", "Подготовить запуск базового прогона по актуальному снимку набора испытаний.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Подготовить запуск", capability_ids=("calculation.run_setup", "calculation.baseline_run", "calculation.launch"), launch_surface="workspace", status_label="Подготовка запуска", help_topic_id="baseline_run", automation_id="BL-BTN-RUN-PLAIN", search_aliases=("запустить базовый прогон", "подготовить базовый прогон", "обычный запуск")),
        DesktopShellCommandSpec("baseline.run.execute", "Запустить базовый прогон", "Запустить подготовленный базовый прогон в фоне и добавить результат в историю для явного просмотра и принятия.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Запустить в фоне", capability_ids=("calculation.run_setup", "calculation.baseline_run", "calculation.launch"), launch_surface="workspace", status_label="Фоновый запуск", help_topic_id="baseline_run", automation_id="BL-BTN-RUN-EXECUTE", search_aliases=("запустить базовый прогон", "фоновый запуск", "начать базовый прогон", "расчёт базового прогона")),
        DesktopShellCommandSpec("baseline.run.cancel", "Отменить базовый прогон", "Остановить текущий фоновый базовый прогон без принятия результата.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Отменить запуск", capability_ids=("calculation.run_setup", "calculation.baseline_run", "calculation.launch"), launch_surface="workspace", status_label="Остановка запуска", help_topic_id="baseline_run", automation_id="BL-BTN-RUN-CANCEL", search_aliases=("отменить базовый прогон", "остановить расчёт", "прервать базовый прогон")),
        DesktopShellCommandSpec("baseline.run.open_log", "Показать журнал базового прогона", "Показать журнал последнего подготовленного или выполненного базового прогона в дочерней dock-панели рабочей области.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Журнал", capability_ids=("calculation.run_setup", "calculation.baseline_run", "calculation.launch"), launch_surface="workspace", status_label="Журнал запуска", help_topic_id="baseline_run", automation_id="BL-BTN-RUN-OPEN-LOG", search_aliases=("журнал базового прогона", "лог запуска", "показать лог расчёта")),
        DesktopShellCommandSpec("baseline.run.open_result", "Показать результаты прогона", "Показать файлы последнего подготовленного или выполненного базового прогона в дочерней dock-панели рабочей области.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Результаты", capability_ids=("calculation.run_setup", "calculation.baseline_run", "calculation.launch"), launch_surface="workspace", status_label="Результаты прогона", help_topic_id="baseline_run", automation_id="BL-BTN-RUN-OPEN-RESULT", search_aliases=("папка результата", "результат базового прогона", "файлы расчёта")),
        DesktopShellCommandSpec("baseline.run.road_preview", "Показать предпросмотр дороги", "Показать параметры предпросмотра дороги и расчёта в дочерней dock-панели рабочей области.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Предпросмотр дороги", capability_ids=("calculation.run_setup", "calculation.baseline_run", "calculation.launch"), launch_surface="workspace", status_label="Предпросмотр дороги", help_topic_id="baseline_run", automation_id="BL-BTN-RUN-ROAD-PREVIEW", search_aliases=("предпросмотр дороги", "параметры дороги", "проверить дорогу")),
        DesktopShellCommandSpec("baseline.run.warnings", "Показать предупреждения запуска", "Показать условия, которые могут ограничить подготовку или выполнение базового прогона.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Предупреждения", capability_ids=("calculation.run_setup", "calculation.baseline_run", "calculation.launch"), launch_surface="workspace", status_label="Предупреждения запуска", help_topic_id="baseline_run", automation_id="BL-BTN-RUN-WARNINGS", search_aliases=("предупреждения запуска", "проверить предупреждения", "ограничения запуска")),
        DesktopShellCommandSpec("baseline.optimization_handoff.show", "Показать передачу в оптимизацию", "Показать активный опорный прогон, состояние сверки и следующий шаг перед переходом в оптимизацию.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Передача в оптимизацию", capability_ids=("calculation.baseline_run", "optimization.orchestration_and_databases"), launch_surface="workspace", status_label="Передача в оптимизацию", help_topic_id="baseline_run", automation_id="BL-BTN-HANDOFF-OPTIMIZATION", search_aliases=("передача в оптимизацию", "handoff оптимизации", "что увидит оптимизация", "опорный прогон для оптимизации")),
        DesktopShellCommandSpec("baseline.legacy_run_setup.open", "Сервисный центр запуска", "Открыть прежний центр запуска только для восстановления или сравнения поведения.", "baseline_run", "launch_module", "Сервис -> Старые окна -> Базовый прогон", module="pneumo_solver_ui.tools.desktop_run_setup_center", capability_ids=("calculation.run_setup", "calculation.baseline_run", "calculation.launch"), launch_surface="legacy_bridge", status_label="Сервисный fallback", help_topic_id="baseline_run", availability="support_fallback"),
        DesktopShellCommandSpec("baseline.center.open", "Перейти к базовому прогону", "Перейти к базовому прогону: активный результат, история, просмотр, принятие и восстановление.", "baseline_run", "open_workspace", "Окна -> Базовый прогон -> Просмотр и управление", target_workspace_id="baseline_run", launch_surface="workspace", status_label="Рабочий раздел", help_topic_id="baseline_run", search_aliases=("базовый прогон", "активный опорный прогон", "история прогона", "запустить опорный прогон", "базовый запуск")),
        DesktopShellCommandSpec("baseline.review", "Просмотреть выбранный опорный прогон", "Показать активный или исторический прогон, матрицу расхождений и правила применения без изменения активного результата.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Просмотр опорного прогона", status_label="Только просмотр", help_topic_id="baseline_run", automation_id="BL-BTN-REVIEW", search_aliases=("просмотр опорного прогона", "проверить опорный прогон", "матрица расхождений", "история опорного прогона")),
        DesktopShellCommandSpec("baseline.adopt", "Принять выбранный опорный прогон", "Явно принять проверенный выбранный прогон как новый активный результат; молчаливая подмена запрещена.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Принять опорный прогон", status_label="Явное действие", help_topic_id="baseline_run", automation_id="BL-BTN-ADOPT", search_aliases=("принять опорный прогон", "сделать прогон активным", "явно принять результат", "базовый прогон")),
        DesktopShellCommandSpec("baseline.restore", "Восстановить исторический опорный прогон", "Явно восстановить исторический прогон как активный; расхождение по набору, исходным данным или режиму требует предупреждения и подтверждения.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Восстановить опорный прогон", status_label="Явное действие", help_topic_id="baseline_run", automation_id="BL-BTN-RESTORE", search_aliases=("восстановить опорный прогон", "исторический опорный прогон", "расхождение опорного прогона", "явное восстановление")),
        DesktopShellCommandSpec("workspace.optimization.open", "Перейти к оптимизации", "Перейти к целям расчёта, обязательным ограничениям и активному режиму оптимизации.", "optimization", "open_workspace", "Окна -> Оптимизация", target_workspace_id="optimization", capability_ids=("optimization.orchestration_and_databases",), help_topic_id="optimization"),
        DesktopShellCommandSpec("optimization.center.open", "Настроить оптимизацию", "Работать с целями, ограничениями, основным расчётом и расширенной координацией прямо в рабочем шаге.", "optimization", "hosted_action", "Окна -> Оптимизация -> Настройка и запуск", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="Рабочий раздел", help_topic_id="optimization", search_aliases=("поэтапный запуск", "основной расчёт", "распределённая координация", "решатель")),
        DesktopShellCommandSpec("optimization.readiness.check", "Проверить готовность оптимизации", "Проверить цели, ограничение, опорный прогон и набор испытаний перед запуском.", "optimization", "hosted_action", "Окна -> Оптимизация -> Проверка готовности", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="Проверка готовности", help_topic_id="optimization", search_aliases=("проверить оптимизацию", "готовность оптимизации", "проверка перед оптимизацией")),
        DesktopShellCommandSpec("optimization.primary_launch.prepare", "Подготовить основной запуск", "Собрать видимые условия запуска и следующий шаг без перехода в подробную настройку.", "optimization", "hosted_action", "Окна -> Оптимизация -> Подготовить основной запуск", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="Подготовка запуска", help_topic_id="optimization", search_aliases=("подготовить оптимизацию", "основной запуск оптимизации", "запуск оптимизации")),
        DesktopShellCommandSpec("optimization.primary_launch.execute", "Запустить оптимизацию", "Запустить рекомендуемый основной путь оптимизации в фоне из рабочего шага.", "optimization", "hosted_action", "Окна -> Оптимизация -> Запустить оптимизацию", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="Фоновый запуск", help_topic_id="optimization", automation_id="OP-BTN-EXECUTE", search_aliases=("запустить оптимизацию", "запустить основной расчёт", "основной запуск", "старт оптимизации")),
        DesktopShellCommandSpec("optimization.primary_launch.soft_stop", "Мягкая остановка оптимизации", "Запросить остановку активной оптимизации через файл остановки без немедленного завершения процесса.", "optimization", "hosted_action", "Окна -> Оптимизация -> Мягкая остановка", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="Остановка запуска", help_topic_id="optimization", automation_id="OP-BTN-SOFT-STOP", search_aliases=("мягко остановить оптимизацию", "stop файл", "остановить после итерации")),
        DesktopShellCommandSpec("optimization.primary_launch.hard_stop", "Остановить оптимизацию сейчас", "Немедленно остановить активный запуск оптимизации, если мягкая остановка не подходит.", "optimization", "hosted_action", "Окна -> Оптимизация -> Остановить сейчас", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="Остановка запуска", help_topic_id="optimization", automation_id="OP-BTN-HARD-STOP", search_aliases=("остановить оптимизацию", "прервать оптимизацию", "убить запуск")),
        DesktopShellCommandSpec("optimization.primary_launch.open_log", "Открыть журнал оптимизации", "Открыть журнал последнего активного или подготовленного запуска оптимизации.", "optimization", "hosted_action", "Окна -> Оптимизация -> Открыть журнал", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="Журнал запуска", help_topic_id="optimization", automation_id="OP-BTN-OPEN-LOG", search_aliases=("журнал оптимизации", "лог основного расчёта", "открыть лог оптимизации")),
        DesktopShellCommandSpec("optimization.primary_launch.open_run_dir", "Открыть папку запуска оптимизации", "Открыть папку последнего активного или подготовленного запуска оптимизации.", "optimization", "hosted_action", "Окна -> Оптимизация -> Открыть папку запуска", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="Папка запуска", help_topic_id="optimization", automation_id="OP-BTN-OPEN-RUN-DIR", search_aliases=("папка оптимизации", "файлы основного расчёта", "открыть папку запуска")),
        DesktopShellCommandSpec("optimization.history.show", "Показать историю запусков", "Показать историю запусков оптимизации в дочерней dock-панели рабочей области.", "optimization", "hosted_action", "Окна -> Оптимизация -> История запусков", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="История запусков", help_topic_id="optimization", automation_id="OP-BTN-HISTORY", search_aliases=("история оптимизации", "история запусков", "прошлые прогоны")),
        DesktopShellCommandSpec("optimization.finished.show", "Показать готовые прогоны", "Показать готовые и частично готовые прогоны оптимизации в дочерней dock-панели рабочей области.", "optimization", "hosted_action", "Окна -> Оптимизация -> Готовые прогоны", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="Готовые прогоны", help_topic_id="optimization", automation_id="OP-BTN-FINISHED", search_aliases=("готовые прогоны", "завершённые прогоны", "проверенные прогоны")),
        DesktopShellCommandSpec("optimization.handoff.show", "Показать передачу стадий", "Показать кандидатов продолжения через координатор в дочерней dock-панели рабочей области.", "optimization", "hosted_action", "Окна -> Оптимизация -> Передача стадий", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="Передача стадий", help_topic_id="optimization", automation_id="OP-BTN-HANDOFF", search_aliases=("передача стадий", "кандидаты продолжения", "продолжить оптимизацию")),
        DesktopShellCommandSpec("optimization.packaging.show", "Показать упаковку и выпуск", "Показать готовность выпуска по прогонам оптимизации в дочерней dock-панели рабочей области.", "optimization", "hosted_action", "Окна -> Оптимизация -> Упаковка и выпуск", capability_ids=("optimization.orchestration_and_databases",), launch_surface="workspace", status_label="Упаковка и выпуск", help_topic_id="optimization", automation_id="OP-BTN-PACKAGING", search_aliases=("упаковка", "выпуск", "готовность выпуска")),
        DesktopShellCommandSpec("optimization.legacy_center.open", "Сервисный центр оптимизации", "Открыть прежний центр оптимизации только для восстановления или сравнения поведения.", "optimization", "launch_module", "Сервис -> Старые окна -> Оптимизация", module="pneumo_solver_ui.tools.desktop_optimizer_center", capability_ids=("optimization.orchestration_and_databases",), launch_surface="legacy_bridge", status_label="Сервисный fallback", help_topic_id="optimization", availability="support_fallback"),
        DesktopShellCommandSpec("workspace.results_analysis.open", "Перейти к анализу результатов", "Перейти к графикам, проверкам, сравнению и файлам результатов.", "results_analysis", "open_workspace", "Окна -> Анализ результатов", target_workspace_id="results_analysis", capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"), help_topic_id="results_analysis"),
        DesktopShellCommandSpec("results.center.open", "Анализировать результаты", "Работать с проверками, сравнением и файлами результатов прямо в рабочем шаге анализа.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Графики и проверка", capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"), launch_surface="workspace", status_label="Рабочий раздел", help_topic_id="results_analysis", search_aliases=("результаты", "анализ", "проверка")),
        DesktopShellCommandSpec("results.run_materials.show", "Показать материалы прогона", "Показать архив, каталоги проверок, отчёты и следующий шаг после последнего запуска.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Материалы прогона", capability_ids=("results.compare_and_review", "tools.diagnostics_and_bundle"), launch_surface="workspace", status_label="Материалы прогона", help_topic_id="results_analysis", automation_id="RS-BTN-RUN-MATERIALS", search_aliases=("материалы прогона", "последний прогон", "каталог проверок после запуска", "каталог проверки проекта", "что смотреть после запуска")),
        DesktopShellCommandSpec("results.selected_material.show", "Выбранный материал", "Показать карточку выбранного файла результата, путь для сравнения, связь с анимацией и краткий предпросмотр без старого окна анализа.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Выбранный материал", capability_ids=("results.compare_and_review", "visualization.animator_and_mnemo"), launch_surface="workspace", status_label="Карточка материала", help_topic_id="results_analysis", automation_id="RS-BTN-SELECTED-MATERIAL", search_aliases=("выбранный материал", "карточка результата", "детали результата", "материал результата", "selected material")),
        DesktopShellCommandSpec("results.chart_detail.show", "Подробности графика", "Показать выбранную числовую серию, диапазон, samples и compare-context прямо в рабочем шаге анализа результатов.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Подробности графика", capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"), launch_surface="workspace", status_label="Подробности графика", help_topic_id="results_analysis", automation_id="RS-BTN-CHART-DETAIL", search_aliases=("подробности графика", "детали серии", "числовая серия", "samples графика", "chart detail")),
        DesktopShellCommandSpec("results.engineering_qa.show", "Инженерная проверка", "Показать готовность инженерного разбора, найденные пробелы и следующий шаг внутри анализа результатов.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Инженерная проверка", capability_ids=("analysis.influence_and_exploration", "results.compare_and_review"), launch_surface="workspace", status_label="Инженерная проверка", help_topic_id="results_analysis", automation_id="RS-BTN-ENGINEERING-QA", search_aliases=("инженерная проверка", "инженерный разбор", "пробелы анализа", "готовность анализа", "анализ влияния")),
        DesktopShellCommandSpec("results.engineering_candidates.show", "Кандидаты анализа", "Показать оптимизационные прогоны, готовность к инженерному разбору, недостающие входные данные и причины блокировки.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Кандидаты анализа", capability_ids=("analysis.influence_and_exploration", "optimization.orchestration_and_databases"), launch_surface="workspace", status_label="Кандидаты анализа", help_topic_id="results_analysis", automation_id="RS-BTN-ENGINEERING-CANDIDATES", search_aliases=("кандидаты анализа", "готовые прогоны", "выбрать прогон анализа", "прогоны оптимизации", "недостающие входные данные")),
        DesktopShellCommandSpec("results.engineering_run.pin", "Зафиксировать прогон", "Зафиксировать готовый оптимизационный прогон как источник инженерного разбора и показать созданные материалы.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Зафиксировать прогон", capability_ids=("analysis.influence_and_exploration", "optimization.orchestration_and_databases"), launch_surface="workspace", status_label="Выбранный прогон", help_topic_id="results_analysis", automation_id="RS-BTN-ENGINEERING-PIN-RUN", search_aliases=("зафиксировать прогон", "выбранный прогон", "принять кандидат анализа", "источник инженерного разбора", "готовый прогон")),
        DesktopShellCommandSpec("results.engineering_influence.run", "Рассчитать влияние системы", "Запустить расчёт влияния системы для выбранного прогона без открытия старого инженерного окна.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Рассчитать влияние системы", capability_ids=("analysis.influence_and_exploration", "results.compare_and_review"), launch_surface="workspace", status_label="Расчёт влияния", help_topic_id="results_analysis", automation_id="RS-BTN-ENGINEERING-INFLUENCE-RUN", search_aliases=("рассчитать влияние", "влияние системы запуск", "system influence", "анализ влияния запустить", "расчёт влияния системы")),
        DesktopShellCommandSpec("results.engineering_full_report.run", "Полный отчёт", "Собрать полный отчёт по выбранному прогону без открытия старого инженерного окна.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Полный отчёт", capability_ids=("analysis.influence_and_exploration", "results.compare_and_review"), launch_surface="workspace", status_label="Полный отчёт", help_topic_id="results_analysis", automation_id="RS-BTN-ENGINEERING-FULL-REPORT-RUN", search_aliases=("полный отчёт", "собрать полный отчёт", "full report", "отчёт по прогону", "полный инженерный отчёт")),
        DesktopShellCommandSpec("results.engineering_param_staging.run", "Диапазоны влияния", "Построить диапазоны и этапы подбора по данным влияния выбранного прогона без открытия старого инженерного окна.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Диапазоны влияния", capability_ids=("analysis.influence_and_exploration", "results.compare_and_review"), launch_surface="workspace", status_label="Диапазоны влияния", help_topic_id="results_analysis", automation_id="RS-BTN-ENGINEERING-PARAM-STAGING-RUN", search_aliases=("диапазоны влияния", "параметрический staging", "param staging", "этапы подбора", "stages influence")),
        DesktopShellCommandSpec("results.influence_review.show", "Влияние системы", "Показать материалы влияния, таблицы чувствительности, графики влияния и недостающие артефакты внутри анализа результатов.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Влияние системы", capability_ids=("analysis.influence_and_exploration", "results.compare_and_review"), launch_surface="workspace", status_label="Влияние системы", help_topic_id="results_analysis", automation_id="RS-BTN-INFLUENCE-REVIEW", search_aliases=("влияние системы", "таблица чувствительности", "анализ влияния", "инженерные материалы", "артефакты разбора")),
        DesktopShellCommandSpec("results.compare_influence.show", "Сравнение влияния", "Показать связи параметров и целевых метрик, top-связи и готовность источников результата внутри анализа результатов.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Сравнение влияния", capability_ids=("analysis.influence_and_exploration", "results.compare_and_review"), launch_surface="workspace", status_label="Сравнение влияния", help_topic_id="results_analysis", automation_id="RS-BTN-COMPARE-INFLUENCE", search_aliases=("сравнение влияния", "связи параметров", "корреляции результата", "топ связи", "параметры и метрики")),
        DesktopShellCommandSpec("results.engineering_evidence.export", "Сохранить материалы разбора", "Сохранить инженерные материалы, сводку влияния и найденные пробелы для проверки проекта.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Сохранить материалы разбора", capability_ids=("analysis.influence_and_exploration", "tools.diagnostics_and_bundle"), launch_surface="workspace", status_label="Сохранение материалов", help_topic_id="results_analysis", automation_id="RS-BTN-ENGINEERING-EVIDENCE", search_aliases=("сохранить материалы разбора", "материалы инженерного анализа", "материалы проверки проекта", "передать в диагностику")),
        DesktopShellCommandSpec("results.engineering_animation_link.export", "Подготовить связь с анимацией", "Подготовить связь выбранного результата с рабочим шагом анимации и показать созданные файлы.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Связь с анимацией", capability_ids=("analysis.influence_and_exploration", "visualization.animator_and_mnemo"), launch_surface="workspace", status_label="Связь с анимацией", help_topic_id="results_analysis", automation_id="RS-BTN-ENGINEERING-ANIMATION-LINK", search_aliases=("связь с анимацией", "анимация инженерного анализа", "подготовить анимацию результата", "передать выбранный результат")),
        DesktopShellCommandSpec("results.compare.prepare", "Подготовить сравнение", "Подготовить текущий контекст сравнения без ухода из рабочего шага анализа результатов.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Подготовить сравнение", capability_ids=("results.compare_and_review",), launch_surface="workspace", status_label="Подготовка сравнения", help_topic_id="results_analysis", search_aliases=("подготовить сравнение", "сравнение прогонов", "сравнить результаты")),
        DesktopShellCommandSpec("results.evidence.prepare", "Подготовить материалы проверки", "Подготовить материалы анализа для проверки проекта и архива.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Материалы проверки", capability_ids=("results.compare_and_review", "tools.diagnostics_and_bundle"), launch_surface="workspace", status_label="Подготовка материалов", help_topic_id="results_analysis", search_aliases=("материалы проверки", "передать анализ", "архив проекта")),
        DesktopShellCommandSpec("results.animation.prepare", "Передать в анимацию", "Передать выбранный материал анализа в рабочий шаг анимации без потери контекста результата.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Передать в анимацию", capability_ids=("results.compare_and_review", "visualization.animator_and_mnemo"), launch_surface="workspace", status_label="Передача в анимацию", help_topic_id="results_analysis", automation_id="RS-BTN-HANDOFF-ANIMATION", search_aliases=("передать в анимацию", "анимация результата", "проверить выбранный результат")),
        DesktopShellCommandSpec("results.legacy_center.open", "Сервисный центр анализа", "Открыть прежний центр анализа только для восстановления или сравнения поведения.", "results_analysis", "launch_module", "Сервис -> Старые окна -> Анализ результатов", module="pneumo_solver_ui.tools.desktop_results_center", capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"), launch_surface="legacy_bridge", status_label="Сервисный fallback", help_topic_id="results_analysis", availability="support_fallback"),
        DesktopShellCommandSpec("results.compare.open", "Показать сравнение", "Показать сравнение выбранного результата с текущими данными и открыть первый графический разбор прямо в анализе.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Показать сравнение", capability_ids=("results.compare_and_review",), launch_surface="workspace", status_label="Сравнение результатов", help_topic_id="results_analysis", automation_id="RS-BTN-OPEN-COMPARE", search_aliases=("сравнение", "сравнение прогонов", "показать сравнение", "график сравнения")),
        DesktopShellCommandSpec("results.legacy_compare.open", "Сервисный просмотр сравнения", "Открыть прежний просмотр сравнения только для восстановления или сравнения поведения.", "results_analysis", "launch_module", "Сервис -> Старые окна -> Сравнение", module="pneumo_solver_ui.qt_compare_viewer", capability_ids=("results.compare_and_review",), launch_surface="external_window", help_topic_id="results_analysis", availability="support_fallback"),
        DesktopShellCommandSpec("analysis.engineering.open", "Сервисный инженерный анализ", "Открыть прежний инженерный анализ только для восстановления или сравнения поведения.", "results_analysis", "launch_module", "Сервис -> Старые окна -> Инженерный анализ", module="pneumo_solver_ui.tools.desktop_engineering_analysis_center", capability_ids=("analysis.influence_and_exploration",), launch_surface="tooling", help_topic_id="results_analysis", status_label="Сервисный fallback", availability="support_fallback"),
        DesktopShellCommandSpec("workspace.animation.open", "Перейти к анимации", "Перейти к аниматору, мнемосхеме и честным визуальным режимам.", "animation", "open_workspace", "Окна -> Анимация", target_workspace_id="animation", capability_ids=("visualization.animator_and_mnemo",), help_topic_id="animation"),
        DesktopShellCommandSpec("animation.animator.open", "Анимировать результат", "Проверить готовность анимации и открыть управление сценой внутри рабочего шага.", "animation", "hosted_action", "Окна -> Анимация -> Аниматор", capability_ids=("visualization.animator_and_mnemo",), launch_surface="workspace", status_label="Рабочий раздел", help_topic_id="animation", search_aliases=("аниматор", "анимация", "трёхмерный вид")),
        DesktopShellCommandSpec("animation.animator.launch", "Проверить движение", "Показать проверку движения внутри рабочего шага анимации.", "animation", "hosted_action", "Окна -> Анимация -> Проверить движение", capability_ids=("visualization.animator_and_mnemo",), launch_surface="workspace", status_label="Графическая проверка", help_topic_id="animation", automation_id="AM-DETACH", search_aliases=("проверить движение", "графическая проверка", "анализ движения")),
        DesktopShellCommandSpec("animation.mnemo.open", "Показать мнемосхему", "Проверить журнал мнемосхемы и связанные события внутри рабочего шага.", "animation", "hosted_action", "Окна -> Анимация -> Мнемосхема", capability_ids=("visualization.animator_and_mnemo",), launch_surface="workspace", status_label="Рабочий раздел", help_topic_id="animation", search_aliases=("мнемосхема", "пневмосхема")),
        DesktopShellCommandSpec("animation.mnemo.launch", "Проверить схему", "Показать проверку мнемосхемы внутри рабочего шага анимации.", "animation", "hosted_action", "Окна -> Анимация -> Проверить схему", capability_ids=("visualization.animator_and_mnemo",), launch_surface="workspace", status_label="Графическая проверка", help_topic_id="animation", automation_id="AM-BTN-DETACH-MNEMO", search_aliases=("проверить схему", "проверить мнемосхему", "события мнемосхемы")),
        DesktopShellCommandSpec("animation.diagnostics.prepare", "Передать в проверку проекта", "Передать текущий материал анимации в рабочий шаг проверки проекта без потери контекста сцены.", "animation", "hosted_action", "Окна -> Анимация -> Передать в проверку проекта", capability_ids=("visualization.animator_and_mnemo", "tools.diagnostics_and_bundle"), launch_surface="workspace", status_label="Передача в проверку проекта", help_topic_id="animation", automation_id="AM-BTN-HANDOFF-DIAGNOSTICS", search_aliases=("передать в проверку", "проверка проекта", "архив с анимацией")),
        DesktopShellCommandSpec("animation.legacy_animator.open", "Сервисный просмотр анимации", "Открыть прежний просмотр анимации только для восстановления или сравнения поведения.", "animation", "launch_module", "Сервис -> Старые окна -> Анимация", module="pneumo_solver_ui.desktop_animator.app", capability_ids=("visualization.animator_and_mnemo",), launch_surface="external_window", help_topic_id="animation", availability="support_fallback"),
        DesktopShellCommandSpec("animation.legacy_mnemo.open", "Сервисный просмотр мнемосхемы", "Открыть прежний просмотр мнемосхемы только для восстановления или сравнения поведения.", "animation", "launch_module", "Сервис -> Старые окна -> Мнемосхема", module="pneumo_solver_ui.desktop_mnemo.main", capability_ids=("visualization.animator_and_mnemo",), launch_surface="external_window", help_topic_id="animation", availability="support_fallback"),
        DesktopShellCommandSpec("workspace.diagnostics.open", "Перейти к проверке проекта", "Перейти к проверке проекта, архиву проекта и ручному копированию архива.", "diagnostics", "open_workspace", "Окна -> Проверка проекта", target_workspace_id="diagnostics", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics"),
        DesktopShellCommandSpec("diagnostics.full_check.run", "Полная проверка проекта", "Запустить полную проверку проекта и сохранение архива в рабочем шаге проверки проекта.", "diagnostics", "hosted_action", "Окна -> Проверка проекта -> Полная проверка проекта", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("полная проверка проекта", "full diagnostics", "run_full_diagnostics", "проверка проекта", "собрать диагностику"), status_label="Полная проверка проекта", launch_surface="workspace", automation_id="DG-BTN-FULL-CHECK"),
        DesktopShellCommandSpec("diagnostics.send_review.show", "Показать материалы отправки", "Показать архив, состояние копирования, проверки и материалы анимации перед ручной передачей.", "diagnostics", "hosted_action", "Окна -> Проверка проекта -> Материалы отправки", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("материалы отправки", "что отправлять", "передать архив", "папка архивов", "сведения об анимации"), status_label="Материалы отправки", launch_surface="workspace", automation_id="DG-BTN-SEND-REVIEW"),
        DesktopShellCommandSpec("diagnostics.collect_bundle", "Сохранить архив проекта", "Открыть проверку проекта и сохранить архив проекта через общее действие приложения.", "diagnostics", "hosted_action", "Окна -> Проверка проекта -> Сохранить архив проекта", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("сохранить архив", "архив проекта", "проверка проекта"), status_label="Всегда доступно"),
        DesktopShellCommandSpec("diagnostics.verify_bundle", "Проверить архив проекта", "Обновить проверку состава и состояния архива проекта.", "diagnostics", "hosted_action", "Окна -> Проверка проекта -> Проверить архив", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("проверить архив", "архив проекта", "проверка архива"), status_label="Проверка проекта"),
        DesktopShellCommandSpec("diagnostics.send_results", "Скопировать архив", "Скопировать сохранённый архив для ручной передачи.", "diagnostics", "hosted_action", "Окна -> Проверка проекта -> Скопировать архив", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("скопировать архив", "архив проекта", "передать вручную"), status_label="Проверка проекта"),
        DesktopShellCommandSpec("diagnostics.legacy_center.open", "Сервисная проверка проекта", "Открыть прежний центр проверки только для восстановления или сравнения поведения.", "diagnostics", "launch_module", "Сервис -> Старые окна -> Проверка проекта", module="pneumo_solver_ui.tools.desktop_diagnostics_center", capability_ids=("tools.diagnostics_and_bundle",), launch_surface="legacy_bridge", help_topic_id="diagnostics", status_label="Сервисный fallback", availability="support_fallback"),
        DesktopShellCommandSpec("workspace.app_settings.open", "Перейти к параметрам приложения", "Перейти к редким настройкам приложения и рабочего места.", "app_settings", "open_workspace", "Окна -> Параметры приложения", target_workspace_id="app_settings", help_topic_id="app_settings"),
        DesktopShellCommandSpec("workspace.tools.open", "Перейти к инструментам", "Перейти к вспомогательным, справочным и профессиональным окнам.", "tools", "open_workspace", "Окна -> Инструменты", target_workspace_id="tools", help_topic_id="tools"),
        DesktopShellCommandSpec("tools.geometry_reference.open", "Справочник геометрии", "Работать со справочником геометрии внутри рабочего места инструментов.", "tools", "hosted_action", "Окна -> Инструменты -> Справочник геометрии", capability_ids=("reference.geometry_and_guides", "analysis.influence_and_exploration"), launch_surface="workspace", help_topic_id="tools", search_aliases=("геометрия", "справочник", "reference center")),
        DesktopShellCommandSpec("tools.autotest.open", "Проверки проекта", "Выполнить автономные проверки внутри рабочего места инструментов.", "tools", "hosted_action", "Окна -> Инструменты -> Проверки", launch_surface="workspace", help_topic_id="tools", search_aliases=("autotest", "автотест", "проверки")),
        DesktopShellCommandSpec("tools.geometry_reference.legacy_open", "Сервисный справочник геометрии", "Открыть прежний справочник геометрии только для восстановления или сравнения поведения.", "tools", "launch_module", "Сервис -> Старые окна -> Справочник геометрии", module="pneumo_solver_ui.tools.desktop_geometry_reference_center", capability_ids=("reference.geometry_and_guides", "analysis.influence_and_exploration"), launch_surface="tooling", help_topic_id="tools", status_label="Сервисный fallback", availability="support_fallback"),
        DesktopShellCommandSpec("tools.autotest.legacy_open", "Сервисные проверки проекта", "Открыть прежнее окно проверок только для восстановления или сравнения поведения.", "tools", "launch_module", "Сервис -> Старые окна -> Проверки проекта", module="pneumo_solver_ui.tools.run_autotest_gui", launch_surface="tooling", help_topic_id="tools", status_label="Сервисный fallback", availability="support_fallback"),
        DesktopShellCommandSpec("tools.qt_main_shell.open", "Старое рабочее место Qt", "Открыть прежнее Qt-рабочее место только для восстановления или сравнения поведения.", "tools", "launch_module", "Сервис -> Старые окна -> Qt shell", module="pneumo_solver_ui.tools.desktop_main_shell_qt", launch_surface="tooling", help_topic_id="tools", status_label="Сервисный fallback", availability="support_fallback"),
        DesktopShellCommandSpec("tools.spec_shell.open", "Текущее рабочее место", "Сервисная команда текущего рабочего места; не используется как отдельный пользовательский вход.", "tools", "launch_module", "Сервис -> Старые окна -> Текущее рабочее место", module="pneumo_solver_ui.tools.desktop_gui_spec_shell", launch_surface="tooling", help_topic_id="tools", status_label="Сервисный fallback", availability="support_fallback"),
        DesktopShellCommandSpec("tools.legacy_shell.open", "Старое рабочее место Tk", "Открыть прежнее рабочее место во вкладках только для восстановления или сравнения поведения.", "tools", "launch_module", "Сервис -> Старые окна -> Tk shell", module="pneumo_solver_ui.tools.desktop_main_shell", launch_surface="tooling", help_topic_id="tools", status_label="Сервисный fallback", availability="support_fallback"),
        DesktopShellCommandSpec("results.compare.target.next", "Следующая пара сравнения", "Переключить активный материал сравнения и сразу обновить панель сравнения.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Следующая пара сравнения", capability_ids=("results.compare_and_review",), launch_surface="workspace", status_label="Смена compare-пары", help_topic_id="results_analysis", automation_id="RS-BTN-COMPARE-NEXT-TARGET", search_aliases=("следующая пара сравнения", "переключить compare пару", "сменить материал сравнения", "next compare target")),
        DesktopShellCommandSpec("results.compare.signal.next", "Следующий сигнал сравнения", "Переключить активную числовую серию и сразу обновить панель сравнения.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Следующий сигнал сравнения", capability_ids=("results.compare_and_review",), launch_surface="workspace", status_label="Смена compare-сигнала", help_topic_id="results_analysis", automation_id="RS-BTN-COMPARE-NEXT-SIGNAL", search_aliases=("следующий сигнал сравнения", "переключить compare сигнал", "сменить timeline сигнал", "next compare signal")),
        DesktopShellCommandSpec("results.compare.playhead.next", "Следующая точка сравнения", "Переключить следующую точку графика сравнения и сразу обновить панель анализа.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Следующая точка сравнения", capability_ids=("results.compare_and_review",), launch_surface="workspace", status_label="Смена точки сравнения", help_topic_id="results_analysis", automation_id="RS-BTN-COMPARE-NEXT-PLAYHEAD", search_aliases=("следующая точка сравнения", "переключить compare point", "сменить playhead", "следующая точка delta timeline", "next compare playhead")),
        DesktopShellCommandSpec("results.compare.window.next", "Следующее окно сравнения", "Переключить следующее окно времени на графике сравнения и сразу обновить панель анализа.", "results_analysis", "hosted_action", "Окна -> Анализ результатов -> Следующее окно сравнения", capability_ids=("results.compare_and_review",), launch_surface="workspace", status_label="Смена окна сравнения", help_topic_id="results_analysis", automation_id="RS-BTN-COMPARE-NEXT-WINDOW", search_aliases=("следующее окно сравнения", "переключить окно сравнения", "сменить окно времени", "следующее окно delta timeline", "next compare window")),
    )

    enriched: list[DesktopShellCommandSpec] = []
    parity_aliases = _load_parity_aliases()
    for command in commands:
        extra_aliases: list[str] = list(command.search_aliases)
        for capability_id in command.capability_ids:
            extra_aliases.extend(parity_aliases.get(capability_id, ()))
        enriched.append(
            _bind_command_catalog(
                DesktopShellCommandSpec(
                command_id=command.command_id,
                title=command.title,
                summary=command.summary,
                workspace_id=command.workspace_id,
                kind=command.kind,
                route_label=command.route_label,
                target_workspace_id=command.target_workspace_id,
                module=command.module,
                capability_ids=command.capability_ids,
                search_aliases=_dedupe(extra_aliases),
                web_aliases=command.web_aliases,
                launch_surface=command.launch_surface,
                status_label=command.status_label,
                help_topic_id=command.help_topic_id,
                automation_id=command.automation_id,
                tooltip_id=command.tooltip_id,
                availability=command.availability,
                access_key=command.access_key,
                hotkey=command.hotkey,
                )
            )
        )
    return tuple(enriched)


def build_workspace_map() -> dict[str, DesktopWorkspaceSpec]:
    return {workspace.workspace_id: workspace for workspace in build_shell_workspaces()}


def build_command_map() -> dict[str, DesktopShellCommandSpec]:
    return {command.command_id: command for command in build_shell_commands()}
