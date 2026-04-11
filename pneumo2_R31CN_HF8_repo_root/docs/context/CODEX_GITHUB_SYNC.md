# Codex GitHub Sync

Purpose: save the Codex continuation context into Git-tracked files so work can be resumed
on another machine after `git pull`.

This workflow does not sync the live Codex chat UI itself. It syncs the repository state,
the tracked context files, and the generated handoff snapshot.

## Paths That Matter

- Git root: `C:\Users\User\Desktop\pneumo2_R31CN_HF8_github_push_package`
- Project root inside the repo: `pneumo2_R31CN_HF8_repo_root`
- Quick refresh command: `pneumo2_R31CN_HF8_repo_root\SAVE_CODEX_CONTEXT_TO_GITHUB.cmd`
- Handoff generator: `pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\tools\write_codex_handoff.py`
- Contract test: `pneumo2_R31CN_HF8_repo_root\tests\test_codex_github_handoff_contract.py`

## Canonical Handoff Files

- `pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_GITHUB_SYNC.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_HANDOFF_LATEST.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_HANDOFF_LATEST.json`
- `pneumo2_R31CN_HF8_repo_root/docs/context/context_pn_main_chat.txt`
- `pneumo2_R31CN_HF8_repo_root/docs/context/AI_SNAPSHOT_WORKING_DELTA_2026-04-08.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/PROJECT_CONTEXT_ANALYSIS_v2.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/WISHLIST.json`
- `pneumo2_R31CN_HF8_repo_root/docs/01_RequirementsFromContext.md`
- `pneumo2_R31CN_HF8_repo_root/docs/01_RequirementsFromContext.json`

## Update Workflow

How to update on the current machine:

1. Open a shell in `pneumo2_R31CN_HF8_repo_root`.
2. Run `SAVE_CODEX_CONTEXT_TO_GITHUB.cmd`.
3. Review `docs/context/CODEX_HANDOFF_LATEST.md`.
4. Run the contract check:

```powershell
pytest tests/test_codex_github_handoff_contract.py
```

5. Stage and push the refreshed context together with the code changes you want to preserve:

```powershell
git -C .. add pneumo2_R31CN_HF8_repo_root
git -C .. commit -m "Update Codex handoff and sync context"
git -C .. push
```

If you are already at the git root instead of the project root, run:

```powershell
.\pneumo2_R31CN_HF8_repo_root\SAVE_CODEX_CONTEXT_TO_GITHUB.cmd
```

## Continue Workflow

How to continue on another machine:

1. Clone or pull the repository and checkout the branch recorded in `CODEX_HANDOFF_LATEST.md`.
2. Open `pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_HANDOFF_LATEST.md` first.
3. Open `pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_GITHUB_SYNC.md` if you need the workflow.
4. Recreate `.venv` if needed.
5. Start the next Codex session with a prompt like:

```text
Read pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_HANDOFF_LATEST.md and continue from the saved branch.
```

## Not Synced By GitHub

- live Codex chat UI/thread state
- git stashes
- local worktrees
- `.venv`
- `local_portable_release/` unless it is explicitly added to git

Use `pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_HANDOFF_LATEST.md` as the source of truth
for the last saved git/context snapshot.
