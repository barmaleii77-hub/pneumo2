# Chat Prompt: Geometry Catalogs Reference Center

## Контекст

Геометрия подвески, каталоги компонентов и инженерные справочники должны жить в отдельном desktop reference-workspace, а не в WEB pages.

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

## Готовый промт

```text
Работай только в lane "Geometry Catalogs Reference Center".

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

Сделай первый или следующий шаг по desktop geometry/reference center.
```
