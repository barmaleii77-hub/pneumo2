from __future__ import annotations

import json
from typing import Any, Callable

import pandas as pd

from pneumo_solver_ui.ui_suite_editor_panel_helpers import (
    render_app_suite_master_detail_panel,
    render_heavy_suite_master_detail_panel,
)
from pneumo_solver_ui.ui_suite_editor_shell_helpers import (
    build_suite_filter_summary,
    render_app_suite_editor_intro,
    render_heavy_suite_editor_intro,
    render_heavy_suite_filter_row,
    render_heavy_suite_preset_wizard,
    render_suite_hidden_summary,
)


HEAVY_STAGE_GUIDANCE_TEXT = (
    "Логика оптимизации по стадиям: S0 — быстрый предварительный отсев; "
    "S1 — длинные дорожные и манёвренные сценарии; "
    "S2 — финальная проверка устойчивости. "
    "Колонка «Стадия» показывает, с какого этапа сценарий впервые участвует в расчёте; "
    "значение 1 не должно молча превращаться в 0."
)


def _pick_existing_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        if name in frame.columns:
            return name
    return None


def render_app_suite_editor_section(
    st: Any,
    *,
    df_suite_edit: pd.DataFrame,
    expected_suite_cols: list[str],
    allowed_test_types: list[str],
    default_suite_path: Any,
    normalize_suite_df_for_editor_fn: Callable[..., pd.DataFrame],
    load_default_suite_disabled_fn: Callable[[Any], list[dict[str, Any]]],
    first_suite_selected_index_fn: Callable[[pd.DataFrame], int],
) -> pd.DataFrame:
    render_app_suite_editor_intro(st)

    with st.expander("Импорт, экспорт и восстановление набора", expanded=True):
        colIE1, colIE2, colIE3 = st.columns([1.2, 1.0, 1.0], gap="medium")

        with colIE1:
            suite_upload = st.file_uploader(
                "Импорт набора сценариев (JSON)",
                type=["json"],
                help="Загрузите ранее сохранённый файл `suite.json` с набором сценариев.",
                key="suite_upload_json",
            )
            if suite_upload is not None:
                try:
                    suite_loaded = json.loads(suite_upload.getvalue().decode("utf-8"))
                    if isinstance(suite_loaded, list):
                        loaded_df = normalize_suite_df_for_editor_fn(
                            pd.DataFrame(suite_loaded),
                            context="app.suite_upload",
                        )
                        st.session_state["df_suite_edit"] = loaded_df
                        st.session_state["suite_sel"] = first_suite_selected_index_fn(loaded_df)
                        st.success("Набор сценариев загружен.")
                        st.rerun()
                    else:
                        st.error("JSON должен содержать список сценариев.")
                except Exception as exc:
                    st.error(f"Не удалось прочитать JSON: {exc}")

        with colIE2:
            if st.button("Вернуть набор по умолчанию", key="suite_reset_default"):
                default_df = normalize_suite_df_for_editor_fn(
                    pd.DataFrame(load_default_suite_disabled_fn(default_suite_path)),
                    context="app.suite_reset_default",
                )
                st.session_state["df_suite_edit"] = default_df
                st.session_state["suite_sel"] = first_suite_selected_index_fn(default_df)
                st.rerun()

        with colIE3:
            try:
                df_tmp = st.session_state["df_suite_edit"].copy()
                suite_out: list[dict[str, Any]] = []
                for _, row in df_tmp.iterrows():
                    rec: dict[str, Any] = {}
                    for key, value in row.to_dict().items():
                        if isinstance(value, float) and pd.isna(value):
                            continue
                        if value is None:
                            continue
                        rec[key] = value
                    if rec:
                        suite_out.append(rec)
                suite_json = json.dumps(suite_out, ensure_ascii=False, indent=2)
            except Exception:
                suite_json = "[]"
            st.download_button(
                "Скачать suite.json",
                data=suite_json,
                file_name="suite_export.json",
                mime="application/json",
                key="suite_download_json",
            )

    df_suite_edit = st.session_state.get("df_suite_edit", df_suite_edit).copy()
    render_app_suite_master_detail_panel(
        st,
        df_suite_edit=df_suite_edit,
        expected_suite_cols=expected_suite_cols,
        allowed_test_types=allowed_test_types,
        first_suite_selected_index_fn=first_suite_selected_index_fn,
    )
    return st.session_state.get("df_suite_edit", df_suite_edit)


