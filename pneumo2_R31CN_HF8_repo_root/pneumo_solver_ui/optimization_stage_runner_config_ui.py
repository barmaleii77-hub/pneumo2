from __future__ import annotations

from typing import Any

from pneumo_solver_ui.optimization_defaults import (
    DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS,
    DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID,
    DIAGNOSTIC_INFLUENCE_EPS_REL,
    DIAGNOSTIC_OPT_MINUTES_DEFAULT,
    DIAGNOSTIC_SEED_CANDIDATES,
    DIAGNOSTIC_SEED_CONDITIONS,
    DIAGNOSTIC_SORT_TESTS_BY_COST,
    DIAGNOSTIC_SURROGATE_SAMPLES,
    DIAGNOSTIC_SURROGATE_TOP_K,
    DIAGNOSTIC_WARMSTART_MODE,
    influence_eps_grid_text,
    stage_aware_influence_profiles_text,
)
from pneumo_solver_ui.optimization_stage_policy import (
    DEFAULT_STAGE_POLICY_MODE,
    stage_seed_policy_summary_text,
)

STAGE_RUNNER_CONTRACT_LABEL = "StageRunner: warm-start, influence и staged seed/promotion"


def render_stage_runner_configuration_controls(
    st: Any,
    *,
    ui_jobs_default: int,
) -> None:
    with st.expander("StageRunner: warm-start, influence и стадийный отбор", expanded=True):
        st.markdown(
            "Этот блок управляет **стадийным pipeline**: длительность запуска, seeds, warm-start, early-stop и "
            "influence-aware политикой отбора и продвижения. Именно эти ручки определяют поведение `opt_stage_runner_v1.py`."
        )

        c_s0, c_s1, c_s2, c_s3 = st.columns([1, 1, 1, 1])
        with c_s0:
            st.number_input(
                "Минуты на staged run",
                min_value=0.1,
                max_value=1440.0,
                value=float(
                    st.session_state.get("ui_opt_minutes", DIAGNOSTIC_OPT_MINUTES_DEFAULT)
                    or DIAGNOSTIC_OPT_MINUTES_DEFAULT
                ),
                step=1.0,
                key="ui_opt_minutes",
                help="Общий wall-clock budget для StageRunner. Внутри него он сам распределяет время между стадиями.",
            )
        with c_s1:
            st.number_input(
                "Jobs (локальный parallel worker pool)",
                min_value=1,
                max_value=512,
                value=int(st.session_state.get("ui_jobs", ui_jobs_default) or ui_jobs_default),
                step=1,
                key="ui_jobs",
                help="Число локальных worker jobs для opt_worker_v3_margins_energy.py внутри StageRunner.",
            )
        with c_s2:
            st.checkbox(
                "Авто-обновлять baseline_best.json",
                value=bool(st.session_state.get("opt_autoupdate_baseline", True)),
                key="opt_autoupdate_baseline",
                help="Если найден кандидат лучше текущего baseline — StageRunner запишет его в workspace/baselines/baseline_best.json.",
            )
        with c_s3:
            stage_resume_enabled = st.checkbox(
                "Resume staged run",
                value=bool(st.session_state.get("opt_stage_resume", False)),
                key="opt_stage_resume",
                help=(
                    "Продолжает staged run в совместимую папку: сначала берёт выбранный staged run из истории, "
                    "иначе подхватывает последний совместимый run в workspace."
                ),
            )
        if stage_resume_enabled:
            st.caption(
                "Resume mode: StageRunner продолжит выбранный staged run из истории или последний совместимый run_dir в workspace."
            )

        c_s4, c_s5, c_s6, c_s7 = st.columns([1, 1, 1, 1])
        with c_s4:
            st.number_input(
                "Seed кандидатов",
                min_value=0,
                max_value=2_147_483_647,
                value=int(
                    st.session_state.get("ui_seed_candidates", DIAGNOSTIC_SEED_CANDIDATES)
                    or DIAGNOSTIC_SEED_CANDIDATES
                ),
                step=1,
                key="ui_seed_candidates",
                help="Влияет только на генерацию набора кандидатов в staged optimizer.",
            )
        with c_s5:
            st.number_input(
                "Seed условий",
                min_value=0,
                max_value=2_147_483_647,
                value=int(
                    st.session_state.get("ui_seed_conditions", DIAGNOSTIC_SEED_CONDITIONS)
                    or DIAGNOSTIC_SEED_CONDITIONS
                ),
                step=1,
                key="ui_seed_conditions",
                help="Влияет на стохастические условия в staged tests (если они включены).",
            )
        with c_s6:
            st.number_input(
                "flush_every",
                min_value=1,
                max_value=200,
                value=int(st.session_state.get("ui_flush_every", 20) or 20),
                step=1,
                key="ui_flush_every",
                help="Как часто StageRunner сбрасывает строки результатов в CSV на диск.",
            )
        with c_s7:
            st.number_input(
                "progress_every_sec",
                min_value=0.2,
                max_value=10.0,
                value=float(st.session_state.get("ui_progress_every_sec", 1.0) or 1.0),
                step=0.2,
                key="ui_progress_every_sec",
                help="Как часто StageRunner пишет progress.json.",
            )

        c_s7, c_s8, c_s9 = st.columns([1, 1, 1])
        with c_s7:
            warmstart_options = ["surrogate", "archive", "none"]
            warmstart_value = str(
                st.session_state.get("warmstart_mode", DIAGNOSTIC_WARMSTART_MODE)
                or DIAGNOSTIC_WARMSTART_MODE
            )
            warmstart_index = warmstart_options.index(warmstart_value) if warmstart_value in warmstart_options else 0
            st.selectbox(
                "Warm-start режим",
                options=warmstart_options,
                index=warmstart_index,
                key="warmstart_mode",
                help="surrogate: прогреть распределение по surrogate; archive: стартовать из истории; none: без warm-start.",
            )
        with c_s8:
            st.number_input(
                "Surrogate samples",
                min_value=500,
                max_value=50000,
                value=int(
                    st.session_state.get("surrogate_samples", DIAGNOSTIC_SURROGATE_SAMPLES)
                    or DIAGNOSTIC_SURROGATE_SAMPLES
                ),
                step=500,
                key="surrogate_samples",
                help="Сколько случайных точек ранжировать в surrogate warm-start.",
            )
        with c_s9:
            st.number_input(
                "Surrogate top-k",
                min_value=8,
                max_value=512,
                value=int(
                    st.session_state.get("surrogate_top_k", DIAGNOSTIC_SURROGATE_TOP_K)
                    or DIAGNOSTIC_SURROGATE_TOP_K
                ),
                step=8,
                key="surrogate_top_k",
                help="Размер элиты для инициализации распределения staged search.",
            )

        c_s10, c_s11, c_s12 = st.columns([1, 1, 1])
        with c_s10:
            st.number_input(
                "Early-stop штраф (stage1)",
                min_value=0.0,
                max_value=1e9,
                value=float(st.session_state.get("stop_pen_stage1", 25.0) or 25.0),
                step=1.0,
                key="stop_pen_stage1",
                help="Если накопленный штраф > порога — StageRunner прерывает оставшиеся тесты для кандидата на длинной стадии.",
            )
        with c_s11:
            st.number_input(
                "Early-stop штраф (stage2)",
                min_value=0.0,
                max_value=1e9,
                value=float(st.session_state.get("stop_pen_stage2", 15.0) or 15.0),
                step=1.0,
                key="stop_pen_stage2",
                help="Более строгий порог для финальной стадии.",
            )
        with c_s12:
            st.checkbox(
                "Сортировать тесты по стоимости",
                value=bool(st.session_state.get("sort_tests_by_cost", DIAGNOSTIC_SORT_TESTS_BY_COST)),
                key="sort_tests_by_cost",
                help="Дешёвые тесты идут первыми, чтобы early-stop быстрее отбрасывал плохих кандидатов.",
            )

        c_s13, c_s14, c_s15 = st.columns([1, 1, 1])
        with c_s13:
            influence_eps_rel = st.number_input(
                "System Influence eps_rel",
                min_value=1e-6,
                max_value=0.25,
                value=float(
                    st.session_state.get("influence_eps_rel", DIAGNOSTIC_INFLUENCE_EPS_REL)
                    or DIAGNOSTIC_INFLUENCE_EPS_REL
                ),
                step=1e-3,
                format="%.6g",
                key="influence_eps_rel",
                help="Явный относительный шаг возмущения для system_influence_report_v1 в StageRunner.",
            )
        with c_s14:
            adaptive_influence_eps = st.checkbox(
                "Adaptive epsilon для System Influence",
                value=bool(st.session_state.get("adaptive_influence_eps", DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS)),
                key="adaptive_influence_eps",
                help=(
                    "System Influence прогоняет сетку eps_rel и выбирает более устойчивый шаг. "
                    f"Базовая сетка: {influence_eps_grid_text(DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID)}."
                ),
            )
        with c_s15:
            stage_policy_options = ["influence_weighted", "static"]
            stage_policy_value = str(
                st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE)
                or DEFAULT_STAGE_POLICY_MODE
            )
            stage_policy_index = (
                stage_policy_options.index(stage_policy_value)
                if stage_policy_value in stage_policy_options
                else 0
            )
            st.selectbox(
                "Политика отбора и продвижения",
                options=stage_policy_options,
                index=stage_policy_index,
                key="stage_policy_mode",
                help=(
                    "influence_weighted — позже стадии сильнее фокусируются на stage-relevant параметрах; "
                    "static — историческое поведение без influence-aware promotion."
                ),
            )

        st.caption("Профиль стадийного отбора и продвижения: " + stage_seed_policy_summary_text())
        if adaptive_influence_eps:
            st.caption(
                "Адаптивный epsilon по стадиям: "
                + stage_aware_influence_profiles_text(
                    requested_eps_rel=float(influence_eps_rel),
                    base_grid=DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID,
                )
            )


__all__ = [
    "render_stage_runner_configuration_controls",
]
