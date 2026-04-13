from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.release_packaging import build_portable_release_tree, build_portable_release_zip


REQUIRED_ROOT_FILES = [
    "app.py",
    "START_DESKTOP_CONTROL_CENTER.cmd",
    "START_DESKTOP_CONTROL_CENTER.py",
    "START_DESKTOP_CONTROL_CENTER.pyw",
    "START_DESKTOP_CONTROL_CENTER.vbs",
    "START_DESKTOP_MAIN_SHELL.cmd",
    "START_DESKTOP_MAIN_SHELL.py",
    "START_DESKTOP_MAIN_SHELL.pyw",
    "START_DESKTOP_MAIN_SHELL.vbs",
    "START_DESKTOP_OPTIMIZER_CENTER.cmd",
    "START_DESKTOP_OPTIMIZER_CENTER.py",
    "START_DESKTOP_OPTIMIZER_CENTER.pyw",
    "START_DESKTOP_OPTIMIZER_CENTER.vbs",
    "START_DESKTOP_RING_EDITOR.cmd",
    "START_DESKTOP_RING_EDITOR.py",
    "START_DESKTOP_RING_EDITOR.pyw",
    "START_DESKTOP_RING_EDITOR.vbs",
    "START_PNEUMO_APP.pyw",
    "VERSION.txt",
    "release_tag.json",
    "BUILD_INFO_LATEST.txt",
    "RELEASE_NOTES_LATEST.txt",
    "README.md",
    "requirements.txt",
    "00_READ_FIRST__ABSOLUTE_LAW.md",
    "01_PARAMETER_REGISTRY.md",
]


