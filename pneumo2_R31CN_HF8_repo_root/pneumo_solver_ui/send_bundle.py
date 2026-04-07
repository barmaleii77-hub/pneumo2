"""Send-bundle (полная диагностика)

Единая точка для сборки *полного* диагностического архива (ZIP).

Зачем это нужно:
- Пользователь требует ОДНУ кнопку/механизм для сохранения ВСЕЙ диагностики.
- Автосохранение диагностики при краше также должно собирать тот же полный ZIP.

В проекте реальная реализация находится в `pneumo_solver_ui/tools/make_send_bundle.py`.
Этот модуль — стабильный API-слой, чтобы другие части приложения импортировали
`pneumo_solver_ui.send_bundle` и не зависели от внутренней структуры tools/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union, Tuple

from .tools.make_send_bundle import make_send_bundle as _make_send_bundle

PathLike = Union[str, Path]


def make_send_bundle(
    repo_root: PathLike,
    out_dir: Optional[PathLike] = None,
    keep_last_n: int = 50,
    max_file_mb: int = 80,
    include_workspace_osc: bool = True,
    primary_session_dir: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
    tag: Optional[str] = None,
    operator_note: Optional[str] = None,
) -> Path:
    """Собрать полный диагностический ZIP.

    Параметры:
    - repo_root: корень проекта (папка приложения).
    - out_dir: куда сохранять ZIP (по умолчанию <project_root>/send_bundles).
    - keep_last_n: сколько последних ZIP хранить (остальные удаляются).
    - max_file_mb: лимит размера отдельного файла внутри ZIP.
    - include_workspace_osc: включать экспорт Workspace OSC (если доступно).
    - primary_session_dir: активная сессия (если известна) — для дедупликации.
    - project_root: если отличается от repo_root (обычно не нужно).

    Возвращает:
    - путь к ZIP.
    """
    root = Path(project_root) if project_root is not None else Path(repo_root)
    # R59: canonical output folder name is `send_bundles` (lowercase).
    # Windows is case-insensitive, but Linux/macOS are not — keep it stable.
    out_dir_path = Path(out_dir) if out_dir is not None else (root / "send_bundles")
    out_dir_path.mkdir(parents=True, exist_ok=True)

    # NOTE: `tag` is optional; the underlying bundler will sanitize it.

    return _make_send_bundle(
        Path(repo_root),
        out_dir=out_dir_path,
        keep_last_n=keep_last_n,
        max_file_mb=max_file_mb,
        include_workspace_osc=include_workspace_osc,
        primary_session_dir=(Path(primary_session_dir) if primary_session_dir is not None else None),
        project_root=root,
        tag=tag,
        operator_note=operator_note,
    )


def make_send_bundle_bytes(
    repo_root: PathLike,
    out_dir: Optional[PathLike] = None,
    keep_last_n: int = 50,
    max_file_mb: int = 80,
    include_workspace_osc: bool = True,
    primary_session_dir: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
    tag: Optional[str] = None,
    operator_note: Optional[str] = None,
) -> Tuple[bytes, str]:
    """Собрать полный диагностический ZIP и вернуть (bytes, filename)."""
    p = make_send_bundle(
        repo_root=repo_root,
        out_dir=out_dir,
        tag=tag,
        operator_note=operator_note,
        keep_last_n=keep_last_n,
        max_file_mb=max_file_mb,
        include_workspace_osc=include_workspace_osc,
        primary_session_dir=primary_session_dir,
        project_root=project_root,
    )
    return p.read_bytes(), p.name
