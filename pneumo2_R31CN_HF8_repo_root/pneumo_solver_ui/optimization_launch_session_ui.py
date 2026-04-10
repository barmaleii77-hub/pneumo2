from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pneumo_solver_ui.optimization_finished_job_ui import (
    render_finished_optimization_job_panel,
)
from pneumo_solver_ui.optimization_launch_panel_ui import (
    render_optimization_launch_panel,
)
from pneumo_solver_ui.optimization_live_job_panel_ui import (
    render_live_optimization_job_panel,
)


def render_optimization_launch_session_block(
    st: Any,
    *,
    job: Any,
    is_staged: bool,
    tail_file_text_fn: Callable[[Path], str],
    soft_stop_requested_fn: Callable[[Any], bool],
    parse_done_from_log_fn: Callable[[str], int | None],
    render_stage_runtime_fn: Callable[[Any], None] | None,
    write_soft_stop_file_fn: Callable[[Any], bool],
    terminate_process_fn: Callable[[Any], None],
    rerun_fn: Callable[[Any], None],
    sleep_fn: Callable[[float], None],
    clear_job_fn: Callable[[], None],
    launch_job_fn: Callable[[], None],
    build_cmd_preview_text_fn: Callable[[], str],
    current_problem_hash: str = "",
    current_problem_hash_mode: str = "",
    render_live_panel_fn: Callable[..., Any] = render_live_optimization_job_panel,
    render_finished_panel_fn: Callable[..., Any] = render_finished_optimization_job_panel,
    render_launch_panel_fn: Callable[..., bool] = render_optimization_launch_panel,
) -> None:
    with st.expander("Запуск оптимизации", expanded=True):
        if is_staged:
            st.markdown(
                "Будет запущен **opt_stage_runner_v1.py**. Он ведёт staged run, пишет `sp.json`, stage CSV и "
                "live seed/promotion artifacts. Во время выполнения UI показывает хвост лога, live stage rows и "
                "текущую stage policy."
            )
        else:
            st.markdown(
                "Будет запущен **tools/dist_opt_coordinator.py**. Это distributed coordinator path для Dask/Ray/BoTorch. "
                "Во время выполнения UI показывает хвост лога и done-progress."
            )

        job_rc = None if job is None else getattr(getattr(job, "proc", None), "poll", lambda: None)()

        if job is not None and job_rc is None:
            log_text = tail_file_text_fn(getattr(job, "log_path"))
            render_live_panel_fn(
                st,
                job,
                log_text=log_text,
                soft_stop_requested=soft_stop_requested_fn(job),
                coordinator_done=parse_done_from_log_fn(log_text),
                render_stage_runtime=(
                    (lambda: render_stage_runtime_fn(job))
                    if render_stage_runtime_fn is not None
                    else None
                ),
                write_soft_stop_file_fn=write_soft_stop_file_fn,
                terminate_process_fn=terminate_process_fn,
                rerun_fn=rerun_fn,
                sleep_fn=sleep_fn,
                running_message=(
                    f"Оптимизация выполняется… (PID={job.proc.pid}, pipeline={job.pipeline_mode}, "
                    f"backend={job.backend}, run_dir={job.run_dir.name})"
                ),
                soft_stop_active_message=(
                    "Запрошена мягкая остановка через STOP_OPTIMIZATION.txt. "
                    "StageRunner должен корректно завершить текущий шаг и сохранить CSV/progress."
                ),
                soft_stop_label="Стоп (мягко)",
                soft_stop_help="Создаёт STOP-файл. StageRunner сам корректно завершится и сохранит CSV/прогресс.",
                soft_stop_success_message="Запрошена мягкая остановка. Лог обновится через пару секунд.",
                soft_stop_error_message="Не удалось записать STOP-файл.",
                hard_stop_label="Стоп (жёстко)",
                hard_stop_help="Создаёт STOP-файл и принудительно завершает процесс. Используйте только если мягкая остановка не срабатывает.",
                hard_stop_warning_message="Отправлен жёсткий сигнал остановки. Лог обновится через пару секунд.",
                hard_stop_with_stopfile_warning="STOP-файл записать не удалось; продолжаю жёсткую остановку процесса.",
                hard_only_label="Остановить (жёстко)",
                hard_only_help="Попытаться остановить текущую оптимизацию",
                hard_only_error_prefix="Не удалось остановить",
                refresh_label="Обновить",
                refresh_help="Перечитать лог",
                auto_refresh_label="Авто-обновлять страницу (каждые ~2 секунды)",
                auto_refresh_help="Если включено — UI будет сам обновляться, пока оптимизация активна.",
                auto_refresh_default=bool(st.session_state.get("__opt_autorefresh_enabled", True)),
                current_problem_hash=current_problem_hash,
                current_problem_hash_mode=current_problem_hash_mode,
            )

        elif job is not None and job_rc is not None:
            render_finished_panel_fn(
                st,
                job,
                rc=int(job_rc),
                soft_stop_requested=soft_stop_requested_fn(job),
                clear_job_fn=clear_job_fn,
                rerun_fn=rerun_fn,
            )

        if job is None or job_rc is not None:
            launch_button_label = (
                "Запустить StageRunner" if is_staged else "Запустить distributed coordinator"
            )
            launch_clicked = render_launch_panel_fn(
                st,
                launch_button_label=launch_button_label,
                launch_intro_markdown=(
                    "**Что нажимать:** выберите режим выше, настройте только видимые для него блоки и затем нажмите "
                    f"**{launch_button_label}**. Другой путь запуска сейчас не активен."
                ),
                workflow_caption=(
                    "Нормальный инженерный сценарий: сначала StageRunner как быстрый physical gate, затем distributed "
                    "coordinator как длинный trade study. Эти run dirs не считаются параллельными и сохраняются отдельно "
                    "в журнале последовательных запусков выше."
                ),
                cmd_preview_text=build_cmd_preview_text_fn(),
                is_staged=bool(is_staged),
            )
            if launch_clicked:
                launch_job_fn()


__all__ = [
    "render_optimization_launch_session_block",
]
