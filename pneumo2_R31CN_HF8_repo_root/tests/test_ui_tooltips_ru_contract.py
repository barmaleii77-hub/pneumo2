from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "pneumo_solver_ui" / "ui_tooltips_ru.py"


def test_ui_tooltips_keep_scenario_wording_for_suite_actions() -> None:
    text = HELPERS.read_text(encoding="utf-8")

    assert "Быстрый выбор шаблона набора сценариев." in text
    assert "Фильтр сценариев по стадиям." in text
    assert "Показывать только включённые сценарии." in text
    assert "Поиск по имени и типу сценария." in text
    assert "создать CSV и сценарий" in text
    assert "сопоставления сценариев с измерениями" in text
    assert "Считает выбранные сценарии" in text
    assert "набор сценариев и диапазоны корректны" in text
    assert "Включить все сценарии в наборе" in text
    assert "Выключить все сценарии" in text
    assert "добавить новый сценарий в таблицу набора" in text
    assert "лучше текущего опорного прогона" in text
    assert "Пакетный калибровочный прогон" in text
    assert "подготовка NPZ и запуск калибровочных пайплайнов без ручной консоли" in text
    assert "Запустить опорный прогон" in text
    assert "Создать копию выбранного сценария" in text
    assert "Удалить выбранный сценарий из таблицы" in text
    assert "Быстрый выбор шаблона тест-набора." not in text
    assert "Фильтр тестов по стадиям." not in text
    assert "Показывать только включённые тесты." not in text
    assert "Поиск по имени теста и типу." not in text
    assert "создать CSV и тест" not in text
    assert "сопоставления тестов с измерениями" not in text
    assert "Считает выбранные тесты" not in text
    assert "тест-набор и диапазоны корректны" not in text
    assert "Включить все тесты в наборе" not in text
    assert "Выключить все тесты" not in text
    assert "добавить новый тест в таблицу тест‑набора" not in text
    assert "лучше текущего baseline" not in text
    assert "OneClick: пакетные прогоны и подготовка NPZ/логов для калибровки." not in text
    assert "Создать копию выбранного теста" not in text
    assert "Удалить выбранный тест из таблицы" not in text
