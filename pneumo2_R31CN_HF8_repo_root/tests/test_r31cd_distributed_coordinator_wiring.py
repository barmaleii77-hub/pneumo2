from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_distributed_wiring import (
    append_coordinator_runtime_args,
    migrated_ray_runtime_env_json,
    migrated_ray_runtime_env_mode,
)
from pneumo_solver_ui.tools.dist_opt_coordinator import build_arg_parser, resolve_proposer_mode


def _flag_values(cmd: list[str], flag: str) -> list[str]:
    vals: list[str] = []
    for i, token in enumerate(cmd[:-1]):
        if token == flag:
            vals.append(cmd[i + 1])
    return vals


def test_r31cd_parser_accepts_restored_runtime_and_botorch_flags() -> None:
    parser = build_arg_parser()
    ns = parser.parse_args(
        [
            "--backend",
            "ray",
            "--ray-address",
            "local",
            "--ray-runtime-env",
            "on",
            "--ray-runtime-env-json",
            '{"env_vars": {"OMP_NUM_THREADS": "1"}}',
            "--ray-runtime-exclude",
            "runs/",
            "--ray-local-num-cpus",
            "12",
            "--ray-local-dashboard",
            "--ray-local-dashboard-port",
            "8265",
            "--ray-num-evaluators",
            "6",
            "--ray-cpus-per-evaluator",
            "1.5",
            "--ray-num-proposers",
            "2",
            "--ray-gpus-per-proposer",
            "0.5",
            "--proposer-buffer",
            "77",
            "--db-engine",
            "duckdb",
            "--db",
            "runs/exp.duckdb",
            "--resume",
            "--run-id",
            "RID-123",
            "--stale-ttl-sec",
            "1800",
            "--no-hv-log",
            "--export-every",
            "13",
            "--n-init",
            "21",
            "--min-feasible",
            "5",
            "--botorch-num-restarts",
            "17",
            "--botorch-raw-samples",
            "1024",
            "--botorch-maxiter",
            "333",
            "--botorch-ref-margin",
            "0.25",
            "--botorch-no-normalize-objectives",
            "--dask-threads-per-worker",
            "3",
            "--dask-memory-limit",
            "4GB",
            "--dask-dashboard-address",
            ":0",
        ]
    )
    assert ns.ray_runtime_env == "on"
    assert ns.ray_runtime_env_json == '{"env_vars": {"OMP_NUM_THREADS": "1"}}'
    assert ns.ray_local_num_cpus == 12
    assert ns.ray_local_dashboard is True
    assert ns.ray_local_dashboard_port == 8265
    assert ns.ray_num_evaluators == 6
    assert ns.ray_cpus_per_evaluator == 1.5
    assert ns.ray_num_proposers == 2
    assert ns.ray_gpus_per_proposer == 0.5
    assert ns.proposer_buffer == 77
    assert ns.db_engine == "duckdb"
    assert ns.resume is True
    assert ns.run_id == "RID-123"
    assert ns.stale_ttl_sec == 1800
    assert ns.hv_log is False
    assert ns.export_every == 13
    assert ns.n_init == 21
    assert ns.min_feasible == 5
    assert ns.botorch_num_restarts == 17
    assert ns.botorch_raw_samples == 1024
    assert ns.botorch_maxiter == 333
    assert ns.botorch_ref_margin == 0.25
    assert ns.botorch_no_normalize_objectives is True
    assert ns.dask_threads_per_worker == 3
    assert ns.dask_memory_limit == "4GB"
    assert ns.dask_dashboard_address == ":0"


