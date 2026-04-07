# RELEASE NOTES — R14 — 2026-03-18

## Главное
- В solver добавлен второй рычаг (`arm2_pivot/arm2_joint`) как служебная производная от существующей геометрии.
- Второй цилиндр `C2` теперь привязывается к второму рычагу, а не к первому.
- Active generators `worldroad` и `camozzi` экспортируют канонические solver-points для обоих рычагов.
- Desktop Animator и диагностика подвески знают про второй рычаг и учитывают его в проверках.

## Проверки
- `python -m compileall -q pneumo_solver_ui` — OK
- targeted pytest — 14 passed
- `selfcheck_suite --level standard` — RC=0

## Ограничение
- Полноценная параметрическая геометрия верхнего рычага как независимого raw-объекта пока не введена. В R14 используется service-derived модель без добавления новых raw/base ключей.
