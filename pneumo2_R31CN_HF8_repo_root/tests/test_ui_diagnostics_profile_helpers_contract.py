from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.ui_diagnostics_profile_helpers import build_ui_diagnostics_zip_writer


ROOT = Path(__file__).resolve().parents[1]


def test_build_ui_diagnostics_zip_writer_preserves_optional_json_safe(tmp_path: Path) -> None:
    here = tmp_path / "pneumo_solver_ui"
    workspace = here / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    def _json_safe(obj):
        if isinstance(obj, dict):
            return {key: _json_safe(value) for key, value in obj.items()}
        if isinstance(obj, set):
            return sorted(obj)
        return obj

    write_zip = build_ui_diagnostics_zip_writer(
        here=here,
        workspace_dir=workspace,
        log_dir=None,
        app_release="HF8",
        json_safe_fn=_json_safe,
    )
    out_zip = write_zip(
        meta={"tags": {"a", "b"}},
        include_logs=False,
        include_results=False,
        include_calibration=False,
        include_workspace=False,
    )

    with zipfile.ZipFile(out_zip) as zf:
        meta = json.loads(zf.read("meta.json").decode("utf-8"))

    assert sorted(meta["tags"]) == ["a", "b"]


def test_active_entrypoints_use_shared_diagnostics_profile_builder() -> None:
    helper_source = (ROOT / "pneumo_solver_ui" / "ui_diagnostics_profile_helpers.py").read_text(encoding="utf-8")
    app_source = (ROOT / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    heavy_source = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")

    assert "def build_ui_diagnostics_zip_writer" in helper_source
    assert "from pneumo_solver_ui.ui_diagnostics_profile_helpers import (" in app_source
    assert "from pneumo_solver_ui.ui_diagnostics_profile_helpers import (" in heavy_source
    assert "build_ui_diagnostics_zip_writer(" in app_source
    assert "build_ui_diagnostics_zip_writer(" in heavy_source
    assert "json_safe_fn=_json_safe" in heavy_source
