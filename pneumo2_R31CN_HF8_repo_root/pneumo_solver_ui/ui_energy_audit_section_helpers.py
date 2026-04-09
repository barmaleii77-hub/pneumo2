from __future__ import annotations

from typing import Any


def render_energy_audit_results_section(
    st: Any,
    *,
    df_Egroups,
    df_Eedges,
    safe_dataframe_fn: Any,
    has_plotly: bool,
    px_module: Any,
    safe_plotly_chart_fn: Any,
    section_title: str,
    top_edges_title: str,
    group_column: str = "группа",
    energy_column: str = "энергия_Дж",
    chart_title: str = "Энергия по группам",
) -> None:
    st.subheader(section_title)
    if df_Egroups is not None and len(df_Egroups):
        df_groups_sorted = df_Egroups.sort_values(energy_column, ascending=False)
        safe_dataframe_fn(df_groups_sorted, height=220)
        if has_plotly and px_module is not None:
            try:
                fig = px_module.bar(
                    df_groups_sorted,
                    x=group_column,
                    y=energy_column,
                    title=chart_title,
                )
                safe_plotly_chart_fn(fig)
            except Exception:
                pass
    if df_Eedges is not None and len(df_Eedges):
        st.markdown(top_edges_title)
        safe_dataframe_fn(
            df_Eedges.sort_values(energy_column, ascending=False).head(20),
            height=320,
        )
