from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pneumo_solver_ui.desktop_optimizer_panels import (
    KeyValueGridPanel,
    OptimizationParametersTreePanel,
    ScrollableFrame,
    TextReportPanel,
    replace_text,
)
from pneumo_solver_ui.optimization_contract_summary_ui import format_hard_gate


PROBLEM_HASH_MODE_LABELS: dict[str, str] = {
    "stable": "Обычный контроль",
    "legacy": "Совместимый контроль",
}


OPERATOR_TOKEN_LABELS: dict[str, str] = {
    "default_base.json only": "базовый файл по умолчанию",
    "active_baseline_contract.json": "активный опорный прогон",
    "active_contract": "активный опорный прогон",
    "current": "актуален",
    "stale": "устарел",
    "missing": "не найден",
    "invalid": "ошибка",
}


def _problem_hash_mode_label(value: object) -> str:
    text = str(value or "").strip().lower()
    return PROBLEM_HASH_MODE_LABELS.get(text, text or "режим не выбран")


def _operator_token_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"
    if text in OPERATOR_TOKEN_LABELS:
        return OPERATOR_TOKEN_LABELS[text]
    lower = text.lower()
    if lower in OPERATOR_TOKEN_LABELS:
        return OPERATOR_TOKEN_LABELS[lower]
    if text.startswith("метрика_"):
        return text.removeprefix("метрика_").replace("_", " ")
    return text


def _operator_list_text(values: object) -> str:
    if isinstance(values, str):
        items = (values,)
    else:
        items = tuple(values or ())
    return ", ".join(_operator_token_text(item) for item in items) or "—"


def _stage_count_text(rows: dict[object, object]) -> str:
    parts: list[str] = []
    stage_labels = {
        "stage0_relevance": "предварительный отбор",
        "stage1_long": "длинная проверка",
        "stage2_final": "финальная проверка",
        "0": "предварительный отбор",
        "1": "длинная проверка",
        "2": "финальная проверка",
    }
    for key, value in rows.items():
        label = stage_labels.get(str(key), str(key).replace("_", " "))
        parts.append(f"{label} - {value}")
    return "; ".join(parts) or "нет включённых стадий"