def test_r31cd_resolve_proposer_mode_honors_warmup_and_feasible_gates() -> None:
    args = SimpleNamespace(proposer="auto", n_init=12, min_feasible=3)
    early = resolve_proposer_mode(args, done_n=11, feasible_n=10, dim=5)
    assert early["mode"] == "random"
    assert early["ready_by_done"] is False
    assert early["ready_by_feasible"] is True

    gated = resolve_proposer_mode(args, done_n=12, feasible_n=2, dim=5)
    assert gated["mode"] == "random"
    assert gated["ready_by_done"] is True
    assert gated["ready_by_feasible"] is False

    ready = resolve_proposer_mode(args, done_n=12, feasible_n=3, dim=5)
    assert ready["mode"] == "qnehvi"
    assert ready["ready_by_done"] is True
    assert ready["ready_by_feasible"] is True

    portfolio_args = SimpleNamespace(proposer="portfolio", n_init=4, min_feasible=2)
    cold_portfolio = resolve_proposer_mode(portfolio_args, done_n=3, feasible_n=9, dim=2)
    assert cold_portfolio["mode"] == "random"
    assert cold_portfolio["portfolio_enabled"] is False

    hot_portfolio = resolve_proposer_mode(portfolio_args, done_n=4, feasible_n=2, dim=2)
    assert hot_portfolio["mode"] == "portfolio"
    assert hot_portfolio["portfolio_enabled"] is True


def test_r31cd_runtime_arg_builder_restores_real_wiring_for_dask_and_ray() -> None:
    dask_state = {
        "dask_mode": "Локальный кластер (создать автоматически)",
        "dask_workers": 4,
        "dask_threads_per_worker": 2,
        "dask_memory_limit": "4GB",
        "dask_dashboard_address": ":0",
        "opt_db_path": "runs/local.sqlite",
        "opt_db_engine": "sqlite",
        "opt_resume": True,
        "opt_dist_run_id": "R31CD-DASK",
        "opt_stale_ttl_sec": 123,
        "opt_hv_log": False,
        "opt_export_every": 7,
        "opt_botorch_n_init": 11,
        "opt_botorch_min_feasible": 2,
        "opt_botorch_num_restarts": 9,
        "opt_botorch_raw_samples": 256,
        "opt_botorch_maxiter": 50,
        "opt_botorch_ref_margin": 0.33,
        "opt_botorch_normalize_objectives": False,
    }
    dask_cmd = append_coordinator_runtime_args(["python", "coord.py"], dask_state, backend_cli="dask")
    assert _flag_values(dask_cmd, "--dask-workers") == ["4"]
    assert _flag_values(dask_cmd, "--dask-threads-per-worker") == ["2"]
    assert _flag_values(dask_cmd, "--dask-memory-limit") == ["4GB"]
    assert _flag_values(dask_cmd, "--dask-dashboard-address") == [":0"]
    assert _flag_values(dask_cmd, "--db") == ["runs/local.sqlite"]
    assert _flag_values(dask_cmd, "--db-engine") == ["sqlite"]
    assert "--resume" in dask_cmd
    assert _flag_values(dask_cmd, "--run-id") == ["R31CD-DASK"]
    assert _flag_values(dask_cmd, "--stale-ttl-sec") == ["123"]
    assert "--no-hv-log" in dask_cmd
    assert _flag_values(dask_cmd, "--export-every") == ["7"]
    assert _flag_values(dask_cmd, "--n-init") == ["11"]
    assert _flag_values(dask_cmd, "--min-feasible") == ["2"]
    assert _flag_values(dask_cmd, "--botorch-num-restarts") == ["9"]
    assert _flag_values(dask_cmd, "--botorch-raw-samples") == ["256"]
    assert _flag_values(dask_cmd, "--botorch-maxiter") == ["50"]
    assert _flag_values(dask_cmd, "--botorch-ref-margin") == ["0.33"]
    assert "--botorch-no-normalize-objectives" in dask_cmd

    ray_state = {
        "ray_mode": "Подключиться к кластеру",
        "ray_address": "auto",
        "ray_runtime_env_mode": "on",
        "ray_runtime_env_json": '{"env_vars": {"OMP_NUM_THREADS": "1"}}',
        "ray_runtime_exclude": "runs/\n__pycache__/",
        "ray_num_evaluators": 8,
        "ray_cpus_per_evaluator": 1.5,
        "ray_num_proposers": 2,
        "ray_gpus_per_proposer": 0.5,
        "proposer_buffer": 99,
        "opt_db_engine": "duckdb",
        "opt_hv_log": True,
        "opt_export_every": 15,
        "opt_botorch_n_init": 30,
        "opt_botorch_min_feasible": 4,
        "opt_botorch_num_restarts": 20,
        "opt_botorch_raw_samples": 1024,
        "opt_botorch_maxiter": 300,
        "opt_botorch_ref_margin": 0.2,
        "opt_botorch_normalize_objectives": True,
    }
    assert migrated_ray_runtime_env_mode(ray_state) == "on"
    assert migrated_ray_runtime_env_json(ray_state) == '{"env_vars": {"OMP_NUM_THREADS": "1"}}'
    ray_cmd = append_coordinator_runtime_args(["python", "coord.py"], ray_state, backend_cli="ray")
    assert _flag_values(ray_cmd, "--ray-address") == ["auto"]
    assert _flag_values(ray_cmd, "--ray-runtime-env") == ["on"]
    assert _flag_values(ray_cmd, "--ray-runtime-env-json") == ['{"env_vars": {"OMP_NUM_THREADS": "1"}}']
    assert _flag_values(ray_cmd, "--ray-runtime-exclude") == ["runs/", "__pycache__/"]
    assert _flag_values(ray_cmd, "--ray-num-evaluators") == ["8"]
    assert _flag_values(ray_cmd, "--ray-cpus-per-evaluator") == ["1.5"]
    assert _flag_values(ray_cmd, "--ray-num-proposers") == ["2"]
    assert _flag_values(ray_cmd, "--ray-gpus-per-proposer") == ["0.5"]
    assert _flag_values(ray_cmd, "--proposer-buffer") == ["99"]
    assert _flag_values(ray_cmd, "--db-engine") == ["duckdb"]
    assert "--hv-log" in ray_cmd
    assert _flag_values(ray_cmd, "--export-every") == ["15"]
    assert _flag_values(ray_cmd, "--n-init") == ["30"]
    assert _flag_values(ray_cmd, "--min-feasible") == ["4"]
    assert "--botorch-no-normalize-objectives" not in ray_cmd


