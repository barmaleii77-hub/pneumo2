from __future__ import annotations

from ..contracts import DesktopShellToolSpec
from ..external_launch import spawn_module


def _launch_desktop_mnemo() -> object:
    return spawn_module("pneumo_solver_ui.desktop_mnemo.app")


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_mnemo",
        title="Desktop Mnemo",
        description="Внешнее окно мнемосхемы с follow-режимом и просмотром событий.",
        group="Внешние окна",
        mode="external",
        standalone_module="pneumo_solver_ui.desktop_mnemo.app",
        launch_external=_launch_desktop_mnemo,
    )
