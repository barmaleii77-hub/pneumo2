from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_playhead_section_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
RESULTS_SURFACE_SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


def test_render_playhead_results_section_coordinates_shared_layers(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    fallback_calls: list[str] = []

    monkeypatch.setattr(
        ui_playhead_section_helpers,
        "render_playhead_sync_controls",
        lambda: (False, 2, 30),
    )

    def fake_render_playhead_component(component, **kwargs):
        calls.append(("component", kwargs))
        assert component == "playhead-component"
        assert kwargs["send_hz"] == 2
        assert kwargs["storage_hz"] == 30
        return "missing"

    monkeypatch.setattr(
        ui_playhead_section_helpers,
        "render_playhead_component",
        fake_render_playhead_component,
    )
    monkeypatch.setattr(
        ui_playhead_section_helpers,
        "render_event_alerts_panel",
        lambda events_list, *, safe_dataframe_fn: calls.append(("events", list(events_list or []))),
    )
    monkeypatch.setattr(
        ui_playhead_section_helpers,
        "render_playhead_display_settings",
        lambda **kwargs: calls.append(("settings", kwargs)) or (True, False),
    )
    monkeypatch.setattr(
        ui_playhead_section_helpers,
        "render_playhead_value_panel",
        lambda **kwargs: calls.append(("panel", kwargs)),
    )

    status = ui_playhead_section_helpers.render_playhead_results_section(
        "playhead-component",
        dataset_id="dataset-1",
        time_s=[0.0, 1.0],
        session_state={"playhead_cmd": {"ts": 1}},
        events_list=[{"t": 1.0, "label": "A"}],
        safe_dataframe_fn=lambda *args, **kwargs: None,
        df_main="df_main",
        df_p="df_p",
        df_mdot="df_mdot",
        playhead_x=1.0,
        pressure_from_pa_fn=float,
        pressure_unit="бар (изб.)",
        stroke_scale=1000.0,
        stroke_unit="мм",
        flow_scale_and_unit_fn=lambda **kwargs: (1.0, "кг/с"),
        p_atm=101325.0,
        model_module=object(),
        info_fn=lambda text: None,
        caption_fn=lambda text: None,
        expander_fn=lambda *args, **kwargs: None,
        columns_fn=lambda count: [object()] * count,
        checkbox_fn=lambda *args, **kwargs: True,
        missing_component_fallback_fn=lambda: fallback_calls.append("missing"),
    )

    assert status == "missing"
    assert fallback_calls == ["missing"]
    assert [name for name, _ in calls] == ["component", "events", "settings", "panel"]
    assert calls[3][1]["enabled"] is False
    assert calls[3][1]["pressure_unit"] == "бар (изб.)"
    assert calls[3][1]["stroke_unit"] == "мм"


def test_entrypoints_use_shared_playhead_results_section() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = RESULTS_SURFACE_SECTION_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_playhead_section_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_playhead_section_helpers import (" not in heavy_text
    assert "render_playhead_results_section(" not in app_text
    assert "render_playhead_results_section(" not in heavy_text
    assert "render_playhead_results_section_fn=render_playhead_results_section" in surface_text
    assert "render_playhead_sync_controls()" not in app_text
    assert "render_playhead_sync_controls()" not in heavy_text
    assert "render_event_alerts_panel(" not in app_text
    assert "render_event_alerts_panel(" not in heavy_text
    assert "render_playhead_display_settings(" not in app_text
    assert "render_playhead_display_settings(" not in heavy_text
    assert "render_playhead_value_panel(" not in app_text
    assert "render_playhead_value_panel(" not in heavy_text
