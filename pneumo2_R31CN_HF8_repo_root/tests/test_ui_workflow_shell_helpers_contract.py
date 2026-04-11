from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_workflow_shell_helpers as helpers


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.titles: list[str] = []
        self.captions: list[str] = []

    def title(self, text: str) -> None:
        self.titles.append(text)

    def caption(self, text: str) -> None:
        self.captions.append(text)


def test_workflow_constants_are_human_readable_and_ordered() -> None:
    assert helpers.UI_MODES == ["Рабочее место", "Пошаговый режим"]
    assert helpers.FULL_SECTIONS == [
        "1. Модель",
        "2. Параметры",
        "3. Тесты",
        "4. Прогон",
        "5. Результаты",
        "6. Инструменты",
    ]


def test_render_home_workflow_header_uses_clean_russian_labels() -> None:
    fake_st = _FakeStreamlit()

    helpers.render_home_workflow_header(fake_st)

    assert fake_st.titles == ["Пневмоподвеска: модель, расчёт и оптимизация"]
    assert "Рабочее место" in fake_st.captions[0]
    assert "Результаты" in fake_st.captions[0]
    assert "запуск расчёта и разбор результатов" in fake_st.captions[0]


def test_render_heavy_workflow_header_uses_clean_russian_labels() -> None:
    fake_st = _FakeStreamlit()

    helpers.render_heavy_workflow_header(fake_st)

    assert fake_st.titles == ["Пневмоподвеска: инженерный центр"]
    assert "оптимизацию как отдельную страницу настройки и запуска" in fake_st.captions[0]


def test_render_workflow_mode_and_section_and_visibility_contract() -> None:
    calls: list[tuple[str, list[str], str, int, bool]] = []

    def _choose(label: str, options: list[str], *, key: str, index: int, horizontal: bool) -> str:
        calls.append((label, list(options), key, index, horizontal))
        if key == "ui_mode":
            return "Пошаговый режим"
        return "5. Результаты"

    ui_mode, ui_section = helpers.render_workflow_mode_and_section(choose_fn=_choose)

    assert ui_mode == "Пошаговый режим"
    assert ui_section == "5. Результаты"
    assert calls == [
        ("Режим работы", helpers.UI_MODES, "ui_mode", 0, True),
        ("Шаг", helpers.FULL_SECTIONS, "ui_section", 0, True),
    ]

    assert helpers.workflow_visibility(helpers.WORKSPACE_VIEW) == {
        "show_model": False,
        "show_params": False,
        "show_tests": False,
        "show_run": True,
        "show_results": True,
        "show_tools": False,
    }
    assert helpers.workflow_visibility("5. Результаты")["show_results"] is True


def test_entrypoints_use_shared_workflow_helpers_and_no_question_mark_garbage() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_workflow_shell_helpers import (" in app_text
    assert "render_home_workflow_header(st)" in app_text
    assert "render_workflow_mode_and_section" in app_text
    assert "workflow_visibility" in app_text
    assert "from pneumo_solver_ui.ui_workflow_shell_helpers import (" in heavy_text
    assert "render_heavy_workflow_header(st)" in heavy_text

    for text in (app_text, heavy_text):
        assert "????" not in text
