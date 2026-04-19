from __future__ import annotations

import csv
from pathlib import Path

from pneumo_solver_ui.desktop_shell.launcher_catalog import build_desktop_launch_catalog
from pneumo_solver_ui.desktop_spec_shell.catalogs import legacy_key_aliases
from pneumo_solver_ui.desktop_spec_shell.help_registry import build_help_registry, _payload_text
from pneumo_solver_ui.desktop_spec_shell.overview_state import build_overview_snapshot
from pneumo_solver_ui.desktop_spec_shell.registry import (
    SHELL_WORKSPACE_CODE,
    build_command_map,
    build_shell_workspaces,
    build_workspace_map,
)
from pneumo_solver_ui.desktop_spec_shell.search import build_search_entries, search_command_palette


ROOT = Path(__file__).resolve().parents[1]


def test_gui_spec_shell_workspace_order_matches_canonical_route() -> None:
    workspaces = build_shell_workspaces()
    assert [workspace.title for workspace in workspaces] == [
        "Обзор",
        "Исходные данные",
        "Сценарии и редактор кольца",
        "Набор испытаний",
        "Базовый прогон",
        "Оптимизация",
        "Анализ результатов",
        "Анимация",
        "Диагностика",
        "Параметры приложения",
        "Инструменты",
    ]


def test_gui_spec_shell_registry_is_catalog_driven_for_route_critical_surfaces() -> None:
    commands = build_command_map()
    workspaces = {workspace.workspace_id: workspace for workspace in build_shell_workspaces()}

    assert workspaces["input_data"].workspace_owner == "WS-INPUTS"
    assert workspaces["ring_editor"].workspace_owner == "WS-RING"
    assert workspaces["test_matrix"].workspace_owner == "WS-SUITE"
    assert workspaces["baseline_run"].workspace_owner == "WS-BASELINE"
    assert workspaces["optimization"].workspace_owner == "WS-OPTIMIZATION"
    assert workspaces["overview"].workspace_owner == "WS-PROJECT"
    assert workspaces["results_analysis"].workspace_owner == "WS-ANALYSIS"
    assert workspaces["diagnostics"].workspace_owner == "WS-DIAGNOSTICS"
    assert workspaces["tools"].workspace_owner == "WS-TOOLS"
    assert "WS-RESULTS" in workspaces["results_analysis"].catalog_owner_aliases
    assert "WS-ANALYTICS" in workspaces["results_analysis"].catalog_owner_aliases

    assert workspaces["baseline_run"].automation_id == "BL-CONTRACT-CARD"
    assert workspaces["optimization"].automation_id == "OP-STAGERUNNER-BLOCK"
    assert workspaces["results_analysis"].automation_id == "RS-LEADERBOARD"
    assert workspaces["diagnostics"].automation_id == "DG-LAST-BUNDLE"
    assert workspaces["input_data"].launch_surface == "workspace"

    assert commands["diagnostics.collect_bundle"].kind == "hosted_action"
    assert commands["diagnostics.collect_bundle"].automation_id == "DG-BTN-COLLECT"
    assert commands["baseline.center.open"].kind == "open_workspace"
    assert commands["baseline.center.open"].target_workspace_id == "baseline_run"
    assert commands["baseline.center.open"].automation_id == "BL-BTN-RUN"
    assert commands["baseline.review"].kind == "hosted_action"
    assert commands["baseline.review"].automation_id == "BL-BTN-REVIEW"
    assert commands["baseline.adopt"].kind == "hosted_action"
    assert commands["baseline.adopt"].automation_id == "BL-BTN-ADOPT"
    assert commands["baseline.restore"].kind == "hosted_action"
    assert commands["baseline.restore"].automation_id == "BL-BTN-RESTORE"
    assert commands["baseline.legacy_launch.open"].module == "pneumo_solver_ui.tools.test_center_gui"
    assert commands["optimization.center.open"].automation_id == "OP-BTN-LAUNCH"
    assert commands["input.editor.open"].launch_surface == "legacy_bridge"
    assert commands["ring.editor.open"].launch_surface == "legacy_bridge"
    assert commands["test.center.open"].launch_surface == "legacy_bridge"
    assert commands["baseline.legacy_launch.open"].launch_surface == "legacy_bridge"
    assert commands["baseline.center.open"].launch_surface == "workspace"
    assert commands["optimization.center.open"].launch_surface == "legacy_bridge"
    assert commands["results.center.open"].launch_surface == "legacy_bridge"
    assert commands["diagnostics.legacy_center.open"].launch_surface == "legacy_bridge"
    assert commands["diagnostics.legacy_center.open"].module == "pneumo_solver_ui.tools.desktop_diagnostics_center"
    assert "baseline.review" in workspaces["baseline_run"].quick_action_ids
    assert "baseline.adopt" in workspaces["baseline_run"].quick_action_ids
    assert "baseline.restore" in workspaces["baseline_run"].quick_action_ids
    assert "baseline.legacy_launch.open" in workspaces["baseline_run"].quick_action_ids
    assert "workspace.baseline_run.open" in workspaces["optimization"].quick_action_ids


