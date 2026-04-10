from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from pneumo_solver_ui.desktop_animator.app import MainWindow


ROOT = Path(__file__).resolve().parents[1]
ANIM_LATEST_NPZ = ROOT / "pneumo_solver_ui" / "workspace" / "exports" / "anim_latest.npz"


def _make_live_gl_window() -> tuple[QtWidgets.QApplication, MainWindow]:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    win = MainWindow(enable_gl=True)
    win.show()
    app.processEvents()
    return app, win


def _skip_if_live_gl_unavailable(win: MainWindow) -> None:
    car3d = getattr(win.cockpit, "car3d", None)
    if car3d is None:
        pytest.skip("live GL widget is not available in this build")
    if not bool(car3d.has_live_gl_context()):
        pytest.skip("live GL context is not available in this environment")


@pytest.mark.skipif(
    not ANIM_LATEST_NPZ.exists(),
    reason="real anim_latest bundle is not available in workspace/exports",
)
def test_desktop_animator_live_gl_explicit_detach_and_redock_smoke() -> None:
    app, win = _make_live_gl_window()
    try:
        _skip_if_live_gl_unavailable(win)
        cockpit = win.cockpit
        dock = cockpit._docks["dock_3d"]
        ext = cockpit._external_windows["dock_3d"]

        win.load_npz(ANIM_LATEST_NPZ)
        app.processEvents()
        assert win.bundle is not None

        win._update_frame(0)
        app.processEvents()
        assert dock.isVisible()
        assert not cockpit._uses_external_panel_window("dock_3d")

        cockpit._set_external_panel_visible("dock_3d", True)
        app.processEvents()

        assert cockpit._uses_external_panel_window("dock_3d")
        assert ext.isVisible()
        assert not dock.isVisible()
        assert ext.panel_widget() is cockpit._dock_live_widgets["dock_3d"]

        mid = min(10, max(0, len(win.bundle.t) - 1))
        win._update_frame(mid)
        app.processEvents()

        cockpit._set_external_panel_visible("dock_3d", False)
        app.processEvents()

        assert not cockpit._uses_external_panel_window("dock_3d")
        assert not ext.isVisible()
        assert dock.isVisible()
        assert not dock.isFloating()

        win._update_frame(mid)
        app.processEvents()
    finally:
        try:
            if bool(getattr(win, "_playing", False)):
                win.toggle_play()
        except Exception:
            pass
        win.close()
        app.processEvents()


@pytest.mark.skipif(
    not ANIM_LATEST_NPZ.exists(),
    reason="real anim_latest bundle is not available in workspace/exports",
)
def test_desktop_animator_live_gl_layout_guard_auto_pauses_and_resumes_playback() -> None:
    app, win = _make_live_gl_window()
    try:
        _skip_if_live_gl_unavailable(win)
        car3d = win.cockpit.car3d
        assert car3d is not None

        win.load_npz(ANIM_LATEST_NPZ)
        app.processEvents()
        assert win.bundle is not None

        win.toggle_play()
        app.processEvents()
        assert bool(getattr(win, "_playing", False)) is True

        win._on_live_gl_layout_activity("dock_3d:test_runtime")
        app.processEvents()

        assert bool(getattr(win, "_gl_layout_transition_active", False)) is True
        assert bool(getattr(win, "_playing", False)) is False
        assert bool(getattr(win, "_resume_after_gl_layout_transition", False)) is True
        assert bool(getattr(car3d, "_layout_transition_active", False)) is True

        win._finish_gl_layout_transition()
        app.processEvents()

        assert bool(getattr(win, "_gl_layout_transition_active", False)) is False
        assert bool(getattr(win, "_playing", False)) is True
        assert bool(getattr(win, "_resume_after_gl_layout_transition", False)) is False
        assert bool(getattr(car3d, "_layout_transition_active", False)) is False
    finally:
        try:
            if bool(getattr(win, "_playing", False)):
                win.toggle_play()
        except Exception:
            pass
        win.close()
        app.processEvents()
