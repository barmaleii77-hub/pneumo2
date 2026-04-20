from __future__ import annotations

from PySide6 import QtWidgets

from .catalogs import V19WorkspaceGuidance, get_v19_workspace_guidance
from .contracts import DesktopWorkspaceSpec


V19_ACTION_FEEDBACK_TITLE = "Действие, проверка и обратная связь"


def v19_guidance_for_workspace(workspace: DesktopWorkspaceSpec) -> V19WorkspaceGuidance | None:
    owner_codes = (
        *str(workspace.workspace_owner or "").split(";"),
        *workspace.catalog_owner_aliases,
    )
    for owner in owner_codes:
        guidance = get_v19_workspace_guidance(str(owner or "").strip())
        if guidance is not None:
            return guidance
    return None


def _label(text: str, *, muted: bool = False, bold: bool = False) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    if muted:
        label.setStyleSheet("color: #576574;")
    if bold:
        font = label.font()
        font.setBold(True)
        label.setFont(font)
    return label


def _add_lines(
    layout: QtWidgets.QVBoxLayout,
    title: str,
    lines: tuple[str, ...],
    *,
    limit: int = 3,
) -> None:
    if not lines:
        return
    layout.addWidget(_label(title, bold=True))
    for line in lines[:limit]:
        layout.addWidget(_label(f"• {line}"))


def build_v19_action_feedback_box(
    workspace: DesktopWorkspaceSpec,
    parent: QtWidgets.QWidget | None = None,
) -> QtWidgets.QGroupBox | None:
    guidance = v19_guidance_for_workspace(workspace)
    if guidance is None:
        return None

    box = QtWidgets.QGroupBox(V19_ACTION_FEEDBACK_TITLE, parent)
    box.setObjectName(f"V19-ACTION-FEEDBACK-{guidance.workspace}")
    layout = QtWidgets.QVBoxLayout(box)
    layout.setSpacing(8)

    route_lines: list[str] = []
    if guidance.direct_open_route:
        route_lines.append(f"Открывается напрямую из левого дерева. {guidance.direct_open_route}.")
    if guidance.direct_open_required:
        route_lines.append("Промежуточное окно не требуется.")
    if guidance.intermediate_step_forbidden:
        route_lines.append("Лишний промежуточный шаг нельзя делать основным путём.")
    if route_lines:
        layout.addWidget(_label(" ".join(route_lines), muted=True))

    _add_lines(layout, "Что должно быть видно", guidance.visibility_lines)
    _add_lines(layout, "Что проверяет окно", guidance.check_lines, limit=2)
    _add_lines(layout, "Что блокирует движение дальше", guidance.block_lines, limit=2)
    _add_lines(layout, "Повторяемый рабочий цикл", guidance.loop_lines, limit=2)
    _add_lines(layout, "Цель пользователя", guidance.user_goals, limit=2)

    boundary = guidance.evidence_boundary or (
        "Текущий экран считается готовым только после живого запуска и сохранённого результата."
    )
    layout.addWidget(_label(f"Граница принятия. {boundary}", muted=True))
    return box
