# TODO / WISHLIST ADDENDUM R31AS (2026-03-27)

## Что реализовано этим шагом
- Возвращён нормальный cadence auxiliary panes во время playback: main helper panes снова обновляются заметно живее, вместо R31AL-переужатия.
- 3D speed arrow снова показывает signed solver speed along road (`скорость_vx_м_с`).
- 3D acceleration arrow снова показывает signed external longitudinal/lateral acceleration (`ускорение_продольное_ax_м_с2`, `ускорение_поперечное_ay_м_с2`).
- Убрана подмена этих 3D стрелок derived body/world kinematics на стороне Animator.

## Что это закрывает по пользовательским требованиям Animator
- Вспомогательные окна не должны выглядеть "замороженными" во время playback.
- Стрелка скорости в 3D должна показывать именно текущую скорость по дороге из solver и учитывать знак.
- Стрелка ускорения в 3D должна показывать внешнее ускорение машины: разгон/торможение и поворот, тоже с учётом знака.

## Что остаётся живой проверкой
- Подтвердить на новом Windows SEND bundle, что restored cadence визуально достаточен при реальном числе detached panes.
- Подтвердить глазами, что 3D arrows снова читаются именно как speed-along-road + external accel, без семантического дрейфа.
