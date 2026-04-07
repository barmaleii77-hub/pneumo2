from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKTREE_ROOT = PROJECT_ROOT.parent


def test_gitignore_covers_local_runtime_noise() -> None:
    text = WORKTREE_ROOT.joinpath(".gitignore").read_text(encoding="utf-8")

    assert "*_repo_root.zip" in text
    assert "pneumo2_R31CN_HF8_repo_root/.venv/" in text
    assert "pneumo2_R31CN_HF8_repo_root/**/__pycache__/" in text
    assert "pneumo2_R31CN_HF8_repo_root/workspace/" in text
    assert "pneumo2_R31CN_HF8_repo_root/runs/ui_sessions/" in text
    assert "pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/logs/*" in text
    assert "!pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/logs/.keep" in text
    assert "pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/workspace/" in text
    assert "pneumo2_R31CN_HF8_repo_root/runs/index.json" in text
    assert "pneumo2_R31CN_HF8_repo_root/runs/run_registry.jsonl" in text


def test_gitattributes_normalizes_cross_platform_text_and_binary_files() -> None:
    text = WORKTREE_ROOT.joinpath(".gitattributes").read_text(encoding="utf-8")

    assert "*.py text eol=lf" in text
    assert "*.cmd text eol=crlf" in text
    assert "*.zip binary" in text
    assert "*.bundle binary" in text


def test_python_version_is_pinned_for_workspace_and_project_root() -> None:
    workspace_version = WORKTREE_ROOT.joinpath(".python-version").read_text(encoding="utf-8").strip()
    project_version = PROJECT_ROOT.joinpath(".python-version").read_text(encoding="utf-8").strip()

    assert workspace_version == "3.14.3"
    assert project_version == workspace_version
