# -*- coding: utf-8 -*-
"""Label placement utilities for QGraphicsView overlays.

Desktop Animator uses `QGraphicsTextItem` overlays with
`ItemIgnoresTransformations` so text stays readable when the view zooms.

If several labels are anchored to nearby points (typical for small suspension
motion or when the user zooms out), naive placement makes them overlap.

This module provides a tiny, deterministic layout step executed every frame:
- place labels in *viewport pixel* coordinates,
- try a few candidate positions around an anchor,
- avoid overlaps and keep labels inside the viewport.

The resulting pixel positions are mapped back into scene coordinates via
`QGraphicsView.mapToScene()`.

The goal is not perfect typography, but a robust "never overlap" behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except Exception:  # pragma: no cover
    QtCore = QtGui = QtWidgets = None  # type: ignore


@dataclass
class LabelSpec:
    """One label to be placed."""

    item: QtWidgets.QGraphicsTextItem
    anchor_scene: QtCore.QPointF
    # Preferred offset from anchor in pixels (viewport coordinates).
    # NOTE: QtCore.QPointF is mutable -> must be default_factory (dataclasses).
    offset_px: QtCore.QPointF = field(default_factory=lambda: QtCore.QPointF(8.0, -8.0))
    # Optional priority: higher is placed first.
    priority: int = 0
    # Additional padding between labels, pixels.
    pad_px: int = 2


def _rect_from_topleft(x: float, y: float, w: float, h: float) -> QtCore.QRectF:
    return QtCore.QRectF(float(x), float(y), float(w), float(h))


def _intersects_any(r: QtCore.QRectF, rects: Sequence[QtCore.QRectF]) -> bool:
    for rr in rects:
        if r.intersects(rr):
            return True
    return False


def _clamp_rect_into(r: QtCore.QRectF, bounds: QtCore.QRectF) -> QtCore.QRectF:
    """Clamp rectangle into bounds (keeps size, moves only)."""
    x = r.x()
    y = r.y()
    if r.right() > bounds.right():
        x = bounds.right() - r.width()
    if r.left() < bounds.left():
        x = bounds.left()
    if r.bottom() > bounds.bottom():
        y = bounds.bottom() - r.height()
    if r.top() < bounds.top():
        y = bounds.top()
    return QtCore.QRectF(float(x), float(y), float(r.width()), float(r.height()))


def layout_labels(
    view: QtWidgets.QGraphicsView,
    labels: Iterable[LabelSpec],
    *,
    viewport_rect_px: Optional[QtCore.QRectF] = None,
    margin_px: int = 6,
) -> List[QtCore.QRectF]:
    """Place labels so they stay inside the viewport and don't overlap.

    Returns:
        List of placed label rectangles in viewport pixel coordinates.

    Notes:
        - Works best for labels with ItemIgnoresTransformations.
        - Deterministic: the same anchors => the same layout.
    """

    if QtWidgets is None:
        return []

    vp = view.viewport()
    if viewport_rect_px is None:
        viewport_rect_px = QtCore.QRectF(0.0, 0.0, float(vp.width()), float(vp.height()))

    bounds = viewport_rect_px.adjusted(float(margin_px), float(margin_px), float(-margin_px), float(-margin_px))

    # Sort by priority (desc) then by object id (stable).
    specs = sorted(list(labels), key=lambda s: (-int(s.priority), int(id(s.item))))

    placed: List[QtCore.QRectF] = []

    for spec in specs:
        it = spec.item
        if not it.isVisible():
            continue

        # Bounding rect in item coordinates. With ItemIgnoresTransformations
        # this corresponds to device pixel size reasonably well.
        br = it.boundingRect()
        w = float(br.width())
        h = float(br.height())
        if w <= 1.0 or h <= 1.0:
            # Fallback: measure the plain text
            fm = QtGui.QFontMetrics(it.font())
            r = fm.boundingRect(it.toPlainText())
            w = float(max(8, r.width()))
            h = float(max(8, r.height()))

        # Anchor in viewport pixels
        anchor_px = view.mapFromScene(spec.anchor_scene)
        ax = float(anchor_px.x())
        ay = float(anchor_px.y())

        dx = float(spec.offset_px.x())
        dy = float(spec.offset_px.y())

        # Candidate top-left positions (viewport pixels)
        # Start with preferred quadrant, then try mirrored placements.
        candidates: List[Tuple[float, float]] = []

        # Preferred
        candidates.append((ax + dx, ay + dy - h))
        # Mirror X
        candidates.append((ax - dx - w, ay + dy - h))
        # Mirror Y
        candidates.append((ax + dx, ay - dy))
        # Mirror both
        candidates.append((ax - dx - w, ay - dy))
        # Directly above/below centered
        candidates.append((ax - 0.5 * w, ay - 1.1 * h))
        candidates.append((ax - 0.5 * w, ay + 0.2 * h))

        # Clamp each candidate inside bounds before collision check
        best_rect: Optional[QtCore.QRectF] = None
        best_cost: float = 1e18

        for (tx, ty) in candidates:
            r = _rect_from_topleft(tx, ty, w, h)
            r = _clamp_rect_into(r, bounds)

            # Inflate for padding
            pad = float(max(0, int(spec.pad_px)))
            r_pad = r.adjusted(-pad, -pad, pad, pad)

            if not _intersects_any(r_pad, placed):
                best_rect = r
                best_cost = 0.0
                break

            # Compute simple overlap area as cost
            overlap = 0.0
            for pr in placed:
                inter = r_pad.intersected(pr)
                if not inter.isNull():
                    overlap += float(inter.width() * inter.height())
            if overlap < best_cost:
                best_cost = overlap
                best_rect = r

        if best_rect is None:
            # Shouldn't happen, but be safe.
            best_rect = _clamp_rect_into(_rect_from_topleft(ax, ay, w, h), bounds)

        # Apply: map viewport pixels back to scene
        scene_pos = view.mapToScene(QtCore.QPoint(int(best_rect.x()), int(best_rect.y())))
        it.setPos(scene_pos)

        # Store padded rect for subsequent collision checks
        pad = float(max(0, int(spec.pad_px)))
        placed.append(best_rect.adjusted(-pad, -pad, pad, pad))

    return placed
