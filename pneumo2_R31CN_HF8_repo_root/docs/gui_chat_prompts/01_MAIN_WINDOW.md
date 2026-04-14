# Chat Prompt: Главное окно приложения

## Канонический слой

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `docs/context/gui_spec_imports/v3/current_macro.dot`
- `docs/context/gui_spec_imports/v3/optimized_macro.dot`
- `docs/context/gui_spec_imports/v3/ui_element_catalog.csv`
- `docs/context/gui_spec_imports/v3/help_catalog.csv`
- `docs/context/gui_spec_imports/v3/tooltip_catalog.csv`
- `docs/context/gui_spec_imports/v3/keyboard_matrix.csv`
- `docs/context/gui_spec_imports/v3/docking_matrix.csv`
- `docs/context/gui_spec_imports/v3/ui_state_matrix.csv`

## Цель lane

Развивать главное окно как native Windows shell для инженерного desktop-приложения:

- сверху command surface и command search;
- слева навигация и browser только там, где реально есть иерархия;
- по центру document/viewport-first рабочая поверхность;
- справа context-sensitive properties/help pane;
- снизу status/progress strip.

## Можно менять

- `pneumo_solver_ui/desktop_shell/main_window.py`
- `pneumo_solver_ui/desktop_shell/workspace.py`
- `pneumo_solver_ui/desktop_shell/menu_builder.py`
- `pneumo_solver_ui/desktop_shell/toolbar.py`
- `pneumo_solver_ui/desktop_shell/home_view.py`
- `pneumo_solver_ui/desktop_shell/navigation.py`
- `pneumo_solver_ui/desktop_shell/lifecycle.py`
- `pneumo_solver_ui/tools/desktop_main_shell.py`
- `tests/test_desktop_main_shell_contract.py`

## Можно читать как источник поведения

- `pneumo_solver_ui/pneumo_ui_app.py`
- `pneumo_solver_ui/page_registry.py`
- parity map и imported workflow graphs

## Нельзя менять

- feature-логику отдельных окон;
- `qt_compare_viewer.py`;
- `desktop_animator/*`;
- `desktop_mnemo/*`;
- web pages как target implementation surface.

## Правила

- Shell не превращать в новый монолит.
- Новые seams выносить в отдельные shell-модули.
- Логика hosted и external tools не дублируется внутри shell.
- `Command search`, diagnostics entrypoint и user route обязаны соответствовать `17/18`.

## Готовый prompt

```text
Работай только в lane "Главное окно приложения".

Сначала прочитай:
- docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md
- docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md
- docs/context/desktop_web_parity_map.json

Цель: развивать native Windows shell как основной document-first вход в систему без потери desktop affordances, command search, diagnostics visibility и workflow route.

Можно менять только shell-файлы и targeted tests. Не переноси feature-логику отдельных окон внутрь shell и не строй новый монолит.
```
