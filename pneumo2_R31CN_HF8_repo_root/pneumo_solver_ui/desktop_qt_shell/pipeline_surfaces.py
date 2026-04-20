from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShellPipelineSurface:
    key: str
    workspace_id: str
    title: str
    tool_key: str | None
    purpose: str
    source_label: str
    next_action: str
    handoff_label: str
    search_aliases: tuple[str, ...] = ()


V38_PIPELINE_SURFACES: tuple[ShellPipelineSurface, ...] = (
    ShellPipelineSurface(
        key="ws_project",
        workspace_id="WS-PROJECT",
        title="Панель проекта",
        tool_key=None,
        purpose="Сводка проекта, готовность рабочих файлов и ближайший инженерный шаг.",
        source_label="Текущий проект и выбранная рабочая папка",
        next_action="Перейти к исходным данным или выбрать нужное окно в списке.",
        handoff_label="Начало работы",
        search_aliases=("проект", "панель проекта", "ближайший шаг", "готовность проекта"),
    ),
    ShellPipelineSurface(
        key="ws_inputs",
        workspace_id="WS-INPUTS",
        title="Исходные данные",
        tool_key="desktop_input_editor",
        purpose="Единое место изменения исходных параметров модели.",
        source_label="База проекта и допустимые значения ввода",
        next_action="Проверить геометрию, пневматику, механику и расчётные настройки.",
        handoff_label="Готовит исходные данные для сценариев и набора испытаний",
        search_aliases=("ввод", "параметры", "геометрия", "пневматика", "допустимые значения"),
    ),
    ShellPipelineSurface(
        key="ws_ring",
        workspace_id="WS-RING",
        title="Редактор циклического сценария",
        tool_key="desktop_ring_editor",
        purpose="Единое место подготовки дорожного профиля и циклического сценария.",
        source_label="Циклический сценарий",
        next_action="Проверить сегменты, стыки и экспорт сценария.",
        handoff_label="Готовит проверенный набор файлов для испытаний",
        search_aliases=("циклический сценарий", "редактор кольца", "сценарии", "профиль дороги", "экспорт сценария"),
    ),
    ShellPipelineSurface(
        key="ws_suite",
        workspace_id="WS-SUITE",
        title="Набор испытаний",
        tool_key="test_center",
        purpose="Проверенный набор испытаний без повторного владения геометрией сценария.",
        source_label="Экспорты циклического сценария и разрешённые поправки тестов",
        next_action="Проверить включение тестов, этапы, приоритеты, шаг расчёта и длительность.",
        handoff_label="Готовит проверенный набор испытаний для базового прогона",
        search_aliases=("набор испытаний", "матрица испытаний", "снимок набора", "контроль набора"),
    ),
    ShellPipelineSurface(
        key="ws_baseline",
        workspace_id="WS-BASELINE",
        title="Базовый прогон",
        tool_key="desktop_run_setup_center",
        purpose="Базовый прогон, история и правила его замены.",
        source_label="Проверенный набор испытаний",
        next_action="Создать или проверить базовый прогон перед оптимизацией.",
        handoff_label="Готовит выбранный базовый прогон для оптимизации",
        search_aliases=("базовый прогон", "опорный прогон", "активный прогон"),
    ),
    ShellPipelineSurface(
        key="ws_optimization",
        workspace_id="WS-OPTIMIZATION",
        title="Оптимизация",
        tool_key="desktop_optimizer_center",
        purpose="Параметры оптимизации, диапазоны поиска, цели, ограничения качества и один активный режим запуска.",
        source_label="Базовый прогон, параметры оптимизации и диапазоны поиска",
        next_action="Выбрать параметры оптимизации, диапазоны поиска, цель и режим запуска.",
        handoff_label="Готовит выбранный прогон для анализа",
        search_aliases=("оптимизация", "параметры оптимизации", "диапазоны поиска", "локальный запуск", "параллельный запуск", "цели расчёта"),
    ),
    ShellPipelineSurface(
        key="ws_analysis",
        workspace_id="WS-ANALYSIS",
        title="Анализ результатов",
        tool_key="desktop_results_center",
        purpose="Выбранный прогон, сравнение, проверка результатов и подготовка к визуализации.",
        source_label="Зафиксированный выбранный прогон",
        next_action="Выбрать прогон, сравнить результаты и подготовить результат для анимации.",
        handoff_label="Готовит данные анализа и перечень подтверждающих файлов",
        search_aliases=("анализ", "результаты", "сравнение", "проверка результатов"),
    ),
    ShellPipelineSurface(
        key="ws_animator",
        workspace_id="WS-ANIMATOR",
        title="Анимация",
        tool_key="desktop_animator",
        purpose="Достоверная визуализация результатов расчёта после анализа.",
        source_label="Данные анализа и ссылки на файлы результатов расчёта",
        next_action="Запускать анимацию только после выбора результатов расчёта.",
        handoff_label="Готовит сведения о визуализации для диагностики",
        search_aliases=("анимация", "визуализация", "трёхмерный вид", "мнемосхема"),
    ),
    ShellPipelineSurface(
        key="ws_diagnostics",
        workspace_id="WS-DIAGNOSTICS",
        title="Проверка и отправка",
        tool_key="desktop_diagnostics_center",
        purpose="Проверка файлов проекта, архив для отправки и понятный отчёт о готовности.",
        source_label="Результаты анализа, анимации и проверка готовности файлов",
        next_action="Проверить проект или подготовить архив для отправки.",
        handoff_label="Финальный архив для отправки и отчёт проверки",
        search_aliases=("проверка проекта", "архив для отправки", "отправка результатов", "проверка готовности"),
    ),
)


