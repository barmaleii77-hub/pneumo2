from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.ui_data_helpers import decimate_minmax, downsample_df, write_tests_index_csv


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ENTRYPOINTS = [
    REPO_ROOT / "pneumo_solver_ui" / "app.py",
    REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py",
]


def test_write_tests_index_csv_creates_expected_minimal_index(tmp_path: Path) -> None:
    out = write_tests_index_csv(
        tmp_path / "osc",
        [{"name": "alpha"}, {}, {"name": "gamma"}],
    )
    assert out.name == "tests_index.csv"
    content = out.read_text(encoding="utf-8-sig")
    assert "имя_теста" in content
    df = pd.read_csv(out, encoding="utf-8-sig")
    assert df.to_dict("records") == [
        {"test_num": 1, "имя_теста": "alpha", "npz_file": "T01_osc.npz"},
        {"test_num": 2, "имя_теста": "T02", "npz_file": "T02_osc.npz"},
        {"test_num": 3, "имя_теста": "gamma", "npz_file": "T03_osc.npz"},
    ]


def test_downsample_df_and_decimate_minmax_preserve_bounds_and_spikes() -> None:
    df = pd.DataFrame({"t": np.arange(10), "y": np.arange(10) * 2})
    sampled = downsample_df(df, max_points=4)
    assert len(sampled) == 4
    assert sampled.iloc[0]["t"] == 0
    assert sampled.iloc[-1]["t"] == 9

    x = np.arange(10, dtype=float)
    y = np.array([0.0, 0.0, 10.0, 0.0, 0.0, -8.0, 0.0, 0.0, 0.0, 1.0], dtype=float)
    dx, dy = decimate_minmax(x, y, max_points=6)
    assert dx[0] == 0.0
    assert dx[-1] == 9.0
    assert 10.0 in dy
    assert -8.0 in dy
    assert len(dx) == len(dy)


def test_large_ui_entrypoints_import_shared_data_helpers() -> None:
    for path in UI_ENTRYPOINTS:
        src = path.read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_data_helpers import decimate_minmax, downsample_df, write_tests_index_csv" in src
        assert "def write_tests_index_csv(" not in src
        assert "def downsample_df(" not in src
        assert "def decimate_minmax(" not in src
