from __future__ import annotations

from pathlib import Path


def test_desktop_mnemo_settings_bridge_reads_view_mode_and_falls_back(tmp_path: Path) -> None:
    from pneumo_solver_ui.desktop_mnemo.settings_bridge import (
        build_desktop_mnemo_settings_contract,
        desktop_mnemo_event_log_path,
        desktop_mnemo_settings_path,
        desktop_mnemo_view_mode_label,
        infer_desktop_mnemo_startup_seek,
        normalize_desktop_mnemo_detail_mode,
        normalize_desktop_mnemo_flow_display_mode,
        normalize_desktop_mnemo_pressure_display_mode,
        normalize_desktop_mnemo_view_mode,
        read_desktop_mnemo_display_units,
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
    assert normalize_desktop_mnemo_flow_display_mode("kg_s") == "kg_s"
    assert normalize_desktop_mnemo_flow_display_mode("anything_else") == "nlpm"
    assert normalize_desktop_mnemo_pressure_display_mode("pa_abs") == "pa_abs"
    assert normalize_desktop_mnemo_pressure_display_mode("anything_else") == "bar_g"
    assert normalize_desktop_mnemo_detail_mode("full") == "full"
    assert normalize_desktop_mnemo_detail_mode("anything_else") == "operator"
    assert desktop_mnemo_view_mode_label("overview") == "Полная схема"
    assert desktop_mnemo_view_mode_label("focus") == "Фокусный сценарий"
    assert read_desktop_mnemo_view_mode(tmp_path) == "focus"
    assert read_desktop_mnemo_display_units(tmp_path) == {
        "flow_display_mode": "nlpm",
        "pressure_display_mode": "bar_g",
        "detail_mode": "operator",
    }
    missing_settings_contract = build_desktop_mnemo_settings_contract(tmp_path)
    assert missing_settings_contract["schema_version"] == "desktop_mnemo_settings_bridge_v1"
    assert missing_settings_contract["settings_available"] is False
    assert missing_settings_contract["view_mode"] == "focus"
    assert missing_settings_contract["flow_display_mode"] == "nlpm"
    assert missing_settings_contract["pressure_display_mode"] == "bar_g"
    assert missing_settings_contract["detail_mode"] == "operator"
    assert missing_settings_contract["display_units_truth_state"] == "unavailable"
    assert missing_settings_contract["truth_state"] == "unavailable"
    missing_seek = infer_desktop_mnemo_startup_seek(npz_path)
    assert missing_seek["available"] is False
    assert missing_seek["source"] == "none"
    assert missing_seek["edge_name"] == ""
    assert missing_seek["node_name"] == ""
    assert missing_seek["focus_label"] == ""

    ini_path = desktop_mnemo_settings_path(tmp_path)
    ini_path.parent.mkdir(parents=True, exist_ok=True)
    ini_path.write_text(
        "[desktop_mnemo]\n"
        "view_mode=overview\n"
        "flow_display_mode=kg_s\n"
        "pressure_display_mode=pa_abs\n"
        "detail_mode=full\n",
        encoding="utf-8",
    )

    assert read_desktop_mnemo_view_mode(tmp_path) == "overview"
    assert read_desktop_mnemo_display_units(tmp_path) == {
        "flow_display_mode": "kg_s",
        "pressure_display_mode": "pa_abs",
        "detail_mode": "full",
    }
    settings_contract = build_desktop_mnemo_settings_contract(tmp_path)
    assert settings_contract["settings_available"] is True
    assert settings_contract["view_mode"] == "overview"
    assert settings_contract["view_mode_label"] == "Полная схема"
    assert settings_contract["flow_display_mode"] == "kg_s"
    assert settings_contract["pressure_display_mode"] == "pa_abs"
    assert settings_contract["detail_mode"] == "full"
    assert settings_contract["display_units"] == {
        "flow_display_mode": "kg_s",
        "pressure_display_mode": "pa_abs",
        "detail_mode": "full",
    }
    assert settings_contract["display_units_truth_state"] == "source_data_confirmed"
    assert settings_contract["truth_state"] == "source_data_confirmed"

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
