# RELEASE NOTES — R31F (2026-03-22)

База: `PneumoApp_v6_80_R176_R31E_GEOM_ACCEPT_WR_XY_2026-03-22`

## Что исправлено

### 1) Явная семантика амплитуды синуса в Ring UI
- Поля ввода SINE теперь подписаны как **`Амплитуда A (полуразмах), мм`**.
- Прямо под полями показывается производный `p-p = 2A`.
- Добавлено жёсткое пояснение:
  - `A=100 мм` означает профиль **от -100 до +100 мм** относительно локального нуля,
  - полный размах `p-p = 200 мм`.

### 2) Авто-детальный прогон после baseline теперь действительно пересчитывается
- Раньше после свежего baseline секция detail могла тихо подхватить **старый detail cache** с диска.
- Визуально это выглядело как «автозапуск есть, но не считает».
- Теперь после свежего baseline для текущего test/cache_key detail cache **игнорируется ровно один раз**,
  и выполняется реальный пересчёт детального лога.

### 3) Явная наблюдаемость источника detail-лога
- UI теперь показывает, откуда взят детальный лог:
  - **свежий расчёт**,
  - или **кэш**.
- При bypass кэша после baseline выводится явное сообщение.
- При загрузке из кэша выводится отдельное сообщение, а не «тишина».

## Изменённые файлы
- `pneumo_solver_ui/ui_scenario_ring.py`
- `pneumo_solver_ui/app.py`
- `pneumo_solver_ui/detail_autorun_policy.py`
- `tests/test_r33_ring_sine_input_semantics.py`
- `tests/test_r33_detail_autorun_policy.py`

## Что проверено
- Targeted pytest slice: **10 passed**
  - `test_r27_ring_sine_phase_amplitude.py`
  - `test_r30_ring_segment_summary.py`
  - `test_r30_ring_sine_segment_local_metrics.py`
  - `test_r32_ring_closure_policy_and_ui_labels.py`
  - `test_r33_ring_sine_input_semantics.py`
  - `test_r33_detail_autorun_policy.py`

## Что сознательно НЕ заявляется
- Этот шаг не заявляет, что закрыт весь UI/launcher/runtime проект.
- Этот шаг бьёт ровно в две живые проблемы:
  1. двусмысленность `A` vs `p-p`,
  2. ложное ощущение, что detail после baseline «не считает», потому что подхватывался disk cache.
