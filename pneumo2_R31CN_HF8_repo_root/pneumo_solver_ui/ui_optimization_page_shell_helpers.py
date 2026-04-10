from __future__ import annotations

from typing import Any


SECTION_PROJECT_FILES = "1. Файлы проекта"
SECTION_TEST_SUITE = "2. Тестовый набор"
SECTION_SEARCH_SPACE = "3. Пространство поиска"
SECTION_ADVANCED = "4. Продвинутые инженерные настройки"


def render_heavy_optimization_page_overview(st: Any) -> None:
    st.info(
        "Как работать с этой страницей: 1) проверьте файлы проекта, "
        "2) подготовьте тестовый набор, 3) задайте пространство поиска параметров, "
        "4) при необходимости откройте продвинутые инженерные настройки. "
        "Сам запуск, мониторинг и результаты оптимизации находятся на отдельной странице оптимизации."
    )


def render_project_files_section_intro(st: Any) -> None:
    st.header(SECTION_PROJECT_FILES)
    st.caption(
        "Сначала проверьте, какие файл модели и какой оптимизатор подключены к текущей сессии. "
        "Обычно здесь ничего менять не нужно, но этот шаг помогает не перепутать версии проекта."
    )


def render_test_suite_section_intro(st: Any) -> None:
    st.divider()
    st.header(SECTION_TEST_SUITE)
    st.caption(
        "Здесь формируется набор сценариев, по которым потом будут проверяться кандидаты. "
        "Сначала удобно собрать и отфильтровать suite, а уже потом переходить к диапазонам параметров."
    )


def render_search_space_section_intro(st: Any) -> None:
    st.header(SECTION_SEARCH_SPACE)
    st.caption(
        "На этой странице настраивается search-space contract: какие параметры разрешено менять и в каких границах. "
        "Запуск, мониторинг и результаты оптимизации вынесены на отдельную страницу."
    )


def render_advanced_optimization_section_intro(st: Any) -> None:
    st.divider()
    st.subheader(SECTION_ADVANCED)
    st.caption(
        "Эти параметры нужны для отладки, сравнения стратегий поиска и тонкой инженерной настройки distributed-оптимизации. "
        "Если задача типовая, этот раздел обычно можно не менять."
    )
