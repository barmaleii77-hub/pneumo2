from __future__ import annotations

import ast
import csv
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


ACTIVE_GUI_SPEC_IMPORT_VERSION = "v3"
ACTIVE_IMPORT_ROOT = _repo_root() / "docs" / "context" / "gui_spec_imports" / ACTIVE_GUI_SPEC_IMPORT_VERSION
UI_ELEMENT_CATALOG_PATH = ACTIVE_IMPORT_ROOT / "ui_element_catalog.csv"
FIELD_CATALOG_PATH = ACTIVE_IMPORT_ROOT / "field_catalog.csv"
HELP_CATALOG_PATH = ACTIVE_IMPORT_ROOT / "help_catalog.csv"
TOOLTIP_CATALOG_PATH = ACTIVE_IMPORT_ROOT / "tooltip_catalog.csv"
MIGRATION_MATRIX_PATH = ACTIVE_IMPORT_ROOT / "migration_matrix.csv"
KEYBOARD_MATRIX_PATH = ACTIVE_IMPORT_ROOT / "keyboard_matrix.csv"
DOCKING_MATRIX_PATH = ACTIVE_IMPORT_ROOT / "docking_matrix.csv"
UI_STATE_MATRIX_PATH = ACTIVE_IMPORT_ROOT / "ui_state_matrix.csv"
V19_GRAPH_IMPORT_ROOT = _repo_root() / "docs" / "context" / "gui_spec_imports" / "v19_graph_iteration"
V19_COGNITIVE_VISIBILITY_PATH = V19_GRAPH_IMPORT_ROOT / "COGNITIVE_VISIBILITY_MATRIX_V19.csv"
V19_TASK_CHECK_BLOCK_LOOP_PATH = V19_GRAPH_IMPORT_ROOT / "TASK_CHECK_BLOCK_LOOP_MATRIX_V19.csv"
V19_TREE_DIRECT_OPEN_PATH = V19_GRAPH_IMPORT_ROOT / "TREE_DIRECT_OPEN_MATRIX_V19.csv"
V19_NOT_PROVEN_CURRENT_WINDOWS_PATH = V19_GRAPH_IMPORT_ROOT / "NOT_PROVEN_CURRENT_WINDOWS_V19.csv"
V19_PATH_COST_SCENARIOS_PATH = V19_GRAPH_IMPORT_ROOT / "PATH_COST_SCENARIOS_V19.csv"
V19_GUI_LABEL_SEMANTIC_AUDIT_PATH = V19_GRAPH_IMPORT_ROOT / "GUI_LABEL_SEMANTIC_AUDIT_V19.csv"
V16_VISIBILITY_IMPORT_ROOT = _repo_root() / "docs" / "context" / "gui_spec_imports" / "v16_visibility_priority"
V16_MUST_SEE_STATE_PATH = V16_VISIBILITY_IMPORT_ROOT / "MUST_SEE_STATE_MATRIX_V16.csv"
V16_PLACEMENT_POLICY_PATH = V16_VISIBILITY_IMPORT_ROOT / "ALWAYS_VISIBLE_CONDITIONAL_INSPECTOR_MATRIX_V16.csv"
V16_WORKSPACE_FIRST_SECONDS_PATH = V16_VISIBILITY_IMPORT_ROOT / "WORKSPACE_FIRST_5_SECONDS_V16.csv"


@dataclass(frozen=True)
class UiElementCatalogEntry:
    element_id: str
    automation_id: str
    title: str
    kind: str
    region: str
    tooltip_id: str
    help_id: str
    purpose: str
    pipeline_node: str
    visibility: str
    availability: str
    access_key: str
    hotkey: str
    tab_index: float | None
    workspace_owner: str
    rect: dict[str, Any]


@dataclass(frozen=True)
class FieldCatalogEntry:
    field_id: str
    title: str
    field_type: str
    required: bool
    help_id: str
    short_hint: str
    catalog: str
    options: tuple[str, ...]
    unit: str


@dataclass(frozen=True)
class HelpCatalogEntry:
    help_id: str
    title: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class TooltipCatalogEntry:
    tooltip_id: str
    text: str
    rule: str
    related_help_id: str


@dataclass(frozen=True)
class MigrationMatrixEntry:
    web_feature_id: str
    title: str
    old_place: str
    new_place: str
    workspace_codes: tuple[str, ...]
    source_of_truth: str
    preserved_fully: bool
    improvements: str
    search_hint: str
    migration_status: str


@dataclass(frozen=True)
class KeyboardMatrixEntry:
    kind: str
    order: int | None
    value: str
    keys: str


@dataclass(frozen=True)
class DockingMatrixEntry:
    panel: str
    can_dock: bool
    can_float: bool
    can_auto_hide: bool
    can_second_monitor: bool
    note: str


@dataclass(frozen=True)
class UiStateMatrixEntry:
    state_id: str
    title: str
    border: str
    background: str
    text: str


@dataclass(frozen=True)
class V19CognitiveVisibilityEntry:
    vis_id: str
    workspace: str
    user_action_or_state: str
    optimized_visibility: str
    required_feedback: str
    why_critical: str


@dataclass(frozen=True)
class V19TaskCheckBlockLoopEntry:
    node_id: str
    workspace: str
    node_kind: str
    label: str


@dataclass(frozen=True)
class V19DirectOpenEntry:
    workspace: str
    tree_item: str
    optimized_route: str
    direct_open_required: bool
    intermediate_step_forbidden: bool


