from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from PySide6 import QtCore, QtGui, QtWidgets

from pneumo_solver_ui.desktop_suite_runtime import (
    build_desktop_suite_snapshot_context,
    write_desktop_suite_handoff_snapshot,
)
from pneumo_solver_ui.desktop_suite_snapshot import load_suite_rows
from pneumo_solver_ui.optimization_baseline_source import (
    apply_baseline_center_action,
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
)
from .v19_guidance_widgets import build_v19_action_feedback_box


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

    def _build_extra_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
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

    def refresh_view(self) -> None:
        super().refresh_view()
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
