from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_run_history import discover_workspace_optimization_runs, format_run_choice
from pneumo_solver_ui.optimization_runtime_paths import build_optimization_run_dir


def test_r31cq_build_optimization_run_dir_keeps_unique_short_tokens_for_sequential_launches(tmp_path: Path) -> None:
    run_a = build_optimization_run_dir(tmp_path, 'coord', 'coordinator_20260403_120001')
    run_b = build_optimization_run_dir(tmp_path, 'coord', 'coordinator_20260403_120502')
    run_c = build_optimization_run_dir(tmp_path, 'staged', 'staged_20260403_120001')
    run_d = build_optimization_run_dir(tmp_path, 'staged', 'staged_20260403_120502')

    assert run_a != run_b
    assert run_c != run_d
    assert len(run_a.name) <= 14
    assert len(run_b.name) <= 14
    assert len(run_c.name) <= 14
    assert len(run_d.name) <= 14


def test_r31cq_workspace_history_surfaces_staged_and_coordinator_runs_side_by_side(tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    staged = workspace / 'opt_runs' / 'staged' / 'p_staged_a1b2'
    coord = workspace / 'opt_runs' / 'coord' / 'p_coord_c3d4'
    staged.mkdir(parents=True)
    coord.mkdir(parents=True)

    (staged / 'sp.json').write_text(
        '{"status": "done", "ts": "2026-04-03 11:45:00", "combined_csv": ""}',
        encoding='utf-8',
    )
    (staged / 'results_all.csv').write_text('id,val\n1,2\n2,3\n', encoding='utf-8')

    export_dir = coord / 'export'
    export_dir.mkdir(parents=True)
    (export_dir / 'trials.csv').write_text(
        'trial_id,status,error_text\n1,DONE,\n2,ERROR,bad physics\n3,RUNNING,\n',
        encoding='utf-8',
    )
    (coord / 'coordinator.log').write_text('Compute Failed\n', encoding='utf-8')

    items = discover_workspace_optimization_runs(workspace)
    labels = [format_run_choice(item) for item in items]

    assert len(items) == 2
    assert any(item.pipeline_mode == 'staged' and item.status == 'done' and item.row_count == 2 for item in items)
    assert any(item.pipeline_mode == 'coordinator' and item.status == 'partial' and item.done_count == 1 and item.running_count == 1 and item.error_count == 1 for item in items)
    assert any('StageRunner' in label for label in labels)
    assert any('Distributed coordinator' in label for label in labels)


def test_r31cq_workspace_history_maps_cached_pending_and_failed_trial_statuses(tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    coord = workspace / 'opt_runs' / 'coord' / 'p_coord_status_aliases'
    export_dir = coord / 'export'
    export_dir.mkdir(parents=True)
    (export_dir / 'trials.csv').write_text(
        'trial_id,status,error_text\n'
        '1,CACHED,\n'
        '2,RESERVED,\n'
        '3,FAILED,ray worker exception\n',
        encoding='utf-8',
    )
    (coord / 'coordinator.log').write_text('resume coordinator\n', encoding='utf-8')

    items = discover_workspace_optimization_runs(workspace)
    assert len(items) == 1
    summary = items[0]
    assert summary.pipeline_mode == 'coordinator'
    assert summary.done_count == 1
    assert summary.running_count == 1
    assert summary.error_count == 1
    assert summary.status == 'partial'
    assert summary.last_error == 'ray worker exception'
