from __future__ import annotations

from PySide6 import QtWidgets

from .catalogs import V16WorkspaceVisibilityGuidance, get_v16_workspace_guidance
from .contracts import DesktopWorkspaceSpec


V16_VISIBILITY_TITLE = "Что должно быть видно сразу"


def v16_guidance_for_workspace(workspace: DesktopWorkspaceSpec) -> V16WorkspaceVisibilityGuidance | None:
    owner_codes = (
        *str(workspace.workspace_owner or "").split(";"),
        *workspace.catalog_owner_aliases,
    )
    for owner in owner_codes:
        guidance = get_v16_workspace_guidance(str(owner or "").strip())
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
    limit: int = 4,
) -> None:
    if not lines:
        return
    layout.addWidget(_label(title, bold=True))
    for line in lines[:limit]:
        layout.addWidget(_label(f"• {line}"))


def build_v16_visibility_priority_box(
    workspace: DesktopWorkspaceSpec,
    parent: QtWidgets.QWidget | None = None,
) -> QtWidgets.QGroupBox | None:
    guidance = v16_guidance_for_workspace(workspace)
    if guidance is None:
        return None

    box = QtWidgets.QGroupBox(V16_VISIBILITY_TITLE, parent)
    box.setObjectName(f"V16-VISIBILITY-{guidance.workspace}")
    layout = QtWidgets.QVBoxLayout(box)
    layout.setSpacing(8)

    if guidance.first_seconds:
        layout.addWidget(
            _label(f"Первые 3-5 секунд. {guidance.first_seconds}", muted=True)
        )

    _add_lines(layout, "Всегда на экране", guidance.always_visible_lines)
    _add_lines(layout, "Показывать при конфликте", guidance.conditional_lines, limit=3)
    _add_lines(
        layout,
        "Не прятать в правой панели",
        guidance.inspector_boundary_lines,
        limit=3,
    )
    return box
