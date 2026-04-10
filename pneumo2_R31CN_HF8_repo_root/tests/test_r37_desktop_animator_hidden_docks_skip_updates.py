from __future__ import annotations

from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py"


def test_desktop_animator_skips_non_exposed_docks_on_playback_updates() -> None:
    src = APP.read_text(encoding="utf-8")

    assert 'def _dock_is_visible(self, dock_name: str) -> bool:' in src
    assert 'def _dock_is_exposed(self, dock_name: str) -> bool:' in src
    assert 'if not self._dock_is_exposed(dock_name):' in src
    assert 'if self._dock_is_exposed("dock_timeline"):' in src
    assert 'if self._dock_is_exposed("dock_trends"):' in src
    assert 'if self.car3d is not None and self._dock_is_visible("dock_3d"):' in src

    assert 'self.axleF.update_frame(b, i)' not in src
    assert 'self.axleR.update_frame(b, i)' not in src
    assert 'self.sideL.update_frame(b, i)' not in src
    assert 'self.sideR.update_frame(b, i)' not in src
    assert 'self.telemetry.update_frame(b, i)' not in src
    assert 'self.timeline.set_playhead_time(self._playback_sample_t_s, idx=i)' in src


def test_desktop_animator_refreshes_current_frame_when_dock_becomes_visible() -> None:
    src = APP.read_text(encoding="utf-8")

    assert 'dock.visibilityChanged.connect(lambda visible, _name=str(obj_name): self._on_dock_visibility_changed(_name, bool(visible)))' in src
    assert 'def _on_dock_visibility_changed(self, dock_name: str, visible: bool) -> None:' in src
    assert 'self.update_frame(self._last_i)' in src
