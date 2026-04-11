#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run mechanical motion selfcheck across a test suite.

Purpose
-------
The mechanical model (world-road double wishbone) writes a compact set of
`mech_selfcheck_*` fields into df_atm (row 0). This script runs the full
suite and collects those fields into a single CSV/JSON report.

It is intentionally lightweight and does not change the math model.

Usage
-----
python -m pneumo_solver_ui.tools.run_mech_suite_selfcheck

or
python pneumo_solver_ui/tools/run_mech_suite_selfcheck.py --help

Output
------
Writes:
- pneumo_solver_ui/autotest_runs/mech_selfcheck_report_latest.csv
- pneumo_solver_ui/autotest_runs/mech_selfcheck_report_latest.json
- timestamped copies next to them.

Exit code
---------
0 - all enabled tests have mech_selfcheck_ok==1
2 - at least one enabled test failed selfcheck (ok==0) or exception happened

"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
import time
from pathlib import Path

# Allow running this file directly (not only via `python -m ...`).
# We add the repository root to sys.path so `import pneumo_solver_ui...` works
# no matter what the current working directory is.
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[2]  # .../<repo>/pneumo_solver_ui/tools/run_mech_suite_selfcheck.py
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from typing import Any, Dict, List

import pandas as pd


def _build_probe_enabled_suite(suite_rows: List[Dict[str, Any]] | List[Any]) -> List[Dict[str, Any]]:
    """Force-enable a non-destructive probe copy of suite rows.

    Shipped `default_suite.json` may intentionally keep every row disabled so the UI
    starts from a safe blank selection. This tool is an explicit selfcheck entrypoint,
    so when no rows are enabled we still want to execute the mechanical checks on a
    cloned probe suite instead of reporting a misleading green `tests=0`.
    """
    out: List[Dict[str, Any]] = []
    for row in list(suite_rows or []):
        if not isinstance(row, dict):
            continue
        probe = dict(row)
        probe["enabled"] = True
        probe["включен"] = True
        out.append(probe)
    return out


def _as_bool(v: Any, default: bool = True) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"0", "false", "no", "off", "disabled"}:
            return False
        if s in {"1", "true", "yes", "on", "enabled"}:
            return True
    return default


def _test_name(test: Dict[str, Any]) -> str:
    return (
        test.get("имя")
        or test.get("name")
        or test.get("название")
        or test.get("title")
        or "(unnamed_test)"
    )


