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


def test_heavy_progress_and_stage_policy_use_human_labels() -> None:
    heavy_text = ENTRYPOINTS[1].read_text(encoding="utf-8")

    assert 'st.metric("Активный путь", "По стадиям" if opt_use_staged else "Распределённый")' in heavy_text
    assert "Параллельных задач" in heavy_text
    assert "Имя запуска" in heavy_text
    assert "Префикс CSV:" in heavy_text
    assert "Параллельных задач: {jobs}; запуск: {run_name}; префикс CSV: {out_prefix}" in heavy_text
    assert "тёплый старт=" in heavy_text
    assert "точек для surrogate-модели=" in heavy_text
    assert "размер элиты surrogate-модели=" in heavy_text
    assert "кандидатов для отбора=" in heavy_text
    assert "условий отбора=" in heavy_text
    assert "дешёвые тесты первыми=" in heavy_text
    assert "авто-обновление лучшего опорного прогона=" in heavy_text
    assert "Распределённый режим / BoTorch / координатор:" in heavy_text
    assert "движок=" in heavy_text
    assert "метод выбора кандидатов=" in heavy_text
    assert "размер пакета q=" in heavy_text
    assert "вычислительное устройство=" in heavy_text
    assert "Среда распределённого расчёта:" in heavy_text
    assert "режим runtime_env Ray=" in heavy_text
    assert "начальных точек BoTorch=" in heavy_text
    assert "минимум допустимых точек для BoTorch=" in heavy_text
    assert "Режим по стадиям — рекомендуется" in heavy_text
    assert "Нумерация стадий начинается с нуля" in heavy_text
    assert "Режим по стадиям: ускорение поиска (обычно не трогать)" in heavy_text
    assert "Режим тёплого старта" in heavy_text
    assert "Точек для surrogate-модели" in heavy_text
    assert "Размер элиты surrogate-модели (top-k)" in heavy_text
    assert "Порог досрочной остановки по штрафу (стадия 1)" in heavy_text
    assert "Порог досрочной остановки по штрафу (стадия 2)" in heavy_text
    assert "Относительный шаг System Influence (eps_rel)" in heavy_text
    assert "Адаптивный epsilon для System Influence" in heavy_text
    assert "Политика отбора и продвижения" in heavy_text
    assert "Профиль отбора и продвижения по стадиям" in heavy_text
    assert "Адаптивный epsilon по стадиям" in heavy_text
    assert "Стадия: **{stage_name}** (этап {stage_idx + 1} из {max(1, stage_total)})" in heavy_text
    assert "Политика отбора и продвижения (текущая стадия)" in heavy_text
    assert "Профиль: {policy_name or '—'}" in heavy_text
    assert "запрошенный режим:" in heavy_text
    assert "фактический режим:" in heavy_text
    assert "Бюджет отбора:" in heavy_text
    assert "разведка=" in heavy_text
    assert "фокус=" in heavy_text
    assert "выбрано=" in heavy_text
    assert "выбрано по группам фокус/разведка=" in heavy_text
    assert "Приоритетные параметры текущей стадии:" in heavy_text
    assert "Решений для продвижения выбрано:" in heavy_text
    assert "В последнем пакете: успешно={ok}, с ошибкой={err}" in heavy_text
    assert "процесс расчёта завершился аварийно" in heavy_text
    assert "Проверьте логи и файлы staged_progress / stage_*_progress.json." in heavy_text

    assert '"jobs"' not in heavy_text
    assert '"Run"' not in heavy_text
    assert "jobs={jobs}; run={run_name}; csv={out_prefix}" not in heavy_text
    assert "CSV prefix:" not in heavy_text
    assert 'st.metric("Активный путь", "StageRunner" if opt_use_staged else "Distributed")' not in heavy_text
    assert "warmstart=" not in heavy_text
    assert "surrogate_samples=" not in heavy_text
    assert "surrogate_top_k=" not in heavy_text
    assert "seed_candidates=" not in heavy_text
    assert "seed_conditions=" not in heavy_text
    assert "sort_tests_by_cost=" not in heavy_text
    assert "autoupdate_baseline=" not in heavy_text
    assert "Distributed / BoTorch / coordinator:" not in heavy_text
    assert "Distributed runtime/env:" not in heavy_text
    assert "backend=" not in heavy_text
    assert "proposer=" not in heavy_text
    assert "device=" not in heavy_text
    assert "f\"q={int(st.session_state.get('opt_q', DIST_OPT_Q_DEFAULT) or DIST_OPT_Q_DEFAULT)}" not in heavy_text
    assert "ray_runtime_env_mode=" not in heavy_text
    assert "opt_botorch_n_init=" not in heavy_text
    assert "opt_botorch_min_feasible=" not in heavy_text
    assert "минимум feasible для BoTorch=" not in heavy_text
    assert "Режим по стадиям (StageRunner) — рекомендуется" not in heavy_text
    assert "Нумерация стадий 0-based" not in heavy_text
    assert "StageRunner: ускорение поиска (обычно не трогать)" not in heavy_text
    assert "Warm‑start режим" not in heavy_text
    assert '"Surrogate samples"' not in heavy_text
    assert '"Surrogate top-k"' not in heavy_text
    assert "Early‑stop штраф (stage1)" not in heavy_text
    assert "Early‑stop штраф (stage2)" not in heavy_text
    assert '"System Influence eps_rel"' not in heavy_text
    assert "Adaptive epsilon для System Influence" not in heavy_text
    assert "Stage-specific seed/promotion profile" not in heavy_text
    assert "Stage-aware adaptive epsilon" not in heavy_text
    assert "idx={stage_idx}, 0-based" not in heavy_text
    assert "Seed/promotion policy (текущая стадия)" not in heavy_text
    assert "policy={policy_name or '—'}" not in heavy_text
    assert "requested={requested_mode_live or '—'}" not in heavy_text
    assert "effective={effective_mode or '—'}" not in heavy_text
    assert "summary={summary_status_live or '—'}" not in heavy_text
    assert '"Seed budget:"' not in heavy_text
    assert "focus/explore selected=" not in heavy_text
    assert "Priority params for this stage:" not in heavy_text
    assert "Promotion decisions selected:" not in heavy_text
    assert "В последнем батче: OK={ok}, ERR={err}" not in heavy_text
    assert "worker/staged-runner" not in heavy_text
    assert "Смотрите log/CSV/staged_progress" not in heavy_text
