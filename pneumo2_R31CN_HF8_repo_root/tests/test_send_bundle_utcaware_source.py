from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_send_bundle_and_selfcheck_use_timezone_aware_utc_timestamps() -> None:
    send_bundle = (ROOT / "pneumo_solver_ui" / "tools" / "make_send_bundle.py").read_text(encoding="utf-8")
    diag_selfcheck = (ROOT / "pneumo_solver_ui" / "diag" / "selfcheck.py").read_text(encoding="utf-8")

    assert 'datetime.now(UTC)' in send_bundle
    assert 'datetime.utcnow()' not in send_bundle
    assert 'datetime.now(UTC)' in diag_selfcheck
    assert 'datetime.utcnow()' not in diag_selfcheck