def _collect_targets(test: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k, v in test.items():
        if isinstance(k, str) and k.startswith("target_"):
            try:
                out[k] = float(v)
            except Exception:
                continue
    return out


def _eval_worker_metrics(
    worker,
    model,
    params: Dict[str, Any],
    test: Dict[str, Any],
    *,
    dt: float,
    t_end: float,
    targets: Dict[str, float],
    record_full: bool,
) -> Dict[str, Any]:
    """Call worker evaluation through the currently supported contract.

    Historical worker versions expose metrics-only `eval_candidate_once(...)`, while
    newer flows may also provide `eval_candidate_once_full(...)` for full time-series
    logging. The mech selfcheck only needs metrics, so we adapt to either shape instead
    of assuming a `record_full=` keyword that older workers do not accept.
    """
    if record_full and hasattr(worker, "eval_candidate_once_full"):
        metrics, _out = worker.eval_candidate_once_full(
            model,
            params,
            test,
            dt=dt,
            t_end=t_end,
            targets=targets,
        )
        return metrics

    eval_once = worker.eval_candidate_once
    kwargs = {
        "dt": dt,
        "t_end": t_end,
        "targets": targets,
    }
    try:
        if "record_full" in inspect.signature(eval_once).parameters:
            kwargs["record_full"] = bool(record_full)
    except Exception:
        pass
    return eval_once(model, params, test, **kwargs)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run mech selfcheck for all tests in a suite")
    ap.add_argument(
        "--base",
        default="default_base.json",
        help="Base params JSON (relative to pneumo_solver_ui/)",
    )
    ap.add_argument(
        "--suite",
        default="default_suite.json",
        help="Suite JSON list (relative to pneumo_solver_ui/)",
    )
    ap.add_argument(
        "--model",
        default="model_pneumo_v9_mech_doublewishbone_worldroad.py",
        help="Model .py path (relative to pneumo_solver_ui/)",
    )
    ap.add_argument("--dt", type=float, default=0.005, help="Default dt if not specified in test")
    ap.add_argument("--t_end", type=float, default=6.0, help="Default t_end if not specified in test")
    ap.add_argument(
        "--outdir",
        default="autotest_runs",
        help="Output directory (relative to pneumo_solver_ui/)",
    )
    ap.add_argument(
        "--record_full",
        action="store_true",
        help="Keep full df_main output (slower); by default only metrics are computed",
    )

    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    base_path = (root / args.base).resolve() if not Path(args.base).is_absolute() else Path(args.base)
    suite_path = (root / args.suite).resolve() if not Path(args.suite).is_absolute() else Path(args.suite)
    model_path = (root / args.model).resolve() if not Path(args.model).is_absolute() else Path(args.model)
    outdir = (root / args.outdir).resolve() if not Path(args.outdir).is_absolute() else Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Import worker lazily to keep this file standalone.
    try:
        from pneumo_solver_ui import opt_worker_v3_margins_energy as worker
    except Exception as e:
        print(f"ERROR: cannot import opt_worker_v3_margins_energy: {e}", file=sys.stderr)
        return 2

    params = json.loads(base_path.read_text(encoding="utf-8"))
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    if not isinstance(suite, list):
        print("ERROR: suite must be a JSON list", file=sys.stderr)
        return 2

    enabled_suite = [
        test
        for test in suite
        if isinstance(test, dict) and _as_bool(test.get("enabled", test.get("включен", True)), True)
    ]
    effective_suite = enabled_suite
    if not effective_suite:
        effective_suite = _build_probe_enabled_suite(suite)
        if effective_suite:
            print("INFO: suite has no enabled rows; running forced-enable probe copy for mech selfcheck")
    if not effective_suite:
        print("ERROR: suite does not contain any runnable dict rows", file=sys.stderr)
        return 2

    model = worker.load_model(str(model_path))

    rows: List[Dict[str, Any]] = []
    all_ok = True

    for test in effective_suite:
        name = _test_name(test)
        dt = float(test.get("dt", args.dt))
        t_end = float(test.get("t_end", test.get("t_end_s", args.t_end)))
        targets = _collect_targets(test)

        t0 = time.time()
        try:
            metrics = _eval_worker_metrics(
                worker,
                model,
                params,
                test,
                dt=dt,
                t_end=t_end,
                targets=targets,
                record_full=bool(args.record_full),
            )

            ok = int(metrics.get("mech_selfcheck_ok", 1))
            msg = metrics.get("mech_selfcheck_msg", "")

            row: Dict[str, Any] = {
                "test": name,
                "ok": ok,
                "msg": msg,
                "dt": dt,
                "t_end": t_end,
                "run_s": time.time() - t0,
            }

            # Copy all selfcheck-related keys
            for k, v in metrics.items():
                if isinstance(k, str) and k.startswith("mech_selfcheck_"):
                    row[k] = v

            rows.append(row)
            if ok != 1:
                all_ok = False

        except Exception as e:
            all_ok = False
            rows.append(
                {
                    "test": name,
                    "ok": 0,
                    "msg": f"EXCEPTION: {e}",
                    "dt": dt,
                    "t_end": t_end,
                    "run_s": time.time() - t0,
                }
            )

    df = pd.DataFrame(rows)

    ts = time.strftime("%Y%m%d_%H%M%S")
    csv_ts = outdir / f"mech_selfcheck_report_{ts}.csv"
    json_ts = outdir / f"mech_selfcheck_report_{ts}.json"
    csv_latest = outdir / "mech_selfcheck_report_latest.csv"
    json_latest = outdir / "mech_selfcheck_report_latest.json"

    df.to_csv(csv_ts, index=False, encoding="utf-8")
    df.to_json(json_ts, orient="records", force_ascii=False, indent=2)
    df.to_csv(csv_latest, index=False, encoding="utf-8")
    df.to_json(json_latest, orient="records", force_ascii=False, indent=2)

    n = len(df)
    n_bad = int((df["ok"] != 1).sum()) if ("ok" in df.columns) else 0

    print(f"mech_selfcheck: tests={n}, failed={n_bad}")
    print(f"report: {csv_latest}")

    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
