# V19 Graph Iteration Imported Reference Layer

Imported from `pneumo_gui_graph_iteration_v19.zip`.

This directory is a repo-local imported reference layer, not a manually
maintained human-readable canon. The human-readable GUI source of truth remains:

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`

`v38_actualized_with_v10` remains the current active KB/TZ/spec successor layer.
V19 is an active detailed graph/action-feedback refinement for four route-critical
workspaces: `WS-INPUTS`, `WS-RING`, `WS-OPTIMIZATION`, and `WS-DIAGNOSTICS`.

Raw `.zip` files are not stored in git. CSV, DOT, JSON, and markdown artifacts in
this folder are imported as source artifacts and should stay close to the archive
shape. Derived interpretation belongs in `17/18`, `PROJECT_SOURCES.md`, the GUI
knowledge base, and doc-contract tests.

## Scope

V19 extends the GUI-spec with internal action-to-feedback subgraphs. It does not
only ask where a user navigates; it also records:

- what task the user is trying to perform;
- which checks and blocking states the UI must expose;
- what feedback, loop, and next step must be visible;
- whether current runtime internals are proven or only evidence-bound.

V19 explicitly does not prove full current runtime/window coverage. For current
`WS-INPUTS`, `WS-RING`, `WS-OPTIMIZATION`, and `WS-DIAGNOSTICS` internals, the
current layer remains evidence-bound unless a separate runtime artifact proves
otherwise. In short: this is not runtime-closure proof.

## Key Artifacts

- `EXEC_SUMMARY.json` - machine-readable package summary and metrics.
- `GRAPH_ANALYSIS_REPORT_V19.md` - human-readable graph analysis and boundary.
- `SEMANTIC_FIX_PRIORITY_V19.md` - priority label/microcopy fixes.
- `NODE_CATALOG_V19.csv` and `EDGE_CATALOG_V19.csv` - graph nodes and edges.
- `USER_ACTION_FEEDBACK_MATRIX_V19.csv` - action-to-feedback edges.
- `TASK_CHECK_BLOCK_LOOP_MATRIX_V19.csv` - task/check/block/loop nodes.
- `COGNITIVE_VISIBILITY_MATRIX_V19.csv` - visibility requirements.
- `TREE_DIRECT_OPEN_MATRIX_V19.csv` - direct-open route requirements.
- `DOCK_WINDOW_AND_DOCK_WIDGET_MATRIX_V19.csv` - dock/window expectations.
- `PATH_COST_SCENARIOS_V19.csv` - user-path cost scenarios.
- `GUI_LABEL_SEMANTIC_AUDIT_V19.csv` - label semantic audit.
- `CURRENT_INTERNAL_DEFICITS_V19.csv` - current evidence-bound deficits.
- `NOT_PROVEN_CURRENT_WINDOWS_V19.csv` - explicit not-proven current windows.
- `COMPLIANCE_MATRIX_V19.csv` and `GRAPH_METRICS_V19.csv` - coverage and metrics.
- `SUBGRAPH_CURRENT_WS-*.dot` - current evidence-bound subgraphs.
- `SUBGRAPH_OPTIMIZED_WS-*.dot` - optimized target subgraphs.

## Implementation Consequences

- `WS-INPUTS` must make two-spring selection, alignment mode/method/residual,
  mirror symmetry, graphical twins, and validated snapshot visible before numeric
  edits look final.
- `WS-RING` must make segment geometry semantics, turn type, single crossfall
  parameter, seam gate, auto-close, and stale export state first-class.
- `WS-OPTIMIZATION` must keep one active mode, objective contract summary, stage
  live rows, underfill/gate reasons, promotion reasons, and history provenance
  visible.
- `WS-DIAGNOSTICS` must keep one dominant collect route, self-check/runtime
  provenance, contents preview before collect, and send actions only after a
  ready diagnostics archive.

Use V19 when planning or reviewing GUI work in these four workspaces. If V19
conflicts with `17/18`, keep `17/18` authoritative and record the conflict as a
gap or assumption instead of silently treating imported data as runtime proof.
