from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_card_panel_helpers.py"
EDITOR_PANEL_HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_editor_panel_helpers.py"
APP = ROOT / "pneumo_solver_ui" / "app.py"
HEAVY = ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


def test_suite_card_panel_helper_wraps_shell_runtime() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_suite_card_shell_helpers import (" in text
    assert "render_app_suite_right_card_shell," in text
    assert "render_heavy_suite_right_card_shell," in text
    assert "from pneumo_solver_ui.ui_suite_editor_shell_helpers import (" in text
    assert "render_suite_empty_card_state," in text
    assert "render_suite_missing_card_state," in text
    assert "def render_app_suite_right_card_panel(" in text
    assert "def render_heavy_suite_right_card_panel(" in text
    assert 'if st.button("✅ Применить"' in text
    assert 'if st.button("Применить изменения"' in text
    assert 'st.success("Сохранено.")' in text
    assert 'set_flash_fn("success", "Тест обновлён.")' in text
    assert "render_app_suite_right_card_shell(" in text
    assert "render_heavy_suite_right_card_shell(" in text


def test_suite_editor_panel_helper_uses_suite_card_panels() -> None:
    text = EDITOR_PANEL_HELPER.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_suite_card_panel_helpers import (" in text
    assert "render_app_suite_right_card_panel," in text
    assert "render_heavy_suite_right_card_panel," in text
    assert "render_app_suite_right_card_panel(" in text
    assert "render_heavy_suite_right_card_panel(" in text


def test_entrypoints_no_longer_call_suite_card_panels_directly() -> None:
    app_text = APP.read_text(encoding="utf-8")
    heavy_text = HEAVY.read_text(encoding="utf-8")

    assert "render_app_suite_right_card_panel(" not in app_text
    assert "render_heavy_suite_right_card_panel(" not in heavy_text