class DesktopOptimizerContractTab(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: object) -> None:
        super().__init__(master)
        self.controller = controller
        self.problem_hash_mode_var = tk.StringVar(
            value=_problem_hash_mode_label(controller.var("settings_opt_problem_hash_mode").get())
        )
        self.scrollable = ScrollableFrame(self)
        self.scrollable.pack(fill="both", expand=True)
        body = self.scrollable.body

        ttk.Label(
            body,
            text="Параметры оптимизации и диапазоны поиска",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text=(
                "Здесь выбираются параметры, которые можно менять в оптимизации, и диапазоны поиска для них. "
                "Допустимые значения в исходных данных нужны для проверки ввода и не заменяют этот список."
            ),
            wraplength=980,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 10))

        self.parameters_panel = OptimizationParametersTreePanel(body)
        self.parameters_panel.grid(row=2, column=0, sticky="ew")

        self.summary_panel = KeyValueGridPanel(body, text="Снимок параметров оптимизации")
        self.summary_panel.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        self.paths_panel = KeyValueGridPanel(body, text="Подготовленные файлы")
        self.paths_panel.grid(row=4, column=0, sticky="ew", pady=(10, 0))

        objective_frame = ttk.LabelFrame(body, text="Цели и ограничение", padding=10)
        objective_frame.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        objective_frame.columnconfigure(1, weight=1)
        objective_frame.columnconfigure(3, weight=1)

        ttk.Label(objective_frame, text="Цели оптимизации").grid(row=0, column=0, sticky="nw", padx=(0, 8))
        self.objective_text = tk.Text(objective_frame, height=5, wrap="word")
        self.objective_text.grid(row=0, column=1, columnspan=3, sticky="ew")

        ttk.Label(objective_frame, text="Ключ штрафа").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(
            objective_frame,
            textvariable=controller.var("opt_penalty_key"),
        ).grid(row=1, column=1, sticky="ew", pady=(8, 0))

        ttk.Label(objective_frame, text="Допуск штрафа").grid(row=1, column=2, sticky="w", padx=(12, 8), pady=(8, 0))
        ttk.Entry(
            objective_frame,
            textvariable=controller.var("opt_penalty_tol"),
            width=14,
        ).grid(row=1, column=3, sticky="w", pady=(8, 0))

        ttk.Label(objective_frame, text="Режим контроля задачи").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.problem_hash_mode_combo = ttk.Combobox(
            objective_frame,
            textvariable=self.problem_hash_mode_var,
            values=tuple(PROBLEM_HASH_MODE_LABELS.values()),
            state="readonly",
            width=18,
        )
        self.problem_hash_mode_combo.grid(row=2, column=1, sticky="w", pady=(8, 0))
        self.problem_hash_mode_combo.bind("<<ComboboxSelected>>", self._on_problem_hash_mode_selected)

        actions = ttk.Frame(objective_frame)
        actions.grid(row=2, column=2, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(
            actions,
            text="Обновить сводку",
            command=controller.refresh_all,
        ).pack(side="right")

        self.stage_policy_panel = TextReportPanel(
            body,
            text="План стадий",
            height=8,
        )
        self.stage_policy_panel.grid(row=6, column=0, sticky="ew", pady=(10, 0))

        self.drift_panel = TextReportPanel(
            body,
            text="Расхождение выбранного прогона с текущим запуском",
            height=10,
        )
        self.drift_panel.grid(row=7, column=0, sticky="ew", pady=(10, 0))

        selection_frame = ttk.LabelFrame(body, text="Действия по выбранному прогону", padding=10)
        selection_frame.grid(row=8, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(
            selection_frame,
            text="Применить параметры оптимизации",
            command=controller.apply_selected_run_contract,
        ).pack(side="left")
        ttk.Button(
            selection_frame,
            text="Открыть паспорт целей",
            command=controller.open_selected_objective_contract,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            selection_frame,
            text="История",
            command=controller.show_history_tab,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            selection_frame,
            text="Обзор",
            command=controller.show_dashboard_tab,
        ).pack(side="left", padx=(8, 0))

        open_frame = ttk.LabelFrame(body, text="Быстрые действия", padding=10)
        open_frame.grid(row=9, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(
            open_frame,
            text="Открыть исходные данные",
            command=lambda: controller.open_current_artifact("base_json_path"),
        ).pack(side="left")
        ttk.Button(
            open_frame,
            text="Открыть диапазоны",
            command=lambda: controller.open_current_artifact("ranges_json_path"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            open_frame,
            text="Открыть набор испытаний",
            command=lambda: controller.open_current_artifact("suite_json_path"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            open_frame,
            text="Открыть рабочую папку",
            command=lambda: controller.open_current_artifact("workspace_dir"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            open_frame,
            text="Открыть базовый прогон",
            command=controller.open_baseline_center,
        ).pack(side="left", padx=(8, 0))

    def set_objectives_text(self, text: str) -> None:
        replace_text(self.objective_text, text)

    def objectives_text(self) -> str:
        return self.objective_text.get("1.0", "end").strip()

    def _on_problem_hash_mode_selected(self, _event: object | None = None) -> None:
        selected = self.problem_hash_mode_var.get()
        by_label = {label: key for key, label in PROBLEM_HASH_MODE_LABELS.items()}
        self.controller.var("settings_opt_problem_hash_mode").set(by_label.get(selected, "stable"))

    def render(
        self,
        *,
        snapshot: object,
        stage_policy_text: str,
        drift_text: str,
    ) -> None:
        self.problem_hash_mode_var.set(_problem_hash_mode_label(getattr(snapshot, "problem_hash_mode", "")))
        stage_counts = _stage_count_text(dict(getattr(snapshot, "enabled_stage_counts", {}) or {}))
        sample_params = _operator_list_text(getattr(snapshot, "sample_search_params", ()))
        baseline_source = (
            getattr(snapshot, "baseline_source_label", "")
            or getattr(snapshot, "baseline_source_kind", "")
            or "default_base.json only"
        )
        self.parameters_panel.set_rows(tuple(getattr(snapshot, "search_param_rows", ()) or ()))
        self.summary_panel.set_rows(
            [
                ("Рабочая папка", str(getattr(snapshot, "workspace_dir", ""))),
                ("Цели оптимизации", _operator_list_text(getattr(snapshot, "objective_keys", ()))),
                (
                    "Жёсткая проверка",
                    format_hard_gate(
                        getattr(snapshot, "penalty_key", ""),
                        getattr(snapshot, "penalty_tol", None),
                    )
                    or "—",
                ),
                ("Контроль задачи", str(getattr(snapshot, "problem_hash", "")) or "—"),
                ("Режим контроля", _problem_hash_mode_label(getattr(snapshot, "problem_hash_mode", ""))),
                (
                    "Источник опорного прогона",
                    _operator_token_text(baseline_source),
                ),
                (
                    "Активный опорный прогон",
                    (
                        f"{_operator_token_text(getattr(snapshot, 'active_baseline_state', ''))} / "
                        f"{'доступен' if bool(getattr(snapshot, 'optimizer_baseline_can_consume', False)) else 'заблокирован'}"
                    ),
                ),
                (
                    "Контроль активного прогона",
                    str(getattr(snapshot, "active_baseline_hash", "") or "—")[:12],
                ),
                (
                    "Автообновление опорного прогона",
                    "включено" if bool(self.controller.var("opt_autoupdate_baseline").get()) else "выключено",
                ),
                (
                    "Параметры оптимизации",
                    f"Всего исходных параметров {int(getattr(snapshot, 'base_param_count', 0) or 0)}. "
                    f"Выбрано для оптимизации {int(getattr(snapshot, 'search_param_count', 0) or 0)}. "
                    f"Скрыто расчётных настроек {int(getattr(snapshot, 'removed_runtime_knob_count', 0) or 0)}. "
                    f"Расширенных диапазонов поиска {int(getattr(snapshot, 'widened_range_count', 0) or 0)}.",
                ),
                (
                    "Покрытие набора",
                    f"В наборе {int(getattr(snapshot, 'suite_row_count', 0) or 0)} строк. "
                    f"Включено {int(getattr(snapshot, 'enabled_suite_total', 0) or 0)}. "
                    f"По стадиям: {stage_counts}.",
                ),
                ("Что будет изменяться", sample_params),
            ]
        )
        self.paths_panel.set_rows(
            [
                ("Модель", str(getattr(snapshot, "model_path", ""))),
                ("Исполнитель", str(getattr(snapshot, "worker_path", ""))),
                ("Исходные данные", str(getattr(snapshot, "base_json_path", ""))),
                ("Диапазоны поиска оптимизации", str(getattr(snapshot, "ranges_json_path", ""))),
                ("Набор испытаний", str(getattr(snapshot, "suite_json_path", ""))),
                (
                    "Настройка стадий",
                    str(getattr(snapshot, "stage_tuner_json_path", "") or "не подготовлено"),
                ),
                (
                    "Опорный прогон для области",
                    str(getattr(snapshot, "baseline_path", "") or "не найден"),
                ),
                (
                    "Паспорт активного опорного прогона",
                    str(getattr(snapshot, "active_baseline_contract_path", "") or "не найден"),
                ),
            ]
        )
        self.stage_policy_panel.set_text(stage_policy_text)
        self.drift_panel.set_text(drift_text)


__all__ = ["DesktopOptimizerContractTab"]
