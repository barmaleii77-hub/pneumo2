from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.tools.write_codex_handoff import (
    collect_handoff_snapshot,
    render_handoff_markdown,
)

ROOT = Path(__file__).resolve().parents[1]


def test_codex_handoff_snapshot_tracks_context_and_unsynced_references() -> None:
    snapshot = collect_handoff_snapshot(ROOT)

    assert Path(snapshot["repo_root"]) == ROOT
    assert snapshot["branch"]
    assert len(snapshot["head_commit"]) == 40
    assert "docs/context/context_pn_main_chat.txt" in snapshot["synced_context_files"]
    assert "docs/context/PROJECT_CONTEXT_ANALYSIS_v2.md" in snapshot["synced_context_files"]

    rendered = render_handoff_markdown(snapshot)
    assert "live Codex chat thread state" in rendered
    assert "../local_portable_release/" in rendered
    assert "docs/context/CODEX_HANDOFF_LATEST.md" in rendered
