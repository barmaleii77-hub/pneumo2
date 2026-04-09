# Источники проекта и контекста

## Канон внутри релиза

1. `00_READ_FIRST__ABSOLUTE_LAW.md` — абсолютный закон проекта.
2. `01_PARAMETER_REGISTRY.md` — единый реестр параметров.
3. `DATA_CONTRACT_UNIFIED_KEYS.md` — единый контракт ключей.
4. `docs/context/PROJECT_CONTEXT_ANALYSIS.md` — локальная сводка контекста проекта.
5. `docs/11_TODO.md` — текущий рабочий TODO-снимок.
6. `docs/12_Wishlist.md` — текущий рабочий wishlist-снимок.

## Зафиксированные внешние AI snapshots

- `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md` — локально зафиксированная human-readable выжимка актуальной пары external snapshots от 2026-04-08: `DIRECT_CHAT_SUPPLEMENT + LLM_SLIM`.
- `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.json` — машинно-читаемый digest той же пары для AI/bootstrap/use-as-context сценариев.
- `docs/context/AI_SNAPSHOT_WORKING_DELTA_2026-04-08.md` — короткая рабочая delta-заметка: что из snapshot важно помнить для дальнейшей разработки прямо сейчас.
- `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json.gz` — локальная project mirror-копия default external AI source. Workspace-слой gitignored.
- `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_DIRECT_CHAT_SUPPLEMENT_2026-04-08.json.gz` — локальная project mirror-копия полного provenance/evidence snapshot. Workspace-слой gitignored.

## Внешние источники контекста (Google Drive)

Эти папки являются внешними источниками контекста проекта и должны учитываться при разборе истории релизов, архивов, документов и переписки:

- `Downloads` — https://drive.google.com/drive/folders/1INCx3J11p24XZIgY_th3-J2ZBCltQiwX?usp=sharing
- `Downloads` — https://drive.google.com/drive/folders/147bS-lCxGY4jsQ6jCnsq9Os6pk7U6zE7?usp=sharing
- `пневмоподвеска` — https://drive.google.com/drive/folders/1tEJwV4UtRNwsbX2Jgf-O-GihTktWHBfN?usp=sharing

## Правило использования

- Внешние ссылки **не заменяют** локальный канон (`ABSOLUTE LAW`, реестр параметров, data contract).
- Архивы/доки/экспорты из Google Drive рассматриваются как **источники контекста, истории релизов и требований**.
- Для AI/bootstrap по умолчанию сначала читать локальный digest `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.json`, затем локальную mirror-копию `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json.gz`, а к `DIRECT_CHAT_SUPPLEMENT` подниматься только когда нужен raw provenance/evidence слой.
- При конфликте между историческими архивами и текущим каноном исправляется код/экспорт, а не вводятся алиасы и runtime-мосты.
