from __future__ import annotations

"""Shared optimization objective contract helpers.

Why this module exists:
- StageRunner and distributed coordinator must rank candidates against the same
  explicit objective stack instead of drifting into UI-only alignment;
- historical CSV/archive rows may still carry legacy key names, so runtime
  readers need a single alias map rather than each tool inventing its own;
- baseline promotion and surrogate warm-start must be objective-contract aware;
- run artifacts and problem hashing need one honest place to serialize the
  objective/penalty contract instead of re-encoding it ad hoc.
"""

from typing import Any, Mapping, Optional, Sequence
import hashlib
import json
import math
import re

from pneumo_solver_ui.optimization_defaults import (
    DEFAULT_OPTIMIZATION_OBJECTIVES,
    DIST_OPT_PENALTY_KEY_DEFAULT,
)

LEGACY_STAGE_RUNNER_OBJECTIVES: tuple[str, ...] = (
    "цель1_устойчивость_инерция__с",
    "цель2_комфорт__RMS_ускор_м_с2",
    "метрика_энергия_дроссели_микро_Дж",
)

# Symmetric alias groups. Each key in a group resolves to all siblings.
_ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    (
        DIST_OPT_PENALTY_KEY_DEFAULT,
        "penalty_total",
    ),
    (
        "метрика_комфорт__RMS_ускор_рамы_микро_м_с2",
        "цель2_комфорт__RMS_ускор_м_с2",
        "obj_comfort_rms",
        "микро_синфаза__RMS_ускор_рамы_м_с2",
    ),
    (
        "метрика_крен_ay3_град",
        "obj_roll_ay3_deg",
        "obj_roll_deg",
        "инерция_крен_ay3__крен_max_град",
        "инерция_крен_ay3__крен_peak_град",
    ),
    (
        "метрика_энергия_дроссели_микро_Дж",
        "energy_J",
        "метрика_энергия__J",
        "микро_синфаза__энергия_дроссели_Дж",
    ),
    (
        "цель1_устойчивость_инерция__с",
        "obj_stability_s",
    ),
)

_ALIAS_MAP: dict[str, tuple[str, ...]] = {}
for _group in _ALIAS_GROUPS:
    cleaned = tuple(dict.fromkeys(str(x).strip() for x in _group if str(x).strip()))
    for _key in cleaned:
        _ALIAS_MAP[_key] = cleaned


def _collect_objective_keys(raw: Any, out: list[str]) -> None:
    if raw is None:
        return
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return
        if text[:1] in {"[", '"'}:
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            if parsed is not None and parsed is not raw:
                _collect_objective_keys(parsed, out)
                return
        for piece in re.split(r"[\n,;]+", text):
            key = str(piece or "").strip()
            if key and key not in out:
                out.append(key)
        return
    if isinstance(raw, Sequence):
        for item in raw:
            _collect_objective_keys(item, out)
        return
    key = str(raw or "").strip()
    if key and key not in out:
        out.append(key)


def normalize_objective_keys(objective_keys: Any | None = None) -> tuple[str, ...]:
    out: list[str] = []
    _collect_objective_keys(objective_keys, out)
    return tuple(out or tuple(str(x) for x in DEFAULT_OPTIMIZATION_OBJECTIVES))


def normalize_penalty_key(penalty_key: str | None = None) -> str:
    key = str(penalty_key or '').strip()
    return key or DIST_OPT_PENALTY_KEY_DEFAULT


def alias_keys_for_metric(metric_key: str) -> tuple[str, ...]:
    key = str(metric_key or '').strip()
    if not key:
        return tuple()
    aliases = _ALIAS_MAP.get(key)
    if aliases:
        return aliases
    return (key,)


def _finite_float(value: Any, default: float = float('inf')) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not math.isfinite(out):
        return float(default)
    return float(out)


def normalize_penalty_tol(penalty_tol: Any | None = None, *, default: float = 0.0) -> float:
    out = _finite_float(penalty_tol, default=default)
    return float(out if math.isfinite(out) else default)


def metric_value_from_row(
    row: Mapping[str, Any] | None,
    metric_key: str,
    *,
    default: float = float('inf'),
) -> float:
    if not isinstance(row, Mapping):
        return float(default)
    for key in alias_keys_for_metric(metric_key):
        if key not in row:
            continue
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == '':
            continue
        out = _finite_float(value, default=float('inf'))
        if math.isfinite(out):
            return float(out)
    return float(default)


def score_tuple_from_row(
    row: Mapping[str, Any] | None,
    *,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
) -> tuple[float, ...]:
    pen_key = normalize_penalty_key(penalty_key)
    obj_keys = normalize_objective_keys(objective_keys)
    parts = [metric_value_from_row(row, pen_key, default=float('inf'))]
    for key in obj_keys:
        parts.append(metric_value_from_row(row, key, default=float('inf')))
    return tuple(float(x) for x in parts)


