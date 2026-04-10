from __future__ import annotations

from pneumo_solver_ui.optimization_objective_contract import (
    normalize_objective_keys,
    parse_saved_score_payload,
    score_contract_matches,
)


def test_normalize_objective_keys_accepts_text_json_and_nested_sequences() -> None:
    assert normalize_objective_keys('comfort,\nroll;energy') == ('comfort', 'roll', 'energy')
    assert normalize_objective_keys('["comfort", "roll", "energy"]') == ('comfort', 'roll', 'energy')
    assert normalize_objective_keys(['comfort', ' roll ; energy ', ['comfort', 'packaging']]) == (
        'comfort',
        'roll',
        'energy',
        'packaging',
    )


def test_parse_saved_score_payload_preserves_string_objective_contracts() -> None:
    payload = parse_saved_score_payload(
        {
            'score': [1, 2, 3],
            'objective_keys': 'comfort,\nroll;energy',
            'penalty_key': 'penalty_total',
            'penalty_tol': 0.5,
            'source': 'legacy_string_payload',
        }
    )

    assert payload is not None
    assert payload['objective_keys'] == ['comfort', 'roll', 'energy']
    assert payload['score_labels'] == ['penalty_total', 'comfort', 'roll', 'energy']
    assert payload['penalty_tol'] == 0.5


def test_score_contract_matches_accepts_saved_string_objective_keys() -> None:
    assert score_contract_matches(
        {
            'objective_keys': 'comfort,\nroll;energy',
            'penalty_key': 'penalty_total',
        },
        objective_keys=['comfort', 'roll', 'energy'],
        penalty_key='penalty_total',
    )
