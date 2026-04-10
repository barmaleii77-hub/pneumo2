from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPT_SHELL_HELPERS = ROOT / "pneumo_solver_ui" / "ui_optimization_page_shell_helpers.py"
SUITE_SHELL_HELPERS = ROOT / "pneumo_solver_ui" / "ui_suite_editor_shell_helpers.py"
SUITE_SECTION_HELPERS = ROOT / "pneumo_solver_ui" / "ui_suite_editor_section_helpers.py"
SUITE_EDITOR_PANEL_HELPERS = ROOT / "pneumo_solver_ui" / "ui_suite_editor_panel_helpers.py"
SUITE_CARD_SHELL_HELPERS = ROOT / "pneumo_solver_ui" / "ui_suite_card_shell_helpers.py"
SUITE_CARD_PANEL_HELPERS = ROOT / "pneumo_solver_ui" / "ui_suite_card_panel_helpers.py"
ENTRYPOINTS = [
    ROOT / "pneumo_solver_ui" / "app.py",
    ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py",
]
SHARED_TEXT_FILES = [
    ROOT / "pneumo_solver_ui" / "ui_animation_mode_helpers.py",
    ROOT / "pneumo_solver_ui" / "ui_optimization_page_shell_helpers.py",
    ROOT / "pneumo_solver_ui" / "ui_results_section_helpers.py",
    ROOT / "pneumo_solver_ui" / "ui_suite_editor_shell_helpers.py",
    ROOT / "pneumo_solver_ui" / "ui_suite_editor_section_helpers.py",
    ROOT / "pneumo_solver_ui" / "ui_suite_editor_panel_helpers.py",
    ROOT / "pneumo_solver_ui" / "ui_suite_card_shell_helpers.py",
    ROOT / "pneumo_solver_ui" / "ui_suite_card_panel_helpers.py",
    ROOT / "pneumo_solver_ui" / "ui_workflow_shell_helpers.py",
    ROOT / "pneumo_solver_ui" / "tools" / "make_send_bundle.py",
    ROOT / "pneumo_solver_ui" / "tools" / "triage_report.py",
]

STRONG_MOJIBAKE_MARKERS = (
    "Р В Р’В Р РЋРЎСџР В Р’В ",
    "Р В Р’В Р РЋРІР‚в„ўР В Р’В ",
    "Р В Р’В Р В Р вЂ№Р В Р’В ",
    "Р В Р’В Р РЋРЎв„ўР В Р’В ",
    "Р В Р вЂ Р В РІР‚С™",
    "Р В Р вЂ Р Р†Р вЂљР’В ",
    "Р вЂњРІР‚СњР вЂњР’В ",
    "Р вЂњР вЂЎР вЂњР’В°",
)


def test_shared_text_files_have_no_strong_mojibake_markers() -> None:
    offenders: list[str] = []

    for path in SHARED_TEXT_FILES:
        text = path.read_text(encoding="utf-8")
        bad = [marker for marker in STRONG_MOJIBAKE_MARKERS if marker in text]
        if bad:
            offenders.append(f"{path.name}: {', '.join(bad)}")

    assert not offenders, "\n".join(offenders)


def test_entrypoints_do_not_contain_question_mark_garbage_in_strings() -> None:
    offenders: list[str] = []

    for path in ENTRYPOINTS:
        text = path.read_text(encoding="utf-8")
        if "????" in text:
            offenders.append(path.name)

    assert not offenders, ", ".join(offenders)


def test_key_ui_files_have_no_c1_controls_after_utf8_decode() -> None:
    offenders: list[str] = []

    for path in ENTRYPOINTS + SHARED_TEXT_FILES:
        text = path.read_text(encoding="utf-8")
        bad_lines = [
            str(lineno)
            for lineno, line in enumerate(text.splitlines(), start=1)
            if any(0x80 <= ord(ch) <= 0x9F for ch in line)
        ]
        if bad_lines:
            offenders.append(f"{path.name}: {', '.join(bad_lines[:10])}")

    assert not offenders, "\n".join(offenders)


def test_key_ui_files_keep_clean_visible_russian_labels() -> None:
    app_text = ENTRYPOINTS[0].read_text(encoding="utf-8")
    heavy_text = ENTRYPOINTS[1].read_text(encoding="utf-8")
    opt_shell_text = OPT_SHELL_HELPERS.read_text(encoding="utf-8")
    suite_shell_text = SUITE_SHELL_HELPERS.read_text(encoding="utf-8")
    suite_section_text = SUITE_SECTION_HELPERS.read_text(encoding="utf-8")
    suite_editor_panel_text = SUITE_EDITOR_PANEL_HELPERS.read_text(encoding="utf-8")
    suite_card_shell_text = SUITE_CARD_SHELL_HELPERS.read_text(encoding="utf-8")
    suite_card_panel_text = SUITE_CARD_PANEL_HELPERS.read_text(encoding="utf-8")

    assert "NPZ: готов" in app_text
    assert "PTR: готов" in app_text
    assert "NPZ: нет" in app_text
    assert "PTR: нет" in app_text
    assert '"единица": meta.get("ед", "СИ")' in app_text
    assert '"мин": mn_ui' in app_text

    assert "render_heavy_suite_editor_section(" in heavy_text
    assert "legacy dead after extraction" not in heavy_text
    assert "Инициализация завершена" in heavy_text
    assert "Имя прогона" in heavy_text
    assert "Имя CSV (префикс)" in heavy_text
    assert "Интервал автообновления (с)" in heavy_text
    assert '"test": test_for_events,' in heavy_text
    assert '"test": test,' not in heavy_text

    assert "4. Продвинутые инженерные настройки" in opt_shell_text
    assert "Как работать с этой страницей" in opt_shell_text

    assert "2. Тестовый набор" in suite_shell_text
    assert "Карточка выбранного сценария." in suite_shell_text
    assert "Инерция: торможение ax=-3 м/с²" in suite_shell_text

    assert "Импорт, экспорт и сброс" in suite_section_text
    assert "Импорт набора тестов (suite, JSON)" in suite_section_text
    assert "Логика staged-оптимизации" in suite_section_text
    assert "Открыть редактор сценариев (сегменты-кольцо)" in heavy_text

    assert '"например: крен, микро, кочка..."' in suite_editor_panel_text
    assert '"инерция_крен"' in suite_editor_panel_text

    assert "#### 1. Основное" in suite_card_shell_text
    assert "#### 2. Время расчета" in suite_card_shell_text
    assert "#### 4. Цели и ограничения" in suite_card_shell_text
    assert "CSV профиля дороги / маневра (опционально)" in suite_card_shell_text
    assert "Используется в сценариях с дорожным профилем из CSV" in suite_card_shell_text
    assert "Используется в сценариях с маневром из CSV" in suite_card_shell_text

    assert '"Тип"' in suite_card_panel_text
    assert '"dt, с"' in suite_card_panel_text
    assert '"ax, м/с²"' in suite_card_panel_text
    assert '"ay, м/с²"' in suite_card_panel_text
    assert '"Применить изменения"' in suite_card_panel_text
    assert '"Тест обновлён."' in suite_card_panel_text
