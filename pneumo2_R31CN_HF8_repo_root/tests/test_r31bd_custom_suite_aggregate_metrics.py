from __future__ import annotations

from pneumo_solver_ui.opt_worker_v3_margins_energy import synthesize_aggregate_objectives_from_available_tests


def test_custom_suite_ring_metrics_fill_canonical_aggregates() -> None:
    row = {
        "штраф_физичности_сумма": 123.0,
        "метрика_комфорт__RMS_ускор_рамы_микро_м_с2": float("nan"),
        "метрика_энергия_дроссели_микро_Дж": 0.0,
        "метрика_крен_ay3_град": float("nan"),
        "цель1_устойчивость_инерция__с": 999.0,
        "цель2_комфорт__RMS_ускор_м_с2": float("nan"),
        "метрика_раньше_жёстко_ay2__запас_свыше_Pmid_бар": -999.0,
        "ring_test_01__RMS_ускор_рамы_м_с2": 3.6877439509,
        "ring_test_01__крен_peak_град": 11.4909967785,
        "ring_test_01__энергия_дроссели_Дж": 2.6549049716,
        "ring_test_01__время_успокоения_крен_с": 2.75,
        "ring_test_01__запас_свыше_Pmid_бар": -0.42,
    }

    out = synthesize_aggregate_objectives_from_available_tests(dict(row))

    assert out["метрика_комфорт__RMS_ускор_рамы_микро_м_с2"] == row["ring_test_01__RMS_ускор_рамы_м_с2"]
    assert out["цель2_комфорт__RMS_ускор_м_с2"] == row["ring_test_01__RMS_ускор_рамы_м_с2"]
    assert out["метрика_крен_ay3_град"] == row["ring_test_01__крен_peak_град"]
    assert out["метрика_энергия_дроссели_микро_Дж"] == row["ring_test_01__энергия_дроссели_Дж"]
    assert out["цель1_устойчивость_инерция__с"] == row["ring_test_01__время_успокоения_крен_с"]
    assert out["метрика_раньше_жёстко_ay2__запас_свыше_Pmid_бар"] == row["ring_test_01__запас_свыше_Pmid_бар"]


def test_existing_canonical_metrics_are_preserved() -> None:
    row = {
        "метрика_комфорт__RMS_ускор_рамы_микро_м_с2": 1.23,
        "метрика_энергия_дроссели_микро_Дж": 4.56,
        "метрика_крен_ay3_град": 7.89,
        "цель1_устойчивость_инерция__с": 0.75,
        "цель2_комфорт__RMS_ускор_м_с2": 1.23,
        "метрика_раньше_жёстко_ay2__запас_свыше_Pmid_бар": -0.1,
        "ring_test_01__RMS_ускор_рамы_м_с2": 99.0,
        "ring_test_01__крен_peak_град": 99.0,
        "ring_test_01__энергия_дроссели_Дж": 99.0,
        "ring_test_01__время_успокоения_крен_с": 99.0,
        "ring_test_01__запас_свыше_Pmid_бар": -9.9,
    }

    out = synthesize_aggregate_objectives_from_available_tests(dict(row))

    assert out["метрика_комфорт__RMS_ускор_рамы_микро_м_с2"] == 1.23
    assert out["метрика_энергия_дроссели_микро_Дж"] == 4.56
    assert out["метрика_крен_ay3_град"] == 7.89
    assert out["цель1_устойчивость_инерция__с"] == 0.75
    assert out["цель2_комфорт__RMS_ускор_м_с2"] == 1.23
    assert out["метрика_раньше_жёстко_ay2__запас_свыше_Pmid_бар"] == -0.1
