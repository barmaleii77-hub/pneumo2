from __future__ import annotations

from pathlib import Path


def test_desktop_animator_bool_guard_for_qt_visibility() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")

    assert "setVisible(bool(np.isfinite(z_rL)))" in src
    assert "setVisible(bool(np.isfinite(z_rR)))" in src
    assert "setVisible(bool(np.isfinite(z_rF)))" in src


def test_desktop_animator_all_panels_are_dock_windows_and_not_tabified() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")

    assert 'obj_name="dock_hud"' in src
    assert 'obj_name="dock_3d"' in src
    assert 'obj_name="dock_front"' in src
    assert 'obj_name="dock_rear"' in src
    assert 'obj_name="dock_left"' in src
    assert 'obj_name="dock_right"' in src
    assert 'obj_name="dock_telemetry"' in src
    assert 'obj_name="dock_trends"' in src
    assert 'obj_name="dock_timeline"' in src

    assert "main.setCentralWidget(self.hud)" not in src
    assert "main.tabifyDockWidget(dock_telemetry, dock_trends)" not in src
    assert "main.tabifyDockWidget(dock_telemetry, dock_timeline)" not in src
    assert "dock.setFloating(True)" in src
    assert "dock.toggleViewAction()" in src
    assert "def enforce_detached_windows(self, main: QtWidgets.QMainWindow" in src
