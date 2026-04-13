from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Callable

from .contracts import DesktopShellToolSpec
from .lifecycle import HostedToolSession
from .navigation import (
    PRIMARY_WORKFLOW_KEYS,
    describe_workflow_progress,
    numbered_recently_closed_label,
    numbered_session_label,
    ordered_workflow_specs,
)


WORKFLOW_KEYS: tuple[str, ...] = PRIMARY_WORKFLOW_KEYS

WORKFLOW_HINTS: dict[str, str] = {
    "desktop_input_editor": "Подготовьте исходные данные, геометрию, пневматику и параметры расчета.",
    "test_center": "Проверьте конфигурацию и соберите основной маршрут проверок из одного места.",
    "autotest_gui": "Запускайте autotest напрямую, когда нужен отдельный контур прогона без лишних экранов.",
    "full_diagnostics_gui": "Соберите подробную диагностику перед разбором проблем или передачей bundle.",
    "send_results_gui": "Сформируйте итоговый архив и подготовьте результаты к отправке без возврата в WEB.",
}


@dataclass
class ShellHomeViewController:
    workflow_specs: tuple[DesktopShellToolSpec, ...]
    continue_workflow: Callable[[], None]
    list_open_sessions: Callable[[], tuple[HostedToolSession, ...]]
    select_hosted_session: Callable[[str], bool]
    list_recently_closed_specs: Callable[[], tuple[DesktopShellToolSpec, ...]]
    reopen_recently_closed_at_index: Callable[[int], bool]
    workflow_summary_var: tk.StringVar
    continue_workflow_button: ttk.Button
    session_summary_var: tk.StringVar
    session_picker_var: tk.StringVar
    session_picker: ttk.Combobox
    focus_button: ttk.Button
    recently_closed_summary_var: tk.StringVar
    recently_closed_picker_var: tk.StringVar
    recently_closed_picker: ttk.Combobox
    reopen_button: ttk.Button
    workflow_status_vars: dict[str, tk.StringVar]
    workflow_buttons: dict[str, ttk.Button]
    session_label_to_key: dict[str, str]
    recently_closed_label_to_index: dict[str, int]

    def refresh(self) -> None:
        sessions = self.list_open_sessions()
        recently_closed_specs = self.list_recently_closed_specs()
        open_keys = {session.key for session in sessions}
        self.session_label_to_key = {
            numbered_session_label(session, index): session.key
            for index, session in enumerate(sessions, start=1)
        }
        self.recently_closed_label_to_index = {
            numbered_recently_closed_label(spec, index): index
            for index, spec in enumerate(recently_closed_specs, start=1)
        }
        if self.workflow_specs:
            self.workflow_summary_var.set(
                describe_workflow_progress(self.workflow_specs, open_keys)
            )
            self.continue_workflow_button.configure(state="normal")
        else:
            self.workflow_summary_var.set(
                "Основной маршрут пока недоступен в текущей сборке shell."
            )
            self.continue_workflow_button.configure(state="disabled")

        for key, status_var in self.workflow_status_vars.items():
            status_var.set(
                "Открыто в рабочей области" if key in open_keys else "Готово к открытию"
            )
        for key, button in self.workflow_buttons.items():
            button.configure(text="Перейти к окну" if key in open_keys else "Открыть этап")

        if not sessions:
            self.session_summary_var.set(
                "Пока нет открытых встроенных окон. Начните с маршрута слева "
                "или откройте модуль через меню и toolbar."
            )
            self.session_picker_var.set("")
            self.session_picker.configure(values=(), state="disabled")
            self.focus_button.configure(state="disabled")
        else:
            labels = list(self.session_label_to_key.keys())
            self.session_picker.configure(values=labels, state="readonly")
            if self.session_picker_var.get() not in labels:
                self.session_picker_var.set(labels[0])
            listed_titles = ", ".join(labels[:3])
            if len(labels) > 3:
                listed_titles = f"{listed_titles} и еще {len(labels) - 3}"
            self.session_summary_var.set(
                f"Открыто встроенных окон: {len(labels)}. "
                f"Быстрый переход: {listed_titles}."
            )
            self.focus_button.configure(state="normal")

        recent_labels = list(self.recently_closed_label_to_index.keys())
        if not recent_labels:
            self.recently_closed_summary_var.set(
                "Недавно закрытых встроенных окон пока нет. История появится после закрытия вкладок."
            )
            self.recently_closed_picker_var.set("")
            self.recently_closed_picker.configure(values=(), state="disabled")
            self.reopen_button.configure(state="disabled")
            return

        self.recently_closed_picker.configure(values=recent_labels, state="readonly")
        if self.recently_closed_picker_var.get() not in recent_labels:
            self.recently_closed_picker_var.set(recent_labels[0])
        listed_recent = ", ".join(recent_labels[:3])
        if len(recent_labels) > 3:
            listed_recent = f"{listed_recent} и еще {len(recent_labels) - 3}"
        self.recently_closed_summary_var.set(
            f"Можно быстро вернуть: {listed_recent}."
        )
        self.reopen_button.configure(state="normal")

    def focus_selected_session(self) -> bool:
        selected_label = self.session_picker_var.get().strip()
        if not selected_label:
            return False

        key = self.session_label_to_key.get(selected_label)
        if not key:
            self.refresh()
            return False
        return self.select_hosted_session(key)

    def reopen_selected_recently_closed(self) -> bool:
        selected_label = self.recently_closed_picker_var.get().strip()
        if not selected_label:
            return False

        index = self.recently_closed_label_to_index.get(selected_label)
        if index is None:
            self.refresh()
            return False
        return self.reopen_recently_closed_at_index(index)


