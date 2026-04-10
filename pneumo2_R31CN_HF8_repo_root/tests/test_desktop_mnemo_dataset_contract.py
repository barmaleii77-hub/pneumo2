from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest


def test_prepare_dataset_builds_semantic_mnemo_from_minimal_npz(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")

    from pneumo_solver_ui.desktop_mnemo.app import (
        _build_frame_alert_payload,
        _build_frame_narrative,
        build_onboarding_focus_target,
        build_onboarding_focus_region_payload,
        prepare_dataset,
    )

    t = np.array([0.0, 0.5, 1.0], dtype=float)
    npz_path = tmp_path / "mnemo_bundle.npz"

    meta = {
        "P_ATM": 101325.0,
        "geometry": {
            "wheelbase_m": 2.8,
            "track_m": 1.6,
            "wheel_radius_m": 0.32,
            "wheel_width_m": 0.24,
            "frame_length_m": 3.2,
            "frame_width_m": 1.7,
            "frame_height_m": 0.25,
        },
    }

    p_cols = np.array(
        [
            "время_с",
            "Ресивер1",
            "Ресивер3",
            "узел_после_рег_Pmid",
            "узел_после_ОК_Pmid",
        ],
        dtype=object,
    )
    q_cols = np.array(
        [
            "время_с",
            "регулятор_до_себя_Pmid_сброс",
            "обратный_клапан_Pmid_к_выхлопу",
            "дроссель_выхлоп_Pmid",
        ],
        dtype=object,
    )
    open_cols = np.array(
        [
            "время_с",
            "регулятор_до_себя_Pmid_сброс",
            "обратный_клапан_Pmid_к_выхлопу",
            "дроссель_выхлоп_Pmid",
        ],
        dtype=object,
    )

    np.savez(
        npz_path,
        main_cols=np.array(["время_с"], dtype=object),
        main_values=np.column_stack([t]).astype(float),
        p_cols=p_cols,
        p_values=np.column_stack(
            [
                t,
                np.array([305000.0, 308000.0, 312000.0], dtype=float),
                np.array([498000.0, 501000.0, 505000.0], dtype=float),
                np.array([255000.0, 260000.0, 270000.0], dtype=float),
                np.array([240000.0, 242000.0, 245000.0], dtype=float),
            ]
        ).astype(float),
        q_cols=q_cols,
        q_values=np.column_stack(
            [
                t,
                np.array([0.0010, 0.0012, 0.0014], dtype=float),
                np.array([0.0007, 0.0004, 0.0001], dtype=float),
                np.array([0.0002, 0.0005, 0.0008], dtype=float),
            ]
        ).astype(float),
        open_cols=open_cols,
        open_values=np.column_stack(
            [
                t,
                np.array([1, 1, 0], dtype=float),
                np.array([1, 0, 0], dtype=float),
                np.array([0, 1, 1], dtype=float),
            ]
        ).astype(float),
        meta_json=np.array(json.dumps(meta, ensure_ascii=False), dtype=object),
    )

    dataset = prepare_dataset(npz_path)

    assert dataset.npz_path == npz_path.resolve()
    assert dataset.q_unit == "Нл/мин"
    assert dataset.p_atm == pytest.approx(101325.0)
    assert dataset.edge_names == [
        "регулятор_до_себя_Pmid_сброс",
        "обратный_клапан_Pmid_к_выхлопу",
        "дроссель_выхлоп_Pmid",
    ]
    assert dataset.overlay_node_names
    assert {"Ресивер1", "Ресивер3", "узел_после_рег_Pmid"}.issubset(set(dataset.overlay_node_names))
    assert "Пневматическая мнемосхема" in dataset.svg_inline
    assert dataset.mapping["edges_meta"]["регулятор_до_себя_Pmid_сброс"]["mnemo_route"] == "rail"
    assert dataset.mapping["edges_meta"]["обратный_клапан_Pmid_к_выхлопу"]["mnemo_route"] == "regulator_bus"
    assert dataset.mapping["edges_meta"]["дроссель_выхлоп_Pmid"]["endpoints"] == ["узел_после_ОК_Pmid", "АТМ"]
    assert len(dataset.edge_series) == 3
    assert dataset.edge_series[0]["open"] == [1, 1, 0]
    assert [item["name"] for item in dataset.node_series] == dataset.overlay_node_names

    narrative = _build_frame_narrative(
        dataset,
        1,
        selected_edge="обратный_клапан_Pmid_к_выхлопу",
        selected_node="узел_после_рег_Pmid",
    )
    assert narrative.primary_title == "Регуляторный коридор"
    assert narrative.top_edge_name == "регулятор_до_себя_Pmid_сброс"
    assert narrative.pressure_spread > 2.0
    assert any(mode.title == "Большой перепад давлений" for mode in narrative.modes)
    assert any(mode.title == "Фокус узла" for mode in narrative.modes)

    alerts = _build_frame_alert_payload(
        dataset,
        1,
        selected_edge="обратный_клапан_Pmid_к_выхлопу",
        selected_node="узел_после_рег_Pmid",
    )
    assert alerts["primary"]["title"] == "Регуляторный коридор"
    assert any(item["name"] == "регулятор_до_себя_Pmid_сброс" and item["severity"] == "focus" for item in alerts["edges"])
    assert any(item["name"] == "Ресивер3" and item["severity"] == "warn" for item in alerts["nodes"])
    assert any(item["name"] == "узел_после_рег_Pmid" and item["severity"] == "warn" for item in alerts["nodes"])
    assert any(item["title"] == "Большой перепад давлений" and item["severity"] == "warn" for item in alerts["mode_badges"])

    focus_target = build_onboarding_focus_target(
        dataset,
        1,
        selected_edge="обратный_клапан_Pmid_к_выхлопу",
        selected_node="узел_после_рег_Pmid",
    )
    assert focus_target.has_target is True
    assert focus_target.edge_name == "регулятор_до_себя_Pmid_сброс"
    assert focus_target.node_name == "Ресивер3"
    assert focus_target.mode_title == "Регуляторный коридор"
    assert "Стартовый фокус" in focus_target.summary

    focus_payload = build_onboarding_focus_region_payload(
        dataset,
        1,
        selected_edge="обратный_клапан_Pmid_к_выхлопу",
        selected_node="узел_после_рег_Pmid",
        source="dataset_load",
        auto_focus=True,
    )
    assert focus_payload["available"] is True
    assert focus_payload["edge_name"] == "регулятор_до_себя_Pmid_сброс"
    assert focus_payload["node_name"] == "Ресивер3"
    assert focus_payload["auto_focus"] is True
    assert focus_payload["source"] == "dataset_load"
    assert "Регуляторный коридор" in focus_payload["summary"]


def test_mnemo_event_tracker_latches_warn_and_mode_switches(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")

    from pneumo_solver_ui.desktop_mnemo.app import (
        MnemoEventTracker,
        _build_event_log_payload,
        _event_log_sidecar_path,
        _write_event_log_sidecar,
        prepare_dataset,
    )

    t = np.array([0.0, 0.5, 1.0], dtype=float)
    npz_path = tmp_path / "mnemo_tracker_bundle.npz"

    meta = {
        "P_ATM": 101325.0,
        "geometry": {
            "wheelbase_m": 2.8,
            "track_m": 1.6,
            "wheel_radius_m": 0.32,
            "wheel_width_m": 0.24,
            "frame_length_m": 3.2,
            "frame_width_m": 1.7,
            "frame_height_m": 0.25,
        },
    }

    p_cols = np.array(
        [
            "время_с",
            "Ресивер1",
            "Ресивер3",
            "узел_после_рег_Pmid",
            "узел_после_ОК_Pmid",
        ],
        dtype=object,
    )
    q_cols = np.array(
        [
            "время_с",
            "регулятор_до_себя_Pmid_сброс",
            "обратный_клапан_Pmid_к_выхлопу",
            "дроссель_выхлоп_Pmid",
        ],
        dtype=object,
    )
    open_cols = q_cols.copy()

    np.savez(
        npz_path,
        main_cols=np.array(["время_с"], dtype=object),
        main_values=np.column_stack([t]).astype(float),
        p_cols=p_cols,
        p_values=np.column_stack(
            [
                t,
                np.array([305000.0, 308000.0, 312000.0], dtype=float),
                np.array([498000.0, 501000.0, 505000.0], dtype=float),
                np.array([255000.0, 260000.0, 270000.0], dtype=float),
                np.array([240000.0, 242000.0, 245000.0], dtype=float),
            ]
        ).astype(float),
        q_cols=q_cols,
        q_values=np.column_stack(
            [
                t,
                np.array([0.0010, 0.0012, 0.0002], dtype=float),
                np.array([0.0007, 0.0004, 0.0001], dtype=float),
                np.array([0.0001, 0.0005, 0.0010], dtype=float),
            ]
        ).astype(float),
        open_cols=open_cols,
        open_values=np.column_stack(
            [
                t,
                np.array([1, 1, 0], dtype=float),
                np.array([1, 0, 0], dtype=float),
                np.array([0, 1, 1], dtype=float),
            ]
        ).astype(float),
        meta_json=np.array(json.dumps(meta, ensure_ascii=False), dtype=object),
    )

    dataset = prepare_dataset(npz_path)
    tracker = MnemoEventTracker(max_events=16)
    tracker.bind_dataset(dataset, idx=0)
    tracker.observe_frame(dataset, idx=1)
    tracker.observe_frame(dataset, idx=2)

    assert any(event.title == "Новый прогон" and event.kind == "session" for event in tracker.events)
    assert any(event.title == "Большой перепад давлений" and event.severity == "warn" for event in tracker.events)
    assert any(event.title == "Сброс присутствует параллельно" and event.severity == "attention" for event in tracker.events)
    assert any(event.title == "Смена режима" and "Сброс / разгрузка" in event.summary for event in tracker.events)
    assert any(event.title == "Сброс присутствует параллельно" for event in tracker.latched_events(limit=4))

    tracker.reset_memory(dataset, idx=1)
    active_before_ack = tracker.active_latched_events(limit=4)
    assert any(event.title == "Большой перепад давлений" for event in active_before_ack)
    acked_now = tracker.acknowledge_active_latches(dataset=dataset, idx=1)
    assert any(event.title == "Большой перепад давлений" for event in acked_now)
    assert tracker.active_latched_events(limit=4) == []
    assert any(event.title == "Большой перепад давлений" for event in tracker.acknowledged_latched_events(limit=4))

    sidecar_path = _event_log_sidecar_path(dataset.npz_path)
    assert sidecar_path.name == "mnemo_tracker_bundle.desktop_mnemo_events.json"

    payload = _build_event_log_payload(
        dataset,
        tracker,
        idx=1,
        selected_edge="обратный_клапан_Pmid_к_выхлопу",
        selected_node="узел_после_рег_Pmid",
        follow_enabled=True,
        pointer_path=tmp_path / "anim_latest.json",
    )
    assert payload["schema_version"] == "desktop_mnemo_event_log_v1"
    assert payload["active_latch_count"] == 0
    assert payload["acknowledged_latch_count"] >= 1
    assert "Большой перепад давлений" in payload["acknowledged_titles"]
    assert payload["current_mode"] == "Регуляторный коридор"
    written = _write_event_log_sidecar(
        dataset,
        tracker,
        idx=1,
        selected_edge="обратный_клапан_Pmid_к_выхлопу",
        selected_node="узел_после_рег_Pmid",
        follow_enabled=True,
        pointer_path=tmp_path / "anim_latest.json",
    )
    assert written == sidecar_path
    saved = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert saved["npz_path"] == str(dataset.npz_path)
    assert saved["acknowledged_latch_count"] >= 1
    assert any(event["title"] == "ACK latched-событий" for event in saved["events"])


def test_build_launch_onboarding_context_supports_defaults_and_explicit_preset() -> None:
    pytest.importorskip("PySide6")

    from pneumo_solver_ui.desktop_mnemo.app import (
        build_launch_onboarding_context,
        build_onboarding_focus_region_payload,
        build_onboarding_focus_target,
    )

    follow_ctx = build_launch_onboarding_context(
        npz_path=Path("C:/repo/workspace/exports/anim_latest.npz"),
        follow=True,
        pointer_path=Path("C:/repo/workspace/_pointers/anim_latest.json"),
        preset_key="operational_follow_triage",
        title="Оперативный follow-разбор",
        reason="Есть активные latch-события и нужен live triage.",
        checklist=[
            "Сначала подтвердите ведущую ветку.",
            "ACK делайте только после сверки со схемой.",
        ],
    )
    assert follow_ctx.launch_mode == "follow"
    assert follow_ctx.preset_key == "operational_follow_triage"
    assert follow_ctx.title == "Оперативный follow-разбор"
    assert "live triage" in follow_ctx.reason
    assert follow_ctx.checklist[0] == "Сначала подтвердите ведущую ветку."

    review_ctx = build_launch_onboarding_context(
        npz_path=Path("C:/repo/workspace/exports/case_a.npz"),
        follow=False,
        pointer_path=Path("C:/repo/workspace/_pointers/anim_latest.json"),
    )
    assert review_ctx.launch_mode == "npz"
    assert review_ctx.preset_key == "npz"
    assert review_ctx.title == "Ретроспективный разбор NPZ"
    assert any("фиксированный сценарий" in item for item in review_ctx.checklist)

    waiting_focus = build_onboarding_focus_target(None, 0)
    assert waiting_focus.has_target is False
    assert waiting_focus.mode_title == "Ожидание данных"
    assert "не вычислен" in waiting_focus.summary

    waiting_payload = build_onboarding_focus_region_payload(None, 0, source="startup_banner", auto_focus=False)
    assert waiting_payload["available"] is False
    assert waiting_payload["edge_name"] == ""
    assert waiting_payload["node_name"] == ""
    assert waiting_payload["auto_focus"] is False
