from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from pneumo_solver_ui.desktop_results_model import (
    DesktopResultsArtifact,
    DesktopResultsOverviewRow,
    DesktopResultsSessionHandoff,
    DesktopResultsSnapshot,
    format_npz_summary,
    format_optimizer_gate_summary,
    format_recent_runs_summary,
    format_triage_summary,
    format_validation_summary,
)
from pneumo_solver_ui.desktop_results_runtime import DesktopResultsRuntime


def _open_path(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def _button_text(prefix: str, text: str, *, limit: int = 58) -> str:
    raw = " ".join(str(text or "").split())
    if not raw:
        return prefix
    if len(raw) > limit:
        raw = raw[: max(0, limit - 3)].rstrip() + "..."
    return f"{prefix}: {raw}"


def _artifact_matches_filters(
    artifact: DesktopResultsArtifact,
    *,
    category: str,
    query: str,
) -> bool:
    target_category = str(category or "").strip().lower()
    if target_category and target_category != "all":
        if str(artifact.category or "").strip().lower() != target_category:
            return False

    raw_query = " ".join(str(query or "").split()).strip().lower()
    if not raw_query:
        return True

    haystack = " ".join(
        [
            str(artifact.title or ""),
            str(artifact.category or ""),
            str(artifact.path or ""),
            str(artifact.detail or ""),
        ]
    ).lower()
    return all(token in haystack for token in raw_query.split(" ") if token)


class DesktopResultsCenter(ttk.Frame):
    _CURRENT_RUN_GROUP_IID = "current_run_group"
    _LATEST_ARTIFACTS_GROUP_IID = "latest_artifacts_group"

    def __init__(
        self,
        master: tk.Misc,
        *,
        runtime: DesktopResultsRuntime,
    ) -> None:
        super().__init__(master, padding=10)
        self.runtime = runtime
        self.snapshot_state: DesktopResultsSnapshot | None = None
        self.session_handoff_state: DesktopResultsSessionHandoff | None = None
        self._artifact_by_iid: dict[str, DesktopResultsArtifact] = {}
        self._overview_by_iid: dict[str, DesktopResultsOverviewRow] = {}

        self.validation_var = tk.StringVar(master=self, value="Validation: not available yet.")
        self.optimizer_var = tk.StringVar(master=self, value="Optimizer gate: n/a")
        self.triage_var = tk.StringVar(master=self, value="Triage: critical=0 | warn=0 | info=0 | red_flags=0")
        self.npz_var = tk.StringVar(master=self, value="Latest NPZ: not available yet.")
        self.runs_var = tk.StringVar(master=self, value="Recent runs: autotest=— | diagnostics=—")
        self.next_step_var = tk.StringVar(master=self, value="Suggested next step: wait for the first validation snapshot.")
        self.next_detail_var = tk.StringVar(master=self, value="Why now: latest validation/results artifacts are not available yet.")
        self.handoff_summary_var = tk.StringVar(master=self, value="Latest run handoff: no local run handoff yet.")
        self.handoff_detail_var = tk.StringVar(master=self, value="Run tests from the first tab to pin the current session into this center.")
        self.handoff_steps_var = tk.StringVar(master=self, value="")
        self.show_current_run_only = tk.BooleanVar(master=self, value=False)
        self.browse_category_var = tk.StringVar(master=self, value="all")
        self.browse_query_var = tk.StringVar(master=self, value="")
        self.status_var = tk.StringVar(master=self, value="Results center ready.")

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        ttk.Label(
            self,
            text="Validation & Results",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            self,
            text=(
                "Operator-facing обзор последних validation/results артефактов. "
                "Здесь остаёмся после прогона и только потом ветвимся в compare viewer, animator, diagnostics или send center."
            ),
            wraplength=1120,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        summary = ttk.LabelFrame(self, text="Overview", padding=10)
        summary.pack(fill="x")
        ttk.Label(summary, textvariable=self.validation_var).pack(anchor="w")
        ttk.Label(summary, textvariable=self.optimizer_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.triage_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.npz_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.runs_var).pack(anchor="w", pady=(4, 0))

        handoff = ttk.LabelFrame(self, text="Suggested next step", padding=10)
        handoff.pack(fill="x", pady=(10, 0))
        ttk.Label(
            handoff,
            textvariable=self.next_step_var,
            font=("Segoe UI", 10, "bold"),
            wraplength=1120,
            justify="left",
        ).pack(anchor="w")
        ttk.Label(
            handoff,
            textvariable=self.next_detail_var,
            wraplength=1120,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        handoff_actions = ttk.Frame(handoff)
        handoff_actions.pack(fill="x", pady=(8, 0))
        self.btn_run_next_step = ttk.Button(
            handoff_actions,
            text="Run suggested next step",
            command=self._run_suggested_next_step,
        )
        self.btn_run_next_step.pack(side="left")

        run_handoff = ttk.LabelFrame(self, text="Latest run handoff", padding=10)
        run_handoff.pack(fill="x", pady=(10, 0))
        ttk.Label(
            run_handoff,
            textvariable=self.handoff_summary_var,
            font=("Segoe UI", 10, "bold"),
            wraplength=1120,
            justify="left",
        ).pack(anchor="w")
        ttk.Label(
            run_handoff,
            textvariable=self.handoff_detail_var,
            wraplength=1120,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        ttk.Label(
            run_handoff,
            textvariable=self.handoff_steps_var,
            wraplength=1120,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        run_handoff_actions = ttk.Frame(run_handoff)
        run_handoff_actions.pack(fill="x", pady=(8, 0))
        self.btn_open_handoff_zip = ttk.Button(
            run_handoff_actions,
            text="Open latest ZIP",
            command=self._open_handoff_zip,
        )
        self.btn_open_handoff_zip.pack(side="left")
        self.btn_open_handoff_autotest = ttk.Button(
            run_handoff_actions,
            text="Open latest autotest run",
            command=self._open_handoff_autotest_run,
        )
        self.btn_open_handoff_autotest.pack(side="left", padx=(8, 0))
        self.btn_open_handoff_diagnostics = ttk.Button(
            run_handoff_actions,
            text="Open latest diagnostics run",
            command=self._open_handoff_diagnostics_run,
        )
        self.btn_open_handoff_diagnostics.pack(side="left", padx=(8, 0))
        self.btn_focus_suggested = ttk.Button(
            run_handoff_actions,
            text="Focus suggested branch",
            command=self._focus_suggested_branch,
        )
        self.btn_focus_suggested.pack(side="left", padx=(8, 0))
        run_handoff_shortcuts = ttk.Frame(run_handoff)
        run_handoff_shortcuts.pack(fill="x", pady=(8, 0))
        self.btn_handoff_validation = ttk.Button(
            run_handoff_shortcuts,
            text="Open current validation",
            command=self._open_handoff_validation,
        )
        self.btn_handoff_validation.pack(side="left")
        self.btn_handoff_triage = ttk.Button(
            run_handoff_shortcuts,
            text="Open current triage",
            command=self._open_handoff_triage,
        )
        self.btn_handoff_triage.pack(side="left", padx=(8, 0))
        self.btn_handoff_compare = ttk.Button(
            run_handoff_shortcuts,
            text="Branch current compare",
            command=self._branch_handoff_compare,
        )
        self.btn_handoff_compare.pack(side="left", padx=(8, 0))
        self.btn_handoff_animator = ttk.Button(
            run_handoff_shortcuts,
            text="Branch current animator",
            command=self._branch_handoff_animator,
        )
        self.btn_handoff_animator.pack(side="left", padx=(8, 0))

        overview = ttk.LabelFrame(self, text="Validation overview", padding=8)
        overview.pack(fill="x", pady=(10, 0))
        self.overview_tree = ttk.Treeview(
            overview,
            columns=("status", "detail", "next_action", "evidence"),
            show="tree headings",
            height=6,
        )
        self.overview_tree.heading("#0", text="Check")
        self.overview_tree.heading("status", text="Status")
        self.overview_tree.heading("detail", text="Detail")
        self.overview_tree.heading("next_action", text="Next action")
        self.overview_tree.heading("evidence", text="Evidence")
        self.overview_tree.column("#0", width=220, anchor="w")
        self.overview_tree.column("status", width=110, anchor="w")
        self.overview_tree.column("detail", width=340, anchor="w")
        self.overview_tree.column("next_action", width=220, anchor="w")
        self.overview_tree.column("evidence", width=340, anchor="w")
        self.overview_tree.pack(fill="x", expand=False)
        self.overview_tree.bind("<<TreeviewSelect>>", self._on_overview_select)
        self.overview_tree.bind("<Double-1>", self._on_overview_open)
        overview_actions = ttk.Frame(overview)
        overview_actions.pack(fill="x", pady=(8, 0))
        self.btn_overview_action = ttk.Button(
            overview_actions,
            text="Run selected overview action",
            command=self._run_selected_overview_action,
        )
        self.btn_overview_action.pack(side="left")

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(10, 8))
        ttk.Button(actions, text="Обновить обзор", command=self.refresh).pack(side="left")
        self.btn_open_selected = ttk.Button(actions, text="Открыть выбранный артефакт", command=self._open_selected)
        self.btn_open_selected.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Открыть send_bundles", command=self._open_send_bundles).pack(side="left", padx=(8, 0))
        self.btn_compare = ttk.Button(actions, text="Открыть Compare Viewer", command=self._launch_compare_viewer)
        self.btn_compare.pack(side="left", padx=(8, 0))
        self.btn_animator = ttk.Button(actions, text="Открыть Desktop Animator", command=self._launch_animator)
        self.btn_animator.pack(side="left", padx=(8, 0))
        self.btn_animator_follow = ttk.Button(actions, text="Animator follow", command=self._launch_animator_follow)
        self.btn_animator_follow.pack(side="left", padx=(8, 0))

        tools = ttk.Frame(self)
        tools.pack(fill="x", pady=(0, 8))
        ttk.Button(tools, text="Открыть GUI диагностики", command=self._launch_full_diagnostics_gui).pack(side="left")
        ttk.Button(tools, text="Открыть Send Center", command=self._launch_send_results_gui).pack(side="left", padx=(8, 0))

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)

        browse = ttk.LabelFrame(body, text="Results browsing", padding=8)
        details = ttk.LabelFrame(body, text="Details", padding=8)
        body.add(browse, weight=3)
        body.add(details, weight=4)

        browse_controls = ttk.Frame(browse)
        browse_controls.pack(fill="x", pady=(0, 8))
        self.chk_current_run_only = ttk.Checkbutton(
            browse_controls,
            text="Current run only",
            variable=self.show_current_run_only,
            command=self._on_browse_scope_changed,
        )
        self.chk_current_run_only.pack(side="left")
        ttk.Label(browse_controls, text="Category:").pack(side="left", padx=(12, 4))
        self.cmb_browse_category = ttk.Combobox(
            browse_controls,
            textvariable=self.browse_category_var,
            values=["all", "validation", "triage", "results", "anim_latest", "runs", "bundle"],
            width=14,
            state="readonly",
        )
        self.cmb_browse_category.pack(side="left")
        self.cmb_browse_category.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_browse_scope_changed(),
        )
        ttk.Label(browse_controls, text="Search:").pack(side="left", padx=(12, 4))
        self.entry_browse_query = ttk.Entry(
            browse_controls,
            textvariable=self.browse_query_var,
            width=28,
        )
        self.entry_browse_query.pack(side="left")
        self.entry_browse_query.bind(
            "<KeyRelease>",
            lambda _event: self._on_browse_scope_changed(),
        )
        self.btn_clear_browse_query = ttk.Button(
            browse_controls,
            text="Clear",
            command=self._clear_browse_query,
        )
        self.btn_clear_browse_query.pack(side="left", padx=(8, 0))

        self.tree = ttk.Treeview(
            browse,
            columns=("category", "path"),
            show="tree headings",
            height=16,
        )
        self.tree.heading("#0", text="Artifact")
        self.tree.heading("category", text="Category")
        self.tree.heading("path", text="Path")
        self.tree.column("#0", width=240, anchor="w")
        self.tree.column("category", width=120, anchor="w")
        self.tree.column("path", width=420, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(browse, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_open_selected)

        self.details = tk.Text(details, wrap="word", height=16)
        self.details.pack(fill="both", expand=True)
        self.details.configure(state="disabled")

        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")

    def refresh(self) -> None:
        self.snapshot_state = self.runtime.snapshot()
        snapshot = self.snapshot_state
        self.validation_var.set(format_validation_summary(snapshot))
        self.optimizer_var.set(format_optimizer_gate_summary(snapshot))
        self.triage_var.set(format_triage_summary(snapshot))
        self.npz_var.set(format_npz_summary(snapshot))
        self.runs_var.set(format_recent_runs_summary(snapshot))
        self.next_step_var.set("Suggested next step: " + snapshot.suggested_next_step)
        self.next_detail_var.set("Why now: " + snapshot.suggested_next_detail)
        self._render_overview(snapshot)
        self._render_artifacts(snapshot)
        self._select_initial_overview(snapshot)
        self._render_session_handoff()
        self._render_details()
        self._refresh_action_states(snapshot)
        self.status_var.set("Validation/results overview refreshed.")

    def set_session_handoff(self, handoff: DesktopResultsSessionHandoff | None) -> None:
        self.session_handoff_state = handoff
        if self.snapshot_state is not None:
            self._render_artifacts(self.snapshot_state)
            self._select_initial_overview(self.snapshot_state)
        self._render_session_handoff()
        self._render_details()
        if self.snapshot_state is not None:
            self._refresh_action_states(self.snapshot_state)

    def _refresh_action_states(self, snapshot: DesktopResultsSnapshot) -> None:
        artifact = self._selected_artifact()
        row = self._selected_overview_row()
        row_artifact = self.runtime.preferred_overview_evidence_artifact(
            snapshot,
            row,
            handoff=self.session_handoff_state,
        )
        compare_target = self.runtime.compare_viewer_path(snapshot, artifact=artifact)
        animator_npz, animator_pointer = self.runtime.animator_target_paths(
            snapshot,
            artifact=artifact,
        )
        self.btn_open_selected.configure(
            state="normal" if bool(self._artifact_by_iid) else "disabled"
        )
        self.btn_compare.configure(
            state="normal" if compare_target is not None else "disabled"
        )
        self.btn_animator.configure(
            state="normal"
            if (animator_npz is not None or animator_pointer is not None)
            else "disabled"
        )
        self.btn_animator_follow.configure(
            state="normal"
            if (animator_pointer is not None or animator_npz is not None)
            else "disabled"
        )
        self.btn_run_next_step.configure(
            text=_button_text("Run suggested next step", snapshot.suggested_next_step),
            state=(
                "normal"
                if self._can_run_action(
                    snapshot,
                    snapshot.suggested_next_action_key,
                    artifact=self.runtime.preferred_artifact_by_key(
                        snapshot,
                        snapshot.suggested_next_artifact_key,
                        handoff=self.session_handoff_state,
                    ),
                )
                else "disabled"
            ),
        )
        handoff = self.session_handoff_state
        has_session_artifacts = self._has_session_artifacts(snapshot)
        if not has_session_artifacts and self.show_current_run_only.get():
            self.show_current_run_only.set(False)
        self.chk_current_run_only.configure(
            state="normal" if has_session_artifacts else "disabled"
        )
        self.cmb_browse_category.configure(
            state="readonly"
        )
        self.btn_clear_browse_query.configure(
            state="normal" if str(self.browse_query_var.get() or "").strip() else "disabled"
        )
        self.btn_open_handoff_zip.configure(
            state=(
                "normal"
                if handoff is not None and handoff.zip_path is not None
                else "disabled"
            )
        )
        self.btn_open_handoff_autotest.configure(
            state=(
                "normal"
                if handoff is not None and handoff.autotest_run_dir is not None
                else "disabled"
            )
        )
        self.btn_open_handoff_diagnostics.configure(
            state=(
                "normal"
                if handoff is not None and handoff.diagnostics_run_dir is not None
                else "disabled"
            )
        )
        current_validation_artifact = self._preferred_handoff_artifact("validation_json")
        current_triage_artifact = self._preferred_handoff_artifact("triage_json")
        current_compare_artifact = self._preferred_handoff_artifact("latest_npz")
        current_animator_artifact = (
            self._preferred_handoff_artifact("latest_pointer")
            or self._preferred_handoff_artifact("latest_npz")
        )
        self.btn_handoff_validation.configure(
            state="normal" if current_validation_artifact is not None else "disabled"
        )
        self.btn_handoff_triage.configure(
            state="normal" if current_triage_artifact is not None else "disabled"
        )
        self.btn_handoff_compare.configure(
            state=(
                "normal"
                if self._can_run_action(
                    snapshot,
                    "open_compare_viewer",
                    artifact=current_compare_artifact,
                )
                else "disabled"
            )
        )
        self.btn_handoff_animator.configure(
            state=(
                "normal"
                if self._can_run_action(
                    snapshot,
                    "open_animator_follow",
                    artifact=current_animator_artifact,
                )
                else "disabled"
            )
        )
        self.btn_focus_suggested.configure(
            state="normal" if bool(snapshot.validation_overview_rows) else "disabled"
        )
        overview_action_label = row.next_action if row is not None else ""
        self.btn_overview_action.configure(
            text=_button_text("Run selected overview action", overview_action_label),
            state=(
                "normal"
                if (
                    row is not None
                    and self._can_run_action(
                        snapshot,
                        row.action_key,
                        artifact=row_artifact,
                        path=row.evidence_path,
                    )
                )
                else "disabled"
            ),
        )

    def _render_artifacts(self, snapshot: DesktopResultsSnapshot) -> None:
        selected_artifact = self._selected_artifact()
        selected_key = selected_artifact.key if selected_artifact is not None else ""
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._artifact_by_iid.clear()
        session_artifacts = list(
            self.runtime.session_artifacts(snapshot, self.session_handoff_state)
        )
        latest_artifacts = list(snapshot.recent_artifacts)
        session_artifacts = [
            artifact for artifact in session_artifacts if self._artifact_matches_browse_filter(artifact)
        ]
        latest_artifacts = [
            artifact for artifact in latest_artifacts if self._artifact_matches_browse_filter(artifact)
        ]
        show_current_only = self.show_current_run_only.get() and bool(session_artifacts)

        if session_artifacts:
            self.tree.insert(
                "",
                "end",
                iid=self._CURRENT_RUN_GROUP_IID,
                text="Current run (pinned)",
                values=("section", f"{len(session_artifacts)} artifacts"),
                open=True,
            )
            for artifact in session_artifacts:
                iid = artifact.key
                self._artifact_by_iid[iid] = artifact
                self.tree.insert(
                    self._CURRENT_RUN_GROUP_IID,
                    "end",
                    iid=iid,
                    text=artifact.title,
                    values=(artifact.category, str(artifact.path)),
                )

        if latest_artifacts and not show_current_only:
            self.tree.insert(
                "",
                "end",
                iid=self._LATEST_ARTIFACTS_GROUP_IID,
                text="Latest workspace artifacts",
                values=("section", f"{len(latest_artifacts)} artifacts"),
                open=True,
            )
            for artifact in latest_artifacts:
                iid = artifact.key
                self._artifact_by_iid[iid] = artifact
                self.tree.insert(
                    self._LATEST_ARTIFACTS_GROUP_IID,
                    "end",
                    iid=iid,
                    text=artifact.title,
                    values=(artifact.category, str(artifact.path)),
                )

        artifacts = session_artifacts if show_current_only else session_artifacts + latest_artifacts
        if artifacts:
            target_key = selected_key if selected_key in self._artifact_by_iid else artifacts[0].key
            self.tree.selection_set(target_key)
            self.tree.focus(target_key)
            self.tree.see(target_key)

    def _render_overview(self, snapshot: DesktopResultsSnapshot) -> None:
        for iid in self.overview_tree.get_children():
            self.overview_tree.delete(iid)
        self._overview_by_iid.clear()
        for row in snapshot.validation_overview_rows:
            self._overview_by_iid[row.key] = row
            self.overview_tree.insert(
                "",
                "end",
                iid=row.key,
                text=row.title,
                values=(
                    row.status,
                    row.detail,
                    row.next_action,
                    str(row.evidence_path) if row.evidence_path is not None else "",
                ),
            )

    def _selected_artifact(self) -> DesktopResultsArtifact | None:
        selected = list(self.tree.selection())
        if not selected:
            return None
        return self._artifact_by_iid.get(selected[0])

    def _selected_overview_row(self) -> DesktopResultsOverviewRow | None:
        selected = list(self.overview_tree.selection())
        if not selected:
            return None
        return self._overview_by_iid.get(selected[0])

    def _select_artifact(self, artifact: DesktopResultsArtifact | None) -> None:
        if artifact is None or artifact.key not in self._artifact_by_iid:
            return
        self.tree.selection_set(artifact.key)
        self.tree.focus(artifact.key)
        self.tree.see(artifact.key)

    def _select_initial_overview(self, snapshot: DesktopResultsSnapshot) -> None:
        if not snapshot.validation_overview_rows:
            return
        target_row = None
        if snapshot.suggested_next_artifact_key:
            for row in snapshot.validation_overview_rows:
                if row.artifact_key == snapshot.suggested_next_artifact_key:
                    target_row = row
                    break
        if target_row is None:
            target_row = snapshot.validation_overview_rows[0]
        self.overview_tree.selection_set(target_row.key)
        self.overview_tree.focus(target_row.key)
        self.overview_tree.see(target_row.key)
        self._select_artifact(
            self.runtime.preferred_overview_evidence_artifact(
                snapshot,
                target_row,
                handoff=self.session_handoff_state,
            )
        )

    def _render_session_handoff(self) -> None:
        handoff = self.session_handoff_state
        if handoff is None:
            self.handoff_summary_var.set("Latest run handoff: no local run handoff yet.")
            self.handoff_detail_var.set(
                "Run tests from the first tab to pin the current session into this center."
            )
            self.handoff_steps_var.set("")
            return
        self.handoff_summary_var.set("Latest run handoff: " + str(handoff.summary or ""))
        self.handoff_detail_var.set(str(handoff.detail or ""))
        self.handoff_steps_var.set(
            "Steps: " + " | ".join(str(item) for item in handoff.step_lines if str(item).strip())
            if handoff.step_lines
            else ""
        )

    def _preferred_handoff_artifact(
        self,
        artifact_key: str,
    ) -> DesktopResultsArtifact | None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return None
        return self.runtime.preferred_artifact_by_key(
            snapshot,
            artifact_key,
            handoff=self.session_handoff_state,
        )

    def _has_session_artifacts(self, snapshot: DesktopResultsSnapshot) -> bool:
        return bool(self.runtime.session_artifacts(snapshot, self.session_handoff_state))

    def _artifact_matches_browse_filter(self, artifact: DesktopResultsArtifact) -> bool:
        return _artifact_matches_filters(
            artifact,
            category=self.browse_category_var.get(),
            query=self.browse_query_var.get(),
        )

    def _browse_scope_summary(self) -> str:
        scope = (
            "current run only"
            if self.show_current_run_only.get()
            else "current run + latest workspace"
        )
        category = str(self.browse_category_var.get() or "all").strip() or "all"
        query = " ".join(str(self.browse_query_var.get() or "").split()).strip()
        return f"{scope} | category={category} | query={query or '—'}"

    def _clear_browse_query(self) -> None:
        if not str(self.browse_query_var.get() or "").strip():
            return
        self.browse_query_var.set("")
        self._on_browse_scope_changed()

    def _on_browse_scope_changed(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        if self.show_current_run_only.get() and not self._has_session_artifacts(snapshot):
            self.show_current_run_only.set(False)
        self._render_artifacts(snapshot)
        self._render_details()
        self._refresh_action_states(snapshot)
        self.status_var.set("Browse scope updated: " + self._browse_scope_summary())

    def _can_run_action(
        self,
        snapshot: DesktopResultsSnapshot,
        action_key: str,
        *,
        artifact: DesktopResultsArtifact | None = None,
        path: Path | None = None,
    ) -> bool:
        action = str(action_key or "").strip()
        if not action:
            return False
        if action == "open_artifact":
            return artifact is not None or path is not None
        if action == "open_compare_viewer":
            return self.runtime.compare_viewer_path(snapshot, artifact=artifact) is not None
        if action == "open_animator":
            npz_path, pointer_path = self.runtime.animator_target_paths(
                snapshot,
                artifact=artifact,
            )
            return npz_path is not None or pointer_path is not None
        if action == "open_animator_follow":
            args = self.runtime.animator_args(
                snapshot,
                follow=True,
                artifact=artifact,
            )
            return bool(args)
        if action in {
            "open_diagnostics_gui",
            "open_send_center",
            "open_send_bundles",
        }:
            return True
        return False

    def _render_details(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        artifact = self._selected_artifact()
        row = self._selected_overview_row()
        handoff = self.session_handoff_state
        lines = [
            format_validation_summary(snapshot),
            format_optimizer_gate_summary(snapshot),
            format_triage_summary(snapshot),
            format_npz_summary(snapshot),
            format_recent_runs_summary(snapshot),
            "Browse scope: " + self._browse_scope_summary(),
            "",
            "Suggested next step:",
            snapshot.suggested_next_step,
            f"Why now: {snapshot.suggested_next_detail}",
        ]
        if handoff is not None:
            lines.extend(
                [
                    "",
                    "Latest run handoff:",
                    handoff.summary,
                ]
            )
            if handoff.detail:
                lines.append(handoff.detail)
            if handoff.step_lines:
                lines.extend(f"- {item}" for item in handoff.step_lines)
        if row is not None:
            lines.extend(
                [
                    "",
                    f"Selected check: {row.title}",
                    f"Check status: {row.status}",
                    f"Check detail: {row.detail}",
                ]
            )
            if row.next_action:
                lines.append(f"Check next action: {row.next_action}")
            if row.evidence_path is not None:
                lines.append(f"Check evidence: {row.evidence_path}")
        if snapshot.mnemo_current_mode:
            lines.append(f"Desktop Mnemo mode: {snapshot.mnemo_current_mode}")
        if snapshot.mnemo_recent_titles:
            lines.append("Recent Mnemo events: " + " | ".join(snapshot.mnemo_recent_titles[:3]))
        if snapshot.optimizer_scope_gate_reason:
            lines.append(f"Optimizer gate reason: {snapshot.optimizer_scope_gate_reason}")
        if artifact is not None:
            lines.extend(
                [
                    "",
                    f"Selected artifact: {artifact.title}",
                    f"Category: {artifact.category}",
                    f"Path: {artifact.path}",
                ]
            )
            try:
                st = artifact.path.stat()
                lines.append(f"Modified: {st.st_mtime:.0f}")
                if artifact.path.is_file():
                    lines.append(f"Size bytes: {int(st.st_size)}")
            except Exception:
                pass
            if artifact.detail:
                lines.append(f"Detail: {artifact.detail}")
            compare_target = self.runtime.compare_viewer_path(snapshot, artifact=artifact)
            animator_npz, animator_pointer = self.runtime.animator_target_paths(
                snapshot,
                artifact=artifact,
            )
            if compare_target is not None:
                lines.append(f"Compare target NPZ: {compare_target}")
            if animator_pointer is not None:
                lines.append(f"Animator pointer: {animator_pointer}")
            elif animator_npz is not None:
                lines.append(f"Animator NPZ: {animator_npz}")
            preview_lines = self.runtime.artifact_preview_lines(artifact)
            if preview_lines:
                lines.extend(["", "Preview:"])
                lines.extend(f"- {line}" for line in preview_lines)
        if snapshot.validation_errors:
            lines.extend(["", "Validation errors:"])
            lines.extend(f"- {item}" for item in snapshot.validation_errors[:5])
        if snapshot.validation_warnings:
            lines.extend(["", "Validation warnings:"])
            lines.extend(f"- {item}" for item in snapshot.validation_warnings[:5])
        if snapshot.triage_red_flags:
            lines.extend(["", "Triage red flags:"])
            lines.extend(f"- {item}" for item in snapshot.triage_red_flags[:5])
        if snapshot.anim_summary_lines:
            lines.extend(["", "Anim latest summary:"])
            lines.extend(f"- {line}" for line in snapshot.anim_summary_lines)
        if snapshot.operator_recommendations:
            lines.extend(["", "Recommended branch actions:"])
            lines.extend(
                f"{idx}. {item}"
                for idx, item in enumerate(snapshot.operator_recommendations, start=1)
            )

        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", "\n".join(lines))
        self.details.configure(state="disabled")

    def _on_select(self, _event=None) -> None:
        self._render_details()
        if self.snapshot_state is not None:
            self._refresh_action_states(self.snapshot_state)

    def _on_overview_select(self, _event=None) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        row = self._selected_overview_row()
        if row is not None:
            self._select_artifact(
                self.runtime.preferred_overview_evidence_artifact(
                    snapshot,
                    row,
                    handoff=self.session_handoff_state,
                )
            )
        self._render_details()
        self._refresh_action_states(snapshot)

    def _on_overview_open(self, _event=None) -> None:
        self._run_selected_overview_action()

    def _on_open_selected(self, _event=None) -> None:
        self._open_selected()

    def _open_selected(self) -> None:
        artifact = self._selected_artifact()
        if artifact is None:
            return
        self._run_action("open_artifact", artifact=artifact, success_message=f"Opened: {artifact.title}")

    def _run_action(
        self,
        action_key: str,
        *,
        artifact: DesktopResultsArtifact | None = None,
        path: Path | None = None,
        success_message: str = "",
    ) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        try:
            action = str(action_key or "").strip()
            if action == "open_artifact":
                target_path = artifact.path if artifact is not None else path
                if target_path is None:
                    return
                _open_path(target_path)
            elif action == "open_compare_viewer":
                self.runtime.launch_compare_viewer(snapshot, artifact=artifact)
            elif action == "open_animator":
                self.runtime.launch_animator(snapshot, follow=False, artifact=artifact)
            elif action == "open_animator_follow":
                self.runtime.launch_animator(snapshot, follow=True, artifact=artifact)
            elif action == "open_diagnostics_gui":
                self.runtime.launch_full_diagnostics_gui()
            elif action == "open_send_center":
                self.runtime.launch_send_results_gui()
            elif action == "open_send_bundles":
                self.runtime.send_bundles_dir.mkdir(parents=True, exist_ok=True)
                _open_path(self.runtime.send_bundles_dir)
            else:
                return
            self.status_var.set(success_message or f"Action completed: {action}")
        except Exception as exc:
            messagebox.showerror("Validation & Results", f"Не удалось выполнить действие:\n{exc}")

    def _run_suggested_next_step(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        artifact = self.runtime.preferred_artifact_by_key(
            snapshot,
            snapshot.suggested_next_artifact_key,
            handoff=self.session_handoff_state,
        )
        self._run_action(
            snapshot.suggested_next_action_key,
            artifact=artifact,
            success_message="Suggested next step launched.",
        )

    def _run_selected_overview_action(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        row = self._selected_overview_row()
        if row is None:
            return
        artifact = self.runtime.preferred_overview_evidence_artifact(
            snapshot,
            row,
            handoff=self.session_handoff_state,
        )
        self._run_action(
            row.action_key,
            artifact=artifact,
            path=row.evidence_path,
            success_message=f"Overview action launched: {row.title}",
        )

    def _focus_suggested_branch(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        self._select_initial_overview(snapshot)
        self._render_details()
        self._refresh_action_states(snapshot)
        self.status_var.set("Suggested branch focused in Validation & Results.")

    def _open_handoff_zip(self) -> None:
        handoff = self.session_handoff_state
        if handoff is None or handoff.zip_path is None:
            return
        self._run_action(
            "open_artifact",
            path=handoff.zip_path,
            success_message=f"Opened: {handoff.zip_path}",
        )

    def _open_handoff_validation(self) -> None:
        artifact = self._preferred_handoff_artifact("validation_json")
        if artifact is None:
            return
        self._run_action(
            "open_artifact",
            artifact=artifact,
            success_message="Current run validation opened.",
        )

    def _open_handoff_triage(self) -> None:
        artifact = self._preferred_handoff_artifact("triage_json")
        if artifact is None:
            return
        self._run_action(
            "open_artifact",
            artifact=artifact,
            success_message="Current run triage opened.",
        )

    def _branch_handoff_compare(self) -> None:
        artifact = self._preferred_handoff_artifact("latest_npz")
        if artifact is None:
            return
        self._run_action(
            "open_compare_viewer",
            artifact=artifact,
            success_message="Current run compare branch launched.",
        )

    def _branch_handoff_animator(self) -> None:
        artifact = self._preferred_handoff_artifact("latest_pointer")
        if artifact is None:
            artifact = self._preferred_handoff_artifact("latest_npz")
        if artifact is None:
            return
        self._run_action(
            "open_animator_follow",
            artifact=artifact,
            success_message="Current run animator branch launched.",
        )

    def _open_handoff_autotest_run(self) -> None:
        handoff = self.session_handoff_state
        if handoff is None or handoff.autotest_run_dir is None:
            return
        self._run_action(
            "open_artifact",
            path=handoff.autotest_run_dir,
            success_message=f"Opened: {handoff.autotest_run_dir}",
        )

    def _open_handoff_diagnostics_run(self) -> None:
        handoff = self.session_handoff_state
        if handoff is None or handoff.diagnostics_run_dir is None:
            return
        self._run_action(
            "open_artifact",
            path=handoff.diagnostics_run_dir,
            success_message=f"Opened: {handoff.diagnostics_run_dir}",
        )

    def _open_send_bundles(self) -> None:
        self._run_action(
            "open_send_bundles",
            success_message=f"Opened: {self.runtime.send_bundles_dir}",
        )

    def _launch_compare_viewer(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        self._run_action(
            "open_compare_viewer",
            artifact=self._selected_artifact(),
            success_message="Compare Viewer launched from Validation & Results.",
        )

    def _launch_animator(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        self._run_action(
            "open_animator",
            artifact=self._selected_artifact(),
            success_message="Desktop Animator launched on latest result.",
        )

    def _launch_animator_follow(self) -> None:
        snapshot = self.snapshot_state
        if snapshot is None:
            return
        self._run_action(
            "open_animator_follow",
            artifact=self._selected_artifact(),
            success_message="Desktop Animator follow launched from latest pointer.",
        )

    def _launch_full_diagnostics_gui(self) -> None:
        self._run_action(
            "open_diagnostics_gui",
            success_message="Full Diagnostics GUI launched.",
        )

    def _launch_send_results_gui(self) -> None:
        self._run_action(
            "open_send_center",
            success_message="Send Center launched.",
        )


__all__ = ["DesktopResultsCenter"]
