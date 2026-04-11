# Codex Handoff Latest

Generated: `2026-04-10T16:54:24+03:00`
Git root: `C:\Users\User\Desktop\pneumo2_R31CN_HF8_github_push_package`
Project root: `C:\Users\User\Desktop\pneumo2_R31CN_HF8_github_push_package\pneumo2_R31CN_HF8_repo_root`
Project root from git: `pneumo2_R31CN_HF8_repo_root`
Origin: `https://github.com/barmaleii77-hub/pneumo2.git`

## Current Git state

- Branch: `codex/desktop-animator-cinematic-pass-r76`
- HEAD: `7cfa972` (`7cfa972f934d5d808b712a74ccbbf89bc56a9ae7`)
- Upstream: `origin/codex/desktop-animator-cinematic-pass-r76`
- Ahead/behind upstream: `2/0`

### Manual notes

- Snapshot captures saved work commit 7cfa972 on branch codex/desktop-animator-cinematic-pass-r76.
- Validated in .venv with the targeted playback/render/handoff test subset before sync.
- local_portable_release remains local-only unless it is explicitly added to git.

### Status

- `## codex/desktop-animator-cinematic-pass-r76...origin/codex/desktop-animator-cinematic-pass-r76 [ahead 2]`
- ` M pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_HANDOFF_LATEST.json`
- ` M pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_HANDOFF_LATEST.md`
- `?? local_portable_release/`

### Recent commits

- `7cfa972 Fix Codex handoff divergence parsing`
- `e9c1c68 Save animator progress and Codex handoff tooling`
- `93e99b8 Add GitHub-backed Codex handoff sync`
- `2dd4d80 Fix animator update_frame helper scope`
- `0319c77 Fix UI mojibake and heavy results event context`
- `4bdf3ba Fix baseline all-tests mojibake filter`
- `9c6f760 Fix ring editor default dt contract`
- `de5d08a Fix portable UI params columns and bundle manifest casing`
- `a514321 Fix UI regression contracts and expdb scope export`
- `919bfd0 Merge branch 'codex/desktop-animator-cinematic-pass-r76' into codex/merge-main-hf8`

### Branches already at this HEAD

Local:
- `codex/desktop-animator-cinematic-pass-r76`

Remote:
- `No remote branches point at HEAD`

### Local-only references

Stashes:
- `stash@{0}: On codex/merge-main-hf8: codex-merge-main-hf8-before-align-to-main-2026-04-10`
- `stash@{1}: On main: codex-pre-main-merge-runtime-artifacts-2026-04-10`

Worktrees:
- `C:/Users/User/Desktop/pneumo2_R31CN_HF8_github_push_package 7cfa972 [codex/desktop-animator-cinematic-pass-r76]`
- `C:/Users/User/Desktop/pneumo2_R31CN_HF8_main_integration    2dd4d80 (detached HEAD)`

Portable sibling entries:
- `C:\Users\User\Desktop\pneumo2_R31CN_HF8_github_push_package\local_portable_release\PneumoApp_R31CN_HF8_portable_20260410`
- `C:\Users\User\Desktop\pneumo2_R31CN_HF8_github_push_package\local_portable_release\PneumoApp_R31CN_HF8_portable_20260410.zip`
- `C:\Users\User\Desktop\pneumo2_R31CN_HF8_github_push_package\local_portable_release\PneumoApp_R31CN_HF8_portable_20260410.zip.manifest.json`

## What GitHub syncs

- All tracked repository files, including `docs/context/*`.
- The generated handoff files: `docs/context/CODEX_HANDOFF_LATEST.md` and `docs/context/CODEX_HANDOFF_LATEST.json`.
- Existing long-lived context artifacts already committed in this repository.

## Refresh tools

- Quick save command: `pneumo2_R31CN_HF8_repo_root/SAVE_CODEX_CONTEXT_TO_GITHUB.cmd`
- Handoff writer: `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/write_codex_handoff.py`
- Contract test: `pneumo2_R31CN_HF8_repo_root/tests/test_codex_github_handoff_contract.py`

## What GitHub does not sync

- `live Codex chat thread state`
- `git stashes and local worktrees themselves`
- `.venv virtual environment`
- `local_portable_release/ unless explicitly added to git`

## Open these first on another machine

- `docs/context/CODEX_GITHUB_SYNC.md`
- `docs/context/CODEX_HANDOFF_LATEST.md`

## Tracked context inventory

- `pneumo2_R31CN_HF8_repo_root/docs/context/AI_SNAPSHOT_WORKING_DELTA_2026-04-08.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_GITHUB_SYNC.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_HANDOFF_LATEST.json`
- `pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_HANDOFF_LATEST.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/PROJECT_CONTEXT_ANALYSIS.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/PROJECT_CONTEXT_ANALYSIS_v2.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/WISHLIST.json`
- `pneumo2_R31CN_HF8_repo_root/docs/context/WISHLIST.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/WISHLIST_v2.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/context_pn_main_chat.txt`

## Derived context docs

- `pneumo2_R31CN_HF8_repo_root/docs/01_RequirementsFromContext.json`
- `pneumo2_R31CN_HF8_repo_root/docs/01_RequirementsFromContext.md`
- `pneumo2_R31CN_HF8_repo_root/docs/01_RequirementsFromContext_RAW.md`

## Update workflow

1. Open the project root recorded above.
2. Run `pneumo2_R31CN_HF8_repo_root/SAVE_CODEX_CONTEXT_TO_GITHUB.cmd`.
3. Review `docs/context/CODEX_HANDOFF_LATEST.md`.
4. Run `pneumo2_R31CN_HF8_repo_root/tests/test_codex_github_handoff_contract.py`.
5. Commit and push the refreshed context together with the code changes you want to preserve.

## Continue on another machine

1. `git pull` the target branch.
2. Open `docs/context/CODEX_HANDOFF_LATEST.md` and `docs/context/CODEX_GITHUB_SYNC.md` first.
3. Recreate `.venv` if needed, because environments do not move through Git.
4. Treat stash/worktree lines in this file as references only; they are not transferred automatically.
5. Resume from the branch recorded above, usually with a prompt like: `Read pneumo2_R31CN_HF8_repo_root/docs/context/CODEX_HANDOFF_LATEST.md and continue from the saved branch.`

