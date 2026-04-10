from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from pneumo_solver_ui.ui_suite_card_panel_helpers import (
    render_app_suite_right_card_panel,
    render_heavy_suite_right_card_panel,
)
from pneumo_solver_ui.ui_suite_editor_shell_helpers import (
    render_app_suite_left_panel,
    render_app_suite_search_box,
    render_heavy_suite_left_panel,
)


FirstSelectedIndexFn = Callable[[pd.DataFrame], int | None]
WidgetKeyFn = Callable[[str, str], str]
SeedStateFn = Callable[[str, dict[str, Any]], None]
InferStageFn = Callable[[dict[str, Any]], int]
SaveUploadFn = Callable[[Any, str], str | None]
QueueSelectedIdFn = Callable[[str], None]
EnsureStageVisibleFn = Callable[[int], None]
SetFlashFn = Callable[[str, str], None]
EnsureSuiteColumnsFn = Callable[[pd.DataFrame], pd.DataFrame]
VisibleActionFn = Callable[[bool], None]
SelectedActionFn = Callable[[], None]


def render_app_suite_master_detail_panel(
    st: Any,
    *,
    df_suite_edit: pd.DataFrame,
    expected_suite_cols: list[str],
    allowed_test_types: list[str],
    first_suite_selected_index_fn: FirstSelectedIndexFn,
) -> None:
    left, right = st.columns([1.0, 1.2], gap="large")

    with left:
        render_app_suite_search_box(
            st,
            key="suite_search",
            placeholder="например: крен, микро, кочка...",
        )
        sel_i, app_suite_actions = render_app_suite_left_panel(
            st,
            df_suite_edit=df_suite_edit,
            search_key="suite_search",
            search_placeholder="например: крен, микро, кочка...",
            selection_key="suite_sel",
        )
        if app_suite_actions["add_clicked"]:
            new_row = {column: np.nan for column in expected_suite_cols}
            new_row["включен"] = True
            new_row["имя"] = f"new_test_{len(df_suite_edit)+1}"
            new_row["тип"] = allowed_test_types[0] if allowed_test_types else "инерция_крен"
            new_row["dt"] = 0.01
            new_row["t_end"] = 3.0
            df_suite_edit = pd.concat([df_suite_edit, pd.DataFrame([new_row])], ignore_index=True)
            st.session_state["df_suite_edit"] = df_suite_edit
            st.session_state["suite_sel"] = int(len(df_suite_edit) - 1)
            st.rerun()

        if app_suite_actions["duplicate_clicked"] and sel_i is not None:
            row = df_suite_edit.loc[sel_i].to_dict()
            row["имя"] = str(row.get("имя") or "copy") + "_copy"
            df_suite_edit = pd.concat([df_suite_edit, pd.DataFrame([row])], ignore_index=True)
            st.session_state["df_suite_edit"] = df_suite_edit
            st.session_state["suite_sel"] = int(len(df_suite_edit) - 1)
            st.rerun()

        if app_suite_actions["delete_clicked"] and sel_i is not None and len(df_suite_edit) > 0:
            df_suite_edit = df_suite_edit.drop(index=sel_i).reset_index(drop=True)
            st.session_state["df_suite_edit"] = df_suite_edit
            st.session_state["suite_sel"] = first_suite_selected_index_fn(df_suite_edit)
            st.rerun()

    with right:
        render_app_suite_right_card_panel(
            st,
            df_suite_edit=df_suite_edit,
            sel_i=sel_i,
            allowed_test_types=allowed_test_types,
            expected_suite_cols=expected_suite_cols,
        )


def render_heavy_suite_master_detail_panel(
    st: Any,
    *,
    df_suite_edit: pd.DataFrame,
    df_view: pd.DataFrame,
    row_ids: list[str],
    current_selected_id: str,
    filtered: bool,
    total_count: int,
    allowed_test_types: list[str],
    suite_editor_widget_key_fn: WidgetKeyFn,
    seed_suite_editor_state_fn: SeedStateFn,
    infer_suite_stage_fn: InferStageFn,
    save_upload_fn: SaveUploadFn,
    queue_suite_selected_id_fn: QueueSelectedIdFn,
    ensure_stage_visible_in_filter_fn: EnsureStageVisibleFn,
    set_flash_fn: SetFlashFn,
    ensure_suite_columns_fn: EnsureSuiteColumnsFn,
    on_enable_visible: VisibleActionFn,
    on_disable_visible: VisibleActionFn,
    on_duplicate_selected: SelectedActionFn,
    on_delete_selected: SelectedActionFn,
) -> None:
    left, right = st.columns([1.05, 1.0], gap="large")

    with left:
        render_heavy_suite_left_panel(
            st,
            df_view=df_view,
            row_ids=row_ids,
            current_selected_id=current_selected_id,
            selection_key="ui_suite_selected_id",
            filtered=filtered,
            total_count=total_count,
            on_enable_visible=on_enable_visible,
            on_disable_visible=on_disable_visible,
            on_duplicate_selected=on_duplicate_selected,
            on_delete_selected=on_delete_selected,
        )

    with right:
        render_heavy_suite_right_card_panel(
            st,
            df_suite_edit=df_suite_edit,
            row_ids=row_ids,
            allowed_test_types=allowed_test_types,
            suite_editor_widget_key_fn=suite_editor_widget_key_fn,
            seed_suite_editor_state_fn=seed_suite_editor_state_fn,
            infer_suite_stage_fn=infer_suite_stage_fn,
            save_upload_fn=save_upload_fn,
            queue_suite_selected_id_fn=queue_suite_selected_id_fn,
            ensure_stage_visible_in_filter_fn=ensure_stage_visible_in_filter_fn,
            set_flash_fn=set_flash_fn,
            ensure_suite_columns_fn=ensure_suite_columns_fn,
        )
