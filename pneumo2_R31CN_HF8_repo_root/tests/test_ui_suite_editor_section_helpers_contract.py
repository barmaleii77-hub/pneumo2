from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_editor_section_helpers.py"
APP = ROOT / "pneumo_solver_ui" / "app.py"
HEAVY = ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


def test_suite_editor_section_helper_contains_app_and_heavy_orchestration() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "def render_app_suite_editor_section(" in text
    assert "def render_heavy_suite_editor_section(" in text
    assert "render_app_suite_editor_intro(" in text
    assert "render_heavy_suite_editor_intro(" in text
    assert "render_app_suite_master_detail_panel(" in text
    assert "render_heavy_suite_master_detail_panel(" in text
    assert 'with st.expander("Импорт, экспорт и восстановление набора", expanded=True):' in text
    assert "HEAVY_STAGE_GUIDANCE_TEXT" in text
    assert "Логика оптимизации по стадиям" in text
    assert "быстрый предварительный отсев" in text
    assert "Импорт набора тестов (JSON)" in text
    assert "Набор тестов загружен." in text
    assert "JSON должен содержать список тестов." in text
    assert "Вернуть набор по умолчанию" in text
    assert "Скачать suite.json" in text
    assert "staged-оптимизации" not in text
    assert "Suite загружен." not in text
    assert "списком объектов (list[dict])" not in text
    assert "Сбросить к default_suite.json" not in text


def test_entrypoints_use_suite_editor_section_helper() -> None:
    app_text = APP.read_text(encoding="utf-8")
    heavy_text = HEAVY.read_text(encoding="utf-8")

    assert "render_app_suite_editor_section(" in app_text
    assert "render_heavy_suite_editor_section(" in heavy_text
