# Branch And Tree Recovery Audit 2026-04-18

Purpose: record the recovery pass after the local branch/worktree sprawl and
the mixed GUI dirty tree. This document supersedes the branch/worktree state
reported in `CODE_TREE_AUDIT_2026-04-18.md` for new work starts.

This is a coordination and hygiene artifact. It does not approve the
quarantined GUI code and does not claim runtime closure.

## Repository State After Recovery

Command snapshot:

- current primary worktree: `C:\Users\Admin\Documents\GitHub\pneumo2`
- current branch: `codex/work`
- remote tracking branch: `origin/codex/work`
- primary worktree status after cleanup: clean
- remote branches after `git fetch --all --prune`: `origin/main`,
  `origin/codex/work`
- local branches intentionally retained: `main`, `codex/work`,
  `codex/quarantine-mixed-gui-dirty-20260418`
- additional local worktrees after cleanup: none
- tracked Python files: `1140`
- tracked tests: `492`
- tracked GUI/desktop/web-adjacent tests matched by audit query: `164`

## What Was Cleaned

The mixed dirty work that was present in the primary worktree was preserved
first, then the working tree was cleaned.

Preserved safety snapshot:

- local branch: `codex/quarantine-mixed-gui-dirty-20260418`
- commit: `7823dc2 chore: quarantine mixed gui dirty tree`
- scope: unfinished mixed changes across main shell, input editor, Desktop
  Mnemo, optimizer/results and related tests
- status: quarantine only, not approved for integration and not a source branch
  for new chats

Additional local safety copies were stored under the ignored workspace folder:

- `workspace/20260418_branch_tree_audit/full_unstaged.patch`
- `workspace/20260418_branch_tree_audit/full_staged.patch`
- `workspace/20260418_branch_tree_audit/input.patch`
- `workspace/20260418_branch_tree_audit/shell.patch`
- `workspace/20260418_branch_tree_audit/mnemo.patch`
- `workspace/20260418_branch_tree_audit/optimizer_results.patch`
- `workspace/20260418_branch_tree_audit/DESKTOP_MNEMO_WINDOWS_ACCEPTANCE_2026-04-18.md`

Removed local duplicate worktrees:

- `C:\Users\Admin\Documents\GitHub\pneumo2_compare_viewer_acceptance`
- `C:\Users\Admin\Documents\GitHub\pneumo2_desktop_animator_truth_runtime`
- `C:\Users\Admin\Documents\GitHub\pneumo2_desktop_animator_truth_runtime_clean`
- `C:\Users\Admin\Documents\GitHub\pneumo2_diagnostics_send_bundle`
- `C:\Users\Admin\Documents\GitHub\pneumo2_diagnostics_send_bundle_fresh`
- `C:\Users\Admin\Documents\GitHub\pneumo2_engineering_analysis_calibration`
- `C:\Users\Admin\Documents\GitHub\pneumo2_engineering_analysis_calibration_traceability`
- `C:\Users\Admin\Documents\GitHub\pneumo2_geometry_producer_truth`
- `C:\Users\Admin\Documents\GitHub\pneumo2_geometry_producer_truth_v2`
- `C:\Users\Admin\Documents\GitHub\pneumo2_ring_run_setup_handoff`

Deleted local duplicate/stale lane branches:

- `codex/compare-viewer-acceptance`
- `codex/desktop-animator-truth-runtime`
- `codex/desktop-animator-truth-runtime-clean`
- `codex/desktop-mnemo-windows-acceptance`
- `codex/diagnostics-send-bundle`
- `codex/diagnostics-send-bundle-honest-evidence`
- `codex/engineering-analysis-calibration`
- `codex/engineering-analysis-calibration-traceability`
- `codex/geometry-producer-truth`
- `codex/geometry-producer-truth-v2`
- `codex/input-data-gui`
- `codex/input-data-gui-20260418`
- `codex/main-shell-launch-surface`
- `codex/optimizer-results-center`
- `codex/optimizer-results-center-20260418`
- `codex/ring-run-setup-handoff`

Remote cleanup result:

- no stale remote lane branches were present after prune;
- no remote branch deletion was required;
- `origin/codex/work` remains the integration trunk for project work.

## Code Audit Snapshot

