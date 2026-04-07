from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')


def test_follow_watcher_caches_npz_and_road_signatures_before_recollecting_dependencies() -> None:
    assert 'self._last_npz_sig: Optional[Tuple[bool, int, int]] = None' in APP
    assert 'self._last_road_path: Optional[Path] = None' in APP
    assert 'self._last_road_sig: Optional[Tuple[bool, int, int]] = None' in APP
    assert 'cached_road_sig = self._file_sig(self._last_road_path)' in APP
    assert 'and npz_sig == self._last_npz_sig' in APP
    assert 'and cached_road_sig == self._last_road_sig' in APP


def test_road_preview_window_is_frozen_per_bundle_not_by_instantaneous_speed() -> None:
    assert 'def set_bundle_context(self, bundle: Optional[DataBundle]) -> None:' in APP
    assert 'self.hud.set_bundle_context(b)' in APP
    assert 'self.car3d.set_bundle_context(b)' in APP
    assert 'self._bundle_lookahead_m: Optional[float] = None' in APP
    assert 'self._bundle_history_m: Optional[float] = None' in APP
    assert 'la = self._stable_road_preview_lookahead_m()' in APP
    assert 'la = self._auto_lookahead(vx)' not in APP


def test_playback_tick_redraws_every_service_tick_so_sample_t_affects_visible_geometry() -> None:
    assert 'Continuous playback sampling only helps if we actually redraw every service tick.' in APP
    # Keep this check structural rather than line-exact: while playing we now redraw on
    # every timer wakeup, and only the slider remains quantised to source rows.
    pattern = re.compile(
        r"if self\._playing:\n\s+self\._update_frame\(int\(self\._idx\)\)\n\s+elif advanced or not self\._playing:\n\s+self\._update_frame\(int\(self\._idx\)\)",
        re.MULTILINE,
    )
    assert pattern.search(APP) is not None
    assert 'sample_t=self._playback_sample_t_s if bool(playing) else None' in APP
