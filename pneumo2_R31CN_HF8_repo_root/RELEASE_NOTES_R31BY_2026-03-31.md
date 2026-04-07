# RELEASE NOTES — R31BY (2026-03-31)

## Что изменено
- StageRunner теперь строит **stage-aware adaptive epsilon** профили для `system_influence_report_v1`:
  - `stage0_relevance` → `coarse`
  - `stage1_long` → `balanced`
  - `stage2_final` → `fine`
- Для каждой runtime-стадии StageRunner пишет отдельный System Influence отчёт в `staging/stage_aware/<stage_name>/`.
- `stage_plan_preview.json` теперь содержит `influence_profile` по каждой стадии.
- `system_influence_report_v1` принимает `--adaptive_eps_strategy` и `--stage_name`, а в JSON/MD артефактах пишет стратегию и stage label.
- UI при adaptive-mode теперь явно прокидывает базовую `adaptive_influence_eps_grid` в StageRunner.

## Зачем это сделано
Раньше adaptive epsilon был глобальным и одинаковым для всех стадий. Это делало sensitivity слишком грубой на поздних стадиях и недостаточно устойчивой на раннем relevance-screen. Теперь профили разведены по смыслу стадии.

## Совместимость
- Базовый `system_influence.json` для planner остаётся на месте.
- Stage-aware отчёты добавлены как **дополнительный слой**, без ломки существующего staged pipeline.
