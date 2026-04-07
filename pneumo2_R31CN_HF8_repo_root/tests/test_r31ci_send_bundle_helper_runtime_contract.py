from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.tools import health_report as hr
from pneumo_solver_ui.tools.make_send_bundle import (
    _health_report_failure_payload,
    _resolve_cli_python_executable,
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


def test_launcher_source_uses_console_python_for_send_results_gui_and_exports_shared_venv_python() -> None:
    src = (ROOT / "START_PNEUMO_APP.py").read_text(encoding="utf-8", errors="replace")

    assert 'env["PNEUMO_SHARED_VENV_PYTHON"] = str(_venv_python(prefer_gui=False))' in src
    assert '"PNEUMO_SHARED_VENV_PYTHON": env["PNEUMO_SHARED_VENV_PYTHON"]' in src
    assert 'py_cli = _venv_python(prefer_gui=False)' in src
    assert 'env["PNEUMO_SHARED_VENV_PYTHON"] = str(py_cli)' in src
    assert 'send_results_gui_python' in src


def test_make_send_bundle_source_records_shared_venv_python_in_bundle_meta_env() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "make_send_bundle.py").read_text(encoding="utf-8", errors="replace")

    assert '"PNEUMO_SHARED_VENV_PYTHON"' in src
    assert '"PNEUMO_VENV_PYTHON"' in src
