# TECHNICAL_SPECIFICATION

## Package status V38 actualized with V10
Этот документ входит в successor repo-adoption / commit-ready package V38, актуализированный с учётом report-only слоя V10 по иерархии launcher-shell. Исторические упоминания `v30`, `V32`, `V33` ниже относятся к lineage и provenance. Пакет не заявляет runtime-closure proof без отдельного runtime evidence слоя.


## 0. Repo adoption layer
V38 не меняет продуктовый канон `17/18`, а переводит consolidated spec в commit-ready successor layer для GitHub knowledge base.

## 1. Назначение
Подготовить recipient-neutral ТЗ и машиночитаемую спецификацию для реализации инженерного Windows desktop GUI проекта `Пневмоподвеска` в CODEX.

Пакет описывает **целевое настольное приложение**, а не текущую web-реализацию, и сохраняет обязательное правило:
- не терять функции при web -> desktop migration;
- не подменять truth-contract красивой графикой;
- не плодить вторые источники истины;
- не заставлять CODEX заново исследовать проект вместо реализации.

## 2. Базовые принципы
1. Приложение проектируется как **native Windows desktop engineering software**.
2. Shell обязан быть **document-first / viewport-first**.
3. Пользовательская модель начинается с **проекта**, а не с внутренних JSON/CSV.
4. Единственный editable source-of-truth для сценариев — **Редактор циклического сценария**.
5. Единственный editable source-of-truth для model inputs до handoff — **WS-INPUTS**.
6. Downstream workspaces потребляют только frozen contracts, refs, hashes и lineage.
7. Для graphics truth обязательны состояния:
   - `solver_confirmed`
   - `source_data_confirmed`
   - `approximate_inferred_with_warning`
   - `unavailable`
8. Для цилиндров full-truth body/rod/piston разрешён только при complete packaging passport; иначе действует `axis-only honesty mode`.
9. Длительные операции всегда показывают progress на текущем экране.
10. Команда **«Собрать диагностику»** остаётся always-visible first-class action.

## 3. Архитектура shell
### 3.1 Главное окно
Главное окно — `WIN-MAIN-SHELL`.
Оно содержит:
- классическое верхнее меню;
- command search;
- левую dockable tree/navigation pane;
- центральную рабочую область;
- правый context-sensitive inspector/help/provenance pane;
- нижнюю status/progress/messages strip.



### 3.1.a Launcher hierarchy and first 15 minutes rule
Стартовая shell-поверхность обязана показывать **один доминирующий маршрут**, а не каталог почти равноправных дверей.

Доминирующий стартовый маршрут:
1. Исходные данные
2. Редактор кольца / сценариев
3. Набор испытаний
4. Базовый прогон
5. Оптимизация
6. Анализ результатов
7. Анимация
8. Диагностика

Launcher-shell обязан различать:
- **primary workspaces**: Inputs, Ring, Suite, Baseline, Optimization, Analysis, Diagnostics;
- **specialized route-bound surface**: Desktop Animator;
- **advanced surfaces**: Compare Viewer, Desktop Mnemo, Инструменты.

Команда отправки результатов не является отдельным стартовым направлением. Это второе действие внутри Diagnostics после готового bundle.
Embedded compare внутри Analysis остаётся primary compare-route; Compare Viewer открывается как расширенный режим из Analysis.

### 3.2 Специализированные окна
Сохраняются как specialized top-level surfaces, но не равны по launcher-priority:
- `Desktop Animator` — route-bound specialized surface после Analysis
- `Compare Viewer` — advanced compare surface из Analysis
- `Desktop Mnemo` — advanced engineering surface из Analysis/Tools
- `Диагностика` — first-class terminal workspace с одной заметной командой

### 3.3 Layout profiles
Поддерживаются layout profiles:
- wide
- standard
- compact
- narrow
- micro
- dual-monitor animator

