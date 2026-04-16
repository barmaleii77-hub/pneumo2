# V32-16 Acceptance Note 2026-04-17

Purpose: accept the V32-16 docs/helper patch as a release-readiness layer before
runtime/domain lane packages are integrated.

This note is not a runtime closure claim. It only records source authority,
ownership, evidence requirements and the focused checks that passed for the
V32-16 scope.

## Accepted Scope

V32-16 owns these release-readiness files for the current pass:

- `docs/context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md`
- `docs/context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md`
- `docs/context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md`
- `docs/context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_HARDENING_MATRIX.csv`
- `docs/context/gui_spec_imports/v32_connector_reconciled/GAP_TO_EVIDENCE_ACTION_MAP.csv`
- `docs/gui_chat_prompts/13_RELEASE_GATES_KB_ACCEPTANCE.md`
- `docs/gui_chat_prompts/00_INDEX.md`
- `docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `docs/13_CHAT_REQUIREMENTS_LOG.md`
- `docs/14_CHAT_PLANS_LOG.md`
- `docs/15_CHAT_KNOWLEDGE_BASE.json`
- `docs/PROJECT_SOURCES.md`
- `pneumo_solver_ui/tools/knowledge_base_sync.py`
- `pneumo_solver_ui/workspace_contract.py`
- `tests/test_gui_spec_docs_contract.py`
- `tests/test_knowledge_base_sync_contract.py`

`pneumo_solver_ui/release_gate.py` is accepted only for read-only source
metadata helpers and gate-report `reference_layers`. Its runtime-evidence CLI
options remain V32-15 draft work until that lane supplies measured artifacts.

## Source Alignment

- Active connector layer: `docs/context/gui_spec_imports/v33_connector_reconciled`.
- Active workstream/gate-extract layer:
  `docs/context/gui_spec_imports/v32_connector_reconciled`.
- V32 checked-in extracts stay minimal: 20 hardening rows, 6 open-gap rows and
  one human acceptance map.
- Raw connector ZIP files are not imported into the repository.

## Closure Rule

No gap moves to `covered` from docs alone. A closure claim must name:

- an artifact path;
- a test id or targeted pytest command;
- SEND-bundle evidence or runtime evidence where the gate requires it.

## Validation

Focused V32-16 checks passed:

```powershell
python -m pytest tests/test_gui_spec_docs_contract.py tests/test_knowledge_base_sync_contract.py tests/test_ui_text_no_mojibake_contract.py -q
```

Result: `23 passed`.

## Next Integration Order

1. Diagnostics evidence: V32-11, `OG-005`, SEND bundle and diagnostics note.
2. Runtime evidence: V32-15, `OG-003` and `OG-004`, measured traces only.
3. Producer truth: V32-14, `OG-001`, producer-side hardpoints and anim export.
4. Animator truth: V32-09, `OG-002`, truth states and frame-budget evidence.
5. Compare/objective integrity: V32-08 and V32-06, mismatch and stale-context tests.
