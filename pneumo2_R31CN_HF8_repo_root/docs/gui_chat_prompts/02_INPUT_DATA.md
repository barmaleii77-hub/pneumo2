# Chat Prompt: Ввод исходных данных

## Канонический слой

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `docs/context/gui_spec_imports/v3/field_catalog.csv`
- `docs/context/gui_spec_imports/v3/help_catalog.csv`
- `docs/context/gui_spec_imports/v3/source_of_truth_matrix.csv`
- `docs/context/desktop_web_parity_map.json`

## Цель lane

Сделать `Исходные данные` главным master-copy параметров машины, геометрии,
пневматики, механики, масс и базовых solver settings.

Обязательные свойства surface:

- cluster-based структура;
- units и help у каждого meaningful control;
- парность `число/таблица + графика/схема`;
- явный readiness-summary;
- связка с command search и inspector/help pane.

## Можно менять

- `pneumo_solver_ui/tools/desktop_input_editor.py`
- `pneumo_solver_ui/desktop_input_model.py`
- `tests/test_desktop_input_editor_contract.py`
- `tests/test_desktop_input_graphics_contract.py`

## Можно читать как источник поведения

- `pneumo_solver_ui/pneumo_ui_app.py`
- `pneumo_solver_ui/pages/10_SuspensionGeometry.py`
- `pneumo_solver_ui/pages/13_CamozziCylindersCatalog.py`
- `pneumo_solver_ui/pages/14_SpringsGeometry_CoilBind.py`
- `01_PARAMETER_REGISTRY.md`

## Нельзя менять

- shell core;
- optimizer GUI;
- compare viewer;
- animator и mnemo;
- web pages как target implementation surface.

## Правила

- Ввод данных не расползается по случайным secondary routes.
- Обозначения без названия и единицы измерения запрещены.
- Графика рядом с вводом обязана быть честной: `расчетно подтверждено / по исходным данным / условно`.
- Для справочников и reference-data использовать contextual/tool routes, а не новые top-level pages.