def _touch(p: Path, text: str = "x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_build_portable_release_zip_excludes_runtime_noise_and_long_doc_sources(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    for rel in REQUIRED_ROOT_FILES:
        _touch(root / rel, rel)

    _touch(root / ".streamlit" / "config.toml", "[server]\nheadless=true\n")
    _touch(root / "pneumo_solver_ui" / "__init__.py", "")
    _touch(root / "pneumo_solver_ui" / "core.py", "print('ok')\n")
    _touch(root / "pneumo_solver_ui" / "__pycache__" / "core.cpython-313.pyc", "pyc")
    _touch(root / "pneumo_dist" / "__init__.py", "")
    _touch(root / "docs" / "11_TODO.md", "todo")
    _touch(root / "docs" / "12_Wishlist.md", "wish")
    _touch(root / "docs" / "WISHLIST.json", "{}")

    _touch(root / "DOCS_SOURCES" / "RELEASE_READMES" / "very_long_history_file_name_that_should_not_ship_in_portable_release.md", "history")
    _touch(root / "tests" / "test_should_not_ship.py", "def test_x():\n    assert True\n")
    _touch(root / "runs" / "ui_sessions" / "last.log", "log")
    _touch(root / "send_bundles" / "latest_send_bundle.zip", "zip")
    _touch(root / "workspace" / "cache" / "x.txt", "cache")
    _touch(root / ".pytest_cache" / "v" / "cache" / "nodeids", "[]")
    _touch(root / "pneumo_solver_ui" / "autotest_runs" / "RUN_1" / "workspace_live" / "long.json", "{}")
    _touch(root / "tmp_compare_viewer_snapshots" / "snap1.json", "{}")
    _touch(root / "pneumo_solver_ui" / "tmp_mnemo_svg_crops" / "crop1.png", "fake")
    _touch(root / "tmp_bundle_analysis" / "note.txt", "tmp")

    out_zip = tmp_path / "PneumoApp_R31AZ_portable_20260328.zip"
    manifest = build_portable_release_zip(root, out_zip)

    assert out_zip.exists()
    manifest_path = out_zip.with_suffix(out_zip.suffix + ".manifest.json")
    assert manifest_path.exists()
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved["member_count"] == manifest["member_count"]
    assert manifest["max_abs_path_len_desktop"] < 240

    with zipfile.ZipFile(out_zip, "r") as zf:
        names = set(zf.namelist())

    assert "app.py" in names
    assert "START_DESKTOP_CONTROL_CENTER.cmd" in names
    assert "START_DESKTOP_CONTROL_CENTER.py" in names
    assert "START_DESKTOP_CONTROL_CENTER.pyw" in names
    assert "START_DESKTOP_CONTROL_CENTER.vbs" in names
    assert "START_DESKTOP_MAIN_SHELL.cmd" in names
    assert "START_DESKTOP_MAIN_SHELL.py" in names
    assert "START_DESKTOP_MAIN_SHELL.pyw" in names
    assert "START_DESKTOP_MAIN_SHELL.vbs" in names
    assert "START_DESKTOP_OPTIMIZER_CENTER.cmd" in names
    assert "START_DESKTOP_OPTIMIZER_CENTER.py" in names
    assert "START_DESKTOP_OPTIMIZER_CENTER.pyw" in names
    assert "START_DESKTOP_OPTIMIZER_CENTER.vbs" in names
    assert "START_DESKTOP_RING_EDITOR.cmd" in names
    assert "START_DESKTOP_RING_EDITOR.py" in names
    assert "START_DESKTOP_RING_EDITOR.pyw" in names
    assert "START_DESKTOP_RING_EDITOR.vbs" in names
    assert "START_PNEUMO_APP.pyw" in names
    assert "pneumo_solver_ui/core.py" in names
    assert "docs/11_TODO.md" in names
    assert "docs/12_Wishlist.md" in names
    assert "docs/WISHLIST.json" in names

    assert not any(name.startswith("DOCS_SOURCES/") for name in names)
    assert not any(name.startswith("tests/") for name in names)
    assert not any(name.startswith("runs/") for name in names)
    assert not any(name.startswith("send_bundles/") for name in names)
    assert not any(name.startswith("workspace/") for name in names)
    assert not any("autotest_runs/" in name for name in names)
    assert not any(name.startswith("tmp_compare_viewer_snapshots/") for name in names)
    assert not any("tmp_mnemo_svg_crops/" in name for name in names)
    assert not any(name.startswith("tmp_bundle_analysis/") for name in names)
    assert not any("__pycache__" in name for name in names)
    assert not any(name.endswith(".pyc") for name in names)


def test_build_portable_release_tree_excludes_runtime_noise_and_writes_manifest(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    for rel in REQUIRED_ROOT_FILES:
        _touch(root / rel, rel)

    _touch(root / ".streamlit" / "config.toml", "[server]\nheadless=true\n")
    _touch(root / "pneumo_solver_ui" / "__init__.py", "")
    _touch(root / "pneumo_solver_ui" / "core.py", "print('ok')\n")
    _touch(root / "pneumo_dist" / "__init__.py", "")
    _touch(root / "docs" / "11_TODO.md", "todo")
    _touch(root / "docs" / "12_Wishlist.md", "wish")
    _touch(root / "docs" / "WISHLIST.json", "{}")
    _touch(root / "tests" / "test_should_not_ship.py", "def test_x():\n    assert True\n")
    _touch(root / "runs" / "ui_sessions" / "last.log", "log")
    _touch(root / "workspace" / "cache" / "x.txt", "cache")
    _touch(root / "pneumo_solver_ui" / "__pycache__" / "core.cpython-313.pyc", "pyc")
    _touch(root / "pneumo_solver_ui" / "autotest_runs" / "RUN_1" / "workspace_live" / "long.json", "{}")
    _touch(root / "tmp_compare_viewer_snapshots" / "snap1.json", "{}")
    _touch(root / "pneumo_solver_ui" / "tmp_mnemo_svg_crops" / "crop1.png", "fake")
    _touch(root / "tmp_bundle_analysis" / "note.txt", "tmp")

    out_dir = tmp_path / "portable_tree"
    manifest = build_portable_release_tree(root, out_dir, clean=True)

    assert out_dir.exists()
    manifest_path = out_dir / "portable_release_manifest.json"
    assert manifest_path.exists()
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved["member_count"] == manifest["member_count"]
    assert (out_dir / "app.py").exists()
    assert (out_dir / "START_DESKTOP_MAIN_SHELL.cmd").exists()
    assert (out_dir / "START_DESKTOP_MAIN_SHELL.py").exists()
    assert (out_dir / "START_DESKTOP_MAIN_SHELL.pyw").exists()
    assert (out_dir / "START_DESKTOP_MAIN_SHELL.vbs").exists()
    assert (out_dir / "START_DESKTOP_OPTIMIZER_CENTER.cmd").exists()
    assert (out_dir / "START_DESKTOP_OPTIMIZER_CENTER.py").exists()
    assert (out_dir / "START_DESKTOP_OPTIMIZER_CENTER.pyw").exists()
    assert (out_dir / "START_DESKTOP_OPTIMIZER_CENTER.vbs").exists()
    assert (out_dir / "START_DESKTOP_RING_EDITOR.cmd").exists()
    assert (out_dir / "START_DESKTOP_RING_EDITOR.py").exists()
    assert (out_dir / "START_DESKTOP_RING_EDITOR.pyw").exists()
    assert (out_dir / "START_DESKTOP_RING_EDITOR.vbs").exists()
    assert (out_dir / "START_PNEUMO_APP.pyw").exists()
    assert (out_dir / "pneumo_solver_ui" / "core.py").exists()
    assert (out_dir / "docs" / "11_TODO.md").exists()
    assert not (out_dir / "tests").exists()
    assert not (out_dir / "runs").exists()
    assert not (out_dir / "workspace").exists()
    assert not (out_dir / "pneumo_solver_ui" / "autotest_runs").exists()
    assert not (out_dir / "tmp_compare_viewer_snapshots").exists()
    assert not (out_dir / "pneumo_solver_ui" / "tmp_mnemo_svg_crops").exists()
    assert not (out_dir / "tmp_bundle_analysis").exists()
    assert not any("__pycache__" in p.parts for p in out_dir.rglob("*"))
