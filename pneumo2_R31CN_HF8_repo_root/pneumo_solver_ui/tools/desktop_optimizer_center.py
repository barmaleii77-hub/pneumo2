from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from pneumo_solver_ui.desktop_optimizer_model import launch_profile_key_for_label
from pneumo_solver_ui.desktop_optimizer_runtime import DesktopOptimizerRuntime
from pneumo_solver_ui.desktop_optimizer_tabs import (
    DesktopOptimizerContractTab,
    DesktopOptimizerDashboardTab,
    DesktopOptimizerFinishedTab,
    DesktopOptimizerHandoffTab,
    DesktopOptimizerHistoryTab,
    DesktopOptimizerPackagingTab,
    DesktopOptimizerRuntimeTab,
)
from pneumo_solver_ui.optimization_contract_summary_ui import format_hard_gate

try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


BOOLEAN_KEYS = {
    "adaptive_influence_eps",
    "opt_finished_done_only",
    "opt_finished_truth_ready_only",
    "opt_finished_verification_only",
    "opt_autoupdate_baseline",
    "opt_botorch_normalize_objectives",
    "opt_hv_log",
    "opt_packaging_done_only",
    "opt_packaging_truth_ready_only",
    "opt_packaging_verification_only",
    "opt_packaging_zero_interference_only",
    "opt_resume",
    "opt_stage_resume",
    "opt_use_staged",
    "ray_local_dashboard",
    "sort_tests_by_cost",
}


DRIFT_LABELS = {
    "objective stack": "состав целей",
    "penalty key": "ключ ограничения",
    "penalty tol": "допуск ограничения",
}


OPERATOR_TOKEN_LABELS = {
    "staged": "поэтапный запуск",
    "distributed": "распределённая координация",
    "coordinator": "координатор",
    "StageRunner": "поэтапный исполнитель",
    "Dask": "Dask-исполнитель",
    "Ray": "Ray-исполнитель",
    "dask": "Dask-исполнитель",
    "ray": "Ray-исполнитель",
    "default_base.json only": "базовый файл по умолчанию",
    "active_baseline_contract.json": "активный опорный прогон",
    "active_contract": "активный опорный прогон",
    "ui_opt_minutes": "бюджет поэтапного запуска",
    "ui_jobs": "число задач",
    "ui_seed_candidates": "стартовые кандидаты",
    "ui_seed_conditions": "стартовые условия",
    "opt_budget": "бюджет координатора",
    "opt_max_inflight": "одновременные задачи",
    "settings_opt_problem_hash_mode": "режим контроля задачи",
    "stage0_relevance": "предварительный отбор",
    "stage1_long": "длинная проверка",
    "stage2_final": "финальная проверка",
    "0": "предварительный отбор",
    "1": "длинная проверка",
    "2": "финальная проверка",
    "pareto": "Парето",
    "full_ring": "полное кольцо",
    "true": "да",
    "false": "нет",
    "True": "да",
    "False": "нет",
    "yes": "да",
    "no": "нет",
    "LIVE": "выполняется",
}


def _short_hash(value: Any, *, width: int = 12) -> str:
    text = str(value or "").strip()
    return text[:width] if text else "—"


def _operator_state(value: Any, *, fallback: str = "нет данных") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    labels = {
        "MISSING": "не найден",
        "READY": "готов",
        "WARN": "требует внимания",
        "BLOCKED": "заблокирован",
        "INVALID": "ошибка",
        "DONE": "завершён",
        "done": "завершён",
        "ready": "готов",
        "missing": "не найден",
        "current": "актуален",
        "stale": "устарел",
        "ok": "готов",
        "warn": "требует внимания",
        "error": "ошибка",
        "failed": "ошибка",
        "running": "выполняется",
        "LIVE": "выполняется",
    }
    return labels.get(text, labels.get(text.upper(), labels.get(text.lower(), text)))


def _problem_hash_mode_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    labels = {
        "stable": "обычный контроль",
        "legacy": "совместимый контроль",
    }
    return labels.get(text, text or "режим не выбран")


def _operator_compat_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "нет данных"
    labels = {
        "same": "совпадает",
        "different": "отличается",
        "unknown": "нет данных",
    }
    return labels.get(text, text)


def _operator_token_text(value: Any) -> str:
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


def _operator_issue_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text == "run incomplete":
        return "запуск ещё не завершён"
    if text == "missing results " + "artifact":
        return "нет файла результатов"
    if text.startswith("run status is "):
        return "состояние запуска: " + _operator_state(text.removeprefix("run status is "), fallback="нет данных")
    if text.startswith("run "):
        return "состояние запуска: " + _operator_state(text.removeprefix("run "), fallback="нет данных")
    return text


def _operator_list_text(values: Any) -> str:
    if isinstance(values, str):
        items = (values,)
    else:
        items = tuple(values or ())
    return ", ".join(_operator_token_text(item) for item in items) or "—"


def _operator_preset_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"
    return (
        text.replace("ray", "Ray")
        .replace("dask", "Dask")
        .replace("botorch", "BoTorch")
        .replace("/q", "/группа ")
    )


