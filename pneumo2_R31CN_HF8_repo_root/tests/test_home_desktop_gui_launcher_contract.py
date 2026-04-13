from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_heavy_home_page_keeps_compact_desktop_gui_launcher_block() -> None:
    src = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "def launch_desktop_gui_module(" in src
    assert "def _watch_desktop_gui_process(" in src
    assert "desktop_gui_spawned" in src
    assert "desktop_gui_spawn_failed" in src
    assert "desktop_gui_exit" in src
    assert "🖥 Desktop Animator (внешнее окно, по выгрузке anim_latest)" in src
    assert "Запустить Desktop Animator" in src
    assert "Запустить Mnemo (follow)" in src
    assert "Другие отдельные GUI-окна проекта" in src
    assert "_desktop_gui_items = [" in src
    assert "Открыть центр desktop-инструментов" in src
    assert "Открыть редактор исходных данных" in src
    assert "Открыть центр тестов" in src
    assert "Открыть GUI автотестов" in src
    assert "Открыть GUI диагностики" in src
    assert "Открыть GUI отправки результатов" in src
    assert "Открыть Compare Viewer" in src
    assert "pneumo_solver_ui.tools.desktop_control_center" in src
    assert "pneumo_solver_ui.tools.desktop_input_editor" in src
    assert "pneumo_solver_ui.tools.test_center_gui" in src
    assert "pneumo_solver_ui.tools.run_autotest_gui" in src
    assert "pneumo_solver_ui.tools.run_full_diagnostics_gui" in src
    assert "pneumo_solver_ui.tools.send_results_gui" in src
    assert "pneumo_solver_ui.qt_compare_viewer" in src
    assert "[str(npz_path)] if npz_path.exists() else []" in src
    assert "Окно «{_window_label}» запущено (если система позволяет GUI)." in src
    assert "Не удалось запустить окно «{_window_label}» (см. логи)." in src

    assert "Что делать дальше сейчас" not in src
    assert "Последние артефакты" not in src
    assert "Рабочие папки desktop-контура" not in src
    assert "st.caption(_window_status)" not in src
    assert "st.caption(_window_desc)" not in src
