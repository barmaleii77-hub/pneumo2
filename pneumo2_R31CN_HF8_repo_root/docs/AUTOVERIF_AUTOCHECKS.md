# Автономные автопроверки (autoverif)

Цель: чтобы оптимизация/подбор параметров **не мог "тихо" уехать в физически некорректные области**.

Автопроверки запускаются автоматически:
- из `opt_worker_v3_margins_energy.py` в конце `eval_candidate_once()`;
- возвращают метрики `верификация_ok`, `верификация_штраф`, `верификация_флаги`, `верификация_сообщение`;
- штраф `верификация_штраф` прибавляется к целевой функции каждого теста.

## Что проверяется

1) **NaN/Inf в метриках**
   - если в метриках кандидата есть NaN/Inf → большой штраф (`autoverif_penalty_nonfinite`).

2) **Схема “заперта”**
   - `enforce_scheme_integrity` должен быть `true`;
   - `enforce_camozzi_only` должен быть `true`;
   - иначе штраф (`autoverif_penalty_invariant`) и флаги `scheme_lock_off`/`camozzi_only_off`.

3) **Механическая самопроверка (если модель вернула)**
   - если `mech_selfcheck_ok=0` → штраф (`autoverif_penalty_selfcheck`) и флаг `mech_selfcheck_fail`.

4) **Энергетический баланс (если есть)**
   - если `|ошибка_энергии_газа_отн| > autoverif_energy_err_rel_max` → штраф и флаг `energy_balance`.

5) **Неотрицательность энтропийного смешения (если есть)**
   - если `энтропия_смешение_Дж_К < autoverif_entropy_mix_min` → штраф и флаг `entropy_mix_negative`.

6) **Геометрические константы (колея/база)**
   - проверяются `колея`/`база` относительно `autoverif_track_expected_m`/`autoverif_wheelbase_expected_m`.

## Настройка

Все параметры задаются в `pneumo_solver_ui/default_base.json`:

- `autoverif_enable` — включить/выключить модуль.
- `autoverif_strict` — если `true`, то вместо штрафов выбрасывается исключение (жёсткий режим).
- `autoverif_require_scheme_lock` — требовать `enforce_scheme_integrity=true` и `enforce_camozzi_only=true`.

Порог/штрафы:
- `autoverif_energy_err_rel_max`
- `autoverif_entropy_mix_min`
- `autoverif_penalty_nonfinite`
- `autoverif_penalty_invariant`
- `autoverif_penalty_selfcheck`

## Как отключить (если вам нужно экспериментировать)

1) Самый простой способ — `autoverif_enable=false`.
2) Если хотите временно снять блокировку схемы — можно `autoverif_require_scheme_lock=false`, но это уменьшает “защиту от скрытых ошибок”.

