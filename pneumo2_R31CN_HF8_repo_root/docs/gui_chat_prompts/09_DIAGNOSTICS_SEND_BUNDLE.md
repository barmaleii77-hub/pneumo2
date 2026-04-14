# Chat Prompt: Diagnostics And Send Bundle Center

## Канонический слой

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `docs/context/gui_spec_imports/v3/migration_matrix.csv`
- `docs/context/gui_spec_imports/v3/help_catalog.csv`
- `docs/context/gui_spec_imports/v3/acceptance_criteria.csv`
- `docs/context/gui_spec_imports/v3/source_of_truth_matrix.csv`
- `docs/context/gui_spec_imports/v3/pipeline_observability.csv`
- `docs/context/desktop_web_parity_map.json`

## Цель lane

Сделать единый desktop diagnostics/send center без скрытых web-зависимостей.

Пользователь должен уметь:

- запускать диагностику одной заметной командой;
- видеть состав пакета, путь, свежесть и последний ZIP;
- видеть self-check и autosave policy;
- управлять bundle settings без похода по историческим страницам.

## Можно менять

- `pneumo_solver_ui/tools/run_full_diagnostics_gui.py`
- `pneumo_solver_ui/tools/send_results_gui.py`
- новые `desktop_diagnostics_*` модули
- diagnostics/send desktop tests

## Можно читать как источник поведения

- `pneumo_solver_ui/pages/99_Diagnostics.py`
- `pneumo_solver_ui/pages/98_BuildBundle_ZIP.py`
- `pneumo_solver_ui/pages/98_SendBundle.py`
- `pneumo_solver_ui/diagnostics_entrypoint.py`
- `pneumo_solver_ui/diagnostics_unified.py`
- `pneumo_solver_ui/send_bundle.py`

## Нельзя менять

- `test_center_gui.py`, кроме явной интеграции;
- desktop input editor;
- compare viewer;
- web pages как target.

## Правила

- Не дублировать web pages один-в-один.
- Diagnostic path должен быть machine-readable, а не только набором кнопок.
- Команда `Собрать диагностику` обязана оставаться discoverable из shell и из result-oriented flows.
