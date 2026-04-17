# Self-Check Warnings Review 2026-04-17

Scope: `V32-16` release-readiness docs and `V32-11` diagnostics handoff
review.

Reviewed generated artifacts:

- `REPORTS/SELF_CHECK_SILENT_WARNINGS.json`
- `REPORTS/SELF_CHECK_SILENT_WARNINGS.md`

Current generated snapshot:

- `generated_at_utc=2026-04-17T03:36:37Z`
- `release=PneumoApp_v6_80_R176_R31CN_HF8_2026-04-03`
- `rc=0`
- `fail_count=0`
- `warn_count=0`
- `fails=[]`
- `warnings=[]`

Decision: keep the generated self-check silent-warnings reports as a clean
release-readiness snapshot for the current worktree. This review closes the
`needs-review` triage state for those two report files only.

Boundary:

- This does not close `OG-005`.
- This does not supersede the V32-11 diagnostics/SEND bundle warning state in
  `DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md` or
  `DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md`.
- Producer-owned warnings for analysis, geometry, animator and runtime/perf
  evidence remain owned by their V32 lanes until named runtime artifacts or
  SEND-bundle entries exist.
- This review does not alter solver, optimizer, animator, geometry,
  diagnostics runtime behavior, or domain calculations.

Targeted docs validation:

```powershell
python -m pytest tests/test_gui_spec_docs_contract.py tests/test_knowledge_base_sync_contract.py tests/test_ui_text_no_mojibake_contract.py -q
```
