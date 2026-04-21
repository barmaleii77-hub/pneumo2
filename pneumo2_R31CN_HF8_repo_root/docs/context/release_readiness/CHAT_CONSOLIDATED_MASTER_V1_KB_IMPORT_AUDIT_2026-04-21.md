# Chat Consolidated Master V1 KB Import Audit - 2026-04-21

Source archive: `C:/Users/User/Downloads/pneumo_chat_consolidated_master_v1.zip`.

Repo-local import target: `docs/context/gui_spec_imports/chat_consolidated_master_v1/`.

Status: imported as consolidated reference/provenance layer. It is not runtime-closure proof and does not replace the human-readable GUI canon in `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md` and `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`.

## Read Coverage

- Archive package id: `pneumo_chat_consolidated_master_v1`.
- Package identity file: `06_INDEX/MASTER_EXEC_SUMMARY.json`.
- Imported file entries from zip: 171.
- Package selfcheck reports `included_artifacts_count = 19`.
- Package selfcheck reports `files_in_package = 168` for the hashed manifest.
- `06_INDEX/PACKAGE_MANIFEST.json` is preserved and validated by doc-contract tests against local file sizes and SHA-256 hashes.
- `06_INDEX/SUPERSEDED_AND_EXCLUDED.csv` is preserved to prevent re-importing noisy or superseded layers as active sources.

## What This Adds To The KB

- A single deduplicated reading order for chat-derived project materials.
- Source context plus the V38+V10 final CODEX spec package.
- V34 repo audit and KB alignment evidence.
- V21 current-to-canonical reconciliation and launchpoint-only triage through
  `04_GRAPH_ANALYSIS/01_reconciliation_v21/GRAPH_ANALYSIS_REPORT_V21.md`.
- V20 workspace graphs for `WS-PROJECT`, `WS-SUITE`, `WS-BASELINE`, `WS-ANALYSIS`
  and `WS-ANIMATOR` through
  `04_GRAPH_ANALYSIS/02_workspace_graphs_v20/GRAPH_ANALYSIS_REPORT_V20.md`.
- V17 route-cost and decision-entropy evidence through
  `04_GRAPH_ANALYSIS/04_cost_entropy_v17/GRAPH_ANALYSIS_REPORT_V17.md`.
- Human report-only layers V10 through V16 for launcher hierarchy, current vs canonical launchpoints, window internals, canonical operations, tree/dock context, state continuity and visibility priority.

## Priority Rule

Use this layer in this order:

1. Keep `17/18` as the human-readable canon.
2. Read `chat_consolidated_master_v1/06_INDEX/*` for package identity, reading order and superseded/excluded decisions.
3. Use `chat_consolidated_master_v1/02_CODEX_SPEC_FINAL/v38_actualized_with_v10/*` for final spec package provenance.
4. Use `chat_consolidated_master_v1/04_GRAPH_ANALYSIS/*` and `05_HUMAN_REPORTS/*` as evidence-bound reference layers.
5. Require separate runtime, visual and release evidence before closing implementation gaps.

## Evidence Boundary

This import proves that the archive was read, copied into the repo-local knowledge stack, indexed and contract-tested. It does not prove current desktop GUI runtime behavior, portable package quality, visual acceptance, real Windows multi-monitor behavior, or successful user-path execution.
