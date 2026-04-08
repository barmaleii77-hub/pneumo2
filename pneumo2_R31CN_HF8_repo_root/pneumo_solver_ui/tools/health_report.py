# -*- coding: utf-8 -*-
"""pneumo_solver_ui.tools.health_report (Testy R639)

Сводный отчёт по "здоровью" send-bundle ZIP.
Цель: одним файлом дать быстрый ответ:
- валиден ли ZIP
- есть ли критичные проблемы в логах (loglint strict)
- прошли ли selfchecks
- не потеряны ли anim_latest reload diagnostics

Используется из make_send_bundle: после сборки/валидации ZIP создаём health_report.*
и добавляем его внутрь ZIP.

Best-effort: никогда не должен валить сборку.
"""

from __future__ import annotations

import importlib
import json
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .send_bundle_contract import (
    ANIM_DIAG_JSON,
    ANIM_GLOBAL_POINTER,
    ANIM_LOCAL_NPZ,
    ANIM_LOCAL_POINTER,
    annotate_anim_source_for_bundle,
    choose_anim_snapshot,
    extract_anim_snapshot,
)


@dataclass
class HealthReport:
    schema: str
    schema_version: str
    created_at: str
    zip_path: str
    ok: bool
    signals: Dict[str, Any]
    notes: List[str]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_json_from_zip(z: zipfile.ZipFile, name: str) -> Optional[Dict[str, Any]]:
    try:
        with z.open(name, "r") as f:
            raw = f.read()
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None


def _glob_zip_names(names: List[str], suffix: str) -> List[str]:
    return [n for n in names if n.endswith(suffix)]




