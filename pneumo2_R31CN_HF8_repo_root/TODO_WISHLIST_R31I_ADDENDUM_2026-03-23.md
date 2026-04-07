# TODO / WISHLIST addendum R31I (2026-03-23)

## Закрыто этим шагом

- [x] **RING-META-01:** ring export meta больше не теряет `scenario_json` рядом с generated sidecars (`*_road.csv`, `*_axay.csv`).
- [x] **RING-SPEED-02:** canonical `vx0_м_с` для ring-export теперь выводится из authored ring-spec даже если stale suite row содержит `0.0`.
- [x] **COCKPIT-SEG-03:** segment overlays добавлены в minimap/cockpit beyond mech_car3d.
- [x] **COCKPIT-SEG-04:** road profile panel теперь показывает segment bands и текущий сегмент.

## Остаётся открытым

- [ ] **WEB-PERF-05b:** measured browser Performance trace на Windows (CPU/FPS/idle after solve).
- [ ] **SOLVER-PTS-06:** добить solver-points completeness для полностью честной подвесочной геометрии.
- [ ] **BUNDLE-HISTORY-07:** старые уже собранные bundle с `vx0_м_с=0` остаются историческими; нужен только forward-fix и при желании отдельный re-export.

## Практический смысл

После R31I будущие ring bundle должны:
- корректно тащить `scenario_json` в anim/export pipeline;
- иметь каноническую speed meta без тихого `vx0_м_с=0`;
- показывать segment highlighting не только в 3D, но и в cockpit/minimap.
