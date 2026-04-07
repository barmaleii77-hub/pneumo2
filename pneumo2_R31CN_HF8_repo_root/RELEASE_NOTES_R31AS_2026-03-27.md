# Release notes R31AS (2026-03-27)

## Что исправлено
- Desktop Animator auxiliary panes перестали быть переужатыми во время playback: main helper panes снова живут на нормальном cadence.
- 3D speed arrow снова показывает signed solver speed along road (`скорость_vx_м_с`).
- 3D acceleration arrow снова показывает signed external longitudinal/lateral acceleration (`ускорение_продольное_ax_м_с2`, `ускорение_поперечное_ay_м_с2`).
- Сохранены display-rate continuous-time playhead и sub-frame sampling для 3D geometry.
- Обновлены regression tests под текущую playback-модель, чтобы они больше не проверяли устаревший 4 ms frame-chasing path.

## Честный статус
Это кодовый source patch. Финальная визуальная приёмка всё равно должна быть на новом Windows SEND bundle: cadence detached panes и семантика 3D arrows нужно подтвердить глазами на живом runtime.
