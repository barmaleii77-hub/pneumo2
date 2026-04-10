from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


def normalize_problem_hash_mode(value: object, *, default: str = "stable") -> str:
    mode = str(value or "").strip().lower()
    if mode in {"stable", "legacy"}:
        return mode
    fallback = str(default or "").strip().lower()
    if fallback in {"stable", "legacy"}:
        return fallback
    return ""


def problem_hash_mode_from_env(
    env: Mapping[str, str] | None = None,
    *,
    default: str = "stable",
) -> str:
    source = env if env is not None else os.environ
    try:
        raw = source.get("PNEUMO_OPT_PROBLEM_HASH_MODE")
    except Exception:
        raw = None
    return normalize_problem_hash_mode(raw, default=default)


def problem_hash_mode_artifact_path(run_dir: Path | str) -> Path:
    return Path(run_dir) / "problem_hash_mode.txt"


def read_problem_hash_mode_artifact(run_dir: Path | str) -> str:
    path = problem_hash_mode_artifact_path(run_dir)
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    return normalize_problem_hash_mode(raw, default="")


def write_problem_hash_mode_artifact(run_dir: Path | str, mode: object) -> Path:
    path = problem_hash_mode_artifact_path(run_dir)
    normalized = normalize_problem_hash_mode(mode, default="")
    if not normalized:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8")
    return path


__all__ = [
    "normalize_problem_hash_mode",
    "problem_hash_mode_artifact_path",
    "problem_hash_mode_from_env",
    "read_problem_hash_mode_artifact",
    "write_problem_hash_mode_artifact",
]
