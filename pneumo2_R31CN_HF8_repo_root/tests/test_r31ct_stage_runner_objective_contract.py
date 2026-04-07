from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pneumo_solver_ui.opt_stage_runner_v1 import pick_best_row, score_row
from pneumo_solver_ui.optimization_defaults import DEFAULT_OPTIMIZATION_OBJECTIVES
from pneumo_solver_ui.optimization_objective_contract import (
    LEGACY_STAGE_RUNNER_OBJECTIVES,
    parse_saved_score_payload,
    score_contract_matches,
)


def _row(*, rid: int, comfort: float, roll: float, energy: float, settle: float, pen: float = 0.0) -> dict:
    return {
        'id': rid,
        'ошибка': '',
        'штраф_физичности_сумма': pen,
        'метрика_комфорт__RMS_ускор_рамы_микро_м_с2': comfort,
        'метрика_крен_ay3_град': roll,
        'метрика_энергия_дроссели_микро_Дж': energy,
        'цель1_устойчивость_инерция__с': settle,
        'цель2_комфорт__RMS_ускор_м_с2': comfort,
    }


def test_r31ct_default_stage_runner_scoring_uses_shared_canonical_objective_stack(tmp_path: Path) -> None:
    csv_path = tmp_path / 'results.csv'
    pd.DataFrame([
        _row(rid=101, comfort=1.0, roll=9.0, energy=1.0, settle=99.0),
        _row(rid=202, comfort=2.0, roll=1.0, energy=1.0, settle=0.1),
    ]).to_csv(csv_path, index=False)

    best = pick_best_row(csv_path)
    assert best is not None
    assert int(best['id']) == 101
    assert score_row(best) == (0.0, 1.0, 9.0, 1.0)


def test_r31ct_stage_runner_can_explicitly_follow_legacy_stability_first_stack(tmp_path: Path) -> None:
    csv_path = tmp_path / 'results.csv'
    pd.DataFrame([
        _row(rid=101, comfort=1.0, roll=9.0, energy=1.0, settle=99.0),
        _row(rid=202, comfort=2.0, roll=1.0, energy=1.0, settle=0.1),
    ]).to_csv(csv_path, index=False)

    best = pick_best_row(csv_path, objective_keys=LEGACY_STAGE_RUNNER_OBJECTIVES)
    assert best is not None
    assert int(best['id']) == 202


def test_r31ct_saved_score_payload_keeps_objective_contract_metadata() -> None:
    legacy = parse_saved_score_payload([0.0, 0.5, 1.2, 3.4])
    assert legacy is not None
    assert legacy['objective_keys'] == list(LEGACY_STAGE_RUNNER_OBJECTIVES)
    assert score_contract_matches(legacy, objective_keys=LEGACY_STAGE_RUNNER_OBJECTIVES, penalty_key='штраф_физичности_сумма') is True

    explicit = parse_saved_score_payload({
        'penalty_key': 'штраф_физичности_сумма',
        'objective_keys': ['цель1_устойчивость_инерция__с', 'метрика_комфорт__RMS_ускор_рамы_микро_м_с2'],
        'score': [0.0, 0.1, 1.5],
    })
    assert explicit is not None
    assert explicit['objective_keys'] == ['цель1_устойчивость_инерция__с', 'метрика_комфорт__RMS_ускор_рамы_микро_м_с2']
