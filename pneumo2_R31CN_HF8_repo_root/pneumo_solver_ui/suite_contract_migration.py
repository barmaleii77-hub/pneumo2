from __future__ import annotations

"""Explicit suite-schema migration helpers.

ABSOLUTE LAW:
- No runtime compatibility bridges.
- No silent aliases.
- One parameter name == one meaning.

The only allowed exception is a *loud, one-time migration at data ingress* when a
user loads an old suite file. This module performs exactly that:
- known legacy columns are moved to canonical names;
- legacy columns are removed immediately from editor state;
- every migration/conflict is returned as a human-readable warning.

The caller is responsible for surfacing these warnings to the user and logging them.
"""

from typing import Any
import math

import pandas as pd

# Only documented suite-level legacy keys are migrated here.
LEGACY_SUITE_COLUMN_SUGGESTIONS: dict[str, str] = {
    # speed
    "road_speed_mps": "vx0_м_с",
    "speed_mps": "vx0_м_с",
    "v0_м_с": "vx0_м_с",
    "скорость_м_с": "vx0_м_с",
    # road / profiles
    "road_profile_path": "road_csv",
    "road_profile_csv": "road_csv",
    # maneuvers
    "road_ay_csv": "axay_csv",
    "road_axay_csv": "axay_csv",
}


def _is_missing_suite_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def migrate_legacy_suite_columns(
    df: pd.DataFrame | None,
    *,
    context: str = "suite",
) -> tuple[pd.DataFrame, list[str]]:
    """Explicitly migrate known legacy suite columns to canonical names.

    This is **not** a runtime alias layer. Legacy columns are removed from the
    returned dataframe, and all performed actions are reported back to the caller.

    Rules:
    - if only legacy column exists -> rename to canonical and report it;
    - if both legacy and canonical exist -> fill missing canonical cells from
      legacy, preserve canonical cells on conflicts, then drop legacy column;
    - duplicate column names are collapsed (first occurrence wins) to keep UI alive.
    """

    if df is None:
        return pd.DataFrame(), []

    out = df.copy()
    issues: list[str] = []

    for legacy, canonical in LEGACY_SUITE_COLUMN_SUGGESTIONS.items():
        if legacy not in out.columns:
            continue

        if canonical not in out.columns:
            out = out.rename(columns={legacy: canonical})
            issues.append(
                f"[{context}] Legacy колонка '{legacy}' явно мигрирована в canonical '{canonical}'. "
                "Пересохраните suite.json без legacy-имён."
            )
            continue

        filled_from_legacy = 0
        conflicts = 0

        for idx in list(out.index):
            legacy_value = out.at[idx, legacy]
            canonical_value = out.at[idx, canonical]

            if _is_missing_suite_value(legacy_value):
                continue
            if _is_missing_suite_value(canonical_value):
                out.at[idx, canonical] = legacy_value
                filled_from_legacy += 1
                continue

            if legacy_value != canonical_value:
                conflicts += 1

        out = out.drop(columns=[legacy])

        if conflicts > 0:
            issues.append(
                f"[{context}] Legacy колонка '{legacy}' удалена после миграции в '{canonical}': "
                f"заполнено пустых canonical-ячеек={filled_from_legacy}, конфликтов={conflicts}. "
                "При конфликтах сохранено canonical-значение."
            )
        elif filled_from_legacy > 0:
            issues.append(
                f"[{context}] Legacy колонка '{legacy}' удалена после миграции в '{canonical}': "
                f"заполнено пустых canonical-ячеек={filled_from_legacy}."
            )
        else:
            issues.append(
                f"[{context}] Legacy колонка '{legacy}' удалена: canonical '{canonical}' уже присутствовала."
            )

    try:
        if out.columns.duplicated().any():
            dups = out.columns[out.columns.duplicated()].tolist()
            out = out.loc[:, ~out.columns.duplicated()]
            issues.append(
                f"[{context}] Обнаружены дубли колонок {dups!r}; сохранены первые вхождения для безопасной деградации UI."
            )
    except Exception:
        pass

    return out, issues
