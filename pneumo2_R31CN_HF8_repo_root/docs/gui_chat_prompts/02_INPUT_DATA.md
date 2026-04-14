# Chat Prompt: Ввод Исходных Данных

## Контекст

Это основной GUI ввода параметров вместо WEB-форм. Пользователь должен настраивать систему по понятным кластерам, а не через длинный Streamlit-экран.

## Наследование desktop-канона

- Перед локальными решениями сначала следуй [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md), затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Здесь применяем document/workspace-first логику: слева section browser только по делу, в центре рабочая форма и preview, справа context-sensitive inspector/properties pane.
- Все параметры должны быть подписаны названием и единицей измерения, кроме очевидно безразмерных. Обозначения без названий запрещены.
- Явные scrollbars, resize affordances, keyboard navigation и `command search` для больших наборов полей обязательны.

## Цель

Сделать основное окно ввода исходных данных понятным для инженера и пользователя. Оно должно быть cluster-based: Геометрия, Пневматика, Механика, Статическая настройка, Компоненты, Справочные данные.

## Можно менять

- [desktop_input_editor.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_input_editor.py)
- [desktop_input_model.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_model.py)
- [test_desktop_input_editor_contract.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/tests/test_desktop_input_editor_contract.py)

## Можно читать как источник поведения

- [pneumo_ui_app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pneumo_ui_app.py)
- [10_SuspensionGeometry.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/10_SuspensionGeometry.py)
- [13_CamozziCylindersCatalog.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/13_CamozziCylindersCatalog.py)
- [14_SpringsGeometry_CoilBind.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/14_SpringsGeometry_CoilBind.py)
- [spring_geometry_ui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_geometry_ui.py)
- [spring_table.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_table.py)
- [01_PARAMETER_REGISTRY.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/01_PARAMETER_REGISTRY.md)

## Нельзя менять

- shell core
- optimizer GUI
- compare viewer
- desktop animator
- desktop mnemo
- WEB pages

## Правила

- Не дублируй compare/animator/mnemo.
- Не складывай всё в один огромный Tk-класс.
- Если нужны новые blocks, выноси их в отдельные panel/model helpers.
- Сохраняй понятный desktop UX: секции, пресеты, профили, snapshots, быстрый поиск.
- Не превращай input editor в web-style длинную ленту форм без устойчивых регионов и без понятного inspector flow.

## Готовый промт

```text
Работай только в lane "Ввод Исходных Данных".

Сначала прочитай docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md, затем docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md и соблюдай их как project-wide baseline и augmented A–M project-specific contract.

Контекст: это основной GUI ввода параметров вместо WEB. Пользователь должен настраивать систему по понятным кластерам, а не через длинный WEB-экран.

Цель: сделать desktop input editor удобным и инженерно понятным. Нужны секции: Геометрия, Пневматика, Механика, Статическая настройка, Компоненты, Справочные данные.

Можно менять только:
- pneumo_solver_ui/tools/desktop_input_editor.py
- pneumo_solver_ui/desktop_input_model.py
- tests/test_desktop_input_editor_contract.py

Можно читать как источник поведения:
- pneumo_solver_ui/pneumo_ui_app.py
- pneumo_solver_ui/pages/10_SuspensionGeometry.py
- pneumo_solver_ui/pages/13_CamozziCylindersCatalog.py
- pneumo_solver_ui/pages/14_SpringsGeometry_CoilBind.py
- pneumo_solver_ui/spring_geometry_ui.py
- pneumo_solver_ui/spring_table.py
- 01_PARAMETER_REGISTRY.md

Нельзя менять:
- shell core
- optimizer GUI
- compare viewer
- desktop animator
- desktop mnemo
- WEB pages

Правила:
- не дублируй compare/animator/mnemo
- не складывай всё в один огромный Tk-класс
- если нужны новые blocks, выноси их в отдельные panel/model helpers
- сохраняй понятный desktop UX: секции, пресеты, профили, snapshots, быстрый поиск
- держи слева section browser только при реальной иерархии, справа context-sensitive inspector
- все величины подписывай названием и единицей измерения, кроме очевидно безразмерных

Сделай следующий полезный шаг именно по окну ввода исходных данных и прогони его targeted tests.
```
