from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence

import streamlit as st


PLAYHEAD_NO_TIME_MESSAGE = "Нет временного массива для таймлайна."
PLAYHEAD_COMPONENT_MISSING_MESSAGE = "Компонент playhead_ctrl не найден (components/playhead_ctrl)."
PLAYHEAD_COMPONENT_HINT = (
    "Воспроизведение и точный переход по времени. Loop по умолчанию выключен "
    "(можно включить в контроле)."
)


def make_playhead_reset_command(*, speed: float = 0.25, time_ms_fn=time.time) -> dict:
    return {
        "ts": int(time_ms_fn() * 1000),
        "set_idx": 0,
        "set_playing": False,
        "set_loop": False,
        "set_speed": float(speed),
    }


def make_playhead_jump_command(index: int, *, time_ms_fn=time.time) -> dict:
    return {
        "ts": int(time_ms_fn() * 1000),
        "set_idx": int(index),
        "set_playing": False,
    }


def make_playhead_pause_command(*, time_ms_fn=time.time) -> dict:
    return {
        "ts": int(time_ms_fn() * 1000),
        "set_playing": False,
    }


def pause_playhead_on_view_switch(
    session_state,
    *,
    view: str,
    cur_hash: str,
    test_pick: str,
    log_event_fn,
    time_ms_fn=time.time,
) -> bool:
    prev_view_key = f"__prev_view_res__{cur_hash}::{test_pick}"
    prev_view = session_state.get(prev_view_key)
    if prev_view == view:
        return False
    session_state[prev_view_key] = view
    log_event_fn("view_switch", view=view, test=test_pick)
    session_state["playhead_cmd"] = make_playhead_pause_command(time_ms_fn=time_ms_fn)
    return True


def render_results_view_selector(
    *,
    options: Sequence[str],
    session_state,
    cur_hash: str,
    test_pick: str,
    log_event_fn,
    radio_fn=None,
    label: str = "Раздел результатов",
    key: str = "baseline_view_res",
    horizontal: bool = True,
) -> str:
    radio_fn = radio_fn or st.radio
    view = radio_fn(
        label,
        options=list(options),
        horizontal=horizontal,
        key=key,
    )
    pause_playhead_on_view_switch(
        session_state,
        view=view,
        cur_hash=cur_hash,
        test_pick=test_pick,
        log_event_fn=log_event_fn,
    )
    return str(view)


def build_playhead_component_events(events_list: Sequence[dict] | None) -> list[dict]:
    return [
        {
            "t": float(event.get("t", event.get("t_s", 0.0))),
            "label": str(event.get("label", "")),
        }
        for event in (events_list or [])
    ]


def render_playhead_component(
    playhead_component,
    *,
    time_s: Sequence[float] | None,
    dataset_id,
    session_state: Mapping[str, object],
    events_list: Sequence[dict] | None,
    send_hz: int,
    storage_hz: int,
    info_fn: Callable[[str], object],
    title: str = "Playhead",
    storage_key: str = "pneumo_play_state",
    height: int = 88,
    events_max: int = 40,
    hint: str = PLAYHEAD_COMPONENT_HINT,
    restore_state: bool = False,
    key: str = "playhead_event",
) -> str:
    has_time = time_s is not None and len(time_s) > 0
    if playhead_component is not None and has_time:
        playhead_component(
            title=title,
            time=time_s,
            dataset_id=str(dataset_id),
            storage_key=storage_key,
            send_hz=int(send_hz),
            storage_hz=int(storage_hz),
            height=int(height),
            cmd=session_state.get("playhead_cmd"),
            events=build_playhead_component_events(events_list),
            events_max=int(events_max),
            hint=hint,
            restore_state=bool(restore_state),
            key=key,
            default=None,
        )
        return "rendered"
    if not has_time:
        info_fn(PLAYHEAD_NO_TIME_MESSAGE)
        return "no_time"
    info_fn(PLAYHEAD_COMPONENT_MISSING_MESSAGE)
    return "missing"


def render_playhead_sync_controls() -> tuple[bool, int, int]:
    cols_phsync = st.columns([1.35, 0.95, 0.95, 0.95], gap="medium")
    with cols_phsync[0]:
        ph_server_sync = st.checkbox(
            "Синхронизация графиков во время Play (СЕРВЕР, тяжело)",
            value=False,
            key="playhead_server_sync",
        )
    with cols_phsync[1]:
        if ph_server_sync:
            ph_send_hz = st.slider(
                "Hz (сервер)",
                1,
                10,
                2,
                1,
                key="playhead_send_hz",
                help=(
                    "Каждые N раз/сек будет происходить полный rerun Streamlit-скрипта, "
                    "чтобы двигались маркеры на графиках. Это может подвисать при N>2."
                ),
            )
        else:
            ph_send_hz = 0
    with cols_phsync[2]:
        ph_storage_hz = st.slider(
            "FPS (браузер)",
            5,
            60,
            30,
            1,
            key="playhead_storage_hz",
            help=(
                "Ограничивает частоту обновления общего playhead через localStorage. "
                "Влияет на плавность 2D/3D анимации, но не вызывает rerun на сервере."
            ),
        )
    with cols_phsync[3]:
        st.caption(
            "Рекомендация: **Hz(сервер)=0** для плавной анимации. "
            "Если нужны маркеры на графиках — 1–2 Hz."
        )

    if ph_server_sync and int(ph_send_hz) >= 4:
        st.warning(
            "Hz(сервер) ≥ 4 часто приводит к зависанию: Streamlit не успевает перерабатывать rerun. "
            "Для плавности увеличивайте FPS(браузер), а не Hz(сервер)."
        )

    return bool(ph_server_sync), int(ph_send_hz), int(ph_storage_hz)
