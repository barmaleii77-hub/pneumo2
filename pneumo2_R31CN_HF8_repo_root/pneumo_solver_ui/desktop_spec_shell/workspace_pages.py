from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
import sys
import copy
from typing import Any, Callable, Iterable, Mapping, Sequence

from PySide6 import QtCore, QtGui, QtWidgets

from pneumo_solver_ui.desktop_input_model import (
    DESKTOP_QUICK_PRESET_OPTIONS,
    DESKTOP_INPUT_SECTIONS,
    DesktopInputFieldSpec,
    apply_desktop_quick_preset,
    build_desktop_profile_diff,
    build_desktop_section_change_cards,
    build_desktop_section_issue_cards,
    build_desktop_section_summary_cards,
    describe_desktop_field_source_state,
    describe_desktop_inputs_snapshot_state,
    desktop_profile_display_name,
    desktop_section_status_label,
    desktop_snapshot_display_name,
    default_base_json_path,
    default_working_copy_path,
    field_spec_map,
    find_desktop_field_matches,
    list_desktop_profile_paths,
    list_desktop_snapshot_paths,
    load_base_defaults,
    load_base_with_defaults,
    load_desktop_profile,
    load_desktop_snapshot,
    quick_preset_description,
    quick_preset_label,
    save_base_payload,
    save_desktop_inputs_snapshot,
    save_desktop_profile,
    save_desktop_snapshot,
)
from pneumo_solver_ui.desktop_ring_editor_model import (
    CLOSURE_POLICIES,
    EVENT_KINDS,
    EVENT_SIDES,
    GD_PICKS,
    ISO_CLASSES,
    PASSAGE_MODES,
    ROAD_MODES,
    TURN_DIRECTIONS,
    build_blank_event,
    build_blank_segment,
    build_ring_preset,
    build_segment_flow_rows,
    build_segment_preset,
    clone_segment,
    ensure_road_defaults,
    get_segments,
    list_ring_preset_names,
    list_segment_preset_names,
    normalize_spec,
    safe_float,
    safe_int,
    save_spec_to_path,
)
from pneumo_solver_ui.desktop_ring_editor_runtime import (
    build_ring_editor_diagnostics,
    export_ring_scenario_bundle,
)
from pneumo_solver_ui.desktop_results_runtime import DesktopResultsRuntime
from pneumo_solver_ui.desktop_engineering_analysis_runtime import DesktopEngineeringAnalysisRuntime
from pneumo_solver_ui.desktop_suite_runtime import (
    build_desktop_suite_snapshot_context,
    write_desktop_suite_handoff_snapshot,
)
from pneumo_solver_ui.desktop_suite_snapshot import load_suite_rows
from pneumo_solver_ui.desktop_optimizer_runtime import DesktopOptimizerRuntime
from pneumo_solver_ui.desktop_geometry_reference_runtime import DesktopGeometryReferenceRuntime
from pneumo_solver_ui.desktop_run_setup_model import (
    DESKTOP_RUN_CACHE_POLICY_OPTIONS,
    DESKTOP_RUN_PROFILE_OPTIONS,
    DESKTOP_RUN_RUNTIME_POLICY_OPTIONS,
    DesktopRunSetupSnapshot,
    apply_run_setup_profile,
    cache_policy_description,
    cache_policy_label,
    describe_plain_launch_availability,
    describe_run_launch_target,
    describe_run_setup_snapshot,
    recommended_run_launch_action,
    run_profile_description,
    run_profile_label,
    runtime_policy_description,
    runtime_policy_label,
)
from pneumo_solver_ui.desktop_baseline_run_runtime import (
    append_baseline_run_execution_log,
    complete_baseline_run_launch_request,
    mark_baseline_run_launch_request_started,
    prepare_baseline_run_launch_request,
    read_baseline_run_launch_request,
)
from pneumo_solver_ui.optimization_baseline_source import (
    apply_baseline_center_action,
    baseline_suite_handoff_launch_gate,
    build_baseline_center_surface,
)

from .catalogs import workspace_elements_by_owner
from .contracts import DesktopShellCommandSpec, DesktopWorkspaceSpec
from .workspace_runtime import (
    WorkspaceSummaryFact,
    WorkspaceSummaryState,
    build_baseline_workspace_summary,
    build_diagnostics_workspace_summary,
    build_input_workspace_summary,
    build_optimization_workspace_summary,
    build_results_workspace_summary,
    build_ring_workspace_summary,
    _load_ring_spec_for_workspace,
    _operator_result_text,
)
from .v19_guidance_widgets import build_v19_action_feedback_box
from .v16_guidance_widgets import build_v16_visibility_priority_box


def _clear_layout(layout: QtWidgets.QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


def _table_snapshot_rows(
    table: QtWidgets.QTableWidget,
    *,
    max_rows: int = 16,
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    for row_index in range(min(table.rowCount(), max_rows)):
        first = table.item(row_index, 0)
        label = " ".join((first.text() if first is not None else f"Строка {row_index + 1}").split())
        values: list[str] = []
        for column in range(1, table.columnCount()):
            item = table.item(row_index, column)
            text = " ".join((item.text() if item is not None else "").split()).strip()
            if text:
                values.append(text)
        rows.append((label, " | ".join(values) if values else "нет данных"))
    return tuple(rows)


def _value_text(value: object, *, unit: str = "", precision: int = 3, fallback: str = "нет данных") -> str:
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            return fallback
        text = f"{number:.{precision}f}".rstrip("0").rstrip(".")
        return f"{text} {unit}".strip()
    text = " ".join(str(value or "").split()).strip()
    return text if text else fallback


def _baseline_field_label(field: str) -> str:
    labels = {
        "active_baseline_hash": "Опорный прогон",
        "suite_snapshot_hash": "Снимок набора",
        "inputs_snapshot_hash": "Исходные данные",
        "ring_source_hash": "Циклический сценарий",
        "policy_mode": "Режим",
        "launch_profile": "Профиль запуска",
        "preview_dt": "Шаг предпросмотра",
        "preview_t_end": "Длительность предпросмотра",
        "run_dt": "Шаг расчёта",
        "run_t_end": "Длительность расчёта",
        "record_full": "Расширенный журнал",
        "cache_policy": "Повторное использование",
        "export_csv": "Таблицы результатов",
        "export_npz": "Файл анимации",
        "auto_check": "Проверка перед запуском",
        "write_log_file": "Журнал запуска",
        "runtime_policy": "Политика предупреждений",
    }
    return labels.get(str(field or "").strip(), str(field or "").strip())


def _baseline_field_list(fields: Iterable[str]) -> str:
    return ", ".join(_baseline_field_label(field) for field in fields if str(field or "").strip())


def _baseline_action_label(action: str) -> str:
    labels = {
        "review": "Просмотреть",
        "adopt": "Принять",
        "restore": "Восстановить",
    }
    return labels.get(str(action or "").strip(), "Просмотреть")


def _baseline_state_label(state: str) -> str:
    labels = {
        "active": "уже активен",
        "applied": "применено",
        "blocked": "заблокировано",
        "cancelled": "отменено",
        "current": "актуален",
        "historical_mismatch": "другой набор данных",
        "historical_same_context": "тот же набор данных",
        "invalid": "требует проверки",
        "missing": "не найден",
        "review_only": "просмотр выполнен",
        "stale": "устарел",
        "unknown": "нет данных",
    }
    text = str(state or "").strip()
    return labels.get(text, "нет данных" if not text else "требуется проверка")


def _baseline_policy_label(policy_mode: str) -> str:
    labels = {
        "restore_only": "только восстановление",
        "review_adopt": "просмотр и принятие",
    }
    text = str(policy_mode or "").strip()
    return labels.get(text, "не задан" if not text else "особый режим")


def _baseline_reason_label(reason: str) -> str:
    labels = {
        "active_baseline_hash_mismatch": "не совпала контрольная сумма",
        "inputs_snapshot_hash_changed": "изменились исходные данные",
        "missing_active_baseline_contract": "активный опорный прогон не найден",
        "ring_source_hash_changed": "изменился циклический сценарий",
        "suite_snapshot_hash_changed": "изменился набор испытаний",
        "suite_snapshot_not_validated": "снимок набора не проверен",
        "unsupported_active_baseline_schema": "неподдерживаемый формат записи",
        "wrong_baseline_handoff_id": "запись относится к другой передаче",
    }
    text = str(reason or "").strip()
    return labels.get(text, "требуется повторная проверка")


def _baseline_launch_gate_text(raw: object) -> str:
    text = " ".join(str(raw or "").split()).strip()
    replacements = (
        ("включено=", "включено "),
        ("не хватает ссылок=", "не хватает ссылок "),
        ("ошибок владения данными=", "ошибок владения данными "),
        ("отклонено изменений=", "отклонено изменений "),
        ("с контролем=", "с контролем "),
        ("baseline_launch_allowed=", "запуск опорного прогона "),
        ("handoff_ready=", "передача набора "),
        ("True", "да"),
        ("False", "нет"),
        ("true", "да"),
        ("false", "нет"),
        ("missing_validated_suite_snapshot", "снимок набора не найден"),
        ("unsupported_validated_suite_snapshot_schema", "неподдерживаемый формат снимка набора"),
        ("suite_validation_failed", "набор испытаний не прошёл проверку"),
        ("missing_upstream_handoff_refs", "не хватает ссылок на исходные данные или сценарий"),
        ("rejected_suite_overrides", "часть изменений набора отклонена"),
        ("snapshot", "снимок"),
        ("handoff", "передача"),
        ("baseline", "опорный прогон"),
        ("suite", "набор испытаний"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _workspace_owner_text(raw: str) -> str:
    labels = {
        "WS-PROJECT": "Панель проекта",
        "WS-INPUTS": "Исходные данные",
        "WS-RING": "Редактор циклического сценария",
        "WS-SUITE": "Набор испытаний",
        "WS-BASELINE": "Базовый прогон",
        "WS-OPTIMIZATION": "Оптимизация",
        "WS-ANALYSIS": "Анализ результатов",
        "WS-ANIMATOR": "Анимация",
        "WS-DIAGNOSTICS": "Проверка проекта",
        "WS-SETTINGS": "Параметры приложения",
        "WS-TOOLS": "Инструменты",
    }
    parts = [
        labels.get(part.strip(), part.strip())
        for part in str(raw or "").split(";")
        if part.strip()
    ]
    return "; ".join(parts) if parts else "нет данных"


def _launch_surface_text(raw: str) -> str:
    labels = {
        "workspace": "встроенное окно",
        "legacy_bridge": "сервисный fallback",
        "external_window": "вторичная графическая проверка",
        "tooling": "инструментальное окно",
    }
    return labels.get(str(raw or "").strip(), "обычное окно")


def _operator_catalog_text(raw: str) -> str:
    text = " ".join(str(raw or "").split()).strip()
    replacements = (
        ("Карточка контракта baseline", "Карточка опорного прогона"),
        ("карточка контракта baseline", "карточка опорного прогона"),
        ("Карточка предупреждений контракта", "Карточка предупреждений условий расчёта"),
        ("карточка предупреждений контракта", "карточка предупреждений условий расчёта"),
        ("Индикатор контракта целей и ограничений", "Индикатор целей и ограничений"),
        ("индикатор контракта целей и ограничений", "индикатор целей и ограничений"),
        ("Показывает режим:", "Показывает достоверность отображения:"),
        ("показывает режим:", "показывает достоверность отображения:"),
        ("suite", "набор испытаний"),
        ("Suite", "Набор испытаний"),
        ("objective stack", "цели расчёта"),
        ("Objective stack", "Цели расчёта"),
        ("baseline source", "источник опорного прогона"),
        ("objective contract", "цели расчёта"),
        ("hard gate", "обязательное условие"),
        ("Hard gate", "Обязательное условие"),
        ("active mode", "активный режим"),
        ("Active mode", "Активный режим"),
        ("estimated stage budgets", "оценка длительности этапов"),
        ("Estimated stage budgets", "Оценка длительности этапов"),
        ("Лидерборд запусков", "Таблица запусков"),
        ("лидерборд запусков", "таблица запусков"),
        ("KPI", "показателями"),
        ("Compare и validation", "Окно сравнения и проверка"),
        ("validation", "проверка"),
        ("bundle_ready=False", "архив не готов"),
        ("bundle_ready=True", "архив готов"),
        ("bundle_ready", "архив готов"),
        ("legacy workspace surface", "отдельное рабочее окно"),
        ("Legacy workspace surface", "Отдельное рабочее окно"),
        ("workspace", "рабочее окно"),
        ("Workspace", "Рабочее окно"),
        ("surface", "окно"),
        ("Surface", "Окно"),
        ("bundle", "архив проекта"),
        ("Bundle", "Архив проекта"),
        ("legacy", "отдельное"),
        ("Legacy", "Отдельное"),
        ("run-ов", "запусков"),
        ("baseline", "опорный прогон"),
        ("contract", "условия"),
        ("Contract", "Условия"),
        ("контрактов", "условий"),
        ("Контрактов", "Условий"),
        ("контракта", "условий"),
        ("Контракта", "Условий"),
        ("контракт", "условия"),
        ("Контракт", "Условия"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _suite_row_enabled(row: dict[str, Any]) -> bool:
    value = row.get("включен", row.get("enabled", True))
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().casefold() not in {"0", "false", "no", "off", "нет"}
    return bool(value)


def _suite_visible_name(row: dict[str, Any]) -> str:
    raw = str(row.get("имя") or row.get("name") or row.get("id") or "без названия")
    return " ".join(raw.replace("_", " ").split())


def _suite_visible_type(row: dict[str, Any]) -> str:
    raw = str(row.get("тип") or row.get("type") or "").strip()
    labels = {
        "maneuver_csv": "манёвр из файла",
        "road_profile_csv": "профиль дороги",
        "worldroad": "дорожная модель",
        "инерция_крен": "крен при боковом ускорении",
        "инерция_тангаж": "тангаж при продольном ускорении",
        "микро_разнофаза": "микроход в противофазе",
        "микро_разнофаза_перед_зад": "передняя и задняя ось в противофазе",
        "микро_разнофаза_диагональ": "диагональный микроход",
        "микро_синфаза": "микроход в синфазе",
        "кочка_одно_колесо": "одиночная кочка под колесом",
    }
    if raw in labels:
        return labels[raw]
    return " ".join(raw.replace("_", " ").split()) or "обычное испытание"


def _suite_visible_stage(row: dict[str, Any]) -> str:
    value = row.get("стадия", row.get("stage", ""))
    text = str(value).strip()
    if text in {"", "0", "0.0"}:
        return "сразу"
    return f"после шага {text}"


def _suite_number_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key, "")
    if value in ("", None):
        return "не задано"
    try:
        return f"{float(value):g}"
    except Exception:
        return str(value)


def _suite_scenario_refs_text(row: dict[str, Any]) -> str:
    refs: list[str] = []
    if str(row.get("scenario_json") or "").strip():
        refs.append("циклический сценарий")
    if str(row.get("road_csv") or "").strip():
        refs.append("дорога")
    if str(row.get("axay_csv") or "").strip():
        refs.append("манёвр")
    return ", ".join(refs) if refs else "не требуется"


def _suite_validation_message(context: dict[str, Any]) -> str:
    snapshot = dict(context.get("snapshot") or {})
    validation = dict(snapshot.get("validation") or {})
    preview = dict(snapshot.get("preview") or {})
    enabled_count = int(preview.get("enabled_count", 0) or 0)
    missing_refs = int(validation.get("blocking_missing_ref_count", 0) or 0)
    upstream_errors = int(validation.get("upstream_ref_error_count", 0) or 0)
    ownership_errors = int(validation.get("ownership_violation_count", 0) or 0)
    if bool(validation.get("ok", False)):
        return "Набор проверен и готов для базового прогона."
    if enabled_count <= 0:
        return "Включите хотя бы одно испытание перед базовым прогоном."
    if upstream_errors:
        return "Сначала сохраните исходные данные проекта, затем проверьте набор ещё раз."
    if missing_refs:
        return "Есть испытания, где не найден файл сценария, дороги или манёвра."
    if ownership_errors:
        return "В набор попали параметры, которые должны задаваться в исходных данных или сценарии."
    return "Набор требует повторной проверки перед базовым прогоном."


class RuntimeWorkspacePage(QtWidgets.QWidget):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        action_commands: Iterable[DesktopShellCommandSpec],
        on_command: Callable[[str], None],
        summary_builder: Callable[[], WorkspaceSummaryState],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.action_commands = tuple(action_commands)
        self.on_command = on_command
        self.summary_builder = summary_builder

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        scroll.setWidget(inner)
        layout = QtWidgets.QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QtWidgets.QLabel(workspace.title)
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 5)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        summary = QtWidgets.QLabel(workspace.summary)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        details = QtWidgets.QLabel(workspace.details)
        details.setWordWrap(True)
        details.setStyleSheet("color: #405060;")
        layout.addWidget(details)

        self.status_box = QtWidgets.QGroupBox("Текущее состояние")
        status_layout = QtWidgets.QVBoxLayout(self.status_box)
        self.headline_label = QtWidgets.QLabel("")
        headline_font = self.headline_label.font()
        headline_font.setBold(True)
        headline_font.setPointSize(headline_font.pointSize() + 1)
        self.headline_label.setFont(headline_font)
        self.headline_label.setWordWrap(True)
        self.detail_label = QtWidgets.QLabel("")
        self.detail_label.setWordWrap(True)
        status_layout.addWidget(self.headline_label)
        status_layout.addWidget(self.detail_label)
        layout.addWidget(self.status_box)

        self.facts_box = QtWidgets.QGroupBox("Ключевые сигналы")
        self.facts_layout = QtWidgets.QVBoxLayout(self.facts_box)
        layout.addWidget(self.facts_box)

        self.evidence_box = QtWidgets.QGroupBox("Происхождение данных")
        self.evidence_layout = QtWidgets.QVBoxLayout(self.evidence_box)
        layout.addWidget(self.evidence_box)

        v16_box = build_v16_visibility_priority_box(workspace)
        if v16_box is not None:
            layout.addWidget(v16_box)

        v19_box = build_v19_action_feedback_box(workspace)
        if v19_box is not None:
            layout.addWidget(v19_box)

        actions_box = QtWidgets.QGroupBox("Быстрые действия")
        actions_layout = QtWidgets.QVBoxLayout(actions_box)
        refresh_button = QtWidgets.QPushButton("Обновить сводку")
        refresh_button.clicked.connect(self.refresh_view)
        actions_layout.addWidget(refresh_button)
        for command in self.action_commands:
            button = QtWidgets.QPushButton(command.title)
            button.setToolTip(command.summary)
            button.clicked.connect(
                lambda _checked=False, cid=command.command_id: self.on_command(cid)
            )
            actions_layout.addWidget(button)
        layout.addWidget(actions_box)
        self._build_extra_controls(layout)
        layout.addStretch(1)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh_view()

    def _build_extra_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        del layout

    def _render_fact(self, fact: WorkspaceSummaryFact) -> None:
        box = QtWidgets.QFrame()
        box.setFrameShape(QtWidgets.QFrame.StyledPanel)
        box_layout = QtWidgets.QVBoxLayout(box)
        box_layout.setContentsMargins(10, 8, 10, 8)
        box_layout.setSpacing(4)

        label = QtWidgets.QLabel(fact.label)
        label_font = label.font()
        label_font.setBold(True)
        label.setFont(label_font)
        box_layout.addWidget(label)

        value = QtWidgets.QLabel(fact.value)
        value.setWordWrap(True)
        box_layout.addWidget(value)

        if fact.detail:
            detail = QtWidgets.QLabel(fact.detail)
            detail.setWordWrap(True)
            detail.setStyleSheet("color: #576574;")
            box_layout.addWidget(detail)
        self.facts_layout.addWidget(box)

    def refresh_view(self) -> None:
        summary = self.summary_builder()
        self.headline_label.setText(summary.headline)
        self.detail_label.setText(summary.detail)

        _clear_layout(self.facts_layout)
        for fact in summary.facts:
            self._render_fact(fact)
        if not summary.facts:
            self.facts_layout.addWidget(QtWidgets.QLabel("Сводка пока не заполнена."))

        _clear_layout(self.evidence_layout)
        evidence_lines = summary.evidence_lines or ("Свежие сведения о происхождении данных пока не найдены.",)
        for line in evidence_lines:
            label = QtWidgets.QLabel(f"• {line}")
            label.setWordWrap(True)
            self.evidence_layout.addWidget(label)


class ControlHubWorkspacePage(QtWidgets.QWidget):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        action_commands: Iterable[DesktopShellCommandSpec],
        on_command: Callable[[str], None],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.action_commands = tuple(action_commands)
        self.on_command = on_command

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        scroll.setWidget(inner)
        layout = QtWidgets.QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QtWidgets.QLabel(workspace.title)
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 5)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        summary = QtWidgets.QLabel(workspace.summary)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        details = QtWidgets.QLabel(workspace.details)
        details.setWordWrap(True)
        details.setStyleSheet("color: #405060;")
        layout.addWidget(details)

        contract_box = QtWidgets.QGroupBox("Смысл и правила окна")
        contract_layout = QtWidgets.QFormLayout(contract_box)
        contract_layout.addRow("Источник данных", QtWidgets.QLabel(workspace.source_of_truth))
        contract_layout.addRow("Связанная область", QtWidgets.QLabel(_workspace_owner_text(workspace.workspace_owner)))
        contract_layout.addRow("Основная область", QtWidgets.QLabel(workspace.title))
        contract_layout.addRow("Следующий шаг", QtWidgets.QLabel(workspace.next_step))
        contract_layout.addRow("Обязательное условие", QtWidgets.QLabel(workspace.hard_gate))
        layout.addWidget(contract_box)

        v16_box = build_v16_visibility_priority_box(workspace)
        if v16_box is not None:
            layout.addWidget(v16_box)

        v19_box = build_v19_action_feedback_box(workspace)
        if v19_box is not None:
            layout.addWidget(v19_box)

        self.surface_box = QtWidgets.QGroupBox("Ключевые элементы рабочего шага")
        self.surface_layout = QtWidgets.QVBoxLayout(self.surface_box)
        layout.addWidget(self.surface_box)

        self.actions_box = QtWidgets.QGroupBox("Основные действия")
        self.actions_layout = QtWidgets.QVBoxLayout(self.actions_box)
        layout.addWidget(self.actions_box)

        evidence_box = QtWidgets.QGroupBox("Графика и происхождение данных")
        evidence_layout = QtWidgets.QVBoxLayout(evidence_box)
        graphics = QtWidgets.QLabel(workspace.graphics_policy)
        graphics.setWordWrap(True)
        evidence_layout.addWidget(graphics)
        units = QtWidgets.QLabel(workspace.units_policy)
        units.setWordWrap(True)
        units.setStyleSheet("color: #576574;")
        evidence_layout.addWidget(units)
        layout.addWidget(evidence_box)
        layout.addStretch(1)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh_view()

    def _workspace_elements(self) -> tuple[str, ...]:
        owners = [
            item.strip()
            for item in (
                *str(self.workspace.workspace_owner or "").split(";"),
                *self.workspace.catalog_owner_aliases,
            )
        ]
        labels: list[str] = []
        for owner in owners:
            if not owner:
                continue
            for entry in workspace_elements_by_owner().get(owner, ())[:10]:
                text = _operator_catalog_text(entry.title)
                if entry.purpose:
                    text = f"{text}: {_operator_catalog_text(entry.purpose)}"
                labels.append(text)
        seen: set[str] = set()
        ordered: list[str] = []
        for label in labels:
            key = label.casefold()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(label)
        return tuple(ordered[:8])

    def refresh_view(self) -> None:
        _clear_layout(self.surface_layout)
        _clear_layout(self.actions_layout)

        elements = self._workspace_elements()
        if not elements:
            self.surface_layout.addWidget(
                QtWidgets.QLabel("Каталог элементов для этого рабочего шага пока не привязан к конкретным элементам окна.")
            )
        for line in elements:
            label = QtWidgets.QLabel(f"• {line}")
            label.setWordWrap(True)
            self.surface_layout.addWidget(label)

        if not self.action_commands:
            self.actions_layout.addWidget(QtWidgets.QLabel("Действия для этого рабочего шага пока не зарегистрированы."))
            return

        for command in self.action_commands:
            button = QtWidgets.QPushButton(command.title)
            button.setToolTip(command.summary)
            if command.automation_id:
                button.setObjectName(command.automation_id)
                button.setAccessibleName(command.title)
            if command.hotkey:
                try:
                    button.setShortcut(command.hotkey)
                except Exception:
                    pass
            button.clicked.connect(
                lambda _checked=False, cid=command.command_id: self.on_command(cid)
            )
            self.actions_layout.addWidget(button)

            meta = QtWidgets.QLabel(
                "\n".join(
                    line
                    for line in (
                        command.summary,
                        f"Расположение: {command.route_label}",
                        f"Открытие: {_launch_surface_text(command.launch_surface)}",
                    )
                    if line
                )
            )
            meta.setWordWrap(True)
            meta.setStyleSheet("color: #576574;")
            self.actions_layout.addWidget(meta)


class ToolsWorkspacePage(QtWidgets.QWidget):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        action_commands: Iterable[DesktopShellCommandSpec],
        on_command: Callable[[str], None],
        *,
        repo_root: Path,
        python_executable: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("WS-TOOLS-HOSTED-PAGE")
        self.workspace = workspace
        self.action_commands = tuple(action_commands)
        self.on_command = on_command
        self.repo_root = Path(repo_root)
        self.python_executable = python_executable or sys.executable
        self.geometry_runtime = DesktopGeometryReferenceRuntime(ui_root=self.repo_root / "pneumo_solver_ui")
        self.autotest_process: QtCore.QProcess | None = None

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        scroll.setWidget(inner)
        layout = QtWidgets.QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QtWidgets.QLabel(workspace.title)
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 5)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        summary = QtWidgets.QLabel(
            "Сервисные функции остаются внутри рабочего места: справочник геометрии и проверки проекта "
            "открываются как виджеты, без отдельного окна-хаба."
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        self._build_geometry_reference_widget(layout)
        self._build_autotest_widget(layout)
        layout.addStretch(1)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh_view()

    def _build_geometry_reference_widget(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.geometry_box = QtWidgets.QGroupBox("Справочник геометрии")
        self.geometry_box.setObjectName("TOOLS-GEOMETRY-REFERENCE")
        box_layout = QtWidgets.QVBoxLayout(self.geometry_box)
        self.geometry_source_label = QtWidgets.QLabel("")
        self.geometry_source_label.setWordWrap(True)
        self.geometry_road_label = QtWidgets.QLabel("")
        self.geometry_road_label.setWordWrap(True)
        box_layout.addWidget(self.geometry_source_label)
        box_layout.addWidget(self.geometry_road_label)

        self.geometry_cylinder_table = QtWidgets.QTableWidget(0, 6)
        self.geometry_cylinder_table.setObjectName("TOOLS-GEOMETRY-CYLINDERS")
        self.geometry_cylinder_table.setHorizontalHeaderLabels(
            ("Семейство", "Поршень, мм", "Шток, мм", "Ход, мм", "Площадь поршня, см2", "Кольцевая, см2")
        )
        box_layout.addWidget(self.geometry_cylinder_table)

        self.geometry_fit_table = QtWidgets.QTableWidget(0, 6)
        self.geometry_fit_table.setObjectName("TOOLS-GEOMETRY-FIT")
        self.geometry_fit_table.setHorizontalHeaderLabels(
            ("Семейство", "Статус", "Использование хода", "Текущий ход", "Рекомендация", "Что сделать")
        )
        box_layout.addWidget(self.geometry_fit_table)

        self.geometry_spring_table = QtWidgets.QTableWidget(0, 6)
        self.geometry_spring_table.setObjectName("TOOLS-GEOMETRY-SPRINGS")
        self.geometry_spring_table.setHorizontalHeaderLabels(
            ("Семейство", "Проволока, мм", "Средний диаметр, мм", "Жёсткость, Н/мм", "Свободная длина, мм", "Запас до смыкания, мм")
        )
        box_layout.addWidget(self.geometry_spring_table)

        button_row = QtWidgets.QHBoxLayout()
        self.geometry_refresh_button = QtWidgets.QPushButton("Обновить справочник")
        self.geometry_refresh_button.setObjectName("TOOLS-BTN-GEOMETRY-REFRESH")
        self.geometry_refresh_button.clicked.connect(self.refresh_geometry_reference)
        button_row.addWidget(self.geometry_refresh_button)
        button_row.addStretch(1)
        box_layout.addLayout(button_row)
        layout.addWidget(self.geometry_box)

    def _build_autotest_widget(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.autotest_box = QtWidgets.QGroupBox("Проверки проекта")
        self.autotest_box.setObjectName("TOOLS-AUTOTEST")
        box_layout = QtWidgets.QVBoxLayout(self.autotest_box)
        intro = QtWidgets.QLabel(
            "Запуск проверок выполняется внутри рабочего места. Результаты пишутся в папку autotest_runs, "
            "а ход выполнения виден ниже."
        )
        intro.setWordWrap(True)
        box_layout.addWidget(intro)

        controls = QtWidgets.QHBoxLayout()
        self.autotest_level_combo = QtWidgets.QComboBox()
        self.autotest_level_combo.setObjectName("TOOLS-AUTOTEST-LEVEL")
        self.autotest_level_combo.addItem("Быстрая проверка", "quick")
        self.autotest_level_combo.addItem("Стандартная проверка", "standard")
        self.autotest_level_combo.addItem("Полная проверка", "full")
        controls.addWidget(self.autotest_level_combo)
        self.autotest_run_button = QtWidgets.QPushButton("Запустить проверки")
        self.autotest_run_button.setObjectName("TOOLS-BTN-AUTOTEST-RUN")
        self.autotest_run_button.clicked.connect(self.run_autotest)
        controls.addWidget(self.autotest_run_button)
        self.autotest_stop_button = QtWidgets.QPushButton("Остановить")
        self.autotest_stop_button.setObjectName("TOOLS-BTN-AUTOTEST-STOP")
        self.autotest_stop_button.clicked.connect(self.stop_autotest)
        controls.addWidget(self.autotest_stop_button)
        self.autotest_open_dir_button = QtWidgets.QPushButton("Открыть папку проверок")
        self.autotest_open_dir_button.setObjectName("TOOLS-BTN-AUTOTEST-OPEN-DIR")
        self.autotest_open_dir_button.clicked.connect(self.open_autotest_runs_dir)
        controls.addWidget(self.autotest_open_dir_button)
        controls.addStretch(1)
        box_layout.addLayout(controls)

        self.autotest_status_label = QtWidgets.QLabel("Проверки не запускались в этой сессии.")
        self.autotest_status_label.setWordWrap(True)
        box_layout.addWidget(self.autotest_status_label)
        self.autotest_log_view = QtWidgets.QPlainTextEdit()
        self.autotest_log_view.setObjectName("TOOLS-AUTOTEST-LOG")
        self.autotest_log_view.setReadOnly(True)
        self.autotest_log_view.setMinimumHeight(220)
        box_layout.addWidget(self.autotest_log_view)
        layout.addWidget(self.autotest_box)

    def _fill_table(self, table: QtWidgets.QTableWidget, rows: Iterable[Iterable[object]]) -> None:
        materialized = [tuple(row) for row in rows]
        table.setRowCount(len(materialized))
        for row_index, row in enumerate(materialized):
            for column_index, value in enumerate(row):
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                table.setItem(row_index, column_index, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def refresh_geometry_reference(self) -> None:
        try:
            source = self.geometry_runtime.describe_base_source()
            cylinders = self.geometry_runtime.current_cylinder_rows()
            fit_rows = self.geometry_runtime.component_fit_rows()
            spring_snapshot = self.geometry_runtime.current_spring_snapshot()
            road = self.geometry_runtime.road_width_reference()
        except Exception as exc:
            self.geometry_source_label.setText(f"Справочник временно недоступен: {exc}")
            self._fill_table(self.geometry_cylinder_table, ())
            self._fill_table(self.geometry_fit_table, ())
            self._fill_table(self.geometry_spring_table, ())
            return

        self.geometry_source_label.setText(f"Источник данных: {source}")
        self.geometry_road_label.setText(
            f"{road.label}: {_value_text(road.effective_road_width_m, unit=road.unit_label)}. "
            f"Источник: {road.source}. {road.explanation}"
        )
        self._fill_table(
            self.geometry_cylinder_table,
            (
                (
                    row.family,
                    _value_text(row.bore_mm),
                    _value_text(row.rod_mm),
                    _value_text(row.stroke_mm),
                    _value_text(row.cap_area_cm2),
                    _value_text(row.annulus_area_cm2),
                )
                for row in cylinders
            ),
        )
        self._fill_table(
            self.geometry_fit_table,
            (
                (
                    row.family,
                    row.status,
                    _value_text(row.stroke_usage_pct, unit="%"),
                    _value_text(row.current_stroke_mm, unit="мм"),
                    f"{row.recommended_catalog_label}, {_value_text(row.recommended_stroke_mm, unit='мм')}",
                    row.action_summary,
                )
                for row in fit_rows
            ),
        )
        self._fill_table(
            self.geometry_spring_table,
            (
                (
                    row.family,
                    _value_text(row.wire_mm),
                    _value_text(row.mean_diameter_mm),
                    _value_text(row.rate_N_per_mm),
                    _value_text(row.free_length_mm),
                    _value_text(row.bind_travel_margin_mm),
                )
                for row in spring_snapshot.families
            ),
        )

    def refresh_autotest_state(self) -> None:
        busy = self.autotest_process is not None and self.autotest_process.state() != QtCore.QProcess.NotRunning
        self.autotest_run_button.setEnabled(not busy)
        self.autotest_stop_button.setEnabled(busy)

    def _autotest_runs_dir(self) -> Path:
        return self.repo_root / "pneumo_solver_ui" / "autotest_runs"

    def run_autotest(self) -> None:
        if self.autotest_process is not None and self.autotest_process.state() != QtCore.QProcess.NotRunning:
            self.autotest_status_label.setText("Проверки уже выполняются.")
            return
        level = str(self.autotest_level_combo.currentData() or "quick")
        self.autotest_log_view.clear()
        self.autotest_status_label.setText(f"Запущена проверка: {level}.")
        process = QtCore.QProcess(self)
        process.setProgram(str(self.python_executable))
        process.setArguments(["-m", "pneumo_solver_ui.tools.run_autotest", "--level", level])
        process.setWorkingDirectory(str(self.repo_root))
        env = QtCore.QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUTF8", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(env)
        process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_autotest_output)
        process.finished.connect(self._on_autotest_finished)
        process.errorOccurred.connect(self._on_autotest_error)
        self.autotest_process = process
        self.refresh_autotest_state()
        process.start()

    def _read_autotest_output(self) -> None:
        process = self.autotest_process
        if process is None:
            return
        data = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.autotest_log_view.appendPlainText(data.rstrip())

    def _on_autotest_finished(self, exit_code: int, _exit_status: QtCore.QProcess.ExitStatus) -> None:
        self._read_autotest_output()
        self.autotest_status_label.setText(
            "Проверки завершены успешно." if int(exit_code) == 0 else f"Проверки завершены с кодом {int(exit_code)}."
        )
        self.refresh_autotest_state()

    def _on_autotest_error(self, error: QtCore.QProcess.ProcessError) -> None:
        self.autotest_status_label.setText(f"Не удалось выполнить проверки: {error.name}.")
        self.refresh_autotest_state()

    def stop_autotest(self) -> None:
        process = self.autotest_process
        if process is None or process.state() == QtCore.QProcess.NotRunning:
            return
        process.terminate()
        QtCore.QTimer.singleShot(1500, self._kill_autotest_if_running)
        self.autotest_status_label.setText("Остановка проверок запрошена.")

    def _kill_autotest_if_running(self) -> None:
        process = self.autotest_process
        if process is not None and process.state() != QtCore.QProcess.NotRunning:
            process.kill()

    def open_autotest_runs_dir(self) -> None:
        path = self._autotest_runs_dir()
        path.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def refresh_view(self) -> None:
        self.refresh_geometry_reference()
        self.refresh_autotest_state()

    def handle_command(self, command_id: str) -> object:
        if command_id == "tools.geometry_reference.open":
            self.refresh_geometry_reference()
            self.geometry_box.setFocus(QtCore.Qt.OtherFocusReason)
            return
        if command_id == "tools.autotest.open":
            self.run_autotest()


class SuiteWorkspacePage(QtWidgets.QWidget):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        action_commands: Iterable[DesktopShellCommandSpec],
        on_command: Callable[[str], None],
        *,
        repo_root: Path,
        python_executable: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("WS-SUITE-HOSTED-PAGE")
        self.workspace = workspace
        self.action_commands = tuple(action_commands)
        self.on_command = on_command
        self.repo_root = Path(repo_root)
        self.python_executable = python_executable or sys.executable
        self.suite_source_path = self.repo_root / "pneumo_solver_ui" / "default_suite.json"
        self._suite_rows: list[dict[str, Any]] = []
        self._refreshing_suite_table = False
        self._last_suite_context: dict[str, Any] | None = None
        self.suite_autotest_process: QtCore.QProcess | None = None

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        scroll.setWidget(inner)
        layout = QtWidgets.QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QtWidgets.QLabel(workspace.title)
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 5)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        summary = QtWidgets.QLabel(
            "Здесь выбираются испытания для следующего расчёта и проверяется связь "
            "с исходными данными и циклическим сценарием."
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        state_box = QtWidgets.QGroupBox("Готовность набора")
        state_layout = QtWidgets.QVBoxLayout(state_box)
        self.summary_label = QtWidgets.QLabel("")
        self.summary_label.setWordWrap(True)
        self.ring_link_label = QtWidgets.QLabel("")
        self.ring_link_label.setWordWrap(True)
        self.validation_label = QtWidgets.QLabel("")
        self.validation_label.setObjectName("TS-VALIDATION-SUMMARY")
        self.validation_label.setWordWrap(True)
        self.snapshot_label = QtWidgets.QLabel("Снимок набора ещё не сохранён для базового прогона.")
        self.snapshot_label.setWordWrap(True)
        state_layout.addWidget(self.summary_label)
        state_layout.addWidget(self.ring_link_label)
        state_layout.addWidget(self.validation_label)
        state_layout.addWidget(self.snapshot_label)
        layout.addWidget(state_box)

        table_box = QtWidgets.QGroupBox("Испытания в наборе")
        table_layout = QtWidgets.QVBoxLayout(table_box)
        filter_row = QtWidgets.QHBoxLayout()
        self.suite_filter_edit = QtWidgets.QLineEdit()
        self.suite_filter_edit.setObjectName("TS-FILTER")
        self.suite_filter_edit.setPlaceholderText("Найти испытание, тип или связанный файл")
        self.suite_filter_edit.textChanged.connect(lambda _text: self._apply_suite_filter())
        filter_row.addWidget(self.suite_filter_edit, 1)
        self.suite_filter_preset_combo = QtWidgets.QComboBox()
        self.suite_filter_preset_combo.setObjectName("TS-FILTER-PRESET")
        self.suite_filter_preset_combo.addItems(
            (
                "Все испытания",
                "Только включённые",
                "Требуют сценарий",
                "Без сценария",
            )
        )
        self.suite_filter_preset_combo.currentIndexChanged.connect(
            lambda _index: self._apply_suite_filter()
        )
        filter_row.addWidget(self.suite_filter_preset_combo)
        table_layout.addLayout(filter_row)
        self.suite_table = QtWidgets.QTableWidget(0, 7)
        self.suite_table.setObjectName("TS-TABLE")
        self.suite_table.setHorizontalHeaderLabels(
            (
                "Включено",
                "Название",
                "Тип испытания",
                "Первый вход",
                "Шаг, с",
                "Длительность, с",
                "Связанные файлы",
            )
        )
        self.suite_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.suite_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.suite_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.suite_table.verticalHeader().setVisible(False)
        self.suite_table.horizontalHeader().setStretchLastSection(True)
        self.suite_table.itemChanged.connect(self._on_suite_item_changed)
        self.suite_table.itemSelectionChanged.connect(self._on_suite_selection_changed)
        table_layout.addWidget(self.suite_table)
        layout.addWidget(table_box, 1)

        self.suite_detail_box = QtWidgets.QGroupBox("Карточка выбранного испытания")
        self.suite_detail_box.setObjectName("TS-DETAIL")
        detail_layout = QtWidgets.QVBoxLayout(self.suite_detail_box)
        self.suite_detail_label = QtWidgets.QLabel("")
        self.suite_detail_label.setObjectName("TS-DETAIL-SUMMARY")
        self.suite_detail_label.setWordWrap(True)
        detail_layout.addWidget(self.suite_detail_label)
        self.suite_detail_table = QtWidgets.QTableWidget(0, 2)
        self.suite_detail_table.setObjectName("TS-DETAIL-TABLE")
        self.suite_detail_table.setHorizontalHeaderLabels(("Поле", "Значение"))
        self.suite_detail_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.suite_detail_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.suite_detail_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.suite_detail_table.verticalHeader().setVisible(False)
        self.suite_detail_table.horizontalHeader().setStretchLastSection(True)
        detail_layout.addWidget(self.suite_detail_table)
        layout.addWidget(self.suite_detail_box)

        self._build_suite_autotest_widget(layout)

        actions_box = QtWidgets.QGroupBox("Действия")
        actions_layout = QtWidgets.QHBoxLayout(actions_box)
        self.check_button = QtWidgets.QPushButton("Проверить набор")
        self.check_button.setObjectName("TS-BTN-VALIDATE")
        self.check_button.clicked.connect(self.check_suite)
        actions_layout.addWidget(self.check_button)
        self.detail_button = QtWidgets.QPushButton("Показать карточку")
        self.detail_button.setObjectName("TS-BTN-DETAIL")
        self.detail_button.clicked.connect(lambda _checked=False: self.on_command("test.selection.show"))
        actions_layout.addWidget(self.detail_button)
        self.validation_dock_button = QtWidgets.QPushButton("Показать проверку")
        self.validation_dock_button.setObjectName("TS-BTN-VALIDATION-DOCK")
        self.validation_dock_button.clicked.connect(lambda _checked=False: self.on_command("test.validation.show"))
        actions_layout.addWidget(self.validation_dock_button)
        self.save_button = QtWidgets.QPushButton("Сохранить снимок для базового прогона")
        self.save_button.setObjectName("TS-BTN-SAVE-SNAPSHOT")
        self.save_button.clicked.connect(self.save_suite_snapshot)
        actions_layout.addWidget(self.save_button)
        self.snapshot_dock_button = QtWidgets.QPushButton("Показать снимок")
        self.snapshot_dock_button.setObjectName("TS-BTN-SNAPSHOT-DOCK")
        self.snapshot_dock_button.clicked.connect(lambda _checked=False: self.on_command("test.snapshot.show"))
        actions_layout.addWidget(self.snapshot_dock_button)
        scenario_button = QtWidgets.QPushButton("Редактировать циклический сценарий")
        scenario_button.setObjectName("TS-BTN-GO-RING")
        scenario_button.clicked.connect(
            lambda _checked=False: self.on_command("workspace.ring_editor.open")
        )
        actions_layout.addWidget(scenario_button)
        baseline_command = next(
            (command for command in self.action_commands if command.command_id == "workspace.baseline_run.open"),
            None,
        )
        if baseline_command is not None:
            baseline_button = QtWidgets.QPushButton(baseline_command.title)
            baseline_button.setObjectName("TS-BTN-RUN-BASELINE")
            baseline_button.setToolTip(baseline_command.summary)
            baseline_button.clicked.connect(
                lambda _checked=False, cid=baseline_command.command_id: self.on_command(cid)
            )
            actions_layout.addWidget(baseline_button)
        layout.addWidget(actions_box)

        v16_box = build_v16_visibility_priority_box(workspace)
        if v16_box is not None:
            layout.addWidget(v16_box)

        v19_box = build_v19_action_feedback_box(workspace)
        if v19_box is not None:
            layout.addWidget(v19_box)
        layout.addStretch(1)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh_view()

    def _build_suite_autotest_widget(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.suite_autotest_box = QtWidgets.QGroupBox("Автономная проверка набора и проекта")
        self.suite_autotest_box.setObjectName("TS-AUTOTEST")
        box_layout = QtWidgets.QVBoxLayout(self.suite_autotest_box)
        intro = QtWidgets.QLabel(
            "Проверка запускается из рабочего шага набора испытаний. Артефакты пишутся в "
            "папку автономных проверок, старое сервисное окно не открывается."
        )
        intro.setWordWrap(True)
        box_layout.addWidget(intro)

        controls = QtWidgets.QHBoxLayout()
        self.suite_autotest_level_combo = QtWidgets.QComboBox()
        self.suite_autotest_level_combo.setObjectName("TS-AUTOTEST-LEVEL")
        self.suite_autotest_level_combo.addItem("Быстрая проверка", "quick")
        self.suite_autotest_level_combo.addItem("Стандартная проверка", "standard")
        self.suite_autotest_level_combo.addItem("Полная проверка", "full")
        controls.addWidget(self.suite_autotest_level_combo)

        self.suite_autotest_run_button = QtWidgets.QPushButton("Запустить автономную проверку")
        self.suite_autotest_run_button.setObjectName("TS-BTN-AUTOTEST-RUN")
        self.suite_autotest_run_button.clicked.connect(lambda _checked=False: self.on_command("test.autotest.run"))
        controls.addWidget(self.suite_autotest_run_button)

        self.suite_autotest_stop_button = QtWidgets.QPushButton("Остановить")
        self.suite_autotest_stop_button.setObjectName("TS-BTN-AUTOTEST-STOP")
        self.suite_autotest_stop_button.clicked.connect(self.stop_suite_autotest)
        controls.addWidget(self.suite_autotest_stop_button)

        self.suite_autotest_open_dir_button = QtWidgets.QPushButton("Открыть папку проверок")
        self.suite_autotest_open_dir_button.setObjectName("TS-BTN-AUTOTEST-OPEN-DIR")
        self.suite_autotest_open_dir_button.clicked.connect(self.open_suite_autotest_runs_dir)
        controls.addWidget(self.suite_autotest_open_dir_button)
        controls.addStretch(1)
        box_layout.addLayout(controls)

        self.suite_autotest_status_label = QtWidgets.QLabel("Автономная проверка не запускалась в этой сессии.")
        self.suite_autotest_status_label.setObjectName("TS-AUTOTEST-STATUS")
        self.suite_autotest_status_label.setWordWrap(True)
        box_layout.addWidget(self.suite_autotest_status_label)

        self.suite_autotest_log_view = QtWidgets.QPlainTextEdit()
        self.suite_autotest_log_view.setObjectName("TS-AUTOTEST-LOG")
        self.suite_autotest_log_view.setReadOnly(True)
        self.suite_autotest_log_view.setMinimumHeight(180)
        box_layout.addWidget(self.suite_autotest_log_view)
        layout.addWidget(self.suite_autotest_box)

    def refresh_view(self) -> None:
        try:
            self._suite_rows = load_suite_rows(self.suite_source_path)
        except Exception:
            self._suite_rows = []
            self.validation_label.setText("Не удалось прочитать основной набор испытаний.")
        self._refreshing_suite_table = True
        try:
            self.suite_table.setRowCount(len(self._suite_rows))
            for row_index, row in enumerate(self._suite_rows):
                self._fill_table_row(row_index, row)
        finally:
            self._refreshing_suite_table = False
        self._resize_table()
        self._apply_suite_filter()
        self._update_summary_labels()
        self._refresh_suite_detail()
        self.refresh_suite_autotest_state()
        if self._suite_rows:
            self.validation_label.setText("Нажмите «Проверить набор» перед базовым прогоном.")

    def _fill_table_row(self, row_index: int, row: dict[str, Any]) -> None:
        enabled_item = QtWidgets.QTableWidgetItem("")
        enabled_item.setFlags(
            QtCore.Qt.ItemIsEnabled
            | QtCore.Qt.ItemIsSelectable
            | QtCore.Qt.ItemIsUserCheckable
        )
        enabled_item.setCheckState(QtCore.Qt.Checked if _suite_row_enabled(row) else QtCore.Qt.Unchecked)
        self.suite_table.setItem(row_index, 0, enabled_item)
        values = (
            _suite_visible_name(row),
            _suite_visible_type(row),
            _suite_visible_stage(row),
            _suite_number_text(row, "dt"),
            _suite_number_text(row, "t_end"),
            _suite_scenario_refs_text(row),
        )
        for column, value in enumerate(values, start=1):
            item = QtWidgets.QTableWidgetItem(value)
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.suite_table.setItem(row_index, column, item)

    def _resize_table(self) -> None:
        self.suite_table.resizeColumnsToContents()
        self.suite_table.setMinimumHeight(260)

    def _apply_suite_filter(self) -> None:
        query = " ".join(self.suite_filter_edit.text().casefold().split()) if hasattr(self, "suite_filter_edit") else ""
        preset = self.suite_filter_preset_combo.currentText() if hasattr(self, "suite_filter_preset_combo") else "Все испытания"
        first_visible = -1
        for row_index, row in enumerate(self._suite_rows):
            haystack = " ".join(
                str(value or "")
                for value in (
                    _suite_visible_name(row),
                    _suite_visible_type(row),
                    _suite_visible_stage(row),
                    _suite_scenario_refs_text(row),
                    row.get("scenario_json"),
                    row.get("road_csv"),
                    row.get("axay_csv"),
                )
            ).casefold()
            visible = True
            if query and query not in haystack:
                visible = False
            if preset == "Только включённые" and not _suite_row_enabled(row):
                visible = False
            if preset == "Требуют сценарий" and _suite_scenario_refs_text(row) == "не требуется":
                visible = False
            if preset == "Без сценария" and _suite_scenario_refs_text(row) != "не требуется":
                visible = False
            self.suite_table.setRowHidden(row_index, not visible)
            if visible and first_visible < 0:
                first_visible = row_index
        if first_visible >= 0 and not self.suite_table.selectionModel().selectedRows():
            self.suite_table.selectRow(first_visible)
        self._refresh_suite_detail()

    def _rows_from_table(self) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self._suite_rows]
        for row_index, row in enumerate(rows):
            item = self.suite_table.item(row_index, 0)
            if item is not None:
                row["включен"] = item.checkState() == QtCore.Qt.Checked
        return rows

    def _update_summary_labels(self) -> None:
        rows = self._rows_from_table() if self._suite_rows else []
        enabled_count = sum(1 for row in rows if _suite_row_enabled(row))
        linked_count = sum(1 for row in rows if _suite_scenario_refs_text(row) != "не требуется")
        self.summary_label.setText(
            f"Всего испытаний - {len(rows)}. Включено для следующего прогона - {enabled_count}."
        )
        if linked_count:
            self.ring_link_label.setText(
                "Связано с редактором циклического сценария - "
                f"{linked_count} испытаний используют файлы сценария, дороги или манёвра."
            )
        else:
            self.ring_link_label.setText(
                "Связь с редактором циклического сценария не требуется для текущих строк."
            )

    def _selected_suite_row_index(self) -> int:
        selected = self.suite_table.selectionModel().selectedRows()
        if selected:
            row_index = selected[0].row()
            if 0 <= row_index < len(self._suite_rows):
                return row_index
        for row_index in range(self.suite_table.rowCount()):
            if not self.suite_table.isRowHidden(row_index):
                return row_index
        return 0 if self._suite_rows else -1

    def _selected_suite_row(self) -> dict[str, Any] | None:
        row_index = self._selected_suite_row_index()
        if row_index < 0 or row_index >= len(self._suite_rows):
            return None
        rows = self._rows_from_table()
        return dict(rows[row_index])

    @staticmethod
    def _suite_row_detail_rows(row: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
        if not row:
            return (("Состояние", "Испытание не выбрано"),)
        return (
            ("Название", _suite_visible_name(row)),
            ("Тип испытания", _suite_visible_type(row)),
            ("Включено", "да" if _suite_row_enabled(row) else "нет"),
            ("Первый вход", _suite_visible_stage(row)),
            ("Шаг, с", _suite_number_text(row, "dt")),
            ("Длительность, с", _suite_number_text(row, "t_end")),
            ("Связанные файлы", _suite_scenario_refs_text(row)),
            ("Файл сценария", str(row.get("scenario_json") or "не требуется")),
            ("Файл дороги", str(row.get("road_csv") or "не требуется")),
            ("Файл манёвра", str(row.get("axay_csv") or "не требуется")),
        )

    def _refresh_suite_detail(self) -> None:
        if not hasattr(self, "suite_detail_table"):
            return
        row = self._selected_suite_row()
        rows = self._suite_row_detail_rows(row)
        if row:
            self.suite_detail_label.setText(
                f"Выбрано: {_suite_visible_name(row)}. {_suite_visible_type(row)}. "
                "Эта карточка показывает, какие данные уйдут в снимок набора."
            )
        else:
            self.suite_detail_label.setText("Выберите испытание в таблице.")
        self.suite_detail_table.setRowCount(len(rows))
        for row_index, (label, value) in enumerate(rows):
            self.suite_detail_table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(label))
            self.suite_detail_table.setItem(row_index, 1, QtWidgets.QTableWidgetItem(value))
        self.suite_detail_table.resizeColumnsToContents()

    def _on_suite_selection_changed(self) -> None:
        self._refresh_suite_detail()

    def _on_suite_item_changed(self, _item: QtWidgets.QTableWidgetItem) -> None:
        if self._refreshing_suite_table:
            return
        self._update_summary_labels()
        self._refresh_suite_detail()
        self.validation_label.setText("Набор изменён. Проверьте его перед базовым прогоном.")
        self.snapshot_label.setText("Снимок набора нужно сохранить заново.")

    def _snapshot_context(self) -> dict[str, Any]:
        return build_desktop_suite_snapshot_context(
            self._rows_from_table(),
            suite_source_path=self.suite_source_path,
            repo_root=self.repo_root,
            context_label="main_window_test_matrix",
            require_inputs_snapshot=True,
            require_ring_hash_for_ring_refs=True,
        )

    def check_suite(self) -> None:
        try:
            context = self._snapshot_context()
        except Exception:
            self.validation_label.setText("Проверка набора не выполнена из-за ошибки чтения данных.")
            return
        self._last_suite_context = context
        self.validation_label.setText(_suite_validation_message(context))

    def save_suite_snapshot(self) -> None:
        try:
            context = self._snapshot_context()
            if not bool(dict(context.get("snapshot") or {}).get("validated", False)):
                self.validation_label.setText(_suite_validation_message(context))
                self.snapshot_label.setText("Снимок набора не сохранён, пока проверка не пройдена.")
                return
            write_desktop_suite_handoff_snapshot(
                self._rows_from_table(),
                suite_source_path=self.suite_source_path,
                repo_root=self.repo_root,
                context_label="main_window_test_matrix",
                require_inputs_snapshot=True,
                require_ring_hash_for_ring_refs=True,
            )
            self._last_suite_context = context
        except Exception:
            self.snapshot_label.setText("Не удалось сохранить снимок набора.")
            return
        self.snapshot_label.setText("Снимок набора сохранён для базового прогона.")
        self.validation_label.setText("Набор проверен и готов для базового прогона.")

    @staticmethod
    def _suite_child_dock_payload(
        *,
        title: str,
        object_name: str,
        content_object_name: str,
        table_object_name: str,
        summary: str,
        rows: Iterable[tuple[str, ...]],
    ) -> dict[str, Any]:
        return {
            "child_dock": {
                "title": title,
                "object_name": object_name,
                "content_object_name": content_object_name,
                "table_object_name": table_object_name,
                "summary": summary,
                "rows": tuple(rows),
            }
        }

    def _show_selected_test_dock(self) -> dict[str, Any]:
        row = self._selected_suite_row()
        self._refresh_suite_detail()
        summary = self.suite_detail_label.text()
        return self._suite_child_dock_payload(
            title="Карточка испытания",
            object_name="child_dock_suite_selected_test",
            content_object_name="CHILD-SUITE-SELECTED-TEST-CONTENT",
            table_object_name="CHILD-SUITE-SELECTED-TEST-TABLE",
            summary=summary,
            rows=self._suite_row_detail_rows(row),
        )

    def _show_validation_dock(self) -> dict[str, Any]:
        try:
            context = self._snapshot_context()
        except Exception as exc:
            rows = (("Ошибка", str(exc)),)
            summary = "Проверка набора не выполнена из-за ошибки чтения данных."
        else:
            self._last_suite_context = context
            self.validation_label.setText(_suite_validation_message(context))
            snapshot = dict(context.get("snapshot") or {})
            preview = dict(snapshot.get("preview") or {})
            validation = dict(snapshot.get("validation") or {})
            ring_context = dict(context.get("ring_context") or {})
            inputs_context = dict(context.get("inputs_context") or {})
            rows = (
                ("Результат проверки", "готов" if bool(validation.get("ok", False)) else "требует внимания"),
                ("Включено испытаний", str(preview.get("enabled_count", 0) or 0)),
                ("Всего строк", str(preview.get("row_count", 0) or 0)),
                ("Нет связанных файлов", str(validation.get("blocking_missing_ref_count", 0) or 0)),
                ("Ошибок входных ссылок", str(validation.get("upstream_ref_error_count", 0) or 0)),
                ("Снимок исходных данных", str(inputs_context.get("banner") or "нет данных")),
                ("Связь со сценарием", str(ring_context.get("banner") or "нет данных")),
                ("Следующий шаг", _suite_validation_message(context)),
            )
            summary = self.validation_label.text()
        return self._suite_child_dock_payload(
            title="Проверка набора",
            object_name="child_dock_suite_validation",
            content_object_name="CHILD-SUITE-VALIDATION-CONTENT",
            table_object_name="CHILD-SUITE-VALIDATION-TABLE",
            summary=summary,
            rows=rows,
        )

    def _show_snapshot_dock(self) -> dict[str, Any]:
        context = self._last_suite_context
        if context is None:
            try:
                context = self._snapshot_context()
                self._last_suite_context = context
            except Exception:
                context = {}
        snapshot = dict(context.get("snapshot") or {})
        preview = dict(snapshot.get("preview") or {})
        validation = dict(snapshot.get("validation") or {})
        existing_state = dict(context.get("existing_state") or {})
        rows = (
            ("Файл снимка", str(context.get("handoff_path") or "ещё не сохранён")),
            ("Состояние снимка", str(existing_state.get("banner") or "снимок ещё не проверен")),
            ("Контроль набора", str(snapshot.get("suite_snapshot_hash") or "нет данных")),
            ("Включено испытаний", str(preview.get("enabled_count", 0) or 0)),
            ("Проверка", "готов" if bool(validation.get("ok", False)) else "требует внимания"),
            ("Следующий шаг", "Сохраните снимок, затем переходите к базовому прогону."),
        )
        return self._suite_child_dock_payload(
            title="Снимок набора",
            object_name="child_dock_suite_snapshot",
            content_object_name="CHILD-SUITE-SNAPSHOT-CONTENT",
            table_object_name="CHILD-SUITE-SNAPSHOT-TABLE",
            summary=self.snapshot_label.text(),
            rows=rows,
        )

    def _suite_autotest_runs_dir(self) -> Path:
        return self.repo_root / "pneumo_solver_ui" / "autotest_runs"

    def _suite_autotest_level(self) -> str:
        return str(self.suite_autotest_level_combo.currentData() or "quick")

    def refresh_suite_autotest_state(self) -> None:
        busy = (
            self.suite_autotest_process is not None
            and self.suite_autotest_process.state() != QtCore.QProcess.NotRunning
        )
        self.suite_autotest_run_button.setEnabled(not busy)
        self.suite_autotest_stop_button.setEnabled(busy)

    def run_suite_autotest(self) -> dict[str, Any]:
        if (
            self.suite_autotest_process is not None
            and self.suite_autotest_process.state() != QtCore.QProcess.NotRunning
        ):
            self.suite_autotest_status_label.setText("Автономная проверка уже выполняется.")
            return self._show_suite_autotest_dock()

        level = self._suite_autotest_level()
        cmd = [str(self.python_executable), "-m", "pneumo_solver_ui.tools.run_autotest", "--level", level]
        self.suite_autotest_log_view.clear()
        self.suite_autotest_log_view.appendPlainText("Команда: " + " ".join(cmd))
        self.suite_autotest_status_label.setText(f"Запущена автономная проверка: {level}.")

        process = QtCore.QProcess(self)
        process.setProgram(cmd[0])
        process.setArguments(cmd[1:])
        process.setWorkingDirectory(str(self.repo_root))
        env = QtCore.QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUTF8", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(env)
        process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_suite_autotest_output)
        process.finished.connect(self._on_suite_autotest_finished)
        process.errorOccurred.connect(self._on_suite_autotest_error)
        self.suite_autotest_process = process
        self.refresh_suite_autotest_state()
        process.start()
        return self._show_suite_autotest_dock()

    def _read_suite_autotest_output(self) -> None:
        process = self.suite_autotest_process
        if process is None:
            return
        data = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.suite_autotest_log_view.appendPlainText(data.rstrip())

    def _on_suite_autotest_finished(self, exit_code: int, _exit_status: QtCore.QProcess.ExitStatus) -> None:
        self._read_suite_autotest_output()
        self.suite_autotest_status_label.setText(
            "Автономная проверка завершена успешно."
            if int(exit_code) == 0
            else f"Автономная проверка завершена с кодом {int(exit_code)}."
        )
        self.refresh_suite_autotest_state()

    def _on_suite_autotest_error(self, error: QtCore.QProcess.ProcessError) -> None:
        self.suite_autotest_status_label.setText(f"Не удалось выполнить автономную проверку: {error.name}.")
        self.refresh_suite_autotest_state()

    def stop_suite_autotest(self) -> None:
        process = self.suite_autotest_process
        if process is None or process.state() == QtCore.QProcess.NotRunning:
            return
        process.terminate()
        QtCore.QTimer.singleShot(1500, self._kill_suite_autotest_if_running)
        self.suite_autotest_status_label.setText("Остановка автономной проверки запрошена.")
        self.refresh_suite_autotest_state()

    def _kill_suite_autotest_if_running(self) -> None:
        process = self.suite_autotest_process
        if process is not None and process.state() != QtCore.QProcess.NotRunning:
            process.kill()

    def open_suite_autotest_runs_dir(self) -> None:
        path = self._suite_autotest_runs_dir()
        path.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def _show_suite_autotest_dock(self) -> dict[str, Any]:
        log_lines = tuple(
            line.strip()
            for line in self.suite_autotest_log_view.toPlainText().splitlines()
            if line.strip()
        )
        rows: list[tuple[str, str]] = [
            ("Уровень проверки", self._suite_autotest_level()),
            ("Состояние", self.suite_autotest_status_label.text()),
            ("Папка артефактов", str(self._suite_autotest_runs_dir())),
        ]
        if log_lines:
            rows.extend((f"Лог {index + 1}", line) for index, line in enumerate(log_lines[-12:]))
        else:
            rows.append(("Лог", "пока нет сообщений"))
        return self._suite_child_dock_payload(
            title="Автономная проверка набора",
            object_name="child_dock_suite_autotest",
            content_object_name="CHILD-SUITE-AUTOTEST-CONTENT",
            table_object_name="CHILD-SUITE-AUTOTEST-TABLE",
            summary=self.suite_autotest_status_label.text(),
            rows=rows,
        )

    def handle_command(self, command_id: str) -> object:
        if command_id == "test.center.open":
            self.refresh_view()
            self.suite_table.setFocus(QtCore.Qt.OtherFocusReason)
            if self._suite_rows:
                self.validation_label.setText(
                    "Проверка набора открыта в рабочем шаге. Проверьте строки, сохраните снимок и переходите к базовому прогону."
                )
            return None
        if command_id == "test.selection.show":
            return self._show_selected_test_dock()
        if command_id == "test.validation.show":
            return self._show_validation_dock()
        if command_id == "test.snapshot.show":
            return self._show_snapshot_dock()
        if command_id == "test.autotest.run":
            return self.run_suite_autotest()


class BaselineWorkspacePage(RuntimeWorkspacePage):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        action_commands: Iterable[DesktopShellCommandSpec],
        on_command: Callable[[str], None],
        *,
        repo_root: Path,
        python_executable: str | None = None,
        on_shell_status: Callable[[str, bool], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.python_executable = python_executable
        self.on_shell_status = on_shell_status
        self._selected_history_id = ""
        self._last_surface: dict[str, Any] = {}
        self._refreshing_baseline_controls = False
        self._run_setup_snapshot: dict[str, Any] = dict(vars(DesktopRunSetupSnapshot()))
        self._baseline_process: QtCore.QProcess | None = None
        self._baseline_current_request_path: Path | None = None
        self._baseline_last_request_path: Path | None = None
        self._baseline_last_log_path: Path | None = None
        self._baseline_last_run_dir: Path | None = None
        self._baseline_buffered_output = ""
        self._baseline_cancel_requested = False
        super().__init__(
            workspace,
            action_commands,
            on_command,
            lambda: build_baseline_workspace_summary(
                repo_root,
                python_executable=python_executable,
            ),
            parent,
        )
        self._init_baseline_process()
        self.setObjectName("WS-BASELINE-HOSTED-PAGE")

    def _init_baseline_process(self) -> None:
        self._baseline_process = QtCore.QProcess(self)
        self._baseline_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self._baseline_process.readyReadStandardOutput.connect(self._on_baseline_process_output)
        self._baseline_process.finished.connect(self._on_baseline_process_finished)
        self._baseline_process.errorOccurred.connect(self._on_baseline_process_error)

    def _build_extra_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        self._build_run_setup_controls(layout)

        self.baseline_center_box = QtWidgets.QGroupBox("Базовый прогон: просмотр, принятие, восстановление")
        center_layout = QtWidgets.QVBoxLayout(self.baseline_center_box)
        center_layout.setSpacing(8)

        self.baseline_banner_label = QtWidgets.QLabel("")
        self.baseline_banner_label.setObjectName("BL-BANNER")
        self.baseline_banner_label.setWordWrap(True)
        center_layout.addWidget(self.baseline_banner_label)

        self.baseline_selected_label = QtWidgets.QLabel("")
        self.baseline_selected_label.setWordWrap(True)
        self.baseline_selected_label.setStyleSheet("color: #405060;")
        center_layout.addWidget(self.baseline_selected_label)

        self.baseline_history_table = QtWidgets.QTableWidget(0, 6)
        self.baseline_history_table.setObjectName("BL-HISTORY-TABLE")
        self.baseline_history_table.setHorizontalHeaderLabels(
            ("Время", "Действие", "Сверка", "Контроль прогона", "Контроль набора", "Режим")
        )
        self.baseline_history_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.baseline_history_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.baseline_history_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.baseline_history_table.verticalHeader().setVisible(False)
        self.baseline_history_table.horizontalHeader().setStretchLastSection(True)
        self.baseline_history_table.itemSelectionChanged.connect(self._on_history_selection_changed)
        center_layout.addWidget(self.baseline_history_table)

        self.baseline_mismatch_label = QtWidgets.QLabel("")
        self.baseline_mismatch_label.setWordWrap(True)
        center_layout.addWidget(self.baseline_mismatch_label)

        self.baseline_mismatch_matrix = QtWidgets.QTableWidget(0, 4)
        self.baseline_mismatch_matrix.setObjectName("BL-MISMATCH-MATRIX")
        self.baseline_mismatch_matrix.setHorizontalHeaderLabels(
            ("Поле", "Активный прогон", "Выбранная запись", "Сверка")
        )
        self.baseline_mismatch_matrix.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.baseline_mismatch_matrix.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.baseline_mismatch_matrix.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.baseline_mismatch_matrix.verticalHeader().setVisible(False)
        self.baseline_mismatch_matrix.horizontalHeader().setStretchLastSection(True)
        center_layout.addWidget(self.baseline_mismatch_matrix)

        self.baseline_review_detail_box = QtWidgets.QGroupBox("Карточка проверки выбранного результата")
        self.baseline_review_detail_box.setObjectName("BL-REVIEW-DETAILS")
        self.baseline_review_detail_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        detail_layout = QtWidgets.QVBoxLayout(self.baseline_review_detail_box)
        detail_layout.setSpacing(6)
        self.baseline_review_detail_label = QtWidgets.QLabel("")
        self.baseline_review_detail_label.setObjectName("BL-REVIEW-DETAILS-SUMMARY")
        self.baseline_review_detail_label.setWordWrap(True)
        self.baseline_review_detail_label.setStyleSheet("color: #405060;")
        detail_layout.addWidget(self.baseline_review_detail_label)
        self.baseline_review_detail_table = QtWidgets.QTableWidget(0, 3)
        self.baseline_review_detail_table.setObjectName("BL-REVIEW-DETAILS-TABLE")
        self.baseline_review_detail_table.setHorizontalHeaderLabels(("Проверка", "Значение", "Следующий шаг"))
        self.baseline_review_detail_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.baseline_review_detail_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.baseline_review_detail_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.baseline_review_detail_table.verticalHeader().setVisible(False)
        self.baseline_review_detail_table.horizontalHeader().setStretchLastSection(True)
        detail_layout.addWidget(self.baseline_review_detail_table)
        center_layout.addWidget(self.baseline_review_detail_box)

        self.explicit_confirmation_checkbox = QtWidgets.QCheckBox(
            "Разрешить явное принятие или восстановление выбранного опорного прогона"
        )
        self.explicit_confirmation_checkbox.setObjectName("BL-CHECK-EXPLICIT")
        self.explicit_confirmation_checkbox.setToolTip(
            "Принятие и восстановление недоступны, пока этот флаг не включён вручную."
        )
        self.explicit_confirmation_checkbox.toggled.connect(lambda _checked=False: self.refresh_view())
        center_layout.addWidget(self.explicit_confirmation_checkbox)

        button_row = QtWidgets.QHBoxLayout()
        self.review_button = QtWidgets.QPushButton("Просмотреть")
        self.review_button.setObjectName("BL-BTN-REVIEW")
        self.review_button.clicked.connect(lambda: self.apply_baseline_action("review"))
        self.adopt_button = QtWidgets.QPushButton("Принять")
        self.adopt_button.setObjectName("BL-BTN-ADOPT")
        self.adopt_button.clicked.connect(lambda: self.apply_baseline_action("adopt"))
        self.restore_button = QtWidgets.QPushButton("Восстановить")
        self.restore_button.setObjectName("BL-BTN-RESTORE")
        self.restore_button.clicked.connect(lambda: self.apply_baseline_action("restore"))
        for button in (self.review_button, self.adopt_button, self.restore_button):
            button_row.addWidget(button)
        button_row.addStretch(1)
        center_layout.addLayout(button_row)

        self.action_result_label = QtWidgets.QLabel("")
        self.action_result_label.setObjectName("BL-ACTION-RESULT")
        self.action_result_label.setWordWrap(True)
        self.action_result_label.setStyleSheet("color: #576574;")
        center_layout.addWidget(self.action_result_label)

        handoff_row = QtWidgets.QHBoxLayout()
        self.baseline_optimization_handoff_button = QtWidgets.QPushButton("Показать передачу в оптимизацию")
        self.baseline_optimization_handoff_button.setObjectName("BL-BTN-HANDOFF-OPTIMIZATION")
        self.baseline_optimization_handoff_button.setToolTip(
            "Показать, какой опорный прогон увидит оптимизация, без запуска отдельного окна."
        )
        self.baseline_optimization_handoff_button.clicked.connect(
            lambda: self.handle_command("baseline.optimization_handoff.show")
        )
        self.baseline_go_optimization_button = QtWidgets.QPushButton("Перейти к оптимизации")
        self.baseline_go_optimization_button.setObjectName("BL-BTN-GO-OPTIMIZATION")
        self.baseline_go_optimization_button.setToolTip(
            "Открыть следующий рабочий этап маршрута после проверки опорного прогона."
        )
        self.baseline_go_optimization_button.clicked.connect(
            lambda: self.on_command("workspace.optimization.open")
        )
        handoff_row.addWidget(self.baseline_optimization_handoff_button)
        handoff_row.addWidget(self.baseline_go_optimization_button)
        handoff_row.addStretch(1)
        center_layout.addLayout(handoff_row)

        layout.addWidget(self.baseline_center_box)

    def _build_run_setup_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.run_setup_box = QtWidgets.QGroupBox("Базовый прогон: настройка и запуск")
        self.run_setup_box.setObjectName("BL-RUN-SETUP-PANEL")
        self.run_setup_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        setup_layout = QtWidgets.QVBoxLayout(self.run_setup_box)
        setup_layout.setSpacing(8)

        intro = QtWidgets.QLabel(
            "Здесь фиксируется профиль расчёта перед опорным прогоном: режим, повторное использование результата, "
            "обязательная проверка и готовность снимка набора испытаний."
        )
        intro.setWordWrap(True)
        setup_layout.addWidget(intro)

        form = QtWidgets.QFormLayout()
        self.run_profile_combo = QtWidgets.QComboBox()
        self.run_profile_combo.setObjectName("BL-RUN-PROFILE")
        self.run_cache_policy_combo = QtWidgets.QComboBox()
        self.run_cache_policy_combo.setObjectName("BL-RUN-CACHE-POLICY")
        self.run_runtime_policy_combo = QtWidgets.QComboBox()
        self.run_runtime_policy_combo.setObjectName("BL-RUN-RUNTIME-POLICY")
        for combo, options in (
            (self.run_profile_combo, DESKTOP_RUN_PROFILE_OPTIONS),
            (self.run_cache_policy_combo, DESKTOP_RUN_CACHE_POLICY_OPTIONS),
            (self.run_runtime_policy_combo, DESKTOP_RUN_RUNTIME_POLICY_OPTIONS),
        ):
            for key, label, description in options:
                combo.addItem(label, key)
                combo.setItemData(combo.count() - 1, description, QtCore.Qt.ToolTipRole)
            combo.currentIndexChanged.connect(lambda _index=0: self._refresh_run_setup_controls())
        form.addRow("Профиль запуска", self.run_profile_combo)
        form.addRow("Повторное использование", self.run_cache_policy_combo)
        form.addRow("Режим выполнения", self.run_runtime_policy_combo)
        self._set_combo_data(self.run_profile_combo, self._run_setup_snapshot.get("launch_profile"))
        self._set_combo_data(self.run_cache_policy_combo, self._run_setup_snapshot.get("cache_policy"))
        self._set_combo_data(self.run_runtime_policy_combo, self._run_setup_snapshot.get("runtime_policy"))
        setup_layout.addLayout(form)

        self.run_setup_summary_label = QtWidgets.QLabel("")
        self.run_setup_summary_label.setWordWrap(True)
        self.run_setup_summary_label.setStyleSheet("color: #334455;")
        setup_layout.addWidget(self.run_setup_summary_label)

        self.run_setup_gate_label = QtWidgets.QLabel("")
        self.run_setup_gate_label.setObjectName("BL-RUN-GATE")
        self.run_setup_gate_label.setWordWrap(True)
        setup_layout.addWidget(self.run_setup_gate_label)

        self.run_setup_launch_hint_label = QtWidgets.QLabel("")
        self.run_setup_launch_hint_label.setObjectName("BL-RUN-LAUNCH-HINT")
        self.run_setup_launch_hint_label.setWordWrap(True)
        self.run_setup_launch_hint_label.setStyleSheet("color: #1f5d50;")
        setup_layout.addWidget(self.run_setup_launch_hint_label)

        self._build_run_preview_policy_controls(setup_layout)

        button_row = QtWidgets.QHBoxLayout()
        self.run_setup_check_button = QtWidgets.QPushButton("Проверить готовность")
        self.run_setup_check_button.setObjectName("BL-BTN-RUN-CHECK")
        self.run_setup_check_button.clicked.connect(lambda: self.handle_command("baseline.run_setup.verify"))
        self.run_setup_checked_launch_button = QtWidgets.QPushButton("Проверить и подготовить запуск")
        self.run_setup_checked_launch_button.setObjectName("BL-BTN-RUN-CHECKED")
        self.run_setup_checked_launch_button.clicked.connect(
            lambda: self.handle_command("baseline.run_setup.prepare_checked")
        )
        self.run_setup_plain_launch_button = QtWidgets.QPushButton("Подготовить запуск")
        self.run_setup_plain_launch_button.setObjectName("BL-BTN-RUN-PLAIN")
        self.run_setup_plain_launch_button.clicked.connect(
            lambda: self.handle_command("baseline.run_setup.prepare")
        )
        self.run_setup_execute_button = QtWidgets.QPushButton("Запустить в фоне")
        self.run_setup_execute_button.setObjectName("BL-BTN-RUN-EXECUTE")
        self.run_setup_execute_button.clicked.connect(
            lambda: self.handle_command("baseline.run.execute")
        )
        self.run_setup_cancel_button = QtWidgets.QPushButton("Отменить запуск")
        self.run_setup_cancel_button.setObjectName("BL-BTN-RUN-CANCEL")
        self.run_setup_cancel_button.clicked.connect(
            lambda: self.handle_command("baseline.run.cancel")
        )
        self.run_setup_open_log_button = QtWidgets.QPushButton("Показать журнал")
        self.run_setup_open_log_button.setObjectName("BL-BTN-RUN-OPEN-LOG")
        self.run_setup_open_log_button.clicked.connect(
            lambda: self.handle_command("baseline.run.open_log")
        )
        self.run_setup_open_result_button = QtWidgets.QPushButton("Показать результаты")
        self.run_setup_open_result_button.setObjectName("BL-BTN-RUN-OPEN-RESULT")
        self.run_setup_open_result_button.clicked.connect(
            lambda: self.handle_command("baseline.run.open_result")
        )
        self.run_setup_road_preview_button = QtWidgets.QPushButton("Показать предпросмотр дороги")
        self.run_setup_road_preview_button.setObjectName("BL-BTN-RUN-ROAD-PREVIEW")
        self.run_setup_road_preview_button.clicked.connect(
            lambda: self.handle_command("baseline.run.road_preview")
        )
        self.run_setup_warnings_button = QtWidgets.QPushButton("Показать предупреждения")
        self.run_setup_warnings_button.setObjectName("BL-BTN-RUN-WARNINGS")
        self.run_setup_warnings_button.clicked.connect(
            lambda: self.handle_command("baseline.run.warnings")
        )
        for button in (
            self.run_setup_check_button,
            self.run_setup_checked_launch_button,
            self.run_setup_plain_launch_button,
            self.run_setup_execute_button,
            self.run_setup_cancel_button,
            self.run_setup_open_log_button,
            self.run_setup_open_result_button,
            self.run_setup_road_preview_button,
            self.run_setup_warnings_button,
        ):
            button_row.addWidget(button)
        button_row.addStretch(1)
        setup_layout.addLayout(button_row)

        self.run_setup_result_label = QtWidgets.QLabel("")
        self.run_setup_result_label.setObjectName("BL-RUN-ACTION-RESULT")
        self.run_setup_result_label.setWordWrap(True)
        self.run_setup_result_label.setStyleSheet("color: #576574;")
        setup_layout.addWidget(self.run_setup_result_label)

        layout.addWidget(self.run_setup_box)

    def _build_run_preview_policy_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.run_preview_policy_box = QtWidgets.QGroupBox("Предпросмотр дороги и политика запуска")
        self.run_preview_policy_box.setObjectName("BL-RUN-PREVIEW-POLICY")
        policy_layout = QtWidgets.QVBoxLayout(self.run_preview_policy_box)
        policy_layout.setSpacing(8)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)

        self.run_preview_dt_spin = self._double_spin(
            "BL-PREVIEW-DT",
            minimum=0.001,
            maximum=0.1,
            step=0.001,
            decimals=3,
            value=float(self._run_setup_snapshot.get("preview_dt", 0.01) or 0.01),
            suffix=" с",
        )
        self.run_preview_t_end_spin = self._double_spin(
            "BL-PREVIEW-T-END",
            minimum=0.1,
            maximum=120.0,
            step=0.1,
            decimals=1,
            value=float(self._run_setup_snapshot.get("preview_t_end", 3.0) or 3.0),
            suffix=" с",
        )
        self.run_preview_road_len_spin = self._double_spin(
            "BL-PREVIEW-ROAD-LEN",
            minimum=1.0,
            maximum=10000.0,
            step=1.0,
            decimals=1,
            value=float(self._run_setup_snapshot.get("preview_road_len_m", 60.0) or 60.0),
            suffix=" м",
        )
        self.run_dt_spin = self._double_spin(
            "BL-RUN-DT",
            minimum=0.0005,
            maximum=0.1,
            step=0.0005,
            decimals=4,
            value=float(self._run_setup_snapshot.get("run_dt", 0.003) or 0.003),
            suffix=" с",
        )
        self.run_t_end_spin = self._double_spin(
            "BL-RUN-T-END",
            minimum=0.1,
            maximum=300.0,
            step=0.1,
            decimals=1,
            value=float(self._run_setup_snapshot.get("run_t_end", 1.6) or 1.6),
            suffix=" с",
        )
        for row, (label, widget) in enumerate(
            (
                ("Шаг предпросмотра", self.run_preview_dt_spin),
                ("Длительность предпросмотра", self.run_preview_t_end_spin),
                ("Длина участка дороги", self.run_preview_road_len_spin),
                ("Шаг расчёта", self.run_dt_spin),
                ("Длительность расчёта", self.run_t_end_spin),
            )
        ):
            form.addWidget(QtWidgets.QLabel(label), row // 2, (row % 2) * 2)
            form.addWidget(widget, row // 2, (row % 2) * 2 + 1)

        self.run_record_full_checkbox = self._checkbox(
            "BL-RUN-RECORD-FULL",
            "Расширенный журнал давления и потоков",
            bool(self._run_setup_snapshot.get("record_full", False)),
        )
        self.run_export_csv_checkbox = self._checkbox(
            "BL-RUN-EXPORT-CSV",
            "Сохранять таблицы результатов",
            bool(self._run_setup_snapshot.get("export_csv", True)),
        )
        self.run_export_npz_checkbox = self._checkbox(
            "BL-RUN-EXPORT-NPZ",
            "Сохранять файл анимации",
            bool(self._run_setup_snapshot.get("export_npz", False)),
        )
        self.run_auto_check_checkbox = self._checkbox(
            "BL-RUN-AUTO-CHECK",
            "Проверять перед запуском",
            bool(self._run_setup_snapshot.get("auto_check", True)),
        )
        self.run_write_log_checkbox = self._checkbox(
            "BL-RUN-WRITE-LOG",
            "Сохранять журнал запуска",
            bool(self._run_setup_snapshot.get("write_log_file", True)),
        )
        checkbox_row = QtWidgets.QHBoxLayout()
        for checkbox in (
            self.run_record_full_checkbox,
            self.run_export_csv_checkbox,
            self.run_export_npz_checkbox,
            self.run_auto_check_checkbox,
            self.run_write_log_checkbox,
        ):
            checkbox_row.addWidget(checkbox)
        checkbox_row.addStretch(1)

        self.apply_run_profile_button = QtWidgets.QPushButton("Применить профиль к параметрам")
        self.apply_run_profile_button.setObjectName("BL-BTN-APPLY-RUN-PROFILE")
        self.apply_run_profile_button.setToolTip(
            "Заполнить шаг, длительность, сохранение и политику по выбранному профилю запуска."
        )
        self.apply_run_profile_button.clicked.connect(self._apply_selected_run_profile_to_controls)

        self.run_policy_table = QtWidgets.QTableWidget(0, 3)
        self.run_policy_table.setObjectName("BL-RUN-POLICY-TABLE")
        self.run_policy_table.setHorizontalHeaderLabels(("Проверка", "Состояние", "Что делать"))
        self.run_policy_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.run_policy_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.run_policy_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.run_policy_table.verticalHeader().setVisible(False)
        self.run_policy_table.horizontalHeader().setStretchLastSection(True)

        policy_layout.addLayout(form)
        policy_layout.addLayout(checkbox_row)
        policy_layout.addWidget(self.apply_run_profile_button, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        policy_layout.addWidget(self.run_policy_table)
        layout.addWidget(self.run_preview_policy_box)

    def _double_spin(
        self,
        object_name: str,
        *,
        minimum: float,
        maximum: float,
        step: float,
        decimals: int,
        value: float,
        suffix: str,
    ) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setObjectName(object_name)
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.setSuffix(suffix)
        spin.setValue(value)
        spin.valueChanged.connect(lambda _value=0.0: self._refresh_run_setup_controls())
        return spin

    def _checkbox(self, object_name: str, text: str, checked: bool) -> QtWidgets.QCheckBox:
        checkbox = QtWidgets.QCheckBox(text)
        checkbox.setObjectName(object_name)
        checkbox.setChecked(checked)
        checkbox.toggled.connect(lambda _checked=False: self._refresh_run_setup_controls())
        return checkbox

    def _surface(self) -> dict[str, Any]:
        explicit = bool(
            getattr(self, "explicit_confirmation_checkbox", None)
            and self.explicit_confirmation_checkbox.isChecked()
        )
        return build_baseline_center_surface(
            repo_root=self.repo_root,
            selected_history_id=self._selected_history_id,
            explicit_confirmation=explicit,
        )

    def _set_combo_data(self, combo: QtWidgets.QComboBox, value: object) -> None:
        wanted = str(value or "").strip()
        for index in range(combo.count()):
            if str(combo.itemData(index) or "").strip() == wanted:
                combo.setCurrentIndex(index)
                return

    def _combo_data(self, combo: QtWidgets.QComboBox, fallback: str) -> str:
        value = str(combo.currentData() or "").strip()
        return value or fallback

    def _current_run_setup_snapshot(self) -> dict[str, Any]:
        snapshot = dict(self._run_setup_snapshot)
        if hasattr(self, "run_profile_combo"):
            snapshot["launch_profile"] = self._combo_data(self.run_profile_combo, "detail")
            snapshot["cache_policy"] = self._combo_data(self.run_cache_policy_combo, "reuse")
            snapshot["runtime_policy"] = self._combo_data(self.run_runtime_policy_combo, "balanced")
        if hasattr(self, "run_preview_dt_spin"):
            snapshot["preview_dt"] = float(self.run_preview_dt_spin.value())
            snapshot["preview_t_end"] = float(self.run_preview_t_end_spin.value())
            snapshot["preview_road_len_m"] = float(self.run_preview_road_len_spin.value())
            snapshot["run_dt"] = float(self.run_dt_spin.value())
            snapshot["run_t_end"] = float(self.run_t_end_spin.value())
            snapshot["record_full"] = bool(self.run_record_full_checkbox.isChecked())
            snapshot["export_csv"] = bool(self.run_export_csv_checkbox.isChecked())
            snapshot["export_npz"] = bool(self.run_export_npz_checkbox.isChecked())
            snapshot["auto_check"] = bool(self.run_auto_check_checkbox.isChecked())
            snapshot["write_log_file"] = bool(self.run_write_log_checkbox.isChecked())
        self._run_setup_snapshot = snapshot
        return snapshot

    def _set_run_setup_widgets_from_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        current = dict(snapshot or {})
        for combo, key in (
            (getattr(self, "run_profile_combo", None), "launch_profile"),
            (getattr(self, "run_cache_policy_combo", None), "cache_policy"),
            (getattr(self, "run_runtime_policy_combo", None), "runtime_policy"),
        ):
            if combo is not None:
                blocker = QtCore.QSignalBlocker(combo)
                self._set_combo_data(combo, current.get(key))
                del blocker
        for widget_name, key in (
            ("run_preview_dt_spin", "preview_dt"),
            ("run_preview_t_end_spin", "preview_t_end"),
            ("run_preview_road_len_spin", "preview_road_len_m"),
            ("run_dt_spin", "run_dt"),
            ("run_t_end_spin", "run_t_end"),
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                blocker = QtCore.QSignalBlocker(widget)
                widget.setValue(float(current.get(key, widget.value()) or widget.value()))
                del blocker
        for widget_name, key in (
            ("run_record_full_checkbox", "record_full"),
            ("run_export_csv_checkbox", "export_csv"),
            ("run_export_npz_checkbox", "export_npz"),
            ("run_auto_check_checkbox", "auto_check"),
            ("run_write_log_checkbox", "write_log_file"),
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                blocker = QtCore.QSignalBlocker(widget)
                widget.setChecked(bool(current.get(key, widget.isChecked())))
                del blocker

    def _apply_selected_run_profile_to_controls(self) -> None:
        profile_key = self._combo_data(self.run_profile_combo, "detail")
        updated, changed = apply_run_setup_profile(
            self._current_run_setup_snapshot(),
            profile_key,
            scenario_key="worldroad",
        )
        self._run_setup_snapshot = updated
        self._set_run_setup_widgets_from_snapshot(updated)
        changed_text = ", ".join(_baseline_field_label(item) for item in changed) if changed else "без изменений"
        self.run_setup_result_label.setText(
            f"Профиль «{run_profile_label(profile_key)}» применён к параметрам запуска: {changed_text}."
        )
        self._refresh_run_setup_controls()

    def _remember_baseline_request(self, request: Mapping[str, Any] | None) -> None:
        payload = dict(request or {})
        paths = dict(payload.get("paths") or {})
        raw_request = str(paths.get("request") or "").strip()
        raw_log = str(payload.get("process_log_path") or paths.get("log") or "").strip()
        raw_run_dir = str(paths.get("run_dir") or "").strip()
        raw_summary = str(payload.get("run_summary_path") or "").strip()
        if raw_request:
            self._baseline_last_request_path = Path(raw_request).expanduser().resolve()
        if raw_log:
            self._baseline_last_log_path = Path(raw_log).expanduser().resolve()
        if raw_run_dir:
            self._baseline_last_run_dir = Path(raw_run_dir).expanduser().resolve()
        elif raw_summary:
            self._baseline_last_run_dir = Path(raw_summary).expanduser().resolve().parent

    def _latest_baseline_request(self) -> dict[str, Any]:
        try:
            request = read_baseline_run_launch_request(repo_root=self.repo_root)
        except Exception:
            request = {}
        self._remember_baseline_request(request)
        return request

    @staticmethod
    def _path_state(path: Path | None) -> str:
        if path is None:
            return "не задан"
        return "найден" if path.exists() else "не найден"

    @staticmethod
    def _path_size_text(path: Path | None) -> str:
        if path is None or not path.exists() or not path.is_file():
            return ""
        try:
            size = path.stat().st_size
        except OSError:
            return ""
        if size < 1024:
            return f"{size} байт"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} КБ"
        return f"{size / (1024 * 1024):.1f} МБ"

    @staticmethod
    def _path_text(path: Path | None) -> str:
        return str(path) if path is not None else "нет данных"

    def _baseline_request_rows(self, request: Mapping[str, Any] | None = None) -> list[tuple[str, ...]]:
        payload = dict(request or self._latest_baseline_request() or {})
        paths = dict(payload.get("paths") or {})
        setup = dict(payload.get("run_setup") or {})
        selected_test = dict(payload.get("selected_test") or {})
        blockers = tuple(str(item) for item in payload.get("operator_blockers") or () if str(item).strip())
        rows: list[tuple[str, ...]] = [
            ("Запрос", str(payload.get("request_id") or "нет"), "machine-readable request WS-BASELINE"),
            (
                "Готовность выполнения",
                "готов" if bool(payload.get("execution_ready", False)) else "ждёт данных",
                "; ".join(blockers) if blockers else "блокеров не показано",
            ),
            (
                "Статус запуска",
                str(payload.get("execution_status") or "не запускался"),
                str(payload.get("completed_at_utc") or payload.get("started_at_utc") or payload.get("created_at_utc") or ""),
            ),
            (
                "Выбранное испытание",
                str(selected_test.get("name") or "нет"),
                f"индекс {selected_test.get('index')}" if selected_test.get("index") is not None else "индекс не задан",
            ),
            ("Профиль", str(setup.get("launch_profile") or "detail"), "профиль базового расчёта"),
            ("Кеш", str(setup.get("cache_policy") or "reuse"), "политика повторного использования"),
            ("Предупреждения", str(setup.get("runtime_policy") or "balanced"), "политика выполнения"),
        ]
        for label, key in (
            ("Файл запроса", "request"),
            ("Снимок набора", "suite_snapshot"),
            ("Исходные данные", "inputs_snapshot"),
            ("Подготовленные входные данные", "prepared_inputs"),
            ("Подготовленный набор", "prepared_suite"),
            ("Папка результата", "run_dir"),
            ("Журнал", "log"),
        ):
            raw_path = str(paths.get(key) or "").strip()
            path = Path(raw_path).expanduser().resolve() if raw_path else None
            rows.append((label, self._path_text(path), self._path_state(path)))
        return rows

    def _child_dock_payload(
        self,
        *,
        title: str,
        object_name: str,
        content_object_name: str,
        table_object_name: str,
        summary: str,
        rows: Iterable[Sequence[object]],
    ) -> dict[str, Any]:
        return {
            "status": "shown",
            "child_dock": {
                "title": title,
                "object_name": object_name,
                "content_object_name": content_object_name,
                "table_object_name": table_object_name,
                "summary": summary,
                "rows": tuple(tuple(str(value) for value in row) for row in rows),
            },
        }

    @staticmethod
    def _bool_label(value: object) -> str:
        return "да" if bool(value) else "нет"

    @staticmethod
    def _float_text(value: object, *, precision: int = 3, unit: str = "") -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "нет данных"
        text = f"{number:.{precision}f}".rstrip("0").rstrip(".")
        return f"{text} {unit}".strip()

    def _run_setup_policy_rows(
        self,
        snapshot: Mapping[str, Any],
        summary: Mapping[str, str] | None = None,
        gate: Mapping[str, Any] | None = None,
        plain_state: Mapping[str, Any] | None = None,
        recommendation: str = "",
    ) -> list[tuple[str, str, str]]:
        current = dict(snapshot or {})
        summary_map = dict(summary or {})
        gate_map = dict(gate or {})
        plain_map = dict(plain_state or {})
        profile = str(current.get("launch_profile") or "detail")
        cache_policy = str(current.get("cache_policy") or "reuse")
        runtime_policy = str(current.get("runtime_policy") or "balanced")
        gate_allowed = bool(gate_map.get("baseline_launch_allowed", False))
        plain_enabled = bool(plain_map.get("enabled", False))
        recommendation_text = (
            "сначала проверка, затем подготовка"
            if recommendation != "plain_launch"
            else "можно готовить запуск сразу"
        )
        rows: list[tuple[str, str, str]] = [
            (
                "Профиль запуска",
                run_profile_label(profile),
                run_profile_description(profile) or str(summary_map.get("headline") or ""),
            ),
            (
                "Предпросмотр дороги",
                "ровная дорога",
                (
                    f"шаг {self._float_text(current.get('preview_dt'), precision=3, unit='с')}; "
                    f"длительность {self._float_text(current.get('preview_t_end'), precision=1, unit='с')}; "
                    f"участок {self._float_text(current.get('preview_road_len_m'), precision=1, unit='м')}"
                ),
            ),
            (
                "Расчёт",
                f"шаг {self._float_text(current.get('run_dt'), precision=4, unit='с')}",
                (
                    f"длительность {self._float_text(current.get('run_t_end'), precision=1, unit='с')}; "
                    f"расширенный журнал: {self._bool_label(current.get('record_full', False))}"
                ),
            ),
            (
                "Повторное использование",
                cache_policy_label(cache_policy),
                cache_policy_description(cache_policy),
            ),
            (
                "Поведение при предупреждениях",
                runtime_policy_label(runtime_policy),
                runtime_policy_description(runtime_policy),
            ),
            (
                "Проверка перед запуском",
                self._bool_label(current.get("auto_check", True)),
                recommendation_text,
            ),
            (
                "Сохранение результата",
                (
                    f"таблицы: {self._bool_label(current.get('export_csv', True))}; "
                    f"анимация: {self._bool_label(current.get('export_npz', False))}; "
                    f"журнал: {self._bool_label(current.get('write_log_file', True))}"
                ),
                "сохраняется вместе с запросом базового прогона",
            ),
            (
                "Готовность набора",
                "готов" if gate_allowed else "требует подготовки",
                _baseline_launch_gate_text(gate_map.get("banner")),
            ),
            (
                "Обычная подготовка",
                "доступна" if plain_enabled else "заблокирована",
                str(plain_map.get("detail") or "нет деталей"),
            ),
        ]
        return rows

    def _run_setup_warning_rows(
        self,
        snapshot: Mapping[str, Any],
        gate: Mapping[str, Any],
        plain_state: Mapping[str, Any],
    ) -> list[tuple[str, str, str]]:
        current = dict(snapshot or {})
        rows: list[tuple[str, str, str]] = []
        gate_allowed = bool(gate.get("baseline_launch_allowed", False))
        rows.append(
            (
                "Набор испытаний",
                "готов" if gate_allowed else "требует подготовки",
                _baseline_launch_gate_text(gate.get("banner")),
            )
        )
        runtime_policy = str(current.get("runtime_policy") or "balanced")
        rows.append(
            (
                "Политика предупреждений",
                runtime_policy_label(runtime_policy),
                runtime_policy_description(runtime_policy),
            )
        )
        if not bool(current.get("auto_check", True)):
            rows.append(
                (
                    "Проверка перед запуском",
                    "выключена",
                    "включите проверку, если это не осознанный быстрый повтор",
                )
            )
        if runtime_policy == "force":
            rows.append(
                (
                    "Форсированный запуск",
                    "требует внимания",
                    "предупреждения будут только зафиксированы в журнале",
                )
            )
        if not bool(current.get("write_log_file", True)):
            rows.append(
                (
                    "Журнал запуска",
                    "выключен",
                    "для разбора ошибок лучше сохранять журнал",
                )
            )
        if float(current.get("run_dt", 0.003) or 0.003) > float(current.get("preview_dt", 0.01) or 0.01):
            rows.append(
                (
                    "Шаг расчёта",
                    "крупнее предпросмотра",
                    "проверьте точность перед принятием результата как опорного",
                )
            )
        if not bool(plain_state.get("enabled", False)):
            rows.append(
                (
                    "Обычная подготовка",
                    "заблокирована",
                    str(plain_state.get("detail") or "сначала нужна проверка"),
                )
            )
        if len(rows) == 2 and gate_allowed:
            rows.append(("Предупреждения", "критичных нет", "можно готовить запуск по текущей политике"))
        return rows

    def _populate_run_policy_table(self, rows: Iterable[Sequence[object]]) -> None:
        if not hasattr(self, "run_policy_table"):
            return
        table_rows = [tuple(str(value) for value in row) for row in rows]
        blocker = QtCore.QSignalBlocker(self.run_policy_table)
        self.run_policy_table.setRowCount(len(table_rows))
        for row_index, row_values in enumerate(table_rows):
            for column_index, value in enumerate(row_values[:3]):
                item = QtWidgets.QTableWidgetItem(value)
                if row_values[1] in {"требует подготовки", "заблокирована", "выключена", "требует внимания"}:
                    item.setBackground(QtGui.QColor("#fff4e5"))
                elif row_values[1] in {"готов", "доступна", "критичных нет"}:
                    item.setBackground(QtGui.QColor("#e8f7ee"))
                self.run_policy_table.setItem(row_index, column_index, item)
        self.run_policy_table.resizeColumnsToContents()
        del blocker

    def _show_run_road_preview_dock(self) -> dict[str, Any]:
        snapshot = self._current_run_setup_snapshot()
        summary = describe_run_setup_snapshot(
            snapshot,
            scenario_label="дорожный сценарий",
            preview_surface_label="ровная дорога",
            snapshot_enabled=True,
            snapshot_name="снимок перед запуском",
        )
        rows = [
            ("Профиль дороги", "ровная дорога", "источник: текущие параметры базового прогона"),
            ("Шаг предпросмотра", self._float_text(snapshot.get("preview_dt"), precision=3, unit="с"), "влияет только на быстрый просмотр"),
            ("Длительность предпросмотра", self._float_text(snapshot.get("preview_t_end"), precision=1, unit="с"), "должна покрывать интересующий манёвр"),
            ("Длина участка дороги", self._float_text(snapshot.get("preview_road_len_m"), precision=1, unit="м"), "используется для оценки дороги перед расчётом"),
            ("Шаг расчёта", self._float_text(snapshot.get("run_dt"), precision=4, unit="с"), "пойдёт в запрос базового прогона"),
            ("Длительность расчёта", self._float_text(snapshot.get("run_t_end"), precision=1, unit="с"), "пойдёт в запрос базового прогона"),
            ("Сводка предпросмотра", str(summary.get("preview_line") or ""), "проверяется до запуска"),
        ]
        self.run_setup_result_label.setText(
            "Предпросмотр дороги показан в дочерней dock-панели рабочей области."
        )
        return self._child_dock_payload(
            title="Предпросмотр дороги",
            object_name="child_dock_baseline_road_preview",
            content_object_name="CHILD-BASELINE-ROAD-PREVIEW-CONTENT",
            table_object_name="CHILD-BASELINE-ROAD-PREVIEW-TABLE",
            summary=self.run_setup_result_label.text(),
            rows=rows,
        )

    def _show_run_warnings_dock(self) -> dict[str, Any]:
        snapshot = self._current_run_setup_snapshot()
        gate = self._run_setup_gate()
        plain_state = describe_plain_launch_availability(
            auto_check_enabled=bool(snapshot.get("auto_check", True)),
            runtime_policy_key=str(snapshot.get("runtime_policy") or "balanced"),
            summary=None,
            report_exists=False,
        )
        rows = self._run_setup_warning_rows(snapshot, gate, plain_state)
        self.run_setup_result_label.setText(
            "Предупреждения запуска показаны в дочерней dock-панели рабочей области."
        )
        return self._child_dock_payload(
            title="Предупреждения запуска",
            object_name="child_dock_baseline_warnings",
            content_object_name="CHILD-BASELINE-WARNINGS-CONTENT",
            table_object_name="CHILD-BASELINE-WARNINGS-TABLE",
            summary=self.run_setup_result_label.text(),
            rows=rows,
        )

    def _show_baseline_log_dock(self) -> dict[str, Any]:
        request = self._latest_baseline_request()
        log_path = self._baseline_last_log_path
        rows = self._baseline_request_rows(request)
        if log_path is None or not log_path.exists():
            self.run_setup_result_label.setText(
                "Журнал базового прогона пока не найден. Панель журнала показала текущий запрос и блокеры."
            )
            rows.append(("Журнал", "не найден", "подготовьте или запустите базовый прогон"))
        else:
            try:
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError as exc:
                lines = [f"Не удалось прочитать журнал: {exc}"]
            rows.append(("Журнал", str(log_path), self._path_size_text(log_path)))
            for index, line in enumerate(lines[-24:], start=max(1, len(lines) - 23)):
                text = " ".join(str(line).split()).strip()
                if text:
                    rows.append((f"Строка {index}", text[:240], "последние сообщения"))
            self.run_setup_result_label.setText(
                "Журнал базового прогона показан в дочерней dock-панели рабочей области."
            )
        return self._child_dock_payload(
            title="Журнал базового прогона",
            object_name="child_dock_baseline_log",
            content_object_name="CHILD-BASELINE-LOG-CONTENT",
            table_object_name="CHILD-BASELINE-LOG-TABLE",
            summary=self.run_setup_result_label.text(),
            rows=rows,
        )

    def _show_baseline_artifacts_dock(self) -> dict[str, Any]:
        request = self._latest_baseline_request()
        run_dir = self._baseline_last_run_dir
        rows = self._baseline_request_rows(request)
        if run_dir is None or not run_dir.exists():
            self.run_setup_result_label.setText(
                "Папка результата базового прогона пока не найдена. Панель результатов показала текущий запрос и блокеры."
            )
            rows.append(("Папка результата", "не найдена", "подготовьте или запустите базовый прогон"))
        else:
            try:
                files = sorted(
                    (path for path in run_dir.rglob("*") if path.is_file()),
                    key=lambda path: (path.parent.as_posix(), path.name),
                )
            except OSError:
                files = []
            artifact_rows: list[tuple[str, str, str]] = []
            for path in files[:32]:
                try:
                    label = str(path.relative_to(run_dir))
                except ValueError:
                    label = path.name
                artifact_rows.append((label, str(path), self._path_size_text(path)))
            rows.append(("Папка результата", str(run_dir), f"{len(files)} файлов"))
            rows.extend(artifact_rows or [("Файлы результата", "файлы не найдены", "проверьте журнал запуска")])
            self.run_setup_result_label.setText(
                "Результаты базового прогона показаны в дочерней dock-панели рабочей области."
            )
        return self._child_dock_payload(
            title="Результаты базового прогона",
            object_name="child_dock_baseline_artifacts",
            content_object_name="CHILD-BASELINE-ARTIFACTS-CONTENT",
            table_object_name="CHILD-BASELINE-ARTIFACTS-TABLE",
            summary=self.run_setup_result_label.text(),
            rows=rows,
        )

    def _show_optimization_handoff_dock(self) -> dict[str, Any]:
        surface = self._surface()
        active = dict(surface.get("active_baseline") or {})
        selected = dict(surface.get("selected_history") or {})
        banner_state = dict(surface.get("banner_state") or {})
        mismatch_state = dict(surface.get("mismatch_state") or {})
        active_hash = str(active.get("active_baseline_hash") or "")
        selected_hash = str(selected.get("active_baseline_hash") or "")
        optimizer_ready = bool(active.get("optimizer_baseline_can_consume", False))
        mismatch_fields = tuple(str(field) for field in mismatch_state.get("mismatch_fields") or ())
        next_step = (
            "Переходите в оптимизацию: активный опорный прогон видим и доступен."
            if optimizer_ready
            else "Сначала выполните или явно примите опорный прогон в этом рабочем шаге."
        )
        rows = [
            ("Активный опорный прогон", self._short_matrix_value(active_hash), _baseline_state_label(str(active.get("state") or "missing"))),
            ("Доступен оптимизации", "да" if optimizer_ready else "нет", "оптимизация читает только явно активный результат"),
            ("Выбранная история", str(surface.get("selected_history_id") or "нет"), self._short_matrix_value(selected_hash)),
            ("Снимок набора", self._short_matrix_value(str(active.get("suite_snapshot_hash") or selected.get("suite_snapshot_hash") or "")), "должен соответствовать набору испытаний"),
            ("Исходные данные", self._short_matrix_value(str(active.get("inputs_snapshot_hash") or selected.get("inputs_snapshot_hash") or "")), "должны соответствовать зафиксированному снимку"),
            ("Циклический сценарий", self._short_matrix_value(str(active.get("ring_source_hash") or selected.get("ring_source_hash") or "")), "должен соответствовать WS-RING"),
            ("Сверка", _baseline_field_list(mismatch_fields) if mismatch_fields else "нет показанных расхождений", "молчаливая подмена запрещена"),
            ("Предупреждение", str(banner_state.get("banner") or "нет"), "проверьте перед оптимизацией"),
            ("Следующий шаг", next_step, "кнопка «Перейти к оптимизации» открывает следующий dock-виджет"),
        ]
        self.action_result_label.setText(
            "Передача в оптимизацию показана в дочерней dock-панели рабочей области."
        )
        return self._child_dock_payload(
            title="Передача в оптимизацию",
            object_name="child_dock_baseline_optimization_handoff",
            content_object_name="CHILD-BASELINE-OPTIMIZATION-HANDOFF-CONTENT",
            table_object_name="CHILD-BASELINE-OPTIMIZATION-HANDOFF-TABLE",
            summary=self.action_result_label.text(),
            rows=rows,
        )

    def _run_setup_gate(self) -> dict[str, Any]:
        snapshot = self._current_run_setup_snapshot()
        return baseline_suite_handoff_launch_gate(
            launch_profile=str(snapshot.get("launch_profile") or "detail"),
            runtime_policy=str(snapshot.get("runtime_policy") or "balanced"),
            repo_root=self.repo_root,
        )

    def _refresh_run_setup_controls(self) -> None:
        if not hasattr(self, "run_setup_summary_label"):
            return
        snapshot = self._current_run_setup_snapshot()
        summary = describe_run_setup_snapshot(
            snapshot,
            scenario_label="дорожный сценарий",
            preview_surface_label="ровная дорога",
            snapshot_enabled=True,
            snapshot_name="снимок перед запуском",
        )
        gate = self._run_setup_gate()
        launch_target = describe_run_launch_target(
            launch_profile_key=str(snapshot.get("launch_profile") or "detail"),
            scenario_key="worldroad",
            scenario_label="дорожный сценарий",
        )
        recommendation = recommended_run_launch_action(
            auto_check_enabled=bool(snapshot.get("auto_check", True)),
            summary=None,
            report_exists=False,
        )
        plain_state = describe_plain_launch_availability(
            auto_check_enabled=bool(snapshot.get("auto_check", True)),
            runtime_policy_key=str(snapshot.get("runtime_policy") or "balanced"),
            summary=None,
            report_exists=False,
        )
        gate_allowed = bool(gate.get("baseline_launch_allowed", False))
        gate_banner = _baseline_launch_gate_text(gate.get("banner"))
        self._latest_baseline_request()
        busy = self._baseline_run_is_busy()
        has_log = self._baseline_last_log_path is not None and self._baseline_last_log_path.exists()
        has_run_dir = self._baseline_last_run_dir is not None and self._baseline_last_run_dir.exists()
        self.run_setup_summary_label.setText(
            "\n".join(
                part
                for part in (
                    summary.get("headline", ""),
                    summary.get("detail_line", ""),
                    summary.get("runtime_line", ""),
                    summary.get("cost_summary", ""),
                )
                if part
            )
        )
        gate_state = "готов к запуску" if gate_allowed else "требует подготовки"
        self.run_setup_gate_label.setText(
            f"Готовность набора испытаний: {gate_state}. {gate_banner}"
        )
        self.run_setup_gate_label.setStyleSheet(
            "background: #e8f7ee; color: #1f5f3a; padding: 8px; border: 1px solid #64b883;"
            if gate_allowed
            else "background: #fff4e5; color: #6f4e00; padding: 8px; border: 1px solid #d9822b;"
        )
        plain_detail = str(plain_state.get("detail") or "").strip()
        recommendation_text = (
            "рекомендуется обычная подготовка"
            if recommendation == "plain_launch"
            else "рекомендуется проверка перед подготовкой"
        )
        self.run_setup_launch_hint_label.setText(
            f"{launch_target.get('hint_line') or 'Целевой запуск: опорный прогон.'} "
            f"{recommendation_text}. Обычный запуск: {plain_detail}."
        )
        policy_rows = self._run_setup_policy_rows(snapshot, summary, gate, plain_state, recommendation)
        self._populate_run_policy_table(policy_rows)
        self.run_setup_check_button.setEnabled(not busy)
        self.run_setup_checked_launch_button.setEnabled(not busy)
        self.run_setup_plain_launch_button.setEnabled(gate_allowed and not busy)
        self.run_setup_plain_launch_button.setToolTip(
            "Доступно после актуального снимка набора испытаний."
            if gate_allowed
            else "Сначала обновите и сохраните снимок набора испытаний."
        )
        self.run_setup_execute_button.setEnabled(gate_allowed and not busy)
        self.run_setup_execute_button.setToolTip(
            "Запустить подготовленный расчёт без открытия расширенного центра."
            if gate_allowed
            else "Сначала обновите и сохраните снимок набора испытаний."
        )
        self.run_setup_cancel_button.setEnabled(busy)
        self.run_setup_cancel_button.setToolTip(
            "Остановить текущий фоновый базовый прогон."
            if busy
            else "Нет выполняющегося базового прогона."
        )
        self.run_setup_open_log_button.setEnabled(has_log)
        self.run_setup_open_log_button.setToolTip(
            "Открыть журнал последнего фонового запуска."
            if has_log
            else "Журнал появится после подготовки или запуска базового прогона."
        )
        self.run_setup_open_result_button.setEnabled(has_run_dir)
        self.run_setup_open_result_button.setToolTip(
            "Открыть папку результата последнего базового прогона."
            if has_run_dir
            else "Папка результата появится после подготовки или запуска базового прогона."
        )
        self.run_setup_road_preview_button.setEnabled(not busy)
        self.run_setup_warnings_button.setEnabled(not busy)

    def _baseline_run_is_busy(self) -> bool:
        return self._baseline_process is not None and self._baseline_process.state() != QtCore.QProcess.NotRunning

    def _set_baseline_shell_status(self, text: str, *, busy: bool) -> None:
        if callable(self.on_shell_status):
            self.on_shell_status(text, busy)

    def _set_baseline_run_busy(self, busy: bool) -> None:
        for button_name in (
            "run_setup_check_button",
            "run_setup_checked_launch_button",
            "run_setup_plain_launch_button",
            "run_setup_execute_button",
            "run_setup_advanced_button",
        ):
            button = getattr(self, button_name, None)
            if button is not None:
                button.setEnabled(not busy)
        cancel_button = getattr(self, "run_setup_cancel_button", None)
        if cancel_button is not None:
            cancel_button.setEnabled(busy)
        log_button = getattr(self, "run_setup_open_log_button", None)
        if log_button is not None:
            log_button.setEnabled(self._baseline_last_log_path is not None and self._baseline_last_log_path.exists())
        result_button = getattr(self, "run_setup_open_result_button", None)
        if result_button is not None:
            result_button.setEnabled(self._baseline_last_run_dir is not None and self._baseline_last_run_dir.exists())

    def _activate_run_setup_panel(self, message: str = "") -> None:
        self._refresh_run_setup_controls()
        self.run_setup_box.setFocus(QtCore.Qt.OtherFocusReason)
        if message:
            self.run_setup_result_label.setText(message)

    def _verify_run_setup_gate(self) -> dict[str, Any]:
        gate = self._run_setup_gate()
        self._refresh_run_setup_controls()
        state = "готов" if bool(gate.get("baseline_launch_allowed", False)) else "не готов"
        self.run_setup_result_label.setText(
            f"Проверка готовности: {state}. {_baseline_launch_gate_text(gate.get('banner'))}"
        )
        return gate

    def _prepare_run_setup_launch(self, *, checked: bool) -> dict[str, Any]:
        gate = self._verify_run_setup_gate()
        request = prepare_baseline_run_launch_request(
            self._current_run_setup_snapshot(),
            repo_root=self.repo_root,
            python_executable=self.python_executable,
            checked=checked,
        )
        self._remember_baseline_request(request)
        request_ready = bool(request.get("execution_ready", False))
        request_path = str(dict(request.get("paths") or {}).get("request") or "").strip()
        if request_ready:
            run_dir = str(dict(request.get("paths") or {}).get("run_dir") or "").strip()
            self.run_setup_result_label.setText(
                "Команда запуска подготовлена. "
                f"Запрос сохранён {request_path}. Папка результата {run_dir}."
            )
        else:
            blockers = "; ".join(str(item) for item in list(request.get("operator_blockers") or []) if str(item).strip())
            detail = blockers or _baseline_launch_gate_text(gate.get("banner"))
            prefix = "Проверка выполнена. " if checked else ""
            self.run_setup_result_label.setText(
                f"{prefix}Подготовка запуска сохранена, но выполнение ждёт данных. {detail}. "
                f"Запрос сохранён {request_path}."
            )
        return {
            **request,
            "action": "prepare_checked" if checked else "prepare",
            "allowed": bool(gate.get("baseline_launch_allowed", False)),
        }

    def _execute_baseline_run(self) -> dict[str, Any]:
        if self._baseline_run_is_busy():
            self.run_setup_result_label.setText("Базовый прогон уже выполняется. Дождитесь завершения текущего запуска.")
            self._set_baseline_shell_status("Базовый прогон уже выполняется.", busy=True)
            return {"status": "running"}

        request = self._prepare_run_setup_launch(checked=True)
        if not bool(request.get("execution_ready", False)):
            self._set_baseline_shell_status("Базовый прогон ждёт готовых данных.", busy=False)
            return {**request, "status": "blocked"}
        command = [str(part) for part in list(request.get("command") or []) if str(part).strip()]
        if not command:
            self.run_setup_result_label.setText("Запуск не начат: команда расчёта не подготовлена.")
            self._set_baseline_shell_status("Команда базового прогона не подготовлена.", busy=False)
            return {**request, "status": "blocked"}
        if self._baseline_process is None:
            self._init_baseline_process()

        paths = dict(request.get("paths") or {})
        self._baseline_current_request_path = Path(str(paths.get("request") or "")).expanduser().resolve()
        self._baseline_buffered_output = ""
        self._baseline_cancel_requested = False
        started_request = mark_baseline_run_launch_request_started(request)
        self._remember_baseline_request(started_request)
        process = self._baseline_process
        process.setWorkingDirectory(str(self.repo_root))
        process.setProgram(command[0])
        process.setArguments(command[1:])
        process.start()
        self._set_baseline_run_busy(True)
        self.run_setup_result_label.setText("Базовый прогон выполняется в фоне. Окно остаётся доступным.")
        self._set_baseline_shell_status("Базовый прогон выполняется...", busy=True)
        return {**request, "status": "running"}

    def _kill_baseline_process_if_running(self) -> None:
        if self._baseline_process is not None and self._baseline_run_is_busy():
            self._baseline_process.kill()

    def _cancel_baseline_run(self) -> dict[str, Any]:
        if not self._baseline_run_is_busy() or self._baseline_process is None:
            self.run_setup_result_label.setText("Нет выполняющегося базового прогона для отмены.")
            self._set_baseline_shell_status("Нет выполняющегося базового прогона.", busy=False)
            self._refresh_run_setup_controls()
            return {"status": "idle"}
        self._baseline_cancel_requested = True
        self.run_setup_result_label.setText("Отмена базового прогона запрошена. Ждём остановки процесса.")
        self._set_baseline_shell_status("Отмена базового прогона...", busy=True)
        self._baseline_process.terminate()
        self._baseline_process.kill()
        self._set_baseline_run_busy(True)
        return {"status": "cancelling"}

    def _on_baseline_process_output(self) -> None:
        if self._baseline_current_request_path is None:
            return
        if self._baseline_process is None:
            return
        text = bytes(self._baseline_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if not text:
            return
        self._baseline_buffered_output += text
        append_baseline_run_execution_log(self._baseline_current_request_path, text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            self.run_setup_result_label.setText(f"Базовый прогон выполняется. Последнее сообщение {lines[-1][:180]}.")

    def _on_baseline_process_finished(self, exit_code: int, _exit_status: QtCore.QProcess.ExitStatus) -> None:
        request_path = self._baseline_current_request_path
        self._set_baseline_run_busy(False)
        self._baseline_current_request_path = None
        if request_path is None:
            self.run_setup_result_label.setText("Базовый прогон завершился, но сведения о запросе не найдены.")
            self._set_baseline_shell_status("Базовый прогон завершился без сведений о запросе.", busy=False)
            return
        cancelled = bool(self._baseline_cancel_requested)
        self._baseline_cancel_requested = False
        result = complete_baseline_run_launch_request(
            request_path,
            returncode=-15 if cancelled and int(exit_code) == 0 else int(exit_code),
            stdout_tail=self._baseline_buffered_output[-4000:],
            stderr_tail="Запуск отменён оператором." if cancelled else "",
        )
        self._remember_baseline_request(result)
        if cancelled:
            self.run_setup_result_label.setText("Базовый прогон отменён оператором. Журнал запуска сохранён.")
            self._set_baseline_shell_status("Базовый прогон отменён.", busy=False)
        elif int(exit_code) == 0:
            candidate = dict(result.get("baseline_candidate") or {})
            if candidate.get("history_id"):
                self.run_setup_result_label.setText(
                    "Базовый прогон завершён. Результат добавлен в историю для просмотра и явного принятия."
                )
            else:
                self.run_setup_result_label.setText(
                    "Базовый прогон завершён. Сводка результата сохранена, но запись истории требует проверки."
                )
            self._set_baseline_shell_status("Базовый прогон завершён.", busy=False)
        else:
            self.run_setup_result_label.setText(
                f"Базовый прогон завершился с кодом {int(exit_code)}. Проверьте журнал запуска."
            )
            self._set_baseline_shell_status("Базовый прогон завершился с ошибкой.", busy=False)
        self.refresh_view()

    def _on_baseline_process_error(self, error: QtCore.QProcess.ProcessError) -> None:
        if self._baseline_cancel_requested:
            return
        request_path = self._baseline_current_request_path
        self._set_baseline_run_busy(False)
        self._baseline_current_request_path = None
        self._baseline_cancel_requested = False
        if request_path is not None:
            result = complete_baseline_run_launch_request(
                request_path,
                returncode=127,
                stderr_tail=str(error),
            )
            self._remember_baseline_request(result)
        self.run_setup_result_label.setText("Не удалось начать базовый прогон. Проверьте путь к Python и журнал запуска.")
        self._set_baseline_shell_status("Не удалось начать базовый прогон.", busy=False)

    def refresh_view(self) -> None:
        super().refresh_view()
        if hasattr(self, "run_setup_summary_label"):
            self._refresh_run_setup_controls()
        if hasattr(self, "baseline_history_table"):
            self._refresh_baseline_center_controls()

    def _refresh_baseline_center_controls(self) -> None:
        self._refreshing_baseline_controls = True
        try:
            surface = self._surface()
            self._last_surface = surface
            active = dict(surface.get("active_baseline") or {})
            selected = dict(surface.get("selected_history") or {})
            banner_state = dict(surface.get("banner_state") or {})
            mismatch_state = dict(surface.get("mismatch_state") or {})
            action_strip = dict(surface.get("action_strip") or {})

            banner = str(banner_state.get("banner") or "").strip()
            if banner:
                self.baseline_banner_label.setText(f"Предупреждение: {banner}")
                self.baseline_banner_label.setStyleSheet(
                    "background: #fff4e5; color: #6f4e00; padding: 8px; border: 1px solid #d9822b;"
                )
            else:
                self.baseline_banner_label.setText(
                    f"Опорный прогон {_baseline_state_label(str(active.get('state') or 'missing'))}. "
                    f"Доступен оптимизатору - {'да' if bool(active.get('optimizer_baseline_can_consume', False)) else 'нет'}."
                )
                self.baseline_banner_label.setStyleSheet(
                    "background: #e8f7ee; color: #1f5f3a; padding: 8px; border: 1px solid #64b883;"
                )

            selected_id = str(surface.get("selected_history_id") or "")
            if selected_id:
                self._selected_history_id = selected_id
            active_hash = str(active.get("active_baseline_hash") or "")
            selected_hash = str(selected.get("active_baseline_hash") or "")
            self.baseline_selected_label.setText(
                "\n".join(
                    line
                    for line in (
                        f"Активный прогон - {active_hash[:16] or '—'}; выбранная запись - {selected_id or 'нет'}",
                        f"Набор испытаний - {str(active.get('suite_snapshot_hash') or selected.get('suite_snapshot_hash') or '')[:16] or '—'}",
                        f"Исходные данные - {str(active.get('inputs_snapshot_hash') or selected.get('inputs_snapshot_hash') or '')[:16] or '—'}",
                        f"Циклический сценарий: {str(active.get('ring_source_hash') or selected.get('ring_source_hash') or '')[:16] or '—'}",
                        f"Выбранный прогон: {selected_hash[:16] or '—'}",
                    )
                    if line
                )
            )

            self._populate_history_table(tuple(dict(row) for row in surface.get("history_rows") or ()))
            mismatch_fields = tuple(str(field) for field in mismatch_state.get("mismatch_fields") or ())
            mismatch_text = (
                _baseline_field_list(mismatch_fields)
                if mismatch_fields
                else str(mismatch_state.get("state") or "нет расхождений")
            )
            self.baseline_mismatch_label.setText(
                f"Состояние сверки: {mismatch_text}. Молчаливая подмена запрещена."
            )
            self._populate_mismatch_matrix(active, selected)
            self._populate_review_details(active, selected, action_strip, explicit=self.explicit_confirmation_checkbox.isChecked())

            review = dict(action_strip.get("review") or {})
            adopt = dict(action_strip.get("adopt") or {})
            restore = dict(action_strip.get("restore") or {})
            explicit = self.explicit_confirmation_checkbox.isChecked()
            self.review_button.setEnabled(bool(review.get("enabled", False)))
            self.adopt_button.setEnabled(explicit and bool(adopt.get("enabled", False)))
            self.restore_button.setEnabled(explicit and bool(restore.get("enabled", False)))
            self.adopt_button.setToolTip(self._action_tooltip("adopt", adopt, explicit=explicit))
            self.restore_button.setToolTip(self._action_tooltip("restore", restore, explicit=explicit))
            self.review_button.setToolTip("Просмотр выбранной строки истории без изменения данных.")
        finally:
            self._refreshing_baseline_controls = False

    def _populate_history_table(self, rows: tuple[dict[str, Any], ...]) -> None:
        blocker = QtCore.QSignalBlocker(self.baseline_history_table)
        self.baseline_history_table.setRowCount(len(rows))
        selected_row_index = -1
        for row_index, row in enumerate(rows):
            history_id = str(row.get("history_id") or "")
            values = (
                str(row.get("ts_utc") or row.get("created_at_utc") or ""),
                _baseline_action_label(str(row.get("action") or "")),
                _baseline_state_label(str(row.get("compare_state") or "")),
                str(row.get("active_baseline_hash") or "")[:12],
                str(row.get("suite_snapshot_hash") or "")[:12],
                _baseline_policy_label(str(row.get("policy_mode") or "")),
            )
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value or "—")
                item.setData(QtCore.Qt.UserRole, history_id)
                self.baseline_history_table.setItem(row_index, column, item)
            if history_id and history_id == self._selected_history_id:
                selected_row_index = row_index
        self.baseline_history_table.resizeColumnsToContents()
        if selected_row_index >= 0:
            self.baseline_history_table.selectRow(selected_row_index)
        del blocker

    def _populate_mismatch_matrix(
        self,
        active: dict[str, Any],
        selected: dict[str, Any],
    ) -> None:
        fields = (
            ("Опорный прогон", "active_baseline_hash"),
            ("Снимок набора", "suite_snapshot_hash"),
            ("Исходные данные", "inputs_snapshot_hash"),
            ("Циклический сценарий", "ring_source_hash"),
            ("Режим", "policy_mode"),
        )
        blocker = QtCore.QSignalBlocker(self.baseline_mismatch_matrix)
        self.baseline_mismatch_matrix.setRowCount(len(fields))
        for row_index, (label, key) in enumerate(fields):
            active_value = str(active.get(key) or "")
            selected_value = str(selected.get(key) or "")
            if not active_value or not selected_value:
                status = "нет данных"
                color = QtGui.QColor("#fff4e5")
            elif active_value == selected_value:
                status = "совпадает"
                color = QtGui.QColor("#e8f7ee")
            else:
                status = "расходится"
                color = QtGui.QColor("#fdecea")
            values = (
                label,
                self._short_matrix_value(active_value),
                self._short_matrix_value(selected_value),
                status,
            )
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if column == 3:
                    item.setBackground(color)
                self.baseline_mismatch_matrix.setItem(row_index, column, item)
        self.baseline_mismatch_matrix.resizeColumnsToContents()
        del blocker

    def _short_matrix_value(self, value: str) -> str:
        text = str(value or "")
        if not text:
            return "—"
        if len(text) <= 24:
            return text
        return f"{text[:12]}...{text[-8:]}"

    def _review_next_step(
        self,
        *,
        selected: dict[str, Any],
        action_strip: dict[str, Any],
        explicit: bool,
    ) -> str:
        if not str(selected.get("history_id") or "").strip():
            return "Выберите строку истории или выполните новый базовый прогон."
        mismatch_fields = tuple(str(field) for field in selected.get("mismatch_fields") or ())
        if mismatch_fields:
            return f"Есть расхождения: {_baseline_field_list(mismatch_fields)}. Перед передачей в оптимизацию нужен явный выбор."
        adopt = dict(action_strip.get("adopt") or {})
        restore = dict(action_strip.get("restore") or {})
        if explicit and bool(adopt.get("enabled", False)):
            return "Можно нажать «Принять» и сделать результат активным опорным прогоном."
        if explicit and bool(restore.get("enabled", False)):
            return "Можно нажать «Восстановить» и явно вернуть исторический результат."
        if not explicit:
            return "Сначала выполните просмотр и включите явное подтверждение, если этот результат должен стать активным."
        return "Доступен безопасный просмотр; активный опорный прогон не меняется."

    def _populate_review_details(
        self,
        active: dict[str, Any],
        selected: dict[str, Any],
        action_strip: dict[str, Any],
        *,
        explicit: bool,
    ) -> None:
        selected_id = str(selected.get("history_id") or "").strip()
        selected_hash = str(selected.get("active_baseline_hash") or "").strip()
        active_hash = str(active.get("active_baseline_hash") or "").strip()
        compare_state = str(selected.get("compare_state") or "").strip()
        mismatch_fields = tuple(str(field) for field in selected.get("mismatch_fields") or ())
        next_step = self._review_next_step(selected=selected, action_strip=action_strip, explicit=explicit)
        optimizer_ready = bool(active.get("optimizer_baseline_can_consume", False))
        if selected_id:
            self.baseline_review_detail_label.setText(
                "Карточка проверки показывает, какой результат выбран, откуда он взят и что можно безопасно сделать дальше. "
                "Автоматическое принятие результата запрещено."
            )
        else:
            self.baseline_review_detail_label.setText(
                "История опорных прогонов пока пуста. Выполните базовый прогон или выберите существующую запись."
            )
        rows = (
            (
                "Выбранная запись",
                selected_id or "нет",
                "Просмотрите карточку перед любым изменением активного результата." if selected_id else "Нет выбранной записи истории.",
            ),
            (
                "Действие истории",
                _baseline_action_label(str(selected.get("action") or "")),
                "Это происхождение записи; оно не применяет результат автоматически.",
            ),
            (
                "Файл результата",
                str(selected.get("baseline_path") or "нет"),
                "Откройте файл/папку результата перед принятием." if selected.get("baseline_path") else "Файл результата не указан.",
            ),
            (
                "Папка запуска",
                str(selected.get("source_run_dir") or "нет"),
                "Проверьте файлы запуска и журнал." if selected.get("source_run_dir") else "Папка запуска не указана.",
            ),
            (
                "Контроль прогона",
                self._short_matrix_value(selected_hash),
                "Должен быть осознанно выбран перед оптимизацией.",
            ),
            (
                "Активный контроль",
                self._short_matrix_value(active_hash),
                "Это текущий результат, который видит оптимизация.",
            ),
            (
                "Снимок набора",
                self._short_matrix_value(str(selected.get("suite_snapshot_hash") or active.get("suite_snapshot_hash") or "")),
                "При расхождении нужен новый прогон или явное восстановление.",
            ),
            (
                "Исходные данные",
                self._short_matrix_value(str(selected.get("inputs_snapshot_hash") or active.get("inputs_snapshot_hash") or "")),
                "При расхождении проверьте WS-INPUTS и WS-SUITE.",
            ),
            (
                "Циклический сценарий",
                self._short_matrix_value(str(selected.get("ring_source_hash") or active.get("ring_source_hash") or "")),
                "При расхождении проверьте WS-RING.",
            ),
            (
                "Состояние сверки",
                _baseline_state_label(compare_state or "unknown"),
                _baseline_field_list(mismatch_fields) if mismatch_fields else "Критичных расхождений с активным контекстом не показано.",
            ),
            (
                "Доступность оптимизации",
                "готов" if optimizer_ready else "не готов",
                "Оптимизация берёт только активный явно принятый опорный прогон.",
            ),
            ("Следующий безопасный шаг", next_step, "Молчаливая подмена запрещена."),
        )
        blocker = QtCore.QSignalBlocker(self.baseline_review_detail_table)
        self.baseline_review_detail_table.setRowCount(len(rows))
        for row_index, (label, value, hint) in enumerate(rows):
            values = (label, value, hint)
            for column, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(text or "—"))
                if row_index == len(rows) - 1:
                    item.setBackground(QtGui.QColor("#eef5ff"))
                elif mismatch_fields and label in {"Состояние сверки", "Снимок набора", "Исходные данные", "Циклический сценарий"}:
                    item.setBackground(QtGui.QColor("#fff4e5"))
                self.baseline_review_detail_table.setItem(row_index, column, item)
        self.baseline_review_detail_table.resizeColumnsToContents()
        del blocker

    def _on_history_selection_changed(self) -> None:
        if self._refreshing_baseline_controls:
            return
        items = self.baseline_history_table.selectedItems()
        if not items:
            return
        history_id = str(items[0].data(QtCore.Qt.UserRole) or "").strip()
        if history_id and history_id != self._selected_history_id:
            self._selected_history_id = history_id
            self._refresh_baseline_center_controls()

    def _action_tooltip(self, action: str, payload: dict[str, Any], *, explicit: bool) -> str:
        policy = dict(payload.get("policy") or {})
        if not explicit and action in {"adopt", "restore"}:
            return "Сначала включите явное подтверждение."
        if bool(payload.get("enabled", False)):
            return f"Действие «{_baseline_action_label(action)}» для выбранного опорного прогона будет применено после подтверждения."
        candidate_state = str(policy.get("candidate_state") or "unknown")
        stale = ", ".join(_baseline_reason_label(str(item)) for item in policy.get("candidate_stale_reasons") or ())
        return (
            f"Недоступно: состояние выбранного прогона: {_baseline_state_label(candidate_state)}."
            + (f" Причины: {stale}." if stale else "")
        )

    def _confirm_baseline_action(self, action: str, surface: dict[str, Any]) -> bool:
        selected = dict(surface.get("selected_history") or {})
        mismatch_fields = _baseline_field_list(
            str(field) for field in selected.get("mismatch_fields") or ()
        )
        warning = f"\n\nПредупреждение: расходятся поля: {mismatch_fields}" if mismatch_fields else ""
        answer = QtWidgets.QMessageBox.question(
            self,
            "Базовый прогон",
            (
                f"Подтвердить действие «{_baseline_action_label(action)}» для выбранной строки истории?\n\n"
                f"Строка истории: {surface.get('selected_history_id') or 'нет'}\n"
                f"Контроль опорного прогона: {str(selected.get('active_baseline_hash') or '')[:16] or '—'}"
                f"{warning}\n\nМолчаливая подмена запрещена; действие будет записано явно."
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        return answer == QtWidgets.QMessageBox.Yes

    def apply_baseline_action(self, action: str) -> dict[str, Any]:
        requested_action = str(action or "review").strip().lower() or "review"
        surface = self._surface()
        history_id = str(surface.get("selected_history_id") or "").strip()
        if requested_action in {"adopt", "restore"}:
            if not self.explicit_confirmation_checkbox.isChecked():
                self.action_result_label.setText(
                    "Действие заблокировано: включите явное подтверждение."
                )
                return {"action": requested_action, "status": "blocked"}
            if not self._confirm_baseline_action(requested_action, surface):
                self.action_result_label.setText("Действие отменено пользователем.")
                return {"action": requested_action, "status": "cancelled"}

        result = apply_baseline_center_action(
            action=requested_action,
            history_id=history_id,
            repo_root=self.repo_root,
            explicit_confirmation=bool(
                requested_action in {"adopt", "restore"}
                and self.explicit_confirmation_checkbox.isChecked()
            ),
            actor="desktop_spec_shell",
            note=f"explicit {requested_action} from baseline center",
        )
        self.action_result_label.setText(self._format_action_result(result))
        if requested_action == "review":
            self.baseline_review_detail_box.setFocus(QtCore.Qt.OtherFocusReason)
        if requested_action in {"adopt", "restore"} and result.get("status") == "applied":
            self.explicit_confirmation_checkbox.setChecked(False)
        self.refresh_view()
        return result

    def _format_action_result(self, result: dict[str, Any]) -> str:
        policy = dict(result.get("policy") or {})
        bits = [
            f"Действие: {_baseline_action_label(str(result.get('action') or ''))}",
            f"Состояние: {_baseline_state_label(str(result.get('status') or ''))}",
            f"Активный прогон записан: {'да' if bool(result.get('wrote_active_contract', False)) else 'нет'}",
            f"История дополнена: {'да' if bool(result.get('history_appended', False)) else 'нет'}",
            f"Молчаливая подмена разрешена: {'да' if bool(result.get('silent_rebinding_allowed', False)) else 'нет'}",
        ]
        banner = str(policy.get("banner") or "")
        if banner:
            bits.append(f"Предупреждение: {banner}")
        return ". ".join(bits) + "."

    def handle_command(self, command_id: str) -> None:
        if command_id == "baseline.run_setup.open":
            self._activate_run_setup_panel("Настройка запуска открыта в рабочем шаге базового прогона.")
            return
        if command_id == "baseline.run_setup.verify":
            self._verify_run_setup_gate()
            return
        if command_id == "baseline.run_setup.prepare_checked":
            self._prepare_run_setup_launch(checked=True)
            return
        if command_id == "baseline.run_setup.prepare":
            self._prepare_run_setup_launch(checked=False)
            return
        if command_id == "baseline.run.execute":
            self._execute_baseline_run()
            return
        if command_id == "baseline.run.cancel":
            self._cancel_baseline_run()
            return
        if command_id == "baseline.run.open_log":
            return self._show_baseline_log_dock()
        if command_id == "baseline.run.open_result":
            return self._show_baseline_artifacts_dock()
        if command_id == "baseline.run.road_preview":
            return self._show_run_road_preview_dock()
        if command_id == "baseline.run.warnings":
            return self._show_run_warnings_dock()
        if command_id == "baseline.optimization_handoff.show":
            return self._show_optimization_handoff_dock()
        if command_id == "baseline.center.open":
            self.refresh_view()
            return
        if command_id == "baseline.review":
            self.apply_baseline_action("review")
            return
        if command_id == "baseline.adopt":
            self.apply_baseline_action("adopt")
            return
        if command_id == "baseline.restore":
            self.apply_baseline_action("restore")


class InputWorkspacePage(RuntimeWorkspacePage):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        action_commands: Iterable[DesktopShellCommandSpec],
        on_command: Callable[[str], None],
        *,
        repo_root: Path,
        python_executable: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.python_executable = python_executable
        self._input_payload: dict[str, Any] = {}
        self._input_reference_payload: dict[str, Any] = {}
        self._input_profile_paths: dict[str, Path] = {}
        self._input_snapshot_paths: dict[str, Path] = {}
        self._input_search_results: list[dict[str, str]] = []
        self._input_source_path: Path = default_working_copy_path()
        self._refreshing_input_table = False
        self._refreshing_input_aux = False
        super().__init__(
            workspace,
            action_commands,
            on_command,
            lambda: build_input_workspace_summary(
                repo_root,
                python_executable=python_executable,
            ),
            parent,
        )
        self.setObjectName("WS-INPUTS-HOSTED-PAGE")

    def _build_extra_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.input_editor_box = QtWidgets.QGroupBox("Редактируемая копия исходных данных")
        self.input_editor_box.setObjectName("ID-PARAM-TABLE")
        self.input_editor_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        editor_layout = QtWidgets.QVBoxLayout(self.input_editor_box)
        editor_layout.setSpacing(8)

        intro = QtWidgets.QLabel(
            "Это основной встроенный слой WS-INPUTS: он читает текущую рабочую копию, показывает "
            "секцию, параметр, значение и единицу измерения, а сохранение выполняет через desktop_input_model."
        )
        intro.setWordWrap(True)
        editor_layout.addWidget(intro)

        self.input_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.input_splitter.setObjectName("ID-EDITOR-SPLITTER")
        self.input_splitter.setChildrenCollapsible(False)
        editor_layout.addWidget(self.input_splitter, 1)

        input_table_panel = QtWidgets.QWidget(self.input_splitter)
        input_table_layout = QtWidgets.QVBoxLayout(input_table_panel)
        input_table_layout.setContentsMargins(0, 0, 8, 0)
        input_table_layout.setSpacing(8)

        self.input_table = QtWidgets.QTableWidget(0, 5)
        self.input_table.setObjectName("ID-PARAM-TABLE-VIEW")
        self.input_table.setHorizontalHeaderLabels(
            ("Раздел", "Параметр", "Значение", "Ед.", "Подсказка")
        )
        self.input_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.input_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.input_table.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked
            | QtWidgets.QAbstractItemView.EditKeyPressed
            | QtWidgets.QAbstractItemView.SelectedClicked
        )
        self.input_table.verticalHeader().setVisible(False)
        self.input_table.horizontalHeader().setStretchLastSection(True)
        self.input_table.itemChanged.connect(self._on_input_item_changed)
        self.input_table.itemSelectionChanged.connect(self._on_input_selection_changed)
        input_table_layout.addWidget(self.input_table, 1)

        actions = QtWidgets.QHBoxLayout()
        self.input_refresh_button = QtWidgets.QPushButton("Обновить параметры")
        self.input_refresh_button.setObjectName("ID-BTN-REFRESH")
        self.input_refresh_button.clicked.connect(self._refresh_input_editor_controls)
        actions.addWidget(self.input_refresh_button)

        self.input_save_button = QtWidgets.QPushButton("Сохранить рабочую копию")
        self.input_save_button.setObjectName("ID-BTN-SAVE-WORKING-COPY")
        self.input_save_button.clicked.connect(self._save_input_working_copy)
        actions.addWidget(self.input_save_button)

        self.input_snapshot_button = QtWidgets.QPushButton("Зафиксировать снимок для маршрута")
        self.input_snapshot_button.setObjectName("ID-BTN-SAVE-HANDOFF")
        self.input_snapshot_button.clicked.connect(self._save_input_handoff_snapshot)
        actions.addWidget(self.input_snapshot_button)

        self.input_load_file_button = QtWidgets.QPushButton("Загрузить файл данных")
        self.input_load_file_button.setObjectName("ID-BTN-LOAD-FILE")
        self.input_load_file_button.clicked.connect(self._load_input_json_file)
        actions.addWidget(self.input_load_file_button)

        self.input_save_as_button = QtWidgets.QPushButton("Сохранить как")
        self.input_save_as_button.setObjectName("ID-BTN-SAVE-AS")
        self.input_save_as_button.clicked.connect(self._save_input_as_file)
        actions.addWidget(self.input_save_as_button)

        self.input_restore_template_button = QtWidgets.QPushButton("Вернуть исходный шаблон")
        self.input_restore_template_button.setObjectName("ID-BTN-RESTORE-TEMPLATE")
        self.input_restore_template_button.clicked.connect(self._restore_input_template)
        actions.addWidget(self.input_restore_template_button)

        input_table_layout.addLayout(actions)
        self.input_splitter.addWidget(input_table_panel)
        self._build_input_detail_panel(self.input_splitter)
        self.input_splitter.setStretchFactor(0, 3)
        self.input_splitter.setStretchFactor(1, 2)
        self.input_splitter.setSizes((880, 620))

        self.input_action_label = QtWidgets.QLabel("")
        self.input_action_label.setObjectName("ID-ACTION-RESULT")
        self.input_action_label.setWordWrap(True)
        self.input_action_label.setStyleSheet("color: #576574;")
        editor_layout.addWidget(self.input_action_label)

        layout.addWidget(self.input_editor_box)

    def _build_input_detail_panel(self, parent: QtWidgets.QSplitter) -> None:
        detail_scroll = QtWidgets.QScrollArea()
        detail_scroll.setObjectName("ID-DETAIL-SCROLL")
        detail_scroll.setWidgetResizable(True)
        panel = QtWidgets.QWidget()
        panel.setObjectName("ID-DETAIL-PANEL")
        detail_layout = QtWidgets.QVBoxLayout(panel)
        detail_layout.setSpacing(10)

        source_box = QtWidgets.QGroupBox("Источник данных", panel)
        source_layout = QtWidgets.QVBoxLayout(source_box)
        self.input_source_label = QtWidgets.QLabel("")
        self.input_source_label.setObjectName("ID-SOURCE-LABEL")
        self.input_source_label.setWordWrap(True)
        source_layout.addWidget(self.input_source_label)
        detail_layout.addWidget(source_box)

        search_box = QtWidgets.QGroupBox("Поиск и выбранный параметр", panel)
        search_layout = QtWidgets.QVBoxLayout(search_box)
        self.input_search_edit = QtWidgets.QLineEdit(search_box)
        self.input_search_edit.setObjectName("ID-FIELD-SEARCH")
        self.input_search_edit.setPlaceholderText("Найти параметр по названию, единице или смыслу")
        self.input_search_edit.textChanged.connect(self._refresh_input_search_results)
        search_layout.addWidget(self.input_search_edit)
        self.input_search_results = QtWidgets.QListWidget(search_box)
        self.input_search_results.setObjectName("ID-FIELD-SEARCH-RESULTS")
        self.input_search_results.itemActivated.connect(self._on_input_search_result_activated)
        search_layout.addWidget(self.input_search_results, 1)
        self.input_field_inspector = QtWidgets.QLabel("Выберите параметр в таблице или через поиск.")
        self.input_field_inspector.setObjectName("ID-FIELD-INSPECTOR")
        self.input_field_inspector.setWordWrap(True)
        search_layout.addWidget(self.input_field_inspector)
        detail_layout.addWidget(search_box)

        status_box = QtWidgets.QGroupBox("Готовность разделов и снимок маршрута", panel)
        status_layout = QtWidgets.QVBoxLayout(status_box)
        self.input_snapshot_status_label = QtWidgets.QLabel("")
        self.input_snapshot_status_label.setObjectName("ID-SNAPSHOT-STATUS")
        self.input_snapshot_status_label.setWordWrap(True)
        status_layout.addWidget(self.input_snapshot_status_label)
        self.input_section_status_table = QtWidgets.QTableWidget(0, 5, status_box)
        self.input_section_status_table.setObjectName("ID-SECTION-STATUS-TABLE")
        self.input_section_status_table.setHorizontalHeaderLabels(
            ("Раздел", "Статус", "Сводка", "Замечания", "Изменения")
        )
        self.input_section_status_table.verticalHeader().setVisible(False)
        self.input_section_status_table.horizontalHeader().setStretchLastSection(True)
        self.input_section_status_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.input_section_status_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.input_section_status_table.itemActivated.connect(self._on_input_section_status_activated)
        status_layout.addWidget(self.input_section_status_table, 1)
        detail_layout.addWidget(status_box)

        profile_box = QtWidgets.QGroupBox("Пресеты, профили и снимки", panel)
        profile_layout = QtWidgets.QVBoxLayout(profile_box)
        preset_row = QtWidgets.QHBoxLayout()
        self.input_quick_preset_combo = QtWidgets.QComboBox(profile_box)
        self.input_quick_preset_combo.setObjectName("ID-QUICK-PRESET")
        for key, label, description in DESKTOP_QUICK_PRESET_OPTIONS:
            self.input_quick_preset_combo.addItem(label, userData=key)
            index = self.input_quick_preset_combo.count() - 1
            self.input_quick_preset_combo.setItemData(index, description, QtCore.Qt.ToolTipRole)
        preset_row.addWidget(self.input_quick_preset_combo, 1)
        self.input_apply_preset_button = QtWidgets.QPushButton("Применить пресет", profile_box)
        self.input_apply_preset_button.setObjectName("ID-BTN-APPLY-PRESET")
        self.input_apply_preset_button.clicked.connect(self._apply_input_quick_preset)
        preset_row.addWidget(self.input_apply_preset_button)
        profile_layout.addLayout(preset_row)

        profile_form = QtWidgets.QFormLayout()
        self.input_profile_combo = QtWidgets.QComboBox(profile_box)
        self.input_profile_combo.setObjectName("ID-PROFILE-LIST")
        profile_form.addRow("Профиль", self.input_profile_combo)
        self.input_profile_name_edit = QtWidgets.QLineEdit("рабочий_вариант", profile_box)
        self.input_profile_name_edit.setObjectName("ID-PROFILE-NAME")
        profile_form.addRow("Имя профиля", self.input_profile_name_edit)
        profile_layout.addLayout(profile_form)
        profile_buttons = QtWidgets.QHBoxLayout()
        self.input_save_profile_button = QtWidgets.QPushButton("Сохранить профиль", profile_box)
        self.input_save_profile_button.setObjectName("ID-BTN-SAVE-PROFILE")
        self.input_save_profile_button.clicked.connect(self._save_input_profile)
        profile_buttons.addWidget(self.input_save_profile_button)
        self.input_load_profile_button = QtWidgets.QPushButton("Загрузить профиль", profile_box)
        self.input_load_profile_button.setObjectName("ID-BTN-LOAD-PROFILE")
        self.input_load_profile_button.clicked.connect(self._load_input_profile)
        profile_buttons.addWidget(self.input_load_profile_button)
        profile_layout.addLayout(profile_buttons)

        snapshot_form = QtWidgets.QFormLayout()
        self.input_snapshot_combo = QtWidgets.QComboBox(profile_box)
        self.input_snapshot_combo.setObjectName("ID-SNAPSHOT-LIST")
        snapshot_form.addRow("Снимок", self.input_snapshot_combo)
        self.input_snapshot_name_edit = QtWidgets.QLineEdit("перед_запуском", profile_box)
        self.input_snapshot_name_edit.setObjectName("ID-SNAPSHOT-NAME")
        snapshot_form.addRow("Имя снимка", self.input_snapshot_name_edit)
        profile_layout.addLayout(snapshot_form)
        snapshot_buttons = QtWidgets.QHBoxLayout()
        self.input_save_snapshot_button = QtWidgets.QPushButton("Сохранить снимок", profile_box)
        self.input_save_snapshot_button.setObjectName("ID-BTN-SAVE-SNAPSHOT")
        self.input_save_snapshot_button.clicked.connect(self._save_input_snapshot)
        snapshot_buttons.addWidget(self.input_save_snapshot_button)
        self.input_load_snapshot_button = QtWidgets.QPushButton("Загрузить снимок", profile_box)
        self.input_load_snapshot_button.setObjectName("ID-BTN-LOAD-SNAPSHOT")
        self.input_load_snapshot_button.clicked.connect(self._load_input_snapshot)
        snapshot_buttons.addWidget(self.input_load_snapshot_button)
        profile_layout.addLayout(snapshot_buttons)
        detail_layout.addWidget(profile_box)

        changes_box = QtWidgets.QGroupBox("Отличия от сохранённой рабочей копии", panel)
        changes_layout = QtWidgets.QVBoxLayout(changes_box)
        self.input_change_table = QtWidgets.QTableWidget(0, 4, changes_box)
        self.input_change_table.setObjectName("ID-CHANGE-TABLE")
        self.input_change_table.setHorizontalHeaderLabels(("Параметр", "Текущее", "Было", "Ед."))
        self.input_change_table.verticalHeader().setVisible(False)
        self.input_change_table.horizontalHeader().setStretchLastSection(True)
        self.input_change_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.input_change_table.itemActivated.connect(self._on_input_change_activated)
        changes_layout.addWidget(self.input_change_table, 1)
        detail_layout.addWidget(changes_box)

        detail_layout.addStretch(1)
        detail_scroll.setWidget(panel)
        parent.addWidget(detail_scroll)

    def refresh_view(self) -> None:
        super().refresh_view()
        self._refresh_input_editor_controls()

    def _section_specs(self) -> tuple[tuple[str, DesktopInputFieldSpec], ...]:
        rows: list[tuple[str, DesktopInputFieldSpec]] = []
        for section in DESKTOP_INPUT_SECTIONS:
            for spec in section.fields:
                rows.append((section.title, spec))
        return tuple(rows)

    def _format_input_value(self, spec: DesktopInputFieldSpec, payload: dict[str, Any]) -> str:
        value = spec.to_ui(payload.get(spec.key))
        if spec.control == "bool":
            return "да" if bool(value) else "нет"
        if spec.control == "choice":
            return str(value)
        if spec.control in {"int", "slider"}:
            try:
                digits = 0 if spec.control == "int" else max(0, int(spec.digits))
                return f"{float(value):.{digits}f}"
            except Exception:
                return str(value)
        return str(value)

    def _parse_input_value(self, spec: DesktopInputFieldSpec, raw: str) -> Any:
        text = str(raw or "").strip()
        if spec.control == "bool":
            return spec.to_base(text.casefold() in {"1", "true", "yes", "on", "да", "истина"})
        if spec.control == "choice":
            return spec.to_base(text)
        if spec.control == "int":
            return spec.to_base(int(round(float(text.replace(",", ".")))))
        if spec.control == "slider":
            return spec.to_base(float(text.replace(",", ".")))
        return spec.to_base(text)

    def _add_input_table_item(
        self,
        row: int,
        column: int,
        text: str,
        *,
        spec: DesktopInputFieldSpec,
        editable: bool = False,
    ) -> None:
        item = QtWidgets.QTableWidgetItem(text)
        flags = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        if editable:
            flags |= QtCore.Qt.ItemIsEditable
        item.setFlags(flags)
        item.setData(QtCore.Qt.UserRole, spec.key)
        self.input_table.setItem(row, column, item)

    def _input_saved_reference_payload(self) -> dict[str, Any]:
        return load_base_with_defaults(default_working_copy_path())

    def _input_source_label_text(self) -> str:
        source = self._input_source_path
        default_path = default_base_json_path()
        working_path = default_working_copy_path()
        if source == default_path:
            role = "исходный шаблон"
        elif source == working_path:
            role = "рабочая копия"
        else:
            role = "загруженный файл"
        exists = "есть" if source.exists() else "будет создан при сохранении"
        return f"Текущий источник: {role}. Путь: {source}. Состояние файла: {exists}."

    def _render_input_payload(self, payload: Mapping[str, Any], *, selected_key: str = "") -> None:
        self._refreshing_input_table = True
        try:
            self._input_payload = dict(payload or {})
            rows = self._section_specs()
            self.input_table.setRowCount(len(rows))
            selected_row = 0
            for row_index, (section_title, spec) in enumerate(rows):
                if selected_key and spec.key == selected_key:
                    selected_row = row_index
                self._add_input_table_item(row_index, 0, section_title, spec=spec)
                self._add_input_table_item(row_index, 1, spec.label, spec=spec)
                self._add_input_table_item(
                    row_index,
                    2,
                    self._format_input_value(spec, self._input_payload),
                    spec=spec,
                    editable=True,
                )
                self._add_input_table_item(row_index, 3, spec.unit_label or "—", spec=spec)
                self._add_input_table_item(row_index, 4, spec.description, spec=spec)
            self.input_table.resizeColumnsToContents()
            if rows:
                self.input_table.selectRow(min(max(0, selected_row), len(rows) - 1))
        finally:
            self._refreshing_input_table = False

    def _refresh_input_editor_controls(self) -> None:
        if not hasattr(self, "input_table"):
            return
        try:
            self._input_reference_payload = self._input_saved_reference_payload()
            self._input_source_path = default_working_copy_path()
            self._render_input_payload(self._input_reference_payload)
            self._refresh_input_profile_snapshot_lists()
            self._refresh_input_aux_panels()
        except Exception as exc:
            self.input_table.setRowCount(0)
            self.input_action_label.setText(f"Не удалось прочитать исходные данные: {exc}")

    def _gather_input_payload_from_table(self) -> dict[str, Any]:
        payload = load_base_with_defaults()
        spec_by_key = {
            spec.key: spec
            for _section_title, spec in self._section_specs()
        }
        for row_index in range(self.input_table.rowCount()):
            value_item = self.input_table.item(row_index, 2)
            if value_item is None:
                continue
            key = str(value_item.data(QtCore.Qt.UserRole) or "").strip()
            spec = spec_by_key.get(key)
            if spec is None:
                continue
            payload[key] = self._parse_input_value(spec, value_item.text())
        return payload

    def _selected_input_key(self) -> str:
        selected = self.input_table.selectionModel().selectedRows()
        row = int(selected[0].row()) if selected else self.input_table.currentRow()
        if row < 0:
            return ""
        item = self.input_table.item(row, 2) or self.input_table.item(row, 1)
        return str(item.data(QtCore.Qt.UserRole) or "").strip() if item is not None else ""

    def _focus_input_field_by_key(self, key: str) -> bool:
        clean_key = str(key or "").strip()
        if not clean_key:
            return False
        for row_index in range(self.input_table.rowCount()):
            item = self.input_table.item(row_index, 2) or self.input_table.item(row_index, 1)
            if item is not None and str(item.data(QtCore.Qt.UserRole) or "").strip() == clean_key:
                self.input_table.selectRow(row_index)
                self.input_table.scrollToItem(item)
                self.input_table.setFocus(QtCore.Qt.OtherFocusReason)
                self._refresh_input_field_inspector()
                return True
        return False

    def _refresh_input_profile_snapshot_lists(self) -> None:
        if not hasattr(self, "input_profile_combo"):
            return
        self._refreshing_input_aux = True
        try:
            current_profile = self.input_profile_combo.currentData()
            self.input_profile_combo.clear()
            self.input_profile_combo.addItem("— нет выбранного профиля —", userData="")
            self._input_profile_paths = {}
            for path in list_desktop_profile_paths():
                display = desktop_profile_display_name(path)
                self._input_profile_paths[str(path)] = path
                self.input_profile_combo.addItem(display, userData=str(path))
            if current_profile:
                index = self.input_profile_combo.findData(str(current_profile))
                if index >= 0:
                    self.input_profile_combo.setCurrentIndex(index)

            current_snapshot = self.input_snapshot_combo.currentData()
            self.input_snapshot_combo.clear()
            self.input_snapshot_combo.addItem("— нет выбранного снимка —", userData="")
            self._input_snapshot_paths = {}
            for path in list_desktop_snapshot_paths():
                display = desktop_snapshot_display_name(path)
                self._input_snapshot_paths[str(path)] = path
                self.input_snapshot_combo.addItem(display, userData=str(path))
            if current_snapshot:
                index = self.input_snapshot_combo.findData(str(current_snapshot))
                if index >= 0:
                    self.input_snapshot_combo.setCurrentIndex(index)
        finally:
            self._refreshing_input_aux = False

    def _table_item_text(self, value: object) -> QtWidgets.QTableWidgetItem:
        item = QtWidgets.QTableWidgetItem(str(value if value is not None else ""))
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        return item

    def _refresh_input_section_status_table(self, payload: dict[str, Any]) -> None:
        summary_cards = {str(card.get("title") or ""): card for card in build_desktop_section_summary_cards(payload)}
        issue_cards = {str(card.get("title") or ""): card for card in build_desktop_section_issue_cards(payload)}
        change_cards = {
            str(card.get("title") or ""): card
            for card in build_desktop_section_change_cards(payload, self._input_reference_payload)
        }
        self.input_section_status_table.setRowCount(len(DESKTOP_INPUT_SECTIONS))
        for row_index, section in enumerate(DESKTOP_INPUT_SECTIONS):
            title = section.title
            summary = summary_cards.get(title, {})
            issues = issue_cards.get(title, {})
            changes = change_cards.get(title, {})
            focus_key = str(
                issues.get("focus_key")
                or changes.get("focus_key")
                or summary.get("focus_key")
                or ""
            )
            values = (
                title,
                desktop_section_status_label(str(summary.get("status") or "")),
                str(summary.get("headline") or summary.get("details") or ""),
                str(issues.get("summary") or "замечаний нет"),
                str(changes.get("summary") or "без изменений"),
            )
            for column, text in enumerate(values):
                item = self._table_item_text(text)
                item.setData(QtCore.Qt.UserRole, focus_key)
                self.input_section_status_table.setItem(row_index, column, item)
        self.input_section_status_table.resizeColumnsToContents()

    def _refresh_input_change_table(self, payload: dict[str, Any]) -> None:
        diffs = build_desktop_profile_diff(payload, self._input_reference_payload)
        self.input_change_table.setRowCount(len(diffs))
        for row_index, diff in enumerate(diffs):
            key = str(diff.get("key") or "")
            values = (
                str(diff.get("label") or key),
                str(diff.get("current") if diff.get("current") is not None else ""),
                str(diff.get("reference") if diff.get("reference") is not None else ""),
                str(diff.get("unit_label") or ""),
            )
            for column, text in enumerate(values):
                item = self._table_item_text(text)
                item.setData(QtCore.Qt.UserRole, key)
                self.input_change_table.setItem(row_index, column, item)
        self.input_change_table.resizeColumnsToContents()

    def _refresh_input_snapshot_status(self, payload: dict[str, Any]) -> None:
        info = describe_desktop_inputs_snapshot_state(payload)
        banner = str(info.get("banner") or "").strip()
        path = str(info.get("path") or "").strip()
        self.input_snapshot_status_label.setText(
            f"{banner}\nПуть снимка маршрута: {path}" if path else banner
        )
        if hasattr(self, "input_source_label"):
            self.input_source_label.setText(self._input_source_label_text())

    def _refresh_input_field_inspector(self) -> None:
        if not hasattr(self, "input_field_inspector"):
            return
        key = self._selected_input_key()
        specs = field_spec_map()
        spec = specs.get(key)
        payload = self._gather_input_payload_from_table() if hasattr(self, "input_table") else self._input_payload
        if spec is None:
            self.input_field_inspector.setText("Выберите параметр в таблице или через поиск.")
            return
        state = describe_desktop_field_source_state(
            payload,
            self._input_reference_payload,
            key,
            "сохранённая рабочая копия",
        )
        self.input_field_inspector.setText(
            f"{spec.label}\n"
            f"Раздел: {next((title for title, item in self._section_specs() if item.key == key), '—')}\n"
            f"Единица: {spec.unit_label or '—'}\n"
            f"{state.get('marker') or ''}\n"
            f"{spec.description}"
        )

    def _refresh_input_aux_panels(self) -> None:
        if self._refreshing_input_aux or not hasattr(self, "input_section_status_table"):
            return
        try:
            payload = self._gather_input_payload_from_table()
        except Exception:
            payload = dict(self._input_payload or {})
        self._input_payload = dict(payload)
        self._refresh_input_snapshot_status(payload)
        self._refresh_input_section_status_table(payload)
        self._refresh_input_change_table(payload)
        self._refresh_input_field_inspector()
        self._refresh_input_search_results()

    def _refresh_input_search_results(self, *_args: object) -> None:
        if not hasattr(self, "input_search_results"):
            return
        query = self.input_search_edit.text().strip()
        self.input_search_results.clear()
        self._input_search_results = find_desktop_field_matches(query, limit=30) if query else []
        if not self._input_search_results:
            item = QtWidgets.QListWidgetItem(
                "Введите текст поиска: например, колея, давление, шток, стабилизатор."
            )
            item.setFlags(QtCore.Qt.NoItemFlags)
            self.input_search_results.addItem(item)
            return
        for result in self._input_search_results:
            item = QtWidgets.QListWidgetItem(str(result.get("display") or result.get("label") or ""))
            item.setToolTip(str(result.get("description") or ""))
            item.setData(QtCore.Qt.UserRole, str(result.get("key") or ""))
            self.input_search_results.addItem(item)

    def _on_input_search_result_activated(self, item: QtWidgets.QListWidgetItem) -> None:
        key = str(item.data(QtCore.Qt.UserRole) or "").strip()
        if self._focus_input_field_by_key(key):
            self.input_action_label.setText("Параметр найден и выделен в таблице исходных данных.")

    def _on_input_section_status_activated(self, item: QtWidgets.QTableWidgetItem) -> None:
        key = str(item.data(QtCore.Qt.UserRole) or "").strip()
        if key and self._focus_input_field_by_key(key):
            self.input_action_label.setText("Открыт параметр, который требует внимания или изменён.")

    def _on_input_change_activated(self, item: QtWidgets.QTableWidgetItem) -> None:
        key = str(item.data(QtCore.Qt.UserRole) or "").strip()
        if key and self._focus_input_field_by_key(key):
            self.input_action_label.setText("Открыт изменённый параметр.")

    def _on_input_selection_changed(self) -> None:
        if self._refreshing_input_table:
            return
        self._refresh_input_field_inspector()

    def _on_input_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if self._refreshing_input_table or item.column() != 2:
            return
        self._refresh_input_aux_panels()
        self.input_action_label.setText(
            "Есть несохранённые изменения в таблице исходных данных. Сохраните рабочую копию перед переходом дальше."
        )

    def _selected_input_profile_path(self) -> Path | None:
        value = self.input_profile_combo.currentData() if hasattr(self, "input_profile_combo") else ""
        text = str(value or "").strip()
        return Path(text) if text else None

    def _selected_input_snapshot_path(self) -> Path | None:
        value = self.input_snapshot_combo.currentData() if hasattr(self, "input_snapshot_combo") else ""
        text = str(value or "").strip()
        return Path(text) if text else None

    def _apply_input_payload_as_unsaved(self, payload: Mapping[str, Any], message: str) -> None:
        selected_key = self._selected_input_key()
        merged = load_base_with_defaults()
        merged.update(dict(payload or {}))
        self._render_input_payload(merged, selected_key=selected_key)
        self._refresh_input_aux_panels()
        self.input_action_label.setText(message)

    def _load_input_file_path(self, path: Path | str) -> Path:
        target = Path(path).resolve()
        raw = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Файл исходных данных должен быть JSON-объектом: {target}")
        payload = load_base_with_defaults(target)
        self._input_source_path = target
        self._input_reference_payload = dict(payload)
        self._render_input_payload(payload)
        self._refresh_input_aux_panels()
        self.input_action_label.setText(
            f"Файл исходных данных загружен в рабочую форму: {target}. Сохраните рабочую копию перед переходом дальше."
        )
        return target

    def _load_input_json_file(self) -> None:
        path, _selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Открыть файл исходных данных",
            str(self.repo_root),
            "Файлы JSON (*.json);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            self._load_input_file_path(path)
        except Exception as exc:
            self.input_action_label.setText(f"Не удалось загрузить файл исходных данных: {exc}")

    def _save_input_as_path(self, path: Path | str) -> Path:
        target = Path(path).resolve()
        payload = self._gather_input_payload_from_table()
        saved = save_base_payload(target, payload)
        self._input_source_path = saved
        self._input_reference_payload = dict(payload)
        self._refresh_input_aux_panels()
        self.input_action_label.setText(f"Исходные данные сохранены как: {saved}")
        return saved

    def _save_input_as_file(self) -> None:
        path, _selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Сохранить исходные данные как",
            str(self.repo_root / "workspace" / "ui_state" / "desktop_input_base.json"),
            "Файлы JSON (*.json);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            self._save_input_as_path(path)
        except Exception as exc:
            self.input_action_label.setText(f"Не удалось сохранить исходные данные как файл: {exc}")

    def _restore_input_template(self) -> None:
        try:
            payload = load_base_defaults()
            self._input_source_path = default_base_json_path()
            self._input_reference_payload = dict(payload)
            self._render_input_payload(payload)
            self._refresh_input_aux_panels()
            self.input_action_label.setText(
                "Исходный шаблон загружен в рабочую форму без автосохранения. Сохраните рабочую копию, если хотите принять эти значения."
            )
        except Exception as exc:
            self.input_action_label.setText(f"Не удалось восстановить исходный шаблон: {exc}")

    def _apply_input_quick_preset(self) -> None:
        try:
            preset_key = str(self.input_quick_preset_combo.currentData() or "").strip()
            payload = self._gather_input_payload_from_table()
            updated, changed_keys = apply_desktop_quick_preset(payload, preset_key)
            label = quick_preset_label(preset_key)
            description = quick_preset_description(preset_key)
            changed_label = len(changed_keys)
            self._render_input_payload(updated, selected_key=changed_keys[0] if changed_keys else "")
            self._refresh_input_aux_panels()
            self.input_action_label.setText(
                f"Пресет применён: {label}. Изменено параметров: {changed_label}. {description}"
            )
        except Exception as exc:
            self.input_action_label.setText(f"Не удалось применить пресет исходных данных: {exc}")

    def _save_input_profile(self) -> None:
        try:
            payload = self._gather_input_payload_from_table()
            raw_name = self.input_profile_name_edit.text().strip() or "рабочий_вариант"
            target = save_desktop_profile(raw_name, payload)
            self._refresh_input_profile_snapshot_lists()
            index = self.input_profile_combo.findData(str(target))
            if index >= 0:
                self.input_profile_combo.setCurrentIndex(index)
            self.input_action_label.setText(f"Профиль исходных данных сохранён: {target}")
        except Exception as exc:
            self.input_action_label.setText(f"Не удалось сохранить профиль исходных данных: {exc}")

    def _load_input_profile(self) -> None:
        try:
            path = self._selected_input_profile_path()
            if path is None:
                self.input_action_label.setText("Выберите профиль исходных данных для загрузки.")
                return
            payload = load_desktop_profile(path)
            self._apply_input_payload_as_unsaved(
                payload,
                f"Профиль загружен в рабочую форму без автосохранения: {path}",
            )
        except Exception as exc:
            self.input_action_label.setText(f"Не удалось загрузить профиль исходных данных: {exc}")

    def _save_input_snapshot(self) -> None:
        try:
            payload = self._gather_input_payload_from_table()
            raw_name = self.input_snapshot_name_edit.text().strip() or "перед_запуском"
            target = save_desktop_snapshot(raw_name, payload)
            self._refresh_input_profile_snapshot_lists()
            index = self.input_snapshot_combo.findData(str(target))
            if index >= 0:
                self.input_snapshot_combo.setCurrentIndex(index)
            self.input_action_label.setText(f"Снимок исходных данных сохранён: {target}")
        except Exception as exc:
            self.input_action_label.setText(f"Не удалось сохранить снимок исходных данных: {exc}")

    def _load_input_snapshot(self) -> None:
        try:
            path = self._selected_input_snapshot_path()
            if path is None:
                self.input_action_label.setText("Выберите снимок исходных данных для загрузки.")
                return
            payload = load_desktop_snapshot(path)
            self._apply_input_payload_as_unsaved(
                payload,
                f"Снимок загружен в рабочую форму без автосохранения: {path}",
            )
        except Exception as exc:
            self.input_action_label.setText(f"Не удалось загрузить снимок исходных данных: {exc}")

    def _save_input_working_copy(self) -> None:
        try:
            payload = self._gather_input_payload_from_table()
            target = save_base_payload(default_working_copy_path(), payload)
            self._input_payload = dict(payload)
            self._input_reference_payload = dict(payload)
            self._input_source_path = target
            self._refresh_input_aux_panels()
            self.input_action_label.setText(f"Рабочая копия сохранена: {target}")
        except Exception as exc:
            self.input_action_label.setText(f"Не удалось сохранить рабочую копию: {exc}")

    def _save_input_handoff_snapshot(self) -> None:
        try:
            payload = self._gather_input_payload_from_table()
            working_copy = save_base_payload(default_working_copy_path(), payload)
            snapshot = save_desktop_inputs_snapshot(payload, source_path=working_copy)
            self._input_payload = dict(payload)
            self._input_reference_payload = dict(payload)
            self._input_source_path = working_copy
            self._refresh_input_aux_panels()
            self.input_action_label.setText(f"Снимок исходных данных зафиксирован для маршрута: {snapshot}")
        except Exception as exc:
            self.input_action_label.setText(f"Не удалось зафиксировать снимок исходных данных: {exc}")

    def handle_command(self, command_id: str) -> None:
        if command_id == "input.editor.open":
            self._refresh_input_editor_controls()
            self.input_editor_box.setFocus(QtCore.Qt.OtherFocusReason)
            self.input_action_label.setText(
                "Редактирование исходных данных открыто в рабочем шаге. Проверьте таблицу, сохраните рабочую копию и зафиксируйте снимок перед переходом к сценарию."
            )


class RingWorkspacePage(RuntimeWorkspacePage):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        action_commands: Iterable[DesktopShellCommandSpec],
        on_command: Callable[[str], None],
        *,
        repo_root: Path,
        python_executable: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.python_executable = python_executable
        self._ring_spec: dict[str, Any] = {}
        self._ring_source_path: Path | None = None
        self._refreshing_ring_table = False
        self._refreshing_ring_detail = False
        self._ring_detail_row = 0
        self._ring_dirty = False
        self._ring_artifacts_stale = True
        self._ring_last_bundle: dict[str, Any] = {}
        super().__init__(
            workspace,
            action_commands,
            on_command,
            lambda: build_ring_workspace_summary(
                repo_root,
                python_executable=python_executable,
            ),
            parent,
        )
        self.setObjectName("WS-RING-HOSTED-PAGE")

    def _build_extra_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.ring_editor_box = QtWidgets.QGroupBox("Сегменты циклического сценария")
        self.ring_editor_box.setObjectName("RG-SEGMENT-LIST")
        self.ring_editor_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        editor_layout = QtWidgets.QVBoxLayout(self.ring_editor_box)
        editor_layout.setSpacing(8)

        intro = QtWidgets.QLabel(
            "Здесь редактируется основной сценарий кольца: сегменты, длительность, скорость, профиль дороги и события. "
            "После проверки сохраните сценарий и переходите к набору испытаний."
        )
        intro.setWordWrap(True)
        editor_layout.addWidget(intro)

        self.ring_source_label = QtWidgets.QLabel("")
        self.ring_source_label.setObjectName("RG-SOURCE-LABEL")
        self.ring_source_label.setWordWrap(True)
        self.ring_source_label.setStyleSheet("color: #405060;")
        editor_layout.addWidget(self.ring_source_label)

        self.ring_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.ring_splitter.setObjectName("RG-EDITOR-SPLITTER")
        self.ring_splitter.setChildrenCollapsible(False)
        editor_layout.addWidget(self.ring_splitter, 1)

        list_panel = QtWidgets.QWidget(self.ring_splitter)
        list_layout = QtWidgets.QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 8, 0)
        list_layout.setSpacing(8)

        self.ring_segment_table = QtWidgets.QTableWidget(0, 7)
        self.ring_segment_table.setObjectName("RG-SEGMENT-TABLE")
        self.ring_segment_table.setHorizontalHeaderLabels(
            ("#", "Сегмент", "Длительность, с", "Скорость выхода, км/ч", "Манёвр", "Профиль дороги", "События")
        )
        self.ring_segment_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.ring_segment_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.ring_segment_table.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked
            | QtWidgets.QAbstractItemView.EditKeyPressed
            | QtWidgets.QAbstractItemView.SelectedClicked
        )
        self.ring_segment_table.verticalHeader().setVisible(False)
        self.ring_segment_table.horizontalHeader().setStretchLastSection(True)
        self.ring_segment_table.itemChanged.connect(self._on_ring_item_changed)
        self.ring_segment_table.itemSelectionChanged.connect(self._on_ring_selection_changed)
        list_layout.addWidget(self.ring_segment_table, 1)

        actions = QtWidgets.QHBoxLayout()
        self.ring_refresh_button = QtWidgets.QPushButton("Обновить сценарий")
        self.ring_refresh_button.setObjectName("RG-BTN-REFRESH")
        self.ring_refresh_button.clicked.connect(self._refresh_ring_editor_controls)
        actions.addWidget(self.ring_refresh_button)

        self.ring_add_button = QtWidgets.QPushButton("Добавить сегмент")
        self.ring_add_button.setObjectName("RG-BTN-ADD-SEGMENT")
        self.ring_add_button.clicked.connect(self._add_ring_segment)
        actions.addWidget(self.ring_add_button)

        self.ring_dup_button = QtWidgets.QPushButton("Дублировать сегмент")
        self.ring_dup_button.setObjectName("RG-BTN-DUP-SEGMENT")
        self.ring_dup_button.clicked.connect(self._duplicate_ring_segment)
        actions.addWidget(self.ring_dup_button)

        self.ring_delete_button = QtWidgets.QPushButton("Удалить сегмент")
        self.ring_delete_button.setObjectName("RG-BTN-DELETE-SEGMENT")
        self.ring_delete_button.clicked.connect(self._delete_ring_segment)
        actions.addWidget(self.ring_delete_button)

        self.ring_save_button = QtWidgets.QPushButton("Сохранить сценарий")
        self.ring_save_button.setObjectName("RG-BTN-SAVE-SOURCE")
        self.ring_save_button.clicked.connect(self._save_ring_source)
        actions.addWidget(self.ring_save_button)

        self.ring_check_button = QtWidgets.QPushButton("Проверить шов")
        self.ring_check_button.setObjectName("RG-SEAM-DIAGNOSTICS")
        self.ring_check_button.clicked.connect(self._check_ring_source)
        actions.addWidget(self.ring_check_button)
        list_layout.addLayout(actions)

        route_actions = QtWidgets.QHBoxLayout()
        self.ring_to_suite_button = QtWidgets.QPushButton("Перейти к набору испытаний")
        self.ring_to_suite_button.setObjectName("RG-BTN-ADD-TO-SUITE")
        self.ring_to_suite_button.clicked.connect(
            lambda _checked=False: self.on_command("workspace.test_matrix.open")
        )
        route_actions.addWidget(self.ring_to_suite_button)
        list_layout.addLayout(route_actions)

        self.ring_splitter.addWidget(list_panel)
        self._build_ring_detail_panel(self.ring_splitter)
        self.ring_splitter.setStretchFactor(0, 3)
        self.ring_splitter.setStretchFactor(1, 2)
        self.ring_splitter.setSizes((900, 620))

        self.ring_action_label = QtWidgets.QLabel("")
        self.ring_action_label.setObjectName("RG-ACTION-RESULT")
        self.ring_action_label.setWordWrap(True)
        self.ring_action_label.setStyleSheet("color: #576574;")
        editor_layout.addWidget(self.ring_action_label)

        layout.addWidget(self.ring_editor_box)

    def _ring_default_output_dir(self) -> Path:
        return self.repo_root / "runs" / "ring_editor"

    def _add_combo_items(
        self,
        combo: QtWidgets.QComboBox,
        values: Iterable[str],
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        for value in values:
            raw = str(value)
            combo.addItem((labels or {}).get(raw, raw), userData=raw)

    def _set_combo_value(self, combo: QtWidgets.QComboBox, value: object) -> None:
        index = combo.findData(str(value or ""))
        if index < 0:
            index = combo.findText(str(value or ""))
        combo.setCurrentIndex(max(0, index))

    def _combo_value(self, combo: QtWidgets.QComboBox, fallback: str) -> str:
        value = combo.currentData()
        return str(value if value is not None else combo.currentText() or fallback)

    def _new_double_spin(
        self,
        *,
        minimum: float,
        maximum: float,
        decimals: int,
        suffix: str = "",
        object_name: str = "",
    ) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(float(minimum), float(maximum))
        spin.setDecimals(int(decimals))
        spin.setSingleStep(0.1 if decimals else 1.0)
        if suffix:
            spin.setSuffix(suffix)
        if object_name:
            spin.setObjectName(object_name)
        spin.valueChanged.connect(self._on_ring_detail_changed)
        return spin

    def _new_int_spin(
        self,
        *,
        minimum: int,
        maximum: int,
        object_name: str = "",
    ) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setRange(int(minimum), int(maximum))
        if object_name:
            spin.setObjectName(object_name)
        spin.valueChanged.connect(self._on_ring_detail_changed)
        return spin

    def _build_ring_detail_panel(self, parent: QtWidgets.QSplitter) -> None:
        detail_scroll = QtWidgets.QScrollArea()
        detail_scroll.setObjectName("RG-SEGMENT-DETAIL-SCROLL")
        detail_scroll.setWidgetResizable(True)
        panel = QtWidgets.QWidget(detail_scroll)
        panel.setObjectName("RG-SEGMENT-DETAIL")
        detail_layout = QtWidgets.QVBoxLayout(panel)
        detail_layout.setSpacing(10)

        preset_box = QtWidgets.QGroupBox("Пресеты сценария и сегмента", panel)
        preset_layout = QtWidgets.QGridLayout(preset_box)
        self.ring_preset_combo = QtWidgets.QComboBox(preset_box)
        self.ring_preset_combo.setObjectName("RG-RING-PRESET")
        self.ring_preset_combo.addItems(list_ring_preset_names())
        preset_layout.addWidget(QtWidgets.QLabel("Сценарий"), 0, 0)
        preset_layout.addWidget(self.ring_preset_combo, 0, 1)
        self.ring_apply_preset_button = QtWidgets.QPushButton("Применить сценарий", preset_box)
        self.ring_apply_preset_button.setObjectName("RG-BTN-APPLY-RING-PRESET")
        self.ring_apply_preset_button.clicked.connect(self._apply_ring_preset)
        preset_layout.addWidget(self.ring_apply_preset_button, 0, 2)

        self.ring_segment_preset_combo = QtWidgets.QComboBox(preset_box)
        self.ring_segment_preset_combo.setObjectName("RG-SEGMENT-PRESET")
        self.ring_segment_preset_combo.addItems(list_segment_preset_names())
        preset_layout.addWidget(QtWidgets.QLabel("Сегмент"), 1, 0)
        preset_layout.addWidget(self.ring_segment_preset_combo, 1, 1)
        segment_buttons = QtWidgets.QHBoxLayout()
        self.ring_apply_segment_preset_button = QtWidgets.QPushButton("Заменить сегмент", preset_box)
        self.ring_apply_segment_preset_button.setObjectName("RG-BTN-APPLY-SEGMENT-PRESET")
        self.ring_apply_segment_preset_button.clicked.connect(self._apply_segment_preset)
        segment_buttons.addWidget(self.ring_apply_segment_preset_button)
        self.ring_insert_segment_preset_button = QtWidgets.QPushButton("Вставить сегмент", preset_box)
        self.ring_insert_segment_preset_button.setObjectName("RG-BTN-INSERT-SEGMENT-PRESET")
        self.ring_insert_segment_preset_button.clicked.connect(self._insert_segment_preset)
        segment_buttons.addWidget(self.ring_insert_segment_preset_button)
        preset_layout.addLayout(segment_buttons, 1, 2)
        detail_layout.addWidget(preset_box)

        global_box = QtWidgets.QGroupBox("Параметры кольца", panel)
        global_form = QtWidgets.QFormLayout(global_box)
        self.ring_closure_combo = QtWidgets.QComboBox(global_box)
        self.ring_closure_combo.setObjectName("RG-CLOSURE-POLICY")
        self._add_combo_items(self.ring_closure_combo, CLOSURE_POLICIES)
        self.ring_closure_combo.currentIndexChanged.connect(self._on_ring_detail_changed)
        global_form.addRow("Замыкание", self.ring_closure_combo)
        self.ring_v0_spin = self._new_double_spin(minimum=0.0, maximum=300.0, decimals=2, suffix=" км/ч", object_name="RG-V0-KPH")
        global_form.addRow("Стартовая скорость", self.ring_v0_spin)
        self.ring_laps_spin = self._new_int_spin(minimum=1, maximum=100, object_name="RG-N-LAPS")
        global_form.addRow("Кругов", self.ring_laps_spin)
        self.ring_dx_spin = self._new_double_spin(minimum=0.001, maximum=5.0, decimals=4, suffix=" м", object_name="RG-DX-M")
        global_form.addRow("Шаг дороги dx", self.ring_dx_spin)
        self.ring_dt_spin = self._new_double_spin(minimum=0.001, maximum=1.0, decimals=4, suffix=" с", object_name="RG-DT-S")
        global_form.addRow("Шаг расчёта dt", self.ring_dt_spin)
        detail_layout.addWidget(global_box)

        segment_box = QtWidgets.QGroupBox("Карточка выбранного сегмента", panel)
        segment_form = QtWidgets.QFormLayout(segment_box)
        self.ring_detail_name_edit = QtWidgets.QLineEdit(segment_box)
        self.ring_detail_name_edit.setObjectName("RG-SEGMENT-NAME")
        self.ring_detail_name_edit.textEdited.connect(self._on_ring_detail_changed)
        segment_form.addRow("Название", self.ring_detail_name_edit)
        self.ring_detail_duration_spin = self._new_double_spin(minimum=0.05, maximum=3600.0, decimals=3, suffix=" с", object_name="RG-SEGMENT-DURATION-S")
        segment_form.addRow("Длительность", self.ring_detail_duration_spin)
        self.ring_detail_speed_spin = self._new_double_spin(minimum=0.0, maximum=300.0, decimals=2, suffix=" км/ч", object_name="RG-SEGMENT-SPEED-END-KPH")
        segment_form.addRow("Скорость в конце", self.ring_detail_speed_spin)
        self.ring_detail_turn_combo = QtWidgets.QComboBox(segment_box)
        self.ring_detail_turn_combo.setObjectName("RG-SEGMENT-TURN")
        self._add_combo_items(
            self.ring_detail_turn_combo,
            TURN_DIRECTIONS,
            labels={"STRAIGHT": "Прямо", "LEFT": "Влево", "RIGHT": "Вправо"},
        )
        self.ring_detail_turn_combo.currentIndexChanged.connect(self._on_ring_detail_changed)
        segment_form.addRow("Манёвр", self.ring_detail_turn_combo)
        self.ring_detail_passage_combo = QtWidgets.QComboBox(segment_box)
        self.ring_detail_passage_combo.setObjectName("RG-SEGMENT-PASSAGE")
        self._add_combo_items(
            self.ring_detail_passage_combo,
            PASSAGE_MODES,
            labels={"steady": "постоянно", "accel": "разгон", "brake": "торможение", "custom": "вручную"},
        )
        self.ring_detail_passage_combo.currentIndexChanged.connect(self._on_ring_detail_changed)
        segment_form.addRow("Продольный режим", self.ring_detail_passage_combo)
        self.ring_detail_turn_radius_spin = self._new_double_spin(minimum=0.0, maximum=10000.0, decimals=2, suffix=" м", object_name="RG-SEGMENT-TURN-RADIUS-M")
        segment_form.addRow("Радиус поворота", self.ring_detail_turn_radius_spin)
        detail_layout.addWidget(segment_box)

        road_box = QtWidgets.QGroupBox("Профиль дороги и поперечный уклон", panel)
        road_form = QtWidgets.QFormLayout(road_box)
        self.ring_road_mode_combo = QtWidgets.QComboBox(road_box)
        self.ring_road_mode_combo.setObjectName("RG-ROAD-MODE")
        self._add_combo_items(self.ring_road_mode_combo, ROAD_MODES, labels={"ISO8608": "ISO 8608", "SINE": "Синусоида"})
        self.ring_road_mode_combo.currentIndexChanged.connect(self._on_ring_detail_changed)
        road_form.addRow("Тип профиля", self.ring_road_mode_combo)
        self.ring_center_start_spin = self._new_double_spin(minimum=-1000.0, maximum=1000.0, decimals=2, suffix=" мм", object_name="RG-CENTER-START-MM")
        road_form.addRow("Высота в начале", self.ring_center_start_spin)
        self.ring_center_end_spin = self._new_double_spin(minimum=-1000.0, maximum=1000.0, decimals=2, suffix=" мм", object_name="RG-CENTER-END-MM")
        road_form.addRow("Высота в конце", self.ring_center_end_spin)
        self.ring_cross_start_spin = self._new_double_spin(minimum=-30.0, maximum=30.0, decimals=3, suffix=" %", object_name="RG-CROSSFALL-START-PCT")
        road_form.addRow("Поперечный уклон в начале", self.ring_cross_start_spin)
        self.ring_cross_end_spin = self._new_double_spin(minimum=-30.0, maximum=30.0, decimals=3, suffix=" %", object_name="RG-CROSSFALL-END-PCT")
        road_form.addRow("Поперечный уклон в конце", self.ring_cross_end_spin)
        self.ring_iso_class_combo = QtWidgets.QComboBox(road_box)
        self.ring_iso_class_combo.setObjectName("RG-ISO-CLASS")
        self._add_combo_items(self.ring_iso_class_combo, ISO_CLASSES)
        self.ring_iso_class_combo.currentIndexChanged.connect(self._on_ring_detail_changed)
        road_form.addRow("Класс ISO", self.ring_iso_class_combo)
        self.ring_gd_pick_combo = QtWidgets.QComboBox(road_box)
        self.ring_gd_pick_combo.setObjectName("RG-GD-PICK")
        self._add_combo_items(self.ring_gd_pick_combo, GD_PICKS, labels={"lower": "нижняя", "mid": "средняя", "upper": "верхняя"})
        self.ring_gd_pick_combo.currentIndexChanged.connect(self._on_ring_detail_changed)
        road_form.addRow("Уровень неровности", self.ring_gd_pick_combo)
        self.ring_sine_amp_left_spin = self._new_double_spin(minimum=0.0, maximum=1000.0, decimals=2, suffix=" мм", object_name="RG-SINE-AMP-L-MM")
        road_form.addRow("Синус L амплитуда", self.ring_sine_amp_left_spin)
        self.ring_sine_amp_right_spin = self._new_double_spin(minimum=0.0, maximum=1000.0, decimals=2, suffix=" мм", object_name="RG-SINE-AMP-R-MM")
        road_form.addRow("Синус R амплитуда", self.ring_sine_amp_right_spin)
        self.ring_sine_lambda_left_spin = self._new_double_spin(minimum=0.01, maximum=1000.0, decimals=3, suffix=" м", object_name="RG-SINE-LAMBDA-L-M")
        road_form.addRow("Синус L длина волны", self.ring_sine_lambda_left_spin)
        self.ring_sine_lambda_right_spin = self._new_double_spin(minimum=0.01, maximum=1000.0, decimals=3, suffix=" м", object_name="RG-SINE-LAMBDA-R-M")
        road_form.addRow("Синус R длина волны", self.ring_sine_lambda_right_spin)
        detail_layout.addWidget(road_box)

        events_box = QtWidgets.QGroupBox("События сегмента", panel)
        events_layout = QtWidgets.QVBoxLayout(events_box)
        self.ring_events_table = QtWidgets.QTableWidget(0, 6, events_box)
        self.ring_events_table.setObjectName("RG-EVENTS-TABLE")
        self.ring_events_table.setHorizontalHeaderLabels(("Тип", "Сторона", "Начало, м", "Длина, м", "Высота/глубина, мм", "Пандус, м"))
        self.ring_events_table.verticalHeader().setVisible(False)
        self.ring_events_table.horizontalHeader().setStretchLastSection(True)
        self.ring_events_table.itemChanged.connect(self._on_ring_event_item_changed)
        events_layout.addWidget(self.ring_events_table)
        event_buttons = QtWidgets.QHBoxLayout()
        self.ring_add_event_button = QtWidgets.QPushButton("Добавить событие", events_box)
        self.ring_add_event_button.setObjectName("RG-BTN-ADD-EVENT")
        self.ring_add_event_button.clicked.connect(self._add_ring_event)
        event_buttons.addWidget(self.ring_add_event_button)
        self.ring_delete_event_button = QtWidgets.QPushButton("Удалить событие", events_box)
        self.ring_delete_event_button.setObjectName("RG-BTN-DELETE-EVENT")
        self.ring_delete_event_button.clicked.connect(self._delete_ring_event)
        event_buttons.addWidget(self.ring_delete_event_button)
        events_layout.addLayout(event_buttons)
        detail_layout.addWidget(events_box)

        export_box = QtWidgets.QGroupBox("Источник истины и файлы сценария", panel)
        export_layout = QtWidgets.QVBoxLayout(export_box)
        self.ring_export_status_label = QtWidgets.QLabel("", export_box)
        self.ring_export_status_label.setObjectName("RG-EXPORT-STATUS")
        self.ring_export_status_label.setWordWrap(True)
        export_layout.addWidget(self.ring_export_status_label)
        export_form = QtWidgets.QFormLayout()
        self.ring_output_dir_edit = QtWidgets.QLineEdit(str(self._ring_default_output_dir()), export_box)
        self.ring_output_dir_edit.setObjectName("RG-OUTPUT-DIR")
        self.ring_output_dir_edit.textEdited.connect(self._on_ring_export_target_changed)
        export_form.addRow("Папка выгрузки", self.ring_output_dir_edit)
        self.ring_export_tag_edit = QtWidgets.QLineEdit("ring", export_box)
        self.ring_export_tag_edit.setObjectName("RG-EXPORT-TAG")
        self.ring_export_tag_edit.textEdited.connect(self._on_ring_export_target_changed)
        export_form.addRow("Тег файлов", self.ring_export_tag_edit)
        export_layout.addLayout(export_form)
        export_buttons = QtWidgets.QHBoxLayout()
        self.ring_export_button = QtWidgets.QPushButton("Пересобрать файлы сценария", export_box)
        self.ring_export_button.setObjectName("RG-BTN-EXPORT-BUNDLE")
        self.ring_export_button.clicked.connect(self._export_ring_artifacts)
        export_buttons.addWidget(self.ring_export_button)
        self.ring_open_output_button = QtWidgets.QPushButton("Открыть папку выгрузки", export_box)
        self.ring_open_output_button.setObjectName("RG-BTN-OPEN-OUTPUT")
        self.ring_open_output_button.clicked.connect(self._open_ring_output_dir)
        export_buttons.addWidget(self.ring_open_output_button)
        export_layout.addLayout(export_buttons)
        self.ring_bundle_table = QtWidgets.QTableWidget(0, 2, export_box)
        self.ring_bundle_table.setObjectName("RG-BUNDLE-TABLE")
        self.ring_bundle_table.setHorizontalHeaderLabels(("Файл", "Путь"))
        self.ring_bundle_table.verticalHeader().setVisible(False)
        self.ring_bundle_table.horizontalHeader().setStretchLastSection(True)
        export_layout.addWidget(self.ring_bundle_table)
        detail_layout.addWidget(export_box)

        self.ring_diagnostics_text = QtWidgets.QPlainTextEdit(panel)
        self.ring_diagnostics_text.setObjectName("RG-DIAGNOSTICS-SUMMARY")
        self.ring_diagnostics_text.setReadOnly(True)
        self.ring_diagnostics_text.setMinimumHeight(120)
        detail_layout.addWidget(self.ring_diagnostics_text)
        detail_layout.addStretch(1)

        detail_scroll.setWidget(panel)
        parent.addWidget(detail_scroll)

    def refresh_view(self) -> None:
        super().refresh_view()
        self._refresh_ring_editor_controls()

    def _default_ring_source_path(self) -> Path:
        return self.repo_root / "pneumo_solver_ui" / "workspace" / "ring_source_of_truth.json"

    def _load_ring_spec(self) -> None:
        spec, source_path, _source_kind = _load_ring_spec_for_workspace(self.repo_root)
        self._ring_spec = normalize_spec(spec)
        self._ring_source_path = source_path if source_path is not None else self._default_ring_source_path()
        self._ring_dirty = False

    def _selected_ring_row(self) -> int:
        selected = self.ring_segment_table.selectionModel().selectedRows()
        if not selected:
            return max(0, self.ring_segment_table.currentRow())
        return int(selected[0].row())

    def _ring_segments(self) -> list[dict[str, Any]]:
        return get_segments(self._ring_spec)

    def _selected_ring_segment(self) -> dict[str, Any] | None:
        segments = self._ring_segments()
        if not segments:
            return None
        row = min(max(0, self._selected_ring_row()), len(segments) - 1)
        return segments[row]

    def _apply_ring_global_controls_to_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        if not hasattr(self, "ring_closure_combo"):
            return spec
        spec["closure_policy"] = self._combo_value(self.ring_closure_combo, "closed_c1_periodic")
        spec["v0_kph"] = float(self.ring_v0_spin.value())
        spec["n_laps"] = int(self.ring_laps_spin.value())
        spec["dx_m"] = float(self.ring_dx_spin.value())
        spec["dt_s"] = float(self.ring_dt_spin.value())
        return spec

    def _apply_ring_detail_to_spec(self, *, row: int | None = None) -> None:
        if not hasattr(self, "ring_detail_name_edit"):
            return
        segments = self._ring_segments()
        if not segments:
            return
        row_index = self._ring_detail_row if row is None else int(row)
        row_index = min(max(0, row_index), len(segments) - 1)
        segment = segments[row_index]
        segment["name"] = " ".join(self.ring_detail_name_edit.text().split()) or f"S{row_index + 1}"
        segment["duration_s"] = float(self.ring_detail_duration_spin.value())
        segment["speed_end_kph"] = float(self.ring_detail_speed_spin.value())
        segment["turn_direction"] = self._combo_value(self.ring_detail_turn_combo, "STRAIGHT").upper()
        segment["passage_mode"] = self._combo_value(self.ring_detail_passage_combo, "steady")
        segment["turn_radius_m"] = float(self.ring_detail_turn_radius_spin.value())
        road = dict(segment.get("road", {}) or {})
        road["mode"] = self._combo_value(self.ring_road_mode_combo, "ISO8608").upper()
        road["center_height_start_mm"] = float(self.ring_center_start_spin.value())
        road["center_height_end_mm"] = float(self.ring_center_end_spin.value())
        road["cross_slope_start_pct"] = float(self.ring_cross_start_spin.value())
        road["cross_slope_end_pct"] = float(self.ring_cross_end_spin.value())
        road["iso_class"] = self._combo_value(self.ring_iso_class_combo, "E").upper()
        road["gd_pick"] = self._combo_value(self.ring_gd_pick_combo, "mid")
        road["aL_mm"] = float(self.ring_sine_amp_left_spin.value())
        road["aR_mm"] = float(self.ring_sine_amp_right_spin.value())
        road["lambdaL_m"] = float(self.ring_sine_lambda_left_spin.value())
        road["lambdaR_m"] = float(self.ring_sine_lambda_right_spin.value())
        segment["road"] = road
        self._apply_events_table_to_segment(segment)
        ensure_road_defaults(segment)
        segments[row_index] = segment
        self._ring_spec["segments"] = segments

    def _apply_events_table_to_segment(self, segment: dict[str, Any]) -> None:
        if not hasattr(self, "ring_events_table") or self._refreshing_ring_detail:
            return
        events: list[dict[str, Any]] = []
        for row_index in range(self.ring_events_table.rowCount()):
            def cell(column: int) -> str:
                item = self.ring_events_table.item(row_index, column)
                return item.text().strip() if item is not None else ""

            kind = cell(0) or "яма"
            side = cell(1) or "left"
            if kind not in EVENT_KINDS:
                kind = "яма"
            if side not in EVENT_SIDES:
                side = "left"
            events.append(
                {
                    "kind": kind,
                    "side": side,
                    "start_m": max(0.0, safe_float(cell(2).replace(",", "."), 0.0)),
                    "length_m": max(0.001, safe_float(cell(3).replace(",", "."), 0.4)),
                    "depth_mm": safe_float(cell(4).replace(",", "."), -25.0),
                    "ramp_m": max(0.0, safe_float(cell(5).replace(",", "."), 0.1)),
                }
            )
        segment["events"] = events

    def _populate_ring_events_table(self, segment: dict[str, Any]) -> None:
        self._refreshing_ring_detail = True
        try:
            events = [dict(item) for item in list(segment.get("events", []) or []) if isinstance(item, dict)]
            self.ring_events_table.setRowCount(len(events))
            for row_index, event in enumerate(events):
                values = (
                    str(event.get("kind") or "яма"),
                    str(event.get("side") or "left"),
                    f"{safe_float(event.get('start_m', 0.0), 0.0):.3f}",
                    f"{safe_float(event.get('length_m', 0.4), 0.4):.3f}",
                    f"{safe_float(event.get('depth_mm', -25.0), -25.0):.2f}",
                    f"{safe_float(event.get('ramp_m', 0.1), 0.1):.3f}",
                )
                for column, value in enumerate(values):
                    self.ring_events_table.setItem(row_index, column, QtWidgets.QTableWidgetItem(value))
            self.ring_events_table.resizeColumnsToContents()
        finally:
            self._refreshing_ring_detail = False

    def _refresh_ring_detail_controls(self, *, diagnostics: Any | None = None) -> None:
        if not hasattr(self, "ring_detail_name_edit"):
            return
        segments = self._ring_segments()
        self._ring_detail_row = min(max(0, self._selected_ring_row()), max(0, len(segments) - 1))
        segment = segments[self._ring_detail_row] if segments else None
        self._refreshing_ring_detail = True
        try:
            self._set_combo_value(self.ring_closure_combo, self._ring_spec.get("closure_policy", "closed_c1_periodic"))
            self.ring_v0_spin.setValue(safe_float(self._ring_spec.get("v0_kph", 40.0), 40.0))
            self.ring_laps_spin.setValue(max(1, safe_int(self._ring_spec.get("n_laps", 1), 1)))
            self.ring_dx_spin.setValue(max(0.001, safe_float(self._ring_spec.get("dx_m", 0.02), 0.02)))
            self.ring_dt_spin.setValue(max(0.001, safe_float(self._ring_spec.get("dt_s", 0.01), 0.01)))
            if segment is None:
                self.ring_detail_name_edit.clear()
                self.ring_events_table.setRowCount(0)
                return
            road = ensure_road_defaults(segment)
            self.ring_detail_name_edit.setText(str(segment.get("name") or f"S{self._ring_detail_row + 1}"))
            self.ring_detail_duration_spin.setValue(max(0.05, safe_float(segment.get("duration_s", 3.0), 3.0)))
            self.ring_detail_speed_spin.setValue(max(0.0, safe_float(segment.get("speed_end_kph", 40.0), 40.0)))
            self._set_combo_value(self.ring_detail_turn_combo, str(segment.get("turn_direction") or "STRAIGHT").upper())
            self._set_combo_value(self.ring_detail_passage_combo, str(segment.get("passage_mode") or "steady"))
            self.ring_detail_turn_radius_spin.setValue(max(0.0, safe_float(segment.get("turn_radius_m", 0.0), 0.0)))
            self._set_combo_value(self.ring_road_mode_combo, str(road.get("mode") or "ISO8608").upper())
            self.ring_center_start_spin.setValue(safe_float(road.get("center_height_start_mm", 0.0), 0.0))
            self.ring_center_end_spin.setValue(safe_float(road.get("center_height_end_mm", 0.0), 0.0))
            self.ring_cross_start_spin.setValue(safe_float(road.get("cross_slope_start_pct", 0.0), 0.0))
            self.ring_cross_end_spin.setValue(safe_float(road.get("cross_slope_end_pct", 0.0), 0.0))
            self._set_combo_value(self.ring_iso_class_combo, str(road.get("iso_class") or "E").upper())
            self._set_combo_value(self.ring_gd_pick_combo, str(road.get("gd_pick") or "mid"))
            self.ring_sine_amp_left_spin.setValue(max(0.0, safe_float(road.get("aL_mm", 50.0), 50.0)))
            self.ring_sine_amp_right_spin.setValue(max(0.0, safe_float(road.get("aR_mm", 50.0), 50.0)))
            self.ring_sine_lambda_left_spin.setValue(max(0.01, safe_float(road.get("lambdaL_m", 1.5), 1.5)))
            self.ring_sine_lambda_right_spin.setValue(max(0.01, safe_float(road.get("lambdaR_m", 1.5), 1.5)))
        finally:
            self._refreshing_ring_detail = False
        if segment is not None:
            self._populate_ring_events_table(segment)
        self._refresh_ring_source_and_export_status(diagnostics=diagnostics)

    def _refresh_ring_source_and_export_status(self, *, diagnostics: Any | None = None) -> None:
        if not hasattr(self, "ring_export_status_label"):
            return
        if diagnostics is None:
            try:
                diagnostics = build_ring_editor_diagnostics(self._ring_spec)
            except Exception:
                diagnostics = None
        source_state = "есть несохранённые изменения" if self._ring_dirty else "сохранён"
        artifact_state = "требуется пересборка" if self._ring_artifacts_stale else "актуальны"
        output_dir = self.ring_output_dir_edit.text().strip() if hasattr(self, "ring_output_dir_edit") else ""
        metrics = getattr(diagnostics, "metrics", {}) if diagnostics is not None else {}
        self.ring_export_status_label.setText(
            "Источник истины: "
            f"{self._ring_source_path or self._default_ring_source_path()} | "
            f"сценарий: {source_state} | файлы сценария: {artifact_state} | "
            f"папка выгрузки: {output_dir or self._ring_default_output_dir()} | "
            f"длина круга: {float(metrics.get('ring_length_m', 0.0) or 0.0):.2f} м | "
            f"макс. шов: {float(metrics.get('seam_max_mm', 0.0) or 0.0):.2f} мм"
        )
        if hasattr(self, "ring_diagnostics_text"):
            summary = getattr(diagnostics, "summary_text", "") if diagnostics is not None else ""
            self.ring_diagnostics_text.setPlainText(summary or "Сводка проверки пока недоступна.")

    def _on_ring_detail_changed(self, *_args: object) -> None:
        if self._refreshing_ring_detail or self._refreshing_ring_table:
            return
        try:
            self._apply_ring_detail_to_spec()
            self._apply_ring_global_controls_to_spec(self._ring_spec)
            self._mark_ring_dirty(
                "Есть несохранённые изменения в карточке сегмента. Сохраните сценарий и пересоберите файлы сценария."
            )
            self._render_current_ring_spec(selected_row=self._ring_detail_row)
        except Exception as exc:
            self.ring_action_label.setText(f"Не удалось применить изменение сегмента: {exc}")

    def _on_ring_event_item_changed(self, _item: QtWidgets.QTableWidgetItem) -> None:
        if self._refreshing_ring_detail or self._refreshing_ring_table:
            return
        self._on_ring_detail_changed()

    def _on_ring_selection_changed(self) -> None:
        if self._refreshing_ring_table:
            return
        try:
            self._apply_ring_detail_to_spec(row=self._ring_detail_row)
        except Exception:
            pass
        self._ring_detail_row = self._selected_ring_row()
        self._refresh_ring_detail_controls()

    def _on_ring_export_target_changed(self, *_args: object) -> None:
        if self._refreshing_ring_detail:
            return
        self._ring_artifacts_stale = True
        self._refresh_ring_source_and_export_status()

    def _ring_table_item(
        self,
        row: int,
        column: int,
        text: str,
        *,
        editable: bool = False,
    ) -> None:
        item = QtWidgets.QTableWidgetItem(text)
        flags = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        if editable:
            flags |= QtCore.Qt.ItemIsEditable
        item.setFlags(flags)
        self.ring_segment_table.setItem(row, column, item)

    def _refresh_ring_editor_controls(self) -> None:
        if not hasattr(self, "ring_segment_table"):
            return
        self._refreshing_ring_table = True
        try:
            self._load_ring_spec()
            rows = build_segment_flow_rows(self._ring_spec)
            diagnostics = build_ring_editor_diagnostics(self._ring_spec)
            self.ring_source_label.setText(
                f"Основной файл сценария: {self._ring_source_path}. Ошибки проверки {len(diagnostics.errors)}; предупреждения {len(diagnostics.warnings)}."
            )
            self.ring_segment_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                self._ring_table_item(row_index, 0, str(row_index + 1))
                self._ring_table_item(row_index, 1, str(row.get("name") or f"S{row_index + 1}"), editable=True)
                self._ring_table_item(row_index, 2, f"{float(row.get('duration_s', 0.0) or 0.0):.3f}", editable=True)
                self._ring_table_item(row_index, 3, f"{float(row.get('speed_end_kph', 0.0) or 0.0):.2f}", editable=True)
                self._ring_table_item(row_index, 4, str(row.get("turn_direction") or "STRAIGHT"), editable=True)
                self._ring_table_item(row_index, 5, str(row.get("road_mode") or "ISO8608"), editable=True)
                self._ring_table_item(row_index, 6, str(int(row.get("event_count", 0) or 0)))
            self.ring_segment_table.resizeColumnsToContents()
            if rows:
                self.ring_segment_table.selectRow(min(self._ring_detail_row, len(rows) - 1))
            self._refresh_ring_detail_controls(diagnostics=diagnostics)
        except Exception as exc:
            self.ring_segment_table.setRowCount(0)
            self.ring_action_label.setText(f"Не удалось прочитать циклический сценарий: {exc}")
        finally:
            self._refreshing_ring_table = False

    def _apply_ring_table_to_spec(self) -> dict[str, Any]:
        spec = normalize_spec(copy.deepcopy(self._ring_spec))
        segments = get_segments(spec)
        for row_index in range(min(self.ring_segment_table.rowCount(), len(segments))):
            segment = segments[row_index]
            name_item = self.ring_segment_table.item(row_index, 1)
            duration_item = self.ring_segment_table.item(row_index, 2)
            speed_item = self.ring_segment_table.item(row_index, 3)
            turn_item = self.ring_segment_table.item(row_index, 4)
            road_item = self.ring_segment_table.item(row_index, 5)
            if name_item is not None:
                segment["name"] = " ".join(name_item.text().split()) or f"S{row_index + 1}"
            if duration_item is not None:
                segment["duration_s"] = max(0.05, safe_float(duration_item.text().replace(",", "."), segment.get("duration_s", 3.0)))
            if speed_item is not None:
                segment["speed_end_kph"] = max(0.0, safe_float(speed_item.text().replace(",", "."), segment.get("speed_end_kph", 40.0)))
            if turn_item is not None:
                turn = str(turn_item.text() or "").strip().upper()
                segment["turn_direction"] = turn if turn in TURN_DIRECTIONS else str(segment.get("turn_direction") or "STRAIGHT")
            road = ensure_road_defaults(segment)
            if road_item is not None:
                mode = str(road_item.text() or "").strip().upper()
                road["mode"] = mode if mode in ROAD_MODES else str(road.get("mode") or "ISO8608")
                segment["road"] = ensure_road_defaults(segment)
        spec["segments"] = segments
        self._apply_ring_global_controls_to_spec(spec)
        return normalize_spec(spec)

    def _mark_ring_dirty(self, message: str) -> None:
        self._ring_dirty = True
        self._ring_artifacts_stale = True
        self.ring_action_label.setText(message)
        self._refresh_ring_source_and_export_status()

    def _on_ring_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if self._refreshing_ring_table or item.column() not in {1, 2, 3, 4, 5}:
            return
        self._mark_ring_dirty(
            "Есть несохранённые изменения в сценарии. Сохраните основной файл перед переходом к набору испытаний."
        )

    def _add_ring_segment(self) -> None:
        self._ring_spec = self._apply_ring_table_to_spec()
        self._apply_ring_detail_to_spec()
        segments = self._ring_segments()
        insert_at = min(max(0, self._selected_ring_row()) + 1, len(segments))
        segments.insert(insert_at, build_blank_segment(seed=safe_int(self._ring_spec.get("seed", 123), 123)))
        self._mark_ring_dirty("Добавлен новый сегмент. Проверьте длительность, скорость и профиль дороги.")
        self._render_current_ring_spec(selected_row=insert_at)

    def _duplicate_ring_segment(self) -> None:
        self._ring_spec = self._apply_ring_table_to_spec()
        self._apply_ring_detail_to_spec()
        segments = self._ring_segments()
        if not segments:
            self._add_ring_segment()
            return
        source_index = min(max(0, self._selected_ring_row()), len(segments) - 1)
        segments.insert(source_index + 1, clone_segment(segments[source_index]))
        self._mark_ring_dirty("Сегмент продублирован. Сохраните сценарий после проверки.")
        self._render_current_ring_spec(selected_row=source_index + 1)

    def _delete_ring_segment(self) -> None:
        self._ring_spec = self._apply_ring_table_to_spec()
        self._apply_ring_detail_to_spec()
        segments = self._ring_segments()
        if len(segments) <= 1:
            self.ring_action_label.setText("В циклическом сценарии должен остаться хотя бы один сегмент.")
            return
        delete_at = min(max(0, self._selected_ring_row()), len(segments) - 1)
        segments.pop(delete_at)
        self._mark_ring_dirty("Сегмент удалён. Сохраните сценарий после проверки маршрута.")
        self._render_current_ring_spec(selected_row=max(0, delete_at - 1))

    def _apply_ring_preset(self) -> None:
        preset_name = self.ring_preset_combo.currentText().strip()
        try:
            seed = safe_int(self._ring_spec.get("seed", 123), 123)
            self._ring_spec = build_ring_preset(preset_name, seed=seed)
            self._ring_detail_row = 0
            self._mark_ring_dirty(f"Применён пресет сценария: {preset_name}. Сохраните источник истины и пересоберите файлы.")
            self._render_current_ring_spec(selected_row=0)
        except Exception as exc:
            self.ring_action_label.setText(f"Не удалось применить пресет сценария: {exc}")

    def _apply_segment_preset(self) -> None:
        preset_name = self.ring_segment_preset_combo.currentText().strip()
        try:
            self._ring_spec = self._apply_ring_table_to_spec()
            segments = self._ring_segments()
            if not segments:
                return
            row = min(max(0, self._selected_ring_row()), len(segments) - 1)
            current_uid = str(segments[row].get("uid") or "")
            segment = build_segment_preset(preset_name, seed=safe_int(self._ring_spec.get("seed", 123), 123))
            if current_uid:
                segment["uid"] = current_uid
            segments[row] = segment
            self._mark_ring_dirty(f"Текущий сегмент заменён пресетом: {preset_name}.")
            self._render_current_ring_spec(selected_row=row)
        except Exception as exc:
            self.ring_action_label.setText(f"Не удалось применить пресет сегмента: {exc}")

    def _insert_segment_preset(self) -> None:
        preset_name = self.ring_segment_preset_combo.currentText().strip()
        try:
            self._ring_spec = self._apply_ring_table_to_spec()
            self._apply_ring_detail_to_spec()
            segments = self._ring_segments()
            insert_at = min(max(0, self._selected_ring_row()) + 1, len(segments))
            segment = build_segment_preset(preset_name, seed=safe_int(self._ring_spec.get("seed", 123), 123))
            segments.insert(insert_at, segment)
            self._mark_ring_dirty(f"Вставлен новый сегмент из пресета: {preset_name}.")
            self._render_current_ring_spec(selected_row=insert_at)
        except Exception as exc:
            self.ring_action_label.setText(f"Не удалось вставить пресет сегмента: {exc}")

    def _add_ring_event(self) -> None:
        try:
            self._apply_ring_detail_to_spec()
            segment = self._selected_ring_segment()
            if segment is None:
                return
            events = list(segment.get("events", []) or [])
            events.append(build_blank_event())
            segment["events"] = events
            self._mark_ring_dirty("Добавлено событие сегмента. Проверьте сторону, длину и высоту/глубину.")
            self._populate_ring_events_table(segment)
            self._render_current_ring_spec(selected_row=self._selected_ring_row())
        except Exception as exc:
            self.ring_action_label.setText(f"Не удалось добавить событие: {exc}")

    def _delete_ring_event(self) -> None:
        try:
            self._apply_ring_detail_to_spec()
            segment = self._selected_ring_segment()
            if segment is None:
                return
            events = list(segment.get("events", []) or [])
            selected = self.ring_events_table.selectionModel().selectedRows()
            row = int(selected[0].row()) if selected else self.ring_events_table.currentRow()
            if 0 <= row < len(events):
                events.pop(row)
                segment["events"] = events
                self._mark_ring_dirty("Событие удалено из выбранного сегмента.")
                self._populate_ring_events_table(segment)
                self._render_current_ring_spec(selected_row=self._selected_ring_row())
        except Exception as exc:
            self.ring_action_label.setText(f"Не удалось удалить событие: {exc}")

    def _render_current_ring_spec(self, *, selected_row: int = 0) -> None:
        self._refreshing_ring_table = True
        try:
            rows = build_segment_flow_rows(self._ring_spec)
            self.ring_segment_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                self._ring_table_item(row_index, 0, str(row_index + 1))
                self._ring_table_item(row_index, 1, str(row.get("name") or f"S{row_index + 1}"), editable=True)
                self._ring_table_item(row_index, 2, f"{float(row.get('duration_s', 0.0) or 0.0):.3f}", editable=True)
                self._ring_table_item(row_index, 3, f"{float(row.get('speed_end_kph', 0.0) or 0.0):.2f}", editable=True)
                self._ring_table_item(row_index, 4, str(row.get("turn_direction") or "STRAIGHT"), editable=True)
                self._ring_table_item(row_index, 5, str(row.get("road_mode") or "ISO8608"), editable=True)
                self._ring_table_item(row_index, 6, str(int(row.get("event_count", 0) or 0)))
            self.ring_segment_table.resizeColumnsToContents()
            if rows:
                self.ring_segment_table.selectRow(min(max(0, selected_row), len(rows) - 1))
            self._refresh_ring_detail_controls()
        finally:
            self._refreshing_ring_table = False

    def _populate_ring_bundle_table(self, bundle: Mapping[str, Any]) -> None:
        if not hasattr(self, "ring_bundle_table"):
            return
        visible_keys = (
            "ring_source_of_truth_json",
            "road_csv",
            "axay_csv",
            "scenario_json",
            "meta_json",
            "anim_latest_road_csv",
            "anim_latest_axay_csv",
            "anim_latest_scenario_json",
        )
        rows = [(key, str(bundle.get(key) or "")) for key in visible_keys if str(bundle.get(key) or "").strip()]
        self.ring_bundle_table.setRowCount(len(rows))
        for row_index, (key, path_text) in enumerate(rows):
            label_item = QtWidgets.QTableWidgetItem(key)
            label_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            path_item = QtWidgets.QTableWidgetItem(path_text)
            path_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            path_item.setToolTip(path_text)
            self.ring_bundle_table.setItem(row_index, 0, label_item)
            self.ring_bundle_table.setItem(row_index, 1, path_item)
        self.ring_bundle_table.resizeColumnsToContents()

    def _export_ring_artifacts(self) -> None:
        try:
            self._ring_spec = self._apply_ring_table_to_spec()
            self._apply_ring_detail_to_spec()
            target = self._ring_source_path or self._default_ring_source_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            saved = save_spec_to_path(self._ring_spec, target)
            self._ring_source_path = saved
            output_dir = Path(self.ring_output_dir_edit.text().strip() or str(self._ring_default_output_dir()))
            tag = " ".join(self.ring_export_tag_edit.text().split()) or "ring"
            bundle = export_ring_scenario_bundle(self._ring_spec, output_dir=output_dir, tag=tag)
            self._ring_last_bundle = dict(bundle)
            self._ring_dirty = False
            self._ring_artifacts_stale = False
            self._populate_ring_bundle_table(self._ring_last_bundle)
            diagnostics = build_ring_editor_diagnostics(self._ring_spec)
            self.ring_action_label.setText(
                f"Сценарий сохранён и файлы пересобраны. Папка: {output_dir}. Ошибки проверки {len(diagnostics.errors)}; предупреждения {len(diagnostics.warnings)}."
            )
            self._render_current_ring_spec(selected_row=self._selected_ring_row())
            self._refresh_ring_source_and_export_status(diagnostics=diagnostics)
            self.refresh_view()
        except Exception as exc:
            self.ring_action_label.setText(f"Не удалось пересобрать файлы сценария: {exc}")

    def _open_ring_output_dir(self) -> None:
        target = Path(self.ring_output_dir_edit.text().strip() or str(self._ring_default_output_dir()))
        target.mkdir(parents=True, exist_ok=True)
        opened = QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(target)))
        self.ring_action_label.setText(
            f"Открыта папка выгрузки: {target}" if opened else f"Не удалось открыть папку выгрузки: {target}"
        )

    def _save_ring_source(self) -> None:
        try:
            self._ring_spec = self._apply_ring_table_to_spec()
            self._apply_ring_detail_to_spec()
            target = self._ring_source_path or self._default_ring_source_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            saved = save_spec_to_path(self._ring_spec, target)
            self._ring_source_path = saved
            self._ring_dirty = False
            self._ring_artifacts_stale = True
            diagnostics = build_ring_editor_diagnostics(self._ring_spec)
            self.ring_action_label.setText(
                f"Сценарий сохранён: {saved}. Файлы сценария требуют пересборки. Ошибки проверки {len(diagnostics.errors)}; предупреждения {len(diagnostics.warnings)}."
            )
            self.refresh_view()
        except Exception as exc:
            self.ring_action_label.setText(f"Не удалось сохранить циклический сценарий: {exc}")

    def _check_ring_source(self) -> None:
        try:
            self._ring_spec = self._apply_ring_table_to_spec()
            self._apply_ring_detail_to_spec()
            spec = normalize_spec(self._ring_spec)
            diagnostics = build_ring_editor_diagnostics(spec)
            if diagnostics.errors:
                self.ring_action_label.setText(f"Проверка шва: есть ошибки: {diagnostics.errors[0]}")
                return
            if diagnostics.warnings:
                self.ring_action_label.setText(f"Проверка шва: есть предупреждения: {diagnostics.warnings[0]}")
                return
            metrics = diagnostics.metrics
            self.ring_action_label.setText(
                f"Проверка шва пройдена. Длина круга {float(metrics.get('ring_length_m', 0.0) or 0.0):.2f} м; максимальный шов {float(metrics.get('seam_max_mm', 0.0) or 0.0):.2f} мм."
            )
            self._refresh_ring_source_and_export_status(diagnostics=diagnostics)
        except Exception as exc:
            self.ring_action_label.setText(f"Не удалось проверить циклический сценарий: {exc}")

    def handle_command(self, command_id: str) -> None:
        if command_id == "ring.editor.open":
            self._refresh_ring_editor_controls()
            self.ring_editor_box.setFocus(QtCore.Qt.OtherFocusReason)
            self.ring_action_label.setText(
                "Редактор циклического сценария открыт в рабочем шаге. Измените сегменты, сохраните основной файл и переходите к набору испытаний."
            )


class OptimizationWorkspacePage(RuntimeWorkspacePage):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        action_commands: Iterable[DesktopShellCommandSpec],
        on_command: Callable[[str], None],
        *,
        repo_root: Path,
        python_executable: str | None = None,
        on_shell_status: Callable[[str, bool], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.python_executable = python_executable
        self.on_shell_status = on_shell_status
        self._optimizer_runtime_instance: DesktopOptimizerRuntime | None = None
        self._optimization_last_run_dir: Path | None = None
        self._optimization_last_log_path: Path | None = None
        self._optimization_refresh_timer: QtCore.QTimer | None = None
        super().__init__(
            workspace,
            action_commands,
            on_command,
            lambda: build_optimization_workspace_summary(
                repo_root,
                python_executable=python_executable,
            ),
            parent,
        )
        self.setObjectName("WS-OPTIMIZATION-HOSTED-PAGE")
        self._optimization_refresh_timer = QtCore.QTimer(self)
        self._optimization_refresh_timer.setInterval(1000)
        self._optimization_refresh_timer.timeout.connect(self._refresh_optimization_controls)
        self._optimization_refresh_timer.start()

    def _build_extra_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.optimization_launch_box = QtWidgets.QGroupBox("Оптимизация и основной запуск")
        self.optimization_launch_box.setObjectName("OP-STAGERUNNER-BLOCK")
        self.optimization_launch_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        launch_layout = QtWidgets.QVBoxLayout(self.optimization_launch_box)
        launch_layout.setSpacing(8)

        intro = QtWidgets.QLabel(
            "Основной расчёт является рекомендуемым путём. Расширенная координация доступна отдельно "
            "и не должна запускаться параллельно с основным расчётом."
        )
        intro.setWordWrap(True)
        launch_layout.addWidget(intro)

        self.optimization_source_label = QtWidgets.QLabel("")
        self.optimization_source_label.setWordWrap(True)
        self.optimization_source_label.setStyleSheet("color: #405060;")
        launch_layout.addWidget(self.optimization_source_label)

        form = QtWidgets.QFormLayout()
        self.optimization_objectives_label = QtWidgets.QLabel("")
        self.optimization_gate_label = QtWidgets.QLabel("")
        self.optimization_baseline_label = QtWidgets.QLabel("")
        self.optimization_suite_label = QtWidgets.QLabel("")
        self.optimization_active_job_label = QtWidgets.QLabel("")
        self.optimization_latest_run_label = QtWidgets.QLabel("")
        for label in (
            self.optimization_objectives_label,
            self.optimization_gate_label,
            self.optimization_baseline_label,
            self.optimization_suite_label,
            self.optimization_active_job_label,
            self.optimization_latest_run_label,
        ):
            label.setWordWrap(True)
        form.addRow("Цели расчёта", self.optimization_objectives_label)
        form.addRow("Обязательное условие", self.optimization_gate_label)
        form.addRow("Опорный прогон", self.optimization_baseline_label)
        form.addRow("Набор испытаний", self.optimization_suite_label)
        form.addRow("Активное задание", self.optimization_active_job_label)
        form.addRow("Последний запуск", self.optimization_latest_run_label)
        launch_layout.addLayout(form)

        button_row = QtWidgets.QHBoxLayout()
        self.optimization_check_button = QtWidgets.QPushButton("Проверить готовность")
        self.optimization_check_button.setObjectName("OP-BTN-CHECK")
        self.optimization_check_button.setToolTip(
            "Проверить цели, ограничение, опорный прогон и набор испытаний перед запуском."
        )
        self.optimization_check_button.clicked.connect(
            lambda: self.on_command("optimization.readiness.check")
        )
        self.optimization_prepare_button = QtWidgets.QPushButton("Подготовить основной запуск")
        self.optimization_prepare_button.setObjectName("OP-BTN-LAUNCH")
        self.optimization_prepare_button.setToolTip(
            "Собрать видимые условия запуска и следующий рекомендуемый шаг."
        )
        self.optimization_prepare_button.clicked.connect(
            lambda: self.on_command("optimization.primary_launch.prepare")
        )
        self.optimization_execute_button = QtWidgets.QPushButton("Запустить оптимизацию")
        self.optimization_execute_button.setObjectName("OP-BTN-EXECUTE")
        self.optimization_execute_button.setToolTip(
            "Запустить рекомендуемый основной путь из текущего рабочего шага оптимизации."
        )
        self.optimization_execute_button.clicked.connect(
            lambda: self.on_command("optimization.primary_launch.execute")
        )
        self.optimization_soft_stop_button = QtWidgets.QPushButton("Мягкая остановка")
        self.optimization_soft_stop_button.setObjectName("OP-BTN-SOFT-STOP")
        self.optimization_soft_stop_button.setToolTip(
            "Попросить активный запуск остановиться через stop-файл без немедленного убийства процесса."
        )
        self.optimization_soft_stop_button.clicked.connect(
            lambda: self.on_command("optimization.primary_launch.soft_stop")
        )
        self.optimization_hard_stop_button = QtWidgets.QPushButton("Остановить сейчас")
        self.optimization_hard_stop_button.setObjectName("OP-BTN-HARD-STOP")
        self.optimization_hard_stop_button.setToolTip(
            "Жёстко остановить активный запуск оптимизации, если мягкая остановка не подходит."
        )
        self.optimization_hard_stop_button.clicked.connect(
            lambda: self.on_command("optimization.primary_launch.hard_stop")
        )
        self.optimization_open_log_button = QtWidgets.QPushButton("Открыть журнал")
        self.optimization_open_log_button.setObjectName("OP-BTN-OPEN-LOG")
        self.optimization_open_log_button.setToolTip(
            "Открыть журнал последнего активного или подготовленного запуска оптимизации."
        )
        self.optimization_open_log_button.clicked.connect(
            lambda: self.on_command("optimization.primary_launch.open_log")
        )
        self.optimization_open_run_dir_button = QtWidgets.QPushButton("Открыть папку запуска")
        self.optimization_open_run_dir_button.setObjectName("OP-BTN-OPEN-RUN-DIR")
        self.optimization_open_run_dir_button.setToolTip(
            "Открыть папку последнего активного запуска оптимизации."
        )
        self.optimization_open_run_dir_button.clicked.connect(
            lambda: self.on_command("optimization.primary_launch.open_run_dir")
        )
        for button in (
            self.optimization_check_button,
            self.optimization_prepare_button,
            self.optimization_execute_button,
            self.optimization_soft_stop_button,
            self.optimization_hard_stop_button,
            self.optimization_open_log_button,
            self.optimization_open_run_dir_button,
        ):
            button_row.addWidget(button)
        button_row.addStretch(1)
        launch_layout.addLayout(button_row)

        review_row = QtWidgets.QHBoxLayout()
        self.optimization_history_button = QtWidgets.QPushButton("История запусков")
        self.optimization_history_button.setObjectName("OP-BTN-HISTORY")
        self.optimization_history_button.setToolTip(
            "Показать историю запусков оптимизации внутри рабочего места."
        )
        self.optimization_history_button.clicked.connect(
            lambda: self.on_command("optimization.history.show")
        )
        self.optimization_finished_button = QtWidgets.QPushButton("Готовые прогоны")
        self.optimization_finished_button.setObjectName("OP-BTN-FINISHED")
        self.optimization_finished_button.setToolTip(
            "Показать завершённые и частично готовые прогоны без открытия старого центра."
        )
        self.optimization_finished_button.clicked.connect(
            lambda: self.on_command("optimization.finished.show")
        )
        self.optimization_handoff_button = QtWidgets.QPushButton("Передача стадий")
        self.optimization_handoff_button.setObjectName("OP-BTN-HANDOFF")
        self.optimization_handoff_button.setToolTip(
            "Показать кандидатов продолжения через координатор."
        )
        self.optimization_handoff_button.clicked.connect(
            lambda: self.on_command("optimization.handoff.show")
        )
        self.optimization_packaging_button = QtWidgets.QPushButton("Упаковка и выпуск")
        self.optimization_packaging_button.setObjectName("OP-BTN-PACKAGING")
        self.optimization_packaging_button.setToolTip(
            "Показать готовность выпуска по прогонам оптимизации."
        )
        self.optimization_packaging_button.clicked.connect(
            lambda: self.on_command("optimization.packaging.show")
        )
        for button in (
            self.optimization_history_button,
            self.optimization_finished_button,
            self.optimization_handoff_button,
            self.optimization_packaging_button,
        ):
            review_row.addWidget(button)
        review_row.addStretch(1)
        launch_layout.addLayout(review_row)

        self.optimization_result_label = QtWidgets.QLabel("")
        self.optimization_result_label.setObjectName("OP-ACTION-RESULT")
        self.optimization_result_label.setWordWrap(True)
        self.optimization_result_label.setStyleSheet("color: #576574;")
        launch_layout.addWidget(self.optimization_result_label)

        layout.addWidget(self.optimization_launch_box)

    def _optimizer_runtime(self) -> DesktopOptimizerRuntime:
        if self._optimizer_runtime_instance is None:
            self._optimizer_runtime_instance = DesktopOptimizerRuntime(
                ui_root=self.repo_root,
                python_executable=self.python_executable,
            )
        return self._optimizer_runtime_instance

    @staticmethod
    def _token_text(raw: object, fallback: str = "не задано") -> str:
        text = " ".join(str(raw or "").replace("_", " ").split()).strip()
        if not text:
            return fallback
        labels = {
            "stage runner": "основной расчёт",
            "staged": "основной расчёт",
            "coordinator": "распределённый режим",
            "coord": "распределённый режим",
            "missing": "не найдено",
            "unknown": "нет данных",
            "ready": "готов",
            "blocked": "требует подготовки",
            "done": "завершён",
            "failed": "есть ошибка",
            "active": "активен",
            "stale": "устарел",
            "invalid": "требует проверки",
        }
        return labels.get(text.casefold(), text)

    @staticmethod
    def _short_value(raw: object, *, fallback: str = "нет данных") -> str:
        text = " ".join(str(raw or "").split()).strip()
        if not text:
            return fallback
        if len(text) <= 24:
            return text
        return f"{text[:12]}...{text[-8:]}"

    @staticmethod
    def _yes_no(value: object) -> str:
        return "да" if bool(value) else "нет"

    def _optimization_child_dock_payload(
        self,
        *,
        title: str,
        object_name: str,
        content_object_name: str,
        table_object_name: str,
        summary: str,
        rows: Iterable[Sequence[object]],
    ) -> dict[str, Any]:
        return {
            "status": "shown",
            "child_dock": {
                "title": title,
                "object_name": object_name,
                "content_object_name": content_object_name,
                "table_object_name": table_object_name,
                "summary": summary,
                "rows": tuple(tuple(str(value) for value in row) for row in rows),
            },
        }

    @staticmethod
    def _int_text(raw: object) -> str:
        try:
            return str(int(raw or 0))
        except Exception:
            return "0"

    def _empty_optimization_rows(self, label: str, hint: str) -> list[tuple[str, str, str]]:
        return [(label, "нет данных", hint)]

    def _show_optimization_history_dock(self) -> dict[str, Any]:
        try:
            runtime = self._optimizer_runtime()
            summaries = list(runtime.history_summaries())
            pointer = runtime.latest_pointer_summary()
        except Exception as exc:
            rows = self._empty_optimization_rows(
                "История запусков",
                f"Не удалось прочитать историю: {exc}",
            )
            summary = "История запусков оптимизации временно недоступна."
        else:
            rows = []
            for item in summaries[:40]:
                rows.append(
                    (
                        Path(getattr(item, "run_dir", "")).name or "без имени",
                        self._token_text(getattr(item, "status_label", "") or getattr(item, "status", "")),
                        (
                            f"{self._token_text(getattr(item, 'pipeline_mode', ''))}; "
                            f"строк {self._int_text(getattr(item, 'row_count', 0))}; "
                            f"готово {self._int_text(getattr(item, 'done_count', 0))}; "
                            f"ошибок {self._int_text(getattr(item, 'error_count', 0))}"
                        ),
                    )
                )
            if not rows:
                rows = self._empty_optimization_rows(
                    "История запусков",
                    "После первого запуска оптимизации список появится здесь.",
                )
            latest = str(pointer.get("run_name") or "").strip() or "не выбран"
            summary = f"История запусков оптимизации: {len(summaries)}. Текущий материал для анализа: {latest}."
        self.optimization_result_label.setText(
            "История запусков показана в дочерней dock-панели рабочей области."
        )
        return self._optimization_child_dock_payload(
            title="История запусков оптимизации",
            object_name="child_dock_optimization_history",
            content_object_name="CHILD-OPTIMIZATION-HISTORY-CONTENT",
            table_object_name="CHILD-OPTIMIZATION-HISTORY-TABLE",
            summary=summary,
            rows=rows,
        )

    def _show_optimization_finished_dock(self) -> dict[str, Any]:
        try:
            runtime = self._optimizer_runtime()
            overview = runtime.finished_job_overview()
            finished_rows = list(runtime.finished_job_rows())
        except Exception as exc:
            rows = self._empty_optimization_rows(
                "Готовые прогоны",
                f"Не удалось прочитать список: {exc}",
            )
            summary = "Список готовых прогонов временно недоступен."
        else:
            rows = [
                (
                    str(row.get("name") or "без имени"),
                    str(row.get("status_label") or row.get("status") or "нет статуса"),
                    (
                        f"{self._token_text(row.get('pipeline'))}; "
                        f"готовность {self._int_text(row.get('truth_ready_rows'))}; "
                        f"проверка {self._int_text(row.get('verification_pass_rows'))}; "
                        f"риски {self._int_text(row.get('interference_rows'))}"
                    ),
                )
                for row in finished_rows[:40]
            ]
            if not rows:
                rows = self._empty_optimization_rows(
                    "Готовые прогоны",
                    "После завершения оптимизации готовые прогоны появятся здесь.",
                )
            summary = (
                f"Готовые прогоны: {self._int_text(overview.get('total_jobs'))}; "
                f"с результатами {self._int_text(overview.get('jobs_with_results'))}; "
                f"готовых к проверке {self._int_text(overview.get('truth_ready_jobs'))}; "
                f"с проверкой {self._int_text(overview.get('verification_pass_jobs'))}."
            )
        self.optimization_result_label.setText(
            "Готовые прогоны показаны в дочерней dock-панели рабочей области."
        )
        return self._optimization_child_dock_payload(
            title="Готовые прогоны оптимизации",
            object_name="child_dock_optimization_finished",
            content_object_name="CHILD-OPTIMIZATION-FINISHED-CONTENT",
            table_object_name="CHILD-OPTIMIZATION-FINISHED-TABLE",
            summary=summary,
            rows=rows,
        )

    def _show_optimization_handoff_dock(self) -> dict[str, Any]:
        try:
            runtime = self._optimizer_runtime()
            overview = runtime.handoff_overview_summary()
            handoff_rows = list(runtime.handoff_overview_rows())
        except Exception as exc:
            rows = self._empty_optimization_rows(
                "Передача стадий",
                f"Не удалось прочитать кандидатов: {exc}",
            )
            summary = "Кандидаты продолжения временно недоступны."
        else:
            rows = [
                (
                    str(row.get("run") or Path(str(row.get("__run_dir") or "")).name or "без имени"),
                    str(row.get("preset") or "профиль не задан"),
                    (
                        f"оценка {row.get('quality_score', 0)}; "
                        f"бюджет {self._int_text(row.get('budget'))}; "
                        f"стартовых вариантов {self._int_text(row.get('seeds'))}; "
                        f"полное кольцо {row.get('full_ring') or 'нет данных'}"
                    ),
                )
                for row in handoff_rows[:40]
            ]
            if not rows:
                rows = self._empty_optimization_rows(
                    "Передача стадий",
                    "Кандидаты появятся после основного прогона с планом продолжения.",
                )
            summary = (
                f"Кандидаты продолжения: {self._int_text(overview.get('total_candidates'))}; "
                f"завершённых {self._int_text(overview.get('done_candidates'))}; "
                f"полное кольцо {self._int_text(overview.get('full_ring_candidates'))}; "
                f"лучший прогон: {overview.get('best_run') or 'не выбран'}."
            )
        self.optimization_result_label.setText(
            "Передача стадий показана в дочерней dock-панели рабочей области."
        )
        return self._optimization_child_dock_payload(
            title="Передача стадий оптимизации",
            object_name="child_dock_optimization_handoff",
            content_object_name="CHILD-OPTIMIZATION-HANDOFF-CONTENT",
            table_object_name="CHILD-OPTIMIZATION-HANDOFF-TABLE",
            summary=summary,
            rows=rows,
        )

    def _show_optimization_packaging_dock(self) -> dict[str, Any]:
        try:
            runtime = self._optimizer_runtime()
            overview = runtime.packaging_overview()
            packaging_rows = list(runtime.packaging_rows())
        except Exception as exc:
            rows = self._empty_optimization_rows(
                "Упаковка и выпуск",
                f"Не удалось прочитать готовность выпуска: {exc}",
            )
            summary = "Готовность выпуска временно недоступна."
        else:
            rows = [
                (
                    str(row.get("name") or "без имени"),
                    str(row.get("ready_state") or row.get("status_label") or "нет статуса"),
                    (
                        f"строк выпуска {self._int_text(row.get('rows_with_packaging'))}; "
                        f"готовность {self._int_text(row.get('truth_ready_rows'))}; "
                        f"проверка {self._int_text(row.get('verification_pass_rows'))}; "
                        f"риски {self._int_text(row.get('interference_rows'))}; "
                        f"резервные данные {self._int_text(row.get('runtime_fallback_rows'))}"
                    ),
                )
                for row in packaging_rows[:40]
            ]
            if not rows:
                rows = self._empty_optimization_rows(
                    "Упаковка и выпуск",
                    "После появления результатов оптимизации здесь будет готовность выпуска.",
                )
            summary = (
                f"Выпуск: прогонов {self._int_text(overview.get('total_runs'))}; "
                f"готовых {self._int_text(overview.get('truth_ready_runs'))}; "
                f"с проверкой {self._int_text(overview.get('verification_runs'))}; "
                f"без пересечений {self._int_text(overview.get('zero_interference_runs'))}; "
                f"лучший прогон: {overview.get('best_run') or 'не выбран'}."
            )
        self.optimization_result_label.setText(
            "Упаковка и выпуск показаны в дочерней dock-панели рабочей области."
        )
        return self._optimization_child_dock_payload(
            title="Упаковка и выпуск",
            object_name="child_dock_optimization_packaging",
            content_object_name="CHILD-OPTIMIZATION-PACKAGING-CONTENT",
            table_object_name="CHILD-OPTIMIZATION-PACKAGING-TABLE",
            summary=summary,
            rows=rows,
        )

    def _readiness_state(self, snapshot: Any) -> tuple[bool, tuple[str, ...]]:
        blockers: list[str] = []
        if not tuple(getattr(snapshot, "objective_keys", ()) or ()):
            blockers.append("цели расчёта не выбраны")
        if not str(getattr(snapshot, "penalty_key", "") or "").strip():
            blockers.append("обязательное ограничение не выбрано")
        if not bool(getattr(snapshot, "optimizer_baseline_can_consume", False)):
            blockers.append("опорный прогон требует проверки")
        if int(getattr(snapshot, "enabled_suite_total", 0) or 0) <= 0:
            blockers.append("нет включённых испытаний")
        return (not blockers, tuple(blockers))

    def _refresh_optimization_controls(self) -> None:
        if not hasattr(self, "optimization_launch_box"):
            return
        try:
            runtime = self._optimizer_runtime()
            snapshot = runtime.contract_snapshot()
            pointer = runtime.latest_pointer_summary()
            current_job = runtime.current_job()
            active_surface = runtime.active_job_surface() if current_job is not None else {}
        except Exception as exc:
            message = f"Сводка оптимизации временно недоступна: {exc}"
            for label in (
                self.optimization_objectives_label,
                self.optimization_gate_label,
                self.optimization_baseline_label,
                self.optimization_suite_label,
                self.optimization_active_job_label,
                self.optimization_latest_run_label,
            ):
                label.setText(message)
            self.optimization_prepare_button.setEnabled(False)
            self.optimization_execute_button.setEnabled(False)
            self.optimization_soft_stop_button.setEnabled(False)
            self.optimization_hard_stop_button.setEnabled(False)
            self.optimization_open_log_button.setEnabled(False)
            self.optimization_open_run_dir_button.setEnabled(False)
            return

        objectives = tuple(str(item) for item in getattr(snapshot, "objective_keys", ()) or ())
        objective_text = ", ".join(self._token_text(item) for item in objectives[:5]) if objectives else "цели не выбраны"
        if len(objectives) > 5:
            objective_text += f"; ещё {len(objectives) - 5}"
        penalty_key = self._token_text(getattr(snapshot, "penalty_key", ""), fallback="не выбрано")
        penalty_tol = float(getattr(snapshot, "penalty_tol", 0.0) or 0.0)
        ready, blockers = self._readiness_state(snapshot)

        self.optimization_source_label.setText(
            "Данные берутся из опорного прогона, набора испытаний, диапазонов оптимизации "
            "и настроек стадий в рабочей папке проекта."
        )
        self.optimization_objectives_label.setText(objective_text)
        self.optimization_gate_label.setText(
            f"{penalty_key} не выше {penalty_tol:g}. "
            + ("Проверка готовности пройдена." if ready else "Нужно исправить: " + ", ".join(blockers) + ".")
        )
        baseline_hash = self._short_value(getattr(snapshot, "active_baseline_hash", ""))
        baseline_state = self._token_text(getattr(snapshot, "active_baseline_state", ""), fallback="не найден")
        self.optimization_baseline_label.setText(
            f"Состояние опорного прогона - {baseline_state}. "
            f"Контроль прогона - {baseline_hash}. "
            f"Доступен оптимизатору - {self._yes_no(getattr(snapshot, 'optimizer_baseline_can_consume', False))}."
        )
        enabled_total = int(getattr(snapshot, "enabled_suite_total", 0) or 0)
        suite_total = int(getattr(snapshot, "suite_row_count", 0) or 0)
        search_count = int(getattr(snapshot, "search_param_count", 0) or 0)
        base_count = int(getattr(snapshot, "base_param_count", 0) or 0)
        self.optimization_suite_label.setText(
            f"Включено {enabled_total} из {suite_total} испытаний. "
            f"Параметров в переборе {search_count}; всего базовых параметров {base_count}."
        )

        if current_job is None:
            self.optimization_active_job_label.setText(
                "Активного задания нет. Запускайте только один способ выполнения."
            )
        else:
            self.optimization_active_job_label.setText(
                f"Исполнитель - {self._token_text(getattr(current_job, 'backend', ''))}; "
                f"режим выполнения - {self._token_text(getattr(current_job, 'pipeline_mode', ''))}; "
                f"папка - {self._short_value(getattr(current_job, 'run_dir', ''))}."
            )

        if bool(pointer.get("exists")):
            self.optimization_latest_run_label.setText(
                f"{self._token_text(pointer.get('status_label'), fallback='запуск')}; "
                f"{self._token_text(pointer.get('run_name'), fallback='без имени')}. "
                f"Таблица {int(pointer.get('rows') or 0)} строк, выполнено {int(pointer.get('done_count') or 0)}, "
                f"ошибок {int(pointer.get('error_count') or 0)}."
            )
        else:
            self.optimization_latest_run_label.setText(
                "Последний запуск пока не найден. После запуска здесь появится ссылка на результат."
            )

        if current_job is not None:
            self._remember_optimization_job(current_job)
        busy = self._optimization_job_is_busy(runtime)
        has_log = self._optimization_last_log_path is not None and self._optimization_last_log_path.exists()
        has_run_dir = self._optimization_last_run_dir is not None and self._optimization_last_run_dir.exists()
        self.optimization_prepare_button.setEnabled(ready and not busy)
        self.optimization_execute_button.setEnabled(ready and not busy)
        self.optimization_soft_stop_button.setEnabled(busy)
        self.optimization_hard_stop_button.setEnabled(busy)
        self.optimization_open_log_button.setEnabled(has_log)
        self.optimization_open_run_dir_button.setEnabled(has_run_dir)
        self.optimization_prepare_button.setToolTip(
            "Готово к подготовке основного запуска."
            if ready
            else "Сначала устраните блокирующие причины в целях, опорном прогоне или наборе испытаний."
        )

    def _remember_optimization_job(self, job: Any) -> None:
        run_dir = getattr(job, "run_dir", None)
        log_path = getattr(job, "log_path", None)
        self._optimization_last_run_dir = Path(run_dir) if run_dir else None
        self._optimization_last_log_path = Path(log_path) if log_path else None

    def _optimization_job_is_busy(self, runtime: DesktopOptimizerRuntime | None = None) -> bool:
        runtime = runtime or self._optimizer_runtime()
        job = runtime.current_job()
        if job is None:
            return False
        self._remember_optimization_job(job)
        poll = getattr(getattr(job, "proc", None), "poll", None)
        if not callable(poll):
            return True
        try:
            return poll() is None
        except Exception:
            return True

    def _set_optimization_shell_status(self, text: str, *, busy: bool) -> None:
        if callable(self.on_shell_status):
            self.on_shell_status(text, busy)

    def _open_optimization_path(self, path: Path | None, *, missing_message: str, opened_message: str) -> bool:
        if path is None or not path.exists():
            self.optimization_result_label.setText(missing_message)
            self._set_optimization_shell_status(missing_message, busy=False)
            return False
        opened = QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))
        self.optimization_result_label.setText(opened_message if opened else "Не удалось открыть путь запуска оптимизации.")
        self._set_optimization_shell_status(self.optimization_result_label.text(), busy=False)
        return bool(opened)

    def _open_optimization_log(self) -> bool:
        runtime = self._optimizer_runtime()
        job = runtime.current_job()
        if job is not None:
            self._remember_optimization_job(job)
        return self._open_optimization_path(
            self._optimization_last_log_path,
            missing_message="Журнал запуска оптимизации пока не найден.",
            opened_message="Журнал запуска оптимизации открыт.",
        )

    def _open_optimization_run_dir(self) -> bool:
        runtime = self._optimizer_runtime()
        job = runtime.current_job()
        if job is not None:
            self._remember_optimization_job(job)
        return self._open_optimization_path(
            self._optimization_last_run_dir,
            missing_message="Папка запуска оптимизации пока не найдена.",
            opened_message="Папка запуска оптимизации открыта.",
        )

    def _execute_primary_launch(self) -> dict[str, Any]:
        runtime = self._optimizer_runtime()
        if self._optimization_job_is_busy(runtime):
            self.optimization_result_label.setText("Оптимизация уже выполняется. Дождитесь завершения или остановите текущий запуск.")
            self._set_optimization_shell_status("Оптимизация уже выполняется.", busy=True)
            return {"status": "running"}
        ready, blockers = self._verify_optimization_readiness()
        if not ready:
            self.optimization_result_label.setText("Запуск оптимизации остановлен: " + ", ".join(blockers) + ".")
            self._set_optimization_shell_status("Запуск оптимизации заблокирован.", busy=False)
            return {"status": "blocked", "blockers": blockers}
        try:
            job = runtime.start_job()
        except Exception as exc:
            self.optimization_result_label.setText(f"Не удалось запустить оптимизацию: {exc}")
            self._set_optimization_shell_status("Ошибка запуска оптимизации.", busy=False)
            self._refresh_optimization_controls()
            return {"status": "failed", "error": str(exc)}
        self._remember_optimization_job(job)
        self.optimization_result_label.setText(
            f"Оптимизация запущена в фоне. Папка запуска: {self._short_value(getattr(job, 'run_dir', ''))}."
        )
        self._set_optimization_shell_status("Оптимизация выполняется...", busy=True)
        self._refresh_optimization_controls()
        return {"status": "running", "run_dir": str(getattr(job, "run_dir", ""))}

    def _request_optimization_soft_stop(self) -> bool:
        runtime = self._optimizer_runtime()
        if not self._optimization_job_is_busy(runtime):
            self.optimization_result_label.setText("Нет активного запуска оптимизации для мягкой остановки.")
            self._set_optimization_shell_status("Нет активного запуска оптимизации.", busy=False)
            return False
        requested = runtime.request_soft_stop()
        self.optimization_result_label.setText(
            "Мягкая остановка запрошена. Дождитесь завершения текущей итерации."
            if requested
            else "Не удалось записать stop-файл для мягкой остановки."
        )
        self._set_optimization_shell_status("Мягкая остановка оптимизации запрошена.", busy=True)
        self._refresh_optimization_controls()
        return bool(requested)

    def _request_optimization_hard_stop(self) -> bool:
        runtime = self._optimizer_runtime()
        if runtime.current_job() is None:
            self.optimization_result_label.setText("Нет активного запуска оптимизации для остановки.")
            self._set_optimization_shell_status("Нет активного запуска оптимизации.", busy=False)
            return False
        stopped = runtime.request_hard_stop()
        self.optimization_result_label.setText("Остановка активного запуска оптимизации запрошена.")
        self._set_optimization_shell_status("Останавливаю оптимизацию...", busy=True)
        self._refresh_optimization_controls()
        return bool(stopped)

    def _activate_optimization_panel(self, message: str = "") -> None:
        self._refresh_optimization_controls()
        self.optimization_launch_box.setFocus(QtCore.Qt.OtherFocusReason)
        if message:
            self.optimization_result_label.setText(message)

    def _verify_optimization_readiness(self) -> tuple[bool, tuple[str, ...]]:
        runtime = self._optimizer_runtime()
        snapshot = runtime.contract_snapshot()
        ready, blockers = self._readiness_state(snapshot)
        self._refresh_optimization_controls()
        if ready:
            self.optimization_result_label.setText(
                "Проверка готовности - оптимизация готова к основному запуску."
            )
        else:
            self.optimization_result_label.setText(
                "Проверка готовности - нужно исправить: " + ", ".join(blockers) + "."
            )
        return ready, blockers

    def _prepare_primary_launch(self) -> None:
        ready, blockers = self._verify_optimization_readiness()
        if ready:
            self.optimization_result_label.setText(
                "Основной запуск подготовлен: цели, обязательное условие, опорный прогон и набор испытаний видимы в этом рабочем шаге."
            )
        else:
            self.optimization_result_label.setText(
                "Подготовка остановлена: " + ", ".join(blockers) + "."
            )

    def refresh_view(self) -> None:
        super().refresh_view()
        self._refresh_optimization_controls()

    def handle_command(self, command_id: str) -> object:
        if command_id == "optimization.center.open":
            self._activate_optimization_panel(
                "Настройка основного запуска открыта в рабочем шаге оптимизации."
            )
            return
        if command_id == "optimization.readiness.check":
            self._verify_optimization_readiness()
            return
        if command_id == "optimization.primary_launch.prepare":
            self._prepare_primary_launch()
            return
        if command_id == "optimization.primary_launch.execute":
            self._execute_primary_launch()
            return
        if command_id == "optimization.primary_launch.soft_stop":
            self._request_optimization_soft_stop()
            return
        if command_id == "optimization.primary_launch.hard_stop":
            self._request_optimization_hard_stop()
            return
        if command_id == "optimization.primary_launch.open_log":
            self._open_optimization_log()
            return
        if command_id == "optimization.primary_launch.open_run_dir":
            self._open_optimization_run_dir()
            return
        if command_id == "optimization.history.show":
            return self._show_optimization_history_dock()
        if command_id == "optimization.finished.show":
            return self._show_optimization_finished_dock()
        if command_id == "optimization.handoff.show":
            return self._show_optimization_handoff_dock()
        if command_id == "optimization.packaging.show":
            return self._show_optimization_packaging_dock()


class ResultsWorkspacePage(RuntimeWorkspacePage):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        action_commands: Iterable[DesktopShellCommandSpec],
        on_command: Callable[[str], None],
        *,
        repo_root: Path,
        python_executable: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.python_executable = python_executable or sys.executable
        self.engineering_analysis_process: QtCore.QProcess | None = None
        self.engineering_analysis_process_command: tuple[str, ...] = ()
        self.engineering_analysis_process_run_dir: Path | None = None
        self.engineering_analysis_log_lines: list[str] = []
        self._results_selected_artifact_key = ""
        self._results_chart_preview_selected_row = 0
        self._results_compare_playhead_selected_index = -1
        self._results_compare_playhead_signature = ""
        self._results_compare_window_selected_index = -1
        self._results_compare_window_signature = ""
        self.engineering_analysis_status_text = "Инженерное действие не запускалось."
        self.engineering_analysis_source_label = ""
        self.engineering_analysis_dock_title = "Инженерное действие"
        self.engineering_analysis_dock_object_name = "child_dock_results_engineering_job"
        self.engineering_analysis_content_object_name = "CHILD-RESULTS-ENGINEERING-JOB-CONTENT"
        self.engineering_analysis_table_object_name = "CHILD-RESULTS-ENGINEERING-JOB-TABLE"
        self.engineering_analysis_next_step = "Выберите следующее инженерное действие."
        self.engineering_analysis_success_text = "Инженерное действие завершено успешно."
        self.engineering_analysis_failure_prefix = "Не удалось выполнить инженерное действие"
        super().__init__(
            workspace,
            action_commands,
            on_command,
            lambda: build_results_workspace_summary(
                repo_root,
                python_executable=python_executable,
            ),
            parent,
        )
        self.setObjectName("WS-ANALYSIS-HOSTED-PAGE")

    def _build_extra_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.results_analysis_box = QtWidgets.QGroupBox("Анализ результатов и сравнение")
        self.results_analysis_box.setObjectName("RS-LEADERBOARD")
        self.results_analysis_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        analysis_layout = QtWidgets.QVBoxLayout(self.results_analysis_box)
        analysis_layout.setSpacing(8)

        intro = QtWidgets.QLabel(
            "Здесь собраны последние результаты, проверки, материалы сравнения и передача в проверку проекта. "
            "Внешние окна остаются расширенными инструментами, а основной обзор живёт в этом рабочем шаге."
        )
        intro.setWordWrap(True)
        analysis_layout.addWidget(intro)

        self.results_context_label = QtWidgets.QLabel("")
        self.results_context_label.setObjectName("RS-CONTEXT-SUMMARY")
        self.results_context_label.setWordWrap(True)
        self.results_context_label.setStyleSheet("color: #405060;")
        analysis_layout.addWidget(self.results_context_label)

        self.results_overview_table = QtWidgets.QTableWidget(0, 4)
        self.results_overview_table.setObjectName("RS-OVERVIEW-TABLE")
        self.results_overview_table.setHorizontalHeaderLabels(
            ("Проверка", "Состояние", "Что видно", "Следующий шаг")
        )
        self.results_overview_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.results_overview_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.results_overview_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.results_overview_table.verticalHeader().setVisible(False)
        self.results_overview_table.horizontalHeader().setStretchLastSection(True)
        analysis_layout.addWidget(self.results_overview_table)

        self.results_artifacts_table = QtWidgets.QTableWidget(0, 3)
        self.results_artifacts_table.setObjectName("RS-ARTIFACTS-TABLE")
        self.results_artifacts_table.setHorizontalHeaderLabels(
            ("Материал", "Тип", "Файл или папка")
        )
        self.results_artifacts_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.results_artifacts_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.results_artifacts_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.results_artifacts_table.verticalHeader().setVisible(False)
        self.results_artifacts_table.horizontalHeader().setStretchLastSection(True)
        self.results_artifacts_table.itemSelectionChanged.connect(
            self._on_results_artifact_selection_changed
        )
        analysis_layout.addWidget(self.results_artifacts_table)

        self.results_compare_label = QtWidgets.QLabel("")
        self.results_compare_label.setObjectName("RS-COMPARE-SUMMARY")
        self.results_compare_label.setWordWrap(True)
        analysis_layout.addWidget(self.results_compare_label)

        self.results_compare_preview_box = QtWidgets.QGroupBox("Предпросмотр сравнения")
        self.results_compare_preview_box.setObjectName("RS-COMPARE-PREVIEW")
        preview_layout = QtWidgets.QVBoxLayout(self.results_compare_preview_box)
        self.results_compare_preview_table = QtWidgets.QTableWidget(0, 2)
        self.results_compare_preview_table.setObjectName("RS-COMPARE-PREVIEW-TABLE")
        self.results_compare_preview_table.setHorizontalHeaderLabels(("Пункт", "Значение"))
        self.results_compare_preview_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.results_compare_preview_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.results_compare_preview_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.results_compare_preview_table.verticalHeader().setVisible(False)
        self.results_compare_preview_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self.results_compare_preview_table)
        analysis_layout.addWidget(self.results_compare_preview_box)

        self.results_chart_preview_box = QtWidgets.QGroupBox("Предпросмотр графиков")
        self.results_chart_preview_box.setObjectName("RS-CHART-PREVIEW")
        chart_layout = QtWidgets.QVBoxLayout(self.results_chart_preview_box)
        chart_layout.setSpacing(6)
        chart_intro = QtWidgets.QLabel(
            "Сводка серий показывает, какие числовые данные уже готовы для графического разбора."
        )
        chart_intro.setWordWrap(True)
        chart_layout.addWidget(chart_intro)
        self.results_chart_preview_table = QtWidgets.QTableWidget(0, 4)
        self.results_chart_preview_table.setObjectName("RS-CHART-PREVIEW-TABLE")
        self.results_chart_preview_table.setHorizontalHeaderLabels(
            ("Серия", "Точки", "Диапазон", "Готовность")
        )
        self.results_chart_preview_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.results_chart_preview_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.results_chart_preview_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.results_chart_preview_table.verticalHeader().setVisible(False)
        self.results_chart_preview_table.horizontalHeader().setStretchLastSection(True)
        self.results_chart_preview_table.itemSelectionChanged.connect(
            self._remember_selected_chart_preview_row
        )
        chart_layout.addWidget(self.results_chart_preview_table)
        self.results_chart_preview_scene = QtWidgets.QGraphicsScene(self.results_chart_preview_box)
        self.results_chart_preview_view = QtWidgets.QGraphicsView(self.results_chart_preview_scene)
        self.results_chart_preview_view.setObjectName("RS-CHART-NATIVE-PREVIEW")
        self.results_chart_preview_view.setMinimumHeight(132)
        self.results_chart_preview_view.setRenderHint(QtGui.QPainter.Antialiasing, True)
        self.results_chart_preview_view.setToolTip(
            "Встроенный предпросмотр первой числовой серии выбранного результата."
        )
        chart_layout.addWidget(self.results_chart_preview_view)
        analysis_layout.addWidget(self.results_chart_preview_box)

        button_row = QtWidgets.QHBoxLayout()
        self.results_refresh_button = QtWidgets.QPushButton("Обновить анализ")
        self.results_refresh_button.setObjectName("RS-BTN-REFRESH")
        self.results_refresh_button.clicked.connect(self.refresh_view)
        self.results_prepare_compare_button = QtWidgets.QPushButton("Подготовить сравнение")
        self.results_prepare_compare_button.setObjectName("RS-BTN-PREPARE-COMPARE")
        self.results_prepare_compare_button.setToolTip(
            "Собрать текущий контекст сравнения для выбранных результатов."
        )
        self.results_prepare_compare_button.clicked.connect(
            lambda: self.on_command("results.compare.prepare")
        )
        self.results_prepare_evidence_button = QtWidgets.QPushButton("Подготовить материалы проверки")
        self.results_prepare_evidence_button.setObjectName("RS-BTN-PREPARE-EVIDENCE")
        self.results_prepare_evidence_button.setToolTip(
            "Собрать материалы анализа для проверки проекта."
        )
        self.results_prepare_evidence_button.clicked.connect(
            lambda: self.on_command("results.evidence.prepare")
        )
        self.results_run_materials_button = QtWidgets.QPushButton("Материалы прогона")
        self.results_run_materials_button.setObjectName("RS-BTN-RUN-MATERIALS")
        self.results_run_materials_button.setToolTip(
            "Показать архив, каталоги проверок, отчёты и следующий шаг после последнего запуска."
        )
        self.results_run_materials_button.clicked.connect(
            lambda: self.on_command("results.run_materials.show")
        )
        self.results_selected_material_button = QtWidgets.QPushButton("Выбранный материал")
        self.results_selected_material_button.setObjectName("RS-BTN-SELECTED-MATERIAL")
        self.results_selected_material_button.setToolTip(
            "Показать карточку выбранного файла результата, путь для сравнения, связь с анимацией и краткий предпросмотр."
        )
        self.results_selected_material_button.clicked.connect(
            lambda: self.on_command("results.selected_material.show")
        )
        self.results_engineering_qa_button = QtWidgets.QPushButton("Инженерная проверка")
        self.results_engineering_qa_button.setObjectName("RS-BTN-ENGINEERING-QA")
        self.results_engineering_qa_button.setToolTip(
            "Показать готовность инженерного разбора, пробелы и следующий шаг."
        )
        self.results_engineering_qa_button.clicked.connect(
            lambda: self.on_command("results.engineering_qa.show")
        )
        self.results_engineering_candidates_button = QtWidgets.QPushButton("Кандидаты анализа")
        self.results_engineering_candidates_button.setObjectName("RS-BTN-ENGINEERING-CANDIDATES")
        self.results_engineering_candidates_button.setToolTip(
            "Показать прогоны, которые можно взять для инженерного разбора."
        )
        self.results_engineering_candidates_button.clicked.connect(
            lambda: self.on_command("results.engineering_candidates.show")
        )
        self.results_engineering_pin_run_button = QtWidgets.QPushButton("Зафиксировать прогон")
        self.results_engineering_pin_run_button.setObjectName("RS-BTN-ENGINEERING-PIN-RUN")
        self.results_engineering_pin_run_button.setToolTip(
            "Зафиксировать готовый прогон как источник инженерного разбора."
        )
        self.results_engineering_pin_run_button.clicked.connect(
            lambda: self.on_command("results.engineering_run.pin")
        )
        self.results_engineering_influence_run_button = QtWidgets.QPushButton("Рассчитать влияние")
        self.results_engineering_influence_run_button.setObjectName("RS-BTN-ENGINEERING-INFLUENCE-RUN")
        self.results_engineering_influence_run_button.setToolTip(
            "Запустить расчёт влияния системы для выбранного прогона внутри рабочего шага анализа."
        )
        self.results_engineering_influence_run_button.clicked.connect(
            lambda: self.on_command("results.engineering_influence.run")
        )
        self.results_engineering_full_report_button = QtWidgets.QPushButton("Полный отчёт")
        self.results_engineering_full_report_button.setObjectName("RS-BTN-ENGINEERING-FULL-REPORT-RUN")
        self.results_engineering_full_report_button.setToolTip(
            "Собрать полный отчёт по выбранному прогону внутри рабочего шага анализа."
        )
        self.results_engineering_full_report_button.clicked.connect(
            lambda: self.on_command("results.engineering_full_report.run")
        )
        self.results_engineering_param_staging_button = QtWidgets.QPushButton("Диапазоны влияния")
        self.results_engineering_param_staging_button.setObjectName("RS-BTN-ENGINEERING-PARAM-STAGING-RUN")
        self.results_engineering_param_staging_button.setToolTip(
            "Построить диапазоны и этапы подбора по данным влияния выбранного прогона внутри рабочего шага анализа."
        )
        self.results_engineering_param_staging_button.clicked.connect(
            lambda: self.on_command("results.engineering_param_staging.run")
        )
        self.results_influence_review_button = QtWidgets.QPushButton("Влияние системы")
        self.results_influence_review_button.setObjectName("RS-BTN-INFLUENCE-REVIEW")
        self.results_influence_review_button.setToolTip(
            "Показать материалы влияния, таблицы чувствительности и найденные пробелы."
        )
        self.results_influence_review_button.clicked.connect(
            lambda: self.on_command("results.influence_review.show")
        )
        self.results_compare_influence_button = QtWidgets.QPushButton("Сравнение влияния")
        self.results_compare_influence_button.setObjectName("RS-BTN-COMPARE-INFLUENCE")
        self.results_compare_influence_button.setToolTip(
            "Показать связи параметров и целевых метрик для выбранного результата."
        )
        self.results_compare_influence_button.clicked.connect(
            lambda: self.on_command("results.compare_influence.show")
        )
        self.results_engineering_evidence_button = QtWidgets.QPushButton("Сохранить материалы разбора")
        self.results_engineering_evidence_button.setObjectName("RS-BTN-ENGINEERING-EVIDENCE")
        self.results_engineering_evidence_button.setToolTip(
            "Сохранить инженерные материалы для проверки проекта."
        )
        self.results_engineering_evidence_button.clicked.connect(
            lambda: self.on_command("results.engineering_evidence.export")
        )
        self.results_engineering_animation_link_button = QtWidgets.QPushButton("Связь с анимацией")
        self.results_engineering_animation_link_button.setObjectName("RS-BTN-ENGINEERING-ANIMATION-LINK")
        self.results_engineering_animation_link_button.setToolTip(
            "Подготовить связь выбранного результата с рабочим шагом анимации."
        )
        self.results_engineering_animation_link_button.clicked.connect(
            lambda: self.on_command("results.engineering_animation_link.export")
        )
        self.results_animation_handoff_button = QtWidgets.QPushButton("Передать в анимацию")
        self.results_animation_handoff_button.setObjectName("RS-BTN-HANDOFF-ANIMATION")
        self.results_animation_handoff_button.setToolTip(
            "Передать выбранный материал анализа в следующий рабочий шаг маршрута."
        )
        self.results_animation_handoff_button.clicked.connect(
            lambda: self.on_command("results.animation.prepare")
        )
        self.results_compare_window_button = QtWidgets.QPushButton("Показать сравнение")
        self.results_compare_window_button.setObjectName("RS-BTN-OPEN-COMPARE")
        self.results_compare_window_button.setToolTip(
            "Показать подробный просмотр сравнения внутри рабочего шага."
        )
        self.results_compare_window_button.clicked.connect(
            lambda: self.on_command("results.compare.open")
        )
        self.results_compare_next_target_button = QtWidgets.QPushButton("Следующая пара")
        self.results_compare_next_target_button.setObjectName("RS-BTN-COMPARE-NEXT-TARGET")
        self.results_compare_next_target_button.setToolTip(
            "Переключить следующий материал сравнения и сразу обновить панель сравнения."
        )
        self.results_compare_next_target_button.clicked.connect(
            lambda: self.on_command("results.compare.target.next")
        )
        self.results_compare_next_signal_button = QtWidgets.QPushButton("Следующий сигнал")
        self.results_compare_next_signal_button.setObjectName("RS-BTN-COMPARE-NEXT-SIGNAL")
        self.results_compare_next_signal_button.setToolTip(
            "Переключить следующую числовую серию и сразу обновить панель сравнения."
        )
        self.results_compare_next_signal_button.clicked.connect(
            lambda: self.on_command("results.compare.signal.next")
        )
        self.results_compare_next_playhead_button = QtWidgets.QPushButton("Следующая точка")
        self.results_compare_next_playhead_button.setObjectName("RS-BTN-COMPARE-NEXT-PLAYHEAD")
        self.results_compare_next_playhead_button.setToolTip(
            "Переключить следующую точку графика сравнения и сразу обновить панель."
        )
        self.results_compare_next_playhead_button.clicked.connect(
            lambda: self.on_command("results.compare.playhead.next")
        )
        self.results_compare_next_window_button = QtWidgets.QPushButton("Следующее окно")
        self.results_compare_next_window_button.setObjectName("RS-BTN-COMPARE-NEXT-WINDOW")
        self.results_compare_next_window_button.setToolTip(
            "Переключить следующее окно времени на графике сравнения и сразу обновить панель."
        )
        self.results_compare_next_window_button.clicked.connect(
            lambda: self.on_command("results.compare.window.next")
        )
        self.results_chart_detail_button = QtWidgets.QPushButton("Подробности графика")
        self.results_chart_detail_button.setObjectName("RS-BTN-CHART-DETAIL")
        self.results_chart_detail_button.setToolTip(
            "Показать выбранную числовую серию, диапазон, точки и compare-context в дочерней dock-панели."
        )
        self.results_chart_detail_button.clicked.connect(
            lambda: self.on_command("results.chart_detail.show")
        )
        for button in (
            self.results_refresh_button,
            self.results_prepare_compare_button,
            self.results_prepare_evidence_button,
            self.results_run_materials_button,
            self.results_selected_material_button,
            self.results_engineering_qa_button,
            self.results_engineering_candidates_button,
            self.results_engineering_pin_run_button,
            self.results_engineering_influence_run_button,
            self.results_engineering_full_report_button,
            self.results_engineering_param_staging_button,
            self.results_influence_review_button,
            self.results_compare_influence_button,
            self.results_engineering_evidence_button,
            self.results_engineering_animation_link_button,
            self.results_animation_handoff_button,
            self.results_compare_window_button,
            self.results_compare_next_target_button,
            self.results_compare_next_signal_button,
            self.results_compare_next_playhead_button,
            self.results_compare_next_window_button,
            self.results_chart_detail_button,
        ):
            button_row.addWidget(button)
        button_row.addStretch(1)
        analysis_layout.addLayout(button_row)

        self.results_action_label = QtWidgets.QLabel("")
        self.results_action_label.setObjectName("RS-ACTION-RESULT")
        self.results_action_label.setWordWrap(True)
        self.results_action_label.setStyleSheet("color: #576574;")
        analysis_layout.addWidget(self.results_action_label)

        layout.addWidget(self.results_analysis_box)

    def _results_runtime(self) -> DesktopResultsRuntime:
        return DesktopResultsRuntime(
            repo_root=self.repo_root,
            python_executable=str(self.python_executable or sys.executable),
        )

    def _engineering_analysis_runtime(self) -> DesktopEngineeringAnalysisRuntime:
        return DesktopEngineeringAnalysisRuntime(
            repo_root=self.repo_root,
            python_executable=str(self.python_executable or sys.executable),
        )

    @staticmethod
    def _status_text(raw: object) -> str:
        text = " ".join(str(raw or "").replace("_", " ").split()).strip()
        labels = {
            "PASS": "норма",
            "FAIL": "ошибка",
            "WARN": "предупреждение",
            "READY": "готово",
            "MISSING": "нет данных",
            "BLOCKED": "заблокировано",
            "CRITICAL": "критично",
            "PARTIAL": "частично",
            "INFO": "справка",
            "CURRENT": "актуально",
            "HISTORICAL": "исторические данные",
            "STALE": "устарело",
            "UNKNOWN": "нет данных",
        }
        return labels.get(text.upper(), text.lower() if text else "нет данных")

    @staticmethod
    def _category_text(raw: object) -> str:
        text = " ".join(str(raw or "").replace("_", " ").split()).strip().casefold()
        labels = {
            "bundle": "архив проекта",
            "validation": "проверка",
            "triage": "разбор",
            "results": "результаты",
            "anim latest": "анимация",
            "runs": "прогоны",
            "evidence": "материалы",
        }
        return labels.get(text, text or "материал")

    @staticmethod
    def _short_text(raw: object, *, fallback: str = "нет данных", limit: int = 96) -> str:
        text = _operator_result_text(raw)
        text = " ".join(str(text or "").split()).strip()
        if not text:
            return fallback
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    @staticmethod
    def _preview_value_text(raw: object, *, fallback: str = "нет данных", limit: int = 120) -> str:
        text = " ".join(str(raw or "").split()).strip()
        if not text:
            return fallback
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    @staticmethod
    def _path_label(path: Path | None) -> str:
        if path is None:
            return "нет файла"
        if path.is_dir():
            return "папка найдена"
        return "файл найден"

    def _refresh_results_controls(self) -> None:
        if not hasattr(self, "results_analysis_box"):
            return
        try:
            runtime = self._results_runtime()
            snapshot = runtime.snapshot()
        except Exception as exc:
            message = f"Сводка анализа временно недоступна: {exc}"
            self.results_context_label.setText(message)
            self.results_compare_label.setText(message)
            self.results_overview_table.setRowCount(0)
            self.results_artifacts_table.setRowCount(0)
            if hasattr(self, "results_chart_preview_table"):
                self.results_chart_preview_table.setRowCount(0)
            return

        context_state = self._status_text(snapshot.result_context_state)
        self.results_context_label.setText(
            f"Результаты расчёта: {context_state}. "
            f"{self._short_text(snapshot.result_context_banner, fallback='Свежие результаты пока не найдены.')}"
        )

        rows = tuple(snapshot.validation_overview_rows)
        self.results_overview_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                row.title,
                self._status_text(row.status),
                self._short_text(row.detail),
                self._short_text(row.next_action, fallback="обновить анализ"),
            )
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                self.results_overview_table.setItem(row_index, column, item)
        self.results_overview_table.resizeColumnsToContents()

        selected_artifact_key = str(getattr(self, "_results_selected_artifact_key", "") or "").strip()
        if not selected_artifact_key and hasattr(self, "results_artifacts_table"):
            current_row = self._selected_results_artifact_row()
            if current_row >= 0:
                current_item = self.results_artifacts_table.item(current_row, 0)
                if current_item is not None:
                    selected_artifact_key = str(current_item.data(QtCore.Qt.UserRole) or "").strip()

        artifacts = tuple(snapshot.recent_artifacts[:8])
        self.results_artifacts_table.setRowCount(len(artifacts))
        selected_row = -1
        for row_index, artifact in enumerate(artifacts):
            values = (
                artifact.title,
                self._category_text(artifact.category),
                self._path_label(artifact.path),
            )
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setToolTip(str(artifact.path))
                item.setData(QtCore.Qt.UserRole, artifact.key)
                self.results_artifacts_table.setItem(row_index, column, item)
            if str(getattr(artifact, "key", "") or "").strip() == selected_artifact_key:
                selected_row = row_index
        self.results_artifacts_table.resizeColumnsToContents()
        if artifacts:
            if selected_row < 0:
                selected_row = 0
            self._select_results_artifact_row(selected_row)

        compare_ready = snapshot.latest_npz_path is not None
        selected_state = self._status_text(snapshot.selected_run_contract_status)
        self.results_compare_label.setText(
            "Сравнение готово - "
            + ("да" if compare_ready else "нет")
            + f". Выбранный прогон оптимизации: {selected_state}. "
            + self._short_text(snapshot.selected_run_contract_banner, fallback="Выберите результат перед сравнением.")
        )
        self.results_compare_window_button.setEnabled(compare_ready)
        self.results_compare_window_button.setToolTip(
            "Показать подробный просмотр сравнения внутри рабочего шага."
            if compare_ready
            else "Сначала нужен файл результата для сравнения."
        )
        self._refresh_engineering_analysis_process_state()
        self._populate_compare_preview(runtime, snapshot)
        self._populate_chart_preview(runtime, snapshot)

    def _engineering_analysis_process_is_busy(self) -> bool:
        process = self.engineering_analysis_process
        return process is not None and process.state() != QtCore.QProcess.NotRunning

    def _refresh_engineering_analysis_process_state(self) -> None:
        if not hasattr(self, "results_engineering_influence_run_button"):
            return
        busy = self._engineering_analysis_process_is_busy()
        self.results_engineering_influence_run_button.setEnabled(not busy)
        if hasattr(self, "results_engineering_full_report_button"):
            self.results_engineering_full_report_button.setEnabled(not busy)
        if hasattr(self, "results_engineering_param_staging_button"):
            self.results_engineering_param_staging_button.setEnabled(not busy)
        self.results_engineering_influence_run_button.setToolTip(
            "Расчёт влияния системы уже выполняется."
            if busy
            else "Запустить расчёт влияния системы для выбранного прогона внутри рабочего шага анализа."
        )
        if hasattr(self, "results_engineering_full_report_button"):
            self.results_engineering_full_report_button.setToolTip(
                "Инженерное действие уже выполняется."
                if busy
                else "Собрать полный отчёт по выбранному прогону внутри рабочего шага анализа."
            )
        if hasattr(self, "results_engineering_param_staging_button"):
            self.results_engineering_param_staging_button.setToolTip(
                "Инженерное действие уже выполняется."
                if busy
                else "Построить диапазоны и этапы подбора по данным влияния выбранного прогона внутри рабочего шага анализа."
            )

    def _activate_results_panel(self, message: str = "") -> None:
        self._refresh_results_controls()
        self.results_analysis_box.setFocus(QtCore.Qt.OtherFocusReason)
        if message:
            self.results_action_label.setText(message)

    @staticmethod
    def _results_child_dock_payload(
        *,
        title: str,
        object_name: str,
        content_object_name: str,
        table_object_name: str,
        summary: str,
        rows: Iterable[tuple[str, ...]],
        plot_preview: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        child_dock: dict[str, Any] = {
            "title": title,
            "object_name": object_name,
            "content_object_name": content_object_name,
            "table_object_name": table_object_name,
            "summary": summary,
            "rows": tuple(rows),
        }
        if isinstance(plot_preview, Mapping):
            child_dock["plot_preview"] = dict(plot_preview)
        return {"child_dock": child_dock}

    def _populate_compare_preview(
        self,
        runtime: DesktopResultsRuntime,
        snapshot: Any,
        *,
        artifact: Any | None = None,
    ) -> None:
        target_artifact = artifact if artifact is not None else runtime.artifact_by_key(snapshot, "latest_npz")
        sidecar_artifact = runtime.artifact_by_key(snapshot, "compare_current_context_sidecar")
        target_path = runtime.compare_viewer_path(snapshot, artifact=target_artifact)
        rows: list[tuple[str, str]] = [
            (
                "Файл результата",
                target_path.name if target_path is not None else "нужен результат расчёта",
            ),
            (
                "Контекст сравнения",
                self._path_label(getattr(sidecar_artifact, "path", None)) if sidecar_artifact is not None else "подготовьте сравнение",
            ),
            (
                "Выбранный прогон",
                self._status_text(getattr(snapshot, "selected_run_contract_status", "")),
            ),
            (
                "Следующий шаг",
                "откройте сравнение" if target_path is not None else "сначала выполните расчёт",
            ),
        ]
        if target_artifact is not None and hasattr(runtime, "artifact_preview_lines"):
            for index, line in enumerate(runtime.artifact_preview_lines(target_artifact)[:3], start=1):
                rows.append((f"Деталь {index}", self._short_text(line, limit=120)))

        self.results_compare_preview_table.setRowCount(len(rows))
        for row_index, (label, value) in enumerate(rows):
            self.results_compare_preview_table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(label))
            self.results_compare_preview_table.setItem(row_index, 1, QtWidgets.QTableWidgetItem(value))
        self.results_compare_preview_table.resizeColumnsToContents()

    def _populate_chart_preview(
        self,
        runtime: DesktopResultsRuntime,
        snapshot: Any,
        *,
        artifact: Any | None = None,
    ) -> None:
        if not hasattr(self, "results_chart_preview_table"):
            return
        target_artifact = artifact
        if hasattr(runtime, "artifact_by_key"):
            try:
                target_artifact = target_artifact or runtime.artifact_by_key(snapshot, "latest_npz")
            except Exception:
                target_artifact = None

        chart_rows: list[tuple[str, str, str, str]] = []
        if hasattr(runtime, "chart_preview_rows"):
            try:
                raw_rows = runtime.chart_preview_rows(snapshot, artifact=target_artifact)
            except Exception:
                raw_rows = ()
            for raw in raw_rows:
                if isinstance(raw, Mapping):
                    chart_rows.append(
                        (
                            self._preview_value_text(raw.get("series")),
                            self._preview_value_text(raw.get("points")),
                            self._preview_value_text(raw.get("range")),
                            self._preview_value_text(raw.get("role")),
                        )
                    )
                elif isinstance(raw, (tuple, list)) and len(raw) >= 4:
                    chart_rows.append(
                        (
                            self._preview_value_text(raw[0]),
                            self._preview_value_text(raw[1]),
                            self._preview_value_text(raw[2]),
                            self._preview_value_text(raw[3]),
                        )
                    )

        if not chart_rows:
            target_path = getattr(snapshot, "latest_npz_path", None)
            chart_rows.append(
                (
                    "Файл результата",
                    "1" if target_path is not None else "0",
                    Path(target_path).name if target_path is not None else "нужен результат расчёта",
                    "готово к графику" if target_path is not None else "сначала выполните расчёт",
                )
            )
            if target_artifact is not None and hasattr(runtime, "artifact_preview_lines"):
                try:
                    preview_lines = runtime.artifact_preview_lines(target_artifact)
                except Exception:
                    preview_lines = ()
                for index, line in enumerate(preview_lines[:2], start=1):
                    chart_rows.append(
                        (
                            f"Деталь {index}",
                            "сводка",
                            self._preview_value_text(line, limit=140),
                            "проверьте перед передачей",
                        )
                    )

        preview_payload: Mapping[str, Any] | None = None
        if hasattr(runtime, "chart_preview_series_samples"):
            try:
                candidate = runtime.chart_preview_series_samples(
                    snapshot,
                    artifact=target_artifact,
                )
            except Exception:
                candidate = None
            if isinstance(candidate, Mapping):
                preview_payload = candidate

        selected_row = self._selected_chart_series_row()
        self.results_chart_preview_table.setRowCount(len(chart_rows))
        for row_index, values in enumerate(chart_rows):
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(self._preview_value_text(value))
                if column == 0:
                    item.setData(QtCore.Qt.UserRole, str(value))
                self.results_chart_preview_table.setItem(row_index, column, item)
        self.results_chart_preview_table.resizeColumnsToContents()
        if chart_rows:
            if selected_row < 0:
                selected_row = 0
            self._select_chart_series_row(selected_row)
        else:
            self._results_chart_preview_selected_row = 0
        if hasattr(self, "results_chart_detail_button"):
            chart_ready = self.results_chart_preview_table.rowCount() > 0
            self.results_chart_detail_button.setEnabled(chart_ready)
            self.results_chart_detail_button.setToolTip(
                "Показать выбранную числовую серию, диапазон, точки и compare-context в дочерней dock-панели."
                if chart_ready
                else "Сначала нужен файл результата с числовыми сериями."
            )
        self._draw_native_chart_preview(chart_rows, preview_payload)

    def _draw_native_chart_preview(
        self,
        chart_rows: Iterable[tuple[str, str, str, str]],
        preview_payload: Mapping[str, Any] | None,
    ) -> None:
        if not hasattr(self, "results_chart_preview_scene"):
            return
        scene = self.results_chart_preview_scene
        scene.clear()
        width = 460.0
        height = 118.0
        margin_left = 36.0
        margin_right = 18.0
        margin_top = 18.0
        margin_bottom = 24.0
        scene.setSceneRect(0.0, 0.0, width, height)
        scene.addRect(
            0.0,
            0.0,
            width,
            height,
            QtGui.QPen(QtGui.QColor("#d5dde6")),
            QtGui.QBrush(QtGui.QColor("#f8fafc")),
        )
        axis_pen = QtGui.QPen(QtGui.QColor("#7f8fa6"))
        scene.addLine(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom, axis_pen)
        scene.addLine(margin_left, margin_top, margin_left, height - margin_bottom, axis_pen)

        payload = dict(preview_payload or {})
        raw_samples = payload.get("samples") or ()
        samples: list[float] = []
        for raw in raw_samples:
            try:
                value = float(raw)
            except Exception:
                continue
            if value == value and value not in {float("inf"), float("-inf")}:
                samples.append(value)

        series_name = self._preview_value_text(payload.get("series"), fallback="серия")
        point_count = self._preview_value_text(payload.get("point_count"), fallback=str(len(samples)))
        if len(samples) >= 2:
            minimum = min(samples)
            maximum = max(samples)
            span = maximum - minimum
            if span == 0:
                span = 1.0
            plot_width = width - margin_left - margin_right
            plot_height = height - margin_top - margin_bottom
            path = QtGui.QPainterPath()
            for index, value in enumerate(samples):
                x = margin_left + plot_width * index / max(1, len(samples) - 1)
                y = margin_top + plot_height * (1.0 - ((value - minimum) / span))
                if index == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            scene.addPath(path, QtGui.QPen(QtGui.QColor("#0f766e"), 2.2))
            scene.addText(series_name).setPos(margin_left, 0.0)
            scene.addText(f"{minimum:g} .. {maximum:g}").setPos(margin_left, height - 22.0)
            scene.addText(f"{point_count} точек").setPos(width - 118.0, height - 22.0)
            self.results_chart_preview_view.setToolTip(
                f"{series_name}: {minimum:g} .. {maximum:g}; {point_count} точек"
            )
            return

        bars = list(chart_rows)[:3]
        if not bars:
            bars = [("Результат", "0", "нужен результат расчёта", "сначала выполните расчёт")]
        bar_width = width - margin_left - margin_right
        for index, (series, points, value_range, role) in enumerate(bars):
            y = margin_top + 12.0 + index * 24.0
            fill = QtGui.QColor("#9fb3c8") if index else QtGui.QColor("#38bdf8")
            scene.addRect(margin_left, y, bar_width * max(0.2, 1.0 - index * 0.18), 9.0, QtGui.QPen(fill), QtGui.QBrush(fill))
            scene.addText(self._preview_value_text(series, limit=32)).setPos(margin_left, y + 8.0)
            scene.addText(self._preview_value_text(points, fallback="", limit=24)).setPos(width - 122.0, y + 8.0)
        first = bars[0]
        self.results_chart_preview_view.setToolTip(
            f"{self._preview_value_text(first[0])}: {self._preview_value_text(first[2])}; {self._preview_value_text(first[3])}"
        )

    def _on_results_artifact_selection_changed(self) -> None:
        previous_key = str(getattr(self, "_results_selected_artifact_key", "") or "")
        self._remember_selected_results_artifact_key()
        if str(getattr(self, "_results_selected_artifact_key", "") or "") != previous_key:
            self._reset_compare_playhead_selection()
        self._refresh_selected_result_preview()

    def _remember_selected_results_artifact_key(self) -> None:
        if not hasattr(self, "results_artifacts_table"):
            return
        table = self.results_artifacts_table
        selected_rows = table.selectionModel().selectedRows()
        row = selected_rows[0].row() if selected_rows else -1
        if row < 0 or row >= table.rowCount():
            return
        item = table.item(row, 0)
        if item is None:
            return
        self._results_selected_artifact_key = str(item.data(QtCore.Qt.UserRole) or "").strip()

    def _selected_results_artifact_row(self) -> int:
        if not hasattr(self, "results_artifacts_table"):
            return -1
        table = self.results_artifacts_table
        selected_rows = table.selectionModel().selectedRows()
        row = selected_rows[0].row() if selected_rows else -1
        if 0 <= row < table.rowCount():
            return row
        selected_key = str(getattr(self, "_results_selected_artifact_key", "") or "").strip()
        if selected_key:
            for index in range(table.rowCount()):
                item = table.item(index, 0)
                if item is not None and str(item.data(QtCore.Qt.UserRole) or "").strip() == selected_key:
                    return index
        return 0 if table.rowCount() > 0 else -1

    def _select_results_artifact_row(self, row: int) -> None:
        if not hasattr(self, "results_artifacts_table"):
            return
        table = self.results_artifacts_table
        if table.rowCount() <= 0:
            return
        row = max(0, min(int(row), table.rowCount() - 1))
        table.selectRow(row)
        self._remember_selected_results_artifact_key()

    def _remember_selected_chart_preview_row(self) -> None:
        if not hasattr(self, "results_chart_preview_table"):
            return
        table = self.results_chart_preview_table
        selected_rows = table.selectionModel().selectedRows()
        row = selected_rows[0].row() if selected_rows else -1
        if 0 <= row < table.rowCount():
            previous_row = int(getattr(self, "_results_chart_preview_selected_row", 0) or 0)
            self._results_chart_preview_selected_row = row
            if row != previous_row:
                self._reset_compare_playhead_selection()

    def _selected_chart_series_row(self) -> int:
        if not hasattr(self, "results_chart_preview_table"):
            return -1
        table = self.results_chart_preview_table
        selected_rows = table.selectionModel().selectedRows()
        row = selected_rows[0].row() if selected_rows else -1
        if 0 <= row < table.rowCount():
            return row
        remembered_row = int(getattr(self, "_results_chart_preview_selected_row", 0) or 0)
        if table.rowCount() <= 0:
            return -1
        return max(0, min(remembered_row, table.rowCount() - 1))

    def _select_chart_series_row(self, row: int) -> None:
        if not hasattr(self, "results_chart_preview_table"):
            return
        table = self.results_chart_preview_table
        if table.rowCount() <= 0:
            self._results_chart_preview_selected_row = 0
            return
        row = max(0, min(int(row), table.rowCount() - 1))
        self._results_chart_preview_selected_row = row
        table.selectRow(row)

    def _reset_compare_playhead_selection(self) -> None:
        self._results_compare_playhead_selected_index = -1
        self._results_compare_playhead_signature = ""
        self._results_compare_window_selected_index = -1
        self._results_compare_window_signature = ""

    def _compare_playhead_rows(
        self,
        preview: Mapping[str, Any] | None,
    ) -> tuple[dict[str, Any], ...]:
        preview_map = dict(preview or {})
        context_rows = preview_map.get("context_rows") or ()
        rows: list[dict[str, Any]] = []
        for item in context_rows:
            row = dict(item) if isinstance(item, Mapping) else {}
            if row.get("time_s") in (None, ""):
                continue
            rows.append(row)
        if rows:
            return tuple(rows)
        for point in preview_map.get("sample_points") or ():
            if not isinstance(point, (tuple, list)) or len(point) < 2:
                continue
            rows.append(
                {
                    "time_s": point[0],
                    "delta": point[1],
                }
            )
        return tuple(rows)

    def _compare_playhead_signature(self, preview: Mapping[str, Any] | None) -> str:
        preview_map = dict(preview or {})
        return "|".join(
            [
                str(preview_map.get("reference_label") or "").strip(),
                str(preview_map.get("compare_label") or "").strip(),
                str(preview_map.get("signal") or "").strip(),
                str(tuple(preview_map.get("time_window") or ())),
            ]
        )

    def _default_compare_playhead_index(
        self,
        preview: Mapping[str, Any] | None,
        rows: Sequence[Mapping[str, Any]],
    ) -> int:
        if not rows:
            return -1
        hotspot_time = dict(preview or {}).get("hotspot_time")
        if hotspot_time in (None, ""):
            return 0
        try:
            hotspot_value = float(hotspot_time)
        except Exception:
            return 0
        best_index = 0
        best_distance = float("inf")
        for index, item in enumerate(rows):
            try:
                row_time = float(dict(item).get("time_s"))
            except Exception:
                continue
            distance = abs(row_time - hotspot_value)
            if distance < best_distance:
                best_distance = distance
                best_index = index
        return best_index

    def _selected_compare_playhead_row(
        self,
        preview: Mapping[str, Any] | None,
    ) -> tuple[int, dict[str, Any] | None, tuple[dict[str, Any], ...]]:
        rows = self._compare_playhead_rows(preview)
        if not rows:
            self._reset_compare_playhead_selection()
            return -1, None, ()
        signature = self._compare_playhead_signature(preview)
        index = int(getattr(self, "_results_compare_playhead_selected_index", -1))
        if (
            signature != str(getattr(self, "_results_compare_playhead_signature", "") or "")
            or index < 0
            or index >= len(rows)
        ):
            index = self._default_compare_playhead_index(preview, rows)
            self._results_compare_playhead_signature = signature
            self._results_compare_playhead_selected_index = index
        return index, dict(rows[index]), rows

    def _compare_window_rows(
        self,
        preview: Mapping[str, Any] | None,
        point_rows: Sequence[Mapping[str, Any]] | None = None,
    ) -> tuple[dict[str, Any], ...]:
        preview_map = dict(preview or {})
        rows = tuple(dict(item) for item in (point_rows or self._compare_playhead_rows(preview_map)))
        if not rows:
            return ()
        raw_window = tuple(preview_map.get("time_window") or ())
        global_start: float | None = None
        global_end: float | None = None
        if len(raw_window) >= 2:
            try:
                global_start = float(raw_window[0])
                global_end = float(raw_window[1])
            except Exception:
                global_start = None
                global_end = None
        times: list[float] = []
        for row in rows:
            try:
                times.append(float(row.get("time_s")))
            except Exception:
                continue
        if not times:
            return ()
        windows: list[dict[str, Any]] = []
        last_index = len(times) - 1
        for index, time_value in enumerate(times):
            if index == 0:
                start_value = global_start if global_start is not None else time_value
            else:
                start_value = (times[index - 1] + time_value) / 2.0
            if index == last_index:
                end_value = global_end if global_end is not None else time_value
            else:
                end_value = (time_value + times[index + 1]) / 2.0
            if global_start is not None:
                start_value = max(global_start, start_value)
            if global_end is not None:
                end_value = min(global_end, end_value)
            point_count = 0
            for candidate in times:
                if candidate < start_value:
                    continue
                if candidate > end_value:
                    continue
                point_count += 1
            windows.append(
                {
                    "start_s": float(start_value),
                    "end_s": float(end_value),
                    "focus_time_s": float(time_value),
                    "point_count": int(point_count),
                }
            )
        return tuple(windows)

    def _selected_compare_window_row(
        self,
        preview: Mapping[str, Any] | None,
        *,
        selected_playhead_index: int = -1,
        point_rows: Sequence[Mapping[str, Any]] | None = None,
    ) -> tuple[int, dict[str, Any] | None, tuple[dict[str, Any], ...]]:
        rows = self._compare_window_rows(preview, point_rows=point_rows)
        if not rows:
            self._results_compare_window_selected_index = -1
            self._results_compare_window_signature = ""
            return -1, None, ()
        signature = self._compare_playhead_signature(preview)
        index = int(getattr(self, "_results_compare_window_selected_index", -1))
        if (
            signature != str(getattr(self, "_results_compare_window_signature", "") or "")
            or index < 0
            or index >= len(rows)
        ):
            fallback_index = selected_playhead_index if 0 <= selected_playhead_index < len(rows) else 0
            index = fallback_index
            self._results_compare_window_signature = signature
            self._results_compare_window_selected_index = index
        return index, dict(rows[index]), rows

    def _build_compare_plot_preview(
        self,
        preview: Mapping[str, Any] | None,
        *,
        selected_playhead_row: Mapping[str, Any] | None = None,
        selected_window_row: Mapping[str, Any] | None = None,
        active_pair_label: str = "",
        active_signal_label: str = "",
        action_summary: str = "",
    ) -> dict[str, Any] | None:
        preview_map = dict(preview or {})
        context_rows = [
            dict(item)
            for item in (preview_map.get("context_rows") or ())
            if isinstance(item, Mapping)
        ]
        if not context_rows:
            return None

        window_start: float | None = None
        window_end: float | None = None
        if selected_window_row is not None:
            try:
                window_start = float(selected_window_row.get("start_s"))
                window_end = float(selected_window_row.get("end_s"))
            except Exception:
                window_start = None
                window_end = None

        plot_rows = context_rows
        if window_start is not None and window_end is not None:
            filtered_rows: list[dict[str, Any]] = []
            for row in context_rows:
                try:
                    time_value = float(row.get("time_s"))
                except Exception:
                    continue
                if time_value < window_start or time_value > window_end:
                    continue
                filtered_rows.append(row)
            if len(filtered_rows) >= 2:
                plot_rows = filtered_rows

        def _points_for(key: str) -> tuple[tuple[float, float], ...]:
            points: list[tuple[float, float]] = []
            for row in plot_rows:
                try:
                    x_value = float(row.get("time_s"))
                    y_value = float(row.get(key))
                except Exception:
                    continue
                if not math.isfinite(x_value) or not math.isfinite(y_value):
                    continue
                points.append((x_value, y_value))
            return tuple(points)

        reference_points = _points_for("reference_value")
        compare_points = _points_for("compare_value")
        delta_points = _points_for("delta")
        if not reference_points and not compare_points and not delta_points:
            return None

        series_rows: list[dict[str, Any]] = []
        reference_label = str(preview_map.get("reference_label") or "").strip() or "Опорный прогон"
        compare_label = str(preview_map.get("compare_label") or "").strip() or "Сравниваемый прогон"
        if reference_points:
            series_rows.append(
                {
                    "label": reference_label,
                    "color": "#64748b",
                    "points": reference_points,
                }
            )
        if compare_points:
            series_rows.append(
                {
                    "label": compare_label,
                    "color": "#0f766e",
                    "points": compare_points,
                }
            )
        if delta_points:
            series_rows.append(
                {
                    "label": "Δ",
                    "color": "#dc2626",
                    "points": delta_points,
                }
            )

        focus_x: float | None = None
        if selected_playhead_row is not None:
            try:
                focus_x = float(selected_playhead_row.get("time_s"))
            except Exception:
                focus_x = None

        unit = str(preview_map.get("unit") or "").strip()
        pair_label = active_pair_label or (
            f"{reference_label} -> {compare_label}" if reference_label and compare_label else ""
        )
        title = "График сравнения"
        summary_parts: list[str] = []
        if pair_label:
            summary_parts.append(self._short_text(pair_label, limit=120))
        if window_start is not None and window_end is not None:
            summary_parts.append(f"окно {window_start:.3f} .. {window_end:.3f} s")
        if focus_x is not None and math.isfinite(focus_x):
            summary_parts.append(f"точка {focus_x:.3f} s")
        if unit:
            summary_parts.append(f"единицы {unit}")
        summary = str(action_summary or "").strip() or " | ".join(summary_parts)
        tooltip = title
        if summary:
            tooltip = f"{tooltip} | {summary}"

        plot_preview: dict[str, Any] = {
            "object_name": "CHILD-COMPARE-PLOT",
            "title": title,
            "summary": summary,
            "tooltip": tooltip,
            "series": tuple(series_rows),
        }
        if focus_x is not None and math.isfinite(focus_x):
            plot_preview["focus_x"] = float(focus_x)
        if window_start is not None and window_end is not None:
            plot_preview["window"] = (float(window_start), float(window_end))
        return plot_preview

    def _cycle_compare_playhead(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        artifact = self._selected_results_artifact(runtime, snapshot)
        if not hasattr(runtime, "build_hosted_compare_delta_timeline_preview"):
            self.results_action_label.setText("График сравнения недоступен в текущем окружении.")
            return {"status": "blocked"}
        try:
            preview = runtime.build_hosted_compare_delta_timeline_preview(
                snapshot,
                artifact=artifact,
                series_name=self._selected_chart_series_name(),
            )
        except Exception as exc:
            self.results_action_label.setText(f"Не удалось обновить график сравнения: {exc}")
            return {"status": "failed", "error": str(exc)}
        rows = self._compare_playhead_rows(preview)
        if not rows:
            self.results_action_label.setText("Нет доступных точек графика сравнения.")
            return {"status": "blocked"}
        signature = self._compare_playhead_signature(preview)
        current_index = int(getattr(self, "_results_compare_playhead_selected_index", -1))
        if (
            signature != str(getattr(self, "_results_compare_playhead_signature", "") or "")
            or current_index < 0
            or current_index >= len(rows)
        ):
            current_index = self._default_compare_playhead_index(preview, rows)
        self._results_compare_playhead_signature = signature
        self._results_compare_playhead_selected_index = (current_index + 1) % len(rows)
        return self._show_compare_detail()

    def _cycle_compare_window(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        artifact = self._selected_results_artifact(runtime, snapshot)
        if not hasattr(runtime, "build_hosted_compare_delta_timeline_preview"):
            self.results_action_label.setText("Окно графика сравнения недоступно в текущем окружении.")
            return {"status": "blocked"}
        try:
            preview = runtime.build_hosted_compare_delta_timeline_preview(
                snapshot,
                artifact=artifact,
                series_name=self._selected_chart_series_name(),
            )
        except Exception as exc:
            self.results_action_label.setText(f"Не удалось обновить окно графика сравнения: {exc}")
            return {"status": "failed", "error": str(exc)}
        point_rows = self._compare_playhead_rows(preview)
        window_rows = self._compare_window_rows(preview, point_rows=point_rows)
        if not window_rows:
            self.results_action_label.setText("Нет доступных окон времени на графике сравнения.")
            return {"status": "blocked"}
        signature = self._compare_playhead_signature(preview)
        current_index = int(getattr(self, "_results_compare_window_selected_index", -1))
        if (
            signature != str(getattr(self, "_results_compare_window_signature", "") or "")
            or current_index < 0
            or current_index >= len(window_rows)
        ):
            fallback_index = int(getattr(self, "_results_compare_playhead_selected_index", -1))
            current_index = fallback_index if 0 <= fallback_index < len(window_rows) else 0
        self._results_compare_window_signature = signature
        self._results_compare_window_selected_index = (current_index + 1) % len(window_rows)
        return self._show_compare_detail()

    def _refresh_selected_result_preview(self) -> None:
        if not hasattr(self, "results_artifacts_table"):
            return
        try:
            runtime = self._results_runtime()
            snapshot = runtime.snapshot()
            artifact = self._selected_results_artifact(runtime, snapshot)
            self._populate_compare_preview(runtime, snapshot, artifact=artifact)
            self._populate_chart_preview(runtime, snapshot, artifact=artifact)
            target_path = runtime.compare_viewer_path(snapshot, artifact=artifact)
        except Exception:
            return
        self.results_compare_window_button.setEnabled(target_path is not None)
        self.results_compare_window_button.setToolTip(
            "Показать подробный просмотр сравнения внутри рабочего шага."
            if target_path is not None
            else "Сначала нужен файл результата для сравнения."
        )

        if hasattr(self, "results_compare_next_target_button"):
            self.results_compare_next_target_button.setEnabled(self.results_artifacts_table.rowCount() > 0)
        if hasattr(self, "results_compare_next_signal_button"):
            self.results_compare_next_signal_button.setEnabled(self.results_chart_preview_table.rowCount() > 0)
        if hasattr(self, "results_compare_next_playhead_button"):
            compare_ready = target_path is not None and self.results_chart_preview_table.rowCount() > 0
            self.results_compare_next_playhead_button.setEnabled(compare_ready)
            self.results_compare_next_playhead_button.setToolTip(
                "Переключить следующую точку графика сравнения и сразу обновить панель."
                if compare_ready
                else "Сначала нужен выбранный результат и числовая серия для графика сравнения."
            )
        if hasattr(self, "results_compare_next_window_button"):
            compare_ready = target_path is not None and self.results_chart_preview_table.rowCount() > 0
            self.results_compare_next_window_button.setEnabled(compare_ready)
            self.results_compare_next_window_button.setToolTip(
                "Переключить следующее окно времени на графике сравнения и сразу обновить панель."
                if compare_ready
                else "Сначала нужен выбранный результат и числовая серия для окна времени."
            )

    def _prepare_compare_context(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        path = runtime.write_compare_current_context_sidecar(snapshot)
        self._refresh_results_controls()
        self.results_action_label.setText(
            f"Сравнение подготовлено: {self._path_label(path)}."
        )
        rows = list(_table_snapshot_rows(self.results_compare_preview_table))
        rows.extend(
            (f"График: {label}", value)
            for label, value in _table_snapshot_rows(self.results_chart_preview_table, max_rows=6)
        )
        rows.append(("Контекст сравнения", self._path_label(path), str(path)))
        return self._results_child_dock_payload(
            title="Контекст сравнения",
            object_name="child_dock_results_compare_context",
            content_object_name="CHILD-RESULTS-COMPARE-CONTEXT-CONTENT",
            table_object_name="CHILD-RESULTS-COMPARE-CONTEXT-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
        )

    def _prepare_evidence_manifest(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        path = runtime.write_diagnostics_evidence_manifest(snapshot)
        self._refresh_results_controls()
        self.results_action_label.setText(
            f"Материалы проверки подготовлены: {self._path_label(path)}."
        )
        rows: list[tuple[str, ...]] = [
            ("Материалы проверки", self._path_label(path), str(path)),
            ("Состояние результата", self._status_text(snapshot.result_context_state)),
        ]
        rows.extend(_table_snapshot_rows(self.results_overview_table, max_rows=8))
        rows.extend(
            (f"Материал: {label}", value)
            for label, value in _table_snapshot_rows(self.results_artifacts_table, max_rows=8)
        )
        return self._results_child_dock_payload(
            title="Материалы проверки",
            object_name="child_dock_results_evidence",
            content_object_name="CHILD-RESULTS-EVIDENCE-CONTENT",
            table_object_name="CHILD-RESULTS-EVIDENCE-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
        )

    def _show_run_materials(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        self._refresh_results_controls()
        self.results_action_label.setText(
            "Материалы последнего прогона показаны в дочерней dock-панели."
        )
        rows: list[tuple[str, ...]] = [
            ("Состояние результатов", self._status_text(getattr(snapshot, "result_context_state", ""))),
            (
                "Сводка результатов",
                self._short_text(
                    getattr(snapshot, "result_context_banner", ""),
                    fallback="Свежие результаты пока не найдены.",
                    limit=140,
                ),
            ),
            ("Последний архив", self._path_label(getattr(snapshot, "latest_zip_path", None)), str(getattr(snapshot, "latest_zip_path", "") or "")),
            ("Каталог автопроверки", self._path_label(getattr(snapshot, "latest_autotest_run_dir", None)), str(getattr(snapshot, "latest_autotest_run_dir", "") or "")),
            ("Каталог проверки проекта", self._path_label(getattr(snapshot, "latest_diagnostics_run_dir", None)), str(getattr(snapshot, "latest_diagnostics_run_dir", "") or "")),
            ("Отчёт проверки", self._path_label(getattr(snapshot, "latest_validation_md_path", None)), str(getattr(snapshot, "latest_validation_md_path", "") or "")),
            ("Разбор замечаний", self._path_label(getattr(snapshot, "latest_triage_md_path", None)), str(getattr(snapshot, "latest_triage_md_path", "") or "")),
            ("Файл результата", self._path_label(getattr(snapshot, "latest_npz_path", None)), str(getattr(snapshot, "latest_npz_path", "") or "")),
            ("Данные анимации", self._path_label(getattr(snapshot, "latest_pointer_json_path", None)), str(getattr(snapshot, "latest_pointer_json_path", "") or "")),
            (
                "Выбранный прогон оптимизации",
                self._status_text(getattr(snapshot, "selected_run_contract_status", "")),
                self._short_text(getattr(snapshot, "selected_run_contract_banner", ""), limit=140),
            ),
        ]
        recommendations = tuple(getattr(snapshot, "operator_recommendations", ()) or ())
        if recommendations:
            for index, line in enumerate(recommendations[:4], start=1):
                rows.append((f"Рекомендация {index}", self._short_text(line, limit=160)))
        else:
            rows.append(("Следующий шаг", self._short_text(getattr(snapshot, "suggested_next_step", ""), fallback="Проверьте материалы и выберите сравнение или анимацию.", limit=160)))
        rows.extend(_table_snapshot_rows(self.results_overview_table, max_rows=8))
        rows.extend(
            (f"Материал: {label}", value)
            for label, value in _table_snapshot_rows(self.results_artifacts_table, max_rows=8)
        )
        return self._results_child_dock_payload(
            title="Материалы последнего прогона",
            object_name="child_dock_results_run_materials",
            content_object_name="CHILD-RESULTS-RUN-MATERIALS-CONTENT",
            table_object_name="CHILD-RESULTS-RUN-MATERIALS-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
        )

    def _show_selected_material(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        artifact = self._selected_results_artifact(runtime, snapshot)
        recent_artifacts = tuple(getattr(snapshot, "recent_artifacts", ()) or ())
        if artifact is None and recent_artifacts:
            artifact = recent_artifacts[0]
        if artifact is None:
            self.results_action_label.setText(
                "Карточка выбранного материала недоступна: список результатов пока пуст."
            )
            return self._results_child_dock_payload(
                title="Выбранный материал",
                object_name="child_dock_results_selected_material",
                content_object_name="CHILD-RESULTS-SELECTED-MATERIAL-CONTENT",
                table_object_name="CHILD-RESULTS-SELECTED-MATERIAL-TABLE",
                summary=self.results_action_label.text(),
                rows=(
                    ("Состояние", "материал не найден"),
                    ("Следующий шаг", "Обновите анализ и выберите файл результата или указатель анимации."),
                ),
            )

        artifact_path_raw = getattr(artifact, "path", None)
        artifact_path = Path(artifact_path_raw) if artifact_path_raw is not None else None
        compare_target = runtime.compare_viewer_path(snapshot, artifact=artifact)
        animator_npz = getattr(snapshot, "latest_npz_path", None)
        animator_pointer = getattr(snapshot, "latest_pointer_json_path", None)
        animator_target_paths = getattr(runtime, "animator_target_paths", None)
        if callable(animator_target_paths):
            try:
                animator_npz, animator_pointer = animator_target_paths(snapshot, artifact=artifact)
            except Exception:
                animator_npz = getattr(snapshot, "latest_npz_path", None)
                animator_pointer = getattr(snapshot, "latest_pointer_json_path", None)
        try:
            preview_lines = tuple(runtime.artifact_preview_lines(artifact))
        except Exception:
            preview_lines = ()

        self._populate_compare_preview(runtime, snapshot, artifact=artifact)
        self._populate_chart_preview(runtime, snapshot, artifact=artifact)
        self.results_action_label.setText(
            "Карточка выбранного материала показана в дочерней dock-панели."
        )

        title = self._short_text(
            getattr(artifact, "title", ""),
            fallback=(artifact_path.name if artifact_path is not None else "нет данных"),
            limit=120,
        )
        rows: list[tuple[str, ...]] = [
            ("Выбранный материал", title),
            ("Раздел", self._category_text(getattr(artifact, "category", ""))),
            ("Файл", self._path_label(artifact_path), str(artifact_path or "")),
        ]
        if artifact_path is not None:
            try:
                stat = artifact_path.stat()
            except OSError:
                stat = None
            if stat is not None:
                changed_at = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                rows.append(("Изменён", changed_at))
                if artifact_path.is_file():
                    rows.append(("Размер файла", f"{int(stat.st_size)} байт"))
        detail = self._short_text(getattr(artifact, "detail", ""), fallback="", limit=180)
        if detail:
            rows.append(("Примечание", detail))
        rows.append(("Файл для сравнения", self._path_label(compare_target), str(compare_target or "")))
        rows.append(("Файл анимации", self._path_label(animator_npz), str(animator_npz or "")))
        rows.append(
            (
                "Указатель анимации",
                self._path_label(animator_pointer),
                str(animator_pointer or ""),
            )
        )
        for index, line in enumerate(preview_lines[:6], start=1):
            rows.append((f"Предпросмотр {index}", self._short_text(line, limit=180)))
        rows.append(
            (
                "Следующий шаг",
                "Откройте сравнение или передайте выбранный материал в анимацию."
                if compare_target is not None or animator_npz is not None or animator_pointer is not None
                else "Проверьте, что материал результата сохранён и доступен для сравнения или анимации.",
            )
        )
        return self._results_child_dock_payload(
            title="Выбранный материал",
            object_name="child_dock_results_selected_material",
            content_object_name="CHILD-RESULTS-SELECTED-MATERIAL-CONTENT",
            table_object_name="CHILD-RESULTS-SELECTED-MATERIAL-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
        )

    def _cycle_compare_target(self) -> dict[str, Any]:
        if not hasattr(self, "results_artifacts_table"):
            self.results_action_label.setText("Список материалов сравнения недоступен.")
            return {"status": "blocked"}
        table = self.results_artifacts_table
        if table.rowCount() <= 0:
            self.results_action_label.setText("Список материалов сравнения пуст.")
            return {"status": "blocked"}
        current_row = self._selected_results_artifact_row()
        next_row = (current_row + 1) % table.rowCount() if current_row >= 0 else 0
        self._select_results_artifact_row(next_row)
        return self._show_compare_detail()

    def _cycle_compare_signal(self) -> dict[str, Any]:
        if not hasattr(self, "results_chart_preview_table"):
            self.results_action_label.setText("Список сигналов сравнения недоступен.")
            return {"status": "blocked"}
        table = self.results_chart_preview_table
        if table.rowCount() <= 0:
            self.results_action_label.setText("Нет доступных сигналов для сравнения.")
            return {"status": "blocked"}
        current_row = self._selected_chart_series_row()
        next_row = (current_row + 1) % table.rowCount() if current_row >= 0 else 0
        self._select_chart_series_row(next_row)
        return self._show_compare_detail()

    def _selected_chart_series_name(self) -> str | None:
        if not hasattr(self, "results_chart_preview_table"):
            return None
        table = self.results_chart_preview_table
        row = self._selected_chart_series_row()
        if row < 0 or row >= table.rowCount():
            return None
        item = table.item(row, 0)
        if item is None:
            return None
        series_name = str(item.data(QtCore.Qt.UserRole) or item.text() or "").strip()
        return series_name or None

    def _show_chart_detail(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        artifact = self._selected_results_artifact(runtime, snapshot)
        recent_artifacts = tuple(getattr(snapshot, "recent_artifacts", ()) or ())
        if artifact is None and recent_artifacts:
            artifact = recent_artifacts[0]
        series_name = self._selected_chart_series_name()
        compare_target = runtime.compare_viewer_path(snapshot, artifact=artifact)

        sidecar_artifact = None
        if hasattr(runtime, "artifact_by_key"):
            try:
                sidecar_artifact = runtime.artifact_by_key(snapshot, "compare_current_context_sidecar")
            except Exception:
                sidecar_artifact = None

        chart_preview_payload: Mapping[str, Any] | None = None
        chart_preview_series_samples = getattr(runtime, "chart_preview_series_samples", None)
        if callable(chart_preview_series_samples):
            try:
                chart_preview_payload = chart_preview_series_samples(
                    snapshot,
                    artifact=artifact,
                    series_name=series_name,
                )
            except TypeError:
                chart_preview_payload = chart_preview_series_samples(
                    snapshot,
                    artifact=artifact,
                )
            except Exception:
                chart_preview_payload = None

        self._populate_compare_preview(runtime, snapshot, artifact=artifact)
        self._populate_chart_preview(runtime, snapshot, artifact=artifact)
        self.results_chart_preview_box.setFocus(QtCore.Qt.OtherFocusReason)
        self.results_action_label.setText(
            "Подробности графика показаны в дочерней dock-панели."
        )

        selected_chart_rows = list(_table_snapshot_rows(self.results_chart_preview_table, max_rows=8))
        chart_row = selected_chart_rows[0] if selected_chart_rows else ("Серия", "нет данных")
        if self.results_chart_preview_table.rowCount() > 0:
            selected_rows = self.results_chart_preview_table.selectionModel().selectedRows()
            row_index = selected_rows[0].row() if selected_rows else 0
            chart_row = tuple(
                self._preview_value_text(
                    self.results_chart_preview_table.item(row_index, column).text()
                    if self.results_chart_preview_table.item(row_index, column) is not None
                    else ""
                )
                for column in range(self.results_chart_preview_table.columnCount())
            )

        rows: list[tuple[str, ...]] = [
            ("Выбранная серия", self._short_text(series_name, fallback=chart_row[0] if chart_row else "нет данных", limit=120)),
            ("Файл результата", self._path_label(compare_target), str(compare_target or "")),
            ("Compare-context", self._path_label(getattr(sidecar_artifact, "path", None)), str(getattr(sidecar_artifact, "path", "") or "")),
        ]
        if len(chart_row) >= 4:
            rows.extend(
                (
                    ("Серия в таблице", chart_row[0]),
                    ("Точки", chart_row[1]),
                    ("Диапазон", chart_row[2]),
                    ("Готовность", chart_row[3]),
                )
            )
        if chart_preview_payload is not None:
            rows.extend(
                (
                    ("Состояние серии", self._status_text(chart_preview_payload.get("status"))),
                    ("Серия runtime", self._short_text(chart_preview_payload.get("series"), fallback="нет данных", limit=120)),
                    ("Точек всего", self._preview_value_text(chart_preview_payload.get("point_count"))),
                    ("Конечных точек", self._preview_value_text(chart_preview_payload.get("finite_count"))),
                    ("Runtime-диапазон", self._preview_value_text(chart_preview_payload.get("range"), limit=140)),
                )
            )
            source_path = str(chart_preview_payload.get("source_path") or "")
            rows.append(
                (
                    "Источник samples",
                    self._path_label(Path(source_path)) if source_path else "нет файла",
                    source_path,
                )
            )
            for index, sample in enumerate(tuple(chart_preview_payload.get("samples") or ())[:8], start=1):
                rows.append((f"Sample {index}", self._preview_value_text(sample)))
        if sidecar_artifact is not None and hasattr(runtime, "artifact_preview_lines"):
            try:
                sidecar_lines = tuple(runtime.artifact_preview_lines(sidecar_artifact))
            except Exception:
                sidecar_lines = ()
            for index, line in enumerate(sidecar_lines[:4], start=1):
                rows.append((f"Контекст {index}", self._short_text(line, limit=180)))
        rows.append(
            (
                "Следующий шаг",
                "Откройте сравнение для полного multi-run просмотра или выберите другую серию в таблице графиков.",
            )
        )
        return self._results_child_dock_payload(
            title="Подробности графика",
            object_name="child_dock_results_chart_detail",
            content_object_name="CHILD-RESULTS-CHART-DETAIL-CONTENT",
            table_object_name="CHILD-RESULTS-CHART-DETAIL-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
        )

    def _show_engineering_qa(self) -> dict[str, Any]:
        runtime = self._engineering_analysis_runtime()
        snapshot = runtime.snapshot()
        try:
            candidate_readiness = dict(runtime.selected_run_candidate_readiness(limit=25))
        except Exception as exc:
            candidate_readiness = {
                "candidate_count": 0,
                "ready_candidate_count": 0,
                "missing_inputs_candidate_count": 0,
                "failed_candidate_count": 0,
                "unique_missing_inputs": (f"{type(exc).__name__}: {exc!s}",),
                "unique_blocking_states": (),
                "ready_run_dirs": (),
            }
        self._refresh_results_controls()
        self.results_action_label.setText(
            "Инженерная проверка показана в дочерней dock-панели."
        )

        selected_context = getattr(snapshot, "selected_run_context", None)
        run_id = getattr(selected_context, "run_id", "") if selected_context is not None else ""
        objective_hash = (
            getattr(selected_context, "objective_contract_hash", "")
            if selected_context is not None
            else ""
        )
        hard_gate_key = (
            getattr(selected_context, "hard_gate_key", "")
            if selected_context is not None
            else ""
        )
        run_dir = getattr(snapshot, "run_dir", None)
        manifest_path = getattr(snapshot, "diagnostics_evidence_manifest_path", None)
        rows: list[tuple[str, ...]] = [
            ("Состояние инженерного разбора", self._status_text(getattr(snapshot, "status", ""))),
            ("Данные влияния системы", self._status_text(getattr(snapshot, "influence_status", ""))),
            ("Отчёты подгонки", self._status_text(getattr(snapshot, "calibration_status", ""))),
            ("Сравнение влияния", self._status_text(getattr(snapshot, "compare_status", ""))),
            ("Выбранный прогон", self._status_text(getattr(snapshot, "contract_status", ""))),
            ("Папка выбранного прогона", self._path_label(run_dir), str(run_dir or "")),
            (
                "Материалы инженерного разбора",
                self._status_text(getattr(snapshot, "diagnostics_evidence_manifest_status", "")),
                str(manifest_path or ""),
            ),
            ("Прогон", self._short_text(run_id, fallback="не выбран")),
            ("Целевой профиль", self._short_text(objective_hash, fallback="нет данных", limit=44)),
            ("Обязательное ограничение", self._short_text(hard_gate_key, fallback="нет данных")),
            ("Артефактов разбора", str(len(tuple(getattr(snapshot, "artifacts", ()) or ())))),
            ("Строк чувствительности", str(len(tuple(getattr(snapshot, "sensitivity_rows", ()) or ())))),
            ("Кандидатов к просмотру", str(int(candidate_readiness.get("candidate_count") or 0))),
            ("Готовых кандидатов", str(int(candidate_readiness.get("ready_candidate_count") or 0))),
            (
                "Не хватает входных данных",
                str(int(candidate_readiness.get("missing_inputs_candidate_count") or 0)),
            ),
            ("Ошибочных кандидатов", str(int(candidate_readiness.get("failed_candidate_count") or 0))),
        ]

        blocking_states = tuple(str(item) for item in getattr(snapshot, "blocking_states", ()) or () if str(item).strip())
        for index, item in enumerate(blocking_states[:6], start=1):
            rows.append((f"Блокировка {index}", self._short_text(item, limit=150)))

        for index, item in enumerate(candidate_readiness.get("unique_missing_inputs") or (), start=1):
            if index > 6:
                break
            rows.append((f"Недостаёт {index}", self._short_text(item, limit=150)))

        for index, item in enumerate(candidate_readiness.get("unique_blocking_states") or (), start=1):
            if index > 6:
                break
            rows.append((f"Ограничение кандидата {index}", self._short_text(item, limit=150)))

        ready_run_dirs = tuple(
            str(item)
            for item in candidate_readiness.get("ready_run_dirs") or ()
            if str(item).strip()
        )
        for index, item in enumerate(ready_run_dirs[:4], start=1):
            rows.append((f"Готовый прогон {index}", Path(item).name, item))

        if manifest_path is None:
            rows.append(
                (
                    "Следующий шаг",
                    "Выберите готовый прогон и сформируйте материалы инженерного разбора.",
                )
            )
        else:
            rows.append(
                (
                    "Следующий шаг",
                    "Проверьте материалы разбора и передайте их в проверку проекта.",
                )
            )
        rows.extend(_table_snapshot_rows(self.results_overview_table, max_rows=6))
        return self._results_child_dock_payload(
            title="Инженерная проверка",
            object_name="child_dock_results_engineering_qa",
            content_object_name="CHILD-RESULTS-ENGINEERING-QA-CONTENT",
            table_object_name="CHILD-RESULTS-ENGINEERING-QA-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
        )

    @staticmethod
    def _engineering_row_value(row: Any, key: str, fallback: object = "") -> object:
        if isinstance(row, Mapping):
            return row.get(key, fallback)
        return getattr(row, key, fallback)

    def _show_engineering_candidates(self) -> dict[str, Any]:
        runtime = self._engineering_analysis_runtime()
        snapshot = runtime.snapshot()
        try:
            candidates = tuple(runtime.discover_selected_run_candidates(limit=25))
        except Exception as exc:
            candidates = ()
            discovery_error = f"{type(exc).__name__}: {exc!s}"
        else:
            discovery_error = ""
        try:
            readiness = dict(runtime.selected_run_candidate_readiness(limit=25))
        except Exception:
            readiness = {}

        self._refresh_results_controls()
        self.results_action_label.setText(
            "Кандидаты инженерного анализа показаны в дочерней dock-панели."
        )
        rows: list[tuple[str, ...]] = [
            ("Выбранный прогон", self._status_text(getattr(snapshot, "contract_status", ""))),
            (
                "Файл выбранного прогона",
                self._path_label(getattr(snapshot, "selected_run_contract_path", None)),
                str(getattr(snapshot, "selected_run_contract_path", "") or ""),
            ),
            ("Кандидатов найдено", str(len(candidates) or int(readiness.get("candidate_count") or 0))),
            ("Готовых кандидатов", str(int(readiness.get("ready_candidate_count") or 0))),
            (
                "Не хватает входных данных",
                str(int(readiness.get("missing_inputs_candidate_count") or 0)),
            ),
            ("Ошибочных кандидатов", str(int(readiness.get("failed_candidate_count") or 0))),
        ]
        if discovery_error:
            rows.append(("Ошибка поиска", self._short_text(discovery_error, limit=180)))

        for index, candidate in enumerate(candidates[:25], start=1):
            item = dict(candidate or {})
            bridge_status = self._status_text(item.get("bridge_status") or item.get("status"))
            run_label = self._short_text(
                item.get("run_id") or item.get("run_name"),
                fallback=f"Прогон {index}",
                limit=64,
            )
            progress = (
                f"строк: {int(item.get('row_count') or 0)}; "
                f"готово: {int(item.get('done_count') or 0)}"
            )
            rows.append(
                (
                    f"Кандидат {index}: {run_label}",
                    bridge_status,
                    progress,
                    str(item.get("run_dir") or ""),
                )
            )
            if item.get("status_label"):
                rows.append((f"Состояние кандидата {index}", self._short_text(item.get("status_label"), limit=120)))
            if item.get("result_path"):
                rows.append((f"Результат кандидата {index}", self._path_label(Path(str(item.get("result_path")))), str(item.get("result_path") or "")))
            if item.get("objective_contract_hash"):
                rows.append((f"Цели кандидата {index}", self._short_text(item.get("objective_contract_hash"), limit=44)))
            if item.get("hard_gate_key"):
                rows.append((f"Ограничение кандидата {index}", self._short_text(item.get("hard_gate_key"), limit=80)))
            for missing_index, missing in enumerate(item.get("missing_inputs") or (), start=1):
                if missing_index > 3:
                    break
                rows.append(
                    (
                        f"Недостаёт {index}.{missing_index}",
                        self._short_text(missing, limit=120),
                    )
                )
            for warn_index, warning in enumerate(item.get("warnings") or (), start=1):
                if warn_index > 2:
                    break
                rows.append(
                    (
                        f"Предупреждение {index}.{warn_index}",
                        self._short_text(warning, limit=120),
                    )
                )
            if item.get("error"):
                rows.append((f"Ошибка кандидата {index}", self._short_text(item.get("error"), limit=160)))

        if not candidates:
            rows.append(
                (
                    "Следующий шаг",
                    "Запустите оптимизацию или проверьте папку рабочих прогонов.",
                )
            )
        else:
            rows.append(
                (
                    "Следующий шаг",
                    "Выберите готовый прогон как источник инженерного разбора.",
                )
            )
        return self._results_child_dock_payload(
            title="Кандидаты анализа",
            object_name="child_dock_results_engineering_candidates",
            content_object_name="CHILD-RESULTS-ENGINEERING-CANDIDATES-CONTENT",
            table_object_name="CHILD-RESULTS-ENGINEERING-CANDIDATES-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
        )

    def _pin_engineering_run(self) -> dict[str, Any]:
        def _optional_path(raw: object) -> Path | None:
            if raw is None:
                return None
            text = str(raw).strip()
            return Path(text) if text else None

        runtime = self._engineering_analysis_runtime()
        snapshot = runtime.snapshot()
        discovery_error = ""
        try:
            candidates = tuple(runtime.discover_selected_run_candidates(limit=25))
        except Exception as exc:
            candidates = ()
            discovery_error = f"{type(exc).__name__}: {exc!s}"

        selected_run_dir: Path | None = None
        selected_reason = ""
        for candidate in candidates:
            item = dict(candidate or {})
            status = str(item.get("bridge_status") or item.get("status") or "").strip().upper()
            run_dir_text = str(item.get("run_dir") or "").strip()
            if status == "READY" and run_dir_text:
                selected_run_dir = Path(run_dir_text)
                selected_reason = self._short_text(
                    item.get("run_id") or item.get("run_name"),
                    fallback="готовый кандидат",
                    limit=72,
                )
                break

        if selected_run_dir is None:
            run_dir = getattr(snapshot, "run_dir", None)
            if run_dir is not None:
                selected_run_dir = Path(run_dir)
                selected_reason = "текущий выбранный прогон"

        if selected_run_dir is None:
            self._refresh_results_controls()
            self.results_action_label.setText(
                "Не найден готовый прогон для фиксации в инженерном разборе."
            )
            rows: list[tuple[str, ...]] = [
                ("Состояние", "нужен готовый прогон"),
                ("Кандидатов найдено", str(len(candidates))),
            ]
            if discovery_error:
                rows.append(("Ошибка поиска", self._short_text(discovery_error, limit=180)))
            rows.append(("Следующий шаг", "Запустите оптимизацию или проверьте папку рабочих прогонов."))
            return self._results_child_dock_payload(
                title="Зафиксированный прогон",
                object_name="child_dock_results_engineering_pin_run",
                content_object_name="CHILD-RESULTS-ENGINEERING-PIN-RUN-CONTENT",
                table_object_name="CHILD-RESULTS-ENGINEERING-PIN-RUN-TABLE",
                summary=self.results_action_label.text(),
                rows=rows,
            )

        try:
            result = runtime.export_selected_run_contract_from_run_dir(
                selected_run_dir,
                selected_from="desktop_results_workspace",
            )
        except Exception as exc:
            self._refresh_results_controls()
            self.results_action_label.setText(
                f"Не удалось зафиксировать прогон: {type(exc).__name__}: {exc!s}"
            )
            return self._results_child_dock_payload(
                title="Зафиксированный прогон",
                object_name="child_dock_results_engineering_pin_run",
                content_object_name="CHILD-RESULTS-ENGINEERING-PIN-RUN-CONTENT",
                table_object_name="CHILD-RESULTS-ENGINEERING-PIN-RUN-TABLE",
                summary=self.results_action_label.text(),
                rows=(
                    ("Состояние", "ошибка"),
                    ("Папка прогона", self._path_label(selected_run_dir), str(selected_run_dir)),
                    ("Причина", self._short_text(f"{type(exc).__name__}: {exc!s}", limit=180)),
                    ("Следующий шаг", "Проверьте готовность кандидата и повторите фиксацию."),
                ),
            )

        contract_path = None
        for artifact in tuple(getattr(result, "artifacts", ()) or ()):
            if getattr(artifact, "key", "") == "selected_run_contract_json":
                contract_path = _optional_path(getattr(artifact, "path", None))
                break

        evidence_path = None
        evidence_error = ""
        updated_snapshot = None
        if bool(getattr(result, "ok", False)):
            try:
                updated_snapshot = runtime.snapshot()
            except Exception as exc:
                evidence_error = f"Не удалось обновить состояние: {type(exc).__name__}: {exc!s}"
            else:
                blocked = (
                    getattr(updated_snapshot, "status", "") == "BLOCKED"
                    or getattr(updated_snapshot, "contract_status", "") in {"MISSING", "INVALID", "BLOCKED"}
                )
                if not blocked:
                    try:
                        evidence_path = runtime.write_diagnostics_evidence_manifest(updated_snapshot)
                    except Exception as exc:
                        evidence_error = (
                            "Не удалось автоматически сохранить материалы проверки проекта: "
                            f"{type(exc).__name__}: {exc!s}"
                        )
                else:
                    evidence_error = "Материалы проверки проекта не сохранены: выбранный прогон ещё не готов."

        self._refresh_results_controls()
        if bool(getattr(result, "ok", False)):
            if evidence_path is not None:
                self.results_action_label.setText(
                    "Выбранный прогон зафиксирован; материалы проверки проекта сохранены."
                )
            else:
                self.results_action_label.setText(
                    "Выбранный прогон зафиксирован; материалы проверки проекта не сохранены."
                )
        else:
            self.results_action_label.setText(
                "Не удалось зафиксировать выбранный прогон."
            )

        rows = [
            ("Состояние", self._status_text(getattr(result, "status", ""))),
            ("Источник выбора", selected_reason),
            (
                "Папка прогона",
                self._path_label(_optional_path(getattr(result, "run_dir", selected_run_dir))),
                str(getattr(result, "run_dir", selected_run_dir) or ""),
            ),
        ]
        if contract_path is None and updated_snapshot is not None:
            contract_path = _optional_path(getattr(updated_snapshot, "selected_run_contract_path", None))
        rows.append(("Файл выбранного прогона", self._path_label(contract_path), str(contract_path or "")))
        rows.append(("Материалы проверки проекта", self._path_label(evidence_path), str(evidence_path or "")))
        if discovery_error:
            rows.append(("Предупреждение поиска", self._short_text(discovery_error, limit=180)))
        for index, artifact in enumerate(tuple(getattr(result, "artifacts", ()) or ())[:8], start=1):
            rows.append(
                (
                    f"Материал {index}",
                    self._short_text(getattr(artifact, "title", ""), fallback=getattr(artifact, "key", "материал"), limit=80),
                    self._path_label(getattr(artifact, "path", None)),
                    str(getattr(artifact, "path", "") or ""),
                )
            )
        if getattr(result, "command", ()):
            rows.append(("Порядок запуска", self._short_text(" ".join(str(item) for item in result.command), limit=180)))
        if getattr(result, "log_text", ""):
            rows.append(("Журнал", self._short_text(getattr(result, "log_text", ""), limit=180)))
        if getattr(result, "error", ""):
            rows.append(("Ошибка", self._short_text(getattr(result, "error", ""), limit=180)))
        if evidence_error:
            rows.append(("Материалы проверки проекта", self._short_text(evidence_error, limit=180)))
        rows.append(("Следующий шаг", "Проверьте инженерную проверку и сохраните материалы разбора."))
        return self._results_child_dock_payload(
            title="Зафиксированный прогон",
            object_name="child_dock_results_engineering_pin_run",
            content_object_name="CHILD-RESULTS-ENGINEERING-PIN-RUN-CONTENT",
            table_object_name="CHILD-RESULTS-ENGINEERING-PIN-RUN-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
        )

    def _selected_engineering_run_dir(
        self,
        runtime: DesktopEngineeringAnalysisRuntime,
        snapshot: Any,
    ) -> tuple[Path | None, str, str]:
        run_dir = getattr(snapshot, "run_dir", None)
        if run_dir is not None:
            resolved = runtime.resolve_run_dir(run_dir)
            if resolved is not None:
                return resolved, "выбранный прогон", ""

        try:
            candidates = tuple(runtime.discover_selected_run_candidates(limit=25))
        except Exception as exc:
            return None, "", f"{type(exc).__name__}: {exc!s}"

        for candidate in candidates:
            item = dict(candidate or {})
            status = str(item.get("bridge_status") or item.get("status") or "").strip().upper()
            run_dir_text = str(item.get("run_dir") or "").strip()
            if status != "READY" or not run_dir_text:
                continue
            resolved = runtime.resolve_run_dir(run_dir_text)
            if resolved is not None:
                label = self._short_text(
                    item.get("run_id") or item.get("run_name"),
                    fallback="готовый кандидат",
                    limit=72,
                )
                return resolved, label, ""
        return None, "", ""

    def _start_engineering_analysis_job(
        self,
        *,
        title: str,
        object_name: str,
        content_object_name: str,
        table_object_name: str,
        started_message: str,
        missing_selected_run_message: str,
        missing_next_step: str,
        next_step: str,
        preparation_error_prefix: str,
        success_message: str,
        failure_prefix: str,
        command_builder: Callable[[DesktopEngineeringAnalysisRuntime, Path], Sequence[str]],
    ) -> dict[str, Any]:
        if self._engineering_analysis_process_is_busy():
            self.results_action_label.setText(self.engineering_analysis_status_text)
            return self._show_engineering_analysis_job_dock()

        runtime = self._engineering_analysis_runtime()
        snapshot = runtime.snapshot()
        run_dir, source_label, discovery_error = self._selected_engineering_run_dir(runtime, snapshot)
        if run_dir is None:
            self._refresh_results_controls()
            self.results_action_label.setText(missing_selected_run_message)
            rows: list[tuple[str, ...]] = [
                ("Состояние", "нужен выбранный прогон"),
                ("Выбранный прогон", self._status_text(getattr(snapshot, "contract_status", ""))),
                ("Следующий шаг", missing_next_step),
            ]
            if discovery_error:
                rows.append(("Ошибка поиска кандидатов", self._short_text(discovery_error, limit=180)))
            return self._results_child_dock_payload(
                title=title,
                object_name=object_name,
                content_object_name=content_object_name,
                table_object_name=table_object_name,
                summary=self.results_action_label.text(),
                rows=rows,
            )

        try:
            command = tuple(str(item) for item in command_builder(runtime, run_dir))
        except Exception as exc:
            self._refresh_results_controls()
            self.results_action_label.setText(
                f"{preparation_error_prefix}: {type(exc).__name__}: {exc!s}"
            )
            return self._results_child_dock_payload(
                title=title,
                object_name=object_name,
                content_object_name=content_object_name,
                table_object_name=table_object_name,
                summary=self.results_action_label.text(),
                rows=(
                    ("Состояние", "ошибка подготовки"),
                    ("Папка прогона", self._path_label(run_dir), str(run_dir)),
                    ("Причина", self._short_text(f"{type(exc).__name__}: {exc!s}", limit=180)),
                ),
            )

        self.engineering_analysis_dock_title = title
        self.engineering_analysis_dock_object_name = object_name
        self.engineering_analysis_content_object_name = content_object_name
        self.engineering_analysis_table_object_name = table_object_name
        self.engineering_analysis_next_step = next_step
        self.engineering_analysis_success_text = success_message
        self.engineering_analysis_failure_prefix = failure_prefix
        self.engineering_analysis_process_command = tuple(command)
        self.engineering_analysis_process_run_dir = run_dir
        self.engineering_analysis_source_label = source_label or "выбранный прогон"
        self.engineering_analysis_log_lines = [
            "Команда: " + " ".join(self.engineering_analysis_process_command),
            f"Папка прогона: {run_dir}",
            f"Источник: {self.engineering_analysis_source_label}",
        ]
        self.engineering_analysis_status_text = f"{title} запущен."

        process = QtCore.QProcess(self)
        process.setProgram(self.engineering_analysis_process_command[0])
        process.setArguments(list(self.engineering_analysis_process_command[1:]))
        process.setWorkingDirectory(str(self.repo_root))
        env = QtCore.QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUTF8", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(env)
        process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_engineering_analysis_output)
        process.finished.connect(self._on_engineering_analysis_finished)
        process.errorOccurred.connect(self._on_engineering_analysis_error)
        self.engineering_analysis_process = process
        self._refresh_engineering_analysis_process_state()
        process.start()
        self.results_action_label.setText(started_message)
        return self._show_engineering_analysis_job_dock()

    def _start_engineering_influence_run(self) -> dict[str, Any]:
        return self._start_engineering_analysis_job(
            title="Расчёт влияния системы",
            object_name="child_dock_results_engineering_influence_run",
            content_object_name="CHILD-RESULTS-ENGINEERING-INFLUENCE-RUN-CONTENT",
            table_object_name="CHILD-RESULTS-ENGINEERING-INFLUENCE-RUN-TABLE",
            started_message="Расчёт влияния системы запущен внутри рабочего шага анализа.",
            missing_selected_run_message="Расчёт влияния системы не запущен: сначала нужен выбранный готовый прогон.",
            missing_next_step="Зафиксируйте готовый прогон и повторите расчёт влияния системы.",
            next_step="После завершения откройте «Влияние системы» и проверьте созданные таблицы и графики.",
            preparation_error_prefix="Не удалось подготовить расчёт влияния системы",
            success_message="Расчёт влияния системы завершён успешно.",
            failure_prefix="Не удалось выполнить расчёт влияния системы",
            command_builder=lambda runtime, run_dir: runtime.build_system_influence_command(
                run_dir,
                adaptive_eps=True,
                stage_name="desktop_results_workspace",
            ),
        )

    def _start_engineering_full_report_run(self) -> dict[str, Any]:
        return self._start_engineering_analysis_job(
            title="Полный отчёт",
            object_name="child_dock_results_engineering_full_report_run",
            content_object_name="CHILD-RESULTS-ENGINEERING-FULL-REPORT-RUN-CONTENT",
            table_object_name="CHILD-RESULTS-ENGINEERING-FULL-REPORT-RUN-TABLE",
            started_message="Сборка полного отчёта запущена внутри рабочего шага анализа.",
            missing_selected_run_message="Полный отчёт не запущен: сначала нужен выбранный готовый прогон.",
            missing_next_step="Зафиксируйте готовый прогон и повторите сборку полного отчёта.",
            next_step="После завершения проверьте созданный полный отчёт и затем обновите материалы разбора.",
            preparation_error_prefix="Не удалось подготовить полный отчёт",
            success_message="Полный отчёт завершён успешно.",
            failure_prefix="Не удалось выполнить полный отчёт",
            command_builder=lambda runtime, run_dir: runtime.build_full_report_command(
                run_dir,
                max_plots=12,
            ),
        )

    def _build_param_staging_command_for_results(
        self,
        runtime: DesktopEngineeringAnalysisRuntime,
        run_dir: Path,
    ) -> tuple[str, ...]:
        fit_ranges_path = runtime._resolve_fit_ranges_json(run_dir)
        influence_path = run_dir / "system_influence.json"
        missing: list[str] = []
        if fit_ranges_path is None:
            missing.append("fit_ranges_json")
        if not influence_path.exists():
            missing.append("system_influence_json")
        if missing:
            raise ValueError("missing inputs: " + ", ".join(missing))
        oed_path = run_dir / "oed_report.json"
        return runtime.build_param_staging_command(
            run_dir,
            fit_ranges_json=fit_ranges_path,
            system_influence_json=influence_path,
            oed_report_json=oed_path if oed_path.exists() else None,
            out_dir=run_dir,
        )

    def _start_engineering_param_staging_run(self) -> dict[str, Any]:
        return self._start_engineering_analysis_job(
            title="Диапазоны влияния",
            object_name="child_dock_results_engineering_param_staging_run",
            content_object_name="CHILD-RESULTS-ENGINEERING-PARAM-STAGING-RUN-CONTENT",
            table_object_name="CHILD-RESULTS-ENGINEERING-PARAM-STAGING-RUN-TABLE",
            started_message="Расчёт диапазонов влияния запущен внутри рабочего шага анализа.",
            missing_selected_run_message="Диапазоны влияния не запущены: сначала нужен выбранный готовый прогон.",
            missing_next_step="Зафиксируйте готовый прогон, рассчитайте влияние системы и затем повторите диапазоны влияния.",
            next_step="После завершения проверьте `PARAM_STAGING_INFLUENCE.md`, `stages_influence.json` и затем обновите материалы разбора.",
            preparation_error_prefix="Не удалось подготовить диапазоны влияния",
            success_message="Диапазоны влияния завершены успешно.",
            failure_prefix="Не удалось выполнить диапазоны влияния",
            command_builder=self._build_param_staging_command_for_results,
        )

    def _read_engineering_analysis_output(self) -> None:
        process = self.engineering_analysis_process
        if process is None:
            return
        data = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            text = line.strip()
            if text:
                self.engineering_analysis_log_lines.append(text)

    def _on_engineering_analysis_finished(
        self,
        exit_code: int,
        _exit_status: QtCore.QProcess.ExitStatus,
    ) -> None:
        self._read_engineering_analysis_output()
        if int(exit_code) == 0:
            self.engineering_analysis_status_text = self.engineering_analysis_success_text
        else:
            self.engineering_analysis_status_text = (
                f"{self.engineering_analysis_dock_title} завершён с кодом {int(exit_code)}."
            )
        self.results_action_label.setText(self.engineering_analysis_status_text)
        self._refresh_engineering_analysis_process_state()
        self._refresh_results_controls()

    def _on_engineering_analysis_error(self, error: QtCore.QProcess.ProcessError) -> None:
        self.engineering_analysis_status_text = f"{self.engineering_analysis_failure_prefix}: {error.name}."
        self.engineering_analysis_log_lines.append(self.engineering_analysis_status_text)
        self.results_action_label.setText(self.engineering_analysis_status_text)
        self._refresh_engineering_analysis_process_state()

    def _show_engineering_analysis_job_dock(self) -> dict[str, Any]:
        busy = self._engineering_analysis_process_is_busy()
        rows: list[tuple[str, ...]] = [
            ("Состояние", "выполняется" if busy else self.engineering_analysis_status_text),
            ("Источник", self.engineering_analysis_source_label or "нет данных"),
            (
                "Папка прогона",
                self._path_label(self.engineering_analysis_process_run_dir),
                str(self.engineering_analysis_process_run_dir or ""),
            ),
        ]
        if self.engineering_analysis_process_command:
            rows.append(
                (
                    "Порядок запуска",
                    self._short_text(" ".join(self.engineering_analysis_process_command), limit=180),
                )
            )
        if self.engineering_analysis_log_lines:
            rows.extend(
                (f"Журнал {index}", self._short_text(line, limit=180))
                for index, line in enumerate(self.engineering_analysis_log_lines[-10:], start=1)
            )
        else:
            rows.append(("Журнал", "пока нет сообщений"))
        rows.append(
            (
                "Следующий шаг",
                self.engineering_analysis_next_step,
            )
        )
        return self._results_child_dock_payload(
            title=self.engineering_analysis_dock_title,
            object_name=self.engineering_analysis_dock_object_name,
            content_object_name=self.engineering_analysis_content_object_name,
            table_object_name=self.engineering_analysis_table_object_name,
            summary=self.results_action_label.text(),
            rows=rows,
        )

    def _show_influence_review(self) -> dict[str, Any]:
        runtime = self._engineering_analysis_runtime()
        snapshot = runtime.snapshot()
        try:
            pipeline_rows = tuple(runtime.analysis_workspace_pipeline_status(snapshot))
        except Exception as exc:
            pipeline_rows = (
                {
                    "title": "Состояние последовательности",
                    "status": "WARN",
                    "detail": f"{type(exc).__name__}: {exc!s}",
                    "path": "",
                },
            )
        try:
            chart_table_preview = dict(runtime.analysis_workspace_chart_table_preview(snapshot, max_rows=8))
        except Exception as exc:
            chart_table_preview = {
                "status": "WARN",
                "warnings": (f"{type(exc).__name__}: {exc!s}",),
                "charts": (),
                "tables": (),
                "sensitivity_table": {},
            }
        try:
            validated_artifacts = dict(runtime.validated_artifacts_summary(snapshot))
        except Exception as exc:
            validated_artifacts = {
                "status": "WARN",
                "required_artifact_count": 0,
                "ready_required_artifact_count": 0,
                "missing_required_artifact_count": 0,
                "missing_required_artifacts": (),
                "discovered_artifacts": (),
                "error": f"{type(exc).__name__}: {exc!s}",
            }

        self._refresh_results_controls()
        self.results_action_label.setText(
            "Материалы влияния системы показаны в дочерней dock-панели."
        )
        run_dir = getattr(snapshot, "run_dir", None)
        rows: list[tuple[str, ...]] = [
            ("Состояние инженерного разбора", self._status_text(getattr(snapshot, "status", ""))),
            ("Данные влияния системы", self._status_text(getattr(snapshot, "influence_status", ""))),
            ("Папка выбранного прогона", self._path_label(run_dir), str(run_dir or "")),
            (
                "Обязательные материалы",
                f"{int(validated_artifacts.get('ready_required_artifact_count') or 0)} из "
                f"{int(validated_artifacts.get('required_artifact_count') or 0)}",
                self._status_text(validated_artifacts.get("status")),
            ),
            (
                "Недостающие материалы",
                str(int(validated_artifacts.get("missing_required_artifact_count") or 0)),
            ),
            ("Строк чувствительности", str(len(tuple(getattr(snapshot, "sensitivity_rows", ()) or ())))),
            ("Графиков влияния", str(len(tuple(chart_table_preview.get("charts") or ())))),
            ("Таблиц разбора", str(len(tuple(chart_table_preview.get("tables") or ())))),
        ]

        for index, row in enumerate(pipeline_rows[:10], start=1):
            title = self._short_text(self._engineering_row_value(row, "title"), fallback=f"Шаг {index}", limit=72)
            status = self._status_text(self._engineering_row_value(row, "status"))
            detail = self._short_text(self._engineering_row_value(row, "detail"), limit=120)
            path = self._engineering_row_value(row, "path", "")
            rows.append((f"Шаг разбора {index}: {title}", status, detail, str(path or "")))

        sensitivity_rows = tuple(getattr(snapshot, "sensitivity_rows", ()) or ())
        for index, row in enumerate(sensitivity_rows[:8], start=1):
            param = self._short_text(self._engineering_row_value(row, "param"), fallback=f"Параметр {index}", limit=48)
            score = self._short_text(self._engineering_row_value(row, "score"), fallback="нет данных", limit=32)
            strongest_metric = self._short_text(
                self._engineering_row_value(row, "strongest_metric"),
                fallback="нет данных",
                limit=60,
            )
            status = self._status_text(self._engineering_row_value(row, "status"))
            rows.append((f"Чувствительность {index}: {param}", score, strongest_metric, status))

        sensitivity_table = dict(chart_table_preview.get("sensitivity_table") or {})
        if sensitivity_table:
            rows.append(
                (
                    "Таблица чувствительности",
                    self._status_text(sensitivity_table.get("status")),
                    f"строк: {int(sensitivity_table.get('row_count') or 0)}",
                )
            )

        for index, chart in enumerate(chart_table_preview.get("charts") or (), start=1):
            if index > 5:
                break
            chart_map = dict(chart or {})
            title = self._short_text(chart_map.get("title"), fallback=f"График {index}", limit=72)
            rows.append(
                (
                    f"График влияния {index}",
                    title,
                    f"параметров: {int(chart_map.get('feature_count') or 0)}; "
                    f"целей: {int(chart_map.get('target_count') or 0)}",
                    str(chart_map.get("source_path") or ""),
                )
            )

        for index, table in enumerate(chart_table_preview.get("tables") or (), start=1):
            if index > 5:
                break
            table_map = dict(table or {})
            columns = tuple(str(item) for item in table_map.get("columns") or () if str(item).strip())
            rows.append(
                (
                    f"Таблица {index}",
                    self._short_text(table_map.get("title") or table_map.get("key"), fallback="таблица", limit=72),
                    self._status_text(table_map.get("status")),
                    ", ".join(columns[:4]) if columns else str(table_map.get("source_path") or ""),
                )
            )

        for index, artifact in enumerate(tuple(getattr(snapshot, "artifacts", ()) or ())[:10], start=1):
            rows.append(
                (
                    f"Материал {index}",
                    self._short_text(getattr(artifact, "title", ""), fallback=getattr(artifact, "key", ""), limit=72),
                    self._status_text(getattr(artifact, "status", "READY")),
                    str(getattr(artifact, "path", "") or ""),
                )
            )

        for index, item in enumerate(validated_artifacts.get("missing_required_artifacts") or (), start=1):
            if index > 6:
                break
            item_map = dict(item or {})
            rows.append(
                (
                    f"Нет материала {index}",
                    self._short_text(item_map.get("title") or item_map.get("key"), limit=72),
                    self._status_text(item_map.get("validation_status")),
                    str(item_map.get("path") or ""),
                )
            )

        for index, warning in enumerate(chart_table_preview.get("warnings") or (), start=1):
            if index > 4:
                break
            rows.append((f"Предупреждение {index}", self._short_text(warning, limit=160)))

        return self._results_child_dock_payload(
            title="Влияние системы",
            object_name="child_dock_results_influence_review",
            content_object_name="CHILD-RESULTS-INFLUENCE-REVIEW-CONTENT",
            table_object_name="CHILD-RESULTS-INFLUENCE-REVIEW-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
        )

    def _show_compare_influence(self) -> dict[str, Any]:
        runtime = self._engineering_analysis_runtime()
        snapshot = runtime.snapshot()
        try:
            compare_summary = dict(runtime.analysis_compare_handoff_summary(snapshot))
        except Exception as exc:
            compare_summary = {
                "status": "WARN",
                "run_id": "",
                "run_dir": str(getattr(snapshot, "run_dir", "") or ""),
                "selected_results_ref": "",
                "selected_artifact_dir": "",
                "compare_surface_count": 0,
                "blocking_states": (),
                "warnings": (f"{type(exc).__name__}: {exc!s}",),
            }
        try:
            results_boundary = dict(runtime.analysis_results_boundary_summary(snapshot))
        except Exception as exc:
            results_boundary = {
                "status": "WARN",
                "results_csv_path": "",
                "results_ref_exists": False,
                "artifact_dir": "",
                "artifact_dir_exists": False,
                "rules": (f"{type(exc).__name__}: {exc!s}",),
            }
        try:
            surfaces = tuple(runtime.compare_influence_surfaces(snapshot, top_k=8))
        except Exception as exc:
            surfaces = ()
            compare_summary.setdefault("warnings", ())
            compare_summary["warnings"] = tuple(compare_summary.get("warnings") or ()) + (
                f"{type(exc).__name__}: {exc!s}",
            )

        self._refresh_results_controls()
        self.results_action_label.setText(
            "Сравнение влияния показано в дочерней dock-панели."
        )
        run_dir = getattr(snapshot, "run_dir", None)
        results_path = str(
            compare_summary.get("selected_results_ref")
            or results_boundary.get("results_csv_path")
            or ""
        )
        artifact_dir = str(
            compare_summary.get("selected_artifact_dir")
            or results_boundary.get("artifact_dir")
            or ""
        )
        rows: list[tuple[str, ...]] = [
            ("Готовность сравнения влияния", self._status_text(compare_summary.get("status"))),
            ("Выбранный прогон", self._short_text(compare_summary.get("run_id"), fallback="не выбран")),
            ("Папка выбранного прогона", self._path_label(run_dir), str(run_dir or "")),
            (
                "Файл результатов",
                "найден" if bool(results_boundary.get("results_ref_exists")) else "нужен файл результатов",
                results_path,
            ),
            (
                "Каталог материалов",
                "найден" if bool(results_boundary.get("artifact_dir_exists")) else "нужен каталог материалов",
                artifact_dir,
            ),
            ("Поверхностей влияния", str(len(surfaces) or int(compare_summary.get("compare_surface_count") or 0))),
            (
                "Связь с результатами",
                self._status_text(results_boundary.get("status")),
            ),
        ]

        for index, item in enumerate(compare_summary.get("blocking_states") or (), start=1):
            if index > 6:
                break
            rows.append((f"Блокировка сравнения {index}", self._short_text(item, limit=150)))
        for index, item in enumerate(compare_summary.get("warnings") or (), start=1):
            if index > 6:
                break
            rows.append((f"Предупреждение сравнения {index}", self._short_text(item, limit=150)))

        if not surfaces:
            rows.append(
                (
                    "Следующий шаг",
                    "Сформируйте материалы влияния системы или выберите прогон с готовой поверхностью влияния.",
                )
            )

        for surface_index, surface in enumerate(surfaces[:4], start=1):
            surface_map = dict(surface or {})
            axes = dict(surface_map.get("axes") or {})
            feature_count = len(tuple(axes.get("features") or ()))
            target_count = len(tuple(axes.get("targets") or ()))
            diagnostics = dict(surface_map.get("diagnostics") or {})
            title = self._short_text(
                surface_map.get("title"),
                fallback=f"Поверхность {surface_index}",
                limit=72,
            )
            rows.append(
                (
                    f"Поверхность {surface_index}",
                    title,
                    f"параметров: {feature_count}; целей: {target_count}; "
                    f"ячеек: {int(diagnostics.get('finite_cell_count') or 0)}",
                    str(surface_map.get("source") or ""),
                )
            )
            max_abs = diagnostics.get("max_abs_corr")
            if max_abs not in (None, ""):
                rows.append((f"Максимальная связь {surface_index}", self._short_text(max_abs, limit=32)))

            for cell_index, cell in enumerate(tuple(surface_map.get("top_cells") or ())[:6], start=1):
                cell_map = dict(cell or {})
                feature = self._short_text(cell_map.get("feature"), fallback="параметр", limit=52)
                target = self._short_text(cell_map.get("target"), fallback="цель", limit=52)
                corr = self._short_text(cell_map.get("corr"), fallback="нет данных", limit=32)
                units = " / ".join(
                    part
                    for part in (
                        str(cell_map.get("feature_unit") or "").strip(),
                        str(cell_map.get("target_unit") or "").strip(),
                    )
                    if part
                )
                rows.append(
                    (
                        f"Связь {surface_index}.{cell_index}",
                        feature,
                        target,
                        f"{corr}; {units}" if units else corr,
                    )
                )

        for index, rule in enumerate(results_boundary.get("rules") or (), start=1):
            if index > 3:
                break
            rows.append((f"Правило {index}", self._short_text(rule, limit=150)))

        return self._results_child_dock_payload(
            title="Сравнение влияния",
            object_name="child_dock_results_compare_influence",
            content_object_name="CHILD-RESULTS-COMPARE-INFLUENCE-CONTENT",
            table_object_name="CHILD-RESULTS-COMPARE-INFLUENCE-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
        )

    def _export_engineering_evidence(self) -> dict[str, Any]:
        runtime = self._engineering_analysis_runtime()
        snapshot = runtime.snapshot()
        surfaces: tuple[Mapping[str, Any], ...] | None = None
        surface_error = ""
        try:
            surfaces = tuple(runtime.compare_influence_surfaces(snapshot, top_k=12))
        except Exception as exc:
            surface_error = f"{type(exc).__name__}: {exc!s}"

        try:
            path = runtime.write_diagnostics_evidence_manifest(
                snapshot,
                compare_surfaces=surfaces,
            )
            payload = {}
            try:
                payload_obj = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
                payload = dict(payload_obj) if isinstance(payload_obj, Mapping) else {}
            except Exception:
                payload = {}
            self._refresh_results_controls()
            self.results_action_label.setText(
                f"Материалы инженерного разбора сохранены: {self._path_label(path)}."
            )
            validation = dict(payload.get("validation") or {})
            validated = dict(payload.get("validated_artifacts") or {})
            compare_diag = dict(payload.get("compare_influence_diagnostics") or {})
            rows: list[tuple[str, ...]] = [
                ("Материалы инженерного разбора", self._path_label(path), str(path)),
                (
                    "Метка материалов",
                    self._short_text(payload.get("evidence_manifest_hash"), fallback="нет данных", limit=44),
                ),
                ("Состояние разбора", self._status_text(validation.get("status") or getattr(snapshot, "status", ""))),
                ("Данные влияния", self._status_text(validation.get("influence_status") or getattr(snapshot, "influence_status", ""))),
                ("Отчёты подгонки", self._status_text(validation.get("calibration_status") or getattr(snapshot, "calibration_status", ""))),
                ("Сравнение влияния", self._status_text(validation.get("compare_status") or getattr(snapshot, "compare_status", ""))),
                (
                    "Выбранный прогон",
                    self._status_text(validation.get("selected_run_contract_status") or getattr(snapshot, "contract_status", "")),
                ),
                (
                    "Артефактов выбрано",
                    str(len(tuple(payload.get("selected_artifact_list") or ()))),
                ),
                (
                    "Обязательные материалы",
                    f"{int(validated.get('ready_required_artifact_count') or 0)} из "
                    f"{int(validated.get('required_artifact_count') or 0)}",
                ),
                ("Таблиц выбрано", str(len(tuple(payload.get("selected_tables") or ())))),
                ("Графиков выбрано", str(len(tuple(payload.get("selected_charts") or ())))),
                ("Поверхностей влияния", str(int(compare_diag.get("surface_count") or 0))),
            ]
            if surface_error:
                rows.append(("Предупреждение поверхностей", self._short_text(surface_error, limit=160)))

            for index, warning in enumerate(validation.get("warnings") or (), start=1):
                if index > 6:
                    break
                rows.append((f"Предупреждение {index}", self._short_text(warning, limit=160)))
            for index, item in enumerate(validated.get("missing_required_artifacts") or (), start=1):
                if index > 6:
                    break
                item_map = dict(item or {})
                rows.append(
                    (
                        f"Нет материала {index}",
                        self._short_text(item_map.get("title") or item_map.get("key"), limit=72),
                        self._status_text(item_map.get("validation_status")),
                        str(item_map.get("path") or ""),
                    )
                )
            for index, title in enumerate(compare_diag.get("surface_titles") or (), start=1):
                if index > 6:
                    break
                rows.append((f"Поверхность влияния {index}", self._short_text(title, limit=120)))
            rows.append(
                (
                    "Следующий шаг",
                    "Откройте Диагностику и проверьте материалы проекта перед сохранением архива.",
                )
            )
            return self._results_child_dock_payload(
                title="Материалы инженерного разбора",
                object_name="child_dock_results_engineering_evidence",
                content_object_name="CHILD-RESULTS-ENGINEERING-EVIDENCE-CONTENT",
                table_object_name="CHILD-RESULTS-ENGINEERING-EVIDENCE-TABLE",
                summary=self.results_action_label.text(),
                rows=rows,
            )
        except Exception as exc:
            self._refresh_results_controls()
            self.results_action_label.setText(
                f"Не удалось сохранить материалы инженерного разбора: {type(exc).__name__}: {exc!s}"
            )
            return self._results_child_dock_payload(
                title="Материалы инженерного разбора",
                object_name="child_dock_results_engineering_evidence",
                content_object_name="CHILD-RESULTS-ENGINEERING-EVIDENCE-CONTENT",
                table_object_name="CHILD-RESULTS-ENGINEERING-EVIDENCE-TABLE",
                summary=self.results_action_label.text(),
                rows=(
                    ("Состояние", "ошибка"),
                    ("Причина", self._short_text(f"{type(exc).__name__}: {exc!s}", limit=180)),
                    ("Следующий шаг", "Проверьте выбранный прогон и материалы влияния системы."),
                ),
            )

    def _export_engineering_animation_link(self) -> dict[str, Any]:
        runtime = self._engineering_analysis_runtime()
        snapshot = runtime.snapshot()
        results_runtime = self._results_runtime()
        results_snapshot = results_runtime.snapshot()
        artifact = self._selected_results_artifact(results_runtime, results_snapshot)
        pointer = getattr(artifact, "path", None)
        if pointer is None:
            pointer = (
                getattr(results_snapshot, "latest_npz_path", None)
                or getattr(results_snapshot, "latest_pointer_json_path", None)
            )
        if pointer is None:
            fallback_artifact = results_runtime.animation_handoff_artifact(results_snapshot)
            pointer = getattr(fallback_artifact, "path", None)

        compare_contract: Mapping[str, Any] | None = None
        compare_summary: dict[str, Any] = {}
        try:
            compare_summary = dict(runtime.analysis_compare_handoff_summary(snapshot))
            compare_contract = dict(compare_summary.get("analysis_compare_contract") or {})
        except Exception:
            compare_contract = None

        try:
            payload = runtime.export_analysis_to_animator_link_contract(
                snapshot,
                selected_result_artifact_pointer=pointer,
                compare_contract=compare_contract,
            )
            try:
                animator_summary = dict(runtime.analysis_animator_handoff_summary(snapshot))
            except Exception:
                animator_summary = {}
            self._refresh_results_controls()
            self.results_action_label.setText(
                "Связь с анимацией подготовлена в дочерней dock-панели."
            )
            pointer_payload = dict(payload.get("selected_result_artifact_pointer") or {})
            link_payload = dict(payload.get("animator_link_contract") or {})
            rows: list[tuple[str, ...]] = [
                ("Состояние связи", self._status_text(animator_summary.get("status") or link_payload.get("ready_state"))),
                (
                    "Данные анализа",
                    self._path_label(Path(str(payload.get("analysis_context_path") or ""))),
                    str(payload.get("analysis_context_path") or ""),
                ),
                (
                    "Файл связи",
                    self._path_label(Path(str(payload.get("animator_link_contract_path") or ""))),
                    str(payload.get("animator_link_contract_path") or ""),
                ),
                (
                    "Метка связи",
                    self._short_text(
                        payload.get("animator_link_contract_hash")
                        or link_payload.get("animator_link_contract_hash"),
                        fallback="нет данных",
                        limit=44,
                    ),
                ),
                (
                    "Метка данных анализа",
                    self._short_text(payload.get("analysis_context_hash"), fallback="нет данных", limit=44),
                ),
                (
                    "Выбранный результат",
                    "найден" if bool(pointer_payload.get("exists")) else "нужен файл результата",
                    str(pointer_payload.get("path") or pointer or ""),
                ),
                ("Прогон", self._short_text(link_payload.get("run_id"), fallback="не выбран")),
                ("Испытание", self._short_text(link_payload.get("selected_test_id"), fallback="не выбрано")),
                ("Участок", self._short_text(link_payload.get("selected_segment_id"), fallback="весь результат")),
            ]
            for index, item in enumerate(link_payload.get("blocking_states") or (), start=1):
                if index > 6:
                    break
                rows.append((f"Блокировка {index}", self._short_text(item, limit=150)))
            for index, item in enumerate(link_payload.get("warnings") or (), start=1):
                if index > 6:
                    break
                rows.append((f"Предупреждение {index}", self._short_text(item, limit=150)))
            for index, item in enumerate(link_payload.get("rules") or (), start=1):
                if index > 3:
                    break
                rows.append((f"Правило {index}", self._short_text(item, limit=150)))
            rows.append(
                (
                    "Следующий шаг",
                    "Откройте рабочий шаг Анимация и проверьте движение выбранного результата.",
                )
            )
            return self._results_child_dock_payload(
                title="Связь с анимацией",
                object_name="child_dock_results_engineering_animation_link",
                content_object_name="CHILD-RESULTS-ENGINEERING-ANIMATION-LINK-CONTENT",
                table_object_name="CHILD-RESULTS-ENGINEERING-ANIMATION-LINK-TABLE",
                summary=self.results_action_label.text(),
                rows=rows,
            )
        except Exception as exc:
            self._refresh_results_controls()
            self.results_action_label.setText(
                f"Не удалось подготовить связь с анимацией: {type(exc).__name__}: {exc!s}"
            )
            rows: list[tuple[str, ...]] = [
                ("Состояние", "ошибка"),
                ("Причина", self._short_text(f"{type(exc).__name__}: {exc!s}", limit=180)),
                ("Выбранный результат", self._path_label(pointer), str(pointer or "")),
            ]
            if compare_summary:
                rows.append(("Сравнение влияния", self._status_text(compare_summary.get("status"))))
            rows.append(("Следующий шаг", "Выберите файл результата и повторите подготовку связи."))
            return self._results_child_dock_payload(
                title="Связь с анимацией",
                object_name="child_dock_results_engineering_animation_link",
                content_object_name="CHILD-RESULTS-ENGINEERING-ANIMATION-LINK-CONTENT",
                table_object_name="CHILD-RESULTS-ENGINEERING-ANIMATION-LINK-TABLE",
                summary=self.results_action_label.text(),
                rows=rows,
            )

    def _prepare_animation_handoff(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        artifact = self._selected_results_artifact(runtime, snapshot)
        path = runtime.write_analysis_animation_handoff(snapshot, artifact=artifact)
        self._refresh_results_controls()
        self.results_action_label.setText(
            f"Материал передан в анимацию: {self._path_label(path)}."
        )
        artifact_path = getattr(artifact, "path", None)
        rows: list[tuple[str, ...]] = [
            ("Передача в анимацию", self._path_label(path), str(path)),
            (
                "Выбранный материал",
                Path(artifact_path).name if artifact_path is not None else "используется последний результат",
                str(artifact_path or getattr(snapshot, "latest_npz_path", "") or ""),
            ),
            ("Следующий шаг", "Откройте рабочий шаг «Анимация» и проверьте движение/мнемосхему."),
        ]
        rows.extend(_table_snapshot_rows(self.results_compare_preview_table, max_rows=6))
        rows.extend(
            (f"График: {label}", value)
            for label, value in _table_snapshot_rows(self.results_chart_preview_table, max_rows=6)
        )
        return self._results_child_dock_payload(
            title="Передача в анимацию",
            object_name="child_dock_results_animation_handoff",
            content_object_name="CHILD-RESULTS-ANIMATION-HANDOFF-CONTENT",
            table_object_name="CHILD-RESULTS-ANIMATION-HANDOFF-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
        )

    def _selected_results_artifact(
        self,
        runtime: DesktopResultsRuntime,
        snapshot: Any,
    ) -> Any:
        selected_rows = self.results_artifacts_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        item = self.results_artifacts_table.item(row, 0)
        if item is None:
            return None
        key = str(item.data(QtCore.Qt.UserRole) or "").strip()
        if not key:
            return None
        return runtime.artifact_by_key(snapshot, key)

    def _compare_contract_rows(
        self,
        snapshot: Any,
        compare_payload: Mapping[str, Any] | None,
    ) -> list[tuple[str, ...]]:
        payload = dict(compare_payload or {})
        mismatch_summary = dict(payload.get("mismatch_summary") or {})
        mismatch_banner = dict(payload.get("mismatch_banner") or {})
        result_context = dict(payload.get("result_context") or {})
        selected_contract = dict(payload.get("optimizer_selected_run_contract") or {})
        artifacts = dict(payload.get("artifacts") or {})

        current_context = dict(payload.get("current_context_ref") or result_context.get("current") or {})
        selected_context = dict(payload.get("selected_context_ref") or result_context.get("selected") or {})
        snapshot_fields = tuple(getattr(snapshot, "result_context_fields", ()) or ())
        if not current_context:
            current_context = {
                str(getattr(field, "key", "") or "").strip(): getattr(field, "current_value", "")
                for field in snapshot_fields
                if str(getattr(field, "key", "") or "").strip()
                and getattr(field, "current_value", "")
            }
        if not selected_context:
            selected_context = {
                str(getattr(field, "key", "") or "").strip(): getattr(field, "selected_value", "")
                for field in snapshot_fields
                if str(getattr(field, "key", "") or "").strip()
                and getattr(field, "selected_value", "")
            }

        mismatches = list(mismatch_banner.get("mismatches") or mismatch_summary.get("mismatches") or ())
        if not mismatches:
            mismatches = [
                {
                    "key": getattr(field, "key", ""),
                    "title": getattr(field, "title", ""),
                    "current": getattr(field, "current_value", ""),
                    "selected": getattr(field, "selected_value", ""),
                    "detail": getattr(field, "detail", ""),
                }
                for field in snapshot_fields
                if str(getattr(field, "status", "") or "").upper() == "STALE"
            ]

        rows: list[tuple[str, ...]] = []
        context_state = (
            result_context.get("state")
            or mismatch_summary.get("state")
            or getattr(snapshot, "result_context_state", "")
        )
        rows.append(("Состояние данных", self._status_text(context_state)))

        context_banner = (
            mismatch_summary.get("banner")
            or getattr(snapshot, "result_context_banner", "")
            or getattr(snapshot, "result_context_detail", "")
        )
        if context_banner:
            rows.append(("Сводка контекста", self._short_text(context_banner, limit=180)))

        context_detail = mismatch_summary.get("detail") or getattr(snapshot, "result_context_detail", "")
        if context_detail:
            rows.append(("Деталь контекста", self._short_text(context_detail, limit=180)))

        required_action = (
            mismatch_summary.get("required_action")
            or getattr(snapshot, "result_context_action", "")
        )
        if required_action:
            rows.append(("Требуемое действие", self._short_text(required_action, limit=180)))

        banner_id = str(mismatch_banner.get("banner_id") or "").strip()
        if banner_id:
            rows.append(("Маркер согласования", banner_id))

        selected_contract_status = (
            selected_contract.get("status")
            or getattr(snapshot, "selected_run_contract_status", "")
        )
        rows.append(("Контракт выбранного прогона", self._status_text(selected_contract_status)))

        selected_contract_path = str(
            selected_contract.get("path")
            or artifacts.get("selected_run_contract_path")
            or getattr(snapshot, "selected_run_contract_path", "")
            or ""
        ).strip()
        if selected_contract_path:
            rows.append(
                (
                    "Файл выбранного прогона",
                    self._path_label(Path(selected_contract_path)),
                    selected_contract_path,
                )
            )

        selected_contract_hash = str(
            selected_contract.get("hash")
            or getattr(snapshot, "selected_run_contract_hash", "")
            or ""
        ).strip()
        if selected_contract_hash:
            rows.append(
                (
                    "Метка выбранного прогона",
                    self._short_text(selected_contract_hash, limit=48),
                )
            )

        for prefix, context_map in (
            ("Текущее", current_context),
            ("Выбранное", selected_context),
        ):
            for index, (key, value) in enumerate(context_map.items(), start=1):
                if index > 4:
                    break
                rows.append(
                    (
                        f"{prefix}: {self._short_text(key, limit=48)}",
                        self._short_text(value, limit=140),
                    )
                )

        rows.append(("Несовпадений", str(len(mismatches))))
        for index, mismatch in enumerate(mismatches[:6], start=1):
            mismatch_map = dict(mismatch) if isinstance(mismatch, Mapping) else {}
            title = self._short_text(
                mismatch_map.get("title") or mismatch_map.get("key") or f"поле {index}",
                limit=72,
            )
            current_value = self._short_text(
                mismatch_map.get("current"),
                fallback="не задано",
                limit=72,
            )
            selected_value = self._short_text(
                mismatch_map.get("selected"),
                fallback="не задано",
                limit=72,
            )
            rows.append(
                (
                    f"Несовпадение {index}",
                    f"{title}: текущее {current_value}; выбранное {selected_value}",
                )
                )
            detail = str(mismatch_map.get("detail") or "").strip()
            if detail:
                rows.append((f"Причина {index}", self._short_text(detail, limit=180)))
        return rows

    def _show_compare_detail(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        artifact = self._selected_results_artifact(runtime, snapshot)
        target_path = runtime.compare_viewer_path(snapshot, artifact=artifact)
        if target_path is None:
            self._refresh_results_controls()
            self.results_action_label.setText(
                "Сравнение пока недоступно: нужен файл результата расчёта."
            )
            return {"status": "blocked"}
        try:
            sidecar_path = runtime.write_compare_current_context_sidecar(snapshot)
        except Exception as exc:
            self._refresh_results_controls()
            self.results_action_label.setText(f"Не удалось подготовить сравнение: {exc}")
            return {"status": "failed", "error": str(exc)}

        compare_payload: Mapping[str, Any] | None = None
        if hasattr(runtime, "build_compare_current_context_sidecar"):
            try:
                compare_payload = runtime.build_compare_current_context_sidecar(snapshot)
            except Exception:
                compare_payload = None
        hosted_compare_contract: Mapping[str, Any] | None = None
        if hasattr(runtime, "build_hosted_compare_contract_preview"):
            try:
                hosted_compare_contract = runtime.build_hosted_compare_contract_preview(
                    snapshot,
                    artifact=artifact,
                    series_name=self._selected_chart_series_name(),
                )
            except Exception:
                hosted_compare_contract = None
        hosted_compare_session: Mapping[str, Any] | None = None
        if hasattr(runtime, "build_hosted_compare_session_preview"):
            try:
                hosted_compare_session = runtime.build_hosted_compare_session_preview(
                    snapshot,
                    artifact=artifact,
                    series_name=self._selected_chart_series_name(),
                    current_context_path=sidecar_path,
                )
            except Exception:
                hosted_compare_session = None
        hosted_compare_peak_heat: Mapping[str, Any] | None = None
        if hasattr(runtime, "build_hosted_compare_peak_heat_preview"):
            try:
                hosted_compare_peak_heat = runtime.build_hosted_compare_peak_heat_preview(
                    snapshot,
                    artifact=artifact,
                    series_name=self._selected_chart_series_name(),
                )
            except Exception:
                hosted_compare_peak_heat = None
        hosted_compare_delta_timeline: Mapping[str, Any] | None = None
        if hasattr(runtime, "build_hosted_compare_delta_timeline_preview"):
            try:
                hosted_compare_delta_timeline = runtime.build_hosted_compare_delta_timeline_preview(
                    snapshot,
                    artifact=artifact,
                    series_name=self._selected_chart_series_name(),
                )
            except Exception:
                hosted_compare_delta_timeline = None
        hosted_compare_open_timeline: Mapping[str, Any] | None = None
        if hasattr(runtime, "build_hosted_compare_open_timeline_preview"):
            try:
                hosted_compare_open_timeline = runtime.build_hosted_compare_open_timeline_preview(
                    snapshot,
                    artifact=artifact,
                )
            except Exception:
                hosted_compare_open_timeline = None

        self._populate_compare_preview(runtime, snapshot, artifact=artifact)
        self._populate_chart_preview(runtime, snapshot, artifact=artifact)
        self.results_compare_preview_box.setFocus(QtCore.Qt.OtherFocusReason)
        active_pair_label = ""
        active_signal_label = ""
        active_playhead_time_text = ""
        active_window_text = ""
        if hosted_compare_session:
            timeline_target = dict(hosted_compare_session.get("timeline_target") or {})
            active_pair_label = str(timeline_target.get("pair_label") or "").strip()
            active_signal_label = str(timeline_target.get("signal") or "").strip()
        if not active_signal_label:
            active_signal_label = str(self._selected_chart_series_name() or "").strip()
        selected_playhead_index = -1
        selected_playhead_row: dict[str, Any] | None = None
        selected_playhead_rows: tuple[dict[str, Any], ...] = ()
        selected_window_index = -1
        selected_window_row: dict[str, Any] | None = None
        selected_window_rows: tuple[dict[str, Any], ...] = ()
        if hosted_compare_delta_timeline:
            (
                selected_playhead_index,
                selected_playhead_row,
                selected_playhead_rows,
            ) = self._selected_compare_playhead_row(hosted_compare_delta_timeline)
            if selected_playhead_row is not None:
                try:
                    active_playhead_time_text = f"{float(selected_playhead_row.get('time_s')):.3f} s"
                except Exception:
                    active_playhead_time_text = ""
            (
                selected_window_index,
                selected_window_row,
                selected_window_rows,
            ) = self._selected_compare_window_row(
                hosted_compare_delta_timeline,
                selected_playhead_index=selected_playhead_index,
                point_rows=selected_playhead_rows,
            )
            if selected_window_row is not None:
                try:
                    active_window_text = (
                        f"{float(selected_window_row.get('start_s')):.3f} .. "
                        f"{float(selected_window_row.get('end_s')):.3f} s"
                    )
                except Exception:
                    active_window_text = ""
        status_message = (
            f"Сравнение показано в рабочем шаге: {self._path_label(target_path)}; контекст {self._path_label(sidecar_path)}"
        )
        if active_pair_label:
            status_message += f"; пара {self._short_text(active_pair_label, limit=120)}"
        if active_signal_label:
            status_message += f"; сигнал {self._short_text(active_signal_label, limit=120)}"
        if active_window_text:
            status_message += f"; окно {active_window_text}"
        if active_playhead_time_text:
            status_message += f"; точка {active_playhead_time_text}"
        self.results_action_label.setText(f"{status_message}.")
        compare_plot_preview = self._build_compare_plot_preview(
            hosted_compare_delta_timeline,
            selected_playhead_row=selected_playhead_row,
            selected_window_row=selected_window_row,
            active_pair_label=active_pair_label,
            active_signal_label=active_signal_label,
            action_summary=self.results_action_label.text(),
        )

        rows = list(_table_snapshot_rows(self.results_compare_preview_table))
        rows.extend(
            (f"График: {label}", value)
            for label, value in _table_snapshot_rows(self.results_chart_preview_table, max_rows=8)
        )
        rows.append(("Файл результата", self._path_label(target_path), str(target_path)))
        rows.append(("Контекст сравнения", self._path_label(sidecar_path), str(sidecar_path)))
        rows.extend(self._compare_contract_rows(snapshot, compare_payload))
        if hosted_compare_contract:
            compare_status = str(hosted_compare_contract.get("status") or "").strip()
            if compare_status:
                rows.append(("Compare contract status", compare_status))
            selected_table = str(hosted_compare_contract.get("selected_table") or "").strip()
            if selected_table:
                rows.append(("Compare table", selected_table))
            selected_metrics = [
                str(value).strip()
                for value in list(hosted_compare_contract.get("selected_metrics") or ())
                if str(value).strip()
            ]
            if selected_metrics:
                rows.append(
                    (
                        "Compare signals",
                        self._short_text(", ".join(selected_metrics), limit=180),
                    )
                )
            selected_time_window = list(hosted_compare_contract.get("selected_time_window") or ())
            if len(selected_time_window) >= 2:
                try:
                    rows.append(
                        (
                            "Compare window",
                            f"{float(selected_time_window[0]):.3f} .. {float(selected_time_window[1]):.3f}",
                        )
                    )
                except Exception:
                    pass
            alignment_mode = str(hosted_compare_contract.get("alignment_mode") or "").strip()
            if alignment_mode:
                rows.append(("Compare alignment", alignment_mode))
            run_ref_source = str(hosted_compare_contract.get("run_ref_source") or "").strip()
            if run_ref_source:
                rows.append(("Compare ref source", run_ref_source))
            compare_contract_hash = str(hosted_compare_contract.get("compare_contract_hash") or "").strip()
            if compare_contract_hash:
                rows.append(("Compare contract hash", self._short_text(compare_contract_hash, limit=48)))
            mismatch_banner_text = str(hosted_compare_contract.get("mismatch_banner_text") or "").strip()
            if mismatch_banner_text:
                rows.append(
                    (
                        "Compare banner",
                        self._short_text(mismatch_banner_text, limit=220),
                    )
                )
            for index, line in enumerate(hosted_compare_contract.get("summary_lines") or (), start=1):
                text = str(line or "").strip()
                if text:
                    rows.append((f"Compare summary {index}", self._short_text(text, limit=220)))
        if hosted_compare_session:
            session_source = str(hosted_compare_session.get("session_source") or "").strip()
            if session_source:
                rows.append(("Compare session source", session_source))
            mode = str(hosted_compare_session.get("mode") or "").strip()
            if mode:
                rows.append(("Compare session mode", mode))
            run_refs_count = hosted_compare_session.get("run_refs_count")
            if run_refs_count not in (None, ""):
                rows.append(("Compare session runs", self._preview_value_text(run_refs_count)))
            npz_count = hosted_compare_session.get("npz_count")
            if npz_count not in (None, ""):
                rows.append(("Compare session npz", self._preview_value_text(npz_count)))
            reference_label = str(hosted_compare_session.get("reference_label") or "").strip()
            if reference_label:
                rows.append(("Compare session ref", self._short_text(reference_label, limit=120)))
            playhead_t = hosted_compare_session.get("playhead_t")
            if playhead_t not in (None, ""):
                try:
                    rows.append(("Compare session playhead", f"{float(playhead_t):.3f} s"))
                except Exception:
                    pass
            timeline_target = dict(hosted_compare_session.get("timeline_target") or {})
            target_signal = str(timeline_target.get("signal") or "").strip()
            if target_signal:
                rows.append(("Compare session target signal", self._short_text(target_signal, limit=120)))
            pair_label = str(timeline_target.get("pair_label") or "").strip()
            if pair_label:
                rows.append(("Compare session pair", self._short_text(pair_label, limit=180)))
            target_window = list(timeline_target.get("time_window") or ())
            if len(target_window) >= 2:
                try:
                    rows.append(
                        (
                            "Compare session target window",
                            f"{float(target_window[0]):.3f} .. {float(target_window[1]):.3f}",
                        )
                    )
                except Exception:
                    pass
            for index, label in enumerate(hosted_compare_session.get("labels") or (), start=1):
                text = str(label or "").strip()
                if text:
                    rows.append((f"Compare session run {index}", self._short_text(text, limit=120)))
            for index, item in enumerate(hosted_compare_session.get("run_rows") or (), start=1):
                run_row = dict(item) if isinstance(item, Mapping) else {}
                label = str(run_row.get("label") or "").strip()
                if not label:
                    continue
                value_parts = []
                role = str(run_row.get("role") or "").strip()
                if role:
                    value_parts.append(f"role={role}")
                source = str(run_row.get("source") or "").strip()
                if source:
                    value_parts.append(f"source={source}")
                run_id = str(run_row.get("run_id") or "").strip()
                if run_id and run_id != label:
                    value_parts.append(f"run_id={run_id}")
                path_name = str(run_row.get("path_name") or "").strip()
                if path_name:
                    value_parts.append(f"path={path_name}")
                rows.append(
                    (
                        f"Compare session item {index}",
                        self._short_text(f"{label} | {' | '.join(value_parts)}", limit=220),
                    )
                )
            for index, line in enumerate(hosted_compare_session.get("summary_lines") or (), start=1):
                text = str(line or "").strip()
                if text:
                    rows.append(
                        (f"Compare session summary {index}", self._short_text(text, limit=220))
                    )
        if hosted_compare_peak_heat:
            peak_status = str(hosted_compare_peak_heat.get("status") or "").strip()
            if peak_status:
                rows.append(("Peak heat status", peak_status))
            table_name = str(hosted_compare_peak_heat.get("table") or "").strip()
            if table_name:
                rows.append(("Peak heat table", table_name))
            run_count = hosted_compare_peak_heat.get("run_count")
            if run_count not in (None, ""):
                rows.append(("Peak heat runs", self._preview_value_text(run_count)))
            signal_count = hosted_compare_peak_heat.get("signal_count")
            if signal_count not in (None, ""):
                rows.append(("Peak heat signals", self._preview_value_text(signal_count)))
            reference_label = str(hosted_compare_peak_heat.get("reference_label") or "").strip()
            if reference_label:
                rows.append(("Peak heat ref", self._short_text(reference_label, limit=120)))
            compare_label = str(hosted_compare_peak_heat.get("compare_label") or "").strip()
            if compare_label:
                rows.append(("Peak heat compare", self._short_text(compare_label, limit=120)))
            hotspot_signal = str(hosted_compare_peak_heat.get("hotspot_signal") or "").strip()
            if hotspot_signal:
                rows.append(("Peak heat hotspot signal", self._short_text(hotspot_signal, limit=120)))
            hotspot_run = str(hosted_compare_peak_heat.get("hotspot_run") or "").strip()
            if hotspot_run:
                rows.append(("Peak heat hotspot run", self._short_text(hotspot_run, limit=120)))
            hotspot_time = hosted_compare_peak_heat.get("hotspot_time")
            if hotspot_time not in (None, ""):
                try:
                    rows.append(("Peak heat hotspot time", f"{float(hotspot_time):.3f} s"))
                except Exception:
                    pass
            hotspot_peak = hosted_compare_peak_heat.get("hotspot_peak")
            hotspot_unit = str(hosted_compare_peak_heat.get("hotspot_unit") or "").strip()
            if hotspot_peak not in (None, ""):
                try:
                    peak_text = self._preview_value_text(hotspot_peak)
                    if hotspot_unit:
                        peak_text = f"{peak_text} {hotspot_unit}"
                    rows.append(("Peak heat hotspot abs delta", peak_text))
                except Exception:
                    pass
            hotspot_signed_delta = hosted_compare_peak_heat.get("hotspot_signed_delta")
            if hotspot_signed_delta not in (None, ""):
                try:
                    signed_text = self._preview_value_text(hotspot_signed_delta)
                    if hotspot_unit:
                        signed_text = f"{signed_text} {hotspot_unit}"
                    rows.append(("Peak heat hotspot signed delta", signed_text))
                except Exception:
                    pass
            dominant_signal = str(hosted_compare_peak_heat.get("dominant_signal") or "").strip()
            if dominant_signal:
                rows.append(("Peak heat dominant signal", self._short_text(dominant_signal, limit=120)))
            dominant_run = str(hosted_compare_peak_heat.get("dominant_run") or "").strip()
            if dominant_run:
                rows.append(("Peak heat dominant run", self._short_text(dominant_run, limit=120)))
            signal_competition = hosted_compare_peak_heat.get("signal_competition")
            if signal_competition not in (None, ""):
                rows.append(("Peak heat competing signals", self._preview_value_text(signal_competition)))
            run_competition = hosted_compare_peak_heat.get("run_competition")
            if run_competition not in (None, ""):
                rows.append(("Peak heat competing runs", self._preview_value_text(run_competition)))
            bridge_headline = str(hosted_compare_peak_heat.get("bridge_headline") or "").strip()
            if bridge_headline:
                rows.append(("Peak heat bridge", self._short_text(bridge_headline, limit=220)))
            bridge_detail = str(hosted_compare_peak_heat.get("bridge_detail") or "").strip()
            if bridge_detail:
                rows.append(("Peak heat bridge detail", self._short_text(bridge_detail, limit=220)))
            bridge_tone = str(hosted_compare_peak_heat.get("bridge_tone") or "").strip()
            if bridge_tone:
                rows.append(("Peak heat bridge tone", bridge_tone))
            note = str(hosted_compare_peak_heat.get("note") or "").strip()
            if note:
                rows.append(("Peak heat note", self._short_text(note, limit=220)))
            for index, line in enumerate(hosted_compare_peak_heat.get("summary_lines") or (), start=1):
                text = str(line or "").strip()
                if text:
                    rows.append((f"Peak heat summary {index}", self._short_text(text, limit=220)))
            for index, item in enumerate(hosted_compare_peak_heat.get("signal_rows") or (), start=1):
                signal = dict(item) if isinstance(item, Mapping) else {}
                name = str(signal.get("name") or "").strip()
                if not name:
                    continue
                run_name = str(signal.get("run") or "").strip() or "-"
                value = f"run={run_name}"
                signal_time = signal.get("time_s")
                if signal_time not in (None, ""):
                    try:
                        value = f"{value} | time={float(signal_time):.3f} s"
                    except Exception:
                        pass
                peak_abs = signal.get("peak_abs")
                if peak_abs not in (None, ""):
                    value = f"{value} | abs_delta={self._preview_value_text(peak_abs)}"
                signed_delta = signal.get("signed_delta")
                if signed_delta not in (None, ""):
                    value = f"{value} | signed_delta={self._preview_value_text(signed_delta)}"
                unit = str(signal.get("unit") or "").strip()
                if unit:
                    value = f"{value} | unit={unit}"
                rows.append((f"Peak signal {index}", f"{name} | {value}"))
        if hosted_compare_delta_timeline:
            timeline_status = str(hosted_compare_delta_timeline.get("status") or "").strip()
            if timeline_status:
                rows.append(("Delta timeline status", timeline_status))
            table_name = str(hosted_compare_delta_timeline.get("table") or "").strip()
            if table_name:
                rows.append(("Delta timeline table", table_name))
            signal_name = str(hosted_compare_delta_timeline.get("signal") or "").strip()
            if signal_name:
                rows.append(("Delta timeline signal", self._short_text(signal_name, limit=120)))
            reference_label = str(hosted_compare_delta_timeline.get("reference_label") or "").strip()
            if reference_label:
                rows.append(("Delta timeline ref", self._short_text(reference_label, limit=120)))
            compare_label = str(hosted_compare_delta_timeline.get("compare_label") or "").strip()
            if compare_label:
                rows.append(("Delta timeline compare", self._short_text(compare_label, limit=120)))
            point_count = hosted_compare_delta_timeline.get("point_count")
            if point_count not in (None, ""):
                rows.append(("Delta timeline points", self._preview_value_text(point_count)))
            time_window = list(hosted_compare_delta_timeline.get("time_window") or ())
            if len(time_window) >= 2:
                try:
                    rows.append(
                        (
                            "Delta timeline window",
                            f"{float(time_window[0]):.3f} .. {float(time_window[1]):.3f}",
                        )
                    )
                except Exception:
                    pass
            hotspot_time = hosted_compare_delta_timeline.get("hotspot_time")
            if hotspot_time not in (None, ""):
                try:
                    rows.append(("Delta timeline hotspot time", f"{float(hotspot_time):.3f} s"))
                except Exception:
                    pass
            delta_unit = str(hosted_compare_delta_timeline.get("unit") or "").strip()
            hotspot_peak = hosted_compare_delta_timeline.get("hotspot_peak")
            if hotspot_peak not in (None, ""):
                peak_text = self._preview_value_text(hotspot_peak)
                if delta_unit:
                    peak_text = f"{peak_text} {delta_unit}"
                rows.append(("Delta timeline hotspot abs delta", peak_text))
            hotspot_signed_delta = hosted_compare_delta_timeline.get("hotspot_signed_delta")
            if hotspot_signed_delta not in (None, ""):
                signed_text = self._preview_value_text(hotspot_signed_delta)
                if delta_unit:
                    signed_text = f"{signed_text} {delta_unit}"
                rows.append(("Delta timeline hotspot signed delta", signed_text))
            hotspot_reference_value = hosted_compare_delta_timeline.get("hotspot_reference_value")
            if hotspot_reference_value not in (None, ""):
                ref_text = self._preview_value_text(hotspot_reference_value)
                if delta_unit:
                    ref_text = f"{ref_text} {delta_unit}"
                rows.append(("Delta timeline hotspot ref value", ref_text))
            hotspot_compare_value = hosted_compare_delta_timeline.get("hotspot_compare_value")
            if hotspot_compare_value not in (None, ""):
                compare_text = self._preview_value_text(hotspot_compare_value)
                if delta_unit:
                    compare_text = f"{compare_text} {delta_unit}"
                rows.append(("Delta timeline hotspot compare value", compare_text))
            if selected_playhead_row is not None:
                rows.append(
                    (
                        "Активная точка графика",
                        f"{selected_playhead_index + 1}/{len(selected_playhead_rows)}",
                    )
                )
                point_time = selected_playhead_row.get("time_s")
                if point_time not in (None, ""):
                    try:
                        rows.append(("Время активной точки", f"{float(point_time):.3f} s"))
                    except Exception:
                        pass
                active_ref_value = selected_playhead_row.get("reference_value")
                if active_ref_value not in (None, ""):
                    ref_text = self._preview_value_text(active_ref_value)
                    if delta_unit:
                        ref_text = f"{ref_text} {delta_unit}"
                    rows.append(("Опорное значение точки", ref_text))
                active_compare_value = selected_playhead_row.get("compare_value")
                if active_compare_value not in (None, ""):
                    compare_text = self._preview_value_text(active_compare_value)
                    if delta_unit:
                        compare_text = f"{compare_text} {delta_unit}"
                    rows.append(("Сравниваемое значение точки", compare_text))
                active_delta_value = selected_playhead_row.get("delta")
                if active_delta_value not in (None, ""):
                    delta_text = self._preview_value_text(active_delta_value)
                    if delta_unit:
                        delta_text = f"{delta_text} {delta_unit}"
                    rows.append(("Расхождение в активной точке", delta_text))
            if selected_window_row is not None:
                rows.append(
                    (
                        "Активное окно графика",
                        f"{selected_window_index + 1}/{len(selected_window_rows)}",
                    )
                )
                try:
                    rows.append(
                        (
                            "Границы активного окна",
                            (
                                f"{float(selected_window_row.get('start_s')):.3f} .. "
                                f"{float(selected_window_row.get('end_s')):.3f} s"
                            ),
                        )
                    )
                except Exception:
                    pass
                focus_time = selected_window_row.get("focus_time_s")
                if focus_time not in (None, ""):
                    try:
                        rows.append(("Центр активного окна", f"{float(focus_time):.3f} s"))
                    except Exception:
                        pass
                point_count_in_window = selected_window_row.get("point_count")
                if point_count_in_window not in (None, ""):
                    rows.append(("Точек в активном окне", self._preview_value_text(point_count_in_window)))
            note = str(hosted_compare_delta_timeline.get("note") or "").strip()
            if note:
                rows.append(("Delta timeline note", self._short_text(note, limit=220)))
            for index, line in enumerate(hosted_compare_delta_timeline.get("summary_lines") or (), start=1):
                text = str(line or "").strip()
                if text:
                    rows.append((f"Delta timeline summary {index}", self._short_text(text, limit=220)))
            context_rows = hosted_compare_delta_timeline.get("context_rows") or ()
            if context_rows:
                for index, point in enumerate(context_rows, start=1):
                    point_map = dict(point) if isinstance(point, Mapping) else {}
                    point_time = point_map.get("time_s")
                    if point_time in (None, ""):
                        continue
                    try:
                        point_text = f"t={float(point_time):.3f} s"
                    except Exception:
                        continue
                    ref_value = point_map.get("reference_value")
                    if ref_value not in (None, ""):
                        point_text = f"{point_text} | ref={self._preview_value_text(ref_value)}"
                        if delta_unit:
                            point_text = f"{point_text} {delta_unit}"
                    compare_value = point_map.get("compare_value")
                    if compare_value not in (None, ""):
                        point_text = f"{point_text} | compare={self._preview_value_text(compare_value)}"
                        if delta_unit:
                            point_text = f"{point_text} {delta_unit}"
                    delta_value = point_map.get("delta")
                    if delta_value not in (None, ""):
                        point_text = f"{point_text} | delta={self._preview_value_text(delta_value)}"
                        if delta_unit:
                            point_text = f"{point_text} {delta_unit}"
                    rows.append((f"Delta point {index}", point_text))
            else:
                for index, point in enumerate(hosted_compare_delta_timeline.get("sample_points") or (), start=1):
                    if not isinstance(point, (tuple, list)) or len(point) < 2:
                        continue
                    try:
                        point_text = f"t={float(point[0]):.3f} s | delta={self._preview_value_text(point[1])}"
                    except Exception:
                        continue
                    if delta_unit:
                        point_text = f"{point_text} {delta_unit}"
                    rows.append((f"Delta point {index}", point_text))
        if hosted_compare_open_timeline:
            timeline_status = str(hosted_compare_open_timeline.get("status") or "").strip()
            if timeline_status:
                rows.append(("Open timeline status", timeline_status))
            reference_label = str(hosted_compare_open_timeline.get("reference_label") or "").strip()
            if reference_label:
                rows.append(("Open timeline ref", self._short_text(reference_label, limit=120)))
            valve_count = hosted_compare_open_timeline.get("valve_count")
            if valve_count not in (None, ""):
                rows.append(("Open timeline valves", self._preview_value_text(valve_count)))
            changed_count = hosted_compare_open_timeline.get("changed_count")
            if changed_count not in (None, ""):
                rows.append(("Open timeline changed", self._preview_value_text(changed_count)))
            active_count = hosted_compare_open_timeline.get("active_count")
            if active_count not in (None, ""):
                rows.append(("Open timeline active", self._preview_value_text(active_count)))
            time_window = list(hosted_compare_open_timeline.get("time_window") or ())
            if len(time_window) >= 2:
                try:
                    rows.append(
                        (
                            "Open timeline window",
                            f"{float(time_window[0]):.3f} .. {float(time_window[1]):.3f}",
                        )
                    )
                except Exception:
                    pass
            note = str(hosted_compare_open_timeline.get("note") or "").strip()
            if note:
                rows.append(("Open timeline note", self._short_text(note, limit=220)))
            for index, line in enumerate(hosted_compare_open_timeline.get("summary_lines") or (), start=1):
                text = str(line or "").strip()
                if text:
                    rows.append(
                        (f"Open timeline summary {index}", self._short_text(text, limit=220))
                    )
            for index, item in enumerate(hosted_compare_open_timeline.get("valve_rows") or (), start=1):
                valve = dict(item) if isinstance(item, Mapping) else {}
                name = str(valve.get("name") or "").strip()
                if not name:
                    continue
                value = (
                    f"changed={int(valve.get('changed') or 0)} | "
                    f"active={int(valve.get('active') or 0)} | "
                    f"transitions={int(valve.get('transitions') or 0)} | "
                    f"duty={float(valve.get('duty') or 0.0):.2f}"
                )
                rows.append((f"Open valve {index}", f"{name} | {value}"))
        if compare_payload:
            compare_hash = str(compare_payload.get("current_context_ref_hash") or "").strip()
            if compare_hash:
                rows.append(("Хэш текущего контекста", self._short_text(compare_hash, limit=48)))
        rows.append(
            (
                "Следующий шаг",
                "Если контекст согласован, продолжайте графический разбор; если есть расхождения, синхронизируйте выбранный прогон и повторите сравнение.",
            )
        )
        payload = self._results_child_dock_payload(
            title="Сравнение результатов",
            object_name="child_dock_results_compare",
            content_object_name="CHILD-COMPARE-CONTENT",
            table_object_name="CHILD-COMPARE-TABLE",
            summary=self.results_action_label.text(),
            rows=rows,
            plot_preview=compare_plot_preview,
        )
        payload.update(
            {
                "status": "shown",
                "path": target_path,
                "sidecar": sidecar_path,
            }
        )
        return payload

    def _open_compare_viewer(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        artifact = self._selected_results_artifact(runtime, snapshot)
        target_path = runtime.compare_viewer_path(snapshot, artifact=artifact)
        if target_path is None:
            self._refresh_results_controls()
            self.results_action_label.setText(
                "Сравнение пока недоступно: нужен файл результата расчёта."
            )
            return {"status": "blocked"}
        try:
            sidecar_path = runtime.write_compare_current_context_sidecar(snapshot)
        except Exception as exc:
            self._refresh_results_controls()
            self.results_action_label.setText(f"Не удалось подготовить сравнение: {exc}")
            return {"status": "failed", "error": str(exc)}
        self._populate_compare_preview(runtime, snapshot, artifact=artifact)
        self._populate_chart_preview(runtime, snapshot, artifact=artifact)
        self.results_compare_preview_box.setFocus(QtCore.Qt.OtherFocusReason)
        self.results_action_label.setText(
            f"Сравнение показано в рабочем шаге: {self._path_label(target_path)}; контекст {self._path_label(sidecar_path)}."
        )
        rows = list(_table_snapshot_rows(self.results_compare_preview_table))
        rows.extend(
            (f"График: {label}", value)
            for label, value in _table_snapshot_rows(self.results_chart_preview_table, max_rows=8)
        )
        rows.append(("Файл результата", self._path_label(target_path)))
        rows.append(("Контекст сравнения", self._path_label(sidecar_path)))
        return {
            "status": "shown",
            "path": target_path,
            "sidecar": sidecar_path,
            "child_dock": {
                "title": "Сравнение результатов",
                "object_name": "child_dock_results_compare",
                "content_object_name": "CHILD-COMPARE-CONTENT",
                "table_object_name": "CHILD-COMPARE-TABLE",
                "summary": self.results_action_label.text(),
                "rows": tuple(rows),
            },
        }

    def refresh_view(self) -> None:
        super().refresh_view()
        self._refresh_results_controls()

    def handle_command(self, command_id: str) -> object:
        if command_id == "results.center.open":
            self._activate_results_panel(
                "Анализ результатов открыт в рабочем шаге анализа."
            )
            return
        if command_id == "results.compare.prepare":
            return self._prepare_compare_context()
        if command_id == "results.evidence.prepare":
            return self._prepare_evidence_manifest()
        if command_id == "results.run_materials.show":
            return self._show_run_materials()
        if command_id == "results.selected_material.show":
            return self._show_selected_material()
        if command_id == "results.chart_detail.show":
            return self._show_chart_detail()
        if command_id == "results.engineering_qa.show":
            return self._show_engineering_qa()
        if command_id == "results.engineering_candidates.show":
            return self._show_engineering_candidates()
        if command_id == "results.engineering_run.pin":
            return self._pin_engineering_run()
        if command_id == "results.engineering_influence.run":
            return self._start_engineering_influence_run()
        if command_id == "results.engineering_full_report.run":
            return self._start_engineering_full_report_run()
        if command_id == "results.engineering_param_staging.run":
            return self._start_engineering_param_staging_run()
        if command_id == "results.influence_review.show":
            return self._show_influence_review()
        if command_id == "results.compare_influence.show":
            return self._show_compare_influence()
        if command_id == "results.engineering_evidence.export":
            return self._export_engineering_evidence()
        if command_id == "results.engineering_animation_link.export":
            return self._export_engineering_animation_link()
        if command_id == "results.animation.prepare":
            return self._prepare_animation_handoff()
        if command_id == "results.compare.open":
            return self._show_compare_detail()
        if command_id == "results.compare.target.next":
            return self._cycle_compare_target()
        if command_id == "results.compare.signal.next":
            return self._cycle_compare_signal()
        if command_id == "results.compare.playhead.next":
            return self._cycle_compare_playhead()
        if command_id == "results.compare.window.next":
            return self._cycle_compare_window()


class AnimationWorkspacePage(RuntimeWorkspacePage):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        action_commands: Iterable[DesktopShellCommandSpec],
        on_command: Callable[[str], None],
        *,
        repo_root: Path,
        python_executable: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.python_executable = python_executable
        super().__init__(
            workspace,
            action_commands,
            on_command,
            lambda: build_results_workspace_summary(
                repo_root,
                python_executable=python_executable,
            ),
            parent,
        )
        self.setObjectName("WS-ANIMATOR-HOSTED-PAGE")

    def _build_extra_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.animation_hub_box = QtWidgets.QGroupBox("Анимация и мнемосхема")
        self.animation_hub_box.setObjectName("AM-VIEWPORT")
        self.animation_hub_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        hub_layout = QtWidgets.QVBoxLayout(self.animation_hub_box)
        hub_layout.setSpacing(8)

        intro = QtWidgets.QLabel(
            "Этот рабочий шаг показывает готовность данных сцены, достоверность отображения и журнал мнемосхемы. "
            "Подробные графические окна остаются доступными как отдельные инструменты просмотра."
        )
        intro.setWordWrap(True)
        hub_layout.addWidget(intro)

        self.animation_scene_label = QtWidgets.QLabel("")
        self.animation_truth_label = QtWidgets.QLabel("")
        self.animation_mnemo_label = QtWidgets.QLabel("")
        self.animation_next_label = QtWidgets.QLabel("")
        for label in (
            self.animation_scene_label,
            self.animation_truth_label,
            self.animation_mnemo_label,
            self.animation_next_label,
        ):
            label.setWordWrap(True)
            hub_layout.addWidget(label)

        self.animation_status_table = QtWidgets.QTableWidget(0, 3)
        self.animation_status_table.setObjectName("AM-STATUS-TABLE")
        self.animation_status_table.setHorizontalHeaderLabels(
            ("Область", "Состояние", "Следующий шаг")
        )
        self.animation_status_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.animation_status_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.animation_status_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.animation_status_table.verticalHeader().setVisible(False)
        self.animation_status_table.horizontalHeader().setStretchLastSection(True)
        hub_layout.addWidget(self.animation_status_table)

        self.animation_scene_preview_box = QtWidgets.QGroupBox("Предпросмотр сцены")
        self.animation_scene_preview_box.setObjectName("AM-SCENE-PREVIEW")
        preview_layout = QtWidgets.QVBoxLayout(self.animation_scene_preview_box)
        preview_layout.setSpacing(6)
        preview_intro = QtWidgets.QLabel(
            "Короткая сводка показывает, какие данные сцены будут переданы в проверку движения и мнемосхемы."
        )
        preview_intro.setWordWrap(True)
        preview_layout.addWidget(preview_intro)
        self.animation_scene_preview_table = QtWidgets.QTableWidget(0, 2)
        self.animation_scene_preview_table.setObjectName("AM-SCENE-PREVIEW-TABLE")
        self.animation_scene_preview_table.setHorizontalHeaderLabels(("Пункт", "Значение"))
        self.animation_scene_preview_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.animation_scene_preview_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.animation_scene_preview_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.animation_scene_preview_table.verticalHeader().setVisible(False)
        self.animation_scene_preview_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self.animation_scene_preview_table)
        self.animation_scene_preview_scene = QtWidgets.QGraphicsScene(self.animation_scene_preview_box)
        self.animation_scene_preview_view = QtWidgets.QGraphicsView(self.animation_scene_preview_scene)
        self.animation_scene_preview_view.setObjectName("AM-SCENE-NATIVE-PREVIEW")
        self.animation_scene_preview_view.setMinimumHeight(132)
        self.animation_scene_preview_view.setRenderHint(QtGui.QPainter.Antialiasing, True)
        self.animation_scene_preview_view.setToolTip(
            "Встроенный контур движения по текущему файлу сцены."
        )
        preview_layout.addWidget(self.animation_scene_preview_view)
        hub_layout.addWidget(self.animation_scene_preview_box)

        button_row = QtWidgets.QHBoxLayout()
        self.animation_refresh_button = QtWidgets.QPushButton("Обновить анимацию")
        self.animation_refresh_button.setObjectName("AM-BTN-REFRESH")
        self.animation_refresh_button.clicked.connect(self.refresh_view)
        self.animation_open_button = QtWidgets.QPushButton("Проверить аниматор")
        self.animation_open_button.setObjectName("AM-BTN-CHECK-ANIMATOR")
        self.animation_open_button.setToolTip("Показать готовность данных сцены внутри рабочего шага.")
        self.animation_open_button.clicked.connect(lambda: self.on_command("animation.animator.open"))
        self.animation_mnemo_button = QtWidgets.QPushButton("Проверить мнемосхему")
        self.animation_mnemo_button.setObjectName("AM-BTN-CHECK-MNEMO")
        self.animation_mnemo_button.setToolTip("Показать журнал и события мнемосхемы внутри рабочего шага.")
        self.animation_mnemo_button.clicked.connect(lambda: self.on_command("animation.mnemo.open"))
        self.animation_detach_button = QtWidgets.QPushButton("Проверить движение")
        self.animation_detach_button.setObjectName("AM-DETACH")
        self.animation_detach_button.setToolTip("Показать проверку движения с текущими данными сцены внутри рабочего шага.")
        self.animation_detach_button.clicked.connect(lambda: self.on_command("animation.animator.launch"))
        self.animation_mnemo_detach_button = QtWidgets.QPushButton("Проверить схему")
        self.animation_mnemo_detach_button.setObjectName("AM-BTN-DETACH-MNEMO")
        self.animation_mnemo_detach_button.setToolTip("Показать проверку мнемосхемы с текущими данными внутри рабочего шага.")
        self.animation_mnemo_detach_button.clicked.connect(lambda: self.on_command("animation.mnemo.launch"))
        self.animation_diagnostics_button = QtWidgets.QPushButton("Передать в проверку проекта")
        self.animation_diagnostics_button.setObjectName("AM-BTN-HANDOFF-DIAGNOSTICS")
        self.animation_diagnostics_button.setToolTip(
            "Передать текущий материал сцены в рабочий шаг проверки проекта."
        )
        self.animation_diagnostics_button.clicked.connect(
            lambda: self.on_command("animation.diagnostics.prepare")
        )
        for button in (
            self.animation_refresh_button,
            self.animation_open_button,
            self.animation_mnemo_button,
            self.animation_detach_button,
            self.animation_mnemo_detach_button,
            self.animation_diagnostics_button,
        ):
            button_row.addWidget(button)
        button_row.addStretch(1)
        hub_layout.addLayout(button_row)

        self.animation_action_label = QtWidgets.QLabel("")
        self.animation_action_label.setObjectName("AM-ACTION-RESULT")
        self.animation_action_label.setWordWrap(True)
        self.animation_action_label.setStyleSheet("color: #576574;")
        hub_layout.addWidget(self.animation_action_label)

        layout.addWidget(self.animation_hub_box)

    def _results_runtime(self) -> DesktopResultsRuntime:
        return DesktopResultsRuntime(
            repo_root=self.repo_root,
            python_executable=str(self.python_executable or sys.executable),
        )

    @staticmethod
    def _status_text(raw: object) -> str:
        text = " ".join(str(raw or "").replace("_", " ").split()).strip()
        labels = {
            "READY": "готово",
            "MISSING": "нет данных",
            "BLOCKED": "заблокировано",
            "WARN": "предупреждение",
            "PASS": "норма",
            "FAIL": "ошибка",
            "CURRENT": "актуально",
            "STALE": "устарело",
            "UNKNOWN": "нет данных",
        }
        return labels.get(text.upper(), text.lower() if text else "нет данных")

    @staticmethod
    def _present(path: Path | None) -> str:
        return "найдено" if path is not None else "нет данных"

    @staticmethod
    def _operator_text(raw: object, *, fallback: str = "нет данных", limit: int = 110) -> str:
        text = _operator_result_text(raw)
        text = " ".join(str(text or "").split()).strip()
        if not text:
            return fallback
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    @staticmethod
    def _path_name(path: object, *, fallback: str = "нет данных") -> str:
        if path is None:
            return fallback
        try:
            return Path(path).name or str(path)
        except Exception:
            return str(path) or fallback

    @staticmethod
    def _preview_value_text(raw: object, *, fallback: str = "нет данных", limit: int = 160) -> str:
        text = " ".join(str(raw or "").split()).strip()
        if not text:
            return fallback
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    @staticmethod
    def _artifact_by_key_safe(
        runtime: DesktopResultsRuntime,
        snapshot: Any,
        artifact_key: str,
    ) -> Any | None:
        if not hasattr(runtime, "artifact_by_key"):
            return None
        try:
            return runtime.artifact_by_key(snapshot, artifact_key)
        except Exception:
            return None

    def _artifact_preview_lines_safe(
        self,
        runtime: DesktopResultsRuntime,
        artifact: Any | None,
    ) -> tuple[str, ...]:
        if artifact is None or not hasattr(runtime, "artifact_preview_lines"):
            return ()
        try:
            lines = runtime.artifact_preview_lines(artifact)
        except Exception:
            return ()
        return tuple(
            self._preview_value_text(line, fallback="", limit=140)
            for line in lines
            if self._preview_value_text(line, fallback="", limit=140)
        )

    @staticmethod
    def _analysis_animation_artifact_safe(
        runtime: DesktopResultsRuntime,
        snapshot: Any,
    ) -> Any | None:
        if not hasattr(runtime, "animation_handoff_artifact"):
            return None
        try:
            return runtime.animation_handoff_artifact(snapshot)
        except Exception:
            return None

    @staticmethod
    def _animation_target_paths_safe(
        runtime: DesktopResultsRuntime,
        snapshot: Any,
        artifact: Any | None = None,
    ) -> tuple[Any | None, Any | None]:
        if hasattr(runtime, "animator_target_paths"):
            try:
                return runtime.animator_target_paths(snapshot, artifact=artifact)
            except Exception:
                pass
        return (
            getattr(snapshot, "latest_npz_path", None),
            getattr(snapshot, "latest_pointer_json_path", None),
        )

    def _populate_scene_preview(
        self,
        runtime: DesktopResultsRuntime,
        snapshot: Any,
        *,
        artifact: Any | None = None,
    ) -> None:
        if not hasattr(self, "animation_scene_preview_table"):
            return
        scene_artifact = artifact or self._artifact_by_key_safe(runtime, snapshot, "latest_npz")
        pointer_artifact = self._artifact_by_key_safe(runtime, snapshot, "latest_pointer")
        mnemo_artifact = self._artifact_by_key_safe(runtime, snapshot, "mnemo_event_log")
        capture_artifact = self._artifact_by_key_safe(runtime, snapshot, "capture_export_manifest")

        latest_npz_path, latest_pointer_path = self._animation_target_paths_safe(
            runtime,
            snapshot,
            artifact=artifact,
        )
        latest_mnemo_path = getattr(snapshot, "latest_mnemo_event_log_path", None)
        has_scene = latest_npz_path is not None or latest_pointer_path is not None
        rows: list[tuple[str, str]] = [
            ("Источник", "передано из анализа" if artifact is not None else "последний результат"),
            ("Файл сцены", self._path_name(latest_npz_path, fallback="нужен результат расчёта")),
            ("Данные проигрывания", self._path_name(latest_pointer_path)),
            ("Журнал мнемосхемы", self._path_name(latest_mnemo_path)),
            (
                "Достоверность",
                self._status_text(getattr(snapshot, "latest_capture_export_manifest_status", "")),
            ),
            ("Следующий шаг", "проверьте движение" if has_scene else "сначала выполните расчёт"),
        ]
        if capture_artifact is not None and getattr(capture_artifact, "path", None) is not None:
            rows.append(("Запись сохранения", self._path_name(getattr(capture_artifact, "path", None))))

        preview_source = scene_artifact or pointer_artifact or mnemo_artifact
        for index, line in enumerate(self._artifact_preview_lines_safe(runtime, preview_source)[:3], start=1):
            rows.append((f"Деталь {index}", line))

        scene_payload: Mapping[str, Any] | None = None
        if hasattr(runtime, "animation_scene_preview_points"):
            try:
                candidate = runtime.animation_scene_preview_points(
                    snapshot,
                    artifact=artifact,
                )
            except Exception:
                candidate = None
            if isinstance(candidate, Mapping):
                scene_payload = candidate

        self.animation_scene_preview_table.setRowCount(len(rows))
        for row_index, (label, value) in enumerate(rows):
            self.animation_scene_preview_table.setItem(
                row_index,
                0,
                QtWidgets.QTableWidgetItem(self._operator_text(label, limit=80)),
            )
            self.animation_scene_preview_table.setItem(
                row_index,
                1,
                QtWidgets.QTableWidgetItem(self._preview_value_text(value, limit=160)),
            )
        self.animation_scene_preview_table.resizeColumnsToContents()
        self._draw_native_animation_scene_preview(
            rows,
            scene_payload,
            scene_path=latest_npz_path,
            pointer_path=latest_pointer_path,
        )

    def _draw_native_animation_scene_preview(
        self,
        rows: Iterable[tuple[str, str]],
        preview_payload: Mapping[str, Any] | None,
        *,
        scene_path: Any | None,
        pointer_path: Any | None,
    ) -> None:
        if not hasattr(self, "animation_scene_preview_scene"):
            return
        scene = self.animation_scene_preview_scene
        scene.clear()
        width = 460.0
        height = 118.0
        margin_left = 34.0
        margin_right = 18.0
        margin_top = 16.0
        margin_bottom = 24.0
        scene.setSceneRect(0.0, 0.0, width, height)
        scene.addRect(
            0.0,
            0.0,
            width,
            height,
            QtGui.QPen(QtGui.QColor("#d8e1ea")),
            QtGui.QBrush(QtGui.QColor("#f8fafc")),
        )
        axis_pen = QtGui.QPen(QtGui.QColor("#8a9bad"))
        scene.addLine(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom, axis_pen)
        scene.addLine(margin_left, margin_top, margin_left, height - margin_bottom, axis_pen)

        payload = dict(preview_payload or {})
        raw_points = payload.get("points") or ()
        points: list[tuple[float, float]] = []
        for raw in raw_points:
            if not isinstance(raw, (tuple, list)) or len(raw) < 2:
                continue
            try:
                x = float(raw[0])
                y = float(raw[1])
            except Exception:
                continue
            if x == x and y == y and x not in {float("inf"), float("-inf")} and y not in {float("inf"), float("-inf")}:
                points.append((x, y))

        source_name = self._path_name(scene_path, fallback="нет файла сцены")
        pointer_name = self._path_name(pointer_path, fallback="нет данных проигрывания")
        if len(points) >= 2:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            x_span = x_max - x_min or 1.0
            y_span = y_max - y_min or 1.0
            plot_width = width - margin_left - margin_right
            plot_height = height - margin_top - margin_bottom
            path = QtGui.QPainterPath()
            for index, (x, y) in enumerate(points):
                px = margin_left + plot_width * ((x - x_min) / x_span)
                py = margin_top + plot_height * (1.0 - ((y - y_min) / y_span))
                if index == 0:
                    path.moveTo(px, py)
                else:
                    path.lineTo(px, py)
            scene.addPath(path, QtGui.QPen(QtGui.QColor("#2563eb"), 2.2))
            scene.addText(self._preview_value_text(payload.get("series_y"), fallback="траектория")).setPos(margin_left, 0.0)
            scene.addText(source_name).setPos(margin_left, height - 22.0)
            scene.addText(f"{int(payload.get('point_count') or len(points))} точек").setPos(width - 118.0, height - 22.0)
            self.animation_scene_preview_view.setToolTip(
                f"{source_name}: {self._preview_value_text(payload.get('range'), fallback='контур готов')}"
            )
            return

        status_rows = list(rows)[:4] or [
            ("Сцена", source_name),
            ("Данные проигрывания", pointer_name),
        ]
        colors = ("#60a5fa", "#38bdf8", "#5eead4", "#a7f3d0")
        for index, (label, value) in enumerate(status_rows):
            y = margin_top + 8.0 + index * 22.0
            color = QtGui.QColor(colors[index % len(colors)])
            scene.addRect(margin_left, y, 16.0, 10.0, QtGui.QPen(color), QtGui.QBrush(color))
            scene.addText(self._preview_value_text(label, limit=26)).setPos(margin_left + 22.0, y - 7.0)
            scene.addText(self._preview_value_text(value, limit=38)).setPos(width - 176.0, y - 7.0)
        self.animation_scene_preview_view.setToolTip(
            f"{source_name}; {pointer_name}"
        )

    def _refresh_animation_controls(self) -> None:
        if not hasattr(self, "animation_hub_box"):
            return
        try:
            runtime = self._results_runtime()
            snapshot = runtime.snapshot()
        except Exception as exc:
            message = f"Сводка анимации временно недоступна: {exc}"
            self.animation_scene_label.setText(message)
            self.animation_truth_label.setText(message)
            self.animation_mnemo_label.setText(message)
            self.animation_next_label.setText(message)
            self.animation_status_table.setRowCount(0)
            if hasattr(self, "animation_scene_preview_table"):
                self.animation_scene_preview_table.setRowCount(0)
            if hasattr(self, "animation_scene_preview_scene"):
                self.animation_scene_preview_scene.clear()
            return

        handoff_artifact = self._analysis_animation_artifact_safe(runtime, snapshot)
        scene_path, pointer_path = self._animation_target_paths_safe(
            runtime,
            snapshot,
            artifact=handoff_artifact,
        )
        scene_state = self._present(scene_path)
        pointer_state = self._present(pointer_path)
        mnemo_state = self._present(snapshot.latest_mnemo_event_log_path)
        capture_state = self._status_text(snapshot.latest_capture_export_manifest_status)
        mode_text = self._operator_text(snapshot.mnemo_current_mode, fallback="режим не выбран")
        recent_title = self._operator_text(
            snapshot.mnemo_recent_titles[0] if snapshot.mnemo_recent_titles else "",
            fallback="события пока не найдены",
        )
        recommendation = self._operator_text(
            snapshot.operator_recommendations[0] if snapshot.operator_recommendations else "",
            fallback="после проверки сцены вернитесь к анализу результатов или проверке проекта",
        )

        self.animation_scene_label.setText(
            f"Данные сцены - {scene_state}. Данные проигрывания - {pointer_state}."
        )
        self.animation_truth_label.setText(
            f"Достоверность отображения - {capture_state}. Связь с выбранным результатом проверяется по записи сохранения."
        )
        self.animation_mnemo_label.setText(
            f"Мнемосхема - {mnemo_state}. Текущий режим - {mode_text}. Последнее событие - {recent_title}."
        )
        self.animation_next_label.setText(f"Следующий шаг - {recommendation}.")

        rows = (
            (
                "Сцена",
                f"данные сцены - {scene_state}; данные проигрывания - {pointer_state}",
                "проверьте движение, если данные найдены",
            ),
            (
                "Мнемосхема",
                f"журнал - {mnemo_state}; режим - {mode_text}",
                recent_title,
            ),
            (
                "Достоверность",
                capture_state,
                "проверьте связь с выбранным результатом перед передачей проекта",
            ),
        )
        self.animation_status_table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(self._operator_text(value))
                self.animation_status_table.setItem(row_index, column, item)
        self.animation_status_table.resizeColumnsToContents()

        has_scene = scene_path is not None or pointer_path is not None
        has_mnemo = has_scene or snapshot.latest_mnemo_event_log_path is not None
        self.animation_detach_button.setEnabled(has_scene)
        self.animation_detach_button.setToolTip(
            "Показать проверку движения с текущими данными сцены внутри рабочего шага."
            if has_scene
            else "Сначала нужен результат для отображения."
        )
        self.animation_mnemo_detach_button.setEnabled(has_mnemo)
        self.animation_mnemo_detach_button.setToolTip(
            "Показать проверку мнемосхемы с текущими данными внутри рабочего шага."
            if has_mnemo
            else "Сначала нужны данные сцены или журнал мнемосхемы."
        )
        self._populate_scene_preview(runtime, snapshot, artifact=handoff_artifact)

    def _activate_animation_panel(self, message: str = "") -> None:
        self._refresh_animation_controls()
        self.animation_hub_box.setFocus(QtCore.Qt.OtherFocusReason)
        if message:
            self.animation_action_label.setText(message)

    def _show_animator_check(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        artifact = self._analysis_animation_artifact_safe(runtime, snapshot)
        args = runtime.animator_args(snapshot, follow=True, artifact=artifact)
        if not args:
            self._refresh_animation_controls()
            self.animation_action_label.setText(
                "Аниматор пока недоступен: нужен результат или данные проигрывания."
            )
            return {"status": "blocked"}
        self._populate_scene_preview(runtime, snapshot, artifact=artifact)
        self.animation_scene_preview_box.setFocus(QtCore.Qt.OtherFocusReason)
        self.animation_action_label.setText(
            "Проверка движения показана в дочерней dock-панели главного окна. Standalone-окно не запускалось."
        )
        return {
            "status": "shown",
            "args": args,
            "child_dock": {
                "title": "Проверка движения",
                "object_name": "child_dock_animation_motion",
                "content_object_name": "CHILD-ANIMATION-MOTION-CONTENT",
                "table_object_name": "CHILD-ANIMATION-MOTION-TABLE",
                "summary": self.animation_action_label.text(),
                "rows": _table_snapshot_rows(self.animation_scene_preview_table),
            },
        }

    def _show_mnemo_check(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        artifact = self._analysis_animation_artifact_safe(runtime, snapshot)
        args = runtime.mnemo_args(snapshot, follow=True, artifact=artifact)
        if not args:
            self._refresh_animation_controls()
            self.animation_action_label.setText(
                "Мнемосхема пока недоступна: нужны данные сцены или журнал событий."
            )
            return {"status": "blocked"}
        self._refresh_animation_controls()
        self.animation_status_table.setFocus(QtCore.Qt.OtherFocusReason)
        self.animation_action_label.setText(
            "Проверка мнемосхемы показана в дочерней dock-панели главного окна. Standalone-окно не запускалось."
        )
        return {
            "status": "shown",
            "args": args,
            "child_dock": {
                "title": "Мнемосхема",
                "object_name": "child_dock_animation_mnemo",
                "content_object_name": "CHILD-ANIMATION-MNEMO-CONTENT",
                "table_object_name": "CHILD-ANIMATION-MNEMO-TABLE",
                "summary": self.animation_action_label.text(),
                "rows": _table_snapshot_rows(self.animation_status_table),
            },
        }

    def _prepare_diagnostics_handoff(self) -> dict[str, Any]:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        artifact = self._analysis_animation_artifact_safe(runtime, snapshot)
        scene_path, pointer_path = runtime.animator_target_paths(snapshot, artifact=artifact)
        try:
            path = runtime.write_animation_diagnostics_handoff(snapshot, artifact=artifact)
        except Exception as exc:
            self._refresh_animation_controls()
            self.animation_action_label.setText(f"Не удалось передать материал в проверку проекта: {exc}")
            return {"status": "failed", "error": str(exc)}
        self._refresh_animation_controls()
        self.animation_action_label.setText(
            f"Материал передан в проверку проекта: {self._path_name(path)}."
        )
        rows: list[tuple[str, str]] = [
            ("Материал проверки", str(path)),
            ("Результат сцены", self._path_name(scene_path)),
            ("Указатель сцены", self._path_name(pointer_path)),
        ]
        rows.extend(_table_snapshot_rows(self.animation_status_table, max_rows=6))
        rows.extend(_table_snapshot_rows(self.animation_scene_preview_table, max_rows=8))
        return {
            "status": "prepared",
            "path": path,
            "child_dock": {
                "title": "Передача анимации в диагностику",
                "object_name": "child_dock_animation_diagnostics_handoff",
                "content_object_name": "CHILD-ANIMATION-DIAGNOSTICS-HANDOFF-CONTENT",
                "table_object_name": "CHILD-ANIMATION-DIAGNOSTICS-HANDOFF-TABLE",
                "summary": self.animation_action_label.text(),
                "rows": tuple(rows),
            },
        }

    def refresh_view(self) -> None:
        super().refresh_view()
        self._refresh_animation_controls()

    def handle_command(self, command_id: str) -> object:
        if command_id == "animation.animator.open":
            self._activate_animation_panel(
                "Анимация открыта в рабочем шаге. Проверьте готовность данных сцены перед подробным просмотром."
            )
            return
        if command_id == "animation.animator.launch":
            return self._show_animator_check()
        if command_id == "animation.mnemo.open":
            self._activate_animation_panel(
                "Мнемосхема открыта в рабочем шаге. Проверьте журнал и последнее событие перед подробным просмотром."
            )
            return
        if command_id == "animation.mnemo.launch":
            return self._show_mnemo_check()
        if command_id == "animation.diagnostics.prepare":
            return self._prepare_diagnostics_handoff()


class DiagnosticsWorkspacePage(RuntimeWorkspacePage):
    def __init__(
        self,
        workspace: DesktopWorkspaceSpec,
        action_commands: Iterable[DesktopShellCommandSpec],
        on_command: Callable[[str], None],
        *,
        repo_root: Path,
        python_executable: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(
            workspace,
            action_commands,
            on_command,
            lambda: build_diagnostics_workspace_summary(
                repo_root,
                python_executable=python_executable,
            ),
            parent,
        )
