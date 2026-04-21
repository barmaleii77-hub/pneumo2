from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Callable, Iterable

from PySide6 import QtCore, QtGui, QtWidgets

from pneumo_solver_ui.desktop_results_runtime import DesktopResultsRuntime
from pneumo_solver_ui.desktop_suite_runtime import (
    build_desktop_suite_snapshot_context,
    write_desktop_suite_handoff_snapshot,
)
from pneumo_solver_ui.desktop_suite_snapshot import load_suite_rows
from pneumo_solver_ui.desktop_optimizer_runtime import DesktopOptimizerRuntime
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
        "legacy_bridge": "рабочее окно",
        "external_window": "отдельное специализированное окно",
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
            baseline_button.setToolTip(baseline_command.summary)
            baseline_button.clicked.connect(
                lambda _checked=False, cid=baseline_command.command_id: self.on_command(cid)
            )
            actions_layout.addWidget(baseline_button)
        for command in self.action_commands:
            if command.command_id != "test.center.open":
                continue
            advanced_button = QtWidgets.QPushButton("Расширенная настройка набора")
            advanced_button.setToolTip(command.summary)
            advanced_button.clicked.connect(
                lambda _checked=False, cid=command.command_id: self.on_command(cid)
            )
            actions_layout.addWidget(advanced_button)
            break
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


