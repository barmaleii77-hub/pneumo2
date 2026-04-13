from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from pneumo_solver_ui.desktop_ui_core import (
    ScrollableFrame,
    build_scrolled_text,
    build_scrolled_treeview,
    build_status_strip,
    create_scrollable_tab,
)


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def test_desktop_ui_core_exports_scroll_resize_primitives() -> None:
    src = (UI_ROOT / "desktop_ui_core.py").read_text(encoding="utf-8", errors="replace")

    assert "class ScrollableFrame" in src
    assert "def create_scrollable_tab(" in src
    assert "def build_scrolled_text(" in src
    assert "def build_scrolled_treeview(" in src
    assert "def build_status_strip(" in src
    assert "ttk.Sizegrip(strip)" in src
    assert "self.vscrollbar" in src
    assert "self.hscrollbar" in src
    assert "self._wheel_bindtag" in src
    assert "bind_class(self._wheel_bindtag, \"<MouseWheel>\"" in src
    assert "widget.bindtags((bindtags[0], self._wheel_bindtag, *bindtags[1:]))" in src


def test_desktop_ui_core_widgets_create_scrollbars_and_sizegrip() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        host = ScrollableFrame(root, xscroll=True, yscroll=True)
        assert isinstance(host.canvas, tk.Canvas)
        assert isinstance(host.body, ttk.Frame)
        assert isinstance(host.vscrollbar, ttk.Scrollbar)
        assert isinstance(host.hscrollbar, ttk.Scrollbar)
        entry = ttk.Entry(host.body)
        entry.pack()
        host.update_idletasks()
        assert host._wheel_bindtag in entry.bindtags()

        notebook = ttk.Notebook(root)
        tab_host, tab_body = create_scrollable_tab(notebook, padding=8)
        assert isinstance(tab_host, ScrollableFrame)
        assert isinstance(tab_body, ttk.Frame)

        text_frame, text_widget = build_scrolled_text(root, wrap="none")
        assert isinstance(text_widget, tk.Text)
        assert sum(isinstance(child, ttk.Scrollbar) for child in text_frame.winfo_children()) >= 2

        tree_frame, tree = build_scrolled_treeview(root, columns=("a",), show="headings")
        assert isinstance(tree, ttk.Treeview)
        assert sum(isinstance(child, ttk.Scrollbar) for child in tree_frame.winfo_children()) == 2

        primary = tk.StringVar(master=root, value="Готово")
        secondary = tk.StringVar(master=root, value="Состояние")
        strip = build_status_strip(root, primary_var=primary, secondary_vars=(secondary,), reserve_columns=1)
        assert any(isinstance(child, ttk.Sizegrip) for child in strip.winfo_children())
    finally:
        root.destroy()


def test_desktop_windows_reuse_shared_scroll_and_status_core() -> None:
    expectations = {
        "tools/desktop_input_editor.py": ("ScrollableFrame", "build_scrolled_text", "ttk.Sizegrip("),
        "tools/desktop_run_setup_center.py": ("ScrollableFrame", "build_status_strip", ".minsize("),
        "tools/desktop_results_center.py": ("build_scrolled_treeview", "build_scrolled_text", "ttk.Panedwindow"),
        "desktop_shell/main_window.py": ("ScrollableFrame", "ttk.Scrollbar(tree_frame", "ttk.Sizegrip(status)"),
        "tools/desktop_diagnostics_center.py": ("create_scrollable_tab", "build_scrolled_text", "build_status_strip"),
        "tools/desktop_geometry_reference_center.py": ("create_scrollable_tab", "build_status_strip", ".minsize("),
        "tools/desktop_control_center.py": ("build_scrolled_text", "build_status_strip", ".minsize("),
        "tools/test_center_gui.py": ("ScrollableFrame", "build_scrolled_text", "build_status_strip"),
    }

    for rel_path, needles in expectations.items():
        src = (UI_ROOT / rel_path).read_text(encoding="utf-8", errors="replace")
        for needle in needles:
            assert needle in src, f"{rel_path} is missing {needle}"


def test_specialized_qt_windows_keep_desktop_resize_contract() -> None:
    compare_src = (UI_ROOT / "qt_compare_viewer.py").read_text(encoding="utf-8", errors="replace")
    mnemo_src = (UI_ROOT / "desktop_mnemo" / "app.py").read_text(encoding="utf-8", errors="replace")

    assert "class CompareViewer(QtWidgets.QMainWindow)" in compare_src
    assert "self.setMinimumSize(1220, 820)" in compare_src
    assert "QDockWidget" in compare_src
    assert "QSplitter" in compare_src
    assert "QStatusBar" in compare_src

    assert "class MnemoMainWindow(QtWidgets.QMainWindow)" in mnemo_src
    assert "self.setMinimumSize(1500, 980)" in mnemo_src
    assert "self.statusBar().addWidget(self.status_text, 1)" in mnemo_src
    assert "QtWidgets.QDockWidget" in mnemo_src
