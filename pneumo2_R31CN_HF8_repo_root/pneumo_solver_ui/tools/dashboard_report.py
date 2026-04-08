#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dashboard_report.py

R53: Unified HTML Dashboard (triage + validation + sqlite metrics + run registry)
==============================================================================

Goal
----
Provide a *single* human-friendly entry point after a run. The dashboard is
intended to be included into the Send Bundle ZIP and also written as a sidecar
file next to bundles.

The dashboard shows (best-effort):
- Triage (md + json)
- Send bundle validation (md + json)
- Anim latest diagnostics (md + json)
- SQLite metrics report (md + json) if generated
- Run registry tail / index

Usage
-----
CLI:
  python -m pneumo_solver_ui.tools.dashboard_report --out_dir send_bundles --print_paths

From make_send_bundle.py:
  - embed dashboard into ZIP: dashboard/index.html, dashboard/dashboard.json
  - write sidecars: send_bundles/latest_dashboard.html / .json

Design notes
------------
- Best-effort: failures MUST NOT break bundle creation.
- No external template deps: pure Python string formatting.

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

from .send_bundle_contract import (
    ANIM_DIAG_JSON,
    ANIM_DIAG_MD,
    ANIM_DIAG_SIDECAR_JSON,
    ANIM_DIAG_SIDECAR_MD,
    anim_has_signal,
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
            rep["warnings"].append("triage sidecar not found; generated on the fly")
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
            rep["warnings"].append("validation sidecar not found; validated zip on the fly")
        except Exception:
            rep["errors"].append("failed to load/generate validation")
            val_md = "(validation not available)\n" + traceback.format_exc()
            val_json = {"error": "validation_failed"}

    rep["sections"]["validation"] = {
        "md_path": str(val_md_path) if val_md_path.exists() else None,
        "json_path": str(val_json_path) if val_json_path.exists() else None,
    }

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
            rep["warnings"].append("anim_latest markdown sidecar not found next to bundle; using ZIP copy")

    if anim_json_path.exists():
        anim_json = _safe_json_load(anim_json_path)
    elif zip_path is not None:
        anim_json = _safe_zip_json_load(zip_path, ANIM_DIAG_JSON)
        if anim_json is not None:
            rep["warnings"].append("anim_latest json sidecar not found next to bundle; using ZIP copy")

    if anim_json is None and isinstance(val_json, dict):
        anim_json = val_json.get("anim_latest")
        if isinstance(anim_json, dict):
            rep["warnings"].append("anim_latest diagnostics sidecar not found; using validation summary")

    anim_norm = normalize_anim_dashboard_obj(anim_json)
    val_anim_json = val_json.get("anim_latest") if isinstance(val_json, dict) else None
    val_anim_norm = normalize_anim_dashboard_obj(val_anim_json)
    if (not anim_has_signal(anim_norm)) and anim_has_signal(val_anim_norm):
        anim_json = val_anim_json
        anim_norm = val_anim_norm
        rep["warnings"].append("anim_latest ZIP/sidecar diagnostics are empty; using validation summary")
        anim_md = render_anim_latest_md(anim_json)
    elif not anim_md and isinstance(anim_json, dict):
        anim_md = render_anim_latest_md(anim_json)

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
    if anim_pointer_sync is True:
        anim_pointer_sync_html = '<span class="ok">OK</span>'
    elif anim_pointer_sync is False:
        anim_pointer_sync_html = '<span class="bad">MISMATCH</span>'
    else:
        anim_pointer_sync_html = '<span class="warn">n/a</span>'

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
      <div class=\"k\">generated_at</div><div>{_html_escape(rep.get('generated_at',''))}</div>
      <div class=\"k\">release</div><div>{_html_escape(RELEASE)}</div>
      <div class=\"k\">zip_path</div><div>{_html_escape(rep.get('zip_path') or '')}</div>
      <div class=\"k\">PNEUMO_RUN_ID</div><div>{_html_escape(env_run_id)}</div>
      <div class=\"k\">validation.ok</div><div>{'<span class="ok">OK</span>' if val_ok is True else ('<span class="bad">FAIL</span>' if val_ok is False else '<span class="warn">n/a</span>')}</div>
      <div class=\"k\">anim_latest.available</div><div>{'<span class="ok">YES</span>' if anim_available else '<span class="warn">NO / n-a</span>'}</div>
      <div class=\"k\">anim_latest.token</div><div>{_html_escape(_short_token(anim_token) or '—')}</div>
      <div class=\"k\">anim_latest.pointer_sync</div><div>{anim_pointer_sync_html}</div>
      <div class=\"k\">anim_latest.reload_inputs</div><div>{_html_escape(', '.join(str(x) for x in anim_reload_inputs) if anim_reload_inputs else '—')}</div>
      <div class=\"k\">anim_latest.bundle_usable</div><div>{'<span class="ok">YES</span>' if anim_bundle_usable is True else ('<span class="bad">NO</span>' if anim_bundle_usable is False else '<span class="warn">n/a</span>')}</div>
    </div>
  </div>

  <details open>
    <summary>📌 Triage report (markdown)</summary>
    <pre>{_html_escape(triage_md)}</pre>
  </details>

  <details>
    <summary>🎞️ Anim latest diagnostics</summary>
    <div class=\"grid\">
      <div class=\"k\">available</div><div>{_html_escape(str(anim_available))}</div>
      <div class=\"k\">visual_cache_token</div><div>{_html_escape(anim_token or '—')}</div>
      <div class=\"k\">visual_reload_inputs</div><div>{_html_escape(', '.join(str(x) for x in anim_reload_inputs) if anim_reload_inputs else '—')}</div>
      <div class=\"k\">pointer_sync_ok</div><div>{anim_pointer_sync_html}</div>
      <div class=\"k\">usable_from_bundle</div><div>{_html_escape(str(anim_bundle_usable))}</div>
    </div>
    <pre>{_html_escape(anim_md if anim_md else '(anim_latest diagnostics not found)')}</pre>
  </details>

  <details>
    <summary>✅ Send bundle validation report (markdown)</summary>
    <pre>{_html_escape(val_md)}</pre>
  </details>

  <details>
    <summary>🗄️ SQLite metrics report (markdown)</summary>
    <pre>{_html_escape(sql_md if sql_md else '(sqlite report not found)')}</pre>
  </details>

  <details>
    <summary>🧾 Run registry index.json</summary>
    <pre>{_html_escape(_pretty_json(rr_index_obj) if rr_index_obj is not None else '(runs/index.json not found)')}</pre>
  </details>

  <details>
    <summary>🧾 Run registry tail (run_registry.jsonl last ~200KB)</summary>
    <pre>{_html_escape(rr_tail_txt if rr_tail_txt else '(runs/run_registry.jsonl not found)')}</pre>
  </details>

  <details>
    <summary>📦 send_bundles/index.json</summary>
    <pre>{_html_escape(_pretty_json(bundles_index_obj) if bundles_index_obj is not None else '(send_bundles/index.json not found)')}</pre>
  </details>

  <details>
    <summary>🔧 dashboard_report.json (raw)</summary>
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
    ap = argparse.ArgumentParser(description="Generate unified HTML dashboard report")
    ap.add_argument("--out_dir", default="send_bundles", help="Directory where send bundle sidecars live")
    ap.add_argument("--keep_last_n", type=int, default=3)
    ap.add_argument("--zip", default=None, help="Optional send bundle zip path (for validation on the fly)")
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
