# RELEASE NOTES — R31AG (2026-03-25)

## Что исправлено

### 1) Desktop Animator: дорога снова видна
- Исправлена регрессия R31AF: road mesh / road edges / road stripes больше не остаются скрытыми после успешной сборки валидной геометрии кадра.
- В invalid/empty ветках road-объекты по-прежнему честно скрываются.

### 2) Цилиндры / поршни / шток
- В geometry contract добавлены explicit derived keys:
  - `cylinder_wall_thickness_m`
  - `cyl1_dead_height_m`, `cyl2_dead_height_m`
  - `cyl1_body_length_front_m`, `cyl1_body_length_rear_m`
  - `cyl2_body_length_front_m`, `cyl2_body_length_rear_m`
- Формула body length теперь соответствует текущему согласованному закону:
  - `dead_height = dead_volume / piston_area`
  - `outer_diameter = bore + 2 * wall_thickness`
  - `body_length = stroke + 2 * dead_height + 2 * wall_thickness`
- Animator больше не рисует full pin-to-pin housing shell как будто корпус цилиндра доходит до рычага.
- При росте `stroke_pos` поршень теперь движется к rod/arm side, а не к cap/frame side.
- Body shell фиксирован по длине; exposed rod отделён от fixed body shell.
- Frame-side mount markers сохранены и читаются лучше.

### 3) Front/Rear 2D views
- Playback perf-mode больше не обрезает front/rear axle views.
- Частично отключённая richer graphics на видах спереди/сзади больше не должна исчезать только из-за playback budget.

### 4) Web UI idle CPU
- Для тяжёлых follower/render components убран постоянный idle self-polling как основной механизм ожидания.
- В idle/paused состоянии render loops теперь могут полностью останавливаться и будятся через:
  - render/update
  - storage
  - focus
  - visibility
  - user interaction
- Это адресует не только timeout cadence, а сам persistent browser render-loop tail.

## Честный статус
- Это сильный corrective release, но не финальная browser/Windows acceptance.
- Для честного подтверждения CPU-tail и визуальной приёмки нужен новый SEND bundle уже на `PneumoApp_v6_80_R176_R31AG_2026-03-25`.
