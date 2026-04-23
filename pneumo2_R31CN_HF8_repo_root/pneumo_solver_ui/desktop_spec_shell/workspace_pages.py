from __future__ import annotations

import math
from pathlib import Path
import sys
import copy
from typing import Any, Callable, Iterable, Mapping

from PySide6 import QtCore, QtGui, QtWidgets

from pneumo_solver_ui.desktop_input_model import (
    DESKTOP_INPUT_SECTIONS,
    DesktopInputFieldSpec,
    default_working_copy_path,
    load_base_with_defaults,
    save_base_payload,
    save_desktop_inputs_snapshot,
)
from pneumo_solver_ui.desktop_ring_editor_model import (
    ROAD_MODES,
    TURN_DIRECTIONS,
    build_blank_segment,
    build_segment_flow_rows,
    clone_segment,
    ensure_road_defaults,
    get_segments,
    normalize_spec,
    safe_float,
    safe_int,
    save_spec_to_path,
)
from pneumo_solver_ui.desktop_ring_editor_runtime import build_ring_editor_diagnostics
from pneumo_solver_ui.desktop_results_runtime import DesktopResultsRuntime
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
    describe_plain_launch_availability,
    describe_run_launch_target,
    describe_run_setup_snapshot,
    recommended_run_launch_action,
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

    def handle_command(self, command_id: str) -> None:
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
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("WS-SUITE-HOSTED-PAGE")
        self.workspace = workspace
        self.action_commands = tuple(action_commands)
        self.on_command = on_command
        self.repo_root = Path(repo_root)
        self.suite_source_path = self.repo_root / "pneumo_solver_ui" / "default_suite.json"
        self._suite_rows: list[dict[str, Any]] = []
        self._refreshing_suite_table = False

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
        table_layout.addWidget(self.suite_table)
        layout.addWidget(table_box, 1)

        actions_box = QtWidgets.QGroupBox("Действия")
        actions_layout = QtWidgets.QHBoxLayout(actions_box)
        self.check_button = QtWidgets.QPushButton("Проверить набор")
        self.check_button.setObjectName("TS-BTN-VALIDATE")
        self.check_button.clicked.connect(self.check_suite)
        actions_layout.addWidget(self.check_button)
        self.save_button = QtWidgets.QPushButton("Сохранить снимок для базового прогона")
        self.save_button.clicked.connect(self.save_suite_snapshot)
        actions_layout.addWidget(self.save_button)
        scenario_button = QtWidgets.QPushButton("Редактировать циклический сценарий")
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
        self._update_summary_labels()
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

    def _on_suite_item_changed(self, _item: QtWidgets.QTableWidgetItem) -> None:
        if self._refreshing_suite_table:
            return
        self._update_summary_labels()
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
        except Exception:
            self.snapshot_label.setText("Не удалось сохранить снимок набора.")
            return
        self.snapshot_label.setText("Снимок набора сохранён для базового прогона.")
        self.validation_label.setText("Набор проверен и готов для базового прогона.")

    def handle_command(self, command_id: str) -> None:
        if command_id == "test.center.open":
            self.refresh_view()
            self.suite_table.setFocus(QtCore.Qt.OtherFocusReason)
            if self._suite_rows:
                self.validation_label.setText(
                    "Проверка набора открыта в рабочем шаге. Проверьте строки, сохраните снимок и переходите к базовому прогону."
                )


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
        self.run_setup_open_log_button = QtWidgets.QPushButton("Открыть журнал")
        self.run_setup_open_log_button.setObjectName("BL-BTN-RUN-OPEN-LOG")
        self.run_setup_open_log_button.clicked.connect(
            lambda: self.handle_command("baseline.run.open_log")
        )
        self.run_setup_open_result_button = QtWidgets.QPushButton("Открыть папку результата")
        self.run_setup_open_result_button.setObjectName("BL-BTN-RUN-OPEN-RESULT")
        self.run_setup_open_result_button.clicked.connect(
            lambda: self.handle_command("baseline.run.open_result")
        )
        for button in (
            self.run_setup_check_button,
            self.run_setup_checked_launch_button,
            self.run_setup_plain_launch_button,
            self.run_setup_execute_button,
            self.run_setup_cancel_button,
            self.run_setup_open_log_button,
            self.run_setup_open_result_button,
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
        self._run_setup_snapshot = snapshot
        return snapshot

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

    def _open_baseline_path(self, path: Path | None, *, missing_message: str, opened_message: str) -> bool:
        if path is None or not path.exists():
            self.run_setup_result_label.setText(missing_message)
            self._set_baseline_shell_status(missing_message, busy=False)
            return False
        opened = QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))
        if opened:
            self.run_setup_result_label.setText(opened_message)
        else:
            self.run_setup_result_label.setText(f"Не удалось открыть: {path}")
        return bool(opened)

    def _open_baseline_log(self) -> bool:
        self._latest_baseline_request()
        return self._open_baseline_path(
            self._baseline_last_log_path,
            missing_message="Журнал базового прогона пока не найден.",
            opened_message="Журнал базового прогона открыт.",
        )

    def _open_baseline_result_dir(self) -> bool:
        self._latest_baseline_request()
        return self._open_baseline_path(
            self._baseline_last_run_dir,
            missing_message="Папка результата базового прогона пока не найдена.",
            opened_message="Папка результата базового прогона открыта.",
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
                "Проверьте артефакты запуска и журнал." if selected.get("source_run_dir") else "Папка запуска не указана.",
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
            self._open_baseline_log()
            return
        if command_id == "baseline.run.open_result":
            self._open_baseline_result_dir()
            return
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
        self._refreshing_input_table = False
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
        editor_layout.addWidget(self.input_table)

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

        editor_layout.addLayout(actions)

        self.input_action_label = QtWidgets.QLabel("")
        self.input_action_label.setObjectName("ID-ACTION-RESULT")
        self.input_action_label.setWordWrap(True)
        self.input_action_label.setStyleSheet("color: #576574;")
        editor_layout.addWidget(self.input_action_label)

        layout.addWidget(self.input_editor_box)

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

    def _refresh_input_editor_controls(self) -> None:
        if not hasattr(self, "input_table"):
            return
        self._refreshing_input_table = True
        try:
            self._input_payload = load_base_with_defaults()
            rows = self._section_specs()
            self.input_table.setRowCount(len(rows))
            for row_index, (section_title, spec) in enumerate(rows):
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
        except Exception as exc:
            self.input_table.setRowCount(0)
            self.input_action_label.setText(f"Не удалось прочитать исходные данные: {exc}")
        finally:
            self._refreshing_input_table = False

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

    def _on_input_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if self._refreshing_input_table or item.column() != 2:
            return
        self.input_action_label.setText(
            "Есть несохранённые изменения в таблице исходных данных. Сохраните рабочую копию перед переходом дальше."
        )

    def _save_input_working_copy(self) -> None:
        try:
            payload = self._gather_input_payload_from_table()
            target = save_base_payload(default_working_copy_path(), payload)
            self._input_payload = dict(payload)
            self.input_action_label.setText(f"Рабочая копия сохранена: {target}")
            self.refresh_view()
        except Exception as exc:
            self.input_action_label.setText(f"Не удалось сохранить рабочую копию: {exc}")

    def _save_input_handoff_snapshot(self) -> None:
        try:
            payload = self._gather_input_payload_from_table()
            working_copy = save_base_payload(default_working_copy_path(), payload)
            snapshot = save_desktop_inputs_snapshot(payload, source_path=working_copy)
            self._input_payload = dict(payload)
            self.input_action_label.setText(f"Снимок исходных данных зафиксирован для маршрута: {snapshot}")
            self.refresh_view()
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
        self._ring_dirty = False
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
        editor_layout.addWidget(self.ring_segment_table)

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
        editor_layout.addLayout(actions)

        route_actions = QtWidgets.QHBoxLayout()
        self.ring_to_suite_button = QtWidgets.QPushButton("Перейти к набору испытаний")
        self.ring_to_suite_button.setObjectName("RG-BTN-ADD-TO-SUITE")
        self.ring_to_suite_button.clicked.connect(
            lambda _checked=False: self.on_command("workspace.test_matrix.open")
        )
        route_actions.addWidget(self.ring_to_suite_button)

        editor_layout.addLayout(route_actions)

        self.ring_action_label = QtWidgets.QLabel("")
        self.ring_action_label.setObjectName("RG-ACTION-RESULT")
        self.ring_action_label.setWordWrap(True)
        self.ring_action_label.setStyleSheet("color: #576574;")
        editor_layout.addWidget(self.ring_action_label)

        layout.addWidget(self.ring_editor_box)

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
        return normalize_spec(spec)

    def _mark_ring_dirty(self, message: str) -> None:
        self._ring_dirty = True
        self.ring_action_label.setText(message)

    def _on_ring_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if self._refreshing_ring_table or item.column() not in {1, 2, 3, 4, 5}:
            return
        self._mark_ring_dirty(
            "Есть несохранённые изменения в сценарии. Сохраните основной файл перед переходом к набору испытаний."
        )

    def _add_ring_segment(self) -> None:
        self._ring_spec = self._apply_ring_table_to_spec()
        segments = self._ring_segments()
        insert_at = min(max(0, self._selected_ring_row()) + 1, len(segments))
        segments.insert(insert_at, build_blank_segment(seed=safe_int(self._ring_spec.get("seed", 123), 123)))
        self._mark_ring_dirty("Добавлен новый сегмент. Проверьте длительность, скорость и профиль дороги.")
        self._render_current_ring_spec(selected_row=insert_at)

    def _duplicate_ring_segment(self) -> None:
        self._ring_spec = self._apply_ring_table_to_spec()
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
        segments = self._ring_segments()
        if len(segments) <= 1:
            self.ring_action_label.setText("В циклическом сценарии должен остаться хотя бы один сегмент.")
            return
        delete_at = min(max(0, self._selected_ring_row()), len(segments) - 1)
        segments.pop(delete_at)
        self._mark_ring_dirty("Сегмент удалён. Сохраните сценарий после проверки маршрута.")
        self._render_current_ring_spec(selected_row=max(0, delete_at - 1))

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
        finally:
            self._refreshing_ring_table = False

    def _save_ring_source(self) -> None:
        try:
            self._ring_spec = self._apply_ring_table_to_spec()
            target = self._ring_source_path or self._default_ring_source_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            saved = save_spec_to_path(self._ring_spec, target)
            self._ring_source_path = saved
            self._ring_dirty = False
            diagnostics = build_ring_editor_diagnostics(self._ring_spec)
            self.ring_action_label.setText(
                f"Сценарий сохранён: {saved}. Ошибки проверки {len(diagnostics.errors)}; предупреждения {len(diagnostics.warnings)}."
            )
            self.refresh_view()
        except Exception as exc:
            self.ring_action_label.setText(f"Не удалось сохранить циклический сценарий: {exc}")

    def _check_ring_source(self) -> None:
        try:
            spec = self._apply_ring_table_to_spec()
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
            "Открыть папку артефактов последнего активного запуска оптимизации."
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

    def handle_command(self, command_id: str) -> None:
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
            self._refresh_selected_result_preview
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
        for button in (
            self.results_refresh_button,
            self.results_prepare_compare_button,
            self.results_prepare_evidence_button,
            self.results_animation_handoff_button,
            self.results_compare_window_button,
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

        artifacts = tuple(snapshot.recent_artifacts[:8])
        self.results_artifacts_table.setRowCount(len(artifacts))
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
        self.results_artifacts_table.resizeColumnsToContents()

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
        self._populate_compare_preview(runtime, snapshot)
        self._populate_chart_preview(runtime, snapshot)

    def _activate_results_panel(self, message: str = "") -> None:
        self._refresh_results_controls()
        self.results_analysis_box.setFocus(QtCore.Qt.OtherFocusReason)
        if message:
            self.results_action_label.setText(message)

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

        self.results_chart_preview_table.setRowCount(len(chart_rows))
        for row_index, values in enumerate(chart_rows):
            for column, value in enumerate(values):
                self.results_chart_preview_table.setItem(
                    row_index,
                    column,
                    QtWidgets.QTableWidgetItem(self._preview_value_text(value)),
                )
        self.results_chart_preview_table.resizeColumnsToContents()
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

    def _prepare_compare_context(self) -> Path:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        path = runtime.write_compare_current_context_sidecar(snapshot)
        self._refresh_results_controls()
        self.results_action_label.setText(
            f"Сравнение подготовлено: {self._path_label(path)}."
        )
        return path

    def _prepare_evidence_manifest(self) -> Path:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        path = runtime.write_diagnostics_evidence_manifest(snapshot)
        self._refresh_results_controls()
        self.results_action_label.setText(
            f"Материалы проверки подготовлены: {self._path_label(path)}."
        )
        return path

    def _prepare_animation_handoff(self) -> Path:
        runtime = self._results_runtime()
        snapshot = runtime.snapshot()
        artifact = self._selected_results_artifact(runtime, snapshot)
        path = runtime.write_analysis_animation_handoff(snapshot, artifact=artifact)
        self._refresh_results_controls()
        self.results_action_label.setText(
            f"Материал передан в анимацию: {self._path_label(path)}."
        )
        return path

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
            self._prepare_compare_context()
            return
        if command_id == "results.evidence.prepare":
            self._prepare_evidence_manifest()
            return
        if command_id == "results.animation.prepare":
            self._prepare_animation_handoff()
            return
        if command_id == "results.compare.open":
            return self._open_compare_viewer()


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
        return {"status": "prepared", "path": path}

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
            self._prepare_diagnostics_handoff()


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
