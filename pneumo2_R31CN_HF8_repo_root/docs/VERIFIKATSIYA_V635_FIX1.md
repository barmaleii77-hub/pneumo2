# Verifikatsiya V6.35 WinSafe Fix1

Дата: 2026-01-30

Этот пакет — "следующий шаг" поверх базы **UnifiedPneumoApp_UNIFIED_v6_35_WINSAFE**.

Фокус релиза: **поиск/устранение скрытых и явных ошибок**, повышение доверия к матмодели (особенно на крайних режимах), и внедрение **автономных автопроверок**, которые работают *внутри оптимизации*.

## 1) Исправления багов

### 1.1 ISO 6358: вакуум‑режим (pr <= 0) в v9 моделях

**Проблема:** в `model_pneumo_v9_doublewishbone_camozzi.py` и `model_pneumo_v9_mech_doublewishbone_r48_reference.py` функция `iso6358_phi(pr, ...)` возвращала `0.0` при `pr<=0`.

Это неправильно: при сильном перепаде давления (вакуум на выходе) поток находится в режиме захлёбывания, и `phi` должна стремиться к 1.0.

**Симптом:** падали unit‑tests `tests/test_iso6358_phi.py`.

**Исправление:** реализован вакуум‑safe блок:
- `pr <= 0 → 1.0`
- `pr >= 1 → 0.0`
- `not finite → 0.0`

## 2) Защита от скрытых ошибок: неизменяемость схемы и "только Camozzi"

В базе флаги схемной защиты были выключены в `default_base.json`:
- `enforce_scheme_integrity = false`
- `enforce_camozzi_only = false`

**Что сделано:**
- В `default_base.json` флаги включены по умолчанию (`true`).
- Для **всех основных моделей** добавлены проверки схемы внутри `simulate()`:
  - сверка fingerprint топологии (узлы/рёбра) с эталоном
  - проверка, что все элементы в схеме имеют коды из `component_passport.json`

### 2.1 Два эталонных fingerprint (важно)

Оказалось, что в проекте реально живут **две разные топологии схемы**:

1) `scheme_fingerprint.json` — 46 узлов / 70 рёбер (основная схема v9/v10)
2) `scheme_fingerprint_v8_r48.json` — 49 узлов / 73 ребра (ветка v8 и R48 reference)

Чтобы не ломать v8/R48 и одновременно жёстко фиксировать схему, добавлен второй эталон:
- `pneumo_solver_ui/scheme_fingerprint_v8_r48.json`

И в моделях v8/R48 по умолчанию используется именно он.

## 3) Автономные автоматические самопроверки (Autoverif)

Добавлен новый модуль:
- `pneumo_solver_ui/verif_autochecks.py`

Он запускается **изнутри** оптимизационного воркера и добавляет в метрики:
- `верификация_ok`
- `верификация_штраф`
- `верификация_флаги`
- `верификация_сообщение`

### 3.1 Что проверяется автоматически

1) **NaN/Inf в метриках** → штраф `autoverif_penalty_nonfinite`
2) **Отключение защиты схемы** (`enforce_scheme_integrity/enforce_camozzi_only`) → штраф `autoverif_penalty_invariant`
3) **Провал механической самопроверки**, если модель отдала `mech_selfcheck_ok=0` → штраф `autoverif_penalty_selfcheck`
4) **Контроль геометрии** (колея/база должны быть фиксированы как в базе) → штраф `autoverif_penalty_invariant`
5) **Баланс энергии газа** (`ошибка_энергии_газа_отн`) если он выведен моделью → штраф (масштабируется)
6) **Неотрицательность энтропийного смешения** (`энтропия_смешение_Дж_К`) если она выведена моделью

### 3.2 Где включается/настраивается

В `pneumo_solver_ui/default_base.json` добавлены параметры:
- `autoverif_enable`
- `autoverif_strict`
- `autoverif_require_scheme_lock`
- `autoverif_energy_err_rel_max`
- `autoverif_entropy_mix_min`
- `autoverif_penalty_nonfinite`
- `autoverif_penalty_invariant`
- `autoverif_penalty_selfcheck`
- `autoverif_track_expected_m`
- `autoverif_wheelbase_expected_m`
- `autoverif_geom_tol_m`

По умолчанию **strict=false**, то есть оптимизация не падает, а получает штраф.

### 3.3 Интеграция в оптимизацию

Файл:
- `pneumo_solver_ui/opt_worker_v3_margins_energy.py`

Изменения:
- метрики `mech_selfcheck_ok/msg` подхватываются из `df_atm`
- автопроверка вызывается в конце `eval_candidate_once()`
- штраф `верификация_штраф` добавляется к итоговому штрафу теста

## 4) Самопроверки/тесты

- Исправлены падающие `tests/test_iso6358_phi.py`
- Добавлен новый smoke‑тест `tests/test_autoverif_smoke.py`

Запуск:
```bash
pytest -q
```

## 5) Что НЕ делалось (осознанно)

- Не удалялись и не "ужимались" тяжёлые папки проекта (кроме кешей тестов), чтобы не ломать рабочий функционал.
- Не менялась физика основного решателя/интегратора — только исправления очевидных несоответствий и добавление автомониторинга.

## 6) Контрольные суммы (SHA256)

База:
- `UnifiedPneumoApp_UNIFIED_v6_35_WINSAFE.zip` — `6c80eb6a14e211d5555a4b7446d3af17b5ca2d25f9d41c5e8741aaa8f5bc0c53`

Выходной архив Verifikatsiya:
- `VerifikatsiyaV635WinSafeFix1.zip` — вычислите локально (хэш зависит от состава архива).
  Команда: `sha256sum VerifikatsiyaV635WinSafeFix1.zip` (или PowerShell: `Get-FileHash ... -Algorithm SHA256`).

