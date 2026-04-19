# V38 actualized with V10 KB import audit

Дата: 2026-04-19

## Источник

- Архив: `C:/Users/Admin/Downloads/pneumo_codex_tz_spec_connector_reconciled_v38_actualized_with_v10.zip`
- Импорт в репозиторий: `docs/context/gui_spec_imports/v38_actualized_with_v10/`
- Package id: `pneumo_codex_tz_spec_connector_reconciled_v38_actualized_with_v10`

## Что прочитано при импорте

- `README.md`
- `EXEC_SUMMARY.json`
- `TECHNICAL_SPECIFICATION.md`
- `GUI_SPEC.yaml`
- `V10_ACTUALIZATION_REPORT.md`
- `LAUNCHER_HIERARCHY_RECONCILIATION_V10.md`
- `V10_RECONCILIATION_MATRIX.csv`
- `REQUIREMENTS_MATRIX.csv`
- `CONFLICTS_AND_ASSUMPTIONS.csv`
- `REPO_OPEN_GAPS_TO_KEEP_OPEN.csv`
- `ACTIVE_CANON_SUCCESSOR_MATRIX.csv`
- `PACKAGE_SELFCHECK_REPORT.json`
- `STRUCTURE_LINT_REPORT.md`
- `PACKAGE_NON_RUNTIME_CLOSURE_NOTICE.md`

## Решение по канону

`v38_actualized_with_v10` становится текущим активным imported GUI/TZ/spec слоем для новой desktop-GUI работы.

Приоритет выше остаётся у:

1. `00_READ_FIRST__ABSOLUTE_LAW.md`
2. `01_PARAMETER_REGISTRY.md`
3. `DATA_CONTRACT_UNIFIED_KEYS.md`
4. `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
5. `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`

Предыдущий `v38_github_kb_commit_ready`, отдельные human GUI reports V5/V6/V10 и V37/V33/V32 сохраняются как provenance, evidence и historical reference, но не должны читаться как более свежий активный слой, если противоречат `v38_actualized_with_v10`.

## Что добавляет V38 actualized with V10

- V10 findings встроены в V38 как явная иерархия запуска.
- Стартовый shell должен показывать один доминирующий маршрут из 8 шагов:
  `Исходные данные -> Редактор кольца / сценариев -> Набор испытаний -> Базовый прогон -> Оптимизация -> Анализ результатов -> Анимация -> Диагностика`.
- `Редактор кольца` усиливается как доминирующий сценарный центр и единственный editable source-of-truth сценариев.
- `Диагностика` имеет один основной маршрут; отправка результатов является вложенным действием после готовой диагностики, а не отдельным стартовым направлением.
- Встроенное сравнение в анализе является основным маршрутом сравнения; отдельное окно сравнения остаётся расширенным режимом из анализа.
- `Desktop Mnemo` и инструменты остаются доступными, но не конкурируют с основным маршрутом первых минут.
- Добавлены требования `REQ-046` ... `REQ-050` и соответствующие acceptance/test rows.

## Проверка на противоречия

Блокирующего противоречия с текущей базой знаний не обнаружено.

Неблокирующая неоднозначность: заголовок `README.md` сохраняет историческое
название `README_V38_GITHUB_KB_COMMIT_READY`. Активный статус пакета
определяется по `EXEC_SUMMARY.json`, `TECHNICAL_SPECIFICATION.md`,
`V10_ACTUALIZATION_REPORT.md` и `PACKAGE_SELFCHECK_REPORT.json`, где пакет
зафиксирован как V38 actualized with V10. Заголовок README трактуется как
lineage/provenance, а не как отмена V10-актуализации.

Зафиксированное в пакете `CONFLICT-V10-001` трактуется как разрешённое целевое решение: специализированные окна сохраняются, но их launcher-priority понижается относительно основного маршрута. Это не отменяет требования не ломать и не дублировать `Desktop Animator`, `Compare Viewer` и `Desktop Mnemo`.

## Что нельзя считать закрытым

Пакет не является runtime-closure proof. Открытыми остаются:

- producer-side hardpoints / solver_points truth;
- cylinder packaging passport;
- measured browser performance / viewport gating;
- Windows visual/runtime acceptance.

Эти пункты нельзя закрывать словами в документах без новых runtime artifacts, тестов и визуальной проверки.

## Правило для следующих чатов

Перед изменениями GUI читать:

1. `docs/00_PROJECT_KNOWLEDGE_BASE.md`
2. `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
3. `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
4. `docs/context/gui_spec_imports/v38_actualized_with_v10/README.md`
5. `docs/context/gui_spec_imports/v38_actualized_with_v10/TECHNICAL_SPECIFICATION.md`
6. `docs/context/gui_spec_imports/v38_actualized_with_v10/GUI_SPEC.yaml`
7. `docs/context/gui_spec_imports/v38_actualized_with_v10/LAUNCHER_HIERARCHY_RECONCILIATION_V10.md`
8. `docs/context/gui_spec_imports/v38_actualized_with_v10/V10_RECONCILIATION_MATRIX.csv`
9. `docs/context/gui_spec_imports/v38_actualized_with_v10/REQUIREMENTS_MATRIX.csv`
10. `docs/context/gui_spec_imports/v38_actualized_with_v10/ACCEPTANCE_MATRIX.csv`

Практическая проверка для GUI: видимый пользовательский маршрут должен совпадать с V10-актуализированной восьмишаговой иерархией, а служебные названия и внутренние статусы не должны вылезать в интерфейс как пользовательская информация.