def render_heavy_suite_editor_section(
    st: Any,
    *,
    df_suite_edit: pd.DataFrame,
    diagnostic_suite_preset: str,
    allowed_test_types: list[str],
    suite_editor_widget_key_fn: Callable[[str], str],
    seed_suite_editor_state_fn: Callable[[dict[str, Any]], None],
    infer_suite_stage_fn: Callable[[dict[str, Any]], int],
    save_upload_fn: Callable[[Any, str], str],
    queue_suite_selected_id_fn: Callable[[str], None],
    ensure_stage_visible_in_filter_fn: Callable[[int], None],
    set_flash_fn: Callable[[str, str], None],
    ensure_suite_columns_fn: Callable[[pd.DataFrame], pd.DataFrame],
    on_enable_visible: Callable[[], None],
    on_disable_visible: Callable[[], None],
    on_duplicate_selected: Callable[[], None],
    on_delete_selected: Callable[[], None],
    maybe_autosave_pending_fn: Callable[[], None],
    render_flash_fn: Callable[[], None],
    on_add_preset: Callable[[str], None],
    suite_filtered_view_fn: Callable[[pd.DataFrame, list[int], bool, str], pd.DataFrame],
    normalize_suite_id_value_fn: Callable[[Any], str],
    sync_multiselect_all_fn: Callable[[str, list[int], Callable[[Any], int]], None],
    reset_filters_callback: Callable[[list[int]], None],
    show_all_callback: Callable[[list[int]], None],
    render_ring_editor_fn: Callable[[pd.DataFrame], pd.DataFrame],
) -> pd.DataFrame:
    render_heavy_suite_editor_intro(st)
    maybe_autosave_pending_fn()
    render_flash_fn()
    st.session_state.pop("ui_suite_selected_row", None)

    render_heavy_suite_preset_wizard(
        st,
        preset_options=["worldroad_flat", "worldroad_sine_x", "worldroad_bump", "inertia_brake"],
        preset_key="ui_suite_preset",
        default_preset=diagnostic_suite_preset,
        add_button_key="ui_suite_add_preset_btn",
        on_add_preset=on_add_preset,
    )

    df_suite_edit = render_ring_editor_fn(df_suite_edit)

    stages = (
        sorted({int(infer_suite_stage_fn(row.to_dict())) for _, row in df_suite_edit.iterrows()})
        if not df_suite_edit.empty
        else [0]
    )
    if not stages:
        stages = [0]

    for stage_key in ("ui_suite_stage_filter", "ui_suite_stage_filter__options_prev", "ui_suite_stage_all_prev"):
        try:
            raw_stage_vals = list(st.session_state.get(stage_key) or [])
            norm_stage_vals = sorted({max(0, int(x)) for x in raw_stage_vals})
            if norm_stage_vals:
                st.session_state[stage_key] = norm_stage_vals
            elif stage_key == "ui_suite_stage_filter":
                st.session_state[stage_key] = stages.copy()
        except Exception:
            pass

    if st.session_state.pop("_ui_suite_filters_reset_pending", False) or st.session_state.pop(
        "_ui_suite_show_all_pending", False
    ):
        st.session_state["ui_suite_stage_filter"] = stages.copy()
        st.session_state["ui_suite_only_enabled"] = False
        st.session_state["ui_suite_search"] = ""

    pending_stage_extend = st.session_state.pop("_ui_suite_stage_filter_extend_pending", None)
    if pending_stage_extend is not None:
        try:
            pending_vals = [int(x) for x in list(pending_stage_extend)]
        except Exception:
            pending_vals = []
        try:
            current_stage_filter = [int(x) for x in list(st.session_state.get("ui_suite_stage_filter") or [])]
        except Exception:
            current_stage_filter = []
        merged_stage_filter = [x for x in current_stage_filter if x in stages]
        for stage_value in pending_vals:
            if stage_value in stages and stage_value not in merged_stage_filter:
                merged_stage_filter.append(stage_value)
        st.session_state["ui_suite_stage_filter"] = sorted(
            set(int(x) for x in (merged_stage_filter or stages.copy()))
        )

    sync_multiselect_all_fn("ui_suite_stage_filter", stages, cast=int)
    stage_filter, only_enabled, suite_search = render_heavy_suite_filter_row(
        st,
        stages=list(stages),
        default_stages=list(stages),
        stage_filter_key="ui_suite_stage_filter",
        only_enabled_key="ui_suite_only_enabled",
        search_key="ui_suite_search",
        on_reset_filters=reset_filters_callback,
        reset_args=(list(stages),),
    )

    st.caption(HEAVY_STAGE_GUIDANCE_TEXT)

    df_view = suite_filtered_view_fn(df_suite_edit, stage_filter, False, "")
    enabled_col = _pick_existing_column(df_view, ("включен", "РІРєР»СЋС‡РµРЅ"))
    if only_enabled and enabled_col:
        df_view = df_view[df_view[enabled_col].astype(bool)]
    if suite_search:
        search_cols = [
            col
            for col in (
                _pick_existing_column(df_view, ("имя", "РёРјСЏ")),
                _pick_existing_column(df_view, ("тип", "С‚РёРї")),
            )
            if col
        ]
        if search_cols:
            mask = pd.Series(False, index=df_view.index)
            for col in search_cols:
                mask = mask | df_view[col].astype(str).str.contains(suite_search, case=False, na=False)
            df_view = df_view[mask]

    total_count = int(len(df_suite_edit))
    visible_count = int(len(df_view))
    summary_text = build_suite_filter_summary(total_count=total_count, visible_count=visible_count)
    render_suite_hidden_summary(
        st,
        summary_text=summary_text,
        show_all_button_key="ui_suite_show_all_btn",
        on_show_all=show_all_callback,
        show_all_args=(list(stages),),
    )

    row_ids = df_view["id"].astype(str).tolist() if "id" in df_view.columns else []
    row_ids = [normalize_suite_id_value_fn(x) for x in row_ids]
    row_ids = [x for x in row_ids if x]
    pending_sel = normalize_suite_id_value_fn(st.session_state.pop("_ui_suite_selected_id_pending", ""))
    current_sel = normalize_suite_id_value_fn(st.session_state.get("ui_suite_selected_id"))
    if row_ids:
        if pending_sel and pending_sel in set(row_ids):
            current_sel = pending_sel
            st.session_state["ui_suite_selected_id"] = current_sel
        elif current_sel not in set(row_ids):
            current_sel = str(row_ids[0])
            st.session_state["ui_suite_selected_id"] = current_sel
    else:
        st.session_state.pop("ui_suite_selected_id", None)
        current_sel = ""

    filtered = bool(only_enabled or suite_search or sorted(stage_filter) != sorted(stages))
    render_heavy_suite_master_detail_panel(
        st,
        df_suite_edit=df_suite_edit,
        df_view=df_view,
        row_ids=row_ids,
        current_selected_id=current_sel,
        filtered=filtered,
        total_count=len(df_suite_edit),
        allowed_test_types=allowed_test_types,
        suite_editor_widget_key_fn=suite_editor_widget_key_fn,
        seed_suite_editor_state_fn=seed_suite_editor_state_fn,
        infer_suite_stage_fn=infer_suite_stage_fn,
        save_upload_fn=save_upload_fn,
        queue_suite_selected_id_fn=queue_suite_selected_id_fn,
        ensure_stage_visible_in_filter_fn=ensure_stage_visible_in_filter_fn,
        set_flash_fn=set_flash_fn,
        ensure_suite_columns_fn=ensure_suite_columns_fn,
        on_enable_visible=on_enable_visible,
        on_disable_visible=on_disable_visible,
        on_duplicate_selected=on_duplicate_selected,
        on_delete_selected=on_delete_selected,
    )

    st.session_state["df_suite_edit"] = df_suite_edit
    return df_suite_edit
