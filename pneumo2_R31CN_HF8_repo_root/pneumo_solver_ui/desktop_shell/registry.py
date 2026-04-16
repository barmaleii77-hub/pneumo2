from __future__ import annotations

from .adapters.autotest_adapter import build_spec as build_autotest_spec
from .adapters.compare_viewer_adapter import build_spec as build_compare_viewer_spec
from .adapters.desktop_animator_adapter import build_spec as build_desktop_animator_spec
from .adapters.desktop_diagnostics_center_adapter import (
    build_spec as build_desktop_diagnostics_center_spec,
)
from .adapters.desktop_engineering_analysis_center_adapter import (
    build_spec as build_desktop_engineering_analysis_center_spec,
)
from .adapters.desktop_geometry_reference_adapter import (
    build_spec as build_desktop_geometry_reference_spec,
)
from .adapters.desktop_input_editor_adapter import build_spec as build_desktop_input_editor_spec
from .adapters.desktop_mnemo_adapter import build_spec as build_desktop_mnemo_spec
from .adapters.desktop_optimizer_center_adapter import (
    build_spec as build_desktop_optimizer_center_spec,
)
from .adapters.desktop_results_center_adapter import (
    build_spec as build_desktop_results_center_spec,
)
from .adapters.desktop_ring_editor_adapter import build_spec as build_desktop_ring_editor_spec
from .adapters.test_center_adapter import build_spec as build_test_center_spec
from .contracts import DesktopShellToolSpec


def build_desktop_shell_specs() -> tuple[DesktopShellToolSpec, ...]:
    specs = (
        build_desktop_input_editor_spec(),
        build_desktop_geometry_reference_spec(),
        build_desktop_ring_editor_spec(),
        build_test_center_spec(),
        build_desktop_optimizer_center_spec(),
        build_desktop_results_center_spec(),
        build_desktop_engineering_analysis_center_spec(),
        build_autotest_spec(),
        build_desktop_diagnostics_center_spec(),
        build_compare_viewer_spec(),
        build_desktop_animator_spec(),
        build_desktop_mnemo_spec(),
    )
    return tuple(
        sorted(
            specs,
            key=lambda spec: (
                int(spec.menu_order),
                int(spec.nav_order),
                str(spec.title or "").lower(),
            ),
        )
    )
