#!/usr/bin/env python3
"""Write a Git-tracked Codex handoff snapshot for cross-machine continuation."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _run_git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _run_git_lines(repo_root: Path, *args: str) -> list[str]:
    output = _run_git(repo_root, *args)
    return [line.rstrip() for line in output.splitlines() if line.strip()]


def _git_toplevel(repo_root: Path) -> Path:
    output = _run_git(repo_root, "rev-parse", "--show-toplevel")
    if output:
        return Path(output).resolve()
    return repo_root.resolve()


def _repo_rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _list_relative_files(base_dir: Path, repo_root: Path) -> list[str]:
    if not base_dir.exists():
        return []
    return sorted(
        _repo_rel(path, repo_root)
        for path in base_dir.rglob("*")
        if path.is_file() and path.name.lower() != "desktop.ini"
    )


def _list_portable_entries(git_root: Path) -> list[str]:
    portable_root = git_root / "local_portable_release"
    if not portable_root.exists():
        return []
    return sorted(str(path.resolve()) for path in portable_root.iterdir())


def _branches_at_head(repo_root: Path, head_commit: str) -> tuple[list[str], list[str]]:
    refs = _run_git_lines(
        repo_root,
        "for-each-ref",
        "--format=%(refname:short) %(objectname)",
        "refs/heads",
        "refs/remotes/origin",
    )
    local: list[str] = []
    remote: list[str] = []
    for line in refs:
        try:
            ref_name, object_name = line.rsplit(" ", 1)
        except ValueError:
            continue
        if object_name != head_commit:
            continue
        if ref_name in {"origin", "origin/HEAD"}:
            continue
        if ref_name.startswith("origin/"):
            remote.append(ref_name)
        else:
            local.append(ref_name)
    return sorted(local), sorted(remote)


def _parse_divergence(raw_counts: str) -> tuple[int, int]:
    if not raw_counts:
        return 0, 0
    parts = raw_counts.split()
    if len(parts) != 2:
        return 0, 0
    try:
        ahead = int(parts[1])
        behind = int(parts[0])
    except ValueError:
        return 0, 0
    return ahead, behind


def collect_handoff_snapshot(repo_root: Path, notes: list[str] | None = None) -> dict[str, Any]:
    project_root = repo_root.resolve()
    git_root = _git_toplevel(project_root)
    head_commit = _run_git(git_root, "rev-parse", "HEAD")
    upstream = _run_git(git_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    divergence = _run_git(git_root, "rev-list", "--left-right", "--count", "HEAD...@{u}") if upstream else ""
    ahead, behind = _parse_divergence(divergence)
    local_at_head, remote_at_head = _branches_at_head(git_root, head_commit)

    context_files = _list_relative_files(project_root / "docs" / "context", git_root)
    derived_context_docs = sorted(
        _repo_rel(path, git_root)
        for path in (project_root / "docs").glob("*RequirementsFromContext*")
        if path.is_file()
    )
    handoff_writer = _repo_rel(project_root / "pneumo_solver_ui" / "tools" / "write_codex_handoff.py", git_root)
    quick_save_command = _repo_rel(project_root / "SAVE_CODEX_CONTEXT_TO_GITHUB.cmd", git_root)
    handoff_contract_test = _repo_rel(project_root / "tests" / "test_codex_github_handoff_contract.py", git_root)
    project_root_from_git = _repo_rel(project_root, git_root)

    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "git_root": str(git_root),
        "project_root": str(project_root),
        "project_root_from_git": project_root_from_git,
        "origin_url": _run_git(git_root, "remote", "get-url", "origin"),
        "branch": _run_git(git_root, "rev-parse", "--abbrev-ref", "HEAD"),
        "head_commit": head_commit,
        "head_short": head_commit[:7] if head_commit else "",
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "status_lines": _run_git_lines(git_root, "status", "--short", "--branch"),
        "recent_commits": _run_git_lines(git_root, "log", "--oneline", "-10"),
        "stash_lines": _run_git_lines(git_root, "stash", "list", "--max-count=10"),
        "worktree_lines": _run_git_lines(git_root, "worktree", "list"),
        "local_branches_at_head": local_at_head,
        "remote_branches_at_head": remote_at_head,
        "synced_context_files": context_files,
        "derived_context_docs": derived_context_docs,
        "portable_entries": _list_portable_entries(git_root),
        "handoff_writer": handoff_writer,
        "quick_save_command": quick_save_command,
        "handoff_contract_test": handoff_contract_test,
        "resume_prompt": f"Read {project_root_from_git}/docs/context/CODEX_HANDOFF_LATEST.md and continue from the saved branch.",
        "not_synced_items": [
            "live Codex chat thread state",
            "git stashes and local worktrees themselves",
            ".venv virtual environment",
            "local_portable_release/ unless explicitly added to git",
        ],
        "notes": list(notes or []),
    }


def render_handoff_markdown(snapshot: dict[str, Any]) -> str:
    notes = snapshot.get("notes") or ["No manual notes recorded for this snapshot."]
    status_lines = snapshot.get("status_lines") or ["git status returned no lines"]
    recent_commits = snapshot.get("recent_commits") or ["No commits found"]
    stash_lines = snapshot.get("stash_lines") or ["No stashes recorded"]
    worktree_lines = snapshot.get("worktree_lines") or ["No worktrees recorded"]
    local_branches = snapshot.get("local_branches_at_head") or ["No local branches point at HEAD"]
    remote_branches = snapshot.get("remote_branches_at_head") or ["No remote branches point at HEAD"]
    context_files = snapshot.get("synced_context_files") or ["docs/context is missing"]
    derived_docs = snapshot.get("derived_context_docs") or ["No derived requirements docs found"]
    portable_entries = snapshot.get("portable_entries") or ["No sibling local_portable_release directory found"]

    starter_paths = [
        "docs/context/CODEX_GITHUB_SYNC.md",
        "docs/context/CODEX_HANDOFF_LATEST.md",
        "docs/context/AI_SNAPSHOT_WORKING_DELTA_2026-04-08.md",
        "docs/context/PROJECT_CONTEXT_ANALYSIS_v2.md",
        "docs/context/WISHLIST.json",
        "docs/context/context_pn_main_chat.txt",
    ]
    preferred_paths = [path for path in starter_paths if path in context_files or path == "docs/context/CODEX_HANDOFF_LATEST.md" or path == "docs/context/CODEX_GITHUB_SYNC.md"]

    lines: list[str] = []
    lines.append("# Codex Handoff Latest")
    lines.append("")
    lines.append(f"Generated: `{snapshot.get('generated_at', '')}`")
    lines.append(f"Git root: `{snapshot.get('git_root', '')}`")
    lines.append(f"Project root: `{snapshot.get('project_root', '')}`")
    lines.append(f"Project root from git: `{snapshot.get('project_root_from_git', '')}`")
    lines.append(f"Origin: `{snapshot.get('origin_url', '')}`")
    lines.append("")
    lines.append("## Current Git state")
    lines.append("")
    lines.append(f"- Branch: `{snapshot.get('branch', '')}`")
    lines.append(f"- HEAD: `{snapshot.get('head_short', '')}` (`{snapshot.get('head_commit', '')}`)")
    if snapshot.get("upstream"):
        lines.append(f"- Upstream: `{snapshot['upstream']}`")
        lines.append(f"- Ahead/behind upstream: `{snapshot.get('ahead', 0)}/{snapshot.get('behind', 0)}`")
    lines.append("")
    lines.append("### Manual notes")
    lines.append("")
    for note in notes:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("### Status")
    lines.append("")
    for line in status_lines:
        lines.append(f"- `{line}`")
    lines.append("")
    lines.append("### Recent commits")
    lines.append("")
    for line in recent_commits:
        lines.append(f"- `{line}`")
    lines.append("")
    lines.append("### Branches already at this HEAD")
    lines.append("")
    lines.append("Local:")
    for line in local_branches:
        lines.append(f"- `{line}`")
    lines.append("")
    lines.append("Remote:")
    for line in remote_branches:
        lines.append(f"- `{line}`")
    lines.append("")
    lines.append("### Local-only references")
    lines.append("")
    lines.append("Stashes:")
    for line in stash_lines:
        lines.append(f"- `{line}`")
    lines.append("")
    lines.append("Worktrees:")
    for line in worktree_lines:
        lines.append(f"- `{line}`")
    lines.append("")
    lines.append("Portable sibling entries:")
    for line in portable_entries:
        lines.append(f"- `{line}`")
    lines.append("")
    lines.append("## What GitHub syncs")
    lines.append("")
    lines.append("- All tracked repository files, including `docs/context/*`.")
    lines.append("- The generated handoff files: `docs/context/CODEX_HANDOFF_LATEST.md` and `docs/context/CODEX_HANDOFF_LATEST.json`.")
    lines.append("- Existing long-lived context artifacts already committed in this repository.")
    lines.append("")
    lines.append("## Refresh tools")
    lines.append("")
    lines.append(f"- Quick save command: `{snapshot.get('quick_save_command', '')}`")
    lines.append(f"- Handoff writer: `{snapshot.get('handoff_writer', '')}`")
    lines.append(f"- Contract test: `{snapshot.get('handoff_contract_test', '')}`")
    lines.append("")
    lines.append("## What GitHub does not sync")
    lines.append("")
    for item in snapshot.get("not_synced_items", []):
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("## Open these first on another machine")
    lines.append("")
    for path in preferred_paths:
        lines.append(f"- `{path}`")
    lines.append("")
    lines.append("## Tracked context inventory")
    lines.append("")
    for path in context_files:
        lines.append(f"- `{path}`")
    lines.append("")
    lines.append("## Derived context docs")
    lines.append("")
    for path in derived_docs:
        lines.append(f"- `{path}`")
    lines.append("")
    lines.append("## Update workflow")
    lines.append("")
    lines.append("1. Open the project root recorded above.")
    lines.append(f"2. Run `{snapshot.get('quick_save_command', '')}`.")
    lines.append("3. Review `docs/context/CODEX_HANDOFF_LATEST.md`.")
    lines.append(f"4. Run `{snapshot.get('handoff_contract_test', '')}`.")
    lines.append("5. Commit and push the refreshed context together with the code changes you want to preserve.")
    lines.append("")
    lines.append("## Continue on another machine")
    lines.append("")
    lines.append("1. `git pull` the target branch.")
    lines.append("2. Open `docs/context/CODEX_HANDOFF_LATEST.md` and `docs/context/CODEX_GITHUB_SYNC.md` first.")
    lines.append("3. Recreate `.venv` if needed, because environments do not move through Git.")
    lines.append("4. Treat stash/worktree lines in this file as references only; they are not transferred automatically.")
    lines.append(f"5. Resume from the branch recorded above, usually with a prompt like: `{snapshot.get('resume_prompt', '')}`")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_handoff_files(
    repo_root: Path,
    out_md: str = "docs/context/CODEX_HANDOFF_LATEST.md",
    out_json: str = "docs/context/CODEX_HANDOFF_LATEST.json",
    notes: list[str] | None = None,
) -> tuple[Path, Path]:
    snapshot = collect_handoff_snapshot(repo_root, notes=notes)
    md_path = (repo_root / out_md).resolve()
    json_path = (repo_root / out_json).resolve()
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_handoff_markdown(snapshot), encoding="utf-8")
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a Git-tracked Codex handoff snapshot.")
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect.")
    parser.add_argument("--out-md", default="docs/context/CODEX_HANDOFF_LATEST.md")
    parser.add_argument("--out-json", default="docs/context/CODEX_HANDOFF_LATEST.json")
    parser.add_argument(
        "--note",
        action="append",
        default=[],
        help="Optional note line to include in the handoff snapshot. Can be passed more than once.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    md_path, json_path = write_handoff_files(
        repo_root=repo_root,
        out_md=args.out_md,
        out_json=args.out_json,
        notes=args.note,
    )
    print(f"Wrote: {md_path}")
    print(f"Wrote: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
