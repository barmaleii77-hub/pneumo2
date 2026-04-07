# TODO / WISHLIST addendum R31P (2026-03-24)

## Закрыто этим шагом

- [x] **WIN-GL-13:** по Windows manual SEND-bundle локализован и закрыт crash-path: floating `dock_3d` в detached layout больше не используется на GL build.
- [x] **LOG-SEQ-14:** strict loglint больше не даёт ложный `non-monotonic seq` при смешении parent UI и child Desktop Animator в одном session log.

## Остаётся открытым

- [ ] **WIN-ACCEPT-12b:** повторно принять R31P на реальном Windows viewport/driver stack.
- [ ] **META-ROAD-15:** довести canonical `road_width_m` в export/meta, чтобы Animator не уходил в derived warning.
- [ ] **WEB-PERF-05b:** measured browser Performance trace на Windows (CPU/FPS/idle after solve).
- [ ] **SOLVER-PTS-06:** добить solver-points completeness для полностью честной подвесочной геометрии.
- [ ] **CYL-PACK-11:** финализировать packaging contract цилиндров/штоков/поршней.

## Практический смысл

После R31P:
- manual SEND-bundle дал не абстрактный “Windows что-то падает”, а конкретный reproducible fix-path;
- detached layout остаётся usable, но 3D OpenGL окно больше не вынуждается в floating mode;
- strict bundle health меньше шумит ложными seq-ошибками multi-process логирования.