def test_gui_spec_shell_launch_module_commands_do_not_claim_native_workspace_surface() -> None:
    commands = build_command_map()
    allowed_surfaces = {"legacy_bridge", "external_window", "tooling"}

    for command in commands.values():
        if command.kind != "launch_module":
            continue
        assert command.launch_surface in allowed_surfaces, command.command_id
        if command.launch_surface == "legacy_bridge":
            assert command.status_label in {"Отдельное окно", "Переходное окно", "Резервное окно"}


def test_gui_spec_shell_covers_shared_desktop_launch_catalog_without_duplicate_gui_modules() -> None:
    catalog_modules = {
        item.module
        for item in build_desktop_launch_catalog(include_mnemo=True)
        if item.module
    }
    commands = build_command_map()
    command_modules = {
        command.module
        for command in commands.values()
        if command.kind == "launch_module" and command.module
    }
    tools_workspace = build_workspace_map()["tools"]

    assert catalog_modules <= command_modules
    assert commands["animation.mnemo.open"].module == "pneumo_solver_ui.desktop_mnemo.main"
    assert "tools.qt_main_shell.open" in tools_workspace.quick_action_ids
    assert "tools.spec_shell.open" in tools_workspace.quick_action_ids
    assert "animation.mnemo.open" in tools_workspace.quick_action_ids
    assert "animation.animator.open" in tools_workspace.quick_action_ids
    assert "results.compare.open" in tools_workspace.quick_action_ids


def test_gui_spec_shell_runtime_workspace_owners_cover_v37_contract_matrix() -> None:
    matrix_path = ROOT / "docs" / "context" / "gui_spec_imports" / "v37_github_kb_supplement" / "WORKSPACE_CONTRACT_MATRIX.csv"
    with matrix_path.open("r", encoding="utf-8-sig", newline="") as handle:
        v37_workspace_ids = {row["workspace_id"] for row in csv.DictReader(handle)}

    runtime_workspace_ids = {
        workspace.workspace_owner
        for workspace in build_shell_workspaces()
        if workspace.workspace_owner
    }
    runtime_workspace_ids.add(SHELL_WORKSPACE_CODE)

    assert v37_workspace_ids <= runtime_workspace_ids
    assert "GLOBAL" not in runtime_workspace_ids
    assert "WS-RESULTS" not in runtime_workspace_ids
    assert "WS-ANALYTICS" not in runtime_workspace_ids


