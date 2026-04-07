"""I/O + formatting for structured self_check warnings.

Цель: чтобы WARN из self_check/preflight не были "тихими".
- self_check.py пишет REPORTS/SELF_CHECK_SILENT_WARNINGS.json (+ .md)
- UI/triage_report читают этот файл и показывают сигнализацию.

Файл специально без тяжёлых зависимостей (pandas/np) — только json/pathlib.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPORT_JSON_NAME = "SELF_CHECK_SILENT_WARNINGS.json"
REPORT_MD_NAME = "SELF_CHECK_SILENT_WARNINGS.md"


def get_project_root() -> Path:
    # .../pneumo_solver_ui/diag/silent_warnings_report.py -> project root is 3 levels up
    return Path(__file__).resolve().parents[2]


def get_reports_dir(project_root: Optional[Path] = None) -> Path:
    root = project_root or get_project_root()
    return root / "REPORTS"


def load_report(reports_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    rdir = reports_dir or get_reports_dir()
    p = rdir / REPORT_JSON_NAME
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        # Не валим UI/triage из-за битого JSON — лучше показать "нет данных".
        return None


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|")


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {}) or {}
    warn_count = int(summary.get("warn_count", 0) or 0)
    fail_count = int(summary.get("fail_count", 0) or 0)
    rc = report.get("rc")

    lines = []
    lines.append("# SELF_CHECK — Silent warnings snapshot")
    lines.append("")
    lines.append(f"- generated_at_utc: {report.get('generated_at_utc','')}")
    lines.append(f"- release: {report.get('release','')}")
    lines.append(f"- version: {report.get('version','')}")
    lines.append(f"- rc: {rc}")
    lines.append(f"- fail_count: {fail_count}")
    lines.append(f"- warn_count: {warn_count}")
    lines.append("")

    if fail_count:
        lines.append("## ❌ FAIL")
        for it in (report.get("fails") or []):
            step = it.get("step", "")
            msg = it.get("message", "")
            lines.append(f"- [{step}] {_md_escape(str(msg))}")
        lines.append("")

    if warn_count:
        lines.append("## ⚠️ WARN")
        for it in (report.get("warnings") or []):
            step = it.get("step", "")
            msg = it.get("message", "")
            lines.append(f"- [{step}] {_md_escape(str(msg))}")
        lines.append("")

    # Compact table (first N)
    items = (report.get("fails") or []) + (report.get("warnings") or [])
    if items:
        lines.append("## Details")
        lines.append("")
        lines.append("|level|step|message|data|")
        lines.append("|---|---:|---|---|")
        for it in items[:200]:
            lvl = it.get("level", "")
            step = it.get("step", "")
            msg = _md_escape(str(it.get("message", "")))
            data = it.get("data", {}) or {}
            try:
                data_s = _md_escape(json.dumps(data, ensure_ascii=False))
            except Exception:
                data_s = _md_escape(str(data))
            lines.append(f"|{lvl}|{step}|{msg}|{data_s}|")
        lines.append("")

    return "\n".join(lines) + "\n"


def write_report(report: Dict[str, Any], reports_dir: Optional[Path] = None) -> Tuple[Path, Path]:
    rdir = reports_dir or get_reports_dir()
    rdir.mkdir(parents=True, exist_ok=True)

    json_path = rdir / REPORT_JSON_NAME
    md_path = rdir / REPORT_MD_NAME

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
