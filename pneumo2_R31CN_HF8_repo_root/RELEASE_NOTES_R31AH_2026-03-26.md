# RELEASE_NOTES_R31AH_2026-03-26

## Что это за релиз

R31AH — corrective release по **геометрической неразрывности** solver/export/animator и по индексации архива чатов.

Этот проход не пытается замазать старые симптомы в Animator consumer-side кодом. Вместо этого исправлен источник: solver/export теперь обязан держать frame-mounted hardpoints жёстко приклеенными к раме и rod-side cylinder mount — к выбранной ветви рычага.

## Что исправлено

### Solver / export
- `frame_corner` больше не подменяется world XY wheel-center.
- Все frame-mounted точки (`frame_corner`, inboard arm points, `cyl*_top`) теперь проходят через **единый rigid-frame transform**, восстановленный из lower frame contour.
- `cyl*_bot` теперь вычисляется как интерполяция по **фактической world-геометрии выбранной ветви рычага**, а не через смешанный локальный XY/Z путь.
- Linear-arm path приведён к той же политике continuity для frame-side points.

### Diagnostics / self-check / control
- Добавлены continuity-метрики:
  - `max_frame_mount_body_local_drift_m`
  - `max_hub_mount_pairwise_drift_m`
  - `max_cyl1_bot_arm_offset_m`
  - `max_cyl2_bot_arm_offset_m`
- HUD/self-check теперь поднимают FAIL/WARN, если:
  - frame-mounted hardpoints дрейфуют относительно рамы;
  - hub/wheel hardpoints дрейфуют относительно wheel/upright;
  - `cyl*_bot` уходит с ветви рычага.

### Source-data defaults / fallbacks
- Fallback-постановка frame-side cylinder mounts в модельных code paths выровнена с каноническими дефолтами source-data: span берётся от `ширина_рамы`, высота — от `высота_рамы`.

### Docs / context
- `mhtml.zip` проиндексирован: выделены точные дубли и тематические кластеры.
- TODO/WISHLIST уточнены: geometric continuity становится явным P0 gate; Web UI CPU остаётся P0, но переводится на browser trace/render-loop truth.

## Что проверено локально
- `py_compile`: PASS
- `compileall`: PASS
- targeted pytest slice: 22 passed

## Что остаётся открытым
- Нужен свежий Windows SEND bundle уже на R31AH, чтобы подтвердить continuity на живом runtime.
- Web UI post-run CPU tail **не объявляю закрытым**: в этом релизе backlog/контроль исправлены, но новый browser-side trace bundle ещё нужен.
- Если пользовательский кейс снова покажет off-arm drift или frame drift, это уже должно ловиться новой диагностикой bundle/self-check, а не только глазами.
