# Release Notes — ETALON v6_80 R116 (integrated)

Дата сборки: 2026-02-18

## Ключевые изменения (P0/P1)

### 1) Оптимизация: стабильный problem_hash по умолчанию

- Введён единый переключатель режима вычисления `problem_hash` для distributed optimization:
  - `PNEUMO_OPT_PROBLEM_HASH_MODE=stable` (по умолчанию)
  - `PNEUMO_OPT_PROBLEM_HASH_MODE=legacy`

- В режиме **stable** hash считается по содержимому задачи:
  - sha256(model.py) + sha256(worker.py)
  - фиксированная часть `base.json` (ключи из `ranges.json` исключаются)
  - набор optimizable keys (ключи `ranges.json`)
  - `suite.json`
  - `extra` (безопасное подмножество cfg: objective_keys/penalty_targets)

- В режиме **legacy** используется старое поведение (paths + cfg + sha) для совместимости со старыми run_id.

### 2) Исправлена совместимость stable_hash_problem между скриптами

- `pneumo_solver_ui/pneumo_dist/trial_hash.py` теперь поддерживает оба исторических API:
  - `stable_hash_problem(spec: ProblemSpec)`
  - `stable_hash_problem(model_py=..., worker_py=..., base=..., ranges=..., suite=..., extra=...)`

Это устраняет падения старых инструментов (Ray/Dask) из‑за несовпадения сигнатур.

### 3) Verifikatsiya: исправления энерго‑энтропийного аудита

- `model_pneumo_v8_energy_audit_vacuum.py` обновлён согласно VerifikatsiyaV680Fix2:
  - консервативное обновление энергии через `U(t)` и восстановление `T` через обратную функцию `T_from_h`
  - более корректная (монотонная) модель смешения энтропии при массообмене
  - снижена вероятность «энергия не сохраняется» и «энтропия не монотонна» на граничных режимах

### 4) ISO6358: управляемая плотность ρ_ANR

- Добавлен переключатель `PNEUMO_ISO6358_RHO_ANR_MODE`:
  - `norm` (по умолчанию) — нормативная ρ_ANR=1.185 кг/м³ (ISO 8778)
  - `calc` — вычислять ρ_ANR из p_ANR и T_ANR по идеальному газу

- `iso6358_system.py` теперь использует `rho_ANR_ref()` (динамически), поэтому переключатель влияет на расчёты без правки кода.

### 5) Алгоритмы оптимизации: сценарии

- При разворачивании `suite.json` по scenario_matrix:
  - сценарий `nominal` **не получает суффикс**, имя теста остаётся историческим
  - остальные сценарии получают суффикс `__sc_<id>`
  - добавлены `_meta_base_test` и `_meta_scenario_id` для трассировки

## Контракты/реестры

- Добавлен статический генератор реестра ключей:
  - `pneumo_solver_ui/tools/build_key_registry.py`
  - генерирует `pneumo_solver_ui/contracts/generated/key_usage_index.json` и `keys_registry.yaml`

- Добавлен агрегатор TODO/WISHLIST по всем распакованным архивам:
  - `pneumo_solver_ui/tools/aggregate_todo_wishlist.py`
  - генерирует `docs/consolidated/consolidated_todo_wishlist.*`

## Замечания по совместимости

- Новые env‑переключатели полностью обратимы.
- `stable` режим `problem_hash` меняет идентификаторы задач (ожидаемо), но `legacy` режим позволяет воспроизвести старые.

