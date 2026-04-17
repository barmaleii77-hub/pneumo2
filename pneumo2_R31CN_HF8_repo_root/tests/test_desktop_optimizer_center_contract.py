from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.desktop_optimizer_model import (
    build_contract_snapshot,
    build_optimizer_session_defaults,
)
from pneumo_solver_ui.desktop_optimizer_runtime import DesktopOptimizerRuntime
from pneumo_solver_ui.desktop_suite_snapshot import build_validated_suite_snapshot
from pneumo_solver_ui.optimization_baseline_source import (
    active_baseline_contract_path,
    baseline_suite_handoff_snapshot_path,
    build_active_baseline_contract,
    write_active_baseline_contract,
)
from pneumo_solver_ui.optimization_job_session_runtime import (
    DistOptJob,
    load_job_from_session,
    save_job_to_session,
)
from pneumo_solver_ui.optimization_objective_contract import (
    objective_contract_hash,
    objective_contract_payload,
)
from pneumo_solver_ui.optimization_run_history import OptimizationRunSummary
from pneumo_solver_ui.desktop_shell.launcher_catalog import build_desktop_launch_catalog
from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def _optimizer_suite_snapshot(
    *,
    inputs_hash: str = "inputs-hash-optimizer-1",
    ring_hash: str = "ring-hash-optimizer-1",
) -> dict[str, object]:
    return build_validated_suite_snapshot(
        [
            {
                "id": "optimizer-baseline-row-1",
                "имя": "optimizer_baseline_smoke",
                "тип": "инерция_крен",
                "включен": True,
                "стадия": 0,
                "dt": 0.01,
                "t_end": 1.0,
            }
        ],
        inputs_snapshot_hash=inputs_hash,
        ring_source_hash=ring_hash,
        created_at_utc="2026-04-17T00:00:00Z",
        context_label="optimizer-baseline-unit",
    )


def _write_stale_optimizer_baseline_context(
    *,
    workspace_dir: Path,
    tmp_path: Path,
) -> dict[str, object]:
    old_suite = _optimizer_suite_snapshot(
        inputs_hash="inputs-hash-before",
        ring_hash="ring-hash-before",
    )
    current_suite = _optimizer_suite_snapshot(
        inputs_hash="inputs-hash-current",
        ring_hash="ring-hash-current",
    )
    suite_path = baseline_suite_handoff_snapshot_path(
        workspace_dir=workspace_dir,
        repo_root=ROOT,
    )
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite_path.write_text(json.dumps(current_suite, ensure_ascii=False), encoding="utf-8")
    active = build_active_baseline_contract(
        suite_snapshot=old_suite,
        baseline_path=tmp_path / "baseline_stale.json",
        baseline_payload={"param_a": 1.0},
        baseline_meta={"problem_hash": "optimizer-stale-baseline"},
        source_run_dir=tmp_path / "runs" / "baseline_old",
        created_at_utc="2026-04-17T00:20:00Z",
    )
    contract_path = write_active_baseline_contract(
        active,
        workspace_dir=workspace_dir,
        repo_root=ROOT,
    )
    return {
        "active": active,
        "contract_path": contract_path,
        "current_suite": current_suite,
        "old_suite": old_suite,
    }


def test_desktop_optimizer_center_is_registered_as_hosted_shell_tool() -> None:
    specs = build_desktop_shell_specs()
    by_key = {spec.key: spec for spec in specs}

    assert "desktop_optimizer_center" in by_key
    spec = by_key["desktop_optimizer_center"]
    assert spec.mode == "hosted"
    assert spec.group == "Встроенные окна"
    assert spec.standalone_module == "pneumo_solver_ui.tools.desktop_optimizer_center"
    assert spec.create_hosted is not None

    catalog_modules = {item.module for item in build_desktop_launch_catalog(include_mnemo=False)}
    assert "pneumo_solver_ui.tools.desktop_optimizer_center" in catalog_modules


def test_desktop_optimizer_center_uses_workspace_layout_instead_of_big_intro_panels() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_optimizer_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'workspace = ttk.Panedwindow(outer, orient="horizontal")' in src
    assert 'context_frame = ttk.LabelFrame(sidebar, text="Контекст", padding=8)' in src
    assert 'nav_frame = ttk.LabelFrame(sidebar, text="Переходы", padding=8)' in src
    assert 'text="Открыть Baseline Center", command=self.open_baseline_center' in src
    assert "PNEUMO_GUI_SPEC_SHELL_OPEN_WORKSPACE" in src
    assert '"baseline_run"' in src
    assert '"pneumo_solver_ui.tools.desktop_gui_spec_shell"' in src
    assert 'ttk.Sizegrip(footer).pack(side="right", padx=(10, 0))' in src


