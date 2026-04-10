from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _src() -> str:
    return (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')


def test_desktop_animator_uses_native_floatable_dock_for_live_gl_and_guards_layout_changes() -> None:
    src = _src()

    assert 'class ExternalPanelWindow' in src
    assert 'has_live_gl_context' in src
    assert 'QtWidgets.QDockWidget.DockWidgetFloatable' in src
    assert 'self._register_live_gl_layout_guard("dock_3d", dock_3d)' in src
    assert 'self._gl_layout_pause_timer' in src
    assert 'set_layout_transition_active' in src
    assert 'self._register_external_panel_window(' in src
    assert 'dock_name="dock_3d"' in src
    assert 'gl_safe_external_window_on_detach' in src


def test_old_keep_gl_docked_workaround_is_removed_and_native_dock_can_re_attach() -> None:
    src = _src()

    assert 'keep_docked_for_gl' not in src
    assert 'gl_float_dock_suppressed' not in src
    assert 'dock.setFloating(False)' not in src
    assert 'dock.topLevelChanged.connect' in src
    assert 'dock.dockLocationChanged.connect' in src
