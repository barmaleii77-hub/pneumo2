from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_car3d_always_uses_current_playback_sample_time_not_only_play_state() -> None:
    marker = "if self.car3d is not None and self._dock_is_visible(\"dock_3d\"):"
    assert marker in APP
    tail = APP.split(marker, 1)[1][:240]
    assert "self.car3d.update_frame(" in tail
    assert "sample_t=self._playback_sample_t_s," in tail
