# TODO_MASTER_v9 — R31G addendum (2026-03-22)

Статус прохода R31G:

- [x] **WEB-PERF-05 (partial):** найден реальный post-run CPU culprit: `components/mech_car3d/index.html` держал бесконечный `requestAnimationFrame(renderFrame)` при `W < 10 || H < 10` (скрытая/схлопнутая панель).
- [x] **WEB-VIEWPORT-09 (partial):** в follower web-components добавлен best-effort parent-viewport aware idle policy и увеличены paused/off-screen idle intervals.
- [x] **DETAIL-AUTORUN-FRESH-11:** в `pneumo_ui_app.py` baseline→auto-detail теперь после свежего baseline может принудительно игнорировать старый disk-cache для текущего теста.
- [x] **AMPLITUDE-SEMANTICS-12:** worldroad sine input в `pneumo_ui_app.py` теперь явно помечает `A` как полуразмах и показывает `p-p = 2A`.
- [ ] **WEB-PERF-05b:** собрать browser Performance trace на Windows после этого патча и подтвердить реальное снижение post-run CPU.
- [ ] **WEB-VIEWPORT-09b:** если same-origin доступ к `window.frameElement` окажется недостаточным в отдельных окружениях, добавить явный parent->iframe visibility hint channel.
