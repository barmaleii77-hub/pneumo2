from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_persistence as up


def test_pick_state_dir_prefers_project_workspace_over_appdata(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    app_here = repo / 'pneumo_solver_ui'
    app_here.mkdir(parents=True)

    appdata = tmp_path / 'appdata'
    monkeypatch.delenv('PNEUMO_STATE_DIR', raising=False)
    monkeypatch.delenv('PNEUMO_UI_STATE_DIR', raising=False)
    monkeypatch.delenv('PNEUMO_WORKSPACE_DIR', raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(appdata))
    monkeypatch.setenv('PNEUMO_RELEASE', 'PneumoApp_v6_80_R176')

    state_dir = up.pick_state_dir(app_here=app_here)
    assert state_dir == repo / 'workspace' / 'ui_state'
    assert state_dir != appdata / 'UnifiedPneumoApp' / 'ui_state' / 'v6_80'


def test_build_state_dict_drops_runtime_path_keys() -> None:
    state = {
        'ui_autosave_enabled': True,
        'ui_model_path': 'C:/old_release/pneumo_solver_ui/model.py',
        'ui_worker_path': 'C:/old_release/pneumo_solver_ui/worker.py',
        'anim_latest_npz': 'C:/old_release/workspace/exports/anim_latest.npz',
        'baseline_cache_dir': 'C:/old_release/workspace/cache/baseline',
        'ui_params_selected_key': 'ISO_b_default',
    }

    out = up.build_state_dict(state)

    assert 'ui_model_path' not in out
    assert 'ui_worker_path' not in out
    assert 'anim_latest_npz' not in out
    assert 'baseline_cache_dir' not in out
    assert out['ui_params_selected_key'] == 'ISO_b_default'
    assert '_repo_root' in out
    assert '_workspace_root' in out


def test_sanitize_loaded_state_drops_foreign_absolute_paths(tmp_path: Path) -> None:
    repo_current = tmp_path / 'repo_current'
    app_here = repo_current / 'pneumo_solver_ui'
    app_here.mkdir(parents=True)

    repo_old = tmp_path / 'repo_old'
    model_old = repo_old / 'pneumo_solver_ui' / 'model.py'
    model_old.parent.mkdir(parents=True)
    model_old.write_text('# old model\n', encoding='utf-8')

    state = {
        '_schema': 4,
        '_repo_root': str(repo_old),
        '_workspace_root': str(repo_old / 'workspace'),
        'ui_autosave_enabled': True,
        'ui_model_path': str(model_old),
        'anim_latest_npz': str(repo_old / 'workspace' / 'exports' / 'anim_latest.npz'),
        'svg_detail_cache': str(repo_old / 'workspace' / 'cache' / 'detail.pkl.gz'),
        'ui_params_selected_key': 'ISO_b_default',
        'diag_output_dir': 'send_bundles',
    }

    sanitized = up.sanitize_loaded_state(state, app_here=app_here)

    assert sanitized['ui_params_selected_key'] == 'ISO_b_default'
    assert sanitized['diag_output_dir'] == 'send_bundles'
    assert 'ui_model_path' not in sanitized
    assert 'anim_latest_npz' not in sanitized
    assert 'svg_detail_cache' not in sanitized
