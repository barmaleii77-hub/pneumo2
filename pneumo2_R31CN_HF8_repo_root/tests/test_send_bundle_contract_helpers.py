from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.tools.send_bundle_contract import (
    ANIM_LATEST_INDEX_FIELDS,
    ANIM_LATEST_REGISTRY_EVENT_FIELDS,
    ANIM_GLOBAL_POINTER,
    ANIM_LOCAL_NPZ,
    ANIM_LOCAL_POINTER,
    annotate_anim_source_for_bundle,
    build_anim_operator_recommendations,
    choose_anim_snapshot,
    extract_anim_snapshot,
    format_anim_dashboard_brief_lines,
    load_latest_send_bundle_anim_dashboard,
    normalize_anim_dashboard_obj,
    pick_anim_latest_fields,
    render_anim_latest_md,
    summarize_ring_closure,
)


def test_extract_anim_snapshot_supports_legacy_anim_latest_fields() -> None:
    snap = extract_anim_snapshot(
        {
            "anim_latest_available": True,
            "anim_latest_pointer_json": "/abs/workspace/exports/anim_latest.json",
            "anim_latest_global_pointer_json": "/abs/workspace/_pointers/anim_latest.json",
            "anim_latest_npz_path": "/abs/workspace/exports/anim_latest.npz",
            "anim_latest_visual_cache_token": "tok-123",
            "anim_latest_visual_reload_inputs": ["npz", "road_csv"],
            "anim_latest_updated_utc": "2026-04-07T12:00:00+00:00",
            "anim_latest_meta": {
                "road_csv": "anim_latest_road_csv.csv",
                "scenario_kind": "ring",
                "ring_closure_policy": "strict_exact",
                "ring_seam_open": True,
                "ring_seam_max_jump_m": 0.012,
                "ring_raw_seam_max_jump_m": 0.015,
            },
        },
        source="diagnostics",
    )

    assert snap is not None
    assert snap["source"] == "diagnostics"
    assert snap["available"] is True
    assert snap["visual_cache_token"] == "tok-123"
    assert snap["visual_reload_inputs"] == ["npz", "road_csv"]
    assert snap["pointer_json"].endswith("anim_latest.json")
    assert snap["npz_path"].endswith("anim_latest.npz")
    assert snap["scenario_kind"] == "ring"
    assert snap["ring_closure_policy"] == "strict_exact"
    assert snap["ring_seam_open"] is True
    assert snap["ring_seam_max_jump_m"] == 0.012


def test_annotate_anim_source_for_bundle_marks_mirrored_pointer_and_npz() -> None:
    annotated = annotate_anim_source_for_bundle(
        {
            "source": "local_pointer",
            "available": True,
            "pointer_json": "/abs/workspace/exports/anim_latest.json",
            "npz_path": "/abs/workspace/exports/anim_latest.npz",
            "visual_cache_token": "tok-123",
            "issues": [],
        },
        name_set={ANIM_LOCAL_POINTER, ANIM_LOCAL_NPZ, ANIM_GLOBAL_POINTER},
    )

    assert annotated is not None
    assert annotated["pointer_json_in_bundle"] is True
    assert annotated["npz_path_in_bundle"] is True
    assert annotated["usable_from_bundle"] is True
    assert annotated["issues"] == []


def test_choose_anim_snapshot_prefers_requested_source_and_reports_mismatch() -> None:
    chosen = choose_anim_snapshot(
        {
            "diagnostics": {
                "source": "diagnostics",
                "available": True,
                "visual_cache_token": "tok-sidecar",
                "visual_reload_inputs": ["npz", "road_csv"],
                "npz_path": "/abs/workspace/exports/anim_latest.npz",
                "issues": [],
            },
            "global_pointer": {
                "source": "global_pointer",
                "available": True,
                "visual_cache_token": "tok-global",
                "visual_reload_inputs": ["npz", "road_csv"],
                "npz_path": "/abs/workspace/exports/anim_latest.npz",
                "issues": [],
            },
        },
        preferred_order=("diagnostics", "global_pointer"),
    )

    assert chosen["source"] == "diagnostics"
    assert chosen["visual_cache_token"] == "tok-sidecar"
    assert chosen["pointer_sync_ok"] is False
    assert any("Токен визуального кэша" in msg for msg in chosen["issues"])


