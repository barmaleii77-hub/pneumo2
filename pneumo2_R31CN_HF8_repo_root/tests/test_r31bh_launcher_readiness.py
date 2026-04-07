from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.launcher_readiness import session_log_ready

ROOT = Path(__file__).resolve().parents[1]


def test_session_log_ready_via_ui_event(tmp_path: Path) -> None:
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()
    events = log_dir / 'events.jsonl'
    rows = [
        {"event": "Bootstrap", "ts": "2026-03-29T09:16:05"},
        {"event": "ui_start", "ts": "2026-03-29T09:16:09"},
    ]
    events.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding='utf-8')

    ok, diag = session_log_ready(log_dir)
    assert ok is True
    assert diag["ready_via"] == "event"
    assert diag["ready_event"] == "ui_start"
    assert str(events) in diag["checked_files"]


def test_session_log_ready_via_streamlit_stdout(tmp_path: Path) -> None:
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()
    stdout_log = log_dir / 'streamlit_stdout.log'
    stdout_log.write_text(
        "You can now view your Streamlit app in your browser.\nLocal URL: http://127.0.0.1:8505\n",
        encoding='utf-8',
    )

    ok, diag = session_log_ready(log_dir)
    assert ok is True
    assert diag["ready_via"] == "streamlit_log"
    assert diag["source"] == str(stdout_log)


def test_session_log_ready_false_when_only_bootstrap_exists(tmp_path: Path) -> None:
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()
    events = log_dir / 'events.jsonl'
    rows = [
        {"event": "Bootstrap", "ts": "2026-03-29T09:16:05"},
        {"event": "BootstrapApp", "ts": "2026-03-29T09:16:05"},
    ]
    events.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding='utf-8')

    ok, diag = session_log_ready(log_dir)
    assert ok is False
    assert diag["ready_event"] is None
    assert "Bootstrap" in diag["events_seen_tail"]


def test_launcher_source_contains_session_log_fallback_and_stopped_status() -> None:
    src = (ROOT / 'START_PNEUMO_APP.py').read_text(encoding='utf-8', errors='replace')
    assert '_session_log_ready(log_dir)' in src
    assert 'launcher_ready_source' in src
    assert 'launcher_http_ready' in src
    assert 'status = "stopped"' in src
