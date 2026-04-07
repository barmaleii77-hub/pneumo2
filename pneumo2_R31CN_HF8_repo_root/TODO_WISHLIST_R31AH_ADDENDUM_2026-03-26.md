# TODO / WISHLIST addendum — R31AH — 2026-03-26

## Что закрыто в этом проходе

- Архив `mhtml.zip` разобран как контекстный индекс: выявлены точные дубли и тематические кластеры; это подтверждает, что CPU / geometry / UI / math / code вопросы обсуждались многократно и не должны лечиться по памяти или по устаревшим слоям.
- Исправлен solver/export слой для жёсткой связи frame-mounted hardpoints с рамой: `frame_corner`, inboard arm points и `cyl*_top` больше не живут отдельными yaw-only XY траекториями с независимым Z.
- Исправлен слой `шток → рычаг`: `cyl*_bot` теперь строится на фактической world-ветви рычага и поэтому сохраняет геометрическую неразрывность с arm branch.
- Добавлены diagnostics/self-check/tests на три вида continuity: `frame ↔ frame-mounted hardpoints`, `wheel/upright ↔ wheel-mounted hardpoints`, `arm branch ↔ cyl*_bot`.

## Что остаётся P0

- Повторная живая Windows acceptance уже на R31AH: проверить continuity визуально и по HUD/self-check.
- Web UI CPU tail остаётся отдельной задачей: теперь её нужно доказывать browser trace/render-loop counters, а не только правками idle sleep.
