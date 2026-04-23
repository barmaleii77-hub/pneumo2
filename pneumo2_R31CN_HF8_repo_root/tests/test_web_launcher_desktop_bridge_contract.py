from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_web_launcher_can_start_canonical_desktop_gui_through_shared_bootstrap() -> None:
    text = (ROOT / "START_PNEUMO_APP.py").read_text(encoding="utf-8", errors="replace")

    assert 'text="Запустить WEB"' in text
    assert 'text="Запустить GUI"' in text
    assert "Запустить (с авто-установкой зависимостей)" not in text
    assert 'text="Открыть рабочее место"' not in text
    assert 'command=self.start_desktop_shell' in text
    assert 'def start_desktop_shell(' in text
    assert 'self._prepare_child_session_env(' in text
    assert 'run_prefix="DESKTOP"' in text
    assert '"PNEUMO_LAUNCH_SURFACE": "desktop_main_shell_qt"' in text
    assert '"PNEUMO_DESKTOP_MAIN_SHELL_QT": "1"' in text
    assert '"PNEUMO_DESKTOP_GUI_SPEC_SHELL": "1"' not in text
    assert '"PNEUMO_LAUNCH_SURFACE": "web_streamlit"' in text
    assert 'pneumo_solver_ui.tools.desktop_main_shell_qt' in text
    assert 'desktop_main_shell_qt.log' in text
    assert 'self._launch_logged_process(' in text
    assert 'self.stream_log_fh.flush()' in text


def test_root_start_launchers_have_single_public_app_launcher_and_support_wrappers() -> None:
    launcher_families = {
        re.sub(r"\.(cmd|py|pyw|vbs)$", "", path.name, flags=re.IGNORECASE)
        for path in ROOT.glob("START_*")
        if path.suffix.lower() in {".cmd", ".py", ".pyw", ".vbs"}
    }

    assert launcher_families == {
        "START_PNEUMO_APP",
        "START_DESKTOP_GUI_SPEC_SHELL",
        "START_DESKTOP_MAIN_SHELL",
        "START_DESKTOP_CONTROL_CENTER",
        "START_DESKTOP_OPTIMIZER_CENTER",
        "START_DESKTOP_RING_EDITOR",
    }

    public_launcher = (ROOT / "START_PNEUMO_APP.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    assert "единственный пользовательский вход верхнего уровня - `START_PNEUMO_APP.*`" in (
        ROOT / "docs" / "00_PROJECT_KNOWLEDGE_BASE.md"
    ).read_text(encoding="utf-8", errors="replace")
    assert "Запустить WEB" in public_launcher
    assert "Запустить GUI" in public_launcher
    spec_text = (
        ROOT / "docs" / "18_PNEUMOAPP_WINDOWS_GUI_SPEC.md"
    ).read_text(encoding="utf-8", errors="replace")
    assert "`START_DESKTOP_*` wrappers" in spec_text
    assert "support/dev entrypoints" in spec_text
    assert "не считаются отдельными главными пользовательскими launcher-ами" in spec_text
    assert "`Запустить GUI` запускает `pneumo_solver_ui.tools.desktop_main_shell_qt`" in spec_text
    assert "`desktop_gui_spec_shell` не является primary route" in spec_text


def test_uploaded_gui_memory_keeps_tree_dock_primary_route_contract() -> None:
    memory_path = (
        ROOT
        / "docs"
        / "context"
        / "release_readiness"
        / "GUI_CANONICAL_WINDOW_MEMORY_2026-04-23.md"
    )
    memory_text = memory_path.read_text(encoding="utf-8")
    kb_text = (ROOT / "docs" / "00_PROJECT_KNOWLEDGE_BASE.md").read_text(
        encoding="utf-8"
    )
    sources_text = (ROOT / "docs" / "PROJECT_SOURCES.md").read_text(
        encoding="utf-8"
    )

    assert "pneumo_chat_consolidated_master_v1 (2).zip" in memory_text
    assert "pneumo_gui_graph_iteration_v21_reconciliation.zip" in memory_text
    assert "pneumo_human_gui_report_only_v14_tree_dock_context.zip" in memory_text
    assert "`START_PNEUMO_APP.* -> Запустить GUI` must launch `pneumo_solver_ui.tools.desktop_main_shell_qt`" in memory_text
    assert "desktop_gui_spec_shell` is not the user-facing primary route" in memory_text
    assert "A click in the tree must directly open or focus" in memory_text
    assert "Do not add a launcher-grid or center-of-windows" in memory_text
    assert "`Сценарии и редактор кольца` is the only editable scenario source-of-truth" in memory_text
    assert "GUI_CANONICAL_WINDOW_MEMORY_2026-04-23.md" in kb_text
    assert "GUI_CANONICAL_WINDOW_MEMORY_2026-04-23.md" in sources_text
