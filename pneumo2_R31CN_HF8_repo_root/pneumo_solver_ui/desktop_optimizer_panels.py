from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.body = ttk.Frame(self.canvas)
        self.body.columnconfigure(0, weight=1)
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(self.window, width=event.width),
        )


class KeyValueGridPanel(ttk.LabelFrame):
    def __init__(self, master: tk.Misc, *, text: str) -> None:
        super().__init__(master, text=text, padding=10)
        self.columnconfigure(1, weight=1)
        self._rows: list[tuple[ttk.Label, ttk.Label]] = []

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        for label_widget, value_widget in self._rows:
            label_widget.destroy()
            value_widget.destroy()
        self._rows = []
        for row_idx, (label, value) in enumerate(rows):
            label_widget = ttk.Label(self, text=label)
            value_widget = ttk.Label(
                self,
                text=value,
                justify="left",
                wraplength=820,
            )
            label_widget.grid(row=row_idx, column=0, sticky="nw", padx=(0, 12), pady=2)
            value_widget.grid(row=row_idx, column=1, sticky="ew", pady=2)
            self._rows.append((label_widget, value_widget))


class TextReportPanel(ttk.LabelFrame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        text: str,
        height: int = 8,
        wrap: str = "word",
    ) -> None:
        super().__init__(master, text=text, padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.text_widget = tk.Text(
            self,
            height=height,
            wrap=wrap,
            relief="flat",
            borderwidth=0,
        )
        self.text_widget.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.text_widget.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text_widget.configure(yscrollcommand=scrollbar.set)

    def set_text(self, text: str) -> None:
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", str(text or ""))
        self.text_widget.configure(state="disabled")


class HistoryTreePanel(ttk.LabelFrame):
    def __init__(self, master: tk.Misc, *, on_select: callable) -> None:
        super().__init__(master, text="История рабочей области", padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self,
            columns=("status", "pipeline", "backend"),
            show="tree headings",
            height=18,
        )
        self.tree.heading("#0", text="Прогон")
        self.tree.heading("status", text="Статус")
        self.tree.heading("pipeline", text="Контур")
        self.tree.heading("backend", text="Исполнитель")
        self.tree.column("#0", width=260, stretch=True)
        self.tree.column("status", width=90, stretch=False, anchor="center")
        self.tree.column("pipeline", width=90, stretch=False, anchor="center")
        self.tree.column("backend", width=180, stretch=True)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: on_select())

    def set_rows(self, rows: list[dict[str, str]], *, selected_key: str = "") -> None:
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            iid = str(row.get("run_dir") or row.get("name") or "")
            self.tree.insert(
                "",
                "end",
                iid=iid,
                text=str(row.get("name") or ""),
                values=(
                    str(row.get("status") or ""),
                    str(row.get("pipeline") or ""),
                    str(row.get("backend") or ""),
                ),
            )
        if selected_key and self.tree.exists(selected_key):
            self.tree.selection_set(selected_key)
            self.tree.focus(selected_key)
            self.tree.see(selected_key)
        elif rows:
            first = str(rows[0].get("run_dir") or "")
            if first and self.tree.exists(first):
                self.tree.selection_set(first)
                self.tree.focus(first)

    def selected_key(self) -> str:
        selection = self.tree.selection()
        return str(selection[0]) if selection else ""


class FinishedJobsTreePanel(ttk.LabelFrame):
    def __init__(self, master: tk.Misc, *, on_select: callable) -> None:
        super().__init__(master, text="Готовые прогоны", padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self,
            columns=("status", "pipeline", "truth", "verify", "risk"),
            show="tree headings",
            height=18,
        )
        self.tree.heading("#0", text="Прогон")
        self.tree.heading("status", text="Статус")
        self.tree.heading("pipeline", text="Контур")
        self.tree.heading("truth", text="Готовность")
        self.tree.heading("verify", text="Проверка")
        self.tree.heading("risk", text="Риск")
        self.tree.column("#0", width=250, stretch=True)
        self.tree.column("status", width=90, stretch=False, anchor="center")
        self.tree.column("pipeline", width=100, stretch=False, anchor="center")
        self.tree.column("truth", width=90, stretch=False, anchor="center")
        self.tree.column("verify", width=80, stretch=False, anchor="center")
        self.tree.column("risk", width=80, stretch=False, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: on_select())

    def set_rows(self, rows: list[dict[str, str]], *, selected_key: str = "") -> None:
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            iid = str(row.get("run_dir") or row.get("name") or "")
            self.tree.insert(
                "",
                "end",
                iid=iid,
                text=str(row.get("name") or ""),
                values=(
                    str(row.get("status") or ""),
                    str(row.get("pipeline") or ""),
                    str(row.get("truth") or ""),
                    str(row.get("verify") or ""),
                    str(row.get("risk") or ""),
                ),
            )
        if selected_key and self.tree.exists(selected_key):
            self.tree.selection_set(selected_key)
            self.tree.focus(selected_key)
            self.tree.see(selected_key)

    def selected_key(self) -> str:
        selection = self.tree.selection()
        return str(selection[0]) if selection else ""


