from __future__ import annotations

from typing import Any

from pneumo_solver_ui.optimization_defaults import (
    DEFAULT_OPTIMIZATION_OBJECTIVES,
    DIAGNOSTIC_PROBLEM_HASH_MODE,
    DIST_OPT_BUDGET_DEFAULT,
    DIST_OPT_DEVICE_DEFAULT,
    DIST_OPT_MAX_INFLIGHT_DEFAULT,
    DIST_OPT_PENALTY_KEY_DEFAULT,
    DIST_OPT_PENALTY_TOL_DEFAULT,
    DIST_OPT_PROPOSER_DEFAULT,
    DIST_OPT_Q_DEFAULT,
    DIST_OPT_SEED_DEFAULT,
    objectives_text,
)


def render_coordinator_algorithm_controls(
    st: Any,
    *,
    show_staged_caption: bool = False,
) -> None:
    with st.expander("Алгоритм и критерии останова", expanded=True):
        st.markdown(
            "Здесь задаются **инженерные параметры оптимизации**: выбор метода порождения кандидатов, "
            "бюджет, seed, лимит параллельных вычислений и критерии по штрафам/ограничениям."
        )
        if show_staged_caption:
            st.caption(
                "Этот блок нужен для distributed coordinator path. В staged режиме он не пропадает, "
                "но применяется только когда вы выключаете StageRunner."
            )

        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            st.selectbox(
                "Метод (алгоритм) предложения кандидатов",
                options=["auto", "portfolio", "qnehvi", "random"],
                index=["auto", "portfolio", "qnehvi", "random"].index(
                    str(st.session_state.get("opt_proposer", DIST_OPT_PROPOSER_DEFAULT) or DIST_OPT_PROPOSER_DEFAULT)
                )
                if str(st.session_state.get("opt_proposer", DIST_OPT_PROPOSER_DEFAULT) or DIST_OPT_PROPOSER_DEFAULT)
                in ["auto", "portfolio", "qnehvi", "random"]
                else 0,
                key="opt_proposer",
                help=(
                    "auto — использовать лучшее доступное (qNEHVI при наличии BoTorch, иначе random).\n"
                    "portfolio — смешивать qNEHVI и random для устойчивости.\n"
                    "qnehvi — BoTorch qNEHVI (требует установленных зависимостей).\n"
                    "random — LHS/случайный поиск."
                ),
            )

        with c2:
            st.number_input(
                "Бюджет (кол-во оценок целевой функции)",
                min_value=1,
                max_value=100000,
                value=int(st.session_state.get("opt_budget", DIST_OPT_BUDGET_DEFAULT) or DIST_OPT_BUDGET_DEFAULT),
                step=10,
                key="opt_budget",
                help="Сколько запусков/оценок выполнить суммарно. Это главный 'стоп' критерий.",
            )

        with c3:
            st.number_input(
                "Макс. параллельных задач",
                min_value=0,
                max_value=4096,
                value=int(
                    st.session_state.get("opt_max_inflight", DIST_OPT_MAX_INFLIGHT_DEFAULT)
                    or DIST_OPT_MAX_INFLIGHT_DEFAULT
                ),
                step=1,
                key="opt_max_inflight",
                help=(
                    "Ограничивает, сколько оценок одновременно может быть 'в полёте'.\n"
                    "0 — автоматически (≈ 2×кол-во воркеров)."
                ),
            )

        c4, c5, c6 = st.columns([2, 2, 2])
        with c4:
            st.number_input(
                "Seed (для воспроизводимости)",
                min_value=0,
                max_value=2**31 - 1,
                value=int(st.session_state.get("opt_seed", DIST_OPT_SEED_DEFAULT) or DIST_OPT_SEED_DEFAULT),
                step=1,
                key="opt_seed",
                help="Фиксирует генератор случайных чисел. Одинаковый seed → более повторяемые эксперименты.",
            )

        with c5:
            st.text_input(
                "Ключ штрафа/ограничений (penalty_key)",
                value=str(st.session_state.get("opt_penalty_key", DIST_OPT_PENALTY_KEY_DEFAULT) or DIST_OPT_PENALTY_KEY_DEFAULT),
                key="opt_penalty_key",
                help=(
                    "Имя поля в результатах расчёта, которое интерпретируется как штраф (constraint violation). "
                    "0 — полностью допустимо; >0 — нарушение."
                ),
            )

        with c6:
            st.number_input(
                "Допуск штрафа (penalty_tolerance)",
                min_value=0.0,
                max_value=1e9,
                value=float(
                    st.session_state.get("opt_penalty_tol", DIST_OPT_PENALTY_TOL_DEFAULT)
                    or DIST_OPT_PENALTY_TOL_DEFAULT
                ),
                step=1e-9,
                format="%.3e",
                key="opt_penalty_tol",
                help="Если penalty <= tol — считаем решение допустимым.",
            )

        hash_modes = ["stable", "legacy"]
        hash_mode_value = str(
            st.session_state.get("settings_opt_problem_hash_mode", DIAGNOSTIC_PROBLEM_HASH_MODE)
            or DIAGNOSTIC_PROBLEM_HASH_MODE
        )
        hash_mode_index = hash_modes.index(hash_mode_value) if hash_mode_value in hash_modes else 0
        st.selectbox(
            "Режим идентификатора задачи (problem_hash)",
            options=hash_modes,
            index=hash_mode_index,
            key="settings_opt_problem_hash_mode",
            help=(
                "stable (рекомендуется) — устойчивый hash по содержимому (фикс. часть base + набор optim keys + suite + sha кода).\n"
                "legacy — совместимость со старыми run_id; может зависеть от путей/настроек."
            ),
        )

        st.divider()

        c7, c8, c9 = st.columns([2, 2, 2])
        with c7:
            st.number_input(
                "q (сколько кандидатов предлагать за шаг)",
                min_value=1,
                max_value=256,
                value=int(st.session_state.get("opt_q", DIST_OPT_Q_DEFAULT) or DIST_OPT_Q_DEFAULT),
                step=1,
                key="opt_q",
                help="Для qNEHVI/portfolio можно предлагать пачку кандидатов за итерацию.",
            )
        with c8:
            device_options = ["auto", "cpu", "cuda"]
            device_value = str(st.session_state.get("opt_device", DIST_OPT_DEVICE_DEFAULT) or DIST_OPT_DEVICE_DEFAULT)
            device_index = device_options.index(device_value) if device_value in device_options else 0
            st.selectbox(
                "Устройство для модели (device)",
                options=device_options,
                index=device_index,
                key="opt_device",
                help="auto — выбрать автоматически. cuda — использовать GPU (если доступно и установлены зависимости).",
            )
        with c9:
            st.text_area(
                "Целевые метрики (objective keys) — по одной в строке",
                value=str(
                    st.session_state.get(
                        "opt_objectives",
                        objectives_text(DEFAULT_OPTIMIZATION_OBJECTIVES),
                    )
                ),
                height=92,
                key="opt_objectives",
                help=(
                    "Ключи метрик, которые оптимизируются (multi-objective).\n"
                    "Формат: по одной в строке (или можно разделять запятыми)."
                ),
            )


__all__ = [
    "render_coordinator_algorithm_controls",
]
