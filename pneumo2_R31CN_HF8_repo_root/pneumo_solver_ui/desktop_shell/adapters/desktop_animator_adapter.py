from __future__ import annotations

from ..contracts import DesktopShellToolSpec
from ..external_launch import spawn_module


def _launch_desktop_animator() -> object:
    return spawn_module("pneumo_solver_ui.desktop_animator.app")


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_animator",
        title="Desktop Animator",
        description="Внешний PySide6-аниматор для anim_latest и локальных сценариев.",
        group="Внешние окна",
        mode="external",
        standalone_module="pneumo_solver_ui.desktop_animator.app",
        launch_external=_launch_desktop_animator,
    )
