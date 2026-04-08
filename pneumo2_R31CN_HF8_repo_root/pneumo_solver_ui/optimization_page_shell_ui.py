from __future__ import annotations

from typing import Any, Callable


def render_optimization_page_header(
    st: Any,
    *,
    title: str,
    caption: str,
) -> None:
    st.title(title)
    st.caption(caption)


def render_optimization_navigation_row(
    st: Any,
    *,
    home_label: str,
    home_key: str,
    home_action: Callable[[], None],
    home_fallback: str,
    results_label: str,
    results_key: str,
    results_action: Callable[[], None],
    results_fallback: str,
    db_label: str,
    db_key: str,
    db_action: Callable[[], None],
    db_fallback: str,
) -> None:
    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if st.button(home_label, width="stretch", key=home_key):
            try:
                home_action()
            except Exception:
                st.info(home_fallback)
    with nav2:
        if st.button(results_label, width="stretch", key=results_key):
            try:
                results_action()
            except Exception:
                st.info(results_fallback)
    with nav3:
        if st.button(db_label, width="stretch", key=db_key):
            try:
                db_action()
            except Exception:
                st.info(db_fallback)


def render_optimization_readonly_expanders(
    st: Any,
    *,
    last_label: str,
    render_last: Callable[[], None],
    physical_label: str,
    render_physical: Callable[[], None],
    history_label: str,
    render_history: Callable[[], None],
) -> None:
    with st.expander(last_label, expanded=True):
        render_last()
    with st.expander(physical_label, expanded=True):
        render_physical()
    with st.expander(history_label, expanded=True):
        render_history()


def render_optimization_help_expander(
    st: Any,
    *,
    label: str,
    markdown_text: str,
    expanded: bool = False,
) -> None:
    with st.expander(label, expanded=expanded):
        st.markdown(markdown_text)


__all__ = [
    "render_optimization_help_expander",
    "render_optimization_navigation_row",
    "render_optimization_page_header",
    "render_optimization_readonly_expanders",
]
