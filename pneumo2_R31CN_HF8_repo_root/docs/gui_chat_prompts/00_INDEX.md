# GUI Chat Prompts

Этот каталог хранит lane-level implementation prompts. Он не является
самостоятельным каноном и должен читаться только после GUI-spec слоя.

## Порядок чтения

1. [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
   — project-wide desktop baseline.
2. [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
   — project-specific GUI contract для `Пневмоподвески`.
3. [gui_spec_imports/v3/README.md](../context/gui_spec_imports/v3/README.md)
   и related `v3/*`
   — active detailed machine-readable reference layer.
4. [gui_spec_imports/v13_ring_editor_migration/README.md](../context/gui_spec_imports/v13_ring_editor_migration/README.md)
   и related `v13_ring_editor_migration/*`
   — специализированный addendum для `WS-RING` и handoff `WS-RING -> WS-SUITE`.
5. `docs/gui_chat_prompts/*`
   — implementation prompts, которые должны наследовать канон, а не заменять его.

## Что считается reference layer

- `v3` задаёт общий detailed layer:
  shell, layout, UI elements, help/tooltip catalogs, migration matrix,
  acceptance, verification, keyboard/docking/state/observability contracts.
- `v13_ring_editor_migration` задаёт специализированный ring layer:
  schema contract, screen blueprints, element/field catalogs, state machine,
  user pipeline, ring-level migration matrix, acceptance gates и suite-link
  contract.

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
- если lane касается ring editor, handoff сценария или suite consumer
  сценарного контракта, обязательно дополнительно смотреть
  `v13_ring_editor_migration/*`;
- при конфликте приоритет у `17/18`, затем у `v3`, затем у специализированного
  `v13_ring_editor_migration`, затем у historical imports.
