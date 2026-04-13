from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def normalize_help_text(text: str | None) -> str:
    raw = " ".join(str(text or "").split()).strip()
    return raw


def show_help_dialog(
    parent: tk.Misc,
    *,
    title: str,
    headline: str = "",
    body: str = "",
) -> None:
    window = tk.Toplevel(parent)
    window.title(title)
    window.geometry("660x420")
    window.minsize(520, 320)
    window.transient(parent.winfo_toplevel())

    outer = ttk.Frame(window, padding=14)
    outer.pack(fill="both", expand=True)

    if headline:
        ttk.Label(
            outer,
            text=headline,
            font=("Segoe UI", 11, "bold"),
            wraplength=600,
            justify="left",
        ).pack(anchor="w")

    text = tk.Text(
        outer,
        wrap="word",
        relief="solid",
        borderwidth=1,
        padx=10,
        pady=10,
    )
    text.pack(fill="both", expand=True, pady=(10, 0))
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=text.yview)
    scrollbar.place(relx=1.0, rely=0.14, relheight=0.74, anchor="ne")
    text.configure(yscrollcommand=scrollbar.set)
    text.insert("1.0", body.strip() + "\n")
    text.configure(state="disabled")

    ttk.Button(outer, text="Закрыть", command=window.destroy).pack(anchor="e", pady=(10, 0))
    window.focus_force()


class HoverTooltip:
    def __init__(
        self,
        widget: tk.Misc,
        *,
        text: str,
        delay_ms: int = 450,
        wraplength: int = 360,
    ) -> None:
        self.widget = widget
        self.text = normalize_help_text(text)
        self.delay_ms = int(delay_ms)
        self.wraplength = int(wraplength)
        self._after_id: str | None = None
        self._tip_window: tk.Toplevel | None = None

        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _event: object | None = None) -> None:
        if not self.text:
            return
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _event: object | None = None) -> None:
        self._cancel()
        self._hide()

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        if self._tip_window is not None or not self.text:
            return
        root = self.widget.winfo_toplevel()
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        window = tk.Toplevel(root)
        window.wm_overrideredirect(True)
        window.wm_geometry(f"+{x}+{y}")
        frame = ttk.Frame(window, padding=8, relief="solid", borderwidth=1)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=self.text,
            wraplength=self.wraplength,
            justify="left",
        ).pack(anchor="w")
        self._tip_window = window

    def _hide(self) -> None:
        if self._tip_window is not None:
            try:
                self._tip_window.destroy()
            except Exception:
                pass
            self._tip_window = None


def attach_tooltip(widget: tk.Misc, text: str | None) -> HoverTooltip | None:
    normalized = normalize_help_text(text)
    if not normalized:
        return None
    return HoverTooltip(widget, text=normalized)


__all__ = [
    "HoverTooltip",
    "attach_tooltip",
    "normalize_help_text",
    "show_help_dialog",
]
