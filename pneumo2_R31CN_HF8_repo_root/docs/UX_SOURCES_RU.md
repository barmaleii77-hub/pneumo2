# UX источники (для обоснования решений интерфейса)

Ниже — ключевые источники, на которые опирается «Интерфейс» при упрощении UI:

1) Progressive disclosure (прогрессивное раскрытие) — не показывать всё сразу, а раскрывать сложные/редкие настройки по мере необходимости:
- NN/g: Progressive Disclosure — https://www.nngroup.com/articles/progressive-disclosure/
- IxDF: Progressive Disclosure (обзор) — https://www.interaction-design.org/literature/topics/progressive-disclosure

2) Таблицы и большие наборы данных:
- NN/g: Data Tables: Four Major User Tasks — https://www.nngroup.com/articles/data-tables/
  (ключевая мысль: таблица должна поддерживать задачи поиска/сравнения/редактирования одной строки/действий)
- Microsoft: List/details pattern — https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/list-details
  (паттерн «список → детали», хорошо заменяет «широкие таблицы»)
- Microsoft (Dynamics): grid 2–15 полей + быстрый фильтр, ссылки в детали — https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/user-interface/list-page-form-pattern

3) Горизонтальная прокрутка:
- NN/g: Beware Horizontal Scrolling… — https://www.nngroup.com/articles/horizontal-scrolling/
- NN/g: Scrolling and Scrollbars — https://www.nngroup.com/articles/scrolling-and-scrollbars/
  (в т.ч. «avoid horizontal scrolling»)

4) Подсказки (tooltips) в Streamlit:
- Streamlit Docs: параметр `help` у виджетов (пример: st.text_input) — https://docs.streamlit.io/develop/api-reference/widgets/st.text_input
- Streamlit Docs: help у кнопок — https://docs.streamlit.io/develop/api-reference/widgets/st.button

