# -*- coding: utf-8 -*-
"""Helpers for loading Python modules from file paths under the project tree.

Absolute-law intent:
- no runtime compatibility aliases for parameter names;
- but dynamic module loading must preserve the *real* package context,
  otherwise relative imports inside canonical project modules break.

Main fixes:
- derive canonical dotted module name for files that physically live inside
  an actual Python package (e.g. ``pneumo_solver_ui.model_x``);
- register the module in ``sys.modules`` before execution;
- add the package import root and the file parent to ``sys.path`` so that
  both relative imports and explicit sibling imports continue to work.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

LogFn = Callable[..., None]


# Lightweight module cache to avoid re-importing heavy model/worker modules on every
# Streamlit rerun when the source file has not changed. This keeps relative imports
# correct (canonical resolved_name is still used) while preventing repeated optional-
# dependency import churn.
_MODULE_CACHE: Dict[str, Tuple[str, Tuple[int, int], Any]] = {}


def _file_signature(path: Path) -> Tuple[int, int]:
    st = Path(path).stat()
    return int(getattr(st, 'st_mtime_ns', int(st.st_mtime * 1e9))), int(st.st_size)


def _sanitize_module_name(name: str) -> str:
    raw_parts = [p for p in str(name).split('.') if str(p).strip()]
    if not raw_parts:
        return 'dynamic_module'
    out: list[str] = []
    for raw in raw_parts:
        part = re.sub(r'[^0-9A-Za-z_]+', '_', str(raw).strip())
        if not part:
            part = 'module'
        if part[0].isdigit():
            part = f'm_{part}'
        out.append(part)
    return '.'.join(out) if out else 'dynamic_module'


def _package_chain(path: Path) -> list[Path]:
    """Return package directories from top-level package to file parent.

    Example:
        /repo/pneumo_solver_ui/pneumo_dist/eval_core.py
        -> [ /repo/pneumo_solver_ui, /repo/pneumo_solver_ui/pneumo_dist ]

    Non-package folders (without ``__init__.py``) stop the chain.
    """
    p = Path(path).resolve()
    dirs: list[Path] = []
    cur = p.parent
    while (cur / '__init__.py').exists():
        dirs.append(cur)
        cur = cur.parent
    dirs.reverse()
    return dirs


def canonical_dynamic_module_name(path: Path, fallback_name: Optional[str] = None) -> str:
    p = Path(path).resolve()
    chain = _package_chain(p)
    if chain:
        names = [d.name for d in chain]
        if p.name != '__init__.py':
            names.append(p.stem)
        return '.'.join(names)
    return _sanitize_module_name(fallback_name or p.stem)


def package_import_root(path: Path) -> Optional[Path]:
    chain = _package_chain(path)
    if not chain:
        return None
    return chain[0].parent.resolve()


def load_python_module_from_path(
    path: Path | str,
    module_name: Optional[str] = None,
    *,
    log: Optional[LogFn] = None,
    force_reload: bool = False,
):
    """Load a Python file as a module while preserving canonical package context.

    Parameters
    ----------
    path:
        File path to ``.py``.
    module_name:
        Requested/fallback module name. For files inside a real package the
        canonical dotted name wins (for example ``pneumo_solver_ui.model_x``),
        because relative imports depend on it.
    log:
        Optional callback compatible with ``log(event, message, **kw)``.
    """
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f'Python module file not found: {p}')

    requested_name = str(module_name or p.stem)
    resolved_name = canonical_dynamic_module_name(p, fallback_name=requested_name)

    import_root = package_import_root(p)
    path_candidates: list[Path] = []
    if import_root is not None:
        path_candidates.append(import_root)
    path_candidates.append(p.parent)

    for cand in path_candidates:
        cand_s = str(cand)
        if cand_s not in sys.path:
            sys.path.insert(0, cand_s)
            if log is not None:
                try:
                    log('SysPathInsert', cand_s, requested_name=requested_name, resolved_name=resolved_name, file=str(p))
                except Exception:
                    pass

    if resolved_name != requested_name and log is not None:
        try:
            log(
                'ModuleLoadCanonicalName',
                f'{requested_name} -> {resolved_name}',
                requested_name=requested_name,
                resolved_name=resolved_name,
                file=str(p),
            )
        except Exception:
            pass

    sig = _file_signature(p)
    cached = _MODULE_CACHE.get(resolved_name)
    if not force_reload and cached is not None:
        cached_path, cached_sig, cached_mod = cached
        if cached_path == str(p) and cached_sig == sig and sys.modules.get(resolved_name) is cached_mod:
            return cached_mod

    importlib.invalidate_caches()

    parent_pkg = resolved_name.rpartition('.')[0]
    if parent_pkg:
        try:
            importlib.import_module(parent_pkg)
        except Exception:
            # Non-fatal: spec/exec below may still succeed once sys.path is correct.
            pass

    kwargs: dict[str, Any] = {}
    if p.name == '__init__.py':
        kwargs['submodule_search_locations'] = [str(p.parent)]
    spec = importlib.util.spec_from_file_location(resolved_name, str(p), **kwargs)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Не удалось загрузить модуль из {p}')

    mod = importlib.util.module_from_spec(spec)
    sys.modules[resolved_name] = mod
    try:
        # Read source explicitly instead of delegating to SourceFileLoader.exec_module().
        # This keeps reloads truthful even when the file changes inside one-second timestamp
        # granularity windows or retains the same byte length (a common case during quick edits).
        source_bytes = p.read_bytes()
        code = compile(source_bytes, str(p), 'exec', dont_inherit=True)
        exec(code, mod.__dict__)
    except Exception:
        if sys.modules.get(resolved_name) is mod:
            sys.modules.pop(resolved_name, None)
        _MODULE_CACHE.pop(resolved_name, None)
        raise
    _MODULE_CACHE[resolved_name] = (str(p), sig, mod)
    return mod
