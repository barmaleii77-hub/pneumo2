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
        _build_selected_edge_focus_meta,
        _build_mnemo_diagnostics_payload,
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
    assert len(dataset.canonical_node_names) == 46
    assert len(dataset.canonical_edge_names) == 70
    assert dataset.scheme_fidelity["canonical_nodes_total"] == 46
    assert dataset.scheme_fidelity["canonical_nodes_positioned"] == 46
    assert dataset.scheme_fidelity["canonical_edges_total"] == 70
    assert dataset.scheme_fidelity["canonical_edges_routed"] == 70
    assert dataset.scheme_fidelity["canonical_route_issues"] == []
    assert dataset.scheme_fidelity["bundle_edges_known"] == 3
    assert dataset.scheme_fidelity["bundle_nodes_known"] == 4
    assert dataset.scheme_fidelity["status"] == "ok"
    assert dataset.mapping["edges_meta"]["регулятор_до_себя_Pmid_сброс"]["mnemo_route"] == "rail"
    assert dataset.mapping["edges_meta"]["обратный_клапан_Pmid_к_выхлопу"]["mnemo_route"] == "regulator_bus"
    assert dataset.mapping["edges_meta"]["дроссель_выхлоп_Pmid"]["endpoints"] == ["узел_после_ОК_Pmid", "АТМ"]
    assert dataset.edge_defs["регулятор_до_себя_Pmid_сброс"]["camozzi_code"] == "VMR 1/8-B10"
    assert dataset.edge_defs["обратный_клапан_Pmid_к_выхлопу"]["kind"] == "check"
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
    assert alerts["scheme_fidelity"]["canonical_edges_routed"] == 70
    assert alerts["scheme_fidelity"]["bundle_edges_known"] == 3

    diagnostics = _build_mnemo_diagnostics_payload(
        dataset,
        1,
        selected_edge="обратный_клапан_Pmid_к_выхлопу",
        selected_node="узел_после_рег_Pmid",
    )
    assert diagnostics["scheme_fidelity"]["canonical_nodes_positioned"] == 46
    assert any(item["canonical_kind"] == "check" for item in diagnostics["components"])
    assert any(item["camozzi_code"] == "VNR-238-3/8" for item in diagnostics["components"])
    assert any(item["icon_key"] == "check" for item in diagnostics["components"])

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

    selected_focus_target = build_onboarding_focus_target(
        dataset,
        1,
        selected_edge="обратный_клапан_Pmid_к_выхлопу",
        selected_node="узел_после_рег_Pmid",
        prefer_selected=True,
    )
    assert selected_focus_target.edge_name == "обратный_клапан_Pmid_к_выхлопу"
    assert selected_focus_target.node_name == "узел_после_рег_Pmid"

    selected_focus_payload = build_onboarding_focus_region_payload(
        dataset,
        1,
        selected_edge="обратный_клапан_Pmid_к_выхлопу",
        selected_node="узел_после_рег_Pmid",
        prefer_selected=True,
        source="startup_handoff",
        auto_focus=True,
    )
    assert selected_focus_payload["edge_name"] == "обратный_клапан_Pmid_к_выхлопу"
    assert selected_focus_payload["node_name"] == "узел_после_рег_Pmid"
    assert selected_focus_payload["source"] == "startup_handoff"

    edge_focus = _build_selected_edge_focus_meta(
        dataset,
        1,
        edge_name="регулятор_до_себя_Pmid_сброс",
    )
    assert edge_focus["edge_name"] == "регулятор_до_себя_Pmid_сброс"
    assert edge_focus["phase_sequence_label"] == "SIG → ΔP → Q"
    assert [item["phase_label"] for item in edge_focus["phase_items"]] == ["SIG", "ΔP", "Q"]
    assert edge_focus["step_rows"][0]["index_label"] == "01"
    assert edge_focus["step_rows"][0]["target_idx"] == 2
    assert edge_focus["step_rows"][0]["target_time_s"] == pytest.approx(1.0)
    assert edge_focus["step_rows"][1]["phase_label"] == "ΔP"
    assert edge_focus["step_rows"][1]["target_idx"] == 1
    assert edge_focus["step_rows"][2]["target_idx"] == 1
    assert any(item["badge_text"] == "P+" for item in edge_focus["terminal_markers"])
    assert any(item["badge_text"] == "P-" for item in edge_focus["terminal_markers"])
    assert any(item["badge_text"] == "SRC" for item in edge_focus["terminal_markers"])
    assert any(item["badge_text"] == "SNK" for item in edge_focus["terminal_markers"])


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
        startup_time_s=1.25,
        startup_time_label="1.250 s · Большой перепад давлений",
        checklist=[
            "Сначала подтвердите ведущую ветку.",
            "ACK делайте только после сверки со схемой.",
        ],
    )
    assert follow_ctx.launch_mode == "follow"
    assert follow_ctx.preset_key == "operational_follow_triage"
    assert follow_ctx.title == "Оперативный follow-разбор"
    assert "live triage" in follow_ctx.reason
    assert "1.250 s" in follow_ctx.reason
    assert follow_ctx.checklist[0] == "Сначала проверьте кадр около 1.250 s · Большой перепад давлений и убедитесь, что режим на схеме совпадает с ожиданием."
    assert follow_ctx.startup_time_s == pytest.approx(1.25)
    assert follow_ctx.startup_time_label == "1.250 s · Большой перепад давлений"

    review_ctx = build_launch_onboarding_context(
        npz_path=Path("C:/repo/workspace/exports/case_a.npz"),
        follow=False,
        pointer_path=Path("C:/repo/workspace/_pointers/anim_latest.json"),
    )
    assert review_ctx.launch_mode == "npz"
    assert review_ctx.preset_key == "npz"
    assert review_ctx.title == "Ретроспективный разбор NPZ"
    assert any("фиксированный сценарий" in item for item in review_ctx.checklist)
    assert review_ctx.startup_time_s is None

    waiting_focus = build_onboarding_focus_target(None, 0)
    assert waiting_focus.has_target is False
    assert waiting_focus.mode_title == "Ожидание данных"
    assert "не вычислен" in waiting_focus.summary

    waiting_payload = build_onboarding_focus_region_payload(None, 0, source="startup_banner", auto_focus=False)
    assert waiting_payload["available"] is False
    assert waiting_payload["edge_name"] == ""
    assert waiting_payload["node_name"] == ""
    assert waiting_payload["auto_focus"] is False


