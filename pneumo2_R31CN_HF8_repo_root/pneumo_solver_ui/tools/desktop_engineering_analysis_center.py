from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from pneumo_solver_ui.desktop_engineering_analysis_model import (
    EngineeringAnalysisArtifact,
    EngineeringAnalysisJobResult,
    EngineeringAnalysisSnapshot,
    EngineeringSensitivityRow,
)
from pneumo_solver_ui.desktop_engineering_analysis_runtime import DesktopEngineeringAnalysisRuntime
from pneumo_solver_ui.desktop_ui_core import build_scrolled_text, build_scrolled_treeview
from pneumo_solver_ui.release_info import get_release


ANALYSIS_COMMAND_OPEN_TARGETS: tuple[tuple[str, str], ...] = (
    ("selected_contract", "Открыть HO-007 selected_run_contract.json"),
    ("run_dir", "Открыть selected run_dir"),
    ("selected_artifact", "Открыть selected artifact"),
    ("evidence_manifest", "Открыть HO-009 evidence manifest"),
    ("analysis_context", "Открыть HO-008 analysis_context.json"),
    ("animator_link", "Открыть HO-008 animator_link_contract.json"),
)


def _open_path(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def _status_text(value: str) -> str:
    labels = {
        "PASS": "готово",
        "READY": "готово",
        "PARTIAL": "частично",
        "MISSING": "нет данных",
        "BLOCKED": "заблокировано",
        "DEGRADED": "требует внимания",
        "FAILED": "ошибка",
        "FINISHED": "завершено",
        "MISSING_INPUTS": "нет входных данных",
    }
    raw = str(value or "").strip()
    return labels.get(raw.upper(), raw or "-")


def format_contract_banner(snapshot: EngineeringAnalysisSnapshot | None) -> str:
    if snapshot is None:
        return "Selected run contract: not loaded."
    parts = [f"contract={snapshot.contract_status or 'MISSING'}"]
    if snapshot.selected_run_contract_path:
        parts.append(f"path={snapshot.selected_run_contract_path}")
    if snapshot.selected_run_contract_hash:
        parts.append(f"hash={snapshot.selected_run_contract_hash[:12]}")
    if snapshot.blocking_states:
        parts.append("blocking=" + "; ".join(snapshot.blocking_states))
    return "Selected run contract: " + " | ".join(parts)


def format_selected_run_summary(snapshot: EngineeringAnalysisSnapshot | None) -> str:
    if snapshot is None or snapshot.selected_run_context is None:
        return "Selected run: not available."
    context = snapshot.selected_run_context
    return (
        f"Selected run: {context.run_id or '-'} | mode={context.mode or '-'} | "
        f"status={context.status or '-'} | hard_gate={context.hard_gate_key or '-'} | "
        f"baseline={context.active_baseline_hash[:12] if context.active_baseline_hash else '-'}"
    )


class DesktopEngineeringAnalysisCenter(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        runtime: DesktopEngineeringAnalysisRuntime,
    ) -> None:
        super().__init__(master, padding=10)
        self.runtime = runtime
        self.snapshot_state: EngineeringAnalysisSnapshot | None = None
        self._artifact_by_iid: dict[str, EngineeringAnalysisArtifact] = {}
        self._path_by_iid: dict[str, Path] = {}
        self._candidate_by_iid: dict[str, dict] = {}
        self._sensitivity_by_iid: dict[str, EngineeringSensitivityRow] = {}
        self._worker_thread: threading.Thread | None = None

        self.release_var = tk.StringVar(master=self, value=f"Release: {get_release(default='unknown')}")
        self.summary_var = tk.StringVar(master=self, value="Engineering analysis: waiting for snapshot.")
        self.contract_var = tk.StringVar(master=self, value="Selected run contract: not loaded.")
        self.selected_run_var = tk.StringVar(master=self, value="Selected run: not available.")
        self.evidence_var = tk.StringVar(master=self, value="Evidence: not exported.")
        self.status_var = tk.StringVar(master=self, value="Engineering Analysis Center ready.")
        self.candidate_ready_only_var = tk.BooleanVar(master=self, value=False)
        self.candidate_filter_summary_var = tk.StringVar(master=self, value="HO-007 candidates: not loaded.")
        self.command_var = tk.StringVar(master=self, value=ANALYSIS_COMMAND_OPEN_TARGETS[0][1])

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(
            title_box,
            text="Engineering Analysis / Calibration / Influence",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(title_box, textvariable=self.summary_var, justify="left", wraplength=760).pack(anchor="w", pady=(2, 0))
        ttk.Label(title_box, textvariable=self.release_var, justify="left").pack(anchor="w", pady=(2, 0))

        actions = ttk.Frame(header)
        actions.pack(side="right", anchor="ne")
        self.btn_refresh = ttk.Button(actions, text="Обновить", command=self.refresh)
        self.btn_refresh.pack(side="left")
        self.btn_open_selected = ttk.Button(actions, text="Открыть выбранное", command=self._open_selected)
        self.btn_open_selected.pack(side="left", padx=(8, 0))
        self.btn_export_ho007 = ttk.Button(actions, text="Экспорт HO-007", command=self._export_selected_run_contract_bridge)
        self.btn_export_ho007.pack(side="left", padx=(8, 0))
        self.btn_export_evidence = ttk.Button(actions, text="Экспорт evidence", command=self._export_diagnostics_evidence)
        self.btn_export_evidence.pack(side="left", padx=(8, 0))
        self.btn_animator_link = ttk.Button(actions, text="Animator link", command=self._export_animator_link)
        self.btn_animator_link.pack(side="left", padx=(8, 0))
        self.btn_system_influence = ttk.Button(actions, text="System Influence", command=self._run_system_influence)
        self.btn_system_influence.pack(side="left", padx=(8, 0))
        self.btn_full_report = ttk.Button(actions, text="Full Report", command=self._run_full_report)
        self.btn_full_report.pack(side="left", padx=(8, 0))
        self.btn_param_staging = ttk.Button(actions, text="Influence Staging", command=self._run_param_staging)
        self.btn_param_staging.pack(side="left", padx=(8, 0))
        self.btn_diagnostics = ttk.Button(actions, text="Собрать диагностику", command=self._launch_full_diagnostics_gui)
        self.btn_diagnostics.pack(side="left", padx=(8, 0))

        workspace = ttk.Panedwindow(self, orient="horizontal")
        workspace.pack(fill="both", expand=True)

        left_column = ttk.Frame(workspace)
        left_column.columnconfigure(0, weight=1)
        left_column.rowconfigure(0, weight=1)
        artifact_box = ttk.LabelFrame(left_column, text="Study / artifacts", padding=8)
        artifact_box.grid(row=0, column=0, sticky="nsew")
        artifact_box.columnconfigure(0, weight=1)
        artifact_box.rowconfigure(2, weight=1)
        command_bar = ttk.Frame(artifact_box)
        command_bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        command_bar.columnconfigure(1, weight=1)
        ttk.Label(command_bar, text="Command").grid(row=0, column=0, sticky="w")
        self.command_combo = ttk.Combobox(
            command_bar,
            textvariable=self.command_var,
            values=[label for _key, label in ANALYSIS_COMMAND_OPEN_TARGETS],
            state="readonly",
            width=44,
        )
        self.command_combo.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.btn_open_command = ttk.Button(
            command_bar,
            text="Открыть",
            command=self._run_command_surface_action,
        )
        self.btn_open_command.grid(row=0, column=2, sticky="e")
        candidate_filter_bar = ttk.Frame(artifact_box)
        candidate_filter_bar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Checkbutton(
            candidate_filter_bar,
            text="READY only",
            variable=self.candidate_ready_only_var,
            command=self._refresh_candidate_filter,
        ).pack(side="left")
        ttk.Label(
            candidate_filter_bar,
            textvariable=self.candidate_filter_summary_var,
        ).pack(side="left", padx=(10, 0))
        artifact_frame, self.artifact_tree = build_scrolled_treeview(
            artifact_box,
            columns=("status", "category", "path"),
            show="tree headings",
            height=18,
        )
        self.artifact_tree.heading("#0", text="Artifact")
        self.artifact_tree.heading("status", text="Status")
        self.artifact_tree.heading("category", text="Category")
        self.artifact_tree.heading("path", text="Path")
        self.artifact_tree.column("#0", width=260, anchor="w")
        self.artifact_tree.column("status", width=110, anchor="w")
        self.artifact_tree.column("category", width=130, anchor="w")
        self.artifact_tree.column("path", width=380, anchor="w")
        artifact_frame.grid(row=2, column=0, sticky="nsew")
        self.artifact_tree.bind("<<TreeviewSelect>>", self._on_artifact_select)
        self.artifact_tree.bind("<Double-1>", lambda _event: self._open_selected())

        right_column = ttk.Frame(workspace)
        right_column.columnconfigure(0, weight=1)
        right_column.rowconfigure(0, weight=1)
        right_pane = ttk.Panedwindow(right_column, orient="vertical")
        right_pane.grid(row=0, column=0, sticky="nsew")

        report_box = ttk.Frame(right_pane)
        report_box.columnconfigure(0, weight=1)
        report_box.rowconfigure(1, weight=1)
        summary_box = ttk.LabelFrame(report_box, text="Report / provenance", padding=8)
        summary_box.grid(row=0, column=0, sticky="ew")
        ttk.Label(summary_box, textvariable=self.contract_var, wraplength=720, justify="left").pack(anchor="w")
        ttk.Label(summary_box, textvariable=self.selected_run_var, wraplength=720, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(summary_box, textvariable=self.evidence_var, wraplength=720, justify="left").pack(anchor="w", pady=(4, 0))

        sensitivity_box = ttk.LabelFrame(report_box, text="Sensitivity summary", padding=8)
        sensitivity_box.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        sensitivity_box.columnconfigure(0, weight=1)
        sensitivity_box.rowconfigure(0, weight=1)
        sens_frame, self.sensitivity_tree = build_scrolled_treeview(
            sensitivity_box,
            columns=("group", "score", "status", "metric", "elasticity", "eps"),
            show="headings",
            height=10,
        )
        for col, title, width in (
            ("group", "Group", 120),
            ("score", "Score", 90),
            ("status", "Status", 90),
            ("metric", "Strongest metric", 180),
            ("elasticity", "Elasticity", 100),
            ("eps", "eps", 100),
        ):
            self.sensitivity_tree.heading(col, text=title)
            self.sensitivity_tree.column(col, width=width, anchor="w")
        sens_frame.grid(row=0, column=0, sticky="nsew")
        self.sensitivity_tree.bind("<<TreeviewSelect>>", self._on_sensitivity_select)

        details_box = ttk.LabelFrame(right_pane, text="Details / log", padding=8)
        details_box.columnconfigure(0, weight=1)
        details_box.rowconfigure(0, weight=1)
        detail_frame, self.detail_text = build_scrolled_text(details_box, height=10, wrap="word")
        detail_frame.grid(row=0, column=0, sticky="nsew")
        log_frame, self.log_text = build_scrolled_text(details_box, height=8, wrap="word")
        log_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.detail_text.configure(state="disabled")
        self.log_text.configure(state="disabled")

        right_pane.add(report_box, weight=3)
        right_pane.add(details_box, weight=2)
        workspace.add(left_column, weight=2)
        workspace.add(right_column, weight=3)

        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(footer, mode="determinate", length=180)
        self.progress.pack(side="right", padx=(8, 8))
        ttk.Sizegrip(footer).pack(side="right")

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", str(text or ""))
        widget.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        if self.log_text.index("end-1c") != "1.0":
            self.log_text.insert("end", "\n")
        self.log_text.insert("end", str(text or ""))
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def refresh(self) -> None:
        try:
            snapshot = self.runtime.snapshot()
        except Exception as exc:
            self.status_var.set(f"Snapshot failed: {type(exc).__name__}: {exc!s}")
            messagebox.showerror("Engineering Analysis", f"Не удалось обновить snapshot:\n{exc!s}")
            return
        self.snapshot_state = snapshot
        self._populate_snapshot(snapshot)
        self.status_var.set("Snapshot refreshed.")

    def _populate_snapshot(self, snapshot: EngineeringAnalysisSnapshot) -> None:
        self._artifact_by_iid.clear()
        self._path_by_iid.clear()
        self._candidate_by_iid.clear()
        self._sensitivity_by_iid.clear()
        self.artifact_tree.delete(*self.artifact_tree.get_children())
        self.sensitivity_tree.delete(*self.sensitivity_tree.get_children())

        self.summary_var.set(
            " | ".join(
                (
                    f"analysis={_status_text(snapshot.status)}",
                    f"influence={_status_text(snapshot.influence_status)}",
                    f"calibration={_status_text(snapshot.calibration_status)}",
                    f"compare={_status_text(snapshot.compare_status)}",
                )
            )
        )
        self.contract_var.set(format_contract_banner(snapshot))
        self.selected_run_var.set(format_selected_run_summary(snapshot))
        evidence_path = snapshot.diagnostics_evidence_manifest_path
        self.evidence_var.set(
            f"Evidence: {snapshot.diagnostics_evidence_manifest_status} | "
            f"hash={snapshot.diagnostics_evidence_manifest_hash[:12] or '-'} | "
            f"path={evidence_path or '-'}"
        )

        run_label = snapshot.run_dir.name if snapshot.run_dir else "no run_dir"
        run_iid = self.artifact_tree.insert(
            "",
            "end",
            text=f"Run: {run_label}",
            values=(snapshot.status, "run", str(snapshot.run_dir or "")),
            open=True,
        )
        if snapshot.run_dir:
            self._path_by_iid[run_iid] = snapshot.run_dir
        if snapshot.selected_run_contract_path:
            iid = self.artifact_tree.insert(
                run_iid,
                "end",
                text="Selected run contract",
                values=(snapshot.contract_status, "contract", str(snapshot.selected_run_contract_path)),
            )
            self._path_by_iid[iid] = snapshot.selected_run_contract_path
        if snapshot.diagnostics_evidence_manifest_path:
            iid = self.artifact_tree.insert(
                run_iid,
                "end",
                text="Engineering analysis evidence manifest",
                values=(snapshot.diagnostics_evidence_manifest_status, "evidence", str(snapshot.diagnostics_evidence_manifest_path)),
            )
            self._path_by_iid[iid] = snapshot.diagnostics_evidence_manifest_path

        group_iids: dict[str, str] = {}
        for artifact in sorted(snapshot.artifacts, key=lambda item: (item.category, item.title)):
            group_iid = group_iids.get(artifact.category)
            if group_iid is None:
                group_iid = self.artifact_tree.insert(
                    run_iid,
                    "end",
                    text=artifact.category,
                    values=("", "category", ""),
                    open=True,
                )
                group_iids[artifact.category] = group_iid
            iid = self.artifact_tree.insert(
                group_iid,
                "end",
                text=artifact.title,
                values=(artifact.status, artifact.category, str(artifact.path)),
            )
            self._artifact_by_iid[iid] = artifact
            self._path_by_iid[iid] = artifact.path

        candidate_root = self.artifact_tree.insert(
            "",
            "end",
            text="Optimization runs for HO-007",
            values=("", "ho007_candidates", ""),
            open=not bool(snapshot.run_dir),
        )
        discovery_failed = False
        try:
            candidates = self.runtime.discover_selected_run_candidates(limit=25)
        except Exception as exc:
            discovery_failed = True
            self.artifact_tree.insert(
                candidate_root,
                "end",
                text="Candidate discovery failed",
                values=("FAILED", "optimization_run", f"{type(exc).__name__}: {exc!s}"),
            )
            candidates = ()
        all_candidates = tuple(candidates)
        ready_only = bool(self.candidate_ready_only_var.get())
        filtered_candidates = tuple(
            candidate
            for candidate in all_candidates
            if not ready_only or str(candidate.get("bridge_status") or "") == "READY"
        )
        ready_count = sum(
            1
            for candidate in all_candidates
            if str(candidate.get("bridge_status") or "") == "READY"
        )
        self.candidate_filter_summary_var.set(
            f"HO-007 candidates: shown={len(filtered_candidates)}/{len(all_candidates)} | ready={ready_count}"
        )
        self.artifact_tree.item(
            candidate_root,
            text=f"Optimization runs for HO-007 ({len(filtered_candidates)}/{len(all_candidates)})",
        )
        if not filtered_candidates and not discovery_failed:
            self.artifact_tree.insert(
                candidate_root,
                "end",
                text="No READY optimization runs found" if ready_only else "No optimization runs found",
                values=("MISSING", "optimization_run", ""),
            )
        for candidate in filtered_candidates:
            run_dir_text = str(candidate.get("run_dir") or "")
            bridge_status = str(candidate.get("bridge_status") or "UNKNOWN")
            status_label = str(candidate.get("status_label") or candidate.get("status") or "").strip()
            run_id = str(candidate.get("run_id") or candidate.get("run_name") or "optimization run")
            label = f"{run_id} [{status_label or bridge_status}]"
            iid = self.artifact_tree.insert(
                candidate_root,
                "end",
                text=label,
                values=(bridge_status, "optimization_run", run_dir_text),
            )
            if run_dir_text:
                self._path_by_iid[iid] = Path(run_dir_text)
            self._candidate_by_iid[iid] = dict(candidate)

        for idx, row in enumerate(snapshot.sensitivity_rows, start=1):
            iid = f"sens_{idx}"
            self.sensitivity_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    row.group,
                    f"{row.score:.6g}",
                    row.status,
                    row.strongest_metric,
                    f"{row.strongest_elasticity:.6g}",
                    "" if row.eps_rel_used is None else f"{row.eps_rel_used:.6g}",
                ),
            )
            self._sensitivity_by_iid[iid] = row

        self._set_text(self.detail_text, self._snapshot_detail(snapshot))

    def _snapshot_detail(self, snapshot: EngineeringAnalysisSnapshot) -> str:
        payload = {
            "status": snapshot.status,
            "run_dir": str(snapshot.run_dir or ""),
            "influence_status": snapshot.influence_status,
            "calibration_status": snapshot.calibration_status,
            "compare_status": snapshot.compare_status,
            "contract_status": snapshot.contract_status,
            "blocking_states": list(snapshot.blocking_states),
            "artifact_count": len(snapshot.artifacts),
            "sensitivity_row_count": len(snapshot.sensitivity_rows),
            "unit_catalog": dict(snapshot.unit_catalog),
            "handoff_requirements": self.runtime.selected_run_handoff_requirements(snapshot),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _refresh_candidate_filter(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            self.refresh()
            return
        self._populate_snapshot(snapshot)
        self.status_var.set(
            "HO-007 candidate filter: READY only"
            if bool(self.candidate_ready_only_var.get())
            else "HO-007 candidate filter: all candidates"
        )

    def _selected_tree_iid(self) -> str:
        selected = self.artifact_tree.selection()
        return str(selected[0]) if selected else ""

    def _selected_tree_path(self) -> Path | None:
        iid = self._selected_tree_iid()
        if iid:
            path = self._path_by_iid.get(iid)
            if path is not None:
                return path
        return None

    def _selected_candidate_run_dir(self) -> Path | None:
        iid = self._selected_tree_iid()
        if not iid:
            return None
        candidate = self._candidate_by_iid.get(iid)
        if not candidate:
            return None
        raw = str(candidate.get("run_dir") or "").strip()
        if not raw:
            return None
        path = Path(raw)
        return path if path.exists() and path.is_dir() else None

    def _open_selected(self) -> None:
        path = self._selected_tree_path()
        if path is None:
            messagebox.showinfo("Engineering Analysis", "Выберите artifact, manifest или run_dir.")
            return
        try:
            _open_path(path)
            self.status_var.set(f"Opened: {path}")
        except Exception as exc:
            messagebox.showerror("Engineering Analysis", f"Не удалось открыть:\n{path}\n\n{exc!s}")

    def _on_artifact_select(self, _event: tk.Event | None = None) -> None:
        selected = self.artifact_tree.selection()
        if not selected:
            return
        iid = selected[0]
        artifact = self._artifact_by_iid.get(iid)
        if artifact is not None:
            payload = artifact.to_payload()
            path = artifact.path
            payload["exists"] = path.exists()
            payload["size_bytes"] = path.stat().st_size if path.exists() and path.is_file() else None
            self._set_text(self.detail_text, json.dumps(payload, ensure_ascii=False, indent=2))
            return
        candidate = self._candidate_by_iid.get(iid)
        if candidate is not None:
            self._set_text(self.detail_text, json.dumps(candidate, ensure_ascii=False, indent=2))
            return
        path = self._path_by_iid.get(iid)
        if path is not None:
            self._set_text(self.detail_text, json.dumps({"path": str(path), "exists": path.exists()}, ensure_ascii=False, indent=2))

    def _on_sensitivity_select(self, _event: tk.Event | None = None) -> None:
        selected = self.sensitivity_tree.selection()
        if not selected:
            return
        row = self._sensitivity_by_iid.get(selected[0])
        if row is not None:
            self._set_text(self.detail_text, json.dumps(row.to_payload(), ensure_ascii=False, indent=2))

    def _current_run_dir(self) -> Path | None:
        if self.snapshot_state is None:
            self.snapshot_state = self.runtime.snapshot()
        return self.snapshot_state.run_dir if self.snapshot_state else None

    def _set_busy(self, busy: bool, label: str = "") -> None:
        buttons = (
            self.btn_refresh,
            self.btn_export_ho007,
            self.btn_export_evidence,
            self.btn_animator_link,
            self.btn_system_influence,
            self.btn_full_report,
            self.btn_param_staging,
            self.btn_diagnostics,
        )
        for button in buttons:
            button.configure(state="disabled" if busy else "normal")
        if busy:
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
            self.status_var.set(f"running: {label}")
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)

    def _run_job(
        self,
        label: str,
        worker: Callable[[Path], EngineeringAnalysisJobResult],
    ) -> None:
        existing = self._worker_thread
        if existing is not None and existing.is_alive():
            messagebox.showinfo("Engineering Analysis", "Дождитесь завершения текущей команды.")
            return
        run_dir = self._current_run_dir()
        if run_dir is None:
            messagebox.showwarning("Engineering Analysis", "Нет run_dir для запуска команды.")
            return

        self._set_busy(True, label)
        self._append_log(f"$ {label}\nrun_dir={run_dir}")

        def _target() -> None:
            try:
                result = worker(run_dir)
            except Exception as exc:
                result = EngineeringAnalysisJobResult(
                    ok=False,
                    status="FAILED",
                    command=(),
                    returncode=None,
                    run_dir=run_dir,
                    artifacts=(),
                    log_text="",
                    error=f"{type(exc).__name__}: {exc!s}",
                )
            self.after(0, lambda: self._finish_job(label, result))

        self._worker_thread = threading.Thread(target=_target, name=f"engineering-analysis-{label}", daemon=True)
        self._worker_thread.start()

    def _finish_job(self, label: str, result: EngineeringAnalysisJobResult) -> None:
        self._set_busy(False)
        status = result.status or ("FINISHED" if result.ok else "FAILED")
        self.status_var.set(f"{label}: {status}")
        if result.command:
            self._append_log("command: " + " ".join(result.command))
        if result.log_text:
            self._append_log(result.log_text)
        if result.error:
            self._append_log("error: " + result.error)
        self.refresh()
        if label == "Export HO-007" and result.ok:
            self._auto_export_evidence_after_ho007()

    def _auto_export_evidence_after_ho007(self) -> None:
        snapshot = self.snapshot_state or self.runtime.snapshot()
        if snapshot.status == "BLOCKED" or snapshot.contract_status in {"MISSING", "INVALID", "BLOCKED"}:
            self._append_log("evidence auto-export skipped: selected run contract is not ready")
            self.status_var.set("Export HO-007: FINISHED; evidence auto-export skipped")
            return
        try:
            path = self.runtime.write_diagnostics_evidence_manifest(snapshot)
        except Exception as exc:
            self._append_log(f"evidence auto-export failed: {type(exc).__name__}: {exc!s}")
            self.status_var.set("Export HO-007: FINISHED; evidence auto-export failed")
            return
        self._append_log(f"evidence auto-exported after HO-007: {path}")
        self.status_var.set(f"Export HO-007: FINISHED; evidence exported: {path}")
        self.refresh()

    def _run_system_influence(self) -> None:
        self._run_job(
            "System Influence",
            lambda run_dir: self.runtime.run_system_influence(
                run_dir,
                adaptive_eps=True,
                stage_name="engineering_analysis_center",
            ),
        )

    def _run_full_report(self) -> None:
        self._run_job("Full Report", lambda run_dir: self.runtime.run_full_report(run_dir, max_plots=12))

    def _run_param_staging(self) -> None:
        self._run_job("Influence Staging", lambda run_dir: self.runtime.run_param_staging(run_dir))

    def _export_selected_run_contract_bridge(self) -> None:
        existing = self._worker_thread
        if existing is not None and existing.is_alive():
            messagebox.showinfo("Engineering Analysis", "Дождитесь завершения текущей команды.")
            return
        snapshot = self.snapshot_state or self.runtime.snapshot()
        run_dir = self._selected_candidate_run_dir()
        if run_dir is None:
            selected = self._selected_tree_path()
            initial_dir = selected if selected is not None and selected.is_dir() else snapshot.run_dir
            if initial_dir is None:
                initial_dir = self.runtime.repo_root
            chosen = filedialog.askdirectory(
                parent=self,
                title="Выберите completed optimization run directory для HO-007",
                initialdir=str(initial_dir),
            )
            if not chosen:
                return
            run_dir = Path(chosen)
        self._set_busy(True, "Export HO-007")
        self._append_log(f"$ Export HO-007\nrun_dir={run_dir}")

        def _target() -> None:
            try:
                result = self.runtime.export_selected_run_contract_from_run_dir(
                    run_dir,
                    selected_from="desktop_engineering_analysis_center",
                )
            except Exception as exc:
                result = EngineeringAnalysisJobResult(
                    ok=False,
                    status="FAILED",
                    command=(),
                    returncode=None,
                    run_dir=run_dir,
                    artifacts=(),
                    log_text="",
                    error=f"{type(exc).__name__}: {exc!s}",
                )
            self.after(0, lambda: self._finish_job("Export HO-007", result))

        self._worker_thread = threading.Thread(
            target=_target,
            name="engineering-analysis-export-ho007",
            daemon=True,
        )
        self._worker_thread.start()

    def _export_diagnostics_evidence(self) -> None:
        snapshot = self.snapshot_state or self.runtime.snapshot()
        try:
            path = self.runtime.write_diagnostics_evidence_manifest(snapshot)
        except Exception as exc:
            messagebox.showerror("Engineering Analysis", f"Не удалось экспортировать evidence:\n{exc!s}")
            self.status_var.set("Evidence export failed.")
            return
        self._append_log(f"evidence exported: {path}")
        self.status_var.set(f"Evidence exported: {path}")
        self.refresh()

    def _export_animator_link(self) -> None:
        snapshot = self.snapshot_state or self.runtime.snapshot()
        pointer = self._selected_tree_path()
        if pointer is None and snapshot.selected_run_context is not None:
            pointer_text = snapshot.selected_run_context.results_csv_path
            pointer = Path(pointer_text) if pointer_text else None
        if pointer is None:
            messagebox.showwarning("Engineering Analysis", "Выберите artifact для явной передачи в Animator.")
            return
        try:
            payload = self.runtime.export_analysis_to_animator_link_contract(
                snapshot,
                selected_result_artifact_pointer=pointer,
            )
        except Exception as exc:
            messagebox.showerror("Engineering Analysis", f"Не удалось экспортировать HO-008:\n{exc!s}")
            self.status_var.set("Animator link export failed.")
            return
        self._append_log(
            "HO-008 animator link exported: "
            + str(payload.get("animator_link_contract_path") or "")
        )
        self.status_var.set(
            "Animator link exported: "
            + str(payload.get("analysis_context_path") or "")
        )

    def _launch_full_diagnostics_gui(self) -> None:
        command = [
            sys.executable,
            "-m",
            "pneumo_solver_ui.tools.desktop_diagnostics_center",
        ]
        try:
            proc = subprocess.Popen(command, cwd=str(self.runtime.repo_root))
        except Exception as exc:
            messagebox.showerror("Engineering Analysis", f"Не удалось запустить диагностику:\n{exc!s}")
            self.status_var.set("Diagnostics launch failed.")
            return
        self._append_log("command: " + " ".join(command))
        self.status_var.set(f"Diagnostics launched: pid={getattr(proc, 'pid', '-')}")


def _default_runtime() -> DesktopEngineeringAnalysisRuntime:
    return DesktopEngineeringAnalysisRuntime(
        repo_root=Path(__file__).resolve().parents[2],
        python_executable=sys.executable,
    )


def main() -> int:
    root = tk.Tk()
    root.title("Engineering Analysis Center")
    root.geometry("1360x860")
    root.minsize(1120, 720)
    center = DesktopEngineeringAnalysisCenter(root, runtime=_default_runtime())
    center.pack(fill="both", expand=True)
    root.mainloop()
    return 0


__all__ = [
    "DesktopEngineeringAnalysisCenter",
    "format_contract_banner",
    "format_selected_run_summary",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