def build_shell_home_view(
    parent: ttk.Frame,
    *,
    hosted_specs: tuple[DesktopShellToolSpec, ...],
    external_specs: tuple[DesktopShellToolSpec, ...],
    open_tool: Callable[[str], None],
    continue_workflow: Callable[[], None],
    list_open_sessions: Callable[[], tuple[HostedToolSession, ...]],
    select_hosted_session: Callable[[str], bool],
    list_recently_closed_specs: Callable[[], tuple[DesktopShellToolSpec, ...]],
    reopen_recently_closed_at_index: Callable[[int], bool],
) -> ShellHomeViewController:
    ttk.Label(
        parent,
        text="Pneumo Desktop Shell",
        font=("Segoe UI", 16, "bold"),
    ).pack(anchor="w")

    ttk.Label(
        parent,
        text=(
            "Классическое главное окно для модульных desktop-инструментов проекта. "
            "Tk-окна можно постепенно встраивать внутрь shell, а специализированные Qt/PySide6 "
            "окна пока запускаются отдельно, без дублирования их логики."
        ),
        wraplength=1100,
        justify="left",
    ).pack(anchor="w", pady=(6, 14))

    summary = ttk.Frame(parent)
    summary.pack(fill="x", pady=(0, 14))
    summary.columnconfigure(0, weight=1)
    summary.columnconfigure(1, weight=1)
    summary.columnconfigure(2, weight=1)

    main_specs = tuple(spec for spec in hosted_specs if spec.entry_kind == "main")
    tool_specs = tuple(spec for spec in hosted_specs if spec.entry_kind != "main")
    workflow_specs = ordered_workflow_specs(main_specs)
    (
        workflow_summary_var,
        continue_workflow_button,
        workflow_status_vars,
        workflow_buttons,
    ) = _build_workflow_box(
        summary,
        0,
        workflow_specs,
        open_tool,
        continue_workflow,
    )
    (
        session_summary_var,
        session_picker_var,
        session_picker,
        focus_button,
    ) = _build_open_sessions_box(summary, 1)
    (
        recently_closed_summary_var,
        recently_closed_picker_var,
        recently_closed_picker,
        reopen_button,
    ) = _build_recently_closed_box(summary, 2)

    controller = ShellHomeViewController(
        workflow_specs=workflow_specs,
        continue_workflow=continue_workflow,
        list_open_sessions=list_open_sessions,
        select_hosted_session=select_hosted_session,
        list_recently_closed_specs=list_recently_closed_specs,
        reopen_recently_closed_at_index=reopen_recently_closed_at_index,
        workflow_summary_var=workflow_summary_var,
        continue_workflow_button=continue_workflow_button,
        session_summary_var=session_summary_var,
        session_picker_var=session_picker_var,
        session_picker=session_picker,
        focus_button=focus_button,
        recently_closed_summary_var=recently_closed_summary_var,
        recently_closed_picker_var=recently_closed_picker_var,
        recently_closed_picker=recently_closed_picker,
        reopen_button=reopen_button,
        workflow_status_vars=workflow_status_vars,
        workflow_buttons=workflow_buttons,
        session_label_to_key={},
        recently_closed_label_to_index={},
    )
    focus_button.configure(command=controller.focus_selected_session)
    session_picker.bind(
        "<<ComboboxSelected>>",
        lambda _event: controller.focus_selected_session(),
    )
    reopen_button.configure(command=controller.reopen_selected_recently_closed)
    recently_closed_picker.bind(
        "<<ComboboxSelected>>",
        lambda _event: controller.reopen_selected_recently_closed(),
    )

    cards = ttk.Frame(parent)
    cards.pack(fill="both", expand=True)
    cards.columnconfigure(0, weight=1)
    cards.columnconfigure(1, weight=1)

    _build_group_box(cards, 0, "Справочники и служебные центры", tool_specs, open_tool)
    _build_group_box(cards, 1, "Анализ и визуализация", external_specs, open_tool)
    controller.refresh()
    return controller


