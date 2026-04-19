from __future__ import annotations

from pneumo_solver_ui.desktop_spec_shell.catalogs import (
    ACTIVE_GUI_SPEC_IMPORT_VERSION,
    ACTIVE_IMPORT_ROOT,
    docking_rules_by_panel,
    f6_region_order,
    get_help_topic,
    get_tooltip,
    get_ui_element,
    keyboard_shortcuts_by_name,
    load_field_catalog,
    load_help_catalog,
    load_migration_matrix,
    load_tooltip_catalog,
    load_ui_element_catalog,
    ui_state_palette,
)
from pneumo_solver_ui.desktop_spec_shell.registry import build_command_map, build_shell_workspaces


def test_active_catalogs_load_from_v3_and_keep_utf8_machine_readable_contracts() -> None:
    ui_elements = load_ui_element_catalog()
    fields = load_field_catalog()
    help_topics = load_help_catalog()
    tooltips = load_tooltip_catalog()
    migration_rows = load_migration_matrix()

    assert ACTIVE_GUI_SPEC_IMPORT_VERSION == "v3"
    assert ACTIVE_IMPORT_ROOT.name == "v3"
    assert ui_elements["SH-CMD-SEARCH"].title == "Поиск команд"
    assert fields["RG-FLD-SCENARIO-NAME"].title == "Название сценария"
    assert fields["RG-FLD-SCENARIO-NAME"].field_type == "text_editor"
    assert help_topics["HELP-SH-CMD-SEARCH"].title == "Поиск команд"
    assert help_topics["HELP-SH-CMD-SEARCH"].payload["что_это"] == "Поиск команд"
    assert tooltips["TT-SH-CMD-SEARCH"].related_help_id == "HELP-SH-CMD-SEARCH"
    assert migration_rows[0].workspace_codes == ("WS-INPUTS",)


def test_route_critical_workspaces_and_hosted_commands_have_catalog_metadata() -> None:
    workspaces = {workspace.workspace_id: workspace for workspace in build_shell_workspaces()}
    commands = build_command_map()

    for workspace_id in (
        "input_data",
        "ring_editor",
        "test_matrix",
        "baseline_run",
        "optimization",
        "results_analysis",
        "diagnostics",
    ):
        workspace = workspaces[workspace_id]
        assert workspace.automation_id
        assert workspace.help_id
        assert workspace.workspace_owner
        assert get_ui_element(workspace.automation_id) is not None
        assert get_help_topic(workspace.help_id) is not None

    for command_id in (
        "diagnostics.collect_bundle",
        "baseline.center.open",
        "optimization.center.open",
    ):
        command = commands[command_id]
        assert command.automation_id
        assert command.tooltip_id
        assert get_ui_element(command.automation_id) is not None
        assert get_tooltip(command.tooltip_id) is not None


def test_v3_runtime_matrices_expose_shell_shortcuts_docking_and_state_contracts() -> None:
    shortcuts = keyboard_shortcuts_by_name()
    docks = docking_rules_by_panel()
    states = ui_state_palette()

    assert shortcuts["Поиск команд"] == "Ctrl+K"
    assert shortcuts["Быстрый поиск"] == "Ctrl+K"
    assert shortcuts["Главное действие шага"] == "Ctrl+Enter"
    assert shortcuts["Собрать диагностику"] == "Ctrl+Shift+D"
    assert shortcuts["Помощь по выбранному элементу"] == "F1"
    assert f6_region_order() == (
        "верхняя_командная_панель",
        "левая_навигация",
        "центральная_рабочая_область",
        "правая_панель_свойств_и_справки",
        "нижняя_строка_состояния",
    )
    assert docks["левая_навигация"].can_float is False
    assert docks["правая_панель_свойств_и_справки"].can_second_monitor is True
    assert states["STATE-WARNING"].title == "Предупреждение"
    assert states["STATE-ERROR"].border == "граница_ошибки"
