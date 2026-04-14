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
    "objective stack": "objective stack",
    "penalty key": "penalty key",
    "penalty tol": "penalty tol",
}


class DesktopOptimizerCenter:
    def __init__(self, host: tk.Misc | None = None, *, hosted: bool = False) -> None:
        self._owns_root = host is None
        self._hosted = bool(hosted or not self._owns_root)
        self.root = host if host is not None else tk.Tk()
        if self._owns_root:
            self.root.title(f"Центр автоматизированной оптимизации ({RELEASE})")
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
            value="Готово. Автоматизированная оптимизация доступна в отдельном инженерном центре."
        )
        self.mode_summary_var = tk.StringVar(
            value="Режим: active optimization mode, baseline и runtime contract будут показаны после первого обновления."
        )
        self.workspace_summary_var = tk.StringVar(
            value="Контекст: контракт, история прогонов и готовые выпуски будут показаны после первого обновления."
        )
        self.baseline_summary_var = tk.StringVar(
            value="Baseline: источник и политика автообновления будут показаны после первого обновления."
        )
        self.contract_summary_var = tk.StringVar(
            value="Runtime contract: objective stack и hard gate будут показаны после первого обновления."
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
            text="Baseline и optimization",
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
            text="Маршрут",
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
            text="Обновить",
            command=self.refresh_all,
        ).pack(side="left", padx=(12, 0))

        workspace = ttk.Panedwindow(outer, orient="horizontal")
        workspace.pack(fill="both", expand=True)

        sidebar = ttk.Frame(workspace, padding=(0, 0, 8, 0))
        sidebar.columnconfigure(0, weight=1)
        context_frame = ttk.LabelFrame(sidebar, text="Контекст", padding=8)
        context_frame.pack(fill="x")
        ttk.Label(
            context_frame,
            textvariable=self.workspace_summary_var,
            justify="left",
            wraplength=300,
        ).pack(anchor="w")

        baseline_frame = ttk.LabelFrame(sidebar, text="Baseline", padding=8)
        baseline_frame.pack(fill="x", pady=(8, 0))
        ttk.Label(
            baseline_frame,
            textvariable=self.baseline_summary_var,
            justify="left",
            wraplength=300,
        ).pack(anchor="w")

        contract_frame = ttk.LabelFrame(sidebar, text="Runtime contract", padding=8)
        contract_frame.pack(fill="x", pady=(8, 0))
        ttk.Label(
            contract_frame,
            textvariable=self.contract_summary_var,
            justify="left",
            wraplength=300,
        ).pack(anchor="w")

        nav_frame = ttk.LabelFrame(sidebar, text="Переходы", padding=8)
        nav_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(nav_frame, text="Baseline и контракт", command=self.show_contract_tab).pack(fill="x")
        ttk.Button(nav_frame, text="Optimization runtime", command=self.show_runtime_tab).pack(fill="x", pady=(6, 0))
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
        self.notebook.add(self.dashboard_tab, text="Baseline и запуск")
        self.notebook.add(self.contract_tab, text="Baseline и контракт")
        self.notebook.add(self.runtime_tab, text="Optimization runtime")
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
                "Desktop Optimizer Center",
                f"Не удалось открыть путь:\n{exc}",
            )

    def _format_stage_policy_blueprint_text(self, rows: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for row in rows:
            explore_pct = int(round(float(row.get("explore_frac", 0.0) or 0.0) * 100.0))
            line = (
                f"{row.get('stage_name')}: {row.get('role')}\n"
                f"  policy={row.get('policy_name')} | requested={row.get('requested_mode')} | "
                f"effective={row.get('effective_mode')} | top_k={int(row.get('top_k', 0) or 0)} | "
                f"explore={explore_pct}% | explore_budget={int(row.get('explore_budget', 0) or 0)} | "
                f"focus_budget={int(row.get('focus_budget', 0) or 0)}"
            )
            fallback_reason = str(row.get("fallback_reason") or "")
            if fallback_reason:
                line += f"\n  fallback: {fallback_reason}"
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
            return "Активного optimization job сейчас нет."
        job = surface.get("job")
        rc = surface.get("returncode")
        runtime_summary = dict(surface.get("runtime_summary") or {})
        lines = [
            f"run_dir: {getattr(job, 'run_dir', '')}",
            f"pipeline: {getattr(job, 'pipeline_mode', '')}",
            f"backend: {getattr(job, 'backend', '')}",
            f"budget: {int(getattr(job, 'budget', 0) or 0)}",
        ]
        lines.append("состояние: выполняется" if rc is None else f"состояние: завершено rc={int(rc)}")
        if surface.get("soft_stop_requested"):
            lines.append("soft-stop: requested")
        if runtime_summary:
            lines.append("")
            lines.extend(str(line) for line in surface.get("captions") or [])
        return "\n".join(lines)

    def _format_resume_target_text(self) -> str:
        payload = self.runtime.resume_target_summary()
        selected_run_dir = str(payload.get("selected_run_dir") or "")
        if not selected_run_dir:
            return (
                "History target не выбран.\n"
                "Выберите staged/coordinator run во вкладке History, чтобы использовать его как resume target."
            )
        lines = [
            f"выбранный прогон: {payload.get('selected_run_name') or '—'}",
            f"контур выбранного прогона: {payload.get('selected_pipeline') or '—'}",
            f"путь к выбранному прогону: {selected_run_dir}",
            f"контур текущего запуска: {payload.get('launch_pipeline') or '—'}",
        ]
        if payload.get("selected_run_id"):
            lines.append(f"идентификатор координатора: {payload.get('selected_run_id')}")
        if bool(payload.get("stage_resume_enabled")):
            lines.append("продолжение стадий: включено")
        else:
            lines.append("продолжение стадий: выключено")
        if bool(payload.get("coord_resume_enabled")):
            lines.append(
                f"продолжение координатора: включено (run_id={payload.get('coord_run_id') or 'auto/problem-hash'})"
            )
        else:
            lines.append("продолжение координатора: выключено")
        return "\n".join(lines)

    def _format_dashboard_workspace_text(self) -> str:
        snapshot = self._contract_snapshot
        if snapshot is None:
            snapshot = self.runtime.contract_snapshot()
        objective_keys = ", ".join(tuple(getattr(snapshot, "objective_keys", ()) or ())) or "—"
        stage_counts = ", ".join(
            f"{key}={value}"
            for key, value in dict(getattr(snapshot, "enabled_stage_counts", {}) or {}).items()
        ) or "—"
        return "\n".join(
            [
                f"рабочая область: {getattr(snapshot, 'workspace_dir', '')}",
                f"хэш задачи: {getattr(snapshot, 'problem_hash', '') or '—'}",
                f"режим хэша: {getattr(snapshot, 'problem_hash_mode', '') or '—'}",
                f"цели оптимизации: {objective_keys}",
                (
                    "пространство поиска: "
                    f"базовых={int(getattr(snapshot, 'base_param_count', 0) or 0)}, "
                    f"проектных={int(getattr(snapshot, 'search_param_count', 0) or 0)}, "
                    f"расширенных={int(getattr(snapshot, 'widened_range_count', 0) or 0)}"
                ),
                (
                    "покрытие сценариев: "
                    f"строк={int(getattr(snapshot, 'suite_row_count', 0) or 0)}, "
                    f"включено={int(getattr(snapshot, 'enabled_suite_total', 0) or 0)}, "
                    f"стадии={stage_counts}"
                ),
                f"источник базового решения: {getattr(snapshot, 'baseline_source_label', '') or getattr(snapshot, 'baseline_source_kind', '') or '—'}",
            ]
        )

    def _format_dashboard_runtime_text(self, dashboard: dict[str, Any]) -> str:
        launch_profile = dict(dashboard.get("launch_profile") or {})
        resume_target = dict(dashboard.get("resume_target") or {})
        active_surface = dict(dashboard.get("active_surface") or {})
        lines = [
            f"профиль запуска: {launch_profile.get('profile_label') or '—'}",
            (
                "режим запуска: "
                f"{launch_profile.get('launch_pipeline') or '—'} / "
                f"{launch_profile.get('backend') or '—'}"
            ),
            (
                "resume target: "
                f"{resume_target.get('selected_run_name') or 'not selected'} / "
                f"{resume_target.get('selected_pipeline') or '—'}"
            ),
        ]
        if not active_surface:
            lines.append("active job: none")
            return "\n".join(lines)
        job = active_surface.get("job")
        lines.append(
            "active job: "
            f"{getattr(job, 'pipeline_mode', '') or '—'} / "
            f"{getattr(job, 'backend', '') or '—'} @ {getattr(job, 'run_dir', '') or '—'}"
        )
        lines.extend(str(line) for line in active_surface.get("captions") or [])
        return "\n".join(lines)

    def _format_dashboard_finished_text(self, dashboard: dict[str, Any]) -> str:
        overview = dict(dashboard.get("finished_overview") or {})
        best = dict(dashboard.get("best_finished_row") or {})
        if int(overview.get("total_jobs", 0) or 0) <= 0:
            return "Finished jobs readiness: historical finished runs пока не найдены."
        lines = [
            (
                "jobs: "
                f"total={int(overview.get('total_jobs', 0) or 0)}, "
                f"truth_ready={int(overview.get('truth_ready_jobs', 0) or 0)}, "
                f"verification={int(overview.get('verification_pass_jobs', 0) or 0)}, "
                f"interference={int(overview.get('interference_jobs', 0) or 0)}"
            ),
            (
                "rows: "
                f"packaging={int(overview.get('rows_with_packaging_total', 0) or 0)}, "
                f"truth_ready={int(overview.get('truth_ready_rows_total', 0) or 0)}, "
                f"verification={int(overview.get('verification_rows_total', 0) or 0)}"
            ),
        ]
        if best:
            lines.append(
                "best finished run: "
                f"{best.get('name') or '—'} | ready={best.get('ready_state') or '—'} | "
                f"truth={int(best.get('truth_ready_rows', 0) or 0)} | "
                f"verify={int(best.get('verification_pass_rows', 0) or 0)} | "
                f"risk={int(best.get('interference_rows', 0) or 0)}"
            )
        return "\n".join(lines)

    def _format_dashboard_handoff_text(self, dashboard: dict[str, Any]) -> str:
        overview = dict(dashboard.get("handoff_overview") or {})
        best = dict(dashboard.get("best_handoff_row") or {})
        if int(overview.get("total_candidates", 0) or 0) <= 0:
            return "Handoff: staged continuation candidates пока не найдены."
        lines = [
            (
                "candidates: "
                f"total={int(overview.get('total_candidates', 0) or 0)}, "
                f"done={int(overview.get('done_candidates', 0) or 0)}, "
                f"full_ring={int(overview.get('full_ring_candidates', 0) or 0)}, "
                f"live={int(overview.get('live_candidates', 0) or 0)}"
            ),
            f"seed inventory: {int(overview.get('seed_total', 0) or 0)}",
        ]
        if best:
            lines.append(
                "best handoff: "
                f"{best.get('run') or '—'} | preset={best.get('preset') or '—'} | "
                f"score={float(best.get('quality_score', 0.0) or 0.0):.1f} | "
                f"budget={int(best.get('budget', 0) or 0)} | seeds={int(best.get('seeds', 0) or 0)}"
            )
        return "\n".join(lines)

    def _format_dashboard_packaging_text(self, dashboard: dict[str, Any]) -> str:
        overview = dict(dashboard.get("packaging_overview") or {})
        best = dict(dashboard.get("best_packaging_row") or {})
        if int(overview.get("total_runs", 0) or 0) <= 0:
            return "Packaging: packaging evidence по finished runs пока недоступен."
        lines = [
            (
                "runs: "
                f"total={int(overview.get('total_runs', 0) or 0)}, "
                f"truth_ready={int(overview.get('truth_ready_runs', 0) or 0)}, "
                f"verification={int(overview.get('verification_runs', 0) or 0)}, "
                f"zero_interference={int(overview.get('zero_interference_runs', 0) or 0)}"
            ),
            (
                "row totals: "
                f"packaging={int(overview.get('packaging_rows_total', 0) or 0)}, "
                f"truth_ready={int(overview.get('truth_ready_rows_total', 0) or 0)}, "
                f"verification={int(overview.get('verification_rows_total', 0) or 0)}"
            ),
        ]
        if best:
            lines.append(
                "best packaging run: "
                f"{best.get('name') or '—'} | ready={best.get('ready_state') or '—'} | "
                f"truth={int(best.get('truth_ready_rows', 0) or 0)} | "
                f"verify={int(best.get('verification_pass_rows', 0) or 0)} | "
                f"risk={int(best.get('interference_rows', 0) or 0)}"
            )
        return "\n".join(lines)

    def _format_compact_mode_summary(self) -> str:
        payload = self.runtime.launch_profile_summary()
        profile = str(payload.get("profile_label") or "Автоматический маршрут")
        pipeline = str(payload.get("launch_pipeline") or "—")
        backend = str(payload.get("backend") or "—")
        drift_keys = tuple(str(key) for key in payload.get("drift_keys") or ())
        summary = f"Режим: {profile} | Контур: {pipeline} | Исполнитель: {backend}"
        if drift_keys:
            summary += " | Изменено вручную: " + ", ".join(drift_keys[:3])
            if len(drift_keys) > 3:
                summary += "..."
        return summary

    def _format_compact_workspace_summary(self) -> str:
        snapshot = self._contract_snapshot
        if snapshot is None:
            snapshot = self.runtime.contract_snapshot()
        return "\n".join(
            [
                f"Хэш задачи: {getattr(snapshot, 'problem_hash', '') or '—'}",
                (
                    "Сценарии: "
                    f"всего {int(getattr(snapshot, 'suite_row_count', 0) or 0)}, "
                    f"активно {int(getattr(snapshot, 'enabled_suite_total', 0) or 0)}"
                ),
                (
                    "Параметры поиска: "
                    f"{int(getattr(snapshot, 'search_param_count', 0) or 0)}"
                ),
                "Рабочая зона: baseline, runtime, history, handoff и выпуск открываются справа во вкладках.",
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
        source_label = str(getattr(snapshot, "baseline_source_label", "") or getattr(snapshot, "baseline_source_kind", "") or "—")
        baseline_path = str(getattr(snapshot, "baseline_path", "") or "не найден")
        return "\n".join(
            [
                f"Активный baseline: {source_label}",
                f"Путь: {baseline_path}",
                f"Автообновление baseline: {'включено' if auto_update else 'выключено'}",
            ]
        )

    def _format_runtime_contract_summary_text(self) -> str:
        snapshot = self._contract_snapshot
        if snapshot is None:
            snapshot = self.runtime.contract_snapshot()
        objective_stack = ", ".join(tuple(getattr(snapshot, "objective_keys", ()) or ())) or "—"
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
                f"Активный режим: {mode_label}",
                f"Objective stack: {objective_stack}",
                f"Hard gate: {hard_gate}",
            ]
        )

    def _format_dashboard_pointer_text(self, dashboard: dict[str, Any]) -> str:
        pointer = dict(dashboard.get("latest_pointer") or {})
        if not bool(pointer.get("exists")):
            return (
                "Latest optimization pointer ещё не materialized.\n"
                "Выберите run в History / Finished Jobs / Packaging / Handoff и нажмите `Make latest pointer`."
            )
        lines = [
            f"pointer file: {pointer.get('pointer_path') or '—'}",
            (
                "target run: "
                f"{pointer.get('run_name') or '—'} | "
                f"{pointer.get('pipeline_mode') or '—'} / {pointer.get('backend') or '—'} | "
                f"{pointer.get('status_label') or pointer.get('status') or '—'}"
            ),
            (
                "meta: "
                f"selected_from={pointer.get('selected_from') or '—'} | "
                f"updated_at={pointer.get('updated_at') or '—'}"
            ),
            (
                "rows: "
                f"total={int(pointer.get('rows', 0) or 0)}, "
                f"done={int(pointer.get('done_count', 0) or 0)}, "
                f"errors={int(pointer.get('error_count', 0) or 0)}"
            ),
        ]
        if bool(pointer.get("selected_matches_pointer")):
            lines.append("selected run relation: current selection already matches latest_optimization.")
        elif self._selected_run_dir:
            lines.append("selected run relation: latest_optimization currently points to another run.")
        if not bool(pointer.get("pointer_in_history")):
            lines.append("history relation: pointer target is outside current workspace history snapshot.")
        elif pointer.get("result_path"):
            lines.append(f"results artifact: {pointer.get('result_path')}")
        return "\n".join(lines)

    def _format_selected_run_next_step_text(self, payload: dict[str, Any]) -> str:
        rows = tuple(payload.get("rows") or ())
        if not rows:
            return "Selected run next step summary пока недоступен."
        lines = [
            f"headline: {payload.get('headline') or '—'}",
            f"next action: {payload.get('next_action') or '—'}",
            "",
        ]
        for row in rows:
            status = str(row.get("status") or "info").strip().upper() or "INFO"
            lines.append(
                f"[{status}] {row.get('title') or 'step'} -> {row.get('action') or '—'}"
            )
            lines.append(str(row.get("summary") or ""))
            lines.append("")
        return "\n".join(lines).strip()

    def _format_dashboard_selection_text(self) -> str:
        if not self._selected_run_dir:
            return "Selected run context: run пока не выбран. Используйте History, Finished Jobs, Handoff или Packaging."
        details = self.runtime.selected_run_details(self._selected_run_dir)
        if details is None:
            return f"Selected run context: {self._selected_run_dir}\nRun уже недоступен в workspace history."
        summary = getattr(details, "summary")
        drift = self.runtime.contract_drift_summary(summary)
        packaging_row = self.runtime.selected_packaging_row(self._selected_run_dir)
        handoff_row = self.runtime.selected_handoff_row(self._selected_run_dir)
        latest_pointer = self.runtime.latest_pointer_summary()
        lines = [
            f"selected run: {summary.run_dir}",
            f"status: {summary.status_label} ({summary.status})",
            f"pipeline/backend: {summary.pipeline_mode} / {summary.backend}",
            f"objective keys: {', '.join(summary.objective_keys) or '—'}",
            f"results: {summary.result_path or 'not found'}",
        ]
        if bool(latest_pointer.get("selected_matches_pointer")):
            lines.append("latest pointer: this selected run is the current latest_optimization target")
        elif bool(latest_pointer.get("exists")):
            lines.append(
                "latest pointer: "
                f"{latest_pointer.get('run_name') or '—'}"
            )
        diff_bits = tuple(drift.get("diff_bits") or ())
        scope_payload = dict(drift.get("scope_payload") or {})
        if diff_bits:
            lines.append(
                "contract drift: " + ", ".join(
                    DRIFT_LABELS.get(str(bit), str(bit)) for bit in diff_bits
                )
            )
        else:
            lines.append("contract drift: none")
        if str(scope_payload.get("compatibility") or ""):
            lines.append(
                "problem scope compatibility: "
                + str(scope_payload.get("compatibility") or "")
            )
        if packaging_row is not None:
            lines.append(
                "packaging state: "
                f"{packaging_row.get('ready_state') or '—'} | "
                f"truth={int(packaging_row.get('truth_ready_rows', 0) or 0)} | "
                f"verify={int(packaging_row.get('verification_pass_rows', 0) or 0)} | "
                f"risk={int(packaging_row.get('interference_rows', 0) or 0)}"
            )
        if handoff_row is not None:
            lines.append(
                "handoff state: "
                f"preset={handoff_row.get('preset') or '—'} | "
                f"score={float(handoff_row.get('quality_score', 0.0) or 0.0):.1f} | "
                f"budget={int(handoff_row.get('budget', 0) or 0)} | "
                f"seeds={int(handoff_row.get('seeds', 0) or 0)}"
            )
        return "\n".join(lines)

    def _format_selected_contract_drift_text(self) -> str:
        if not self._selected_run_dir:
            return (
                "Исторический run не выбран.\n"
                "Выберите run во вкладке History, Finished Jobs, Handoff или Packaging, "
                "чтобы сравнить его objective contract и problem scope с текущим launch context."
            )
        details = self.runtime.selected_run_details(self._selected_run_dir)
        if details is None:
            return "Выбранный run больше не найден в workspace history."
        summary = getattr(details, "summary")
        drift = self.runtime.contract_drift_summary(summary)
        diff_bits = tuple(str(bit) for bit in (drift.get("diff_bits") or ()) if str(bit).strip())
        scope_payload = dict(drift.get("scope_payload") or {})
        baseline_compatibility = str(drift.get("baseline_compatibility") or "")

        def _compat_text(value: str) -> str:
            normalized = str(value or "").strip()
            if not normalized:
                return "n/a"
            return normalized

        lines = [
            f"selected run: {summary.run_dir}",
            f"pipeline/status: {summary.pipeline_mode} / {summary.status_label}",
            (
                "selected contract: "
                f"objectives={', '.join(tuple(drift.get('selected_objective_keys') or ())) or '—'} | "
                f"penalty={drift.get('selected_penalty_key') or '—'} | "
                f"tol={drift.get('selected_penalty_tol') if drift.get('selected_penalty_tol') is not None else '—'}"
            ),
            (
                "current launch contract: "
                f"objectives={', '.join(tuple(drift.get('current_objective_keys') or ())) or '—'} | "
                f"penalty={drift.get('current_penalty_key') or '—'} | "
                f"tol={drift.get('current_penalty_tol') if drift.get('current_penalty_tol') is not None else '—'}"
            ),
        ]
        if diff_bits:
            lines.append(
                "objective-contract drift: "
                + ", ".join(DRIFT_LABELS.get(bit, bit) for bit in diff_bits)
            )
        else:
            lines.append("objective-contract drift: none")
        lines.append(
            "problem scope: "
            f"run={drift.get('selected_problem_hash') or '—'} | "
            f"current={drift.get('current_problem_hash') or '—'} | "
            f"compatibility={_compat_text(scope_payload.get('compatibility', ''))}"
        )
        lines.append(
            "hash mode: "
            f"run={drift.get('selected_problem_hash_mode') or '—'} | "
            f"current={drift.get('current_problem_hash_mode') or '—'} | "
            f"compatibility={_compat_text(scope_payload.get('mode_compatibility', ''))}"
        )
        lines.append(
            "baseline source: "
            f"run={drift.get('selected_baseline_label') or drift.get('selected_baseline_path') or '—'} | "
            f"current={drift.get('current_baseline_label') or drift.get('current_baseline_path') or '—'} | "
            f"compatibility={_compat_text(baseline_compatibility)}"
        )
        lines.append("")
        if str(scope_payload.get("compatibility") or "") == "different" or str(
            scope_payload.get("mode_compatibility") or ""
        ) == "different":
            lines.append(
                "Operator note: scope differs from the current launch contract. "
                "Resume/cache/baseline guards will treat this as another optimization problem."
            )
        elif diff_bits:
            lines.append(
                "Operator note: scope matches, but objective contract differs. "
                "Use `Apply selected contract`, если хотите честный apples-to-apples relaunch."
            )
        else:
            lines.append(
                "Operator note: selected run is aligned with the current launch contract and scope."
            )
        return "\n".join(lines)

    def _format_launch_profile_text(self) -> str:
        summary = self.runtime.launch_profile_summary()
        lines = [
            f"profile: {summary.get('profile_label') or '—'}",
            f"pipeline/backend: {summary.get('launch_pipeline') or '—'} / {summary.get('backend') or '—'}",
            str(summary.get("description") or "Профиль задаёт стартовый runtime preset для operator workflow."),
        ]
        if str(summary.get("launch_pipeline") or "") == "staged":
            lines.append(
                "stage knobs: "
                f"minutes={float(summary.get('stage_minutes', 0.0) or 0.0):.1f}, "
                f"jobs={int(summary.get('stage_jobs', 0) or 0)}, "
                f"seed_candidates={int(summary.get('seed_candidates', 0) or 0)}, "
                f"seed_conditions={int(summary.get('seed_conditions', 0) or 0)}, "
                f"warmstart={summary.get('warmstart_mode') or '—'}"
            )
            lines.append(
                "runtime flags: "
                f"adaptive_eps={'on' if bool(summary.get('adaptive_influence_eps')) else 'off'}, "
                f"stage_resume={'on' if bool(summary.get('resume_stage')) else 'off'}"
            )
        else:
            lines.append(
                "coordinator knobs: "
                f"budget={int(summary.get('budget', 0) or 0)}, "
                f"max_inflight={int(summary.get('max_inflight', 0) or 0)}, "
                f"q={int(summary.get('q', 0) or 0)}, "
                f"export_every={int(summary.get('export_every', 0) or 0)}"
            )
            lines.append(
                "cluster knobs: "
                f"dask_workers={int(summary.get('dask_workers', 0) or 0)} x "
                f"{int(summary.get('dask_threads_per_worker', 0) or 0)} threads, "
                f"ray_eval={int(summary.get('ray_num_evaluators', 0) or 0)}, "
                f"ray_prop={int(summary.get('ray_num_proposers', 0) or 0)}"
            )
            lines.append(
                "resume flags: "
                f"coord_resume={'on' if bool(summary.get('resume_coord')) else 'off'}"
            )
        drift_keys = tuple(summary.get("drift_keys") or ())
        if drift_keys:
            lines.append("")
            lines.append("manual overrides since preset:")
            lines.append(", ".join(str(key) for key in drift_keys))
        else:
            lines.append("")
            lines.append("Preset currently matches the live launch knobs.")
        return "\n".join(lines)

    def _format_launch_readiness_text(self, readiness: dict[str, Any]) -> str:
        rows = tuple(readiness.get("rows") or ())
        if not rows:
            return "Launch readiness snapshot пока недоступен."
        lines = [
            f"headline: {readiness.get('headline') or '—'}",
            (
                "status counts: "
                f"warn={int(readiness.get('warn_count', 0) or 0)}, "
                f"info={int(readiness.get('info_count', 0) or 0)}, "
                f"ok={int(readiness.get('ok_count', 0) or 0)}"
            ),
            f"next recommended surface: {readiness.get('next_action') or 'Runtime'}",
            "",
        ]
        for row in rows:
            status = str(row.get("status") or "info").strip().upper() or "INFO"
            lines.append(
                f"[{status}] {row.get('title') or 'check'} -> {row.get('action') or 'Runtime'}"
            )
            lines.append(str(row.get("summary") or ""))
            lines.append("")
        return "\n".join(lines).strip()

    def _format_stage_runtime_text(self, rows: tuple[dict[str, Any], ...]) -> str:
        if not rows:
            return "StageRunner runtime policy пока недоступен."
        lines: list[str] = []
        for row in rows:
            if not bool(row.get("available")):
                lines.append(f"{row.get('stage_name')}: нет live audit/artifacts.")
                continue
            seed_count = int(row.get("seed_count", 0) or 0)
            target = int(row.get("target_seed_count", 0) or 0)
            lines.append(
                f"{row.get('stage_name')}: {row.get('summary_line') or row.get('policy_name')}\n"
                f"  seeds={seed_count}/{target} | mode={row.get('effective_mode')} | "
                f"underfill={row.get('underfill_message') or 'ok'}"
            )
        return "\n\n".join(lines)

    def _history_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for summary in self.runtime.history_summaries():
            rows.append(
                {
                    "run_dir": str(summary.run_dir),
                    "name": str(summary.run_dir.name),
                    "status": str(summary.status_label),
                    "pipeline": str(summary.pipeline_mode),
                    "backend": str(summary.backend),
                }
            )
        return rows

    def _format_handoff_overview_text(self) -> str:
        rows = self.runtime.handoff_overview_rows()
        if not rows:
            return "Сейчас в workspace нет staged runs с готовым coordinator handoff."
        lines: list[str] = []
        for idx, row in enumerate(rows[:8], start=1):
            lines.append(
                f"{idx}. {row.get('run')} | live={row.get('live_now')} | preset={row.get('preset')} | "
                f"score={float(row.get('quality_score', 0.0) or 0.0):.1f} | budget={int(row.get('budget', 0) or 0)} | "
                f"seeds={int(row.get('seeds', 0) or 0)} | pool={row.get('pool')} | full_ring={row.get('full_ring')}"
            )
            lines.append(
                f"   valid={int(row.get('valid_rows', 0) or 0)} | promotable={int(row.get('promotable', 0) or 0)} | "
                f"unique={int(row.get('unique', 0) or 0)} | fragments={int(row.get('fragments', 0) or 0)} | suite={row.get('suite')}"
            )
        if len(rows) > 8:
            lines.append(f"... и ещё {len(rows) - 8} handoff rows в workspace history.")
        return "\n".join(lines)

    def _handoff_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row in self.runtime.handoff_overview_rows():
            rows.append(
                {
                    "run_dir": str(row.get("__run_dir") or ""),
                    "name": str(row.get("run") or ""),
                    "live": str(row.get("live_now") or ""),
                    "preset": str(row.get("preset") or ""),
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
            return "Сейчас в workspace нет staged runs с handoff-plan для seeded continuation."
        filters = dict(summary.get("filters") or {})
        return "\n".join(
            [
                f"candidates in view: {int(summary.get('total_candidates', 0) or 0)}",
                (
                    "readiness: "
                    f"done={int(summary.get('done_candidates', 0) or 0)}, "
                    f"full_ring={int(summary.get('full_ring_candidates', 0) or 0)}, "
                    f"live={int(summary.get('live_candidates', 0) or 0)}"
                ),
                f"seed inventory: total={int(summary.get('seed_total', 0) or 0)}",
                (
                    "best ranked candidate: "
                    f"{summary.get('best_run') or '—'} | preset={summary.get('best_preset') or '—'} | "
                    f"score={float(summary.get('best_score', 0.0) or 0.0):.1f}"
                ),
                (
                    "filters: "
                    f"sort={summary.get('sort_mode') or '—'}, "
                    f"full_ring_only={'on' if bool(filters.get('full_ring_only')) else 'off'}, "
                    f"done_only={'on' if bool(filters.get('done_only')) else 'off'}, "
                    f"min_seeds={int(filters.get('min_seeds', 0) or 0)}"
                ),
            ]
        )

    def _format_handoff_ranking_text(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "После текущих handoff-фильтров подходящих staged continuation-кандидатов не осталось."
        lines: list[str] = []
        for idx, row in enumerate(rows[:8], start=1):
            lines.append(
                f"{idx}. {row.get('run')} | live={row.get('live_now')} | preset={row.get('preset')} | "
                f"score={float(row.get('quality_score', 0.0) or 0.0):.1f} | budget={int(row.get('budget', 0) or 0)} | "
                f"seeds={int(row.get('seeds', 0) or 0)}"
            )
            lines.append(
                f"   valid={int(row.get('valid_rows', 0) or 0)} | promotable={int(row.get('promotable', 0) or 0)} | "
                f"unique={int(row.get('unique', 0) or 0)} | pool={row.get('pool')} | "
                f"fragments={int(row.get('fragments', 0) or 0)} | full_ring={row.get('full_ring')}"
            )
        if len(rows) > 8:
            lines.append(f"... и ещё {len(rows) - 8} handoff candidates в текущем ranked view.")
        return "\n".join(lines)

    def _format_selected_handoff_text(self, details: object | None, row: dict[str, Any] | None) -> str:
        if details is None or row is None:
            return "Выберите staged run слева, чтобы увидеть handoff recommendation и continuation contract."
        summary = getattr(details, "summary")
        lines = [
            f"source staged run: {summary.run_dir}",
            f"status: {summary.status_label} ({summary.status})",
            (
                "handoff preset: "
                f"{summary.handoff_preset_tag or row.get('preset') or '—'} | "
                f"backend={summary.handoff_backend or '—'} | proposer={summary.handoff_proposer or '—'} | "
                f"q={int(summary.handoff_q or 0)}"
            ),
            (
                "continuation budget: "
                f"{int(summary.handoff_budget or 0)} | seed_count={int(summary.handoff_seed_count or 0)} | "
                f"suite={summary.handoff_suite_family or '—'}"
            ),
            (
                "seed bridge: "
                f"valid={int(summary.handoff_staged_rows_ok or 0)} | "
                f"promotable={int(summary.handoff_promotable_rows or 0)} | "
                f"unique={int(summary.handoff_unique_param_candidates or 0)} | "
                f"pool={summary.handoff_selection_pool or '—'}"
            ),
            (
                "full ring validation: "
                f"{'required' if bool(summary.handoff_requires_full_ring_validation) else 'optional'} | "
                f"has_full_ring={'yes' if bool(summary.handoff_has_full_ring) else 'no'} | "
                f"fragments={int(summary.handoff_fragment_count or 0)}"
            ),
        ]
        if summary.handoff_target_run_dir is not None:
            lines.append(f"target run dir: {summary.handoff_target_run_dir}")
        if summary.handoff_reason_lines:
            lines.append("")
            lines.append("handoff reasoning:")
            lines.extend(str(line) for line in summary.handoff_reason_lines)
        return "\n".join(lines)

    def _format_handoff_runtime_text(self, row: dict[str, Any] | None) -> str:
        if row is None:
            return "Live continuation state появится здесь для выбранного handoff-кандидата."
        lines = [
            f"selected candidate: {row.get('run') or '—'}",
            f"live now: {row.get('live_now') or '—'}",
        ]
        active_context = self.runtime.active_launch_context()
        if str(row.get("live_now") or "") == "LIVE":
            lines.append("handoff status: active seeded coordinator continuation")
            source_run_dir = str(active_context.get("source_run_dir") or "")
            if source_run_dir:
                lines.append(f"active source run dir: {source_run_dir}")
        else:
            lines.append("handoff status: not running right now")
        surface = self.runtime.active_job_surface()
        runtime_summary = dict(surface.get("runtime_summary") or {})
        if runtime_summary and str(row.get("live_now") or "") == "LIVE":
            lines.append("")
            lines.extend(str(item) for item in surface.get("captions") or ())
        else:
            lines.append("")
            lines.append("Use `Start handoff`, чтобы перевести selected staged run в coordinator continuation.")
        return "\n".join(lines)

    def _finished_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row in self.runtime.finished_job_rows():
            rows.append(
                {
                    "run_dir": str(row.get("run_dir") or ""),
                    "name": str(row.get("name") or ""),
                    "status": str(row.get("status_label") or row.get("status") or ""),
                    "pipeline": str(row.get("pipeline") or ""),
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
            return "В workspace пока нет finished optimization jobs с доступной historical сводкой."
        status_counts = ", ".join(
            f"{name}={count}" for name, count in tuple(overview.get("status_counts") or ())
        ) or "—"
        pipeline_counts = ", ".join(
            f"{name}={count}" for name, count in tuple(overview.get("pipeline_counts") or ())
        ) or "—"
        filters = dict(overview.get("filters") or {})
        return "\n".join(
            [
                f"jobs in view: {int(overview.get('total_jobs', 0) or 0)}",
                f"jobs with results: {int(overview.get('jobs_with_results', 0) or 0)}",
                (
                    "packaging rows: "
                    f"with_packaging={int(overview.get('rows_with_packaging_total', 0) or 0)}, "
                    f"truth_ready={int(overview.get('truth_ready_rows_total', 0) or 0)}, "
                    f"verification_pass={int(overview.get('verification_rows_total', 0) or 0)}"
                ),
                (
                    "job readiness: "
                    f"truth_ready_jobs={int(overview.get('truth_ready_jobs', 0) or 0)}, "
                    f"verification_jobs={int(overview.get('verification_pass_jobs', 0) or 0)}, "
                    f"interference_jobs={int(overview.get('interference_jobs', 0) or 0)}, "
                    f"fallback_jobs={int(overview.get('runtime_fallback_jobs', 0) or 0)}"
                ),
                f"status counts: {status_counts}",
                f"pipeline counts: {pipeline_counts}",
                (
                    "filters: "
                    f"sort={overview.get('sort_mode') or '—'}, "
                    f"done_only={'on' if bool(filters.get('done_only')) else 'off'}, "
                    f"truth_only={'on' if bool(filters.get('truth_ready_only')) else 'off'}, "
                    f"verification_only={'on' if bool(filters.get('verification_only')) else 'off'}"
                ),
            ]
        )

    def _format_finished_ranking_text(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "После текущих finished-job фильтров подходящих run не осталось."
        lines: list[str] = []
        for idx, row in enumerate(rows[:8], start=1):
            lines.append(
                f"{idx}. {row.get('name')} | {row.get('status_label')} | {row.get('pipeline')} | "
                f"ready={row.get('ready_state')} | truth={int(row.get('truth_ready_rows', 0) or 0)} | "
                f"verify={int(row.get('verification_pass_rows', 0) or 0)} | "
                f"risk={int(row.get('interference_rows', 0) or 0)}"
            )
            lines.append(
                f"   packaging={int(row.get('rows_with_packaging', 0) or 0)}/{int(row.get('rows_considered', 0) or 0)} | "
                f"complete={int(row.get('packaging_complete_rows', 0) or 0)} | "
                f"fallback={int(row.get('runtime_fallback_rows', 0) or 0)} | "
                f"status_counts={row.get('status_counts_text') or 'n/a'}"
            )
        if len(rows) > 8:
            lines.append(f"... и ещё {len(rows) - 8} finished jobs в текущем filtered view.")
        return "\n".join(lines)

    def _format_finished_packaging_text(self, details: object | None, row: dict[str, Any] | None) -> str:
        if details is None or row is None:
            return "Выберите finished run слева, чтобы увидеть packaging snapshot и readiness signals."
        packaging = getattr(details, "packaging_snapshot")
        status_counts = ", ".join(
            f"{name}={count}" for name, count in tuple(getattr(packaging, "status_counts", ()) or ())
        ) or "—"
        return "\n".join(
            [
                f"selected ready-state: {row.get('ready_state') or '—'}",
                (
                    "packaging rows: "
                    f"{int(getattr(packaging, 'rows_with_packaging', 0) or 0)} / "
                    f"{int(getattr(packaging, 'rows_considered', 0) or 0)} done-rows"
                ),
                f"truth-ready rows: {int(getattr(packaging, 'packaging_truth_ready_rows', 0) or 0)}",
                f"verification-pass rows: {int(getattr(packaging, 'packaging_verification_pass_rows', 0) or 0)}",
                f"complete rows: {int(getattr(packaging, 'packaging_complete_rows', 0) or 0)}",
                f"runtime fallback rows: {int(getattr(packaging, 'runtime_fallback_rows', 0) or 0)}",
                (
                    "interference rows: "
                    f"spring-host={int(getattr(packaging, 'spring_host_interference_rows', 0) or 0)}, "
                    f"spring-pair={int(getattr(packaging, 'spring_pair_interference_rows', 0) or 0)}"
                ),
                f"packaging statuses: {status_counts}",
            ]
        )

    def _format_finished_summary_text(self, details: object | None, row: dict[str, Any] | None) -> str:
        if details is None or row is None:
            return "Selected finished-job summary пока недоступен."
        summary = getattr(details, "summary")
        result_path = summary.result_path if summary.result_path is not None else None
        contract_text = ", ".join(summary.objective_keys) or "—"
        return "\n".join(
            [
                f"run_dir: {summary.run_dir}",
                f"pipeline/backend: {summary.pipeline_mode} / {summary.backend}",
                f"status: {summary.status_label} ({summary.status})",
                f"results: {result_path or 'not found'}",
                f"objective keys: {contract_text}",
                f"penalty: {summary.penalty_key or '—'} tol={summary.penalty_tol if summary.penalty_tol is not None else '—'}",
                f"problem hash mode: {summary.problem_hash_mode or '—'}",
                f"baseline source: {summary.baseline_source_label or summary.baseline_source_kind or '—'}",
                f"note: {summary.note or '—'}",
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
            return "Packaging snapshot пока не нашёл finished runs с доступными packaging metrics."
        filters = dict(overview.get("filters") or {})
        return "\n".join(
            [
                f"packaging runs in view: {int(overview.get('total_runs', 0) or 0)}",
                (
                    "readiness counts: "
                    f"truth_ready={int(overview.get('truth_ready_runs', 0) or 0)}, "
                    f"verification={int(overview.get('verification_runs', 0) or 0)}, "
                    f"zero_interference={int(overview.get('zero_interference_runs', 0) or 0)}, "
                    f"fallback={int(overview.get('fallback_runs', 0) or 0)}"
                ),
                (
                    "row totals: "
                    f"packaging={int(overview.get('packaging_rows_total', 0) or 0)}, "
                    f"truth_ready={int(overview.get('truth_ready_rows_total', 0) or 0)}, "
                    f"verification={int(overview.get('verification_rows_total', 0) or 0)}"
                ),
                (
                    "best ranked packaging run: "
                    f"{overview.get('best_run') or '—'} | ready_state={overview.get('best_ready_state') or '—'}"
                ),
                (
                    "filters: "
                    f"sort={overview.get('sort_mode') or '—'}, "
                    f"done_only={'on' if bool(filters.get('done_only')) else 'off'}, "
                    f"truth_only={'on' if bool(filters.get('truth_ready_only')) else 'off'}, "
                    f"verification_only={'on' if bool(filters.get('verification_only')) else 'off'}, "
                    f"zero_interference_only={'on' if bool(filters.get('zero_interference_only')) else 'off'}"
                ),
            ]
        )

    def _format_packaging_ranking_text(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "После текущих packaging-фильтров подходящих run не осталось."
        lines: list[str] = []
        for idx, row in enumerate(rows[:8], start=1):
            lines.append(
                f"{idx}. {row.get('name')} | {row.get('status_label')} | ready={row.get('ready_state')} | "
                f"truth={int(row.get('truth_ready_rows', 0) or 0)} | verify={int(row.get('verification_pass_rows', 0) or 0)} | "
                f"risk={int(row.get('interference_rows', 0) or 0)} | fallback={int(row.get('runtime_fallback_rows', 0) or 0)}"
            )
            lines.append(
                f"   packaging={int(row.get('rows_with_packaging', 0) or 0)}/{int(row.get('rows_considered', 0) or 0)} | "
                f"complete={int(row.get('packaging_complete_rows', 0) or 0)} | pipeline={row.get('pipeline') or '—'}"
            )
        if len(rows) > 8:
            lines.append(f"... и ещё {len(rows) - 8} packaging runs в текущем ranked view.")
        return "\n".join(lines)

    def _format_selected_packaging_text(self, details: object | None, row: dict[str, Any] | None) -> str:
        if details is None or row is None:
            return "Выберите packaging run слева, чтобы увидеть snapshot достаточности данных и geometry risk."
        packaging = getattr(details, "packaging_snapshot")
        status_counts = ", ".join(
            f"{name}={count}" for name, count in tuple(getattr(packaging, "status_counts", ()) or ())
        ) or "—"
        return "\n".join(
            [
                f"ready state: {row.get('ready_state') or '—'}",
                f"rows with packaging: {int(getattr(packaging, 'rows_with_packaging', 0) or 0)} / {int(getattr(packaging, 'rows_considered', 0) or 0)}",
                f"packaging complete rows: {int(getattr(packaging, 'packaging_complete_rows', 0) or 0)}",
                f"truth-ready rows: {int(getattr(packaging, 'packaging_truth_ready_rows', 0) or 0)}",
                f"verification-pass rows: {int(getattr(packaging, 'packaging_verification_pass_rows', 0) or 0)}",
                f"runtime fallback rows: {int(getattr(packaging, 'runtime_fallback_rows', 0) or 0)}",
                (
                    "interference rows: "
                    f"spring-host={int(getattr(packaging, 'spring_host_interference_rows', 0) or 0)}, "
                    f"spring-pair={int(getattr(packaging, 'spring_pair_interference_rows', 0) or 0)}"
                ),
                f"packaging status counts: {status_counts}",
            ]
        )

    def _format_packaging_contract_text(self, details: object | None, row: dict[str, Any] | None) -> str:
        if details is None or row is None:
            return "Packaging contract context появится здесь для выбранного run."
        summary = getattr(details, "summary")
        return "\n".join(
            [
                f"run_dir: {summary.run_dir}",
                f"pipeline/backend: {summary.pipeline_mode} / {summary.backend}",
                f"objective keys: {', '.join(summary.objective_keys) or '—'}",
                f"penalty: {summary.penalty_key or '—'} tol={summary.penalty_tol if summary.penalty_tol is not None else '—'}",
                f"problem hash: {summary.problem_hash or '—'}",
                f"problem hash mode: {summary.problem_hash_mode or '—'}",
                f"baseline source: {summary.baseline_source_label or summary.baseline_source_kind or '—'}",
                f"results artifact: {summary.result_path or 'not found'}",
                f"note: {summary.note or '—'}",
            ]
        )

    def _history_details_tuple(self, details: object | None) -> tuple[str, str, str, str, str]:
        if details is None:
            empty = "Выберите run в списке слева."
            return empty, empty, empty, empty, ""
        summary = getattr(details, "summary")
        packaging = getattr(details, "packaging_snapshot")
        stage_rows = tuple(getattr(details, "stage_policy_rows") or ())
        summary_lines = [
            f"run_dir: {summary.run_dir}",
            f"status: {summary.status_label} ({summary.status})",
            f"pipeline/backend: {summary.pipeline_mode} / {summary.backend}",
            f"rows: {summary.row_count} | done={summary.done_count} | running={summary.running_count} | errors={summary.error_count}",
            f"note: {summary.note or '—'}",
        ]
        contract_lines = [
            f"objective keys: {', '.join(summary.objective_keys) or '—'}",
            f"penalty: {summary.penalty_key or '—'} tol={summary.penalty_tol if summary.penalty_tol is not None else '—'}",
            f"problem hash: {summary.problem_hash or '—'}",
            f"problem hash mode: {summary.problem_hash_mode or '—'}",
            f"baseline source: {summary.baseline_source_label or summary.baseline_source_kind or '—'}",
        ]
        packaging_lines = [
            f"rows with packaging: {int(packaging.rows_with_packaging)} / {int(packaging.rows_considered)}",
            f"truth-ready: {int(packaging.packaging_truth_ready_rows)}",
            f"verification pass: {int(packaging.packaging_verification_pass_rows)}",
            f"runtime fallback: {int(packaging.runtime_fallback_rows)}",
            f"host interference: {int(packaging.spring_host_interference_rows)}",
            f"pair interference: {int(packaging.spring_pair_interference_rows)}",
        ]
        stage_lines: list[str] = []
        if str(summary.pipeline_mode) == "staged":
            stage_lines.append(
                f"handoff: {'available' if bool(summary.handoff_available) else 'not available'} | "
                f"preset={summary.handoff_preset_tag or '—'} | budget={int(summary.handoff_budget or 0)} | seeds={int(summary.handoff_seed_count or 0)}"
            )
            if summary.handoff_reason_lines:
                stage_lines.append("handoff reason:")
                stage_lines.extend(f"  - {line}" for line in summary.handoff_reason_lines)
            for row in stage_rows:
                if not bool(row.get("available")):
                    continue
                stage_lines.append(
                    f"{row.get('stage_name')}: {row.get('summary_line') or row.get('policy_name')} | "
                    f"seeds={int(row.get('seed_count', 0) or 0)} | "
                    f"underfill={row.get('underfill_message') or 'ok'}"
                )
        else:
            stage_lines.append("Для coordinator run handoff/stage policy не применяется напрямую.")
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
        self.status_var.set("Snapshot desktop optimizer center обновлён.")

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

    def on_history_selection_changed(self) -> None:
        self._selected_run_dir = self.history_tab.selected_run_dir()
        self.refresh_contract()
        self.refresh_history()
        self.refresh_finished_jobs()
        self.refresh_handoff()
        self.refresh_packaging()
        self.refresh_dashboard()

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
        self.refresh_contract()
        self.refresh_history()
        self.refresh_finished_jobs()
        self.refresh_handoff()
        self.refresh_packaging()
        self.refresh_dashboard()

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
        self.refresh_contract()
        self.refresh_history()
        self.refresh_finished_jobs()
        self.refresh_handoff()
        self.refresh_packaging()
        self.refresh_dashboard()

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
        self.refresh_contract()
        self.refresh_history()
        self.refresh_finished_jobs()
        self.refresh_handoff()
        self.refresh_packaging()
        self.refresh_dashboard()

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
        if action in {"Contract", "Contract drift"}:
            self.show_contract_tab()
        elif action == "History":
            self.show_history_tab()
        elif action == "Finished Jobs":
            self.show_finished_tab()
        elif action == "Handoff":
            self.show_handoff_tab()
        elif action == "Packaging":
            self.show_packaging_tab()
        else:
            self.show_runtime_tab()
        self.status_var.set(
            f"Launch readiness рекомендует перейти к поверхности: {action or 'Runtime'}."
        )

    def follow_selected_run_next_step(self) -> None:
        self._sync_widget_state()
        payload = self.runtime.selected_run_next_step_summary(self._selected_run_dir)
        action_kind = str(payload.get("next_action_kind") or "show_history_tab").strip()
        action_label = str(payload.get("next_action") or "History").strip() or "History"
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
        self.status_var.set(
            f"Selected run next step рекомендует перейти к поверхности: {action_label}."
        )

    def open_selected_run_dir(self) -> None:
        if not self._selected_run_dir:
            return
        try:
            self._open_path(Path(self._selected_run_dir))
        except Exception as exc:
            messagebox.showerror(
                "Desktop Optimizer Center",
                f"Не удалось открыть run dir:\n{exc}",
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
                "Desktop Optimizer Center",
                f"Не удалось открыть лог:\n{exc}",
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
                "Desktop Optimizer Center",
                "У выбранного run пока нет results artifact.",
            )
            return
        try:
            self._open_path(path)
        except Exception as exc:
            messagebox.showerror(
                "Desktop Optimizer Center",
                f"Не удалось открыть results artifact:\n{exc}",
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
                "Desktop Optimizer Center",
                "У выбранного run нет objective contract artifact.",
            )
            return
        try:
            self._open_path(path)
        except Exception as exc:
            messagebox.showerror(
                "Desktop Optimizer Center",
                f"Не удалось открыть objective contract:\n{exc}",
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
                "Desktop Optimizer Center",
                "У выбранного run нет handoff plan artifact.",
            )
            return
        try:
            self._open_path(path)
        except Exception as exc:
            messagebox.showerror(
                "Desktop Optimizer Center",
                f"Не удалось открыть handoff plan:\n{exc}",
            )

    def open_latest_optimization_pointer(self) -> None:
        pointer = self.runtime.latest_pointer_summary()
        if not bool(pointer.get("exists")):
            messagebox.showinfo(
                "Desktop Optimizer Center",
                "latest_optimization pointer пока не создан.",
            )
            return
        try:
            self._open_path(Path(str(pointer.get("pointer_path") or "")))
        except Exception as exc:
            messagebox.showerror(
                "Desktop Optimizer Center",
                f"Не удалось открыть latest_optimization pointer:\n{exc}",
            )

    def make_selected_run_latest_pointer(self) -> None:
        details = (
            self.runtime.selected_run_details(self._selected_run_dir)
            if self._selected_run_dir
            else None
        )
        if details is None:
            messagebox.showinfo(
                "Desktop Optimizer Center",
                "Сначала выберите run, который нужно сделать latest_optimization pointer.",
            )
            return
        summary = getattr(details, "summary")
        pointer = self.runtime.save_run_pointer(
            summary,
            selected_from="desktop_optimizer_center",
        )
        self.status_var.set(
            "latest_optimization pointer перепривязан: "
            f"{pointer.get('run_name') or summary.run_dir.name}"
        )
        self.refresh_all()

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
                "Desktop Optimizer Center",
                "У выбранного run нет contract-полей для подстановки в launch context.",
            )
            return
        self._load_state_into_widgets()
        self.status_var.set(
            "Contract выбранного run подставлен в launch context: "
            + ", ".join(sorted(str(key) for key in updates))
        )
        self.refresh_all()
        self.notebook.select(self.contract_tab)

    def apply_launch_profile_label(self, label: str) -> None:
        self._sync_widget_state()
        profile_key = launch_profile_key_for_label(label)
        updates = self.runtime.apply_launch_profile(profile_key)
        if not updates:
            self.status_var.set(
                f"Launch profile уже активен без drift: {label or profile_key}"
            )
            self.refresh_all()
            self.notebook.select(self.runtime_tab)
            return
        self._load_state_into_widgets()
        self.status_var.set(
            "Launch profile применён: "
            f"{label or profile_key} ({len(updates)} knobs updated)"
        )
        self.refresh_all()
        self.notebook.select(self.runtime_tab)

    def launch_job(self) -> None:
        self._sync_widget_state()
        try:
            job = self.runtime.start_job()
        except Exception as exc:
            messagebox.showerror(
                "Desktop Optimizer Center",
                f"Не удалось запустить оптимизацию:\n{exc}",
            )
            return
        self.status_var.set(f"Запуск создан: {getattr(job, 'run_dir', '')}")
        self.refresh_all()
        self.notebook.select(self.runtime_tab)

    def soft_stop_job(self) -> None:
        if self.runtime.request_soft_stop():
            self.status_var.set("Запрошена мягкая остановка текущего optimization job.")
            self.refresh_all()

    def hard_stop_job(self) -> None:
        if self.runtime.request_hard_stop():
            self.status_var.set("Отправлена остановка optimization job (STOP + terminate).")
        else:
            self.status_var.set("Процесс остановлен принудительно.")
        self.refresh_all()

    def clear_job_status(self) -> None:
        self.runtime.clear_finished_job()
        self.status_var.set("Статус текущего optimization job очищен.")
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
                "Desktop Optimizer Center",
                "Handoff доступен только для staged run.",
            )
            return
        if not bool(summary.handoff_available):
            messagebox.showinfo(
                "Desktop Optimizer Center",
                "Для этого staged run coordinator handoff пока не собран.",
            )
            return
        try:
            job = self.runtime.start_handoff(summary.run_dir)
        except Exception as exc:
            messagebox.showerror(
                "Desktop Optimizer Center",
                f"Не удалось запустить handoff:\n{exc}",
            )
            return
        self.status_var.set(f"Handoff запущен: {getattr(job, 'run_dir', '')}")
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
