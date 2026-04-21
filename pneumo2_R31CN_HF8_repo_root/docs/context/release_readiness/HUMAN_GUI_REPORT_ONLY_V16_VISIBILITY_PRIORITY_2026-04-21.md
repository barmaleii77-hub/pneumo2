# Human GUI Report V16 Visibility Priority Import Audit

Source archive:
`C:/Users/User/Downloads/pneumo_human_gui_report_only_v16_visibility_priority.zip`

Import date: 2026-04-21.

## Status

V16 is imported as a repo-local report-only reference layer in
`docs/context/gui_spec_imports/v16_visibility_priority/`.

It updates the knowledge base with visibility priority and must-see state rules,
but it is not a runtime-closure proof, not live screenshot evidence and not a
claim that the current GUI implementation already satisfies the policy.

## Read Coverage

The following archive files were imported and reconciled into the knowledge
stack:

- `VISIBILITY_PRIORITY_POLICY_V16.md`
- `MUST_SEE_STATE_MATRIX_V16.csv`
- `ALWAYS_VISIBLE_CONDITIONAL_INSPECTOR_MATRIX_V16.csv`
- `DOCK_REGION_VISIBILITY_POLICY_V16.csv`
- `WORKSPACE_FIRST_5_SECONDS_V16.csv`
- `COGNITIVE_LOAD_REDUCTION_V16.csv`
- `VISIBILITY_ESCALATION_GRAPH_V16.dot`
- `EXEC_SUMMARY.md`
- `HOW_TO_FIX_V16.md`
- `LIMITS_AND_EVIDENCE_V16.md`
- `WHAT_IS_BAD_V16.md`
- `WHAT_IS_GOOD_V16.md`

## KB Reconciliation

V16 refines V15 continuity/repair-loop work by answering a sharper question:
which state must be visible immediately, which state should escalate only under
conflict, and which details may safely live in the inspector/help layer.

The main GUI-spec impact is:

- Must-see states cannot live only in the inspector or help panel.
- Always-visible state includes active project, current route/workspace, active
  source of truth, current step and global conflict/trust markers.
- Conditional escalation applies to stale, dirty, mismatch, invalid, degraded,
  underfill, blocked and current-vs-historical states.
- Inspector-only placement is acceptable only for details that do not affect
  first decision, result interpretation, repair route or trust.
- The left tree is a first-class direct launcher, the right inspector is
  secondary context, the bottom bar owns status/progress and message/banner
  surfaces own conflicts and blockers.
- Every primary workspace should communicate location, current context, main
  state, trust/conflict and next recommended step within 3-5 seconds.

## Non-Closure Boundary

This audit records a knowledge-base import. It does not close any runtime,
visual, accessibility, packaging or release gate by itself. Future GUI changes
must still provide separate runtime evidence before claiming acceptance.
