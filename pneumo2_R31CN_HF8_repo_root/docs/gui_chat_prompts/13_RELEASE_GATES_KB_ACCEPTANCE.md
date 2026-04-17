# V32-16 Release Gates, KB And Acceptance Map

## Канонический слой

Перед работой читать:

1. [../00_PROJECT_KNOWLEDGE_BASE.md](../00_PROJECT_KNOWLEDGE_BASE.md)
2. [../PROJECT_SOURCES.md](../PROJECT_SOURCES.md)
3. [../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
4. [../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
5. [../context/gui_spec_imports/v33_connector_reconciled/README.md](../context/gui_spec_imports/v33_connector_reconciled/README.md)
6. [../context/gui_spec_imports/v32_connector_reconciled/README.md](../context/gui_spec_imports/v32_connector_reconciled/README.md)
7. [../context/gui_spec_imports/v32_connector_reconciled/COMPLETENESS_ASSESSMENT.md](../context/gui_spec_imports/v32_connector_reconciled/COMPLETENESS_ASSESSMENT.md)
8. [../context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md](../context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md)
9. [../context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md](../context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md)
10. [../context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_HARDENING_MATRIX.csv](../context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_HARDENING_MATRIX.csv)
11. [../context/gui_spec_imports/v32_connector_reconciled/GAP_TO_EVIDENCE_ACTION_MAP.csv](../context/gui_spec_imports/v32_connector_reconciled/GAP_TO_EVIDENCE_ACTION_MAP.csv)
12. [../context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md)
13. [../context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md)
14. [../context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md)
15. [../context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md)
16. [../context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md)
17. [../context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md)
18. [../context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md)
19. [../context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md](../context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md)
20. [../context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md](../context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md)
21. [../context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md](../context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md)
22. [../context/release_readiness/SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md](../context/release_readiness/SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md)
23. [../context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md](../context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md)
24. [../context/release_readiness/PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17.md](../context/release_readiness/PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17.md)

## Scope

Owned scope:

- docs and source-authority references;
- KB logs and `knowledge_base_sync` entries;
- release-readiness triage docs for dirty-tree ownership;
- self-check warnings review docs for generated report provenance;
- lane evidence notes and producer-warning handoffs for inputs/suite handoff,
  producer, compare, geometry, mnemo, engineering analysis, diagnostics and
  runtime/perf hard gates;
- V32-16 acceptance note for docs/helper integration order;
- `release_gate.py` and `workspace_contract.py` helper metadata;
- acceptance map docs/tests;
- prompt indexes and no-mojibake checks.

Do not implement domain runtime features here. Producer truth, animator,
diagnostics bundle, performance traces, optimizer contracts and geometry closure
belong to their owner lanes; this lane only maps their required evidence.

## Acceptance Rules

- Keep `RGH-001...RGH-020` and `OG-001...OG-006` discoverable from local docs.
- Keep release closure claims evidence-bound: artifact, gate, test and bundle
  proof must be named before a gap can move from `gap` to `covered`.
- Keep active reference order visible: `17/18`, then v33/v32, then v3/v13/v12.
- Keep dirty-tree integration partitioned by V32 lane; triage is ownership/evidence
  metadata, not a reason to merge runtime draft changes into V32-16.
- Update `tests/test_gui_spec_docs_contract.py` when adding a new reference
  layer or prompt entry.
- Run the focused docs contract and no-mojibake check before handoff.
