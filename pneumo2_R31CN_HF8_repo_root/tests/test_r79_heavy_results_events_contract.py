from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_heavy_results_runtime_uses_selected_test_context_for_events() -> None:
    text = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")

    assert "test_for_events = {}" in text
    assert 'raw_test = info_pick.get("test")' in text
    assert 'elif any(k in info_pick for k in ("тип", "type", "road_csv", "axay_csv", "t_end", "dt")):' in text
    assert '"test": test_for_events,' in text
    assert '"test": test,' not in text
