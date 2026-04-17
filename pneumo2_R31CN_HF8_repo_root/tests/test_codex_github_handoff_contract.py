from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.tools.write_codex_handoff import (
    collect_handoff_snapshot,
    render_handoff_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
SYNC_DOC = ROOT / "docs" / "context" / "CODEX_GITHUB_SYNC.md"


def test_codex_handoff_snapshot_tracks_context_and_unsynced_references() -> None:
    snapshot = collect_handoff_snapshot(ROOT)

    assert Path(snapshot["project_root"]) == ROOT
    git_root = Path(snapshot["git_root"])
    assert git_root.exists()
    assert snapshot["project_root_from_git"] == "pneumo2_R31CN_HF8_repo_root"
    assert (git_root / snapshot["project_root_from_git"]).resolve() == ROOT
    assert snapshot["branch"]
    assert len(snapshot["head_commit"]) == 40
    assert "pneumo2_R31CN_HF8_repo_root/docs/context/context_pn_main_chat.txt" in snapshot["synced_context_files"]
    assert "pneumo2_R31CN_HF8_repo_root/docs/context/PROJECT_CONTEXT_ANALYSIS_v2.md" in snapshot["synced_context_files"]
    assert snapshot["quick_save_command"].endswith("SAVE_CODEX_CONTEXT_TO_GITHUB.cmd")
    assert snapshot["handoff_writer"].endswith("write_codex_handoff.py")
    assert snapshot["handoff_contract_test"].endswith("test_codex_github_handoff_contract.py")

    rendered = render_handoff_markdown(snapshot)
    assert "live Codex chat thread state" in rendered
    assert "local_portable_release/" in rendered
    assert "docs/context/CODEX_HANDOFF_LATEST.md" in rendered
    assert "## Update workflow" in rendered
    assert "## Continue on another machine" in rendered
    assert snapshot["resume_prompt"] in rendered


def test_codex_github_sync_doc_describes_update_and_continue_workflow() -> None:
    sync_text = SYNC_DOC.read_text(encoding="utf-8")

    for needle in (
        "## Update Workflow",
        "## Continue Workflow",
        "SAVE_CODEX_CONTEXT_TO_GITHUB.cmd",
        "test_codex_github_handoff_contract.py",
        "CODEX_HANDOFF_LATEST.md",
    ):
        assert needle in sync_text
