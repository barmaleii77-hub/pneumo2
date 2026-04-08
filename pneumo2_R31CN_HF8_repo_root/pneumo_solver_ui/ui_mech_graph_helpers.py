from __future__ import annotations

DEFAULT_MECH_CORNERS = ["ЛП", "ПП", "ЛЗ", "ПЗ"]


def render_mech_corner_selection(
    *,
    session_state,
    markdown_fn,
    columns_fn,
    multiselect_fn,
    caption_fn,
    key: str = "mech_plot_corners",
) -> list[str]:
    default_corners = session_state.get(key)
    if not default_corners:
        default_corners = list(DEFAULT_MECH_CORNERS)

    markdown_fn("**Углы (механика) — синхронизация с анимацией**")
    col_pick, col_hint = columns_fn([1, 4], gap="small")
    with col_pick:
        picked_corners = multiselect_fn(
            "Углы",
            options=list(DEFAULT_MECH_CORNERS),
            default=default_corners,
            key=key,
            label_visibility="collapsed",
        )
    with col_hint:
        caption_fn("Клик по колесу/оси в вкладке «Анимация → Механика» обновляет этот выбор.")

    if not picked_corners:
        return list(DEFAULT_MECH_CORNERS)
    return list(picked_corners)


def collect_mech_metric_columns(
    df_main,
    *,
    corners: list[str],
    name_template: str,
    fallback_prefix: str | None = None,
) -> list[str]:
    columns: list[str] = []
    for corner in corners:
        column = name_template.format(corner=corner)
        if column in df_main.columns:
            columns.append(column)
    if not columns and fallback_prefix:
        columns = [column for column in df_main.columns if column.startswith(fallback_prefix)]
    return columns


def render_mech_overview_graphs(
    *,
    plot_lines_fn,
    df_main,
    tcol: str,
    playhead_x,
    events,
    events_max: int,
    events_show_labels: bool,
    session_state,
    markdown_fn,
    columns_fn,
    multiselect_fn,
    caption_fn,
) -> list[str]:
    if df_main is None:
        return []

    picked_corners = render_mech_corner_selection(
        session_state=session_state,
        markdown_fn=markdown_fn,
        columns_fn=columns_fn,
        multiselect_fn=multiselect_fn,
        caption_fn=caption_fn,
    )

    force_columns = collect_mech_metric_columns(
        df_main,
        corners=picked_corners,
        name_template="нормальная_сила_шины_{corner}_Н",
        fallback_prefix="нормальная_сила_шины_",
    )
    if force_columns:
        plot_lines_fn(
            df_main,
            tcol,
            force_columns,
            title="Нормальные силы шин",
            yaxis_title="Н",
            playhead_x=playhead_x,
            events=events,
            events_max=events_max,
            events_show_labels=events_show_labels,
        )

    stroke_columns = collect_mech_metric_columns(
        df_main,
        corners=picked_corners,
        name_template="положение_штока_{corner}_м",
    )
    if stroke_columns:
        plot_lines_fn(
            df_main,
            tcol,
            stroke_columns,
            title="Положение штоков",
            yaxis_title="м",
            playhead_x=playhead_x,
            events=events,
            events_max=events_max,
            events_show_labels=events_show_labels,
        )

    velocity_columns = collect_mech_metric_columns(
        df_main,
        corners=picked_corners,
        name_template="скорость_штока_{corner}_м_с",
        fallback_prefix="скорость_штока_",
    )
    if velocity_columns:
        plot_lines_fn(
            df_main,
            tcol,
            velocity_columns,
            title="Скорость штоков",
            yaxis_title="м/с",
            playhead_x=playhead_x,
            events=events,
            events_max=events_max,
            events_show_labels=events_show_labels,
        )

    return picked_corners