### 3.4 Windows platform contract
Обязательны:
- стандартная строка заголовка и system menu;
- drag/maximize/snap behavior;
- mixed-DPI;
- docking/floating/auto-hide;
- second-monitor workflow;
- layout save/restore;
- keyboard-first and accessibility-first behavior.

## 4. Главный pipeline
Оптимизированный pipeline:
1. `WS-PROJECT`
2. `WS-INPUTS`
3. `WS-RING`
4. `WS-SUITE`
5. `WS-BASELINE`
6. `WS-OPTIMIZATION`
7. `WS-ANALYSIS`
8. `WS-ANIMATOR`
9. `WS-DIAGNOSTICS`
10. возврат к корректировке inputs/ring по результатам

Смысл pipeline:
- `WS-PROJECT` показывает состояние проекта и next action;
- `WS-INPUTS` редактирует canonical model input master copy;
- `WS-RING` редактирует canonical cyclic scenario;
- `WS-SUITE` собирает validated suite snapshot без владения геометрией;
- `WS-BASELINE` создаёт active baseline contract;
- `WS-OPTIMIZATION` запускает один активный режим optimization;
- `WS-ANALYSIS` работает только от frozen selected run context;
- `WS-ANIMATOR` показывает truthful graphics от analysis context;
- `WS-DIAGNOSTICS` собирает evidence manifest и SEND bundle.

## 5. Проект как user-facing truth
Проект должен хранить:
- варианты исходных данных;
- сценарии;
- validated suite snapshots;
- baseline contracts;
- optimization run contracts;
- analysis compare contexts;
- animator contexts/captures;
- diagnostics bundles;
- derived export artifacts.

Global archive допустим только как optional warm-start/resume layer и не может подменять user-facing truth текущего проекта.

## 6. Входные данные и visual twins
### 6.1 WS-PROJECT
Стартовый экран проекта:
- показывает project health;
- блокеры;
- recent activity;
- next action;
- **видимый dominant route по pipeline**;
- быстрые переходы по pipeline без конкуренции secondary surfaces.

### 6.2 WS-INPUTS
Единственная editable-поверхность для model inputs.

Обязательные группы:
- project meta;
- frame geometry;
- masses & inertia;
- cylinders;
- springs;
- pneumatics;
- numerics;
- flags & modes.

У каждой группы есть графический двойник:
- геометрия рамы/подвески;
- схема цилиндров;
- графика диапазонов;
- пневмосхема/мнемосхема;
- профиль дороги/движения;
- статическая посадка и mid-stroke preview;
- ограничения и зазоры при необходимости.

Число и графика синхронизированы двусторонне.

## 7. Циклический сценарий и дорога
### 7.1 Единственный источник
`WS-RING` является единственным editable source-of-truth для дороги и маршрута движения.

### 7.2 Канон сегментов
- Сегмент 0 задаёт начало и конец.
- Сегменты 1..N-1 задают только конец.
- Последний сегмент логически замыкается на начало сегмента 0, но кольцо нигде не рисуется как геометрическая петля.

### 7.3 Геометрический контракт сегмента
Обязательные поля:
- stable `segment_id`
- имя
- покрытие/тип профиля
- длина
- продольная геометрия
- поперечный уклон
- явное направление: `прямо`, `влево`, `вправо`
- режим прохождения
- комментарий/заметки

### 7.4 What is forbidden
- нельзя рисовать scenario как геометрическое кольцо;
- нельзя трактовать `разгон/торможение` как тип дорожного сегмента;
- нельзя задавать левую/правую высоты как независимый first-class ввод вместо одного поля поперечного уклона.

## 8. Матрица испытаний
`WS-SUITE`:
- потребляет refs и export set из `WS-RING`;
- не владеет геометрией сценария;
- хранит только allowed row-overrides:
  - enabled
  - stage entry
  - priority
  - dt
  - t_end
  - test-specific params/targets
- выдаёт `validated_suite_snapshot.json`.

