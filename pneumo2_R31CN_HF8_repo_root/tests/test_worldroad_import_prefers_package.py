from __future__ import annotations

import importlib


def test_worldroad_model_imports_package_road_surface() -> None:
    mod = importlib.import_module("pneumo_solver_ui.model_pneumo_v9_mech_doublewishbone_worldroad")
    assert getattr(mod, "road_surface", None) is not None
