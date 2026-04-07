# RELEASE NOTES — R31R (2026-03-24)

## Что исправлено

### 1) Исправлен реальный корень бага дороги в Desktop Animator
- Причина симптомов в присланном bundle `R31Q`: 3D road window выходил за пределы реального диапазона `s_world` / `road_profile(left/center/right)`.
- `np.interp` при этом прижимал значения к endpoint, из-за чего на старте/финише прогона появлялись repeated longitudinal slices.
- Эти повторы рождали degenerate triangles в GL road mesh, а дальше — warning `MeshData invalid value encountered in divide`, визуальный распад дороги и лишнюю нагрузку на playback.

### 2) Добавлен фикс, а не workaround
- Окно дороги теперь клипуется к общему диапазону реальных данных через `clamp_window_to_interpolation_support(...)` перед построением 3D mesh.
- В результате road mesh больше не строится на фальшивых endpoint-повторах и не рождает zero-area faces на representative start/end frames.

### 3) Добавлен playback perf-tier для Car3D
- Во время playback 3D road mesh автоматически становится легче (`play` tier).
- При множестве открытых dock-панелей включается более жёсткий `play_many` tier.
- Это уменьшает число face updates на кадр без возврата к ложной/редкой дороге.

## Что обновлено
- `pneumo_solver_ui/desktop_animator/geom3d_helpers.py`
- `pneumo_solver_ui/desktop_animator/app.py`
- `tests/test_r40_road_window_clamp_and_3d_playback_perf.py`
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`
- release metadata (`VERSION.txt`, `release_info.py`, `release_tag.json`, latest build/release pointers)

## Bundle regression summary
По representative кадрам bundle `R31Q`:
- `orig`: до тысяч degenerate faces у начала/конца run;
- `fixed`: degenerate faces -> `0`;
- `play`: mesh заметно легче на playback;
- `play_many`: mesh ещё легче для many-docks режима.

Подробно: `BUNDLE_ANALYSIS_R31Q_ROAD_SPEED_2026-03-24.md`.

## Проверка
- `py_compile`: PASS
- targeted pytest: 17 passed

## Честный статус
Это **кодовый fix-release**, который исправляет найденную причину дорожного артефакта и добавляет 3D playback perf-gating.
Но финальная Windows acceptance всё ещё требует нового живого SEND bundle уже на `R31R`:
- подтвердить исчезновение артефакта дороги у начала/конца записи;
- проверить субъективный FPS playback;
- убедиться, что `MeshData` warning-spam исчез на реальном driver stack.
