from __future__ import annotations

from typing import Any

from pneumo_solver_ui.optimization_defaults import (
    DIST_OPT_BOTORCH_MAXITER_DEFAULT,
    DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT,
    DIST_OPT_BOTORCH_N_INIT_DEFAULT,
    DIST_OPT_BOTORCH_NORMALIZE_OBJECTIVES_DEFAULT,
    DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT,
    DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT,
    DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT,
)
from pneumo_solver_ui.optimization_distributed_wiring import (
    botorch_runtime_status,
    botorch_status_markdown,
)


def render_botorch_advanced_controls(
    st: Any,
    *,
    show_staged_caption: bool = False,
) -> None:
    with st.expander("BoTorch / qNEHVI advanced", expanded=False):
        if show_staged_caption:
            st.caption(
                "Этот блок относится к distributed coordinator. В StageRunner он не исчезает, но применяется только "
                "к запуску через Dask/Ray/BoTorch path."
            )
        botorch_status = botorch_runtime_status()
        if botorch_status.get("ready"):
            st.success(botorch_status_markdown(botorch_status))
        else:
            st.warning(
                botorch_status_markdown(botorch_status)
                + ". Для установки зависимостей см. `pneumo_solver_ui/requirements_mobo_botorch.txt`."
            )
        st.caption(
            "qNEHVI включается честно: coordinator сначала проходит warmup, затем проверяет feasible-point gate. "
            "Если done < n_init или feasible < min_feasible, proposer временно откатывается в random/LHS path."
        )

        c_b1, c_b2, c_b3 = st.columns([1, 1, 1])
        with c_b1:
            st.number_input(
                "n-init (warmup before qNEHVI)",
                min_value=0,
                max_value=100000,
                value=int(
                    st.session_state.get("opt_botorch_n_init", DIST_OPT_BOTORCH_N_INIT_DEFAULT)
                    or DIST_OPT_BOTORCH_N_INIT_DEFAULT
                ),
                step=1,
                key="opt_botorch_n_init",
                help="0 — auto threshold (~2×(dim+1), но не меньше 10). До этого qNEHVI не включается.",
            )
            st.number_input(
                "min-feasible",
                min_value=0,
                max_value=100000,
                value=int(
                    st.session_state.get("opt_botorch_min_feasible", DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT)
                    or DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT
                ),
                step=1,
                key="opt_botorch_min_feasible",
                help="Сколько feasible DONE trials нужно накопить перед включением qNEHVI. 0 — gate отключён.",
            )
            st.number_input(
                "num_restarts",
                min_value=1,
                max_value=4096,
                value=int(
                    st.session_state.get("opt_botorch_num_restarts", DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT)
                    or DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT
                ),
                step=1,
                key="opt_botorch_num_restarts",
                help="Число restarts для оптимизации acquisition-функции qNEHVI.",
            )

        with c_b2:
            st.number_input(
                "raw_samples",
                min_value=8,
                max_value=131072,
                value=int(
                    st.session_state.get("opt_botorch_raw_samples", DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT)
                    or DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT
                ),
                step=8,
                key="opt_botorch_raw_samples",
                help="Размер набора raw samples для оптимизации acquisition-функции qNEHVI.",
            )
            st.number_input(
                "maxiter",
                min_value=1,
                max_value=100000,
                value=int(
                    st.session_state.get("opt_botorch_maxiter", DIST_OPT_BOTORCH_MAXITER_DEFAULT)
                    or DIST_OPT_BOTORCH_MAXITER_DEFAULT
                ),
                step=1,
                key="opt_botorch_maxiter",
                help="Максимум итераций внутреннего оптимизатора acquisition-функции.",
            )
            st.number_input(
                "ref_margin",
                min_value=0.0,
                max_value=10.0,
                value=float(
                    st.session_state.get("opt_botorch_ref_margin", DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT)
                    or DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT
                ),
                step=0.01,
                format="%.3f",
                key="opt_botorch_ref_margin",
                help="Запас для reference point при построении qNEHVI / hypervolume geometry.",
            )

        with c_b3:
            st.checkbox(
                "Normalize objectives before GP fit",
                value=bool(
                    st.session_state.get(
                        "opt_botorch_normalize_objectives",
                        DIST_OPT_BOTORCH_NORMALIZE_OBJECTIVES_DEFAULT,
                    )
                ),
                key="opt_botorch_normalize_objectives",
                help="Обычно это стоит оставить включённым; отключать только для осознанной диагностики qNEHVI path.",
            )
            st.info(
                "Эти ручки действуют и для локального proposer path, и для Ray proposer actors. "
                "То есть UI и coordinator теперь реально говорят на одном контракте."
            )


__all__ = [
    "render_botorch_advanced_controls",
]
