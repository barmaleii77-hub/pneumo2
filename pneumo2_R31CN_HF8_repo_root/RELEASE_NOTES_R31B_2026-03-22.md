# RELEASE NOTES — R31B follow-up (2026-03-22)

База: `PneumoApp_v6_80_R176_WINDOWS_CLEAN_R25_2026-03-20_R31_DIAGNOSTICS_WEB_GL_CONTACT_PATCHED.zip`.

Этот пакет собирает в одном чистом релизе:
- ring amplitude/summary/export fix из предыдущего R31A-патча;
- закрытие 5 красных тестов из аудита R31A;
- очистку релиза от `__pycache__`.

## Что исправлено

### Ring / summary / export
- `pneumo_solver_ui/scenario_ring.py`
  - добавлен канонический расчёт длины сегмента `_segment_length_canonical_m(...)`;
  - `summarize_ring_track_segments(...)` больше не требует явный `length_m` и считает длины так же, как генератор;
  - локальная амплитуда `A` считается как `max(|z - median|)`, а не как `0.5 * p-p`;
  - при `generate_ring_scenario_bundle(...)` вычисленное `length_m` сериализуется в `scenario_json`.
- `pneumo_solver_ui/ui_scenario_ring.py`
  - preview/suite выводит `amplitude A` отдельно от `p-p=max-min (НЕ A)`;
  - удалён последний прямой `use_container_width=True` в активном runtime-источнике.

### Solver-points canon
- `pneumo_solver_ui/solver_points_geometry.py`
  - для canonical solver-points в активных генераторах `frame_corner.x/y` теперь жёстко совпадает с `wheel_center.x/y`;
  - убран скрытый frozen track/2 fallback для `frame_corner` в explicit DW2D helper.

### Idle / playback scheduling
- `pneumo_solver_ui/app.py`
- `pneumo_solver_ui/pneumo_ui_app.py`
- активные HTML-компоненты в `pneumo_solver_ui/components/...`
  - idle sleep tightened: `document.hidden ? 800 : 500` вместо `5000 : 2500`.

### Hygiene
- из релизного дерева удалены все `__pycache__`.

## Валидация
- точечный red-suite из аудита R31A: **5/5 passed**;
- расширенный набор вокруг patched областей: **24/24 passed**;
- полный `pytest`: **251 passed in 34.02s**.
