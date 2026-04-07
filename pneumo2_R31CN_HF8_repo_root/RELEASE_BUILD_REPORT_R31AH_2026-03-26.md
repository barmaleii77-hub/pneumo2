# RELEASE_BUILD_REPORT_R31AH_2026-03-26

## База
- Источник: `/mnt/data/src_current`
- Предыдущий релиз: `PneumoApp_v6_80_R176_R31AG_2026-03-25`
- Новый релиз: `PneumoApp_v6_80_R176_R31AH_2026-03-26`

## Ключевые изменения
- Исправлен solver/export continuity для frame-mounted hardpoints.
- Исправлен rod-mount continuity: `cyl*_bot` теперь лежит на фактической ветви рычага.
- Добавлены diagnostics/self-check/HUD метрики на rigid-body continuity.
- Проиндексирован и дедуплицирован архив чатов `mhtml.zip`; TODO/WISHLIST обновлены по результатам.

## Локальная верификация
- `python -m py_compile ...` → PASS
- `python -m compileall pneumo_solver_ui tests` → PASS
- `pytest -q ...` (targeted continuity + regression slice) → PASS (22 passed)

## Bundle-driven выводы перед фиксом
По последнему доступному SEND bundle (R31AF) новые continuity diagnostics показали:
- frame-mounted drift до ~0.193 м;
- wheel/upright drift ≈ 0;
- off-arm offset `cyl1_bot` до ~0.0355 м;
- off-arm offset `cyl2_bot` до ~0.0345 м.

Это и стало основанием для solver/export patch в R31AH.

## Артефакты
- `CHAT_ARCHIVE_ANALYSIS_R31AH_2026-03-26.md`
- `GEOMETRY_CONTINUITY_AUDIT_R31AH_2026-03-26.md`
- `CHAT_AND_GEOMETRY_AUDIT_R31AH_2026-03-26.json`
- `TODO_WISHLIST_R31AH_ADDENDUM_2026-03-26.md`
- `PYCHECKS_R31AH_2026-03-26.log`
- `COMPILEALL_R31AH_2026-03-26.log`
- `PYTEST_TARGETED_R31AH_2026-03-26.log`
