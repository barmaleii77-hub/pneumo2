from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    stable_road_grid_cross_spacing_from_view,
)

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_stable_road_grid_cross_spacing_comes_from_bundle_view_scale() -> None:
    spacing_a = stable_road_grid_cross_spacing_from_view(
        nominal_visible_length_m=66.8,
        viewport_width_px=1280,
    )
    spacing_b = stable_road_grid_cross_spacing_from_view(
        nominal_visible_length_m=66.8,
        viewport_width_px=1280,
    )
    spacing_short = stable_road_grid_cross_spacing_from_view(
        nominal_visible_length_m=18.0,
        viewport_width_px=1280,
    )

    assert spacing_a == spacing_b
    assert spacing_a > spacing_short
    assert abs(spacing_a - 0.95) <= 0.15


def test_car3d_tracks_bundle_context_for_world_grid_spacing() -> None:
    assert "def set_bundle_context(self, bundle: Optional[DataBundle]) -> None:" in APP
    assert "def _stable_road_grid_cross_spacing(self, *, viewport_width_px: int, ds_long_m: float) -> float:" in APP
    assert "stable_road_grid_cross_spacing_from_view as _stable_road_grid_cross_spacing_from_view" in APP
    assert "self._road_grid_nominal_visible_len_m" in APP
    assert "self.car3d.set_bundle_context(b)" in APP
    assert "grid_cross_spacing_m = float(self._stable_road_grid_cross_spacing(" in APP


def test_aux_cadence_metrics_are_emitted_for_future_acceptance_bundles() -> None:
    assert "self._aux_cadence_stats: Dict[str, Dict[str, float]] = {}" in APP
    assert "self._aux_cadence_emit_period_s: float = 1.5" in APP
    assert "def _record_aux_cadence(self, dock_name: str, now_ts: float) -> None:" in APP
    assert "def _emit_aux_cadence_metrics(self, now_ts: float, *, playing: bool, many_visible_budget: bool, force: bool = False) -> None:" in APP
    assert "AnimatorAuxCadence" in APP
    assert "self._record_aux_cadence(\"dock_timeline\", now_ts)" in APP
    assert "self._record_aux_cadence(\"dock_trends\", now_ts)" in APP