class HandoffTreePanel(ttk.LabelFrame):
    def __init__(self, master: tk.Misc, *, on_select: callable) -> None:
        super().__init__(master, text="Кандидаты на передачу", padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self,
            columns=("live", "preset", "score", "budget", "seeds"),
            show="tree headings",
            height=18,
        )
        self.tree.heading("#0", text="Прогон")
        self.tree.heading("live", text="Активен")
        self.tree.heading("preset", text="Профиль")
        self.tree.heading("score", text="Оценка")
        self.tree.heading("budget", text="Бюджет")
        self.tree.heading("seeds", text="Зёрна")
        self.tree.column("#0", width=220, stretch=True)
        self.tree.column("live", width=60, stretch=False, anchor="center")
        self.tree.column("preset", width=180, stretch=True)
        self.tree.column("score", width=80, stretch=False, anchor="center")
        self.tree.column("budget", width=80, stretch=False, anchor="center")
        self.tree.column("seeds", width=70, stretch=False, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: on_select())

    def set_rows(self, rows: list[dict[str, str]], *, selected_key: str = "") -> None:
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            iid = str(row.get("run_dir") or row.get("name") or "")
            self.tree.insert(
                "",
                "end",
                iid=iid,
                text=str(row.get("name") or ""),
                values=(
                    str(row.get("live") or ""),
                    str(row.get("preset") or ""),
                    str(row.get("score") or ""),
                    str(row.get("budget") or ""),
                    str(row.get("seeds") or ""),
                ),
            )
        if selected_key and self.tree.exists(selected_key):
            self.tree.selection_set(selected_key)
            self.tree.focus(selected_key)
            self.tree.see(selected_key)

    def selected_key(self) -> str:
        selection = self.tree.selection()
        return str(selection[0]) if selection else ""


class PackagingTreePanel(ttk.LabelFrame):
    def __init__(self, master: tk.Misc, *, on_select: callable) -> None:
        super().__init__(master, text="Прогоны выпуска", padding=8)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self,
            columns=("status", "truth", "verify", "risk", "fallback"),
            show="tree headings",
            height=18,
        )
        self.tree.heading("#0", text="Прогон")
        self.tree.heading("status", text="Статус")
        self.tree.heading("truth", text="Готовность")
        self.tree.heading("verify", text="Проверка")
        self.tree.heading("risk", text="Риск")
        self.tree.heading("fallback", text="Откат")
        self.tree.column("#0", width=230, stretch=True)
        self.tree.column("status", width=90, stretch=False, anchor="center")
        self.tree.column("truth", width=90, stretch=False, anchor="center")
        self.tree.column("verify", width=80, stretch=False, anchor="center")
        self.tree.column("risk", width=70, stretch=False, anchor="center")
        self.tree.column("fallback", width=80, stretch=False, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: on_select())

    def set_rows(self, rows: list[dict[str, str]], *, selected_key: str = "") -> None:
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            iid = str(row.get("run_dir") or row.get("name") or "")
            self.tree.insert(
                "",
                "end",
                iid=iid,
                text=str(row.get("name") or ""),
                values=(
                    str(row.get("status") or ""),
                    str(row.get("truth") or ""),
                    str(row.get("verify") or ""),
                    str(row.get("risk") or ""),
                    str(row.get("fallback") or ""),
                ),
            )
        if selected_key and self.tree.exists(selected_key):
            self.tree.selection_set(selected_key)
            self.tree.focus(selected_key)
            self.tree.see(selected_key)

    def selected_key(self) -> str:
        selection = self.tree.selection()
        return str(selection[0]) if selection else ""


def replace_text(widget: tk.Text, text: str) -> None:
    widget.delete("1.0", "end")
    widget.insert("1.0", str(text or ""))


__all__ = [
    "FinishedJobsTreePanel",
    "HandoffTreePanel",
    "HistoryTreePanel",
    "KeyValueGridPanel",
    "PackagingTreePanel",
    "ScrollableFrame",
    "TextReportPanel",
    "replace_text",
]
