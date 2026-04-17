# Журнал планов, сгенерированных чатами проекта

> Этот файл обновляется через `pneumo_solver_ui.tools.knowledge_base_sync`.

## Назначение

Этот файл фиксирует планы, decomposition-пакеты, migration-планы и prompt-наборы, которые были сгенерированы в чатах проекта и должны учитываться как рабочий knowledge-base слой.

## Правило ведения

- если чат генерирует рабочий план, migration-map, prompt-pack или ownership matrix, он должен попасть в этот журнал;
- здесь хранится не полный текст каждого плана, а карта plan-артефактов и их назначение;
- полный текст должен лежать в отдельном файле, а здесь должна быть ссылка на него и краткое описание;
- более новый план не стирает старый автоматически: сначала нужно понять, заменяет ли он его или дополняет.

## Актуальные plan-артефакты

1. GUI_MIGRATION_CHAT_PROMPTS.md
Назначение: GUI-only пакет миграции из WEB в desktop GUI по отдельным направлениям.
Артефакт: [GUI_MIGRATION_CHAT_PROMPTS.md](./GUI_MIGRATION_CHAT_PROMPTS.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0001`.

2. PARALLEL_CHAT_PROMPTS_GUI_AND_WEB_2026-04-12.md
Назначение: Исторический пакет параллельной разработки GUI и WEB. После решения о GUI-first WEB-часть использовать только как reference.
Артефакт: [PARALLEL_CHAT_PROMPTS_GUI_AND_WEB_2026-04-12.md](./PARALLEL_CHAT_PROMPTS_GUI_AND_WEB_2026-04-12.md)
Статус: частично актуален.
Источник: chat.
ID: `PLAN-0002`.

3. gui_chat_prompts/00_INDEX.md
Назначение: Индекс prompt-файлов для параллельных GUI-чатов.
Артефакт: [gui_chat_prompts/00_INDEX.md](./gui_chat_prompts/00_INDEX.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0003`.

4. gui_chat_prompts/01_MAIN_WINDOW.md
Назначение: Главное окно приложения.
Артефакт: [gui_chat_prompts/01_MAIN_WINDOW.md](./gui_chat_prompts/01_MAIN_WINDOW.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0004`.

5. gui_chat_prompts/02_INPUT_DATA.md
Назначение: Ввод исходных данных.
Артефакт: [gui_chat_prompts/02_INPUT_DATA.md](./gui_chat_prompts/02_INPUT_DATA.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0005`.

6. gui_chat_prompts/03_RUN_SETUP.md
Назначение: Настройка расчёта.
Артефакт: [gui_chat_prompts/03_RUN_SETUP.md](./gui_chat_prompts/03_RUN_SETUP.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0006`.

7. gui_chat_prompts/04_RING_EDITOR.md
Назначение: Редактор и генератор сценариев колец.
Артефакт: [gui_chat_prompts/04_RING_EDITOR.md](./gui_chat_prompts/04_RING_EDITOR.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0007`.

8. gui_chat_prompts/05_COMPARE_VIEWER.md
Назначение: Compare viewer.
Артефакт: [gui_chat_prompts/05_COMPARE_VIEWER.md](./gui_chat_prompts/05_COMPARE_VIEWER.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0008`.

9. gui_chat_prompts/06_DESKTOP_MNEMO.md
Назначение: Desktop mnemo.
Артефакт: [gui_chat_prompts/06_DESKTOP_MNEMO.md](./gui_chat_prompts/06_DESKTOP_MNEMO.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0009`.

10. gui_chat_prompts/07_DESKTOP_ANIMATOR.md
Назначение: Desktop animator.
Артефакт: [gui_chat_prompts/07_DESKTOP_ANIMATOR.md](./gui_chat_prompts/07_DESKTOP_ANIMATOR.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0010`.

11. gui_chat_prompts/08_OPTIMIZER_CENTER.md
Назначение: Optimizer center со всеми настройками.
Артефакт: [gui_chat_prompts/08_OPTIMIZER_CENTER.md](./gui_chat_prompts/08_OPTIMIZER_CENTER.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0011`.

12. gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md
Назначение: Diagnostics и send bundle.
Артефакт: [gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md](./gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0012`.

13. gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md
Назначение: Test, validation, results center.
Артефакт: [gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md](./gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0013`.

14. gui_chat_prompts/11_GEOMETRY_REFERENCE.md
Назначение: Geometry, catalogs, reference.
Артефакт: [gui_chat_prompts/11_GEOMETRY_REFERENCE.md](./gui_chat_prompts/11_GEOMETRY_REFERENCE.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0014`.

15. gui_chat_prompts/12_ENGINEERING_ANALYSIS.md
Назначение: Engineering analysis, calibration, influence.
Артефакт: [gui_chat_prompts/12_ENGINEERING_ANALYSIS.md](./gui_chat_prompts/12_ENGINEERING_ANALYSIS.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0015`.

16. 17_WINDOWS_DESKTOP_CAD_GUI_CANON.md
Назначение: Project-wide Windows desktop CAD/CAM/CAE GUI canon для shell, editor-окон, viewport/workspace-поверхностей и analysis-модулей.
Артефакт: [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](./17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0016`.

17. 18_PNEUMOAPP_WINDOWS_GUI_SPEC.md
Назначение: Decision-complete GUI-spec для shell, workspaces, command model, workflows, diagnostics, animator truth policy и acceptance criteria проекта Пневмоподвеска.
Артефакт: [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](./18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0017`.

18. 18_PNEUMOAPP_WINDOWS_GUI_SPEC.md (augmented A–M revision)
Назначение: Revision existing project-specific GUI spec to augmented A–M contract with optimization transparency, ring-editor source-of-truth, diagnostics operational surface, truthful animator policy, status/taskbar policy and DPI/windowing/performance rules.
Артефакт: [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](./18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0018`.

19. Refined GUI-spec synchronization from deep research
Назначение: Уточнить 17-й canon, 18-й project-specific GUI-spec, prompt-layer и knowledge-base summary по deep-research-report.md без изменения runtime GUI и без потери web-to-desktop functional parity.
Артефакт: [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](./18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0019`.

20. Digest connector-reconciled v32 GUI/TZ archive into knowledge base
Назначение: Add a repository knowledge-base entrypoint for the v32 archive, update source-priority docs and prompt index so future chats can use v32 without rereading 325 archive files blindly.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/README.md](./context/gui_spec_imports/v32_connector_reconciled/README.md)
Статус: актуален.
Источник: chat + archive:pneumo_codex_tz_spec_connector_reconciled_v32.
ID: `PLAN-0020`.

21. Use v32 parallel chat workstreams for independent project acceleration
Назначение: Split future project work into independent Russian-named workstreams with owned scopes, handoff IDs, forbidden overlap zones and short startup prompts so multiple chats can implement in parallel without confusion.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md](./context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md)
Статус: актуален.
Источник: chat + v32 parallel workstreams.
ID: `PLAN-0021`.

22. Digest connector-reconciled v33 archive into knowledge base
Назначение: Add v33 README and completeness assessment, update source priority docs and prompt index so future chats read v33 before v32 while still using v32 parallel workstreams.
Артефакт: [context/gui_spec_imports/v33_connector_reconciled/README.md](./context/gui_spec_imports/v33_connector_reconciled/README.md)
Статус: актуален.
Источник: chat + archive:pneumo_codex_tz_spec_connector_reconciled_v33.
ID: `PLAN-0022`.

23. V32-16 Release Gates KB acceptance map
Назначение: Maintain the repo-side release-gate hardening, gap-to-evidence map, source-authority links, helper metadata, prompt index and docs-contract tests without implementing domain runtime features.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md](./context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md)
Статус: актуален.
Источник: chat + v32 release-gate acceptance map.
ID: `PLAN-0023`.

24. Release-readiness dirty worktree triage
Назначение: Inventory the current mixed dirty tree by V32 lane, gate/gap, required evidence and targeted tests before integrating runtime/domain draft changes.
Артефакт: [context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md](./context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md)
Статус: актуален.
Источник: chat + release-readiness triage.
ID: `PLAN-0024`.

25. V32-16 docs helper acceptance pass
Назначение: Accept the V32-16 docs/helper release-readiness scope with active v33/v32 reference metadata, triage coverage and focused docs/KB/mojibake tests before runtime lane packages are integrated.
Артефакт: [context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md](./context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md)
Статус: актуален.
Источник: chat + release-readiness acceptance.
ID: `PLAN-0025`.

26. V32-11 diagnostics SEND-bundle evidence acceptance
Назначение: Accept the diagnostics/SEND-bundle evidence contract for PB-002, RGH-006, RGH-007, RGH-016 and OG-005 with evidence manifest, latest pointer/SHA proof, health-after-triage warnings and targeted V32-11 tests; this does not close final release OG-005 without a durable bundle path.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md)
Статус: актуален.
Источник: chat + V32-11 diagnostics evidence.
ID: `PLAN-0026`.

27. V32-15 runtime evidence hard-gate acceptance
Назначение: Accept the runtime evidence validator/hard-gate contract for PB-006, RGH-011, RGH-012, RGH-019, OG-003 and OG-004 with browser perf, viewport gating and animator frame-budget tests; current workspace probe still hard-fails missing measured artifacts so gaps remain open.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md)
Статус: актуален.
Источник: chat + V32-15 runtime evidence.
ID: `PLAN-0027`.

28. V32-14/V32-09 producer animator truth contract acceptance
Назначение: Accept the producer/animator truth evidence contracts for PB-001, RGH-001, RGH-002, RGH-003, RGH-018, OG-001 and OG-002 with solver-points, hardpoints, packaging passport, geometry acceptance and animator truth-gate tests; OG-001 and OG-002 remain open until a named release bundle and complete cylinder packaging passport exist.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md)
Статус: актуален.
Источник: chat + V32-14/V32-09 producer animator truth.
ID: `PLAN-0028`.

29. V32-06/V32-08 compare objective integrity contract acceptance
Назначение: Accept compare/objective integrity contracts for PB-007, PB-008, RGH-013, RGH-014 and RGH-015 with objective persistence, resume mismatch, run-history provenance, compare contract and stale/current banner tests; this is contract/provenance acceptance, not runtime gap closure.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md)
Статус: актуален.
Источник: chat + V32-06/V32-08 compare objective integrity.
ID: `PLAN-0029`.

30. V32-12 geometry reference provenance acceptance
Назначение: Accept the geometry reference evidence contract for PB-001, PB-008, RGH-018, OG-001, OG-002 and OG-006 with artifact freshness, road-width, packaging passport, geometry acceptance and diagnostics handoff tests; OG-006 remains an imported-layer/runtime-proof open question until named release artifact and SEND-bundle proof exist.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md)
Статус: актуален.
Источник: chat + V32-12 geometry reference.
ID: `PLAN-0030`.

31. V32-10 Desktop Mnemo truth graphics acceptance
Назначение: Accept the Desktop Mnemo dataset/provenance truth-graphics contract for V32-10 and RGH-003 with source markers, scheme fidelity, unavailable-state policy, snapshot, settings bridge, launcher and window tests; this is specialized Mnemo acceptance, not runtime gap closure.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md)
Статус: актуален.
Источник: chat + V32-10 Desktop Mnemo truth graphics.
ID: `PLAN-0031`.

