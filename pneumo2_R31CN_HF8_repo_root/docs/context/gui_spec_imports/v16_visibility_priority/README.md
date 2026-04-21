# V16 visibility priority and must-see state policy

Imported from:
`C:/Users/User/Downloads/pneumo_human_gui_report_only_v16_visibility_priority.zip`

Import date: 2026-04-21.

## Role

This directory is a repo-local imported reference layer for the V16 human GUI
report. It refines the GUI knowledge base after V15 by defining visibility
priority, must-see state markers, dock-region responsibility, first-5-seconds
workspace comprehension and the boundary between primary surfaces and
inspector/help-only details.

`17_WINDOWS_DESKTOP_CAD_GUI_CANON.md` and
`18_PNEUMOAPP_WINDOWS_GUI_SPEC.md` remain the human-readable source of truth.
This V16 layer is additive reference material and not a manually maintained
canon replacement.

## Evidence Boundary

V16 is report-only. It is not a runtime-closure proof, not a screenshot proof of
the current application, and not evidence that the current desktop GUI already
passes visual/runtime acceptance. Use it as a target policy when changing or
auditing GUI surfaces.

## Imported Artifacts

- `VISIBILITY_PRIORITY_POLICY_V16.md` - visibility hierarchy: always visible,
  conditionally escalated and inspector/help/details.
- `MUST_SEE_STATE_MATRIX_V16.csv` - states that must be visible for user trust,
  next action and result interpretation.
- `ALWAYS_VISIBLE_CONDITIONAL_INSPECTOR_MATRIX_V16.csv` - canonical placement
  policy for always-visible, conditional and inspector-only states.
- `DOCK_REGION_VISIBILITY_POLICY_V16.csv` - region-level visibility rules for
  tree, docks, message bar, inspector and bottom status.
- `WORKSPACE_FIRST_5_SECONDS_V16.csv` - what each workspace must communicate in
  the first 3-5 seconds.
- `COGNITIVE_LOAD_REDUCTION_V16.csv` - rules that reduce cognitive load without
  hiding critical state.
- `VISIBILITY_ESCALATION_GRAPH_V16.dot` - escalation graph from hidden detail to
  visible blocker/return route.
- `EXEC_SUMMARY.md`, `HOW_TO_FIX_V16.md`, `LIMITS_AND_EVIDENCE_V16.md`,
  `WHAT_IS_BAD_V16.md` and `WHAT_IS_GOOD_V16.md` - narrative report notes.

## How To Apply

- Do not hide must-see states only in the right inspector or help text.
- Use top/message/bottom/inline surfaces for state that changes trust,
  interpretation, repair route or next action.
- Reserve inspector/help-only placement for details that do not affect the first
  user decision inside a workspace.
- Treat stale, dirty, invalid, mismatch, degraded and blocked states as
  escalation candidates rather than passive metadata.
- When auditing a workspace, first check whether the user can understand
  location, current context, main state, trust/conflict and next step within
  3-5 seconds.
