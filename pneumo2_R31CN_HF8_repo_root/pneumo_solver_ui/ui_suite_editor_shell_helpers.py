from __future__ import annotations

from typing import Any

from pneumo_solver_ui.optimization_input_contract import infer_suite_stage


SUITE_PRESET_LABELS = {
    "worldroad_flat": "Ровная дорога (WorldRoad)",
    "worldroad_sine_x": "Синус вдоль (A=2 см, λ=2 м)",
    "worldroad_bump": "Бугор (h=4 см, w=0.6 м)",
    "inertia_brake": "Инерция: торможение ax=-3 м/с²",
}

SUITE_TEST_TYPE_LABELS = {
    "worldroad": "Дорожный профиль (WorldRoad)",
    "road_profile_csv": "Дорога из CSV",
    "maneuver_csv": "Манёвр из CSV (ax/ay)",
    "инерция_крен": "Инерция: крен",
    "инерция_тангаж": "Инерция: тангаж",
    "микро_синфаза": "Микроход: синфаза",
    "микро_разнофаза": "Микроход: разнофаза",
    "кочка_одно_колесо": "Кочка: одно колесо",
    "кочка_диагональ": "Кочка: диагональ",
    "комбо_крен_плюс_микро": "Комбо: крен + микроход",
}


def format_suite_test_type_label(value: Any) -> str:
    key = str(value or "").strip()
    if not key:
        return "тип не задан"
    return str(SUITE_TEST_TYPE_LABELS.get(key, key))


def render_app_suite_editor_intro(st: Any) -> None:
    st.subheader("2. Набор сценариев")
    st.caption(
        "Сначала соберите или загрузите набор сценариев, затем выберите один сценарий слева "
        "и редактируйте его карточку справа. Так проще держать структуру сценариев под "
        "контролем и не теряться в длинных таблицах."
    )


def render_heavy_suite_editor_intro(st: Any) -> None:
    st.caption(
        "Работайте по шагам: сначала настройте фильтры и найдите нужный сценарий, "
        "затем проверьте карточку справа, и только после этого меняйте стадию сценария, тип сценария "
        "и параметры дороги или манёвра."
    )


def render_heavy_suite_preset_wizard(
    st: Any,
    *,
    preset_options: list[str],
    preset_key: str,
    default_preset: str,
    add_button_key: str,
    on_add_preset: Any,
) -> str:
    wiz_l, wiz_r = st.columns([1.2, 1.0], gap="medium")
    current_preset = str(st.session_state.get(preset_key, default_preset) or default_preset)
    if current_preset not in preset_options:
        current_preset = preset_options[0]
    with wiz_l:
        preset = str(
            st.selectbox(
                "Добавить сценарий по шаблону",
                options=preset_options,
                format_func=lambda value: SUITE_PRESET_LABELS.get(str(value), str(value)),
                help="Шаблон добавит новый сценарий с разумными настройками. Затем его можно "
                "уточнить в карточке справа.",
                index=preset_options.index(current_preset),
                key=preset_key,
            )
        )
    with wiz_r:
        st.button(
            "Добавить",
            width="stretch",
            key=add_button_key,
            on_click=on_add_preset,
            args=(preset,),
        )
    return preset


def render_suite_list_caption(st: Any) -> None:
    st.caption("Список сценариев набора. Слева выбирается сценарий, справа редактируется его карточка.")


def render_app_suite_search_box(
    st: Any,
    *,
    key: str,
    placeholder: str,
) -> str:
    return str(
        st.text_input(
            "Поиск сценария",
            value=st.session_state.get(key, ""),
            key=key,
            placeholder=placeholder,
        )
        or ""
    )


