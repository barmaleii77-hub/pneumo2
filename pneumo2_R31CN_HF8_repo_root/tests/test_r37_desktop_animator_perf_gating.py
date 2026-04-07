from __future__ import annotations

from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py"


def test_desktop_animator_refreshes_all_visible_aux_panes_at_capped_fps() -> None:
    src = APP.read_text(encoding="utf-8")

    assert "self._aux_play_fast_fps" in src
    assert "self._aux_play_slow_fps" in src
    assert "self._many_visible_threshold" in src
    assert "def _dock_is_exposed(self, dock_name: str) -> bool:" in src
    assert "for entry in fast_visible:" in src
    assert "for entry in slow_visible:" in src
    assert 'if self.car3d is not None and self._dock_is_visible("dock_3d")' in src
    assert "self.cockpit.update_frame(idx, playing=bool(self._playing))" in src
