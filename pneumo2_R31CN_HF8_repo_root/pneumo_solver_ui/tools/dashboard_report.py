#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dashboard_report.py

R53: единый HTML-отчёт по проверке проекта.

Цель: дать человеку одну понятную точку входа после запуска. Отчёт кладётся в
архив проекта и сохраняется рядом с ним.

Отчёт показывает, если данные доступны:
- разбор замечаний;
- проверку архива проекта;
- сведения о последней анимации;
- отчёт SQLite-метрик;
- реестр запусков.

Запуск:
  python -m pneumo_solver_ui.tools.dashboard_report --out_dir send_bundles --print_paths

Из make_send_bundle.py:
  - положить отчёт в ZIP: dashboard/index.html, dashboard/dashboard.json;
  - записать рядом: send_bundles/latest_dashboard.html / .json.

Правила:
- сбой отчёта не должен ломать создание архива;
- без внешних шаблонов: обычное форматирование строк Python.

"""

from __future__ import annotations

import argparse
import json
import os
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pneumo_solver_ui.optimization_scope_compare import (
    compare_optimizer_scope_sources,
    evaluate_optimizer_scope_gate,
    extract_optimizer_scope_from_health,
    extract_optimizer_scope_from_run_scope,
    extract_optimizer_scope_from_triage,
    extract_optimizer_scope_from_validation,
    optimizer_scope_export_source_name,
)

from .send_bundle_contract import (
    ANIM_DIAG_JSON,
    ANIM_DIAG_MD,
    ANIM_DIAG_SIDECAR_JSON,
    ANIM_DIAG_SIDECAR_MD,
    anim_has_signal,
    choose_anim_snapshot,
    normalize_anim_dashboard_obj,
    render_anim_latest_md,
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


def _safe_read_text(path: Path, max_bytes: int = 4_000_000) -> str:
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



def _safe_zip_read_text(zip_path: Optional[Path], arcname: str, max_bytes: int = 4_000_000) -> str:
    if zip_path is None:
        return ""
    try:
        with zipfile.ZipFile(Path(zip_path), "r") as zf:
            b = zf.read(arcname)
        if len(b) > max_bytes:
            b = b[:max_bytes] + b"\n\n...TRUNCATED...\n"
        return b.decode("utf-8", errors="replace")
    except Exception:
        return ""



def _safe_zip_json_load(zip_path: Optional[Path], arcname: str) -> Any:
    txt = _safe_zip_read_text(zip_path, arcname)
    if not txt:
        return None
    try:
        return json.loads(txt)
    except Exception:
        return None



def _html_escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )



def _pretty_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return repr(obj)



def _short_token(token: str, n: int = 16) -> str:
    tok = str(token or "")
    if not tok:
        return ""
    return tok if len(tok) <= n else tok[:n] + "…"



def generate_dashboard_report(
    repo_root: Path,
    out_dir: Path,
    *,
    zip_path: Optional[Path] = None,
    keep_last_n: int = 3,
) -> Tuple[str, Dict[str, Any]]:
    """Generate dashboard HTML + JSON (best-effort).

    Reads sidecar files written by make_send_bundle:
      - latest_triage_report.md/.json
      - latest_send_bundle_validation.md/.json
      - latest_anim_pointer_diagnostics.md/.json
      - latest_sqlite_report.md/.json (optional)

    If sidecars are missing, it tries to generate some of them on the fly.
    """

    repo_root = Path(repo_root).resolve()
    out_dir = Path(out_dir).resolve()
    zip_path = Path(zip_path).resolve() if zip_path else None

    rep: Dict[str, Any] = {
        "schema": "dashboard_report",
        "schema_version": "1.0.0",
        "release": RELEASE,
        "generated_at": _now_iso(),
        "repo_root": str(repo_root),
        "out_dir": str(out_dir),
        "zip_path": str(zip_path) if zip_path else None,
        "sections": {},
        "errors": [],
        "warnings": [],
        "anim_latest": {},
        "optimizer_scope": {},
        "optimizer_scope_gate": {},
    }

    # -----------------------------
    # Load triage
    # -----------------------------
    triage_md_path = out_dir / "latest_triage_report.md"
    triage_json_path = out_dir / "latest_triage_report.json"

    triage_md = ""
    triage_json: Any = None

    if triage_md_path.exists():
        triage_md = _safe_read_text(triage_md_path)
    if triage_json_path.exists():
        triage_json = _safe_json_load(triage_json_path)

    if not triage_md:
        try:
            from pneumo_solver_ui.tools.triage_report import generate_triage_report

            triage_md, triage_json = generate_triage_report(repo_root, keep_last_n=int(keep_last_n))
            rep["warnings"].append("файл разбора замечаний не найден; сформирован заново")
        except Exception:
            rep["errors"].append("failed to load/generate triage")
            triage_md = "(triage not available)\n" + traceback.format_exc()
            triage_json = {"error": "triage_failed"}

    rep["sections"]["triage"] = {
        "md_path": str(triage_md_path) if triage_md_path.exists() else None,
        "json_path": str(triage_json_path) if triage_json_path.exists() else None,
    }

    # -----------------------------
    # Load validation
    # -----------------------------
    val_md_path = out_dir / "latest_send_bundle_validation.md"
    val_json_path = out_dir / "latest_send_bundle_validation.json"

    val_md = ""
    val_json: Any = None

    if val_md_path.exists():
        val_md = _safe_read_text(val_md_path)
    if val_json_path.exists():
        val_json = _safe_json_load(val_json_path)

    if val_json is None and zip_path is not None:
        try:
            from pneumo_solver_ui.tools.validate_send_bundle import validate_send_bundle

            vres = validate_send_bundle(Path(zip_path))
            val_md = vres.report_md
            val_json = vres.report_json
            rep["warnings"].append("файл проверки архива не найден; ZIP проверен заново")
        except Exception:
            rep["errors"].append("failed to load/generate validation")
            val_md = "(validation not available)\n" + traceback.format_exc()
            val_json = {"error": "validation_failed"}

    rep["sections"]["validation"] = {
        "md_path": str(val_md_path) if val_md_path.exists() else None,
        "json_path": str(val_json_path) if val_json_path.exists() else None,
    }

    optimizer_scope_sources: Dict[str, Dict[str, Any]] = {}
    triage_scope = extract_optimizer_scope_from_triage(triage_json)
    if triage_scope:
        optimizer_scope_sources[str(triage_scope.get("source") or "triage")] = triage_scope

    validation_scope = extract_optimizer_scope_from_validation(val_json)
    if validation_scope:
        optimizer_scope_sources[str(validation_scope.get("source") or "validation")] = validation_scope

    if zip_path is not None:
        health_scope = extract_optimizer_scope_from_health(_safe_zip_json_load(zip_path, "health/health_report.json"))
        if health_scope:
            optimizer_scope_sources[str(health_scope.get("source") or "health")] = health_scope
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for arcname in sorted(
                    name
                    for name in zf.namelist()
                    if name == "run_scope.json" or name.endswith("/export/run_scope.json")
                ):
                    export_scope = extract_optimizer_scope_from_run_scope(
                        _safe_zip_json_load(zip_path, arcname),
                        source=optimizer_scope_export_source_name(arcname),
                        source_path=arcname,
                    )
                    if export_scope:
                        optimizer_scope_sources[str(export_scope.get("source") or arcname)] = export_scope
        except Exception:
            rep["warnings"].append("не удалось проверить файлы области оптимизации из ZIP")

    optimizer_scope = compare_optimizer_scope_sources(
        optimizer_scope_sources,
        preferred_order=("triage", "health", "validation", "export"),
    )
    if optimizer_scope:
        rep["optimizer_scope"] = optimizer_scope
        optimizer_scope_gate = evaluate_optimizer_scope_gate(optimizer_scope)
        rep["optimizer_scope_gate"] = optimizer_scope_gate
        for issue in optimizer_scope.get("issues") or []:
            msg = str(issue).strip()
            if msg and msg not in rep["warnings"]:
                rep["warnings"].append(msg)
        if optimizer_scope_gate.get("release_risk"):
            risk_msg = (
                "риск выпуска по области оптимизации: "
                f"{optimizer_scope_gate.get('release_gate_reason') or 'обнаружено расхождение'}"
            )
            if risk_msg not in rep["warnings"]:
                rep["warnings"].append(risk_msg)

    # -----------------------------
    # Load anim_latest diagnostics
    # -----------------------------
    anim_md_path = out_dir / ANIM_DIAG_SIDECAR_MD
    anim_json_path = out_dir / ANIM_DIAG_SIDECAR_JSON

    anim_md = ""
    anim_json: Any = None

    if anim_md_path.exists():
        anim_md = _safe_read_text(anim_md_path)
    elif zip_path is not None:
        anim_md = _safe_zip_read_text(zip_path, ANIM_DIAG_MD)
        if anim_md:
            rep["warnings"].append("отчёт последней анимации рядом с архивом не найден; используется копия из ZIP")

    if anim_json_path.exists():
        anim_json = _safe_json_load(anim_json_path)
    elif zip_path is not None:
        anim_json = _safe_zip_json_load(zip_path, ANIM_DIAG_JSON)
        if anim_json is not None:
            rep["warnings"].append("данные последней анимации рядом с архивом не найдены; используется копия из ZIP")

    if anim_json is None and isinstance(val_json, dict):
        anim_json = val_json.get("anim_latest")
        if isinstance(anim_json, dict):
            rep["warnings"].append("данные последней анимации не найдены; используется сводка проверки архива")

    val_anim_json = val_json.get("anim_latest") if isinstance(val_json, dict) else None
    anim_norm = normalize_anim_dashboard_obj(anim_json)
    val_anim_norm = normalize_anim_dashboard_obj(val_anim_json)
    canonical_anim = choose_anim_snapshot(
        {
            key: value
            for key, value in (
                ("diagnostics", anim_norm if isinstance(anim_norm, dict) else None),
                ("validation", val_anim_norm if isinstance(val_anim_norm, dict) else None),
            )
            if isinstance(value, dict)
        },
        preferred_order=("diagnostics", "validation"),
    )
    if isinstance(canonical_anim, dict):
        anim_norm = canonical_anim
    if (not anim_has_signal(normalize_anim_dashboard_obj(anim_json))) and anim_has_signal(val_anim_norm):
        anim_json = val_anim_json
        anim_norm = val_anim_norm
        rep["warnings"].append("anim_latest ZIP/sidecar diagnostics are empty; using validation summary")
        anim_md = render_anim_latest_md(anim_norm)
    elif isinstance(anim_norm, dict) and (not anim_md or anim_norm != normalize_anim_dashboard_obj(anim_json)):
        anim_md = render_anim_latest_md(anim_norm)

    rep["sections"]["anim_latest"] = {
        "md_path": str(anim_md_path) if anim_md_path.exists() else None,
        "json_path": str(anim_json_path) if anim_json_path.exists() else None,
        "md_zip_path": ANIM_DIAG_MD if (zip_path is not None and _safe_zip_read_text(zip_path, ANIM_DIAG_MD)) else None,
        "json_zip_path": ANIM_DIAG_JSON if isinstance(_safe_zip_json_load(zip_path, ANIM_DIAG_JSON), dict) else None,
    }
    rep["anim_latest"] = anim_norm

    # -----------------------------
    # Load sqlite metrics report (optional)
    # -----------------------------
    sql_md_path = out_dir / "latest_sqlite_report.md"
    sql_json_path = out_dir / "latest_sqlite_report.json"

    sql_md = ""
    sql_json: Any = None

    if sql_md_path.exists():
        sql_md = _safe_read_text(sql_md_path)
    if sql_json_path.exists():
        sql_json = _safe_json_load(sql_json_path)

    rep["sections"]["sqlite_metrics"] = {
        "md_path": str(sql_md_path) if sql_md_path.exists() else None,
        "json_path": str(sql_json_path) if sql_json_path.exists() else None,
    }

    # -----------------------------
    # Run registry index/tail (optional)
    # -----------------------------
    runs_dir = repo_root / "runs"
    rr_index_path = runs_dir / "index.json"
    rr_jsonl_path = runs_dir / "run_registry.jsonl"

    rr_index_obj: Any = None
    rr_tail_txt = ""

    if rr_index_path.exists():
        rr_index_obj = _safe_json_load(rr_index_path)

    if rr_jsonl_path.exists():
        try:
            b = rr_jsonl_path.read_bytes()
            b = b[-200_000:]
            rr_tail_txt = b.decode("utf-8", errors="replace")
        except Exception:
            rr_tail_txt = ""

    rep["sections"]["run_registry"] = {
        "index_path": str(rr_index_path) if rr_index_path.exists() else None,
        "jsonl_path": str(rr_jsonl_path) if rr_jsonl_path.exists() else None,
        "tail_bytes": 200_000,
    }

    # -----------------------------
    # Bundles index (optional)
    # -----------------------------
    bundles_index_path = out_dir / "index.json"
    bundles_index_obj: Any = None
    if bundles_index_path.exists():
        bundles_index_obj = _safe_json_load(bundles_index_path)
    rep["sections"]["bundles_index"] = {
        "index_path": str(bundles_index_path) if bundles_index_path.exists() else None,
    }

    # -----------------------------
    # Build HTML
    # -----------------------------
    title = "Pneumo Solver UI — Dashboard"

    val_ok = None
    try:
        if isinstance(val_json, dict):
            val_ok = val_json.get("ok")
    except Exception:
        val_ok = None

    anim_summary = dict(rep.get("anim_latest") or {})
    anim_available = bool(anim_summary.get("available") or anim_summary.get("anim_latest_available"))
    anim_token = str(anim_summary.get("visual_cache_token") or anim_summary.get("anim_latest_visual_cache_token") or "")
    anim_reload_inputs = anim_summary.get("visual_reload_inputs")
    if anim_reload_inputs is None:
        anim_reload_inputs = anim_summary.get("anim_latest_visual_reload_inputs")
    anim_reload_inputs = list(anim_reload_inputs or [])
    anim_pointer_sync = anim_summary.get("pointer_sync_ok")
    anim_bundle_usable = anim_summary.get("usable_from_bundle")
    anim_browser_perf_status = str(anim_summary.get("browser_perf_status") or "")
    anim_browser_perf_level = str(anim_summary.get("browser_perf_level") or "")
    anim_browser_perf_evidence_status = str(anim_summary.get("browser_perf_evidence_status") or "")
    anim_browser_perf_evidence_level = str(anim_summary.get("browser_perf_evidence_level") or "")
    anim_browser_perf_bundle_ready = anim_summary.get("browser_perf_bundle_ready")
    anim_browser_perf_comparison_status = str(anim_summary.get("browser_perf_comparison_status") or "")
    anim_browser_perf_comparison_level = str(anim_summary.get("browser_perf_comparison_level") or "")
    anim_browser_perf_comparison_ready = anim_summary.get("browser_perf_comparison_ready")
    optimizer_scope = dict(rep.get("optimizer_scope") or {})
    optimizer_scope_gate = dict(rep.get("optimizer_scope_gate") or {})
    optimizer_problem_scope = str(
        optimizer_scope.get("problem_hash_short")
        or optimizer_scope.get("problem_hash")
        or ""
    )
    optimizer_hash_mode = str(optimizer_scope.get("problem_hash_mode") or "")
    optimizer_scope_sync = optimizer_scope.get("scope_sync_ok")
    optimizer_scope_source = str(optimizer_scope.get("canonical_source") or "")
    optimizer_objective_keys = list(optimizer_scope.get("objective_keys") or [])
    optimizer_scope_gate_name = str(optimizer_scope_gate.get("release_gate") or "")
    optimizer_scope_release_risk = optimizer_scope_gate.get("release_risk")
    optimizer_scope_gate_reason = str(optimizer_scope_gate.get("release_gate_reason") or "")
    if anim_pointer_sync is True:
        anim_pointer_sync_html = '<span class="ok">OK</span>'
    elif anim_pointer_sync is False:
        anim_pointer_sync_html = '<span class="bad">РАСХОЖДЕНИЕ</span>'
    else:
        anim_pointer_sync_html = '<span class="warn">n/a</span>'
    if optimizer_scope_sync is True:
        optimizer_scope_sync_html = '<span class="ok">OK</span>'
    elif optimizer_scope_sync is False:
        optimizer_scope_sync_html = '<span class="bad">РАСХОЖДЕНИЕ</span>'
    else:
        optimizer_scope_sync_html = '<span class="warn">n/a</span>'
    if optimizer_scope_gate_name == "PASS":
        optimizer_scope_gate_html = '<span class="ok">PASS</span>'
    elif optimizer_scope_gate_name == "FAIL":
        optimizer_scope_gate_html = '<span class="bad">FAIL</span>'
    elif optimizer_scope_gate_name == "WARN":
        optimizer_scope_gate_html = '<span class="warn">WARN</span>'
    elif optimizer_scope_gate_name:
        optimizer_scope_gate_html = f'<span class="warn">{_html_escape(optimizer_scope_gate_name)}</span>'
    else:
        optimizer_scope_gate_html = '<span class="warn">n/a</span>'

    env_run_id = os.environ.get("PNEUMO_RUN_ID") or ""

    html = f"""<!doctype html>
