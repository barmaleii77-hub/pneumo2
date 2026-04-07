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
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


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

    args = ap.parse_args(argv)

    project_root = Path(__file__).resolve().parents[1]

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
            "steps": [asdict(s) for s in steps],
            "verdict": verdict,
        }
        (out_dir / "gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    # 3) pytest (optional)
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
        "steps": [asdict(s) for s in steps],
        "verdict": verdict,
    }

    (out_dir / "gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if verdict == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
