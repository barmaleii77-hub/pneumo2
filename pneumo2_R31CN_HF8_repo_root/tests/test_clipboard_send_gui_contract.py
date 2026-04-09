from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.tools import clipboard_file


def test_windows_clipboard_fallback_tries_powershell_before_text(tmp_path, monkeypatch) -> None:
    sample = tmp_path / 'sample.zip'
    sample.write_bytes(b'zip')

    monkeypatch.setattr(clipboard_file.sys, 'platform', 'win32')
    monkeypatch.setattr(clipboard_file, '_copy_windows_cf_hdrop', lambda path: (False, 'cf_hdrop failed'))
    monkeypatch.setattr(clipboard_file, '_copy_windows_powershell_filelist', lambda path: (True, 'powershell ok'))
    monkeypatch.setattr(clipboard_file, '_copy_text_fallback', lambda text: (_ for _ in ()).throw(AssertionError('text fallback must not be used')))

    ok, msg = clipboard_file.copy_file_to_clipboard(sample)
    assert ok is True
    assert 'powershell ok' in msg.lower()


def test_send_results_gui_autocopies_and_persists_status_sidecar() -> None:
    src = (Path(__file__).resolve().parents[1] / 'pneumo_solver_ui' / 'tools' / 'send_results_gui.py').read_text(encoding='utf-8')

    assert 'self._attempt_clipboard_copy_once()' in src
    assert 'latest_send_bundle_clipboard_status.json' in src
    assert 'ZIP для отправки в чат готов и уже скопирован в буфер.' in src
    assert 'load_latest_send_bundle_anim_dashboard' in src
    assert 'format_anim_dashboard_brief_lines' in src
    assert 'Anim pointer diagnostics:' in src
