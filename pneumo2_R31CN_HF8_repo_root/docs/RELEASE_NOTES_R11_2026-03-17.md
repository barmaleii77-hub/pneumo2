# RELEASE NOTES — R11 — 2026-03-17

## Что исправлено

### 1) 3D Animator: строгий канон осей без render-axis remap
- сохранён канон данных и визуализации: `x` вперёд, `y` влево, `z` вверх;
- 3D путь больше не вводит скрытый remap вида `(x, z, -y)`.

### 2) Wheel mesh: убрана скрытая путаница оси/смещения
- wheel cylinder теперь центрируется по своей ширине ещё в mesh-space;
- wheel cylinder сразу ориентируется вдоль локальной оси `+Y`;
- на runtime-кадре больше нет per-wheel `rotate(90° around X)`, который мог скрыто смешивать ориентацию mesh и трансляцию.

### 3) Solver-points preferred
- 3D placement колёс использует `wheel_center_{corner}_{x,y,z}_м` при наличии;
- контакт использует `road_contact_{corner}_{x,y,z}_м`;
- рама использует `frame_corner_{corner}_{x,y,z}_м` для построения локальной 3D-ориентации, если solver-points доступны.

### 4) Локализация world -> car frame
- локализация выполняется только через снятие yaw в плоскости XY;
- `z` не remap-ится и не меняет физический смысл.

## Что проверено
- `python -m compileall -q pneumo_solver_ui/desktop_animator/app.py pneumo_solver_ui/desktop_animator/geom3d_helpers.py` → OK
- `pytest -q tests/test_geom3d_helpers_axes_contract.py tests/test_solver_points_and_road_no_fallback.py tests/test_anim_latest_solver_points_contract_gate.py tests/test_geometry_acceptance_release_gate.py` → 17 passed
- `pytest -q tests/test_visual_consumers_geometry_strict.py tests/test_npz_meta_geometry_contract.py tests/test_geometry_acceptance_web_and_bundle.py` → 12 passed

## Ограничение
Живой Qt/OpenGL smoke в этом контейнере не подтверждён: здесь нет PySide6/pyqtgraph. Исправление подтверждено кодом, тестами и bundle-анализом.
