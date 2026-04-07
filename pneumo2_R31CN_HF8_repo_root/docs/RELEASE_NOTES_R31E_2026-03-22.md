# RELEASE NOTES — R31E (2026-03-22)

Основа: `R31D_STRICTCLOSURE_TRIAGECURRENT`

## Что изменено

Этот шаг **не меняет solver points и не переписывает геометрию подвески**.
Исправляется именно логика acceptance/reporting:

- `geometry_acceptance_contract`: acceptance gate теперь считает `XY mismatch` **только по wheel_center ↔ road_contact**.
- `frame_corner ↔ wheel_center` и `frame_corner ↔ road_contact` больше **не считаются acceptance-ошибкой**; они сохраняются как отдельные наблюдаемые оффсеты `XYfw/XYfr`.
- `desktop_animator.geometry_acceptance`: тот же канон применён в runtime/self-check/HUD.
- `desktop_animator.app`: прибор `triplet_xy` теперь показывает **wheel-road XY** и подписан явно.
- `desktop_animator.self_checks`: warning-текст уточнён до `wheel-road XY mismatch`.

## Зачем

В SEND bundle `SEND_20260321_190236_auto-exit_bundle.zip` старый gate поднимал `WARN` (`ПЗ: XY mismatch 31.574 мм`),
хотя реальный `wheel_center ↔ road_contact` XY mismatch в `anim_latest.npz` равен нулю,
а `31.574 мм` относится к structural `frame_corner` offset.

## Что подтвердилось после фикса

- Пересчёт geometry acceptance на том же SEND bundle даёт:
  - `release_gate = PASS`
  - `release_gate_reason = solver-point contract consistent`
  - `XYwr = 0.000 мм`
  - `XYfw/XYfr = 31.574 / 31.574 мм`
- `validate_send_bundle(...)` на том же ZIP остаётся `ok=true`.
- Общий `health_report.ok` для SEND bundle всё ещё `false`, но уже **по другой причине**: внешние pointer/path внутри bundle не зеркалированы и diagnostics не полностью воспроизводимы из одного ZIP.

## Изменённые файлы

- `pneumo_solver_ui/geometry_acceptance_contract.py`
- `pneumo_solver_ui/desktop_animator/geometry_acceptance.py`
- `pneumo_solver_ui/desktop_animator/self_checks.py`
- `pneumo_solver_ui/desktop_animator/app.py`
- `tests/test_geometry_acceptance_release_gate.py`
- `tests/test_geometry_acceptance_solver_points.py`
- `docs/RELEASE_NOTES_R31E_2026-03-22.md`
