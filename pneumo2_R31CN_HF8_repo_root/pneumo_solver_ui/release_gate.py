"""Release gate runner (machine-readable).

Purpose
- Provide a repeatable, CLI-friendly "gate" that can be used before publishing a build.
- Produce a JSON report (and raw logs) that CI or humans can inspect.

This is *not* a replacement for the in-app diagnostics bundle. It is a lightweight CI-style wrapper
around:
- compileall (syntax check)
- selfcheck_suite (quick/standard/full)
- pytest (optional)

Usage examples
    python -m pneumo_solver_ui.release_gate --level quick
    python -m pneumo_solver_ui.release_gate --level standard --run-pytest

Outputs
- <out_dir>/gate_report.json
- <out_dir>/logs/compileall.txt
- <out_dir>/logs/selfcheck_suite.txt
- <out_dir>/logs/pytest.txt (if enabled)

Exit code
- 0 on PASS
- 2 on FAIL

"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


V32_RELEASE_GATE_REFERENCE_DIR = Path("docs") / "context" / "gui_spec_imports" / "v32_connector_reconciled"
V32_RELEASE_GATE_HARDENING_MATRIX = V32_RELEASE_GATE_REFERENCE_DIR / "RELEASE_GATE_HARDENING_MATRIX.csv"
V32_GAP_TO_EVIDENCE_ACTION_MAP = V32_RELEASE_GATE_REFERENCE_DIR / "GAP_TO_EVIDENCE_ACTION_MAP.csv"
V32_RELEASE_GATE_ACCEPTANCE_MAP = V32_RELEASE_GATE_REFERENCE_DIR / "RELEASE_GATE_ACCEPTANCE_MAP.md"
V33_RELEASE_GATE_REFERENCE_DIR = Path("docs") / "context" / "gui_spec_imports" / "v33_connector_reconciled"
V33_README = V33_RELEASE_GATE_REFERENCE_DIR / "README.md"
V33_COMPLETENESS_ASSESSMENT = V33_RELEASE_GATE_REFERENCE_DIR / "COMPLETENESS_ASSESSMENT.md"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_project_root(project_root: Path | str | None = None) -> Path:
    return Path(project_root).resolve() if project_root is not None else _project_root()


def v32_release_gate_reference_paths(project_root: Path | str | None = None) -> Dict[str, str]:
    """Return local v32 gate/gap reference files used by docs-contract tests."""

    root = _resolve_project_root(project_root)
    return {
        "release_gate_acceptance_map": str(root / V32_RELEASE_GATE_ACCEPTANCE_MAP),
        "release_gate_hardening_matrix": str(root / V32_RELEASE_GATE_HARDENING_MATRIX),
        "gap_to_evidence_action_map": str(root / V32_GAP_TO_EVIDENCE_ACTION_MAP),
    }


def _load_utf8_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_v32_release_gate_hardening_matrix(
    project_root: Path | str | None = None,
) -> List[Dict[str, str]]:
    root = _resolve_project_root(project_root)
    return _load_utf8_csv_rows(root / V32_RELEASE_GATE_HARDENING_MATRIX)


def load_v32_gap_to_evidence_action_map(
    project_root: Path | str | None = None,
) -> List[Dict[str, str]]:
    root = _resolve_project_root(project_root)
    return _load_utf8_csv_rows(root / V32_GAP_TO_EVIDENCE_ACTION_MAP)


def v32_release_gate_reference_metadata(project_root: Path | str | None = None) -> Dict[str, Any]:
    """Small non-runtime metadata block for source-authority and gate checks."""

    paths = v32_release_gate_reference_paths(project_root)
    hardening_path = Path(paths["release_gate_hardening_matrix"])
    gap_path = Path(paths["gap_to_evidence_action_map"])
    return {
        "source_layer": "docs/context/gui_spec_imports/v32_connector_reconciled",
        "paths": paths,
        "hardening_rows": len(_load_utf8_csv_rows(hardening_path)) if hardening_path.exists() else None,
        "open_gap_rows": len(_load_utf8_csv_rows(gap_path)) if gap_path.exists() else None,
        "runtime_closure_claim": False,
    }


def v33_release_gate_reference_paths(project_root: Path | str | None = None) -> Dict[str, str]:
    """Return active v33 connector reference files for release-gate reports."""

    root = _resolve_project_root(project_root)
    return {
        "readme": str(root / V33_README),
        "completeness_assessment": str(root / V33_COMPLETENESS_ASSESSMENT),
    }


def v33_release_gate_reference_metadata(project_root: Path | str | None = None) -> Dict[str, Any]:
    """Active connector-layer metadata; docs-only and never a runtime closure claim."""

    return {
        "source_layer": "docs/context/gui_spec_imports/v33_connector_reconciled",
        "paths": v33_release_gate_reference_paths(project_root),
        "active_connector_layer": True,
        "runtime_closure_claim": False,
    }


def release_gate_reference_metadata(project_root: Path | str | None = None) -> Dict[str, Any]:
    """Combined source-authority metadata for gate reports."""

    return {
        "active_connector": v33_release_gate_reference_metadata(project_root),
        "workstream_gate_extract": v32_release_gate_reference_metadata(project_root),
    }


@dataclass
class StepResult:
    name: str
    ok: bool
    rc: int
    seconds: float
    log_path: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_cmd(cmd: List[str], *, cwd: Path, log_path: Path, env: Dict[str, str]) -> StepResult:
    t0 = time.time()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"# cmd: {' '.join(cmd)}\n")
        f.write(f"# cwd: {cwd}\n")
        f.write(f"# utc_start: {_utc_now_iso()}\n\n")
        f.flush()

        p = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=f, stderr=subprocess.STDOUT, text=True)

    dt = time.time() - t0
    return StepResult(name=" ".join(cmd[:2]) if len(cmd) >= 2 else cmd[0], ok=(p.returncode == 0), rc=p.returncode, seconds=dt, log_path=str(log_path))


def _default_runtime_evidence_dir(project_root: Path) -> Path:
    workspace = os.environ.get("PNEUMO_WORKSPACE_DIR", "").strip()
    if workspace:
        return Path(workspace).expanduser().resolve(strict=False) / "exports"
    return project_root / "pneumo_solver_ui" / "workspace" / "exports"


def _runtime_evidence_step(
    *,
    project_root: Path,
    logs_dir: Path,
    evidence_dir: Path,
    require_browser_trace: bool,
    require_viewport_gating: bool,
    require_animator_frame_budget: bool,
    require_windows_runtime: bool,
) -> StepResult:
    t0 = time.time()
    log_path = logs_dir / "runtime_evidence.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from pneumo_solver_ui.runtime_evidence import validate_runtime_evidence_dir

        report = validate_runtime_evidence_dir(
            evidence_dir,
            require_browser_trace=bool(require_browser_trace),
            require_viewport_gating=bool(require_viewport_gating),
            require_animator_frame_budget=bool(require_animator_frame_budget),
            require_windows_runtime=bool(require_windows_runtime),
        )
        report["project_root"] = str(project_root)
        report["required"] = {
            "browser_trace": bool(require_browser_trace),
            "viewport_gating": bool(require_viewport_gating),
            "animator_frame_budget": bool(require_animator_frame_budget),
            "windows_runtime": bool(require_windows_runtime),
        }
        log_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        ok = bool(report.get("ok"))
        return StepResult(
            name="runtime_evidence",
            ok=ok,
            rc=0 if ok else 1,
            seconds=time.time() - t0,
            log_path=str(log_path),
            meta={
                "evidence_dir": str(evidence_dir),
                "hard_fail_count": int(report.get("hard_fail_count") or 0),
            },
        )
    except Exception as exc:
        payload = {
            "schema": "runtime_evidence_validation.v1",
            "project_root": str(project_root),
            "evidence_dir": str(evidence_dir),
            "ok": False,
            "hard_fail_count": 1,
            "hard_fails": [{"name": "runtime_evidence", "message": repr(exc), "path": ""}],
        }
        log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return StepResult(name="runtime_evidence", ok=False, rc=1, seconds=time.time() - t0, log_path=str(log_path))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="PneumoApp release gate (machine-readable report)")
    ap.add_argument("--level", choices=["quick", "standard", "full"], default="quick", help="Selfcheck suite level")
    ap.add_argument(
        "--out-dir",
        default="gate_runs",
        help="Output directory (relative to project root unless absolute)",
    )
    ap.add_argument("--run-pytest", action="store_true", help="Run pytest -q after selfcheck suite")
    ap.add_argument("--pytest-args", default="-q", help="Extra pytest args (default: -q)")
    ap.add_argument("--fail-fast", action="store_true", help="Stop after first failed step")
    ap.add_argument(
        "--runtime-evidence-dir",
        default="",
        help="Directory containing runtime evidence artifacts (defaults to workspace exports)",
    )
    ap.add_argument(
        "--require-runtime-evidence",
        action="store_true",
        help="Require browser trace, viewport gating, animator frame budget, and Windows runtime proof artifacts",
    )
    ap.add_argument("--require-browser-trace", action="store_true", help="Require PB-006 browser perf trace evidence")
    ap.add_argument("--require-viewport-gating", action="store_true", help="Require PB-006 viewport gating evidence")
    ap.add_argument(
        "--require-animator-frame-budget",
        action="store_true",
        help="Require PB-006 animator frame-budget evidence",
    )
    ap.add_argument(
        "--require-windows-runtime-proof",
        action="store_true",
        help="Require PB-005 Windows snap/DPI/second-monitor/path-budget proof",
    )

    args = ap.parse_args(argv)

    project_root = _project_root()

    # Resolve output dir
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = project_root / out_dir

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = out_dir / f"gate_{run_id}_{args.level}"
    logs_dir = out_dir / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    require_browser_trace = bool(args.require_runtime_evidence or args.require_browser_trace)
    require_viewport_gating = bool(args.require_runtime_evidence or args.require_viewport_gating)
    require_animator_frame_budget = bool(args.require_runtime_evidence or args.require_animator_frame_budget)
    require_windows_runtime = bool(args.require_runtime_evidence or args.require_windows_runtime_proof)
    runtime_evidence_dir = Path(args.runtime_evidence_dir).expanduser() if args.runtime_evidence_dir else _default_runtime_evidence_dir(project_root)
    runtime_evidence_dir = runtime_evidence_dir.resolve(strict=False)

    steps: List[StepResult] = []

    # 1) compileall
    compile_log = logs_dir / "compileall.txt"
    t0 = time.time()
    try:
        import compileall

        ok = compileall.compile_dir(str(project_root), quiet=1)
        dt = time.time() - t0
        compile_log.parent.mkdir(parents=True, exist_ok=True)
        compile_log.write_text(
            f"compileall.compile_dir({project_root}) -> {ok}\n",
            encoding="utf-8",
        )
        steps.append(StepResult(name="compileall", ok=bool(ok), rc=0 if ok else 1, seconds=dt, log_path=str(compile_log)))
    except Exception as e:
        dt = time.time() - t0
        compile_log.parent.mkdir(parents=True, exist_ok=True)
        compile_log.write_text(f"EXCEPTION: {e!r}\n", encoding="utf-8")
        steps.append(StepResult(name="compileall", ok=False, rc=1, seconds=dt, log_path=str(compile_log)))

    if args.fail_fast and not steps[-1].ok:
        verdict = "FAIL"
        report = {
            "utc": _utc_now_iso(),
            "level": args.level,
            "project_root": str(project_root),
            "out_dir": str(out_dir),
            "reference_layers": release_gate_reference_metadata(project_root),
            "steps": [asdict(s) for s in steps],
            "verdict": verdict,
        }
        (out_dir / "gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    # 2) selfcheck_suite
    selfcheck_log = logs_dir / "selfcheck_suite.txt"
    cmd = [sys.executable, "-m", "pneumo_solver_ui.tools.selfcheck_suite", "--level", args.level]
    r = _run_cmd(cmd, cwd=project_root, log_path=selfcheck_log, env=env)
    r.name = "selfcheck_suite"
    steps.append(r)

    if args.fail_fast and not steps[-1].ok:
        verdict = "FAIL"
        report = {
            "utc": _utc_now_iso(),
            "level": args.level,
            "project_root": str(project_root),
            "out_dir": str(out_dir),
            "reference_layers": release_gate_reference_metadata(project_root),
            "steps": [asdict(s) for s in steps],
            "verdict": verdict,
        }
        (out_dir / "gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    # 3) runtime evidence hard gates (optional)
    if require_browser_trace or require_viewport_gating or require_animator_frame_budget or require_windows_runtime:
        r = _runtime_evidence_step(
            project_root=project_root,
            logs_dir=logs_dir,
            evidence_dir=runtime_evidence_dir,
            require_browser_trace=require_browser_trace,
            require_viewport_gating=require_viewport_gating,
            require_animator_frame_budget=require_animator_frame_budget,
            require_windows_runtime=require_windows_runtime,
        )
        steps.append(r)

    if args.fail_fast and not steps[-1].ok:
        verdict = "FAIL"
        report = {
            "utc": _utc_now_iso(),
            "level": args.level,
            "project_root": str(project_root),
            "out_dir": str(out_dir),
            "runtime_evidence_dir": str(runtime_evidence_dir),
            "reference_layers": release_gate_reference_metadata(project_root),
            "steps": [asdict(s) for s in steps],
            "verdict": verdict,
        }
        (out_dir / "gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    # 3) runtime evidence hard gates (optional)
    if require_browser_trace or require_viewport_gating or require_animator_frame_budget or require_windows_runtime:
        r = _runtime_evidence_step(
            project_root=project_root,
            logs_dir=logs_dir,
            evidence_dir=runtime_evidence_dir,
            require_browser_trace=require_browser_trace,
            require_viewport_gating=require_viewport_gating,
            require_animator_frame_budget=require_animator_frame_budget,
            require_windows_runtime=require_windows_runtime,
        )
        steps.append(r)

    if args.fail_fast and not steps[-1].ok:
        verdict = "FAIL"
        report = {
            "utc": _utc_now_iso(),
            "level": args.level,
            "project_root": str(project_root),
            "out_dir": str(out_dir),
            "runtime_evidence_dir": str(runtime_evidence_dir),
            "steps": [asdict(s) for s in steps],
            "verdict": verdict,
        }
        (out_dir / "gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    # 4) pytest (optional)
    if args.run_pytest:
        pytest_log = logs_dir / "pytest.txt"
        cmd = ["pytest"] + args.pytest_args.split()
        r = _run_cmd(cmd, cwd=project_root, log_path=pytest_log, env=env)
        r.name = "pytest"
        steps.append(r)

    verdict = "PASS" if all(s.ok for s in steps) else "FAIL"

    report = {
        "utc": _utc_now_iso(),
        "level": args.level,
        "project_root": str(project_root),
        "out_dir": str(out_dir),
        "runtime_evidence_dir": str(runtime_evidence_dir),
        "reference_layers": release_gate_reference_metadata(project_root),
        "steps": [asdict(s) for s in steps],
        "verdict": verdict,
    }

    (out_dir / "gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if verdict == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
