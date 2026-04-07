# UX / UI Best Practices — sources & how we applied them

Цель этого документа: зафиксировать «почему UI сделан так», чтобы дальше не откатываться к мегатаблицам/миллиону чекбоксов.

## 1) Progressive Disclosure (прогрессивное раскрытие)

Идея: на экране — только то, что нужно **сейчас**. Редкие/экспертные настройки — во вторичном слое (popover/expander).

Источники:
- Interaction Design Foundation — *Progressive Disclosure*:
  https://www.interaction-design.org/literature/topics/progressive-disclosure

Как применено в Interfeis765:
- `ui_popover()` (popover → expander fallback)
- Настройки «детального прогона» baseline и Pareto‑фильтры перенесены в popover.

## 2) Master–Detail / List–Detail pattern для таблиц

Когда таблица становится широкой или «многопараметрической» — это уже не таблица, а база данных.
Решение: **список** для выбора/поиска + **карточка** выбранной строки (детали/действия).

Источники:
- Windows Developer Blog — *Master the Master-Detail Pattern*:
  https://blogs.windows.com/windowsdeveloper/2017/05/01/master-master-detail-pattern/
- Microsoft Learn — *Details Master form pattern* (вариант master→detail для плотных данных):
  https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/user-interface/details-master-form-pattern

Как применено:
- `safe_dataframe()` автоматически переключается на master→detail если таблица «широкая».
- В деталях выбор строки переведён на slider (минимум ручного ввода).

## 3) «Нет горизонтального скролла»

Горизонтальный скролл в таблицах почти всегда означает, что структура данных не подходит для текущего представления.
Решения: группировка, фильтр/поиск, детализация строки.

Источник (косвенно подтверждает важность экрана выше сгиба и эффекты скролла):
- Nielsen Norman Group — *Scrolling and Attention*:
  https://www.nngroup.com/articles/scrolling-and-attention/
- Nielsen Norman Group — *Horizontal Attention Leans Left*:
  https://www.nngroup.com/articles/horizontal-attention-leans-left/

Как применено:
- Любые таблицы, которые потенциально могут стать широкими, идут через `safe_dataframe()` и/или схему «список + карточка».
- В UI правило: если появился горизонтальный скролл — это баг дизайна, нужно переделывать.

## 4) Streamlit: избегать st.tabs для тяжёлого контента

Важно: `st.tabs` не ленивый — всё в каждой вкладке вычисляется всегда.

Источник:
- Streamlit Docs — `st.tabs`:
  https://docs.streamlit.io/develop/api-reference/layout/st.tabs

Как применено:
- Для тяжёлых блоков используем **условный рендеринг** (radio/segmented_control),
  чтобы реально отрисовывался только выбранный экран.
