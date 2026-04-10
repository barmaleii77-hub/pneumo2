# Codex GitHub Sync

Purpose: continue work on another machine by moving the project context through GitHub.

This setup does not sync the live Codex chat window itself. It syncs Git-tracked context
and handoff files inside the repository so another machine can `git pull` and continue.

## Canonical handoff files

- `docs/context/CODEX_HANDOFF_LATEST.md`
- `docs/context/CODEX_HANDOFF_LATEST.json`
- `docs/context/context_pn_main_chat.txt`
- `docs/context/AI_SNAPSHOT_WORKING_DELTA_2026-04-08.md`
- `docs/context/PROJECT_CONTEXT_ANALYSIS_v2.md`
- `docs/context/WISHLIST.json`
- `docs/01_RequirementsFromContext.md`
- `docs/01_RequirementsFromContext.json`

## Update the handoff on the current machine

1. Run `SAVE_CODEX_CONTEXT_TO_GITHUB.cmd` from the repository root.
2. Review `docs/context/CODEX_HANDOFF_LATEST.md`.
3. Commit and push the updated handoff files:

```powershell
git add docs/context/CODEX_HANDOFF_LATEST.md docs/context/CODEX_HANDOFF_LATEST.json docs/context/CODEX_GITHUB_SYNC.md SAVE_CODEX_CONTEXT_TO_GITHUB.cmd
git commit -m "Update Codex handoff"
git push
```

## Continue on another machine

1. Clone or pull the repository.
2. Open `docs/context/CODEX_HANDOFF_LATEST.md` first.
3. Open `docs/context/CODEX_GITHUB_SYNC.md` if you need the workflow.
4. Recreate `.venv` if needed.
5. Start the next Codex session with a short prompt such as:

```text
Read docs/context/CODEX_HANDOFF_LATEST.md and continue from main.
```

## Not synced by GitHub

- live Codex chat UI/thread state
- git stashes
- local worktrees
- `.venv`
- sibling folders outside the repository, including `../local_portable_release/`

Use `docs/context/CODEX_HANDOFF_LATEST.md` as the source of truth for what existed locally
when the last handoff snapshot was created.
