from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from PySide6 import QtCore, QtGui, QtWidgets

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


def _clear_layout(layout: QtWidgets.QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


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

        self.evidence_box = QtWidgets.QGroupBox("Evidence / provenance")
        self.evidence_layout = QtWidgets.QVBoxLayout(self.evidence_box)
        layout.addWidget(self.evidence_box)

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
        evidence_lines = summary.evidence_lines or ("Свежие provenance-сигналы пока не найдены.",)
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

        contract_box = QtWidgets.QGroupBox("Контракт workspace")
        contract_layout = QtWidgets.QFormLayout(contract_box)
        contract_layout.addRow("Источник истины", QtWidgets.QLabel(workspace.source_of_truth))
        contract_layout.addRow("Workspace owner", QtWidgets.QLabel(workspace.workspace_owner or "n/a"))
        contract_layout.addRow("Automation ID", QtWidgets.QLabel(workspace.automation_id or "n/a"))
        contract_layout.addRow("Следующий шаг", QtWidgets.QLabel(workspace.next_step))
        contract_layout.addRow("Hard gate", QtWidgets.QLabel(workspace.hard_gate))
        layout.addWidget(contract_box)

        self.surface_box = QtWidgets.QGroupBox("Ключевые элементы surface")
        self.surface_layout = QtWidgets.QVBoxLayout(self.surface_box)
        layout.addWidget(self.surface_box)

        self.actions_box = QtWidgets.QGroupBox("Основные действия")
        self.actions_layout = QtWidgets.QVBoxLayout(self.actions_box)
        layout.addWidget(self.actions_box)

        evidence_box = QtWidgets.QGroupBox("Graphics / provenance")
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
        owners = [item.strip() for item in str(self.workspace.workspace_owner or "").split(";")]
        labels: list[str] = []
        for owner in owners:
            if not owner:
                continue
            for entry in workspace_elements_by_owner().get(owner, ())[:10]:
                text = f"{entry.title} ({entry.automation_id})"
                if entry.purpose:
                    text = f"{text}: {entry.purpose}"
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
                QtWidgets.QLabel("Каталог v2 для этого workspace пока не привязан к конкретным surface-элементам.")
            )
        for line in elements:
            label = QtWidgets.QLabel(f"• {line}")
            label.setWordWrap(True)
            self.surface_layout.addWidget(label)

        if not self.action_commands:
            self.actions_layout.addWidget(QtWidgets.QLabel("Команды для этого workspace пока не зарегистрированы."))
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
                        f"Маршрут: {command.route_label}",
                        f"Surface: {command.launch_surface.replace('_', ' ')}",
                        f"Automation ID: {command.automation_id or 'n/a'}",
                    )
                    if line
                )
            )
            meta.setWordWrap(True)
            meta.setStyleSheet("color: #576574;")
            self.actions_layout.addWidget(meta)


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
        self.baseline_center_box = QtWidgets.QGroupBox("Baseline Center: review / adopt / restore")
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
            ("Время", "Action", "Compare", "Baseline hash", "Suite hash", "Policy")
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
            ("Field", "Active", "Selected history", "Status")
        )
        self.baseline_mismatch_matrix.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.baseline_mismatch_matrix.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.baseline_mismatch_matrix.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.baseline_mismatch_matrix.verticalHeader().setVisible(False)
        self.baseline_mismatch_matrix.horizontalHeader().setStretchLastSection(True)
        center_layout.addWidget(self.baseline_mismatch_matrix)

        self.explicit_confirmation_checkbox = QtWidgets.QCheckBox(
            "Explicit confirmation: разрешить apply для adopt/restore"
        )
        self.explicit_confirmation_checkbox.setObjectName("BL-CHECK-EXPLICIT")
        self.explicit_confirmation_checkbox.setToolTip(
            "Adopt/restore остаются недоступны, пока этот флаг не включён явно."
        )
        self.explicit_confirmation_checkbox.toggled.connect(lambda _checked=False: self.refresh_view())
        center_layout.addWidget(self.explicit_confirmation_checkbox)

        button_row = QtWidgets.QHBoxLayout()
        self.review_button = QtWidgets.QPushButton("Review")
        self.review_button.setObjectName("BL-BTN-REVIEW")
        self.review_button.clicked.connect(lambda: self.apply_baseline_action("review"))
        self.adopt_button = QtWidgets.QPushButton("Adopt")
        self.adopt_button.setObjectName("BL-BTN-ADOPT")
        self.adopt_button.clicked.connect(lambda: self.apply_baseline_action("adopt"))
        self.restore_button = QtWidgets.QPushButton("Restore")
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
                self.baseline_banner_label.setText(f"Banner: {banner}")
                self.baseline_banner_label.setStyleSheet(
                    "background: #fff4e5; color: #6f4e00; padding: 8px; border: 1px solid #d9822b;"
                )
            else:
                self.baseline_banner_label.setText(
                    f"HO-006 state: {active.get('state') or 'missing'} | "
                    f"optimizer_can_consume={bool(active.get('optimizer_baseline_can_consume', False))}"
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
                        f"active_baseline_hash={active_hash[:16] or '—'} | selected={selected_id or 'нет'}",
                        f"suite_snapshot_hash={str(active.get('suite_snapshot_hash') or selected.get('suite_snapshot_hash') or '')[:16] or '—'}",
                        f"inputs_snapshot_hash={str(active.get('inputs_snapshot_hash') or selected.get('inputs_snapshot_hash') or '')[:16] or '—'}",
                        f"ring_source_hash={str(active.get('ring_source_hash') or selected.get('ring_source_hash') or '')[:16] or '—'}",
                        f"selected_baseline_hash={selected_hash[:16] or '—'}",
                    )
                    if line
                )
            )

            self._populate_history_table(tuple(dict(row) for row in surface.get("history_rows") or ()))
            mismatch_fields = tuple(str(field) for field in mismatch_state.get("mismatch_fields") or ())
            mismatch_text = ", ".join(mismatch_fields) if mismatch_fields else str(mismatch_state.get("state") or "none")
            self.baseline_mismatch_label.setText(
                f"Mismatch state: {mismatch_text}. Silent rebinding: запрещён."
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
            self.review_button.setToolTip("Read-only review выбранного baseline/history item.")
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
                str(row.get("action") or ""),
                str(row.get("compare_state") or ""),
                str(row.get("active_baseline_hash") or "")[:12],
                str(row.get("suite_snapshot_hash") or "")[:12],
                str(row.get("policy_mode") or ""),
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
            ("active_baseline_hash", "active_baseline_hash"),
            ("suite_snapshot_hash", "suite_snapshot_hash"),
            ("inputs_snapshot_hash", "inputs_snapshot_hash"),
            ("ring_source_hash", "ring_source_hash"),
            ("policy_mode", "policy_mode"),
        )
        blocker = QtCore.QSignalBlocker(self.baseline_mismatch_matrix)
        self.baseline_mismatch_matrix.setRowCount(len(fields))
        for row_index, (label, key) in enumerate(fields):
            active_value = str(active.get(key) or "")
            selected_value = str(selected.get(key) or "")
            if not active_value or not selected_value:
                status = "missing"
                color = QtGui.QColor("#fff4e5")
            elif active_value == selected_value:
                status = "match"
                color = QtGui.QColor("#e8f7ee")
            else:
                status = "mismatch"
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
            return "Требуется explicit confirmation flag."
        if bool(payload.get("enabled", False)):
            return f"{action} выбранного baseline будет применён после confirm dialog."
        candidate_state = str(policy.get("candidate_state") or "unknown")
        stale = ", ".join(str(item) for item in policy.get("candidate_stale_reasons") or ())
        return f"Blocked: candidate_state={candidate_state}" + (f" | stale={stale}" if stale else "")

    def _confirm_baseline_action(self, action: str, surface: dict[str, Any]) -> bool:
        selected = dict(surface.get("selected_history") or {})
        mismatch_fields = ", ".join(str(field) for field in selected.get("mismatch_fields") or ())
        warning = f"\n\nWarning: mismatch fields: {mismatch_fields}" if mismatch_fields else ""
        answer = QtWidgets.QMessageBox.question(
            self,
            "Baseline Center",
            (
                f"Подтвердить {action} для selected history item?\n\n"
                f"history_id={surface.get('selected_history_id') or 'нет'}\n"
                f"active_baseline_hash={str(selected.get('active_baseline_hash') or '')[:16] or '—'}"
                f"{warning}\n\nSilent rebinding запрещён; действие будет записано явно."
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
                    f"{requested_action}: blocked, включите explicit confirmation flag."
                )
                return {"action": requested_action, "status": "blocked"}
            if not self._confirm_baseline_action(requested_action, surface):
                self.action_result_label.setText(f"{requested_action}: cancelled by user.")
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
            note=f"explicit {requested_action} from Baseline Center",
        )
        self.action_result_label.setText(self._format_action_result(result))
        if requested_action in {"adopt", "restore"} and result.get("status") == "applied":
            self.explicit_confirmation_checkbox.setChecked(False)
        self.refresh_view()
        return result

    def _format_action_result(self, result: dict[str, Any]) -> str:
        policy = dict(result.get("policy") or {})
        bits = [
            f"action={result.get('action')}",
            f"status={result.get('status')}",
            f"wrote_active_contract={bool(result.get('wrote_active_contract', False))}",
            f"history_appended={bool(result.get('history_appended', False))}",
            f"silent_rebinding_allowed={bool(result.get('silent_rebinding_allowed', False))}",
        ]
        banner = str(policy.get("banner") or "")
        if banner:
            bits.append(f"banner={banner}")
        return " | ".join(bits)

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
