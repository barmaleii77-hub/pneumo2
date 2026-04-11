#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""opt_selfcheck_v1.py

Autonomous preflight checks for the staged optimization pipeline.

Goals:
- Fail fast on broken inputs (JSON, ranges, missing files).
- Catch the most common regressions that lead to silent NaNs in objectives.
- Produce a machine-readable report (JSON) that can be shown in the UI.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui"

try:
    from .module_loading import load_python_module_from_path
except Exception:
    from pneumo_solver_ui.module_loading import load_python_module_from_path


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _is_finite_number(x: Any) -> bool:
    try:
        v = float(x)
        return math.isfinite(v)
    except Exception:
        return False


def _import_module_from_path(mod_name: str, path: Path):
    return load_python_module_from_path(path, mod_name)


@dataclass
class CheckResult:
    ok: bool
    errors: List[str]
    warnings: List[str]


def check_files(model: Path, worker: Path, base_json: Path, ranges_json: Path, suite_json: Path) -> CheckResult:
    errors: List[str] = []
    warnings: List[str] = []
    for p in [model, worker, base_json, ranges_json, suite_json]:
        if not p.exists():
            errors.append(f"Missing file: {p}")
    if model.exists() and model.suffix.lower() not in {".py"}:
        warnings.append(f"Model file extension looks unusual: {model.name}")
    return CheckResult(ok=(len(errors) == 0), errors=errors, warnings=warnings)


def check_ranges(base: Dict[str, Any], ranges: Dict[str, Any]) -> CheckResult:
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(ranges, dict):
        return CheckResult(False, ["ranges_json must be a dict"], warnings)

    for k, v in ranges.items():
        if not isinstance(k, str) or not k.strip():
            errors.append("Range key must be non-empty string")
            continue
        if not isinstance(v, (list, tuple)) or len(v) != 2:
            errors.append(f"Range '{k}' must be [min,max]")
            continue
        lo, hi = v[0], v[1]
        if not _is_finite_number(lo) or not _is_finite_number(hi):
            errors.append(f"Range '{k}' bounds must be finite numbers: {v}")
            continue
        flo, fhi = float(lo), float(hi)
        if not (flo < fhi):
            errors.append(f"Range '{k}' must satisfy min < max (got {flo} >= {fhi})")
        # base value check (only if key exists)
        if k not in base:
            warnings.append(f"Base params do not contain '{k}' (range defined but base missing)")
        else:
            if not _is_finite_number(base.get(k)):
                warnings.append(f"Base value for ranged param '{k}' is not a finite number: {base.get(k)!r}")
    return CheckResult(ok=(len(errors) == 0), errors=errors, warnings=warnings)


def check_suite(suite: Any) -> CheckResult:
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(suite, list) or not suite:
        return CheckResult(False, ["suite_json must be a non-empty list"], warnings)
    names = []
    for i, rec in enumerate(suite):
        if not isinstance(rec, dict):
            errors.append(f"suite[{i}] must be an object")
            continue
        nm = rec.get("имя")
        if not isinstance(nm, str) or not nm.strip():
            errors.append(f"suite[{i}] missing 'имя'")
        else:
            names.append(nm.strip())
    if len(set(names)) != len(names):
        warnings.append("Suite contains duplicate test names (before scenario expansion)")
    # Key legacy tests for objectives
    needed = {"микро_синфаза", "инерция_крен_ay3"}
    missing = sorted([n for n in needed if n not in set(names)])
    if missing:
        warnings.append("Suite does not contain some legacy tests used in default objectives: " + ", ".join(missing))
    return CheckResult(ok=(len(errors) == 0), errors=errors, warnings=warnings)


def check_scenario_expansion(stage_runner_path: Path, base: Dict[str, Any], suite: List[Dict[str, Any]]) -> CheckResult:
    errors: List[str] = []
    warnings: List[str] = []
    try:
        sr = _import_module_from_path("opt_stage_runner_v1", stage_runner_path)
        scenarios = sr.build_default_scenarios(base)
        expanded = sr.expand_suite_by_scenarios(
            suite, scenarios, base, scenario_ids=["nominal", "heavy"]
        )
        names = [str(r.get("имя", "")) for r in expanded]
        if "микро_синфаза" not in names:
            errors.append("After scenario expansion, base test 'микро_синфаза' is missing (should stay unsuffixed).\n"
                         "This breaks downstream objective aggregation.")
        if "инерция_крен_ay3" not in names:
            errors.append("After scenario expansion, base test 'инерция_крен_ay3' is missing (should stay unsuffixed).")        
        if not any("__sc_heavy" in n for n in names):
            warnings.append("Scenario expansion did not create any '__sc_heavy' tests (check scenario_ids).")        
    except Exception as e:
        warnings.append(f"Scenario-expansion check skipped: {e}")
    return CheckResult(ok=(len(errors) == 0), errors=errors, warnings=warnings)


