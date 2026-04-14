# Единая база знаний проекта

## Назначение

Этот документ собирает в одном месте текущий рабочий канон проекта, активные требования, backlog, исполняемые контракты и архивные слои контекста.

Цель документа:

- дать один стартовый источник для AI и разработчиков;
- уменьшить повторное чтение десятков `TODO/WISHLIST/addendum` файлов;
- явно разделить:
  - что является законом и каноном;
  - что является активным планом работ;
  - что является исполняемым контрактом;
  - что является историей и архивом.

Этот файл не заменяет канонические документы. Он задаёт порядок приоритетов и краткую сводку по ним.

## Как использовать

Если нужно начать новую работу, сначала читать этот файл, а затем переходить по слоям приоритета сверху вниз.

Если два источника противоречат друг другу, приоритет определяется разделом `Порядок приоритета`.

## Правило пополнения базы знаний

Начиная с текущего рабочего цикла, база знаний должна пополняться не только из файлов репозитория, но и из рабочих чатов проекта.

Обязательное правило:

- все новые пользовательские хотелки, явно сформулированные в чатах этого проекта, должны фиксироваться в knowledge-base слое;
- все новые планы работ, decomposition, migration plans и prompt-packages, которые генерируют чаты этого проекта, тоже должны фиксироваться в knowledge-base слое;
- если желание или план пока не оформлены в код, они всё равно должны быть занесены как проектное требование, решение или рабочее направление;
- knowledge-base запись не заменяет канон, но становится частью рабочего контекста для следующих задач.

Для этого в базе знаний используются два специальных журнала:

- [docs/13_CHAT_REQUIREMENTS_LOG.md](./13_CHAT_REQUIREMENTS_LOG.md)
- [docs/14_CHAT_PLANS_LOG.md](./14_CHAT_PLANS_LOG.md)
- machine-readable store: [docs/15_CHAT_KNOWLEDGE_BASE.json](./15_CHAT_KNOWLEDGE_BASE.json)

Рабочий инструмент синхронизации:

- `python -m pneumo_solver_ui.tools.knowledge_base_sync ...`

Operational note:

- команды `add-requirement` и `add-plan` в `knowledge_base_sync` по умолчанию рассчитаны на autosave в git: stage, commit и push можно выполнять в том же вызове без отдельного ручного шага;
- если нужен только локальный апдейт без git, используется `--no-git-sync`.

Если в будущем появляются новые существенные решения из чатов, их нужно добавлять туда в том же рабочем цикле.

## Порядок приоритета

### 1. Абсолютный канон

1. [00_READ_FIRST__ABSOLUTE_LAW.md](../00_READ_FIRST__ABSOLUTE_LAW.md)
2. [01_PARAMETER_REGISTRY.md](../01_PARAMETER_REGISTRY.md)
3. [DATA_CONTRACT_UNIFIED_KEYS.md](../DATA_CONTRACT_UNIFIED_KEYS.md)

### 2. Канон запуска, desktop GUI и источников

