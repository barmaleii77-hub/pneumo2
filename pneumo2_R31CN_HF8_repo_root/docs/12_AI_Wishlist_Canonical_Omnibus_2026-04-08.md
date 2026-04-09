# AI Wishlist Canonical Omnibus 2026-04-08

## Что зафиксировано

8 апреля 2026 я изучил и сохранил в проекте два актуальных внешних snapshot-архива из `C:\Users\Admin\Downloads`:

1. `AI_WISHLIST_CANONICAL_OMNIBUS_DIRECT_CHAT_SUPPLEMENT_2026-04-08.json.gz`
2. `AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json.gz`

Сырые архивы не вендорятся в git, но теперь лежат в локальном project mirror:

- `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_DIRECT_CHAT_SUPPLEMENT_2026-04-08.json.gz`
- `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json.gz`

Это workspace-папка, она gitignored. Трекуемая часть фиксации в repo: эта заметка, JSON digest рядом и запись в `docs/PROJECT_SOURCES.md`.

## Иерархия источников

### 1. Full canonical context

- Файл: `AI_WISHLIST_CANONICAL_OMNIBUS_DIRECT_CHAT_SUPPLEMENT_2026-04-08.json.gz`
- Schema: `ai_wishlist_canonical_unified/v3`
- `generated_at_utc`: `2026-04-08T08:45:16Z`
- `sha256`: `b3de508f78addfa98179d7d3abe86517540b5958f6fd472b36d07c7c76c46dd3`
- `size_bytes`: `29392864`
- Верхних секций: `36`

Использовать, когда нужен полный provenance/evidence слой:

- `remote_source_registry`
- `quinary_remote_drive_layer`
- `senary_mhtml_context_archive_layer`
- `septenary_pdf_context_archive_layer`
- `octonary_direct_chat_mhtml_layer`
- полный `technical_runtime_evidence` и `release_evidence_timeline`

### 2. Default LLM working source

- Файл: `AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json.gz`
- Schema: `ai_wishlist_canonical_unified/v3-llm-slim`
- `generated_at_utc`: `2026-04-08T10:40:19Z`
- `sha256`: `d584f5ebeb5503a9dfcdc6f9ceb332565e86c29cc6c1aacc063d83f20b1e7c6a`
- `size_bytes`: `1219883`
- Верхних секций: `38`

Это основной внешний источник для AI-работы по умолчанию. В нем уже сохранены high-signal indexes, excerpts и governance/release слои без тяжелого raw corpus.

### 3. Как эти два слоя использовать вместе

- Для обычной работы сначала читать `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.json`.
- Если нужен внешний raw context, по умолчанию подниматься к локальной mirror-копии `LLM_SLIM`.
- Если нужен provenance, remote folder registry, direct chat MHTML или полный архив evidence, подниматься к `DIRECT_CHAT_SUPPLEMENT`.

## Что архивы подтверждают

### Release anchor

- Selected release: `R176_R31CN_HF8`
- Product release: `PneumoApp_v6_80_R176_R31CN_HF8_2026-04-03`
- Snapshot backlog items: `55`
- Snapshot `open_p0_count`: `25`

### Основной смысл full direct-chat supplement

Этот пакет расширяет обычный omnibus не новой бизнес-истиной, а новым контекстным слоем:

- remote registry источников
- Google Drive provenance
- MHTML/PDF context corpus
- direct chat MHTML snapshots

Он нужен для истории, доказательств, трассировки требований и branch chronology, но не переопределяет локальный канон проекта.

### Основной смысл LLM slim

Это сжатый рабочий срез для ежедневной AI-работы:

- `absolute_laws`
- `frozen_constants`
- `project_identity`
- `current_release_state`
- `requirements_governance`
- `project_context`
- `normalized_backlog`
- `technical_runtime_evidence`
- `progress_since_base_canonical`

Именно его удобнее считать default external context source для дальнейшей разработки.

## Рабочие выводы для текущего repo

1. Эти два архива теперь считаются сохраненными project-context источниками.
2. Локальный tracked digest и `PROJECT_SOURCES` обновлены под них.
3. Raw gzip-копии доступны прямо внутри проекта в `workspace/external_context_snapshots/`.
4. При конфликте между этими архивами и локальным каноном проекта приоритет остаётся за:
   `00_READ_FIRST__ABSOLUTE_LAW.md`,
   `01_PARAMETER_REGISTRY.md`,
   `DATA_CONTRACT_UNIFIED_KEYS.md`
5. Для следующей AI-работы default external source: `LLM_SLIM`, escalation source: `DIRECT_CHAT_SUPPLEMENT`.

## Recommended read order

1. `absolute_laws`
2. `frozen_constants`
3. `project_identity.primary_objectives`
4. `current_release_state`
5. `requirements_governance.summary`
6. `requirements_governance.open_requirement_clusters`
7. `project_context`
8. `requirements_sections`
9. `normalized_backlog`
10. `technical_runtime_evidence`
11. `technical_reference_artifacts`
12. `engineering_todo_wishlist_aggregate`
13. `progress_since_base_canonical`
14. `release_evidence_timeline`
15. `cross_archive_consistency_checks`

## Как использовать это в repo

1. Для быстрой ориентации внутри проекта начинать с:
   `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.json`
   и этой заметки.
2. Для локальной AI-работы с raw snapshot по умолчанию использовать:
   `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json.gz`
3. Для глубокого provenance/evidence разбора использовать:
   `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_DIRECT_CHAT_SUPPLEMENT_2026-04-08.json.gz`
4. Эти snapshots являются источником контекста и требований, но не переопределяют локальный `ABSOLUTE LAW`, parameter registry и data contract.