def test_root_desktop_optimizer_center_wrappers_delegate_to_launcher() -> None:
    cmd = (ROOT / "START_DESKTOP_OPTIMIZER_CENTER.cmd").read_text(
        encoding="utf-8",
        errors="replace",
    ).lower()
    vbs = (ROOT / "START_DESKTOP_OPTIMIZER_CENTER.vbs").read_text(
        encoding="utf-8",
        errors="replace",
    ).lower()
    pyw = (ROOT / "START_DESKTOP_OPTIMIZER_CENTER.pyw").read_text(
        encoding="utf-8",
        errors="replace",
    )
    py = (ROOT / "START_DESKTOP_OPTIMIZER_CENTER.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "start_desktop_optimizer_center.vbs" in cmd or "start_desktop_optimizer_center.pyw" in cmd
    assert "wscript.shell" in vbs
    assert "start_desktop_optimizer_center.pyw" in vbs
    assert 'Path(__file__).with_name("START_DESKTOP_OPTIMIZER_CENTER.py")' in pyw
    assert "ensure_root_launcher_runtime" in py
    assert 'MODULE = "pneumo_solver_ui.tools.desktop_optimizer_center"' in py


def test_desktop_optimizer_defaults_seed_stage_and_distributed_knobs() -> None:
    defaults = build_optimizer_session_defaults(cpu_count=8, platform_name="win32")

    assert defaults["opt_use_staged"] is True
    assert defaults["opt_launch_profile"] == "stage_triage"
    assert defaults["opt_backend"] == "Dask"
    assert defaults["opt_budget"] > 0
    assert defaults["ui_seed_candidates"] > 0
    assert defaults["stage_policy_mode"]
    assert defaults["dask_mode"]
    assert defaults["ray_mode"]
    assert "opt_botorch_n_init" in defaults
    assert defaults["opt_handoff_sort_mode"]
    assert defaults["opt_finished_sort_mode"]
    assert defaults["opt_packaging_sort_mode"]


def test_desktop_optimizer_contract_snapshot_reads_default_contract() -> None:
    session_state = build_optimizer_session_defaults(cpu_count=8, platform_name="win32")
    snapshot = build_contract_snapshot(session_state, ui_root=UI_ROOT)

    assert snapshot.workspace_dir.name == "workspace"
    assert snapshot.model_path.exists()
    assert snapshot.worker_path.exists()
    assert snapshot.base_json_path.exists()
    assert snapshot.ranges_json_path.exists()
    assert snapshot.suite_json_path.exists()
    assert snapshot.search_param_count > 0
    assert snapshot.enabled_suite_total > 0
    assert snapshot.objective_keys
    assert snapshot.penalty_key
    assert snapshot.problem_hash_mode
    assert snapshot.baseline_handoff_id == "HO-006"
    assert snapshot.active_baseline_state in {"missing", "current", "stale", "invalid"}
    assert "active_baseline_contract.json" in snapshot.active_baseline_contract_path
    assert snapshot.optimizer_baseline_can_consume is (
        snapshot.active_baseline_state == "current"
    )


def test_desktop_optimizer_contract_snapshot_never_rebinds_legacy_baseline_best(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace_dir = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))
    baseline_dir = workspace_dir / "baselines"
    baseline_dir.mkdir(parents=True)
    legacy_baseline = baseline_dir / "baseline_best.json"
    legacy_baseline.write_text(json.dumps({"legacy": True}), encoding="utf-8")
    contract_path = active_baseline_contract_path(
        workspace_dir=workspace_dir,
        repo_root=ROOT,
    )

    assert not contract_path.exists()

    session_state = build_optimizer_session_defaults(cpu_count=8, platform_name="win32")
    snapshot = build_contract_snapshot(session_state, ui_root=UI_ROOT)

    assert snapshot.baseline_source_kind == "global"
    assert snapshot.baseline_path == str(legacy_baseline.resolve())
    assert snapshot.baseline_handoff_id == "HO-006"
    assert snapshot.active_baseline_state == "missing"
    assert snapshot.optimizer_baseline_can_consume is False
    assert "active_baseline_contract.json" in snapshot.active_baseline_contract_path
    assert not contract_path.exists()


def test_desktop_optimizer_contract_snapshot_blocks_stale_active_baseline_without_rewrite(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace_dir = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))
    context = _write_stale_optimizer_baseline_context(
        workspace_dir=workspace_dir,
        tmp_path=tmp_path,
    )
    active = dict(context["active"])
    contract_path = Path(context["contract_path"])
    old_suite = dict(context["old_suite"])
    current_suite = dict(context["current_suite"])
    before = contract_path.read_text(encoding="utf-8")

    assert old_suite["suite_snapshot_hash"] != current_suite["suite_snapshot_hash"]

    session_state = build_optimizer_session_defaults(cpu_count=8, platform_name="win32")
    snapshot = build_contract_snapshot(session_state, ui_root=UI_ROOT)

    assert snapshot.baseline_handoff_id == "HO-006"
    assert snapshot.active_baseline_state == "stale"
    assert snapshot.active_baseline_hash == active["active_baseline_hash"]
    assert snapshot.active_baseline_suite_snapshot_hash == old_suite["suite_snapshot_hash"]
    assert snapshot.optimizer_baseline_can_consume is False
    assert "suite_snapshot_hash_changed" in snapshot.active_baseline_banner
    assert contract_path.read_text(encoding="utf-8") == before


def test_desktop_optimizer_runtime_builds_stage_and_coordinator_previews() -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )

    runtime.update_state({"opt_use_staged": True, "use_staged_opt": True})
    stage_preview = runtime.command_preview_text()
    assert "opt_stage_runner_v1.py" in stage_preview
    assert "--stage_policy_mode" in stage_preview

    runtime.update_state({"opt_use_staged": False, "use_staged_opt": False, "opt_backend": "Ray"})
    coord_preview = runtime.command_preview_text()
    assert "dist_opt_coordinator.py" in coord_preview
    assert "--backend ray" in coord_preview
    assert "--budget" in coord_preview
    assert runtime.handoff_overview_rows() == []


