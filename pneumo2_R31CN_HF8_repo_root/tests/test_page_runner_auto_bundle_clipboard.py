from __future__ import annotations

import json
import sys
import types
from pathlib import Path

# _page_runner imports streamlit at module import time; provide a tiny stub.
if 'streamlit' not in sys.modules:
    sys.modules['streamlit'] = types.SimpleNamespace()

from pneumo_solver_ui.pages import _page_runner


def test_copy_bundle_to_clipboard_writes_status_sidecar(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "SEND_test_bundle.zip"
    bundle.write_bytes(b"zip")

    monkeypatch.setattr(_page_runner, '_safe_write_text', lambda path, text: Path(path).write_text(text, encoding='utf-8'))

    from pneumo_solver_ui.tools import clipboard_file

    monkeypatch.setattr(clipboard_file, 'copy_file_to_clipboard', lambda path: (True, f'Copied file to clipboard (CF_HDROP): {path}'))

    ok, msg = _page_runner._copy_bundle_to_clipboard(bundle)
    assert ok is True
    assert 'CF_HDROP' in msg

    sidecar = bundle.parent / 'latest_send_bundle_clipboard_status.json'
    payload = json.loads(sidecar.read_text(encoding='utf-8'))
    assert payload['ok'] is True
    assert payload['zip_path'] == str(bundle)


def test_copy_bundle_to_clipboard_marks_text_fallback_as_not_full_success(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "SEND_test_bundle.zip"
    bundle.write_bytes(b"zip")

    monkeypatch.setattr(_page_runner, '_safe_write_text', lambda path, text: Path(path).write_text(text, encoding='utf-8'))

    from pneumo_solver_ui.tools import clipboard_file

    monkeypatch.setattr(clipboard_file, 'copy_file_to_clipboard', lambda path: (True, 'Fallback(text): Copied path as text'))

    ok, msg = _page_runner._copy_bundle_to_clipboard(bundle)
    assert ok is False
    assert 'Copied path as text' in msg

    sidecar = bundle.parent / 'latest_send_bundle_clipboard_status.json'
    payload = json.loads(sidecar.read_text(encoding='utf-8'))
    assert payload['ok'] is False
