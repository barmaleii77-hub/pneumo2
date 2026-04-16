# Connector-Reconciled GUI/TZ Spec v33

Этот слой фиксирует knowledge-base выжимку из локального архива
`C:/Users/Admin/Downloads/pneumo_codex_tz_spec_connector_reconciled_v33.zip`.
Raw `.zip` в репозиторий не добавляется; этот каталог служит точкой входа для
использования v33 в будущих задачах.

## Роль слоя

- Package ID: `pneumo_codex_tz_spec_connector_reconciled_v33`.
- Дата package/selfcheck: `2026-04-16T19:38:26Z`.
- Архив self-contained и connector-reconciled.
- Внутри `337` файлов.
- Слой уточняет v32 и становится active connector-reconciled GUI/TZ reference
  поверх v32, не заменяя абсолютный закон, parameter registry, data contract и
  human-readable canon `17/18`.

Практически: для новых GUI-first задач сначала читать `17` и `18`, затем этот
v33 digest и [COMPLETENESS_ASSESSMENT.md](./COMPLETENESS_ASSESSMENT.md), затем
при необходимости открывать конкретные файлы из локального архива v33.

## Что v33 исправляет после v32

Из `EXEC_SUMMARY.json`:

- исправлен `PACKAGE_MANIFEST.json` self-hash mismatch;
- исправлены active `V30` labels в package docs;
- для `PB-008` добавлен dedicated playbook.

Новые v33 artifacts:

- `PACKAGE_INTEGRITY_POLICY.md`;
- `PACKAGE_SELFCHECK_REPORT.json`;
- `PACKAGE_REMEDIATION_LOG_V33.md`;
- `REPO_CANON_READ_ORDER.csv`;
- `REPO_CANON_GATE_MAPPING.csv`;
- `PROMPT_MANDATORY_FILES_AUDIT.csv`;
- `PROMPT_ENUM_AUDIT.csv`;
- `PLAYBOOK_CURRENT_HISTORICAL_STALE_CONTEXT.md`;
- `CONNECTOR_REPO_CONFORMANCE_REPORT.md`;
- `SOURCE_CONTEXT/REPO_CANON_VERIFIED_EXTRACTS_V33.md`;
- `SOURCE_CONTEXT/REPO_CANON_URLS_V33.csv`.

## Reading Order из `README.md`

1. `README_PROVENANCE.md`
2. `TECHNICAL_SPECIFICATION.md`
3. `GUI_SPEC.yaml`
4. `REQUIREMENTS_MATRIX.csv`
5. `ACCEPTANCE_MATRIX.csv`
6. `WORKSPACE_CONTRACT_MATRIX.csv`
7. `PROJECT_ENTITY_MODEL.yaml`
8. `CANONICAL_SCENARIO_SOURCE_CONTRACT.yaml`
9. `RELEASE_GATE_MATRIX.csv`
10. `PACKAGE_SELFCHECK_REPORT.json`
11. `CONNECTOR_REPO_CONFORMANCE_REPORT.md`
12. `PACKAGE_INDEX.csv`

## Core Carry-Over From v32

v33 сохраняет ключевой scope v32:

- `45` requirements rows и `45` acceptance rows;
- `12` workspaces;
- `10` handoff rows;
- `61` screen rows и `12` windows;
- `704` UI elements;
- `488` parameter rows;
- `8` acceptance playbooks;
- `20` release-gate hardening rows;
- `16` evidence-required rows;
- `6` open gaps и `6` gap-to-evidence actions.

## Важные уточнения v33

- Manifest policy теперь исключает `PACKAGE_MANIFEST.json` из собственного
  `sha256` словаря; integrity проверяется manifest для остальных файлов,
  `PACKAGE_SELFCHECK_REPORT.json` и при необходимости внешним SHA256 архива.
- `PLAYBOOK_CURRENT_HISTORICAL_STALE_CONTEXT.md` закрывает v32 caveat по `PB-008`.
- `REPO_CANON_READ_ORDER.csv` фиксирует repo-level order:
  `PROJECT_SOURCES -> 17 -> 18 -> parity summary -> TODO`.
- `REPO_CANON_GATE_MAPPING.csv` связывает repo canon с package artifacts и
  release-gate слоями.
- `CONNECTOR_REPO_CONFORMANCE_REPORT.md` подтверждает, что package остается в
  non-code/spec lane и не подменяет implementation/runtime evidence.

## Runtime Limits

v33, как и v32, не объявляет runtime closure:

- producer-side `hardpoints / solver_points` truth closure остается не доказан;
- полный `cylinder packaging passport` не закрыт runtime evidence;
- measured browser/runtime performance acceptance не закрыт;
- полный Windows visual acceptance не закрыт;
- imported layer runtime proof не является доказанным фактом.

Любой чат, который закрывает эти темы, должен приносить живые tests, runtime
artifacts и SEND bundle evidence.

## Связанные документы

- [COMPLETENESS_ASSESSMENT.md](./COMPLETENESS_ASSESSMENT.md) - проверка
  полноты, достаточности и caveats v33;
- [../v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md](../v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md) -
  актуальная матрица параллельных workstreams; v33 уточняет ее reference layer,
  но не меняет сами границы workstream ownership.

## Conflict Policy

- При конфликте между v33 и локальным repo canon приоритет у
  `00_READ_FIRST__ABSOLUTE_LAW.md`, `01_PARAMETER_REGISTRY.md`,
  `DATA_CONTRACT_UNIFIED_KEYS.md`, затем `17/18`.
- При конфликте между v33 и v32 использовать v33 как более новый
  connector-reconciled package layer.
- При конфликте между v33 и historical imports `v1...v13` v33 использовать как
  active reference, пока он не спорит с `17/18`.
