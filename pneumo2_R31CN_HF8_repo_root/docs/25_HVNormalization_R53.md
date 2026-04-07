# Hypervolume (HV) — R53

## Что считаем
- 2 цели минимизации: `obj1`, `obj2`
- feasible если `penalty <= penalty_tol`

## Стабилизация
- сначала переводим в maximization: `Y_max = -Y_min`
- затем робастно нормализуем по квантилям в [0..1]
- считаем HV в [0..1]^2 относительно ref=(0,0)

Реализация: `pneumo_solver_ui/pneumo_dist/hv_tools.py`
