# RELEASE NOTES — PneumoApp_v6_80_R176_R31W_2026-03-24

Дата: 2026-03-24

## Что сделано

- Формализован explicit packaging contract для цилиндров в `meta_json.geometry`.
- Возвращены честные 3D `body/rod/piston` в Desktop Animator при наличии полного контракта.
- Убрана фальшивая эвристика `fake piston thickness`; поршень теперь рисуется как точная contract-derived плоскость/диск.
- Обновлены `01_PARAMETER_REGISTRY.md`, `DATA_CONTRACT_UNIFIED_KEYS.md`, `docs/11_TODO.md`, `docs/12_Wishlist.md`, `docs/WISHLIST.json`.

## Техническая суть

Раньше:
- Animator знал ось цилиндра из solver-points, но отключал body/rod/piston при неполном packaging contract.
- В helper-е для визуализации оставалась invented thickness для поршня, что нарушало основной закон проекта.

Теперь:
- exporter/meta слой публикует явные keys: `cyl1/2_outer_diameter_m`, `cyl1/2_dead_cap_length_m`, `cyl1/2_dead_rod_length_m`;
- dead lengths выводятся строго из канонических `bore/rod/dead_volume`, outer diameter — из `bore + 2 * стенка_толщина_м`;
- Animator строит цилиндр только из `solver-points axis + packaging contract`, без скрытых визуальных догадок;
- piston mesh — это точный диск в contract-derived piston plane.

## Проверка

- `py_compile`: PASS
- `compileall`: PASS
- targeted `pytest`: 20 passed

## Открыто

- Нужен живой Windows SEND bundle на `R31W` для acceptance visible cylinders/rods/pistons без GL/FPS регрессии.
- Следующий инженерный шаг после acceptance: catalogue-aware Camozzi sizing / envelope / clearance, а не возврат к скрытым эвристикам.
