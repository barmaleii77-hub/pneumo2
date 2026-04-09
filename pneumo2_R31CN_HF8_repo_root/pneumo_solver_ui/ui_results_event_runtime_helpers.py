from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable


def compute_results_events(
    *,
    compute_events_fn: Callable[..., Any],
    base_override: Mapping[str, object] | None,
    p_atm: float,
    session_state: Mapping[str, object],
    df_main,
    df_p,
    df_open,
    test: dict[str, Any],
    vacuum_state_key: str,
    pmax_state_key: str,
    vacuum_kwarg_name: str,
    pmax_kwarg_name: str,
    events_enabled_key: str = "events_show",
    chatter_toggle_state_key: str = "events_chatter_toggles",
    default_vacuum_gauge: float = -0.2,
    default_pmax_margin: float = 0.10,
    chatter_window_s: float = 0.25,
    default_chatter_toggles: int = 6,
    max_events: int = 240,
) -> list[dict[str, Any]]:
    if not bool(session_state.get(events_enabled_key, True)):
        return []

    try:
        params_for_events = dict(base_override or {})
        params_for_events["_P_ATM"] = float(p_atm)
        events = compute_events_fn(
            df_main=df_main,
            df_p=df_p,
            df_open=df_open,
            params_abs=params_for_events,
            test=test,
            chatter_window_s=chatter_window_s,
            chatter_toggle_count=int(session_state.get(chatter_toggle_state_key, default_chatter_toggles)),
            max_events=max_events,
            **{
                vacuum_kwarg_name: float(session_state.get(vacuum_state_key, default_vacuum_gauge)),
                pmax_kwarg_name: float(session_state.get(pmax_state_key, default_pmax_margin)),
            },
        )
    except Exception:
        return []

    return list(events or [])
