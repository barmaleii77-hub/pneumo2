# Источники проекта и контекста

## Канон внутри релиза

1. `00_READ_FIRST__ABSOLUTE_LAW.md` — абсолютный закон проекта.
2. `01_PARAMETER_REGISTRY.md` — единый реестр параметров.
3. `DATA_CONTRACT_UNIFIED_KEYS.md` — единый контракт ключей.
4. `docs/context/PROJECT_CONTEXT_ANALYSIS.md` — локальная сводка контекста.
5. `docs/11_TODO.md` — рабочий TODO-снимок.
6. `docs/12_Wishlist.md` — рабочий wishlist-снимок.

## GUI knowledge stack

### Human-readable canon

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md` — project-wide Windows desktop/CAD baseline.
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md` — project-specific GUI contract для `Пневмоподвески`.

### Imported detailed reference

- `docs/context/gui_spec_imports/README.md` — верхний source note для imported GUI-spec layers.
- `docs/context/gui_spec_imports/v3/README.md` — active detailed reference layer из `pneumo_gui_codex_package_v3.zip`.
- `docs/context/gui_spec_imports/v3/pneumo_gui_codex_spec_v3_refined.json` — главный machine-readable GUI-spec.
- `docs/context/gui_spec_imports/v3/current_macro.dot` — текущий macro workflow graph.
- `docs/context/gui_spec_imports/v3/optimized_macro.dot` — целевой macro workflow graph.
- `docs/context/gui_spec_imports/v3/current_element_graph.dot` — текущий element graph.
- `docs/context/gui_spec_imports/v3/optimized_element_graph.dot` — целевой element graph.
- `docs/context/gui_spec_imports/v3/ui_element_catalog.csv` — catalog UI-элементов.
- `docs/context/gui_spec_imports/v3/field_catalog.csv` — catalog полей.
- `docs/context/gui_spec_imports/v3/help_catalog.csv` — catalog help topics.
- `docs/context/gui_spec_imports/v3/tooltip_catalog.csv` — catalog tooltip topics.
- `docs/context/gui_spec_imports/v3/migration_matrix.csv` — machine-readable migration contract `web -> desktop`.
- `docs/context/gui_spec_imports/v3/source_of_truth_matrix.csv` — matrix источников истины и производных представлений.
- `docs/context/gui_spec_imports/v3/ui_state_matrix.csv` — matrix состояний UI-элементов.
- `docs/context/gui_spec_imports/v3/keyboard_matrix.csv` — keyboard и access-key contract.
- `docs/context/gui_spec_imports/v3/docking_matrix.csv` — docking/floating/second-monitor contract.
- `docs/context/gui_spec_imports/v3/pipeline_observability.csv` — observability contract для GUI pipeline.
- `docs/context/gui_spec_imports/v3/best_practices_sources.csv` — curated external best-practices baseline.
- `docs/context/gui_spec_imports/v3/acceptance_criteria.csv` — acceptance layer.
- `docs/context/gui_spec_imports/v3/pipeline_verification.csv` — pipeline verification layer.
- `docs/context/gui_spec_imports/v3/test_suite.csv` — catalog GUI-spec tests.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/README.md` — специализированный imported addendum для `WS-RING` и ring migration.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/pneumo_gui_codex_spec_v13_ring_editor_migration.json` — главный machine-readable ring-editor migration spec.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_schema_contract_v13.json` — каноническая схема данных кольцевого сценария.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_screen_blueprints_v13.csv` — screen/mode blueprints рабочего пространства `WS-RING`.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_element_catalog_v13.csv` — catalog элементов интерфейса ring editor.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_field_catalog_v13.csv` — catalog полей ring editor.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_state_machine_v13.json` — state machine сценарного контура.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_user_pipeline_v13.dot` — ring-level user pipeline graph.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/web_to_desktop_migration_matrix_v13.csv` — специализированная ring-level migration matrix `web -> desktop`.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_acceptance_gates_v13.csv` — acceptance gates для `WS-RING`.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_to_suite_link_contract_v13.json` — handoff contract `WS-RING -> WS-SUITE`.

### Historical import

- `docs/context/gui_spec_imports/v2/README.md` — historical detailed import из `v2`.
- `docs/context/gui_spec_imports/v2/pneumo_gui_codex_spec_v2_detailed.json` — historical detailed machine-readable spec.
- `docs/context/gui_spec_imports/pneumo_gui_codex_spec_v1.json` — historical machine-readable import из `v1`.
- `docs/context/gui_spec_imports/current_pipeline.dot` — historical current workflow graph.
- `docs/context/gui_spec_imports/optimized_pipeline.dot` — historical optimized workflow graph.

### Parity and migration

- `docs/context/desktop_web_parity_map.json` — machine-readable parity map, синхронизированный с `migration_matrix.csv`.
- `docs/context/DESKTOP_WEB_PARITY_SUMMARY.md` — human-readable summary того же migration/parity contract.

### Lane-level implementation prompts

- `docs/gui_chat_prompts/00_INDEX.md` — entrypoint в lane-level prompt docs.
- `docs/gui_chat_prompts/*` — implementation prompts, которые обязаны ссылаться на `17/18` и active detailed reference.

## Правило приоритета

1. `17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
2. `18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
3. `docs/context/gui_spec_imports/v3/*`
4. `docs/context/gui_spec_imports/v13_ring_editor_migration/*` для `WS-RING` и handoff `WS-RING -> WS-SUITE`
5. older versions в `docs/context/gui_spec_imports/*`
6. `docs/gui_chat_prompts/*`

## Зафиксированные внешние AI snapshots

- `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md` — human-readable выжимка external snapshots от `2026-04-08`.
- `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.json` — машиночитаемый digest той же пары для AI/bootstrap сценариев.
- `docs/context/AI_SNAPSHOT_WORKING_DELTA_2026-04-08.md` — короткая рабочая delta-заметка.
- `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json.gz` — локальная mirror-копия default external AI source. Workspace-слой gitignored.
- `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_DIRECT_CHAT_SUPPLEMENT_2026-04-08.json.gz` — локальная mirror-копия provenance/evidence snapshot. Workspace-слой gitignored.

## Внешние источники контекста

- `Downloads` — [Google Drive folder 1](https://drive.google.com/drive/folders/1INCx3J11p24XZIgY_th3-J2ZBCltQiwX?usp=sharing)
- `Downloads` — [Google Drive folder 2](https://drive.google.com/drive/folders/147bS-lCxGY4jsQ6jCnsq9Os6pk7U6zE7?usp=sharing)
- `пневмоподвеска` — [Google Drive folder 3](https://drive.google.com/drive/folders/1tEJwV4UtRNwsbX2Jgf-O-GihTktWHBfN?usp=sharing)

## Правило использования

- Внешние ссылки не заменяют локальный канон.
- Для GUI-first задач сначала читать `17`, затем `18`, затем `gui_spec_imports/v3/*`, затем parity docs и только потом lane-level prompts.
- Imported JSON/DOT/CSV используются как reference artifacts, а не как единственный источник правды.
- При конфликте между imported sources и текущим каноном приоритет у `17/18`.
