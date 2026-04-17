from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from .catalogs import (
    get_ui_element,
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
    "optimization.center.open": "OP-BTN-LAUNCH",
    "results.compare.open": "RS-BTN-OPEN-ANALYTICS",
    "animation.animator.open": "AN-BTN-OPEN-ANIMATOR",
    "workspace.animation.open": "AM-VIEWPORT",
}

ROUTE_QUICK_ACTIONS_BY_WORKSPACE: dict[str, tuple[str, ...]] = {
    "input_data": ("input.editor.open", "workspace.ring_editor.open", "workspace.test_matrix.open"),
    "ring_editor": ("ring.editor.open", "workspace.test_matrix.open"),
    "test_matrix": ("test.center.open", "workspace.baseline_run.open", "workspace.ring_editor.open"),
    "baseline_run": ("baseline.center.open", "workspace.optimization.open", "workspace.results_analysis.open"),
    "optimization": ("optimization.center.open", "workspace.results_analysis.open", "workspace.diagnostics.open"),
    "results_analysis": ("results.center.open", "analysis.engineering.open", "results.compare.open", "workspace.animation.open", "workspace.diagnostics.open"),
    "animation": ("animation.animator.open", "animation.mnemo.open", "workspace.results_analysis.open"),
    "diagnostics": ("diagnostics.collect_bundle", "diagnostics.verify_bundle", "diagnostics.send_results"),
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
        hints = row.get("как_найти_через_поиск_команд") or row.get(
            "РєР°Рє_РЅР°Р№С‚Рё_С‡РµСЂРµР·_РїРѕРёСЃРє_РєРѕРјР°РЅРґ"
        ) or ()
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
            group="Основной маршрут",
            route_order=10,
            kind="main",
            summary="Главная инженерная сводка проекта, baseline, optimization contract, результаты и диагностика.",
            source_of_truth="Обзор - производная dashboard-поверхность над проектом и последними артефактами.",
            launch_surface="workspace",
            next_step="Выберите следующий шаг по основному маршруту и откройте связанный центр.",
            hard_gate="Обзор не заменяет master-copy данных; он только сводит проектный контекст.",
            details="Здесь живут quick actions, health/self-check summary и видимый статус baseline, optimization и diagnostics.",
            units_policy="Единицы на обзоре только поясняют состояние артефактов и не подменяют рабочие экраны.",
            graphics_policy="Карточки обзора обязаны честно показывать, это расчётный артефакт, derived summary или placeholder.",
            search_aliases=("главная", "dashboard", "проект", "обзор"),
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
            group="Основной маршрут",
            route_order=20,
            kind="main",
            summary="Master-copy параметров машины, геометрии, пневматики, механики и базовой готовности проекта.",
            source_of_truth="Только этот workspace задаёт исходную инженерную конфигурацию.",
            launch_surface="workspace",
            next_step="После правки данных переходите в сценарии, затем в набор испытаний и baseline.",
            hard_gate="До готовности исходных данных baseline и optimization не считаются достоверными.",
            details="Hosted workspace показывает рабочую копию, эталон и готовность разделов прямо в shell; legacy editor остаётся fallback surface для детального редактирования.",
            units_policy="Все поля должны показывать величину и единицу; безымянные значения запрещены.",
            graphics_policy="Геометрия и preview обязаны быть двусторонне связаны с числовым вводом.",
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
            group="Основной маршрут",
            route_order=30,
            kind="main",
            summary="Единственный источник истины по кольцу, дороге, сегментам, шву и derived scenario artifacts.",
            source_of_truth="Редактор кольца является single source of truth для сценариев и дороги.",
            launch_surface="legacy_bridge",
            next_step="После подготовки кольца откройте набор испытаний и свяжите сценарии с матрицей испытаний.",
            hard_gate="Сценарии не должны редактироваться в других местах, кроме ring editor.",
            details="Wave 1 открывает существующий ring editor как честный bridge из нового shell.",
            units_policy="Параметры дороги и манёвра обязаны иметь единицы, диапазоны и help policy.",
            graphics_policy="Кольцо, профиль и derived artifacts обязаны быть связаны с числовыми параметрами.",
            search_aliases=("редактор кольца", "кольцо", "сценарии", "дорога"),
            quick_action_ids=("ring.editor.open",),
        ),
        DesktopWorkspaceSpec(
            workspace_id="test_matrix",
            title="Набор испытаний",
            group="Основной маршрут",
            route_order=40,
            kind="main",
            summary="Master-copy набора испытаний, стадий, runtime overrides, suite_snapshot_hash и связей со сценариями.",
            source_of_truth="Матрица испытаний хранит состав и метаданные test flow.",
            launch_surface="legacy_bridge",
            next_step="После настройки набора испытаний переходите в baseline или validation/precheck routes.",
            hard_gate="Без validated_suite_snapshot по HO-005 невозможно честно запускать baseline и optimization.",
            details="На wave 1 используется bridge к текущему test center, но shell держит отдельный workspace и показывает путь к validated_suite_snapshot.",
            units_policy="Времена, шаги интегрирования и stage-метки должны быть показаны явно.",
            graphics_policy="Timeline и stage-summary являются производными view над матрицей испытаний.",
            capability_ids=("calculation.validation_and_prechecks",),
            search_aliases=_aliases_for_capabilities(
                ("calculation.validation_and_prechecks",),
                "набор испытаний",
                "испытания",
                "test matrix",
                "validated_suite_snapshot",
                "suite_snapshot_hash",
                "HO-005",
                "заморозить HO-005",
            ),
            quick_action_ids=("test.center.open",),
        ),
        DesktopWorkspaceSpec(
            workspace_id="baseline_run",
            title="Базовый прогон",
            group="Основной маршрут",
            route_order=50,
            kind="main",
            summary="Источник истины по baseline snapshot, history baseline и handoff в optimization.",
            source_of_truth="Этот workspace отвечает за baseline provenance, даже если текущий runtime живёт в legacy centers.",
            launch_surface="legacy_bridge",
            next_step="Запустите baseline и затем откройте optimization только из baseline-aware контекста.",
            hard_gate="Без baseline provenance objective stack и optimization history считаются неполными.",
            details="Wave 1 даёт отдельный contract-first workspace и честно открывает существующие launch surfaces через bridge.",
            units_policy="Временные и runtime настройки должны быть видимы вместе с baseline provenance.",
            graphics_policy="Baseline summary на shell-уровне всегда derived и обязан указывать source-of-truth.",
            search_aliases=("базовый прогон", "baseline", "run setup"),
            quick_action_ids=("baseline.center.open", "test.center.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="optimization",
            title="Оптимизация",
            group="Основной маршрут",
            route_order=60,
            kind="main",
            summary="Launch contract, objective stack, hard gates, history и runtime monitor оптимизации.",
            source_of_truth="Optimization center держит active launch path и runtime contract.",
            launch_surface="legacy_bridge",
            next_step="Открывайте optimization только после baseline и держите один активный launch path.",
            hard_gate="StageRunner - primary path; distributed coordinator разрешён только как advanced mode того же route.",
            details="Shell обязан всегда показывать objective stack, hard gate и baseline provenance рядом с входом в optimization.",
            units_policy="Целевые показатели и ограничения обязаны показывать смысл и единицы в help/provenance pane.",
            graphics_policy="Любой runtime progress должен честно показывать active mode и origin baseline.",
            capability_ids=("optimization.orchestration_and_databases",),
            search_aliases=_aliases_for_capabilities(("optimization.orchestration_and_databases",), "оптимизация", "stagerunner", "solver"),
            quick_action_ids=("optimization.center.open",),
        ),
        DesktopWorkspaceSpec(
            workspace_id="results_analysis",
            title="Анализ результатов",
            group="Основной маршрут",
            route_order=70,
            kind="main",
            summary="Центр графиков, validation, compare и анализа артефактов после прогонов.",
            source_of_truth="Results center и compare surfaces являются derived views над артефактами прогонов.",
            launch_surface="legacy_bridge",
            next_step="Переходите сюда из baseline или optimization и работайте от конкретного run context.",
            hard_gate="Results и validation не должны жить отдельными потерянными страницами вне run context.",
            details="Wave 1 открывает текущий results center и compare viewer как согласованный analysis lane.",
            units_policy="Графики и таблицы обязаны показывать единицы и source-of-truth артефактов.",
            graphics_policy="Compare и validation обязаны помечать источник данных и время построения.",
            capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"),
            search_aliases=_aliases_for_capabilities(("results.compare_and_review", "analysis.influence_and_exploration"), "анализ", "результаты", "сравнение"),
            quick_action_ids=("results.center.open", "analysis.engineering.open", "results.compare.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="animation",
            title="Анимация",
            group="Основной маршрут",
            route_order=80,
            kind="main",
            summary="Viewport-first visual inspection через Animator и Mnemo с честными режимами достоверности.",
            source_of_truth="Animator и Mnemo остаются отдельными специализированными окнами, запускаемыми из shell-контекста.",
            launch_surface="external_window",
            next_step="Открывайте animation из контекста результатов и возвращайтесь в источник изменения после visual review.",
            hard_gate="Нельзя показывать расчётно подтверждённую графику там, где данных недостаточно.",
            details="Shell удерживает route, а сами viewport-first surfaces остаются отдельными внешними окнами.",
            units_policy="Overlay и inspector обязаны показывать единицы и статус достоверности.",
            graphics_policy="Всегда показывайте marker: расчётно подтверждённый, по исходным данным или условный.",
            capability_ids=("visualization.animator_and_mnemo",),
            search_aliases=_aliases_for_capabilities(("visualization.animator_and_mnemo",), "анимация", "animator", "mnemo"),
            quick_action_ids=("animation.animator.open", "animation.mnemo.open"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="diagnostics",
            title="Диагностика",
            group="Основной маршрут",
            route_order=90,
            kind="main",
            summary="Operational surface для self-check, bundle, latest ZIP, send flow и explainable diagnostics.",
            source_of_truth="Diagnostics center является first-class operational surface и доступен из любого workspace.",
            launch_surface="workspace",
            next_step="Собирайте диагностику из command bar или открывайте полный diagnostics lane для bundle/send.",
            hard_gate="Diagnostics нельзя прятать за secondary menus или в неочевидные legacy routes.",
            details="Header CTA, search aliases и overview card обязаны вести в hosted diagnostics lane без обходных путей; legacy center остаётся fallback tool surface.",
            units_policy="Диагностические поля показывают источник, время и тип артефакта, а не инженерные единицы.",
            graphics_policy="Bundle summary и health обязаны честно показывать готовность и missing artifacts.",
            capability_ids=("tools.diagnostics_and_bundle",),
            search_aliases=_aliases_for_capabilities(("tools.diagnostics_and_bundle",), "диагностика", "bundle", "health"),
            quick_action_ids=("diagnostics.collect_bundle", "diagnostics.verify_bundle", "diagnostics.send_results"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="app_settings",
            title="Параметры приложения",
            group="Поддержка",
            route_order=100,
            kind="support",
            summary="Редкие настройки shell и окружения, не влияющие на главный инженерный маршрут напрямую.",
            source_of_truth="Параметры приложения не должны смешиваться с исходными данными и baseline contract.",
            launch_surface="workspace",
            next_step="Используйте только для редких глобальных настроек или когда shell явно советует это сделать.",
            hard_gate="Настройки не должны подменять рабочие пространства маршрута и не должны ломать provenance.",
            details="Wave 1 задаёт отдельный workspace даже если часть экранов пока в разработке.",
            units_policy="Настройки обязаны честно помечаться как shell/app-level, а не как инженерные параметры.",
            graphics_policy="Настройки не имеют права маскировать источник достоверности графики.",
            search_aliases=("параметры приложения", "настройки", "settings"),
        ),
        DesktopWorkspaceSpec(
            workspace_id="tools",
            title="Инструменты",
            group="Поддержка",
            route_order=110,
            kind="support",
            summary="Вспомогательные, справочные и сервисные профессиональные окна вне основного маршрута.",
            source_of_truth="Инструменты дополняют маршрут, но не подменяют main workspaces.",
            launch_surface="tooling",
            next_step="Используйте geometry/reference, autotest и related tools только в понятном контексте.",
            hard_gate="Secondary tools не должны становиться скрытым главным входом в основной workflow.",
            details="Tools workspace собирает справочные и специализированные окна без потери discoverability.",
            units_policy="Tooling surfaces обязаны сохранять те же правила названий, единиц и help.",
            graphics_policy="Любой tool-view обязан честно маркировать, это reference view, derived result или diagnostic surface.",
            search_aliases=("инструменты", "справочник", "reference"),
            quick_action_ids=("tools.geometry_reference.open", "tools.autotest.open", "results.compare.open"),
        ),
    )
    return tuple(
        _bind_workspace_catalog(item)
        for item in sorted(workspaces, key=lambda item: item.route_order)
    )


def build_shell_commands() -> tuple[DesktopShellCommandSpec, ...]:
    commands = (
        DesktopShellCommandSpec("workspace.overview.open", "Открыть обзор проекта", "Показать инженерный dashboard, baseline, diagnostics и quick actions.", "overview", "open_workspace", "Рабочие пространства -> Обзор", target_workspace_id="overview", search_aliases=("обзор", "dashboard", "главная"), help_topic_id="overview"),
        DesktopShellCommandSpec("workspace.input_data.open", "Открыть workspace \"Исходные данные\"", "Перейти к hosted workspace исходных данных и открыть master-copy проекта в shell-маршруте.", "input_data", "open_workspace", "Рабочие пространства -> Исходные данные", target_workspace_id="input_data", capability_ids=("input.project_entry_and_setup",), help_topic_id="input_data"),
        DesktopShellCommandSpec("input.editor.open", "Открыть центр исходных данных", "Запустить существующий инженерный editor для master-copy исходных данных как fallback surface.", "input_data", "launch_module", "Рабочие пространства -> Исходные данные -> Центр исходных данных", module="pneumo_solver_ui.tools.desktop_input_editor", capability_ids=("input.project_entry_and_setup",), launch_surface="legacy_bridge", status_label="Legacy fallback", help_topic_id="input_data"),
        DesktopShellCommandSpec("workspace.ring_editor.open", "Открыть workspace \"Сценарии и редактор кольца\"", "Перейти к сценарию, кольцу, дороге и derived artifacts.", "ring_editor", "open_workspace", "Рабочие пространства -> Сценарии и редактор кольца", target_workspace_id="ring_editor", help_topic_id="ring_editor"),
        DesktopShellCommandSpec("ring.editor.open", "Открыть редактор кольца", "Запустить существующий ring editor как честный bridge из нового shell.", "ring_editor", "launch_module", "Рабочие пространства -> Сценарии и редактор кольца -> Редактор кольца", module="pneumo_solver_ui.tools.desktop_ring_scenario_editor", launch_surface="legacy_bridge", status_label="Legacy bridge", help_topic_id="ring_editor", search_aliases=("редактор кольца", "сценарии", "генерация дороги")),
        DesktopShellCommandSpec("workspace.test_matrix.open", "Открыть workspace \"Набор испытаний\"", "Перейти к матрице испытаний, stage-логике, overrides и validated suite snapshot.", "test_matrix", "open_workspace", "Рабочие пространства -> Набор испытаний", target_workspace_id="test_matrix", capability_ids=("calculation.validation_and_prechecks",), help_topic_id="test_matrix", search_aliases=("validated_suite_snapshot", "suite_snapshot_hash", "HO-005", "заморозить HO-005")),
        DesktopShellCommandSpec("test.center.open", "Открыть центр испытаний", "Запустить существующий test center для validation, precheck, run orchestration и HO-005 suite handoff.", "test_matrix", "launch_module", "Рабочие пространства -> Набор испытаний -> Центр испытаний", module="pneumo_solver_ui.tools.test_center_gui", capability_ids=("calculation.validation_and_prechecks",), launch_surface="legacy_bridge", status_label="Legacy bridge", help_topic_id="test_matrix", search_aliases=("validated suite", "validated_suite_snapshot", "suite_snapshot_hash", "HO-005", "заморозить HO-005")),
        DesktopShellCommandSpec("workspace.baseline_run.open", "Открыть workspace \"Базовый прогон\"", "Перейти к baseline provenance, baseline history и handoff в optimization.", "baseline_run", "open_workspace", "Рабочие пространства -> Базовый прогон", target_workspace_id="baseline_run", help_topic_id="baseline_run", search_aliases=("baseline", "базовый прогон", "run setup")),
        DesktopShellCommandSpec("baseline.center.open", "Открыть baseline launch surface", "Открыть текущий baseline-aware launch surface через существующий test center bridge.", "baseline_run", "launch_module", "Рабочие пространства -> Базовый прогон -> Legacy launch surface", module="pneumo_solver_ui.tools.test_center_gui", launch_surface="legacy_bridge", status_label="Legacy bridge", help_topic_id="baseline_run", search_aliases=("запустить baseline", "базовый запуск", "baseline launch")),
        DesktopShellCommandSpec("workspace.optimization.open", "Открыть workspace \"Оптимизация\"", "Перейти к objective stack, hard gates и active optimization route.", "optimization", "open_workspace", "Рабочие пространства -> Оптимизация", target_workspace_id="optimization", capability_ids=("optimization.orchestration_and_databases",), help_topic_id="optimization"),
        DesktopShellCommandSpec("optimization.center.open", "Открыть центр оптимизации", "Запустить existing optimization center в route \"StageRunner primary / distributed advanced\".", "optimization", "launch_module", "Рабочие пространства -> Оптимизация -> Центр оптимизации", module="pneumo_solver_ui.tools.desktop_optimizer_center", capability_ids=("optimization.orchestration_and_databases",), launch_surface="legacy_bridge", status_label="Legacy bridge", help_topic_id="optimization", search_aliases=("stagerunner", "distributed", "solver")),
        DesktopShellCommandSpec("workspace.results_analysis.open", "Открыть workspace \"Анализ результатов\"", "Перейти к графикам, validation, compare и results artifacts.", "results_analysis", "open_workspace", "Рабочие пространства -> Анализ результатов", target_workspace_id="results_analysis", capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"), help_topic_id="results_analysis"),
        DesktopShellCommandSpec("results.center.open", "Открыть центр анализа результатов", "Запустить existing results center как основную analysis surface.", "results_analysis", "launch_module", "Рабочие пространства -> Анализ результатов -> Центр результатов", module="pneumo_solver_ui.tools.desktop_results_center", capability_ids=("results.compare_and_review", "analysis.influence_and_exploration"), launch_surface="legacy_bridge", status_label="Legacy bridge", help_topic_id="results_analysis", search_aliases=("результаты", "анализ", "validation")),
        DesktopShellCommandSpec("results.compare.open", "Открыть compare viewer", "Запустить compare surface из analysis lane.", "results_analysis", "launch_module", "Рабочие пространства -> Анализ результатов -> Compare Viewer", module="pneumo_solver_ui.qt_compare_viewer", capability_ids=("results.compare_and_review",), launch_surface="external_window", help_topic_id="results_analysis", search_aliases=("compare", "сравнение", "npz")),
        DesktopShellCommandSpec("analysis.engineering.open", "Открыть Engineering Analysis Center", "Запустить calibration, influence analysis, sensitivity summaries and engineering evidence export surface.", "results_analysis", "launch_module", "Рабочие пространства -> Анализ результатов -> Engineering Analysis Center", module="pneumo_solver_ui.tools.desktop_engineering_analysis_center", capability_ids=("analysis.influence_and_exploration",), launch_surface="tooling", help_topic_id="results_analysis", search_aliases=("engineering analysis", "calibration", "influence", "sensitivity", "system influence", "калибровка", "влияние", "чувствительность")),
        DesktopShellCommandSpec("workspace.animation.open", "Открыть workspace \"Анимация\"", "Перейти к animator/mnemo lane и честным визуальным режимам.", "animation", "open_workspace", "Рабочие пространства -> Анимация", target_workspace_id="animation", capability_ids=("visualization.animator_and_mnemo",), help_topic_id="animation"),
        DesktopShellCommandSpec("animation.animator.open", "Открыть Desktop Animator", "Запустить отдельное viewport-first окно анимации.", "animation", "launch_module", "Рабочие пространства -> Анимация -> Desktop Animator", module="pneumo_solver_ui.desktop_animator.app", capability_ids=("visualization.animator_and_mnemo",), launch_surface="external_window", help_topic_id="animation", search_aliases=("animator", "анимация", "трёхмерный вид")),
        DesktopShellCommandSpec("animation.mnemo.open", "Открыть Desktop Mnemo", "Запустить отдельное окно мнемосхемы из контекста результата.", "animation", "launch_module", "Рабочие пространства -> Анимация -> Desktop Mnemo", module="pneumo_solver_ui.desktop_mnemo.app", capability_ids=("visualization.animator_and_mnemo",), launch_surface="external_window", help_topic_id="animation", search_aliases=("mnemo", "мнемосхема", "пневмосхема")),
        DesktopShellCommandSpec("workspace.diagnostics.open", "Открыть workspace \"Диагностика\"", "Перейти к self-check, bundle, send flow и latest diagnostics state.", "diagnostics", "open_workspace", "Рабочие пространства -> Диагностика", target_workspace_id="diagnostics", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics"),
        DesktopShellCommandSpec("diagnostics.collect_bundle", "Собрать диагностику", "Открыть hosted diagnostics lane и запустить сборку bundle через shell-wide команду.", "diagnostics", "hosted_action", "Рабочие пространства -> Диагностика -> Собрать диагностику", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("собрать диагностику", "bundle", "health"), status_label="Always visible CTA"),
        DesktopShellCommandSpec("diagnostics.verify_bundle", "Проверить bundle", "Выполнить inspection / health refresh внутри hosted diagnostics lane.", "diagnostics", "hosted_action", "Рабочие пространства -> Диагностика -> Проверить bundle", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("проверить bundle", "архив диагностики", "verify bundle"), status_label="Hosted lane"),
        DesktopShellCommandSpec("diagnostics.send_results", "Отправить результаты", "Открыть send flow из hosted diagnostics lane после проверки актуального ZIP.", "diagnostics", "hosted_action", "Рабочие пространства -> Диагностика -> Отправить результаты", capability_ids=("tools.diagnostics_and_bundle",), help_topic_id="diagnostics", search_aliases=("send bundle", "отправить результаты", "send results"), status_label="Hosted lane"),
        DesktopShellCommandSpec("diagnostics.legacy_center.open", "Открыть legacy diagnostics center", "Запустить прежний Tk diagnostics center как fallback / debug surface.", "diagnostics", "launch_module", "Рабочие пространства -> Диагностика -> Legacy Diagnostics Center", module="pneumo_solver_ui.tools.desktop_diagnostics_center", capability_ids=("tools.diagnostics_and_bundle",), launch_surface="legacy_bridge", help_topic_id="diagnostics", search_aliases=("legacy diagnostics", "tk diagnostics", "старый diagnostics center"), status_label="Fallback / debug"),
        DesktopShellCommandSpec("workspace.app_settings.open", "Открыть workspace \"Параметры приложения\"", "Перейти к редким shell/app-level настройкам.", "app_settings", "open_workspace", "Рабочие пространства -> Параметры приложения", target_workspace_id="app_settings", help_topic_id="app_settings"),
        DesktopShellCommandSpec("workspace.tools.open", "Открыть workspace \"Инструменты\"", "Перейти к вспомогательным, справочным и служебным профессиональным окнам.", "tools", "open_workspace", "Рабочие пространства -> Инструменты", target_workspace_id="tools", help_topic_id="tools"),
        DesktopShellCommandSpec("tools.geometry_reference.open", "Открыть geometry reference center", "Запустить справочный геометрический центр как специализированный tool surface.", "tools", "launch_module", "Рабочие пространства -> Инструменты -> Geometry Reference Center", module="pneumo_solver_ui.tools.desktop_geometry_reference_center", capability_ids=("reference.geometry_and_guides", "analysis.influence_and_exploration"), launch_surface="tooling", help_topic_id="tools", search_aliases=("геометрия", "справочник", "reference center")),
        DesktopShellCommandSpec("tools.autotest.open", "Открыть autotest GUI", "Запустить вспомогательный центр автономных проверок.", "tools", "launch_module", "Рабочие пространства -> Инструменты -> Autotest GUI", module="pneumo_solver_ui.tools.run_autotest_gui", launch_surface="tooling", help_topic_id="tools", search_aliases=("autotest", "автотест", "проверки")),
        DesktopShellCommandSpec("tools.legacy_shell.open", "Открыть legacy Tk shell", "Запустить прежний notebook-based shell как fallback/debug surface.", "tools", "launch_module", "Рабочие пространства -> Инструменты -> Legacy Tk Shell", module="pneumo_solver_ui.tools.desktop_main_shell", launch_surface="tooling", help_topic_id="tools", search_aliases=("legacy shell", "tk shell", "старый shell"), status_label="Fallback / debug"),
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
