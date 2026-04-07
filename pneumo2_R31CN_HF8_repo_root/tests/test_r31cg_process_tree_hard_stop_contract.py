from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_r31cg_legacy_ui_hard_stop_uses_process_tree() -> None:
    src = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8", errors="replace")
    assert 'from pneumo_solver_ui.process_tree import terminate_process_tree' in src
    assert 'terminate_process_tree(p, grace_sec=0.8, reason="optimization_hard_stop")' in src


def test_r31cg_engineering_optimization_page_hard_stop_uses_process_tree() -> None:
    src = (ROOT / "pneumo_solver_ui" / "pages" / "03_Optimization.py").read_text(encoding="utf-8", errors="replace")
    assert 'from pneumo_solver_ui.process_tree import terminate_process_tree' in src
    assert 'terminate_process_tree(proc, grace_sec=0.8, reason="optimization_hard_stop")' in src


def test_r31cg_stage_runner_timeout_shutdown_uses_process_tree() -> None:
    src = (ROOT / "pneumo_solver_ui" / "opt_stage_runner_v1.py").read_text(encoding="utf-8", errors="replace")
    assert 'from pneumo_solver_ui.process_tree import terminate_process_tree' in src
    assert 'terminate_process_tree(proc, grace_sec=0.8, reason="stage_runner_worker_startup_timeout")' in src
    assert 'terminate_process_tree(proc, grace_sec=0.8, reason="stage_runner_worker_stall_timeout")' in src
