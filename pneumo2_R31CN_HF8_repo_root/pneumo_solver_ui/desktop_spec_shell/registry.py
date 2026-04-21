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
    "diagnostics.collect_bundle": "DG-BTN-COLLECT",
    "baseline.center.open": "BL-BTN-RUN",
    "baseline.review": "BL-BTN-REVIEW",
    "baseline.adopt": "BL-BTN-ADOPT",
    "baseline.restore": "BL-BTN-RESTORE",
    "optimization.center.open": "OP-BTN-LAUNCH",
    "results.compare.open": "RS-BTN-OPEN-ANALYTICS",
    "animation.animator.open": "AN-BTN-OPEN-ANIMATOR",
    "workspace.animation.open": "AM-VIEWPORT",
}

ROUTE_QUICK_ACTIONS_BY_WORKSPACE: dict[str, tuple[str, ...]] = {
    "input_data": ("input.editor.open", "workspace.ring_editor.open", "workspace.test_matrix.open"),
    "ring_editor": ("ring.editor.open", "workspace.test_matrix.open"),
    "test_matrix": ("test.center.open", "workspace.baseline_run.open", "workspace.ring_editor.open"),
    "baseline_run": ("baseline.run_setup.open", "baseline.review", "baseline.adopt", "baseline.restore", "workspace.optimization.open", "workspace.results_analysis.open"),
    "optimization": ("workspace.baseline_run.open", "optimization.center.open", "workspace.results_analysis.open", "workspace.diagnostics.open"),
    "results_analysis": ("results.center.open", "analysis.engineering.open", "results.compare.open", "workspace.animation.open", "workspace.diagnostics.open"),
    "animation": ("animation.animator.open", "animation.mnemo.open", "workspace.results_analysis.open"),
    "diagnostics": ("diagnostics.verify_bundle", "diagnostics.send_results", "diagnostics.collect_bundle"),
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
            launch_surface="legacy_bridge",
            next_step="После подготовки циклического сценария откройте набор испытаний и свяжите сценарии с матрицей испытаний.",
            hard_gate="Сценарии не должны редактироваться в других местах, кроме редактора циклического сценария.",
        details="Рабочее место открывает существующий редактор циклического сценария без создания второго источника данных.",
            units_policy="Параметры дороги и манёвра обязаны иметь единицы, диапазоны и справку.",
            graphics_policy="Профиль дороги и производные файлы обязаны быть связаны с числовыми параметрами.",
            search_aliases=("редактор циклического сценария", "циклический сценарий", "редактор кольца", "сценарии", "дорога"),
            quick_action_ids=("ring.editor.open",),
        ),
        DesktopWorkspaceSpec(
            workspace_id="test_matrix",
            title="Набор испытаний",
            group="Основная последовательность",
            route_order=40,
            kind="main",
            summary="Единый набор испытаний, стадий, расчётных настроек и связей со сценариями.",
            source_of_truth="Матрица испытаний хранит состав, порядок и параметры проверок.",
            launch_surface="legacy_bridge",
            next_step="После настройки набора испытаний переходите к расчёту, проверке или оптимизации.",
            hard_gate="Без актуального снимка набора испытаний нельзя запускать расчёт и оптимизацию.",
        details="Окно показывает текущий снимок набора, связи со сценариями и причины блокировок без технических меток.",
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
            quick_action_ids=("test.center.open",),
        ),
        DesktopWorkspaceSpec(
            workspace_id="baseline_run",
            title="Базовый прогон",
            group="Основная последовательность",
            route_order=50,
            kind="main",
            summary="Источник данных по опорному прогону, его истории и передаче в оптимизацию.",
            source_of_truth="Этот рабочий шаг отвечает за происхождение опорного прогона и явное принятие результата.",
            launch_surface="legacy_bridge",
            next_step="Запустите опорный прогон и затем переходите к оптимизации только после принятия опорного результата.",
            hard_gate="Без происхождения опорного прогона цели оптимизации и история запусков считаются неполными.",
        details="Рабочий шаг показывает условия запуска и открывает существующие окна без технических меток.",
            units_policy="Временные и расчётные настройки должны быть видимы вместе с происхождением опорного прогона.",
            graphics_policy="Сводка опорного прогона в главном окне всегда производная и обязана указывать источник данных.",
            search_aliases=("базовый прогон", "опорный прогон", "активный опорный прогон", "история прогона", "настройка расчёта"),
            quick_action_ids=("baseline.run_setup.open", "baseline.review", "baseline.adopt", "baseline.restore", "workspace.optimization.open", "workspace.results_analysis.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="optimization",
            title="Оптимизация",
            group="Основная последовательность",
            route_order=60,
            kind="main",
            summary="Цели расчёта, ограничения, история и ход выполнения оптимизации.",
            source_of_truth="Окно оптимизации держит активный способ запуска и условия выполнения.",
            launch_surface="legacy_bridge",
            next_step="Открывайте оптимизацию только после опорного прогона и держите один активный способ запуска.",
            hard_gate="Поэтапный запуск является основным режимом; распределённая координация разрешена только как расширенный режим той же последовательности.",
        details="Рабочее место обязано показывать цели расчёта, обязательные ограничения и происхождение опорного прогона рядом со входом в оптимизацию.",
            units_policy="Целевые показатели и ограничения обязаны показывать смысл и единицы в справке и происхождении данных.",
            graphics_policy="Любой ход выполнения должен честно показывать активный режим и источник опорного прогона.",
            capability_ids=("optimization.orchestration_and_databases",),
            search_aliases=_aliases_for_capabilities(("optimization.orchestration_and_databases",), "оптимизация", "поэтапный запуск", "решатель"),
            quick_action_ids=("optimization.center.open",),
        ),
        DesktopWorkspaceSpec(
            workspace_id="results_analysis",
            title="Анализ результатов",
            group="Основная последовательность",
            route_order=70,
            kind="main",
            summary="Графики, проверки, сравнение и анализ файлов после прогонов.",
            source_of_truth="Анализ результатов и окна сравнения являются производными представлениями над файлами прогонов.",
            launch_surface="legacy_bridge",
            next_step="Переходите сюда из опорного прогона или оптимизации и работайте от конкретного выбранного прогона.",
            hard_gate="Результаты и проверки не должны жить отдельными потерянными страницами вне выбранного прогона.",
        details="Рабочее место открывает анализ результатов и окно сравнения как согласованный рабочий шаг анализа.",
            units_policy="Графики и таблицы обязаны показывать единицы и источник данных.",
            graphics_policy="Окно сравнения и проверка обязаны помечать источник данных и время построения.",
            capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"),
            search_aliases=_aliases_for_capabilities(("results.compare_and_review", "analysis.influence_and_exploration"), "анализ", "результаты", "сравнение"),
            quick_action_ids=("results.center.open", "analysis.engineering.open", "results.compare.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="animation",
            title="Анимация",
            group="Основная последовательность",
            route_order=80,
            kind="main",
            summary="Визуальная проверка через аниматор и мнемосхему с честными режимами достоверности.",
            source_of_truth="Аниматор и мнемосхема остаются специализированными рабочими окнами, запускаемыми после выбора результата.",
            launch_surface="external_window",
            next_step="Переходите к анимации после выбора результата и возвращайтесь к источнику изменения после визуальной проверки.",
            hard_gate="Нельзя показывать расчётно подтверждённую графику там, где данных недостаточно.",
        details="Рабочее место удерживает последовательность работы, а графические окна остаются отдельными специализированными окнами.",
            units_policy="Наложения и панель свойств обязаны показывать единицы и статус достоверности.",
            graphics_policy="Всегда показывайте маркер достоверности: расчётно подтверждённый, по исходным данным или условный.",
            capability_ids=("visualization.animator_and_mnemo",),
            search_aliases=_aliases_for_capabilities(("visualization.animator_and_mnemo",), "анимация", "аниматор", "мнемосхема"),
            quick_action_ids=("animation.animator.open", "animation.mnemo.open"),
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
            quick_action_ids=("diagnostics.collect_bundle", "diagnostics.verify_bundle", "diagnostics.send_results"),
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
                "input.editor.open",
                "ring.editor.open",
                "test.center.open",
                "baseline.run_setup.open",
                "optimization.center.open",
                "results.center.open",
                "analysis.engineering.open",
                "results.compare.open",
                "animation.animator.open",
                "animation.mnemo.open",
                "diagnostics.legacy_center.open",
                "tools.geometry_reference.open",
                "tools.autotest.open",
                "tools.qt_main_shell.open",
                "tools.spec_shell.open",
                "tools.legacy_shell.open",
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
        DesktopShellCommandSpec("input.editor.open", "Редактировать исходные данные", "Работать с инженерным редактором исходных данных.", "input_data", "launch_module", "Окна -> Исходные данные -> Редактор исходных данных", module="pneumo_solver_ui.tools.desktop_input_editor", capability_ids=("input.project_entry_and_setup",), launch_surface="legacy_bridge", status_label="Рабочее окно", help_topic_id="input_data"),
        DesktopShellCommandSpec("workspace.ring_editor.open", "Перейти к редактору циклического сценария", "Перейти к сценарию, дороге, сегментам и производным файлам.", "ring_editor", "open_workspace", "Окна -> Редактор циклического сценария", target_workspace_id="ring_editor", help_topic_id="ring_editor"),
        DesktopShellCommandSpec("ring.editor.open", "Редактировать циклический сценарий", "Работать со сценарием, дорогой, сегментами и производными файлами.", "ring_editor", "launch_module", "Окна -> Редактор циклического сценария -> Редактор", module="pneumo_solver_ui.tools.desktop_ring_scenario_editor", launch_surface="legacy_bridge", status_label="Рабочее окно", help_topic_id="ring_editor", search_aliases=("редактор циклического сценария", "циклический сценарий", "редактор кольца", "сценарии", "генерация дороги")),
        DesktopShellCommandSpec("workspace.test_matrix.open", "Перейти к набору испытаний", "Перейти к матрице испытаний, стадиям, ручным изменениям и снимку набора.", "test_matrix", "open_workspace", "Окна -> Набор испытаний", target_workspace_id="test_matrix", capability_ids=("calculation.validation_and_prechecks",), help_topic_id="test_matrix", search_aliases=("матрица испытаний", "снимок набора", "контроль набора", "зафиксировать набор")),
        DesktopShellCommandSpec("test.center.open", "Проверить набор испытаний", "Подготовить, проверить и зафиксировать снимок набора перед расчётом.", "test_matrix", "launch_module", "Окна -> Набор испытаний -> Проверка набора", module="pneumo_solver_ui.tools.test_center_gui", capability_ids=("calculation.validation_and_prechecks",), launch_surface="legacy_bridge", status_label="Рабочее окно", help_topic_id="test_matrix", search_aliases=("набор испытаний", "снимок набора", "контроль набора", "проверка набора")),
        DesktopShellCommandSpec("workspace.baseline_run.open", "Перейти к базовому прогону", "Перейти к истории опорного прогона и передаче результата в оптимизацию.", "baseline_run", "open_workspace", "Окна -> Базовый прогон", target_workspace_id="baseline_run", help_topic_id="baseline_run", search_aliases=("опорный прогон", "базовый прогон", "история прогона", "настройка расчёта")),
        DesktopShellCommandSpec("baseline.run_setup.open", "Настроить и запустить базовый прогон", "Настроить расчёт, проверить дорогу и запустить базовый прогон после проверки набора испытаний.", "baseline_run", "launch_module", "Окна -> Базовый прогон -> Настройка и запуск", module="pneumo_solver_ui.tools.desktop_run_setup_center", capability_ids=("calculation.run_setup", "calculation.baseline_run", "calculation.launch"), launch_surface="legacy_bridge", status_label="Рабочее окно", help_topic_id="baseline_run", search_aliases=("базовый прогон", "опорный прогон", "настройка расчёта", "запуск расчёта", "предпросмотр дороги")),
        DesktopShellCommandSpec("baseline.center.open", "Перейти к базовому прогону", "Перейти к базовому прогону: активный результат, история, просмотр, принятие и восстановление.", "baseline_run", "open_workspace", "Окна -> Базовый прогон -> Просмотр и управление", target_workspace_id="baseline_run", launch_surface="workspace", status_label="Рабочий раздел", help_topic_id="baseline_run", search_aliases=("базовый прогон", "активный опорный прогон", "история прогона", "запустить опорный прогон", "базовый запуск")),
        DesktopShellCommandSpec("baseline.review", "Просмотреть выбранный опорный прогон", "Показать активный или исторический прогон, матрицу расхождений и правила применения без изменения активного результата.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Просмотр опорного прогона", status_label="Только просмотр", help_topic_id="baseline_run", automation_id="BL-BTN-REVIEW", search_aliases=("просмотр опорного прогона", "проверить опорный прогон", "матрица расхождений", "история опорного прогона")),
        DesktopShellCommandSpec("baseline.adopt", "Принять выбранный опорный прогон", "Явно принять проверенный выбранный прогон как новый активный результат; молчаливая подмена запрещена.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Принять опорный прогон", status_label="Явное действие", help_topic_id="baseline_run", automation_id="BL-BTN-ADOPT", search_aliases=("принять опорный прогон", "сделать прогон активным", "явно принять результат", "базовый прогон")),
        DesktopShellCommandSpec("baseline.restore", "Восстановить исторический опорный прогон", "Явно восстановить исторический прогон как активный; расхождение по набору, исходным данным или режиму требует предупреждения и подтверждения.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Восстановить опорный прогон", status_label="Явное действие", help_topic_id="baseline_run", automation_id="BL-BTN-RESTORE", search_aliases=("восстановить опорный прогон", "исторический опорный прогон", "расхождение опорного прогона", "явное восстановление")),
        DesktopShellCommandSpec("workspace.optimization.open", "Перейти к оптимизации", "Перейти к целям расчёта, обязательным ограничениям и активному режиму оптимизации.", "optimization", "open_workspace", "Окна -> Оптимизация", target_workspace_id="optimization", capability_ids=("optimization.orchestration_and_databases",), help_topic_id="optimization"),
        DesktopShellCommandSpec("optimization.center.open", "Настроить оптимизацию", "Работать с целями, ограничениями, поэтапным режимом и распределённой координацией.", "optimization", "launch_module", "Окна -> Оптимизация -> Настройка и запуск", module="pneumo_solver_ui.tools.desktop_optimizer_center", capability_ids=("optimization.orchestration_and_databases",), launch_surface="legacy_bridge", status_label="Рабочее окно", help_topic_id="optimization", search_aliases=("поэтапный запуск", "распределённая координация", "решатель")),
        DesktopShellCommandSpec("workspace.results_analysis.open", "Перейти к анализу результатов", "Перейти к графикам, проверкам, сравнению и файлам результатов.", "results_analysis", "open_workspace", "Окна -> Анализ результатов", target_workspace_id="results_analysis", capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"), help_topic_id="results_analysis"),
        DesktopShellCommandSpec("results.center.open", "Анализировать результаты", "Работать с графиками, проверками, сравнением и файлами результатов.", "results_analysis", "launch_module", "Окна -> Анализ результатов -> Графики и проверка", module="pneumo_solver_ui.tools.desktop_results_center", capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"), launch_surface="legacy_bridge", status_label="Рабочее окно", help_topic_id="results_analysis", search_aliases=("результаты", "анализ", "проверка")),
        DesktopShellCommandSpec("results.compare.open", "Сравнить прогоны", "Подробно сравнить выбранные прогоны из анализа результатов.", "results_analysis", "launch_module", "Окна -> Анализ результатов -> Сравнение прогонов", module="pneumo_solver_ui.qt_compare_viewer", capability_ids=("results.compare_and_review",), launch_surface="external_window", help_topic_id="results_analysis", search_aliases=("сравнение", "сравнение прогонов")),
        DesktopShellCommandSpec("analysis.engineering.open", "Инженерный анализ", "Работать с калибровкой, анализом влияния, сводками чувствительности и инженерным отчётом.", "results_analysis", "launch_module", "Окна -> Анализ результатов -> Инженерный анализ", module="pneumo_solver_ui.tools.desktop_engineering_analysis_center", capability_ids=("analysis.influence_and_exploration",), launch_surface="tooling", help_topic_id="results_analysis", search_aliases=("engineering analysis", "calibration", "influence", "sensitivity", "system influence", "калибровка", "влияние", "чувствительность")),
        DesktopShellCommandSpec("workspace.animation.open", "Перейти к анимации", "Перейти к аниматору, мнемосхеме и честным визуальным режимам.", "animation", "open_workspace", "Окна -> Анимация", target_workspace_id="animation", capability_ids=("visualization.animator_and_mnemo",), help_topic_id="animation"),
        DesktopShellCommandSpec("animation.animator.open", "Анимировать результат", "Проверить результат в аниматоре с приоритетом визуальной проверки.", "animation", "launch_module", "Окна -> Анимация -> Аниматор", module="pneumo_solver_ui.desktop_animator.app", capability_ids=("visualization.animator_and_mnemo",), launch_surface="external_window", help_topic_id="animation", search_aliases=("аниматор", "анимация", "трёхмерный вид")),
        DesktopShellCommandSpec("animation.mnemo.open", "Показать мнемосхему", "Показать мнемосхему результата.", "animation", "launch_module", "Окна -> Анимация -> Мнемосхема", module="pneumo_solver_ui.desktop_mnemo.main", capability_ids=("visualization.animator_and_mnemo",), launch_surface="external_window", help_topic_id="animation", search_aliases=("мнемосхема", "пневмосхема")),
        DesktopShellCommandSpec("workspace.diagnostics.open", "Перейти к проверке проекта", "Перейти к проверке проекта, архиву проекта и ручному копированию архива.", "diagnostics", "open_workspace", "Окна -> Проверка проекта", target_workspace_id="diagnostics", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics"),
        DesktopShellCommandSpec("diagnostics.collect_bundle", "Сохранить архив проекта", "Открыть проверку проекта и сохранить архив проекта через общее действие приложения.", "diagnostics", "hosted_action", "Окна -> Проверка проекта -> Сохранить архив проекта", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("сохранить архив", "архив проекта", "проверка проекта"), status_label="Всегда доступно"),
        DesktopShellCommandSpec("diagnostics.verify_bundle", "Проверить архив проекта", "Обновить проверку состава и состояния архива проекта.", "diagnostics", "hosted_action", "Окна -> Проверка проекта -> Проверить архив", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("проверить архив", "архив проекта", "проверка архива"), status_label="Проверка проекта"),
        DesktopShellCommandSpec("diagnostics.send_results", "Скопировать архив", "Скопировать сохранённый архив для ручной передачи.", "diagnostics", "hosted_action", "Окна -> Проверка проекта -> Скопировать архив", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("скопировать архив", "архив проекта", "передать вручную"), status_label="Проверка проекта"),
        DesktopShellCommandSpec("diagnostics.legacy_center.open", "Расширенная проверка проекта", "Работать с расширенной проверкой проекта и архивом проекта.", "diagnostics", "launch_module", "Окна -> Проверка проекта -> Расширенная проверка", module="pneumo_solver_ui.tools.desktop_diagnostics_center", capability_ids=("tools.diagnostics_and_bundle",), launch_surface="legacy_bridge", help_topic_id="diagnostics", search_aliases=("расширенная проверка проекта", "архив проекта"), status_label="Рабочее окно"),
        DesktopShellCommandSpec("workspace.app_settings.open", "Перейти к параметрам приложения", "Перейти к редким настройкам приложения и рабочего места.", "app_settings", "open_workspace", "Окна -> Параметры приложения", target_workspace_id="app_settings", help_topic_id="app_settings"),
        DesktopShellCommandSpec("workspace.tools.open", "Перейти к инструментам", "Перейти к вспомогательным, справочным и профессиональным окнам.", "tools", "open_workspace", "Окна -> Инструменты", target_workspace_id="tools", help_topic_id="tools"),
        DesktopShellCommandSpec("tools.geometry_reference.open", "Справочник геометрии", "Работать со справочником геометрии.", "tools", "launch_module", "Окна -> Инструменты -> Справочник геометрии", module="pneumo_solver_ui.tools.desktop_geometry_reference_center", capability_ids=("reference.geometry_and_guides", "analysis.influence_and_exploration"), launch_surface="tooling", help_topic_id="tools", search_aliases=("геометрия", "справочник", "reference center")),
        DesktopShellCommandSpec("tools.autotest.open", "Проверки проекта", "Выполнить вспомогательные автономные проверки.", "tools", "launch_module", "Окна -> Инструменты -> Проверки", module="pneumo_solver_ui.tools.run_autotest_gui", launch_surface="tooling", help_topic_id="tools", search_aliases=("autotest", "автотест", "проверки")),
        DesktopShellCommandSpec("tools.qt_main_shell.open", "Основное рабочее место", "Перейти в основное классическое рабочее место приложения.", "tools", "launch_module", "Окна -> Инструменты -> Основное рабочее место", module="pneumo_solver_ui.tools.desktop_main_shell_qt", launch_surface="tooling", help_topic_id="tools", search_aliases=("основное рабочее место", "рабочее место инженера", "qt")),
        DesktopShellCommandSpec("tools.spec_shell.open", "Панель восстановления окон", "Проверить порядок работы и доступность рабочих окон.", "tools", "launch_module", "Окна -> Инструменты -> Панель восстановления окон", module="pneumo_solver_ui.tools.desktop_gui_spec_shell", launch_surface="tooling", help_topic_id="tools", search_aliases=("восстановление окон", "доступ к окнам", "рабочие окна")),
        DesktopShellCommandSpec("tools.legacy_shell.open", "Рабочие окна во вкладках", "Показать рабочие окна проекта во вкладках.", "tools", "launch_module", "Окна -> Инструменты -> Рабочие окна во вкладках", module="pneumo_solver_ui.tools.desktop_main_shell", launch_surface="tooling", help_topic_id="tools", search_aliases=("рабочие окна во вкладках", "вкладки рабочих окон"), status_label="Рабочее окно"),
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
