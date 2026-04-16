# Release Gate And Acceptance Map v32

Источник: `C:/Users/Admin/Downloads/pneumo_codex_tz_spec_connector_reconciled_v32.zip`.

Этот файл является repo-side картой для `V32-16. Release Gates, KB и acceptance map`.
Он не объявляет runtime closure. Его задача - связать active v32 reference layer
с локальными docs/tests/helpers так, чтобы будущие чаты не закрывали gate без
доказательства.

## Checked-In References

- [RELEASE_GATE_HARDENING_MATRIX.csv](./RELEASE_GATE_HARDENING_MATRIX.csv) -
  20 hardening rows `RGH-001...RGH-020`.
- [GAP_TO_EVIDENCE_ACTION_MAP.csv](./GAP_TO_EVIDENCE_ACTION_MAP.csv) -
  6 open-gap rows `OG-001...OG-006`.
- [README.md](./README.md) - v32 source authority, reading order, workspaces,
  playbooks, release gates and conflict policy.
- [COMPLETENESS_ASSESSMENT.md](./COMPLETENESS_ASSESSMENT.md) - sufficient as
  planning/contract/evidence layer, not runtime proof.
- [PARALLEL_CHAT_WORKSTREAMS.md](./PARALLEL_CHAT_WORKSTREAMS.md) - owner scope
  and handoff boundaries for parallel chats.

## Archive-Only Matrices To Consult

The raw ZIP remains out of git. When deeper evidence is needed, read these
archive files in the v32 primary order:

- `SOURCE_AUTHORITY_MATRIX.csv`
- `ACCEPTANCE_MATRIX.csv`
- `ACCEPTANCE_PLAYBOOK_INDEX.csv`
- `EVIDENCE_REQUIRED_BY_GATE.csv`
- `WORKSPACE_CONTRACT_MATRIX.csv`
- `WORKSPACE_DEPENDENCY_MATRIX.csv`
- `WORKSPACE_HANDOFF_MATRIX.csv`
- `RUNTIME_ARTIFACT_SCHEMA.yaml`

## Blocking Closure Rules

- `RGH-001`, `RGH-002`, `RGH-018` stay tied to `PB-001` and gaps `OG-001` /
  `OG-002`; producer truth is not closed without `anim_latest` contract,
  solver/hardpoint metadata and geometry acceptance evidence.
- `RGH-006`, `RGH-007`, `RGH-016` stay tied to `PB-002` and `OG-005`;
  diagnostics closure requires final SEND bundle, health-after-triage,
  latest pointer and helper runtime provenance.
- `RGH-011`, `RGH-012`, `RGH-019` stay tied to `PB-006` and gaps `OG-003` /
  `OG-004`; performance or viewport fixes are not release-closed without
  measured trace artifacts.
- `RGH-013`, `RGH-014`, `RGH-015` tie objective/compare/stale behavior to
  explicit contracts and banners; silent rebinding of historical artifacts is
  a hard failure.

## Gap-To-Evidence Owners

| Gap | Priority | Required Evidence | Owner Lane |
| --- | --- | --- | --- |
| `OG-001` | P0 | `anim_latest` contract + geometry acceptance report | solver/model/export owners |
| `OG-002` | P0 | complete cylinder packaging passport + truth gate report | solver/export/animator owners |
| `OG-003` | P0 | browser/runtime perf trace in SEND bundle | web/runtime owners |
| `OG-004` | P1 | viewport gating report + trace | web/runtime owners |
| `OG-005` | P1 | Windows SEND bundle + shell runtime proof + latest pointer proof | runtime QA owners |
| `OG-006` | P2 | explicit imported-layer assumption/gap evidence | architecture owners |

## WS-RING / HO-004 Live Evidence

Current repo evidence for `V32-03`, `GAP-005` and the v13 ring gates is scoped
to the `WS-RING -> WS-SUITE` handoff. It does not close unrelated runtime gaps.

- `RG-GATE-012`: `tests/test_r56_ring_editor_canonical_segment_semantics.py`
  checks `segment_id`, road segment metadata, `passage_mode`, lineage hashes and
  no-hidden-closure metadata in the canonical Ring export.
- `RG-GATE-013`: `tests/test_optimization_auto_ring_suite.py` checks that
  `WS-SUITE` stores immutable Ring refs/hashes, keeps geometry read-only, and
  marks canonical handoffs stale when source/export hashes drift.
- `RG-GATE-016`: `tests/test_r56_ring_editor_canonical_segment_semantics.py`
  checks `preview_open_only` warnings and export state so an open preview cannot
  masquerade as a closed road.

## Local Helper Contract

- `pneumo_solver_ui/release_gate.py` exposes read-only helpers for the local
  v32 hardening and gap maps.
- `pneumo_solver_ui/workspace_contract.py` exposes the 12 v32 workspace IDs and
  handoff IDs as contract metadata.
- `tests/test_gui_spec_docs_contract.py` is the executable docs contract for
  this layer, including row counts, active links and mojibake checks.