## 9. Baseline
`WS-BASELINE`:
- читает только `validated_suite_snapshot.json`;
- формирует `active_baseline_contract.json`;
- поддерживает policy modes:
  - `frozen_manual`
  - `review_before_replace`
  - `auto_update_best`
- отделяет active baseline от baseline history.

## 10. Optimization
`WS-OPTIMIZATION`:
- потребляет `active_baseline_contract.json` + `objective_contract.json`;
- поддерживает два режима:
  - `StageRunner`
  - `distributed coordinator`
- но в конкретный момент времени активен только один.

First-class runtime contract обязан показывать:
- objective stack;
- hard gate;
- source baseline;
- run identity;
- stage policy;
- current stage;
- live rows;
- underfill;
- gate reasons;
- warm-start provenance;
- distributed resource state, если он используется.

## 11. Analysis
`WS-ANALYSIS`:
- работает только от selected frozen run contract;
- сравнивает baseline/run/run через explicit compare contract;
- никогда не читает live runtime-state как источник истины;
- умеет report export с provenance manifest.

## 12. Animator
`WS-ANIMATOR`:
- открывается только по explicit analysis context;
- не rebindится молча к текущему проекту/сценарию;
- умеет overlays, compare и playback только в границах truthful graphics contract;
- поддерживает `solver_confirmed`, `source_data_confirmed`, `approximate_inferred_with_warning`, `unavailable`.

### 12.1 Cylinder rule
- full-truth cylinder body/rod/piston только при complete packaging passport;
- иначе `axis-only honesty mode` + warning;
- packaging gap обязан быть видимым и диагностируемым.

## 13. Diagnostics
`WS-DIAGNOSTICS`:
- first-class рабочая поверхность;
- intake only from explicit evidence manifest;
- one visible action: **«Собрать диагностику»**;
- preview bundle contents;
- health summary;
- selfcheck;
- latest ZIP + SHA256 + freshness;
- interpreter provenance;
- manual collect / auto-exit / crash guard как единый bundle lifecycle contract.

## 14. Пневматика и визуальные семантики
Обязательна не только табличная, но и графическая форма:
- пневмосхема/мнемосхема;
- направление потока стрелками;
- давление цветом;
- расход толщиной/скоростью/насыщенностью;
- discrete state отдельным индикатором;
- ресиверы — числом и visual fill level.

Ни один графический кодировочный канал не используется без легенды и единиц измерения.

## 15. Parameter canon
В package составлен полный user-facing параметрический канон:
- `PARAMETER_CATALOG.csv`
- `PARAMETER_GROUPS.csv`
- `PARAMETER_RELATIONS.csv`
- `PARAMETER_VISIBILITY_MATRIX.csv`
- `PARAMETER_PIPELINE_MATRIX.csv`

В каталог включены:
- прямо редактируемые поля;
- read-only outputs;
- derived values;
- visual-only perceived parameters;
- logical flags;
- ranges;
- hashes, provenance and identities, если пользователь их видит.

## 16. Help, units and text
- У каждого значимого поля, кнопки, графика, warning и column header есть tooltip и expanded help.
- Обозначения без названия запрещены.
- Значения без единиц измерения запрещены там, где единица применима.
- Tooltip/help не может быть единственным носителем смысла экрана.

## 17. Backlog reconciliation
Все найденные backlog items из repo TODO/Wishlist и attached layers прошли reconciliation.
Итог статусов отражён в:
- `DISCOVERED_BACKLOG_SOURCES.csv`
- `WISHLIST_TODO_RECONCILIATION.csv`
- `CONFLICTS_AND_ASSUMPTIONS.csv`

Ключевые P0, оставленные открытыми:
- browser performance trace and measurable acceptance;
- complete `hardpoints / solver_points` producer-side truth;
- complete cylinder packaging passport;
- финальное runtime evidence по Windows visual acceptance;
- cleanup duplicate base canon values.

