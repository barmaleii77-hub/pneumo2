from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_optimization_page_shell_helpers as helpers


ROOT = Path(__file__).resolve().parents[1]
HEAVY_PATH = ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = ROOT / "pneumo_solver_ui" / "ui_optimization_page_shell_helpers.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.headers: list[str] = []
        self.subheaders: list[str] = []
        self.captions: list[str] = []
        self.infos: list[str] = []
        self.dividers = 0

    def header(self, text: str) -> None:
        self.headers.append(text)

    def subheader(self, text: str) -> None:
        self.subheaders.append(text)

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def info(self, text: str) -> None:
        self.infos.append(text)

    def divider(self) -> None:
        self.dividers += 1


def test_optimization_shell_constants_are_user_oriented() -> None:
    assert helpers.SECTION_PROJECT_FILES == "1. Файлы проекта"
    assert helpers.SECTION_TEST_SUITE == "2. Тестовый набор"
    assert helpers.SECTION_SEARCH_SPACE == "3. Пространство поиска"
    assert helpers.SECTION_ADVANCED == "4. Продвинутые инженерные настройки"


def test_render_heavy_optimization_page_overview_is_step_by_step() -> None:
    fake_st = _FakeStreamlit()

    helpers.render_heavy_optimization_page_overview(fake_st)

    assert len(fake_st.infos) == 1
    assert "1) проверьте файлы проекта" in fake_st.infos[0]
    assert "2) подготовьте тестовый набор" in fake_st.infos[0]
    assert "3) задайте пространство поиска параметров" in fake_st.infos[0]
    assert "4) при необходимости откройте продвинутые инженерные настройки" in fake_st.infos[0]


def test_section_intro_helpers_emit_ordered_titles_and_captions() -> None:
    fake_st = _FakeStreamlit()

    helpers.render_project_files_section_intro(fake_st)
    helpers.render_test_suite_section_intro(fake_st)
    helpers.render_search_space_section_intro(fake_st)
    helpers.render_advanced_optimization_section_intro(fake_st)

    assert fake_st.headers == [
        "1. Файлы проекта",
        "2. Тестовый набор",
        "3. Пространство поиска",
    ]
    assert fake_st.subheaders == ["4. Продвинутые инженерные настройки"]
    assert fake_st.dividers == 2
    assert any("Сначала проверьте" in text for text in fake_st.captions)
    assert any("формируется набор сценариев" in text for text in fake_st.captions)
    assert any("search-space contract" in text for text in fake_st.captions)
    assert any("distributed-оптимизации" in text for text in fake_st.captions)


def test_heavy_entrypoint_uses_shared_optimization_page_shell_helpers() -> None:
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_optimization_page_shell_helpers import (" in heavy_text
    assert "render_heavy_optimization_page_overview(st)" in heavy_text
    assert "render_project_files_section_intro(st)" in heavy_text
    assert "render_test_suite_section_intro(st)" in heavy_text
    assert "render_search_space_section_intro(st)" in heavy_text
    assert "render_advanced_optimization_section_intro(st)" in heavy_text
    assert 'st.header("Файлы проекта")' not in heavy_text
    assert 'st.header("Настройки тест-набора")' not in heavy_text
    assert 'st.subheader("Инженерные настройки оптимизации")' not in heavy_text
    assert 'SECTION_ADVANCED = "4. Продвинутые инженерные настройки"' in helper_text
