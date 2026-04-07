# -*- coding: utf-8 -*-
"""Helpers to resolve project-local Python module paths safely.

Why this exists
---------------
Streamlit widget state and autosave bundles may preserve absolute file paths from an
older unpacked release tree (for example inside Downloads on Windows). When a new
release is unpacked into another folder, those stale absolute paths break module
loading even though the required file exists in the current release.

ABSOLUTE LAW notes
------------------
- We do **not** invent new module names.
- We only recover from the specific case "same filename, wrong/stale root".
- If the requested filename is different and no exact file exists, we fail loudly.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple


def resolve_project_py_path(
    requested: str | Path,
    *,
    here: str | Path,
    kind: str,
    default_path: str | Path | None = None,
) -> Tuple[Path, List[str]]:
    """Resolve a Python file path for the current release tree.

    Rules:
    1) Exact existing path wins.
    2) If the exact path is missing but a file with the *same basename* exists
       inside the current release directory, use that local file and return a warning.
    3) If requested is empty (or only names the canonical default file), and
       *default_path* exists, use *default_path* with a warning.
    4) Otherwise raise ``FileNotFoundError`` with a human-readable explanation.
    """

    warnings: List[str] = []
    base_dir = Path(here).expanduser().resolve()
    req_str = str(requested or '').strip()
    req = Path(req_str).expanduser()

    try:
        if req.is_file():
            return req.resolve(), warnings
    except Exception:
        pass

    # Important: stale paths can come from Windows widgets/autosave even when the
    # current runtime is POSIX. Path(...).name on POSIX would keep the full string,
    # so we normalize separators manually.
    req_name = req_str.replace('\\', '/').rstrip('/').split('/')[-1].strip()
    if req_name:
        local_same_name = (base_dir / req_name).resolve()
        if local_same_name.is_file():
            warnings.append(
                f"Путь к {kind} не найден: '{req}'. Найден одноимённый файл в текущем релизе: "
                f"'{local_same_name}'. Использую локальную копию текущего релиза."
            )
            return local_same_name, warnings

    default_resolved = None
    default_name = ''
    if default_path is not None:
        default_p = Path(default_path).expanduser()
        default_resolved = default_p.resolve() if default_p.is_absolute() else (base_dir / default_p).resolve()
        default_name = default_resolved.name

    if default_resolved is not None and default_resolved.is_file() and (not req_name or req_name == default_name):
        warnings.append(
            f"Путь к {kind} не найден: '{req}'. Использую канонический файл текущего релиза: "
            f"'{default_resolved}'."
        )
        return default_resolved, warnings

    hint = ''
    if req_name:
        local_hint = (base_dir / req_name).resolve()
        hint = f" Проверьте путь или поместите файл в текущий релиз: '{local_hint}'."
    elif default_resolved is not None:
        hint = f" Канонический файл текущего релиза: '{default_resolved}'."

    raise FileNotFoundError(f"Не найден файл для роли '{kind}': '{req}'.{hint}")
