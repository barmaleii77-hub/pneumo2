from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_animator_warning_logging_is_deduplicated_by_key() -> None:
    text = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")

    assert '_ANIMATOR_WARNING_SEEN' in text
    assert 'def _animator_warning_key' in text
    assert 'if warn_key in _ANIMATOR_WARNING_SEEN:' in text
    assert '_ANIMATOR_WARNING_SEEN.add(warn_key)' in text
