from __future__ import annotations

from ..contracts import DesktopShellToolSpec
from ..external_launch import spawn_module


def _launch_desktop_mnemo() -> object:
    return spawn_module("pneumo_solver_ui.desktop_mnemo.main")


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_mnemo",
        title="Мнемосхема",
        description=(
            "Отдельное окно пневматической схемы: показывает состояние контуров, событий "
            "и связи компонентов по выбранному результату."
        ),
        group="Внешние окна",
        mode="external",
        workflow_stage="visualization",
        entry_kind="external",
        capability_ids=("results.mnemo", "visualization.scheme_mnemo"),
        launch_contexts=("data", "results", "analysis"),
        menu_section="Визуализация",
        nav_section="Визуализация",
        details=(
            "Мнемосхема помогает проверить пневматику и сигналы рядом с аниматором; "
            "движение и геометрию смотрите в окне Аниматор."
        ),
        menu_order=80,
        nav_order=80,
        standalone_module="pneumo_solver_ui.desktop_mnemo.main",
        launch_external=_launch_desktop_mnemo,
    )
