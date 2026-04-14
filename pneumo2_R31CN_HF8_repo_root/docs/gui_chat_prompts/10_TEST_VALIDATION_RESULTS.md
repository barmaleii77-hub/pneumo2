# Chat Prompt: Test Validation Results Center

## Канонический слой

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `docs/context/gui_spec_imports/v3/optimized_macro.dot`
- `docs/context/gui_spec_imports/v3/pipeline_verification.csv`
- `docs/context/gui_spec_imports/v3/acceptance_criteria.csv`
- `docs/context/gui_spec_imports/v3/source_of_truth_matrix.csv`
- `docs/context/desktop_web_parity_map.json`

## Цель lane

Развивать `desktop_results_center` как главный post-run маршрут:

- run -> validate -> inspect -> compare/analyze -> branch в animator или diagnostics.

## Можно менять

- `pneumo_solver_ui/tools/test_center_gui.py`
- `pneumo_solver_ui/tools/desktop_results_center.py`
- `pneumo_solver_ui/desktop_results_model.py`
- `pneumo_solver_ui/desktop_results_runtime.py`
- related desktop workflow tests

## Можно читать как источник поведения

- `pneumo_solver_ui/pages/08_ValidationCockpit_Web.py`
- `pneumo_solver_ui/pages/09_Validation_Web.py`
- `pneumo_solver_ui/pages/12_ResultsViewer.py`
- `pneumo_solver_ui/validation_cockpit_web.py`
- `pneumo_solver_ui/npz_anim_diagnostics.py`
- `pneumo_solver_ui/ui_results_*`

## Нельзя менять

- compare viewer;
- animator;
- send_results_gui, кроме интеграции;
- web pages как target.

## Правила

- Results center — orchestration surface, а не копия compare viewer или animator.
- Глубокая графика остаётся в compare viewer и animator.
- Validation, compare, diagnostics и animation открываются из понятного run context.
