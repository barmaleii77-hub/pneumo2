from __future__ import annotations

from typing import Any, Callable


ANIMATION_VIEW_MECHANICS = "Механика"
ANIMATION_VIEW_FLOW_TOOL = "Потоки (инструмент)"
ANIMATION_VIEW_SVG_SCHEME = "Пневмосхема (SVG)"
ANIMATION_VIEW_OPTIONS = [
    ANIMATION_VIEW_MECHANICS,
    ANIMATION_VIEW_FLOW_TOOL,
    ANIMATION_VIEW_SVG_SCHEME,
]


def render_animation_view_selector(
    st: Any,
    *,
    cur_hash: str,
    test_pick: str,
) -> str:
    st.subheader("Анимация")
    return st.radio(
        "Подраздел",
        options=ANIMATION_VIEW_OPTIONS,
        horizontal=True,
        key=f"anim_view_{cur_hash}::{test_pick}",
    )


def render_non_mechanical_animation_subsection(
    anim_view: str,
    *,
    render_flow_tool_fn: Callable[[], None],
    render_svg_scheme_fn: Callable[[], None],
) -> bool:
    if anim_view == ANIMATION_VIEW_FLOW_TOOL:
        render_flow_tool_fn()
        return True
    if anim_view == ANIMATION_VIEW_SVG_SCHEME:
        render_svg_scheme_fn()
        return True
    return False
