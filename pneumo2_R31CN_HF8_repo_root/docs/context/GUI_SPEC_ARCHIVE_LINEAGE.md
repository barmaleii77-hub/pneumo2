# GUI-Spec Archive Lineage PROMPT_V2 + v1–v13 + v37

Этот документ фиксирует, как upstream prompt source `PROMPT_V2` и серия
архивов `v1…v13`, а также successor supplement `v37`, влияют на текущий
GUI-spec проекта и какие из них считаются active, historical, recovery или
knowledge-base слоями.

## Как читать lineage

- `PROMPT_V2` — pre-`v1` upstream prompt source, который задаёт исходный
  native Windows, no-web-first и no-feature-loss intent.
- `v1–v5` — design-first эволюция машиночитаемого GUI-spec.
- `v6–v11` — implementation-oriented passes: от экранного implementation
  planning до bootstrap, fill-in, interaction pass, backend adapters и
  execution wiring.
- `v12` — design-recovery слой, который сохраняет историю и возвращает проект
  в правильную каноническую ветку.
- `v13` — специализированный design addendum для `WS-RING` и handoff
  `WS-RING -> WS-SUITE`.
- `v37` — import-ready GitHub KB/TZ/spec supplement. Он поднимает
  consolidated technical specification, workspace/parameter/acceptance
  matrices и open gaps в repo-local knowledge-base layer, но не является
  runtime-closure proof.

## Версии

### PROMPT_V2

- Роль: upstream foundational prompt source до серии архивов `v1…v13`.
- Ключевой артефакт:
  `prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md`.
- Что фиксирует:
  native Windows desktop как целевую архитектуру,
  запрет web-first и feature-loss migration,
  diagnostics как first-class surface,
  ring editor как single source of truth,
  honest graphics и обязательные help/tooltip/unit rules.
- Статус: foundational provenance layer в
  `docs/context/gui_spec_imports/foundations/`.

### v1

- Роль: стартовый machine-readable GUI-spec.
- Ключевые артефакты: `pneumo_gui_codex_spec_v1.json`,
  `current_pipeline.dot`, `optimized_pipeline.dot`.
- Статус: historical import, уже хранится в `docs/context/gui_spec_imports/`.

### v2

- Роль: первый подробный detailed reference layer.
- Что добавил: macro/element graphs, catalogs полей/help/tooltip,
  migration matrix, acceptance и pipeline verification.
- Статус: historical detailed import в
  `docs/context/gui_spec_imports/v2/`.

### v3

- Роль: текущий active detailed machine-readable reference layer.
- Что добавил: source-of-truth matrix, keyboard/docking/ui-state matrices,
  pipeline observability и refined shell contract.
- Статус: active layer в `docs/context/gui_spec_imports/v3/`.

### v4

- Роль: ultra-design expansion.
- Что добавил: user step graphs, dialog catalog, screen blueprints, expanded
  shell/title bar/splitter/scrollbar contracts, richer state machine и visual
  verification.
- Статус: historical archive, используется как lineage knowledge, но не как
  active import-layer.

### v5

- Роль: master design layer после `v4`.
- Что добавил: archive evidence index, command search synonyms, microcopy,
  cognitive ergonomics, validation rules, graphics truth matrix, units labels,
  screen element positions и другие detailed matrices.
- Статус: historical archive; важен как родитель для `v12` и `v13`.

### v6

- Роль: implementation pass.
- Что добавил: workspace implementation packets, component library,
  viewmodel/event/command contracts и codex work orders.
- Статус: historical implementation archive; не должен подменять design canon.

### v7

- Роль: bootstrap source skeleton.
- Что добавил: стартовый PySide6/Qt6 shell scaffold, workspace registry,
  automation/help anchors и degraded-truth registry.
- Статус: historical implementation archive.

### v8

- Роль: fill-in поверх bootstrap.
- Что добавил: seeded workspaces, service hub, command registry, local test
  matrix и section-based views.
- Статус: historical implementation archive.

### v9

- Роль: interaction pass.
- Что добавил по смыслу линейки: screen-by-screen interactions и richer
  component usage.
