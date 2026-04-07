from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.ui_persistence import load_autosave, save_autosave
from pneumo_solver_ui.tools.validate_send_bundle import validate_send_bundle


def _write_minimal_bundle(tmp_path: Path, *, ui_state_entries: dict[str, object]) -> Path:
    zip_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle/meta.json", json.dumps({"release": "pytest", "created_at": "2026-03-13T10:00:00"}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/manifest.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/summary.json", json.dumps({"added_files": 1}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/skips.json", json.dumps([], ensure_ascii=False, indent=2))
        zf.writestr("bundle/README_SEND_BUNDLE.txt", "README")
        zf.writestr("triage/triage_report.md", "# triage\n")
        zf.writestr("ui_logs/app.log", "ok\n")
        zf.writestr("workspace/exports/.gitkeep", "")
        zf.writestr("workspace/uploads/placeholder.txt", "u")
        zf.writestr("workspace/road_profiles/placeholder.txt", "r")
        zf.writestr("workspace/maneuvers/placeholder.txt", "m")
        zf.writestr("workspace/opt_runs/placeholder.txt", "o")
        for arcname, obj in ui_state_entries.items():
            if isinstance(obj, (dict, list)):
                payload = json.dumps(obj, ensure_ascii=False, indent=2)
            else:
                payload = str(obj)
            zf.writestr(arcname, payload)
    return zip_path


def test_save_autosave_mirrors_into_workspace_ui_state(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))

    primary_state = tmp_path / "external_state"
    state = {"ui_autosave_enabled": True, "ui_example_value": 42}

    ok, info = save_autosave(primary_state, state)
    assert ok is True
    assert Path(info).exists()

    mirrored = workspace / "ui_state" / "autosave_profile.json"
    assert mirrored.exists()

    data, err = load_autosave(workspace / "ui_state")
    assert err is None
    assert isinstance(data, dict)
    assert data["ui_example_value"] == 42


def test_validate_send_bundle_rejects_marker_only_ui_state(tmp_path: Path) -> None:
    zip_path = _write_minimal_bundle(
        tmp_path,
        ui_state_entries={"workspace/ui_state/_EMPTY_OR_MISSING.txt": "marker only"},
    )

    res = validate_send_bundle(zip_path)

    assert res.ok is False
    assert any("Missing UI autosave state JSON" in msg for msg in (res.report_json.get("errors") or []))
    ui_autosave = dict(res.report_json.get("ui_autosave") or {})
    assert ui_autosave["workspace_ui_state_json_present"] is False
    assert ui_autosave["workspace_ui_state_marker_files"] == ["workspace/ui_state/_EMPTY_OR_MISSING.txt"]


def test_validate_send_bundle_accepts_workspace_ui_state_json(tmp_path: Path) -> None:
    zip_path = _write_minimal_bundle(
        tmp_path,
        ui_state_entries={"workspace/ui_state/autosave_profile.json": {"ui_x": 1, "diag_build_bundle": False}},
    )

    res = validate_send_bundle(zip_path)

    assert res.ok is True
    ui_autosave = dict(res.report_json.get("ui_autosave") or {})
    assert ui_autosave["workspace_ui_state_json_present"] is True
    assert ui_autosave["workspace_ui_state_json_files"] == ["workspace/ui_state/autosave_profile.json"]


def test_sources_wire_ui_autosave_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    ui_persist_text = (root / "pneumo_solver_ui" / "ui_persistence.py").read_text(encoding="utf-8")
    make_text = (root / "pneumo_solver_ui" / "tools" / "make_send_bundle.py").read_text(encoding="utf-8")
    validate_text = (root / "pneumo_solver_ui" / "tools" / "validate_send_bundle.py").read_text(encoding="utf-8")

    assert "workspace_state_dir" in ui_persist_text
    assert "workspace/ui_state" in ui_persist_text
    assert '("ui_state", True)' in make_text
    assert "Missing UI autosave state JSON" in validate_text
    assert '"ui_autosave"' in validate_text
