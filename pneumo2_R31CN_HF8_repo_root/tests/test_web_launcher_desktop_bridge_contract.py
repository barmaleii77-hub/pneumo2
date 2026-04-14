from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_launcher_can_start_desktop_gui_spec_through_shared_bootstrap() -> None:
    text = (ROOT / "START_PNEUMO_APP.py").read_text(encoding="utf-8", errors="replace")

    assert 'command=self.start_desktop_shell' in text
    assert 'def start_desktop_shell(' in text
    assert 'self._prepare_child_session_env(' in text
    assert 'run_prefix="DESKTOP"' in text
    assert '"PNEUMO_LAUNCH_SURFACE": "desktop_gui_spec_shell"' in text
    assert '"PNEUMO_LAUNCH_SURFACE": "web_streamlit"' in text
    assert 'pneumo_solver_ui.tools.desktop_gui_spec_shell' in text
    assert 'desktop_gui_spec_shell.log' in text
    assert 'self._launch_logged_process(' in text
