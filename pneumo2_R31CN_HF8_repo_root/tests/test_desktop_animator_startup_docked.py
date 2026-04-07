from __future__ import annotations

from pathlib import Path


def test_desktop_animator_startup_policy_keeps_docks_attached_and_uses_native_gl_autopause() -> None:
    src = (Path(__file__).resolve().parents[1] / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')

    assert 'startup_native_gl_autopause_with_gl_suspend_on_layout' in src
    assert 'Animator starts with docks attached.' in src
    assert 'native dock/floating mode again' in src
    assert 'the 3D viewport is temporarily suspended until the layout settles' in src
    assert 'startup_external_gl_window' not in src
    assert 'QtCore.QTimer.singleShot(220, _apply_layout)' not in src
    assert 'self._settings.setValue("window/layout_version", self._dock_layout_version)' in src