<html lang=\"ru\">
<head>
  <meta charset=\"utf-8\"/>
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
  <title>{_html_escape(title)}</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Ubuntu,Arial,sans-serif; margin: 24px; line-height: 1.45; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace; }}
    pre {{ background: #f6f8fa; padding: 12px; border-radius: 8px; overflow: auto; }}
    .meta {{ color: #444; }}
    .bad {{ color: #b00020; font-weight: 700; }}
    .ok {{ color: #0a7a2f; font-weight: 700; }}
    .warn {{ color: #8a6d3b; font-weight: 700; }}
    details {{ margin: 14px 0; }}
    summary {{ cursor: pointer; font-size: 1.1rem; }}
    .grid {{ display: grid; grid-template-columns: 220px 1fr; gap: 6px 12px; max-width: 1100px; }}
    .k {{ color: #555; }}
  </style>
</head>
<body>
  <h1>{_html_escape(title)}</h1>
  <div class=\"meta\">
    <div class=\"grid\">
      <div class=\"k\">Сформировано</div><div>{_html_escape(rep.get('generated_at',''))}</div>
      <div class=\"k\">Версия</div><div>{_html_escape(RELEASE)}</div>
      <div class=\"k\">Архив</div><div>{_html_escape(rep.get('zip_path') or '')}</div>
      <div class=\"k\">Идентификатор запуска</div><div>{_html_escape(env_run_id)}</div>
      <div class=\"k\">Проверка архива</div><div>{'<span class="ok">успешно</span>' if val_ok is True else ('<span class="bad">ошибка</span>' if val_ok is False else '<span class="warn">нет данных</span>')}</div>
      <div class=\"k\">Последняя анимация</div><div>{'<span class="ok">доступна</span>' if anim_available else '<span class="warn">нет данных</span>'}</div>
      <div class=\"k\">Токен анимации</div><div>{_html_escape(_short_token(anim_token) or '—')}</div>
      <div class=\"k\">Синхронизация указателя</div><div>{anim_pointer_sync_html}</div>
      <div class=\"k\">Входные данные анимации</div><div>{_html_escape(', '.join(str(x) for x in anim_reload_inputs) if anim_reload_inputs else '—')}</div>
      <div class=\"k\">Восстановление из архива</div><div>{'<span class="ok">да</span>' if anim_bundle_usable is True else ('<span class="bad">нет</span>' if anim_bundle_usable is False else '<span class="warn">нет данных</span>')}</div>
      <div class=\"k\">Производительность анимации</div><div>{_html_escape((anim_browser_perf_status or '—') + (f' / {anim_browser_perf_level}' if anim_browser_perf_level else ''))}</div>
      <div class=\"k\">Данные производительности</div><div>{_html_escape((anim_browser_perf_evidence_status or '—') + (f' / {anim_browser_perf_evidence_level}' if anim_browser_perf_evidence_level else ''))}</div>
      <div class=\"k\">Производительность в архиве</div><div>{'<span class="ok">да</span>' if anim_browser_perf_bundle_ready is True else ('<span class="bad">нет</span>' if anim_browser_perf_bundle_ready is False else '<span class="warn">нет данных</span>')}</div>
      <div class=\"k\">Сравнение производительности</div><div>{_html_escape((anim_browser_perf_comparison_status or '—') + (f' / {anim_browser_perf_comparison_level}' if anim_browser_perf_comparison_level else ''))}</div>
      <div class=\"k\">Сравнение готово</div><div>{'<span class="ok">да</span>' if anim_browser_perf_comparison_ready is True else ('<span class="bad">нет</span>' if anim_browser_perf_comparison_ready is False else '<span class="warn">нет данных</span>')}</div>
      <div class=\"k\">Область задачи</div><div>{_html_escape(optimizer_problem_scope or '—')}</div>
      <div class=\"k\">Режим хэша</div><div>{_html_escape(optimizer_hash_mode or '—')}</div>
      <div class=\"k\">Допуск оптимизации</div><div>{optimizer_scope_gate_html}</div>
      <div class=\"k\">Синхронизация оптимизации</div><div>{optimizer_scope_sync_html}</div>
      <div class=\"k\">Источник оптимизации</div><div>{_html_escape(optimizer_scope_source or '—')}</div>
    </div>
  </div>

  <details open>
    <summary>Разбор замечаний</summary>
    <pre>{_html_escape(triage_md)}</pre>
  </details>

  <details>
    <summary>Область оптимизации</summary>
    <div class=\"grid\">
      <div class=\"k\">Область задачи</div><div>{_html_escape(optimizer_problem_scope or '—')}</div>
      <div class=\"k\">Режим хэша</div><div>{_html_escape(optimizer_hash_mode or '—')}</div>
      <div class=\"k\">Допуск выпуска</div><div>{optimizer_scope_gate_html}</div>
      <div class=\"k\">Риск выпуска</div><div>{_html_escape(str(optimizer_scope_release_risk))}</div>
      <div class=\"k\">Причина допуска</div><div>{_html_escape(optimizer_scope_gate_reason or '—')}</div>
      <div class=\"k\">Синхронизация области</div><div>{optimizer_scope_sync_html}</div>
      <div class=\"k\">Основной источник</div><div>{_html_escape(optimizer_scope_source or '—')}</div>
      <div class=\"k\">Цели расчёта</div><div>{_html_escape(', '.join(str(x) for x in optimizer_objective_keys) if optimizer_objective_keys else '—')}</div>
    </div>
    <pre>{_html_escape(_pretty_json(optimizer_scope) if optimizer_scope else '(область оптимизации не найдена)')}</pre>
  </details>

  <details>
    <summary>Последняя анимация</summary>
    <div class=\"grid\">
      <div class=\"k\">Доступна</div><div>{_html_escape(str(anim_available))}</div>
      <div class=\"k\">Токен визуального кэша</div><div>{_html_escape(anim_token or '—')}</div>
      <div class=\"k\">Входные данные перезагрузки</div><div>{_html_escape(', '.join(str(x) for x in anim_reload_inputs) if anim_reload_inputs else '—')}</div>
      <div class=\"k\">Указатель синхронизирован</div><div>{anim_pointer_sync_html}</div>
      <div class=\"k\">Восстанавливается из архива</div><div>{_html_escape(str(anim_bundle_usable))}</div>
      <div class=\"k\">Состояние производительности</div><div>{_html_escape(anim_browser_perf_status or '—')}</div>
      <div class=\"k\">Данные производительности</div><div>{_html_escape(anim_browser_perf_evidence_status or '—')}</div>
      <div class=\"k\">Данные производительности в архиве</div><div>{_html_escape(str(anim_browser_perf_bundle_ready))}</div>
      <div class=\"k\">Состояние сравнения</div><div>{_html_escape(anim_browser_perf_comparison_status or '—')}</div>
      <div class=\"k\">Сравнение готово</div><div>{_html_escape(str(anim_browser_perf_comparison_ready))}</div>
    </div>
    <pre>{_html_escape(anim_md if anim_md else '(данные последней анимации не найдены)')}</pre>
  </details>

  <details>
    <summary>Проверка архива проекта</summary>
    <pre>{_html_escape(val_md)}</pre>
  </details>

  <details>
    <summary>Отчёт SQLite-метрик</summary>
    <pre>{_html_escape(sql_md if sql_md else '(отчёт SQLite не найден)')}</pre>
  </details>

  <details>
    <summary>Реестр запусков: index.json</summary>
    <pre>{_html_escape(_pretty_json(rr_index_obj) if rr_index_obj is not None else '(runs/index.json не найден)')}</pre>
  </details>

  <details>
    <summary>Реестр запусков: последние записи</summary>
    <pre>{_html_escape(rr_tail_txt if rr_tail_txt else '(runs/run_registry.jsonl не найден)')}</pre>
  </details>

  <details>
    <summary>Архивы проекта: index.json</summary>
    <pre>{_html_escape(_pretty_json(bundles_index_obj) if bundles_index_obj is not None else '(send_bundles/index.json не найден)')}</pre>
  </details>

  <details>
    <summary>dashboard_report.json</summary>
    <pre>{_html_escape(_pretty_json(rep))}</pre>
  </details>

</body>
</html>
"""

    return html, rep



def write_dashboard_sidecars(out_dir: Path, html: str, rep_json: Dict[str, Any], *, stamp: Optional[str] = None) -> Tuple[Path, Path]:
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or _ts()

    html_path = out_dir / f"DASHBOARD_{stamp}.html"
    json_path = out_dir / f"DASHBOARD_{stamp}.json"

    html_path.write_text(html, encoding="utf-8", errors="replace")
    json_path.write_text(json.dumps(rep_json, ensure_ascii=False, indent=2), encoding="utf-8", errors="replace")

    (out_dir / "latest_dashboard.html").write_text(html, encoding="utf-8", errors="replace")
    (out_dir / "latest_dashboard.json").write_text(json.dumps(rep_json, ensure_ascii=False, indent=2), encoding="utf-8", errors="replace")

    return html_path, json_path



def main() -> int:
    ap = argparse.ArgumentParser(description="Сформировать единый HTML-отчёт проверки проекта")
    ap.add_argument("--out_dir", default="send_bundles", help="Папка с файлами архива проекта")
    ap.add_argument("--keep_last_n", type=int, default=3)
    ap.add_argument("--zip", default=None, help="Необязательный путь к ZIP архива проекта для проверки")
    ap.add_argument("--print_paths", action="store_true")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = (repo_root / str(args.out_dir)).resolve()

    html, rep = generate_dashboard_report(
        repo_root,
        out_dir,
        zip_path=Path(args.zip).resolve() if args.zip else None,
        keep_last_n=int(args.keep_last_n),
    )

    stamp = _ts()
    html_path, json_path = write_dashboard_sidecars(out_dir, html, rep, stamp=stamp)

    if args.print_paths:
        print(str(html_path))
        print(str(json_path))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
