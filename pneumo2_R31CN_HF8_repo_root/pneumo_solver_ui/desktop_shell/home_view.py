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
    "desktop_input_editor": "Подготовьте исходные данные, геометрию, пневматику и параметры расчёта.",
    "desktop_ring_editor": "Соберите циклический сценарий и проверьте, что дорога готова к расчётному набору.",
    "test_center": "Проверьте конфигурацию и соберите основной порядок проверок из одного места.",
    "desktop_run_setup_center": "Создайте или проверьте базовый прогон перед оптимизацией.",
    "desktop_optimizer_center": "Настройте цель, ограничения и режим оптимизации перед длительным прогоном.",
    "desktop_results_center": "Проверьте результаты, замечания и переходы к сравнению, анализу и визуализации.",
    "desktop_animator": "Загрузите результаты расчёта в аниматор после анализа.",
    "desktop_diagnostics_center": "Соберите диагностику и подготовьте материалы после проверки результата.",
    "autotest_gui": "Запускайте автотест напрямую, когда нужен отдельный контур прогона без лишних экранов.",
    "full_diagnostics_gui": "Соберите подробную диагностику перед разбором проблем или отправкой архива.",
    "send_results_gui": "Сформируйте итоговый архив и подготовьте результаты к отправке в отдельном окне.",
}

V10_FIRST_PATH_TEXT = (
    "Что делать сначала: исходные данные; сценарии; набор испытаний; базовый прогон; "
    "оптимизация; анализ; анимация; диагностика."
)

DIAGNOSTICS_KEYS: tuple[str, ...] = (
    "desktop_diagnostics_center",
    "full_diagnostics_gui",
    "send_results_gui",
)

CARD_HINTS: dict[str, str] = {
    "desktop_diagnostics_center": (
        "Основной порядок проверки состояния проекта и подготовки архива диагностики. "
        "Начинайте отсюда, если нужно разобраться с ошибкой или передать материалы."
    ),
    "full_diagnostics_gui": (
        "Расширенная проверка для технического разбора. Обычно начинайте с основного порядка диагностики."
    ),
    "send_results_gui": (
        "Дополнительное окно для подготовки материалов к отправке после диагностики и проверки результатов."
    ),
    "compare_viewer": (
        "Расширенный режим из анализа результатов. Используйте его, когда встроенного сравнения уже мало."
    ),
    "desktop_mnemo": (
        "Дополнительная инженерная поверхность после анализа: показывает пневматическое состояние и связи компонентов."
    ),
    "desktop_animator": (
        "Шаг просмотра результатов расчёта после анализа: движение, геометрия и временной ход."
    ),
}

ACTION_BUTTON_TEXTS: dict[str, str] = {
    "desktop_input_editor": "Ввести исходные данные",
    "desktop_ring_editor": "Собрать сценарий",
    "test_center": "Проверить набор испытаний",
    "desktop_run_setup_center": "Создать базовый прогон",
    "desktop_optimizer_center": "Настроить оптимизацию",
    "desktop_results_center": "Разобрать результаты",
    "desktop_geometry_reference_center": "Проверить справочники",
    "desktop_engineering_analysis_center": "Открыть инженерный анализ",
    "desktop_diagnostics_center": "Собрать диагностику",
    "full_diagnostics_gui": "Запустить расширенную проверку",
    "send_results_gui": "Подготовить отправку",
    "autotest_gui": "Запустить автотесты",
    "compare_viewer": "Подробное сравнение",
    "desktop_mnemo": "Показать пневмосхему",
    "desktop_animator": "Загрузить анимацию",
}


def _action_button_text(spec: DesktopShellToolSpec) -> str:
    return ACTION_BUTTON_TEXTS.get(spec.key, f"Перейти: {spec.title}")


