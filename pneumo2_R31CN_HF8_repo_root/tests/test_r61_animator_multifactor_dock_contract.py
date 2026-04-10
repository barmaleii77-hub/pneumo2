from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")
PANEL = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "engineering_analysis_panel.py").read_text(encoding="utf-8")


def test_animator_source_registers_multifactor_analysis_dock_and_panel_updates() -> None:
    for needle in (
        "from .engineering_analysis_panel import MultiFactorAnalysisPanel",
        "self.telemetry_multifactor = MultiFactorAnalysisPanel()",
        'obj_name="dock_multifactor"',
        '("dock_multifactor", getattr(self, "telemetry_multifactor", None), "update_frame")',
        'multifactor_panel = getattr(self, "telemetry_multifactor", None)',
        '"dock_multifactor": (3, 1, 1, 2)',
        'self._dock_layout_version = "r31cz_multifactor_insight_dock_v1"',
    ):
        assert needle in APP


def test_multifactor_panel_source_exposes_corner_cloud_heatmap_and_heuristic_assistant() -> None:
    for needle in (
        "class MultiFactorAnalysisPanel",
        "class _CornerCloudCanvas",
        "class _CorrelationMatrixCanvas",
        "Corner Cloud",
        "Correlation Heatmap",
        "Heuristic Assistant",
        "build_multifactor_analysis_payload(",
    ):
        assert needle in PANEL
