"""Global UI settings.

Principles:
- No hidden "advanced" mode.
- Rare knobs live here; frequently used knobs can be mirrored in thematic pages.
- All values must persist across page navigation and app restarts.
"""

from __future__ import annotations

from pathlib import Path
import os

import streamlit as st

from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_settings import apply_env_from_settings, ensure_defaults, sync_common_flags


st.set_page_config(page_title="Пневмо‑UI | Настройки", layout="wide")

bootstrap(st)
ensure_defaults(st)

st.title("Настройки")
st.caption(
    "Здесь собраны общие настройки приложения: проверка проекта, производительность интерфейса, пути хранения данных. "
    "Часто используемые настройки также должны быть продублированы в тематических разделах."
)

tab_diag, tab_perf, tab_paths = st.tabs(["Проверка проекта", "Производительность UI", "Пути и хранение"])


with tab_diag:
    st.subheader("Проверка проекта и архив")
    st.write(
        "Кнопка «Сохранить архив проекта» сохраняет ZIP‑архив со всем нужным для разбора проекта: "
        "логи, конфиги, версии, состояние, следы ошибок."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.text_input(
            "Папка для архивов проекта",
            key="settings_diag_out_dir",
            help="Куда сохранять ZIP. Должно быть доступно на запись. По умолчанию — в домашней папке пользователя.",
        )
        st.number_input(
            "Хранить последних архивов (шт)",
            min_value=1,
            max_value=200,
            step=1,
            key="settings_diag_keep_last_n",
            help="Автоматическая очистка старых архивов, чтобы папка не разрасталась бесконечно.",
        )
        st.number_input(
            "Ограничение размера одного файла в архиве (МБ)",
            min_value=1,
            max_value=500,
            step=1,
            key="settings_diag_max_file_mb",
            help="Крупные бинарные файлы могут раздувать архив. Ограничение помогает сохранить ZIP компактным.",
        )

    with c2:
        st.checkbox(
            "Включать папку workspace",
            key="settings_diag_include_workspace",
            help="Если выключено, ZIP будет легче. Если включено — воспроизводимость выше.",
        )
        st.checkbox(
            "Автосохранение архива проекта при выходе",
            key="settings_diag_autosave_on_exit",
            help="Сохранять архив проекта автоматически при закрытии приложения.",
        )
        st.checkbox(
            "Автосохранение архива проекта при сбое",
            key="settings_diag_autosave_on_crash",
            help="Если приложение упадёт с необработанным исключением — попытаться автоматически сохранить ZIP.",
        )
        st.text_input(
            "Тег/метка (опционально)",
            key="settings_diag_tag",
            help="Короткая метка для имени архива: например, 'valve_bug' или 'release_test'.",
        )
        st.text_area(
            "Комментарий/причина (опционально)",
            key="settings_diag_reason",
            height=80,
            help="Будет записано в manifest внутри ZIP и поможет быстрее понять контекст проблемы.",
        )

    st.info(
        "Папка и настройки архива проекта применяются сразу. Если автосохранение включено — оно будет работать "
        "и при выходе, и при сбое (насколько это возможно в среде запуска)."
    )

    st.subheader('Детерминизм и идентификаторы')
    st.write('Настройки, влияющие на стабильность идентификаторов задач, и на точность некоторых справочных констант.')

    c1, c2 = st.columns(2)
    with c1:
        st.selectbox(
            'PNEUMO_OPT_PROBLEM_HASH_MODE (по умолчанию)',
            options=['stable', 'legacy'],
            key='settings_opt_problem_hash_mode',
            help=(
                'stable — устойчивый hash по содержимому: фикс. часть base (без optim keys) + набор optim keys + suite + sha кода.\n'
                'legacy — старый режим совместимости (может зависеть от путей/конфигов).\n'
                'Важно: пользователь всегда может переключить режим; значение влияет на resume/кэширование.'
            ),
        )

    with c2:
        st.selectbox(
            'PNEUMO_ISO6358_RHO_ANR_MODE',
            options=['norm', 'calc'],
            key='settings_iso6358_rho_anr_mode',
            help=(
                'norm — нормативная плотность ρ_ANR=1.185 кг/м³ (ISO 8778).\n'
                'calc — вычислять ρ_ANR из p_ANR и T_ANR по идеальному газу.\n'
                'Для паспортных/ISO расчётов обычно нужен norm; для физической согласованности — calc.'
            ),
        )


with tab_perf:
    st.subheader("Производительность UI")
    st.write(
        "Глобальные настройки, которые помогают не перегружать браузер и ускорять интерфейс. "
        "На тяжёлых страницах также есть локальные гейты (чекбоксы) для отдельных графиков/таблиц."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.checkbox(
            "Отключить тяжёлые графики по умолчанию",
            key="settings_ui_disable_heavy_plots",
            help="Если включено, страницы будут стараться не строить тяжёлые графики без явного запроса.",
        )
    with c2:
        st.number_input(
            "TTL кэша UI (сек)",
            min_value=10,
            max_value=24 * 3600,
            step=60,
            key="settings_ui_cache_ttl_sec",
            help="Сколько секунд держать кэш тяжёлых объектов (графики, NPZ‑данные и т.п.).",
        )

    st.caption(
        "Важно: экспандер сам по себе не останавливает код. Для тяжёлых блоков везде должны быть именно гейт‑чекбоксы."
    )


with tab_paths:
    st.subheader("Пути и хранение")
    st.write(
        "Пути используются для сохранения профилей, кэша, промежуточных результатов и архивов проекта. "
        "Если приложение установлено в защищённую папку (например Program Files), лучше указывать пути в домашней папке."
    )

    out_dir = Path(st.session_state.get("settings_diag_out_dir", "")).expanduser()
    exists = out_dir.exists()
    writable = os.access(str(out_dir), os.W_OK) if exists else os.access(str(out_dir.parent), os.W_OK)

    st.markdown("**Архив проекта (папка для ZIP):**")
    st.code(str(out_dir))
    c1, c2, c3 = st.columns(3)
    c1.metric("Существует", "Да" if exists else "Нет")
    c2.metric("Доступна на запись", "Да" if writable else "Нет")
    c3.metric("ENV", "PNEUMO_BUNDLE_OUT_DIR")

    st.caption(
        "Некоторые параметры можно задавать через переменные окружения. Это полезно для CI/серверов."
    )


# Apply immediately
sync_common_flags(st)
apply_env_from_settings(st)

# best‑effort autosave
try:
    from pneumo_solver_ui.ui_persistence import autosave_if_enabled

    autosave_if_enabled(st)
except Exception:
    pass
