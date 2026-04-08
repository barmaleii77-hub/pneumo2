from __future__ import annotations

from pneumo_solver_ui.tools.send_bundle_contract import (
    ANIM_LATEST_INDEX_FIELDS,
    ANIM_LATEST_REGISTRY_EVENT_FIELDS,
    ANIM_GLOBAL_POINTER,
    ANIM_LOCAL_NPZ,
    ANIM_LOCAL_POINTER,
    annotate_anim_source_for_bundle,
    choose_anim_snapshot,
    extract_anim_snapshot,
    normalize_anim_dashboard_obj,
    pick_anim_latest_fields,
    render_anim_latest_md,
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
            "anim_latest_meta": {"road_csv": "anim_latest_road_csv.csv"},
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
    assert any("visual_cache_token mismatch" in msg for msg in chosen["issues"])


def test_dashboard_normalization_and_rendering_use_shared_contract() -> None:
    norm = normalize_anim_dashboard_obj(
        {
            "anim_latest_available": True,
            "anim_latest_pointer_json": "/abs/workspace/exports/anim_latest.json",
            "anim_latest_npz_path": "/abs/workspace/exports/anim_latest.npz",
            "anim_latest_visual_cache_token": "tok-123",
            "anim_latest_visual_reload_inputs": ["npz"],
            "usable_from_bundle": True,
        }
    )
    md = render_anim_latest_md(norm)

    assert norm["available"] is True
    assert norm["visual_cache_token"] == "tok-123"
    assert norm["visual_reload_inputs"] == ["npz"]
    assert "tok-123" in md
    assert "usable_from_bundle: True" in md


def test_pick_anim_latest_fields_copies_selected_lists_and_ignores_unknowns() -> None:
    raw = {
        "anim_latest_available": True,
        "anim_latest_visual_reload_inputs": ["npz"],
        "anim_latest_issues": ["warn-1"],
        "anim_latest_visual_cache_dependencies": {"npz": {"path": "x.npz"}},
        "browser_perf_status": "snapshot_only",
        "other": "ignore-me",
    }

    picked_event = pick_anim_latest_fields(raw, fields=ANIM_LATEST_REGISTRY_EVENT_FIELDS)
    picked_index = pick_anim_latest_fields(raw, fields=ANIM_LATEST_INDEX_FIELDS)

    assert picked_event["anim_latest_available"] is True
    assert picked_event["anim_latest_visual_reload_inputs"] == ["npz"]
    assert picked_event["anim_latest_issues"] == ["warn-1"]
    assert picked_event["anim_latest_visual_cache_dependencies"] == {"npz": {"path": "x.npz"}}
    assert "other" not in picked_event
    assert "anim_latest_visual_cache_dependencies" not in picked_index

    raw["anim_latest_visual_reload_inputs"].append("road_csv")
    raw["anim_latest_issues"].append("warn-2")
    assert picked_event["anim_latest_visual_reload_inputs"] == ["npz"]
    assert picked_event["anim_latest_issues"] == ["warn-1"]
