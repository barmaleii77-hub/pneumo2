from __future__ import annotations

from .adapters.autotest_adapter import build_spec as build_autotest_spec
from .adapters.compare_viewer_adapter import build_spec as build_compare_viewer_spec
from .adapters.desktop_animator_adapter import build_spec as build_desktop_animator_spec
from .adapters.desktop_input_editor_adapter import build_spec as build_desktop_input_editor_spec
from .adapters.desktop_mnemo_adapter import build_spec as build_desktop_mnemo_spec
from .adapters.desktop_optimizer_center_adapter import (
    build_spec as build_desktop_optimizer_center_spec,
)
from .adapters.desktop_ring_editor_adapter import build_spec as build_desktop_ring_editor_spec
from .adapters.full_diagnostics_adapter import build_spec as build_full_diagnostics_spec
from .adapters.send_results_adapter import build_spec as build_send_results_spec
from .adapters.test_center_adapter import build_spec as build_test_center_spec
from .contracts import DesktopShellToolSpec


def build_desktop_shell_specs() -> tuple[DesktopShellToolSpec, ...]:
    return (
        build_desktop_input_editor_spec(),
        build_desktop_optimizer_center_spec(),
        build_desktop_ring_editor_spec(),
        build_test_center_spec(),
        build_autotest_spec(),
        build_full_diagnostics_spec(),
        build_send_results_spec(),
        build_compare_viewer_spec(),
        build_desktop_animator_spec(),
        build_desktop_mnemo_spec(),
    )
