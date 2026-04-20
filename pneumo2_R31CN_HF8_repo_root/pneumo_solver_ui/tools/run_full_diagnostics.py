#!/usr/bin/env python3
"""Full project check runner (headless).

Цель
----
Сделать максимально комплексный прогон самопроверок и ключевых
пайплайнов (baseline-suite / короткий smoke оптимизации / (опционально) NPZ-калибровка)
и собрать *все артефакты* в одну папку + zip.

Это нужно, чтобы:
  • можно было сохранить одним файлом весь контекст (логи, метрики, окружение,
    результаты прогона) без копирования всей папки проекта.

Важно: скрипт не правит исходники. Он пишет только в diagnostics_runs/.

Запуск (Windows)
---------------
Рекомендуемый вариант — батник в корне проекта:
  RUN_FULL_DIAGNOSTICS_WINDOWS.bat

Или напрямую:
  .venv\\Scripts\\python.exe pneumo_solver_ui\\tools\\run_full_diagnostics.py --level full

"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"

from pneumo_solver_ui.entrypoints import canonical_streamlit_entrypoint


@dataclass
class RunResult:
    cmd: list[str]
    returncode: int
    duration_s: float
    stdout: str
    stderr: str
    # Снимки загрузки CPU/RAM вокруг запуска (лучше, чем ничего)
    sys_before: dict | None = None
    sys_after: dict | None = None


def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")


def _safe_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8", errors="replace")


def _copy_tree(src: Path, dst: Path, ignore_names: Optional[set[str]] = None) -> None:
    """Безопасное копирование дерева.

    Нужен для забора уже созданных артефактов (logs/, results/, ...)
    без падения, если папки нет.
    """
    try:
        if not src.exists():
            return

        def _ignore(_dir: str, names: list[str]) -> list[str]:
            if not ignore_names:
                return []
            return [n for n in names if n in ignore_names]

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_ignore)
    except Exception:
        # Не должно валить проверку проекта.
        try:
            _safe_write_text(dst.parent / "copy_tree_error.txt", traceback.format_exc())
        except Exception:
            pass


def _pick_python(repo_root: Path) -> str:
    # Prefer local venv python if exists (Windows/Linux)
    candidates = [
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "bin" / "python",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return sys.executable


def _sys_snapshot() -> dict:
    """Короткий снимок загрузки CPU/RAM для проверки проекта."""
    snap = {"ts": datetime.now().isoformat(timespec="seconds")}
    try:
        import psutil  # type: ignore

        # Короткий интервал, чтобы cpu_percent был осмысленным.
        snap["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        try:
            snap["virtual_memory"] = psutil.virtual_memory()._asdict()
            snap["swap_memory"] = psutil.swap_memory()._asdict()
        except Exception:
            pass

        try:
            p = psutil.Process()
            snap["proc_memory"] = p.memory_info()._asdict()
            snap["proc_cpu_times"] = p.cpu_times()._asdict()
        except Exception:
            pass
    except Exception:
        snap["psutil_error"] = traceback.format_exc()
    return snap


def _pick_free_port() -> int:
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


def _ui_smoke_streamlit(
    python_exe: Path,
    repo_root: Path,
    app_path: Path,
    out_dir: Path,
    timeout_s: float = 30.0,
) -> dict:
    """Headless smoke-test UI: стартуем Streamlit и пробуем HTTP GET /.

    Это не заменяет ручного прогона UI, но ловит критические ошибки уровня import/NameError.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    port = _pick_free_port()
    url = f"http://127.0.0.1:{port}"

    cmd = [
        str(python_exe),
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.headless",
        "true",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
    ]

    meta: dict = {
        "cmd": cmd,
        "url": url,
        "timeout_s": timeout_s,
        "started": False,
        "http_ok": False,
        "http_status": None,
        "returncode": None,
        "duration_s": None,
        "exception": None,
    }

    t0 = time.perf_counter()
    sys_before = _sys_snapshot()
    proc = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    html_snippet: str | None = None

    try:
        try:
            import requests  # type: ignore
        except Exception:
            requests = None

        if requests is None:
            meta["exception"] = "requests_not_available"
            time.sleep(min(timeout_s, 3.0))
        else:
            while time.perf_counter() - t0 < timeout_s:
                if proc.poll() is not None:
                    break
                try:
                    r = requests.get(url, timeout=1.0)
                    meta["http_status"] = int(r.status_code)
                    # Нам важно, что сервер жив. Даже 404 означает, что слушает.
                    if 200 <= r.status_code < 500:
                        meta["http_ok"] = True
                        meta["started"] = True
                        html_snippet = (r.text or "")[:200000]
                        break
                except Exception as e:
                    meta["exception"] = repr(e)
                time.sleep(0.5)
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

        try:
            out, _ = proc.communicate(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            out, _ = proc.communicate(timeout=10)

        meta["returncode"] = proc.returncode
        meta["duration_s"] = float(time.perf_counter() - t0)

        _safe_write_text(out_dir / "streamlit_combined.log", out or "")
        if html_snippet is not None:
            _safe_write_text(out_dir / "root_html_snippet.html", html_snippet)
        _safe_write_json(out_dir / "ui_smoke_meta.json", meta)

    return meta


def _run(cmd: list[str], cwd: Path, timeout_s: Optional[float] = None) -> RunResult:
    sys_before = _sys_snapshot()
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
        dt = time.perf_counter() - t0
        sys_after = _sys_snapshot()
        return RunResult(
            cmd=[str(x) for x in cmd],
            returncode=int(proc.returncode),
            duration_s=float(dt),
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            sys_before=sys_before,
            sys_after=sys_after,
        )
    except subprocess.TimeoutExpired as e:
        dt = time.perf_counter() - t0
        sys_after = _sys_snapshot()
        # e.stdout/e.stderr могут быть None/bytes
        so = e.stdout
        se = e.stderr
        if isinstance(so, bytes):
            so = so.decode(errors="replace")
        if isinstance(se, bytes):
            se = se.decode(errors="replace")
        return RunResult(
            cmd=[str(x) for x in cmd],
            returncode=124,
            duration_s=float(dt),
            stdout=str(so or ""),
            stderr=str(se or "TIMEOUT"),
            sys_before=sys_before,
            sys_after=sys_after,
        )
    except Exception:
        dt = time.perf_counter() - t0
        sys_after = _sys_snapshot()
        return RunResult(
            cmd=[str(x) for x in cmd],
            returncode=125,
            duration_s=float(dt),
            stdout="",
            stderr=traceback.format_exc(),
            sys_before=sys_before,
            sys_after=sys_after,
        )

def _zip_dir(src_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in src_dir.rglob("*"):
            if p.is_dir():
                continue
            arc = p.relative_to(src_dir)
            z.write(p, arcname=str(arc))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=["minimal", "standard", "full"], default="standard")
    ap.add_argument("--out_root", default="diagnostics_runs", help="Куда складывать diagnostics_runs/")
    ap.add_argument("--osc_dir", default=None, help="Папка с NPZ осциллограммами (опционально)")
    ap.add_argument("--skip_ui_smoke", action="store_true", help="Не запускать headless UI smoke тест (streamlit run + HTTP GET)")
    ap.add_argument("--ui_smoke_timeout_s", type=float, default=30.0, help="Таймаут UI smoke теста, секунды")
    ap.add_argument("--no_zip", action="store_true", help="Не упаковывать итоговую папку в zip")
    ap.add_argument("--timeout_rootcause", type=int, default=0, help="Таймаут root_cause_report (сек), 0=без таймаута")
    ap.add_argument("--run_opt_smoke", action="store_true", help="Прогнать короткий smoke оптимизации (полезно для CI)")
    ap.add_argument("--opt_minutes", type=float, default=0.25, help="Длительность smoke оптимизации (мин).")
    ap.add_argument("--opt_jobs", type=int, default=1, help="Параллельность smoke оптимизации (jobs).")
    args = ap.parse_args()

    this_file = Path(__file__).resolve()
    pneumo_dir = this_file.parent.parent  # pneumo_solver_ui/
    repo_root = pneumo_dir.parent

    python_exe = _pick_python(repo_root)

    out_root = Path(args.out_root).expanduser().resolve()
    run_dir = out_root / f"RUN_{_ts()}_full_diagnostics_{args.level}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # meta
    meta: Dict[str, Any] = {
        "ts": _ts(),
        "level": args.level,
        "python_exe": python_exe,
        "sys_executable": sys.executable,
        "platform": platform.platform(),
        "python": sys.version,
        "cwd": os.getcwd(),
        "repo_root": str(repo_root),
        "pneumo_dir": str(pneumo_dir),
        "argv": sys.argv,
    }
    _safe_write_json(run_dir / "meta.json", meta)

    # copy key configs
    cfg_dir = run_dir / "config"
    for fn in [
        "default_base.json",
        "default_suite.json",
        "default_ranges.json",
        "component_passport.json",
    ]:
        src = pneumo_dir / fn
        if src.exists():
            (cfg_dir / fn).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, cfg_dir / fn)

    rc = 0
    zip_path = run_dir.with_suffix(".zip")

    try:
        # environment capture
        env_dir = run_dir / "env"
        rr = _run([python_exe, "-m", "pip", "freeze"], cwd=repo_root)
        _safe_write_text(env_dir / "pip_freeze.txt", rr.stdout + ("\n\nSTDERR:\n" + rr.stderr if rr.stderr else ""))

        rr2 = _run([python_exe, "-m", "pip", "check"], cwd=repo_root)
        _safe_write_text(env_dir / "pip_check.txt", rr2.stdout + ("\n\nSTDERR:\n" + rr2.stderr if rr2.stderr else ""))

        # --- static checks (compileall + ruff undefined names) ---
        static_dir = run_dir / "static_checks"
        try:
            rr_ca = _run([python_exe, "-m", "compileall", "-q", str(pneumo_dir)], cwd=repo_root)
            _safe_write_text(static_dir / "compileall.txt", rr_ca.stdout + ("\n\nSTDERR:\n" + rr_ca.stderr if rr_ca.stderr else ""))
            _safe_write_json(static_dir / "compileall_meta.json", {"returncode": rr_ca.returncode, "duration_s": rr_ca.duration_s, "cmd": rr_ca.cmd})
        except Exception:
            _safe_write_text(static_dir / "compileall_failed.txt", traceback.format_exc())

        try:
            rr_rf = _run([python_exe, "-m", "ruff", "check", str(pneumo_dir), "--select", "F821"], cwd=repo_root)
            _safe_write_text(static_dir / "ruff_F821.txt", rr_rf.stdout + ("\n\nSTDERR:\n" + rr_rf.stderr if rr_rf.stderr else ""))
            _safe_write_json(static_dir / "ruff_F821_meta.json", {"returncode": rr_rf.returncode, "duration_s": rr_rf.duration_s, "cmd": rr_rf.cmd})
        except Exception:
            _safe_write_text(static_dir / "ruff_failed.txt", traceback.format_exc())

        # copy existing app logs (if any)
        _copy_tree(pneumo_dir / "logs", run_dir / "logs", ignore_names={"__pycache__"})

        # --- UI smoke (headless Streamlit run) ---
        if (not args.skip_ui_smoke) and (args.level in {"standard", "full"}):
            try:
                _ui_smoke_streamlit(
                    Path(python_exe),
                    repo_root,
                    canonical_streamlit_entrypoint(here=__file__),
                    run_dir / "ui_smoke",
                    timeout_s=float(args.ui_smoke_timeout_s),
                )
            except Exception:
                _safe_write_text(run_dir / "ui_smoke_failed.txt", traceback.format_exc())

        # --- self_check ---
        checks_dir = run_dir / "checks"
        rr_sc = _run([python_exe, str(pneumo_dir / "self_check.py")], cwd=pneumo_dir)
        _safe_write_text(checks_dir / "self_check.txt", rr_sc.stdout + ("\n\nSTDERR:\n" + rr_sc.stderr if rr_sc.stderr else ""))
        _safe_write_json(checks_dir / "self_check_meta.json", {"returncode": rr_sc.returncode, "duration_s": rr_sc.duration_s, "cmd": rr_sc.cmd, "sys_before": rr_sc.sys_before, "sys_after": rr_sc.sys_after})

        rr_pc = _run([python_exe, str(pneumo_dir / "passport_check.py")], cwd=pneumo_dir)
        _safe_write_text(checks_dir / "passport_check.txt", rr_pc.stdout + ("\n\nSTDERR:\n" + rr_pc.stderr if rr_pc.stderr else ""))
        _safe_write_json(checks_dir / "passport_check_meta.json", {"returncode": rr_pc.returncode, "duration_s": rr_pc.duration_s, "cmd": rr_pc.cmd, "sys_before": rr_pc.sys_before, "sys_after": rr_pc.sys_after})

        # --- baseline root cause report (runs the whole default_suite) ---
        reports_dir = run_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_prefix = (reports_dir / "baseline_root_cause").resolve()
        cmd_rc = [python_exe, str(pneumo_dir / "root_cause_report.py"), "--out", str(out_prefix)]
        timeout = None if int(args.timeout_rootcause) <= 0 else int(args.timeout_rootcause)
        rr_rc = _run(cmd_rc, cwd=repo_root, timeout_s=timeout)
        _safe_write_text(reports_dir / "root_cause_report_stdout.txt", rr_rc.stdout)
        _safe_write_text(reports_dir / "root_cause_report_stderr.txt", rr_rc.stderr)
        _safe_write_json(reports_dir / "root_cause_report_meta.json", {"returncode": rr_rc.returncode, "duration_s": rr_rc.duration_s, "cmd": rr_rc.cmd, "sys_before": rr_rc.sys_before, "sys_after": rr_rc.sys_after})

        # --- optional: optimization smoke ---
        if args.run_opt_smoke or args.level in {"standard", "full"}:
            try:
                opt_dir = run_dir / "opt_smoke"
                opt_dir.mkdir(parents=True, exist_ok=True)
                out_csv = (opt_dir / "opt_smoke.csv").resolve()
                cmd_opt = [
                    python_exe,
                    str(pneumo_dir / "opt_worker_v3_margins_energy.py"),
                    "--minutes",
                    str(args.opt_minutes),
                    "--jobs",
                    str(args.opt_jobs),
                    "--model",
                    str(pneumo_dir / "model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py"),
                    "--out",
                    str(out_csv),
                    "--suite_json",
                    str(pneumo_dir / "default_suite.json"),
                    "--base_json",
                    str(pneumo_dir / "default_base.json"),
                    "--ranges_json",
                    str(pneumo_dir / "default_ranges.json"),
                ]
                rr_opt = _run(cmd_opt, cwd=repo_root)
                _safe_write_text(opt_dir / "opt_stdout.txt", rr_opt.stdout)
                _safe_write_text(opt_dir / "opt_stderr.txt", rr_opt.stderr)
                _safe_write_json(opt_dir / "opt_meta.json", {"returncode": rr_opt.returncode, "duration_s": rr_opt.duration_s, "cmd": rr_opt.cmd, "sys_before": rr_opt.sys_before, "sys_after": rr_opt.sys_after})
            except Exception:
                _safe_write_text(run_dir / "opt_smoke_failed.txt", traceback.format_exc())

        # --- optional: NPZ autopilot (if osc_dir provided) ---
        if args.osc_dir:
            osc_dir = Path(args.osc_dir).expanduser().resolve()
            npz_dir = run_dir / "npz_autopilot"
            npz_dir.mkdir(parents=True, exist_ok=True)
            cmd_npz = [
                python_exe,
                str(pneumo_dir / "calibration" / "pipeline_npz_autopilot_v19.py"),
                "--osc_dir",
                str(osc_dir),
                "--out_dir",
                str(npz_dir),
                "--mode",
                "minimal" if args.level != "full" else "full",
            ]
            rr_npz = _run(cmd_npz, cwd=repo_root)
            _safe_write_text(npz_dir / "npz_autopilot_stdout.txt", rr_npz.stdout)
            _safe_write_text(npz_dir / "npz_autopilot_stderr.txt", rr_npz.stderr)
            _safe_write_json(npz_dir / "npz_autopilot_meta.json", {"returncode": rr_npz.returncode, "duration_s": rr_npz.duration_s, "cmd": rr_npz.cmd, "sys_before": rr_npz.sys_before, "sys_after": rr_npz.sys_after})

    except Exception:
        rc = 2
        _safe_write_text(run_dir / "FATAL.txt", traceback.format_exc())
    finally:
        # ---- pack zip (even on failure) ----
        if not args.no_zip:
            try:
                _zip_dir(run_dir, zip_path)
            except Exception:
                _safe_write_text(run_dir / "zip_failed.txt", traceback.format_exc())

        # Final hint for user
        print("\n=== FULL DIAGNOSTICS FINISHED ===")
        print(f"Run dir: {run_dir}")
        if not args.no_zip:
            print(f"Zip: {zip_path}")

    return int(rc)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("FATAL: run_full_diagnostics crashed")
        traceback.print_exc()
        raise SystemExit(2)
