# Connector-Reconciled GUI/TZ Spec v32

Этот слой фиксирует выжимку из локального архива
`C:/Users/Admin/Downloads/pneumo_codex_tz_spec_connector_reconciled_v32.zip`.
Raw `.zip` в репозиторий не добавляется; этот файл служит knowledge-base
entrypoint и картой чтения для будущих задач.

## Роль слоя

- Package ID: `PNEUMO-CODEX-TZ-SPEC-CONNECTOR-RECONCILED-V32`.
- Дата package: `2026-04-16`.
- Архив self-contained и connector-reconciled.
- Внутри 325 файлов, 12 workspaces, 61 screen catalog rows, 704 UI element rows,
  488 parameter rows, 45 requirements rows и 45 acceptance rows.
- Слой уточняет GUI/TZ knowledge base, но после `v33` используется как previous
  workstream/gate-extract layer; он не заменяет абсолютный закон, parameter
  registry, data contract и human-readable canon `17/18`.

Практически: для новых GUI-first задач сначала читать `17` и `18`, затем
`v33_connector_reconciled`, а этот digest v32 использовать для
`PARALLEL_CHAT_WORKSTREAMS.md`, release-gate extracts и open-gap evidence map.

Связанные рабочие документы:

- [COMPLETENESS_ASSESSMENT.md](./COMPLETENESS_ASSESSMENT.md) - проверка
  полноты и достаточности архива v32;
- [PARALLEL_CHAT_WORKSTREAMS.md](./PARALLEL_CHAT_WORKSTREAMS.md) - разбиение
  дальнейшей работы на независимые параллельные чаты.
- [RELEASE_GATE_ACCEPTANCE_MAP.md](./RELEASE_GATE_ACCEPTANCE_MAP.md) -
  repo-side карта release hardening, open gaps и required evidence для
  `V32-16`.
- [RELEASE_GATE_HARDENING_MATRIX.csv](./RELEASE_GATE_HARDENING_MATRIX.csv) и
  [GAP_TO_EVIDENCE_ACTION_MAP.csv](./GAP_TO_EVIDENCE_ACTION_MAP.csv) -
  checked-in extracts из v32 для docs/tests/helpers. Остальные матрицы остаются
  archive-only reference внутри ZIP.
- [PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md](./PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md) -
  producer/animator truth evidence note для `PB-001 / RGH-001 / RGH-002 /
  RGH-003 / RGH-018 / OG-001 / OG-002`.
- [COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md](./COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md) -
  compare/objective integrity evidence note для `PB-007 / PB-008 /
  RGH-013 / RGH-014 / RGH-015`.
- [GEOMETRY_REFERENCE_EVIDENCE_NOTE.md](./GEOMETRY_REFERENCE_EVIDENCE_NOTE.md) -
  geometry reference evidence note для `PB-001 / PB-008 / RGH-018 /
  OG-001 / OG-002 / OG-006`.
- [DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md](./DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md) -
  runtime evidence note для `PB-002 / RGH-006 / RGH-007 / RGH-016`.
- [RUNTIME_RELEASE_EVIDENCE_NOTE.md](./RUNTIME_RELEASE_EVIDENCE_NOTE.md) -
  runtime hard-gate note для `PB-006 / RGH-011 / RGH-012 / RGH-019 /
  OG-003 / OG-004`.
- [WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md](./WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md) -
  repo evidence note для frozen `WS-INPUTS -> WS-RING -> WS-SUITE ->
  WS-BASELINE` handoff refs/hashes (`HO-002...HO-005`).

## Primary Reading Order из архива

1. `README_PROVENANCE.md`
2. `TECHNICAL_SPECIFICATION.md`
3. `GUI_SPEC.yaml`
4. `ACCEPTANCE_PLAYBOOK_INDEX.csv`
5. [RELEASE_GATE_HARDENING_MATRIX.csv](./RELEASE_GATE_HARDENING_MATRIX.csv)
6. `RUNTIME_ARTIFACT_SCHEMA.yaml`
7. `EVIDENCE_REQUIRED_BY_GATE.csv`
8. [GAP_TO_EVIDENCE_ACTION_MAP.csv](./GAP_TO_EVIDENCE_ACTION_MAP.csv)
9. `NEXT_STEP_DELTA_V32.md`

## Source Priority из `GUI_SPEC.yaml`

1. текущее каноническое задание;
2. прямые уточнения пользователя в текущем чате;
3. локальный канон проекта в GitHub;
4. фактический код и существующий Web UI;
5. imported и historical слои;
6. внешние best practices.

## Core Decisions

- Целью является native Windows desktop engineering software на Qt6/PySide6,
  а не новая web-first реализация.
- Shell обязан быть document-first / viewport-first: верхнее меню, command
  search, левое дерево, центральная рабочая область, правый inspector/help и
  нижняя status/progress/messages strip.
