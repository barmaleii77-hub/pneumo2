#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""triage_report.py

R53: Автоматический triage-отчёт (best-effort)
============================================

Зачем
----
При активной разработке и автономном тестировании быстро появляется много артефактов:
- UI сессии (runs/ui_sessions/UI_*/...)
- autotest_runs/RUN_*/...
- diagnostics_runs/RUN_*/...
- send_bundles/SEND_*_bundle.zip
- run_registry.jsonl (единый журнал событий)

В результате в чат часто нужно отправлять не «всю папку проекта», а *один ZIP*.
Но даже внутри ZIP удобно иметь компактную "шапку":
что запускалось, где лежат логи, какие RC/провалы, что делать дальше.

Этот скрипт генерирует:
- triage_report.md  (человекочитаемо)
- triage_report.json (машиночитаемо)

Идея
----
Отчёт собирается "best effort": если чего-то нет, мы не падаем, а пишем
"not found" и продолжаем.

Генератор используется:
- напрямую (CLI)
- из make_send_bundle.py (вкладывается в ZIP и кладётся рядом как latest_triage_report.*)

Запуск
-----
  python -m pneumo_solver_ui.tools.triage_report --out_dir send_bundles --print_paths

"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import traceback
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pneumo_solver_ui.optimization_problem_hash_mode import read_problem_hash_mode_artifact
from pneumo_solver_ui.optimization_problem_scope import (
    problem_hash_short_label,
    read_problem_hash_artifact,
)
from .send_bundle_contract import (
    ANIM_DIAG_JSON,
    ANIM_DIAG_MD,
    ANIM_DIAG_SIDECAR_JSON,
    ANIM_DIAG_SIDECAR_MD,
    build_anim_operator_recommendations,
    extract_anim_snapshot,
    summarize_ring_closure,
    summarize_mnemo_event_log,
)

try:
    from pneumo_solver_ui.release_info import get_release
    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_read_text(path: Path, max_bytes: int = 2_000_000) -> str:
    try:
        b = path.read_bytes()
        if len(b) > max_bytes:
            b = b[:max_bytes] + b"\n\n...TRUNCATED...\n"
        return b.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _safe_json_load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _format_anim_diag_error(exc: BaseException) -> str:
    if isinstance(exc, ModuleNotFoundError):
        missing = str(getattr(exc, "name", "") or "").strip() or "unknown"
        return f"Отсутствует необязательная зависимость: {missing}"
    return repr(exc)


def _normcase_path_str(value: Any) -> str:
    try:
        return os.path.normcase(str(Path(str(value)).expanduser()))
    except Exception:
        return os.path.normcase(str(value or ""))


def _event_matches_latest_bundle_path(ev: Dict[str, Any], latest_path: Optional[str]) -> bool:
    if not latest_path:
        return False
    want = _normcase_path_str(latest_path)
    got_zip = _normcase_path_str(ev.get("zip_path"))
    got_latest = _normcase_path_str(ev.get("latest_zip_path"))
    if got_zip and got_zip == want:
        return True
    if got_latest and got_latest == want:
        return True
    return False


def _event_seems_local_to_repo(ev: Dict[str, Any], repo_root: Path) -> bool:
    repo_s = _normcase_path_str(repo_root)
    for key in ("zip_path", "latest_zip_path", "primary_session_dir"):
        val = ev.get(key)
        if val and _normcase_path_str(val).startswith(repo_s):
            return True
    env = ev.get("env") or {}
    if isinstance(env, dict):
        cwd = env.get("cwd")
        if cwd and _normcase_path_str(cwd).startswith(repo_s):
            return True
    return False


def _pick_latest_dirs(parent: Path, prefix: str, keep_last_n: int = 1) -> List[Path]:
    if not parent.exists():
        return []
    items = [p for p in parent.iterdir() if p.is_dir() and p.name.startswith(prefix)]
    items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return items[: max(0, int(keep_last_n))]


def _pick_latest_files(parent: Path, pattern: str, keep_last_n: int = 1) -> List[Path]:
    if not parent.exists():
        return []
    items = list(parent.glob(pattern))
    items = [p for p in items if p.is_file()]
    items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return items[: max(0, int(keep_last_n))]


