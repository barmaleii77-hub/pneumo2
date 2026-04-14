# Chat Prompt: Geometry Catalogs Reference Center

## Контекст

Геометрия подвески, каталоги компонентов и инженерные справочники должны жить в отдельном desktop reference-workspace, а не в WEB pages.

## Наследование desktop-канона

- Перед локальными решениями сначала следуй [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md), затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Для geometry/reference lane держи geometry viewer, drawing area или preview в центре там, где он есть; списки и справочники не должны вытеснять основную рабочую поверхность.
- Табличные каталоги и справочники строить через list/details или master/detail, а не через giant grids без инспектора.
- Правая pane должна быть пригодна для context-sensitive properties, component details и reference explanations. Для 3D surfaces обязателен orientation widget.

## Цель

Перенести geometry/catalog/reference workflow из WEB в отдельный desktop workspace. Нужны: просмотр геометрии подвески, справочник цилиндров, геометрия пружин, coil bind, parameter guides.

## Можно менять

- новые файлы рядом с lane:
  - `pneumo_solver_ui/tools/desktop_geometry_reference_center.py`
  - `pneumo_solver_ui/desktop_geometry_reference_model.py`
  - `pneumo_solver_ui/desktop_geometry_reference_runtime.py`
- [spring_geometry_ui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_geometry_ui.py)
- [spring_table.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_table.py)
- related tests

## Можно читать как источник поведения

- [10_SuspensionGeometry.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/10_SuspensionGeometry.py)
- [13_CamozziCylindersCatalog.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/13_CamozziCylindersCatalog.py)
- [14_SpringsGeometry_CoilBind.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/14_SpringsGeometry_CoilBind.py)
- [20_ParamsGuide.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/20_ParamsGuide.py)
- [spring_geometry_ui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_geometry_ui.py)
- [spring_table.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_table.py)

## Нельзя менять

- [desktop_input_editor.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_input_editor.py) кроме интеграции
- optimizer GUI
- WEB pages как target

## Правила

- Это справочно-инженерный desktop workspace, не тащи его внутрь input editor.
- Переносить нужно рабочий смысл, а не WEB layout.
- Reference center должен помогать выбору и анализу компонентов, а не просто показывать таблицы.
- Не допускай, чтобы core-данные жили только в горизонтально скроллимых сетках без явного detail flow.

## Готовый промт

```text
Работай только в lane "Geometry Catalogs Reference Center".

Сначала прочитай docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md, затем docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md и соблюдай их как project-wide baseline и augmented A–M project-specific contract.

Контекст: geometry/catalog/reference workflow уходит из WEB и должен жить в отдельном desktop reference workspace.

Цель: перенести geometry/catalog/reference workflow из WEB в отдельный desktop workspace. Нужны: просмотр геометрии подвески, справочник цилиндров, геометрия пружин, coil bind, parameter guides.

Можно менять только:
- новые desktop_geometry_reference_* модули
- pneumo_solver_ui/spring_geometry_ui.py
- pneumo_solver_ui/spring_table.py
- related tests

Можно читать как источник поведения:
- pneumo_solver_ui/pages/10_SuspensionGeometry.py
- pneumo_solver_ui/pages/13_CamozziCylindersCatalog.py
- pneumo_solver_ui/pages/14_SpringsGeometry_CoilBind.py
- pneumo_solver_ui/pages/20_ParamsGuide.py
- pneumo_solver_ui/spring_geometry_ui.py
- pneumo_solver_ui/spring_table.py

Нельзя менять:
- desktop_input_editor.py кроме интеграции
- optimizer GUI
- WEB pages как target

Правила:
- это справочно-инженерный desktop workspace, не тащи его внутрь input editor
- переносить нужно рабочий смысл, а не WEB layout
- reference center должен помогать выбору и анализу компонентов, а не просто показывать таблицы
- list/details и inspector важнее giant grids
- для 3D или geometry preview держи рабочую поверхность в центре и не убирай её на второй план

Сделай первый или следующий шаг по desktop geometry/reference center.
```