def render_heavy_suite_filter_row(
    st: Any,
    *,
    stages: list[int],
    default_stages: list[int],
    stage_filter_key: str,
    only_enabled_key: str,
    search_key: str,
    on_reset_filters: Any,
    reset_args: tuple[Any, ...],
) -> tuple[list[int], bool, str]:
    f1, f2, f3, f4 = st.columns([1.0, 1.0, 1.2, 0.8], gap="small")
    with f1:
        stage_filter = st.multiselect(
            "Стадии",
            options=stages,
            default=default_stages,
            help="Показывать сценарии выбранных стадий.",
            key=stage_filter_key,
        )
    st.caption(
        "Логика оптимизации по стадиям: S0 — быстрый предварительный отсев; "
        "S1 — длинные дорожные и манёвренные сценарии; "
        "S2 — финальная стадия проверки устойчивости."
    )
    st.caption(
        "Явно заданная стадия 1 не должна молча переписываться в 0 при фильтрации, "
        "редактировании и нормализации стадий."
    )
    with f2:
        only_enabled = bool(
            st.checkbox(
                "Только включённые",
                value=False,
                key=only_enabled_key,
                help="Скрывает выключенные сценарии.",
            )
        )
    with f3:
        suite_search = str(
            st.text_input(
                "Поиск",
                value=st.session_state.get(search_key, ""),
                key=search_key,
                help="Ищет по имени сценария и типу.",
            )
            or ""
        ).strip()
    with f4:
        st.button(
            "Сбросить фильтры",
            width="stretch",
            key="ui_suite_reset_filters_btn",
            on_click=on_reset_filters,
            args=reset_args,
        )
    return list(stage_filter), only_enabled, suite_search


def render_suite_hidden_summary(
    st: Any,
    *,
    summary_text: str | None,
    show_all_button_key: str | None = None,
    on_show_all: Any | None = None,
    show_all_args: tuple[Any, ...] = (),
) -> None:
    if not summary_text:
        return
    cols_info = st.columns([1.0, 0.28], gap="small")
    with cols_info[0]:
        st.info(summary_text)
    with cols_info[1]:
        if show_all_button_key and on_show_all is not None:
            st.button(
                "Показать весь набор",
                key=show_all_button_key,
                width="stretch",
                on_click=on_show_all,
                args=show_all_args,
            )


def render_suite_selection_box(
    st: Any,
    *,
    label: str,
    options: list[Any],
    index: int,
    format_func: Any,
    key: str,
    help_text: str | None = None,
) -> Any:
    return st.selectbox(
        label,
        options=options,
        index=index,
        format_func=format_func,
        key=key,
        help=help_text,
    )


def render_suite_total_count_caption(st: Any, *, total_count: int) -> None:
    st.caption(f"Всего сценариев: {int(total_count)}")


def build_app_suite_selection_options(
    df_suite_edit: Any,
    *,
    query: str,
) -> tuple[list[int], list[str]]:
    labels: list[str] = []
    idx_map: list[int] = []
    query_text = str(query or "").strip().lower()

    for i, r in df_suite_edit.iterrows():
        name = str(r.get("имя") or f"test_{i}")
        typ = str(r.get("тип") or "")
        enabled = bool(r.get("включен")) if ("включен" in r) else True
        label = build_suite_option_label(enabled=enabled, name=name, typ=typ)
        if query_text and query_text not in label.lower():
            continue
        labels.append(label)
        idx_map.append(int(i))

    return idx_map, labels


def render_app_suite_list_panel(
    st: Any,
    *,
    idx_map: list[int],
    labels: list[str],
    selection_key: str,
    filtered: bool,
    total_count: int,
) -> int | None:
    if not labels:
        render_suite_empty_list_state(st, filtered=filtered)
        render_suite_total_count_caption(st, total_count=total_count)
        return None

    render_suite_list_caption(st)
    if selection_key not in st.session_state:
        st.session_state[selection_key] = idx_map[0]
    if st.session_state[selection_key] not in idx_map:
        st.session_state[selection_key] = idx_map[0]

    selected = render_suite_selection_box(
        st,
        label="Сценарий",
        options=idx_map,
        index=idx_map.index(st.session_state[selection_key]) if st.session_state[selection_key] in idx_map else 0,
        format_func=lambda i: (labels[idx_map.index(i)] if i in idx_map else str(i)),
        key=selection_key,
    )
    render_suite_total_count_caption(st, total_count=total_count)
    try:
        return int(selected)
    except Exception:
        return None