def test_dashboard_normalization_and_rendering_use_shared_contract() -> None:
    norm = normalize_anim_dashboard_obj(
        {
            "anim_latest_available": True,
            "anim_latest_pointer_json": "/abs/workspace/exports/anim_latest.json",
            "anim_latest_npz_path": "/abs/workspace/exports/anim_latest.npz",
            "anim_latest_visual_cache_token": "tok-123",
            "anim_latest_visual_reload_inputs": ["npz"],
            "anim_latest_meta": {
                "scenario_kind": "ring",
                "ring_closure_policy": "strict_exact",
                "ring_seam_open": True,
                "ring_seam_max_jump_m": 0.012,
                "ring_raw_seam_max_jump_m": 0.015,
            },
            "anim_latest_mnemo_event_log_ref": "anim_latest.desktop_mnemo_events.json",
            "anim_latest_mnemo_event_log_exists": True,
            "anim_latest_mnemo_event_log_current_mode": "Регуляторный коридор",
            "anim_latest_mnemo_event_log_event_count": 5,
            "anim_latest_mnemo_event_log_active_latch_count": 1,
            "anim_latest_mnemo_event_log_acknowledged_latch_count": 2,
            "anim_latest_mnemo_event_log_recent_titles": ["Большой перепад давлений", "Смена режима"],
            "usable_from_bundle": True,
        }
    )
    md = render_anim_latest_md(norm)

    assert norm["available"] is True
    assert norm["visual_cache_token"] == "tok-123"
    assert norm["visual_reload_inputs"] == ["npz"]
    assert norm["ring_closure_policy"] == "strict_exact"
    assert norm["ring_seam_open"] is True
    assert "tok-123" in md
    assert "Замыкание кольца: режим=strict_exact / применено=None / шов открыт=True / скачок шва, м=0.012 / исходный скачок, м=0.015" in md
    assert "Состояние событий мнемосхемы: режим=Регуляторный коридор / всего=5 / активно=1 / принято=2" in md
    assert "Восстанавливается из архива: True" in md


def test_pick_anim_latest_fields_copies_selected_lists_and_ignores_unknowns() -> None:
    raw = {
        "anim_latest_available": True,
        "anim_latest_visual_reload_inputs": ["npz"],
        "anim_latest_issues": ["warn-1"],
        "anim_latest_visual_cache_dependencies": {"npz": {"path": "x.npz"}},
        "anim_latest_mnemo_event_log_exists": True,
        "anim_latest_mnemo_event_log_recent_titles": ["Большой перепад давлений"],
        "browser_perf_status": "snapshot_only",
        "other": "ignore-me",
    }

    picked_event = pick_anim_latest_fields(raw, fields=ANIM_LATEST_REGISTRY_EVENT_FIELDS)
    picked_index = pick_anim_latest_fields(raw, fields=ANIM_LATEST_INDEX_FIELDS)

    assert picked_event["anim_latest_available"] is True
    assert picked_event["anim_latest_visual_reload_inputs"] == ["npz"]
    assert picked_event["anim_latest_issues"] == ["warn-1"]
    assert picked_event["anim_latest_visual_cache_dependencies"] == {"npz": {"path": "x.npz"}}
    assert picked_event["anim_latest_mnemo_event_log_exists"] is True
    assert picked_event["anim_latest_mnemo_event_log_recent_titles"] == ["Большой перепад давлений"]
    assert "other" not in picked_event
    assert "anim_latest_visual_cache_dependencies" not in picked_index
    assert picked_index["anim_latest_mnemo_event_log_exists"] is True
    assert picked_index["anim_latest_mnemo_event_log_recent_titles"] == ["Большой перепад давлений"]

    raw["anim_latest_visual_reload_inputs"].append("road_csv")
    raw["anim_latest_issues"].append("warn-2")
    raw["anim_latest_mnemo_event_log_recent_titles"].append("ACK latched-событий")
    assert picked_event["anim_latest_visual_reload_inputs"] == ["npz"]
    assert picked_event["anim_latest_issues"] == ["warn-1"]
    assert picked_event["anim_latest_mnemo_event_log_recent_titles"] == ["Большой перепад давлений"]


