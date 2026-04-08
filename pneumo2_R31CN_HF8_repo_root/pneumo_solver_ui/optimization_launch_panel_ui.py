from __future__ import annotations

from typing import Any


def render_optimization_launch_panel(
    st: Any,
    *,
    launch_button_label: str,
    launch_intro_markdown: str,
    workflow_caption: str,
    cmd_preview_text: str,
    is_staged: bool,
    command_filename: str = "dist_opt_command.txt",
    command_help: str = "На случай, если нужно повторить запуск из консоли.",
) -> bool:
    st.subheader("Новый запуск")
    st.markdown(launch_intro_markdown)
    st.caption(workflow_caption)

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        launch_clicked = bool(st.button(launch_button_label, type="primary"))
    with c2:
        st.download_button(
            "Скачать шаблон команды",
            data=cmd_preview_text,
            file_name=command_filename,
            help=command_help,
        )
    with c3:
        if is_staged:
            st.caption(
                "Техническая заметка: StageRunner запускается через console `python.exe`, пишет короткие "
                "runtime paths в workspace/opt_runs и сохраняет `sp.json` + stage artifacts для live UI."
            )
        else:
            st.caption(
                "Техническая заметка: coordinator создаёт локальный кластер автоматически "
                "(если выбран локальный режим) — Dask через LocalCluster, Ray через ray.init()."
            )
    return launch_clicked


__all__ = [
    "render_optimization_launch_panel",
]