def test_desktop_optimizer_runtime_binds_selected_history_run_as_resume_target(tmp_path: Path) -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )

    staged_run = tmp_path / "opt_runs" / "staged" / "p_stage_resume"
    staged_run.mkdir(parents=True)
    runtime.bind_selected_run_dir(staged_run)
    staged_summary = runtime.resume_target_summary()

    assert runtime.session_state["__opt_history_selected_run_dir"] == str(staged_run.resolve())
    assert runtime.session_state["opt_dist_run_id"] == ""
    assert staged_summary["selected_pipeline"] == "staged"
    assert staged_summary["selected_run_name"] == "p_stage_resume"

    coord_run = tmp_path / "opt_runs" / "coord" / "p_coord_resume"
    coord_run.mkdir(parents=True)
    (coord_run / "run_id.txt").write_text("run_target_42", encoding="utf-8")
    runtime.bind_selected_run_dir(coord_run)
    coord_summary = runtime.resume_target_summary()

    assert runtime.session_state["__opt_history_selected_run_dir"] == str(coord_run.resolve())
    assert runtime.session_state["opt_dist_run_id"] == "run_target_42"
    assert coord_summary["selected_pipeline"] == "coordinator"
    assert coord_summary["selected_run_id"] == "run_target_42"


def test_desktop_optimizer_runtime_can_apply_selected_run_contract_to_launch_state(tmp_path: Path) -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )
    summary = OptimizationRunSummary(
        run_dir=tmp_path / "coord_run",
        pipeline_mode="coordinator",
        backend="Ray",
        status="done",
        status_label="DONE",
        started_at="",
        updated_ts=0.0,
        objective_keys=("comfort", "roll", "energy"),
        penalty_key="penalty_total",
        penalty_tol=0.25,
        problem_hash_mode="legacy",
    )

    updates = runtime.apply_run_contract(summary)

    assert updates["opt_objectives"] == "comfort\nroll\nenergy"
    assert updates["opt_penalty_key"] == "penalty_total"
    assert updates["opt_penalty_tol"] == 0.25
    assert updates["settings_opt_problem_hash_mode"] == "legacy"
    assert runtime.session_state["opt_objectives"] == "comfort\nroll\nenergy"
    assert runtime.session_state["opt_penalty_key"] == "penalty_total"
    assert runtime.session_state["opt_penalty_tol"] == 0.25
    assert runtime.session_state["settings_opt_problem_hash_mode"] == "legacy"


def test_desktop_optimizer_runtime_can_apply_operator_launch_profile() -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )

    updates = runtime.apply_launch_profile("coord_dask_explore")
    summary = runtime.launch_profile_summary()

    assert updates["opt_launch_profile"] == "coord_dask_explore"
    assert runtime.session_state["opt_use_staged"] is False
    assert runtime.session_state["use_staged_opt"] is False
    assert runtime.session_state["opt_backend"] == "Dask"
    assert runtime.session_state["opt_budget"] == 300
    assert runtime.session_state["dask_workers"] >= 1
    assert summary["profile_label"] == "Координатор / Dask-исследование"
    assert summary["launch_pipeline"] == "coordinator"

    runtime.update_state({"opt_budget": 111})
    drifted_summary = runtime.launch_profile_summary()
    assert "opt_budget" in drifted_summary["drift_keys"]


def test_desktop_optimizer_runtime_builds_contract_drift_summary(tmp_path: Path) -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )
    current_snapshot = runtime.contract_snapshot()
    summary = OptimizationRunSummary(
        run_dir=tmp_path / "coord_drift",
        pipeline_mode="coordinator",
        backend="Distributed coordinator",
        status="done",
        status_label="DONE",
        started_at="",
        updated_ts=0.0,
        objective_keys=("comfort", "roll"),
        penalty_key="penalty_other",
        penalty_tol=float(current_snapshot.penalty_tol) + 1.0,
        problem_hash="DIFFERENT_SCOPE_HASH",
        problem_hash_mode="legacy" if str(current_snapshot.problem_hash_mode) == "stable" else "stable",
        baseline_source_kind="artifact",
        baseline_source_label="different_baseline",
    )

    drift = runtime.contract_drift_summary(summary)

    assert "objective stack" in drift["diff_bits"]
    assert "penalty key" in drift["diff_bits"]
    assert "penalty tol" in drift["diff_bits"]
    assert drift["scope_payload"]["compatibility"] == "different"
    assert drift["scope_payload"]["mode_compatibility"] == "different"
    assert drift["baseline_compatibility"] == "different"


def test_desktop_optimizer_runtime_builds_launch_readiness_summary(tmp_path: Path) -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )
    runtime.workspace_dir = tmp_path

    coord_run = tmp_path / "opt_runs" / "coord" / "p_readiness_partial"
    (coord_run / "export").mkdir(parents=True)
    (coord_run / "coordinator.log").write_text("coord readiness log", encoding="utf-8")
    (coord_run / "export" / "trials.csv").write_text(
        (
            "status,anim_export_packaging_status,anim_export_packaging_truth_ready,"
            "верификация_флаги,число_runtime_fallback_пружины,"
            "число_пересечений_пружина_цилиндр,число_пересечений_пружина_пружина\n"
            "DONE,partial,0,spring_host_clearance,1,1,0\n"
        ),
        encoding="utf-8",
    )

    readiness = runtime.launch_readiness_summary()
    by_title = {
        str(row.get("title") or ""): dict(row)
        for row in tuple(readiness.get("rows") or ())
    }

    assert readiness["warn_count"] >= 1
    assert readiness["headline"] == "Review blockers before launch."
    assert readiness["next_action"] == "Baseline Center"
    assert by_title["Active baseline HO-006"]["status"] == "warn"
    assert by_title["Active baseline HO-006"]["optimizer_baseline_can_consume"] is False
    assert by_title["Packaging evidence"]["status"] == "warn"
    assert by_title["Selected run alignment"]["status"] == "info"
    assert by_title["Runtime state"]["status"] == "ok"


