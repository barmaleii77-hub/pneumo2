# V12 window internal routes

Источник: `C:/Users/Admin/Downloads/pneumo_human_gui_report_only_v12_window_internal_routes.zip`.

Дата импорта в KB: 2026-04-20.

## Роль слоя

Этот каталог хранит report-only слой про первый рабочий экран и первый
осмысленный маршрут action -> feedback для четырех окон:

- поверхность проверки и отправки архива;
- подробное сравнение результатов;
- исходные данные проекта;
- набор испытаний.

Слой не содержит кода и не является runtime-closure proof. Он фиксирует
канонический first-screen contract, direct tree open, dock role и обязательную
обратную связь, но не доказывает, что живые current-окна уже визуально приняты.

## Отделение от `v12_design_recovery`

`v12_window_internal_routes` не заменяет исторический
`v12_design_recovery`. Это другой архив с совпадающим номером V12:

- `v12_design_recovery` - historical design-recovery слой старой ветки
  `v1...v13`;
- `v12_window_internal_routes` - текущий report-only слой 2026-04-20 про
  внутренние маршруты окон, первый экран и action-feedback.

## Как применять

Использовать после `v38_actualized_with_v10` и `v19_graph_iteration`, когда
работа касается одного из четырех окон этого пакета.

Ключевые правила:

- вход из дерева должен открывать рабочее содержимое напрямую, без кнопки
  промежуточного запуска выбранного этапа;
- первый экран должен за 3-5 секунд объяснять, что открыто, что уже выбрано,
  что готово, что устарело и какой следующий осмысленный шаг;
- длительный процесс должен показывать прогресс и результат на той же
  поверхности, где действие запущено;
- вторичные действия не должны конкурировать с главным маршрутом;
- raw file names, English implementation terms and `GUI ...` labels must not
  leak into operator-facing UI.

## Терминологическое уточнение

Архив использует название `Диагностика` как короткую роль окна. В проектной KB
это не означает автоматическое разрешение голой пользовательской надписи
`Диагностика`, если она сбивает пользователя с расчета подвески на
представление об отладке. Для операторского интерфейса предпочтительна
предметная формулировка маршрута проверки и отправки архива, а не техническая
служебная роль.

## Файлы пакета

- `EXEC_SUMMARY.md` - краткий итог слоя.
- `WINDOW_FIRST_SCREEN_CONTRACT_V12.md` - first-screen contracts для четырех окон.
- `WINDOW_ACTION_FEEDBACK_MATRIX_V12.csv` - primary action -> feedback matrix.
- `DIRECT_TREE_OPEN_AND_DOCK_ROLE_V12.csv` - direct-open и dock-role rules.
- `SEMANTIC_REWRITE_MATRIX_V12.csv` - user-facing semantic rewrites.
- `WINDOW_ROUTE_QUALITY_V12.csv` - оценка качества текущих маршрутов.
- `CURRENT_VS_CANONICAL_*_V12.md` - разбор current evidence против canonical route.
- `*_ACTION_FEEDBACK_SUBGRAPH_V12.dot` - DOT-subgraphs по окнам.
- `LIMITS_AND_NOT_OPENED_V12.md` - границы доказательности.
- `NEXT_STEP_V12.md` - следующий слой работ после V12.
