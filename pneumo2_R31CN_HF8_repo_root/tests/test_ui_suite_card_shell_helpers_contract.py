from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_card_shell_helpers.py"
APP = ROOT / "pneumo_solver_ui" / "app.py"
HEAVY = ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


def test_suite_card_shell_helper_keeps_clean_russian_copy() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_suite_editor_shell_helpers import render_suite_card_heading" in text
    assert "#### 1. Основное" in text
    assert "#### 2. Время расчета" in text
    assert "#### 4. Цели и ограничения" in text
    assert "Черновик карточки живет в UI-state" in text
    assert "CSV профиля дороги / маневра (опционально)" in text
    assert "Используется в сценариях с дорожным профилем из CSV" in text
    assert "Используется в сценариях с маневром из CSV" in text
    assert "render_app_suite_right_card_shell(" in text
    assert "render_heavy_suite_right_card_shell(" in text
    assert "Р С›РЎРѓР Р…Р С•Р Р†Р Р…Р С•Р Вµ" not in text
    assert "Р СџРЎР‚Р С•РЎвЂћР С‘Р В»РЎРЉ" not in text


def test_app_suite_card_no_longer_calls_shell_directly() -> None:
    text = APP.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_suite_editor_section_helpers import (" in text
    assert "render_app_suite_editor_section," in text
    assert "render_app_suite_editor_section(" in text
    assert "render_app_suite_right_card_panel(" not in text
    assert "render_app_suite_right_card_shell(" not in text
    assert "render_suite_card_primary_section_intro(st)" not in text
    assert "render_suite_card_timing_section_intro(st)" not in text
    assert "render_suite_card_targets_section_intro(st)" not in text


def test_heavy_suite_card_no_longer_calls_shell_directly() -> None:
    text = HEAVY.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_suite_editor_section_helpers import (" in text
    assert "render_heavy_suite_editor_section," in text
    assert "render_heavy_suite_editor_section(" in text
    assert "render_heavy_suite_right_card_panel(" not in text
    assert "render_heavy_suite_right_card_shell(" not in text
    assert 'save_upload_fn=lambda uploaded, prefix: _save_upload(uploaded, prefix=prefix)' in text
    assert "legacy dead after extraction" not in text
