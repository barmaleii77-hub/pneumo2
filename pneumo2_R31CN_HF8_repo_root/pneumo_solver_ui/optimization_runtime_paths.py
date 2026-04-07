from __future__ import annotations

"""Path-budget and launcher helpers for optimization runtime.

Why:
- Windows runs were launched from source-style release folders with very long
  names. Combined with staged optimization subdirectories this pushed live CSV
  and progress paths beyond a safe MAX_PATH budget.
- Background optimization workers are non-GUI processes and must use
  ``python.exe`` instead of ``pythonw.exe``. Using ``pythonw.exe`` hides
  stderr/stdout and makes failures look like hangs.
"""

from pathlib import Path
import hashlib
from typing import Optional

from pneumo_solver_ui.name_sanitize import sanitize_id


def console_python_executable(executable: str | Path | None = None) -> str:
    """Return a console-friendly Python interpreter for worker processes.

    On Windows, Streamlit may itself be started from ``pythonw.exe``. That is
    acceptable for the GUI shell, but not for long-running background workers
    that need deterministic multiprocessing and log capture.
    """
    raw = str(executable) if executable is not None else ''
    try:
        p = Path(raw) if raw else Path()
    except Exception:
        return raw
    name = p.name.lower()
    if name == 'pythonw.exe':
        cand = p.with_name('python.exe')
        if cand.exists():
            return str(cand)
    if name == 'python.exe':
        return str(p)
    # If no explicit path is known, just return the original string.
    return raw or str(p)


def normalized_opt_run_id(run_id: str | None, *, max_len: int = 16) -> str:
    raw = sanitize_id(run_id or 'run') or 'run'
    raw = raw.strip('_') or 'run'
    return raw[:max_len] or 'run'


def _compact_problem_token(problem_hash: str | None, *, max_len: int = 12) -> str:
    raw = str(problem_hash or '').strip() or 'noprob'
    raw = sanitize_id(raw) or 'noprob'
    if len(raw) <= max_len:
        return raw
    digest = hashlib.blake2s(raw.encode('utf-8'), digest_size=4).hexdigest()[:6]
    head_len = max(1, max_len - len(digest) - 1)
    return f"{raw[:head_len]}_{digest}"[:max_len]


def build_optimization_run_dir(workspace_dir: Path, run_id: str | None, problem_hash: str | None) -> Path:
    rid = normalized_opt_run_id(run_id)
    ph = _compact_problem_token(problem_hash, max_len=12)
    return Path(workspace_dir) / 'opt_runs' / rid / f'p_{ph}'


def staged_progress_path(run_dir: Path) -> Path:
    return Path(run_dir) / 'sp.json'


def stage_fs_name(stage_idx: int, stage_name: str | None = None) -> str:
    try:
        idx = int(stage_idx)
    except Exception:
        idx = 0
    return f's{idx}'


def stage_out_csv_name(stage_idx: int) -> str:
    return f'o{int(stage_idx):d}.csv'


def stage_worker_progress_path(stage_out_csv: Path) -> Path:
    stem = Path(stage_out_csv).stem
    return Path(stage_out_csv).with_name(f'{stem}_progress.json')


__all__ = [
    'console_python_executable',
    'normalized_opt_run_id',
    '_compact_problem_token',
    'build_optimization_run_dir',
    'staged_progress_path',
    'stage_fs_name',
    'stage_out_csv_name',
    'stage_worker_progress_path',
]
