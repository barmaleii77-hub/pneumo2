from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from pneumo_solver_ui.tools.make_send_bundle import _resolve_cli_python_executable
from pneumo_solver_ui.tools.triage_report import generate_triage_report

ROOT = Path(__file__).resolve().parents[1]


def test_generate_triage_report_does_not_flag_stopped_ui_rc1_as_failure(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    rr = runs_dir / "run_registry.jsonl"
    rows = [
        {
            "event": "run_end",
            "run_type": "ui_session",
            "run_id": "UI_20260401_145859",
            "status": "stopped",
            "rc": 1,
            "launcher_stop_requested": True,
            "launcher_stop_source": "window_close",
            "launcher_ready_source": "http",
            "ts": "2026-04-01T15:15:10",
        },
        {
            "event": "run_end",
            "run_type": "diagnostics",
            "run_id": "RUN_FAIL",
            "status": "fail",
            "rc": 2,
            "ts": "2026-04-01T15:16:00",
        },
    ]
    rr.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")

    md, summary = generate_triage_report(tmp_path, keep_last_n=1)
    recent = list((summary.get("run_registry") or {}).get("recent_failures") or [])

    assert len(recent) == 1
    assert recent[0]["run_id"] == "RUN_FAIL"
    assert recent[0]["status"] == "fail"
    assert "UI_20260401_145859" not in [str(x.get("run_id")) for x in recent]
    assert "stop_source=window_close" in md
    assert "ready_source=http" in md


def test_run_artifacts_import_and_anim_diagnostics_work_without_pandas(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    code = r'''
import builtins, json, os
orig = builtins.__import__
def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "pandas" or name.startswith("pandas."):
        raise ModuleNotFoundError("No module named 'pandas'")
    return orig(name, globals, locals, fromlist, level)
builtins.__import__ = fake_import
import pneumo_solver_ui.run_artifacts as ra
print(json.dumps(ra.collect_anim_latest_diagnostics_summary(include_meta=False), ensure_ascii=False))
'''
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
    env["PNEUMO_WORKSPACE_DIR"] = str(workspace)
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=str(ROOT))

    assert res.returncode == 0, res.stderr
    diag = json.loads(res.stdout)
    assert "anim_latest_available" in diag
    assert diag.get("error") is None



def test_resolve_cli_python_executable_prefers_console_python_when_running_under_pythonw(tmp_path: Path, monkeypatch) -> None:
    scripts = tmp_path / "Scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    pyw = scripts / "pythonw.exe"
    py = scripts / "python.exe"
    pyw.write_text("", encoding="utf-8")
    py.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "executable", str(pyw))

    assert _resolve_cli_python_executable() == str(py)



def test_launcher_source_wires_stop_source_into_registry_and_logs() -> None:
    src = (ROOT / "START_PNEUMO_APP.py").read_text(encoding="utf-8", errors="replace")
    assert "launcher_stop_source" in src
    assert 'command=lambda: self.stop_app(reason="button_stop")' in src
    assert 'self.stop_app(reason="window_close")' in src
    assert 'launcher_stop_source=(self._launcher_stop_source or None)' in src
