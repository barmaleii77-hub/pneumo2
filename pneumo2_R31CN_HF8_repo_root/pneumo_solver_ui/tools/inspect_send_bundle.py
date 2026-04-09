#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inspect_send_bundle.py

Лёгкая offline-инспекция send-bundle ZIP.

Назначение:
- быстро показать, есть ли validation/dashboard/triage/health;
- не потерять anim_latest diagnostics даже у старых bundle,
  где embedded health-report ещё не создавался;
- дать человеку и машине один и тот же компактный summary.

Пример:
  python -m pneumo_solver_ui.tools.inspect_send_bundle --zip SEND_xxx.zip --print_summary
"""

from __future__ import annotations

import argparse
import json
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from .health_report import collect_health_report
from pneumo_solver_ui.geometry_acceptance_contract import format_geometry_acceptance_summary_lines


def inspect_send_bundle(zip_path: Path) -> Dict[str, Any]:
    zp = Path(zip_path).expanduser().resolve()
    rep = collect_health_report(zp)
    name_set = set()
    try:
        with zipfile.ZipFile(zp, "r") as zf:
            name_set = set(zf.namelist())
    except Exception:
        name_set = set()

    signals = dict(rep.signals or {})
    meta = dict(signals.get("meta") or {})
    anim = dict(signals.get("anim_latest") or {})
    mnemo = dict(signals.get("mnemo_event_log") or {})
    artifacts = dict(signals.get("artifacts") or {})
    geometry_acceptance = dict(rep.signals.get("geometry_acceptance") or {})
    summary: Dict[str, Any] = {
        "schema": "send_bundle_inspection",
        "schema_version": "1.1.0",
        "zip_path": str(zp),
        "zip_name": zp.name,
        "ok": bool(rep.ok),
        "release": meta.get("release") or "",
        "artifacts": artifacts,
        "anim_latest": anim,
        "mnemo_event_log": mnemo,
        "geometry_acceptance": geometry_acceptance,
        "geometry_acceptance_gate": str(geometry_acceptance.get("release_gate") or "MISSING") if geometry_acceptance else "MISSING",
        "geometry_acceptance_reason": str(geometry_acceptance.get("release_gate_reason") or "") if geometry_acceptance else "",
        "notes": list(rep.notes or []),
        "health_report": asdict(rep),
        "has_embedded_health_report": bool(artifacts.get("health_report_embedded")),
        "has_validation_report": bool(artifacts.get("validation_report")),
        "has_dashboard_report": bool(artifacts.get("dashboard_report")),
        "has_triage_report": bool(artifacts.get("triage_report")),
        "has_anim_diagnostics": bool(artifacts.get("anim_diagnostics")),
        "has_browser_perf_registry_snapshot": bool(artifacts.get("browser_perf_registry_snapshot")),
        "has_browser_perf_previous_snapshot": bool(artifacts.get("browser_perf_previous_snapshot")),
        "has_browser_perf_contract": bool(artifacts.get("browser_perf_contract")),
        "has_browser_perf_evidence_report": bool(artifacts.get("browser_perf_evidence_report")),
        "has_browser_perf_comparison_report": bool(artifacts.get("browser_perf_comparison_report")),
        "has_browser_perf_trace": bool(artifacts.get("browser_perf_trace")),
        "has_geometry_acceptance": bool(geometry_acceptance),
        "zip_entries": len(name_set),
    }
    if not bool(artifacts.get("health_report_embedded")):
        summary["notes"].insert(0, "embedded health report is missing; summary was reconstructed from bundle contents")
    return summary


def render_inspection_md(summary: Dict[str, Any]) -> str:
    rep_obj = summary.get("health_report") or {}
    rep_signals = dict(rep_obj.get("signals") or {})
    anim = dict(summary.get("anim_latest") or {})
    mnemo = dict(summary.get("mnemo_event_log") or {})
    reload_inputs = list(anim.get("visual_reload_inputs") or [])
    lines = [
        "# Send bundle inspection",
        "",
        f"- ZIP: `{summary.get('zip_name') or ''}`",
        f"- OK: **{bool(summary.get('ok'))}**",
        f"- Release: {summary.get('release') or '—'}",
        f"- Embedded health report: {summary.get('has_embedded_health_report')}",
        f"- Validation report: {summary.get('has_validation_report')}",
        f"- Dashboard report: {summary.get('has_dashboard_report')}",
        f"- Triage report: {summary.get('has_triage_report')}",
        f"- Anim diagnostics: {summary.get('has_anim_diagnostics')}",
        f"- Browser perf snapshot: {summary.get('has_browser_perf_registry_snapshot')}",
        f"- Browser perf previous snapshot: {summary.get('has_browser_perf_previous_snapshot')}",
        f"- Browser perf contract: {summary.get('has_browser_perf_contract')}",
        f"- Browser perf evidence report: {summary.get('has_browser_perf_evidence_report')}",
        f"- Browser perf comparison report: {summary.get('has_browser_perf_comparison_report')}",
        f"- Browser perf trace: {summary.get('has_browser_perf_trace')}",
        f"- Geometry acceptance: {summary.get('has_geometry_acceptance')}",
        f"- Geometry acceptance gate: {summary.get('geometry_acceptance_gate') or 'MISSING'}",
        f"- Geometry acceptance reason: {summary.get('geometry_acceptance_reason') or '—'}",
        "",
        "## Anim latest",
        f"- available: {anim.get('available')}",
        f"- visual_cache_token: `{anim.get('visual_cache_token') or '—'}`",
        f"- visual_reload_inputs: {', '.join(str(x) for x in reload_inputs) if reload_inputs else '—'}",
        f"- pointer_sync_ok: {anim.get('pointer_sync_ok')}",
        f"- reload_inputs_sync_ok: {anim.get('reload_inputs_sync_ok')}",
        f"- npz_path_sync_ok: {anim.get('npz_path_sync_ok')}",
        f"- npz_path: `{anim.get('npz_path') or '—'}`",
        f"- updated_utc: {anim.get('updated_utc') or '—'}",
        f"- browser_perf_status: `{anim.get('browser_perf_status') or '—'}` / level=`{anim.get('browser_perf_level') or '—'}`",
        f"- browser_perf_evidence_status: `{anim.get('browser_perf_evidence_status') or '—'}` / level=`{anim.get('browser_perf_evidence_level') or '—'}` / bundle_ready=`{anim.get('browser_perf_bundle_ready')}` / snapshot_contract_match=`{anim.get('browser_perf_snapshot_contract_match')}`",
        f"- browser_perf_comparison_status: `{anim.get('browser_perf_comparison_status') or '—'}` / level=`{anim.get('browser_perf_comparison_level') or '—'}` / ready=`{anim.get('browser_perf_comparison_ready')}` / changed=`{anim.get('browser_perf_comparison_changed')}`",
        f"- browser_perf_comparison_delta: wakeups=`{anim.get('browser_perf_comparison_delta_total_wakeups')}` / dup=`{anim.get('browser_perf_comparison_delta_total_duplicate_guard_hits')}` / render=`{anim.get('browser_perf_comparison_delta_total_render_count')}` / max_idle_poll_ms=`{anim.get('browser_perf_comparison_delta_max_idle_poll_ms')}`",
        f"- browser_perf_artifacts_primary: snapshot=`{anim.get('browser_perf_registry_snapshot_ref') or '—'}` / exists=`{anim.get('browser_perf_registry_snapshot_exists')}` / in_bundle=`{anim.get('browser_perf_registry_snapshot_in_bundle')}` ; contract=`{anim.get('browser_perf_contract_ref') or '—'}` / exists=`{anim.get('browser_perf_contract_exists')}` / in_bundle=`{anim.get('browser_perf_contract_in_bundle')}`",
        f"- browser_perf_artifacts_secondary: previous=`{anim.get('browser_perf_previous_snapshot_ref') or '—'}` / exists=`{anim.get('browser_perf_previous_snapshot_exists')}` / in_bundle=`{anim.get('browser_perf_previous_snapshot_in_bundle')}` ; evidence=`{anim.get('browser_perf_evidence_report_ref') or '—'}` / exists=`{anim.get('browser_perf_evidence_report_exists')}` / in_bundle=`{anim.get('browser_perf_evidence_report_in_bundle')}` ; comparison=`{anim.get('browser_perf_comparison_report_ref') or '—'}` / exists=`{anim.get('browser_perf_comparison_report_exists')}` / in_bundle=`{anim.get('browser_perf_comparison_report_in_bundle')}` ; trace=`{anim.get('browser_perf_trace_ref') or '—'}` / exists=`{anim.get('browser_perf_trace_exists')}` / in_bundle=`{anim.get('browser_perf_trace_in_bundle')}`",
    ]
    if mnemo:
        lines += [
            "",
            "## Desktop Mnemo events",
            f"- severity: {mnemo.get('severity') or 'missing'}",
            f"- summary: {mnemo.get('headline') or '—'}",
            f"- current_mode: {mnemo.get('current_mode') or '—'}",
            f"- event_state: total=`{mnemo.get('event_count')}` / active=`{mnemo.get('active_latch_count')}` / acked=`{mnemo.get('acknowledged_latch_count')}`",
        ]
        recent_titles = [str(x) for x in (mnemo.get("recent_titles") or []) if str(x).strip()]
        if recent_titles:
            lines.append(f"- recent_titles: {' | '.join(recent_titles[:3])}")
    issues = list(anim.get("issues") or [])
    if issues:
        lines += ["", "## Anim issues"] + [f"- {x}" for x in issues]
    geom = dict(summary.get("geometry_acceptance") or {})
    if geom:
        lines += ["", "## Geometry acceptance"] + format_geometry_acceptance_summary_lines(geom)
    notes = list(summary.get("notes") or [])
    if notes:
        lines += ["", "## Notes"] + [f"- {x}" for x in notes]
    lines += [
        "",
        "## Health signals",
        "```json",
        json.dumps(rep_signals, ensure_ascii=False, indent=2),
        "```",
    ]
    return "\n".join(lines) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Offline inspect send bundle ZIP")
    ap.add_argument("--zip", required=True, help="Path to send bundle ZIP")
    ap.add_argument("--json_out", default="", help="Optional path for JSON summary")
    ap.add_argument("--md_out", default="", help="Optional path for Markdown summary")
    ap.add_argument("--print_summary", action="store_true", help="Print compact summary to stdout")
    ns = ap.parse_args(argv)

    summary = inspect_send_bundle(Path(ns.zip))
    if ns.json_out:
        Path(ns.json_out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md = render_inspection_md(summary)
    if ns.md_out:
        Path(ns.md_out).write_text(md, encoding="utf-8")
    if ns.print_summary:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
