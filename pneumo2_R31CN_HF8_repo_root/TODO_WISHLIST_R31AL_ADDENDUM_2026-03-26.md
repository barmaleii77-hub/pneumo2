# TODO / WISHLIST ADDENDUM R31AL (2026-03-26)

## Что считается закрытым этим шагом
- Проведён углублённый аудит speed/perf path Desktop Animator после R31AK.
- Playback переведён на display-rate continuous-time playhead вместо source-frame chasing.
- Auxiliary panes окончательно демотированы относительно live 3D во время playback.
- Long-idle timeout polling path убран из оставшихся follower/embedded web widgets.
- Cylinder meshes получили торцевые стенки и более читаемую оболочку.

## Что остаётся открытым P0
- Подтвердить на свежем Windows SEND bundle, что speed selector снова реально переключает скорость playback.
- Подтвердить, что `x1.0` перестал дёргаться именно на живом GUI run, а не только по коду/тестам.
- Подтвердить, что post-run browser/Web UI CPU tail действительно ушёл после перевода idle loops в stop-on-idle.
- Если Windows bundle всё ещё покажет проблемы drag/resize/floating 3D, следующий шаг — full recreate GL viewport/context after layout transition.
