# -*- coding: utf-8 -*-
"""pneumo_solver_ui.tools.selfcheck_suite (Testy R639)

Автономный набор самопроверок, который можно запускать:
- вручную (python -m pneumo_solver_ui.tools.selfcheck_suite)
- автоматически из make_send_bundle (чтобы отправляемый ZIP содержал diagnostics)

Цели:
- максимальная надёжность: best-effort, не валим процесс при ошибках
- максимальная информативность: сохраняем stdout/stderr каждой стадии
- минимум зависимостей (stdlib only)

Формат:
- out_dir/selfcheck_report.json
- out_dir/selfcheck_report.md
- out_dir/steps/<step>/{stdout.txt,stderr.txt}

Важно:
- JSON строго валиден (allow_nan=False) через pneumo_solver_ui.diag.json_safe
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pneumo_solver_ui.diag.json_safe import json_dumps, to_jsonable
from pneumo_solver_ui.release_info import get_release
from pneumo_solver_ui.workspace_contract import (
    REQUIRED_WORKSPACE_DIRS,
    ensure_workspace_contract_dirs,
    resolve_effective_workspace_dir,
)


@dataclass
class StepResult:
    name: str
    ok: bool
    rc: int
    duration_s: float
    stdout_rel: str
    stderr_rel: str
    notes: str = ""


@dataclass
class SelfcheckReport:
    schema: str
    schema_version: str
    release: str
    run_id: str
    started_at: str
    finished_at: str
    ok: bool
    steps: List[StepResult]
    summary: Dict[str, Any]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _resolve_cli_python_executable(env: Optional[Dict[str, str]] = None) -> str:
    """Prefer deterministic console python for helper subprocesses.

    Resolution order mirrors send-bundle diagnostics helpers:
    1) launcher-provided shared venv python,
    2) sibling python.exe for current pythonw.exe,
    3) current interpreter.
    """
    env_map = env or os.environ
    for env_key in ("PNEUMO_SHARED_VENV_PYTHON", "PNEUMO_VENV_PYTHON"):
        try:
            raw = str(env_map.get(env_key) or "").strip()
            if raw:
                cand = Path(raw)
                if cand.exists():
                    return str(cand)
        except Exception:
            pass
    try:
        exe = Path(sys.executable)
        if exe.name.lower() == "pythonw.exe":
            cand = exe.with_name("python.exe")
            if cand.exists():
                return str(cand)
        return str(exe)
    except Exception:
        return str(sys.executable)


def _run_step(
    *,
    name: str,
    cmd: List[str],
    cwd: Path,
    out_dir: Path,
    env: Dict[str, str],
    timeout_s: int = 300,
) -> StepResult:
    step_dir = (out_dir / "steps" / name).resolve()
    step_dir.mkdir(parents=True, exist_ok=True)
    out_p = step_dir / "stdout.txt"
    err_p = step_dir / "stderr.txt"

    t0 = time.time()
    rc = 1
    notes = ""
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        rc = int(p.returncode)
        out_p.write_text(p.stdout or "", encoding="utf-8")
        err_p.write_text(p.stderr or "", encoding="utf-8")
        ok = (rc == 0)
    except subprocess.TimeoutExpired as e:
        ok = False
        rc = 124
        notes = f"timeout ({timeout_s}s)"
        out_p.write_text((e.stdout or "") if isinstance(e.stdout, str) else "", encoding="utf-8")
        err_p.write_text((e.stderr or "") if isinstance(e.stderr, str) else "", encoding="utf-8")
    except Exception as e:
        ok = False
        rc = 1
        notes = f"exception: {type(e).__name__}: {e!s}"
        try:
            err_p.write_text(notes, encoding="utf-8")
        except Exception:
            pass

    dt = time.time() - t0
    return StepResult(
        name=name,
        ok=bool(ok),
        rc=int(rc),
        duration_s=float(dt),
        stdout_rel=str(out_p.relative_to(out_dir)).replace("\\", "/"),
        stderr_rel=str(err_p.relative_to(out_dir)).replace("\\", "/"),
        notes=notes,
    )


def run_selfcheck_suite(
    *,
    repo_root: Path,
    out_dir: Path,
    level: str = "standard",
    env_extra: Optional[Dict[str, str]] = None,
) -> SelfcheckReport:
    repo_root = Path(repo_root).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    started = _now_iso()
    t0 = time.time()

    release = (os.environ.get("PNEUMO_RELEASE") or "").strip() or get_release()
    run_id = (os.environ.get("PNEUMO_RUN_ID") or "").strip() or (os.environ.get("PNEUMO_SESSION_ID") or "").strip() or "SELFCHK"

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env.setdefault("PNEUMO_RELEASE", release)
    env.setdefault("PNEUMO_RUN_ID", run_id)
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items()})

    preferred_python = _resolve_cli_python_executable(env)
    env.setdefault("PNEUMO_SHARED_VENV_PYTHON", preferred_python)
    workspace_dir = resolve_effective_workspace_dir(repo_root, env=env)
    ensure_workspace_contract_dirs(workspace_dir, include_optional=True)

    steps: List[StepResult] = []

    # --- Steps ---
    # 1) compileall (syntax)
    steps.append(
        _run_step(
            name="compileall",
            cmd=[preferred_python, "-m", "compileall", str((repo_root / "pneumo_solver_ui").resolve())],
            cwd=repo_root,
            out_dir=out_dir,
            env=env,
            timeout_s=300 if level != "quick" else 120,
        )
    )

    

    # 2) workspace dirs contract smoke (required folders must exist in the *effective* workspace)
    ws_cmd = "\n".join([
        "from pathlib import Path",
        "from pneumo_solver_ui.workspace_contract import REQUIRED_WORKSPACE_DIRS, resolve_effective_workspace_dir",
        "repo_root = Path('.').resolve()",
        "ws = resolve_effective_workspace_dir(repo_root)",
        "missing=[d for d in REQUIRED_WORKSPACE_DIRS if not (ws/d).exists()]",
        "assert not missing, 'missing workspace dirs in ' + str(ws) + ': ' + ','.join(missing)",
        "print('WORKSPACE_DIRS_OK', ws)",
    ])
    steps.append(
        _run_step(
            name="workspace_dirs_contract",
            cmd=[preferred_python, "-c", ws_cmd],
            cwd=repo_root,
            out_dir=out_dir,
            env=env,
            timeout_s=60,
        )
    )

    # 3) import smoke (runtime import errors, missing deps)

    smoke_cmd = "\n".join([
        "import importlib, sys",
        "mods=[",
        "    'pneumo_solver_ui',",
        "    'pneumo_solver_ui.tools.make_send_bundle',",
        "    'pneumo_solver_ui.tools.triage_report',",
        "    'pneumo_solver_ui.tools.validate_send_bundle',",
        "    'pneumo_solver_ui.tools.loglint',",
        "    'pneumo_solver_ui.compare_influence_time',",
        "]",
        "bad=[]",
        "for m in mods:",
        "    try:",
        "        importlib.import_module(m)",
        "    except Exception as e:",
        "        bad.append((m,repr(e)))",
        "print('IMPORT_OK' if not bad else 'IMPORT_FAIL')",
        "print(bad)",
        "sys.exit(0 if not bad else 2)",
    ])

    steps.append(
        _run_step(
            name="import_smoke",
            cmd=[preferred_python, "-c", smoke_cmd],
            cwd=repo_root,
            out_dir=out_dir,
            env=env,
            timeout_s=120,
        )
    )

    # 3) preflight gate (heavy, runs full model checks)
    if level == "full":
        steps.append(
            _run_step(
                name="preflight_gate",
                cmd=[preferred_python, str((repo_root / "pneumo_solver_ui" / "tools" / "preflight_gate.py").resolve())],
                cwd=repo_root,
                out_dir=out_dir,
                env=env,
                timeout_s=120,
            )
        )

    
    # 4) Influence(t) synthetic determinism test
    if level in ("standard", "full"):
        synth_cmd = "\n".join([
            "import numpy as np, pandas as pd",
            "from pneumo_solver_ui.compare_influence_time import build_influence_t_cube",
            "t=np.linspace(0.0,1.0,101)",
            "runs=[]",
            "for i in range(5):",
            "    df=pd.DataFrame({\"t\":t,\"sa\":(i+0.1*np.sin(2*np.pi*t)),\"sb\":(-i+0.1*np.cos(2*np.pi*t))})",
            "    runs.append((f\"run{i}\",{\"tables\":{\"T\":df}}))",
            "X=np.arange(5,dtype=float).reshape(-1,1)",
            "cube=build_influence_t_cube(runs,X=X,feat_names=[\"f1\"],table=\"T\",sigs=[\"sa\",\"sb\"],ref_label=\"run0\",mode=\"value\",max_frames=20,max_time_points=200)",
            "assert cube.cube.shape[1:]==(1,2), cube.cube.shape",
            "c1=float(np.nanmean(cube.cube[:,0,0])); c2=float(np.nanmean(cube.cube[:,0,1]))",
            "assert c1>0.9, c1",
            "assert c2<-0.9, c2",
            "print('INFLUENCE_T_OK',c1,c2)",
        ])
        steps.append(
            _run_step(
                name="influence_t_synth",
                cmd=[preferred_python, "-c", synth_cmd],
                cwd=repo_root,
                out_dir=out_dir,
                env=env,
                timeout_s=120,
            )
        )

    # 5) Discrete events (event_markers) smoke test
    if level in ("standard", "full"):
        ev_cmd = (
            "import pandas as pd; "
            "from pneumo_solver_ui.diag.event_markers import scan_run_tables, events_to_frame; "
            "df=pd.DataFrame({'t':[0.0,0.5,1.0,1.5],'valve_open':[0,0,1,1]}); "
            "evs=scan_run_tables({'main':df}, rising_only=True); "
            "ev_df=events_to_frame(evs); "
            "assert len(ev_df)==1, len(ev_df); "
            "print('EVENT_MARKERS_OK', len(ev_df))"
        )
        steps.append(
            _run_step(
                name="event_markers_smoke",
                cmd=[preferred_python, "-c", ev_cmd],
                cwd=repo_root,
                out_dir=out_dir,
                env=env,
                timeout_s=120,
            )
        )

    # 6) WorldRoad surface schema compatibility smoke (legacy UI h/w/k)
    # P0: UI edits must affect physics (no silent defaulting).
    if level in ("standard", "full"):
        rs_cmd = "\n".join([
            "import numpy as np",
            "from pneumo_solver_ui import road_surface",
            "# --- bump: legacy h/w should map to A/sigma (w treated as FWHM) ---",
            "A=0.04; w=0.6",
            "spec={'type':'bump','h':A,'w':w,'x0':0.0,'y0':0.0}",
            "surf=road_surface.make_surface(spec)",
            "z0=float(surf.h(0.0,0.0))",
            "assert abs(z0-A)<1e-6, (z0,A)",
            "z_half=float(surf.h(w/2.0,0.0))",
            "assert abs(z_half-(A/2.0))<5e-3, (z_half,A/2.0)",
            "# --- ridge_x: legacy h/w should map to A/width ---",
            "A2=0.05; w2=0.4",
            "spec={'type':'ridge_x','h':A2,'w':w2,'x0':0.0}",
            "surf=road_surface.make_surface(spec)",
            "z_mid=float(surf.h(0.0,0.0))",
            "assert abs(z_mid-(A2*0.5))<1e-3, (z_mid,A2*0.5)",
            "# --- ridge_cosine_bump: legacy h/w/k should affect shape ---",
            "A3=0.03; L=0.2; k=3.0",
            "spec={'type':'ridge_cosine_bump','h':A3,'w':L,'k':k,'u0':0.0,'angle_deg':0.0}",
            "surf=road_surface.make_surface(spec)",
            "z_end=float(surf.h(L,0.0))",
            "assert abs(z_end-A3)<1e-6, (z_end,A3)",
            "z_half=float(surf.h(L/2.0,0.0))",
            "# base at s=0.5 -> 0.5, so z=A*(0.5**k)",
            "z_ref=A3*(0.5**k)",
            "assert abs(z_half-z_ref)<2e-3, (z_half,z_ref)",
            "print('ROAD_SURFACE_SCHEMA_OK',z0,z_half,z_mid,z_end)",
        ])
        steps.append(
            _run_step(
                name="road_surface_schema_smoke",
                cmd=[preferred_python, "-c", rs_cmd],
                cwd=repo_root,
                out_dir=out_dir,
                env=env,
                timeout_s=120,
            )
        )

    # 7) Suite normalization smoke: vx0_м_с (canonical speed key) + auto t_end from road_len_m.
    # P0: UI поля должны реально влиять на solver (без молчаливых дефолтов).
    if level in ("standard", "full"):
        sl_cmd = "\n".join([
            "from pneumo_solver_ui.opt_worker_v3_margins_energy import build_test_suite",
            "cfg={'suite':[{'имя':'wr','тип':'worldroad','включен':True,'dt':0.01,'t_end':5.0,'vx0_м_с':20.0,'road_len_m':200.0,'auto_t_end_from_len':True,'road_surface':'flat'}]}",
            "tests=build_test_suite(cfg)",
            "assert len(tests)==1, len(tests)",
            "name,test,dt,t_end,targets=tests[0]",
            "assert abs(dt-0.01)<1e-12, dt",
            "assert abs(t_end-10.0)<1e-9, t_end",
            "assert abs(float(test.get('vx0_м_с', -1))-20.0)<1e-12, test.get('vx0_м_с')",
            "cfg2={'suite':[{'имя':'wr2','тип':'worldroad','включен':True,'dt':0.01,'t_end':7.0,'vx0_м_с':30.0,'road_len_m':200.0,'auto_t_end_from_len':False,'road_surface':'flat'}]}",
            "tests2=build_test_suite(cfg2)",
            "name2,test2,dt2,t_end2,targets2=tests2[0]",
            "assert abs(t_end2-7.0)<1e-9, t_end2",
            "assert abs(float(test2.get('vx0_м_с', -1))-30.0)<1e-12, test2.get('vx0_м_с')",
            "print('SUITE_SPEED_LEN_OK', t_end, t_end2)",
        ])
        steps.append(
            _run_step(
                name="suite_speed_len_smoke",
                cmd=[preferred_python, "-c", sl_cmd],
                cwd=repo_root,
                out_dir=out_dir,
                env=env,
                timeout_s=120,
            )
        )

    # 7) Penalty targets registry smoke: UI must match candidate_penalty keys.
    if level in ("standard", "full"):
        pt_cmd = "\n".join([
            "import inspect, re, json",
            "from pathlib import Path",
            "from pneumo_solver_ui import opt_worker_v3_margins_energy as ow",
            "src = inspect.getsource(ow.candidate_penalty)",
            "keys = re.findall(r\"if\\s+['\\\"]([^'\\\"]+)['\\\"]\\s+in\\s+targets\", src)",
            "keys = sorted(set(keys))",
            "reg = sorted(set(getattr(ow, 'penalty_target_keys')()))",
            "assert keys == reg, (keys, reg)",
            "p = Path(ow.__file__).resolve().parent / 'default_suite.json'",
            "data = json.loads(p.read_text(encoding='utf-8'))",
            "seen = set()",
            "for row in data:",
            "    if isinstance(row, dict):",
            "        for k,v in row.items():",
            "            if isinstance(k, str) and k.startswith('target_') and v not in (None, ''):",
            "                seen.add(k[len('target_'):])",
            "assert (seen & set(reg)), (sorted(seen), reg)",
            "print('PENALTY_TARGETS_REGISTRY_OK', len(reg))",
        ])
        steps.append(
            _run_step(
                name="penalty_targets_registry_smoke",
                cmd=[preferred_python, "-c", pt_cmd],
                cwd=repo_root,
                out_dir=out_dir,
                env=env,
                timeout_s=120,
            )
        )

    # 8) Integrator autotune smoke.
    # Standard level checks core convergence (cheap ~few seconds), full level also
    # verifies step-doubling local error control.
    if level in ("standard", "full"):
        integ_cmd = [preferred_python, "-m", "pneumo_solver_ui.tools.integrator_autotune_smoke_check"]
        integ_timeout = 120
        if level == "full":
            integ_cmd.append("--check_err_control")
            integ_timeout = 240
        steps.append(
            _run_step(
                name="integrator_autotune_smoke",
                cmd=integ_cmd,
                cwd=repo_root,
                out_dir=out_dir,
                env=env,
                timeout_s=integ_timeout,
            )
        )

    ok = all(s.ok for s in steps)

    finished = _now_iso()
    dt_total = time.time() - t0
    summary = {
        "level": level,
        "steps_total": len(steps),
        "steps_failed": [s.name for s in steps if not s.ok],
        "duration_s_total": float(dt_total),
        "python_executable": str(sys.executable),
        "preferred_cli_python": str(preferred_python),
        "effective_workspace_dir": str(workspace_dir),
        "workspace_required_dirs": list(REQUIRED_WORKSPACE_DIRS),
    }

    report = SelfcheckReport(
        schema="selfcheck_report",
        schema_version="1.0.0",
        release=release,
        run_id=run_id,
        started_at=started,
        finished_at=finished,
        ok=bool(ok),
        steps=steps,
        summary=summary,
    )

    # Write JSON/MD (best-effort)
    try:
        (out_dir / "selfcheck_report.json").write_text(json_dumps(to_jsonable(asdict(report)), indent=2), encoding="utf-8")
    except Exception:
        pass

    try:
        md = ["# Selfcheck report", "", f"- Release: `{release}`", f"- Run ID: `{run_id}`", f"- Level: `{level}`", f"- OK: **{ok}**", f"- Started: {started}", f"- Finished: {finished}", f"- Python: `{sys.executable}`", f"- Preferred helper python: `{preferred_python}`", f"- Effective workspace: `{workspace_dir}`", ""]
        md.append("## Steps")
        for s in steps:
            md.append(f"- `{s.name}`: {'OK' if s.ok else 'FAIL'} (rc={s.rc}, {s.duration_s:.2f}s)")
            if s.notes:
                md.append(f"  - notes: {s.notes}")
            md.append(f"  - stdout: `{s.stdout_rel}`")
            md.append(f"  - stderr: `{s.stderr_rel}`")
        md.append("")
        (out_dir / "selfcheck_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    except Exception:
        pass

    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Run autonomous selfcheck suite (best-effort).")
    ap.add_argument("--repo_root", default=str(Path(__file__).resolve().parents[2]), help="Repository root")
    ap.add_argument("--out_dir", default="", help="Output directory (default: <repo>/send_bundles/_selfcheck_tmp)")
    ap.add_argument("--level", choices=["quick", "standard", "full"], default="standard")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (repo_root / "send_bundles" / "_selfcheck_tmp").resolve()

    rep = run_selfcheck_suite(repo_root=repo_root, out_dir=out_dir, level=args.level)
    # Exit code: 0 if ok else 2
    return 0 if rep.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
