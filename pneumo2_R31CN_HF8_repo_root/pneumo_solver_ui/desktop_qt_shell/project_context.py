from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

from pneumo_solver_ui.project_state import (
    ensure_project_dirs,
    get_project_paths,
    read_current_project,
    sanitize_project_name,
)
from pneumo_solver_ui.workspace_contract import (
    missing_workspace_contract_dirs,
    resolve_effective_workspace_dir,
)


@dataclass(frozen=True)
class ShellProjectContext:
    repo_root: Path
    workspace_dir: Path
    state_root: Path
    project_name: str
    project_dir: Path
    workspace_source: str
    missing_workspace_dirs: tuple[str, ...]

    @property
    def workspace_ready(self) -> bool:
        return not self.missing_workspace_dirs

    @property
    def readiness_label(self) -> str:
        if self.workspace_ready:
            return "Рабочая папка готова"
        missing = ", ".join(self.missing_workspace_dirs)
        return f"Нужно подготовить папки: {missing}"


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_shell_project_context(
    *,
    repo_root: Path | str | None = None,
    env: Mapping[str, str] | None = None,
) -> ShellProjectContext:
    repo = Path(repo_root).expanduser().resolve() if repo_root is not None else _default_repo_root()
    env_map = dict(os.environ if env is None else env)
    workspace_dir = resolve_effective_workspace_dir(repo, env=env_map)
    workspace_source = "PNEUMO_WORKSPACE_DIR" if str(env_map.get("PNEUMO_WORKSPACE_DIR") or "").strip() else "repo_local"
    state_root = workspace_dir / "ui_state"
    env_project = str(env_map.get("PNEUMO_PROJECT") or "").strip()
    project_name = sanitize_project_name(env_project) if env_project else read_current_project(state_root)
    project_paths = get_project_paths(state_root, project_name)
    ensure_project_dirs(project_paths)
    missing_dirs = tuple(missing_workspace_contract_dirs(workspace_dir, include_optional=False))
    return ShellProjectContext(
        repo_root=repo,
        workspace_dir=workspace_dir,
        state_root=state_root,
        project_name=project_name,
        project_dir=project_paths.project_dir,
        workspace_source=workspace_source,
        missing_workspace_dirs=missing_dirs,
    )