- Пользовательская модель начинается с проекта, а не с внутренних JSON/CSV.
- `WS-INPUTS` является единственным editable source-of-truth для model inputs
  до handoff.
- `WS-RING` является единственным editable source-of-truth для дороги и
  циклического сценария.
- Downstream workspaces потребляют frozen contracts, refs, hashes и lineage,
  а не редактируют чужие master copies.
- Длительные операции всегда показывают progress на текущем экране.
- Команда `Собрать диагностику` остается always-visible first-class action.
- Потеря существующей функциональности при web -> desktop migration запрещена.

## Workspaces

V32 объявляет 12 рабочих областей:

- `WS-SHELL` - глобальный shell;
- `WS-PROJECT` - панель проекта;
- `WS-INPUTS` - исходные данные;
- `WS-RING` - редактор циклического сценария;
- `WS-SUITE` - набор испытаний;
- `WS-BASELINE` - базовый прогон;
- `WS-OPTIMIZATION` - оптимизация;
- `WS-ANALYSIS` - анализ результатов;
- `WS-ANIMATOR` - анимация;
- `WS-DIAGNOSTICS` - диагностика;
- `WS-SETTINGS` - параметры / настройки;
- `WS-TOOLS` - инструменты.

Главный pipeline: `WS-PROJECT -> WS-INPUTS -> WS-RING -> WS-SUITE ->
WS-BASELINE -> WS-OPTIMIZATION -> WS-ANALYSIS -> WS-ANIMATOR ->
WS-DIAGNOSTICS` с возвратом к корректировке inputs/ring по результатам.

## Truth And Graphics Policy

Graphics truth states из v32:

- `solver_confirmed`;
- `source_data_confirmed`;
- `approximate_inferred_with_warning`;
- `unavailable`.

Для цилиндров full-truth body/rod/piston разрешен только при complete packaging
passport. Если passport неполный, действует `axis-only honesty mode`.

Запрещено:

- скрывать incomplete truth красивой графикой;
- рисовать scenario как геометрическое кольцо;
- трактовать `разгон/торможение` как тип дорожного покрытия;
- плодить второй source-of-truth для сценариев, input master или результатов;
- объявлять runtime closure без runtime artifacts/evidence.

## Key Matrices And Playbooks

На уровне архива v32 ключевыми считаются:

- `SOURCE_AUTHORITY_MATRIX.csv` - порядок авторитетности источников;
- `REQUIREMENTS_MATRIX.csv` и `ACCEPTANCE_MATRIX.csv` - 45 requirements и
  45 acceptance rows;
- `SCREEN_CATALOG.csv`, `UI_ELEMENT_CATALOG.csv`, `PARAMETER_CATALOG.csv` -
  каталоги экранов, элементов и параметров;
- `WORKSPACE_CONTRACT_MATRIX.csv`, `WORKSPACE_DEPENDENCY_MATRIX.csv`,
  `WORKSPACE_HANDOFF_MATRIX.csv` - контракты рабочих областей и handoff;
- `DESKTOP_WEB_PARITY_RECONCILIATION.csv` - сохранение parity при миграции;
- `CURRENT_HISTORICAL_STALE_POLICY.csv` - current/historical/stale политика;
- `SCENARIO_LINEAGE_ENFORCEMENT_MATRIX.csv` - lineage сценариев;
- `DIAGNOSTICS_EVIDENCE_MANIFEST_MATRIX.csv` и
  `BUNDLE_EVIDENCE_EXPECTED_CONTENTS.csv` - диагностика и send-bundle evidence;
- `RELEASE_GATE_MATRIX.csv`, `RELEASE_GATE_HARDENING_MATRIX.csv`,
  `EVIDENCE_REQUIRED_BY_GATE.csv` - release gates и required evidence;
- `RUNTIME_ARTIFACT_SCHEMA.yaml` - схема runtime artifacts/provenance;
- `GAP_TO_EVIDENCE_ACTION_MAP.csv` - связка open gap -> next evidence action.

В репозитории дополнительно закреплены локальные проверяемые extracts:

- [RELEASE_GATE_HARDENING_MATRIX.csv](./RELEASE_GATE_HARDENING_MATRIX.csv) -
  20 release hardening rows `RGH-001...RGH-020`;
- [GAP_TO_EVIDENCE_ACTION_MAP.csv](./GAP_TO_EVIDENCE_ACTION_MAP.csv) -
  6 open gap -> evidence action rows `OG-001...OG-006`;
- [RELEASE_GATE_ACCEPTANCE_MAP.md](./RELEASE_GATE_ACCEPTANCE_MAP.md) -
  человекочитаемая карта для release-gate/acceptance/docs-contract работ.

