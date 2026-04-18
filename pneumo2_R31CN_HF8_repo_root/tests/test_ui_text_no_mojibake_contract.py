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
    ROOT / "pneumo_solver_ui" / "ui_tooltips_ru.py",
    ROOT / "pneumo_solver_ui" / "ui_workflow_shell_helpers.py",
    ROOT / "pneumo_solver_ui" / "desktop_animator" / "operator_text.py",
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
    assert "Версия интерфейса:" in heavy_text
    assert "Файл модели:" in heavy_text
    assert "Контрольная сумма параметров:" in heavy_text
    assert "Контрольная сумма набора сценариев:" in heavy_text
    assert "Самопроверка интерфейса:" in heavy_text
    assert "Стабилизатор интерфейса:" in heavy_text
    assert "включён" in heavy_text
    assert "выключен" in heavy_text
    assert "Самопроверка интерфейса не пройдена." in heavy_text
    assert "Разрешить оптимизацию несмотря на сбой самопроверки" in heavy_text
    assert "Лучше сначала исправить ошибки самопроверки." in heavy_text
    assert "Авто‑обновлять лучший опорный прогон" in heavy_text
    assert "workspace/baselines/baseline_best.json как новый стартовый файл." in heavy_text
    assert "следующую стартовую точку." in heavy_text
    assert "Папка сохранённого кэша:" in heavy_text
    assert "Опорный прогон восстановлен из сохранённого кэша:" in heavy_text

    assert "4. Продвинутые инженерные настройки" in opt_shell_text
    assert "Как работать с этой страницей" in opt_shell_text

    assert "2. Набор сценариев" in suite_shell_text
    assert "Карточка выбранного сценария." in suite_shell_text
    assert "Инерция: торможение ax=-3 м/с²" in suite_shell_text

    assert "Импорт, экспорт и восстановление набора" in suite_section_text
    assert "Импорт набора сценариев (JSON)" in suite_section_text
    assert "Логика оптимизации по стадиям" in suite_section_text
    assert "Открыть редактор сценариев (сегменты-кольцо)" in heavy_text

    assert '"например: крен, микро, кочка..."' in suite_editor_panel_text
    assert '"инерция_крен"' in suite_editor_panel_text
    assert "(копия)" in suite_editor_panel_text

    assert "#### 1. Основное" in suite_card_shell_text
    assert "#### 2. Время расчета" in suite_card_shell_text
    assert "#### 4. Цели и ограничения" in suite_card_shell_text
    assert "CSV профиля дороги / маневра (опционально)" in suite_card_shell_text
    assert "Используется в сценариях с дорожным профилем из CSV" in suite_card_shell_text
    assert "Используется в сценариях с маневром из CSV" in suite_card_shell_text

    assert '"Тип"' in suite_card_panel_text
    assert '"Путь к CSV дороги"' in suite_card_panel_text
    assert '"Тип поверхности"' in suite_card_panel_text
    assert '"Переопределения параметров (сценарий)"' in suite_card_panel_text
    assert '"Переопределения параметров в формате JSON (необязательно)"' in suite_card_panel_text
    assert '"Шаг интегрирования, с"' in suite_card_panel_text
    assert '"Продольное ускорение ax, м/с²"' in suite_card_panel_text
    assert '"Поперечное ускорение ay, м/с²"' in suite_card_panel_text
    assert '"Применить изменения"' in suite_card_panel_text
    assert '"Сценарий обновлён."' in suite_card_panel_text
    assert "Шаблон сценария добавлен в набор." in heavy_text
    assert "Не удалось добавить шаблон сценария:" in heavy_text
    assert "Загрузить набор сценариев (JSON)" in heavy_text
    assert "Можно загрузить ранее сохранённый файл suite.json с набором сценариев." in heavy_text
    assert "Набор сценариев загружен." in heavy_text
    assert "Файл JSON должен содержать список сценариев." in heavy_text
    assert "Скачать набор сценариев (JSON)" in heavy_text
    assert "Набор сценариев и ограничения" in heavy_text
    assert "Здесь задаются параметры сценариев и целевые запасы/ограничения." in heavy_text
    assert "Видимые сценарии обновлены." in heavy_text
    assert "Не удалось обновить видимые сценарии:" in heavy_text
    assert "Выбранный сценарий продублирован." in heavy_text
    assert "Не удалось продублировать сценарий:" in heavy_text
    assert "Выбранный сценарий удалён из набора." in heavy_text
    assert "Не удалось удалить сценарий:" in heavy_text
    assert "Строка {i+1}: пустое имя сценария" in heavy_text
    assert "Сценарий '{name}': dt должен быть > 0" in heavy_text
    assert "Дубли имён включённых сценариев:" in heavy_text
    assert "В наборе сценариев есть ошибки" in heavy_text
    assert "Опорный прогон сценариев" in heavy_text
    assert "Не удалось собрать набор сценариев:" in heavy_text
    assert 'st.selectbox("Сценарий", options=["(все)"] + test_names, index=0)' in heavy_text
    assert "В таблице опорного прогона нет доступных сценариев" in heavy_text
    assert 'st.selectbox("Сценарий для детального прогона"' in heavy_text
    assert "Авто-расчёт при выборе сценария" in heavy_text
    assert 'st.metric("Опорный прогон: сценариев", _n_total)' in heavy_text
    assert "Показывать график худших сценариев" in heavy_text
    assert "Строит Plotly‑график по худшим сценариям" in heavy_text
    assert "Показывает таблицу pen_* по сценариям" in heavy_text
    assert "Худшие сценарии по суммарному штрафу:" in heavy_text
    assert "Худшие сценарии (суммарный штраф)" in heavy_text
    assert "Показывать опорные и служебные строки" in heavy_text
    assert "Опорные и служебные строки не считаются реальными кандидатами" in heavy_text
    assert "Скрыто опорных и служебных строк:" in heavy_text
    assert 'xaxis_title="Сценарий"' in heavy_text
    assert 'labels=dict(x="Сценарий", y="Критерий", color="Штраф")' in heavy_text
    assert "Сначала запустите опорный прогон. Затем выберите один сценарий" in heavy_text
    assert "получите расширенный лог расчёта" in heavy_text
    assert "Расширенный лог (потоки и состояния)" in heavy_text
    assert "Рассчитать полный лог ДЛЯ ВСЕХ сценариев" in heavy_text
    assert "Экспорт NPZ ДЛЯ ВСЕХ сценариев (из кэша)" in heavy_text
    assert "Считаю полный лог для всех сценариев" in heavy_text
    assert "Экспортирую NPZ для всех сценариев" in heavy_text
    assert "Для массового расчёта включите расширенный лог расчёта" in heavy_text
    assert "Экспорт NPZ доступен только для расширенного лога расчёта" in heavy_text
    assert "Нужно для запуска oneclick/autopilot." in heavy_text
    assert "Сопоставление файлов ➜ Txx_osc.npz" in heavy_text
    assert "Калибровочные пайплайны по умолчанию ищут файлы" in heavy_text
    assert "Применить сопоставление (создать/обновить Txx_osc.npz)" in heavy_text
    assert "Показать путь к osc_dir" in heavy_text
    assert "Для сопоставления файлов нужны: (1) набор опорных сценариев" in heavy_text
    assert "Преобразование CSV ➜ NPZ" in heavy_text
    assert "Запуск калибровочных пайплайнов" in heavy_text
    assert "Автоматизация (без консоли): полный расчёт ➜ NPZ ➜ калибровочный пайплайн" in heavy_text
    assert "и запускать пайплайны oneclick/autopilot как самопроверку" in heavy_text
    assert "Калибровка и пакетные пайплайны (NPZ/CSV) — эксперимент" in heavy_text
    assert "Калибровочные пайплайны и Autopilot читают Txx_osc.npz" in heavy_text
    assert "Случайное зерно для координатора" in heavy_text
    assert "Размер пакета q (сколько кандидатов предлагать за шаг)" in heavy_text
    assert "Вычислительное устройство для модели" in heavy_text
    assert "qNEHVI включается не сразу" in heavy_text
    assert "Режим runtime_env для Ray" in heavy_text
    assert "Дополнительный JSON для runtime_env Ray (необязательно)" in heavy_text
    assert "Evaluator-процессов Ray" in heavy_text
    assert "CPU на evaluator-процесс" in heavy_text
    assert "Proposer-процессов Ray" in heavy_text
    assert "GPU на proposer-процесс" in heavy_text
    assert "Движок базы данных" in heavy_text
    assert "Продолжить существующий запуск" in heavy_text
    assert "Явный run_id (необязательно)" in heavy_text
    assert "Срок устаревания, с" in heavy_text
    assert "Интервал экспорта, шагов" in heavy_text
    assert "BoTorch / qNEHVI: дополнительные настройки" in heavy_text
    assert "Начальных точек до qNEHVI (n-init)" in heavy_text
    assert "Минимум допустимых точек (min-feasible)" in heavy_text
    assert "Число перезапусков оптимизатора" in heavy_text
    assert "Число сырых выборок" in heavy_text
    assert "Макс. итераций оптимизатора" in heavy_text
    assert "Запас опорной точки (ref_margin)" in heavy_text
    assert "Нормализовать цели перед GP-fit" in heavy_text
    assert "2) Полный лог + NPZ ➜ oneclick-пайплайн" in heavy_text
    assert "Код завершения пайплайна oneclick:" in heavy_text
    assert "Пайплайн oneclick завершился с ошибкой" in heavy_text
    assert "Пайплайн oneclick выполнен. Результаты сохранены в рабочей папке запуска." in heavy_text
    assert "3) Полный лог + NPZ ➜ Autopilot (минимальный режим)" in heavy_text
    assert "Код завершения пайплайна Autopilot:" in heavy_text
    assert "Пайплайн Autopilot завершился с ошибкой" in heavy_text
    assert "Пайплайн Autopilot выполнен. Результаты сохранены в рабочей папке запуска." in heavy_text
    assert "Запустить пайплайн oneclick" in heavy_text
    assert "Запустить пайплайн Autopilot v19 (по NPZ)" in heavy_text
    assert "Desktop Animator (по последней выгрузке anim_latest)" in heavy_text
    assert "Авто-экспорт последней анимационной выгрузки (anim_latest)" in heavy_text
    assert "с указанием последней выгрузки" in heavy_text
    assert "Desktop Animator подхватит их автоматически." in heavy_text
    assert "Авто-запуск Desktop Animator при экспорте" in heavy_text
    assert "🖥 Desktop Animator (внешнее окно, по выгрузке anim_latest)" in heavy_text
    assert "Desktop Animator читает последнюю выгрузку из папки workspace/exports" in heavy_text
    assert "Экспортировать последнюю выгрузку (anim_latest)" in heavy_text
    assert "Не удалось экспортировать последнюю анимационную выгрузку:" in heavy_text
    assert "Последняя анимационная выгрузка сохранена:" in heavy_text
    assert "Файл NPZ:" in heavy_text
    assert "Готовность anim_latest:" in heavy_text
    assert "Без OpenGL (режим совместимости)" in heavy_text
    assert "Запустить Desktop Animator" in heavy_text
    assert "Desktop Animator запущен (если система позволяет GUI)." in heavy_text
    assert "Не удалось запустить Desktop Animator (см. логи)." in heavy_text
    assert "Другие отдельные GUI-окна проекта" in heavy_text
    assert "Открыть центр desktop-инструментов" in heavy_text
    assert "Открыть редактор исходных данных" in heavy_text
    assert "Открыть центр тестов" in heavy_text
    assert "Открыть GUI автотестов" in heavy_text
    assert "Открыть GUI диагностики" in heavy_text
    assert "Открыть GUI отправки результатов" in heavy_text
    assert "Открыть Compare Viewer" in heavy_text
    assert "Окно «{_window_label}» запущено (если система позволяет GUI)." in heavy_text
    assert "Не удалось запустить окно «{_window_label}» (см. логи)." in heavy_text
    assert "Что делать дальше сейчас" not in heavy_text
    assert "Последние артефакты" not in heavy_text
    assert "Рабочие папки desktop-контура" not in heavy_text
    assert "Подвеска: кинематика и перемещения, плюс проверка DW2D" in heavy_text
    assert "Кинематика и перемещения: в норме" in heavy_text
    assert "Кинематика и перемещения: требуют внимания" in heavy_text
    assert "Кинематика и перемещения: данных нет" in heavy_text
    assert "Рабочий диапазон DW2D: в норме" in heavy_text
    assert "Рабочий диапазон DW2D: требует внимания" in heavy_text
    assert "Рабочий диапазон DW2D: данных нет" in heavy_text
    assert "Проверка рабочего диапазона DW2D" in heavy_text
    assert "Нулевая поза в начале расчёта (t=0)" in heavy_text
    assert "Нулевая поза: в норме" in heavy_text
    assert "Нулевая поза: требует внимания" in heavy_text
    assert "Нулевая поза: данных нет" in heavy_text
    assert "Полный отчёт самопроверки (JSON)" in heavy_text
    assert "Стабилизатор:" in heavy_text
    assert "включён" in heavy_text
    assert "выключен (по умолчанию)" in heavy_text
    assert "Сообщение по механике:" in heavy_text
    assert "Настройка геометрии DW2D доступна на странице" in heavy_text
    assert "Файл прогресса обновлён" in heavy_text
    assert "служебный progress.json" in heavy_text
    assert "строк в CSV текущей стадии" in heavy_text
    assert "по данным progress-файла" in heavy_text
    assert "отстаёт от фактического CSV текущей стадии" in heavy_text
    assert "Угол подвески" in heavy_text
    assert "Уровень дороги, м" in heavy_text
    assert "Колесо относительно рамы, м" in heavy_text
    assert "Шток C1, доля хода" in heavy_text
    assert "Шток C2, доля хода" in heavy_text
    assert "Диагностика — собрать архив ZIP для отправки" in heavy_text
    assert "Основная кнопка диагностики находится в боковой панели" in heavy_text
    assert "включите режим старых страниц" in heavy_text
    assert "Это **локальный архив ZIP**" in heavy_text
    assert "снимок текущих" in heavy_text
    assert "файлов настроек: база параметров, набор сценариев и диапазоны подбора" in heavy_text
    assert "Выберите файл (NPZ/CSV) для этого сценария" in heavy_text
    assert "К какому номеру сценария привязать (Txx_osc.npz)" in heavy_text
    assert "Нет набора опорных сценариев (списка сценариев)." in heavy_text
    assert "1) Полный лог + NPZ (все сценарии)" in heavy_text
    assert "Ошибка в сценарии {tn}:" in heavy_text
    assert "старый сохранённый детальный лог для этого сценария игнорируется" in heavy_text
    assert "Детальный лог для текущего сценария загружен из кэша." in heavy_text
    assert "Подавлен повторный автозапуск детального прогона для текущего сценария" in heavy_text
    assert "Не найден сценарий '{test_pick}' в наборе" in heavy_text
    assert "Тест-шаблон добавлен в набор." not in heavy_text
    assert "Загрузить тест-набор (JSON)" not in heavy_text
    assert "Тест-набор загружен." not in heavy_text
    assert "suite.json должен быть списком объектов (list[dict])." not in heavy_text
    assert "Скачать тест-набор (JSON)" not in heavy_text
    assert "Release:" not in heavy_text
    assert "Model:" not in heavy_text
    assert "base_hash:" not in heavy_text
    assert "suite_hash:" not in heavy_text
    assert "autoselfcheck:" not in heavy_text
    assert "stabilizer:" not in heavy_text
    assert "Разрешить оптимизацию несмотря на FAIL" not in heavy_text
    assert "ошибки selfcheck" not in heavy_text
    assert "Тест-набор и пороги" not in heavy_text
    assert "Здесь задаются параметры тестов и целевые запасы/ограничения." not in heavy_text
    assert "Авто‑обновлять baseline_best.json" not in heavy_text
    assert "cache_dir: `" not in heavy_text
    assert "Видимые тесты обновлены." not in heavy_text
    assert "Выбранный тест удалён из набора." not in heavy_text
    assert "Не удалось удалить тест:" not in heavy_text
    assert "пустое имя теста" not in heavy_text
    assert "В тест-наборе есть ошибки" not in heavy_text
    assert "Опорный прогон тестов" not in heavy_text
    assert "Не удалось собрать тест‑набор:" not in heavy_text
    assert "полный лог (record_full=True)" not in heavy_text
    assert 'st.selectbox("Тест", options=["(все)"] + test_names, index=0)' not in heavy_text
    assert "В таблице опорного прогона нет доступных тестов" not in heavy_text
    assert 'st.selectbox("Тест для детального прогона"' not in heavy_text
    assert "Авто-расчёт при выборе теста" not in heavy_text
    assert '"record_full (потоки/состояния)"' not in heavy_text
    assert 'st.metric("Опорный прогон: тестов", _n_total)' not in heavy_text
    assert "Показывать график худших тестов" not in heavy_text
    assert "Строит Plotly‑график по худшим тестам" not in heavy_text
    assert "Показывает таблицу pen_* по тестам" not in heavy_text
    assert "Худшие тесты по суммарному штрафу:" not in heavy_text
    assert "Худшие тесты (суммарный штраф)" not in heavy_text
    assert "Показывать baseline/service rows" not in heavy_text
    assert "Служебные baseline-anchor строки" not in heavy_text
    assert "Скрыто служебных baseline/service rows:" not in heavy_text
    assert "Показывать служебные строки baseline/service" not in heavy_text
    assert "Служебные строки baseline/service не считаются реальными кандидатами" not in heavy_text
    assert "Скрыто служебных строк baseline/service:" not in heavy_text
    assert 'xaxis_title="Тест"' not in heavy_text
    assert 'labels=dict(x="Тест", y="Критерий", color="Штраф")' not in heavy_text
    assert "Затем выберите один тест" not in heavy_text
    assert "Рассчитать полный лог ДЛЯ ВСЕХ тестов" not in heavy_text
    assert "Экспорт NPZ ДЛЯ ВСЕХ (из кэша)" not in heavy_text
    assert "Считаю полный лог для всех тестов" not in heavy_text
    assert "Экспортирую NPZ для всех тестов" not in heavy_text
    assert "Для массового расчёта включи record_full" not in heavy_text
    assert "Экспорт NPZ имеет смысл только при record_full=True" not in heavy_text
    assert "Нужно для oneclick/autopilot." not in heavy_text
    assert "Mapping файлов ➜ Txx_osc.npz" not in heavy_text
    assert "Применить mapping (создать/обновить Txx_osc.npz)" not in heavy_text
    assert "Открыть osc_dir (путь)" not in heavy_text
    assert "Для построения mapping нужны: (1) набор опорных сценариев" not in heavy_text
    assert "Конвертация CSV ➜ NPZ" not in heavy_text
    assert "Запуск пайплайнов калибровки" not in heavy_text
    assert "Автоматизация (без консоли): полный расчёт ➜ NPZ ➜ oneclick/autopilot" not in heavy_text
    assert "и гонять пайплайны oneclick/autopilot как самопроверку" not in heavy_text
    assert "Калибровка и Autopilot (NPZ/CSV) — эксперимент" not in heavy_text
    assert "Калибровка и Autopilot читают Txx_osc.npz" not in heavy_text
    assert "Seed (distributed / coordinator)" not in heavy_text
    assert '"q (сколько кандидатов предлагать за шаг)"' not in heavy_text
    assert "Устройство для модели (device)" not in heavy_text
    assert "qNEHVI gate: proposer включается не сразу" not in heavy_text
    assert '"Ray runtime_env mode"' not in heavy_text
    assert '"Ray runtime_env JSON merge (optional)"' not in heavy_text
    assert '"Ray evaluators"' not in heavy_text
    assert '"CPU на evaluator"' not in heavy_text
    assert '"Ray proposers"' not in heavy_text
    assert '"GPU на proposer"' not in heavy_text
    assert '"DB engine"' not in heavy_text
    assert '"Resume from existing run"' not in heavy_text
    assert '"Explicit run_id (optional)"' not in heavy_text
    assert '"stale-ttl-sec"' not in heavy_text
    assert '"export-every"' not in heavy_text
    assert "BoTorch / qNEHVI advanced" not in heavy_text
    assert '"n-init (warmup before qNEHVI)"' not in heavy_text
    assert '"min-feasible"' not in heavy_text
    assert '"num_restarts"' not in heavy_text
    assert '"raw_samples"' not in heavy_text
    assert '"maxiter"' not in heavy_text
    assert '"ref_margin"' not in heavy_text
    assert '"Normalize objectives before GP fit"' not in heavy_text
    assert "Код завершения oneclick:" not in heavy_text
    assert "Код завершения Autopilot:" not in heavy_text
    assert "Пайплайн oneclick выполнен. Результаты сохранены в out_dir." not in heavy_text
    assert "Пайплайн Autopilot выполнен. Результаты сохранены в out_dir." not in heavy_text
    assert "см. stdout/stderr ниже и файлы в out_dir." not in heavy_text
    assert "Диагностика — собрать ZIP (для отправки)" not in heavy_text
    assert "Единая кнопка диагностики находится в боковой панели" not in heavy_text
    assert "включите Legacy-режим" not in heavy_text
    assert "Это **локальный** ZIP" not in heavy_text
    assert "JSON (base/suite/ranges)" not in heavy_text
    assert "st.caption('Desktop Animator (follow)')" not in heavy_text
    assert "'Авто-экспорт anim_latest (Desktop Animator)'" not in heavy_text
    assert "Desktop Animator в follow-режиме подхватит автоматически." not in heavy_text
    assert "with st.expander('🖥 Desktop Animator (внешнее окно, follow anim_latest)'" not in heavy_text
    assert "st.caption('Animator читает последнюю выгрузку" not in heavy_text
    assert "if st.button('Экспортировать anim_latest сейчас'" not in heavy_text
    assert "st.error(f'Экспорт anim_latest не удался:" not in heavy_text
    assert "st.success(f'OK: {npz_latest.name}')" not in heavy_text
    assert "st.checkbox('no-gl (compat)'" not in heavy_text
    assert "if st.button('Запустить Animator (follow)'" not in heavy_text
    assert "st.success('Animator запущен (если система позволяет GUI).')" not in heavy_text
    assert "st.warning('Не удалось запустить Animator (см. логи).')" not in heavy_text
    assert "st.markdown('**DW2D dynamic range**')" not in heavy_text
    assert "st.markdown('**Полный autoself_post_json**')" not in heavy_text
    assert "st.success('Кинематика/перемещения: OK')" not in heavy_text
    assert "st.error('Кинематика/перемещения: FAIL')" not in heavy_text
    assert "st.info('Кинематика/перемещения: —')" not in heavy_text
    assert "'Рабочий диапазон DW2D: OK' if _dw_ok else 'Рабочий диапазон DW2D: ПРОБЛЕМА'" not in heavy_text
    assert "st.info('Рабочий диапазон DW2D: —')" not in heavy_text
    assert "'Нулевая поза: OK' if _pz_ok else 'Нулевая поза: ПРОБЛЕМА'" not in heavy_text
    assert "st.info('Нулевая поза: —')" not in heavy_text