def _unique_specs(specs: tuple[DesktopShellToolSpec, ...]) -> tuple[DesktopShellToolSpec, ...]:
    seen: set[str] = set()
    result: list[DesktopShellToolSpec] = []
    for spec in specs:
        if spec.key in seen:
            continue
        seen.add(spec.key)
        result.append(spec)
    return tuple(result)


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
                "Основной порядок работы пока недоступен в текущей сборке."
            )
            self.continue_workflow_button.configure(state="disabled")

        for key, status_var in self.workflow_status_vars.items():
            status_var.set(
                "Открыто в рабочей области" if key in open_keys else "Готов к переходу"
            )
        for key, button in self.workflow_buttons.items():
            spec = next((item for item in self.workflow_specs if item.key == key), None)
            if spec is not None:
                button.configure(text=_action_button_text(spec))

        if not sessions:
            self.session_summary_var.set(
                "Пока нет открытых встроенных окон. Начните с порядка работы слева "
                "или откройте модуль через меню или панель инструментов."
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
        text="Pneumo: рабочее место инженера",
        font=("Segoe UI", 16, "bold"),
    ).pack(anchor="w")

    ttk.Label(
        parent,
        text=(
            "Классическое главное окно показывает один порядок первого запуска. "
            "Дополнительные окна доступны ниже и не спорят с основным путём."
        ),
        wraplength=1100,
        justify="left",
    ).pack(anchor="w", pady=(6, 14))
    ttk.Label(
        parent,
        text=V10_FIRST_PATH_TEXT,
        wraplength=1100,
        justify="left",
    ).pack(anchor="w", pady=(0, 14))

    for child in tuple(parent.pack_slaves()):
        if isinstance(child, ttk.Label):
            child.pack_forget()
    summary = ttk.Frame(parent)
    summary.pack(fill="x", pady=(0, 14))
    summary.columnconfigure(0, weight=1)
    summary.columnconfigure(1, weight=1)
    summary.columnconfigure(2, weight=1)

    main_specs = tuple(spec for spec in hosted_specs if spec.entry_kind == "main")
    tool_specs = tuple(spec for spec in hosted_specs if spec.entry_kind == "tool")
    contextual_specs = tuple(spec for spec in hosted_specs if spec.entry_kind == "contextual")
    diagnostics_specs = tuple(spec for spec in tool_specs if spec.key in DIAGNOSTICS_KEYS)
    support_specs = tuple(spec for spec in tool_specs if spec.key not in DIAGNOSTICS_KEYS) + contextual_specs
    animator_specs = tuple(spec for spec in external_specs if spec.key == "desktop_animator")
    external_secondary_specs = tuple(spec for spec in external_specs if spec.key != "desktop_animator")
    workflow_specs = ordered_workflow_specs(
        _unique_specs((*main_specs, *animator_specs, *diagnostics_specs))
    )
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

    _build_group_box(
        cards,
        0,
        0,
        "Диагностика и отправка",
        diagnostics_specs,
        open_tool,
        intro="Один понятный порядок работы: собрать диагностику и подготовить материалы без поиска по разным окнам.",
        columnspan=2,
        primary_key="desktop_diagnostics_center",
        primary_button_text="Собрать диагностику",
        secondary_title="Дополнительные действия после диагностики",
    )
    _build_group_box(
        cards,
        1,
        0,
        "Справочники, проверка и анализ",
        support_specs,
        open_tool,
        intro="Окна поддержки основного порядка работы: справочники, дополнительные проверки и инженерный разбор.",
    )
    _build_group_box(
        cards,
        1,
        1,
        "Анимация результата",
        animator_specs,
        open_tool,
        intro="Отдельный просмотр движения и геометрии после анализа результата.",
        primary_key="desktop_animator",
        primary_button_text="Загрузить анимацию",
    )
    _build_group_box(
        cards,
        2,
        1,
        "Расширенное сравнение и пневмосхема",
        external_secondary_specs,
        open_tool,
        intro="Второй слой для подробного разбора после анализа: сравнение на отдельном экране и пневматическая схема.",
    )
    controller.refresh()
    return controller


def _build_workflow_box(
    parent: ttk.Frame,
    column: int,
    specs: tuple[DesktopShellToolSpec, ...],
    open_tool: Callable[[str], None],
    continue_workflow: Callable[[], None],
) -> tuple[tk.StringVar, ttk.Button, dict[str, tk.StringVar], dict[str, ttk.Button]]:
    box = ttk.LabelFrame(parent, text="Основной порядок работы", padding=12)
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
        text="Продолжить работу",
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
        status_var = tk.StringVar(value="Готов к переходу")
        ttk.Label(
            card,
            textvariable=status_var,
        ).pack(anchor="w", pady=(0, 6))
        button = ttk.Button(
            card,
            text=_action_button_text(spec),
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
    row: int,
    column: int,
    title: str,
    specs: tuple[DesktopShellToolSpec, ...],
    open_tool: Callable[[str], None],
    *,
    intro: str = "",
    columnspan: int = 1,
    primary_key: str = "",
    primary_button_text: str = "",
    secondary_title: str = "",
) -> None:
    box = ttk.LabelFrame(parent, text=title, padding=12)
    box.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=6, pady=6)

    if intro:
        ttk.Label(
            box,
            text=intro,
            wraplength=960 if columnspan > 1 else 460,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

    if not specs:
        ttk.Label(
            box,
            text="Пока нет отдельных окон в этой группе.",
            wraplength=460,
            justify="left",
        ).pack(anchor="w")
        return

    primary_specs = tuple(spec for spec in specs if primary_key and spec.key == primary_key)
    secondary_specs = tuple(spec for spec in specs if not primary_key or spec.key != primary_key)

    for spec in primary_specs:
        _build_tool_card(
            box,
            spec,
            open_tool,
            columnspan=columnspan,
            button_text=primary_button_text or _action_button_text(spec),
        )

    if secondary_specs and secondary_title:
        ttk.Label(
            box,
            text=secondary_title,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(4, 6))

    for spec in secondary_specs:
        _build_tool_card(
            box,
            spec,
            open_tool,
            columnspan=columnspan,
            button_text=_action_button_text(spec),
        )


def _build_tool_card(
    parent: ttk.Frame,
    spec: DesktopShellToolSpec,
    open_tool: Callable[[str], None],
    *,
    columnspan: int,
    button_text: str,
) -> None:
    card = ttk.Frame(parent, padding=(0, 0, 0, 8))
    card.pack(fill="x", expand=False)
    ttk.Label(card, text=spec.title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
    ttk.Label(
        card,
        text=CARD_HINTS.get(spec.key, spec.description),
        wraplength=960 if columnspan > 1 else 460,
        justify="left",
    ).pack(anchor="w", pady=(2, 6))
    ttk.Button(
        card,
        text=button_text,
        command=lambda key=spec.key: open_tool(key),
    ).pack(anchor="w")