def _read_jsonl_tail(path: Path, max_lines: int = 2000) -> List[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = lines[-max(0, int(max_lines)) :]
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            continue
    return out


def _parse_junit_xml(path: Path) -> Dict[str, Any]:
    """Parse pytest JUnit XML (best-effort).

    Returns a compact summary + list of failing testcases.
    """
    out: Dict[str, Any] = {
        "path": str(path),
        "tests": None,
        "failures": None,
        "errors": None,
        "skipped": None,
        "time": None,
        "failing": [],
    }
    try:
        tree = ET.parse(str(path))
        root = tree.getroot()

        # root может быть <testsuites> или <testsuite>
        suites: List[ET.Element] = []
        if root.tag.lower().endswith("testsuite"):
            suites = [root]
        else:
            suites = [el for el in root.iter() if el.tag.lower().endswith("testsuite")]

        # агрегируем
        def _as_int(x: Optional[str]) -> Optional[int]:
            try:
                return int(x) if x is not None else None
            except Exception:
                return None

        def _as_float(x: Optional[str]) -> Optional[float]:
            try:
                return float(x) if x is not None else None
            except Exception:
                return None

        tests = 0
        failures = 0
        errors = 0
        skipped = 0
        time_s = 0.0

        failing: List[Dict[str, str]] = []

        for s in suites:
            tests += _as_int(s.attrib.get("tests")) or 0
            failures += _as_int(s.attrib.get("failures")) or 0
            errors += _as_int(s.attrib.get("errors")) or 0
            skipped += _as_int(s.attrib.get("skipped")) or 0
            time_s += _as_float(s.attrib.get("time")) or 0.0

            for tc in s.iter():
                if not tc.tag.lower().endswith("testcase"):
                    continue
                name = tc.attrib.get("name") or ""
                classname = tc.attrib.get("classname") or ""

                # failure/error elements
                for child in tc:
                    tag = (child.tag or "").lower()
                    if tag.endswith("failure") or tag.endswith("error"):
                        msg = child.attrib.get("message") or ""
                        failing.append(
                            {
                                "name": name,
                                "classname": classname,
                                "kind": "failure" if tag.endswith("failure") else "error",
                                "message": msg,
                            }
                        )
                        break

        out["tests"] = tests
        out["failures"] = failures
        out["errors"] = errors
        out["skipped"] = skipped
        out["time"] = round(time_s, 3)
        out["failing"] = failing[:50]
        return out
    except Exception:
        out["parse_error"] = traceback.format_exc()
        return out


def _scan_jsonl_levels(path: Path, max_lines: int = 200_000) -> Dict[str, Any]:
    """Fast-ish scan of JSONL log file to count levels and extract last errors."""
    out: Dict[str, Any] = {
        "path": str(path),
        "lines": 0,
        "levels": {},
        "last_errors": [],
        "scan_note": None,
    }
    if not path.exists() or not path.is_file():
        out["scan_note"] = "missing"
        return out

    # Ограничим чтение: если файл огромный — берём хвост.
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
            out["scan_note"] = f"tail_only (max_lines={max_lines})"
        out["lines"] = len(lines)
    except Exception:
        out["scan_note"] = "read_failed"
        return out

    levels: Dict[str, int] = {}
    last_err: List[Dict[str, Any]] = []

    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
            if not isinstance(obj, dict):
                continue
            lvl = str(obj.get("level") or "").lower() or "(none)"
            levels[lvl] = levels.get(lvl, 0) + 1
            if lvl in {"error", "critical"}:
                last_err.append({"ts": obj.get("ts"), "event": obj.get("event"), "msg": obj.get("msg") or obj.get("message")})
        except Exception:
            continue

    out["levels"] = levels
    out["last_errors"] = last_err[-20:]
    return out


def _is_run_end_failure(ev: Dict[str, Any]) -> bool:
    """Return True only for genuinely problematic run_end events.

    Diagnostics truth rule:
    - explicit/benign terminal statuses (ok/done/cached/stopped) are not failures
      even when the underlying process rc is non-zero; launcher-driven UI stop on
      Windows commonly reports rc=1 and must not pollute failure summaries;
    - explicit bad statuses remain failures regardless of rc;
    - rc!=0 remains a fallback only when the event does not clearly say it was an
      explicit stop/normal termination.
    """
    try:
        if str(ev.get("event") or "") != "run_end":
            return False
        status = str(ev.get("status") or "").strip().lower()
        rc = ev.get("rc")
        if status in {"ok", "done", "cached", "stopped"}:
            return False
        if status in {"fail", "error", "degraded", "crash", "failed", "timeout", "interrupted"}:
            return True
        if bool(ev.get("launcher_stop_requested")):
            return False
        if isinstance(rc, int) and int(rc) != 0:
            return True
    except Exception:
        return False
    return False


def _load_anim_latest_summary(repo_root: Path, sb_root: Path) -> Dict[str, Any]:
    """Load canonical anim_latest diagnostics for triage/report surfaces.

    Priority:
    1) latest_anim_pointer_diagnostics.json in send_bundles/SEND_BUNDLES (sidecar written by make_send_bundle)
    2) global pointer snapshot via run_artifacts.collect_anim_latest_diagnostics_summary()

    The result remains flat/canonical (`anim_latest_*` keys) to avoid alias bridges.
    """
    diag_json = sb_root / ANIM_DIAG_SIDECAR_JSON
    diag_md = sb_root / ANIM_DIAG_SIDECAR_MD

    out: Dict[str, Any] = {
        "source": None,
        "diagnostics_json_path": str(diag_json) if diag_json.exists() else None,
        "diagnostics_md_path": str(diag_md) if diag_md.exists() else None,
    }

    def _merge_missing_fields(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base)
        for key, value in extra.items():
            if key in {"source", "diagnostics_json_path", "diagnostics_md_path"}:
                continue
            cur = merged.get(key)
            if cur not in (None, "", [], {}):
                continue
            if value in (None, "", [], {}):
                continue
            if isinstance(value, dict):
                merged[key] = dict(value)
            elif isinstance(value, list):
                merged[key] = list(value)
            else:
                merged[key] = value
        return merged

    j = _safe_json_load(diag_json)
    global_diag: Optional[Dict[str, Any]] = None

    try:
        from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary

        j2 = collect_anim_latest_diagnostics_summary(include_meta=True)
        if isinstance(j2, dict):
            snap = extract_anim_snapshot(j2, source="triage_global_pointer")
            global_diag = _merge_missing_fields(dict(j2), dict(snap or {}))
    except Exception as exc:
        out["error"] = _format_anim_diag_error(exc)

    if isinstance(j, dict):
        snap = extract_anim_snapshot(j, source="triage_send_bundle_sidecar")
        merged = _merge_missing_fields(dict(j), dict(snap or {}))
        merged = _merge_missing_fields(merged, global_diag or {})
        out.update(merged)
        out["source"] = "send_bundle_sidecar"
        return out
    if isinstance(global_diag, dict):
        out.update(global_diag)
        out["source"] = "global_pointer"
        return out

    out.setdefault("anim_latest_available", False)
    return out


def generate_triage_report(
    repo_root: Path,
    *,
    keep_last_n: int = 3,
    primary_session_dir: Optional[Path] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Return (markdown_text, json_summary)."""
    repo_root = Path(repo_root).resolve()

    # ---- locate key paths ----
    runs_root = repo_root / "runs"
    rr_path = runs_root / "run_registry.jsonl"
    rr_events = _read_jsonl_tail(rr_path, max_lines=4000)

    # UI session
    session_dir: Optional[Path] = None
    if primary_session_dir is not None:
        try:
            p = Path(primary_session_dir).expanduser().resolve()
            if p.exists() and p.is_dir():
                session_dir = p
        except Exception:
            pass
    if session_dir is None:
        env_sd = os.environ.get("PNEUMO_SESSION_DIR")
        if env_sd:
            try:
                p = Path(env_sd).expanduser().resolve()
                if p.exists() and p.is_dir():
                    session_dir = p
            except Exception:
                pass
    if session_dir is None:
        ui_parent = runs_root / "ui_sessions"
        latest = _pick_latest_dirs(ui_parent, "UI_", keep_last_n=1)
        session_dir = latest[0] if latest else None

    # Autotest + diagnostics
    pneumo_dir = repo_root / "pneumo_solver_ui"
    at_parent = pneumo_dir / "autotest_runs"
    diag_parent = repo_root / "diagnostics_runs"
    latest_at = _pick_latest_dirs(at_parent, "RUN_", keep_last_n=1)
    latest_diag = _pick_latest_dirs(diag_parent, "RUN_", keep_last_n=1)

    autotest_dir = latest_at[0] if latest_at else None
    diag_dir = latest_diag[0] if latest_diag else None

    # Distributed optimization runs (Ray/Dask)
    dist_parent = runs_root / "dist_runs"
    latest_dist = _pick_latest_dirs(dist_parent, "DIST_", keep_last_n=1)
    dist_dir = latest_dist[0] if latest_dist else None

    dist_progress: Optional[Dict[str, Any]] = None
    if dist_dir is not None:
        j = _safe_json_load(dist_dir / "progress.json")
        if isinstance(j, dict):
            dist_progress = dict(j)
            problem_hash = str(read_problem_hash_artifact(dist_dir) or "").strip()
            if problem_hash:
                dist_progress["problem_hash"] = problem_hash
                dist_progress["problem_hash_short"] = problem_hash_short_label(problem_hash)
            problem_hash_mode = str(read_problem_hash_mode_artifact(dist_dir) or "").strip()
            if problem_hash_mode:
                dist_progress["problem_hash_mode"] = problem_hash_mode


    # Latest send bundle (path file)
    sb_root = repo_root / "SEND_BUNDLES"
    if not sb_root.exists():
        sb_root = repo_root / "send_bundles"
    latest_sb_path_txt = sb_root / "latest_send_bundle_path.txt"
    latest_sb_path: Optional[str] = None
    try:
        if latest_sb_path_txt.exists():
            latest_sb_path = latest_sb_path_txt.read_text(encoding="utf-8", errors="replace").strip() or None
    except Exception:
        latest_sb_path = None

    # R51: Latest send bundle validation sidecar (written by make_send_bundle)
    latest_sb_val_md = sb_root / "latest_send_bundle_validation.md"
    latest_sb_val_json = sb_root / "latest_send_bundle_validation.json"
    sb_validation: Optional[Dict[str, Any]] = None
    try:
        if latest_sb_val_json.exists():
            j = _safe_json_load(latest_sb_val_json)
            if isinstance(j, dict):
                # keep compact subset
                sb_validation = {
                    "ok": bool(j.get("ok")),
                    "errors": list(j.get("errors") or [])[:50],
                    "warnings": list(j.get("warnings") or [])[:50],
                    "stats": j.get("stats") or {},
                    "checked_at": j.get("checked_at"),
                    "zip_path": j.get("zip_path"),
                }
    except Exception:
        sb_validation = None

    # Latest anim_latest diagnostics sidecar / global pointer snapshot
    anim_summary = _load_anim_latest_summary(repo_root, sb_root)
    mnemo_event_summary = summarize_mnemo_event_log(anim_summary)
    ring_closure_summary = summarize_ring_closure(anim_summary)
    operator_recommendations = build_anim_operator_recommendations(anim_summary)

    # ---- parse autotest summary ----
    autotest_summary: Optional[Dict[str, Any]] = None
    junit_summary: Optional[Dict[str, Any]] = None
    if autotest_dir is not None:
        s = _safe_json_load(autotest_dir / "summary" / "summary.json")
        if isinstance(s, dict):
            autotest_summary = s

        junit_paths = _pick_latest_files(autotest_dir / "pytest", "*.xml", keep_last_n=5)
        # prefer pytest_junit.xml
        junit_paths.sort(key=lambda p: (0 if p.name == "pytest_junit.xml" else 1, -p.stat().st_mtime))
        if junit_paths:
            junit_summary = _parse_junit_xml(junit_paths[0])

    # ---- parse diagnostics meta ----
    diag_meta: Dict[str, Any] = {}
    if diag_dir is not None:
        # root cause meta is the most stable structured output
        p = diag_dir / "reports" / "root_cause_report_meta.json"
        j = _safe_json_load(p)
        if isinstance(j, dict):
            diag_meta["root_cause_report_meta"] = j
        # optional fatal
        fatal = diag_dir / "FATAL.txt"
        if fatal.exists():
            diag_meta["fatal"] = True

    # ---- scan key UI log file ----
    ui_scan: Optional[Dict[str, Any]] = None
    if session_dir is not None:
        # prefer combined metrics jsonl, else any .jsonl
        cand = session_dir / "logs" / "metrics_combined.jsonl"
        if cand.exists():
            ui_scan = _scan_jsonl_levels(cand)
        else:
            jsonl = _pick_latest_files(session_dir / "logs", "*.jsonl", keep_last_n=1)
            if jsonl:
                ui_scan = _scan_jsonl_levels(jsonl[0])

    # ---- summarise run registry tail ----
    rr_brief: Dict[str, Any] = {
        "events_tail": len(rr_events),
        "last_ui": None,
        "last_autotest": None,
        "last_diagnostics": None,
        "last_dist_opt": None,
        "last_send_bundle": None,
        "recent_failures": [],
    }

    def _pick_last(run_type: str) -> Optional[Dict[str, Any]]:
        for ev in reversed(rr_events):
            if str(ev.get("run_type") or "") == run_type and str(ev.get("event") or "") == "run_end":
                return ev
        return None

    rr_brief["last_ui"] = _pick_last("ui_session")
    rr_brief["last_autotest"] = _pick_last("autotest")
    rr_brief["last_diagnostics"] = _pick_last("diagnostics")

    # distributed (Ray/Dask)
    rr_brief["last_dist_opt"] = _pick_last("dist_ray_opt") or _pick_last("dist_dask_opt")

    # last send bundle event
    last_send_bundle_event: Optional[Dict[str, Any]] = None
    last_send_bundle_matches_latest = False
    if latest_sb_path:
        for ev in reversed(rr_events):
            if str(ev.get("event") or "") != "send_bundle_created":
                continue
            if _event_matches_latest_bundle_path(ev, latest_sb_path):
                last_send_bundle_event = ev
                last_send_bundle_matches_latest = True
                break
    if last_send_bundle_event is None:
        for ev in reversed(rr_events):
            if str(ev.get("event") or "") != "send_bundle_created":
                continue
            if _event_seems_local_to_repo(ev, repo_root):
                last_send_bundle_event = ev
                break
    if last_send_bundle_event is None:
        for ev in reversed(rr_events):
            if str(ev.get("event") or "") == "send_bundle_created":
                last_send_bundle_event = ev
                break
    rr_brief["last_send_bundle"] = last_send_bundle_event
    rr_brief["last_send_bundle_matches_latest_path"] = bool(last_send_bundle_matches_latest)
    if latest_sb_path and last_send_bundle_event is not None and not last_send_bundle_matches_latest:
        rr_brief["last_send_bundle_mismatch"] = {
            "latest_send_bundle_path": latest_sb_path,
            "registry_zip_path": last_send_bundle_event.get("zip_path"),
        }

    # failures (recent)
    fails: List[Dict[str, Any]] = []
    for ev in rr_events[-500:]:
        try:
            if _is_run_end_failure(ev):
                fails.append({
                    "ts": ev.get("ts"),
                    "run_type": ev.get("run_type"),
                    "run_id": ev.get("run_id"),
                    "status": ev.get("status"),
                    "rc": ev.get("rc"),
                })
        except Exception:
            continue
    rr_brief["recent_failures"] = fails[-20:]

    # ---- Build JSON summary ----
    severity_counts = {"critical": 0, "warn": 0, "info": 0}
    red_flags: List[str] = []
    mnemo_severity = str(mnemo_event_summary.get("severity") or "")
    if mnemo_severity == "critical":
        severity_counts["critical"] += max(1, int(mnemo_event_summary.get("active_latch_count") or 0))
        red_flags.extend(str(x) for x in (mnemo_event_summary.get("red_flags") or []) if str(x).strip())
    elif mnemo_severity == "warn":
        severity_counts["warn"] += 1
    elif mnemo_severity == "ok":
        severity_counts["info"] += 1

    ring_severity = str(ring_closure_summary.get("severity") or "")
    if ring_severity == "critical":
        severity_counts["critical"] += 1
        red_flags.extend(str(x) for x in (ring_closure_summary.get("red_flags") or []) if str(x).strip())
    elif ring_severity == "warn":
        severity_counts["warn"] += 1
        red_flags.extend(str(x) for x in (ring_closure_summary.get("red_flags") or []) if str(x).strip())
    elif ring_severity == "ok":
        severity_counts["info"] += 1

    summary: Dict[str, Any] = {
        "created_at": _now_iso(),
        "release": RELEASE,
        "platform": platform.platform(),
        "python": sys.version,
        "repo_root": str(repo_root),
        "paths": {
            "run_registry": str(rr_path) if rr_path.exists() else None,
            "session_dir": str(session_dir) if session_dir is not None else None,
            "autotest_dir": str(autotest_dir) if autotest_dir is not None else None,
            "diagnostics_dir": str(diag_dir) if diag_dir is not None else None,
            "dist_dir": str(dist_dir) if dist_dir is not None else None,
            "latest_send_bundle_path": latest_sb_path,
            "latest_send_bundle_validation_md": str(latest_sb_val_md) if latest_sb_val_md.exists() else None,
            "latest_send_bundle_validation_json": str(latest_sb_val_json) if latest_sb_val_json.exists() else None,
            "latest_anim_pointer_diagnostics_json": anim_summary.get("diagnostics_json_path"),
            "latest_anim_pointer_diagnostics_md": anim_summary.get("diagnostics_md_path"),
        },
        "run_registry": rr_brief,
        "ui_scan": ui_scan,
        "autotest_summary": autotest_summary,
        "junit": junit_summary,
        "diagnostics": diag_meta,
        "dist_progress": dist_progress,
        "severity_counts": severity_counts,
        "red_flags": red_flags,
        "send_bundle_validation": sb_validation,
        "anim_latest": anim_summary,
        "mnemo_event_log": mnemo_event_summary,
        "ring_closure": ring_closure_summary,
        "operator_recommendations": operator_recommendations,
    }

    # ---- Markdown ----
    def _fmt_path(p: Optional[str]) -> str:
        return p if p else "(не найдено)"

    lines: List[str] = []
    lines.append(f"# Разбор замечаний ({RELEASE})")
    lines.append("")
    lines.append(f"Сформировано: **{summary['created_at']}**")
    lines.append("")
    lines.append("## Быстрые ссылки")
    lines.append(f"- Корень проекта: `{repo_root}`")
    lines.append(f"- Сессия интерфейса: `{_fmt_path(summary['paths']['session_dir'])}`")
    lines.append(f"- Прогон автотестов: `{_fmt_path(summary['paths']['autotest_dir'])}`")
    lines.append(f"- Прогон проверок: `{_fmt_path(summary['paths']['diagnostics_dir'])}`")
    lines.append(f"- Папка оптимизации: `{_fmt_path(summary['paths'].get('dist_dir'))}`")
    lines.append(f"- Журнал запусков: `{_fmt_path(summary['paths']['run_registry'])}`")
    lines.append(f"- Актуальный архив проекта: `{_fmt_path(summary['paths']['latest_send_bundle_path'])}`")
    lines.append(f"- Проверка актуального архива: `{_fmt_path(summary['paths'].get('latest_send_bundle_validation_md'))}`")
    lines.append(f"- Данные последней анимации, JSON: `{_fmt_path(summary['paths'].get('latest_anim_pointer_diagnostics_json'))}`")
    lines.append(f"- Данные последней анимации, Markdown: `{_fmt_path(summary['paths'].get('latest_anim_pointer_diagnostics_md'))}`")

    # Distributed optimization summary (latest)
    if summary.get("dist_progress"):
        dp = summary["dist_progress"]
        lines.append("")
        lines.append("## Оптимизация")
        lines.append(f"Состояние: **{dp.get('status')}**")
        lines.append(
            f"Завершено: {dp.get('completed')}  Выполняется: {dp.get('in_flight')}  Из кэша: {dp.get('cached_hits')}  Пропущено дублей: {dp.get('duplicates_skipped')}"
        )
        if dp.get("problem_hash"):
            lines.append(f"Область задачи: `{dp.get('problem_hash_short') or dp.get('problem_hash')}`")
            if dp.get("problem_hash_short") and dp.get("problem_hash_short") != dp.get("problem_hash"):
                lines.append(f"Полный ключ области: `{dp.get('problem_hash')}`")
        if dp.get("problem_hash_mode"):
            lines.append(f"Режим хэша: `{dp.get('problem_hash_mode')}`")
        if dp.get("hv") is not None:
            lines.append(f"HV: {dp.get('hv')}")
        if (dp.get("best_obj1") is not None) or (dp.get("best_obj2") is not None):
            lines.append(f"Best obj1: {dp.get('best_obj1')}  Best obj2: {dp.get('best_obj2')}")
        if dp.get("last_error"):
            lines.append(f"Last error: `{dp.get('last_error')}`")

    lines.append("")
    lines.append("## Run Registry (tail)")
    lines.append(f"Events read: **{rr_brief['events_tail']}**")
    if rr_brief.get("last_ui"):
        ev = rr_brief["last_ui"]
        extra_ui: list[str] = []
        if ev.get("launcher_stop_requested") is not None:
            extra_ui.append(f"stop_requested={ev.get('launcher_stop_requested')}")
        if ev.get("launcher_stop_source"):
            extra_ui.append(f"stop_source={ev.get('launcher_stop_source')}")
        if ev.get("launcher_ready_source"):
            extra_ui.append(f"ready_source={ev.get('launcher_ready_source')}")
        tail = (" " + " ".join(extra_ui)) if extra_ui else ""
        lines.append(f"- Last UI: ts={ev.get('ts')} status={ev.get('status')} rc={ev.get('rc')} run_id={ev.get('run_id')}{tail}")
    if rr_brief.get("last_autotest"):
        ev = rr_brief["last_autotest"]
        lines.append(f"- Last Autotest: ts={ev.get('ts')} status={ev.get('status')} rc={ev.get('rc')} run_id={ev.get('run_id')}")
    if rr_brief.get("last_diagnostics"):
        ev = rr_brief["last_diagnostics"]
        lines.append(f"- Last Diagnostics: ts={ev.get('ts')} status={ev.get('status')} rc={ev.get('rc')} run_id={ev.get('run_id')}")
    if rr_brief.get("last_dist_opt"):
        ev = rr_brief["last_dist_opt"]
        lines.append(f"- Last DistOpt: ts={ev.get('ts')} status={ev.get('status')} rc={ev.get('rc')} run_id={ev.get('run_id')}")
    if rr_brief.get("last_send_bundle"):
        ev = rr_brief["last_send_bundle"]
        lines.append(
            f"- Last Send Bundle: ts={ev.get('ts')} zip={ev.get('zip_path')} sha256={ev.get('sha256')}"
            + (
                f" validation_ok={ev.get('validation_ok')} errors={ev.get('validation_errors')} warnings={ev.get('validation_warnings')}"
                if (ev.get('validation_ok') is not None)
                else ""
            )
        )
        if rr_brief.get("last_send_bundle_matches_latest_path") is not None:
            lines.append(f"- Last Send Bundle matches latest_send_bundle_path: `{rr_brief.get('last_send_bundle_matches_latest_path')}`")
        if rr_brief.get("last_send_bundle_mismatch"):
            mm = rr_brief.get("last_send_bundle_mismatch") or {}
            lines.append(
                f"- Несовпадение архива: latest_send_bundle_path=`{_fmt_path(mm.get('latest_send_bundle_path'))}`, а журнал выбрал zip=`{_fmt_path(mm.get('registry_zip_path'))}`"
            )

    # R51: Validation summary (from latest sidecar)
    if sb_validation is not None:
        lines.append("")
        lines.append("## Проверка актуального архива проекта")
        lines.append(f"Успешно: **{sb_validation.get('ok')}**")
        stt = sb_validation.get('stats') or {}
        try:
            lines.append(
                f"Состав: zip={stt.get('zip_entries')} проверено={stt.get('manifest_checked')} sha_расхождений={stt.get('manifest_sha_mismatch')} size_расхождений={stt.get('manifest_size_mismatch')}"
            )
        except Exception:
            pass
        if sb_validation.get('errors'):
            lines.append("Ошибки:")
            for e in (sb_validation.get('errors') or [])[:10]:
                lines.append(f"- {e}")
        if sb_validation.get('warnings'):
            lines.append("Предупреждения:")
            for w in (sb_validation.get('warnings') or [])[:10]:
                lines.append(f"- {w}")

    lines.append("")
    lines.append("## События мнемосхемы")
    mnemo = summary.get("mnemo_event_log") or {}
    lines.append(f"- Важность: `{mnemo.get('severity') or 'missing'}`")
    lines.append(f"- Сводка: `{mnemo.get('headline') or '—'}`")
    if mnemo.get("ref") or mnemo.get("path"):
        lines.append(
            f"- Журнал событий: `{mnemo.get('ref') or '—'}` → `{_fmt_path(mnemo.get('path'))}` есть=`{mnemo.get('exists')}` схема=`{mnemo.get('schema_version') or '—'}` обновлено UTC=`{mnemo.get('updated_utc') or '—'}`"
        )
    if mnemo.get("current_mode"):
        lines.append(f"- Текущий режим: `{mnemo.get('current_mode')}`")
    if mnemo.get("event_count") is not None:
        lines.append(
            f"- Состояние событий: всего=`{mnemo.get('event_count')}` активно=`{mnemo.get('active_latch_count')}` принято=`{mnemo.get('acknowledged_latch_count')}`"
        )
    recent_titles = [str(x) for x in (mnemo.get("recent_titles") or []) if str(x).strip()]
    if recent_titles:
        lines.append(f"- Последние события: {' | '.join(recent_titles[:3])}")
    for flag in list(mnemo.get("red_flags") or [])[:3]:
        lines.append(f"- Предупреждение: `{flag}`")

    if operator_recommendations:
        lines.append("")
        lines.append("## Рекомендуемые действия")
        for idx, item in enumerate(operator_recommendations, start=1):
            lines.append(f"{idx}. {item}")

    lines.append("")
    lines.append("## Последняя анимация")
    anim = summary.get("anim_latest") or {}
    lines.append(f"- Источник: {anim.get('source') or '—'}")
    lines.append(f"- Доступна: {bool(anim.get('anim_latest_available'))}")
    if anim.get("scenario_kind"):
        lines.append(f"- Тип сценария: `{anim.get('scenario_kind')}`")
    lines.append(f"- Общий указатель: `{_fmt_path(anim.get('anim_latest_global_pointer_json'))}`")
    lines.append(f"- Указатель: `{_fmt_path(anim.get('anim_latest_pointer_json'))}`")
    lines.append(f"- Файл анимации: `{_fmt_path(anim.get('anim_latest_npz_path'))}`")
    if anim.get('anim_latest_road_csv_ref') or anim.get('anim_latest_road_csv_path'):
        lines.append(f"- anim_latest_road_csv: `{anim.get('anim_latest_road_csv_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_road_csv_path'))}` exists=`{anim.get('anim_latest_road_csv_exists')}`")
    if anim.get('anim_latest_axay_csv_ref') or anim.get('anim_latest_axay_csv_path'):
        lines.append(f"- anim_latest_axay_csv: `{anim.get('anim_latest_axay_csv_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_axay_csv_path'))}` exists=`{anim.get('anim_latest_axay_csv_exists')}`")
    if anim.get('anim_latest_scenario_json_ref') or anim.get('anim_latest_scenario_json_path'):
        lines.append(f"- anim_latest_scenario_json: `{anim.get('anim_latest_scenario_json_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_scenario_json_path'))}` exists=`{anim.get('anim_latest_scenario_json_exists')}`")
    if anim.get('anim_latest_contract_sidecar_ref') or anim.get('anim_latest_contract_sidecar_path'):
        lines.append(f"- anim_latest_contract_sidecar: `{anim.get('anim_latest_contract_sidecar_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_contract_sidecar_path'))}` exists=`{anim.get('anim_latest_contract_sidecar_exists')}`")
    if anim.get('anim_latest_contract_validation_json_ref') or anim.get('anim_latest_contract_validation_json_path'):
        lines.append(f"- anim_latest_contract_validation_json: `{anim.get('anim_latest_contract_validation_json_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_contract_validation_json_path'))}` exists=`{anim.get('anim_latest_contract_validation_json_exists')}`")
    if anim.get('anim_latest_contract_validation_md_ref') or anim.get('anim_latest_contract_validation_md_path'):
        lines.append(f"- anim_latest_contract_validation_md: `{anim.get('anim_latest_contract_validation_md_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_contract_validation_md_path'))}` exists=`{anim.get('anim_latest_contract_validation_md_exists')}`")
    if anim.get('anim_latest_hardpoints_source_of_truth_ref') or anim.get('anim_latest_hardpoints_source_of_truth_path'):
        lines.append(f"- anim_latest_hardpoints_source_of_truth: `{anim.get('anim_latest_hardpoints_source_of_truth_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_hardpoints_source_of_truth_path'))}` exists=`{anim.get('anim_latest_hardpoints_source_of_truth_exists')}`")
    if anim.get('anim_latest_cylinder_packaging_passport_ref') or anim.get('anim_latest_cylinder_packaging_passport_path'):
        lines.append(f"- anim_latest_cylinder_packaging_passport: `{anim.get('anim_latest_cylinder_packaging_passport_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_cylinder_packaging_passport_path'))}` exists=`{anim.get('anim_latest_cylinder_packaging_passport_exists')}`")
    if anim.get('anim_latest_geometry_acceptance_json_ref') or anim.get('anim_latest_geometry_acceptance_json_path'):
        lines.append(f"- anim_latest_geometry_acceptance_json: `{anim.get('anim_latest_geometry_acceptance_json_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_geometry_acceptance_json_path'))}` exists=`{anim.get('anim_latest_geometry_acceptance_json_exists')}`")
    if anim.get('anim_latest_geometry_acceptance_md_ref') or anim.get('anim_latest_geometry_acceptance_md_path'):
        lines.append(f"- anim_latest_geometry_acceptance_md: `{anim.get('anim_latest_geometry_acceptance_md_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_geometry_acceptance_md_path'))}` exists=`{anim.get('anim_latest_geometry_acceptance_md_exists')}`")
    if anim.get('anim_latest_road_contract_web_ref') or anim.get('anim_latest_road_contract_web_path'):
        lines.append(f"- anim_latest_road_contract_web: `{anim.get('anim_latest_road_contract_web_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_road_contract_web_path'))}` exists=`{anim.get('anim_latest_road_contract_web_exists')}`")
    if anim.get('anim_latest_road_contract_desktop_ref') or anim.get('anim_latest_road_contract_desktop_path'):
        lines.append(f"- anim_latest_road_contract_desktop: `{anim.get('anim_latest_road_contract_desktop_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_road_contract_desktop_path'))}` exists=`{anim.get('anim_latest_road_contract_desktop_exists')}`")
    if anim.get('anim_latest_capture_export_manifest_ref') or anim.get('anim_latest_capture_export_manifest_path'):
        lines.append(f"- anim_latest_capture_export_manifest: `{anim.get('anim_latest_capture_export_manifest_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_capture_export_manifest_path'))}` exists=`{anim.get('anim_latest_capture_export_manifest_exists')}` handoff=`{anim.get('anim_latest_capture_export_manifest_handoff_id') or '—'}`")
    if anim.get('anim_latest_frame_budget_evidence_ref') or anim.get('anim_latest_frame_budget_evidence_path'):
        lines.append(f"- anim_latest_frame_budget_evidence: `{anim.get('anim_latest_frame_budget_evidence_ref') or '—'}` → `{_fmt_path(anim.get('anim_latest_frame_budget_evidence_path'))}` exists=`{anim.get('anim_latest_frame_budget_evidence_exists')}` handoff=`{anim.get('anim_latest_frame_budget_evidence_handoff_id') or '—'}`")
    if anim.get('browser_perf_registry_snapshot_ref') or anim.get('browser_perf_registry_snapshot_path'):
        lines.append(f"- browser_perf_registry_snapshot: `{anim.get('browser_perf_registry_snapshot_ref') or '—'}` → `{_fmt_path(anim.get('browser_perf_registry_snapshot_path'))}` exists=`{anim.get('browser_perf_registry_snapshot_exists')}` in_bundle=`{anim.get('browser_perf_registry_snapshot_in_bundle')}`")
    if anim.get('browser_perf_previous_snapshot_ref') or anim.get('browser_perf_previous_snapshot_path'):
        lines.append(f"- browser_perf_previous_snapshot: `{anim.get('browser_perf_previous_snapshot_ref') or '—'}` → `{_fmt_path(anim.get('browser_perf_previous_snapshot_path'))}` exists=`{anim.get('browser_perf_previous_snapshot_exists')}` in_bundle=`{anim.get('browser_perf_previous_snapshot_in_bundle')}`")
    if anim.get('browser_perf_contract_ref') or anim.get('browser_perf_contract_path'):
        lines.append(f"- browser_perf_contract: `{anim.get('browser_perf_contract_ref') or '—'}` → `{_fmt_path(anim.get('browser_perf_contract_path'))}` exists=`{anim.get('browser_perf_contract_exists')}` in_bundle=`{anim.get('browser_perf_contract_in_bundle')}`")
    if anim.get('browser_perf_evidence_report_ref') or anim.get('browser_perf_evidence_report_path'):
        lines.append(f"- browser_perf_evidence_report: `{anim.get('browser_perf_evidence_report_ref') or '—'}` → `{_fmt_path(anim.get('browser_perf_evidence_report_path'))}` exists=`{anim.get('browser_perf_evidence_report_exists')}` in_bundle=`{anim.get('browser_perf_evidence_report_in_bundle')}`")
    if anim.get('browser_perf_comparison_report_ref') or anim.get('browser_perf_comparison_report_path'):
        lines.append(f"- browser_perf_comparison_report: `{anim.get('browser_perf_comparison_report_ref') or '—'}` → `{_fmt_path(anim.get('browser_perf_comparison_report_path'))}` exists=`{anim.get('browser_perf_comparison_report_exists')}` in_bundle=`{anim.get('browser_perf_comparison_report_in_bundle')}`")
    if anim.get('browser_perf_trace_ref') or anim.get('browser_perf_trace_path'):
        lines.append(f"- browser_perf_trace: `{anim.get('browser_perf_trace_ref') or '—'}` → `{_fmt_path(anim.get('browser_perf_trace_path'))}` exists=`{anim.get('browser_perf_trace_exists')}` in_bundle=`{anim.get('browser_perf_trace_in_bundle')}`")
    if anim.get('browser_perf_status') or anim.get('browser_perf_level'):
        lines.append(f"- browser_perf_status: `{anim.get('browser_perf_status') or '—'}` / level=`{anim.get('browser_perf_level') or '—'}` / components=`{anim.get('browser_perf_component_count')}` / wakeups=`{anim.get('browser_perf_total_wakeups')}` / dup=`{anim.get('browser_perf_total_duplicate_guard_hits')}` / max_idle_poll_ms=`{anim.get('browser_perf_max_idle_poll_ms')}`")
    if anim.get('browser_perf_evidence_status') or anim.get('browser_perf_evidence_level'):
        lines.append(f"- browser_perf_evidence_status: `{anim.get('browser_perf_evidence_status') or '—'}` / level=`{anim.get('browser_perf_evidence_level') or '—'}` / bundle_ready=`{anim.get('browser_perf_bundle_ready')}` / snapshot_contract_match=`{anim.get('browser_perf_snapshot_contract_match')}`")
    if anim.get('browser_perf_comparison_status') or anim.get('browser_perf_comparison_level'):
        lines.append(f"- browser_perf_comparison_status: `{anim.get('browser_perf_comparison_status') or '—'}` / level=`{anim.get('browser_perf_comparison_level') or '—'}` / ready=`{anim.get('browser_perf_comparison_ready')}` / changed=`{anim.get('browser_perf_comparison_changed')}` / Δwakeups=`{anim.get('browser_perf_comparison_delta_total_wakeups')}` / Δdup=`{anim.get('browser_perf_comparison_delta_total_duplicate_guard_hits')}` / Δrender=`{anim.get('browser_perf_comparison_delta_total_render_count')}` / Δmax_idle_poll_ms=`{anim.get('browser_perf_comparison_delta_max_idle_poll_ms')}`")
    lines.append(f"- anim_latest_visual_cache_token: `{anim.get('anim_latest_visual_cache_token') or '—'}`")
    _reload_inputs = list(anim.get('anim_latest_visual_reload_inputs') or [])
    lines.append(
        f"- anim_latest_visual_reload_inputs: {', '.join(str(x) for x in _reload_inputs) if _reload_inputs else '—'}"
    )
    if any(anim.get(key) not in (None, "", [], {}) for key in ("ring_closure_policy", "ring_closure_applied", "ring_seam_open", "ring_seam_max_jump_m", "ring_raw_seam_max_jump_m")):
        lines.append(
            f"- Замыкание кольца: режим=`{anim.get('ring_closure_policy') or '—'}`"
            f" / применено=`{anim.get('ring_closure_applied')}`"
            f" / шов открыт=`{anim.get('ring_seam_open')}`"
            f" / скачок шва, м=`{anim.get('ring_seam_max_jump_m') if anim.get('ring_seam_max_jump_m') is not None else '—'}`"
            f" / исходный скачок, м=`{anim.get('ring_raw_seam_max_jump_m') if anim.get('ring_raw_seam_max_jump_m') is not None else '—'}`"
        )
    lines.append(f"- anim_latest_updated_utc: `{anim.get('anim_latest_updated_utc') or '—'}`")
    if anim.get('anim_latest_usable') is not None:
        lines.append(f"- anim_latest_usable: `{anim.get('anim_latest_usable')}`")
    if anim.get('anim_latest_pointer_json_exists') is not None:
        lines.append(f"- anim_latest_pointer_json_exists: `{anim.get('anim_latest_pointer_json_exists')}`")
    if anim.get('anim_latest_npz_exists') is not None:
        lines.append(f"- anim_latest_npz_exists: `{anim.get('anim_latest_npz_exists')}`")
    for msg in list(anim.get('anim_latest_issues') or [])[:6]:
        lines.append(f"- issue: `{msg}`")
    if anim.get('error'):
        lines.append(f"- error: `{anim.get('error')}`")

    if rr_brief.get("recent_failures"):
        lines.append("")
        lines.append("### Recent failures")
        for f in rr_brief["recent_failures"]:
            lines.append(f"- {f.get('ts')}: {f.get('run_type')} {f.get('run_id')} status={f.get('status')} rc={f.get('rc')}")

    lines.append("")
    lines.append("## UI logs (quick scan)")
    if ui_scan is None:
        lines.append("UI scan: (not available)")
    else:
        lines.append(f"Log file: `{ui_scan.get('path')}`")
        lines.append(f"Lines scanned: **{ui_scan.get('lines')}** ({ui_scan.get('scan_note') or 'full'})")
        levels = ui_scan.get("levels") or {}
        if isinstance(levels, dict) and levels:
            lv = ", ".join([f"{k}={v}" for k, v in sorted(levels.items(), key=lambda kv: kv[0])])
            lines.append(f"Levels: {lv}")
        last_err = ui_scan.get("last_errors") or []
        if last_err:
            lines.append("")
            lines.append("Last errors (tail):")
            for e in last_err:
                lines.append(f"- {e.get('ts')}: event={e.get('event')} msg={e.get('msg')}")

    lines.append("")
    lines.append("## Autotest")
    if autotest_summary is None:
        lines.append("No autotest summary found.")
    else:
        lines.append(f"OK: **{autotest_summary.get('ok')}**")
        lines.append(f"RC: **{autotest_summary.get('rc')}**")
        lines.append(f"Level: `{autotest_summary.get('level')}`")
        lines.append(f"Finished: `{autotest_summary.get('finished_at')}`")
        lines.append(f"Run dir: `{autotest_summary.get('run_dir')}`")

    if junit_summary is not None:
        lines.append("")
        lines.append("### Pytest JUnit")
        lines.append(
            f"tests={junit_summary.get('tests')} failures={junit_summary.get('failures')} errors={junit_summary.get('errors')} skipped={junit_summary.get('skipped')} time={junit_summary.get('time')}s"
        )
        failing = junit_summary.get("failing") or []
        if failing:
            lines.append("Failing testcases (up to 50):")
            for tc in failing:
                lines.append(f"- {tc.get('classname')}::{tc.get('name')} ({tc.get('kind')}) {tc.get('message')}")

    lines.append("")
    lines.append("## Diagnostics")
    if diag_dir is None:
        lines.append("No diagnostics run found.")
    else:
        lines.append(f"Run dir: `{diag_dir}`")
        if diag_meta.get("fatal"):
            lines.append("⚠️ FATAL.txt present (run crashed).")
        rc_meta = diag_meta.get("root_cause_report_meta")
        if isinstance(rc_meta, dict):
            lines.append(
                f"root_cause_report: rc={rc_meta.get('returncode')} duration_s={rc_meta.get('duration_s')}"
            )

    lines.append("")
    lines.append("## Next steps")
    lines.append("1) If something failed: open the corresponding run dir and check stdout/stderr + logs.")
    lines.append("2) For UI issues: inspect `session_dir/logs/*.jsonl` and `launcher_streamlit.log`.")
    lines.append("3) If you send the Send Bundle ZIP: this triage report + manifest help to quickly pinpoint the problem.")

    md = "\n".join(lines) + "\n"
    return md, summary


@dataclass
class TriagePaths:
    md_path: Path
    json_path: Path
    latest_md: Path
    latest_json: Path


def write_triage_report(out_dir: Path, md_text: str, json_obj: Dict[str, Any], *, stamp: Optional[str] = None) -> TriagePaths:
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or _ts()

    md_path = out_dir / f"TRIAGE_{stamp}.md"
    json_path = out_dir / f"TRIAGE_{stamp}.json"
    latest_md = out_dir / "latest_triage_report.md"
    latest_json = out_dir / "latest_triage_report.json"

    md_path.write_text(md_text, encoding="utf-8", errors="replace")
    json_path.write_text(json.dumps(json_obj, ensure_ascii=False, indent=2), encoding="utf-8", errors="replace")

    # best-effort pointers
    try:
        latest_md.write_text(md_text, encoding="utf-8", errors="replace")
        latest_json.write_text(json.dumps(json_obj, ensure_ascii=False, indent=2), encoding="utf-8", errors="replace")
    except Exception:
        pass

    return TriagePaths(md_path=md_path, json_path=json_path, latest_md=latest_md, latest_json=latest_json)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a best-effort triage report (md+json)")
    ap.add_argument("--out_dir", default="send_bundles", help="Куда писать triage report (относительно repo root)")
    ap.add_argument("--keep_last_n", type=int, default=3, help="Сколько последних RUN_* учитывать")
    ap.add_argument("--primary_session_dir", default=None, help="Явно указать UI session dir")
    ap.add_argument("--print_paths", action="store_true", help="Напечатать пути к созданным файлам")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = (repo_root / str(args.out_dir)).resolve()

    md, js = generate_triage_report(
        repo_root,
        keep_last_n=int(args.keep_last_n),
        primary_session_dir=Path(args.primary_session_dir) if args.primary_session_dir else None,
    )
    paths = write_triage_report(out_dir, md, js)

    if args.print_paths:
        print(str(paths.md_path))
        print(str(paths.json_path))
        print(str(paths.latest_md))
        print(str(paths.latest_json))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
