from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from pneumo_solver_ui.ui_event_panel_helpers import render_event_alerts_panel
from pneumo_solver_ui.ui_playhead_helpers import (
    render_playhead_component,
    render_playhead_sync_controls,
)
from pneumo_solver_ui.ui_playhead_value_helpers import (
    render_playhead_display_settings,
    render_playhead_value_panel,
)


def render_playhead_results_section(
    playhead_component,
    *,
    dataset_id,
    time_s: Sequence[float] | None,
    session_state: Mapping[str, object],
    events_list: Sequence[dict] | None,
    safe_dataframe_fn,
    df_main,
    df_p,
    df_mdot,
    playhead_x: float | None,
    pressure_from_pa_fn: Callable[[object], float],
    pressure_unit: str,
    stroke_scale: float,
    stroke_unit: str,
    flow_scale_and_unit_fn: Callable[..., tuple[float, str]],
    p_atm: float,
    model_module,
    info_fn,
    caption_fn,
    expander_fn,
    columns_fn,
    checkbox_fn,
    missing_component_fallback_fn: Callable[[], None] | None = None,
    render_event_alerts_panel_fn=None,
) -> str:
    render_event_alerts_panel_fn = render_event_alerts_panel_fn or render_event_alerts_panel
    _ph_server_sync, ph_send_hz, ph_storage_hz = render_playhead_sync_controls()

    playhead_status = render_playhead_component(
        playhead_component,
        time_s=time_s,
        dataset_id=dataset_id,
        session_state=session_state,
        events_list=events_list,
        send_hz=ph_send_hz,
        storage_hz=ph_storage_hz,
        info_fn=info_fn,
    )
    if playhead_status == "missing" and missing_component_fallback_fn is not None:
        missing_component_fallback_fn()

    render_event_alerts_panel_fn(
        events_list,
        safe_dataframe_fn=safe_dataframe_fn,
    )

    _show_markers, show_values = render_playhead_display_settings(
        columns_fn=columns_fn,
        checkbox_fn=checkbox_fn,
    )

    render_playhead_value_panel(
        enabled=show_values,
        df_main=df_main,
        df_p=df_p,
        df_mdot=df_mdot,
        playhead_x=playhead_x,
        session_state=session_state,
        pressure_from_pa_fn=pressure_from_pa_fn,
        pressure_unit=pressure_unit,
        stroke_scale=stroke_scale,
        stroke_unit=stroke_unit,
        flow_scale_and_unit_fn=flow_scale_and_unit_fn,
        p_atm=p_atm,
        model_module=model_module,
        safe_dataframe_fn=safe_dataframe_fn,
        caption_fn=caption_fn,
        info_fn=info_fn,
        expander_fn=expander_fn,
    )
    return playhead_status