def test_r31cd_ui_surfaces_expose_real_distributed_controls() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    page03 = (repo_root / "pneumo_solver_ui" / "pages" / "03_Optimization.py").read_text(encoding="utf-8")
    page03_persistence = (
        repo_root / "pneumo_solver_ui" / "optimization_coordinator_persistence_ui.py"
    ).read_text(encoding="utf-8")
    page03_botorch = (
        repo_root / "pneumo_solver_ui" / "optimization_botorch_advanced_ui.py"
    ).read_text(encoding="utf-8")
    page03_launch_plan = (
        repo_root / "pneumo_solver_ui" / "optimization_launch_plan_runtime.py"
    ).read_text(encoding="utf-8")
    main_ui = (repo_root / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    page03_combined = page03 + "\n" + page03_persistence + "\n" + page03_botorch + "\n" + page03_launch_plan

    for text in (page03_combined, main_ui):
        assert "ray_runtime_env_mode" in text
        assert "ray_runtime_env_json" in text
        assert "opt_botorch_n_init" in text
        assert "opt_botorch_min_feasible" in text
        assert "opt_botorch_num_restarts" in text
        assert "opt_botorch_raw_samples" in text
        assert "opt_botorch_maxiter" in text
        assert "opt_botorch_ref_margin" in text
        assert "opt_botorch_normalize_objectives" in text
        assert "duckdb" in text
        assert "requirements_mobo_botorch.txt" in text

    assert "render_coordinator_persistence_controls" in page03
    assert "render_botorch_advanced_controls" in page03
    assert "build_optimization_launch_plan" in page03
    assert "append_coordinator_runtime_args" in page03_combined