- Примечание: присланный архив содержит шумные `pytest cache` файлы и не
  годится как чистый imported source layer.
- Статус: historical implementation archive, учитывается через lineage.

### v10

- Роль: backend adapter pass.
- Что добавил: реальные файлово-контрактные backend adapters для baseline,
  optimization, diagnostics, ring source-of-truth и producer-side truth.
- Статус: historical implementation archive.

### v11

- Роль: execution wiring pass.
- Что добавил по смыслу линейки: execution wiring поверх interactive shell.
- Примечание: присланные копии архива также содержат шумный `pytest cache`
  вместо чистого README, поэтому используются только как lineage evidence.
- Статус: historical implementation archive.

### v12

- Роль: preservation and design recovery.
- Что добавил: artifact lineage, continuation decision, workspace delta,
  ring-editor canonical contract, optimization control plane contract и
  truthful graphics contract.
- Статус: historical design-recovery layer, импортирован в
  `docs/context/gui_spec_imports/v12_design_recovery/`.

### v13

- Роль: специализированный ring-editor migration addendum.
- Что добавил: schema contract, screen blueprints, element/field catalogs,
  state machine, user pipeline, acceptance gates, ring-level migration matrix и
  handoff contract `WS-RING -> WS-SUITE`.
- Статус: specialized addendum в
  `docs/context/gui_spec_imports/v13_ring_editor_migration/`.

### v37

- Роль: successor GitHub knowledge-base supplement и TZ/spec connector.
- Архив: `pneumo_codex_tz_spec_connector_reconciled_v37_github_kb_supplement.zip`.
- Что добавил: import-ready subtree для
  `docs/context/gui_spec_imports/v37_github_kb_supplement/`,
  `TECHNICAL_SPECIFICATION.md`, `GUI_SPEC.yaml`, workspace contract matrix,
  parameter catalogs, requirements/acceptance matrices, repo canon alignment,
  maintainer checklist и список gaps, которые должны оставаться открытыми.
- Статус: successor KB supplement в
  `docs/context/gui_spec_imports/v37_github_kb_supplement/`.
- Ограничение: слой reference-first и не объявляет producer-side truth,
  measured perf trace или Windows runtime acceptance закрытыми без отдельного
  evidence layer.

## Итоговый приоритет

1. `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
2. `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
3. `docs/context/gui_spec_imports/foundations/*`
4. `docs/context/gui_spec_imports/v37_github_kb_supplement/*`
5. `docs/context/gui_spec_imports/v3/*`
6. `docs/context/gui_spec_imports/v13_ring_editor_migration/*` для `WS-RING`
   и ring-to-suite handoff
7. `docs/context/gui_spec_imports/v12_design_recovery/*`
8. lineage `PROMPT_V2 + v1…v13 + v37`
9. прочие historical imports и implementation archives

## Практическое правило

- Для текущих GUI-задач сначала опираемся на `17`, `18`, `foundations`,
  `v37` как KB/TZ/spec supplement и затем `v3`.
- Для ring editor и suite handoff обязательно добавляем `v13`.
- Для requirements, параметров, workspace coverage, acceptance и open gaps
  обязательно сверяемся с `v37`, но не выдаём его за runtime acceptance.
- Для спорных вопросов о происхождении канона, design/recovery decisions и
  границе между design и implementation-pass читаем `v12` и lineage
  `PROMPT_V2 + v1…v13 + v37`.

## Связанный connector-reconciled слой V32

После этой lineage-цепочки добавлен отдельный knowledge-base слой
`docs/context/gui_spec_imports/v32_connector_reconciled/README.md` из архива
`pneumo_codex_tz_spec_connector_reconciled_v32.zip`.

V32 не является очередным imported implementation pass в линии `v1…v13`.
Его роль другая: собрать connector-reconciled GUI/TZ package с source authority,
workspace contracts, acceptance playbooks, release gates, runtime artifact
schema, evidence policy и open gaps. Поэтому для новых задач V32 читается после
`17/18` как актуальный digest, а этот lineage-документ остается картой
происхождения старых слоев.