def build_heavy_suite_list_label(df_view: Any, suite_id: str) -> str:
    try:
        row = df_view[df_view["id"].astype(str) == str(suite_id)].iloc[0].to_dict()
        stage = int(infer_suite_stage(row))
        name = str(row.get("имя", "")).strip() or "без названия"
        typ = str(row.get("тип", "")).strip() or "тип не задан"
        return build_suite_option_label(
            enabled=bool(row.get("включен", False)),
            name=name,
            typ=typ,
            stage=stage,
        )
    except Exception:
        return str(suite_id)


def build_heavy_suite_list_frame(df_view: Any) -> Any:
    list_df = df_view[["включен", "стадия", "имя", "тип"]].copy()
    list_df["тип"] = list_df["тип"].map(format_suite_test_type_label)
    return list_df.rename(
        columns={
            "включен": "Вкл.",
            "стадия": "Стадия",
            "имя": "Сценарий",
            "тип": "Тип",
        }
    )


def render_heavy_suite_list_panel(
    st: Any,
    *,
    df_view: Any,
    row_ids: list[str],
    current_selected_id: str,
    selection_key: str,
    filtered: bool,
    total_count: int,
) -> str:
    if df_view.empty:
        render_suite_empty_list_state(st, filtered=filtered)
        render_suite_total_count_caption(st, total_count=total_count)
        return ""

    render_suite_list_caption(st)
    if row_ids:
        render_suite_selection_box(
            st,
            label="Сценарий для редактирования",
            options=list(row_ids),
            index=row_ids.index(current_selected_id) if current_selected_id in row_ids else 0,
            format_func=lambda suite_id: build_heavy_suite_list_label(df_view, str(suite_id)),
            key=selection_key,
            help_text="Выберите сценарий, который хотите редактировать в карточке справа.",
        )

    st.dataframe(
        build_heavy_suite_list_frame(df_view),
        hide_index=True,
        width="stretch",
        height=320,
    )
    render_suite_total_count_caption(st, total_count=total_count)
    return str(st.session_state.get(selection_key) or current_selected_id or "")


def render_app_suite_left_panel(
    st: Any,
    *,
    df_suite_edit: Any,
    search_key: str,
    search_placeholder: str,
    selection_key: str,
) -> tuple[int | None, dict[str, bool]]:
    query = render_app_suite_search_box(
        st,
        key=search_key,
        placeholder=search_placeholder,
    )
    idx_map, labels = build_app_suite_selection_options(df_suite_edit, query=query)
    selected_index = render_app_suite_list_panel(
        st,
        idx_map=idx_map,
        labels=labels,
        selection_key=selection_key,
        filtered=bool(query.strip()),
        total_count=len(df_suite_edit),
    )
    actions = render_app_suite_action_row(
        st,
        duplicate_disabled=(selected_index is None),
        delete_disabled=(selected_index is None),
    )
    return selected_index, actions


def render_heavy_suite_left_panel(
    st: Any,
    *,
    df_view: Any,
    row_ids: list[str],
    current_selected_id: str,
    selection_key: str,
    filtered: bool,
    total_count: int,
    on_enable_visible: Any,
    on_disable_visible: Any,
    on_duplicate_selected: Any,
    on_delete_selected: Any,
) -> str:
    render_heavy_suite_action_row(
        st,
        has_visible_rows=bool(row_ids),
        has_selected_row=bool(current_selected_id),
        on_enable_visible=on_enable_visible,
        on_disable_visible=on_disable_visible,
        on_duplicate_selected=on_duplicate_selected,
        on_delete_selected=on_delete_selected,
    )
    return render_heavy_suite_list_panel(
        st,
        df_view=df_view,
        row_ids=row_ids,
        current_selected_id=current_selected_id,
        selection_key=selection_key,
        filtered=filtered,
        total_count=total_count,
    )


