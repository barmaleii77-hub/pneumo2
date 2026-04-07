from __future__ import annotations

from pathlib import Path



def test_desktop_animator_persists_and_closes_external_panel_windows() -> None:
    src = (Path(__file__).resolve().parents[1] / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')

    assert 'restore_external_panel_state' in src
    assert 'save_external_panel_state' in src
    assert 'close_external_panel_windows' in src
    assert 'self.cockpit.restore_external_panel_state(s)' in src
    assert 'self.cockpit.save_external_panel_state(s)' in src
    assert 'self.cockpit.close_external_panel_windows()' in src
    assert 'self._set_external_panel_visible(name, bool(visible))' in src
    assert 'visible = bool(self._uses_external_panel_window(name) and window.isVisible())' in src
