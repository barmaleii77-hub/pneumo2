from __future__ import annotations

from pathlib import Path


def test_install_docks_belongs_to_cockpitwidget_not_pressurepanel() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")

    pressure_start = src.index("class PressurePanel")
    cockpit_start = src.index("class CockpitWidget")
    pressure_slice = src[pressure_start:cockpit_start]
    cockpit_slice = src[cockpit_start:]

    assert "def install_docks(self, main: QtWidgets.QMainWindow) -> None:" not in pressure_slice
    assert "def install_docks(self, main: QtWidgets.QMainWindow) -> None:" in cockpit_slice
    assert "self.cockpit.install_docks(self)" in src
