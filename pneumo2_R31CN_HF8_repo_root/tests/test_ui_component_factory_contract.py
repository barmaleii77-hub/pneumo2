from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_components


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


def test_ui_components_exports_canonical_component_factories() -> None:
    assert callable(ui_components.get_pneumo_svg_flow_component)
    assert callable(ui_components.get_mech_anim_component)
    assert callable(ui_components.get_mech_car3d_component)
    assert callable(ui_components.get_playhead_ctrl_component)
    assert callable(ui_components.last_error)


def test_entrypoints_use_shared_ui_components_without_local_declare_component_blocks() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_components import (" in surface_text

    for pattern in [
        "def get_pneumo_svg_flow_component(",
        "def get_mech_anim_component(",
        "def get_mech_car3d_component(",
        "def get_playhead_ctrl_component(",
        "components.declare_component(",
        "_PNEUMO_SVG_FLOW_COMPONENT",
        "_MECH_ANIM_COMPONENT",
        "_MECH_CAR3D_COMPONENT",
        "_PLAYHEAD_CTRL_COMPONENT",
    ]:
        assert pattern not in app_text
        assert pattern not in heavy_text


def test_heavy_ui_uses_shared_component_last_error_instead_of_local_err_state() -> None:
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")

    assert "last_error as component_last_error" in surface_text
    assert '"component_last_error_fn": component_last_error' in surface_text
    assert "_MECH_ANIM_COMPONENT_ERR" not in surface_text
    assert "_MECH_CAR3D_COMPONENT_ERR" not in surface_text
    assert "ComponentFactoryRebind" not in surface_text
