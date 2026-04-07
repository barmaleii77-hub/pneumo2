from __future__ import annotations

"""Helpers for optimization result-row semantics.

Why:
- stage workers historically wrote baseline anchors into the same CSV as real
  candidates using ``id=-1``;
- later-stage seed promotion must not recycle baseline/service rows as if they
  were promotable solutions;
- UI/triage should be able to hide service rows without guessing ad-hoc rules.
"""

from typing import Any, Mapping

import pandas as pd


BASELINE_ROLE = "baseline_anchor"


def _as_str(value: Any) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        return ""


def row_id_int(row: Mapping[str, Any] | None) -> int | None:
    if not isinstance(row, Mapping):
        return None
    try:
        raw = row.get("id")
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            return None
        return int(raw)
    except Exception:
        return None


def row_candidate_role(row: Mapping[str, Any] | None) -> str:
    if not isinstance(row, Mapping):
        return ""
    return _as_str(row.get("candidate_role"))


def is_error_row(row: Mapping[str, Any] | None) -> bool:
    if not isinstance(row, Mapping):
        return False
    for key in ("ошибка", "error"):
        val = row.get(key)
        if val is None:
            continue
        sval = _as_str(val)
        if sval and sval.lower() != "nan":
            return True
    return False


def is_pruned_row(row: Mapping[str, Any] | None) -> bool:
    if not isinstance(row, Mapping):
        return False
    try:
        val = row.get("pruned_early")
        if val is not None and float(val):
            return True
    except Exception:
        pass
    sval = _as_str(row.get("pruned_after_test"))
    return bool(sval and sval.lower() != "nan")


def is_baseline_row(row: Mapping[str, Any] | None) -> bool:
    if not isinstance(row, Mapping):
        return False
    role = row_candidate_role(row).lower()
    if role == BASELINE_ROLE:
        return True
    meta_source = _as_str(row.get("meta_source")).lower()
    if meta_source.startswith("baseline"):
        return True
    rid = row_id_int(row)
    # Legacy baseline anchors used id=-1, new ones use id=0.
    return rid in {-1, 0}


def is_promotable_row(row: Mapping[str, Any] | None) -> bool:
    return (not is_baseline_row(row)) and (not is_error_row(row)) and (not is_pruned_row(row))


def filter_display_df(df: pd.DataFrame, *, include_baseline: bool = False) -> pd.DataFrame:
    if df is None or df.empty or include_baseline:
        return df
    records = df.to_dict(orient="records")
    keep_mask = [not is_baseline_row(r) for r in records]
    if any(keep_mask):
        return df.loc[keep_mask].copy()
    return df.copy()