def test_load_latest_send_bundle_anim_dashboard_merges_validation_bundle_flags(tmp_path: Path) -> None:
    out_dir = tmp_path
    (out_dir / "latest_anim_pointer_diagnostics.json").write_text(
        json.dumps(
            {
                "anim_latest_available": True,
                "anim_latest_pointer_json": "/abs/workspace/exports/anim_latest.json",
                "anim_latest_npz_path": "/abs/workspace/exports/anim_latest.npz",
                "anim_latest_visual_cache_token": "tok-123",
                "anim_latest_visual_reload_inputs": ["npz", "road_csv"],
                "anim_latest_meta": {
                    "scenario_kind": "ring",
                    "ring_closure_policy": "strict_exact",
                    "ring_seam_open": True,
                    "ring_seam_max_jump_m": 0.012,
                    "ring_raw_seam_max_jump_m": 0.015,
                },
                "anim_latest_mnemo_event_log_ref": "anim_latest.desktop_mnemo_events.json",
                "anim_latest_mnemo_event_log_exists": True,
                "anim_latest_mnemo_event_log_current_mode": "Регуляторный коридор",
                "anim_latest_mnemo_event_log_event_count": 4,
                "anim_latest_mnemo_event_log_active_latch_count": 1,
                "anim_latest_mnemo_event_log_acknowledged_latch_count": 2,
                "anim_latest_mnemo_event_log_recent_titles": ["Большой перепад давлений", "Смена режима"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "latest_send_bundle_validation.json").write_text(
        json.dumps(
            {
                "anim_latest": {
                    "available": True,
                    "visual_cache_token": "tok-123",
                    "browser_perf_evidence_status": "trace_bundle_ready",
                    "browser_perf_evidence_level": "PASS",
                    "browser_perf_bundle_ready": True,
                    "browser_perf_comparison_status": "regression_checked",
                    "browser_perf_comparison_level": "PASS",
                    "browser_perf_comparison_ready": True,
                    "browser_perf_registry_snapshot_in_bundle": True,
                    "browser_perf_previous_snapshot_in_bundle": True,
                    "browser_perf_contract_in_bundle": True,
                    "browser_perf_evidence_report_in_bundle": True,
                    "browser_perf_comparison_report_in_bundle": True,
                    "browser_perf_trace_in_bundle": True,
                },
                "optimizer_scope": {
                    "problem_hash": "ph_scope_full_1234567890",
                    "problem_hash_short": "ph_scope_12",
                    "problem_hash_mode": "stable",
                    "canonical_source": "triage",
                    "scope_sync_ok": False,
                    "mismatch_fields": ["problem_hash", "problem_hash_mode"],
                },
                "optimizer_scope_gate": {
                    "release_gate": "FAIL",
                    "release_gate_reason": "problem_hash mismatch between sources",
                    "release_risk": True,
                    "canonical_source": "triage",
                    "scope_sync_ok": False,
                    "mismatch_fields": ["problem_hash", "problem_hash_mode"],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    anim = load_latest_send_bundle_anim_dashboard(out_dir)
    lines = format_anim_dashboard_brief_lines(anim)

    assert anim["visual_cache_token"] == "tok-123"
    assert anim["browser_perf_evidence_status"] == "trace_bundle_ready"
    assert anim["browser_perf_bundle_ready"] is True
    assert anim["browser_perf_comparison_ready"] is True
    assert anim["browser_perf_evidence_report_in_bundle"] is True
    assert anim["anim_latest_mnemo_event_log_exists"] is True
    assert anim["ring_closure_policy"] == "strict_exact"
    assert anim["ring_seam_open"] is True
    assert anim["optimizer_scope_release_gate"] == "FAIL"
    assert anim["optimizer_scope_release_risk"] is True
    assert anim["optimizer_scope_problem_hash_short"] == "ph_scope_12"
    assert anim["optimizer_scope_problem_hash_mode"] == "stable"
    assert any(
        "Допуск области оптимизации: FAIL / риск выпуска=True / причина=problem_hash mismatch between sources" == line
        for line in lines
    )
    assert any(
        "Область оптимизации: ключ=ph_scope_12 / режим=stable / источник=triage / синхронизация=False / расхождения=problem_hash, problem_hash_mode" == line
        for line in lines
    )
    assert any("Данные производительности анимации: trace_bundle_ready / PASS / готовы_в_архиве=True" == line for line in lines)
    assert any("Сравнение производительности анимации: regression_checked / PASS / готово=True" == line for line in lines)
    assert any("Шов кольца: замыкание=strict_exact / открыт=True / скачок_м=0.012 / исходный_скачок_м=0.015" == line for line in lines)
    assert any("Данные производительности в архиве:" in line and "трасса=True" in line for line in lines)
    assert any("События мнемосхемы: есть=True / всего=4 / активно=1 / принято=2 / режим=Регуляторный коридор" == line for line in lines)
    assert any("Недавние события мнемосхемы: Большой перепад давлений | Смена режима" == line for line in lines)


def test_build_anim_operator_recommendations_prioritizes_mnemo_and_perf_actions() -> None:
    recommendations = build_anim_operator_recommendations(
        {
            "anim_latest_available": True,
            "anim_latest_pointer_json": "/abs/workspace/exports/anim_latest.json",
            "anim_latest_npz_path": "/abs/workspace/exports/anim_latest.npz",
            "anim_latest_mnemo_event_log_exists": True,
            "anim_latest_mnemo_event_log_current_mode": "Регуляторный коридор",
            "anim_latest_mnemo_event_log_active_latch_count": 1,
            "anim_latest_mnemo_event_log_acknowledged_latch_count": 2,
            "anim_latest_mnemo_event_log_recent_titles": ["Большой перепад давлений"],
            "browser_perf_evidence_status": "snapshot_only",
            "browser_perf_evidence_level": "WARN",
            "browser_perf_bundle_ready": False,
            "browser_perf_comparison_status": "no_reference",
            "browser_perf_comparison_level": "WARN",
            "browser_perf_comparison_ready": False,
            "pointer_sync_ok": False,
            "usable_from_bundle": False,
        }
    )

    assert recommendations
    assert recommendations[0].startswith("Сначала откройте мнемосхему")
    assert any("Обновите данные производительности" in item for item in recommendations)
    assert any("эталонный снимок производительности" in item for item in recommendations)
    assert any("Повторно экспортируйте последнюю анимацию" in item for item in recommendations)
    assert any("Пересоберите архив" in item for item in recommendations)


def test_ring_closure_summary_and_recommendations_surface_strict_exact_open_seam() -> None:
    anim = {
        "anim_latest_available": True,
        "anim_latest_meta": {
            "scenario_kind": "ring",
            "ring_closure_policy": "strict_exact",
            "ring_closure_applied": False,
            "ring_seam_open": True,
            "ring_seam_max_jump_m": 0.012,
            "ring_raw_seam_max_jump_m": 0.015,
        },
    }

    ring = summarize_ring_closure(anim)
    recommendations = build_anim_operator_recommendations(anim)

    assert ring["severity"] == "warn"
    assert ring["closure_policy"] == "strict_exact"
    assert ring["seam_open"] is True
    assert any("открытый шов кольца ожидаем" in item for item in recommendations)
