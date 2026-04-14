from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.tools import health_report as hr
from pneumo_solver_ui.tools.make_send_bundle import (
    _collect_anim_latest_bundle_diagnostics,
    _health_report_failure_payload,
    _resolve_cli_python_executable,
    _runtime_python_truth_override,
)

ROOT = Path(__file__).resolve().parents[1]


def _minimal_bundle_with_anim_npz(tmp_path: Path) -> Path:
    zip_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle/meta.json", json.dumps({"release": "pytest", "created_at": "2026-04-01T00:00:00"}, ensure_ascii=False))
        zf.writestr("validation/validation_report.json", json.dumps({"ok": True, "errors": [], "warnings": []}, ensure_ascii=False))
        zf.writestr("dashboard/dashboard.json", json.dumps({"errors": [], "warnings": []}, ensure_ascii=False))
        zf.writestr("triage/triage_report.json", json.dumps({"red_flags": []}, ensure_ascii=False))
        zf.writestr("triage/latest_anim_pointer_diagnostics.json", json.dumps({"anim_latest_available": True}, ensure_ascii=False))
        zf.writestr("workspace/exports/anim_latest.npz", b"not-a-real-npz")
    return zip_path


def test_collect_health_report_survives_missing_geometry_acceptance_helper(tmp_path: Path, monkeypatch) -> None:
    zip_path = _minimal_bundle_with_anim_npz(tmp_path)

    orig_import = hr.importlib.import_module

    def fake_import(name: str, package=None):
        if name == "pneumo_solver_ui.geometry_acceptance_contract":
            raise ModuleNotFoundError("No module named 'numpy'")
        return orig_import(name, package)

    monkeypatch.setattr(hr.importlib, "import_module", fake_import)

    rep = hr.collect_health_report(zip_path)
    geom = dict(rep.signals.get("geometry_acceptance") or {})

    assert rep.ok is True
    assert geom.get("inspection_status") == "unavailable"
    assert "No module named 'numpy'" in str(geom.get("error") or "")
    assert any("geometry acceptance helper unavailable" in str(x) for x in rep.notes)


def test_resolve_cli_python_executable_prefers_launcher_shared_venv_envvar(tmp_path: Path, monkeypatch) -> None:
    scripts = tmp_path / "Scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    py = scripts / "python.exe"
    py.write_text("", encoding="utf-8")
    monkeypatch.setenv("PNEUMO_SHARED_VENV_PYTHON", str(py))

    assert _resolve_cli_python_executable() == str(py)


def test_health_report_failure_payload_records_builder_python_truth() -> None:
    payload = _health_report_failure_payload(Path("bundle.zip"), "boom")
    err = dict((payload.get("signals") or {}).get("health_report_error") or {})

    assert payload["schema"] == "health_report"
    assert payload["ok"] is False
    assert err.get("python_executable")
    assert err.get("preferred_cli_python")
    assert err.get("python_executable_current")
    assert err.get("python_runtime_source")


def test_runtime_python_truth_prefers_shared_venv_python_for_bundle_meta(tmp_path: Path, monkeypatch) -> None:
    scripts = tmp_path / "SharedVenv" / "Scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shared_python = scripts / "python.exe"
    shared_python.write_text("", encoding="utf-8")
    (scripts.parent / "pyvenv.cfg").write_text("home = C:/Python314\n", encoding="utf-8")
    current_pythonw = tmp_path / "base" / "pythonw.exe"
    current_pythonw.parent.mkdir(parents=True, exist_ok=True)
    current_pythonw.write_text("", encoding="utf-8")

    monkeypatch.setenv("PNEUMO_SHARED_VENV_PYTHON", str(shared_python))
    monkeypatch.setattr("pneumo_solver_ui.tools.make_send_bundle.sys.executable", str(current_pythonw))
    monkeypatch.setattr("pneumo_solver_ui.tools.make_send_bundle.sys.prefix", str(current_pythonw.parent))
    monkeypatch.setattr("pneumo_solver_ui.tools.make_send_bundle.sys.base_prefix", str(current_pythonw.parent))

    truth = _runtime_python_truth_override()

    assert truth["python_executable"] == str(shared_python.resolve())
    assert truth["preferred_cli_python"] == str(shared_python)
    assert truth["python_executable_current"] == str(current_pythonw)
    assert truth["venv_active"] is True
    assert truth["python_runtime_source"] == "preferred_cli_python"


def test_collect_anim_latest_bundle_diagnostics_uses_shared_cli_python_when_current_process_differs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    scripts = tmp_path / "SharedVenv" / "Scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shared_python = scripts / "python.exe"
    shared_python.write_text("", encoding="utf-8")
    current_pythonw = tmp_path / "base" / "pythonw.exe"
    current_pythonw.parent.mkdir(parents=True, exist_ok=True)
    current_pythonw.write_text("", encoding="utf-8")
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / "send_bundles"
    out_dir.mkdir(parents=True, exist_ok=True)

    captured: dict[str, object] = {}

    def _fake_run(cmd, cwd=None, timeout_s=0.0):
        captured["cmd"] = list(cmd)
        captured["cwd"] = cwd
        payload = {"anim_latest_available": False, "anim_latest_visual_reload_inputs": [], "anim_latest_issues": []}
        return 0, json.dumps(payload, ensure_ascii=False), ""

    monkeypatch.setenv("PNEUMO_SHARED_VENV_PYTHON", str(shared_python))
    monkeypatch.setattr("pneumo_solver_ui.tools.make_send_bundle.sys.executable", str(current_pythonw))
    monkeypatch.setattr("pneumo_solver_ui.tools.make_send_bundle._run", _fake_run)

    diag, md = _collect_anim_latest_bundle_diagnostics(out_dir, repo_root=repo_root)

    assert diag["anim_latest_available"] is False
    assert "Anim Latest Pointer Diagnostics" in md
    assert captured["cmd"][0] == str(shared_python)
    assert captured["cwd"] == repo_root


def test_launcher_source_uses_console_python_for_send_results_gui_and_exports_shared_venv_python() -> None:
    src = (ROOT / "START_PNEUMO_APP.py").read_text(encoding="utf-8", errors="replace")

    assert '"PNEUMO_SHARED_VENV_PYTHON": str(_venv_python(prefer_gui=False))' in src
    assert 'py_cli = _venv_python(prefer_gui=False)' in src
    assert 'env["PNEUMO_SHARED_VENV_PYTHON"] = str(py_cli)' in src
    assert 'send_results_gui_python' in src


def test_make_send_bundle_source_records_shared_venv_python_in_bundle_meta_env() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "make_send_bundle.py").read_text(encoding="utf-8", errors="replace")

    assert '"PNEUMO_SHARED_VENV_PYTHON"' in src
    assert '"PNEUMO_VENV_PYTHON"' in src