4. [README.md](../README.md)
5. [docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](./17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
6. [docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](./18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
7. [docs/PROJECT_SOURCES.md](./PROJECT_SOURCES.md)
8. [AI_INTEGRATION_PLAYBOOK.yaml](../AI_INTEGRATION_PLAYBOOK.yaml)

### 3. Активные требования и рабочий backlog

9. [docs/01_RequirementsFromContext.md](./01_RequirementsFromContext.md)
10. [docs/10_NextStepsPlan.md](./10_NextStepsPlan.md)
11. [docs/11_TODO.md](./11_TODO.md)
12. [docs/12_Wishlist.md](./12_Wishlist.md)
13. [docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md](./12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md)

### 4. Исполняемые контракты и registries

14. `pneumo_solver_ui/contracts/*`
15. `pneumo_solver_ui/*contract*.py`
16. `tests/test_*contract*`

### 5. История и архив

17. `TODO_MASTER_*`, `WISHLIST_MASTER_*`
18. `TODO_WISHLIST_R31*_ADDENDUM_*.md`
19. `docs/consolidated/*`
20. `docs/context/WISHLIST*`
21. `docs/_legacy_DOCS_upper/*`

## Непереговорные правила проекта

Источник: [00_READ_FIRST__ABSOLUTE_LAW.md](../00_READ_FIRST__ABSOLUTE_LAW.md)

1. Нельзя выдумывать параметры.
2. Нельзя вводить алиасы и псевдо-совместимость вместо исправления контракта.
3. Производные и сервисные сигналы должны быть явно помечены, а не маскироваться под модельные.
4. Геометрия, координаты и физические сигналы должны идти из модели и экспорта, а не придумыватьcя UI или Animator.
5. Любой drift между слоями должен исправляться в контракте и быть видимым в диагностике.

Практический вывод:

- нельзя чинить несовместимость временными мостами;
- нельзя подменять authored data в viewer-слое;
- нельзя добавлять новые ключи без обновления канона и registry.

## Канонические ключи и data contract

Источник: [01_PARAMETER_REGISTRY.md](../01_PARAMETER_REGISTRY.md), [DATA_CONTRACT_UNIFIED_KEYS.md](../DATA_CONTRACT_UNIFIED_KEYS.md)

Главные источники канонических данных:

- `pneumo_solver_ui/default_base.json`
- `pneumo_solver_ui/default_ranges.json`
- `pneumo_solver_ui/default_suite.json`
- `pneumo_solver_ui/contracts/param_registry.yaml`
- `pneumo_solver_ui/contracts/generated/keys_registry.yaml`

Критично помнить:

- suite/test transport использует канонические ключи вроде `dt`, `t_end`, `auto_t_end_from_len`, `road_len_m`, `vx0_м_с`, `road_csv`, `axay_csv`;
- sidecar/meta transport для анимации и diagnostics должен использовать те же ключи без alias-слоя;
- `anim_latest`, `scenario_json`, `road_csv`, `axay_csv`, `meta_json`, `validation` и diagnostics surfaces не должны расходиться по названиям и смыслу полей.

Запрещённые практики:

- legacy-ключи вместо канонических;
- параллельные словари для одного и того же сигнала;
- silent remap без явного contract update.

## Канон источников проекта

Источник: [docs/PROJECT_SOURCES.md](./PROJECT_SOURCES.md), [README.md](../README.md), [AI_INTEGRATION_PLAYBOOK.yaml](../AI_INTEGRATION_PLAYBOOK.yaml)

Проект признаёт несколько слоёв источников:

- локальный канон в репозитории;
- локальные digests и snapshots AI-контекста;
- внешние архивы и Google Drive как контекст и история;
- исполняемые contracts и tests как проверяемое поведение.

Правило приоритета:

- внешние источники и AI snapshots не заменяют локальный канон;
- при конфликте между архивом и текущим каноном исправляется код и экспорт, а не добавляются alias-мосты.

## Активная инженерная повестка

Источник: [docs/10_NextStepsPlan.md](./10_NextStepsPlan.md), [docs/11_TODO.md](./11_TODO.md), [docs/12_Wishlist.md](./12_Wishlist.md)

### Текущие активные направления

- корректность ring и road profile генерации;
- truth-preserving export для animator, compare, validation и diagnostics;
- производительность UI и playback;
- достоверная геометрия подвески, колёс, цилиндров и packaging;
- улучшение дорожной поверхности, contact patch и visual truthfulness;
- optimisation workflow, distributed optimisation и experiment DB;
- единый diagnostics/send-bundle flow;
- улучшение инженерной observability: self-check, energy, thermo, validation.

### Крупные долгосрочные темы

- world coordinates и корректное движение автомобиля по дороге;
- two-cylinder-per-corner и расширенная геометрия креплений;
- длинные прогоны, температура и нагрузка;
- автоанализ численной нестабильности;
- relevance против каталогов и паспортов;
- fully differentiable model;
- совместная финальная анимация механики и пневматики.

### Часто повторяющиеся wishlist-мотивы

- catalogue-aware packaging;
- adaptive road mesh;
- truthful 3D wheel geometry;
- screen-aware layouts;
- browser/GUI performance observability;
- explicit ring closure policy;
- стабильность GL и viewer-контуров;
- устранение drift между authored geometry и displayed geometry.

## GUI-first рабочее направление

Источник: активное решение по развитию проекта, согласованное в текущем рабочем цикле, при опоре на существующие требования и backlog.

Текущее рабочее направление:

- проект переносит операторские сценарии из WEB в классический desktop GUI под Windows;
- WEB временно используется как источник текущего поведения и legacy reference, но не как желаемая целевая платформа;
- перенос должен быть без потери функциональности;
- специализированные окна `Desktop Animator`, `Compare Viewer`, `Desktop Mnemo` остаются отдельными доменами и не должны без необходимости дублироваться;
- GUI-архитектура должна оставаться модульной, чтобы разные окна и подсистемы можно было двигать параллельно разными чатами.

## Канон Windows desktop GUI

Главный desktop GUI source для GUI-first направления:

- [docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](./17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
- [docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](./18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)

Что задаёт общий canon:

- project-wide baseline для shell, editor-окон, viewport/workspace-поверхностей и analysis/workflow-модулей;
- командную поверхность по умолчанию: `menu bar + toolbar + dockable/floating/auto-hide panes + command search + status/progress strip`;
- правило `ribbon optional, not default`;
- обязательную keyboard-first, accessibility, High-DPI и performance discipline;
- нативное Windows windowing behavior: title bar, system menu, drag/maximize/snap semantics и сохранение dock/floating layouts;
- различение `status`, `in-window progress` и taskbar progress reflection;
- `Per-Monitor V2` и `WM_DPICHANGED` suggested-rectangle policy для Win32 path.

Что задаёт project-specific target spec:

- целевую top-level архитектуру `главный shell + specialized windows` для `Animator`, `Compare Viewer` и `Desktop Mnemo`;
- workflow-first contract: `Исходные данные -> Тест-набор / Сценарии -> Baseline -> Optimization -> Analysis / Animator / Diagnostics`;
- матрицу `web -> desktop` как обязательный артефакт сохранения функциональности при миграции;
- один selector optimization-mode, видимые `objective stack`, `hard gate` и baseline policy `автообновлять / не автообновлять`;
- `Ring Editor` как единственный source-of-truth сценариев и derived-only статус для preview/export/artifacts;
- first-class diagnostics contract: `Собрать диагностику`, bundle contents, latest ZIP, health/self-check, autosave on exit/crash;
- честную truth-state model для `Animator`: `truth complete`, `truth partial`, `truth absent`, без fake geometry и с explainable degraded mode;
- обязательные tooltip и question-mark help, которые дополняют layout, но не заменяют его;
- обязательные графические input surfaces, source markers и время построения для расчётных previews и графиков;
- refined Windows title-bar/system-menu/Snap Layout behavior, `UI Automation`, `WM_DPICHANGED`, idle CPU, hidden-pane budget и ETW-style instrumentation policy для desktop GUI.

Связанные, но вспомогательные UX-источники:

- [docs/UX_BEST_PRACTICES_SOURCES.md](./UX_BEST_PRACTICES_SOURCES.md)
- [docs/UX_SOURCES_RU.md](./UX_SOURCES_RU.md)

Их роль:

- они помогают обосновывать отдельные UX-решения;
- они не переопределяют desktop GUI canon и не конкурируют с ним как с главным baseline;
- при конфликте между старым WEB/Streamlit UX-решением и desktop GUI canon приоритет у desktop GUI canon.

## Исполняемые требования

Главная идея: часть требований живёт не в prose-документах, а в коде и тестах.

### Основные contract/registry файлы

- `pneumo_solver_ui/contracts/param_registry.yaml`
- `pneumo_solver_ui/contracts/generated/keys_registry.yaml`
- `pneumo_solver_ui/contracts/registry.py`
- `pneumo_solver_ui/data_contract.py`
- `pneumo_solver_ui/param_contract.py`
- `pneumo_solver_ui/geometry_acceptance_contract.py`
- `pneumo_solver_ui/anim_export_contract.py`
- `pneumo_solver_ui/optimization_input_contract.py`
- `pneumo_solver_ui/optimization_objective_contract.py`
- `pneumo_solver_ui/solver_points_contract.py`
- `pneumo_solver_ui/workspace_contract.py`
- `pneumo_solver_ui/tools/send_bundle_contract.py`

### Вспомогательные инструменты сборки и валидации канона

- `pneumo_solver_ui/tools/build_key_registry.py`
- `pneumo_solver_ui/tools/param_contract_check.py`
- `pneumo_solver_ui/tools/validate_anim_export_contract.py`
- `pneumo_solver_ui/tools/aggregate_todo_wishlist.py`
- `pneumo_solver_ui/tools/extract_requirements_from_context.py`

### Тесты как часть базы знаний

Особенно важны:

- `tests/test_*contract*`
- `tests/test_*requirements*`
- acceptance/regression tests вокруг:
  - animator/export/meta;
  - compare/validation;
  - diagnostics/send bundle;
  - optimization contract surfaces;
  - geometry and packaging.

Если prose-документ и живой contract-тест расходятся, это сигнал к разбору, а не повод silently подгонять реализацию.

## Что считать активным backlog

Активным backlog считать:

- [docs/10_NextStepsPlan.md](./10_NextStepsPlan.md)
- [docs/11_TODO.md](./11_TODO.md)
- [docs/12_Wishlist.md](./12_Wishlist.md)
- [docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md](./12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md)
- [docs/13_CHAT_REQUIREMENTS_LOG.md](./13_CHAT_REQUIREMENTS_LOG.md)
- [docs/14_CHAT_PLANS_LOG.md](./14_CHAT_PLANS_LOG.md)

Их роль:

- `NextStepsPlan` — направление и крупные блоки;
- `TODO` — текущие рабочие и инженерные задачи;
- `Wishlist` — желаемые улучшения;
- `AI Wishlist Omnibus` — AI-friendly digest внешнего контекста, который не имеет права переопределять канон.

## Что считать архивом

Архивом, а не каноном, считать:

- `TODO_MASTER_*`
- `WISHLIST_MASTER_*`
- `TODO_WISHLIST_R31*_ADDENDUM_*`
- `docs/consolidated/*`
- `docs/context/WISHLIST*`
- `docs/_legacy_DOCS_upper/*`
- старые release notes и historical addendum-файлы, если они не переопределены активным TODO/Wishlist

Использовать их можно:

- для поиска утраченных решений;
- для понимания эволюции требований;
- для сверки происхождения feature request;
- для восстановления контекста старых релизов.

Но нельзя использовать их как единственный источник для новых ключей, новых alias-правил или новых контрактов.

## Рекомендуемый порядок чтения перед новой задачей

### Минимальный старт

1. [00_READ_FIRST__ABSOLUTE_LAW.md](../00_READ_FIRST__ABSOLUTE_LAW.md)
2. [01_PARAMETER_REGISTRY.md](../01_PARAMETER_REGISTRY.md)
3. [DATA_CONTRACT_UNIFIED_KEYS.md](../DATA_CONTRACT_UNIFIED_KEYS.md)
4. этот файл

### Если задача затрагивает требования и roadmap

5. [docs/PROJECT_SOURCES.md](./PROJECT_SOURCES.md)
6. [docs/01_RequirementsFromContext.md](./01_RequirementsFromContext.md)
7. [docs/10_NextStepsPlan.md](./10_NextStepsPlan.md)
8. [docs/11_TODO.md](./11_TODO.md)
9. [docs/12_Wishlist.md](./12_Wishlist.md)
10. [docs/13_CHAT_REQUIREMENTS_LOG.md](./13_CHAT_REQUIREMENTS_LOG.md)
11. [docs/14_CHAT_PLANS_LOG.md](./14_CHAT_PLANS_LOG.md)

### Если задача AI/bootstrap или большой merge

12. [docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md](./12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md)
13. [AI_INTEGRATION_PLAYBOOK.yaml](../AI_INTEGRATION_PLAYBOOK.yaml)

### Если задача затрагивает runtime/exports/contracts

14. relevant `*contract*.py`, registries и contract tests

## Короткий operational summary

Для практической работы можно опираться на следующий сжатый набор правил:

1. Канон важнее истории.
2. Контракт важнее convenience alias.
3. Экспорт и viewer должны честно показывать authored/model data.
4. Drift между слоями надо исправлять в contract boundary, а не замазывать UI.
5. Новый функционал должен подкрепляться tests и, при необходимости, registry update.
6. GUI является основным направлением развития операторских сценариев.
7. WEB используется как reference до полного переноса функциональности.

## Статус документа

Этот файл является синтезирующей картой знаний и навигацией по источникам.

Он должен обновляться, когда:

- меняется канон источников;
- появляется новый рабочий backlog-слой;
- меняется приоритет GUI/WEB направления;
- добавляется новый существенный contract layer.
