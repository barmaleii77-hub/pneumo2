from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from json import JSONDecoder
from pathlib import Path
from typing import Any

from pneumo_solver_ui.desktop_input_model import repo_root
from pneumo_solver_ui.desktop_suite_snapshot import (
    VALIDATED_SUITE_SNAPSHOT_FILENAME,
    VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION,
)


def desktop_run_setup_cache_root() -> Path:
    return (repo_root() / "workspace" / "cache" / "desktop_run_setup").resolve()


def desktop_run_setup_log_root() -> Path:
    return (repo_root() / "workspace" / "logs" / "desktop_run_setup").resolve()


def validated_suite_snapshot_handoff_dir(
    *,
    workspace_dir: Path | str | None = None,
) -> Path:
    workspace = Path(workspace_dir).resolve() if workspace_dir is not None else (repo_root() / "workspace").resolve()
    return (workspace / "handoffs" / "WS-SUITE").resolve()


def validated_suite_snapshot_handoff_path(
    *,
    workspace_dir: Path | str | None = None,
) -> Path:
    return (validated_suite_snapshot_handoff_dir(workspace_dir=workspace_dir) / VALIDATED_SUITE_SNAPSHOT_FILENAME).resolve()


def ensure_parent(path: Path) -> Path:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def stable_run_hash(payload: Any) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def desktop_single_run_cache_key(
    *,
    params: dict[str, Any],
    test_row: dict[str, Any],
    dt: float,
    t_end: float,
    record_full: bool,
    export_csv: bool,
    export_npz: bool,
    run_profile: str,
) -> str:
    normalized = {
        "params": params,
        "test_row": test_row,
        "dt": float(dt),
        "t_end": float(t_end),
        "record_full": bool(record_full),
        "export_csv": bool(export_csv),
        "export_npz": bool(export_npz),
        "run_profile": str(run_profile or "").strip(),
    }
    return stable_run_hash(normalized)


def build_selfcheck_subject_signature(
    *,
    payload: dict[str, Any],
    run_settings: dict[str, Any],
) -> str:
    normalized = {
        "payload": dict(payload or {}),
        "run_settings": dict(run_settings or {}),
    }
    return stable_run_hash(normalized)


def desktop_single_run_cache_dir(cache_key: str) -> Path:
    key = str(cache_key or "").strip() or "cache"
    return (desktop_run_setup_cache_root() / "single_run" / key).resolve()


def build_run_log_path(action_label: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(action_label or "desktop_run"))
    safe = "_".join(part for part in safe.split("_") if part) or "desktop_run"
    target = desktop_run_setup_log_root() / f"{stamp}_{safe}.log"
    return ensure_parent(target)


def append_subprocess_log(
    log_path: Path,
    *,
    title: str,
    cmd: list[str],
    returncode: int,
    stdout: str = "",
    stderr: str = "",
) -> Path:
    target = ensure_parent(log_path)
    lines = [
        f"[title] {title}",
        f"[cmd] {' '.join(str(part) for part in cmd)}",
        f"[returncode] {int(returncode)}",
    ]
    if stdout.strip():
        lines.append("[stdout]")
        lines.append(stdout.rstrip())
    if stderr.strip():
        lines.append("[stderr]")
        lines.append(stderr.rstrip())
    lines.append("")
    with target.open("a", encoding="utf-8", errors="replace") as fh:
        fh.write("\n".join(lines))
    return target


def extract_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    decoder = JSONDecoder()
    candidate: dict[str, Any] | None = None
    for idx, char in enumerate(raw):
        if char != "{":
            continue
        try:
            parsed, _end = decoder.raw_decode(raw[idx:])
        except Exception:
            continue
        if isinstance(parsed, dict):
            candidate = parsed
    return candidate


def write_json_report_from_stdout(stdout: str, report_path: Path) -> Path | None:
    parsed = extract_json_object(stdout)
    if parsed is None:
        return None
    target = ensure_parent(report_path)
    target.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def write_validated_suite_snapshot(
    snapshot: dict[str, Any],
    *,
    target_path: Path | str | None = None,
    workspace_dir: Path | str | None = None,
) -> Path:
    if str(dict(snapshot or {}).get("schema_version") or "") != VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("validated_suite_snapshot has unsupported schema_version")
    target = (
        Path(target_path).resolve()
        if target_path is not None
        else validated_suite_snapshot_handoff_path(workspace_dir=workspace_dir)
    )
    ensure_parent(target)
    target.write_text(json.dumps(dict(snapshot), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def read_validated_suite_snapshot(path: Path | str | None = None) -> dict[str, Any]:
    target = Path(path).resolve() if path is not None else validated_suite_snapshot_handoff_path()
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"validated_suite_snapshot must contain a JSON object: {target}")
    if str(raw.get("schema_version") or "") != VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported validated_suite_snapshot schema: {target}")
    return raw


def mirror_tree(src: Path, dst: Path) -> Path:
    source = Path(src).resolve()
    target = Path(dst).resolve()
    target.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        rel = path.relative_to(source)
        out = target / rel
        if path.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
    return target


def remap_saved_files_to_dir(
    saved_files: dict[str, Any] | None,
    outdir: Path,
) -> dict[str, str]:
    target_dir = Path(outdir).resolve()
    remapped: dict[str, str] = {}
    for key, value in dict(saved_files or {}).items():
        filename = Path(str(value or "")).name
        if not filename:
            continue
        candidate = target_dir / filename
        if candidate.exists():
            remapped[str(key)] = str(candidate)
    return remapped


__all__ = [
    "append_subprocess_log",
    "build_selfcheck_subject_signature",
    "build_run_log_path",
    "desktop_run_setup_cache_root",
    "desktop_run_setup_log_root",
    "desktop_single_run_cache_dir",
    "desktop_single_run_cache_key",
    "extract_json_object",
    "mirror_tree",
    "read_validated_suite_snapshot",
    "remap_saved_files_to_dir",
    "stable_run_hash",
    "validated_suite_snapshot_handoff_dir",
    "validated_suite_snapshot_handoff_path",
    "write_validated_suite_snapshot",
    "write_json_report_from_stdout",
]
