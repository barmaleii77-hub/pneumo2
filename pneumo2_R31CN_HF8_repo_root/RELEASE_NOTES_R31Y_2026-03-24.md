# RELEASE_NOTES_R31Y_2026-03-24

## Что исправлено

### 1) Dense road surface drift / resize-dependent behaviour
- Dense road surface в Desktop Animator больше не берёт lateral normal из текущего viewport slice.
- В `Car3DWidget.set_bundle_context(...)` добавлен bundle-level cache world path normals по полному `s_world / путь_x_м / путь_y_м`.
- При построении road mesh текущий видимый диапазон теперь использует эти world normals после локализации, а не локальную аппроксимацию из текущего окна.
- Это адресует симптом, который пользователь описывал как drift/странное поведение mesh/grid, зависящее от размера 3D окна и от текущего playback window.

### 2) 3D window UX / docking regression
- Live GL 3D снова **docked by default**.
- Убран forced startup policy, при которой 3D сразу запускался во внешнем top-level окне и переставал нормально пристыковываться обратно.
- Введён новый `layout_version` (`r31y_safe_gl_redock_v1`), чтобы старый persisted detached-only layout не возвращался после апгрейда.
- Safe separate window для 3D сохранён, но используется только по **явному detach** (`Разнести панели` / toggle в меню `Окна`).
- При возврате из external window панель снова показывается как обычный dock; при detach dock скрывается, чтобы не оставлять confusing placeholder UX.

### 3) Stale lite/perf mode after manual playback stop
- Добавлен `_refresh_after_playback_stop()`.
- Manual stop playback теперь принудительно делает final frame refresh с `playing=False`, поэтому auxiliary panes/labels/overlays больше не остаются в stale облегчённом состоянии до следующего внешнего события.

### 4) Cylinder / rod / piston visual clarity
- По свежему SEND bundle проверено, что экспортированные `cyl*_top` — frame-side, а `cyl*_bot` — arm-side точки; проблема была не в mount-point export, а в visual consumer path.
- Жёлтые scatter-markers для piston plane переведены в **debug-only / hidden-by-default**, чтобы их не путали с frame mounts.
- `cylinder_visual_state_from_packaging(...)` теперь дополнительно отдаёт `housing_seg` — честную transparent full shell по solver-axis до появления exporter-side gland/body-end contract.
- Animator показывает transparent housing shell + exact rod + exact piston plane, не притворяясь, что знает точную внешнюю границу корпуса без отдельного contract key.

## Обновления контекста / docs
- Обновлены `docs/11_TODO.md`, `docs/12_Wishlist.md`, `docs/WISHLIST.json`.
- Обновлены `01_PARAMETER_REGISTRY.md` и `DATA_CONTRACT_UNIFIED_KEYS.md` с фиксацией honest fallback до появления explicit `gland/body-end` contract.

## Что ещё НЕ считается принятым окончательно
- Всё ещё нужен свежий Windows SEND bundle уже на R31Y, чтобы живьём подтвердить:
  1. отсутствие drift dense road surface при resize 3D окна,
  2. понятную видимость piston plane внутри цилиндров,
  3. detach/re-dock UX 3D окна,
  4. отсутствие CPU tail после завершения расчётов и после stop playback.
- Exporter всё ещё не отдаёт explicit `cyl*_gland_xyz` / body-end contract, поэтому transparent housing shell остаётся честным fallback, а не финальной идеальной упаковкой.
