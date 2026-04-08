from __future__ import annotations

from typing import Any


def render_optimization_launch_mode_block(
    st: Any,
    *,
    expander_label: str,
    mode_stage_label: str,
    mode_coord_label: str,
    current_use_staged: bool,
    radio_label: str,
    radio_help: str,
    single_path_message: str,
    staged_message: str,
    coordinator_message: str,
) -> bool:
    with st.expander(expander_label, expanded=True):
        launch_mode_options = [mode_stage_label, mode_coord_label]
        launch_mode_default = mode_stage_label if bool(current_use_staged) else mode_coord_label
        launch_mode_index = launch_mode_options.index(launch_mode_default)
        launch_mode = st.radio(
            radio_label,
            options=launch_mode_options,
            index=launch_mode_index,
            horizontal=False,
            help=radio_help,
        )
        opt_use_staged = launch_mode == mode_stage_label
        st.info(single_path_message)
        if opt_use_staged:
            st.success(staged_message)
        else:
            st.info(coordinator_message)
        return bool(opt_use_staged)


__all__ = [
    "render_optimization_launch_mode_block",
]
