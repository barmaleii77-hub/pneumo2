from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from pneumo_solver_ui import opt_worker_v3_margins_energy as worker


def test_timeseries_compile_cache_reuses_csv_decode_within_process(tmp_path: Path, monkeypatch) -> None:
    road_csv = tmp_path / "road.csv"
    road_csv.write_text("t,z\n0.0,0.0\n0.1,0.01\n", encoding="utf-8")
    axay_csv = tmp_path / "axay.csv"
    axay_csv.write_text("t,ax,ay\n0.0,0.0,0.0\n0.1,0.2,0.3\n", encoding="utf-8")

    original = worker._read_csv_cached
    calls = {"count": 0}

    def _counting_read_csv(path: str) -> pd.DataFrame:
        calls["count"] += 1
        return original(path)

    monkeypatch.setattr(worker, "_read_csv_cached", _counting_read_csv)
    worker._TS_COMPILED_INPUT_CACHE.clear()

    test = {"road_csv": str(road_csv), "axay_csv": str(axay_csv)}
    compiled_a = worker._compile_timeseries_inputs_cached(dict(test))
    compiled_b = worker._compile_timeseries_inputs_cached(dict(test))

    assert callable(compiled_a["road_func"])
    assert callable(compiled_a["ax_func"])
    assert callable(compiled_a["ay_func"])
    assert callable(compiled_b["road_func"])
    assert callable(compiled_b["ax_func"])
    assert callable(compiled_b["ay_func"])
    assert calls["count"] == 2


def test_eval_candidate_can_reuse_prepared_tests_without_rebuilding_suite(monkeypatch) -> None:
    prepared_tests = [("probe_case", {"t_step": 0.0}, 0.01, 0.02, {})]

    def _unexpected_build(_cfg):
        raise AssertionError("build_test_suite must not be called when prepared tests are provided")

    monkeypatch.setattr(worker, "build_test_suite", _unexpected_build)
    monkeypatch.setattr(worker, "fix_consistency", lambda params: dict(params))
    monkeypatch.setattr(
        worker,
        "eval_candidate_once",
        lambda model, params, test, dt, t_end, targets=None: {
            "RMS_ускор_рамы_м_с2": 1.25,
            "энергия_дроссели_Дж": 2.5,
            "крен_max_град": 3.75,
            "время_успокоения_крен_с": 4.5,
            "доля_времени_отрыв": 0.0,
            "Fmin_шины_Н": 100.0,
        },
    )
    monkeypatch.setattr(worker, "candidate_penalty", lambda metrics, targets: 0.0)
    monkeypatch.setattr(worker, "synthesize_aggregate_objectives_from_available_tests", lambda row: row)

    row = worker.eval_candidate(object(), 7, {"foo": 1.0}, {"sort_tests_by_cost": True}, tests=prepared_tests)

    assert row["id"] == 7
    assert row["probe_case__RMS_ускор_рамы_м_с2"] == 1.25
    assert row["probe_case__энергия_дроссели_Дж"] == 2.5
    assert row["probe_case__крен_max_град"] == 3.75
    assert row["probe_case__время_успокоения_крен_с"] == 4.5


def test_rod_margin_and_speed_tolerates_all_nan_series_without_runtime_warning() -> None:
    df = pd.DataFrame(
        {
            f"положение_штока_Ц1_{corner}_м": [float("nan"), float("nan")]
            for corner in ("ЛП", "ПП", "ЛЗ", "ПЗ")
        }
        | {
            f"скорость_штока_Ц1_{corner}_м_с": [float("nan"), float("nan")]
            for corner in ("ЛП", "ПП", "ЛЗ", "ПЗ")
        }
        | {
            f"положение_штока_Ц2_{corner}_м": [float("nan"), float("nan")]
            for corner in ("ЛП", "ПП", "ЛЗ", "ПЗ")
        }
        | {
            f"скорость_штока_Ц2_{corner}_м_с": [float("nan"), float("nan")]
            for corner in ("ЛП", "ПП", "ЛЗ", "ПЗ")
        }
    )
    params = {
        "ход_штока": 0.32,
        "ход_штока_Ц1_перед_м": 0.32,
        "ход_штока_Ц1_зад_м": 0.32,
        "ход_штока_Ц2_перед_м": 0.32,
        "ход_штока_Ц2_зад_м": 0.32,
    }

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        out = worker.rod_margin_and_speed(df, params)

    assert out["шток_лимитирующий_группа"] == ""
    assert pd.isna(out["мин_запас_до_упора_штока_все_м"])
    assert pd.isna(out["макс_скорость_штока_все_м_с"])