def test_stage_policy_strings_are_localized() -> None:
    heavy_text = ENTRYPOINTS[1].read_text(encoding="utf-8")

    assert 'st.metric("Активный путь", "По стадиям" if opt_use_staged else "Распределённый")' in heavy_text
    assert "Параллельных задач" in heavy_text
    assert "Имя запуска" in heavy_text
    assert "Префикс CSV:" in heavy_text
    assert "Параллельных задач: {jobs}; запуск: {run_name}; префикс CSV: {out_prefix}" in heavy_text
    assert "Политика отбора и продвижения" in heavy_text
    assert "Профиль отбора и продвижения по стадиям" in heavy_text
    assert "Относительный шаг System Influence (eps_rel)" in heavy_text
    assert "Адаптивный epsilon для анализа System Influence" in heavy_text
    assert "Приоритетные параметры текущей стадии:" in heavy_text
    assert "строк в CSV текущей стадии" in heavy_text
    assert "по данным progress-файла" in heavy_text

    assert '"jobs"' not in heavy_text
    assert '"Run"' not in heavy_text
    assert "jobs={jobs}; run={run_name}; csv={out_prefix}" not in heavy_text
    assert "CSV prefix:" not in heavy_text
    assert "System Influence eps_rel:" not in heavy_text
    assert "Adaptive epsilon для анализа System Influence: on" not in heavy_text
    assert "st.write('Механика:', mech_msg)" not in heavy_text
    assert "st.write('Стабилизатор:', 'ВКЛ' if _stab_on else 'выкл (по умолчанию)')" not in heavy_text
    assert "Геометрия DW2D настраивается на странице:" not in heavy_text
    assert "Прогресс-файл обновлён" not in heavy_text
    assert "worker пишет progress.json" not in heavy_text
    assert "rows в CSV =" not in heavy_text
    assert "по progress worker =" not in heavy_text
    assert "Вложенный progress.json отстаёт от live CSV текущей стадии" not in heavy_text
    assert "st.caption(f'NPZ: {npz_path}')" not in heavy_text
    assert "'corner': _c" not in heavy_text
    assert "'road_m': _d.get('road_m', float('nan'))" not in heavy_text
    assert "'wheel_rel_frame_m': _d.get('wheel_rel_frame_m', float('nan'))" not in heavy_text
    assert "'rod_C1_frac': _d.get('rod_C1_frac', float('nan'))" not in heavy_text
    assert "'rod_C2_frac': _d.get('rod_C2_frac', float('nan'))" not in heavy_text
    assert 'if st.button("2) Полный лог + NPZ ➜ oneclick", key="oneclick_full_then_oneclick")' not in heavy_text
    assert 'st.write(f"oneclick exit code: {rc}")' not in heavy_text
    assert 'st.error("oneclick завершился с ошибкой — см. stdout/stderr ниже и файлы в out_dir.")' not in heavy_text
    assert 'st.success("oneclick выполнен. Результаты в out_dir.")' not in heavy_text
    assert 'if st.button("3) Полный лог + NPZ ➜ autopilot (minimal)", key="oneclick_full_then_autopilot")' not in heavy_text
    assert 'st.write(f"autopilot exit code: {rc}")' not in heavy_text
    assert 'st.error("autopilot завершился с ошибкой — см. stdout/stderr ниже и файлы в out_dir.")' not in heavy_text
    assert 'st.success("autopilot выполнен. Результаты в out_dir.")' not in heavy_text
    assert "Запустить калибровку (oneclick)" not in heavy_text
    assert "Запустить Autopilot (NPZ) v19" not in heavy_text
    assert "Выбери файл (NPZ/CSV) для этого теста" not in heavy_text
    assert "Для построения mapping нужны: (1) набор опорных тестов (список тестов)" not in heavy_text
    assert "старый detail cache для этого сценария игнорируется" not in heavy_text
    assert "В какой номер теста положить (Txx_osc.npz)" not in heavy_text
    assert "Нет набора опорных тестов (списка тестов)." not in heavy_text
    assert "1) Полный лог + NPZ (все тесты)" not in heavy_text
    assert "Ошибка в тесте {tn}:" not in heavy_text
    assert "старый detail cache для этого теста игнорируется" not in heavy_text
    assert "Детальный лог для текущего теста загружен из кэша." not in heavy_text
    assert "Подавлен повторный автозапуск детального прогона для текущего теста" not in heavy_text
    assert "Не найден тест '{test_pick}' в suite" not in heavy_text
