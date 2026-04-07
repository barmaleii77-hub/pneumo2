# Best practices (Streamlit / диагностика / качество)

Этот файл — краткая выжимка принятых практик для большого Streamlit‑приложения,
чтобы не наступать снова на типовые проблемы (бесконечные rerun, session_state,
тяжёлые вычисления, UI‑компоненты, логи и т.п.).

## 1) Кэширование тяжёлых вычислений

Используем:
- `st.cache_data` для детерминированных расчётов (симуляция/постпроцессинг),
- `st.cache_resource` для «ресурсов» (модели, большие таблицы, ...),
- избегаем скрытых зависимости от `st.session_state` внутри кэшируемых функций.

Рекомендации: см. Streamlit docs по caching.

## 2) Управление `session_state`

Правило: **не пытаться писать в `st.session_state[key]` после того, как создан виджет с этим key**.
Иначе Streamlit кидает `StreamlitAPIException`.

Решения:
- инициализация значений ДО виджета,
- использование `on_change` callback,
- или «single source of truth» в одном месте.

## 3) Изоляция тяжёлых UI‑веток

Если ветка UI запускает тяжёлый код при любом rerun — держим её за «пальцем»,
делаем явные кнопки «Рассчитать», используем флаги `dirty/ready`.

В новых версиях Streamlit можно применять фрагменты (`st.fragment`) для
локального обновления участков страницы.

## 4) Статические проверки (чтобы не ловить NameError в рантайме)

Добавлены:
- `compileall` (компиляция всех python‑файлов),
- `ruff check --select F821` (поиск undefined names).

Это запускается из диагностики и кладётся в архив.



## Ссылки (официальные/референсы)

- Streamlit Fragments: https://docs.streamlit.io/develop/concepts/architecture/fragments
- Streamlit Caching: https://docs.streamlit.io/develop/concepts/architecture/caching
- Ruff rule F821 (undefined-name): https://docs.astral.sh/ruff/rules/undefined-name/
- DiskCache (persistent cache): https://pypi.org/project/diskcache/

