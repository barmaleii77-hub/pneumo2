from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_launcher_cmd_prefers_vbs_or_pyw() -> None:
    cmd_text = (ROOT / 'START_PNEUMO_APP.cmd').read_text(encoding='utf-8', errors='replace').lower()
    assert 'pause' not in cmd_text
    assert 'start_pneumo_app.vbs' in cmd_text or 'start_pneumo_app.pyw' in cmd_text


def test_root_launcher_vbs_exists_and_targets_pyw() -> None:
    vbs = ROOT / 'START_PNEUMO_APP.vbs'
    assert vbs.exists()
    txt = vbs.read_text(encoding='utf-8', errors='replace').lower()
    assert 'start_pneumo_app.pyw' in txt
    assert 'wscript.shell' in txt
