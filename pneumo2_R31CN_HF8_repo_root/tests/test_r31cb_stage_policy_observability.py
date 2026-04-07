from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pneumo_solver_ui.optimization_stage_policy import (
    build_stage_seed_budget_plan,
    build_stage_specific_influence_summary,
)
from pneumo_solver_ui.opt_stage_runner_v1 import collect_seed_points
from pneumo_solver_ui.optimization_stage_policy_live import summarize_stage_policy_runtime


def _row(*, rid: int, pen: float, obj1: float, obj2: float, energy: float, params: dict[str, float]) -> dict:
    row = {
        "id": rid,
        "candidate_role": "search",
        "meta_source": "search",
        "ошибка": "",
        "штраф_физичности_сумма": pen,
        "цель1_устойчивость_инерция__с": obj1,
        "цель2_комфорт__RMS_ускор_м_с2": obj2,
        "метрика_энергия_дроссели_микро_Дж": energy,
        "pruned_early": 0.0,
        "pruned_after_test": "",
    }
    for k, v in params.items():
        row[f"параметр__{k}"] = v
    return row


def test_collect_seed_points_writes_seed_manifest_and_live_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    stage_dir = run_dir / "s1"
    stage_dir.mkdir(parents=True)
    prev_csv = tmp_path / "stage_00.csv"
    pd.DataFrame([
        _row(rid=101, pen=0.0, obj1=0.10, obj2=0.10, energy=1.0, params={"foo": 8.0, "bar": 0.1}),
        _row(rid=102, pen=0.0, obj1=0.20, obj2=0.20, energy=1.0, params={"foo": 5.0, "bar": 9.0}),
    ]).to_csv(prev_csv, index=False)

    payload = {"params": [{"param": "bar", "score": 9.0}, {"param": "foo", "score": 1.0}]}
    summary = build_stage_specific_influence_summary(
        "stage2_final",
        active_params=["foo", "bar"],
        influence_payload=payload,
    )
    plan = build_stage_seed_budget_plan(
        "stage2_final",
        total_seed_cap=2,
        requested_mode="influence_weighted",
        stage_influence_summary=summary,
    )
    (stage_dir / "stage_influence_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (stage_dir / "seed_budget_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    seeds = collect_seed_points(
        stage_idx=1,
        stage_csvs=[("stage0_relevance", prev_csv), ("stage2_final", tmp_path / "stage_01.csv")],
        archive_path=tmp_path / "global.jsonl",
        ranges={"foo": [0.0, 10.0], "bar": [0.0, 10.0]},
        base_params={"foo": 5.0, "bar": 0.1},
        stage_name="stage2_final",
        stage_policy_mode="influence_weighted",
        stage_influence_summary=summary,
        budget_plan=plan,
        promotion_log_path=stage_dir / "promotion_policy_decisions.csv",
        seed_manifest_json_path=stage_dir / "seed_points_manifest.json",
        seed_manifest_csv_path=stage_dir / "seed_points_manifest.csv",
        max_prev=2,
        max_archive=0,
        max_total=2,
    )

    assert len(seeds) == 2
    manifest = json.loads((stage_dir / "seed_points_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 2
    assert manifest[0]["selected_bucket"] == "focus"
    assert manifest[0]["row_id"] == 102
    assert manifest[0]["seed_order"] == 1
    assert manifest[1]["selected_bucket"] == "explore"
    assert (stage_dir / "seed_points_manifest.csv").exists()

    live = summarize_stage_policy_runtime(run_dir, stage_idx=1, stage_name="stage2_final")
    assert live["available"] is True
    assert live["effective_mode"] == "influence_weighted"
    assert live["seed_count"] == 2
    assert live["seed_bucket_counts"]["focus"] == 1
    assert live["seed_bucket_counts"]["explore"] == 1
    assert live["seed_preview"][0]["row_id"] == 102


def test_sources_expose_current_screen_stage_policy_observability() -> None:
    root = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
    ui_src = (root / "pneumo_ui_app.py").read_text(encoding="utf-8")
    runner_src = (root / "opt_stage_runner_v1.py").read_text(encoding="utf-8")
    assert "Seed/promotion policy (текущая стадия)" in ui_src
    assert "summarize_stage_policy_runtime" in ui_src
    assert "seed_points_manifest.json" in runner_src
    assert "stage_seed_manifest_json" in runner_src