@dataclass(frozen=True)
class V19WorkspaceGuidance:
    workspace: str
    direct_open_route: str
    direct_open_required: bool
    intermediate_step_forbidden: bool
    visibility_lines: tuple[str, ...]
    check_lines: tuple[str, ...]
    block_lines: tuple[str, ...]
    loop_lines: tuple[str, ...]
    user_goals: tuple[str, ...]
    evidence_boundary: str


@dataclass(frozen=True)
class V19SemanticLabelEntry:
    node_id: str
    scope: str
    surface: str
    kind: str
    label_current: str
    label_recommended: str
    semantic_issue: str
    severity: str
    status: str
    semantic_quality_score: int | None


@dataclass(frozen=True)
class V16MustSeeStateEntry:
    workspace: str
    state_id: str
    state_name: str
    user_question: str
    severity: str
    visibility_policy: str
    primary_region: str
    trigger: str
    why_must_be_visible: str
    risk_if_hidden: str
    recommended_ui_pattern: str


@dataclass(frozen=True)
class V16PlacementPolicyEntry:
    workspace: str
    state_id: str
    state_name: str
    visibility_policy: str
    required_treatment: str
    default_region: str
    can_live_only_in_inspector: str


@dataclass(frozen=True)
class V16WorkspaceVisibilityGuidance:
    workspace: str
    first_seconds: str
    always_visible_lines: tuple[str, ...]
    conditional_lines: tuple[str, ...]
    inspector_boundary_lines: tuple[str, ...]
    search_hints: tuple[str, ...]


