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


def _load_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    if not path.exists():
        return ()
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _safe_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


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


def _split_workspace_codes(raw: str) -> tuple[str, ...]:
    values = [part.strip() for part in str(raw or "").replace(",", ";").split(";")]
    return tuple(part for part in values if part)


def _row_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    for key in keys:
        if key in row:
            return row.get(key)
    return ""


def _help_payload_and_title(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    title = _safe_text(_row_value(row, "название", "РЅР°Р·РІР°РЅРёРµ"))
    payload_obj = _safe_literal(
        _row_value(
            row,
            "структура_развёрнутого_описания",
            "СЃС‚СЂСѓРєС‚СѓСЂР°_СЂР°Р·РІС‘СЂРЅСѓС‚РѕРіРѕ_РѕРїРёСЃР°РЅРёСЏ",
        )
    )
    if not isinstance(payload_obj, dict):
        return title, {}
    nested_payload = payload_obj.get("структура_развёрнутого_описания")
    if isinstance(nested_payload, dict):
        return (
            title or _safe_text(payload_obj.get("название")),
            nested_payload,
        )
    return (
        title or _safe_text(payload_obj.get("название")),
        payload_obj,
    )


@lru_cache(maxsize=1)
def load_ui_element_catalog() -> dict[str, UiElementCatalogEntry]:
    entries: dict[str, UiElementCatalogEntry] = {}
    for row in _load_csv_rows(UI_ELEMENT_CATALOG_PATH):
        element = UiElementCatalogEntry(
            element_id=_safe_text(_row_value(row, "id")),
            automation_id=_safe_text(_row_value(row, "automation_id")),
            title=_safe_text(_row_value(row, "название", "РЅР°Р·РІР°РЅРёРµ")),
            kind=_safe_text(_row_value(row, "тип", "С‚РёРї")),
            region=_safe_text(_row_value(row, "регион", "СЂРµРіРёРѕРЅ")),
            tooltip_id=_safe_text(_row_value(row, "tooltip_id")),
            help_id=_safe_text(_row_value(row, "help_id")),
            purpose=_safe_text(_row_value(row, "назначение", "РЅР°Р·РЅР°С‡РµРЅРёРµ")),
            pipeline_node=_safe_text(_row_value(row, "узел_пайплайна", "СѓР·РµР»_РїР°Р№РїР»Р°Р№РЅР°")),
            visibility=_safe_text(_row_value(row, "видимость", "РІРёРґРёРјРѕСЃС‚СЊ")),
            availability=_safe_text(_row_value(row, "доступность", "РґРѕСЃС‚СѓРїРЅРѕСЃС‚СЊ")),
            access_key=_safe_text(_row_value(row, "клавиша_доступа", "РєР»Р°РІРёС€Р°_РґРѕСЃС‚СѓРїР°")),
            hotkey=_safe_text(_row_value(row, "горячая_клавиша", "РіРѕСЂСЏС‡Р°СЏ_РєР»Р°РІРёС€Р°")),
            tab_index=_safe_float(_row_value(row, "tab_index")),
            workspace_owner=_safe_text(_row_value(row, "workspace_owner")),
            rect=_safe_literal(
                _row_value(
                    row,
                    "прямоугольник_в_базовом_окне",
                    "РїСЂСЏРјРѕСѓРіРѕР»СЊРЅРёРє_РІ_Р±Р°Р·РѕРІРѕРј_РѕРєРЅРµ",
                )
            ),
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
            title=_safe_text(_row_value(row, "название", "РЅР°Р·РІР°РЅРёРµ")),
            field_type=_safe_text(_row_value(row, "тип", "С‚РёРї")),
            required=_safe_bool(_row_value(row, "обязательное", "РѕР±СЏР·Р°С‚РµР»СЊРЅРѕРµ")),
            help_id=_safe_text(_row_value(row, "help_id")),
            short_hint=_safe_text(_row_value(row, "короткая_подсказка", "РєРѕСЂРѕС‚РєР°СЏ_РїРѕРґСЃРєР°Р·РєР°")),
            catalog=_safe_text(_row_value(row, "каталог", "РєР°С‚Р°Р»РѕРі")),
            options=_tuple_from_scalar_or_list(_row_value(row, "варианты", "РІР°СЂРёР°РЅС‚С‹")),
            unit=_safe_text(_row_value(row, "единица_измерения", "РµРґРёРЅРёС†Р°_РёР·РјРµСЂРµРЅРёСЏ")),
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
            text=_safe_text(_row_value(row, "текст", "С‚РµРєСЃС‚")),
            rule=_safe_text(_row_value(row, "правило", "РїСЂР°РІРёР»Рѕ")),
            related_help_id=_safe_text(_row_value(row, "связанная_помощь", "СЃРІСЏР·Р°РЅРЅР°СЏ_РїРѕРјРѕС‰СЊ")),
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
                title=_safe_text(_row_value(row, "название_функции", "РЅР°Р·РІР°РЅРёРµ_С„СѓРЅРєС†РёРё")),
                old_place=_safe_text(_row_value(row, "старое_место", "СЃС‚Р°СЂРѕРµ_РјРµСЃС‚Рѕ")),
                new_place=_safe_text(_row_value(row, "новое_место", "РЅРѕРІРѕРµ_РјРµСЃС‚Рѕ")),
                workspace_codes=_split_workspace_codes(_row_value(row, "workspace")),
                source_of_truth=_safe_text(_row_value(row, "source_of_truth")),
                preserved_fully=_safe_bool(_row_value(row, "сохранена_полностью", "СЃРѕС…СЂР°РЅРµРЅР°_РїРѕР»РЅРѕСЃС‚СЊСЋ")),
                improvements=_safe_text(_row_value(row, "улучшения", "СѓР»СѓС‡С€РµРЅРёСЏ")),
                search_hint=_safe_text(
                    _row_value(
                        row,
                        "как_найти_через_поиск_команд",
                        "РєР°Рє_РЅР°Р№С‚Рё_С‡РµСЂРµР·_РїРѕРёСЃРє_РєРѕРјР°РЅРґ",
                    )
                ),
                migration_status=_safe_text(_row_value(row, "статус_миграции", "СЃС‚Р°С‚СѓСЃ_РјРёРіСЂР°С†РёРё")),
            )
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def load_keyboard_matrix() -> tuple[KeyboardMatrixEntry, ...]:
    entries: list[KeyboardMatrixEntry] = []
    for row in _load_csv_rows(KEYBOARD_MATRIX_PATH):
        entries.append(
            KeyboardMatrixEntry(
                kind=_safe_text(_row_value(row, "тип", "С‚РёРї")),
                order=int(_safe_float(_row_value(row, "порядок", "РїРѕСЂСЏРґРѕРє")) or 0)
                if _safe_float(_row_value(row, "порядок", "РїРѕСЂСЏРґРѕРє")) is not None
                else None,
                value=_safe_text(_row_value(row, "значение", "Р·РЅР°С‡РµРЅРёРµ")),
                keys=_safe_text(_row_value(row, "клавиши", "РєР»Р°РІРёС€Рё")),
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
            title=_safe_text(_row_value(row, "название", "РЅР°Р·РІР°РЅРёРµ")),
            border=_safe_text(_row_value(row, "рамка")),
            background=_safe_text(_row_value(row, "фон")),
            text=_safe_text(_row_value(row, "текст")),
        )
        if entry.state_id:
            entries[entry.state_id] = entry
    return entries


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
            mapping[entry.value] = entry.keys
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