def _build_workflow_box(
    parent: ttk.Frame,
    column: int,
    specs: tuple[DesktopShellToolSpec, ...],
    open_tool: Callable[[str], None],
    continue_workflow: Callable[[], None],
) -> tuple[tk.StringVar, ttk.Button, dict[str, tk.StringVar], dict[str, ttk.Button]]:
    box = ttk.LabelFrame(parent, text="Основной маршрут", padding=12)
    box.grid(row=0, column=column, sticky="nsew", padx=(0, 6), pady=0)

    workflow_summary_var = tk.StringVar()
    ttk.Label(
        box,
        textvariable=workflow_summary_var,
        wraplength=420,
        justify="left",
    ).pack(anchor="w", pady=(0, 10))
    continue_workflow_button = ttk.Button(
        box,
        text="Продолжить маршрут",
        command=continue_workflow,
    )
    continue_workflow_button.pack(anchor="w", pady=(0, 12))

    workflow_status_vars: dict[str, tk.StringVar] = {}
    workflow_buttons: dict[str, ttk.Button] = {}
    for index, spec in enumerate(specs, start=1):
        card = ttk.Frame(box, padding=(0, 0, 0, 10))
        card.pack(fill="x", expand=False)
        ttk.Label(card, text=f"Шаг {index}", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Label(card, text=spec.title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(
            card,
            text=WORKFLOW_HINTS.get(spec.key, spec.description),
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(2, 6))
        status_var = tk.StringVar(value="Готово к открытию")
        ttk.Label(
            card,
            textvariable=status_var,
        ).pack(anchor="w", pady=(0, 6))
        button = ttk.Button(
            card,
            text="Открыть этап",
            command=lambda key=spec.key: open_tool(key),
        )
        button.pack(anchor="w")
        workflow_status_vars[spec.key] = status_var
        workflow_buttons[spec.key] = button
    return workflow_summary_var, continue_workflow_button, workflow_status_vars, workflow_buttons


def _build_open_sessions_box(
    parent: ttk.Frame,
    column: int,
) -> tuple[tk.StringVar, tk.StringVar, ttk.Combobox, ttk.Button]:
    box = ttk.LabelFrame(parent, text="Открытые встроенные окна", padding=12)
    box.grid(row=0, column=column, sticky="nsew", padx=6, pady=0)

    summary_var = tk.StringVar()
    ttk.Label(
        box,
        textvariable=summary_var,
        wraplength=320,
        justify="left",
    ).pack(anchor="w", pady=(0, 10))

    ttk.Label(box, text="Быстрый переход:").pack(anchor="w")
    picker_row = ttk.Frame(box)
    picker_row.pack(fill="x")

    picker_var = tk.StringVar(value="")
    picker = ttk.Combobox(
        picker_row,
        textvariable=picker_var,
        state="disabled",
        width=26,
    )
    picker.pack(side="left", fill="x", expand=True, padx=(0, 8))

    focus_button = ttk.Button(
        picker_row,
        text="Перейти",
        state="disabled",
    )
    focus_button.pack(side="left")
    return summary_var, picker_var, picker, focus_button


def _build_recently_closed_box(
    parent: ttk.Frame,
    column: int,
) -> tuple[tk.StringVar, tk.StringVar, ttk.Combobox, ttk.Button]:
    box = ttk.LabelFrame(parent, text="Недавно закрытые окна", padding=12)
    box.grid(row=0, column=column, sticky="nsew", padx=(6, 0), pady=0)

    summary_var = tk.StringVar()
    ttk.Label(
        box,
        textvariable=summary_var,
        wraplength=320,
        justify="left",
    ).pack(anchor="w", pady=(0, 10))

    ttk.Label(box, text="Вернуть окно:").pack(anchor="w")
    picker_row = ttk.Frame(box)
    picker_row.pack(fill="x")

    picker_var = tk.StringVar(value="")
    picker = ttk.Combobox(
        picker_row,
        textvariable=picker_var,
        state="disabled",
        width=26,
    )
    picker.pack(side="left", fill="x", expand=True, padx=(0, 8))

    reopen_button = ttk.Button(
        picker_row,
        text="Вернуть",
        state="disabled",
    )
    reopen_button.pack(side="left")
    return summary_var, picker_var, picker, reopen_button

def _build_group_box(
    parent: ttk.Frame,
    column: int,
    title: str,
    specs: tuple[DesktopShellToolSpec, ...],
    open_tool: Callable[[str], None],
) -> None:
    box = ttk.LabelFrame(parent, text=title, padding=12)
    box.grid(row=0, column=column, sticky="nsew", padx=6, pady=6)

    if not specs:
        ttk.Label(
            box,
            text="Пока нет отдельных разделов в этой группе.",
            wraplength=460,
            justify="left",
        ).pack(anchor="w")
        return

    for spec in specs:
        card = ttk.Frame(box, padding=(0, 0, 0, 8))
        card.pack(fill="x", expand=False)
        ttk.Label(card, text=spec.title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(
            card,
            text=spec.description,
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(2, 6))
        ttk.Button(
            card,
            text="Открыть",
            command=lambda key=spec.key: open_tool(key),
        ).pack(anchor="w")
