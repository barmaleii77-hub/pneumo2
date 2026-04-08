# AI Wishlist Canonical Omnibus 2026-04-08

## Что зафиксировано

8 апреля 2026 я изучил внешний canonical knowledge pack из `C:\Users\User\Downloads` и зафиксировал в проекте его рабочую выжимку.

Речь идет о трех связанных слоях:

1. Полный внешний canonical snapshot:
   `AI_WISHLIST_CANONICAL_OMNIBUS_DIAGRAMS_CHAT_SUPPLEMENT_2026-04-08.json.gz`
2. Рабочий LLM-slim snapshot:
   `AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json`
   и
   `AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json.gz`
3. Manifest/provenance layer:
   `AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_MANIFEST_2026-04-08.json`
   и
   `AI_WISHLIST_DIAGRAMS_CHAT_MHTML_MANIFEST_2026-04-08.json`

Сырые внешние файлы не вендорятся в repo, чтобы не тащить десятки мегабайт в git. Вместо этого в проекте лежит эта заметка и машинно-читаемый digest рядом.

## Иерархия источников

### 1. Full canonical context

- Файл: `AI_WISHLIST_CANONICAL_OMNIBUS_DIAGRAMS_CHAT_SUPPLEMENT_2026-04-08.json.gz`
- Schema: `ai_wishlist_canonical_unified/v3`
- `generated_at_utc`: `2026-04-08T09:44:29Z`
- `sha256`: `b803cf2605091ccbc154c4d4ce362458218370868b2ae04064df4c40e14f4a47`
- `size_bytes`: `29274035`

Использовать, когда нужен полный машинный слой:

- `project_context.main_gaps` и `project_context.next_steps_in_code`
- remote registry / Google Drive provenance
- uploaded MHTML turn layer
- content store / path index / raw highlighted evidence

### 2. Default LLM working source

- Файл: `AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json`
- Gzip: `AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json.gz`
- Schema: `ai_wishlist_canonical_unified/v3-llm-slim`
- `profile_id`: `omnibus_llm_slim_v1`
- `generated_at_utc`: `2026-04-08T10:40:19Z`
- `sha256`: `88205a9ab61b0883f0f3cdb5d94ee130bbcd51c815f4046a864ec2bf8d8360f8`
- `gzip_sha256`: `d584f5ebeb5503a9dfcdc6f9ceb332565e86c29cc6c1aacc063d83f20b1e7c6a`
- `size_bytes`: `10127124`
- `gzip_size_bytes`: `1219883`

Это основной внешний источник для AI/LLM-работы. В нем уже оставлены high-signal indexes, excerpts и policy-слой, а тяжелые raw corpora сознательно урезаны.

### 3. Bridge / provenance manifests

#### LLM slim manifest

- Файл: `AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_MANIFEST_2026-04-08.json`
- Родитель: `AI_WISHLIST_CANONICAL_OMNIBUS_DIAGRAMS_CHAT_SUPPLEMENT_2026-04-08.json.gz`
- Назначение: связка `full -> slim`, размеры, sha256, retained/slimmed sections

#### MHTML manifest

- Файл: `AI_WISHLIST_DIAGRAMS_CHAT_MHTML_MANIFEST_2026-04-08.json`
- `generated_at_utc`: `2026-04-08T09:44:29Z`
- `based_on`: `AI_WISHLIST_CANONICAL_OMNIBUS_PDF_SUPPLEMENT_2026-04-08.json.gz`
- `new_full_file`: `AI_WISHLIST_CANONICAL_OMNIBUS_DIAGRAMS_CHAT_SUPPLEMENT_2026-04-08.json`
- `new_gzip_file`: `AI_WISHLIST_CANONICAL_OMNIBUS_DIAGRAMS_CHAT_SUPPLEMENT_2026-04-08.json.gz`

Его главное правило для проекта:

- uploaded MHTML/chat layers добавляют provenance и branch chronology
- они не имеют права переопределять `absolute_laws`, `current_release_state` и release selection
- authoritative current release остается `R176_R31CN_HF8`

## Что это говорит о проекте

### Идентичность проекта

- Проект: `пневмоподвеска`
- One-liner:
  `Симулятор пневмоподвески + механики как единой ODE/численной системы, с оптимизацией, телеметрией, анимацией и выходом к реальному Camozzi-прототипу.`

### Основные цели

1. Реалистичный симулятор `пневматика + механика` как единая система.
2. Многопараметрическая оптимизация под комфорт/устойчивость/ограничения.
3. Полная проверяемость расчётов через логи, графики, анимацию и диагностику.
4. Привязка к реальным компонентам Camozzi и подготовка к физическому прототипу.

### Entry points из canonical snapshot

1. `START_PNEUMO_APP.pyw`
2. `app.py`

### Release anchor

- Selected release: `R176_R31CN_HF8`
- Product release: `PneumoApp_v6_80_R176_R31CN_HF8_2026-04-03`
- Snapshot `open_p0_count`: `25`

## Рабочие правила для AI и разработчика

Из `ai_quickstart.operational_rules_for_ai` для этого repo особенно важны:

1. Не придумывать новые параметры, скрытые алиасы и магические преобразования.
2. Если truth не хватает, требовать явный contract/паспорт/поле, а не гадать.
3. Скрытую автоматику заменять явными режимами, логами и видимыми переключателями.
4. Для схемы/топологии доверять `PNEUMO_SCHEME.json` и `scheme_fingerprint_v8_r48`.
5. Для component facts использовать `component_passport` и явно отмечать `missing_data`.
6. Для статуса релиза сначала читать `current_release_state` и `technical_runtime_evidence`.
7. Governance gaps брать из `requirements_governance.open_requirement_clusters`.
8. Engineering TODO слой считать backlog-слоем для нормализации, а не готовым acceptance truth.
9. При конфликте нового архива с unified `current_release_state` доверять unified `current_release_state`.
10. Для быстрого LLM-анализа начинать со slim-cut excerpt/index слоев, а не с raw corpora.

## Recommended read order

Использовать такой порядок чтения:

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
12. `engineering_todo_wishlist_aggregate.top_items_by_source_span`
13. `progress_since_base_canonical`
14. `markdown_archive_layer.curated_authoritative_docs`
15. `release_evidence_timeline`
16. `cross_archive_consistency_checks`

## Главные gaps и next steps in code

### Main gaps

1. Геометрия крепления цилиндров/рычагов пока не параметризована.
2. Нет полноценной модели разных пар цилиндров с разным ходом.
3. Пружинные packaging constraints учтены только частично.
4. Нужен длинный suite по массе/температуре/давлениям.
5. Требуется расширить набор сигналов для проверки и логирования.

### Next steps in code

1. В `model_*.py` добавить расширенное логирование:
   скорости, ускорения, ЦТ, углы рамы, относительные ходы.
2. В `default_base.json` и `default_ranges.json` добавить параметры геометрии креплений и включить их в механику через кинематику.
3. В `opt_worker_*.py` добавить длинный тест и ранний пакетный прогон по `(масса × температура × давления)`.
4. В UI вывести профиль дороги и HUD по ключевым сигналам в механической анимации.

## Как использовать это в repo

1. Для быстрой ориентации внутри проекта начинать с:
   `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.json`
   и этой заметки.
2. Для внешнего AI/context bootstrap по умолчанию считать LLM-slim snapshot рабочим источником.
3. Если нужен raw evidence / remote layer / branch chronology, подниматься к full gzip snapshot.
4. Эти snapshots являются источником контекста и требований, но не переопределяют локальный `ABSOLUTE LAW`, parameter registry и data contract.
