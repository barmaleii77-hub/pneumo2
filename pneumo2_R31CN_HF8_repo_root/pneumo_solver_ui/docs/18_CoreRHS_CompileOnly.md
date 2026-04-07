# Core RHS export через `simulate(..., compile_only=True)` (v6.43)

## Зачем это нужно
В симуляторе много логики UI/логирования (pandas DataFrame, Excel, графики). Для:

- параметрической оптимизации (много прогонов),
- интеграции с внешними интеграторами (SciPy или собственный),
- подготовки к «полностью дифференцируемой» цепочке,

нужно уметь получить *ядро ОДУ* (правую часть) без построения таблиц и без записи файлов.

Начиная с **v6.43** модель `model_pneumo_v9_mech_doublewishbone_worldroad.py` поддерживает режим
`compile_only=True`, который возвращает компактный объект (словарь) с:

- `state0` — начальное состояние,
- `rhs(state, t)` — правая часть ОДУ (без логирования),
- `rk2_step(state, t, dt)` — один шаг интегратора RK2 (как в `simulate()`),
- `project_masses(state)` — физическая «проекция» масс/давлений (p_abs >= p_abs_min),
- служебные функции `volumes / compute_pressures / compute_flows`,
- `nodes/edges/node_index` для интерпретации состояния.

## Как использовать

### 1) Получить ядро (без симуляции)
```python
import importlib.util

spec = importlib.util.spec_from_file_location(
    'm', 'pneumo_solver_ui/model_pneumo_v9_mech_doublewishbone_worldroad.py'
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

params = {...}
test = {...}
ctx = m.simulate(params, test, dt=1e-3, t_end=3.0, compile_only=True)

state = ctx['state0']
```

### 2) Интегрировать «как в базе» (RK2)
Этот способ гарантирует, что вы получите **те же** результаты, что и обычный `simulate()`
(потому что используется тот же RK2 и та же проекция масс).

```python
state = ctx['state0']
dt = ctx['dt']
t_end = 1.0

steps = int(t_end/dt)
t = 0.0
for _ in range(steps):
    state = ctx['rk2_step'](state, t, dt)
    t += dt
```

### 3) Использовать внешний интегратор (пример: SciPy)
Внешние интеграторы обычно вызывают `fun(t, y)`.
В модели `rhs` имеет сигнатуру `rhs(state, t)`, поэтому нужен адаптер.

Важно: базовая модель после каждого шага делает `project_masses()`. В непрерывном интеграторе
это эквивалентно «граничному условию»/проекции. Если хотите максимально совпасть с базой —
используйте `rk2_step`. Если хотите непрерывность (для автодиффа/adjoint), то проекцию лучше
заменять на гладкие барьеры/параметризацию (будущий шаг).

```python
from scipy.integrate import solve_ivp

rhs = ctx['rhs']
state0 = ctx['state0']

sol = solve_ivp(
    fun=lambda t, y: rhs(y, t),
    t_span=(0.0, 1.0),
    y0=state0,
    max_step=1e-3,
)

state_end = sol.y[:, -1]
```

## Структура `state`
Состояние представляет собой один вектор:

- `state[0:3]` = `[z, phi, theta]` (рама)
- `state[3:7]` = `zw[4]` (колёса)
- `state[7:10]` = `[z_dot, phi_dot, theta_dot]`
- `state[10:14]` = `zw_dot[4]`
- `state[14:]` = массы воздуха `m_i` по всем узлам (в порядке `nodes`)

Чтобы сопоставить индекс массы с узлом, используйте `ctx['node_index']`.

## Ограничения текущего шага
- Это *экспорт ядра* без переписывания на JAX: внутри используются `numpy` и `math`.
- Проекция `project_masses` — кусочно/гладкая в зависимости от `smooth_pressure_floor`.
  Для строгой автодифф-цепочки её лучше заменить на параметризацию (например, `m = softplus(u) + m_floor`).

## Куда дальше (план)
- Вынести «чистый rhs» в отдельный модуль без `math.*` и без python-ветвлений (через smooth-гейты),
  чтобы можно было подменять backend `np` -> `jax.numpy`.
- Добавить режим интегрирования через дифференцируемый интегратор (например Diffrax) и
  градиентную оптимизацию параметров.