Largest tracked Python files by line count:

| lines | path | lane risk |
| ---: | --- | --- |
| 26062 | `pneumo_solver_ui/desktop_animator/app.py` | very large specialized Desktop Animator surface |
| 16965 | `pneumo_solver_ui/qt_compare_viewer.py` | very large specialized Compare Viewer surface |
| 13762 | `pneumo_solver_ui/desktop_mnemo/app.py` | very large specialized Desktop Mnemo surface |
| 7717 | `pneumo_solver_ui/model_pneumo_v9_doublewishbone_camozzi.py` | model/solver layer, not a GUI dumping ground |
| 7498 | `pneumo_solver_ui/pneumo_ui_app.py` | legacy WEB/reference surface, not target platform |
| 5913 | `pneumo_solver_ui/model_pneumo_v9_mech_doublewishbone_worldroad.py` | model/solver layer |
| 5327 | `pneumo_solver_ui/tools/desktop_input_editor.py` | large input editor surface |
| 4052 | `pneumo_solver_ui/app.py` | legacy/app surface |
| 3675 | `pneumo_solver_ui/model_pneumo_v9_mech_doublewishbone_r48_reference.py` | model/solver layer |
| 3527 | `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum.py` | model/solver layer |
| 3500 | `pneumo_solver_ui/opt_worker_v3_margins_energy.py` | optimizer worker layer |
| 3345 | `pneumo_solver_ui/param_influence_ui.py` | engineering/influence surface |

Implications:

- do not grow `desktop_animator/app.py`, `qt_compare_viewer.py` or
  `desktop_mnemo/app.py` with unrelated shell or workflow code;
- do not duplicate the specialized windows inside the main shell;
- migrate WEB functionality to classic desktop GUI without expanding WEB;
- prefer focused helpers, adapters, tests and evidence files over monolithic
  cross-lane patches.

## Knowledge Base Conformance

The cleaned tree now matches the active knowledge-base direction in these
points:

| KB rule | recovery decision |
| --- | --- |
| GUI-first, no WEB-first future | New prompts forbid WEB expansion; WEB may only remain as legacy reference or launch bridge. |
| Modular desktop GUI | One integration trunk plus disjoint lane ownership; no pre-created worktree sprawl. |
| Do not duplicate `Desktop Animator`, `Compare Viewer`, `Desktop Mnemo` | Prompt pack treats these as specialized owned surfaces and forbids shell-side reimplementation. |
| Truth-preserving contracts | Producer/model/diagnostics files stay in their lanes; UI prompts require evidence and contract tests. |
| Parallel chats without confusion | New chats start in Plan mode from clean `origin/codex/work` and create branches only after plan approval. |
| Chat requirements and plans must enter KB | This recovery audit and prompt pack are registered as knowledge-base artifacts. |

## Quarantine Rules For Future Chats

The quarantine branch is not a working base.

Allowed:

- inspect it read-only with `git diff` or `git show`;
- copy a small, reviewed hunk into a lane plan after explaining why it belongs
  to that lane;
- reject or split its changes in a Plan-mode report.

Forbidden without explicit user approval:

- merging or rebasing the whole quarantine branch;
- cherry-picking the whole quarantine commit;
- deleting the quarantine branch before all relevant lanes have either
  adopted, rejected or superseded its changes;
- using the quarantine branch as the starting point for new development.

Recommended read-only commands for lane chats:

```powershell
git diff origin/codex/work...codex/quarantine-mixed-gui-dirty-20260418 -- <owned-path>
git show codex/quarantine-mixed-gui-dirty-20260418:<repo-path>
```

## New Parallel Work Policy

1. Start every new chat in Plan mode.
2. Start from clean `origin/codex/work`.
3. Do not create branches or worktrees before the user approves the plan.
4. Use one branch per accepted lane, created only when implementation starts.
5. Do not stage, commit, push, delete, clean or move files in Plan mode.
6. Keep owned/forbidden file boundaries explicit.
7. If a lane needs quarantined code, inspect it read-only and propose a small
   adoption plan.
8. Record new user wishes and generated plans in the knowledge-base layer.

The updated self-contained prompts are stored in:

- `docs/gui_chat_prompts/16_RECOVERY_PLAN_MODE_START_PROMPTS.md`

