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


def render_animation_section(
    st: Any,
    *,
    cur_hash: str,
    test_pick: str,
    render_mechanics_fn: Callable[[], None],
    render_flow_tool_fn: Callable[[], None],
    render_svg_scheme_fn: Callable[[], None],
) -> str:
    anim_view = render_animation_view_selector(
        st,
        cur_hash=cur_hash,
        test_pick=test_pick,
    )
    if anim_view == ANIMATION_VIEW_MECHANICS:
        render_mechanics_fn()
    else:
        render_non_mechanical_animation_subsection(
            anim_view,
            render_flow_tool_fn=render_flow_tool_fn,
            render_svg_scheme_fn=render_svg_scheme_fn,
        )
    return anim_view


def render_animation_results_section(
    st: Any,
    *,
    cur_hash: str,
    test_pick: str,
    render_mechanics_panel_fn: Callable[..., None],
    mechanics_panel_kwargs: dict[str, Any],
    render_flow_tool_panel_fn: Callable[..., None],
    flow_panel_kwargs: dict[str, Any],
    render_svg_scheme_section_fn: Callable[..., None],
    svg_scheme_args: tuple[Any, ...] = (),
    svg_scheme_kwargs: dict[str, Any],
) -> str:
    def _render_mechanics() -> None:
        render_mechanics_panel_fn(st, **mechanics_panel_kwargs)

    def _render_flow_tool_animation() -> None:
        render_flow_tool_panel_fn(st, **flow_panel_kwargs)

    def _render_svg_scheme_animation() -> None:
        render_svg_scheme_section_fn(st, *svg_scheme_args, **svg_scheme_kwargs)

    return render_animation_section(
        st,
        cur_hash=cur_hash,
        test_pick=test_pick,
        render_mechanics_fn=_render_mechanics,
        render_flow_tool_fn=_render_flow_tool_animation,
        render_svg_scheme_fn=_render_svg_scheme_animation,
    )