class BaselineWorkspacePage(RuntimeWorkspacePage):
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
        self._selected_history_id = ""
        self._last_surface: dict[str, Any] = {}
        self._refreshing_baseline_controls = False
        self._run_setup_snapshot: dict[str, Any] = dict(vars(DesktopRunSetupSnapshot()))
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
        self.setObjectName("WS-BASELINE-HOSTED-PAGE")

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
        self.run_setup_advanced_button = QtWidgets.QPushButton("Расширенный центр запуска")
        self.run_setup_advanced_button.setObjectName("BL-BTN-RUN-ADVANCED")
        self.run_setup_advanced_button.clicked.connect(
            lambda: self.on_command("baseline.legacy_run_setup.open")
        )
        for button in (
            self.run_setup_check_button,
            self.run_setup_checked_launch_button,
            self.run_setup_plain_launch_button,
            self.run_setup_advanced_button,
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
        self.run_setup_plain_launch_button.setEnabled(gate_allowed)
        self.run_setup_plain_launch_button.setToolTip(
            "Доступно после актуального снимка набора испытаний."
            if gate_allowed
            else "Сначала обновите и сохраните снимок набора испытаний."
        )

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
        if checked:
            self.run_setup_result_label.setText(
                "Проверка перед запуском запрошена. "
                + self.run_setup_result_label.text()
            )
            return {"action": "prepare_checked", "allowed": bool(gate.get("baseline_launch_allowed", False))}
        if bool(gate.get("baseline_launch_allowed", False)):
            self.run_setup_result_label.setText(
                "Запуск подготовлен: профиль, режим выполнения и снимок набора испытаний согласованы."
            )
        return {"action": "prepare", "allowed": bool(gate.get("baseline_launch_allowed", False))}

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


class OptimizationWorkspacePage(RuntimeWorkspacePage):
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
            lambda: build_optimization_workspace_summary(
                repo_root,
                python_executable=python_executable,
            ),
            parent,
        )
        self.setObjectName("WS-OPTIMIZATION-HOSTED-PAGE")

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
        self.optimization_advanced_button = QtWidgets.QPushButton("Расширенная настройка")
        self.optimization_advanced_button.setObjectName("OP-BTN-ADVANCED")
        self.optimization_advanced_button.setToolTip(
            "Открыть подробную настройку для специальных сценариев."
        )
        self.optimization_advanced_button.clicked.connect(
            lambda: self.on_command("optimization.legacy_center.open")
        )
        for button in (
            self.optimization_check_button,
            self.optimization_prepare_button,
            self.optimization_advanced_button,
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
        return DesktopOptimizerRuntime(
            ui_root=self.repo_root,
            python_executable=self.python_executable,
        )

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

        self.optimization_prepare_button.setEnabled(ready)
        self.optimization_prepare_button.setToolTip(
            "Готово к подготовке основного запуска."
            if ready
            else "Сначала устраните блокирующие причины в целях, опорном прогоне или наборе испытаний."
        )

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
        analysis_layout.addWidget(self.results_artifacts_table)

        self.results_compare_label = QtWidgets.QLabel("")
        self.results_compare_label.setObjectName("RS-COMPARE-SUMMARY")
        self.results_compare_label.setWordWrap(True)
        analysis_layout.addWidget(self.results_compare_label)

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
        self.results_compare_window_button = QtWidgets.QPushButton("Окно сравнения")
        self.results_compare_window_button.setObjectName("RS-BTN-OPEN-COMPARE")
        self.results_compare_window_button.setToolTip(
            "Открыть отдельное окно сравнения, если нужен подробный графический просмотр."
        )
        self.results_compare_window_button.clicked.connect(
            lambda: self.on_command("results.compare.open")
        )
        self.results_advanced_button = QtWidgets.QPushButton("Расширенный анализ")
        self.results_advanced_button.setObjectName("RS-BTN-ADVANCED")
        self.results_advanced_button.setToolTip(
            "Открыть подробный анализ для специальных сценариев."
        )
        self.results_advanced_button.clicked.connect(
            lambda: self.on_command("results.legacy_center.open")
        )
        for button in (
            self.results_refresh_button,
            self.results_prepare_compare_button,
            self.results_prepare_evidence_button,
            self.results_compare_window_button,
            self.results_advanced_button,
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
            "Открыть отдельное окно сравнения."
            if compare_ready
            else "Сначала нужен файл результата для сравнения."
        )

    def _activate_results_panel(self, message: str = "") -> None:
        self._refresh_results_controls()
        self.results_analysis_box.setFocus(QtCore.Qt.OtherFocusReason)
        if message:
            self.results_action_label.setText(message)

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

    def refresh_view(self) -> None:
        super().refresh_view()
        self._refresh_results_controls()

    def handle_command(self, command_id: str) -> None:
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
        self.animation_detach_button = QtWidgets.QPushButton("Расширенный просмотр анимации")
        self.animation_detach_button.setObjectName("AM-DETACH")
        self.animation_detach_button.setToolTip("Открыть подробную графическую проверку.")
        self.animation_detach_button.clicked.connect(lambda: self.on_command("animation.legacy_animator.open"))
        self.animation_mnemo_detach_button = QtWidgets.QPushButton("Расширенный просмотр мнемосхемы")
        self.animation_mnemo_detach_button.setObjectName("AM-BTN-DETACH-MNEMO")
        self.animation_mnemo_detach_button.setToolTip("Открыть подробную мнемосхему.")
        self.animation_mnemo_detach_button.clicked.connect(lambda: self.on_command("animation.legacy_mnemo.open"))
        for button in (
            self.animation_refresh_button,
            self.animation_open_button,
            self.animation_mnemo_button,
            self.animation_detach_button,
            self.animation_mnemo_detach_button,
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
            return

        scene_state = self._present(snapshot.latest_npz_path)
        pointer_state = self._present(snapshot.latest_pointer_json_path)
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
                "проверьте движение в отдельном окне, если данные найдены",
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

        has_scene = snapshot.latest_npz_path is not None or snapshot.latest_pointer_json_path is not None
        self.animation_detach_button.setEnabled(has_scene)
        self.animation_detach_button.setToolTip(
            "Открыть подробную графическую проверку."
            if has_scene
            else "Сначала нужен результат для отображения."
        )

    def _activate_animation_panel(self, message: str = "") -> None:
        self._refresh_animation_controls()
        self.animation_hub_box.setFocus(QtCore.Qt.OtherFocusReason)
        if message:
            self.animation_action_label.setText(message)

    def refresh_view(self) -> None:
        super().refresh_view()
        self._refresh_animation_controls()

    def handle_command(self, command_id: str) -> None:
        if command_id == "animation.animator.open":
            self._activate_animation_panel(
                "Анимация открыта в рабочем шаге. Проверьте готовность данных сцены перед отдельным просмотром."
            )
            return
        if command_id == "animation.mnemo.open":
            self._activate_animation_panel(
                "Мнемосхема открыта в рабочем шаге. Проверьте журнал и последнее событие перед отдельным просмотром."
            )


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
