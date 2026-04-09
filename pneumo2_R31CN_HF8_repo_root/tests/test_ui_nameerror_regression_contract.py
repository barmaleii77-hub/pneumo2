from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
ANIM_BUILDERS_PATH = ROOT / "pneumo_solver_ui" / "ui_animation_results_builders.py"
SURFACE_SECTION_HELPERS_PATH = ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


def test_ui_entrypoints_keep_nameerror_regression_guards() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    builders_text = ANIM_BUILDERS_PATH.read_text(encoding="utf-8")
    surface_section_text = SURFACE_SECTION_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_surface_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_results_surface_section_helpers import (" in heavy_text
    assert '"route_write_view_box": route_write_view_box' in builders_text
    assert '"route_write_view_box": route_write_view_box' in surface_section_text
    assert "def _json_safe(" in heavy_text
    assert "json_safe_fn=_json_safe" in heavy_text
    assert "tobj.get(" not in app_text


def test_ui_entrypoints_have_no_f821_undefined_names() -> None:
    if importlib.util.find_spec("ruff") is None:
        pytest.skip("ruff is not installed in the active environment")

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            str(APP_PATH),
            str(HEAVY_PATH),
            "--select",
            "F821",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    stdout = res.stdout or ""
    stderr = res.stderr or ""
    assert res.returncode == 0, (stdout + "\n" + stderr).strip()