def test_desktop_optimizer_runtime_launch_readiness_blocks_stale_ho006(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace_dir = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))
    context = _write_stale_optimizer_baseline_context(
        workspace_dir=workspace_dir,
        tmp_path=tmp_path,
    )
    contract_path = Path(context["contract_path"])
    before = contract_path.read_text(encoding="utf-8")
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )

    readiness = runtime.launch_readiness_summary()
    by_title = {
        str(row.get("title") or ""): dict(row)
        for row in tuple(readiness.get("rows") or ())
    }
    ho006_row = by_title["Active baseline HO-006"]

    assert readiness["headline"] == "Review blockers before launch."
    assert readiness["next_action"] == "Baseline Center"
    assert ho006_row["status"] == "warn"
    assert ho006_row["state"] == "stale"
    assert ho006_row["optimizer_baseline_can_consume"] is False
    assert "suite_snapshot_hash_changed" in ho006_row["summary"]
    assert contract_path.read_text(encoding="utf-8") == before


def test_desktop_optimizer_runtime_tracks_latest_pointer_flow(tmp_path: Path) -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )
    runtime.workspace_dir = tmp_path

    coord_run = tmp_path / "opt_runs" / "coord" / "p_pointer_ready"
    (coord_run / "export").mkdir(parents=True)
    (coord_run / "coordinator.log").write_text("coord pointer log", encoding="utf-8")
    (coord_run / "export" / "trials.csv").write_text(
        (
            "status,anim_export_packaging_status,anim_export_packaging_truth_ready,"
            "верификация_флаги,число_runtime_fallback_пружины,"
            "число_пересечений_пружина_цилиндр,число_пересечений_пружина_пружина\n"
            "DONE,complete,1,,0,0,0\n"
        ),
        encoding="utf-8",
    )
    runtime.bind_selected_run_dir(coord_run)

    summary = OptimizationRunSummary(
        run_dir=coord_run,
        pipeline_mode="coordinator",
        backend="Ray",
        status="done",
        status_label="DONE",
        started_at="",
        updated_ts=0.0,
        objective_keys=("comfort", "energy"),
        penalty_key="penalty_total",
        penalty_tol=0.1,
        problem_hash_mode="stable",
    )

    pointer = runtime.save_run_pointer(summary)
    latest = runtime.latest_pointer_summary()

    assert Path(pointer["pointer_path"]).exists()
    assert pointer["run_name"] == "p_pointer_ready"
    assert pointer["selected_from"] == "desktop_optimizer_center"
    assert pointer["selected_matches_pointer"] is True
    assert pointer["pointer_in_history"] is True
    assert latest["run_dir"] == str(coord_run.resolve())
    assert latest["pipeline_mode"] == "coordinator"
    assert latest["backend"] == "Ray"


