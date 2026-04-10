from __future__ import annotations

from pathlib import Path


def test_desktop_mnemo_settings_bridge_reads_view_mode_and_falls_back(tmp_path: Path) -> None:
    from pneumo_solver_ui.desktop_mnemo.settings_bridge import (
        desktop_mnemo_event_log_path,
        desktop_mnemo_settings_path,
        desktop_mnemo_view_mode_label,
        infer_desktop_mnemo_startup_seek,
        normalize_desktop_mnemo_view_mode,
        read_desktop_mnemo_view_mode,
    )

    assert desktop_mnemo_settings_path(tmp_path) == (
        tmp_path / "pneumo_solver_ui" / "workspace" / "desktop_animator_settings.ini"
    )
    npz_path = tmp_path / "workspace" / "exports" / "anim_latest.npz"
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    npz_path.write_bytes(b"")
    assert desktop_mnemo_event_log_path(npz_path) == (
        tmp_path / "workspace" / "exports" / "anim_latest.desktop_mnemo_events.json"
    )
    assert normalize_desktop_mnemo_view_mode("overview") == "overview"
    assert normalize_desktop_mnemo_view_mode("anything_else") == "focus"
    assert desktop_mnemo_view_mode_label("overview") == "Полная схема"
    assert desktop_mnemo_view_mode_label("focus") == "Фокусный сценарий"
    assert read_desktop_mnemo_view_mode(tmp_path) == "focus"
    missing_seek = infer_desktop_mnemo_startup_seek(npz_path)
    assert missing_seek["available"] is False
    assert missing_seek["source"] == "none"
    assert missing_seek["edge_name"] == ""
    assert missing_seek["node_name"] == ""
    assert missing_seek["focus_label"] == ""

    ini_path = desktop_mnemo_settings_path(tmp_path)
    ini_path.parent.mkdir(parents=True, exist_ok=True)
    ini_path.write_text("[desktop_mnemo]\nview_mode=overview\n", encoding="utf-8")

    assert read_desktop_mnemo_view_mode(tmp_path) == "overview"

    event_log = desktop_mnemo_event_log_path(npz_path)
    event_log.write_text(
        """{
  "current_time_s": 0.5,
  "current_mode": "Регуляторный коридор",
  "active_latches": [
    {
      "time_s": 0.5,
      "title": "Большой перепад давлений",
      "summary": "Нужно проверить Ресивер3 и Pmid.",
      "edge_name": "регулятор_до_себя_Pmid_сброс",
      "node_name": "Ресивер3"
    }
  ],
  "recent_events": [
    {
      "time_s": 0.5,
      "title": "Смена режима",
      "summary": "Переход в регуляторный коридор."
    }
  ]
}""",
        encoding="utf-8",
    )
    seek = infer_desktop_mnemo_startup_seek(npz_path)
    assert seek["available"] is True
    assert seek["source"] == "active_latch"
    assert seek["time_s"] == 0.5
    assert "Большой перепад давлений" in str(seek["label"])
    assert seek["edge_name"] == "регулятор_до_себя_Pmid_сброс"
    assert seek["node_name"] == "Ресивер3"
    assert seek["focus_label"] == "регулятор_до_себя_Pmid_сброс / Ресивер3"
