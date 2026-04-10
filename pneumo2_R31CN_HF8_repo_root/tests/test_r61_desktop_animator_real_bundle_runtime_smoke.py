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
def test_desktop_animator_real_bundle_offscreen_smoke_keeps_multifactor_dock_live() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    win = MainWindow(enable_gl=False)
    try:
        cockpit = getattr(win, "cockpit", None)
        assert cockpit is not None
        dock = win.findChild(QtWidgets.QDockWidget, "dock_multifactor")
        assert dock is not None
        assert dock.widget() is getattr(cockpit, "telemetry_multifactor", None)

        win.load_npz(ANIM_LATEST_NPZ)
        win.show()
        app.processEvents()

        assert win.bundle is not None
        assert len(win.bundle.t) > 10

        win._update_frame(0)
        app.processEvents()
        mid = min(10, max(0, len(win.bundle.t) - 1))
        win._update_frame(mid)
        app.processEvents()

        panel = getattr(cockpit, "telemetry_multifactor", None)
        assert panel is not None
        assert getattr(panel, "_catalog", None) is not None
        assert getattr(panel, "_last_payload_key", None) is not None
        assert panel.summary.toPlainText().strip()
        assert "Heuristic Assistant" in panel.summary.toHtml()
    finally:
        win.close()
        app.processEvents()
