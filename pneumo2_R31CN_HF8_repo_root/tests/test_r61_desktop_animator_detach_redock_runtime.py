from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from pneumo_solver_ui.desktop_animator.app import MainWindow


ROOT = Path(__file__).resolve().parents[1]
ANIM_LATEST_NPZ = ROOT / "pneumo_solver_ui" / "workspace" / "exports" / "anim_latest.npz"


@pytest.mark.skipif(
    not ANIM_LATEST_NPZ.exists(),
    reason="real anim_latest bundle is not available in workspace/exports",
)
def test_desktop_animator_explicit_detach_and_redock_keeps_3d_panel_alive() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    win = MainWindow(enable_gl=False)
    try:
        cockpit = getattr(win, "cockpit", None)
        assert cockpit is not None
        dock = cockpit._docks["dock_3d"]
        ext = cockpit._external_windows["dock_3d"]

        win.show()
        app.processEvents()

        cockpit._set_external_panel_visible("dock_3d", False)
        app.processEvents()
        assert not cockpit._uses_external_panel_window("dock_3d")

        win.load_npz(ANIM_LATEST_NPZ)
        app.processEvents()
        assert win.bundle is not None

        win._update_frame(0)
        app.processEvents()
        assert dock.isVisible()

        cockpit._set_external_panel_visible("dock_3d", True)
        app.processEvents()

        assert cockpit._uses_external_panel_window("dock_3d")
        assert ext.isVisible()
        assert not dock.isVisible()
        assert ext.panel_widget() is cockpit._dock_live_widgets["dock_3d"]
        assert not cockpit._dock_detached_placeholders["dock_3d"].isHidden()

        mid = min(10, max(0, len(win.bundle.t) - 1))
        win._update_frame(mid)
        app.processEvents()

        cockpit._set_external_panel_visible("dock_3d", False)
        app.processEvents()

        assert not cockpit._uses_external_panel_window("dock_3d")
        assert not ext.isVisible()
        assert dock.isVisible()
        assert not dock.isFloating()
        assert cockpit._dock_live_widgets["dock_3d"].parent() is cockpit._dock_live_hosts["dock_3d"]

        win._update_frame(mid)
        app.processEvents()
    finally:
        win.close()
        app.processEvents()
