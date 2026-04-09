from pathlib import Path

from pneumo_solver_ui.ui_process_profile_helpers import build_background_worker_starter


ROOT = Path(__file__).resolve().parents[1]


def test_build_background_worker_starter_binds_console_python_resolver() -> None:
    calls = []

    def _fake_console_python(path):
        return str(path) + ".console"

    starter = build_background_worker_starter(
        console_python_executable_fn=_fake_console_python,
    )

    assert starter.func.__name__ == "start_background_worker"
    assert starter.keywords["console_python_executable_fn"] is _fake_console_python


def test_active_entrypoints_use_shared_process_profile_builder() -> None:
    helper_source = (ROOT / "pneumo_solver_ui" / "ui_process_profile_helpers.py").read_text(encoding="utf-8")
    app_source = (ROOT / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    heavy_source = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")

    assert "def build_background_worker_starter" in helper_source
    assert "from pneumo_solver_ui.ui_process_profile_helpers import (" in app_source
    assert "from pneumo_solver_ui.ui_process_profile_helpers import (" in heavy_source
    assert "build_background_worker_starter(" in app_source
    assert "build_background_worker_starter(" in heavy_source
