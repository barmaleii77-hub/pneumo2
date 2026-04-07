from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.module_loading import canonical_dynamic_module_name, load_python_module_from_path


def test_load_python_module_from_path_preserves_relative_import_package_context(tmp_path: Path) -> None:
    pkg = tmp_path / "demo_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "helper.py").write_text("VALUE = 41\n", encoding="utf-8")
    mod_path = pkg / "feature.py"
    mod_path.write_text(
        "from .helper import VALUE\n"
        "def answer():\n"
        "    return VALUE + 1\n",
        encoding="utf-8",
    )

    mod = load_python_module_from_path(mod_path, "fake_name")

    assert mod.__name__ == "demo_pkg.feature"
    assert mod.answer() == 42
    assert canonical_dynamic_module_name(mod_path, fallback_name="fake_name") == "demo_pkg.feature"


def test_load_python_module_from_path_supports_bare_sibling_imports_for_nonpackage_dirs(tmp_path: Path) -> None:
    work = tmp_path / "plain_dir"
    work.mkdir()
    (work / "helper_local.py").write_text("VALUE = 5\n", encoding="utf-8")
    mod_path = work / "feature_local.py"
    mod_path.write_text(
        "import helper_local\n"
        "def answer():\n"
        "    return helper_local.VALUE + 7\n",
        encoding="utf-8",
    )

    mod = load_python_module_from_path(mod_path, "feature_local_runtime")

    assert mod.__name__ == "feature_local_runtime"
    assert mod.answer() == 12