def test_gui_spec_shell_search_indexes_migration_aliases_and_visual_routes() -> None:
    workspaces = build_shell_workspaces()
    commands = tuple(build_command_map().values())
    entries = build_search_entries(workspaces, commands)

    diagnostics_hits = search_command_palette(entries, "собрать диагностику")
    stiffness_hits = search_command_palette(entries, "жёсткость")
    mnemo_hits = search_command_palette(entries, "пневмосхема")
    baseline_hits = search_command_palette(entries, "активный опорный прогон")
    baseline_review_hits = search_command_palette(entries, "просмотр опорного прогона")

    assert diagnostics_hits
    assert diagnostics_hits[0].command_id == "diagnostics.collect_bundle"
    assert stiffness_hits
    assert stiffness_hits[0].command_id == "workspace.input_data.open"
    assert mnemo_hits
    assert any(hit.command_id == "animation.mnemo.open" for hit in mnemo_hits)
    assert baseline_hits
    assert baseline_hits[0].command_id in {"baseline.center.open", "workspace.baseline_run.open"}
    assert baseline_review_hits
    assert any(hit.command_id == "baseline.review" for hit in baseline_review_hits)


def test_gui_spec_shell_help_registry_covers_every_workspace_with_catalog_text() -> None:
    workspaces = build_shell_workspaces()
    help_registry = build_help_registry()

    for workspace in workspaces:
        assert workspace.workspace_id in help_registry
        topic = help_registry[workspace.workspace_id]
        assert topic.source_of_truth
        assert topic.next_step
        assert topic.hard_gate

    assert help_registry["diagnostics"].tooltip_text
    assert help_registry["optimization"].why_it_matters
    assert help_registry["results_analysis"].result_location
    assert help_registry["overview"].title == "Последовательность работы"

    visible_help_text = "\n".join(
        "\n".join(
            (
                topic.title,
                topic.summary,
                topic.source_of_truth,
                topic.units_policy,
                topic.next_step,
                topic.hard_gate,
                topic.graphics_policy,
                topic.tooltip_text,
                topic.why_it_matters,
                topic.result_location,
            )
        )
        for topic in help_registry.values()
    )
    for forbidden in ("pipeline", "source-of-truth", "master-copy", "suite", "baseline", "contract", "контракт"):
        assert forbidden not in visible_help_text


