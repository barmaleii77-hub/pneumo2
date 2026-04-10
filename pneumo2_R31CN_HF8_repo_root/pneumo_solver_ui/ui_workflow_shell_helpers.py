from __future__ import annotations

from collections.abc import Callable
from typing import Any


WORKSPACE_VIEW = "WORKSPACE"

WORKFLOW_MODE_WORKSPACE = "Рабочее место"
WORKFLOW_MODE_GUIDED = "Пошаговый режим"
UI_MODES = [
    WORKFLOW_MODE_WORKSPACE,
    WORKFLOW_MODE_GUIDED,
]

SECTION_MODEL = "1. Модель"
SECTION_PARAMS = "2. Параметры"
SECTION_TESTS = "3. Тесты"
SECTION_RUN = "4. Прогон"
SECTION_RESULTS = "5. Результаты"
SECTION_TOOLS = "6. Инструменты"

FULL_SECTIONS = [
    SECTION_MODEL,
    SECTION_PARAMS,
    SECTION_TESTS,
    SECTION_RUN,
    SECTION_RESULTS,
    SECTION_TOOLS,
]


def render_home_workflow_header(st: Any) -> None:
    st.title("Пневмоподвеска: модель, расчёт и оптимизация")
    st.caption(
        "Порядок работы: 1. Модель -> 2. Параметры -> 3. Тесты -> 4. Прогон -> "
        "5. Результаты -> 6. Инструменты. Режим «Рабочее место» объединяет "
        "прогон и анализ в одном экране."
    )


def render_heavy_workflow_header(st: Any) -> None:
    st.title("Пневмоподвеска: инженерный центр")
    st.caption(
        "Последовательность работы: сначала проверьте файлы проекта и входные "
        "данные, затем откройте оптимизацию как отдельную страницу, а сюда "
        "возвращайтесь за анализом, анимацией и диагностикой."
    )


def render_workflow_mode_and_section(
    *,
    choose_fn: Callable[..., str],
    mode_key: str = "ui_mode",
    section_key: str = "ui_section",
) -> tuple[str, str]:
    ui_mode = choose_fn("Режим работы", UI_MODES, key=mode_key, index=0, horizontal=True)
    if ui_mode == WORKFLOW_MODE_GUIDED:
        ui_section = choose_fn("Шаг", FULL_SECTIONS, key=section_key, index=0, horizontal=True)
    else:
        ui_section = WORKSPACE_VIEW
    return str(ui_mode), str(ui_section)


def workflow_visibility(ui_section: str) -> dict[str, bool]:
    if ui_section == WORKSPACE_VIEW:
        return {
            "show_model": False,
            "show_params": False,
            "show_tests": False,
            "show_run": True,
            "show_results": True,
            "show_tools": False,
        }
    return {
        "show_model": ui_section == SECTION_MODEL,
        "show_params": ui_section == SECTION_PARAMS,
        "show_tests": ui_section == SECTION_TESTS,
        "show_run": ui_section == SECTION_RUN,
        "show_results": ui_section == SECTION_RESULTS,
        "show_tools": ui_section == SECTION_TOOLS,
    }
