# Smooth-flow режим для дросселей (fully-differentiable)

## Что добавлено

В механико-пневматической модели:

- `pneumo_solver_ui/model_pneumo_v9_mech_doublewishbone_worldroad.py`

добавлен **опциональный** режим *smooth-flow* для расчёта расхода через дроссели.

Цель — убрать разрывы производных, возникающие из-за piecewise-переключения:

- subsonic ↔ choked (по критическому отношению давлений)
- смена направления потока при Δp = 0

Это важно для:
- градиентной оптимизации (LBFGS/Adam и т.п.),
- автодиффа (JAX/PyTorch/CasADi),
- устойчивости оптимизации многопараметрических моделей.

По умолчанию **выключено**, чтобы не менять поведение базовой версии.

---

## Как включить

В params:

```json
{
  "pneumo_flow_smooth_mode": true,
  "pneumo_flow_smooth_k_pr": 80.0,
  "pneumo_flow_smooth_k_sign": 0.001,
  "pneumo_flow_smooth_eps_dp_Pa": 1.0
}
```

---

## Что именно сглаживается

### 1) choked/subsonic ветви

Классическая формула расхода через отверстие имеет две ветви:

- **choked** (захлопывание) при `pr = p_dn/p_up <= pr_crit`
- **subsonic** при `pr > pr_crit`

В smooth-режиме вычисляются обе ветви и смешиваются:

- `mdot = (1-w)*mdot_choked + w*mdot_sub`
- `w = 0.5*(1+tanh(0.5*k_pr*(pr - pr_crit)))`

`k_pr` задаёт резкость перехода:
- больше → ближе к piecewise,
- меньше → более плавно, но может чуть смазывать физику в узкой зоне вокруг `pr_crit`.

### 2) Направление потока (signed flow)

В piecewise-логике «вверх/вниз» выбираются через `if p1>p2`.

В smooth-режиме:

- upstream/downstream выбираются через гладкий `|Δp| ≈ sqrt(Δp^2 + eps^2)`
- знак расхода: `sgn = tanh(k_sign*Δp)`

`eps_dp_Pa` задаёт сглаживание в Паскалях.

---

## Где это используется в модели

- Внутри `compute_flows()` для ребра `kind == 'orifice'`:
  - при `pneumo_flow_smooth_mode=True` используется `mdot_orifice_signed_smooth(...)`
  - иначе — старая `mdot_orifice_signed(...)`

Параметры режима записываются в `df_atm`:
- `pneumo_flow_smooth_mode`
- `pneumo_flow_smooth_k_pr`
- `pneumo_flow_smooth_k_sign`
- `pneumo_flow_smooth_eps_dp_Pa`

---

## Практические рекомендации

- Для стартовой градиентной оптимизации:
  - `pneumo_flow_smooth_mode=true`
  - `k_pr=40..120`
  - `k_sign=1e-4..1e-3`
  - `eps_dp_Pa=1..50` (подбирается под масштаб Δp)

- Для финальной валидации «как в железе»:
  - `pneumo_flow_smooth_mode=false` (piecewise)

---

## Ограничения и будущее развитие (TODO)

- добавить smooth-аналог для клапанов (check/reg/relief) как отдельный флаг (частично уже есть `smooth_valves`);
- унифицировать гладкие функции в общий модуль (см. `pneumo_solver_ui/smooth_math.py`);
- добавить режим «sweep smoothness»: начать с мягкого, постепенно увеличивать `k_pr/k_sign` (continuation).

