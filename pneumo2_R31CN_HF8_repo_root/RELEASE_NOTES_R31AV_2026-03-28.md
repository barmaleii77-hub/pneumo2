# Release notes — R31AV (2026-03-28)

## Что исправлено

- Исправлен runtime-блокер страницы `03_Optimization.py`: возвращён отсутствующий `import os`, из-за которого запуск координатора падал на `env = os.environ.copy()`.
- Страница распределённой оптимизации теперь запускает координатор с каноническими путями текущей сборки:
  - `model_pneumo_v9_doublewishbone_camozzi.py`
  - `opt_worker_v3_margins_energy.py`
  - `default_base.json`
  - `default_ranges.json`
  - `default_suite.json`
- Дефолтные objective keys приведены к реальным метрикам worker-а и к пользовательскому приоритету:
  1. `метрика_комфорт__RMS_ускор_рамы_микро_м_с2`
  2. `метрика_крен_ay3_град`
  3. `метрика_энергия_дроссели_микро_Дж`
- CLI-координаторы (`dist_opt_coordinator.py`, `dbqueue_coordinator.py`) больше не стартуют со stale v8 model defaults и теперь корректно добавляют в `sys.path` и project root, и `pneumo_solver_ui`.
- Дефолты UI/StageRunner синхронизированы с архивом диагностики:
  - `ui_opt_minutes = 10`
  - `ui_jobs` capped by diagnostics hint `24`
  - `opt_use_staged = True`
  - `warmstart_mode = surrogate`
  - `surrogate_samples = 8000`
  - `surrogate_top_k = 64`
  - `sort_tests_by_cost = True`
  - `ui_seed_candidates = 1`
  - `ui_seed_conditions = 1`
  - `ui_suite_preset = worldroad_flat`
  - default selected suite id = `75ea0ffc-2fa0-4bed-82da-e4f77aab1779` (если этот тест существует в suite)
  - `problem_hash_mode = stable`
  - `calib_mode_pick = minimal`

## Что намеренно не менял

- `default_base.json` и `default_ranges.json` как численные исходные данные не трогал: сравнение с архивом диагностики показало только несущественные float-rounding расхождения.
- Не включал тесты в `default_suite.json` автоматически: архив диагностики отражает UI state, а не канон того, какие tests всегда должны быть enabled.

## Эффект

- Оптимизационная страница перестаёт падать на NameError.
- Дефолты больше не указывают на stale метрики/модель.
- Оптимизация по умолчанию теперь реально нацелена на минимизацию вертикальной и поперечной динамики рамы, а не на старый surrogate-набор `m_margin_*`.
