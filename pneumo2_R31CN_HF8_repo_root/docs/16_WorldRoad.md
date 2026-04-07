# 16) World-road: z = f(x, y) и корректный pen_dot

## Что сделано в MechanikaR50

1) Добавлен **world-road режим**: профиль дороги задаётся как **стационарная поверхность** `z = f(x, y)` (world-frame).
2) Исправлена относительная скорость проникновения шины:

`pen_dot = z_road_dot - zw_dot`.

3) В модель добавлены дополнительные диагностические каналы:
- `дорога_*_dzdt_м_с` (скорость изменения профиля под колесом);
- `путь_y_м`, `скорость_vy_м_с`;
- `колесо_world_x_*_м`, `колесо_world_y_*_м`.

Файлы:
- `pneumo_solver_ui/road_surface.py` — библиотека поверхностей.
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py` — интеграция world-road.

## Как включить world-road режим

В тест (элемент массива в `pneumo_solver_ui/default_suite.json`) добавьте ключ `road_surface`.
Если `road_surface` присутствует — модель считает `z_road(t)` через координаты колёс `(x_w, y_w)` в world-frame.
Если `road_surface` отсутствует — используется legacy-профиль `road_func(t)`.

Минимальный пример (добавлен как `world_ridge_bump_demo`, выключен по умолчанию):

```json
{
  "имя": "world_ridge_bump_demo",
  "включен": false,
  "тип": "инерция_тангаж",
  "dt": 0.003,
  "t_end": 1.5,
  "t_step": 0.5,
  "ax": 0.0,
  "v0_м_с": 10.0,
  "road_surface": {
    "type": "ridge_cosine_bump",
    "A": 0.03,
    "angle_deg": 35.0,
    "u0": 4.0,
    "length": 0.5
  }
}
```

## Типы поверхностей (road_surface.py)

### 1) flat
Плоская дорога:

```json
{ "type": "flat" }
```

### 2) sine
Синус по оси `x` или `y`:

```json
{ "type": "sine", "A": 0.02, "L": 2.0, "axis": "x", "x0": 0.0, "phase": 0.0 }
```

### 3) gaussian_bump
2D-«кочка» гауссовой формы:

```json
{ "type": "gaussian_bump", "A": 0.03, "x0": 5.0, "y0": 0.0, "sx": 0.25, "sy": 0.35 }
```

### 4) ridge_cosine_bump
Бесконечный вдоль гребня «лежачий полицейский».
Высота меняется по координате `u = cos(a)*x + sin(a)*y`:

```json
{ "type": "ridge_cosine_bump", "A": 0.03, "angle_deg": 35.0, "u0": 4.0, "length": 0.5 }
```

### 5) composite
Сумма нескольких поверхностей:

```json
{
  "type": "composite",
  "items": [
    { "type": "flat" },
    { "type": "gaussian_bump", "A": 0.02, "x0": 6.0, "y0": 0.0, "sx": 0.2, "sy": 0.4 }
  ]
}
```

## Как вычисляется z_road_dot

- В world-road режиме:
  - считается градиент поверхности `(dz/dx, dz/dy)`;
  - считается скорость колеса в world-frame `(x_w_dot, y_w_dot)`;
  - `z_road_dot = dzdx * x_w_dot + dzdy * y_w_dot`.

- В legacy режиме (когда `road_func(t)`):
  - `z_road(t)` семплируется по временной сетке;
  - `z_road_dot` оценивается численной производной `np.gradient(road_z, dt)`.

## Почему исправление pen_dot важно

Сила шины в модели содержит вязкостную часть:

`F_tire = k_tire * pen + c_tire * pen_dot`.

Если игнорировать `z_road_dot`, то при быстро меняющемся профиле (и/или при движении по профилю)
демпфирование шины становится зависимым только от скорости колеса, что даёт неверные пики сил и энергию.

