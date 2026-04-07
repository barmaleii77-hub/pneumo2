from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.ui_shared_helpers import (
    best_match,
    name_score,
    norm_name,
    run_starts,
    shorten_name,
)


ROOT = Path(__file__).resolve().parents[1]


def test_run_starts_detects_rising_edges() -> None:
    mask = np.array([False, True, True, False, True, False, True, True], dtype=bool)
    assert run_starts(mask) == [1, 4, 6]


def test_shorten_name_preserves_short_names_and_truncates_long_ones() -> None:
    assert shorten_name("abc", max_len=5) == "abc"
    assert shorten_name("abcdef", max_len=5) == "abcd…"


def test_name_matching_normalizes_dash_and_spacing_variants() -> None:
    assert norm_name(" Valve—Left / Front ") == "valve left front"
    score = name_score("Valve Left Front", "valve-left/front")
    assert score > 0.9
    assert best_match("front-left valve", ["rear valve", "front left valve", "compressor"])[0] == "front left valve"


def test_large_ui_entrypoints_import_shared_helpers_instead_of_redefining_them() -> None:
    for rel in ("pneumo_solver_ui/app.py", "pneumo_solver_ui/pneumo_ui_app.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_shared_helpers import (" in src
        assert "best_match as _best_match" in src
        assert "norm_name as _norm_name" in src
        assert "run_starts as _run_starts" in src
        assert "shorten_name as _shorten_name" in src
        assert "name_score as _name_score" in src
        assert "def _run_starts(" not in src
        assert "def _shorten_name(" not in src
        assert "def _norm_name(" not in src
        assert "def _name_score(" not in src
        assert "def _best_match(" not in src
