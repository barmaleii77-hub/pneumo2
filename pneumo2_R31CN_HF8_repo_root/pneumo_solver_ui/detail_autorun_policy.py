from __future__ import annotations

from typing import Any, MutableMapping


def arm_detail_autorun_on_test_change(
    state: MutableMapping[str, Any],
    *,
    auto_detail_on_select: bool,
    cache_key: str,
    test_pick: str,
) -> bool:
    """Arm auto-detail when the selected test changes.

    Returns True only when a new pending auto-detail run was armed.
    """
    prev_tp = state.get("detail_prev_test_pick")
    if test_pick == prev_tp:
        return False
    state["detail_prev_test_pick"] = test_pick
    if auto_detail_on_select:
        state["detail_auto_pending"] = cache_key
        return True
    return False


def arm_detail_autorun_after_baseline(
    state: MutableMapping[str, Any],
    *,
    auto_detail_on_select: bool,
    cache_key: str,
    force_fresh_after_baseline: bool = True,
) -> bool:
    """Consume one-shot baseline flag and arm auto-detail for current key.

    If ``force_fresh_after_baseline`` is True, the next detail run for this key must
    bypass disk cache and recalculate from the fresh baseline.
    """
    if not bool(state.get("baseline_just_ran", False)):
        return False
    state["baseline_just_ran"] = False
    if not auto_detail_on_select:
        return False
    state["detail_auto_pending"] = cache_key
    if force_fresh_after_baseline:
        state["detail_force_fresh_key"] = cache_key
    return True


def should_bypass_detail_disk_cache(
    state: MutableMapping[str, Any],
    *,
    cache_key: str,
) -> bool:
    return str(state.get("detail_force_fresh_key") or "") == str(cache_key)


def clear_detail_force_fresh(
    state: MutableMapping[str, Any],
    *,
    cache_key: str,
) -> None:
    if should_bypass_detail_disk_cache(state, cache_key=cache_key):
        state["detail_force_fresh_key"] = None