## 18. External library policy
Использование зрелых внешних библиотек разрешено и требуется, если оно оправдано:
- Qt6 / PySide6 — shell;
- PyOpenGL_accelerate — Windows animator runtime dependency;
- Dask / Ray — distributed optimization;
- BoTorch — advanced proposer/qNEHVI.

Для каждой библиотеки в package зафиксированы:
- назначение;
- причина выбора;
- ограничения;
- fallback strategy.

## 19. Acceptance and lint
Для каждого требования есть:
- `REQ-*`
- минимум один `ACC-*`
- минимум один `TST-*`

Структурный lint пакета проверяет:
- отсутствие orphan IDs;
- отсутствие скрытых duplicate semantics;
- отсутствие неразрешённых cross references;
- отсутствие необоснованных placeholders;
- отсутствие обязательных сущностей без статуса.

## 20. Что остаётся открытым
Этот package сознательно не утверждает runtime closure там, где evidence явно отсутствует.
Именно поэтому `covered_partially` и `gap` сохранены в matrices и lint, а не скрыты.

## 21. Использование пакета в CODEX
1. CODEX читает `README_PROVENANCE.md`.
2. Затем `TECHNICAL_SPECIFICATION.md`.
3. Затем `GUI_SPEC.yaml`.
4. Затем каталоги и матрицы.
5. CODEX реализует GUI по пакету, **не повторяя discovery проекта с нуля**.


## 14. Источники авторитета и reconciliation
### 14.1 Порядок авторитета
1. Канонический prompt текущего шага.
2. Прямые уточнения пользователя в текущем чате.
3. Локальный канон проекта в GitHub:
   - `00_READ_FIRST__ABSOLUTE_LAW.md`
   - `01_PARAMETER_REGISTRY.md`
   - `DATA_CONTRACT_UNIFIED_KEYS.md`
   - `docs/PROJECT_SOURCES.md`
   - `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
   - `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
4. Фактический код и существующий Web UI.
5. Imported/historical GUI layers и snapshot-слои как evidence/reference.
6. Внешние best practices как quality-check, но не как замена проектного замысла.

### 14.2 Обязательный source authority layer
Пакет обязан содержать и использовать:
- `SOURCE_AUTHORITY_MATRIX.csv`
- `DISCOVERED_BACKLOG_SOURCES.csv`
- `CONNECTED_SOURCE_RECONCILIATION.md`
- `REPO_EVIDENCE_INDEX.csv`
- `PROMPT_COMPLIANCE_MATRIX.csv`

## 15. Desktop/Web parity как release-gate
### 15.1 Правило
Миграция `web -> desktop` не имеет права терять функции, скрывать их без явной маркировки `В разработке` или вводить второй источник истины вместо канонического рабочего пространства.

### 15.2 Обязательные артефакты parity
- `DESKTOP_WEB_PARITY_RECONCILIATION.csv`
- `WISHLIST_TODO_RECONCILIATION.csv`
- `SCREEN_CATALOG.csv`
- `WINDOW_CATALOG.csv`
- `UI_ELEMENT_CATALOG.csv`

## 16. Graphics truth как отдельный surface-level contract
Для каждой графической surface должен существовать отдельный truth-state contract. Допустимые состояния:
- `solver_confirmed`
- `source_data_confirmed`
- `approximate_inferred_with_warning`
- `unavailable`

Surface-level политика и ограничения фиксируются в `GRAPHICS_TRUTH_SURFACE_MATRIX.csv`.

## 17. Frozen handoff contracts между рабочими пространствами
Каждый переход между рабочими пространствами должен происходить через frozen contract / snapshot / refs+hashes, а не через live mutable state. Это фиксируется отдельной `WORKSPACE_HANDOFF_MATRIX.csv`.

## 18. Открытые gaps, которые пакет не замазывает
Пакет сохраняет как открытые:
- producer-side `hardpoints / solver_points / cylinder packaging` truth closure;
- measured `browser_perf_trace` и `viewport gating` acceptance;
- runtime-proof closure imported/historical layers;
- финальную Windows visual acceptance для всех P0/P1 узлов.

