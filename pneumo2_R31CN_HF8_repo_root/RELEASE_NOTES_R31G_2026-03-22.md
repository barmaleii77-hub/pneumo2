# RELEASE_NOTES_R31G_2026-03-22

База: `R31F_SINE_A_SEMANTICS_DETAIL_RECALC`

## Изменения

1. **Амплитуда синуса / worldroad**
   - worldroad sine input в `pneumo_ui_app.py` теперь явно помечает `A` как полуразмах;
   - UI показывает интерпретацию `-A..+A` и `p-p = 2A`.

2. **baseline -> auto-detail**
   - `pneumo_ui_app.py` синхронизирован с `detail_autorun_policy.py`;
   - после свежего baseline следующий auto-detail для текущего теста может принудительно обойти старый detail disk-cache;
   - добавлена наблюдаемость `detail_cache_bypassed_after_baseline`.

3. **post-run CPU / idle followers**
   - исправлен полноскоростной rAF-spin в `components/mech_car3d/index.html` при `W < 10 || H < 10`;
   - follower web-components получили parent-viewport aware idle policy и более редкий paused/off-screen idle;
   - `plotly_playhead_html.py` переведён с unconditional `setInterval(...)` на adaptive timer loop.

## Файлы
Смотрите `CHANGED_FILES_R31G_2026-03-22.txt`.

## Acceptance
- targeted regression slice: `15 passed`
- `py_compile`: PASS

## Остаток риска
- нужен Windows browser Performance trace для окончательной приёмки post-run CPU regression.