32. V32-02/V32-04 inputs suite handoff acceptance
Назначение: Accept the frozen inputs and suite handoff evidence for WS-INPUTS, WS-RING, WS-SUITE, WS-BASELINE, HO-002, HO-003, HO-004 and HO-005 with inputs_snapshot, validated_suite_snapshot, stale/current banners, command discoverability and baseline gate tests; this is handoff acceptance, not solver/runtime closure.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md)
Статус: актуален.
Источник: chat + V32-02/V32-04 inputs suite handoff.
ID: `PLAN-0032`.

33. DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md
Назначение: Diagnostics producer-owned warning handoff after SEND-bundle hardening; keeps missing producer evidence visible without runtime closure claims.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md](./context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0033`.

34. ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md
Назначение: V32-13 Engineering Analysis/Calibration/Influence evidence note for HO-007 selected-run contracts, HO-008 animator context and HO-009 diagnostics manifest without SEND runtime closure claims.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0034`.

35. V32-13 Engineering Analysis evidence acceptance
Назначение: Accept Engineering Analysis/Calibration/Influence evidence contracts for WS-ANALYSIS, HO-007, HO-008 and HO-009 with selected_run_contract, compare influence surfaces, unit catalog, report provenance, engineering_analysis_evidence_manifest and analysis-to-animator link tests; this is contract/provenance acceptance, not diagnostics/SEND runtime closure.
Артефакт: [context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md)
Статус: актуален.
Источник: chat + V32-13 Engineering Analysis.
ID: `PLAN-0035`.

36. Self-check silent warnings review
Назначение: Review generated REPORTS/SELF_CHECK_SILENT_WARNINGS.json and .md as clean self-check snapshots with rc=0, fail_count=0 and warn_count=0; keep them as release-readiness report provenance only, not diagnostics/SEND runtime closure and not a replacement for V32-11 producer-owned warning handoffs.
Артефакт: [context/release_readiness/SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md](./context/release_readiness/SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md)
Статус: актуален.
Источник: chat + V32-11/V32-16 self-check review.
ID: `PLAN-0036`.

37. V32-11/V32-06 focused dirty subset validation
Назначение: Record focused validation for current diagnostics readiness-reason evidence and optimizer stale HO-006 blocked-summary coverage: diagnostics producer readiness reasons remain evidence-only and do not close SEND/runtime gaps; optimizer stale baseline formatting is V32-06 contract UI coverage, not optimizer runtime closure.
Артефакт: [context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md](./context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md)
Статус: актуален.
Источник: chat + V32-11/V32-06 focused validation.
ID: `PLAN-0037`.

## Текущее правило интерпретации

Если в будущем возникает вопрос:

- "какой план у проекта сейчас?",
- "какой prompt выдавать новому чату?",
- "какая декомпозиция уже была согласована?",

то сначала нужно читать этот файл, затем открывать соответствующий linked plan document.