## 19. Порядок чтения пакета для CODEX
Обязательный reader order задаётся файлом `CODEx_CONSUMPTION_ORDER.md`. CODEX должен начинать с provenance, authority, technical spec и только потом переходить к matrices/catalogs/graphs.


## 15. Новые annex-слои v30
### 15.1 Workspace canon consolidation
В этот пакет интегрированы workspace-level canonical annexes из ранее подтверждённых imported GUI layers `v13…v26`. Они больше не лежат вне самодостаточного архива и используются как reference annexes внутри `WORKSPACE_CANON/imported/*`.

### 15.2 Project entity model
Project-bound truth дополнительно нормализован в `PROJECT_ENTITY_MODEL.yaml`, чтобы CODEX не строил продукт вокруг россыпи внутренних JSON/CSV.

### 15.3 Visual semantics and explainability
Дополнительные обязательные артефакты:
- `VISUAL_SEMANTICS_DICTIONARY.csv`
- `HELP_AND_EXPLAINABILITY_MATRIX.csv`
- `GRAPHICS_SURFACE_ACTION_MATRIX.csv`
- `PROJECT_TREE_CONTRACT.csv`

### 15.4 Release-gate expansion
`RELEASE_GATE_MATRIX.csv` фиксирует release-gate слой поверх parity/truth/source-of-truth contract и явно оставляет открытые runtime gaps, которые нельзя маскировать как закрытые.


## 18. Сквозной lifecycle и provenance
Пакет дополнен annex-слоем, который фиксирует:
- зависимости рабочих пространств по frozen contracts;
- жизненный цикл project-bound артефактов;
- единый каталог provenance-полей;
- допустимые действия для каждого graphics truth-state;
- отдельную политику current/historical/stale banner-ов;
- матрицу evidence-классов для диагностики.

Обязательные приложенные annex-файлы:
- `WORKSPACE_DEPENDENCY_MATRIX.csv`
- `ARTIFACT_LIFECYCLE_MATRIX.csv`
- `TRUTH_STATE_ACTION_POLICY.csv`
- `CURRENT_HISTORICAL_STALE_POLICY.csv`
- `PROVENANCE_FIELDS_CATALOG.csv`
- `USER_PROGRESS_SURFACE_MATRIX.csv`
- `DIAGNOSTICS_EVIDENCE_MANIFEST_MATRIX.csv`
- `COMPARE_CONTRACT_MATRIX.csv`
- `SCENARIO_LINEAGE_ENFORCEMENT_MATRIX.csv`
- `PROJECT_RESULTS_STORAGE_MODEL.yaml`

## 19. Фронтир следующего non-code шага
Следующий шаг после этого пакета не должен переходить в кодовую ветку.
Он должен использовать текущий annex-слой как constraint surface для:
- producer-side truth closure (`hardpoints`, `solver_points`, `cylinder packaging`);
- export contract `anim_latest`;
- measured `browser perf trace / viewport gating` acceptance;
- окончательной сверки current/historical bundle-banners.

Это фиксируется файлами:
- `REPO_CANON_PROMPT_TRACE.csv`
- `ATTACHED_CONTEXT_RECONCILIATION.csv`
- `NEXT_STEP_EXECUTION_BRIEF.md`


## 15. Release-gate hardening annex
V32 добавляет machine-readable playbook-слой для closure следующих блоков: producer-side truth, diagnostics bundle, scenario canon, web→desktop parity, Windows runtime shell acceptance, measured performance trace и objective-contract persistence. Эти annexes не подменяют runtime proof, а определяют обязательные evidence и hard-fail/soft-fail semantics.

## V10 actualization note
Этот пакет дополнительно интегрирует report-only findings V10 по launcher-shell hierarchy. См. `V10_ACTUALIZATION_REPORT.md`, `LAUNCHER_HIERARCHY_RECONCILIATION_V10.md` и `V10_RECONCILIATION_MATRIX.csv`.
