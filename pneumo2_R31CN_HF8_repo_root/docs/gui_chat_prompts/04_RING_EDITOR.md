# Chat Prompt: Редактор кольца и сценариев

## Канонический слой

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`, раздел `З. Редактор кольца и сценариев`
- `docs/context/gui_spec_imports/v3/pneumo_gui_codex_spec_v3_refined.json`
- `docs/context/gui_spec_imports/v3/field_catalog.csv`
- `docs/context/gui_spec_imports/v3/source_of_truth_matrix.csv`
- `docs/context/gui_spec_imports/v3/optimized_macro.dot`

## Цель lane

Сделать `Редактор кольца и сценариев` единственным источником истины по дороге,
сегментам, профилю, режиму прохождения и derived artifacts.

## Можно менять

- `pneumo_solver_ui/tools/desktop_ring_scenario_editor.py`
- `pneumo_solver_ui/desktop_ring_editor_model.py`
- `pneumo_solver_ui/desktop_ring_editor_runtime.py`
- `pneumo_solver_ui/desktop_ring_editor_panels.py`
- shell adapter/catalog только если реально добавляется новое окно
- `tests/test_desktop_ring_editor_contract.py`

## Можно читать как источник поведения

- `pneumo_solver_ui/ui_scenario_ring.py`
- `pneumo_solver_ui/scenario_ring.py`
- `pneumo_solver_ui/ring_visuals.py`
- `pneumo_solver_ui/scenario_generator.py`
- `pneumo_solver_ui/optimization_auto_ring_suite.py`

## Нельзя менять

- input editor как master-copy входных параметров;
- optimizer center, кроме готовой интеграции по output;
- compare viewer, animator, mnemo;
- web pages как target.

## Правила

- Сценарий нельзя добавить в матрицу испытаний без preview и validation.
- Нельзя создавать второй редактируемый источник истины для дороги.
- UI делить на панели: сегменты, профиль, движение, события, diagnostics, export.
- Ring workflow должен естественно вести в `Матрицу испытаний`, а не в side routes.
