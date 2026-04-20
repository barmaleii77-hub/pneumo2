# GUI Chat Prompts

Этот каталог хранит lane-level implementation prompts. Он не является
самостоятельным каноном и должен читаться только после GUI-spec слоя.

## Порядок чтения

1. [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
   — project-wide desktop baseline.
2. [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
   — project-specific GUI contract для `Пневмоподвески`.
3. [gui_spec_imports/foundations/README.md](../context/gui_spec_imports/foundations/README.md)
   и
   [prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md](../context/gui_spec_imports/foundations/prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md)
   — foundational upstream prompt source (`PROMPT_V2`).
4. [gui_spec_imports/v38_github_kb_commit_ready/README.md](../context/gui_spec_imports/v38_github_kb_commit_ready/README.md),
   [TECHNICAL_SPECIFICATION.md](../context/gui_spec_imports/v38_github_kb_commit_ready/TECHNICAL_SPECIFICATION.md)
   и [GUI_SPEC.yaml](../context/gui_spec_imports/v38_github_kb_commit_ready/GUI_SPEC.yaml)
   — current successor GitHub KB/TZ/spec commit-ready supplement. Он уточняет
   requirements, workspace contracts, parameter catalogs, acceptance и open
   gaps, но не является runtime-closure proof.
5. [gui_spec_imports/v37_github_kb_supplement/README.md](../context/gui_spec_imports/v37_github_kb_supplement/README.md),
   [TECHNICAL_SPECIFICATION.md](../context/gui_spec_imports/v37_github_kb_supplement/TECHNICAL_SPECIFICATION.md)
   и [GUI_SPEC.yaml](../context/gui_spec_imports/v37_github_kb_supplement/GUI_SPEC.yaml)
   — predecessor successor GitHub KB/TZ/spec supplement.
6. [gui_spec_imports/v3/README.md](../context/gui_spec_imports/v3/README.md)
   и related `v3/*`
   — active detailed machine-readable reference layer.
7. [gui_spec_imports/v13_ring_editor_migration/README.md](../context/gui_spec_imports/v13_ring_editor_migration/README.md)
   и related `v13_ring_editor_migration/*`
   — специализированный addendum для `WS-RING` и handoff `WS-RING -> WS-SUITE`.
8. [gui_spec_imports/v12_design_recovery/README.md](../context/gui_spec_imports/v12_design_recovery/README.md)
   — historical design-recovery layer, который возвращает проект из implementation-веток в design-first.
9. [GUI_SPEC_ARCHIVE_LINEAGE.md](../context/GUI_SPEC_ARCHIVE_LINEAGE.md)
   и [gui_spec_archive_lineage.json](../context/gui_spec_archive_lineage.json)
   — lineage `v1…v13 + v37 + v38`, чтобы понимать роль каждого архива и successor supplement.
10. `docs/gui_chat_prompts/*`
   — implementation prompts, которые должны наследовать канон, а не заменять его.

## Что считается reference layer

- `foundations` задаёт upstream intent layer:
  native Windows desktop, no web-first, no feature-loss migration, diagnostics
  as first-class surface, ring editor as single source of truth и honest
  graphics baseline.
- `v38_github_kb_commit_ready` задаёт current successor KB/TZ/spec connector
  layer: consolidated technical specification, GUI_SPEC.yaml, workspace
  contract matrix, parameter catalogs, acceptance/requirements matrices, repo
  canon alignment и список open gaps, которые нельзя скрывать как закрытые.
- `v37_github_kb_supplement` задаёт successor KB/TZ/spec connector layer:
  predecessor/reference supplement после v38.
- `v3` задаёт общий detailed layer:
  shell, layout, UI elements, help/tooltip catalogs, migration matrix,
  acceptance, verification, keyboard/docking/state/observability contracts.
- `v13_ring_editor_migration` задаёт специализированный ring layer:
  schema contract, screen blueprints, element/field catalogs, state machine,
  user pipeline, ring-level migration matrix, acceptance gates и suite-link
  contract.
- `v12_design_recovery` задаёт historical recovery layer:
  ring-editor precursor contract, optimization control plane, truthful graphics
  и workspace recovery delta.

## Lane docs

- [01_MAIN_WINDOW.md](./01_MAIN_WINDOW.md)
- [02_INPUT_DATA.md](./02_INPUT_DATA.md)
- [03_RUN_SETUP.md](./03_RUN_SETUP.md)
- [04_RING_EDITOR.md](./04_RING_EDITOR.md)
- [05_COMPARE_VIEWER.md](./05_COMPARE_VIEWER.md)
- [06_DESKTOP_MNEMO.md](./06_DESKTOP_MNEMO.md)
- [07_DESKTOP_ANIMATOR.md](./07_DESKTOP_ANIMATOR.md)
- [08_OPTIMIZER_CENTER.md](./08_OPTIMIZER_CENTER.md)
- [09_DIAGNOSTICS_SEND_BUNDLE.md](./09_DIAGNOSTICS_SEND_BUNDLE.md)
- [10_TEST_VALIDATION_RESULTS.md](./10_TEST_VALIDATION_RESULTS.md)
- [11_GEOMETRY_REFERENCE.md](./11_GEOMETRY_REFERENCE.md)
- [12_ENGINEERING_ANALYSIS.md](./12_ENGINEERING_ANALYSIS.md)

## Правило использования

- если lane касается shell, сначала смотреть `17`, `18` и `v3`;
- если нужно понять исходный жёсткий intent ещё до `v1`, дополнительно читать
  `foundations/*`;
- если lane затрагивает requirements, параметры, workspace coverage,
  acceptance или open gaps, читать `v38_github_kb_commit_ready/*` как current
  successor knowledge-base supplement, затем `v37_github_kb_supplement/*` как
  predecessor reference, не подменяя ими runtime evidence;
- если lane касается ring editor, handoff сценария или suite consumer
  сценарного контракта, обязательно дополнительно смотреть
  `v13_ring_editor_migration/*`;
- если lane касается происхождения текущего канона, recovery decisions или
  границы между design и implementation-pass, смотреть `v12_design_recovery/*`
  и lineage `v1…v13 + v37 + v38`;
- при конфликте приоритет у `17/18`, затем у `foundations`, затем у
  `v38_github_kb_commit_ready`, затем у `v37_github_kb_supplement`, затем у
  `v3`, затем у специализированного `v13_ring_editor_migration`, затем у
  `v12_design_recovery`, затем у historical imports.
