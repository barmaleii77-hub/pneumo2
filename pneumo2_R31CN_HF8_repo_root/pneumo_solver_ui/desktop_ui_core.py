from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        xscroll: bool = False,
        yscroll: bool = True,
        fit_width: bool = True,
    ) -> None:
        super().__init__(master)
        self._fit_width = bool(fit_width)
        self._wheel_bindtag = f"ScrollableFrameWheel_{id(self)}"
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.body = ttk.Frame(self.canvas)
        self.body.columnconfigure(0, weight=1)
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.vscrollbar: ttk.Scrollbar | None = None
        self.hscrollbar: ttk.Scrollbar | None = None

        if yscroll:
            self.vscrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            self.vscrollbar.grid(row=0, column=1, sticky="ns")
            self.canvas.configure(yscrollcommand=self.vscrollbar.set)
        if xscroll:
            self.hscrollbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
            self.hscrollbar.grid(row=1, column=0, sticky="ew")
            self.canvas.configure(xscrollcommand=self.hscrollbar.set)

        self.bind_class(self._wheel_bindtag, "<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_class(self._wheel_bindtag, "<Button-4>", self._on_mousewheel_up, add="+")
        self.bind_class(self._wheel_bindtag, "<Button-5>", self._on_mousewheel_down, add="+")

        self.body.bind("<Configure>", self._on_body_configure, add="+")
        self.canvas.bind("<Configure>", self._on_canvas_configure, add="+")
        self.after_idle(self._refresh_scroll_bindtags)

    def _on_body_configure(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._refresh_scroll_bindtags()

    def _on_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        if self._fit_width:
            self.canvas.itemconfigure(self.window, width=event.width)
        self._refresh_scroll_bindtags()

    def _iter_descendants(self, widget: tk.Misc) -> list[tk.Misc]:
        nodes: list[tk.Misc] = []
        stack = [widget]
        while stack:
            current = stack.pop()
            for child in current.winfo_children():
                nodes.append(child)
                stack.append(child)
        return nodes

    def _should_attach_mousewheel(self, widget: tk.Misc) -> bool:
        return not isinstance(widget, (tk.Text, tk.Listbox, ttk.Treeview, ttk.Scrollbar))

    def _ensure_bindtag(self, widget: tk.Misc) -> None:
        if not self._should_attach_mousewheel(widget):
            return
        bindtags = tuple(widget.bindtags())
        if self._wheel_bindtag in bindtags:
            return
        widget.bindtags((bindtags[0], self._wheel_bindtag, *bindtags[1:]))

    def _refresh_scroll_bindtags(self) -> None:
        targets = [self.canvas, self.body, *self._iter_descendants(self.body)]
        for widget in targets:
            try:
                self._ensure_bindtag(widget)
            except Exception:
                continue

    def _on_mousewheel(self, event: tk.Event[tk.Misc]) -> str | None:
        if self.vscrollbar is None:
            return None
        delta = int(getattr(event, "delta", 0) or 0)
        if delta == 0:
            return None
        self.canvas.yview_scroll(int(-1 * (delta / 120)), "units")
        return "break"

    def _on_mousewheel_up(self, _event: tk.Event[tk.Misc]) -> str | None:
        if self.vscrollbar is None:
            return None
        self.canvas.yview_scroll(-1, "units")
        return "break"

    def _on_mousewheel_down(self, _event: tk.Event[tk.Misc]) -> str | None:
        if self.vscrollbar is None:
            return None
        self.canvas.yview_scroll(1, "units")
        return "break"


def create_scrollable_tab(
    notebook: ttk.Notebook,
    *,
    padding: int | tuple[int, ...] = 0,
    xscroll: bool = False,
    yscroll: bool = True,
    fit_width: bool = True,
) -> tuple[ScrollableFrame, ttk.Frame]:
    host = ScrollableFrame(
        notebook,
        xscroll=xscroll,
        yscroll=yscroll,
        fit_width=fit_width,
    )
    body = ttk.Frame(host.body, padding=padding)
    body.pack(fill="both", expand=True)
    body.columnconfigure(0, weight=1)
    return host, body


def build_scrolled_text(
    parent: tk.Misc,
    *,
    wrap: str = "word",
    height: int = 10,
    state: str = "normal",
) -> tuple[ttk.Frame, tk.Text]:
    frame = ttk.Frame(parent)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)

    text = tk.Text(frame, wrap=wrap, height=height, state=state)
    text.grid(row=0, column=0, sticky="nsew")

    yscroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    yscroll.grid(row=0, column=1, sticky="ns")
    text.configure(yscrollcommand=yscroll.set)

    if wrap == "none":
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        text.configure(xscrollcommand=xscroll.set)

    return frame, text


def build_scrolled_treeview(
    parent: tk.Misc,
    **tree_kwargs: object,
) -> tuple[ttk.Frame, ttk.Treeview]:
    frame = ttk.Frame(parent)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)

    tree = ttk.Treeview(frame, **tree_kwargs)
    tree.grid(row=0, column=0, sticky="nsew")

    yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    xscroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    yscroll.grid(row=0, column=1, sticky="ns")
    xscroll.grid(row=1, column=0, sticky="ew")
    tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

    return frame, tree


def build_status_strip(
    parent: tk.Misc,
    *,
    primary_var: tk.Variable | None = None,
    secondary_vars: tuple[tk.Variable, ...] = (),
    padding: tuple[int, int] = (10, 6),
    reserve_columns: int = 0,
) -> ttk.Frame:
    strip = ttk.Frame(parent, padding=padding)
    strip.columnconfigure(0, weight=1)

    col = 0
    if primary_var is not None:
        ttk.Label(strip, textvariable=primary_var).grid(row=0, column=0, sticky="w")
        col = 1
    for variable in secondary_vars:
        strip.columnconfigure(col, weight=0)
        ttk.Label(strip, textvariable=variable).grid(row=0, column=col, sticky="e", padx=(12, 0))
        col += 1
    ttk.Sizegrip(strip).grid(row=0, column=col + max(0, int(reserve_columns)), sticky="se", padx=(12, 0))
    return strip
