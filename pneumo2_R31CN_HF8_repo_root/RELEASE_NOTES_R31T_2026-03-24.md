# RELEASE NOTES — R31T (2026-03-24)

## Что исправлено

### 1) Добит второй корень drift-багa дорожной сетки
- В `R31S` cross-bars уже были world-anchored по фазе, но **spacing** всё ещё считался от текущего playback viewport/window.
- На живом bundle это давало не постоянную world-геометрию, а «дышащий» шаг сетки: в последней проверке он гулял от **0.181 м** до **1.059 м** с **612** уникальными значениями по run.
- В `R31T` введён `stable_road_grid_cross_spacing_from_view(...)` и bundle/view-stable cache в Car3D: spacing теперь задаётся от nominal visible length + viewport bucket, а не от каждого кадра playback.

### 2) Поднят cadence floor detached auxiliary panes
- `R31S` уже убрал round-robin starvation, но его floor (`18/9`, `10/5`) всё ещё мог выглядеть «почти frozen» на реальном Windows run при большом числе окон.
- В `R31T` cadence floors подняты до:
  - normal playback: **24 FPS fast / 12 FPS slow**
  - many-docks playback: **18 FPS fast / 10 FPS slow**
- Порог входа в many-docks режим сдвинут до **12** видимых auxiliary docks, чтобы облегчённый режим не включался слишком рано.

### 3) Добавлена telemetry для следующего acceptance
- Desktop Animator теперь пишет event `AnimatorAuxCadence` с cadence-окнами по exposed auxiliary panes, timeline и trends.
- Следующий SEND bundle сможет доказать живость detached окон **количественно**, а не только «на глаз».

## Что обновлено
- `pneumo_solver_ui/desktop_animator/app.py`
- `pneumo_solver_ui/desktop_animator/geom3d_helpers.py`
- `tests/test_r39_desktop_animator_playback_perf_mode.py`
- `tests/test_r42_bundle_stable_road_grid_and_aux_cadence_metrics.py`
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`
- release metadata (`VERSION.txt`, `release_info.py`, `release_tag.json`, latest build/release pointers)

## Проверка
- `py_compile`: PASS
- `compileall -q pneumo_solver_ui tests`: PASS
- targeted pytest: **15 passed**

## Честный статус
`R31T` — это **следующий root-cause patch-release** после `R31S`: он фиксит не только phase-anchor сетки, но и её world-stable spacing, а также добавляет acceptance telemetry для detached panes.
Но финальная Windows acceptance всё ещё нужна на живом `SEND` bundle уже для `R31T`, чтобы подтвердить:
- auxiliary panes действительно остаются живыми на реальном runtime stack;
- road wire-grid больше не меняет скорость/шаг относительно дороги по всему playback;
- 3D FPS остаётся приемлемым после поднятия cadence floor.
