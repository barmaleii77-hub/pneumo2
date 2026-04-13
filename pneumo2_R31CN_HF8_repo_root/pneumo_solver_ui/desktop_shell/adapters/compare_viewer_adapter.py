from __future__ import annotations

from ..contracts import DesktopShellToolSpec
from ..external_launch import spawn_module


def _launch_compare_viewer() -> object:
    return spawn_module("pneumo_solver_ui.qt_compare_viewer")


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="compare_viewer",
        title="Compare Viewer",
        description="Внешнее Qt-окно для сравнения прогонов и NPZ-трасс.",
        group="Внешние окна",
        mode="external",
        standalone_module="pneumo_solver_ui.qt_compare_viewer",
        launch_external=_launch_compare_viewer,
    )
