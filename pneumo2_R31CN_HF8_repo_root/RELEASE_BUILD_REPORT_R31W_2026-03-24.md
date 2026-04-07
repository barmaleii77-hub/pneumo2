# RELEASE BUILD REPORT — PneumoApp_v6_80_R176_R31W_2026-03-24

Дата: 2026-03-24

## Основание
- База: `PneumoApp_v6_80_R176_R31V_2026-03-24`
- Направление работ: TODO/Wishlist + ABSOLUTE LAW + DATA_CONTRACT_UNIFIED_KEYS

## Диагноз
- Цилиндры/поршни в Desktop Animator были отключены не потому, что их нельзя построить, а потому, что packaging contract был недоформализован.
- В visual helper-е оставалась invented `fake piston thickness`, что противоречило запрету на выдуманные параметры.

## Исправление
- `pneumo_solver_ui/data_contract.py`
  - расширен canonical `meta.geometry` ключами packaging contract;
  - добавлен exporter-side derivation dead lengths из `dead_volume_chamber_m3` и площадей камер;
  - добавлен exporter-side derivation outer diameter из bore + wall thickness.
- `pneumo_solver_ui/desktop_animator/geom3d_helpers.py`
  - добавлен honest packaging-based state helper;
  - piston thickness больше не invent'ится;
  - piston plane вычисляется строго из axis + stroke + dead lengths.
- `pneumo_solver_ui/desktop_animator/app.py`
  - восстановлен runtime path рендера cylinders/rods/pistons по packaging contract;
  - piston рисуется как отдельный disc mesh;
  - incomplete contract по-прежнему даёт warning и честное disable, без silent fallback.
- Docs / registry / wishlist синхронизированы под новый contract-first слой.

## Проверка
- `py_compile`: PASS
- `compileall`: PASS
- targeted `pytest`: 20 passed
- `docs/WISHLIST.json`: JSON OK
- `release_tag.json`: JSON OK

## Остаток
- Требуется новый Windows SEND bundle на `R31W`.
- Следующий backlog: catalogue-aware Camozzi sizing/limits, static mid-stroke acceptance, outer-body envelope / clearance contract.
