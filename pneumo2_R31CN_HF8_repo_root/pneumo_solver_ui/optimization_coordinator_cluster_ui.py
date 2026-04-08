from __future__ import annotations

from typing import Any

from pneumo_solver_ui.optimization_defaults import (
    DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT,
    DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT,
)


def render_coordinator_cluster_controls(st: Any) -> None:
    with st.expander("Параллелизм и кластер (Dask / Ray)", expanded=True):
        st.markdown(
            "Здесь выбирается **бэкенд распределённых вычислений** и настройки локального/удалённого кластера.\n\n"
            "Ключевой принцип: **UI умеет создавать локальный кластер автоматически** — без ручных команд, "
            "достаточно выбрать *Локальный* режим и нажать *Запустить оптимизацию*."
        )

        backend = st.selectbox(
            "Бэкенд распределённых вычислений",
            options=["Dask", "Ray"],
            index=0 if str(st.session_state.get("opt_backend", "Dask")) == "Dask" else 1,
            key="opt_backend",
            help="Dask удобен для локального параллелизма и простых кластеров; Ray — для акторов и более сложных сценариев.",
        )

        if backend == "Dask":
            mode = st.radio(
                "Режим Dask",
                options=["Локальный кластер (создать автоматически)", "Подключиться к scheduler"],
                index=0 if not str(st.session_state.get("dask_mode", "")).startswith("Подключ") else 1,
                key="dask_mode",
                help=(
                    "Локальный кластер создаётся координатором автоматически через LocalCluster.\n"
                    "Если есть внешний scheduler — укажите адрес и подключитесь к нему."
                ),
            )

            if mode.startswith("Подключ"):
                st.text_input(
                    "Адрес scheduler (например: tcp://127.0.0.1:8786)",
                    value=str(st.session_state.get("dask_scheduler", "") or ""),
                    key="dask_scheduler",
                    help="Адрес планировщика Dask. Если пусто — будет создан локальный кластер.",
                )
            else:
                c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
                with c1:
                    st.number_input(
                        "Воркеры",
                        min_value=0,
                        max_value=256,
                        value=int(st.session_state.get("dask_workers", 0) or 0),
                        step=1,
                        key="dask_workers",
                        help="0 — автоматически (Dask выберет разумное значение).",
                    )
                with c2:
                    st.number_input(
                        "Потоки/воркер",
                        min_value=1,
                        max_value=128,
                        value=int(
                            st.session_state.get(
                                "dask_threads_per_worker",
                                DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT,
                            )
                            or DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT
                        ),
                        step=1,
                        key="dask_threads_per_worker",
                        help="Количество потоков на каждый процесс-воркер.",
                    )
                with c3:
                    st.text_input(
                        "Лимит памяти/воркер",
                        value=str(st.session_state.get("dask_memory_limit", "") or ""),
                        key="dask_memory_limit",
                        help="Например: 4GB. Пусто — по умолчанию (auto). '0'/'none' — без лимита.",
                    )
                with c4:
                    st.text_input(
                        "Dashboard address",
                        value=str(
                            st.session_state.get(
                                "dask_dashboard_address",
                                DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT,
                            )
                            or DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT
                        ),
                        key="dask_dashboard_address",
                        help="':0' — выбрать порт автоматически. Пусто — отключить dashboard.",
                    )

            st.caption(
                "Подсказка: LocalCluster поддерживает параметры n_workers / threads_per_worker / memory_limit / "
                "dashboard_address (dashboard_address=None отключает dashboard)."
            )

        else:
            mode = st.radio(
                "Режим Ray",
                options=["Локальный кластер (создать автоматически)", "Подключиться к кластеру"],
                index=0 if not str(st.session_state.get("ray_mode", "")).startswith("Подключ") else 1,
                key="ray_mode",
                help=(
                    "Локальный кластер создаётся автоматически через ray.init() в процессе координатора.\n"
                    "Если есть внешний кластер Ray — укажите адрес подключения."
                ),
            )

            if mode.startswith("Подключ"):
                st.text_input(
                    "Адрес Ray (например: 127.0.0.1:6379 или 'auto')",
                    value=str(st.session_state.get("ray_address", "auto") or "auto"),
                    key="ray_address",
                    help="Адрес кластера Ray. 'auto' — подключиться к запущенному, если возможно.",
                )
            else:
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    st.number_input(
                        "Ограничить CPU (0=авто)",
                        min_value=0,
                        max_value=4096,
                        value=int(st.session_state.get("ray_local_num_cpus", 0) or 0),
                        step=1,
                        key="ray_local_num_cpus",
                        help="Если задать >0 — Ray в локальном режиме будет считать, что доступно столько CPU.",
                    )
                with c2:
                    st.checkbox(
                        "Включить dashboard (локально)",
                        value=bool(st.session_state.get("ray_local_dashboard", False)),
                        key="ray_local_dashboard",
                        help="Попытка включить dashboard Ray в локальном режиме.",
                    )
                with c3:
                    st.number_input(
                        "Порт dashboard (0=авто)",
                        min_value=0,
                        max_value=65535,
                        value=int(st.session_state.get("ray_local_dashboard_port", 0) or 0),
                        step=1,
                        key="ray_local_dashboard_port",
                        help="Если 0 — Ray выберет порт автоматически.",
                    )


__all__ = [
    "render_coordinator_cluster_controls",
]
