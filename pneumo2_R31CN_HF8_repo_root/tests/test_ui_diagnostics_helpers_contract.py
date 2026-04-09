from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.ui_diagnostics_helpers import make_ui_diagnostics_zip_bundle


ROOT = Path(__file__).resolve().parents[1]


def test_make_ui_diagnostics_zip_bundle_writes_meta_snapshots_and_skips_runtime_noise(tmp_path: Path) -> None:
    here = tmp_path / "pneumo_solver_ui"
    workspace = here / "workspace"
    log_dir = here / "logs"
    results_dir = here / "results"
    calibration_dir = here / "calibration_runs"
    for path in (workspace, log_dir, results_dir, calibration_dir):
        path.mkdir(parents=True, exist_ok=True)

    (log_dir / "ui.log").write_text("ok", encoding="utf-8")
    (log_dir / "skip.pyc").write_bytes(b"pyc")
    (results_dir / "result.txt").write_text("done", encoding="utf-8")
    (calibration_dir / "calib.json").write_text("{}", encoding="utf-8")
    (workspace / "exports.txt").write_text("exp", encoding="utf-8")

    out_zip = make_ui_diagnostics_zip_bundle(
        here=here,
        workspace_dir=workspace,
        log_dir=log_dir,
        app_release="HF8",
        base_json={"base": 1},
        suite_json=[{"name": "s1"}],
        ranges_json={"x": [0, 1]},
        meta={"custom": "ok"},
    )

    with zipfile.ZipFile(out_zip) as zf:
        names = set(zf.namelist())
        meta = json.loads(zf.read("meta.json").decode("utf-8"))

    assert "snapshot/base_json.json" in names
    assert "snapshot/suite_json.json" in names
    assert "snapshot/ranges_json.json" in names
    assert "logs/ui.log" in names
    assert "results/result.txt" in names
    assert "calibration_runs/calib.json" in names
    assert "workspace/exports.txt" in names
    assert "logs/skip.pyc" not in names
    assert meta["app_release"] == "HF8"
    assert meta["custom"] == "ok"


def test_make_ui_diagnostics_zip_bundle_applies_optional_json_safe_to_meta(tmp_path: Path) -> None:
    here = tmp_path / "pneumo_solver_ui"
    workspace = here / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    def _json_safe(obj):
        if isinstance(obj, dict):
            return {key: _json_safe(value) for key, value in obj.items()}
        if isinstance(obj, set):
            return sorted(obj)
        return obj

    out_zip = make_ui_diagnostics_zip_bundle(
        here=here,
        workspace_dir=workspace,
        log_dir=None,
        app_release="HF8",
        meta={"tags": {"a", "b"}},
        json_safe_fn=_json_safe,
        include_logs=False,
        include_results=False,
        include_calibration=False,
        include_workspace=False,
    )

    with zipfile.ZipFile(out_zip) as zf:
        meta = json.loads(zf.read("meta.json").decode("utf-8"))

    assert sorted(meta["tags"]) == ["a", "b"]


def test_large_ui_entrypoints_import_shared_diagnostics_zip_helper() -> None:
    for rel in ("pneumo_solver_ui/app.py", "pneumo_solver_ui/pneumo_ui_app.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_diagnostics_helpers import make_ui_diagnostics_zip_bundle" in src
        assert "from pneumo_solver_ui.ui_diagnostics_profile_helpers import (" in src
        assert "make_ui_diagnostics_zip = build_ui_diagnostics_zip_writer(" in src
        assert "make_ui_diagnostics_zip_bundle" in src
        assert "def make_ui_diagnostics_zip(" not in src
