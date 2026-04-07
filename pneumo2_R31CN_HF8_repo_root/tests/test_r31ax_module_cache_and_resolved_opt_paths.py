from __future__ import annotations

from pathlib import Path
import importlib
import time

from pneumo_solver_ui.module_loading import load_python_module_from_path


def test_r31ax_load_python_module_from_path_reuses_cached_module_when_unchanged(tmp_path: Path) -> None:
    mod_path = tmp_path / "tmp_mod.py"
    mod_path.write_text("VALUE = 1\n", encoding="utf-8")

    m1 = load_python_module_from_path(mod_path, "tmp_mod_cached")
    m2 = load_python_module_from_path(mod_path, "tmp_mod_cached")

    assert m1 is m2
    assert getattr(m2, "VALUE", None) == 1


def test_r31ax_load_python_module_from_path_reloads_after_file_change(tmp_path: Path) -> None:
    mod_path = tmp_path / "tmp_mod_reload.py"
    mod_path.write_text("VALUE = 1\n", encoding="utf-8")

    m1 = load_python_module_from_path(mod_path, "tmp_mod_reload")
    time.sleep(0.02)
    mod_path.write_text("VALUE = 2\n", encoding="utf-8")
    importlib.invalidate_caches()
    m2 = load_python_module_from_path(mod_path, "tmp_mod_reload")

    assert m1 is not m2
    assert getattr(m2, "VALUE", None) == 2


def test_r31ax_monolithic_opt_ui_uses_canonical_defaults_and_resolved_spawn_paths() -> None:
    app_path = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "pneumo_ui_app.py"
    src = app_path.read_text(encoding="utf-8")

    assert 'value=str(canonical_worker_path(HERE))' in src
    assert 'DEFAULT_SUITE_PATH = canonical_suite_json_path(HERE)' in src
    assert 'str(Path(resolved_model_path))' in src
    assert 'str(Path(resolved_worker_path))' in src
    assert '"worker": str(resolved_worker_path)' in src