def score_labels(
    *,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
) -> tuple[str, ...]:
    return (normalize_penalty_key(penalty_key), *normalize_objective_keys(objective_keys))


def objective_contract_identity_payload(
    *,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
    penalty_tol: Any | None = None,
) -> dict[str, Any]:
    return {
        'version': 'objective_contract_v1',
        'penalty_key': normalize_penalty_key(penalty_key),
        'penalty_tol': normalize_penalty_tol(penalty_tol),
        'objective_keys': list(normalize_objective_keys(objective_keys)),
        'score_labels': list(score_labels(objective_keys=objective_keys, penalty_key=penalty_key)),
    }


def objective_contract_hash(
    *,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
    penalty_tol: Any | None = None,
) -> str:
    payload = objective_contract_identity_payload(
        objective_keys=objective_keys,
        penalty_key=penalty_key,
        penalty_tol=penalty_tol,
    )
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def objective_contract_payload(
    *,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
    penalty_tol: Any | None = None,
    source: str = 'shared_objective_contract_v1',
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'version': 'objective_contract_v1',
        'source': str(source or 'shared_objective_contract_v1'),
        'penalty_key': normalize_penalty_key(penalty_key),
        'objective_keys': list(normalize_objective_keys(objective_keys)),
        'score_labels': list(score_labels(objective_keys=objective_keys, penalty_key=penalty_key)),
        'objective_contract_hash': objective_contract_hash(
            objective_keys=objective_keys,
            penalty_key=penalty_key,
            penalty_tol=penalty_tol,
        ),
    }
    if penalty_tol is not None:
        payload['penalty_tol'] = normalize_penalty_tol(penalty_tol)
    return payload


def score_payload(
    score: Sequence[float],
    *,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
    penalty_tol: Any | None = None,
    source: str = 'shared_objective_contract_v1',
) -> dict[str, Any]:
    payload = objective_contract_payload(
        objective_keys=objective_keys,
        penalty_key=penalty_key,
        penalty_tol=penalty_tol,
        source=source,
    )
    payload['score'] = [float(x) for x in score]
    return payload


def parse_saved_score_payload(raw: Any) -> Optional[dict[str, Any]]:
    if isinstance(raw, Mapping):
        score = raw.get('score')
        if not isinstance(score, Sequence) or isinstance(score, (str, bytes, bytearray)):
            return None
        penalty_tol = raw.get('penalty_tol') if 'penalty_tol' in raw else None
        return score_payload(
            list(score),
            objective_keys=raw.get('objective_keys'),
            penalty_key=str(raw.get('penalty_key') or DIST_OPT_PENALTY_KEY_DEFAULT),
            penalty_tol=penalty_tol,
            source=str(raw.get('source') or raw.get('version') or 'objective_contract_v1'),
        )
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        score_list = [float(x) for x in raw]
        return score_payload(
            score_list,
            objective_keys=LEGACY_STAGE_RUNNER_OBJECTIVES,
            penalty_key=DIST_OPT_PENALTY_KEY_DEFAULT,
            source='legacy_score_list',
        )
    return None


def score_contract_matches(
    saved: Mapping[str, Any] | None,
    *,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
) -> bool:
    if not isinstance(saved, Mapping):
        return False
    saved_pen = normalize_penalty_key(str(saved.get('penalty_key') or ''))
    saved_obj = normalize_objective_keys(saved.get('objective_keys'))
    return saved_pen == normalize_penalty_key(penalty_key) and saved_obj == normalize_objective_keys(objective_keys)


def lexicographic_is_better(new_score: Sequence[float], old_score: Sequence[float]) -> bool:
    try:
        new_t = tuple(float(x) for x in new_score)
        old_t = tuple(float(x) for x in old_score)
    except Exception:
        return True
    if len(new_t) != len(old_t):
        return True
    return new_t < old_t


def scalarize_score_tuple(score: Sequence[float]) -> float:
    vals = [float(x) for x in score]
    if not vals:
        return float('inf')
    if not math.isfinite(vals[0]):
        return float('inf')
    total = 1000.0 * float(vals[0])
    for idx, value in enumerate(vals[1:], start=1):
        if not math.isfinite(value):
            return float('inf')
        if value >= 0.0:
            compressed = math.log1p(float(value))
        else:
            compressed = -math.log1p(abs(float(value)))
        total += (10.0 ** (1 - idx)) * compressed
    return float(total)


__all__ = [
    'LEGACY_STAGE_RUNNER_OBJECTIVES',
    'alias_keys_for_metric',
    'lexicographic_is_better',
    'metric_value_from_row',
    'normalize_objective_keys',
    'normalize_penalty_key',
    'normalize_penalty_tol',
    'objective_contract_hash',
    'objective_contract_identity_payload',
    'objective_contract_payload',
    'parse_saved_score_payload',
    'scalarize_score_tuple',
    'score_contract_matches',
    'score_labels',
    'score_payload',
    'score_tuple_from_row',
]
