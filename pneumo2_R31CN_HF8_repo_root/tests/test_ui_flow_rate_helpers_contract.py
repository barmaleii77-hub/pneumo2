from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_flow_rate_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


class _Model:
    R_AIR = 287.0
    T_AIR = 293.15


class _BrokenModel:
    @property
    def R_AIR(self):
        raise RuntimeError("boom")


def test_flow_rate_display_scale_and_unit_handles_success_and_fallback() -> None:
    scale, unit = ui_flow_rate_helpers.flow_rate_display_scale_and_unit(
        p_atm=101325.0,
        model_module=_Model(),
    )
    assert scale > 0.0
    assert unit == "Нл/мин"

    scale, unit = ui_flow_rate_helpers.flow_rate_display_scale_and_unit(
        p_atm=101325.0,
        model_module=_BrokenModel(),
        fallback_scale=2.5,
        fallback_unit="kg/s fallback",
    )
    assert scale == 2.5
    assert unit == "kg/s fallback"


def test_entrypoints_use_shared_flow_rate_helper_without_inline_formula() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_flow_rate_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_flow_rate_helpers import (" in heavy_text
    assert "flow_scale_and_unit_fn=flow_rate_display_scale_and_unit" in app_text
    assert "flow_scale_and_unit_fn=flow_rate_display_scale_and_unit" in heavy_text
    assert "rho_N = float(P_ATM)" not in app_text
    assert "rho_N = float(P_ATM)" not in heavy_text
    assert "scale = 1000.0 * 60.0 / rho_N" not in app_text
    assert "scale = 1000.0 * 60.0 / rho_N" not in heavy_text
