from pathlib import Path

from pneumo_solver_ui.ui_suite_helpers import load_default_suite_disabled, load_suite, resolve_osc_dir


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ENTRYPOINTS = [
    REPO_ROOT / "pneumo_solver_ui" / "app.py",
    REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py",
]


def test_resolve_osc_dir_and_suite_loading_roundtrip(tmp_path: Path) -> None:
    default_dir = tmp_path / "osc"
    assert resolve_osc_dir(default_dir, {}) == default_dir
    assert resolve_osc_dir(default_dir, {"osc_dir_path": "  "}) == default_dir

    custom_dir = tmp_path / "custom"
    resolved = resolve_osc_dir(default_dir, {"osc_dir_path": str(custom_dir)})
    assert resolved == custom_dir

    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        '[{"name":"A","включен":true},{"name":"B","meta":{"x":1}}]',
        encoding="utf-8",
    )
    assert load_suite(suite_path) == [
        {"name": "A", "включен": True},
        {"name": "B", "meta": {"x": 1}},
    ]
    assert load_default_suite_disabled(suite_path) == [
        {"name": "A", "включен": False},
        {"name": "B", "meta": {"x": 1}, "включен": False},
    ]


def test_large_ui_entrypoints_import_shared_suite_helpers() -> None:
    for path in UI_ENTRYPOINTS:
        src = path.read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_suite_helpers import (" in src
        assert "get_osc_dir = partial(resolve_osc_dir, WORKSPACE_OSC_DIR)" in src
        assert "def get_osc_dir(" not in src
        assert "def load_suite(" not in src
        assert "def load_default_suite_disabled(" not in src
