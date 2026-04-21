# Chat Consolidated Master V1 Import Note

Imported on 2026-04-21 from `C:/Users/User/Downloads/pneumo_chat_consolidated_master_v1.zip`.

This directory is a repo-local consolidated reference layer. It preserves the archive source set as imported reference artifacts and gives the project one deduplicated reading order for the latest chat-derived GUI/TZ/KB materials. The raw `.zip` file is intentionally not stored in git.

Human-readable source of truth remains:

1. `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
2. `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`

This layer does not replace `17/18`, does not replace live runtime evidence, and is not runtime-closure proof. It is used to understand lineage, consolidated intent, superseded archive decisions, and the next audit/reconciliation surface.

## What The Layer Contains

- `01_SOURCE_CONTEXT/` - original prompts, project context, release notes and research context.
- `02_CODEX_SPEC_FINAL/v38_actualized_with_v10/` - final CODEX spec package actualized with V10 launcher hierarchy.
- `03_REPO_AUDIT/v34_repo_audit/` - repo audit and KB conformance evidence from V34.
- `04_GRAPH_ANALYSIS/` - graph/cost/reconciliation packages V17, V19, V20 and V21.
- `05_HUMAN_REPORTS/` - human report-only layers V10 through V16.
- `06_INDEX/` - package identity, manifest, selfcheck, lineage, included artifacts and superseded/excluded registry.

## Recommended Reading Order

1. `README.md`
2. `06_INDEX/MASTER_EXEC_SUMMARY.json`
3. `06_INDEX/LINEAGE_AND_READING_ORDER.md`
4. `06_INDEX/INCLUDED_ARTIFACTS.csv`
5. `06_INDEX/SUPERSEDED_AND_EXCLUDED.csv`
6. `02_CODEX_SPEC_FINAL/v38_actualized_with_v10/TECHNICAL_SPECIFICATION.md`
7. `03_REPO_AUDIT/v34_repo_audit/AUDIT_REPORT.md`
8. `04_GRAPH_ANALYSIS/00_MASTER_SUMMARY.md`
9. `05_HUMAN_REPORTS/00_MASTER_SUMMARY.md`

## Use Boundaries

- Use V21 reconciliation for current-to-canonical gap finding and launchpoint triage.
- Use V20 workspace graphs for project, suite, baseline, analysis and animator routes that were not covered by the earlier V19-focused import.
- Use V17 cost/entropy data to reason about path-cost and cognitive-load reduction.
- Use human reports V10-V16 for launcher hierarchy, window internals, state continuity and visibility-priority evidence.
- Do not treat this import as visual acceptance, runtime acceptance, package build proof or a reason to close open GUI/runtime gaps.
