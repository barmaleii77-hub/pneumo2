from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_all_filter_comparisons_match_visible_label() -> None:
    heavy = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    light = (ROOT / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")

    assert 'options=["(все)"] + test_names' in heavy
    assert 'if pick != "(все)" and name != pick:' in heavy
    assert '"(РІСЃРµ)"' not in heavy

    assert 'options=["(все)"] + groups' in light
    assert 'if grp != "(все)":' in light
    assert 'options=["(все)"] + test_names' in light
    assert 'if pick != "(все)" and name != pick:' in light
    assert '"(РІСЃРµ)"' not in light
