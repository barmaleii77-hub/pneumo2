# RELEASE_BUILD_REPORT_R31Y_2026-03-24

## База сборки
- Исходное дерево: `PneumoApp_v6_80_R176_R31X_2026-03-24.zip`
- Bundle для анализа регрессий: `801c2335-2e66-4d98-95f8-b636ade25a6a.zip`
- Новый релиз: `PneumoApp_v6_80_R176_R31Y_2026-03-24`

## Что делалось
- Проведён bundle-driven разбор пользовательских замечаний по road drift, cylinder/piston visuals, docking UX, stale pane rendering и возврату старых regressions.
- Проверено, что в bundle экспорт mount points цилиндров не инвертирован: `cyl*_top` остаются frame-side, `cyl*_bot` ближе всего к ветвям upper arm.
- Подтверждено, что в старом bundle остался startup warning `startup_external_gl_window`, совпадающий с жалобой на невозможность нормального re-dock 3D окна.
- После этого собран cumulative patch R31Y с кодовыми изменениями в `desktop_animator/app.py` и `geom3d_helpers.py`, плюс обновлён проектный контекст/docs.

## Ключевые кодовые изменения
- `pneumo_solver_ui/desktop_animator/app.py`
  - bundle-level cache world path normals для road surface;
  - world-normal based road orientation вместо viewport-local gradient-only path;
  - docked-by-default startup для live 3D GL;
  - layout-version gate против старого forced detached state;
  - safe external GL window только на explicit detach;
  - show/hide + re-dock logic для external panel window;
  - `_refresh_after_playback_stop()` и немедленное восстановление panes после manual stop.
- `pneumo_solver_ui/desktop_animator/geom3d_helpers.py`
  - `cylinder_visual_state_from_packaging(...)` теперь дополнительно возвращает honest `housing_seg`.

## Проверка
- `py_compile`: PASS
- `compileall`: PASS
- targeted pytest slice: PASS (`50 passed`)

См. логи:
- `PYCHECKS_R31Y_2026-03-24.log`
- `PYTEST_TARGETED_R31Y_2026-03-24.log`

## Bundle evidence used in this patch
- `BUNDLE_ANALYSIS_R31X_REGRESSIONS_2026-03-24.md`
- `BUNDLE_ANALYSIS_R31X_REGRESSIONS_2026-03-24.json`

## Честный статус
Это **не** финальный acceptance sign-off. Это аккуратный patch-release, который исправляет корни найденных regressions в коде и в startup/layout policy.
Финальное подтверждение всё ещё требует нового живого Windows SEND bundle уже на R31Y.
