# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


LATEST_DESKTOP_DIAGNOSTICS_RUN_JSON = "latest_desktop_diagnostics_run.json"
LATEST_DESKTOP_DIAGNOSTICS_RUN_LOG = "latest_desktop_diagnostics_run.log"
LATEST_DESKTOP_DIAGNOSTICS_CENTER_JSON = "latest_desktop_diagnostics_center_state.json"
LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD = "latest_desktop_diagnostics_summary.md"
LATEST_SEND_BUNDLE_INSPECTION_JSON = "latest_send_bundle_inspection.json"
LATEST_SEND_BUNDLE_INSPECTION_MD = "latest_send_bundle_inspection.md"


def now_local_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def path_str(path: Optional[Path | str]) -> str:
    if not path:
        return ""
    try:
        return str(Path(path).expanduser().resolve())
    except Exception:
        return str(path)


@dataclass(slots=True)
class DesktopDiagnosticsRequest:
    level: str = "standard"
    skip_ui_smoke: bool = False
    no_zip: bool = False
    run_opt_smoke: bool = False
    opt_minutes: int = 2
    opt_jobs: int = 2
    osc_dir: str = ""
    out_root: str = ""

    def resolved_out_root(self, repo_root: Path) -> Path:
        raw = str(self.out_root or "").strip()
        if not raw:
            return (repo_root / "diagnostics").resolve()
        try:
            path = Path(raw).expanduser()
            if path.is_absolute():
                return path.resolve()
        except Exception:
            return Path(raw)
        return (repo_root / raw).resolve()


@dataclass(slots=True)
class DesktopDiagnosticsRunRecord:
    ok: bool
    started_at: str
    finished_at: str = ""
    status: str = ""
    command: list[str] = field(default_factory=list)
    returncode: Optional[int] = None
    run_dir: str = ""
    zip_path: str = ""
    out_root: str = ""
    log_path: str = ""
    state_path: str = ""
    last_message: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema"] = "desktop_diagnostics_run_state"
        payload["schema_version"] = "1.0.0"
        return payload


@dataclass(slots=True)
class DesktopDiagnosticsBundleRecord:
    out_dir: str
    latest_zip_path: str = ""
    latest_zip_name: str = ""
    latest_bundle_meta_path: str = ""
    latest_inspection_json_path: str = ""
    latest_inspection_md_path: str = ""
    latest_health_json_path: str = ""
    latest_health_md_path: str = ""
    latest_validation_json_path: str = ""
    latest_validation_md_path: str = ""
    latest_triage_md_path: str = ""
    latest_clipboard_status_path: str = ""
    anim_pointer_diagnostics_path: str = ""
    summary_lines: list[str] = field(default_factory=list)
    clipboard_ok: Optional[bool] = None
    clipboard_message: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema"] = "desktop_diagnostics_bundle_state"
        payload["schema_version"] = "1.0.0"
        return payload


def build_run_full_diagnostics_command(
    python_exe: str,
    script_path: Path,
    request: DesktopDiagnosticsRequest,
) -> list[str]:
    cmd = [str(python_exe), str(script_path), "--level", str(request.level)]
    if request.skip_ui_smoke:
        cmd.append("--skip_ui_smoke")
    if request.no_zip:
        cmd.append("--no_zip")
    if request.run_opt_smoke:
        cmd += [
            "--run_opt_smoke",
            "--opt_minutes",
            str(int(request.opt_minutes)),
            "--opt_jobs",
            str(int(request.opt_jobs)),
        ]
    osc_dir = str(request.osc_dir or "").strip()
    if osc_dir:
        cmd += ["--osc_dir", osc_dir]
    cmd += ["--out_root", str(request.out_root or "")]
    return cmd


def parse_run_full_diagnostics_output_line(line: str) -> dict[str, str]:
    text = str(line or "").strip()
    updates: dict[str, str] = {}
    if text.startswith("Run dir:"):
        updates["run_dir"] = text.split("Run dir:", 1)[1].strip()
    elif text.startswith("Zip:"):
        updates["zip_path"] = text.split("Zip:", 1)[1].strip()
    elif text.startswith("Diagnostics written to:"):
        updates["run_dir"] = text.split("Diagnostics written to:", 1)[1].strip()
    return updates