Эти extracts нужны для локальных docs/tests/helpers. Они не заменяют полный
archive-only слой `ACCEPTANCE_MATRIX.csv`, `EVIDENCE_REQUIRED_BY_GATE.csv`,
`SOURCE_AUTHORITY_MATRIX.csv` и `RUNTIME_ARTIFACT_SCHEMA.yaml`.

Acceptance playbooks:

- `PLAYBOOK_PRODUCER_TRUTH.md`;
- `PLAYBOOK_DIAGNOSTICS_BUNDLE.md`;
- `PLAYBOOK_PARITY_AND_MIGRATION.md`;
- `PLAYBOOK_SCENARIO_CANON.md`;
- `PLAYBOOK_WINDOWS_RUNTIME.md`;
- `PLAYBOOK_PERFORMANCE_TRACE.md`;
- `PLAYBOOK_OBJECTIVE_CONTRACT.md`.

## Integrated Workspace Annexes

Архив включает imported workspace annexes:

- `WS_RING_V13`;
- `WS_SUITE_V14`;
- `WS_BASELINE_V15`;
- `WS_OPTIMIZATION_V16`;
- `WS_ANALYSIS_V17`;
- `WS_ANIMATOR_V18`;
- `WS_DIAGNOSTICS_V19`;
- `WS_SHELL_V20`;
- `WS_PROJECT_INPUTS_V21`;
- `WS_RING_SUITE_RECON_V22`;
- `WS_DOWNSTREAM_LINEAGE_V23`;
- `WS_COMPARE_DIAG_V24`;
- `WS_SCENARIO_SOURCE_V25`;
- `WS_SCENARIO_ENFORCEMENT_V26`.

Эти annexes использовать как detailed implementation planning material, но не
как разрешение нарушать локальный канон `17/18` или contracts/tests.

## Open Gaps Preserved By v32

V32 не объявляет runtime closure. Открытыми или частично закрытыми остаются:

- `GAP-001` / `OG-001`: producer-side hardpoints / solver_points truth closure;
- `GAP-002` / `OG-002`: cylinder packaging passport completion;
- `GAP-003` / `OG-003`: measured browser performance trace evidence;
- `GAP-004` / `OG-004`: viewport gating runtime proof;
- `GAP-005`: ring seam / full-ring summary correctness;
- `GAP-006`: geometry acceptance runtime proof;
- `GAP-007`: `default_base.json` cleanup / duplicate canon cleanup;
- `GAP-008`: `road_width_m` canonicalization;
- `GAP-009` / `OG-006`: imported layer runtime proof;
- `GAP-010` / `OG-005`: Windows visual acceptance for animator and compare.

Repo-side evidence now covers the narrow `WS-RING -> WS-SUITE` slice of
`GAP-005`: canonical Ring export metadata, `segment_id` road CSV, unfolded
preview/no-hidden-closure behavior and `HO-004` Suite stale detection are
checked by the Ring/Suite tests. This is not a claim that the wider runtime
gaps are closed.

Repo-side evidence also covers the narrow frozen input handoff chain from
`WS-INPUTS` through `WS-RING`, `WS-SUITE` and `WS-BASELINE`: canonical
`inputs_snapshot.json`, read-only downstream refs, stale/missing/invalid
banners and hash preservation are checked by desktop input/ring/suite tests.
See [WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md](./WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md).
This is not a solver/runtime closure claim.

Repo-side evidence now covers a narrow `WS-ANALYSIS -> Compare Viewer`
current-context handoff: Results Center may emit readonly
`latest_compare_current_context.json`, Compare Viewer accepts it only through
`--current-context` / `CompareSession.current_context_ref`, preserves
`current_context_path`, surfaces `ready/missing/session` source status in
`dock_compare_contract`, and exports the provenance in `compare_contract.json`.
This is not optimizer history ownership and not animator truth replacement.

Следующий правильный шаг по `NEXT_STEP_DELTA_V32`: не новый summary, а closure
на живых runtime artifacts:

- producer-side truth по `hardpoints / solver_points / cylinder packaging`;
- measured performance evidence по trace / viewport gating / animator frame
  budget;
- Windows runtime evidence pack по snap / DPI / second monitor / path budget /
  docking.

## Conflict Policy

- При конфликте между v32 и локальным repo canon приоритет у
  `00_READ_FIRST__ABSOLUTE_LAW.md`, `01_PARAMETER_REGISTRY.md`,
  `DATA_CONTRACT_UNIFIED_KEYS.md`, затем `17/18`.
- При конфликте между v32 и старым web behavior функция не теряется, но
  целевой UX переносится в desktop GUI.
- При конфликте между v32 и historical imports `v1...v13` v32 использовать как
  более новый connector-reconciled contract layer, пока он не спорит с `17/18`.