def test_gui_spec_shell_legacy_mojibake_keys_are_generated_for_compatibility() -> None:
    aliases = legacy_key_aliases("название")
    assert aliases[0] == "название"
    assert aliases[1].encode("cp1251").decode("utf-8") == "название"
    assert _payload_text({aliases[1]: "Старый импорт"}, aliases, "") == "Старый импорт"

    for rel in (
        "pneumo_solver_ui/desktop_spec_shell/catalogs.py",
        "pneumo_solver_ui/desktop_spec_shell/help_registry.py",
        "pneumo_solver_ui/desktop_spec_shell/registry.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        assert aliases[1] not in text


def test_gui_spec_shell_overview_snapshot_exposes_project_baseline_results_and_diagnostics() -> None:
    snapshot = build_overview_snapshot(ROOT)
    titles = [card.title for card in snapshot.cards]

    assert "Текущий проект" in titles
    assert "Активный опорный прогон" in titles
    assert "Настройки оптимизации" in titles
    assert "Последние результаты" in titles
    assert "Последний архив диагностики" in titles
    assert "Последний diagnostics bundle" not in titles
    assert "Проверка готовности" in titles
    assert "Health / self-check" not in titles
    actions = {card.title: card.action_text for card in snapshot.cards}
    assert actions["Текущий проект"] == "Открыть исходные данные"
    assert actions["Активный опорный прогон"] == "Открыть базовый прогон"
    assert actions["Последний архив диагностики"] == "Собрать диагностику"

    visible_text = "\n".join(
        part
        for card in snapshot.cards
        for part in (card.title, card.value, card.detail)
    )
    for forbidden in (
        "diagnostics bundle",
        "Health / self-check",
        "self-check",
        "Workflow graphs",
        "PySide6=",
        "Animator=",
        "Diagnostics=",
        "shell",
        "bridge",
        "workspace",
        "артефактов",
    ):
        assert forbidden not in visible_text


def test_gui_spec_overview_snapshot_does_not_recursively_scan_user_desktop() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_spec_shell" / "overview_state.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'desktop_root = Path.home() / "Desktop"' in src
    assert "recursive=False" in src
    assert "desktop_root.rglob" not in src
    assert "_latest_path(desktop_root" not in src


def test_gui_spec_shell_main_window_uses_hosted_hubs_and_single_dispatcher() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_spec_shell" / "main_window.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class DesktopGuiSpecMainWindow(QtWidgets.QMainWindow):" in src
    assert "self.command_search = QtWidgets.QComboBox()" in src
    assert 'diagnostics_button = QtWidgets.QPushButton("Собрать диагностику")' in src
    assert "self.primary_action_button = QtWidgets.QPushButton(" in src
    assert "def _compact_command_title(" in src
    assert "def _primary_command_title(" in src
    assert "self.pinned_list = QtWidgets.QListWidget()" in src
    assert "ControlHubWorkspacePage" in src
    assert "InputWorkspacePage" in src
    assert "BaselineWorkspacePage" in src
    assert "OptimizationWorkspacePage" in src
    assert "ResultsWorkspacePage" in src
    assert "DiagnosticsWorkspacePage" in src
    assert 'STARTUP_WORKSPACE_ENV = "PNEUMO_GUI_SPEC_SHELL_OPEN_WORKSPACE"' in src
    assert src.count("def open_workspace(") == 1
    assert src.count("def run_command(") == 1
    for expected in (
        "PneumoApp - Главное окно приложения",
        "Сейчас открыт рабочий шаг «Обзор»",
        "Быстрый поиск окон и действий",
        "Окна",
        "Цели и ограничения: основные показатели расчёта",
        "Обязательное условие. Происхождение опорного прогона должно быть видимо",
        "Краткая сводка.",
        "Открыть рабочее место с вкладками",
        "Открыть центр диагностики",
        "О главном окне приложения",
        "Фокус перенесён в панель свойств и справки",
        "Действие пока недоступно в окне",
        "Окна ->",
        "Главное окно собирает основные инженерные окна приложения",
    ):
        assert expected in src
    for forbidden in (
        "PneumoApp Desktop Shell",
        "Рабочее пространство: Обзор",
        "Рабочие пространства",
        "PneumoApp - главное окно",
        "Раздел: Обзор",
        "Сейчас открыт раздел",
        "Открыто: Обзор",
        "Открыт раздел",
        "Поиск команд, окон и разделов",
        "Фокус региона:",
        "Открыто окно:",
        "Режим:",
        "Сводка окна:",
        "Обязательное условие:",
        "Почему это важно:",
        "Где виден результат:",
        "Контракт:",
        "Жёсткое ограничение:",
        "Маршрут: основной поэтапный запуск",
        "Важно: происхождение опорного прогона",
        "Открыть старое главное окно",
        "Открыть прежний центр диагностики",
        "Открыть резервное окно приложения",
        "Открыть резервный центр диагностики",
        "Действие пока недоступно для раздела",
        "Разделы ->",
        "legacy Tk shell",
        "legacy diagnostics center",
        "О shell по GUI-spec",
        "О GUI-spec shell",
        "Этот shell",
        "Route-critical workspaces",
        "hosted surfaces",
        "Hosted action",
        "fallback/debug surface",
        "inspector/help pane",
    ):
        assert forbidden not in src


def test_gui_spec_shell_is_available_in_shared_launch_catalog() -> None:
    catalog = build_desktop_launch_catalog(include_mnemo=True)
    modules = {item.module for item in catalog}
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_gui_spec_shell.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "pneumo_solver_ui.tools.desktop_gui_spec_shell" in modules
    assert '"--open"' in src
    assert "PNEUMO_GUI_SPEC_SHELL_OPEN_WORKSPACE" in src
