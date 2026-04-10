from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.npz_bundle import (
    ANIMATOR_MAX_FRAME_DS_M,
    _build_animator_dense_time_grid,
    _resample_dataframe_for_animator,
)


ROOT = Path(__file__).resolve().parents[1]
APP_TEXT = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_dense_time_grid_expands_high_speed_bundle_when_distance_step_is_too_large() -> None:
    # 15 m/s with dt=0.02 s -> 0.30 m per sample, which is visibly coarse for animation.
    t = np.linspace(0.0, 0.10, 6)
    df = pd.DataFrame(
        {
            "время_с": t,
            "скорость_vx_м_с": np.full_like(t, 15.0),
            "скорость_vy_м_с": np.zeros_like(t),
            "путь_x_м": 15.0 * t,
        }
    )
    t_new, diag = _build_animator_dense_time_grid(df, meta={"vx0_м_с": 15.0})
    assert t_new is not None
    assert diag["enabled"] is True
    assert int(diag["target_points"]) > len(df)
    assert float(diag["source_max_distance_step_m"]) > float(ANIMATOR_MAX_FRAME_DS_M)
    assert float(diag["target_dt_s"]) <= float(ANIMATOR_MAX_FRAME_DS_M / 15.0) + 1e-12


def test_resample_dataframe_for_animator_keeps_binary_step_hold_for_open_tables() -> None:
    df = pd.DataFrame(
        {
            "время_с": [0.0, 1.0, 2.0],
            "клапан_open": [0.0, 1.0, 0.0],
        }
    )
    t_new = np.asarray([0.0, 0.5, 1.2, 1.8, 2.0], dtype=float)
    out = _resample_dataframe_for_animator(df, t_new, force_step=True)
    assert out is not None
    vals = out["клапан_open"].to_numpy(dtype=float)
    assert set(np.unique(vals).tolist()) <= {0.0, 1.0}
    assert vals.tolist() == [0.0, 0.0, 1.0, 1.0, 0.0]


def test_desktop_animator_uses_continuous_playhead_and_redraws_every_service_tick() -> None:
    assert "self._play_cursor_t_s, self._play_accum_s = _advance_playback_cursor_limited(" in APP_TEXT
    assert "raw_wall_dt_s=raw_wall_dt," in APP_TEXT
    assert "idx = int(_playback_source_index_for_time(t, float(self._play_cursor_t_s)))" in APP_TEXT
    assert "if self._playing:\n            self._update_frame(int(self._idx), sample_t=self._play_cursor_t_s)" in APP_TEXT
    assert "self.cockpit.set_playback_sample_t(" in APP_TEXT
    assert "interactive_scrub: bool = False" in APP_TEXT
