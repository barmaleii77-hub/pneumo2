from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.name_sanitize import sanitize_ascii_id, sanitize_id, sanitize_test_name

ROOT = Path(__file__).resolve().parents[1]


def test_r31ay_unicode_run_ids_are_windows_safe_and_readable() -> None:
    assert sanitize_id('Оптимизация рамы / тест:01') == 'Оптимизация_рамы_тест_01'
    assert sanitize_id('..  ') == 'run'


def test_r31ay_reserved_windows_basenames_are_guarded() -> None:
    assert sanitize_id('CON') == '_CON'
    assert sanitize_id('LPT1.txt') == '_LPT1.txt'
    assert sanitize_ascii_id('PRN') == '_PRN'


def test_r31ay_test_name_keeps_unicode_and_hash_suffix() -> None:
    out = sanitize_test_name('Тест комфорт / ay')
    assert out.startswith('Тест_комфорт_ay_')
    assert len(out.split('_')[-1]) == 12


def test_r31ay_key_modules_use_shared_sanitizer_module() -> None:
    app_py = (ROOT / 'pneumo_solver_ui' / 'app.py').read_text(encoding='utf-8')
    ui_py = (ROOT / 'pneumo_solver_ui' / 'pneumo_ui_app.py').read_text(encoding='utf-8')
    stage_py = (ROOT / 'pneumo_solver_ui' / 'opt_stage_runner_v1.py').read_text(encoding='utf-8')

    assert 'from pneumo_solver_ui.name_sanitize import sanitize_ascii_id as _sanitize_id, sanitize_test_name' in app_py
    assert 'from pneumo_solver_ui.name_sanitize import (' in ui_py
    assert 'from pneumo_solver_ui.name_sanitize import sanitize_id' in stage_py
    assert 'def sanitize_id(' not in stage_py
