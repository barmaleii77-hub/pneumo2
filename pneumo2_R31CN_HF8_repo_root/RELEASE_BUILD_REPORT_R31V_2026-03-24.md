# RELEASE BUILD REPORT — PneumoApp_v6_80_R176_R31V_2026-03-24

Дата: 2026-03-24

## Основание
- База: `PneumoApp_v6_80_R176_R31U_2026-03-24`
- Проверенный SEND bundle: `0d5b8236-0226-4996-9f66-e21deaa1c731.zip`

## Диагноз
- Странное поведение поперечных полос дороги вызвано не road mesh целиком, а путём построения видимых cross-bars:
  - nearest-row snapping к текущему `s_nodes` road mesh;
  - forced terminal cross-bar на последней видимой строке viewport-а.

## Исправление
- Добавлен helper `road_grid_target_s_values_from_range(...)`.
- Добавлен helper `road_crossbar_line_segments_from_profiles(...)`.
- `road_grid_line_segments(...)` расширен флагами `include_longitudinal/include_crossbars/force_last_crossbar`.
- В `Car3D.update_frame()` продольные rails и поперечные cross-bars теперь строятся раздельно:
  - rails — по dense road mesh;
  - cross-bars — по exact world targets без forced edge bar.

## Проверка
- `py_compile`: PASS
- `compileall`: PASS
- targeted `pytest`: 13 passed

## Остаток
- Требуется свежий Windows SEND bundle на `R31V` для окончательного визуального acceptance.
