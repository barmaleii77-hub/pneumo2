from __future__ import annotations

from ..contracts import DesktopShellToolSpec
from ..external_launch import spawn_module


def _launch_desktop_animator() -> object:
    return spawn_module("pneumo_solver_ui.desktop_animator.app")


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_animator",
        title="Аниматор",
        description="Визуализация движения подвески, хода цилиндров и поведения модели по результатам расчёта.",
        group="Внешние окна",
        mode="external",
        workflow_stage="visualization",
        entry_kind="external",
        capability_ids=("results.animator", "visualization.suspension_motion"),
        launch_contexts=("data", "results", "analysis"),
        menu_section="Визуализация",
        nav_section="Визуализация",
        details="Наглядная анимированная проверка кинематики, хода и поведения подвески на дорожном профиле.",
        menu_order=70,
        nav_order=70,
        standalone_module="pneumo_solver_ui.desktop_animator.app",
        launch_external=_launch_desktop_animator,
    )
