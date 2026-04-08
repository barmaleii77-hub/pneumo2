from __future__ import annotations

from typing import Any

from pneumo_solver_ui.optimization_defaults import (
    DIST_OPT_DB_ENGINE_DEFAULT,
    DIST_OPT_EXPORT_EVERY_DEFAULT,
    DIST_OPT_HV_LOG_DEFAULT,
    DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT,
    DIST_OPT_STALE_TTL_SEC_DEFAULT,
)
from pneumo_solver_ui.optimization_distributed_wiring import (
    RAY_RUNTIME_ENV_MODES,
    migrated_ray_runtime_env_json,
    migrated_ray_runtime_env_mode,
)


def render_coordinator_persistence_controls(st: Any) -> None:
    with st.expander("Coordinator advanced / persistence", expanded=False):
        st.markdown(
            "Ниже — **реально подключённые** ручки координатора. Они используют тот же session_state, что и основной UI, "
            "и попадают в `dist_opt_coordinator.py` без фейковых CLI-полей."
        )

        c_adv1, c_adv2 = st.columns([1, 1])
        with c_adv1:
            runtime_env_modes = list(RAY_RUNTIME_ENV_MODES)
            runtime_env_value = migrated_ray_runtime_env_mode(st.session_state)
            runtime_env_index = (
                runtime_env_modes.index(runtime_env_value)
                if runtime_env_value in runtime_env_modes
                else runtime_env_modes.index(DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT)
            )
            st.selectbox(
                "Ray runtime_env mode",
                options=runtime_env_modes,
                index=runtime_env_index,
                key="ray_runtime_env_mode",
                help=(
                    "auto — включать runtime_env только для внешнего Ray-кластера; "
                    "on — принудительно упаковывать working_dir в runtime_env; "
                    "off — не использовать runtime_env."
                ),
            )
            st.text_area(
                "Ray runtime_env JSON merge (optional)",
                value=migrated_ray_runtime_env_json(st.session_state),
                height=120,
                key="ray_runtime_env_json",
                help=(
                    "Опциональный JSON-объект, который будет слит с базовым runtime_env координатора. "
                    "Полезно для env_vars / pip / excludes на кластере."
                ),
            )
            st.text_area(
                "Ray runtime exclude (по одному паттерну в строке)",
                value=str(st.session_state.get("ray_runtime_exclude", "") or ""),
                height=90,
                key="ray_runtime_exclude",
                help="Исключения при упаковке working_dir в Ray runtime_env.",
            )
            st.number_input(
                "Ray evaluators",
                min_value=0,
                max_value=4096,
                value=int(st.session_state.get("ray_num_evaluators", 0) or 0),
                step=1,
                key="ray_num_evaluators",
                help="0 — координатор сам выберет количество evaluator actors.",
            )
            st.number_input(
                "CPU на evaluator",
                min_value=0.25,
                max_value=512.0,
                value=float(st.session_state.get("ray_cpus_per_evaluator", 1.0) or 1.0),
                step=0.25,
                format="%.2f",
                key="ray_cpus_per_evaluator",
                help="Сколько CPU резервировать на один evaluator actor Ray.",
            )
            st.number_input(
                "Ray proposers",
                min_value=0,
                max_value=512,
                value=int(st.session_state.get("ray_num_proposers", 0) or 0),
                step=1,
                key="ray_num_proposers",
                help="0 — auto (попробовать использовать доступные GPU для proposer actors).",
            )
            st.number_input(
                "GPU на proposer",
                min_value=0.0,
                max_value=16.0,
                value=float(st.session_state.get("ray_gpus_per_proposer", 1.0) or 1.0),
                step=0.25,
                format="%.2f",
                key="ray_gpus_per_proposer",
                help="Сколько GPU резервировать на один proposer actor Ray.",
            )

        with c_adv2:
            st.number_input(
                "Буфер кандидатов proposer_buffer",
                min_value=1,
                max_value=8192,
                value=int(st.session_state.get("proposer_buffer", 128) or 128),
                step=1,
                key="proposer_buffer",
                help="Сколько готовых кандидатов держать в буфере координатора.",
            )
            st.text_input(
                "ExperimentDB path / DSN",
                value=str(st.session_state.get("opt_db_path", "") or ""),
                key="opt_db_path",
                help="Путь к sqlite/duckdb файлу или Postgres DSN для ExperimentDB.",
            )
            db_engine_options = ["sqlite", "duckdb", "postgres"]
            db_engine_value = str(
                st.session_state.get("opt_db_engine", DIST_OPT_DB_ENGINE_DEFAULT)
                or DIST_OPT_DB_ENGINE_DEFAULT
            ).strip().lower()
            db_engine_index = (
                db_engine_options.index(db_engine_value)
                if db_engine_value in db_engine_options
                else db_engine_options.index(DIST_OPT_DB_ENGINE_DEFAULT)
            )
            st.selectbox(
                "DB engine",
                options=db_engine_options,
                index=db_engine_index,
                key="opt_db_engine",
                help="Координатор умеет работать с sqlite, duckdb и postgres backends.",
            )
            st.checkbox(
                "Resume from existing run",
                value=bool(st.session_state.get("opt_resume", False)),
                key="opt_resume",
                help="Повторно открыть последний/указанный run_id для той же задачи и доработать его.",
            )
            st.text_input(
                "Explicit run_id (optional)",
                value=str(st.session_state.get("opt_dist_run_id", "") or ""),
                key="opt_dist_run_id",
                help="Если заполнено вместе с Resume — координатор будет пытаться продолжить именно этот run_id.",
            )
            st.number_input(
                "stale-ttl-sec",
                min_value=0,
                max_value=604800,
                value=int(
                    st.session_state.get("opt_stale_ttl_sec", DIST_OPT_STALE_TTL_SEC_DEFAULT)
                    or DIST_OPT_STALE_TTL_SEC_DEFAULT
                ),
                step=60,
                key="opt_stale_ttl_sec",
                help="Через сколько секунд RUNNING trial можно считать stale и requeue при resume.",
            )
            st.checkbox(
                "Писать hypervolume log",
                value=bool(st.session_state.get("opt_hv_log", DIST_OPT_HV_LOG_DEFAULT)),
                key="opt_hv_log",
                help="Если включено — координатор пишет progress_hv.csv по feasible Pareto-front.",
            )
            st.number_input(
                "export-every",
                min_value=1,
                max_value=100000,
                value=int(
                    st.session_state.get("opt_export_every", DIST_OPT_EXPORT_EVERY_DEFAULT)
                    or DIST_OPT_EXPORT_EVERY_DEFAULT
                ),
                step=1,
                key="opt_export_every",
                help="Как часто (по DONE trials) обновлять CSV export из ExperimentDB.",
            )


__all__ = [
    "render_coordinator_persistence_controls",
]