def test_edge_direction_meta_distinguishes_passport_and_live_flow() -> None:
    pytest.importorskip("PySide6")

    from pneumo_solver_ui.desktop_mnemo.app import (
        _edge_consistency_meta,
        _edge_direction_meta,
        _edge_element_flow_contract_meta,
        _edge_operability_meta,
        _edge_pressure_drive_meta,
        _edge_recent_causality_meta,
        _edge_recent_causality_summary,
        _edge_recent_history_meta,
        _edge_recent_history_summary,
        _edge_recent_latency_meta,
        _edge_recent_latency_summary,
        _edge_phase_ribbon_meta,
        _edge_operator_hint_meta,
        _edge_operator_checklist_meta,
        _edge_recent_pressure_meta,
        _edge_recent_pressure_summary,
        _edge_temporal_meta,
    )

    edge_def = {
        "n1": "Ресивер3",
        "n2": "узел_после_рег_Pmid",
    }

    forward_meta = _edge_direction_meta(edge_def, 48.0)
    assert forward_meta["canonical_direction_label"] == "Ресивер 3 → Pmid reg"
    assert forward_meta["flow_direction_label"] == "Ресивер 3 → Pmid reg"
    assert forward_meta["flow_status_label"] == "по паспорту"
    assert forward_meta["canonical_source_short"] == "Ресивер 3"
    assert forward_meta["canonical_sink_short"] == "Pmid reg"
    assert forward_meta["flow_source_short"] == "Ресивер 3"
    assert forward_meta["flow_sink_short"] == "Pmid reg"
    assert forward_meta["flow_matches_canonical"] is True
    assert forward_meta["flow_forward"] is True

    reverse_meta = _edge_direction_meta(edge_def, -12.0)
    assert reverse_meta["canonical_direction_label"] == "Ресивер 3 → Pmid reg"
    assert reverse_meta["flow_direction_label"] == "Pmid reg → Ресивер 3"
    assert reverse_meta["flow_status_label"] == "реверс к паспорту"
    assert reverse_meta["flow_source_short"] == "Pmid reg"
    assert reverse_meta["flow_sink_short"] == "Ресивер 3"
    assert reverse_meta["flow_matches_canonical"] is False
    assert reverse_meta["flow_forward"] is False

    idle_meta = _edge_direction_meta(edge_def, 0.0)
    assert idle_meta["canonical_direction_label"] == "Ресивер 3 → Pmid reg"
    assert idle_meta["flow_direction_label"] == "нет выраженного потока"
    assert idle_meta["flow_status_label"] == "стагнация / переход"
    assert idle_meta["flow_source_short"] == ""
    assert idle_meta["flow_sink_short"] == ""
    assert idle_meta["flow_matches_canonical"] is None
    assert idle_meta["flow_forward"] is None

    forward_pressure = _edge_pressure_drive_meta(
        forward_meta,
        p1_bar_g=5.10,
        p2_bar_g=2.75,
        q_now=48.0,
    )
    assert forward_pressure["delta_p_bar"] == pytest.approx(2.35)
    assert forward_pressure["pressure_drive_label"] == "Ресивер 3 > Pmid reg"
    assert forward_pressure["pressure_drive_status"] == "согласовано с ΔP"
    assert forward_pressure["pressure_drive_badge"] == "ΔP ok"
    assert forward_pressure["endpoint_1_pressure_role"] == "P+"
    assert forward_pressure["endpoint_2_pressure_role"] == "P-"
    assert forward_pressure["flow_vs_pressure"] == "по перепаду"

    reverse_pressure = _edge_pressure_drive_meta(
        reverse_meta,
        p1_bar_g=5.10,
        p2_bar_g=2.75,
        q_now=-12.0,
    )
    assert reverse_pressure["pressure_drive_status"] == "реверс к ΔP"
    assert reverse_pressure["pressure_drive_badge"] == "ΔP rev"
    assert reverse_pressure["flow_vs_pressure"] == "против перепада"

    equalized_pressure = _edge_pressure_drive_meta(
        forward_meta,
        p1_bar_g=3.01,
        p2_bar_g=2.99,
        q_now=0.0,
    )
    assert equalized_pressure["pressure_drive_badge"] == "ΔP≈"
    assert equalized_pressure["endpoint_1_pressure_role"] == "P≈"
    assert equalized_pressure["endpoint_2_pressure_role"] == "P≈"

    check_forward = _edge_element_flow_contract_meta(
        "check",
        "Обратный клапан",
        forward_meta,
        q_now=48.0,
    )
    assert check_forward["element_flow_status"] == "по направлению элемента"
    assert check_forward["element_flow_badge"] == "EL ok"
    assert check_forward["element_flow_tone"] == "ok"

    check_reverse = _edge_element_flow_contract_meta(
        "check",
        "Обратный клапан",
        reverse_meta,
        q_now=-12.0,
    )
    assert check_reverse["element_flow_status"] == "против направления элемента"
    assert check_reverse["element_flow_badge"] == "EL rev"
    assert check_reverse["element_flow_tone"] == "warn"

    orifice_reverse = _edge_element_flow_contract_meta(
        "orifice",
        "Дроссель",
        reverse_meta,
        q_now=-12.0,
    )
    assert orifice_reverse["element_flow_status"] == "двусторонний дроссель"
    assert orifice_reverse["element_flow_badge"] == "EL bi"
    assert orifice_reverse["element_flow_tone"] == "info"

    leak_operability = _edge_operability_meta(
        "закрыт",
        q_now=12.0,
        pressure_meta=forward_pressure,
        element_meta=check_forward,
    )
    assert leak_operability["operability_status"] == "закрыт, но расход есть"
    assert leak_operability["operability_badge"] == "OP leak"
    assert leak_operability["operability_tone"] == "warn"

    healthy_operability = _edge_operability_meta(
        "открыт",
        q_now=48.0,
        pressure_meta=forward_pressure,
        element_meta=check_forward,
    )
    assert healthy_operability["operability_status"] == "ветвь ведёт себя согласованно"
    assert healthy_operability["operability_badge"] == "OP ok"
    assert healthy_operability["operability_tone"] == "ok"

    hold_operability = _edge_operability_meta(
        "открыт",
        q_now=0.0,
        pressure_meta=forward_pressure,
        element_meta=check_forward,
    )
    assert hold_operability["operability_status"] == "открыт, но расход не набран"
    assert hold_operability["operability_badge"] == "OP hold"
    assert hold_operability["operability_tone"] == "info"

    closed_conflict = _edge_consistency_meta(
        "закрыт",
        q_now=12.0,
        pressure_meta=forward_pressure,
        element_meta=check_forward,
    )
    assert closed_conflict["consistency_status"] == "сигнал закрытия конфликтует с расходом"
    assert closed_conflict["consistency_badge"] == "CS q"
    assert closed_conflict["consistency_tone"] == "warn"

    healthy_consistency = _edge_consistency_meta(
        "открыт",
        q_now=48.0,
        pressure_meta=forward_pressure,
        element_meta=check_forward,
    )
    assert healthy_consistency["consistency_status"] == "сигналы ветви согласованы"
    assert healthy_consistency["consistency_badge"] == "CS ok"
    assert healthy_consistency["consistency_tone"] == "ok"

    delayed_consistency = _edge_consistency_meta(
        "открыт",
        q_now=0.0,
        pressure_meta={"pressure_drive_badge": "ΔP ok"},
        element_meta=check_forward,
    )
    assert delayed_consistency["consistency_status"] == "открыт, но расход запаздывает"
    assert delayed_consistency["consistency_badge"] == "CS hold"
    assert delayed_consistency["consistency_tone"] == "info"

    ramp_temporal = _edge_temporal_meta(
        time_s=np.array([0.0, 0.2, 0.4, 0.6], dtype=float),
        q_values=np.array([0.0, 8.0, 18.0, 36.0], dtype=float),
        open_values=np.array([1, 1, 1, 1], dtype=int),
        idx=3,
    )
    assert ramp_temporal["temporal_status"] == "набор расхода"
    assert ramp_temporal["temporal_badge"] == "TM ramp"
    assert ramp_temporal["temporal_tone"] == "info"

    steady_temporal = _edge_temporal_meta(
        time_s=np.array([0.0, 0.2, 0.4, 0.6], dtype=float),
        q_values=np.array([28.0, 30.0, 29.0, 30.0], dtype=float),
        open_values=np.array([1, 1, 1, 1], dtype=int),
        idx=3,
    )
    assert steady_temporal["temporal_status"] == "устойчивый ход"
    assert steady_temporal["temporal_badge"] == "TM steady"
    assert steady_temporal["temporal_tone"] == "ok"

    oscillation_temporal = _edge_temporal_meta(
        time_s=np.array([0.0, 0.2, 0.4, 0.6], dtype=float),
        q_values=np.array([18.0, -20.0, 22.0, -19.0], dtype=float),
        open_values=np.array([1, 1, 1, 1], dtype=int),
        idx=3,
    )
    assert oscillation_temporal["temporal_status"] == "колебание расхода"
    assert oscillation_temporal["temporal_badge"] == "TM osc"
    assert oscillation_temporal["temporal_tone"] == "warn"

    recent_history = _edge_recent_history_meta(
        time_s=np.array([0.0, 0.2, 0.4, 0.6], dtype=float),
        q_values=np.array([0.0, 8.0, 18.0, 36.0], dtype=float),
        open_values=np.array([0, 1, 1, 1], dtype=int),
        idx=3,
        max_points=4,
    )
    assert recent_history["history_available"] is True
    assert recent_history["history_sample_count"] == 4
    assert recent_history["history_peak_abs"] == pytest.approx(36.0)
    assert recent_history["history_span_s"] == pytest.approx(0.6)
    assert recent_history["history_open_ratio"] == pytest.approx(0.75)
    assert len(recent_history["history_points"]) == 4
    assert len(recent_history["history_open_blocks"]) == 4
    assert _edge_recent_history_summary(recent_history, "л/мин").startswith("0.60 s")

    recent_pressure = _edge_recent_pressure_meta(
        time_s=np.array([0.0, 0.2, 0.4, 0.6], dtype=float),
        p1_values=np.array([5.2, 5.0, 4.4, 3.6], dtype=float),
        p2_values=np.array([2.0, 2.1, 2.3, 2.6], dtype=float),
        idx=3,
        max_points=4,
    )
    assert recent_pressure["pressure_history_available"] is True
    assert recent_pressure["pressure_history_sample_count"] == 4
    assert recent_pressure["pressure_history_peak_abs"] == pytest.approx(3.2)
    assert recent_pressure["pressure_history_last_delta"] == pytest.approx(1.0)
    assert recent_pressure["pressure_history_status"] == "ΔP заметно перестраивается"
    assert recent_pressure["pressure_history_tone"] == "info"
    assert len(recent_pressure["pressure_history_points"]) == 4
    assert _edge_recent_pressure_summary(recent_pressure).startswith("0.60 s")

    causality_meta = _edge_recent_causality_meta(
        state_label="открыт",
        history_meta=recent_history,
        pressure_meta=recent_pressure,
        temporal_meta=ramp_temporal,
        consistency_meta=healthy_consistency,
    )
    assert causality_meta["causality_status"] == "Q откликается на открытие и ΔP"
    assert causality_meta["causality_badge"] == "CX ok"
    assert causality_meta["causality_tone"] == "ok"
    assert _edge_recent_causality_summary(causality_meta, recent_history).startswith("Q откликается")

    latency_meta = _edge_recent_latency_meta(
        time_s=np.array([0.0, 0.2, 0.4, 0.6], dtype=float),
        q_values=np.array([0.0, 0.0, 8.0, 20.0], dtype=float),
        open_values=np.array([0, 1, 1, 1], dtype=int),
        p1_values=np.array([2.0, 2.0, 5.0, 5.0], dtype=float),
        p2_values=np.array([2.0, 2.0, 2.0, 2.0], dtype=float),
        idx=3,
        max_points=4,
    )
    assert latency_meta["latency_status"] == "Q подключается с умеренным лагом"
    assert latency_meta["latency_badge"] == "LG soft"
    assert latency_meta["latency_tone"] == "info"
    assert latency_meta["latency_s"] == pytest.approx(0.2)
    assert latency_meta["latency_cause"] == "открытия"
    assert latency_meta["latency_phase_label"] == "SIG → ΔP → Q"
    assert latency_meta["latency_signal_x"] == pytest.approx(1.0 / 3.0)
    assert latency_meta["latency_dp_x"] == pytest.approx(2.0 / 3.0)
    assert latency_meta["latency_q_x"] == pytest.approx(2.0 / 3.0)
    assert _edge_recent_latency_summary(latency_meta).startswith("Q подключается")

    phase_ribbon = _edge_phase_ribbon_meta(latency_meta)
    assert phase_ribbon["phase_ribbon_label"] == "SIG(1) → ΔP(2) → Q(3)"
    assert phase_ribbon["phase_ribbon_interval_label"] == "SIG→ΔP +0.20s • ΔP→Q 0.00s"
    assert phase_ribbon["phase_ribbon_bottleneck_label"] == "SIG→ΔP +0.20s"
    assert phase_ribbon["phase_ribbon_bottleneck_status"] == "умеренный интервал"
    assert phase_ribbon["phase_ribbon_bottleneck_tone"] == "info"
    assert phase_ribbon["phase_ribbon_bottleneck_kind"] == "контур управления"
    assert "между командой" in phase_ribbon["phase_ribbon_bottleneck_comment"]
    assert phase_ribbon["phase_ribbon_focus_pair_label"] == "SIG → ΔP"
    assert phase_ribbon["phase_ribbon_focus_stage_labels"] == ["SIG", "ΔP"]
    assert "сигнала и набора ΔP" in phase_ribbon["phase_ribbon_focus_hint"]
    stages = list(phase_ribbon["phase_ribbon_stages"])
    assert [stage["label"] for stage in stages] == ["SIG", "ΔP", "Q"]
    assert [stage["chip_text"] for stage in stages] == ["1 SIG", "2 ΔP", "3 Q"]
    assert stages[-1]["tone"] == "info"
    intervals = list(phase_ribbon["phase_ribbon_intervals"])
    assert [interval["chip_text"] for interval in intervals] == ["+0.20s", "0.00s"]
    assert [interval["tone"] for interval in intervals] == ["info", "ok"]
    assert [interval["is_bottleneck"] for interval in intervals] == [True, False]
    assert [interval["kind_label"] for interval in intervals] == ["контур управления", "расходный отклик"]

    operator_hint = _edge_operator_hint_meta(
        component_kind="Регулятор",
        canonical_kind="reg_after",
        operability_status=healthy_operability["operability_status"],
        consistency_status=healthy_consistency["consistency_status"],
        pressure_drive_status=forward_pressure["pressure_drive_status"],
        latency_status=latency_meta["latency_status"],
        phase_ribbon_bottleneck_kind=phase_ribbon["phase_ribbon_bottleneck_kind"],
        phase_ribbon_bottleneck_comment=phase_ribbon["phase_ribbon_bottleneck_comment"],
        phase_ribbon_focus_hint=phase_ribbon["phase_ribbon_focus_hint"],
    )
    assert operator_hint["operator_hint_title"] == "проверить команду и сборку ΔP"
    assert "регулятор" in operator_hint["operator_hint_label"]
    assert operator_hint["operator_hint_badge"] == "ACT ctrl"
    assert operator_hint["operator_hint_tone"] == "info"

    operator_checklist = _edge_operator_checklist_meta(
        component_kind="Регулятор",
        canonical_kind="reg_after",
        operator_hint_badge=operator_hint["operator_hint_badge"],
        phase_ribbon_bottleneck_kind=phase_ribbon["phase_ribbon_bottleneck_kind"],
        operability_status=healthy_operability["operability_status"],
        consistency_status=healthy_consistency["consistency_status"],
    )
    assert operator_checklist["operator_checklist_items"][0] == "момент прихода команды на ветвь"
    assert operator_checklist["operator_checklist_rows"][0]["index_label"] == "01"
    assert operator_checklist["operator_checklist_rows"][0]["title"] == "момент прихода команды на ветвь"
    assert operator_checklist["operator_checklist_rows"][0]["is_focus"] is True
    assert operator_checklist["operator_checklist_rows"][0]["tone"] == "info"
    assert "ΔP сразу после команды" in operator_checklist["operator_checklist_summary"]
