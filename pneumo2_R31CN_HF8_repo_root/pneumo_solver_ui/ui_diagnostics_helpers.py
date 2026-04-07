from __future__ import annotations

import json
import platform
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


def make_ui_diagnostics_zip_bundle(
    *,
    here: Path,
    workspace_dir: Path,
    log_dir: Path | None,
    app_release: str,
    out_zip_path: str | Path | None = None,
    base_json: Any = None,
    suite_json: Any = None,
    ranges_json: Any = None,
    tag: str = "ui",
    include_logs: bool = True,
    include_results: bool = True,
    include_calibration: bool = True,
    include_workspace: bool = True,
    extra_paths: list[Any] | None = None,
    meta: dict[str, Any] | None = None,
    json_safe_fn: Callable[[Any], Any] | None = None,
) -> Path:
    """Assemble a diagnostics ZIP from the current UI/runtime context."""
    if out_zip_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_zip_path = workspace_dir / "diagnostics" / f"ui_diagnostics_{ts}_{tag}.zip"
    out_zip_path = Path(out_zip_path)
    out_zip_path.parent.mkdir(parents=True, exist_ok=True)

    extra_paths = list(extra_paths or [])

    default_paths: list[Path | None] = []
    if include_logs:
        default_paths.append(log_dir)
    if include_results:
        default_paths.append(Path(here) / "results")
    if include_calibration:
        default_paths.append(Path(here) / "calibration_runs")
    if include_workspace:
        default_paths.append(Path(workspace_dir))
    all_paths = [Path(p) for p in default_paths + extra_paths if p is not None]

    meta = dict(meta or {})
    meta.setdefault("app_release", app_release)
    meta.setdefault("python", sys.version)
    meta.setdefault("platform", platform.platform())
    meta.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
    meta_payload = json_safe_fn(meta) if json_safe_fn is not None else meta

    def _write_json(zf: zipfile.ZipFile, name: str, obj: Any) -> None:
        try:
            zf.writestr(name, json.dumps(obj, ensure_ascii=False, indent=2))
        except Exception as e:
            zf.writestr(name + ".error.txt", f"Failed to serialize {name}: {e}")

    def _should_skip(path: Path) -> bool:
        suf = path.suffix.lower()
        if suf in {".pyc", ".pyo"}:
            return True
        parts = set(path.parts)
        if ".venv" in parts or "__pycache__" in parts:
            return True
        return False

    with zipfile.ZipFile(out_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("meta.json", json.dumps(meta_payload, ensure_ascii=False, indent=2))
        if base_json is not None:
            _write_json(zf, "snapshot/base_json.json", base_json)
        if suite_json is not None:
            _write_json(zf, "snapshot/suite_json.json", suite_json)
        if ranges_json is not None:
            _write_json(zf, "snapshot/ranges_json.json", ranges_json)

        for base in all_paths:
            if not base.exists():
                continue
            if base.is_file():
                if _should_skip(base):
                    continue
                arc = str(base.relative_to(here)) if str(base).startswith(str(here)) else str(base.name)
                zf.write(base, arcname=arc)
                continue
            for path in base.rglob("*"):
                if path.is_dir() or _should_skip(path):
                    continue
                arc = (
                    str(path.relative_to(here))
                    if str(path).startswith(str(here))
                    else str(Path(base.name) / path.relative_to(base))
                )
                zf.write(path, arcname=arc)

    return out_zip_path


__all__ = ["make_ui_diagnostics_zip_bundle"]
