# RELEASE NOTES — PneumoApp_v6_80_R176 (Windows release r7)

Дата сборки (UTC): 2026-03-15 13:55 UTC
Базовый снимок: `PneumoApp_v6_80_R176_WINDOWS_RELEASE_2026-03-15_r6_geometry_gate_summary.zip`

## Что входит в релиз

- Канонический Windows runtime без цели поддерживать legacy/multiplatform сценарии.
- Уже встроенные r1–r6 фиксы по autosave, suite-state, dependency/runtime stability,
  frame geometry contract, frame-corner solver points, Desktop Animator acceptance HUD,
  web/send-bundle acceptance visibility и release-quality geometry gate.
- Новое в r7: устранение корневого Camozzi-регресса по скорости/радиусу колеса/режиму координаты колеса,
  который ломал world-path и делал положение колеса/рамы ниже дороги.

## Что добавлено в r7

- `model_pneumo_v9_doublewishbone_camozzi.py`
  - стартовая кинематика читает **только** `vx0_м_с`;
  - статика/контакт/пост-процессинг читают канонические wheel-radius keys;
  - post-process больше не перечитывает legacy `wheel_coord_mode`.
- `desktop_animator/self_checks.py`
  - добавлены:
    - `speed_meta_vx0_t0_err_mps`
    - `speed_path_x_consistency_max_err_mps`
    - `wheel_xy_pose_max_err_m`
  - теперь self-check явно ловит потерю стартовой скорости и рассогласование world wheel coordinates.
- `tests/test_camozzi_speed_geometry_contract.py`
  - runtime regression на canonical speed/radius flow и animator self-check.

## Подтверждённый эффект

На реальном send-bundle `SEND_20260314_193024_auto-exit_bundle.zip` до фикса было:

- `meta.vx0_м_с = 11.11`, но `df_main["скорость_vx_м_с"][0] = 0.0`
- `колесо_относительно_дороги_ЛП_м @ t0 < 0`
- `рама_относительно_дороги_ЛП_м @ t0 < 0`

После фикса smoke на текущем дереве даёт:

- `скорость_vx_м_с @ t0 = 11.11`
- положительное `колесо_относительно_дороги_ЛП_м`
- положительное `рама_относительно_дороги_ЛП_м`

## Принципы этой сборки

- Один канон ключей, без runtime-алиасов как стратегии.
- Анимация и compare/validation UI — валидаторы расчёта, а не декоративные подмены.
- Если модель теряет `vx0_м_с` или радиус колеса, это должно быть поймано self-check и тестами.
- Сборка ориентирована на Windows.

## Что очищено перед упаковкой

- `.pytest_cache/`
- все `__pycache__/`
- `runs/index.json`
- `runs/run_registry.jsonl`

## Проверка сборки

```bash
python -m compileall -q pneumo_solver_ui tests app.py START_PNEUMO_APP.py
pytest -q tests/test_camozzi_speed_geometry_contract.py           tests/test_camozzi_rel0_yaw_canon.py           tests/test_geometry_acceptance_solver_points.py           tests/test_geometry_acceptance_release_gate.py
pytest -q $(ls tests/test_*.py | sort | sed -n '1,25p')
pytest -q $(ls tests/test_*.py | sort | sed -n '26,50p')
pytest -q $(ls tests/test_*.py | sort | sed -n '51,73p')
```

Результат:
- compileall: OK
- pytest: 186 passed
