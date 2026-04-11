from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui.optimization_stage_policy import (
    build_stage_seed_budget_plan,
    build_stage_specific_influence_summary,
    stage_seed_policy_summary_text,
)
from pneumo_solver_ui.opt_stage_runner_v1 import collect_seed_points


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


def test_stage_specific_summary_and_seed_budget_progressively_focus_later_stages() -> None:
    active_params = [f"p{i:02d}" for i in range(20)]
    payload = {
        "params": [
            {"param": name, "score": float(20 - idx)}
            for idx, name in enumerate(active_params)
        ]
    }

    s0 = build_stage_specific_influence_summary("stage0_relevance", active_params=active_params, influence_payload=payload)
    s1 = build_stage_specific_influence_summary("stage1_long", active_params=active_params, influence_payload=payload)
    s2 = build_stage_specific_influence_summary("stage2_final", active_params=active_params, influence_payload=payload)

    assert s0["summary_status"] == "ok"
    assert len(s0["top_params"]) == 16
    assert len(s1["top_params"]) == 10
    assert len(s2["top_params"]) == 6

    b0 = build_stage_seed_budget_plan("stage0_relevance", total_seed_cap=10, requested_mode="influence_weighted", stage_influence_summary=s0)
    b1 = build_stage_seed_budget_plan("stage1_long", total_seed_cap=10, requested_mode="influence_weighted", stage_influence_summary=s1)
    b2 = build_stage_seed_budget_plan("stage2_final", total_seed_cap=10, requested_mode="influence_weighted", stage_influence_summary=s2)

    assert b0["explore_budget"] == 6 and b0["focus_budget"] == 4
    assert b1["explore_budget"] == 4 and b1["focus_budget"] == 6
    assert b2["explore_budget"] == 2 and b2["focus_budget"] == 8
    assert "stage0_relevance:" in stage_seed_policy_summary_text()
    assert "stage2_final:" in stage_seed_policy_summary_text()


def test_collect_seed_points_influence_weighted_prefers_aligned_candidate_for_later_stage(tmp_path: Path) -> None:
    prev_csv = tmp_path / "stage_00.csv"
    pd.DataFrame([
        _row(rid=101, pen=0.0, obj1=0.10, obj2=0.10, energy=1.0, params={"foo": 8.0, "bar": 0.1}),
        _row(rid=102, pen=0.0, obj1=0.20, obj2=0.20, energy=1.0, params={"foo": 5.0, "bar": 9.0}),
    ]).to_csv(prev_csv, index=False)

    summary = {
        "summary_status": "ok",
        "top_params": ["bar"],
        "priority_mass": {"bar": 1.0},
        "policy_name": "strict_alignment",
    }
    plan = build_stage_seed_budget_plan(
        "stage2_final",
        total_seed_cap=2,
        requested_mode="influence_weighted",
        stage_influence_summary=summary,
    )

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
        max_prev=2,
        max_archive=0,
        max_total=2,
    )

    assert len(seeds) == 2
    assert float(seeds[0]["bar"]) == 9.0
    assert float(seeds[1]["foo"]) == 8.0


def test_zero_signal_summary_falls_back_to_static_budgeting() -> None:
    summary = {
        "summary_status": "zero_signal",
        "priority_mass": {},
        "top_params": [],
    }
    plan = build_stage_seed_budget_plan(
        "stage1_long",
        total_seed_cap=5,
        requested_mode="influence_weighted",
        stage_influence_summary=summary,
    )
    assert plan["effective_mode"] == "static"
    assert plan["explore_budget"] == 5
    assert plan["focus_budget"] == 0
    assert "zero_signal" in plan["fallback_reason"]


def test_ui_and_stage_runner_sources_expose_stage_policy_controls() -> None:
    root = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
    ui_src = (root / "pneumo_ui_app.py").read_text(encoding="utf-8")
    runner_src = (root / "opt_stage_runner_v1.py").read_text(encoding="utf-8")
    assert '"Политика отбора и продвижения"' in ui_src
    assert 'stage_seed_policy_summary_text()' in ui_src
    assert '"--stage_policy_mode"' in runner_src
    assert 'stage_specific_influence_summary.json' in runner_src
    assert 'promotion_policy_decisions.csv' in runner_src
