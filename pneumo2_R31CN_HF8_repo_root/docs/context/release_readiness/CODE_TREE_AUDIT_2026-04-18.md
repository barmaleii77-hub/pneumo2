# Code Tree Audit 2026-04-18

Purpose: record the code-tree audit after branch cleanup and before launching
the next wave of parallel Plan-mode chats.

This is a coordination and hygiene artifact. It does not claim runtime closure
and does not approve unreviewed dirty code.

## Repository State

Command snapshot:

- current branch: `codex/work`
- remote tracking: `origin/codex/work`
- `main` remains present but is not the working trunk for new chats
- tracked Python files: `1140`
- tracked desktop/Qt GUI focused tests counted by audit query: `47`

Local branch/worktree state after the previous cleanup:

- primary worktree: `C:\Users\Admin\Documents\GitHub\pneumo2`
- additional clean worktrees exist for prepared parallel lanes:
  `compare-viewer-acceptance`, `desktop-animator-truth-runtime`,
  `diagnostics-send-bundle`, `engineering-analysis-calibration`,
  `geometry-producer-truth`, `ring-run-setup-handoff`
- several local lane branches also exist without dedicated worktrees:
  `desktop-mnemo-windows-acceptance`, `input-data-gui`,
  `main-shell-launch-surface`, `optimizer-results-center`

The prepared lane worktrees are not deleted in this audit. They are clean
branch/workspace boundaries that can be used by future chats if explicitly
assigned. Removing them now would increase the chance of another chat losing
its working context.

## Dirty Worktree Audit

The primary `codex/work` worktree is currently dirty. These changes were
present before this audit pass and are treated as existing work, not as audit
edits.

Dirty tracked code/test files observed:

| lane | dirty paths |
| --- | --- |
| V32-01 Main Shell | `START_PNEUMO_APP.py`; `pneumo_solver_ui/desktop_qt_shell/main_window.py`; `pneumo_solver_ui/desktop_qt_shell/runtime_proof.py`; `tests/test_desktop_main_shell_qt_contract.py`; `tests/test_web_launcher_desktop_bridge_contract.py` |
| V32-02 Input Data | `pneumo_solver_ui/desktop_input_graphics.py`; `pneumo_solver_ui/desktop_input_model.py`; `pneumo_solver_ui/tools/desktop_input_editor.py`; `tests/test_desktop_input_editor_contract.py` |
| V32-10 Desktop Mnemo | `pneumo_solver_ui/desktop_mnemo/app.py`; `pneumo_solver_ui/desktop_mnemo/runtime_proof.py`; `tests/test_desktop_mnemo_runtime_proof.py`; `tests/test_desktop_mnemo_window_contract.py`; `docs/context/release_readiness/DESKTOP_MNEMO_WINDOWS_ACCEPTANCE_2026-04-18.md` |
| V32-06/V32-07 Optimizer/Results | `pneumo_solver_ui/desktop_optimizer_panels.py`; `pneumo_solver_ui/desktop_optimizer_runtime.py`; `pneumo_solver_ui/desktop_results_model.py`; `pneumo_solver_ui/desktop_results_runtime.py`; `pneumo_solver_ui/tools/desktop_optimizer_center.py`; `pneumo_solver_ui/tools/desktop_results_center.py`; `tests/test_desktop_optimizer_center_contract.py`; `tests/test_test_center_results_center_contract.py` |

Policy:

- do not overwrite these files from another prompt-pack or audit task;
- any chat assigned to one of these lanes must first inspect the dirty diff and
  decide whether to adopt, split, finish or revert with explicit user approval;
- chats assigned to other lanes must avoid these dirty files unless the user
  explicitly reassigns ownership.

## Ignored Artifact Audit

`git clean -ndX` reported ignored artifacts including:

- Python cache folders such as `__pycache__/` and `.pytest_cache/`
- runtime workspaces such as `workspace/`
- local logs under `pneumo_solver_ui/logs/`
- release/package artifacts such as `local_portable_release/` and
  `send_bundles/`

No bulk ignored-file deletion was performed. A blanket `git clean -fX` would be
unsafe because it would remove local release/send-bundle artifacts that may be
needed for diagnostics or operator handoff. Future cleanup should target only
specific generated cache paths after verifying the resolved absolute paths.

## Code Hotspots

Largest tracked Python files by line count in the audit snapshot:

| lines | path | note |
| ---: | --- | --- |
| 26062 | `pneumo_solver_ui/desktop_animator/app.py` | very large specialized GUI surface; changes must be isolated |
| 16965 | `pneumo_solver_ui/qt_compare_viewer.py` | very large specialized Compare Viewer surface |
| 13779 | `pneumo_solver_ui/desktop_mnemo/app.py` | very large Mnemo surface with current dirty work |
| 7717 | `pneumo_solver_ui/model_pneumo_v9_doublewishbone_camozzi.py` | solver/model layer; avoid UI-driven drift |
| 7498 | `pneumo_solver_ui/pneumo_ui_app.py` | legacy WEB/reference surface, not target platform |
| 5913 | `pneumo_solver_ui/model_pneumo_v9_mech_doublewishbone_worldroad.py` | solver/model layer |
| 5415 | `pneumo_solver_ui/tools/desktop_input_editor.py` | current dirty input GUI surface |
| 4052 | `pneumo_solver_ui/app.py` | legacy/app surface |
| 3345 | `pneumo_solver_ui/param_influence_ui.py` | engineering/influence surface |
| 2669 | `pneumo_solver_ui/tools/make_send_bundle.py` | diagnostics/SEND bundle surface |

Implication:

- specialized windows must stay specialized;
- large files should not be used as dumping grounds for cross-lane behavior;
- new work should prefer small helpers, focused tests and ownership boundaries.

## Tree Hygiene Decisions

1. Keep `codex/work` as integration trunk.
2. Do not start new work from `main`.
3. Do not delete prepared clean lane worktrees without confirming the owning
   chat has finished.
4. Do not bulk-clean ignored artifacts because release bundles and local
   diagnostics are mixed with caches.
5. Update the plan-mode starter prompts so every lane sees current dirty-file
   risks before touching code.

## Immediate Next Prompt Pack

The new self-contained prompts for the same 10 parallel chats are stored in:

- `docs/gui_chat_prompts/15_CODE_AUDIT_PLAN_MODE_START_PROMPTS.md`

These prompts supersede the older generic prompt-pack for new chats because
they include the current dirty tree state and first-action constraints.
