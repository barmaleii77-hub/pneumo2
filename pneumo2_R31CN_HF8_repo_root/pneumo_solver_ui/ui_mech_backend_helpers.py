from __future__ import annotations

from typing import Any


MECH_BACKEND_OPTIONS = [
    "Встроенный (matplotlib, совместимость)",
    "Компонент (SVG/Canvas, быстро)",
]
MECH_BACKEND_HELP = (
    "Если видишь ошибки Streamlit Component (например apiVersion undefined) — "
    "используй встроенный режим."
)
MECH_COMPONENT_TIMELINE_HINT = (
    "Управление Play/Pause/скоростью — в блоке **Таймлайн (общий playhead)** выше. "
    "Во время Play сервер не дёргается; синхронизация графиков выполняется при паузе/скраббинге."
)


def render_mechanical_animation_backend_selector(
    st: Any,
    session_state: dict[str, Any],
    *,
    cache_key: str,
    dataset_id: str,
    log_event_fn: Any,
    proc_metrics_fn: Any,
    default_backend_index: int,
    description_text: str,
) -> bool:
    col_anim_a, col_anim_b = st.columns([1, 2])
    with col_anim_a:
        anim_backend = st.selectbox(
            "Движок анимации",
            MECH_BACKEND_OPTIONS,
            index=int(default_backend_index),
            key=f"anim_backend_{cache_key}",
            help=MECH_BACKEND_HELP,
        )
    use_component_anim = bool(str(anim_backend).startswith("Компонент"))
    with col_anim_b:
        st.caption(description_text)
    try:
        current_backend = "component" if use_component_anim else "fallback"
        last_backend = session_state.get(f"_anim_backend_last::{cache_key}")
        if last_backend != current_backend:
            session_state[f"_anim_backend_last::{cache_key}"] = current_backend
            log_event_fn(
                "anim_backend_selected",
                backend=current_backend,
                dataset_id=str(dataset_id),
                proc=proc_metrics_fn(),
            )
    except Exception:
        pass
    if use_component_anim:
        st.caption(MECH_COMPONENT_TIMELINE_HINT)
    return use_component_anim
