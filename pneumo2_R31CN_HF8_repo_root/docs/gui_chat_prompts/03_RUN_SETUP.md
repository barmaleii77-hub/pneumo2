# Chat Prompt: Настройка расчёта и базовый прогон

## Канонический слой

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`, раздел `К. Базовый прогон, оптимизация и анализ`
- `docs/context/gui_spec_imports/v3/optimized_macro.dot`
- `docs/context/gui_spec_imports/v3/pipeline_verification.csv`
- `docs/context/gui_spec_imports/v3/source_of_truth_matrix.csv`
- `docs/context/desktop_web_parity_map.json`

## Цель lane

Собрать единый desktop workflow для:

- подготовки run contract;
- выбора и запуска baseline;
- отображения progress на месте;
- сохранения provenance baseline и политики его автообновления.

## Можно менять

- `pneumo_solver_ui/tools/desktop_run_setup_center.py`
- `pneumo_solver_ui/desktop_run_setup_model.py`
- `pneumo_solver_ui/desktop_run_setup_runtime.py`
- `tests/test_desktop_run_setup_center_contract.py`
- `tests/test_desktop_run_setup_modules.py`

## Можно читать как источник поведения

- `pneumo_solver_ui/pneumo_ui_app.py`
- `pneumo_solver_ui/app.py`
- `ui_results_*`
- `ui_suite_*`

## Нельзя менять

- optimizer center как отдельный lane;
- results/compare surfaces;
- animator/mnemo;
- web pages как target.

## Правила

- Baseline — отдельный first-class contract, а не скрытая кнопка.
- Пользователь всегда видит источник baseline, историю, auto-update policy и последний accepted snapshot.
- Длительный прогон показывает progress на текущем экране и в status strip.
- Визуально baseline и optimization разделены, но route между ними остаётся линейным и понятным.
