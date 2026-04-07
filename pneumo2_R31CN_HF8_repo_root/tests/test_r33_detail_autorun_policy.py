from __future__ import annotations

from pneumo_solver_ui.detail_autorun_policy import (
    arm_detail_autorun_after_baseline,
    arm_detail_autorun_on_test_change,
    should_bypass_detail_disk_cache,
    clear_detail_force_fresh,
)


def test_detail_autorun_after_baseline_arms_fresh_recalc() -> None:
    state = {
        "baseline_just_ran": True,
        "detail_auto_pending": None,
        "detail_force_fresh_key": None,
    }

    armed = arm_detail_autorun_after_baseline(
        state,
        auto_detail_on_select=True,
        cache_key="ck-1",
        force_fresh_after_baseline=True,
    )

    assert armed is True
    assert state["baseline_just_ran"] is False
    assert state["detail_auto_pending"] == "ck-1"
    assert state["detail_force_fresh_key"] == "ck-1"
    assert should_bypass_detail_disk_cache(state, cache_key="ck-1") is True

    clear_detail_force_fresh(state, cache_key="ck-1")
    assert should_bypass_detail_disk_cache(state, cache_key="ck-1") is False


def test_detail_autorun_on_test_change_arms_only_on_real_change() -> None:
    state = {"detail_prev_test_pick": "T1", "detail_auto_pending": None}

    armed_same = arm_detail_autorun_on_test_change(
        state,
        auto_detail_on_select=True,
        cache_key="ck-same",
        test_pick="T1",
    )
    assert armed_same is False
    assert state["detail_auto_pending"] is None

    armed_new = arm_detail_autorun_on_test_change(
        state,
        auto_detail_on_select=True,
        cache_key="ck-new",
        test_pick="T2",
    )
    assert armed_new is True
    assert state["detail_prev_test_pick"] == "T2"
    assert state["detail_auto_pending"] == "ck-new"
