# GUI Chat Prompts

Этот каталог хранит lane-level implementation prompts. Он не является
самостоятельным каноном и должен читаться только после GUI-spec слоя.

## Порядок чтения

1. [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
   — project-wide desktop baseline.
2. [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
   — project-specific GUI contract для `Пневмоподвески`.
3. [gui_spec_imports/foundations/README.md](../context/gui_spec_imports/foundations/README.md)
   и
   [prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md](../context/gui_spec_imports/foundations/prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md)
   — foundational upstream prompt source (`PROMPT_V2`).
4. [gui_spec_imports/v33_connector_reconciled/README.md](../context/gui_spec_imports/v33_connector_reconciled/README.md)
   и [COMPLETENESS_ASSESSMENT.md](../context/gui_spec_imports/v33_connector_reconciled/COMPLETENESS_ASSESSMENT.md)
   — active connector-reconciled GUI/TZ digest для v33 integrity policy,
   selfcheck/remediation, repo-canon read order, gate mapping и PB-008.
5. [gui_spec_imports/v32_connector_reconciled/README.md](../context/gui_spec_imports/v32_connector_reconciled/README.md),
   [COMPLETENESS_ASSESSMENT.md](../context/gui_spec_imports/v32_connector_reconciled/COMPLETENESS_ASSESSMENT.md)
   и [PARALLEL_CHAT_WORKSTREAMS.md](../context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md)
   — previous connector-reconciled digest и разбиение работы на независимые чаты.
6. [RELEASE_GATE_ACCEPTANCE_MAP.md](../context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md),
   [RELEASE_GATE_HARDENING_MATRIX.csv](../context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_HARDENING_MATRIX.csv)
   и [GAP_TO_EVIDENCE_ACTION_MAP.csv](../context/gui_spec_imports/v32_connector_reconciled/GAP_TO_EVIDENCE_ACTION_MAP.csv)
   — checked-in release/evidence extracts для V32-16 и docs-contract tests.
7. [WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md),
   [PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md),
   [COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md),
   [GEOMETRY_REFERENCE_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md),
   [MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md),
   [ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md),
   [DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md),
   [DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md](../context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md)
   и [RUNTIME_RELEASE_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md)
   — lane evidence notes для V32-02/V32-04/V32-06/V32-08/V32-10/V32-13/V32-14/V32-09/V32-11/V32-15; не объявляют full gap closure без named runtime artifacts.
8. [WORKTREE_TRIAGE_2026-04-17.md](../context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md)
   — release-readiness ownership map текущего dirty tree; не runtime closure proof.
9. [SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md](../context/release_readiness/SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md)
   — reviewed clean self-check warnings snapshot; не diagnostics/SEND closure proof.
10. [V32_16_ACCEPTANCE_NOTE_2026-04-17.md](../context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md)
   — accepted V32-16 docs/helper scope and validation note.
11. [PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17.md](../context/release_readiness/PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17.md)
   — synchronized repository/KB conformance audit and improvement plan; not runtime closure proof.
12. [BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md](../context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md)
   — branch cleanup record and safe parallel-work policy after consolidating
   temporary Codex branches into `codex/work`.
13. [14_PLAN_MODE_PARALLEL_START_PROMPTS.md](./14_PLAN_MODE_PARALLEL_START_PROMPTS.md)
   — copy-paste starter prompts for new parallel chats whose first launch is
   in Plan mode.
14. [CODE_TREE_AUDIT_2026-04-18.md](../context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md)
   — code-tree audit after branch cleanup: dirty files by lane, hotspot modules
   and ignored-artifact cleanup policy.
15. [15_CODE_AUDIT_PLAN_MODE_START_PROMPTS.md](./15_CODE_AUDIT_PLAN_MODE_START_PROMPTS.md)
   — updated self-contained Plan-mode starter prompts for the same 10 chats,
   with current code audit and dirty-tree risks. Prefer this file for new
   chat starts.
16. [gui_spec_imports/v37_github_kb_supplement/README.md](../context/gui_spec_imports/v37_github_kb_supplement/README.md),
   [TECHNICAL_SPECIFICATION.md](../context/gui_spec_imports/v37_github_kb_supplement/TECHNICAL_SPECIFICATION.md)
   и [GUI_SPEC.yaml](../context/gui_spec_imports/v37_github_kb_supplement/GUI_SPEC.yaml)
   — successor GitHub KB/TZ/spec supplement. Он уточняет requirements,
   workspace contracts, parameter catalogs, acceptance и open gaps, но не
   является runtime-closure proof.
17. [gui_spec_imports/v3/README.md](../context/gui_spec_imports/v3/README.md)
   и related `v3/*`
   — checked-in detailed machine-readable reference layer.
18. [gui_spec_imports/v13_ring_editor_migration/README.md](../context/gui_spec_imports/v13_ring_editor_migration/README.md)
   и related `v13_ring_editor_migration/*`
   — специализированный addendum для `WS-RING` и handoff `WS-RING -> WS-SUITE`.
19. [gui_spec_imports/v12_design_recovery/README.md](../context/gui_spec_imports/v12_design_recovery/README.md)
   — historical design-recovery layer, который возвращает проект из implementation-веток в design-first.
20. [GUI_SPEC_ARCHIVE_LINEAGE.md](../context/GUI_SPEC_ARCHIVE_LINEAGE.md)
   и [gui_spec_archive_lineage.json](../context/gui_spec_archive_lineage.json)
   — lineage `v1…v13 + v37`, чтобы понимать роль каждого архива и successor supplement.
21. `docs/gui_chat_prompts/*`
   — implementation prompts, которые должны наследовать канон, а не заменять его.

## Что считается reference layer

- `foundations` задаёт upstream intent layer:
  native Windows desktop, no web-first, no feature-loss migration, diagnostics
  as first-class surface, ring editor as single source of truth и honest
  graphics baseline.
- `v32_connector_reconciled` задаёт previous connector-reconciled GUI/TZ digest:
  source authority, 12 workspace contracts, acceptance playbooks, release gates,
  runtime artifact schema, evidence policy и open gaps.
- `v33_connector_reconciled` уточняет v32:
  package integrity policy, selfcheck/remediation, repo-canon read-order/gate
  mapping, prompt audits и dedicated PB-008 provenance playbook.
- `COMPLETENESS_ASSESSMENT` фиксирует, что v32 достаточно как contract/planning
  layer, но не является runtime closure proof.
- `PARALLEL_CHAT_WORKSTREAMS` задаёт 16 независимых workstreams с owned scope,
  handoff boundaries и короткими стартовыми промтами.
- `RELEASE_GATE_ACCEPTANCE_MAP` плюс checked-in gate/gap CSV задают локальную
  release/evidence карту для V32-16 без объявления runtime closure.
- `WS_INPUTS_HANDOFF_EVIDENCE_NOTE`,
  `PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE`,
  `COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE`,
  `GEOMETRY_REFERENCE_EVIDENCE_NOTE`,
  `MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE`,
  `ENGINEERING_ANALYSIS_EVIDENCE_NOTE`,
  `DIAGNOSTICS_RELEASE_EVIDENCE_NOTE`,
  `DIAGNOSTICS_PRODUCER_GAPS_HANDOFF` и `RUNTIME_RELEASE_EVIDENCE_NOTE`
  фиксируют accepted lane evidence contracts для
  V32-02/V32-04/V32-06/V32-08/V32-10/V32-13/V32-14/V32-09/V32-11/V32-15 и explicit non-closure для gaps,
  которым нужны живые artifacts.
- `WORKTREE_TRIAGE_2026-04-17` фиксирует owner lane, gate/gap, required evidence
  и targeted tests для текущего dirty tree перед release-readiness merge.
- `SELF_CHECK_WARNINGS_REVIEW_2026-04-17` фиксирует clean generated
  self-check snapshot для `REPORTS/SELF_CHECK_SILENT_WARNINGS.*` без
  diagnostics/SEND closure claim.
- `V32_16_ACCEPTANCE_NOTE_2026-04-17` фиксирует accepted V32-16 docs/helper
  scope, focused validation and next lane order.
- `PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17` фиксирует текущую синхронизацию
  `codex/work`, соответствие KB по lane matrix и план дальнейшей доработки.
- `BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18` фиксирует, что временные
  ветки собраны в `codex/work`, remote/local branch refs очищены и будущая
  параллельная работа должна идти только от `codex/work`.
- `14_PLAN_MODE_PARALLEL_START_PROMPTS` задаёт copy-paste стартовые промты для
  новых чатов, где первый запуск выполняется в Plan mode: сначала чтение,
  план, owned/forbidden files, tests and risks; только потом правки после
  подтверждения.
- `CODE_TREE_AUDIT_2026-04-18` фиксирует текущий dirty tree, prepared
  worktrees, ignored artifact cleanup risk и code hotspots. Он не одобряет
  dirty code, а задаёт карту ownership для безопасного продолжения.
- `15_CODE_AUDIT_PLAN_MODE_START_PROMPTS` задаёт обновлённые самодостаточные
  стартовые промты для тех же 10 чатов; для новых стартов предпочитать его,
  потому что он учитывает текущие dirty files и prepared worktree state.
- `v37_github_kb_supplement` задаёт successor KB/TZ/spec connector layer:
  consolidated technical specification, GUI_SPEC.yaml, workspace contract
  matrix, parameter catalogs, acceptance/requirements matrices, repo canon
  alignment и список open gaps, которые нельзя скрывать как закрытые.
- `v3` задаёт общий detailed layer:
  shell, layout, UI elements, help/tooltip catalogs, migration matrix,
  acceptance, verification, keyboard/docking/state/observability contracts.
- `v13_ring_editor_migration` задаёт специализированный ring layer:
  schema contract, screen blueprints, element/field catalogs, state machine,
  user pipeline, ring-level migration matrix, acceptance gates и suite-link
  contract.
- `v12_design_recovery` задаёт historical recovery layer:
  ring-editor precursor contract, optimization control plane, truthful graphics
  и workspace recovery delta.

## Lane docs

- [01_MAIN_WINDOW.md](./01_MAIN_WINDOW.md)
- [02_INPUT_DATA.md](./02_INPUT_DATA.md)
- [03_RUN_SETUP.md](./03_RUN_SETUP.md)
- [04_RING_EDITOR.md](./04_RING_EDITOR.md)
- [05_COMPARE_VIEWER.md](./05_COMPARE_VIEWER.md)
- [06_DESKTOP_MNEMO.md](./06_DESKTOP_MNEMO.md)
- [07_DESKTOP_ANIMATOR.md](./07_DESKTOP_ANIMATOR.md)
- [08_OPTIMIZER_CENTER.md](./08_OPTIMIZER_CENTER.md)
- [09_DIAGNOSTICS_SEND_BUNDLE.md](./09_DIAGNOSTICS_SEND_BUNDLE.md)
- [10_TEST_VALIDATION_RESULTS.md](./10_TEST_VALIDATION_RESULTS.md)
- [11_GEOMETRY_REFERENCE.md](./11_GEOMETRY_REFERENCE.md)
- [12_ENGINEERING_ANALYSIS.md](./12_ENGINEERING_ANALYSIS.md)
- [13_RELEASE_GATES_KB_ACCEPTANCE.md](./13_RELEASE_GATES_KB_ACCEPTANCE.md)
- [14_PLAN_MODE_PARALLEL_START_PROMPTS.md](./14_PLAN_MODE_PARALLEL_START_PROMPTS.md)
- [15_CODE_AUDIT_PLAN_MODE_START_PROMPTS.md](./15_CODE_AUDIT_PLAN_MODE_START_PROMPTS.md)

## Правило использования

- если lane касается shell, сначала смотреть `17`, `18` и `v3`;
- если lane касается cross-workspace architecture, release gates, acceptance
  evidence, runtime artifacts или open gaps, обязательно смотреть
  `v33_connector_reconciled/README.md`, затем `v32_connector_reconciled/README.md`
  и `v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md`; для
  inputs/suite handoff, producer/animator truth, compare/objective integrity,
  geometry reference, mnemo truth graphics, engineering analysis, diagnostics или runtime/perf acceptance
  дополнительно читать соответствующий evidence note;
- если lane касается текущего mixed dirty tree, дополнительно сверять
  `context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md` и
  `context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md`, а также
  `context/release_readiness/PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17.md`; не
  смешивать V32-16 docs/helper patch с runtime/domain lane-пакетами;
- если нужно понять исходный жёсткий intent ещё до `v1`, дополнительно читать
  `foundations/*`;
- если lane затрагивает requirements, параметры, workspace coverage,
  acceptance или open gaps, читать `v37_github_kb_supplement/*` как
  successor knowledge-base supplement, не подменяя им runtime evidence;
- если lane касается ring editor, handoff сценария или suite consumer
  сценарного контракта, обязательно дополнительно смотреть
  `v13_ring_editor_migration/*`;
- если lane касается происхождения текущего канона, recovery decisions или
  границы между design и implementation-pass, смотреть `v12_design_recovery/*`
  и lineage `v1…v13`;
- при конфликте приоритет у `17/18`, затем у `v33_connector_reconciled`, затем
  у `v32_connector_reconciled`, затем у `foundations`, затем у
  `v37_github_kb_supplement`, затем у `v3`, затем у специализированного
  `v13_ring_editor_migration`, затем у `v12_design_recovery`, затем у
  historical imports.
