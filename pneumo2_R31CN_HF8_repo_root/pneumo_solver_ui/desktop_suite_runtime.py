from __future__ import annotations

"""Small runtime facade for the WS-SUITE validated snapshot handoff."""

import json
from pathlib import Path
from typing import Any, Mapping

from pneumo_solver_ui.desktop_input_model import repo_root as desktop_repo_root
from pneumo_solver_ui.desktop_suite_snapshot import (
    VALIDATED_SUITE_SNAPSHOT_FILENAME,
    describe_suite_snapshot_state,
)


def _repo_root(repo_root: Path | str | None = None) -> Path:
    return Path(repo_root).resolve() if repo_root is not None else desktop_repo_root()


def _workspace_dir(
    *,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    if workspace_dir is not None:
        return Path(workspace_dir).resolve()
    return (_repo_root(repo_root) / "workspace").resolve()


def desktop_suite_handoff_path(
    *,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    return (
        _workspace_dir(workspace_dir=workspace_dir, repo_root=repo_root)
        / "handoffs"
        / "WS-SUITE"
        / VALIDATED_SUITE_SNAPSHOT_FILENAME
    ).resolve()


def desktop_suite_handoff_dir(
    *,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    return desktop_suite_handoff_path(workspace_dir=workspace_dir, repo_root=repo_root).parent


def _read_json_object(path: Path | str) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return dict(raw) if isinstance(raw, Mapping) else {}


def read_desktop_suite_handoff_state(
    *,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
    current_inputs_snapshot_hash: str = "",
    current_ring_source_hash: str = "",
    current_suite_snapshot_hash: str = "",
) -> dict[str, Any]:
    target = desktop_suite_handoff_path(workspace_dir=workspace_dir, repo_root=repo_root)
    if not target.exists():
        return {
            "path": str(target),
            **describe_suite_snapshot_state(None),
        }
    try:
        snapshot = _read_json_object(target)
    except Exception as exc:
        return {
            "path": str(target),
            "state": "invalid",
            "is_stale": True,
            "handoff_ready": False,
            "stale_reasons": ["unreadable_validated_suite_snapshot"],
            "banner": f"validated_suite_snapshot не читается: {exc}",
        }
    return {
        "path": str(target),
        "suite_snapshot_hash": str(snapshot.get("suite_snapshot_hash") or ""),
        "preview": dict(snapshot.get("preview") or {}),
        "validation": dict(snapshot.get("validation") or {}),
        **describe_suite_snapshot_state(
            snapshot,
            current_inputs_snapshot_hash=current_inputs_snapshot_hash,
            current_ring_source_hash=current_ring_source_hash,
            current_suite_snapshot_hash=current_suite_snapshot_hash,
        ),
    }


__all__ = [
    "desktop_suite_handoff_dir",
    "desktop_suite_handoff_path",
    "read_desktop_suite_handoff_state",
]
