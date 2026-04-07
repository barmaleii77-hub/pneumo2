from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pneumo_solver_ui.opt_stage_runner_v1 import collect_seed_points, pick_best_row
from pneumo_solver_ui.optimization_result_rows import filter_display_df, is_baseline_row, is_promotable_row


def _row(*, rid: int, role: str = "search", pen: float = 0.0, obj1: float = 1.0, obj2: float = 1.0, energy: float = 1.0, foo: float = 1.0, err: str | None = None, pruned: bool = False) -> dict:
    return {
        "id": rid,
        "candidate_role": role,
        "meta_source": "baseline" if role == "baseline_anchor" else role,
        "ошибка": err,
        "штраф_физичности_сумма": pen,
        "цель1_устойчивость_инерция__с": obj1,
        "цель2_комфорт__RMS_ускор_м_с2": obj2,
        "метрика_энергия_дроссели_микро_Дж": energy,
        "параметр__foo": foo,
        "pruned_early": 1.0 if pruned else 0.0,
        "pruned_after_test": "ring_test_01" if pruned else "",
    }


def test_filter_display_df_hides_service_baseline_rows() -> None:
    df = pd.DataFrame([
        _row(rid=0, role="baseline_anchor", pen=0.0),
        _row(rid=123, role="search", pen=1.0),
    ])
    filtered = filter_display_df(df, include_baseline=False)
    assert list(filtered["id"]) == [123]
    assert is_baseline_row(df.iloc[0].to_dict()) is True
    assert is_promotable_row(df.iloc[1].to_dict()) is True


def test_pick_best_row_prefers_real_candidate_over_baseline_anchor(tmp_path: Path) -> None:
    csv_path = tmp_path / "results.csv"
    pd.DataFrame([
        _row(rid=0, role="baseline_anchor", pen=0.0, obj1=0.1, obj2=0.1, energy=0.1),
        _row(rid=101, role="search", pen=0.5, obj1=0.5, obj2=0.5, energy=0.5),
    ]).to_csv(csv_path, index=False)
    best = pick_best_row(csv_path)
    assert best is not None
    assert int(best["id"]) == 101


def test_collect_seed_points_ignores_baseline_error_and_pruned_rows(tmp_path: Path) -> None:
    prev_csv = tmp_path / "s0.csv"
    pd.DataFrame([
        _row(rid=0, role="baseline_anchor", pen=0.0, obj1=0.1, obj2=0.1, energy=0.1, foo=2.0),
        _row(rid=111, role="search", pen=0.2, obj1=0.2, obj2=0.2, energy=0.2, foo=3.0),
        _row(rid=222, role="search", pen=0.3, obj1=0.3, obj2=0.3, energy=0.3, foo=4.0, pruned=True),
        _row(rid=333, role="search", pen=0.4, obj1=0.4, obj2=0.4, energy=0.4, foo=5.0, err="boom"),
    ]).to_csv(prev_csv, index=False)

    archive_path = tmp_path / "global_history.jsonl"
    with archive_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(_row(rid=0, role="baseline_anchor", pen=0.0, obj1=0.1, obj2=0.1, energy=0.1, foo=2.0), ensure_ascii=False) + "\n")
        f.write(json.dumps(_row(rid=444, role="search", pen=0.6, obj1=0.6, obj2=0.6, energy=0.6, foo=6.0, pruned=True), ensure_ascii=False) + "\n")

    stage_csvs = [("stage0_relevance", prev_csv), ("stage1_long", tmp_path / "s1.csv")]
    seeds = collect_seed_points(
        stage_idx=1,
        stage_csvs=stage_csvs,
        archive_path=archive_path,
        ranges={"foo": [0.0, 10.0]},
        max_prev=8,
        max_archive=8,
        max_total=8,
    )
    assert len(seeds) == 1
    assert float(seeds[0]["foo"]) == 3.0


def test_worker_and_stage_runner_sources_encode_no_negative_baseline_policy() -> None:
    root = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
    worker = (root / "opt_worker_v3_margins_energy.py").read_text(encoding="utf-8")
    runner = (root / "opt_stage_runner_v1.py").read_text(encoding="utf-8")
    assert "BASELINE_RESULT_ID = 0" in worker
    assert '"--skip_baseline"' in worker
    assert 'SEED_ID_OFFSET = 2_000_000_001' in worker
    assert '_mark_candidate_role(row_seed, "seed")' in worker
    assert '_mark_candidate_role(row, "search")' in worker
    assert '"--skip_baseline",' in runner
    assert 'stage_skipped_no_promotable_candidates' in runner
    assert 'previous stage produced no promotable candidates' in runner