def check_model_import(model_path: Path) -> CheckResult:
    errors: List[str] = []
    warnings: List[str] = []
    try:
        mod = _import_module_from_path("pneumo_model", model_path)
        # Soft expectations: simulate() OR run_simulation() present.
        has_any = any(hasattr(mod, nm) for nm in ["simulate", "run_simulation", "run_model", "main"])
        if not has_any:
            warnings.append("Model module imported, but no known entrypoint found (simulate/run_simulation/main).")        
    except Exception as e:
        errors.append(f"Model import failed: {e}")
    return CheckResult(ok=(len(errors) == 0), errors=errors, warnings=warnings)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--worker", required=True)
    ap.add_argument("--base_json", required=True)
    ap.add_argument("--ranges_json", required=True)
    ap.add_argument("--suite_json", required=True)
    ap.add_argument("--run_dir", default="")
    ap.add_argument("--report_json", required=True)
    ap.add_argument("--mode", default="fast", choices=["fast", "full"])
    args = ap.parse_args()

    model = Path(args.model)
    worker = Path(args.worker)
    base_json = Path(args.base_json)
    ranges_json = Path(args.ranges_json)
    suite_json = Path(args.suite_json)
    report_json = Path(args.report_json)

    t0 = time.time()
    report: Dict[str, Any] = {
        "ts": t0,
        "mode": args.mode,
        "files": {
            "model": str(model),
            "worker": str(worker),
            "base_json": str(base_json),
            "ranges_json": str(ranges_json),
            "suite_json": str(suite_json),
        },
        "errors": [],
        "warnings": [],
        "checks": {},
        "ok": False,
    }

    # Files
    r = check_files(model, worker, base_json, ranges_json, suite_json)
    report["checks"]["files"] = {"ok": r.ok, "errors": r.errors, "warnings": r.warnings}
    report["errors"].extend(r.errors)
    report["warnings"].extend(r.warnings)
    if not r.ok:
        report["ok"] = False
        _write_json(report_json, report)
        return 2

    # Parse JSONs
    try:
        base = _read_json(base_json)
        ranges = _read_json(ranges_json)
        suite = _read_json(suite_json)
    except Exception as e:
        report["errors"].append(f"JSON parse error: {e}")
        report["ok"] = False
        _write_json(report_json, report)
        return 2

    if not isinstance(base, dict):
        report["errors"].append("base_json must contain an object/dict")
        report["ok"] = False
        _write_json(report_json, report)
        return 2

    # Ranges
    r = check_ranges(base, ranges if isinstance(ranges, dict) else {})
    report["checks"]["ranges"] = {"ok": r.ok, "errors": r.errors, "warnings": r.warnings}
    report["errors"].extend(r.errors)
    report["warnings"].extend(r.warnings)

    # Suite
    r2 = check_suite(suite)
    report["checks"]["suite"] = {"ok": r2.ok, "errors": r2.errors, "warnings": r2.warnings}
    report["errors"].extend(r2.errors)
    report["warnings"].extend(r2.warnings)

    # Scenario expansion compatibility check
    stage_runner_path = Path(__file__).with_name("opt_stage_runner_v1.py")
    if stage_runner_path.exists() and isinstance(suite, list):
        r3 = check_scenario_expansion(stage_runner_path, base, suite)
        report["checks"]["scenario_expansion"] = {"ok": r3.ok, "errors": r3.errors, "warnings": r3.warnings}
        report["errors"].extend(r3.errors)
        report["warnings"].extend(r3.warnings)

    # Model import (optional but useful)
    if args.mode in {"full"}:
        r4 = check_model_import(model)
        report["checks"]["model_import"] = {"ok": r4.ok, "errors": r4.errors, "warnings": r4.warnings}
        report["errors"].extend(r4.errors)
        report["warnings"].extend(r4.warnings)

    report["ok"] = (len(report["errors"]) == 0)
    report["dt_sec"] = float(time.time() - t0)
    _write_json(report_json, report)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