class DesktopOptimizerCenter:
    def __init__(self, host: tk.Misc | None = None, *, hosted: bool = False) -> None:
        self._owns_root = host is None
        self._hosted = bool(hosted or not self._owns_root)
        self.root = host if host is not None else tk.Tk()
        if self._owns_root:
            self.root.title(f"Автоматизированная оптимизация ({RELEASE})")
            self.root.geometry("1480x980")
            self.root.minsize(1220, 820)
        self.repo_root = Path(__file__).resolve().parents[2]
        self.runtime = DesktopOptimizerRuntime(
            ui_root=self.repo_root / "pneumo_solver_ui",
            python_executable=sys.executable,
            cpu_count=int(os.cpu_count() or 4),
            platform_name=sys.platform,
        )
        self.status_var = tk.StringVar(
            value="Готово. Автоматизированная оптимизация доступна в отдельном инженерном окне."
        )
        self.mode_summary_var = tk.StringVar(
            value="Порядок работы: опорный прогон, оптимизация, анализ. Режим и опорный прогон будут показаны после первого обновления."
        )
        self.workspace_summary_var = tk.StringVar(
            value="Сводка запуска, история прогонов и готовые выпуски будут показаны после первого обновления."
        )
        self.baseline_summary_var = tk.StringVar(
            value="Опорный прогон. Источник и политика автообновления будут показаны после первого обновления."
        )
        self.contract_summary_var = tk.StringVar(
            value="Настройки запуска. Цели и жёсткое ограничение будут показаны после первого обновления."
        )
        self.launch_button_text_var = tk.StringVar(value="Запустить оптимизацию")
        self._poll_after_id: str | None = None
        self._host_closed = False
        self._selected_run_dir = ""
        self._contract_snapshot: Any = None
        self._tk_vars: dict[str, tk.Variable] = {}
        self._build_vars()
        self._build_ui()
        self._load_state_into_widgets()
        self.refresh_all()
        self._schedule_poll()

    def var(self, key: str) -> tk.Variable:
        return self._tk_vars[key]

    def _build_vars(self) -> None:
        for key, value in self.runtime.session_state.items():
            if key in BOOLEAN_KEYS:
                self._tk_vars[key] = tk.BooleanVar(master=self.root, value=bool(value))
            else:
                self._tk_vars[key] = tk.StringVar(
                    master=self.root,
                    value="" if value is None else str(value),
                )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 8))
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(
            title_box,
            text="Опорный прогон и оптимизация",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            textvariable=self.mode_summary_var,
            justify="left",
            wraplength=760,
        ).pack(anchor="w", pady=(2, 0))

        header_actions = ttk.Frame(header)
        header_actions.pack(side="right", anchor="ne")
        ttk.Button(
            header_actions,
            text="Порядок работы",
            command=self.show_dashboard_tab,
        ).pack(side="left")
        ttk.Button(
            header_actions,
            text="Вычисления",
            command=self.show_runtime_tab,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            header_actions,
            text="История",
            command=self.show_history_tab,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            header_actions,
            text="Обновить данные",
            command=self.refresh_all,
        ).pack(side="left", padx=(12, 0))

        workspace = ttk.Panedwindow(outer, orient="horizontal")
        workspace.pack(fill="both", expand=True)

        sidebar = ttk.Frame(workspace, padding=(0, 0, 8, 0))
        sidebar.columnconfigure(0, weight=1)
        context_frame = ttk.LabelFrame(sidebar, text="Сводка", padding=8)
        context_frame.pack(fill="x")
        ttk.Label(
            context_frame,
            textvariable=self.workspace_summary_var,
            justify="left",
            wraplength=300,
        ).pack(anchor="w")

        baseline_frame = ttk.LabelFrame(sidebar, text="Опорный прогон", padding=8)
        baseline_frame.pack(fill="x", pady=(8, 0))
        ttk.Label(
            baseline_frame,
            textvariable=self.baseline_summary_var,
            justify="left",
            wraplength=300,
        ).pack(anchor="w")

        contract_frame = ttk.LabelFrame(sidebar, text="Настройки запуска", padding=8)
        contract_frame.pack(fill="x", pady=(8, 0))
        ttk.Label(
            contract_frame,
            textvariable=self.contract_summary_var,
            justify="left",
            wraplength=300,
        ).pack(anchor="w")

        nav_frame = ttk.LabelFrame(sidebar, text="Переходы", padding=8)
        nav_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(nav_frame, text="Открыть базовый прогон", command=self.open_baseline_center).pack(fill="x")
        ttk.Button(nav_frame, text="Опорный прогон и настройки", command=self.show_contract_tab).pack(fill="x", pady=(6, 0))
        ttk.Button(nav_frame, text="Выполнение оптимизации", command=self.show_runtime_tab).pack(fill="x", pady=(6, 0))
        ttk.Button(nav_frame, text="История", command=self.show_history_tab).pack(fill="x", pady=(6, 0))
        ttk.Button(nav_frame, text="Готовые прогоны", command=self.show_finished_tab).pack(fill="x", pady=(6, 0))
        ttk.Button(nav_frame, text="Передача стадий", command=self.show_handoff_tab).pack(fill="x", pady=(6, 0))
        ttk.Button(nav_frame, text="Упаковка", command=self.show_packaging_tab).pack(fill="x", pady=(6, 0))

        self.notebook = ttk.Notebook(workspace)

        self.dashboard_tab = DesktopOptimizerDashboardTab(self.notebook, self)
        self.contract_tab = DesktopOptimizerContractTab(self.notebook, self)
        self.runtime_tab = DesktopOptimizerRuntimeTab(self.notebook, self)
        self.history_tab = DesktopOptimizerHistoryTab(self.notebook, self)
        self.finished_tab = DesktopOptimizerFinishedTab(self.notebook, self)
        self.handoff_tab = DesktopOptimizerHandoffTab(self.notebook, self)
        self.packaging_tab = DesktopOptimizerPackagingTab(self.notebook, self)
        self.notebook.add(self.dashboard_tab, text="Опорный прогон и запуск")
        self.notebook.add(self.contract_tab, text="Опорный прогон и настройки")
        self.notebook.add(self.runtime_tab, text="Выполнение")
        self.notebook.add(self.history_tab, text="История")
        self.notebook.add(self.finished_tab, text="Готовые прогоны")
        self.notebook.add(self.handoff_tab, text="Передача стадий")
        self.notebook.add(self.packaging_tab, text="Упаковка и выпуск")
        workspace.add(sidebar, weight=1)
        workspace.add(self.notebook, weight=5)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        ttk.Button(footer, text="Обновить всё", command=self.refresh_all).pack(side="right")
        ttk.Sizegrip(footer).pack(side="right", padx=(10, 0))

        if self._owns_root:
            self.root.protocol("WM_DELETE_WINDOW", self._request_close)

    def _load_state_into_widgets(self) -> None:
        for key, variable in self._tk_vars.items():
            if key not in self.runtime.session_state:
                continue
            value = self.runtime.session_state.get(key)
            if key in BOOLEAN_KEYS:
                variable.set(bool(value))
            else:
                variable.set("" if value is None else str(value))
        self.contract_tab.set_objectives_text(
            str(self.runtime.session_state.get("opt_objectives", "") or "")
        )

    def _collect_widget_state(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, variable in self._tk_vars.items():
            payload[key] = variable.get()
        payload["opt_objectives"] = self.contract_tab.objectives_text()
        payload["use_staged_opt"] = bool(payload.get("opt_use_staged", False))
        return payload

    def _sync_widget_state(self) -> None:
        self.runtime.update_state(self._collect_widget_state())

    def _open_path(self, path: Path | str | None) -> None:
        if path is None:
            return
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(str(target))
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
            return
        subprocess.Popen(["xdg-open", str(target)])

    def open_baseline_center(self) -> None:
        env = os.environ.copy()
        env["PNEUMO_GUI_SPEC_SHELL_OPEN_WORKSPACE"] = "baseline_run"
        try:
            subprocess.Popen(
                [sys.executable, "-m", "pneumo_solver_ui.tools.desktop_gui_spec_shell"],
                cwd=str(self.repo_root),
                env=env,
            )
        except Exception as exc:
            messagebox.showerror(
                "Базовый прогон",
                f"Не удалось открыть базовый прогон:\n{exc}",
            )
            return
        self.status_var.set("Открыт базовый прогон.")

    def open_current_artifact(self, attr_name: str) -> None:
        snapshot = self._contract_snapshot
        if snapshot is None:
            self.refresh_all()
            snapshot = self._contract_snapshot
        if snapshot is None:
            return
        try:
            self._open_path(getattr(snapshot, attr_name, None))
        except Exception as exc:
            messagebox.showerror(
                "Оптимизация",
                f"Не удалось открыть путь:\n{exc}",
            )

    def _format_stage_policy_blueprint_text(self, rows: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for row in rows:
            explore_pct = int(round(float(row.get("explore_frac", 0.0) or 0.0) * 100.0))
            line = (
                f"{row.get('stage_name')} - {row.get('role')}\n"
                f"  политика {row.get('policy_name')}; запрошено {row.get('requested_mode')}; "
                f"применено {row.get('effective_mode')}; лучших {int(row.get('top_k', 0) or 0)}; "
                f"разведка {explore_pct}%; бюджет разведки {int(row.get('explore_budget', 0) or 0)}; "
                f"бюджет уточнения {int(row.get('focus_budget', 0) or 0)}"
            )
            fallback_reason = str(row.get("fallback_reason") or "")
            if fallback_reason:
                line += f"\n  причина замены - {fallback_reason}"
            lines.append(line)
        return "\n\n".join(lines)

    def _select_tab(self, tab: ttk.Frame) -> None:
        self.notebook.select(tab)

    def show_dashboard_tab(self) -> None:
        self._select_tab(self.dashboard_tab)

    def show_contract_tab(self) -> None:
        self._select_tab(self.contract_tab)

    def show_runtime_tab(self) -> None:
        self._select_tab(self.runtime_tab)

    def show_history_tab(self) -> None:
        self._select_tab(self.history_tab)

    def show_finished_tab(self) -> None:
        self._select_tab(self.finished_tab)

    def show_handoff_tab(self) -> None:
        self._select_tab(self.handoff_tab)

    def show_packaging_tab(self) -> None:
        self._select_tab(self.packaging_tab)

    def _format_runtime_status_text(self, surface: dict[str, Any]) -> str:
        if not surface:
            return "Активная задача оптимизации сейчас не выполняется."
        job = surface.get("job")
        rc = surface.get("returncode")
        runtime_summary = dict(surface.get("runtime_summary") or {})
        lines = [
            f"Папка запуска - {getattr(job, 'run_dir', '')}",
            f"Контур запуска - {_operator_token_text(getattr(job, 'pipeline_mode', ''))}",
            f"Исполнитель - {_operator_token_text(getattr(job, 'backend', ''))}",
            f"Бюджет - {int(getattr(job, 'budget', 0) or 0)}",
        ]
        lines.append("Состояние - выполняется" if rc is None else f"Состояние - завершено, код {int(rc)}")
        if surface.get("soft_stop_requested"):
            lines.append("Мягкая остановка запрошена.")
        if runtime_summary:
            lines.append("")
            lines.extend(str(line) for line in surface.get("captions") or [])
        return "\n".join(lines)

    def _format_run_identity_text(self, identity: dict[str, Any] | None = None) -> str:
        payload = dict(identity or self.runtime.selected_run_identity_summary())
        state = _operator_state(payload.get("state"), fallback="не найден")
        lines = [
            f"Состояние - {state}",
            str(payload.get("banner") or "Сводка выбранного запуска недоступна."),
            (
                "Продолжение - "
                f"{'запрошено' if bool(payload.get('resume_requested')) else 'не запрошено'}. "
                f"Текущий контур - {_operator_token_text(payload.get('launch_pipeline'))}. "
                f"Выбранный контур - {_operator_token_text(payload.get('selected_pipeline'))}."
            ),
        ]
        if payload.get("selected_run_dir"):
            lines.extend(
                [
                    f"Запуск - {payload.get('selected_run_name') or '—'}",
                    f"Метка запуска - {payload.get('run_id') or '—'}",
                    f"Папка запуска - {payload.get('selected_run_dir')}",
                    (
                        "Контрольные метки - "
                        f"цели {_short_hash(payload.get('objective_contract_hash'))}; "
                        f"задача {_short_hash(payload.get('problem_hash'))}; "
                        f"опорный прогон {_short_hash(payload.get('active_baseline_hash'))}; "
                        f"набор {_short_hash(payload.get('suite_snapshot_hash'))}."
                    ),
                    (
                        "Паспорт выбранного запуска - "
                        f"{_short_hash(payload.get('selected_run_contract_hash'))}. "
                        f"Файл {'есть' if bool(payload.get('selected_run_contract_exists')) else 'не найден'}. "
                        f"Передача в анализ - {_operator_state(payload.get('analysis_handoff_ready_state'), fallback='нет данных')}."
                    ),
                ]
            )
        blockers = tuple(
            str(item) for item in tuple(payload.get("blocking_reasons") or ()) if str(item).strip()
        )
        warnings = tuple(
            str(item) for item in tuple(payload.get("warnings") or ()) if str(item).strip()
        )
        if blockers:
            lines.append(
                "Блокирующие причины - "
                + "; ".join(_operator_issue_text(item) for item in blockers)
            )
        if warnings:
            lines.append(
                "Примечания - "
                + "; ".join(_operator_issue_text(item) for item in warnings)
            )
        return "\n".join(lines)

    def _format_resume_target_text(self) -> str:
        payload = self.runtime.resume_target_summary()
        identity_text = self._format_run_identity_text()
        selected_run_dir = str(payload.get("selected_run_dir") or "")
        if not selected_run_dir:
            return (
                "Запуск из истории не выбран.\n"
                "Выберите поэтапный или координационный запуск во вкладке «История», чтобы продолжить его.\n\n"
                + identity_text
            )
        lines = [
            f"Выбранный прогон - {payload.get('selected_run_name') or '—'}",
            f"Контур выбранного прогона - {_operator_token_text(payload.get('selected_pipeline'))}",
            f"Путь к выбранному прогону - {selected_run_dir}",
            f"Контур текущего запуска - {_operator_token_text(payload.get('launch_pipeline'))}",
        ]
        if payload.get("selected_run_id"):
            lines.append(f"Метка координатора - {payload.get('selected_run_id')}")
        if bool(payload.get("stage_resume_enabled")):
            lines.append("Продолжение стадий включено.")
        else:
            lines.append("Продолжение стадий выключено.")
        if bool(payload.get("coord_resume_enabled")):
            lines.append(
                f"Продолжение координатора включено. Метка - {payload.get('coord_run_id') or 'автоматически'}."
            )
        else:
            lines.append("Продолжение координатора выключено.")
        lines.extend(["", "Сводка запуска и безопасное продолжение:", identity_text])
        return "\n".join(lines)

    def _format_dashboard_workspace_text(self) -> str:
        snapshot = self._contract_snapshot
        if snapshot is None:
            snapshot = self.runtime.contract_snapshot()
        objective_keys = _operator_list_text(getattr(snapshot, "objective_keys", ()))
        stage_counts = ", ".join(
            f"{_operator_token_text(key)} - {value}"
            for key, value in dict(getattr(snapshot, "enabled_stage_counts", {}) or {}).items()
        ) or "—"
        return "\n".join(
            [
                f"Рабочая папка - {getattr(snapshot, 'workspace_dir', '')}",
                f"Контроль задачи - {getattr(snapshot, 'problem_hash', '') or '—'}",
                f"Режим контроля - {_problem_hash_mode_text(getattr(snapshot, 'problem_hash_mode', ''))}",
                f"Цели оптимизации - {objective_keys}",
                (
                    "Пространство поиска - "
                    f"базовых параметров {int(getattr(snapshot, 'base_param_count', 0) or 0)}, "
                    f"проектных параметров {int(getattr(snapshot, 'search_param_count', 0) or 0)}, "
                    f"расширенных диапазонов {int(getattr(snapshot, 'widened_range_count', 0) or 0)}."
                ),
                (
                    "Покрытие сценариев - "
                    f"строк {int(getattr(snapshot, 'suite_row_count', 0) or 0)}, "
                    f"включено {int(getattr(snapshot, 'enabled_suite_total', 0) or 0)}, "
                    f"стадии {stage_counts}."
                ),
                (
                    "Источник опорного прогона - "
                    f"{_operator_token_text(getattr(snapshot, 'baseline_source_label', '') or getattr(snapshot, 'baseline_source_kind', ''))}"
                ),
            ]
        )

    def _format_dashboard_runtime_text(self, dashboard: dict[str, Any]) -> str:
        launch_profile = dict(dashboard.get("launch_profile") or {})
        resume_target = dict(dashboard.get("resume_target") or {})
        identity = dict(dashboard.get("selected_run_identity") or {})
        active_surface = dict(dashboard.get("active_surface") or {})
        lines = [
            f"Профиль запуска - {launch_profile.get('profile_label') or '—'}",
            (
                "Режим запуска - "
                f"{_operator_token_text(launch_profile.get('launch_pipeline'))} / "
                f"{_operator_token_text(launch_profile.get('backend'))}"
            ),
            (
                "Запуск для продолжения - "
                f"{resume_target.get('selected_run_name') or 'не выбран'} / "
                f"{_operator_token_text(resume_target.get('selected_pipeline'))}"
            ),
            (
                "Сводка запуска - "
                f"{_operator_state(identity.get('state'), fallback='не найден')}. "
                f"Цели {_short_hash(identity.get('objective_contract_hash'))}; "
                f"задача {_short_hash(identity.get('problem_hash'))}; "
                f"опорный прогон {_short_hash(identity.get('active_baseline_hash'))}."
            ),
        ]
        if not active_surface:
            lines.append("Активная задача не выполняется.")
            return "\n".join(lines)
        job = active_surface.get("job")
        lines.append(
            "Активная задача - "
            f"{_operator_token_text(getattr(job, 'pipeline_mode', ''))} / "
            f"{_operator_token_text(getattr(job, 'backend', ''))} @ {getattr(job, 'run_dir', '') or '—'}"
        )
        lines.extend(str(line) for line in active_surface.get("captions") or [])
        return "\n".join(lines)

    def _format_dashboard_finished_text(self, dashboard: dict[str, Any]) -> str:
        overview = dict(dashboard.get("finished_overview") or {})
        best = dict(dashboard.get("best_finished_row") or {})
        if int(overview.get("total_jobs", 0) or 0) <= 0:
            return "Завершённые прогоны пока не найдены."
        lines = [
            (
                "Прогоны - "
                f"всего {int(overview.get('total_jobs', 0) or 0)}, "
                f"готовы к проверке {int(overview.get('truth_ready_jobs', 0) or 0)}, "
                f"прошли проверку {int(overview.get('verification_pass_jobs', 0) or 0)}, "
                f"с рисками {int(overview.get('interference_jobs', 0) or 0)}."
            ),
            (
                "Строки результатов - "
                f"для выпуска {int(overview.get('rows_with_packaging_total', 0) or 0)}, "
                f"готовы к проверке {int(overview.get('truth_ready_rows_total', 0) or 0)}, "
                f"прошли проверку {int(overview.get('verification_rows_total', 0) or 0)}."
            ),
        ]
        if best:
            lines.append(
                "Лучший завершённый прогон - "
                f"{best.get('name') or '—'}. Готовность {_operator_state(best.get('ready_state'), fallback='нет данных')}. "
                f"Готовых строк {int(best.get('truth_ready_rows', 0) or 0)}. "
                f"Проверенных строк {int(best.get('verification_pass_rows', 0) or 0)}. "
                f"Строк с рисками {int(best.get('interference_rows', 0) or 0)}."
            )
        return "\n".join(lines)

    def _format_dashboard_handoff_text(self, dashboard: dict[str, Any]) -> str:
        overview = dict(dashboard.get("handoff_overview") or {})
        best = dict(dashboard.get("best_handoff_row") or {})
        if int(overview.get("total_candidates", 0) or 0) <= 0:
            return "Кандидаты для передачи пока не найдены."
        lines = [
            (
                "Кандидаты - "
                f"всего {int(overview.get('total_candidates', 0) or 0)}, "
                f"завершены {int(overview.get('done_candidates', 0) or 0)}, "
                f"полное кольцо {int(overview.get('full_ring_candidates', 0) or 0)}, "
                f"в работе {int(overview.get('live_candidates', 0) or 0)}."
            ),
            f"Стартовых вариантов - {int(overview.get('seed_total', 0) or 0)}.",
        ]
        if best:
            lines.append(
                "Лучший кандидат на передачу - "
                f"{best.get('run') or '—'}. Профиль {_operator_preset_text(best.get('preset'))}. "
                f"Оценка {float(best.get('quality_score', 0.0) or 0.0):.1f}. "
                f"Бюджет {int(best.get('budget', 0) or 0)}. "
                f"Стартовых вариантов {int(best.get('seeds', 0) or 0)}."
            )
        return "\n".join(lines)

    def _format_dashboard_packaging_text(self, dashboard: dict[str, Any]) -> str:
        overview = dict(dashboard.get("packaging_overview") or {})
        best = dict(dashboard.get("best_packaging_row") or {})
        if int(overview.get("total_runs", 0) or 0) <= 0:
            return "Данные для выпуска по завершённым прогонам пока недоступны."
        lines = [
            (
                "Прогоны для выпуска - "
                f"всего {int(overview.get('total_runs', 0) or 0)}, "
                f"готовы к проверке {int(overview.get('truth_ready_runs', 0) or 0)}, "
                f"прошли проверку {int(overview.get('verification_runs', 0) or 0)}, "
                f"без рисков {int(overview.get('zero_interference_runs', 0) or 0)}."
            ),
            (
                "Строки для выпуска - "
                f"всего {int(overview.get('packaging_rows_total', 0) or 0)}, "
                f"готовы к проверке {int(overview.get('truth_ready_rows_total', 0) or 0)}, "
                f"прошли проверку {int(overview.get('verification_rows_total', 0) or 0)}."
            ),
        ]
        if best:
            lines.append(
                "Лучший прогон для выпуска - "
                f"{best.get('name') or '—'}. Готовность {_operator_state(best.get('ready_state'), fallback='нет данных')}. "
                f"Готовых строк {int(best.get('truth_ready_rows', 0) or 0)}. "
                f"Проверенных строк {int(best.get('verification_pass_rows', 0) or 0)}. "
                f"Строк с рисками {int(best.get('interference_rows', 0) or 0)}."
            )
        return "\n".join(lines)

    def _format_compact_mode_summary(self) -> str:
        payload = self.runtime.launch_profile_summary()
        profile = str(payload.get("profile_label") or "Автоматический порядок работы")
        pipeline = _operator_token_text(payload.get("launch_pipeline"))
        backend = _operator_token_text(payload.get("backend"))
        drift_keys = tuple(str(key) for key in payload.get("drift_keys") or ())
        summary = (
            "Порядок работы: опорный прогон, оптимизация, анализ. "
            f"Режим - {profile}. Контур - {pipeline}. Исполнитель - {backend}."
        )
        if drift_keys:
            summary += " Изменено вручную - " + _operator_list_text(drift_keys[:3])
            if len(drift_keys) > 3:
                summary += "..."
        return summary

    def _format_compact_workspace_summary(self) -> str:
        snapshot = self._contract_snapshot
        if snapshot is None:
            snapshot = self.runtime.contract_snapshot()
        return "\n".join(
            [
                f"Контроль задачи - {getattr(snapshot, 'problem_hash', '') or '—'}",
                (
                    "Сценарии - "
                    f"всего {int(getattr(snapshot, 'suite_row_count', 0) or 0)}, "
                    f"активно {int(getattr(snapshot, 'enabled_suite_total', 0) or 0)}"
                ),
                (
                    "Параметры поиска - "
                    f"{int(getattr(snapshot, 'search_param_count', 0) or 0)}"
                ),
                "Рабочая зона: опорный прогон, выполнение оптимизации, история, передача в анализ и выпуск открываются справа во вкладках.",
            ]
        )

    def _active_mode_key(self) -> str:
        if bool(self.var("opt_use_staged").get()):
            return "staged"
        return "distributed"

    def profile_labels_for_active_mode(self) -> tuple[str, ...]:
        mode_key = self._active_mode_key()
        labels: list[str] = []
        for option_key, option_label, _desc in self.runtime.launch_profile_options():
            if mode_key == "staged" and option_key.startswith("stage_"):
                labels.append(option_label)
            if mode_key == "distributed" and option_key.startswith("coord_"):
                labels.append(option_label)
        return tuple(labels)

    def set_active_mode(self, mode_key: str) -> None:
        is_staged = str(mode_key or "").strip().lower() != "distributed"
        self.var("opt_use_staged").set(is_staged)
        self.runtime.session_state["use_staged_opt"] = bool(is_staged)
        current_profile_key = str(self.runtime.session_state.get("opt_launch_profile", "") or "")
        if is_staged and not current_profile_key.startswith("stage_"):
            self.runtime.apply_launch_profile("stage_triage")
            self._load_state_into_widgets()
        if not is_staged and not current_profile_key.startswith("coord_"):
            self.runtime.apply_launch_profile("coord_dask_explore")
            self._load_state_into_widgets()
        self.refresh_all()

    def _primary_launch_button_text(self) -> str:
        if self._active_mode_key() == "staged":
            return "Запустить поэтапный запуск"
        return "Запустить распределённую координацию"

    def _format_baseline_summary_text(self) -> str:
        snapshot = self._contract_snapshot
        if snapshot is None:
            snapshot = self.runtime.contract_snapshot()
        auto_update = bool(self.runtime.session_state.get("opt_autoupdate_baseline", False))
        source_label = _operator_token_text(
            getattr(snapshot, "baseline_source_label", "")
            or getattr(snapshot, "baseline_source_kind", "")
        )
        baseline_path = str(getattr(snapshot, "baseline_path", "") or "не найден")
        ho006_state = str(getattr(snapshot, "active_baseline_state", "") or "missing")
        ho006_hash = str(getattr(snapshot, "active_baseline_hash", "") or "")
        ho006_can_consume = bool(getattr(snapshot, "optimizer_baseline_can_consume", False))
        return "\n".join(
            [
                f"Опорный прогон - {source_label}",
                f"Состояние активного прогона - {_operator_state(ho006_state)} ({'актуален' if ho006_can_consume else 'заблокирован'})",
                f"Контроль активного прогона - {ho006_hash[:12] if ho006_hash else '—'}",
                f"Путь - {baseline_path}",
                f"Автообновление опорного прогона {'включено' if auto_update else 'выключено'}.",
            ]
        )

    def _format_runtime_contract_summary_text(self) -> str:
        snapshot = self._contract_snapshot
        if snapshot is None:
            snapshot = self.runtime.contract_snapshot()
        identity = self.runtime.selected_run_identity_summary()
        objective_stack = _operator_list_text(getattr(snapshot, "objective_keys", ()))
        hard_gate = format_hard_gate(
            getattr(snapshot, "penalty_key", ""),
            getattr(snapshot, "penalty_tol", None),
        ) or "—"
        if self._active_mode_key() == "staged":
            mode_label = "Рекомендуемый: Поэтапный запуск"
        else:
            mode_label = "Расширенный: Распределённая координация"
        return "\n".join(
            [
                f"Настройки запуска - {mode_label}",
                f"Цели оптимизации - {objective_stack}",
                f"Жёсткий критерий - {hard_gate}",
                (
                    "Сводка запуска - "
                    f"{_operator_state(identity.get('state'), fallback='не найден')}. "
                    f"Цели {_short_hash(identity.get('objective_contract_hash'))}; "
                    f"задача {_short_hash(identity.get('problem_hash'))}; "
                    f"продолжение {'запрошено' if bool(identity.get('resume_requested')) else 'выключено'}."
                ),
            ]
        )

    def _format_dashboard_pointer_text(self, dashboard: dict[str, Any]) -> str:
        pointer = dict(dashboard.get("latest_pointer") or {})
        if not bool(pointer.get("exists")):
            return (
                "Прогон для анализа ещё не выбран.\n"
                "Выберите прогон в истории, готовых прогонах, выпуске или передаче. "
                "Паспорт выбранного запуска будет создан автоматически."
            )
        lines = [
            f"Текущий прогон для анализа - {pointer.get('pointer_path') or '—'}",
            (
                "Выбранный прогон - "
                f"{pointer.get('run_name') or '—'}. "
                f"Контур {_operator_token_text(pointer.get('pipeline_mode'))} / {_operator_token_text(pointer.get('backend'))}. "
                f"Состояние {_operator_state(pointer.get('status_label') or pointer.get('status'), fallback='нет данных')}."
            ),
            (
                "Сведения о выборе - "
                f"источник {pointer.get('selected_from') or '—'}, "
                f"обновлён {pointer.get('updated_at') or '—'}."
            ),
            (
                "Строки результата - "
                f"всего {int(pointer.get('rows', 0) or 0)}, "
                f"завершено {int(pointer.get('done_count', 0) or 0)}, "
                f"ошибок {int(pointer.get('error_count', 0) or 0)}."
            ),
        ]
        if bool(pointer.get("selected_matches_pointer")):
            lines.append("Передача в анализ - выбранный прогон уже используется.")
        elif self._selected_run_dir:
            lines.append("Передача в анализ - сейчас используется другой прогон.")
        if not bool(pointer.get("pointer_in_history")):
            lines.append("История - текущий прогон анализа не найден в списке.")
        elif pointer.get("result_path"):
            lines.append(f"Результаты - {pointer.get('result_path')}")
        return "\n".join(lines)

    def _format_selected_run_next_step_text(self, payload: dict[str, Any]) -> str:
        rows = tuple(payload.get("rows") or ())
        if not rows:
            return "Рекомендация по выбранному прогону пока недоступна."
        lines = [
            f"Сводка - {payload.get('headline') or '—'}",
            f"Следующее действие - {payload.get('next_action') or '—'}",
            "",
        ]
        for row in rows:
            status = _operator_state(row.get("status"), fallback="сведения")
            lines.append(
                f"{status}. {row.get('title') or 'шаг'} -> {row.get('action') or '—'}"
            )
            lines.append(str(row.get("summary") or ""))
            lines.append("")
        return "\n".join(lines).strip()

    def _format_dashboard_selection_text(self) -> str:
        if not self._selected_run_dir:
            return "Прогон пока не выбран. Используйте историю, готовые прогоны, передачу или выпуск."
        details = self.runtime.selected_run_details(self._selected_run_dir)
        if details is None:
            return f"Выбранный запуск: {self._selected_run_dir}\nЗапуск уже недоступен в истории рабочей области."
        summary = getattr(details, "summary")
        drift = self.runtime.contract_drift_summary(summary)
        identity = self.runtime.selected_run_identity_summary(self._selected_run_dir)
        packaging_row = self.runtime.selected_packaging_row(self._selected_run_dir)
        handoff_row = self.runtime.selected_handoff_row(self._selected_run_dir)
        latest_pointer = self.runtime.latest_pointer_summary()
        lines = [
            f"Выбранный запуск - {summary.run_dir}",
            f"Состояние - {_operator_state(summary.status_label or summary.status, fallback='нет данных')}",
            f"Контур и исполнитель - {_operator_token_text(summary.pipeline_mode)} / {_operator_token_text(summary.backend)}",
            f"Сводка запуска - {_operator_state(identity.get('state'), fallback='не найден')}. {identity.get('banner') or '—'}",
            (
                "Контрольные метки - "
                f"метка {identity.get('run_id') or '—'}; "
                f"цели {_short_hash(identity.get('objective_contract_hash'))}; "
                f"задача {_short_hash(identity.get('problem_hash'))}; "
                f"опорный прогон {_short_hash(identity.get('active_baseline_hash'))}."
            ),
            f"Цели - {_operator_list_text(summary.objective_keys)}",
            f"Результаты - {summary.result_path or 'не найдены'}",
        ]
        if bool(latest_pointer.get("selected_matches_pointer")):
            lines.append("Передача в анализ - выбранный прогон уже закреплён.")
        elif bool(latest_pointer.get("exists")):
            lines.append(
                "Передача в анализ - закреплён "
                f"{latest_pointer.get('run_name') or '—'}"
            )
        diff_bits = tuple(drift.get("diff_bits") or ())
        scope_payload = dict(drift.get("scope_payload") or {})
        if diff_bits:
            lines.append(
                "Расхождение настроек - " + ", ".join(
                    DRIFT_LABELS.get(str(bit), str(bit)) for bit in diff_bits
                )
            )
        else:
            lines.append("Расхождений настроек нет.")
        if str(scope_payload.get("compatibility") or ""):
            lines.append(
                "Совместимость области задачи - "
                + _operator_compat_text(scope_payload.get("compatibility"))
            )
        if packaging_row is not None:
            lines.append(
                "Состояние выпуска - "
                f"{_operator_state(packaging_row.get('ready_state'), fallback='нет данных')}. "
                f"Готовых строк {int(packaging_row.get('truth_ready_rows', 0) or 0)}. "
                f"Проверенных строк {int(packaging_row.get('verification_pass_rows', 0) or 0)}. "
                f"Строк с рисками {int(packaging_row.get('interference_rows', 0) or 0)}."
            )
        if handoff_row is not None:
            lines.append(
                "Состояние передачи - "
                f"профиль {_operator_preset_text(handoff_row.get('preset'))}. "
                f"Оценка {float(handoff_row.get('quality_score', 0.0) or 0.0):.1f}. "
                f"Бюджет {int(handoff_row.get('budget', 0) or 0)}. "
                f"Стартовых вариантов {int(handoff_row.get('seeds', 0) or 0)}."
            )
        return "\n".join(lines)

    def _format_selected_contract_drift_text(self) -> str:
        if not self._selected_run_dir:
            return (
                "Исторический прогон не выбран.\n"
                "Выберите прогон во вкладке истории, готовых прогонов, передачи или выпуска, "
                "чтобы сравнить его настройки с текущим запуском."
            )
        details = self.runtime.selected_run_details(self._selected_run_dir)
        if details is None:
            return "Выбранный прогон больше не найден в истории рабочей папки."
        summary = getattr(details, "summary")
        drift = self.runtime.contract_drift_summary(summary)
        identity = self.runtime.selected_run_identity_summary(self._selected_run_dir)
        diff_bits = tuple(str(bit) for bit in (drift.get("diff_bits") or ()) if str(bit).strip())
        scope_payload = dict(drift.get("scope_payload") or {})
        baseline_compatibility = str(drift.get("baseline_compatibility") or "")

        def _compat_text(value: str) -> str:
            return _operator_compat_text(value)

        lines = [
            f"Состояние запуска - {_operator_state(identity.get('state'), fallback='не найден')}",
            f"Пояснение - {identity.get('banner') or '—'}",
            (
                "Контрольные метки - "
                f"метка {identity.get('run_id') or '—'}; "
                f"цели {_short_hash(identity.get('objective_contract_hash'))}; "
                f"задача {_short_hash(identity.get('problem_hash'))}; "
                f"опорный прогон {_short_hash(identity.get('active_baseline_hash'))}; "
                f"паспорт выбранного запуска {_short_hash(identity.get('selected_run_contract_hash'))}."
            ),
            "",
            f"Выбранный запуск - {summary.run_dir}",
            f"Контур и состояние - {_operator_token_text(summary.pipeline_mode)} / {_operator_state(summary.status_label, fallback='нет данных')}",
            (
                "Выбранный запуск - "
                f"цели {_operator_list_text(drift.get('selected_objective_keys'))}; "
                f"ограничение {drift.get('selected_penalty_key') or '—'}; "
                f"допуск {drift.get('selected_penalty_tol') if drift.get('selected_penalty_tol') is not None else '—'}."
            ),
            (
                "Текущий запуск - "
                f"цели {_operator_list_text(drift.get('current_objective_keys'))}; "
                f"ограничение {drift.get('current_penalty_key') or '—'}; "
                f"допуск {drift.get('current_penalty_tol') if drift.get('current_penalty_tol') is not None else '—'}."
            ),
        ]
        if diff_bits:
            lines.append(
                "Расхождение целей и ограничения - "
                + ", ".join(DRIFT_LABELS.get(bit, bit) for bit in diff_bits)
            )
        else:
            lines.append("Расхождений целей и ограничения нет.")
        lines.append(
            "Область задачи - "
            f"выбранный прогон {drift.get('selected_problem_hash') or '—'}; "
            f"текущий запуск {drift.get('current_problem_hash') or '—'}; "
            f"совместимость {_compat_text(scope_payload.get('compatibility', ''))}."
        )
        lines.append(
            "Режим контроля - "
            f"выбранный прогон {_problem_hash_mode_text(drift.get('selected_problem_hash_mode'))}; "
            f"текущий запуск {_problem_hash_mode_text(drift.get('current_problem_hash_mode'))}; "
            f"совместимость {_compat_text(scope_payload.get('mode_compatibility', ''))}."
        )
        lines.append(
            "Источник опорного прогона - "
            f"выбранный прогон {_operator_token_text(drift.get('selected_baseline_label') or drift.get('selected_baseline_path'))}; "
            f"текущий запуск {_operator_token_text(drift.get('current_baseline_label') or drift.get('current_baseline_path'))}; "
            f"совместимость {_compat_text(baseline_compatibility)}."
        )
        lines.append("")
        if str(scope_payload.get("compatibility") or "") == "different" or str(
            scope_payload.get("mode_compatibility") or ""
        ) == "different":
            lines.append(
                "Область отличается от текущего запуска. "
                "Продолжение и опорный прогон будут рассматриваться как другая задача оптимизации."
            )
        elif diff_bits:
            lines.append(
                "Область совпадает, но цели или ограничение отличаются. "
                "Примените настройки выбранного запуска, если нужен честный повтор."
            )
        else:
            lines.append(
                "Выбранный прогон согласован с текущими настройками и областью задачи."
            )
        return "\n".join(lines)

    def _format_launch_profile_text(self) -> str:
        summary = self.runtime.launch_profile_summary()
        lines = [
            f"Профиль - {summary.get('profile_label') or '—'}",
            (
                "Контур и исполнитель - "
                f"{_operator_token_text(summary.get('launch_pipeline'))} / "
                f"{_operator_token_text(summary.get('backend'))}"
            ),
            str(summary.get("description") or "Профиль задаёт стартовые настройки выполнения."),
        ]
        if str(summary.get("launch_pipeline") or "") == "staged":
            lines.append(
                "Поэтапный запуск - "
                f"минут {float(summary.get('stage_minutes', 0.0) or 0.0):.1f}, "
                f"задач {int(summary.get('stage_jobs', 0) or 0)}, "
                f"кандидатов {int(summary.get('seed_candidates', 0) or 0)}, "
                f"условий {int(summary.get('seed_conditions', 0) or 0)}, "
                f"тёплый старт {summary.get('warmstart_mode') or '—'}."
            )
            lines.append(
                "Дополнительные флаги - "
                f"автопорог {'включён' if bool(summary.get('adaptive_influence_eps')) else 'выключен'}, "
                f"продолжение стадий {'включено' if bool(summary.get('resume_stage')) else 'выключено'}."
            )
        else:
            lines.append(
                "Координатор - "
                f"бюджет {int(summary.get('budget', 0) or 0)}, "
                f"одновременно задач {int(summary.get('max_inflight', 0) or 0)}, "
                f"группа кандидатов {int(summary.get('q', 0) or 0)}, "
                f"выгрузка каждые {int(summary.get('export_every', 0) or 0)}."
            )
            lines.append(
                "Параметры кластера - "
                f"Dask {int(summary.get('dask_workers', 0) or 0)} x "
                f"{int(summary.get('dask_threads_per_worker', 0) or 0)} потоков, "
                f"Ray исполнителей {int(summary.get('ray_num_evaluators', 0) or 0)}, "
                f"генераторов Ray {int(summary.get('ray_num_proposers', 0) or 0)}."
            )
            lines.append(
                "Продолжение координатора "
                f"{'включено' if bool(summary.get('resume_coord')) else 'выключено'}."
            )
        drift_keys = tuple(summary.get("drift_keys") or ())
        if drift_keys:
            lines.append("")
            lines.append("Изменено вручную после применения профиля:")
            lines.append(_operator_list_text(drift_keys))
        else:
            lines.append("")
            lines.append("Текущие настройки совпадают с выбранным профилем.")
        return "\n".join(lines)

    def _format_launch_readiness_text(self, readiness: dict[str, Any]) -> str:
        rows = tuple(readiness.get("rows") or ())
        if not rows:
            return "Сводка готовности к запуску пока недоступна."
        lines = [
            f"Сводка - {readiness.get('headline') or '—'}",
            (
                "Итоги проверки - "
                f"требуют внимания {int(readiness.get('warn_count', 0) or 0)}, "
                f"информационных {int(readiness.get('info_count', 0) or 0)}, "
                f"готовых {int(readiness.get('ok_count', 0) or 0)}."
            ),
            f"Следующий рекомендуемый шаг - {readiness.get('next_action') or 'Выполнение'}",
            "",
        ]
        for row in rows:
            status = _operator_state(row.get("status"), fallback="сведения")
            lines.append(
                f"{status}. {row.get('title') or 'проверка'} -> {row.get('action') or 'Выполнение'}"
            )
            lines.append(str(row.get("summary") or ""))
            lines.append("")
        return "\n".join(lines).strip()

    def _format_stage_runtime_text(self, rows: tuple[dict[str, Any], ...]) -> str:
        if not rows:
            return "Политика стадий пока недоступна."
        lines: list[str] = []
        for row in rows:
            if not bool(row.get("available")):
                lines.append(f"{row.get('stage_name')}: нет данных о выполнении.")
                continue
            seed_count = int(row.get("seed_count", 0) or 0)
            target = int(row.get("target_seed_count", 0) or 0)
            lines.append(
                f"{row.get('stage_name')}: {row.get('summary_line') or row.get('policy_name')}\n"
                f"  стартовые варианты {seed_count}/{target}; режим {_operator_token_text(row.get('effective_mode'))}; "
                f"заполнение {row.get('underfill_message') or 'готово'}"
            )
        return "\n\n".join(lines)

    def _history_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for summary in self.runtime.history_summaries():
            rows.append(
                {
                    "run_dir": str(summary.run_dir),
                    "name": str(summary.run_dir.name),
                    "status": _operator_state(summary.status_label, fallback=str(summary.status_label)),
                    "pipeline": _operator_token_text(summary.pipeline_mode),
                    "backend": _operator_token_text(summary.backend),
                    "run_id": str(summary.run_id or summary.run_dir.name),
                    "objective": _short_hash(summary.objective_contract_hash),
                    "scope": _short_hash(summary.problem_hash),
                    "baseline": _short_hash(summary.active_baseline_hash),
                }
            )
        return rows

    def _format_handoff_overview_text(self) -> str:
        rows = self.runtime.handoff_overview_rows()
        if not rows:
            return "Сейчас нет поэтапных прогонов, готовых к передаче координатору."
        lines: list[str] = []
        for idx, row in enumerate(rows[:8], start=1):
            lines.append(
                f"{idx}. {row.get('run')} - профиль {_operator_preset_text(row.get('preset'))}; "
                f"оценка {float(row.get('quality_score', 0.0) or 0.0):.1f}; бюджет {int(row.get('budget', 0) or 0)}; "
                f"стартовых вариантов {int(row.get('seeds', 0) or 0)}; полное кольцо {_operator_token_text(row.get('full_ring'))}"
            )
            lines.append(
                f"   допустимых строк {int(row.get('valid_rows', 0) or 0)}; пригодных {int(row.get('promotable', 0) or 0)}; "
                f"уникальных {int(row.get('unique', 0) or 0)}; фрагментов {int(row.get('fragments', 0) or 0)}; набор {_operator_token_text(row.get('suite'))}"
            )
        if len(rows) > 8:
            lines.append(f"... и ещё {len(rows) - 8} кандидатов в истории.")
        return "\n".join(lines)

    def _handoff_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row in self.runtime.handoff_overview_rows():
            rows.append(
                {
                    "run_dir": str(row.get("__run_dir") or ""),
                    "name": str(row.get("run") or ""),
                    "live": _operator_state(row.get("live_now"), fallback="нет"),
                    "preset": _operator_preset_text(row.get("preset")),
                    "score": f"{float(row.get('quality_score', 0.0) or 0.0):.1f}",
                    "budget": str(int(row.get("budget", 0) or 0)),
                    "seeds": str(int(row.get("seeds", 0) or 0)),
                }
            )
        return rows

    def _selected_handoff_row(self) -> dict[str, Any] | None:
        return self.runtime.selected_handoff_row(self._selected_run_dir)

    def _format_handoff_summary_text(self) -> str:
        summary = self.runtime.handoff_overview_summary()
        if int(summary.get("total_candidates", 0) or 0) <= 0:
            return "Сейчас нет поэтапных прогонов с планом передачи для продолжения."
        filters = dict(summary.get("filters") or {})
        return "\n".join(
            [
                f"Кандидатов в списке - {int(summary.get('total_candidates', 0) or 0)}",
                (
                    "Готовность - "
                    f"завершены {int(summary.get('done_candidates', 0) or 0)}, "
                    f"полное кольцо {int(summary.get('full_ring_candidates', 0) or 0)}, "
                    f"в работе {int(summary.get('live_candidates', 0) or 0)}."
                ),
                f"Стартовых вариантов всего - {int(summary.get('seed_total', 0) or 0)}",
                (
                    "Лучший кандидат - "
                    f"{summary.get('best_run') or '—'}. Профиль {_operator_preset_text(summary.get('best_preset'))}. "
                    f"Оценка {float(summary.get('best_score', 0.0) or 0.0):.1f}."
                ),
                (
                    "Фильтры - "
                    f"сортировка {summary.get('sort_mode') or '—'}, "
                    f"только полное кольцо {'да' if bool(filters.get('full_ring_only')) else 'нет'}, "
                    f"только завершённые {'да' if bool(filters.get('done_only')) else 'нет'}, "
                    f"минимум вариантов {int(filters.get('min_seeds', 0) or 0)}."
                ),
            ]
        )

    def _format_handoff_ranking_text(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "После текущих фильтров подходящих кандидатов для продолжения не осталось."
        lines: list[str] = []
        for idx, row in enumerate(rows[:8], start=1):
            lines.append(
                f"{idx}. {row.get('run')} - профиль {_operator_preset_text(row.get('preset'))}; "
                f"оценка {float(row.get('quality_score', 0.0) or 0.0):.1f}; бюджет {int(row.get('budget', 0) or 0)}; "
                f"стартовых вариантов {int(row.get('seeds', 0) or 0)}."
            )
            lines.append(
                f"   допустимых строк {int(row.get('valid_rows', 0) or 0)}; пригодных {int(row.get('promotable', 0) or 0)}; "
                f"уникальных {int(row.get('unique', 0) or 0)}; фрагментов {int(row.get('fragments', 0) or 0)}; "
                f"полное кольцо {_operator_token_text(row.get('full_ring'))}"
            )
        if len(rows) > 8:
            lines.append(f"... и ещё {len(rows) - 8} кандидатов в текущем списке.")
        return "\n".join(lines)

    def _format_selected_handoff_text(self, details: object | None, row: dict[str, Any] | None) -> str:
        if details is None or row is None:
            return "Выберите поэтапный прогон слева, чтобы увидеть рекомендацию по передаче и продолжению."
        summary = getattr(details, "summary")
        identity = self.runtime.selected_run_identity_summary(summary.run_dir)
        lines = [
            f"Исходный поэтапный прогон - {summary.run_dir}",
            f"Состояние - {_operator_state(summary.status_label or summary.status, fallback='нет данных')}",
            f"Сводка запуска - {_operator_state(identity.get('state'), fallback='не найден')}; метка {identity.get('run_id') or '—'}; цели {_short_hash(identity.get('objective_contract_hash'))}",
            (
                "Профиль передачи - "
                f"{_operator_preset_text(summary.handoff_preset_tag or row.get('preset'))}. "
                f"Исполнитель {_operator_token_text(summary.handoff_backend)}. "
                f"Генератор {_operator_token_text(summary.handoff_proposer)}. "
                f"Группа кандидатов {int(summary.handoff_q or 0)}."
            ),
            (
                "Бюджет продолжения - "
                f"{int(summary.handoff_budget or 0)}. Стартовых вариантов {int(summary.handoff_seed_count or 0)}. "
                f"Набор {_operator_token_text(summary.handoff_suite_family)}."
            ),
            (
                "Мост стартовых вариантов - "
                f"допустимых {int(summary.handoff_staged_rows_ok or 0)}. "
                f"пригодных {int(summary.handoff_promotable_rows or 0)}. "
                f"уникальных {int(summary.handoff_unique_param_candidates or 0)}. "
                f"пул {_operator_token_text(summary.handoff_selection_pool)}."
            ),
            (
                "Проверка полного кольца - "
                f"{'обязательна' if bool(summary.handoff_requires_full_ring_validation) else 'не обязательна'}. "
                f"Полное кольцо {'есть' if bool(summary.handoff_has_full_ring) else 'не найдено'}. "
                f"Фрагментов {int(summary.handoff_fragment_count or 0)}."
            ),
        ]
        if summary.handoff_target_run_dir is not None:
            lines.append(f"Целевая папка запуска - {summary.handoff_target_run_dir}")
        if summary.handoff_reason_lines:
            lines.append("")
            lines.append("Пояснение передачи:")
            lines.extend(str(line) for line in summary.handoff_reason_lines)
        return "\n".join(lines)

    def _format_handoff_runtime_text(self, row: dict[str, Any] | None) -> str:
        if row is None:
            return "Состояние продолжения появится здесь для выбранного кандидата."
        lines = [
            f"Выбранный кандидат - {row.get('run') or '—'}",
            f"Сейчас выполняется - {_operator_state(row.get('live_now'), fallback='нет')}",
        ]
        active_context = self.runtime.active_launch_context()
        if str(row.get("live_now") or "") == "LIVE":
            lines.append("Передача выполняется как продолжение координатора.")
            source_run_dir = str(active_context.get("source_run_dir") or "")
            if source_run_dir:
                lines.append(f"Исходная папка активного запуска - {source_run_dir}")
        else:
            lines.append("Передача сейчас не выполняется.")
        surface = self.runtime.active_job_surface()
        runtime_summary = dict(surface.get("runtime_summary") or {})
        if runtime_summary and str(row.get("live_now") or "") == "LIVE":
            lines.append("")
            lines.extend(str(item) for item in surface.get("captions") or ())
        else:
            lines.append("")
            lines.append("Нажмите «Начать передачу», чтобы продолжить выбранный поэтапный прогон через координатор.")
        return "\n".join(lines)

    def _finished_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row in self.runtime.finished_job_rows():
            rows.append(
                {
                    "run_dir": str(row.get("run_dir") or ""),
                    "name": str(row.get("name") or ""),
                    "status": _operator_state(row.get("status_label") or row.get("status"), fallback="нет данных"),
                    "pipeline": _operator_token_text(row.get("pipeline")),
                    "truth": str(row.get("truth_ready_rows") or 0),
                    "verify": str(row.get("verification_pass_rows") or 0),
                    "risk": str(row.get("interference_rows") or 0),
                }
            )
        return rows

    def _selected_finished_row(self) -> dict[str, Any] | None:
        for row in self.runtime.finished_job_rows():
            if str(row.get("run_dir") or "") == str(self._selected_run_dir or ""):
                return row
        return None

    def _format_finished_overview_text(self) -> str:
        overview = self.runtime.finished_job_overview()
        if int(overview.get("total_jobs", 0) or 0) <= 0:
            return "В рабочей папке пока нет завершённых прогонов с доступной сводкой."
        status_counts = ", ".join(
            f"{_operator_state(name, fallback=str(name))} - {count}"
            for name, count in tuple(overview.get("status_counts") or ())
        ) or "—"
        pipeline_counts = ", ".join(
            f"{_operator_token_text(name)} - {count}"
            for name, count in tuple(overview.get("pipeline_counts") or ())
        ) or "—"
        filters = dict(overview.get("filters") or {})
        return "\n".join(
            [
                f"Прогонов в списке - {int(overview.get('total_jobs', 0) or 0)}",
                f"Прогонов с результатами - {int(overview.get('jobs_with_results', 0) or 0)}",
                (
                    "Строки для выпуска - "
                    f"с данными {int(overview.get('rows_with_packaging_total', 0) or 0)}, "
                    f"готовы к проверке {int(overview.get('truth_ready_rows_total', 0) or 0)}, "
                    f"прошли проверку {int(overview.get('verification_rows_total', 0) or 0)}."
                ),
                (
                    "Готовность прогонов - "
                    f"готовы к проверке {int(overview.get('truth_ready_jobs', 0) or 0)}, "
                    f"прошли проверку {int(overview.get('verification_pass_jobs', 0) or 0)}, "
                    f"с рисками {int(overview.get('interference_jobs', 0) or 0)}, "
                    f"с резервными данными {int(overview.get('runtime_fallback_jobs', 0) or 0)}."
                ),
                f"Состояния - {status_counts}",
                f"Режимы запуска - {pipeline_counts}",
                (
                    "Фильтры - "
                    f"сортировка {overview.get('sort_mode') or '—'}, "
                    f"только завершённые {'да' if bool(filters.get('done_only')) else 'нет'}, "
                    f"только готовые к проверке {'да' if bool(filters.get('truth_ready_only')) else 'нет'}, "
                    f"только прошедшие проверку {'да' if bool(filters.get('verification_only')) else 'нет'}."
                ),
            ]
        )

    def _format_finished_ranking_text(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "После текущих фильтров подходящих завершённых прогонов не осталось."
        lines: list[str] = []
        for idx, row in enumerate(rows[:8], start=1):
            lines.append(
                f"{idx}. {row.get('name')} - {_operator_state(row.get('status_label'), fallback='нет данных')}; "
                f"контур {_operator_token_text(row.get('pipeline'))}; готовность {_operator_state(row.get('ready_state'), fallback='нет данных')}; "
                f"готовых строк {int(row.get('truth_ready_rows', 0) or 0)}; "
                f"проверенных {int(row.get('verification_pass_rows', 0) or 0)}; "
                f"с рисками {int(row.get('interference_rows', 0) or 0)}."
            )
            lines.append(
                f"   строк для выпуска {int(row.get('rows_with_packaging', 0) or 0)}/{int(row.get('rows_considered', 0) or 0)}; "
                f"полных {int(row.get('packaging_complete_rows', 0) or 0)}; "
                f"резервных {int(row.get('runtime_fallback_rows', 0) or 0)}; "
                f"состояния {row.get('status_counts_text') or 'нет данных'}"
            )
        if len(rows) > 8:
            lines.append(f"... и ещё {len(rows) - 8} завершённых прогонов в текущем списке.")
        return "\n".join(lines)

    def _format_finished_packaging_text(self, details: object | None, row: dict[str, Any] | None) -> str:
        if details is None or row is None:
            return "Выберите завершённый прогон слева, чтобы увидеть готовность данных для выпуска."
        packaging = getattr(details, "packaging_snapshot")
        status_counts = ", ".join(
            f"{_operator_state(name, fallback=str(name))} - {count}"
            for name, count in tuple(getattr(packaging, "status_counts", ()) or ())
        ) or "—"
        return "\n".join(
            [
                f"Готовность выбранного прогона - {_operator_state(row.get('ready_state'), fallback='нет данных')}",
                (
                    "Строки для выпуска - "
                    f"{int(getattr(packaging, 'rows_with_packaging', 0) or 0)} / "
                    f"{int(getattr(packaging, 'rows_considered', 0) or 0)} завершённых строк"
                ),
                f"Готовых к проверке строк - {int(getattr(packaging, 'packaging_truth_ready_rows', 0) or 0)}",
                f"Проверенных строк - {int(getattr(packaging, 'packaging_verification_pass_rows', 0) or 0)}",
                f"Полных строк - {int(getattr(packaging, 'packaging_complete_rows', 0) or 0)}",
                f"Резервных строк - {int(getattr(packaging, 'runtime_fallback_rows', 0) or 0)}",
                (
                    "Строки с риском пересечения - "
                    f"крепление пружины {int(getattr(packaging, 'spring_host_interference_rows', 0) or 0)}, "
                    f"пара пружин {int(getattr(packaging, 'spring_pair_interference_rows', 0) or 0)}."
                ),
                f"Состояния выпуска - {status_counts}",
            ]
        )

    def _format_finished_summary_text(self, details: object | None, row: dict[str, Any] | None) -> str:
        if details is None or row is None:
            return "Сводка завершённого прогона пока недоступна."
        summary = getattr(details, "summary")
        identity = self.runtime.selected_run_identity_summary(summary.run_dir)
        result_path = summary.result_path if summary.result_path is not None else None
        contract_text = _operator_list_text(summary.objective_keys)
        return "\n".join(
            [
                f"Папка запуска - {summary.run_dir}",
                f"Контур и исполнитель - {_operator_token_text(summary.pipeline_mode)} / {_operator_token_text(summary.backend)}",
                f"Состояние - {_operator_state(summary.status_label or summary.status, fallback='нет данных')}",
                f"Сводка запуска - {_operator_state(identity.get('state'), fallback='не найден')}; метка {identity.get('run_id') or '—'}",
                (
                    "Контрольные метки - "
                    f"цели {_short_hash(identity.get('objective_contract_hash'))}; "
                    f"задача {_short_hash(identity.get('problem_hash'))}; "
                    f"опорный прогон {_short_hash(identity.get('active_baseline_hash'))}; "
                    f"набор {_short_hash(identity.get('suite_snapshot_hash'))}."
                ),
                f"Результаты - {result_path or 'не найдены'}",
                f"Цели - {contract_text}",
                f"Ограничение - {summary.penalty_key or '—'}, допуск {summary.penalty_tol if summary.penalty_tol is not None else '—'}",
                f"Режим контроля - {_problem_hash_mode_text(summary.problem_hash_mode)}",
                f"Источник опорного прогона - {_operator_token_text(summary.baseline_source_label or summary.baseline_source_kind)}",
                f"Примечание - {summary.note or '—'}",
            ]
        )

    def _packaging_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row in self.runtime.packaging_rows():
            rows.append(
                {
                    "run_dir": str(row.get("run_dir") or ""),
                    "name": str(row.get("name") or ""),
                    "status": str(row.get("status_label") or row.get("status") or ""),
                    "truth": str(int(row.get("truth_ready_rows", 0) or 0)),
                    "verify": str(int(row.get("verification_pass_rows", 0) or 0)),
                    "risk": str(int(row.get("interference_rows", 0) or 0)),
                    "fallback": str(int(row.get("runtime_fallback_rows", 0) or 0)),
                }
            )
        return rows

    def _selected_packaging_row(self) -> dict[str, Any] | None:
        return self.runtime.selected_packaging_row(self._selected_run_dir)

    def _format_packaging_overview_text(self) -> str:
        overview = self.runtime.packaging_overview()
        if int(overview.get("total_runs", 0) or 0) <= 0:
            return "Сводка выпуска пока не нашла завершённых прогонов с доступными показателями."
        filters = dict(overview.get("filters") or {})
        return "\n".join(
            [
                f"Прогонов для выпуска в списке - {int(overview.get('total_runs', 0) or 0)}",
                (
                    "Готовность - "
                    f"готовы к проверке {int(overview.get('truth_ready_runs', 0) or 0)}, "
                    f"прошли проверку {int(overview.get('verification_runs', 0) or 0)}, "
                    f"без рисков {int(overview.get('zero_interference_runs', 0) or 0)}, "
                    f"с резервными данными {int(overview.get('fallback_runs', 0) or 0)}."
                ),
                (
                    "Строки - "
                    f"для выпуска {int(overview.get('packaging_rows_total', 0) or 0)}, "
                    f"готовы к проверке {int(overview.get('truth_ready_rows_total', 0) or 0)}, "
                    f"прошли проверку {int(overview.get('verification_rows_total', 0) or 0)}."
                ),
                (
                    "Лучший прогон для выпуска - "
                    f"{overview.get('best_run') or '—'}. Готовность {_operator_state(overview.get('best_ready_state'), fallback='нет данных')}."
                ),
                (
                    "Фильтры - "
                    f"сортировка {overview.get('sort_mode') or '—'}, "
                    f"только завершённые {'да' if bool(filters.get('done_only')) else 'нет'}, "
                    f"только готовые к проверке {'да' if bool(filters.get('truth_ready_only')) else 'нет'}, "
                    f"только прошедшие проверку {'да' if bool(filters.get('verification_only')) else 'нет'}, "
                    f"только без рисков {'да' if bool(filters.get('zero_interference_only')) else 'нет'}."
                ),
            ]
        )

    def _format_packaging_ranking_text(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "После текущих фильтров подходящих прогонов для выпуска не осталось."
        lines: list[str] = []
        for idx, row in enumerate(rows[:8], start=1):
            lines.append(
                f"{idx}. {row.get('name')} - {_operator_state(row.get('status_label'), fallback='нет данных')}; "
                f"готовность {_operator_state(row.get('ready_state'), fallback='нет данных')}; "
                f"готовых строк {int(row.get('truth_ready_rows', 0) or 0)}; "
                f"проверенных {int(row.get('verification_pass_rows', 0) or 0)}; "
                f"с рисками {int(row.get('interference_rows', 0) or 0)}; "
                f"резервных {int(row.get('runtime_fallback_rows', 0) or 0)}."
            )
            lines.append(
                f"   строк для выпуска {int(row.get('rows_with_packaging', 0) or 0)}/{int(row.get('rows_considered', 0) or 0)}; "
                f"полных {int(row.get('packaging_complete_rows', 0) or 0)}; контур {_operator_token_text(row.get('pipeline'))}"
            )
        if len(rows) > 8:
            lines.append(f"... и ещё {len(rows) - 8} прогонов для выпуска в текущем списке.")
        return "\n".join(lines)

    def _format_selected_packaging_text(self, details: object | None, row: dict[str, Any] | None) -> str:
        if details is None or row is None:
            return "Выберите прогон для выпуска слева, чтобы увидеть достаточность данных и геометрические риски."
        packaging = getattr(details, "packaging_snapshot")
        status_counts = ", ".join(
            f"{_operator_state(name, fallback=str(name))} - {count}"
            for name, count in tuple(getattr(packaging, "status_counts", ()) or ())
        ) or "—"
        return "\n".join(
            [
                f"Готовность - {_operator_state(row.get('ready_state'), fallback='нет данных')}",
                f"Строки для выпуска - {int(getattr(packaging, 'rows_with_packaging', 0) or 0)} / {int(getattr(packaging, 'rows_considered', 0) or 0)}",
                f"Полных строк - {int(getattr(packaging, 'packaging_complete_rows', 0) or 0)}",
                f"Готовых к проверке строк - {int(getattr(packaging, 'packaging_truth_ready_rows', 0) or 0)}",
                f"Проверенных строк - {int(getattr(packaging, 'packaging_verification_pass_rows', 0) or 0)}",
                f"Резервных строк - {int(getattr(packaging, 'runtime_fallback_rows', 0) or 0)}",
                (
                    "Строки с риском пересечения - "
                    f"крепление пружины {int(getattr(packaging, 'spring_host_interference_rows', 0) or 0)}, "
                    f"пара пружин {int(getattr(packaging, 'spring_pair_interference_rows', 0) or 0)}."
                ),
                f"Состояния выпуска - {status_counts}",
            ]
        )

    def _format_packaging_contract_text(self, details: object | None, row: dict[str, Any] | None) -> str:
        if details is None or row is None:
            return "Сведения о выбранном прогоне для выпуска появятся здесь."
        summary = getattr(details, "summary")
        identity = self.runtime.selected_run_identity_summary(summary.run_dir)
        return "\n".join(
            [
                f"Папка запуска - {summary.run_dir}",
                f"Контур и исполнитель - {_operator_token_text(summary.pipeline_mode)} / {_operator_token_text(summary.backend)}",
                f"Сводка запуска - {_operator_state(identity.get('state'), fallback='не найден')}; метка {identity.get('run_id') or '—'}",
                f"Цели - {_operator_list_text(summary.objective_keys)}",
                f"Ограничение - {summary.penalty_key or '—'}, допуск {summary.penalty_tol if summary.penalty_tol is not None else '—'}",
                f"Контроль задачи - {summary.problem_hash or '—'}",
                f"Режим контроля - {_problem_hash_mode_text(summary.problem_hash_mode)}",
                f"Источник опорного прогона - {_operator_token_text(summary.baseline_source_label or summary.baseline_source_kind)}",
                f"Результаты - {summary.result_path or 'не найдены'}",
                f"Примечание - {summary.note or '—'}",
            ]
        )

    def _history_details_tuple(self, details: object | None) -> tuple[str, str, str, str, str]:
        if details is None:
            empty = "Выберите прогон в списке слева."
            return empty, empty, empty, empty, ""
        summary = getattr(details, "summary")
        packaging = getattr(details, "packaging_snapshot")
        stage_rows = tuple(getattr(details, "stage_policy_rows") or ())
        identity = self.runtime.selected_run_identity_summary(summary.run_dir)
        summary_lines = [
            f"Папка запуска - {summary.run_dir}",
            f"Состояние - {_operator_state(summary.status_label or summary.status, fallback='нет данных')}",
            f"Контур и исполнитель - {_operator_token_text(summary.pipeline_mode)} / {_operator_token_text(summary.backend)}",
            f"Метка запуска - {identity.get('run_id') or '—'}",
            f"Состояние запуска - {_operator_state(identity.get('state'), fallback='не найден')}",
            f"Строки - всего {summary.row_count}, завершено {summary.done_count}, выполняется {summary.running_count}, ошибок {summary.error_count}",
            f"Примечание - {summary.note or '—'}",
        ]
        contract_lines = [
            (
                "Контрольные метки - "
                f"цели {_short_hash(identity.get('objective_contract_hash'))}; "
                f"задача {_short_hash(identity.get('problem_hash'))}; "
                f"опорный прогон {_short_hash(identity.get('active_baseline_hash'))}; "
                f"набор {_short_hash(identity.get('suite_snapshot_hash'))}."
            ),
            f"Паспорт выбранного запуска - {_short_hash(identity.get('selected_run_contract_hash'))}",
            f"Цели - {_operator_list_text(summary.objective_keys)}",
            f"Ограничение - {summary.penalty_key or '—'}, допуск {summary.penalty_tol if summary.penalty_tol is not None else '—'}",
            f"Контроль задачи - {summary.problem_hash or '—'}",
            f"Режим контроля - {_problem_hash_mode_text(summary.problem_hash_mode)}",
            f"Источник опорного прогона - {_operator_token_text(summary.baseline_source_label or summary.baseline_source_kind)}",
        ]
        packaging_lines = [
            f"Строки для выпуска - {int(packaging.rows_with_packaging)} / {int(packaging.rows_considered)}",
            f"Готовы к проверке - {int(packaging.packaging_truth_ready_rows)}",
            f"Прошли проверку - {int(packaging.packaging_verification_pass_rows)}",
            f"Резервные данные - {int(packaging.runtime_fallback_rows)}",
            f"Риск крепления пружины - {int(packaging.spring_host_interference_rows)}",
            f"Риск пары пружин - {int(packaging.spring_pair_interference_rows)}",
        ]
        stage_lines: list[str] = []
        if str(summary.pipeline_mode) == "staged":
            stage_lines.append(
                f"Передача - {'доступна' if bool(summary.handoff_available) else 'недоступна'}. "
                f"Профиль {_operator_preset_text(summary.handoff_preset_tag)}. Бюджет {int(summary.handoff_budget or 0)}. "
                f"Стартовых вариантов {int(summary.handoff_seed_count or 0)}."
            )
            if summary.handoff_reason_lines:
                stage_lines.append("Пояснение передачи:")
                stage_lines.extend(f"  - {line}" for line in summary.handoff_reason_lines)
            for row in stage_rows:
                if not bool(row.get("available")):
                    continue
                stage_lines.append(
                    f"{row.get('stage_name')}: {row.get('summary_line') or row.get('policy_name')} | "
                    f"стартовых вариантов {int(row.get('seed_count', 0) or 0)} | "
                    f"заполнение {row.get('underfill_message') or 'готово'}"
                )
        else:
            stage_lines.append("Для координационного прогона политика стадий напрямую не применяется.")
        return (
            "\n".join(summary_lines),
            "\n".join(contract_lines),
            "\n".join(packaging_lines),
            "\n".join(stage_lines),
            str(getattr(details, "log_tail", "") or ""),
        )

    def refresh_contract(self) -> None:
        self._sync_widget_state()
        self._contract_snapshot = self.runtime.contract_snapshot()
        self.contract_tab.render(
            snapshot=self._contract_snapshot,
            stage_policy_text=self._format_stage_policy_blueprint_text(
                self.runtime.stage_policy_blueprint_rows()
            ),
            drift_text=self._format_selected_contract_drift_text(),
        )

    def refresh_all(self) -> None:
        self.refresh_contract()
        self.mode_summary_var.set(self._format_compact_mode_summary())
        self.workspace_summary_var.set(self._format_compact_workspace_summary())
        self.baseline_summary_var.set(self._format_baseline_summary_text())
        self.contract_summary_var.set(self._format_runtime_contract_summary_text())
        self.launch_button_text_var.set(self._primary_launch_button_text())
        surface = self.runtime.active_job_surface()
        readiness = self.runtime.launch_readiness_summary()
        self.runtime_tab.render(
            profile_key=str(self.runtime.session_state.get("opt_launch_profile", "") or ""),
            profile_text=self._format_launch_profile_text(),
            readiness_text=self._format_launch_readiness_text(readiness),
            contract_text=self._format_runtime_contract_summary_text(),
            preview_text=self.runtime.command_preview_text(),
            resume_text=self._format_resume_target_text(),
            status_text=self._format_runtime_status_text(surface),
            stage_policy_text=self._format_stage_runtime_text(
                tuple(surface.get("stage_policy_rows") or ())
            ),
            log_text=str(surface.get("log_text") or ""),
        )
        self.refresh_history()
        self.refresh_finished_jobs()
        self.refresh_handoff()
        self.refresh_packaging()
        self.refresh_dashboard()
        self.status_var.set("Сводка оптимизации обновлена.")

    def refresh_history(self) -> None:
        self._sync_widget_state()
        rows = self._history_rows()
        available_run_dirs = {str(row.get("run_dir") or "") for row in rows}
        if self._selected_run_dir and self._selected_run_dir not in available_run_dirs:
            self._selected_run_dir = ""
        if not self._selected_run_dir and rows:
            self._selected_run_dir = str(rows[0].get("run_dir") or "")
        self.runtime.bind_selected_run_dir(self._selected_run_dir)
        if "opt_dist_run_id" in self._tk_vars:
            self._tk_vars["opt_dist_run_id"].set(
                str(self.runtime.session_state.get("opt_dist_run_id", "") or "")
            )
        self.history_tab.set_history_rows(rows, selected_key=self._selected_run_dir)
        details = (
            self.runtime.selected_run_details(self._selected_run_dir)
            if self._selected_run_dir
            else None
        )
        summary_text, contract_text, packaging_text, stage_policy_text, log_text = self._history_details_tuple(details)
        self.history_tab.render_details(
            handoff_text=self._format_handoff_overview_text(),
            summary_text=summary_text,
            contract_text=contract_text,
            packaging_text=packaging_text,
            stage_policy_text=stage_policy_text,
            log_text=log_text,
        )

    def _materialize_selected_run_for_analysis(self, selected_from: str) -> str:
        if not self._selected_run_dir:
            return ""
        self.runtime.bind_selected_run_dir(self._selected_run_dir)
        details = self.runtime.selected_run_details(self._selected_run_dir)
        if details is None:
            return "Передача в анализ не обновлена: выбранный прогон не найден в истории."
        summary = getattr(details, "summary")
        try:
            pointer = self.runtime.save_run_pointer(
                summary,
                selected_from=selected_from,
            )
        except Exception as exc:
            return f"Передача в анализ не обновлена: {exc}"
        contract_state = str(pointer.get("analysis_handoff_ready_state") or "unknown")
        contract_path = str(pointer.get("selected_run_contract_path") or "")
        path_suffix = f" | {contract_path}" if contract_path else ""
        return (
            "Передача в анализ обновлена: "
            f"{pointer.get('run_name') or summary.run_dir.name} | "
            f"паспорт выбранного запуска - {_operator_state(contract_state, fallback='нет данных')}{path_suffix}"
        )

    def _refresh_after_run_selection(self, status_text: str = "") -> None:
        self.refresh_contract()
        self.refresh_history()
        self.refresh_finished_jobs()
        self.refresh_handoff()
        self.refresh_packaging()
        self.refresh_dashboard()
        if status_text:
            self.status_var.set(status_text)

    def on_history_selection_changed(self) -> None:
        self._selected_run_dir = self.history_tab.selected_run_dir()
        status_text = self._materialize_selected_run_for_analysis("history_selection")
        self._refresh_after_run_selection(status_text)

    def refresh_finished_jobs(self) -> None:
        self._sync_widget_state()
        runtime_rows = self.runtime.finished_job_rows()
        tree_rows = self._finished_rows()
        available_run_dirs = {str(row.get("run_dir") or "") for row in tree_rows}
        selected_key = self._selected_run_dir if self._selected_run_dir in available_run_dirs else ""
        self.finished_tab.set_finished_rows(tree_rows, selected_key=selected_key)
        details = (
            self.runtime.selected_run_details(selected_key)
            if selected_key
            else None
        )
        selected_row = self._selected_finished_row()
        self.finished_tab.render_details(
            overview_text=self._format_finished_overview_text(),
            ranking_text=self._format_finished_ranking_text(runtime_rows),
            packaging_text=self._format_finished_packaging_text(details, selected_row),
            summary_text=self._format_finished_summary_text(details, selected_row),
        )

    def on_finished_selection_changed(self) -> None:
        self._selected_run_dir = self.finished_tab.selected_run_dir()
        status_text = self._materialize_selected_run_for_analysis("finished_selection")
        self._refresh_after_run_selection(status_text)

    def refresh_handoff(self) -> None:
        self._sync_widget_state()
        runtime_rows = self.runtime.handoff_overview_rows()
        tree_rows = self._handoff_rows()
        available_run_dirs = {str(row.get("run_dir") or "") for row in tree_rows}
        selected_key = self._selected_run_dir if self._selected_run_dir in available_run_dirs else ""
        self.handoff_tab.set_handoff_rows(tree_rows, selected_key=selected_key)
        details = self.runtime.selected_run_details(selected_key) if selected_key else None
        selected_row = self.runtime.selected_handoff_row(selected_key)
        self.handoff_tab.render_details(
            overview_text=self._format_handoff_summary_text(),
            ranking_text=self._format_handoff_ranking_text(runtime_rows),
            selected_text=self._format_selected_handoff_text(details, selected_row),
            runtime_text=self._format_handoff_runtime_text(selected_row),
        )

    def on_handoff_selection_changed(self) -> None:
        self._selected_run_dir = self.handoff_tab.selected_run_dir()
        status_text = self._materialize_selected_run_for_analysis("handoff_selection")
        self._refresh_after_run_selection(status_text)

    def refresh_packaging(self) -> None:
        self._sync_widget_state()
        runtime_rows = self.runtime.packaging_rows()
        tree_rows = self._packaging_rows()
        available_run_dirs = {str(row.get("run_dir") or "") for row in tree_rows}
        selected_key = self._selected_run_dir if self._selected_run_dir in available_run_dirs else ""
        self.packaging_tab.set_packaging_rows(tree_rows, selected_key=selected_key)
        details = self.runtime.selected_run_details(selected_key) if selected_key else None
        selected_row = self.runtime.selected_packaging_row(selected_key)
        self.packaging_tab.render_details(
            overview_text=self._format_packaging_overview_text(),
            ranking_text=self._format_packaging_ranking_text(runtime_rows),
            snapshot_text=self._format_selected_packaging_text(details, selected_row),
            contract_text=self._format_packaging_contract_text(details, selected_row),
        )

    def on_packaging_selection_changed(self) -> None:
        self._selected_run_dir = self.packaging_tab.selected_run_dir()
        status_text = self._materialize_selected_run_for_analysis("packaging_selection")
        self._refresh_after_run_selection(status_text)

    def refresh_dashboard(self) -> None:
        self._sync_widget_state()
        dashboard = self.runtime.dashboard_snapshot()
        self.dashboard_tab.render(
            workspace_text=self._format_dashboard_workspace_text(),
            runtime_text=self._format_dashboard_runtime_text(dashboard),
            readiness_text=self._format_launch_readiness_text(
                dict(dashboard.get("launch_readiness") or {})
            ),
            pointer_text=self._format_dashboard_pointer_text(dashboard),
            finished_text=self._format_dashboard_finished_text(dashboard),
            handoff_text=self._format_dashboard_handoff_text(dashboard),
            packaging_text=self._format_dashboard_packaging_text(dashboard),
            selection_text=self._format_dashboard_selection_text(),
            next_step_text=self._format_selected_run_next_step_text(
                dict(dashboard.get("selected_run_next_step") or {})
            ),
        )

    def follow_launch_readiness_next_action(self) -> None:
        self._sync_widget_state()
        readiness = self.runtime.launch_readiness_summary()
        action = str(readiness.get("next_action") or "Runtime").strip()
        if action in {"Contract", "Contract drift", "Настройки запуска"}:
            self.show_contract_tab()
        elif action in {"History", "История"}:
            self.show_history_tab()
        elif action in {"Finished Jobs", "Готовые запуски"}:
            self.show_finished_tab()
        elif action in {"Handoff", "Передача данных"}:
            self.show_handoff_tab()
        elif action in {"Packaging", "Упаковка"}:
            self.show_packaging_tab()
        else:
            self.show_runtime_tab()
        action_labels = {
            "Contract": "настройкам запуска",
            "Contract drift": "сверке настроек",
            "Настройки запуска": "настройкам запуска",
            "History": "истории",
            "Finished Jobs": "готовым прогонам",
            "Handoff": "передаче",
            "Packaging": "выпуску",
            "Runtime": "выполнению",
        }
        self.status_var.set(
            f"Готовность запуска рекомендует перейти к разделу {action_labels.get(action, action or 'выполнение')}."
        )

    def follow_selected_run_next_step(self) -> None:
        self._sync_widget_state()
        payload = self.runtime.selected_run_next_step_summary(self._selected_run_dir)
        action_kind = str(payload.get("next_action_kind") or "show_history_tab").strip()
        action_label = str(payload.get("next_action") or "История").strip() or "История"
        if action_kind == "make_latest_pointer":
            self.make_selected_run_latest_pointer()
            return
        if action_kind == "show_contract_tab":
            self.show_contract_tab()
        elif action_kind == "show_runtime_tab":
            self.show_runtime_tab()
        elif action_kind == "show_handoff_tab":
            self.show_handoff_tab()
        elif action_kind == "show_packaging_tab":
            self.show_packaging_tab()
        elif action_kind == "show_finished_tab":
            self.show_finished_tab()
        else:
            self.show_history_tab()
        self.status_var.set(f"Рекомендация по выбранному запуску: перейти к разделу {action_label}.")

    def open_selected_run_dir(self) -> None:
        if not self._selected_run_dir:
            return
        try:
            self._open_path(Path(self._selected_run_dir))
        except Exception as exc:
            messagebox.showerror(
                "Оптимизация",
                f"Не удалось открыть папку запуска:\n{exc}",
            )

    def open_selected_log(self) -> None:
        details = (
            self.runtime.selected_run_details(self._selected_run_dir)
            if self._selected_run_dir
            else None
        )
        if details is None:
            return
        summary = getattr(details, "summary")
        path = summary.log_path if summary.log_path is not None else None
        if path is None:
            return
        try:
            self._open_path(path)
        except Exception as exc:
            messagebox.showerror(
                "Оптимизация",
            f"Не удалось открыть журнал:\n{exc}",
            )

    def open_selected_results(self) -> None:
        details = (
            self.runtime.selected_run_details(self._selected_run_dir)
            if self._selected_run_dir
            else None
        )
        if details is None:
            return
        summary = getattr(details, "summary")
        path = summary.result_path if summary.result_path is not None else None
        if path is None:
            messagebox.showinfo(
                "Оптимизация",
                "У выбранного прогона пока нет файла результатов.",
            )
            return
        try:
            self._open_path(path)
        except Exception as exc:
            messagebox.showerror(
                "Оптимизация",
                f"Не удалось открыть файл результатов:\n{exc}",
            )

    def open_selected_objective_contract(self) -> None:
        details = (
            self.runtime.selected_run_details(self._selected_run_dir)
            if self._selected_run_dir
            else None
        )
        if details is None:
            return
        summary = getattr(details, "summary")
        path = summary.objective_contract_path if summary.objective_contract_path is not None else None
        if path is None:
            messagebox.showinfo(
                "Оптимизация",
                "У выбранного запуска нет файла с паспортом целей.",
            )
            return
        try:
            self._open_path(path)
        except Exception as exc:
            messagebox.showerror(
                "Оптимизация",
                f"Не удалось открыть паспорт целей:\n{exc}",
            )

    def open_selected_handoff_plan(self) -> None:
        details = (
            self.runtime.selected_run_details(self._selected_run_dir)
            if self._selected_run_dir
            else None
        )
        if details is None:
            return
        summary = getattr(details, "summary")
        path = summary.handoff_plan_path if summary.handoff_plan_path is not None else None
        if path is None:
            messagebox.showinfo(
                "Оптимизация",
                "У выбранного запуска нет плана передачи данных.",
            )
            return
        try:
            self._open_path(path)
        except Exception as exc:
            messagebox.showerror(
                "Оптимизация",
                f"Не удалось открыть план передачи данных:\n{exc}",
            )

    def open_latest_optimization_pointer(self) -> None:
        pointer = self.runtime.latest_pointer_summary()
        if not bool(pointer.get("exists")):
            messagebox.showinfo(
                "Оптимизация",
                "Прогон для анализа пока не выбран.",
            )
            return
        try:
            self._open_path(Path(str(pointer.get("pointer_path") or "")))
        except Exception as exc:
            messagebox.showerror(
                "Оптимизация",
                f"Не удалось открыть прогон для анализа:\n{exc}",
            )

    def make_selected_run_latest_pointer(self) -> None:
        details = (
            self.runtime.selected_run_details(self._selected_run_dir)
            if self._selected_run_dir
            else None
        )
        if details is None:
            messagebox.showinfo(
                "Оптимизация",
                "Сначала выберите прогон, который нужно передать в анализ.",
            )
            return
        summary = getattr(details, "summary")
        pointer = self.runtime.save_run_pointer(
            summary,
            selected_from="desktop_optimizer_center_manual_retry",
        )
        status_text = (
            "Прогон передан в анализ: "
            f"{pointer.get('run_name') or summary.run_dir.name}"
        )
        self.refresh_all()
        self.status_var.set(status_text)

    def apply_selected_run_contract(self) -> None:
        details = (
            self.runtime.selected_run_details(self._selected_run_dir)
            if self._selected_run_dir
            else None
        )
        if details is None:
            return
        summary = getattr(details, "summary")
        updates = self.runtime.apply_run_contract(summary)
        if not updates:
            messagebox.showinfo(
                "Оптимизация",
                "У выбранного запуска нет настроек, которые можно подставить в текущий запуск.",
            )
            return
        self._load_state_into_widgets()
        self.status_var.set(
            "Настройки выбранного запуска подставлены в текущий запуск: "
            + ", ".join(sorted(str(key) for key in updates))
            + ". Происхождение опорного прогона не подменялось автоматически."
        )
        self.refresh_all()
        self.notebook.select(self.contract_tab)

    def apply_launch_profile_label(self, label: str) -> None:
        self._sync_widget_state()
        profile_key = launch_profile_key_for_label(label)
        updates = self.runtime.apply_launch_profile(profile_key)
        if not updates:
            self.status_var.set(
                f"Профиль запуска уже активен без ручных отличий - {label or profile_key}"
            )
            self.refresh_all()
            self.notebook.select(self.runtime_tab)
            return
        self._load_state_into_widgets()
        self.status_var.set(
            "Профиль запуска применён - "
            f"{label or profile_key}. Обновлено настроек {len(updates)}."
        )
        self.refresh_all()
        self.notebook.select(self.runtime_tab)

    def launch_job(self) -> None:
        self._sync_widget_state()
        preflight = self.runtime.launch_preflight_summary()
        if not bool(preflight.get("can_launch")):
            reasons = "\n".join(
                "- " + str(item)
                for item in tuple(preflight.get("blocking_reasons") or ())
                if str(item).strip()
            )
            messagebox.showwarning(
                "Оптимизация",
                "Запуск заблокирован предварительной проверкой:\n" + (reasons or "- причина не указана"),
            )
            self.status_var.set("Запуск заблокирован: проверьте разделы выполнения и настроек запуска.")
            self.refresh_all()
            self.notebook.select(self.runtime_tab)
            return
        try:
            job = self.runtime.start_job()
        except Exception as exc:
            messagebox.showerror(
                "Оптимизация",
                f"Не удалось запустить оптимизацию:\n{exc}",
            )
            return
        self.status_var.set(f"Запуск создан - {getattr(job, 'run_dir', '')}")
        self.refresh_all()
        self.notebook.select(self.runtime_tab)

    def soft_stop_job(self) -> None:
        if self.runtime.request_soft_stop():
            self.status_var.set("Запрошена мягкая остановка текущей задачи оптимизации.")
            self.refresh_all()

    def hard_stop_job(self) -> None:
        if self.runtime.request_hard_stop():
            self.status_var.set("Отправлена команда остановки задачи оптимизации.")
        else:
            self.status_var.set("Процесс остановлен принудительно.")
        self.refresh_all()

    def clear_job_status(self) -> None:
        if self.runtime.clear_finished_job():
            self.status_var.set("Сообщение о текущей задаче оптимизации очищено.")
        else:
            self.status_var.set("Задача оптимизации ещё активна; сначала остановите её или дождитесь завершения.")
        self.refresh_all()

    def start_selected_handoff(self) -> None:
        if not self._selected_run_dir:
            return
        details = self.runtime.selected_run_details(self._selected_run_dir)
        if details is None:
            return
        summary = getattr(details, "summary")
        if str(summary.pipeline_mode) != "staged":
            messagebox.showinfo(
                "Оптимизация",
                "Передача доступна только для поэтапного прогона.",
            )
            return
        if not bool(summary.handoff_available):
            messagebox.showinfo(
                "Оптимизация",
                "Для этого поэтапного прогона передача координатору пока не подготовлена.",
            )
            return
        try:
            job = self.runtime.start_handoff(summary.run_dir)
        except Exception as exc:
            messagebox.showerror(
                "Оптимизация",
                f"Не удалось запустить передачу:\n{exc}",
            )
            return
        self.status_var.set(f"Передача запущена - {getattr(job, 'run_dir', '')}")
        self.refresh_all()
        self.notebook.select(self.runtime_tab)

    def _schedule_poll(self) -> None:
        if self._host_closed:
            return
        if self._poll_after_id is not None:
            try:
                self.root.after_cancel(self._poll_after_id)
            except Exception:
                pass
        self._poll_after_id = self.root.after(2000, self._poll_runtime)

    def _poll_runtime(self) -> None:
        self._poll_after_id = None
        if self._host_closed:
            return
        try:
            self.refresh_all()
        except Exception:
            pass
        self._schedule_poll()

    def _request_close(self) -> None:
        self.on_host_close()
        if self._owns_root and int(self.root.winfo_exists()):
            self.root.destroy()

    def focus(self) -> None:
        if not self._owns_root:
            return
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            return

    def on_host_close(self) -> None:
        self._host_closed = True
        if self._poll_after_id is not None:
            try:
                self.root.after_cancel(self._poll_after_id)
            except Exception:
                pass
            self._poll_after_id = None

    def run(self) -> None:
        if self._owns_root:
            self.root.mainloop()


def main() -> int:
    app = DesktopOptimizerCenter()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
