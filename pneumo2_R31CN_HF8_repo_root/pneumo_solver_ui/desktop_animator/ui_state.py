# -*- coding: utf-8 -*-
"""UI state persistence helpers (Desktop Animator).

Design goals
- Persist everything the user changes in UI (values, checkboxes, splitters, window geometry).
- Store settings in a project-local INI file (portable, does not pollute OS registry).
- Be tolerant to invalid/corrupted settings values.

Settings location
- By default: `pneumo_solver_ui/workspace/desktop_animator_settings.ini`

This module is intentionally small and dependency-free (except PySide6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from PySide6 import QtCore, QtWidgets


def default_settings_path(project_root: Path) -> Path:
    """Return a project-local INI path."""
    return Path(project_root) / "pneumo_solver_ui" / "workspace" / "desktop_animator_settings.ini"


@dataclass
class UiState:
    """Thin wrapper around QSettings (INI format)."""

    ini_path: Path
    prefix: str = "desktop_animator"

    def __post_init__(self):
        self.ini_path = Path(self.ini_path)
        try:
            self.ini_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self.qs = QtCore.QSettings(str(self.ini_path), QtCore.QSettings.IniFormat)

    # ----------------
    # low-level access
    # ----------------

    def _k(self, key: str) -> str:
        key = str(key).strip()
        if not self.prefix:
            return key
        return f"{self.prefix}/{key}"

    def sync(self):
        try:
            self.qs.sync()
        except Exception:
            pass

    def value(self, key: str, default: Any = None) -> Any:
        try:
            return self.qs.value(self._k(key), defaultValue=default)
        except Exception:
            return default

    def set_value(self, key: str, value: Any):
        try:
            self.qs.setValue(self._k(key), value)
        except Exception:
            pass

    # -----------------
    # typed convenience
    # -----------------

    def get_str(self, key: str, default: str = "") -> str:
        v = self.value(key, default)
        if v is None:
            return default
        return str(v)

    def get_bool(self, key: str, default: bool = False) -> bool:
        v = self.value(key, default)
        if isinstance(v, bool):
            return bool(v)
        if isinstance(v, (int, float)):
            return bool(int(v))
        s = str(v).strip().lower()
        if s in ("1", "true", "yes", "y", "on"):
            return True
        if s in ("0", "false", "no", "n", "off"):
            return False
        return bool(default)

    def get_int(self, key: str, default: int = 0) -> int:
        v = self.value(key, default)
        try:
            return int(v)
        except Exception:
            return int(default)

    def get_float(self, key: str, default: float = 0.0) -> float:
        v = self.value(key, default)
        try:
            return float(v)
        except Exception:
            return float(default)

    def get_bytes(self, key: str) -> Optional[QtCore.QByteArray]:
        v = self.value(key, None)
        if v is None:
            return None
        if isinstance(v, QtCore.QByteArray):
            return v
        # Sometimes QSettings returns bytes/str depending on backend.
        if isinstance(v, (bytes, bytearray)):
            return QtCore.QByteArray(bytes(v))
        return None

    # -----------------
    # binding utilities
    # -----------------

    def bind_window_geometry(self, w: QtWidgets.QWidget, key: str = "window/geometry"):
        """Restore geometry immediately; caller should save it on close."""
        ba = self.get_bytes(key)
        if ba is not None:
            try:
                w.restoreGeometry(ba)
            except Exception:
                pass

    def save_window_geometry(self, w: QtWidgets.QWidget, key: str = "window/geometry"):
        try:
            self.set_value(key, w.saveGeometry())
        except Exception:
            pass

    def bind_splitter(self, s: QtWidgets.QSplitter, key: str):
        ba = self.get_bytes(key)
        if ba is not None:
            try:
                s.restoreState(ba)
            except Exception:
                pass

        def _save():
            try:
                self.set_value(key, s.saveState())
            except Exception:
                pass

        try:
            s.splitterMoved.connect(lambda *_: _save())
        except Exception:
            pass

    def bind_checkbox(self, cb: QtWidgets.QAbstractButton, key: str, default: bool = False):
        v = self.get_bool(key, default)
        try:
            cb.blockSignals(True)
            cb.setChecked(bool(v))
            cb.blockSignals(False)
        except Exception:
            pass

        try:
            cb.toggled.connect(lambda x: self.set_value(key, bool(x)))
        except Exception:
            pass

    def bind_action_checked(self, act: QtGui.QAction, key: str, default: bool = False):
        # Late import to avoid a hard dependency in non-GUI tests.
        from PySide6 import QtGui

        v = self.get_bool(key, default)
        try:
            act.setCheckable(True)
            act.blockSignals(True)
            act.setChecked(bool(v))
            act.blockSignals(False)
        except Exception:
            pass

        try:
            act.toggled.connect(lambda x: self.set_value(key, bool(x)))
        except Exception:
            pass

    def bind_spinbox(self, sp: QtWidgets.QAbstractSpinBox, key: str, default: float = 0.0):
        # Works for both QSpinBox and QDoubleSpinBox.
        v = self.value(key, default)
        try:
            fv = float(v)
        except Exception:
            fv = float(default)

        try:
            if hasattr(sp, "minimum") and hasattr(sp, "maximum"):
                fv = min(max(fv, float(sp.minimum())), float(sp.maximum()))
            sp.blockSignals(True)
            sp.setValue(fv)  # type: ignore[arg-type]
            sp.blockSignals(False)
        except Exception:
            pass

        try:
            # valueChanged is overloaded; connect to the float version if possible.
            sp.valueChanged.connect(lambda x: self.set_value(key, float(x)))  # type: ignore[attr-defined]
        except Exception:
            try:
                sp.editingFinished.connect(lambda: self.set_value(key, float(sp.value())))  # type: ignore[attr-defined]
            except Exception:
                pass

    def bind_combobox(self, cb: QtWidgets.QComboBox, key: str, default_text: str = ""):
        txt = self.get_str(key, default_text)
        try:
            idx = cb.findText(txt)
            if idx >= 0:
                cb.blockSignals(True)
                cb.setCurrentIndex(idx)
                cb.blockSignals(False)
        except Exception:
            pass

        try:
            cb.currentTextChanged.connect(lambda t: self.set_value(key, str(t)))
        except Exception:
            pass
