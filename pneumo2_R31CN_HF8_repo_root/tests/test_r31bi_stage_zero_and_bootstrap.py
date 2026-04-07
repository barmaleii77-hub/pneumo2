from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_r31bi_ring_editor_uses_zero_based_stage_numbering() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'ui_scenario_ring.py').read_text(encoding='utf-8')
    assert 'Канон staged-optimization в проекте 0-based: первая стадия = 0.' in src
    assert 'return 0' in src
    assert 'min_value=0,' in src
    assert 'Нумерация 0-based: первая стадия = 0.' in src


def test_r31bi_suite_restore_normalizes_stage_numbers_before_filtering() -> None:
    ui_src = (ROOT / 'pneumo_solver_ui' / 'pneumo_ui_app.py').read_text(encoding='utf-8')
    contract_src = (ROOT / 'pneumo_solver_ui' / 'optimization_input_contract.py').read_text(encoding='utf-8')
    assert 'normalize_suite_stage_numbers' in ui_src
    assert 'legacy_bias_rebase_disabled' in contract_src


def test_r31bi_worker_and_stage_runner_publish_bootstrap_progress_before_heavy_startup() -> None:
    worker_src = (ROOT / 'pneumo_solver_ui' / 'opt_worker_v3_margins_energy.py').read_text(encoding='utf-8')
    stage_src = (ROOT / 'pneumo_solver_ui' / 'opt_stage_runner_v1.py').read_text(encoding='utf-8')

    assert '"статус": "bootstrapping"' in worker_src
    assert 'model = load_model(args.model)' in worker_src
    assert worker_src.index('"статус": "bootstrapping"') < worker_src.index('model = load_model(args.model)')

    assert 'worker_progress_path = stage_worker_progress_path(stage_out_csv)' in stage_src
    assert '"статус": "bootstrapping"' in stage_src
    assert 'startup_grace_sec = float(min(180.0, max(90.0, stage_budget_sec * 0.50)))' in stage_src
