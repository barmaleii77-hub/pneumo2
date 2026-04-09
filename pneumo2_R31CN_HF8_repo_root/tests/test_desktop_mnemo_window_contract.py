from __future__ import annotations

from pathlib import Path


def test_desktop_mnemo_window_has_persistent_docks_and_playhead_bridge() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_mnemo" / "app.py").read_text(encoding="utf-8")

    assert 'obj_name="dock_overview"' in src
    assert 'obj_name="dock_selection"' in src
    assert 'obj_name="dock_guide"' in src
    assert 'obj_name="dock_events"' in src
    assert 'obj_name="dock_trends"' in src
    assert 'obj_name="dock_legend"' in src
    assert 'prefix="desktop_mnemo"' in src
    assert "toggleViewAction()" in src
    assert "GuidancePanel" in src
    assert "EventMemoryPanel" in src
    assert "MnemoEventTracker" in src
    assert "Диагностические сценарии" in src
    assert "Латчи и события" in src
    assert "ACK события" in src
    assert "Reset события" in src
    assert "Экспорт событий" in src
    assert "_write_event_log_sidecar" in src
    assert "desktop_mnemo_events.json" in src
    assert "window.codexMnemoDispatch" in src
    assert "window.codexMnemoSetAlerts" in src
    assert "show_alert_overlay" in src
    assert "_build_frame_alert_payload" in src
    assert 'PLAYHEAD_STORAGE_KEY = "pneumo_desktop_mnemo_playhead"' in src


def test_desktop_mnemo_svg_component_has_alert_overlay_contract() -> None:
    src = (
        Path(__file__).resolve().parents[1]
        / "pneumo_solver_ui"
        / "components"
        / "pneumo_svg_flow"
        / "index.html"
    ).read_text(encoding="utf-8")

    assert 'id="alertHud"' in src
    assert 'id="togAlerts"' in src
    assert "pneumo_overlay_alerts" in src
    assert "updateAlertOverlay" in src
    assert "alertPath" in src
    assert "alertNodeRing" in src
