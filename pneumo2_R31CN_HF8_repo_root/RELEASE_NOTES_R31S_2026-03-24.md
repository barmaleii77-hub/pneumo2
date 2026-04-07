# RELEASE NOTES — R31S (2026-03-24)

## Что исправлено

### 1) Убрана искусственная «заморозка» остальных окон во время playback
- В `CockpitWidget.update_frame()` причина оказалась не в OpenGL и не в самих данных bundle.
- R31R при playback переводил auxiliary panes в сверхредкий cadence, а при many-docks режиме обновлял fast/slow панели по одной через round-robin.
- На практике это делало 3D живым, а остальные окна выгляделели почти остановившимися.

### 2) Scheduler auxiliary panes переделан без отключения режимов
- Visible fast/slow панели теперь обновляются **как видимые группы** на capped FPS.
- Many-docks mode по-прежнему включает облегчающий режим, но больше не душит окна до pseudo-freeze.
- 3D остаётся на отдельном top-level GL window из R31Q, а R31R clamp/perf fixes для road mesh сохраняются.

### 3) Исправлен дрейф road wire-grid относительно дороги
- Видимая сетка cross-bars больше не стартует от локального `row=0` текущего viewport window.
- Cross-bars выбираются по world-anchored longitudinal `s`, поэтому wire-grid остаётся привязанной к дороге во время playback и не «плывёт» фазой при движении окна.

## Что обновлено
- `pneumo_solver_ui/desktop_animator/app.py`
- `pneumo_solver_ui/desktop_animator/geom3d_helpers.py`
- `tests/test_r26_road_view_density_helpers.py`
- `tests/test_r37_desktop_animator_perf_gating.py`
- `tests/test_r39_desktop_animator_playback_perf_mode.py`
- `tests/test_r40_road_window_clamp_and_3d_playback_perf.py`
- `tests/test_r41_aux_playback_and_worldanchored_grid.py`
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`
- release metadata (`VERSION.txt`, `release_info.py`, `release_tag.json`, latest build/release pointers)

## Проверка
- `py_compile`: PASS
- targeted pytest: 11 passed

## Честный статус
Это **root-cause patch-release** по двум новым визуально-поведенческим багам Animator: starvation auxiliary panes и viewport-anchored road grid.
Но финальная Windows acceptance всё ещё нужна на живом `SEND` bundle уже для `R31S`: подтвердить субъективную живость 2D окон и отсутствие дрейфа road grid relative to road на реальном driver/runtime stack.
