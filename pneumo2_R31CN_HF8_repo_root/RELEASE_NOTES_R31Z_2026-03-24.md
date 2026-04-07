# RELEASE_NOTES_R31Z_2026-03-24

## Что исправлено

### 1) 3D окно: убран special “safe window” path, возвращён native dock/floating
- Live 3D GL больше не переводится в специальный external/reparent режим как основной пользовательский сценарий.
- `dock_3d` снова использует обычное native `QDockWidget` dock/floating поведение.
- При move/resize/show/hide/top-level change 3D панели во время playback Animator теперь **автоматически ставит playback на паузу**, временно подавляет live GL updates и после короткой стабилизации layout возобновляет playback с текущего кадра.
- Это прямо следует из последнего Windows bundle: crash-path шёл через `_set_panel_external_mode`, поэтому R31Z убирает сам этот путь из normal 3D workflow вместо попытки ещё раз его маскировать.

### 2) Убраны user-facing GL point-sprite “шарики”
- Contact markers переведены с `GLScatterPlotItem` на line-based crosses.
- Piston debug-balls окончательно исключены из обычной сцены; ordinary mode не должен показывать загадочные шары, которые можно принять за frame mounts или внутренние детали цилиндра.
- Это одновременно адресует и UX-путаницу, и реальный Windows/OpenGL warning path (`GL_POINT_SPRITE` invalid-op) из последнего bundle.

### 3) Cylinder packaging стал читаемее
- Outer housing shell остаётся честной full pin-to-pin оболочкой, пока exporter не отдаёт explicit `gland/body-end` point.
- Но теперь user-facing 3D различает четыре слоя:
  - outer shell,
  - exact cap-side chamber,
  - exact rod,
  - exact piston plane/ring.
- То есть сцена больше не сводится к ощущению «просто цилиндры, а где всё остальное».

### 4) Docs / contract / tests
- Обновлены `01_PARAMETER_REGISTRY.md` и `DATA_CONTRACT_UNIFIED_KEYS.md` под law для native live-GL layout и honest cylinder internals.
- Обновлены `docs/11_TODO.md`, `docs/12_Wishlist.md`, `docs/WISHLIST.json`.
- Добавлены source-level regression tests для native GL layout policy и для cleanup user-facing GL point-sprites / cylinder layers.

## Что ещё НЕ считается принятым окончательно
- Нужен свежий Windows SEND bundle уже на R31Z для подтверждения: native float/re-dock 3D во время playback, отсутствие draw-error spam / access violation, и исчезновение CPU tail после расчётов/stop playback.
- Exporter всё ещё не отдаёт explicit `cyl*_gland_xyz` / equivalent body-end contract, поэтому outer shell остаётся честным fallback, а не финальной идеальной геометрией корпуса.
