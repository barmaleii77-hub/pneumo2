from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from .catalogs import (
    get_ui_element,
    legacy_key_aliases,
    migration_hints_by_workspace_code,
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
    "overview": ("WS-PROJECT", "общие_регионы"),
    "results_analysis": (
        "WS-RESULTS",
        "WS-ANALYTICS",
        "рабочее_пространство.Анализ_результатов",
    ),
    "animation": ("рабочее_пространство.Анимация",),
    "diagnostics": ("рабочее_пространство.Диагностика",),
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
    "baseline_run": ("baseline.center.open", "baseline.review", "baseline.adopt", "baseline.restore", "baseline.legacy_launch.open", "workspace.optimization.open", "workspace.results_analysis.open"),
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
        if isinstance(hints, str):
            hints = (hints,)
        aliases[capability_id] = _dedupe(list(hints))
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
    return _dedupe(values)


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
        search_aliases=_dedupe([*spec.search_aliases, *_migration_aliases_for_workspace(spec.workspace_id)]),
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
            title="Обзор",
            group="Основная последовательность",
            route_order=10,
            kind="main",
            summary="Главная инженерная сводка проекта, опорный прогон, цели оптимизации, результаты и диагностика.",
            source_of_truth="Панель проекта показывает производную сводку над проектом и последними файлами расчёта.",
            launch_surface="workspace",
            next_step="Выберите следующий шаг по основной последовательности и откройте связанный центр.",
            hard_gate="Обзор не заменяет исходные данные; он только сводит проектный контекст.",
            details="Здесь находятся быстрые действия, сводка самопроверки и видимое состояние опорного прогона, оптимизации и диагностики.",
            units_policy="Единицы на панели проекта только поясняют состояние файлов и не подменяют рабочие экраны.",
            graphics_policy="Карточки панели проекта обязаны честно показывать, это расчётный файл, производная сводка или незаполненное место.",
            search_aliases=("главная", "проект", "обзор"),
            quick_action_ids=(
                "workspace.input_data.open",
                "workspace.ring_editor.open",
                "workspace.baseline_run.open",
                "workspace.optimization.open",
                "results.center.open",
                "animation.animator.open",
                "diagnostics.collect_bundle",
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
            title="Сценарии и редактор кольца",
            group="Основная последовательность",
            route_order=30,
            kind="main",
            summary="Единственный источник истины по циклическому сценарию, дороге, сегментам, шву и производным файлам сценария.",
            source_of_truth="Редактор циклического сценария является единственным источником сценариев и дороги.",
            launch_surface="legacy_bridge",
            next_step="После подготовки кольца откройте набор испытаний и свяжите сценарии с матрицей испытаний.",
            hard_gate="Сценарии не должны редактироваться в других местах, кроме редактора циклического сценария.",
            details="Главное окно открывает существующий редактор циклического сценария без создания второго источника данных.",
            units_policy="Параметры дороги и манёвра обязаны иметь единицы, диапазоны и справку.",
            graphics_policy="Профиль дороги и производные файлы обязаны быть связаны с числовыми параметрами.",
            search_aliases=("редактор кольца", "кольцо", "сценарии", "дорога"),
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
            details="Окно показывает текущий снимок набора, связи со сценариями и причины блокировок без служебных идентификаторов.",
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
            next_step="Запустите опорный прогон и затем открывайте оптимизацию только из согласованного контекста.",
            hard_gate="Без происхождения опорного прогона цели оптимизации и история запусков считаются неполными.",
            details="Рабочий шаг показывает условия запуска и открывает существующие окна без служебных идентификаторов.",
            units_policy="Временные и расчётные настройки должны быть видимы вместе с происхождением опорного прогона.",
            graphics_policy="Сводка опорного прогона в главном окне всегда производная и обязана указывать источник данных.",
            search_aliases=("базовый прогон", "опорный прогон", "центр опорного прогона", "активный опорный прогон", "история прогона", "настройка расчёта"),
            quick_action_ids=("baseline.center.open", "baseline.legacy_launch.open", "test.center.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="optimization",
            title="Оптимизация",
            group="Основная последовательность",
            route_order=60,
            kind="main",
            summary="Цели расчёта, ограничения, история и ход выполнения оптимизации.",
            source_of_truth="Центр оптимизации держит активный способ запуска и условия выполнения.",
            launch_surface="legacy_bridge",
            next_step="Открывайте оптимизацию только после опорного прогона и держите один активный способ запуска.",
            hard_gate="Поэтапный запуск является основным режимом; распределённая координация разрешена только как расширенный режим той же последовательности.",
            details="Главное окно обязано показывать цели расчёта, обязательные ограничения и происхождение опорного прогона рядом со входом в оптимизацию.",
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
            summary="Центр графиков, проверок, сравнения и анализа файлов после прогонов.",
            source_of_truth="Центр результатов и окна сравнения являются производными представлениями над файлами прогонов.",
            launch_surface="legacy_bridge",
            next_step="Переходите сюда из опорного прогона или оптимизации и работайте от конкретного выбранного прогона.",
            hard_gate="Результаты и проверки не должны жить отдельными потерянными страницами вне выбранного прогона.",
            details="Главное окно открывает центр результатов и окно сравнения как согласованный рабочий шаг анализа.",
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
            summary="Визуальная проверка через Animator и Mnemo с честными режимами достоверности.",
            source_of_truth="Animator и Mnemo остаются отдельными специализированными окнами, запускаемыми из контекста главного окна.",
            launch_surface="external_window",
            next_step="Открывайте анимацию из контекста результатов и возвращайтесь в источник изменения после визуальной проверки.",
            hard_gate="Нельзя показывать расчётно подтверждённую графику там, где данных недостаточно.",
            details="Главное окно удерживает последовательность работы, а графические окна остаются отдельными специализированными окнами.",
            units_policy="Наложения и панель свойств обязаны показывать единицы и статус достоверности.",
            graphics_policy="Всегда показывайте маркер достоверности: расчётно подтверждённый, по исходным данным или условный.",
            capability_ids=("visualization.animator_and_mnemo",),
            search_aliases=_aliases_for_capabilities(("visualization.animator_and_mnemo",), "анимация", "animator", "mnemo"),
            quick_action_ids=("animation.animator.open", "animation.mnemo.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="diagnostics",
            title="Диагностика",
            group="Основная последовательность",
            route_order=90,
            kind="main",
            summary="Самопроверка, архив диагностики, отправка результатов и объяснимая диагностика.",
            source_of_truth="Диагностика является основным рабочим шагом и доступна из любого места приложения.",
            launch_surface="workspace",
            next_step="Собирайте диагностику главной кнопкой или открывайте диагностику для проверки и отправки.",
            hard_gate="Диагностику нельзя прятать за второстепенными меню или неочевидными обходными путями.",
            details="Главная кнопка, быстрый поиск и карточка панели проекта обязаны вести в диагностику без обходных путей; отдельный центр остаётся инструментом восстановления.",
            units_policy="Диагностические поля показывают источник, время и тип артефакта, а не инженерные единицы.",
            graphics_policy="Сводка архива диагностики и состояние проекта обязаны честно показывать готовность и недостающие файлы.",
            capability_ids=("tools.diagnostics_and_bundle",),
            search_aliases=_aliases_for_capabilities(("tools.diagnostics_and_bundle",), "диагностика", "архив диагностики", "самопроверка"),
            quick_action_ids=("diagnostics.collect_bundle", "diagnostics.verify_bundle", "diagnostics.send_results"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="app_settings",
            title="Параметры приложения",
            group="Поддержка",
            route_order=100,
            kind="support",
            summary="Редкие настройки главного окна и окружения, не влияющие на главную инженерную последовательность напрямую.",
            source_of_truth="Параметры приложения не должны смешиваться с исходными данными и условиями опорного прогона.",
            launch_surface="workspace",
            next_step="Используйте только для редких глобальных настроек или когда главное окно явно советует это сделать.",
            hard_gate="Настройки не должны подменять рабочие шаги и не должны ломать происхождение данных.",
            details="Отдельное окно настроек остаётся доступным, даже если часть экранов ещё в разработке.",
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
            next_step="Используйте справочник геометрии, автопроверку и связанные инструменты только в понятном контексте.",
            hard_gate="Вспомогательные инструменты не должны становиться скрытым главным входом в основную последовательность.",
            details="Окно инструментов собирает справочные и специализированные окна без потери обнаруживаемости.",
            units_policy="Окна инструментов обязаны сохранять те же правила названий, единиц и справки.",
            graphics_policy="Любой инструмент обязан честно маркировать, это справочный вид, производный результат или диагностическое окно.",
            search_aliases=("инструменты", "справочник", "reference"),
            quick_action_ids=(
                "input.editor.open",
                "ring.editor.open",
                "test.center.open",
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
        DesktopShellCommandSpec("workspace.overview.open", "Открыть панель проекта", "Показать инженерную сводку, опорный прогон, диагностику и быстрые действия.", "overview", "open_workspace", "Окна -> Панель проекта", target_workspace_id="overview", search_aliases=("обзор", "главная"), help_topic_id="overview"),
        DesktopShellCommandSpec("workspace.input_data.open", "Показать исходные данные", "Перейти к исходным данным и открыть основную редактируемую копию проекта в главной последовательности.", "input_data", "open_workspace", "Окна -> Исходные данные", target_workspace_id="input_data", capability_ids=("input.project_entry_and_setup",), help_topic_id="input_data"),
        DesktopShellCommandSpec("input.editor.open", "Открыть центр исходных данных", "Запустить существующий инженерный редактор исходных данных отдельным окном.", "input_data", "launch_module", "Окна -> Исходные данные -> Центр исходных данных", module="pneumo_solver_ui.tools.desktop_input_editor", capability_ids=("input.project_entry_and_setup",), launch_surface="legacy_bridge", status_label="Отдельное окно", help_topic_id="input_data"),
        DesktopShellCommandSpec("workspace.ring_editor.open", "Показать сценарии и редактор кольца", "Перейти к сценарию, дороге, сегментам и производным файлам.", "ring_editor", "open_workspace", "Окна -> Сценарии и редактор кольца", target_workspace_id="ring_editor", help_topic_id="ring_editor"),
        DesktopShellCommandSpec("ring.editor.open", "Открыть редактор кольца", "Запустить существующий редактор кольца отдельным окном.", "ring_editor", "launch_module", "Окна -> Сценарии и редактор кольца -> Редактор кольца", module="pneumo_solver_ui.tools.desktop_ring_scenario_editor", launch_surface="legacy_bridge", status_label="Отдельное окно", help_topic_id="ring_editor", search_aliases=("редактор кольца", "сценарии", "генерация дороги")),
        DesktopShellCommandSpec("workspace.test_matrix.open", "Показать набор испытаний", "Перейти к матрице испытаний, стадиям, ручным изменениям и снимку набора.", "test_matrix", "open_workspace", "Окна -> Набор испытаний", target_workspace_id="test_matrix", capability_ids=("calculation.validation_and_prechecks",), help_topic_id="test_matrix", search_aliases=("матрица испытаний", "снимок набора", "контроль набора", "зафиксировать набор")),
        DesktopShellCommandSpec("test.center.open", "Открыть центр испытаний", "Запустить центр испытаний для проверок, подготовки и контроля расчёта.", "test_matrix", "launch_module", "Окна -> Набор испытаний -> Центр испытаний", module="pneumo_solver_ui.tools.test_center_gui", capability_ids=("calculation.validation_and_prechecks",), launch_surface="legacy_bridge", status_label="Отдельное окно", help_topic_id="test_matrix", search_aliases=("набор испытаний", "снимок набора", "контроль набора", "проверка набора")),
        DesktopShellCommandSpec("workspace.baseline_run.open", "Показать базовый прогон", "Перейти к истории опорного прогона и передаче результата в оптимизацию.", "baseline_run", "open_workspace", "Окна -> Базовый прогон", target_workspace_id="baseline_run", help_topic_id="baseline_run", search_aliases=("опорный прогон", "базовый прогон", "история прогона", "настройка расчёта")),
        DesktopShellCommandSpec("baseline.center.open", "Открыть центр опорного прогона", "Перейти к окну опорного прогона: активный результат, история, просмотр, принятие и восстановление.", "baseline_run", "open_workspace", "Окна -> Базовый прогон -> Центр опорного прогона", target_workspace_id="baseline_run", launch_surface="workspace", status_label="Встроенное окно", help_topic_id="baseline_run", search_aliases=("центр опорного прогона", "активный опорный прогон", "история прогона", "запустить опорный прогон", "базовый запуск")),
        DesktopShellCommandSpec("baseline.review", "Просмотреть выбранный опорный прогон", "Показать выбранный активный или исторический прогон, матрицу расхождений и правила применения без изменения активного результата.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Просмотр опорного прогона", status_label="Только просмотр", help_topic_id="baseline_run", automation_id="BL-BTN-REVIEW", search_aliases=("просмотр опорного прогона", "проверить опорный прогон", "матрица расхождений", "история опорного прогона")),
        DesktopShellCommandSpec("baseline.adopt", "Принять выбранный опорный прогон", "Явно принять проверенный выбранный прогон как новый активный результат; молчаливая подмена запрещена.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Принять опорный прогон", status_label="Явное действие", help_topic_id="baseline_run", automation_id="BL-BTN-ADOPT", search_aliases=("принять опорный прогон", "сделать прогон активным", "явно принять результат", "центр опорного прогона")),
        DesktopShellCommandSpec("baseline.restore", "Восстановить исторический опорный прогон", "Явно восстановить исторический прогон как активный; расхождение по набору, исходным данным или режиму требует предупреждения и подтверждения.", "baseline_run", "hosted_action", "Окна -> Базовый прогон -> Восстановить опорный прогон", status_label="Явное действие", help_topic_id="baseline_run", automation_id="BL-BTN-RESTORE", search_aliases=("восстановить опорный прогон", "исторический опорный прогон", "расхождение опорного прогона", "явное восстановление")),
        DesktopShellCommandSpec("baseline.legacy_launch.open", "Открыть центр испытаний для опорного прогона", "Запустить центр испытаний для запуска с учётом опорного прогона.", "baseline_run", "launch_module", "Окна -> Базовый прогон -> Центр испытаний", module="pneumo_solver_ui.tools.test_center_gui", launch_surface="legacy_bridge", status_label="Отдельное окно", help_topic_id="baseline_run", search_aliases=("центр испытаний для опорного прогона", "запуск опорного прогона")),
        DesktopShellCommandSpec("workspace.optimization.open", "Показать оптимизацию", "Перейти к целям расчёта, обязательным ограничениям и активному режиму оптимизации.", "optimization", "open_workspace", "Окна -> Оптимизация", target_workspace_id="optimization", capability_ids=("optimization.orchestration_and_databases",), help_topic_id="optimization"),
        DesktopShellCommandSpec("optimization.center.open", "Открыть центр оптимизации", "Запустить центр оптимизации: основной поэтапный режим и расширенная распределённая координация.", "optimization", "launch_module", "Окна -> Оптимизация -> Центр оптимизации", module="pneumo_solver_ui.tools.desktop_optimizer_center", capability_ids=("optimization.orchestration_and_databases",), launch_surface="legacy_bridge", status_label="Отдельное окно", help_topic_id="optimization", search_aliases=("поэтапный запуск", "распределённая координация", "решатель")),
        DesktopShellCommandSpec("workspace.results_analysis.open", "Показать анализ результатов", "Перейти к графикам, проверкам, сравнению и файлам результатов.", "results_analysis", "open_workspace", "Окна -> Анализ результатов", target_workspace_id="results_analysis", capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"), help_topic_id="results_analysis"),
        DesktopShellCommandSpec("results.center.open", "Открыть центр анализа результатов", "Запустить центр результатов как основное окно анализа.", "results_analysis", "launch_module", "Окна -> Анализ результатов -> Центр результатов", module="pneumo_solver_ui.tools.desktop_results_center", capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"), launch_surface="legacy_bridge", status_label="Отдельное окно", help_topic_id="results_analysis", search_aliases=("результаты", "анализ", "проверка")),
        DesktopShellCommandSpec("results.compare.open", "Открыть Compare Viewer", "Запустить окно сравнения из анализа результатов.", "results_analysis", "launch_module", "Окна -> Анализ результатов -> Compare Viewer", module="pneumo_solver_ui.qt_compare_viewer", capability_ids=("results.compare_and_review",), launch_surface="external_window", help_topic_id="results_analysis", search_aliases=("compare", "сравнение", "npz")),
        DesktopShellCommandSpec("analysis.engineering.open", "Открыть инженерный анализ", "Запустить окно калибровки, анализа влияния, сводок чувствительности и инженерного отчёта.", "results_analysis", "launch_module", "Окна -> Анализ результатов -> Инженерный анализ", module="pneumo_solver_ui.tools.desktop_engineering_analysis_center", capability_ids=("analysis.influence_and_exploration",), launch_surface="tooling", help_topic_id="results_analysis", search_aliases=("engineering analysis", "calibration", "influence", "sensitivity", "system influence", "калибровка", "влияние", "чувствительность")),
        DesktopShellCommandSpec("workspace.animation.open", "Показать анимацию", "Перейти к Animator, Mnemo и честным визуальным режимам.", "animation", "open_workspace", "Окна -> Анимация", target_workspace_id="animation", capability_ids=("visualization.animator_and_mnemo",), help_topic_id="animation"),
        DesktopShellCommandSpec("animation.animator.open", "Открыть Desktop Animator", "Запустить отдельное окно анимации с приоритетом визуальной проверки.", "animation", "launch_module", "Окна -> Анимация -> Desktop Animator", module="pneumo_solver_ui.desktop_animator.app", capability_ids=("visualization.animator_and_mnemo",), launch_surface="external_window", help_topic_id="animation", search_aliases=("animator", "анимация", "трёхмерный вид")),
        DesktopShellCommandSpec("animation.mnemo.open", "Открыть Desktop Mnemo", "Запустить отдельное окно мнемосхемы из контекста результата.", "animation", "launch_module", "Окна -> Анимация -> Desktop Mnemo", module="pneumo_solver_ui.desktop_mnemo.main", capability_ids=("visualization.animator_and_mnemo",), launch_surface="external_window", help_topic_id="animation", search_aliases=("mnemo", "мнемосхема", "пневмосхема")),
        DesktopShellCommandSpec("workspace.diagnostics.open", "Показать диагностику", "Перейти к самопроверке, архиву диагностики, отправке результатов и текущему состоянию диагностики.", "diagnostics", "open_workspace", "Окна -> Диагностика", target_workspace_id="diagnostics", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics"),
        DesktopShellCommandSpec("diagnostics.collect_bundle", "Собрать диагностику", "Открыть диагностику и запустить сборку архива через общее действие приложения.", "diagnostics", "hosted_action", "Окна -> Диагностика -> Собрать диагностику", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("собрать диагностику", "архив диагностики", "самопроверка"), status_label="Всегда доступно"),
        DesktopShellCommandSpec("diagnostics.verify_bundle", "Проверить архив диагностики", "Обновить проверку состава и состояния архива диагностики.", "diagnostics", "hosted_action", "Окна -> Диагностика -> Проверить архив диагностики", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("проверить архив", "архив диагностики", "проверка архива"), status_label="Диагностика"),
        DesktopShellCommandSpec("diagnostics.send_results", "Отправить результаты", "Открыть отправку результатов после проверки актуального архива.", "diagnostics", "hosted_action", "Окна -> Диагностика -> Отправить результаты", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("отправить архив", "отправить результаты", "передать результаты"), status_label="Диагностика"),
        DesktopShellCommandSpec("diagnostics.legacy_center.open", "Открыть центр диагностики", "Запустить центр диагностики.", "diagnostics", "launch_module", "Окна -> Диагностика -> Центр диагностики", module="pneumo_solver_ui.tools.desktop_diagnostics_center", capability_ids=("tools.diagnostics_and_bundle",), launch_surface="legacy_bridge", help_topic_id="diagnostics", search_aliases=("диагностика отдельным окном", "центр диагностики"), status_label="Отдельное окно"),
        DesktopShellCommandSpec("workspace.app_settings.open", "Показать параметры приложения", "Перейти к редким настройкам приложения и главного окна.", "app_settings", "open_workspace", "Окна -> Параметры приложения", target_workspace_id="app_settings", help_topic_id="app_settings"),
        DesktopShellCommandSpec("workspace.tools.open", "Показать инструменты", "Перейти к вспомогательным, справочным и профессиональным окнам.", "tools", "open_workspace", "Окна -> Инструменты", target_workspace_id="tools", help_topic_id="tools"),
        DesktopShellCommandSpec("tools.geometry_reference.open", "Открыть справочник геометрии", "Запустить справочный геометрический центр как специализированное окно.", "tools", "launch_module", "Окна -> Инструменты -> Справочник геометрии", module="pneumo_solver_ui.tools.desktop_geometry_reference_center", capability_ids=("reference.geometry_and_guides", "analysis.influence_and_exploration"), launch_surface="tooling", help_topic_id="tools", search_aliases=("геометрия", "справочник", "reference center")),
        DesktopShellCommandSpec("tools.autotest.open", "Открыть автопроверку", "Запустить вспомогательный центр автономных проверок.", "tools", "launch_module", "Окна -> Инструменты -> Автопроверка", module="pneumo_solver_ui.tools.run_autotest_gui", launch_surface="tooling", help_topic_id="tools", search_aliases=("autotest", "автотест", "проверки")),
        DesktopShellCommandSpec("tools.qt_main_shell.open", "Открыть основное рабочее место", "Запустить основное классическое рабочее место приложения отдельным окном.", "tools", "launch_module", "Окна -> Инструменты -> Основное рабочее место", module="pneumo_solver_ui.tools.desktop_main_shell_qt", launch_surface="tooling", help_topic_id="tools", search_aliases=("основное рабочее место", "главное окно приложения", "qt")),
        DesktopShellCommandSpec("tools.spec_shell.open", "Открыть проверочное рабочее место", "Запустить проверочное рабочее место для сверки порядка работы и доступности GUI-окон.", "tools", "launch_module", "Окна -> Инструменты -> Проверочное рабочее место", module="pneumo_solver_ui.tools.desktop_gui_spec_shell", launch_surface="tooling", help_topic_id="tools", search_aliases=("проверочное главное окно", "сверка gui окон")),
        DesktopShellCommandSpec("tools.legacy_shell.open", "Открыть рабочее место с вкладками", "Запустить окно с вкладками для восстановления доступа.", "tools", "launch_module", "Окна -> Инструменты -> Рабочее место с вкладками", module="pneumo_solver_ui.tools.desktop_main_shell", launch_surface="tooling", help_topic_id="tools", search_aliases=("главное окно с вкладками", "tk оболочка"), status_label="Отдельное окно"),
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
