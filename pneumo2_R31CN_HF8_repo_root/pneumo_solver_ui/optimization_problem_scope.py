from __future__ import annotations

from pathlib import Path


def problem_hash_artifact_path(run_dir: Path | str) -> Path:
    return Path(run_dir) / "problem_hash.txt"


def read_problem_hash_artifact(run_dir: Path | str) -> str:
    path = problem_hash_artifact_path(run_dir)
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def problem_hash_short_label(problem_hash: str | None, *, max_len: int = 12) -> str:
    value = str(problem_hash or "").strip()
    if not value:
        return ""
    return value if len(value) <= max_len else value[:max_len]


__all__ = [
    "problem_hash_artifact_path",
    "problem_hash_short_label",
    "read_problem_hash_artifact",
]