def _collect_geometry_acceptance_best_effort(raw_npz: bytes) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Best-effort geometry acceptance extraction without hard import-time dependency.

    Why:
    - send-bundle helpers can be launched from GUI/postmortem contexts where the
      interpreter path is not always obvious from logs;
    - health report must remain available even if heavy numerical deps are not
      importable in that specific helper process.

    Contract:
    - returns (report_dict, None) on success;
    - returns (None, human_readable_error) when helper import/execution is not
      available;
    - never raises.
    """
    try:
        mod = importlib.import_module("pneumo_solver_ui.geometry_acceptance_contract")
        collect = getattr(mod, "collect_geometry_acceptance_from_npz")
    except Exception as e:
        return None, f"geometry acceptance helper unavailable: {type(e).__name__}: {e!s}"

    try:
        rep = collect(raw_npz)
        if isinstance(rep, dict):
            return dict(rep), None
        return None, "geometry acceptance helper returned non-dict result"
    except Exception as e:
        return None, f"failed to inspect anim_latest geometry acceptance: {type(e).__name__}: {e!s}"


def _format_geometry_acceptance_summary_lines_best_effort(geom: Dict[str, Any]) -> List[str]:
    try:
        mod = importlib.import_module("pneumo_solver_ui.geometry_acceptance_contract")
        fmt = getattr(mod, "format_geometry_acceptance_summary_lines")
        lines = fmt(geom)
        return [str(x) for x in lines]
    except Exception:
        gate = str(geom.get("release_gate") or geom.get("inspection_status") or "—")
        reason = str(geom.get("release_gate_reason") or geom.get("error") or "—")
        return [f"- gate: {gate}", f"- reason: {reason}"]


def collect_health_report(zip_path: Path) -> HealthReport:
    zip_path = Path(zip_path).resolve()
    created_at = _now_iso()
    signals: Dict[str, Any] = {}
    notes: List[str] = []
    ok = True

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            name_set = set(names)

            signals["artifacts"] = {
                "validation_report": "validation/validation_report.json" in name_set,
                "dashboard_report": "dashboard/dashboard.json" in name_set,
                "triage_report": "triage/triage_report.json" in name_set or "triage/triage_report.md" in name_set,
                "anim_diagnostics": ANIM_DIAG_JSON in name_set,
                "health_report_embedded": "health/health_report.json" in name_set or "health/health_report.md" in name_set,
            }

            meta = _read_json_from_zip(z, "bundle/meta.json")
            if meta is not None:
                signals["meta"] = {
                    "release": meta.get("release"),
                    "run_id": meta.get("run_id"),
                    "created_at": meta.get("created_at"),
                }

            anim_sources: Dict[str, Dict[str, Any]] = {}

            val = _read_json_from_zip(z, "validation/validation_report.json")
            if val is not None:
                val_errors = list(val.get("errors") or []) if isinstance(val.get("errors"), list) else []
                val_warnings = list(val.get("warnings") or []) if isinstance(val.get("warnings"), list) else []
                signals["validation"] = {
                    "ok": bool(val.get("ok", False)),
                    "errors_count": len(val_errors),
                    "warnings_count": len(val_warnings),
                    "errors_preview": val_errors[:5],
                    "warnings_preview": val_warnings[:5],
                }
                if not bool(val.get("ok", False)):
                    ok = False
                anim_snap = annotate_anim_source_for_bundle(
                    extract_anim_snapshot(val.get("anim_latest"), source="validation"),
                    name_set=name_set,
                )
                if anim_snap is not None:
                    anim_sources["validation"] = anim_snap
                    if anim_snap.get("issues"):
                        notes.extend(str(x) for x in anim_snap.get("issues") or [] if str(x).strip())

            sc = _read_json_from_zip(z, "selfcheck/selfcheck_report.json")
            if sc is not None:
                signals["selfcheck"] = {
                    "ok": bool(sc.get("ok", False)),
                    "failed_steps": (sc.get("summary", {}) or {}).get("steps_failed", []),
                }
                if not bool(sc.get("ok", False)):
                    ok = False

            tri = _read_json_from_zip(z, "triage/triage_report.json")
            if tri is not None:
                sev = tri.get("severity_counts") or {}
                signals["triage"] = {
                    "severity_counts": sev,
                    "red_flags": tri.get("red_flags", []),
                }
                try:
                    if int(sev.get("critical", 0)) > 0:
                        notes.append("triage reports CRITICAL entries")
                except Exception:
                    pass

            dash = _read_json_from_zip(z, "dashboard/dashboard.json")
            if dash is not None:
                sections = list((dash.get("sections") or {}).keys()) if isinstance(dash.get("sections"), dict) else []
                signals["dashboard"] = {
                    "sections": sections,
                    "warnings": list(dash.get("warnings") or [])[:10],
                    "errors": list(dash.get("errors") or [])[:10],
                }
                anim_snap = annotate_anim_source_for_bundle(
                    extract_anim_snapshot(dash.get("anim_latest"), source="dashboard"),
                    name_set=name_set,
                )
                if anim_snap is not None:
                    anim_sources["dashboard"] = anim_snap

            diag = _read_json_from_zip(z, ANIM_DIAG_JSON)
            if diag is not None:
                anim_snap = annotate_anim_source_for_bundle(
                    extract_anim_snapshot(diag, source="diagnostics"),
                    name_set=name_set,
                )
                if anim_snap is not None:
                    anim_sources["diagnostics"] = anim_snap

            local_ptr = _read_json_from_zip(z, ANIM_LOCAL_POINTER)
            if local_ptr is not None:
                anim_snap = annotate_anim_source_for_bundle(
                    extract_anim_snapshot(local_ptr, source="local_pointer"),
                    name_set=name_set,
                )
                if anim_snap is not None:
                    anim_sources["local_pointer"] = anim_snap

            global_ptr = _read_json_from_zip(z, ANIM_GLOBAL_POINTER)
            if global_ptr is not None:
                anim_snap = annotate_anim_source_for_bundle(
                    extract_anim_snapshot(global_ptr, source="global_pointer"),
                    name_set=name_set,
                )
                if anim_snap is not None:
                    anim_sources["global_pointer"] = anim_snap

            # Loglint strict (any source): collect totals and take worst.
            ll_names = _glob_zip_names(names, "/loglint_strict/loglint_report.json")
            if ll_names:
                totals = []
                for name in ll_names:
                    rep = _read_json_from_zip(z, name)
                    if not rep:
                        continue
                    totals.append(
                        {
                            "path": name,
                            "total_errors": int(rep.get("total_errors", 0) or 0),
                            "total_lines": int(rep.get("total_lines", 0) or 0),
                            "files_with_errors": int(rep.get("files_with_errors", 0) or 0),
                        }
                    )
                if totals:
                    worst = max(totals, key=lambda x: x.get("total_errors", 0))
                    signals["loglint_strict"] = {
                        "reports": totals,
                        "worst": worst,
                    }
                    if worst.get("total_errors", 0) > 0:
                        ok = False

            anim_summary = choose_anim_snapshot(
                anim_sources,
                preferred_order=("validation", "diagnostics", "local_pointer", "global_pointer", "dashboard"),
            )
            if ANIM_LOCAL_NPZ in name_set:
                try:
                    with z.open(ANIM_LOCAL_NPZ, "r") as f:
                        raw_npz = f.read()
                    geom_acc, geom_err = _collect_geometry_acceptance_best_effort(raw_npz)
                    if geom_acc is not None:
                        geom_acc = dict(geom_acc)
                        geom_acc["inspection_status"] = "ok"
                        ga_gate = str(geom_acc.get("release_gate") or "MISSING")
                        if ga_gate == "FAIL":
                            ok = False
                            notes.append(f"geometry acceptance gate=FAIL for anim_latest.npz: {geom_acc.get('release_gate_reason') or ''}")
                        elif ga_gate == "WARN":
                            notes.append(f"geometry acceptance gate=WARN for anim_latest.npz: {geom_acc.get('release_gate_reason') or ''}")
                    else:
                        geom_acc = {
                            "inspection_status": "unavailable",
                            "error": str(geom_err or "geometry acceptance helper unavailable"),
                        }
                        notes.append(str(geom_acc["error"]))
                    signals["geometry_acceptance"] = geom_acc
                    anim_summary["geometry_acceptance"] = geom_acc
                except Exception as e:
                    geom_acc = {
                        "inspection_status": "unavailable",
                        "error": f"failed to inspect anim_latest geometry acceptance: {type(e).__name__}: {e!s}",
                    }
                    signals["geometry_acceptance"] = geom_acc
                    anim_summary["geometry_acceptance"] = geom_acc
                    notes.append(str(geom_acc["error"]))
            signals["anim_latest"] = anim_summary
            for msg in anim_summary.get("issues") or []:
                smsg = str(msg).strip()
                if smsg and smsg not in notes:
                    notes.append(smsg)

    except Exception as e:
        ok = False
        notes.append(f"failed to read zip: {type(e).__name__}: {e!s}")

    return HealthReport(
        schema="health_report",
        schema_version="1.3.0",
        created_at=created_at,
        zip_path=str(zip_path),
        ok=bool(ok),
        signals=signals,
        notes=notes,
    )


def render_health_report_md(rep: HealthReport) -> str:
    val = dict(rep.signals.get("validation") or {})
    anim = dict(rep.signals.get("anim_latest") or {})
    artifacts = dict(rep.signals.get("artifacts") or {})
    reload_inputs = list(anim.get("visual_reload_inputs") or [])
    lines = [
        "# Health report",
        "",
        f"- Created: {rep.created_at}",
        f"- ZIP: `{Path(rep.zip_path).name}`",
        f"- OK: **{rep.ok}**",
        "",
        "## Artifacts",
        f"- validation_report: {artifacts.get('validation_report')}",
        f"- dashboard_report: {artifacts.get('dashboard_report')}",
        f"- triage_report: {artifacts.get('triage_report')}",
        f"- anim_diagnostics: {artifacts.get('anim_diagnostics')}",
        f"- health_report_embedded: {artifacts.get('health_report_embedded')}",
    ]

    if val:
        lines += [
            "",
            "## Validation",
            f"- ok: {val.get('ok')}",
            f"- errors_count: {val.get('errors_count')}",
            f"- warnings_count: {val.get('warnings_count')}",
        ]

    if anim:
        lines += [
            "",
            "## Anim latest diagnostics",
            f"- source: {anim.get('source') or '—'}",
            f"- available: {anim.get('available')}",
            f"- visual_cache_token: `{anim.get('visual_cache_token') or '—'}`",
            f"- visual_reload_inputs: {', '.join(str(x) for x in reload_inputs) if reload_inputs else '—'}",
            f"- pointer_sync_ok: {anim.get('pointer_sync_ok')}",
            f"- reload_inputs_sync_ok: {anim.get('reload_inputs_sync_ok')}",
            f"- npz_path_sync_ok: {anim.get('npz_path_sync_ok')}",
            f"- npz_path: `{anim.get('npz_path') or '—'}`",
            f"- updated_utc: {anim.get('updated_utc') or '—'}",
            f"- usable_from_bundle: {anim.get('usable_from_bundle')}",
            f"- pointer_json_in_bundle: {anim.get('pointer_json_in_bundle')}",
            f"- npz_path_in_bundle: {anim.get('npz_path_in_bundle')}",
        ]
        anim_issues = list(anim.get("issues") or [])
        if anim_issues:
            lines += ["", "### Anim latest issues"] + [f"- {x}" for x in anim_issues]

    geom = dict(rep.signals.get("geometry_acceptance") or {})
    if geom:
        lines += ["", "## Geometry acceptance"] + _format_geometry_acceptance_summary_lines_best_effort(geom)

    lines += [
        "",
        "## Signals",
        "```json",
        json.dumps(rep.signals, ensure_ascii=False, indent=2),
        "```",
    ]
    if rep.notes:
        lines += ["", "## Notes"] + [f"- {n}" for n in rep.notes]
    return "\n".join(lines) + "\n"


def build_health_report(
    zip_path: Path,
    *,
    out_dir: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[Path]]:
    zip_path = Path(zip_path).resolve()
    out_dir = Path(out_dir).resolve() if out_dir else zip_path.parent.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rep = collect_health_report(zip_path)

    json_path = out_dir / "latest_health_report.json"
    md_path = out_dir / "latest_health_report.md"

    try:
        json_path.write_text(json.dumps(asdict(rep), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        json_path = None

    try:
        md_path.write_text(render_health_report_md(rep), encoding="utf-8")
    except Exception:
        md_path = None

    return json_path, md_path


def add_health_report_to_zip(zip_path: Path, json_path: Optional[Path], md_path: Optional[Path]) -> None:
    """Append health report files into existing ZIP (best-effort)."""
    try:
        with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            if json_path and json_path.exists():
                z.write(json_path, arcname="health/health_report.json")
            if md_path and md_path.exists():
                z.write(md_path, arcname="health/health_report.md")
    except Exception:
        return
