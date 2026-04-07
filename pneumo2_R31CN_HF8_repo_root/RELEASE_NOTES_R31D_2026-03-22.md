# RELEASE NOTES — R31D strict closure + current triage

Дата: 2026-03-22
База: R31B (с учётом последующего docs-sync слоя R31C)

## Что сделано

### Ring / UI
- введён явный канон `closure_policy=strict_exact`;
- генератор кольца теперь сериализует/возвращает seam-диагностику в `tracks.meta` и `_generated_meta`;
- валидация ring-spec запрещает неканонические closure policy;
- whole-ring preview больше не показывает глобальный `max-min` как единственную «главную» цифру;
- в full-ring summary явно разведены `amplitude A` и `p-p=max-min (НЕ A)`;
- в preview показывается `closure_policy` и шов L/R без скрытых baseline/mean correction.

### Animator / pointer source
- Desktop Animator при автопоиске pointer теперь сначала ищет канонический global pointer текущего workspace (`workspace/_pointers/anim_latest.json`), затем последние UI session workspace pointer/export, и только потом legacy project-local пути.

### Send Bundle / triage
- `latest_anim_pointer_diagnostics.*` теперь явно показывают active source refs для `road_csv`, `axay_csv`, `scenario_json`;
- triage report выбирает `send_bundle_created` с приоритетом по `latest_send_bundle_path.txt`, а не просто «последнее событие в хвосте»;
- финальный triage внутри SEND bundle теперь пересобирается после записи текущего `send_bundle_created` в run registry, чтобы не тащить stale bundle-event;
- убран старый промежуточный triage-rewrite, который создавал duplicate ZIP entries.

## Что НЕ закрыто этим релизом
- geometry acceptance WARN / XY mismatch не исправлен математически;
- browser CPU / viewport gating / trace acceptance не закрыты;
- solver-points / cylinder packaging contract не доведены до полной приёмки.

## Проверка
- targeted regression slice: PASS
- full pytest: 257 passed in 31.28s