def test_desktop_optimizer_runtime_exports_selected_run_contract_for_analysis(tmp_path: Path) -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )
    runtime.workspace_dir = tmp_path
    current = runtime.contract_snapshot()

    run_dir = tmp_path / "opt_runs" / "coord" / "p_ho007_ready"
    export_dir = run_dir / "export"
    export_dir.mkdir(parents=True)
    result_path = export_dir / "trials.csv"
    result_path.write_text("status,metrics_json\nDONE,\"{}\"\n", encoding="utf-8")
    (run_dir / "coordinator.log").write_text("done=1/1\n", encoding="utf-8")
    (run_dir / "run_id.txt").write_text("run_ho007_ready", encoding="utf-8")
    (run_dir / "problem_hash.txt").write_text(current.problem_hash, encoding="utf-8")
    (run_dir / "problem_hash_mode.txt").write_text(current.problem_hash_mode, encoding="utf-8")
    (run_dir / "baseline_source.json").write_text(
        json.dumps(
            {
                "source_kind": current.baseline_source_kind,
                "source_label": current.baseline_source_label,
                "baseline_path": current.baseline_path,
                "active_baseline_hash": "active_baseline_hash_001",
                "suite_snapshot_hash": "suite_snapshot_hash_001",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "objective_contract.json").write_text(
        json.dumps(
            objective_contract_payload(
                objective_keys=current.objective_keys,
                penalty_key=current.penalty_key,
                penalty_tol=current.penalty_tol,
                source="desktop_optimizer_center_test",
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    details = runtime.selected_run_details(run_dir)
    assert details is not None
    summary = details.summary
    payload = runtime.export_selected_run_contract(
        summary,
        selected_from="test_desktop_optimizer_center",
        now_text="2026-04-17T00:00:00Z",
    )
    saved_path = Path(payload["selected_run_contract_path"])
    saved = json.loads(saved_path.read_text(encoding="utf-8"))

    assert saved_path == tmp_path / "handoffs" / "WS-OPTIMIZATION" / "selected_run_contract.json"
    assert saved["handoff_id"] == "HO-007"
    assert saved["source_workspace"] == "WS-OPTIMIZATION"
    assert saved["target_workspace"] == "WS-ANALYSIS"
    assert saved["run_id"] == "run_ho007_ready"
    assert saved["mode"] == "distributed_coordinator"
    assert saved["objective_contract_hash"] == objective_contract_hash(
        objective_keys=current.objective_keys,
        penalty_key=current.penalty_key,
        penalty_tol=current.penalty_tol,
    )
    assert saved["hard_gate_key"] == current.penalty_key
    assert saved["hard_gate_tolerance"] == current.penalty_tol
    assert saved["problem_hash"] == current.problem_hash
    assert saved["active_baseline_hash"] == "active_baseline_hash_001"
    assert saved["suite_snapshot_hash"] == "suite_snapshot_hash_001"
    assert saved["results_csv_path"] == str(result_path.resolve())
    assert saved["results_artifact_index"]["objective_contract_path"].endswith("objective_contract.json")
    assert saved["analysis_handoff_ready_state"] == "ready"
    assert saved["diagnostics_handoff_ready_state"] == "not_finalized_by_optimizer"
    assert saved["selected_run_contract_hash"]

    pointer = runtime.save_run_pointer(summary, selected_from="test_desktop_optimizer_center")
    assert pointer["handoff_id"] == "HO-007"
    assert pointer["selected_run_contract_exists"] is True
    assert pointer["analysis_handoff_ready_state"] == "ready"


def test_desktop_optimizer_runtime_blocks_cleanup_while_job_is_active(tmp_path: Path) -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )

    class _Proc:
        returncode = None

        def poll(self):
            return self.returncode

    proc = _Proc()
    job = DistOptJob(
        proc=proc,
        run_dir=tmp_path,
        log_path=tmp_path / "coordinator.log",
        started_ts=1.0,
        budget=4,
        backend="Ray",
        pipeline_mode="coordinator",
        stop_file=tmp_path / "STOP_OPTIMIZATION.txt",
    )
    save_job_to_session(runtime.session_state, job)
    runtime.session_state["__opt_active_launch_context"] = {"kind": "manual"}

    assert runtime.clear_finished_job() is False
    assert load_job_from_session(runtime.session_state) is not None
    assert runtime.request_soft_stop() is True
    assert (tmp_path / "STOP_OPTIMIZATION.txt").exists()

    proc.returncode = 0
    assert runtime.clear_finished_job() is True
    assert load_job_from_session(runtime.session_state) is None
    assert "__opt_active_launch_context" not in runtime.session_state


def test_desktop_optimizer_runtime_builds_selected_run_next_step_summary(tmp_path: Path) -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )
    runtime.workspace_dir = tmp_path

    staged_run = tmp_path / "opt_runs" / "staged" / "p_next_step"
    staged_run.mkdir(parents=True)
    (staged_run / "sp.json").write_text(
        json.dumps({"status": "done", "ts": "2026-04-13T13:00:00"}),
        encoding="utf-8",
    )
    (staged_run / "results_all.csv").write_text(
        (
            "status,anim_export_packaging_status,anim_export_packaging_truth_ready,"
            "верификация_флаги,число_runtime_fallback_пружины,"
            "число_пересечений_пружина_цилиндр,число_пересечений_пружина_пружина\n"
            "DONE,complete,1,,0,0,0\n"
        ),
        encoding="utf-8",
    )
    handoff_dir = staged_run / "coordinator_handoff"
    handoff_dir.mkdir()
    (handoff_dir / "coordinator_handoff_plan.json").write_text(
        json.dumps(
            {
                "recommended_backend": "ray",
                "recommended_budget": 32,
                "recommended_q": 1,
                "recommended_proposer": "botorch",
                "seed_count": 4,
                "suite_analysis": {"family": "full_ring"},
                "requires_full_ring_validation": True,
            }
        ),
        encoding="utf-8",
    )
    runtime.bind_selected_run_dir(staged_run)

    summary = runtime.selected_run_next_step_summary(staged_run)
    by_title = {
        str(row.get("title") or ""): dict(row)
        for row in tuple(summary.get("rows") or ())
    }

    assert summary["headline"] == "Selected staged run is ready for coordinator continuation."
    assert summary["next_action"] == "Handoff"
    assert summary["next_action_kind"] == "show_handoff_tab"
    assert by_title["Packaging route"]["status"] == "ok"
    assert by_title["Continuation route"]["status"] == "ok"
    assert by_title["Latest pointer"]["action_kind"] == "make_latest_pointer"


def test_desktop_optimizer_runtime_builds_finished_jobs_packaging_view(tmp_path: Path) -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )
    runtime.workspace_dir = tmp_path

    staged_run = tmp_path / "opt_runs" / "staged" / "p_stage_done"
    staged_run.mkdir(parents=True)
    (staged_run / "sp.json").write_text(
        json.dumps({"status": "done", "ts": "2026-04-13T10:00:00"}),
        encoding="utf-8",
    )
    (staged_run / "results_all.csv").write_text(
        (
            "status,anim_export_packaging_status,anim_export_packaging_truth_ready,"
            "верификация_флаги,число_runtime_fallback_пружины,"
            "число_пересечений_пружина_цилиндр,число_пересечений_пружина_пружина\n"
            "DONE,complete,1,,0,0,0\n"
        ),
        encoding="utf-8",
    )

    coord_run = tmp_path / "opt_runs" / "coord" / "p_coord_partial"
    (coord_run / "export").mkdir(parents=True)
    (coord_run / "coordinator.log").write_text("coord log", encoding="utf-8")
    (coord_run / "export" / "trials.csv").write_text(
        (
            "status,anim_export_packaging_status,anim_export_packaging_truth_ready,"
            "верификация_флаги,число_runtime_fallback_пружины,"
            "число_пересечений_пружина_цилиндр,число_пересечений_пружина_пружина\n"
            "DONE,partial,0,spring_host_clearance,1,1,0\n"
            "ERROR,,,,,,\n"
        ),
        encoding="utf-8",
    )

    rows = runtime.finished_job_rows()
    overview = runtime.finished_job_overview()

    assert len(rows) == 2
    assert rows[0]["run_dir"] == str(staged_run)
    assert rows[0]["ready_state"] == "truth-ready"
    assert overview["total_jobs"] == 2
    assert overview["truth_ready_jobs"] == 1
    assert overview["verification_pass_jobs"] == 1
    assert overview["interference_jobs"] == 1

    runtime.update_state({"opt_finished_truth_ready_only": True})
    filtered_rows = runtime.finished_job_rows()
    assert len(filtered_rows) == 1
    assert filtered_rows[0]["run_dir"] == str(staged_run)

    packaging_rows = runtime.packaging_rows()
    packaging_overview = runtime.packaging_overview()
    assert len(packaging_rows) == 2
    assert packaging_rows[0]["run_dir"] == str(staged_run)
    assert packaging_rows[0]["ready_state"] == "truth-ready"
    assert packaging_overview["best_run"] == "p_stage_done"
    assert packaging_overview["zero_interference_runs"] == 1
    selected_packaging = runtime.selected_packaging_row(staged_run)
    assert selected_packaging is not None
    assert selected_packaging["runtime_fallback_rows"] == 0

    runtime.update_state({"opt_packaging_zero_interference_only": True})
    zero_risk_rows = runtime.packaging_rows()
    assert len(zero_risk_rows) == 1
    assert zero_risk_rows[0]["run_dir"] == str(staged_run)


def test_desktop_optimizer_runtime_builds_handoff_candidate_view(tmp_path: Path) -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )
    runtime.workspace_dir = tmp_path

    staged_run = tmp_path / "opt_runs" / "staged" / "p_stage_handoff"
    staged_run.mkdir(parents=True)
    (staged_run / "sp.json").write_text(
        json.dumps({"status": "done", "ts": "2026-04-13T11:00:00"}),
        encoding="utf-8",
    )
    handoff_dir = staged_run / "coordinator_handoff"
    handoff_dir.mkdir()
    (handoff_dir / "coordinator_handoff_plan.json").write_text(
        json.dumps(
            {
                "recommended_backend": "ray",
                "recommended_budget": 64,
                "recommended_q": 2,
                "recommended_proposer": "botorch",
                "seed_count": 5,
                "suite_analysis": {"family": "full_ring"},
                "requires_full_ring_validation": True,
                "recommendation_reason": {
                    "fragment_count": 2,
                    "has_full_ring": True,
                    "pipeline_hint": "staged_then_full_ring",
                    "seed_bridge": {
                        "staged_rows_ok": 9,
                        "promotable_rows": 7,
                        "unique_param_candidates": 6,
                        "selection_pool": "pareto",
                        "seed_count": 5,
                    },
                },
                "cmd_args": [
                    "--backend",
                    "ray",
                    "--proposer",
                    "botorch",
                    "--run-dir",
                    str((tmp_path / "opt_runs" / "coord" / "p_coord_handoff").resolve()),
                ],
            }
        ),
        encoding="utf-8",
    )

    rows = runtime.handoff_overview_rows()
    summary = runtime.handoff_overview_summary()
    selected = runtime.selected_handoff_row(staged_run)

    assert len(rows) == 1
    assert rows[0]["run"] == "p_stage_handoff"
    assert rows[0]["preset"] == "ray/botorch/q2"
    assert rows[0]["full_ring"] == "yes"
    assert rows[0]["seeds"] == 5
    assert summary["total_candidates"] == 1
    assert summary["best_run"] == "p_stage_handoff"
    assert selected is not None
    assert selected["budget"] == 64
    assert selected["pool"] == "pareto"


def test_desktop_optimizer_runtime_builds_operator_dashboard_snapshot(tmp_path: Path) -> None:
    runtime = DesktopOptimizerRuntime(
        ui_root=UI_ROOT,
        cpu_count=8,
        platform_name="win32",
    )
    runtime.workspace_dir = tmp_path

    staged_run = tmp_path / "opt_runs" / "staged" / "p_dashboard"
    staged_run.mkdir(parents=True)
    (staged_run / "sp.json").write_text(
        json.dumps({"status": "done", "ts": "2026-04-13T12:00:00"}),
        encoding="utf-8",
    )
    (staged_run / "results_all.csv").write_text(
        (
            "status,anim_export_packaging_status,anim_export_packaging_truth_ready,"
            "верификация_флаги,число_runtime_fallback_пружины,"
            "число_пересечений_пружина_цилиндр,число_пересечений_пружина_пружина\n"
            "DONE,complete,1,,0,0,0\n"
        ),
        encoding="utf-8",
    )
    handoff_dir = staged_run / "coordinator_handoff"
    handoff_dir.mkdir()
    (handoff_dir / "coordinator_handoff_plan.json").write_text(
        json.dumps(
            {
                "recommended_backend": "ray",
                "recommended_budget": 48,
                "recommended_q": 1,
                "recommended_proposer": "botorch",
                "seed_count": 3,
                "suite_analysis": {"family": "full_ring"},
                "requires_full_ring_validation": True,
                "recommendation_reason": {
                    "fragment_count": 1,
                    "has_full_ring": True,
                    "pipeline_hint": "dashboard_test",
                    "seed_bridge": {
                        "staged_rows_ok": 4,
                        "promotable_rows": 3,
                        "unique_param_candidates": 3,
                        "selection_pool": "pareto",
                        "seed_count": 3,
                    },
                },
                "cmd_args": [
                    "--backend",
                    "ray",
                    "--run-dir",
                    str((tmp_path / "opt_runs" / "coord" / "p_dashboard_handoff").resolve()),
                ],
            }
        ),
        encoding="utf-8",
    )

    snapshot = runtime.dashboard_snapshot()

    assert snapshot["launch_profile"]["profile_label"]
    assert snapshot["launch_readiness"]["headline"]
    assert "latest_pointer" in snapshot
    assert snapshot["selected_run_next_step"]["headline"]
    assert snapshot["resume_target"]["launch_pipeline"] == "staged"
    assert snapshot["best_finished_row"] is not None
    assert snapshot["best_finished_row"]["name"] == "p_dashboard"
    assert snapshot["best_handoff_row"] is not None
    assert snapshot["best_handoff_row"]["run"] == "p_dashboard"
    assert snapshot["best_packaging_row"] is not None
    assert snapshot["best_packaging_row"]["name"] == "p_dashboard"


def test_desktop_optimizer_center_keeps_tabbed_modular_architecture() -> None:
    tool_src = (UI_ROOT / "tools" / "desktop_optimizer_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    model_src = (UI_ROOT / "desktop_optimizer_model.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    panels_src = (UI_ROOT / "desktop_optimizer_panels.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    runtime_src = (UI_ROOT / "desktop_optimizer_runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    contract_tab_src = (UI_ROOT / "desktop_optimizer_tabs" / "contract_tab.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    dashboard_tab_src = (UI_ROOT / "desktop_optimizer_tabs" / "dashboard_tab.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    history_tab_src = (UI_ROOT / "desktop_optimizer_tabs" / "history_tab.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    finished_tab_src = (UI_ROOT / "desktop_optimizer_tabs" / "finished_tab.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    handoff_tab_src = (UI_ROOT / "desktop_optimizer_tabs" / "handoff_tab.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    packaging_tab_src = (UI_ROOT / "desktop_optimizer_tabs" / "packaging_tab.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    runtime_tab_src = (UI_ROOT / "desktop_optimizer_tabs" / "runtime_tab.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class DesktopOptimizerCenter" in tool_src
    assert "ttk.Notebook" in tool_src
    assert "DesktopOptimizerDashboardTab" in tool_src
    assert "DesktopOptimizerContractTab" in tool_src
    assert "DesktopOptimizerRuntimeTab" in tool_src
    assert "DesktopOptimizerHistoryTab" in tool_src
    assert "DesktopOptimizerFinishedTab" in tool_src
    assert "DesktopOptimizerHandoffTab" in tool_src
    assert "DesktopOptimizerPackagingTab" in tool_src
    assert "DesktopOptimizerRuntime(" in tool_src
    assert "def refresh_all(self) -> None:" in tool_src
    assert "def refresh_contract(self) -> None:" in tool_src
    assert "def refresh_history(self) -> None:" in tool_src
    assert "def refresh_finished_jobs(self) -> None:" in tool_src
    assert "def refresh_handoff(self) -> None:" in tool_src
    assert "def refresh_packaging(self) -> None:" in tool_src
    assert "def refresh_dashboard(self) -> None:" in tool_src
    assert "self._sync_widget_state()" in tool_src
    assert "def show_dashboard_tab(self) -> None:" in tool_src
    assert "def show_contract_tab(self) -> None:" in tool_src
    assert "def show_runtime_tab(self) -> None:" in tool_src
    assert "def show_history_tab(self) -> None:" in tool_src
    assert "def show_finished_tab(self) -> None:" in tool_src
    assert "def show_handoff_tab(self) -> None:" in tool_src
    assert "def show_packaging_tab(self) -> None:" in tool_src
    assert "def _format_launch_profile_text(self) -> str:" in tool_src
    assert "def _format_launch_readiness_text(self, readiness: dict[str, Any]) -> str:" in tool_src
    assert "def _format_dashboard_pointer_text(self, dashboard: dict[str, Any]) -> str:" in tool_src
    assert "def _format_selected_run_next_step_text(self, payload: dict[str, Any]) -> str:" in tool_src
    assert "def _format_selected_contract_drift_text(self) -> str:" in tool_src
    assert "def _format_dashboard_workspace_text(self) -> str:" in tool_src
    assert "def _format_dashboard_runtime_text(self, dashboard: dict[str, Any]) -> str:" in tool_src
    assert "def _format_handoff_summary_text(self) -> str:" in tool_src
    assert "def _format_finished_overview_text(self) -> str:" in tool_src
    assert "def _format_packaging_overview_text(self) -> str:" in tool_src
    assert "def _format_resume_target_text(self) -> str:" in tool_src
    assert "def follow_launch_readiness_next_action(self) -> None:" in tool_src
    assert "def follow_selected_run_next_step(self) -> None:" in tool_src
    assert "def open_latest_optimization_pointer(self) -> None:" in tool_src
    assert "def make_selected_run_latest_pointer(self) -> None:" in tool_src
    assert "self.runtime.bind_selected_run_dir(self._selected_run_dir)" in tool_src
    assert "def open_selected_results(self) -> None:" in tool_src
    assert "def open_selected_objective_contract(self) -> None:" in tool_src
    assert "def apply_selected_run_contract(self) -> None:" in tool_src
    assert "def apply_launch_profile_label(self, label: str) -> None:" in tool_src
    assert "def on_finished_selection_changed(self) -> None:" in tool_src
    assert "def on_handoff_selection_changed(self) -> None:" in tool_src
    assert "def on_packaging_selection_changed(self) -> None:" in tool_src
    assert "def open_selected_handoff_plan(self) -> None:" in tool_src
    assert "def _schedule_poll(self) -> None:" in tool_src
    assert "def on_host_close(self) -> None:" in tool_src

    assert "class DesktopOptimizerContractSnapshot" in model_src
    assert "DESKTOP_OPTIMIZER_PROFILE_OPTIONS" in model_src
    assert "FINISHED_JOB_SORT_OPTIONS" in model_src
    assert "PACKAGING_SORT_OPTIONS" in model_src
    assert "def apply_launch_profile(" in model_src
    assert "def build_contract_snapshot(" in model_src
    assert "def build_stage_policy_blueprint_rows(" in model_src

    assert "class DesktopOptimizerRuntime" in runtime_src
    assert "def apply_launch_profile(self, profile_key: str) -> dict[str, Any]:" in runtime_src
    assert "def launch_profile_summary(self) -> dict[str, Any]:" in runtime_src
    assert "def launch_readiness_summary(self) -> dict[str, Any]:" in runtime_src
    assert "def save_run_pointer(" in runtime_src
    assert "def latest_pointer_summary(self) -> dict[str, Any]:" in runtime_src
    assert "def selected_run_next_step_summary(" in runtime_src
    assert "def contract_drift_summary(self, summary: OptimizationRunSummary | None) -> dict[str, Any]:" in runtime_src
    assert "def finished_job_rows(self) -> list[dict[str, Any]]:" in runtime_src
    assert "def finished_job_overview(self) -> dict[str, Any]:" in runtime_src
    assert "def packaging_rows(self) -> list[dict[str, Any]]:" in runtime_src
    assert "def packaging_overview(self) -> dict[str, Any]:" in runtime_src
    assert "def selected_packaging_row(" in runtime_src
    assert "def dashboard_snapshot(self) -> dict[str, Any]:" in runtime_src
    assert "def handoff_overview_summary(self) -> dict[str, Any]:" in runtime_src
    assert "def selected_handoff_row(" in runtime_src
    assert "def command_preview_text(self) -> str:" in runtime_src
    assert "def active_job_surface(self) -> dict[str, Any]:" in runtime_src
    assert "def bind_selected_run_dir(self, run_dir: Path | str | None) -> None:" in runtime_src
    assert "def resume_target_summary(self) -> dict[str, Any]:" in runtime_src
    assert "def apply_run_contract(self, summary: OptimizationRunSummary) -> dict[str, Any]:" in runtime_src
    assert "def selected_run_details(" in runtime_src

    assert "class HandoffTreePanel" in panels_src
    assert "class PackagingTreePanel" in panels_src
    assert "class DesktopOptimizerDashboardTab" in dashboard_tab_src
    assert "class DesktopOptimizerContractTab" in contract_tab_src
    assert "class DesktopOptimizerRuntimeTab" in runtime_tab_src
    assert "class DesktopOptimizerHistoryTab" in history_tab_src
    assert "class DesktopOptimizerFinishedTab" in finished_tab_src
    assert "class DesktopOptimizerHandoffTab" in handoff_tab_src
    assert "class DesktopOptimizerPackagingTab" in packaging_tab_src
    assert 'text="Расхождение выбранного прогона с текущим запуском"' in contract_tab_src
    assert 'text="Применить контракт"' in contract_tab_src
    assert 'text="Быстрые переходы"' in dashboard_tab_src
    assert 'text="Состояние рабочей области"' in dashboard_tab_src
    assert 'text="Готовность к запуску и checklist"' in dashboard_tab_src
    assert 'text="Последний указатель оптимизации"' in dashboard_tab_src
    assert 'text="Следующий шаг по выбранному прогону"' in dashboard_tab_src
    assert 'text="Последний указатель"' in dashboard_tab_src
    assert 'text="Следующий шаг выбранного прогона"' in dashboard_tab_src
    assert 'text="Лучший прогон для выпуска"' in dashboard_tab_src
    assert 'values=("stable", "legacy")' in contract_tab_src
    assert 'text="Профили запуска"' in runtime_tab_src
    assert 'text="Применить профиль"' in runtime_tab_src
    assert 'text="Готовность к запуску"' in runtime_tab_src
    assert 'text="Следующий рекомендуемый шаг"' in runtime_tab_src
    assert 'text="Источник продолжения"' in runtime_tab_src
    assert "HANDOFF_SORT_OPTIONS" in history_tab_src
    assert 'text="Сводка по передаче"' in history_tab_src
    assert 'text="Открыть результаты"' in history_tab_src
    assert 'text="Контракт целей"' in history_tab_src
    assert 'text="Применить контракт"' in history_tab_src
    assert 'text="Сделать текущим указателем"' in history_tab_src
    assert 'text="План передачи"' in history_tab_src
    assert 'text="Фильтры готовых прогонов"' in finished_tab_src
    assert 'text="Сделать текущим указателем"' in finished_tab_src
    assert 'text="Ранжирование для выпуска"' in finished_tab_src
    assert 'text="Фильтры кандидатов на передачу"' in handoff_tab_src
    assert 'text="Сделать текущим указателем"' in handoff_tab_src
    assert 'text="Ранжирование продолжения"' in handoff_tab_src
    assert 'text="Фильтры выпуска"' in packaging_tab_src
    assert 'text="Сделать текущим указателем"' in packaging_tab_src
    assert 'text="Ранжирование по готовности"' in packaging_tab_src
