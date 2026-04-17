# README_PROVENANCE

## Что добавлено в V37
V37 — это import-ready GitHub knowledge-base supplement после repo-adoption pass V36.
Он:
- готовит successor imported layer `v37_github_kb_supplement` для репозитория;
- добавляет patch proposals для `PROJECT_SOURCES.md`, lineage и imports README;
- сохраняет `17/18` как первичный локальный канон;
- не объявляет runtime closure и не скрывает открытые gaps.

## Исторические sections ниже
Все упоминания старых `v3/v12/v13/v36` ниже относятся к lineage и provenance.

## Что это
Этот архив — **самодостаточный пакет ТЗ и машиночитаемой спецификации для CODEX** по проекту инженерного Windows desktop GUI `Пневмоподвеска`.

Пакет собран по каноническому prompt `PNEUMO-GUI-TZ-SPEC-CODEX-RECIPIENT-NEUTRAL-2026-04-16-RECONCILED`, живым документам GitHub-репозитория и reconciled attached context слоям из текущего чата.

## Что реально прочитано и reconciled

### Нормативный prompt-слой
- `SOURCE_CONTEXT/prompt_for_codex_tz_spec_recipient_neutral_CANONICAL_2026-04-16_CONNECTOR_RECONCILED.md`
- `SOURCE_CONTEXT/prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md`

### GitHub-канон
- `00_READ_FIRST__ABSOLUTE_LAW.md`
- `01_PARAMETER_REGISTRY.md`
- `DATA_CONTRACT_UNIFIED_KEYS.md`
- `docs/PROJECT_SOURCES.md`
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `docs/context/desktop_web_parity_map.json`
- `docs/context/DESKTOP_WEB_PARITY_SUMMARY.md`
- `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md`
- `docs/context/AI_SNAPSHOT_WORKING_DELTA_2026-04-08.md`

### Attached context и imported GUI layers
- `SOURCE_CONTEXT/deep-research-report (5).md`
- `SOURCE_CONTEXT/Прогрев контекста проекта.txt`
- `SOURCE_CONTEXT/Проектный релиз.txt`
- `SOURCE_CONTEXT/Разработка софта для подвески.txt`
- imported GUI/detail layers `v13…v26`, находящиеся локально в `/mnt/data`

## Как использовались connected sources
Подключённый GitHub-источник reconciled через **живые raw GitHub documents** и локальный attached corpus. В этой среде не был доступен отдельный tree-listing connector API, поэтому package использует:
1. канонический prompt;
2. live raw GitHub docs;
3. attached/imported context layers;
4. их явную reconciliation-матрицу.

Отдельный контрольный слой приложен как:
- `CONNECTED_SOURCE_RECONCILIATION.md`
- `REPO_EVIDENCE_INDEX.csv`
- `PROMPT_COMPLIANCE_MATRIX.csv`

## Какой рабочий корень репозитория принят
Рабочим корнем принят:
`pneumo2_R31CN_HF8_repo_root`

Основание:
- repo docs указывают именно на этот current root;
- package фиксирует это как `ISSUE-001`.

## Что не заявляется без доказательства
Пакет **не объявляет закрытым**:
- producer-side `hardpoints / solver_points` truth closure;
- полный `cylinder packaging passport`;
- measured browser performance acceptance;
- полный Windows visual acceptance;
- runtime доказательство closure по всем P0 backlog items.

Эти узлы сохранены как `covered_partially` или `gap`, а не помечены как закрытые.

## Что считать главным каноном
Порядок приоритета:
1. текущее каноническое задание;
2. прямые уточнения пользователя в текущем чате;
3. GitHub-канон проекта;
4. фактический код и существующий Web UI;
5. imported/historical layers;
6. внешние best practices.

## Состав package
Обязательные файлы prompt выполнены:
- `TECHNICAL_SPECIFICATION.md`
- `GUI_SPEC.yaml`
- все обязательные CSV/graph/lint/index файлы

Дополнительно приложены:
- `SOURCE_CONTEXT/`
- `REPO_CANONICAL_SNAPSHOTS.md`
- `REPO_EVIDENCE_INDEX.csv`
- `CONNECTED_SOURCE_RECONCILIATION.md`
- `PROMPT_COMPLIANCE_MATRIX.csv`
- `TEST_CATALOG.csv`
- `GUI_ELEMENT_GRAPH_CURRENT.dot`
- `GUI_ELEMENT_GRAPH_OPTIMIZED.dot`
- `PIPELINE_USER_STEPS.csv`


## Что усилено в V29
- введён явный `SOURCE_AUTHORITY_MATRIX.csv`, который связывает prompt, repo law/registry/contract, GUI canon, parity docs, attached context и imported layers с их authority-level и порядком приоритета;
- введён `DESKTOP_WEB_PARITY_RECONCILIATION.csv`, который отделяет release-gate parity от исторических/imported подсказок;
- введён `GRAPHICS_TRUTH_SURFACE_MATRIX.csv`, который делает truth-state surface-level contract отдельным артефактом, пригодным для CODEX и для ручной приёмки;
- введён `WORKSPACE_HANDOFF_MATRIX.csv`, который фиксирует frozen contracts и hash/lineage fields между рабочими пространствами;
- введён `REPO_CANON_CONFLICTS.csv` и `OPEN_GAPS_REGISTER.csv`, чтобы не выдавать за закрытое то, что live repo canon всё ещё считает gap/open_question.


## Что добавлено в v30
- workspace-level canonical annexes `v13…v26` интегрированы внутрь одного самодостаточного архива;
- добавлены `PROJECT_ENTITY_MODEL.yaml`, `CANONICAL_SCENARIO_SOURCE_CONTRACT.yaml`, `VISUAL_SEMANTICS_DICTIONARY.csv`, `HELP_AND_EXPLAINABILITY_MATRIX.csv`, `LAYOUT_DOCKING_PROFILE_MATRIX.csv`, `GRAPHICS_SURFACE_ACTION_MATRIX.csv`, `PROJECT_TREE_CONTRACT.csv`, `WORKSPACE_CONTRACT_MATRIX.csv`, `RELEASE_GATE_MATRIX.csv`;
- добавлен отдельный verified extract layer по repo-canonic docs для контроля source authority.


## Что добавлено в V32
V32 усиливает пакет annex-слоем release-gate hardening: playbooks, evidence requirements, runtime artifact schema и verified repo-canon extracts V32. Этот слой не заменяет runtime evidence, а формализует, что именно должно считаться доказательством закрытия P0/P1 gaps.