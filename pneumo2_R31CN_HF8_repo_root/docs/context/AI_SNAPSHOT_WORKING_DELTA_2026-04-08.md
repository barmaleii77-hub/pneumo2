# AI Snapshot Working Delta 2026-04-08

## Что сохранено

В проекте зафиксированы две внешние canonical snapshot-копии:

- `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json.gz`
- `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_DIRECT_CHAT_SUPPLEMENT_2026-04-08.json.gz`

Default external source для дальнейшей AI-работы: `LLM_SLIM`.
Escalation/provenance source: `DIRECT_CHAT_SUPPLEMENT`.

## Что важно помнить из snapshot

### Release anchor

- Выбранный релиз: `R176_R31CN_HF8`
- Product release: `PneumoApp_v6_80_R176_R31CN_HF8_2026-04-03`
- Snapshot backlog items: `55`
- Открытых `P0`: `25`

### Главное ограничение snapshot

Архив считает HF8 последним интегрированным релизом, но его acceptance status:

- `not_proven_by_provided_runtime_evidence`

Причина из snapshot:

- более свежий `release_tag/manifest` уже есть на `2026-04-03`
- самый свежий `health_report` в evidence-слое относится к `2026-03-25`
- этот `health_report` имеет `ok=false`
- значит код релиза есть, а свежая runtime-приёмка для HF8 по приложенным evidence-артефактам не доказана

## Открытые requirement clusters, которые особенно важны для текущего кода

- `CL-001` — единый контракт ключей и запрет runtime-алиасов
- `CL-008` — UI предотвращает ошибки и остаётся объяснимым
- `CL-010` — параметры дороги корректно доставляются каждому потребителю
- `CL-011` — packaging contract цилиндров и честная деградация
- `CL-012` — доказуемая производительность через trace
- `CL-013` — кэш-корректность web части
- `CL-014` — автоматическая разметка и отсутствие ручного «рисования заново»

## Самые прикладные открытые P0/P1 из snapshot

### P0

- `P0-01` — добавить ЦТ `(z,v,a)` и раму по углам `(z,v,a)` в логи/вывод
- `P0-02` — добавить колёса относительно рамы и дороги `(z,v,a)`
- `P0-03` — world-frame движение: `x(t), v(t), yaw(t)`; дороги как `z(x,y)`
- `P0-04` — long-suite: масса/температура/начальные давления
- `P0-05` — параметризация креплений цилиндров + solver/export packaging contract
- `P0-06` — статика: поршень примерно в середине хода после packaging contract и sizing
- `P0-OPS-02` — единая UI-кнопка диагностического ZIP
- `P0-UI-GL-07` и последующие acceptance-пункты — живая Windows runtime-приёмка

### P1

- `P1-01` — каталог Camozzi для цилиндров: дискретный выбор + ограничения
- `P1-02` — модели пружин с packaging-ограничениями
- `P1-03` — «один экран» проверки: анимация + графики + клапаны
- `P1-04` — синхронизация playhead↔графики

## Практический вывод для следующей разработки

Snapshot хорошо согласуется с текущим направлением работ в repo:

1. Держать `LLM_SLIM` как default внешний контекст.
2. Поднимать `DIRECT_CHAT_SUPPLEMENT` только когда нужны provenance/evidence/Drive/chat layers.
3. Следующий кодовый приоритет после уже сделанных UI/runtime contract-работ:
   evidence acceptance для HF8,
   packaging truth для цилиндров и пружин,
   long-suite,
   расширенное логирование и world-frame observability.

## Как использовать заметку

- Эта заметка не заменяет `docs/11_TODO.md` и `docs/12_Wishlist.md`.
- Она нужна как быстрый мост между внешними snapshot-архивами и текущей работой в repo.
- Если нужно глубже, сначала открывать `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.json`, потом raw mirror-архивы из `workspace/external_context_snapshots/`.
