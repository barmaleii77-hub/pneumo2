# Matematika65 — WorldRoad precompute fix

## Контекст

В проекте есть два режима задания дороги:

1) **Per-wheel road**: пользователь задаёт `road_func(t)->z_road[4]` и (опционально) `road_dfunc(t)->dz/dt`.
2) **World-road**: задаётся поверхность `z = z(x, y)` (например, кочка/волны) и движение машины по плоскости
   определяется интеграцией `v, yaw, x, y` из `ax(t), ay(t)`.

Для world-road в `pneumo_solver_ui/road_surface.py` есть функция:

- `precompute_world_road(...)->WorldRoadCache`

которая предвычисляет `z_wheels(t)` и `zdot_wheels(t)` для 4 колёс, после чего
`build_road_functions_from_world_cache()` возвращает функции `road_func/road_dfunc`.

## Ошибка в базе v6.24

В `model_pneumo_v9_mech_doublewishbone_worldroad.py` вызов делался с именами аргументов:

- `vx0`, `vmin`, `yaw_rate_limit`

а функция ожидает:

- `v0`, `eps_v`, `limit_yaw_rate`

В результате возникало исключение (TypeError), и модель **тихо** откатывалась к per-wheel road.

## Исправление в Matematika65

Внесены изменения:

- исправлены имена аргументов: `v0/eps_v/limit_yaw_rate`
- добавлены `yaw0/x0/y0` (стартовое положение)
- добавлен `warnings.warn(...)` при падении precompute и безопасный fallback
- чтение геометрии: допускаются ключи `база_м/колея_м` и старые `база/колея`

## Как проверить, что world-road реально используется

1) В тесте задайте `road_surface` (не `road_func`).
2) Запустите модель v9 world-road.
3) Если precompute не упал, `road_func/road_dfunc` будут построены из `WorldRoadCache`,
   а профиль под колёсами станет зависеть от траектории `x(t),y(t),yaw(t)`.

При падении precompute в логе/консоли появится предупреждение `WorldRoad: precompute failed ...`.
