from __future__ import annotations

from typing import Any

from pneumo_solver_ui.ui_svg_route_auto_panel_helpers import (
    render_svg_route_auto_panel,
)
from pneumo_solver_ui.ui_svg_route_guided_panel_helpers import (
    render_svg_route_guided_panel,
)
from pneumo_solver_ui.ui_svg_route_helpers import (
    build_svg_route_label_items,
    build_svg_route_options,
    format_svg_route_item,
)
from pneumo_solver_ui.ui_svg_route_search_panel_helpers import (
    render_svg_route_search_panel,
)


def render_svg_connectivity_panel(
    st: Any,
    session_state: dict[str, Any],
    edge_columns: list[str],
    route_write_view_box: str,
    *,
    name_score_fn: Any,
    shortest_path_fn: Any,
    evaluate_quality_fn: Any,
    safe_dataframe_fn: Any,
) -> None:
    with st.expander("Путь по схеме (connectivity beta)", expanded=False):
        st.info(
            "Инструмент ниже ищет кратчайший путь по *геометрическому графу* труб (line->nodes/edges), "
            "между двумя текстовыми метками SVG. "
            "Результат подсвечивается на схеме как маршрут (overlay)."
        )

        analysis = session_state.get("svg_autotrace_analysis")
        if not analysis:
            st.warning("Сначала нажмите **Проанализировать SVG** в блоке выше.")
            return

        texts = analysis.get("texts", [])
        if not isinstance(texts, list) or len(texts) == 0:
            st.warning("В SVG не найдены текстовые метки (<text>).")
            return

        filter_text = st.text_input(
            "Фильтр меток (подстрока, регистр не важен)",
            value=session_state.get("svg_route_filter", ""),
            key="svg_route_filter",
        )

        items = build_svg_route_label_items(texts, filter_text=filter_text, limit=600)
        if len(items) == 0:
            st.warning("Нет подходящих меток (после фильтрации). Попробуйте очистить фильтр.")
            return

        options, option_index = build_svg_route_options(items)

        render_svg_route_guided_panel(
            session_state,
            items,
            edge_columns,
            name_score_fn=name_score_fn,
            format_item_fn=format_svg_route_item,
            safe_dataframe_fn=safe_dataframe_fn,
        )
        render_svg_route_auto_panel(
            session_state,
            items,
            texts,
            analysis,
            edge_columns,
            format_item_fn=format_svg_route_item,
            name_score_fn=name_score_fn,
            shortest_path_fn=shortest_path_fn,
            evaluate_quality_fn=evaluate_quality_fn,
            safe_dataframe_fn=safe_dataframe_fn,
        )
        render_svg_route_search_panel(
            session_state,
            items,
            options,
            option_index,
            texts,
            analysis,
            edge_columns,
            route_write_view_box=route_write_view_box,
            format_item_fn=format_svg_route_item,
            shortest_path_fn=shortest_path_fn,
            evaluate_quality_fn=evaluate_quality_fn,
        )