def _load_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    if not path.exists():
        return ()
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _safe_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_bool(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on", "да", "д"}


def _safe_literal(raw: str) -> Any:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        return ast.literal_eval(text)
    except Exception:
        return {}


def _tuple_from_scalar_or_list(raw: Any) -> tuple[str, ...]:
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return ()
        if text.startswith("[") and text.endswith("]"):
            parsed = _safe_literal(text)
            if isinstance(parsed, (list, tuple)):
                return tuple(_safe_text(item) for item in parsed if _safe_text(item))
        return (text,)
    if isinstance(raw, (list, tuple)):
        return tuple(_safe_text(item) for item in raw if _safe_text(item))
    return ()


def _safe_float(raw: Any) -> float | None:
    try:
        return float(raw)
    except Exception:
        return None


def _safe_int(raw: Any) -> int | None:
    try:
        return int(raw)
    except Exception:
        return None


def _split_workspace_codes(raw: str) -> tuple[str, ...]:
    values = [part.strip() for part in str(raw or "").replace(",", ";").split(";")]
    return tuple(part for part in values if part)


def _v16_region_text(raw: str) -> str:
    text = _safe_text(raw)
    replacements = (
        ("top_bar", "верхняя панель"),
        ("left_tree", "левое дерево"),
        ("message_bar", "полоса предупреждений"),
        ("center_primary_action", "основное действие в центре"),
        ("center_contents", "состав в центре"),
        ("secondary_action", "вторичное действие"),
        ("center_summary", "сводка в центре"),
        ("center_graphic_header", "заголовок графики"),
        ("center_graphic", "графика в центре"),
        ("top_strip", "верхняя лента"),
        ("bottom_status", "нижняя строка состояния"),
        ("inspector", "правая панель"),
        ("+", " + "),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return " ".join(text.split())


def _operator_v16_text(raw: Any) -> str:
    text = _operator_v19_text(raw)
    replacements = (
        ("Собрать " "диаг" "ностику", "Сохранить архив проекта"),
        ("собрать " "диаг" "ностику", "сохранить архив проекта"),
        ("Диаг" "ностика", "Проверка проекта"),
        ("диаг" "ностика", "проверка проекта"),
        ("диаг" "ностику", "проверку проекта"),
        ("cross-workspace", "между окнами"),
        ("dirty", "есть несохранённые изменения"),
        ("stale", "устаревший"),
        ("Enabled", "Включено"),
        ("enabled", "включено"),
        ("Status", "Состояние"),
        ("status", "состояние"),
        ("-link", " связь"),
        ("Link", "Связь"),
        ("link", "связь"),
        ("mismatch", "расхождение"),
        ("degraded", "сниженная достоверность"),
        ("conflict", "конфликт"),
        ("Freshness + path + time", "Свежесть, путь и время"),
        ("Visible архив contents list", "Видимый список состава архива"),
        ("run identity", "карточка выбранного прогона"),
        ("Run identity", "Карточка выбранного прогона"),
        ("report", "отчёт"),
        ("card", "карточка"),
        ("Health", "Состояние"),
        ("health", "состояние"),
        ("first-class surface", "основное окно"),
        ("first маршрутs", "основных маршрута"),
        ("first маршрут", "основной маршрут"),
        ("primary button", "основная кнопка"),
        ("Primary button", "Основная кнопка"),
        ("primary", "основной"),
        ("Primary", "Основной"),
        ("button", "кнопка"),
        ("Button", "Кнопка"),
        ("Packaging", "Упаковка"),
        ("packaging", "упаковка"),
        ("intersection", "пересечение"),
        ("Master-copy", "Главная копия"),
        ("master-copy", "главная копия"),
        ("Truth-state", "состояние достоверности"),
        ("truth-state", "состояние достоверности"),
        ("inspector/help", "правая панель и справка"),
        ("inspector", "правая панель"),
        ("help", "справка"),
        ("summary", "сводка"),
        ("banner", "предупреждение"),
        ("inline", "прямо в окне"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    polish_replacements = (
        ("Свежесть архив", "Свежесть архива"),
        ("Состав архив", "Состав архива"),
        ("последнего архив", "последнего архива"),
        ("готовности архив", "готовности архива"),
        ("архиваа", "архива"),
        ("состояние сводка", "сводка состояния"),
        ("Состояние сводка", "Сводка состояния"),
        ("состояние/state", "состояние"),
        ("Главная копия входов должен", "Главная копия входов должна"),
        ("Главная копия входов должна быть явным", "Главная копия входов должна быть явной"),
        ("краткий состояние сводка", "краткая сводка состояния"),
        ("Состояние отчёт должен быть основное окно", "Отчёт о состоянии должен быть основным окном"),
        ("Проверка проекта должна иметь", "Проверка проекта должна иметь"),
    )
    for old, new in polish_replacements:
        text = text.replace(old, new)
    return " ".join(text.split())


@lru_cache(maxsize=1)
def load_v19_semantic_label_audit() -> tuple[V19SemanticLabelEntry, ...]:
    entries: list[V19SemanticLabelEntry] = []
    for row in _load_csv_rows(V19_GUI_LABEL_SEMANTIC_AUDIT_PATH):
        entries.append(
            V19SemanticLabelEntry(
                node_id=_safe_text(_row_value(row, "node_id")),
                scope=_safe_text(_row_value(row, "scope")),
                surface=_safe_text(_row_value(row, "surface")),
                kind=_safe_text(_row_value(row, "kind")),
                label_current=_safe_text(_row_value(row, "label_current")),
                label_recommended=_safe_text(_row_value(row, "label_recommended")),
                semantic_issue=_safe_text(_row_value(row, "semantic_issue")),
                severity=_safe_text(_row_value(row, "severity")),
                status=_safe_text(_row_value(row, "status")),
                semantic_quality_score=_safe_int(
                    _row_value(row, "semantic_quality_score_1_5")
                ),
            )
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def v19_notation_rewrites_by_label() -> dict[str, str]:
    rewrites: dict[str, str] = {}
    for entry in load_v19_semantic_label_audit():
        if entry.status != "rewrite" or entry.semantic_issue != "notation_without_name":
            continue
        if not entry.label_current or not entry.label_recommended:
            continue
        rewrites[entry.label_current] = entry.label_recommended
    return rewrites


def operator_semantic_text(raw: Any) -> str:
    text = _safe_text(raw)
    if not text:
        return ""

    text = v19_notation_rewrites_by_label().get(text, text)
    replacements = (
        ("C1/C2", "первый и второй контуры (C1/C2)"),
        ("problem hash", "контрольная метка задачи"),
        ("Problem hash", "Контрольная метка задачи"),
        ("hash", "контрольная метка"),
        ("Hash", "Контрольная метка"),
        ("objective contract", "цели расчёта"),
        ("Objective contract", "Цели расчёта"),
        ("baseline history", "история опорных прогонов"),
        ("Baseline history", "История опорных прогонов"),
        ("active baseline", "активный опорный прогон"),
        ("Active baseline", "Активный опорный прогон"),
        ("baseline", "опорный прогон"),
        ("Baseline", "Опорный прогон"),
        ("suite snapshot", "снимок набора испытаний"),
        ("Suite snapshot", "Снимок набора испытаний"),
        ("snapshot", "снимок"),
        ("Snapshot", "Снимок"),
        ("hard gate", "условие допуска"),
        ("Hard gate", "Условие допуска"),
        ("underfill", "недобор"),
        ("Underfill", "Недобор"),
        ("seed budget", "первичный лимит"),
        ("Seed budget", "Первичный лимит"),
        ("promotion-block", "блокировка продвижения кандидата"),
        ("promotion", "продвижение кандидата"),
        ("Promotion", "Продвижение кандидата"),
        ("gate reject", "отклонение по условию допуска"),
        ("surrogate samples", "черновые образцы"),
        ("Surrogate samples", "Черновые образцы"),
        ("Surrogate top-k", "Лучшие черновые варианты"),
        ("surrogate top-k", "лучшие черновые варианты"),
        ("Seed/promotion policy", "Правило первичного лимита и продвижения кандидата"),
        ("seed/promotion policy", "правило первичного лимита и продвижения кандидата"),
        ("StageRunner", "поэтапный запуск"),
        ("staged", "поэтапный"),
        ("Staged", "Поэтапный"),
        ("self-check", "самопроверка"),
        ("Self-check", "Самопроверка"),
        ("selfcheck", "самопроверка"),
        ("Selfcheck", "Самопроверка"),
        ("diagnostics " "bundle", "архив проекта"),
        ("Diagnostics " "bundle", "Архив проекта"),
        ("send-bundle", "архив проекта"),
        ("send " "bundle", "архив проекта"),
        ("bundle", "архив"),
        ("Bundle", "Архив"),
        ("helper python", "вспомогательный Python"),
        ("Helper python", "Вспомогательный Python"),
        ("helper-команд", "вспомогательных команд"),
        ("helper", "вспомогательный модуль"),
        ("Helper", "Вспомогательный модуль"),
        ("runtime", "среда выполнения"),
        ("Runtime", "Среда выполнения"),
        ("provenance", "происхождение"),
        ("Provenance", "Происхождение"),
        ("GUI ", ""),
        (" GUI", ""),
        ("stale", "устаревший"),
        ("Stale", "Устаревший"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    polish_replacements = (
        ("Допуск по условие допуска", "Допуск по условию допуска"),
        ("меняет контрольная метка задачи", "меняет контрольную метку задачи"),
        ("Режим контрольная метка задачи", "Режим контрольной метки задачи"),
        ("Путь к вспомогательный Python, через который", "Путь к вспомогательному Python; через него"),
        ("Путь к вспомогательный Python", "Путь к вспомогательному Python"),
        ("Карточка последнего опорный прогон", "Карточка последнего опорного прогона"),
        ("последнего опорный прогон", "последнего опорного прогона"),
        ("активный опорный прогон contract", "правила активного опорного прогона"),
        ("опорный прогон contract", "правила опорного прогона"),
        ("контрольная метка проверенный снимок", "контрольная метка проверенного снимка"),
        (" and ", " и "),
        (" or ", " или "),
    )
    for old, new in polish_replacements:
        text = text.replace(old, new)
    return " ".join(text.split()).strip()


def _semantic_payload(value: Any) -> Any:
    if isinstance(value, str):
        return operator_semantic_text(value)
    if isinstance(value, dict):
        return {key: _semantic_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_semantic_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_semantic_payload(item) for item in value)
    return value


def _operator_v19_text(raw: Any) -> str:
    text = operator_semantic_text(raw)
    replacements = (
        ("Badge", "метка"),
        ("badge", "метка"),
        ("badges", "метки"),
        ("Mode badge", "метка режима"),
        ("Lock badge", "метка блокировки"),
        ("Mode метка", "метка режима"),
        ("Lock метка", "метка блокировки"),
        ("inspector", "правая панель"),
        ("Inspector", "Правая панель"),
        ("preview", "предпросмотр"),
        ("Preview", "Предпросмотр"),
        ("stale", "устаревший"),
        ("Enabled", "Включено"),
        ("enabled", "включено"),
        ("Status", "Состояние"),
        ("status", "состояние"),
        ("-link", " связь"),
        ("Link", "Связь"),
        ("link", "связь"),
        ("snapshot", "снимок"),
        ("Snapshot", "Снимок"),
        ("Underfill", "недобор"),
        ("underfill", "недобор"),
        ("gate reasons", "причины недопуска"),
        ("selected counts", "выбранные количества"),
        ("Primary collect action", "основное действие сохранения"),
        ("Freshness + path + contents", "свежесть, путь и состав"),
        ("Contract summary", "сводка целей расчёта"),
        ("provenance", "происхождение"),
        ("Promotion reason list", "список причин продвижения"),
        ("Promotion reason", "причина продвижения"),
        ("blocked reason", "причина остановки"),
        ("validated", "проверенный"),
        ("active", "активный"),
        ("budget", "лимит"),
        ("context", "данные"),
        ("evidence manifest", "описание подтверждений"),
        ("helper", "помощник"),
        ("summary", "сводка"),
        ("message", "сообщение"),
        ("unified", "единый"),
        ("auto-close", "автозамыкание"),
        ("меткаs", "метки"),
        ("baseline", "опорный прогон"),
        ("Baseline", "Опорный прогон"),
        ("контракт", "условия расчёта"),
        ("Контракт", "Условия расчёта"),
        ("suite snapshot", "снимок набора испытаний"),
        ("suite", "набор испытаний"),
        ("Suite", "Набор испытаний"),
        ("objective contract", "цели расчёта"),
        ("Objective contract", "Цели расчёта"),
        ("hard gate", "обязательное условие"),
        ("Hard gate", "Обязательное условие"),
        ("seed budget", "первичный лимит"),
        ("stop/resume", "остановка и продолжение"),
        ("Health summary", "Сводка состояния"),
        ("health summary", "сводка состояния"),
        ("helper python", "вспомогательный Python"),
        ("Helper python", "Вспомогательный Python"),
        ("interpreter provenance", "происхождение интерпретатора"),
        ("workspace contract", "правила рабочего окна"),
        ("contract", "условия расчёта"),
        ("Contract", "Условия расчёта"),
        ("effective workspace", "текущее рабочее окно"),
        ("workspace", "рабочее окно"),
        ("Workspace", "Рабочее окно"),
        ("bundle", "архив проекта"),
        ("Bundle", "Архив проекта"),
        ("standard selfcheck", "стандартная самопроверка"),
        ("Standard selfcheck", "Стандартная самопроверка"),
        ("selfcheck", "самопроверка"),
        ("Selfcheck", "Самопроверка"),
        ("live rows", "живые строки"),
        ("Live rows", "Живые строки"),
        ("elapsed budget", "затраченное время"),
        ("method text", "описание метода"),
        ("residual mm", "остаток в миллиметрах"),
        ("mirrored update", "зеркальное обновление"),
        ("Selection sync", "синхронизация выбора"),
        ("unified preview", "единый предпросмотр"),
        ("Seam status", "статус шва"),
        ("live current", "текущие живые"),
        ("Live current", "Текущие живые"),
        ("runtime", "живой запуск"),
        ("Runtime", "Живой запуск"),
        ("still split", "ещё разделены"),
        ("Current layer", "Текущий слой"),
        ("current layer", "текущий слой"),
        ("evidence-bound", "ограничен подтверждением"),
        ("full coverage", "полное покрытие"),
        ("optimized canonical subgraph", "целевой граф"),
        ("locked last segment", "зафиксированный последний сегмент"),
        ("enum", "выбор"),
        ("route", "маршрут"),
        ("advanced", "расширенный"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return " ".join(text.split()).strip()


def _row_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    for key in keys:
        if key in row:
            return row.get(key)
    return ""


def _legacy_mojibake_key(key: str) -> str:
    try:
        return str(key).encode("utf-8").decode("cp1251")
    except Exception:
        return str(key)


def legacy_key_aliases(*keys: str) -> tuple[str, ...]:
    aliases: list[str] = []
    seen: set[str] = set()
    for key in keys:
        for alias in (str(key), _legacy_mojibake_key(str(key))):
            if alias and alias not in seen:
                aliases.append(alias)
                seen.add(alias)
    return tuple(aliases)


def _row_value_ru(row: dict[str, Any], *keys: str) -> Any:
    return _row_value(row, *legacy_key_aliases(*keys))


def _help_payload_and_title(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    title = operator_semantic_text(_row_value_ru(row, "название"))
    payload_obj = _safe_literal(
        _row_value_ru(row, "структура_развёрнутого_описания")
    )
    if not isinstance(payload_obj, dict):
        return title, {}
    nested_payload = _row_value_ru(payload_obj, "структура_развёрнутого_описания")
    if isinstance(nested_payload, dict):
        return (
            title or operator_semantic_text(_row_value_ru(payload_obj, "название")),
            _semantic_payload(nested_payload),
        )
    return (
        title or operator_semantic_text(_row_value_ru(payload_obj, "название")),
        _semantic_payload(payload_obj),
    )


@lru_cache(maxsize=1)
def load_ui_element_catalog() -> dict[str, UiElementCatalogEntry]:
    entries: dict[str, UiElementCatalogEntry] = {}
    for row in _load_csv_rows(UI_ELEMENT_CATALOG_PATH):
        element = UiElementCatalogEntry(
            element_id=_safe_text(_row_value(row, "id")),
            automation_id=_safe_text(_row_value(row, "automation_id")),
            title=operator_semantic_text(_row_value_ru(row, "название")),
            kind=_safe_text(_row_value_ru(row, "тип")),
            region=_safe_text(_row_value_ru(row, "регион")),
            tooltip_id=_safe_text(_row_value(row, "tooltip_id")),
            help_id=_safe_text(_row_value(row, "help_id")),
            purpose=operator_semantic_text(_row_value_ru(row, "назначение")),
            pipeline_node=_safe_text(_row_value_ru(row, "узел_пайплайна")),
            visibility=_safe_text(_row_value_ru(row, "видимость")),
            availability=_safe_text(_row_value_ru(row, "доступность")),
            access_key=_safe_text(_row_value_ru(row, "клавиша_доступа")),
            hotkey=_safe_text(_row_value_ru(row, "горячая_клавиша")),
            tab_index=_safe_float(_row_value(row, "tab_index")),
            workspace_owner=_safe_text(_row_value(row, "workspace_owner")),
            rect=_safe_literal(_row_value_ru(row, "прямоугольник_в_базовом_окне")),
        )
        if element.element_id:
            entries[element.element_id] = element
    return entries


@lru_cache(maxsize=1)
def load_field_catalog() -> dict[str, FieldCatalogEntry]:
    entries: dict[str, FieldCatalogEntry] = {}
    for row in _load_csv_rows(FIELD_CATALOG_PATH):
        entry = FieldCatalogEntry(
            field_id=_safe_text(_row_value(row, "id")),
            title=operator_semantic_text(_row_value_ru(row, "название")),
            field_type=_safe_text(_row_value_ru(row, "тип")),
            required=_safe_bool(_row_value_ru(row, "обязательное")),
            help_id=_safe_text(_row_value(row, "help_id")),
            short_hint=operator_semantic_text(_row_value_ru(row, "короткая_подсказка")),
            catalog=_safe_text(_row_value_ru(row, "каталог")),
            options=_tuple_from_scalar_or_list(_row_value_ru(row, "варианты")),
            unit=operator_semantic_text(_row_value_ru(row, "единица_измерения")),
        )
        if entry.field_id:
            entries[entry.field_id] = entry
    return entries


@lru_cache(maxsize=1)
def load_help_catalog() -> dict[str, HelpCatalogEntry]:
    entries: dict[str, HelpCatalogEntry] = {}
    for row in _load_csv_rows(HELP_CATALOG_PATH):
        title, payload = _help_payload_and_title(row)
        entry = HelpCatalogEntry(
            help_id=_safe_text(_row_value(row, "id")),
            title=title,
            payload=payload,
        )
        if entry.help_id:
            entries[entry.help_id] = entry
    return entries


@lru_cache(maxsize=1)
def load_tooltip_catalog() -> dict[str, TooltipCatalogEntry]:
    entries: dict[str, TooltipCatalogEntry] = {}
    for row in _load_csv_rows(TOOLTIP_CATALOG_PATH):
        entry = TooltipCatalogEntry(
            tooltip_id=_safe_text(_row_value(row, "id")),
            text=operator_semantic_text(_row_value_ru(row, "текст")),
            rule=operator_semantic_text(_row_value_ru(row, "правило")),
            related_help_id=_safe_text(_row_value_ru(row, "связанная_помощь")),
        )
        if entry.tooltip_id:
            entries[entry.tooltip_id] = entry
    return entries


@lru_cache(maxsize=1)
def load_migration_matrix() -> tuple[MigrationMatrixEntry, ...]:
    entries: list[MigrationMatrixEntry] = []
    for row in _load_csv_rows(MIGRATION_MATRIX_PATH):
        entries.append(
            MigrationMatrixEntry(
                web_feature_id=_safe_text(_row_value(row, "web_feature_id")),
                title=_safe_text(_row_value_ru(row, "название_функции")),
                old_place=_safe_text(_row_value_ru(row, "старое_место")),
                new_place=_safe_text(_row_value_ru(row, "новое_место")),
                workspace_codes=_split_workspace_codes(_row_value(row, "workspace")),
                source_of_truth=_safe_text(_row_value(row, "source_of_truth")),
                preserved_fully=_safe_bool(_row_value_ru(row, "сохранена_полностью")),
                improvements=_safe_text(_row_value_ru(row, "улучшения")),
                search_hint=_safe_text(_row_value_ru(row, "как_найти_через_поиск_команд")),
                migration_status=_safe_text(_row_value_ru(row, "статус_" "мигра" "ции")),
            )
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def load_keyboard_matrix() -> tuple[KeyboardMatrixEntry, ...]:
    entries: list[KeyboardMatrixEntry] = []
    for row in _load_csv_rows(KEYBOARD_MATRIX_PATH):
        entries.append(
            KeyboardMatrixEntry(
                kind=_safe_text(_row_value_ru(row, "тип")),
                order=int(_safe_float(_row_value_ru(row, "порядок")) or 0)
                if _safe_float(_row_value_ru(row, "порядок")) is not None
                else None,
                value=_safe_text(_row_value_ru(row, "значение")),
                keys=_safe_text(_row_value_ru(row, "клавиши")),
            )
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def load_docking_matrix() -> tuple[DockingMatrixEntry, ...]:
    entries: list[DockingMatrixEntry] = []
    for row in _load_csv_rows(DOCKING_MATRIX_PATH):
        entries.append(
            DockingMatrixEntry(
                panel=_safe_text(_row_value(row, "панель")),
                can_dock=_safe_bool(_row_value(row, "можно_докировать")),
                can_float=_safe_bool(_row_value(row, "можно_плавающее_окно")),
                can_auto_hide=_safe_bool(_row_value(row, "можно_auto_hide")),
                can_second_monitor=_safe_bool(_row_value(row, "можно_на_второй_монитор")),
                note=_safe_text(_row_value(row, "замечание")),
            )
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def load_ui_state_matrix() -> dict[str, UiStateMatrixEntry]:
    entries: dict[str, UiStateMatrixEntry] = {}
    for row in _load_csv_rows(UI_STATE_MATRIX_PATH):
        entry = UiStateMatrixEntry(
            state_id=_safe_text(_row_value(row, "id")),
            title=_safe_text(_row_value_ru(row, "название")),
            border=_safe_text(_row_value(row, "рамка")),
            background=_safe_text(_row_value(row, "фон")),
            text=_safe_text(_row_value(row, "текст")),
        )
        if entry.state_id:
            entries[entry.state_id] = entry
    return entries


@lru_cache(maxsize=1)
def load_v19_cognitive_visibility_matrix() -> tuple[V19CognitiveVisibilityEntry, ...]:
    entries: list[V19CognitiveVisibilityEntry] = []
    for row in _load_csv_rows(V19_COGNITIVE_VISIBILITY_PATH):
        entries.append(
            V19CognitiveVisibilityEntry(
                vis_id=_safe_text(_row_value(row, "vis_id")),
                workspace=_safe_text(_row_value(row, "workspace")),
                user_action_or_state=_operator_v19_text(
                    _row_value(row, "user_action_or_state")
                ),
                optimized_visibility=_operator_v19_text(
                    _row_value(row, "optimized_visibility")
                ),
                required_feedback=_operator_v19_text(
                    _row_value(row, "required_feedback")
                ),
                why_critical=_operator_v19_text(_row_value(row, "why_critical")),
            )
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def load_v19_task_check_block_loop_matrix() -> tuple[V19TaskCheckBlockLoopEntry, ...]:
    entries: list[V19TaskCheckBlockLoopEntry] = []
    for row in _load_csv_rows(V19_TASK_CHECK_BLOCK_LOOP_PATH):
        entries.append(
            V19TaskCheckBlockLoopEntry(
                node_id=_safe_text(_row_value(row, "node_id")),
                workspace=_safe_text(_row_value(row, "workspace")),
                node_kind=_safe_text(_row_value(row, "node_kind")),
                label=_operator_v19_text(_row_value(row, "label")),
            )
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def load_v19_tree_direct_open_matrix() -> tuple[V19DirectOpenEntry, ...]:
    entries: list[V19DirectOpenEntry] = []
    for row in _load_csv_rows(V19_TREE_DIRECT_OPEN_PATH):
        entries.append(
            V19DirectOpenEntry(
                workspace=_safe_text(_row_value(row, "workspace")),
                tree_item=_operator_v19_text(_row_value(row, "tree_item")),
                optimized_route=_operator_v19_text(_row_value(row, "optimized_route")),
                direct_open_required=_safe_bool(_row_value(row, "direct_open_required")),
                intermediate_step_forbidden=_safe_bool(
                    _row_value(row, "intermediate_step_forbidden")
                ),
            )
        )
    return tuple(entries)


def _top_v19_lines(
    rows: tuple[V19TaskCheckBlockLoopEntry, ...],
    workspace: str,
    node_kind: str,
    *,
    limit: int = 3,
) -> tuple[str, ...]:
    lines: list[str] = []
    for row in rows:
        if row.workspace != workspace or row.node_kind != node_kind or not row.label:
            continue
        if row.label not in lines:
            lines.append(row.label)
        if len(lines) >= limit:
            break
    return tuple(lines)


@lru_cache(maxsize=1)
def v19_guidance_by_workspace_code() -> dict[str, V19WorkspaceGuidance]:
    visibility_rows = load_v19_cognitive_visibility_matrix()
    task_rows = load_v19_task_check_block_loop_matrix()
    direct_rows = {row.workspace: row for row in load_v19_tree_direct_open_matrix()}
    not_proven_rows = {
        _safe_text(_row_value(row, "workspace")): _operator_v19_text(
            _row_value(row, "what_is_not_proven")
        )
        for row in _load_csv_rows(V19_NOT_PROVEN_CURRENT_WINDOWS_PATH)
    }
    path_goals: dict[str, list[str]] = {}
    for row in _load_csv_rows(V19_PATH_COST_SCENARIOS_PATH):
        workspace = _safe_text(_row_value(row, "workspace"))
        goal = _operator_v19_text(_row_value(row, "user_goal"))
        if workspace and goal:
            path_goals.setdefault(workspace, []).append(goal)

    guidance: dict[str, V19WorkspaceGuidance] = {}
    workspaces = sorted(
        {
            *(row.workspace for row in visibility_rows if row.workspace),
            *(row.workspace for row in task_rows if row.workspace),
            *direct_rows.keys(),
        }
    )
    for workspace in workspaces:
        direct = direct_rows.get(workspace)
        visibility_lines: list[str] = []
        for row in visibility_rows:
            if row.workspace != workspace:
                continue
            line = ". ".join(
                part
                for part in (
                    row.optimized_visibility,
                    f"Обратная связь: {row.required_feedback}"
                    if row.required_feedback
                    else "",
                )
                if part
            )
            if line and line not in visibility_lines:
                visibility_lines.append(line)
            if len(visibility_lines) >= 3:
                break

        guidance[workspace] = V19WorkspaceGuidance(
            workspace=workspace,
            direct_open_route=direct.optimized_route if direct is not None else "",
            direct_open_required=direct.direct_open_required if direct is not None else False,
            intermediate_step_forbidden=(
                direct.intermediate_step_forbidden if direct is not None else False
            ),
            visibility_lines=tuple(visibility_lines),
            check_lines=_top_v19_lines(task_rows, workspace, "check"),
            block_lines=_top_v19_lines(task_rows, workspace, "block", limit=2),
            loop_lines=_top_v19_lines(task_rows, workspace, "loop", limit=2),
            user_goals=tuple(path_goals.get(workspace, ())[:3]),
            evidence_boundary=(
                not_proven_rows.get(workspace)
                or "Текущие внутренние экраны не считаются доказанными без отдельного живого артефакта."
            ),
        )
    return guidance


def get_v19_workspace_guidance(workspace_code: str | None) -> V19WorkspaceGuidance | None:
    if not workspace_code:
        return None
    return v19_guidance_by_workspace_code().get(str(workspace_code).strip())


@lru_cache(maxsize=1)
def v19_search_hints_by_workspace_code() -> dict[str, tuple[str, ...]]:
    hints: dict[str, tuple[str, ...]] = {}
    for workspace, guidance in v19_guidance_by_workspace_code().items():
        values = (
            *guidance.visibility_lines,
            *guidance.check_lines,
            *guidance.block_lines,
            *guidance.loop_lines,
            *guidance.user_goals,
            guidance.direct_open_route,
        )
        seen: set[str] = set()
        ordered: list[str] = []
        for raw in values:
            text = _operator_v19_text(raw)
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(text)
        hints[workspace] = tuple(ordered)
    return hints


@lru_cache(maxsize=1)
def load_v16_must_see_state_matrix() -> tuple[V16MustSeeStateEntry, ...]:
    entries: list[V16MustSeeStateEntry] = []
    for row in _load_csv_rows(V16_MUST_SEE_STATE_PATH):
        entries.append(
            V16MustSeeStateEntry(
                workspace=_safe_text(_row_value(row, "workspace")),
                state_id=_safe_text(_row_value(row, "state_id")),
                state_name=_operator_v16_text(_row_value(row, "state_name")),
                user_question=_operator_v16_text(_row_value(row, "user_question")),
                severity=_safe_text(_row_value(row, "severity")),
                visibility_policy=_safe_text(_row_value(row, "visibility_policy")),
                primary_region=_v16_region_text(_row_value(row, "primary_region")),
                trigger=_operator_v16_text(_row_value(row, "trigger")),
                why_must_be_visible=_operator_v16_text(
                    _row_value(row, "why_must_be_visible")
                ),
                risk_if_hidden=_operator_v16_text(_row_value(row, "risk_if_hidden")),
                recommended_ui_pattern=_operator_v16_text(
                    _row_value(row, "recommended_ui_pattern")
                ),
            )
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def load_v16_placement_policy_matrix() -> tuple[V16PlacementPolicyEntry, ...]:
    entries: list[V16PlacementPolicyEntry] = []
    for row in _load_csv_rows(V16_PLACEMENT_POLICY_PATH):
        entries.append(
            V16PlacementPolicyEntry(
                workspace=_safe_text(_row_value(row, "workspace")),
                state_id=_safe_text(_row_value(row, "state_id")),
                state_name=_operator_v16_text(_row_value(row, "state_name")),
                visibility_policy=_safe_text(_row_value(row, "visibility_policy")),
                required_treatment=_operator_v16_text(
                    _row_value(row, "required_treatment")
                ),
                default_region=_v16_region_text(_row_value(row, "default_region")),
                can_live_only_in_inspector=_operator_v16_text(
                    _row_value(row, "can_live_only_in_inspector")
                ),
            )
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def v16_first_seconds_by_workspace_code() -> dict[str, str]:
    return {
        _safe_text(_row_value(row, "workspace")): _operator_v16_text(
            _row_value(row, "must_be_understood_in_first_5_seconds")
        )
        for row in _load_csv_rows(V16_WORKSPACE_FIRST_SECONDS_PATH)
        if _safe_text(_row_value(row, "workspace"))
    }


def _dedupe_text(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        text = _operator_v16_text(raw)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return tuple(ordered)


@lru_cache(maxsize=1)
def v16_guidance_by_workspace_code() -> dict[str, V16WorkspaceVisibilityGuidance]:
    must_rows = load_v16_must_see_state_matrix()
    placement_by_state = {
        row.state_id: row for row in load_v16_placement_policy_matrix() if row.state_id
    }
    first_seconds = v16_first_seconds_by_workspace_code()
    workspaces = sorted(
        {
            *(row.workspace for row in must_rows if row.workspace),
            *first_seconds.keys(),
        }
    )

    guidance: dict[str, V16WorkspaceVisibilityGuidance] = {}
    for workspace in workspaces:
        rows = tuple(row for row in must_rows if row.workspace == workspace)
        always_lines: list[str] = []
        conditional_lines: list[str] = []
        boundary_lines: list[str] = []
        search_values: list[str] = []
        for row in rows:
            placement = placement_by_state.get(row.state_id)
            visibility_policy = (
                placement.visibility_policy if placement is not None else row.visibility_policy
            )
            region = (
                placement.default_region if placement is not None else row.primary_region
            )
            trigger = row.trigger if row.trigger else "при необходимости"
            pattern = row.recommended_ui_pattern
            line = ". ".join(
                part
                for part in (
                    f"{row.state_name} — {region}",
                    f"Показ: {pattern}" if pattern else "",
                )
                if part
            )
            if visibility_policy == "always":
                always_lines.append(line)
            else:
                conditional_lines.append(
                    ". ".join(
                        part
                        for part in (
                            f"{row.state_name} — {region}",
                            f"Когда: {trigger}",
                            f"Риск: {row.risk_if_hidden}" if row.risk_if_hidden else "",
                        )
                        if part
                    )
                )
            if placement is not None and "нет" in placement.can_live_only_in_inspector.casefold():
                boundary_lines.append(
                    f"{row.state_name}: не прятать только в правой панели; {placement.required_treatment}."
                )
            elif placement is not None and placement.can_live_only_in_inspector:
                boundary_lines.append(
                    f"{row.state_name}: {placement.can_live_only_in_inspector}."
                )
            search_values.extend(
                (
                    row.state_name,
                    row.user_question,
                    row.why_must_be_visible,
                    row.risk_if_hidden,
                    row.recommended_ui_pattern,
                    row.primary_region,
                )
            )
        guidance[workspace] = V16WorkspaceVisibilityGuidance(
            workspace=workspace,
            first_seconds=first_seconds.get(workspace, ""),
            always_visible_lines=_dedupe_text(always_lines),
            conditional_lines=_dedupe_text(conditional_lines),
            inspector_boundary_lines=_dedupe_text(boundary_lines),
            search_hints=_dedupe_text(search_values),
        )
    return guidance


def get_v16_workspace_guidance(workspace_code: str | None) -> V16WorkspaceVisibilityGuidance | None:
    if not workspace_code:
        return None
    return v16_guidance_by_workspace_code().get(str(workspace_code).strip())


@lru_cache(maxsize=1)
def v16_search_hints_by_workspace_code() -> dict[str, tuple[str, ...]]:
    return {
        workspace: guidance.search_hints
        for workspace, guidance in v16_guidance_by_workspace_code().items()
    }


@lru_cache(maxsize=1)
def workspace_elements_by_owner() -> dict[str, tuple[UiElementCatalogEntry, ...]]:
    grouped: dict[str, list[UiElementCatalogEntry]] = {}
    for entry in load_ui_element_catalog().values():
        if not entry.workspace_owner:
            continue
        grouped.setdefault(entry.workspace_owner, []).append(entry)
    return {
        owner: tuple(
            sorted(
                items,
                key=lambda item: (
                    item.tab_index is None,
                    item.tab_index if item.tab_index is not None else 9999.0,
                    item.element_id,
                ),
            )
        )
        for owner, items in grouped.items()
    }


@lru_cache(maxsize=1)
def migration_hints_by_workspace_code() -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for entry in load_migration_matrix():
        hints = [entry.title, entry.old_place, entry.new_place, entry.search_hint]
        for code in entry.workspace_codes:
            grouped.setdefault(code, []).extend(hints)
    normalized: dict[str, tuple[str, ...]] = {}
    for code, values in grouped.items():
        seen: set[str] = set()
        ordered: list[str] = []
        for raw in values:
            text = _safe_text(raw)
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(text)
        normalized[code] = tuple(ordered)
    return normalized


@lru_cache(maxsize=1)
def keyboard_shortcuts_by_name() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in load_keyboard_matrix():
        if entry.kind != "горячая_клавиша":
            continue
        if entry.value and entry.keys:
            label = entry.value
            legacy_collect_label = "Собрать архив " + "для " + "от" + "правки"
            if label == legacy_collect_label:
                label = "Сохранить архив проекта"
            mapping[label] = entry.keys
            if entry.value == "Поиск команд":
                mapping["Быстрый поиск"] = entry.keys
    return mapping


@lru_cache(maxsize=1)
def f6_region_order() -> tuple[str, ...]:
    rows = [entry for entry in load_keyboard_matrix() if entry.kind == "F6_порядок" and entry.value]
    rows.sort(key=lambda item: (item.order is None, item.order if item.order is not None else 9999))
    return tuple(entry.value for entry in rows)


@lru_cache(maxsize=1)
def docking_rules_by_panel() -> dict[str, DockingMatrixEntry]:
    return {entry.panel: entry for entry in load_docking_matrix() if entry.panel}


@lru_cache(maxsize=1)
def ui_state_palette() -> dict[str, UiStateMatrixEntry]:
    return load_ui_state_matrix()


def get_ui_element(element_id: str | None) -> UiElementCatalogEntry | None:
    if not element_id:
        return None
    return load_ui_element_catalog().get(str(element_id))


def get_help_topic(help_id: str | None) -> HelpCatalogEntry | None:
    if not help_id:
        return None
    return load_help_catalog().get(str(help_id))


def get_tooltip(tooltip_id: str | None) -> TooltipCatalogEntry | None:
    if not tooltip_id:
        return None
    return load_tooltip_catalog().get(str(tooltip_id))