def render_app_suite_action_row(
    st: Any,
    *,
    duplicate_disabled: bool,
    delete_disabled: bool,
) -> dict[str, bool]:
    btn_c1, btn_c2, btn_c3 = st.columns(3, gap="small")
    with btn_c1:
        add_clicked = bool(st.button("➕ Добавить", key="suite_add"))
    with btn_c2:
        duplicate_clicked = bool(
            st.button("📄 Дублировать", disabled=duplicate_disabled, key="suite_dup")
        )
    with btn_c3:
        delete_clicked = bool(
            st.button("🗑️ Удалить", disabled=delete_disabled, key="suite_del")
        )
    return {
        "add_clicked": add_clicked,
        "duplicate_clicked": duplicate_clicked,
        "delete_clicked": delete_clicked,
    }


def render_heavy_suite_action_row(
    st: Any,
    *,
    has_visible_rows: bool,
    has_selected_row: bool,
    on_enable_visible: Any,
    on_disable_visible: Any,
    on_duplicate_selected: Any,
    on_delete_selected: Any,
) -> None:
    a1, a2, a3, a4 = st.columns([1, 1, 1, 1], gap="small")
    with a1:
        st.button(
            "Включить все видимые",
            width="stretch",
            key="ui_suite_enable_visible_btn",
            on_click=on_enable_visible,
            args=(True,),
            disabled=not has_visible_rows,
        )
    with a2:
        st.button(
            "Выключить все видимые",
            width="stretch",
            key="ui_suite_disable_visible_btn",
            on_click=on_disable_visible,
            args=(False,),
            disabled=not has_visible_rows,
        )
    with a3:
        st.button(
            "Дублировать выбранный сценарий",
            width="stretch",
            key="ui_suite_duplicate_selected_btn",
            on_click=on_duplicate_selected,
            disabled=not has_selected_row,
        )
    with a4:
        st.button(
            "Удалить выбранный сценарий",
            width="stretch",
            key="ui_suite_delete_selected_btn",
            on_click=on_delete_selected,
            disabled=not has_selected_row,
        )


def render_suite_empty_list_state(st: Any, *, filtered: bool) -> None:
    if filtered:
        st.info("По текущим условиям отбора сценарии не найдены. Ослабьте фильтры или измените строку поиска.")
    else:
        st.info("Набор сценариев пока пуст. Добавьте первый сценарий, чтобы начать настройку.")


def render_suite_empty_card_state(st: Any) -> None:
    st.info("Выберите сценарий слева, чтобы открыть карточку редактирования.")


def render_suite_missing_card_state(st: Any) -> None:
    st.error("Выбранный сценарий не найден в текущем наборе. Проверьте фильтры или обновите выбор.")


def render_suite_card_heading(st: Any, title: str) -> None:
    st.markdown(f"### {title}")
    st.caption("Карточка выбранного сценария. Меняйте только то, что действительно нужно для текущего набора.")


def build_suite_option_label(
    *,
    enabled: bool,
    name: str,
    typ: str,
    stage: int | None = None,
) -> str:
    marker = "✓" if enabled else "○"
    name_text = name.strip() or "без названия"
    type_text = format_suite_test_type_label(typ)
    if stage is None:
        return f"{marker} {name_text} · {type_text}"
    return f"{marker} [S{stage}] {name_text} — {type_text}"


def build_suite_filter_summary(*, total_count: int, visible_count: int) -> str | None:
    hidden_count = max(0, int(total_count) - int(visible_count))
    if hidden_count <= 0:
        return None
    return (
        f"Показано **{visible_count}** из **{total_count}** сценариев. "
        f"Скрыто **{hidden_count}** — проверьте фильтр по стадиям, флаг включения и строку поиска."
    )