V38_PIPELINE_WORKSPACE_IDS: tuple[str, ...] = tuple(
    surface.workspace_id for surface in V38_PIPELINE_SURFACES
)


FALLBACK_TOOL_SURFACE_KEYS: dict[str, str] = {
    "autotest_gui": "ws_suite",
    "compare_viewer": "ws_analysis",
    "desktop_engineering_analysis_center": "ws_analysis",
    "desktop_geometry_reference_center": "ws_inputs",
    "desktop_mnemo": "ws_animator",
    "full_diagnostics": "ws_diagnostics",
    "send_results": "ws_diagnostics",
}


WORKSPACE_ARTIFACT_LABELS: dict[str, str] = {
    "exports": "Выгрузки расчётов",
    "uploads": "Загруженные исходные файлы",
    "road_profiles": "Профили дороги",
    "maneuvers": "Манёвры",
    "opt_runs": "Прогоны оптимизации",
    "ui_state": "Состояние интерфейса",
}


SERVICE_JARGON_BLOCKERS: tuple[str, ...] = (
    "Workspace:",
    "Источник workspace",
    "required dirs",
    "Технический модуль",
    "standalone_module",
    "managed_external",
    "migration_status",
    "runtime_kind",
    "pneumo_solver_ui.",
    "desktop_gui_spec_shell",
    "в shell",
    "shell registry",
    "раскладку shell",
    "сообщения shell",
    "Старый shell",
    "Рабочая поверхность shell",
    "Раскладка shell",
    "source-of-truth",
    "analysis context",
    "hard gate",
    "run identity",
    "launchable",
    "launcher-маршрутам",
    " n/a",
)


OPERATOR_FORBIDDEN_LABELS: tuple[str, ...] = (
    "Статус миграции",
    "статус миграции",
    "Открыть выбранный этап",
    "Данные машины",
    "Идентификатор",
    "идентификатор",
    "Идентичность запуска",
    "идентичность запуска",
    "Артефакт",
    "артефакт",
    "Маршрут",
    "маршрут",
    "Workspace:",
    "required dirs",
    "Технический модуль",
    "desktop_gui_spec_shell",
    "Маршрут проекта",
    "Открыть резервное старое окно",
    "Открыть резервное главное окно",
    "Резервное главное окно",
    "Старое окно",
    "Окно восстановления",
    "Раздел:",
    "Поверхность:",
    "Рабочие артефакты",
    "Процесс",
    "pid",
    "PID",
    "Контекстный инструмент",
    "контекстный переход",
    "инженерного контекста",
    "проектный контекст",
    "Служебный контекст анимации",
    "служебный контекст анимации",
    "Контекст анализа",
    "контекст анализа",
    "GUI-модули",
    "GUI-модуль",
    "GUI-окно",
    "GUI-окна",
    "специализированных GUI",
    "запущенные GUI",
    "Compare Viewer",
    "desktop-центр",
    "dock-панелей",
    "launch controls",
    "Проект: default",
    "C:\\",
    "Float",
    "Undocks and re-attaches the dock widget",
    "Close",
    "Closes the dock widget",
    "Scroll Left",
    "Scroll Right",
    "Проверочное рабочее место",
    "dt",
    "t_end",
)


def build_pipeline_surface_by_key() -> dict[str, ShellPipelineSurface]:
    return {surface.key: surface for surface in V38_PIPELINE_SURFACES}


def default_surface_key_for_tool(tool_key: str | None) -> str:
    if not tool_key:
        return "ws_project"
    for surface in V38_PIPELINE_SURFACES:
        if surface.tool_key == tool_key:
            return surface.key
    return FALLBACK_TOOL_SURFACE_KEYS.get(tool_key, "ws_project")


def operator_readiness_label(missing_dirs: tuple[str, ...]) -> str:
    if not missing_dirs:
        return "Рабочая папка готова"
    names = ", ".join(WORKSPACE_ARTIFACT_LABELS.get(name, name) for name in missing_dirs)
    return f"Нужно подготовить: {names}"


def workspace_source_label(source: str) -> str:
    if str(source or "").strip() == "PNEUMO_WORKSPACE_DIR":
        return "выбрана пользователем"
    return "папка проекта по умолчанию"


def artifact_state_label(dirname: str, missing_dirs: tuple[str, ...]) -> str:
    return "нет данных" if dirname in missing_dirs else "готово"


def service_jargon_hits(texts: list[str]) -> list[str]:
    hits: list[str] = []
    for text in texts:
        for blocker in SERVICE_JARGON_BLOCKERS:
            if blocker in text:
                hits.append(text)
                break
    return sorted(set(hits))


def forbidden_operator_label_hits(texts: list[str]) -> list[str]:
    hits: list[str] = []
    for text in texts:
        text_value = str(text)
        for label in OPERATOR_FORBIDDEN_LABELS:
            if label in text_value:
                hits.append(text_value)
                break
    return sorted(set(hits))
