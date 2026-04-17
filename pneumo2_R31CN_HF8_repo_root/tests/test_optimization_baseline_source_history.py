from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.desktop_suite_snapshot import build_validated_suite_snapshot
from pneumo_solver_ui.optimization_baseline_source import (
    ACTIVE_BASELINE_CONTRACT_SCHEMA_VERSION,
    BASELINE_STALE_BANNER_ID,
    WS_BASELINE_HANDOFF_ID,
    append_baseline_history_item,
    apply_baseline_center_action,
    baseline_center_evidence_payload,
    baseline_history_item_from_contract,
    baseline_suite_handoff_snapshot_path,
    baseline_suite_handoff_launch_gate,
    baseline_review_adopt_restore_policy,
    build_active_baseline_contract,
    build_baseline_center_surface,
    compare_active_and_historical_baseline,
    describe_active_baseline_state,
    read_active_baseline_contract,
    read_baseline_history,
    resolve_active_baseline_handoff,
    write_active_baseline_contract,
    write_baseline_source_artifact,
)
from pneumo_solver_ui.optimization_baseline_source_ui import (
    baseline_suite_handoff_surface_payload,
    render_baseline_center_summary,
)
from pneumo_solver_ui.optimization_run_history import (
    format_run_choice,
    summarize_optimization_run,
)


def _suite_snapshot(
    *,
    inputs_hash: str = "inputs-hash-1",
    ring_hash: str = "ring-hash-1",
) -> dict[str, object]:
    return build_validated_suite_snapshot(
        [
            {
                "id": "baseline-row-1",
                "имя": "baseline_smoke",
                "тип": "инерция_крен",
                "включен": True,
                "стадия": 0,
                "dt": 0.01,
                "t_end": 1.0,
            }
        ],
        inputs_snapshot_hash=inputs_hash,
        ring_source_hash=ring_hash,
        created_at_utc="2026-04-17T00:00:00Z",
        context_label="baseline-unit",
    )


def test_run_history_reads_staged_baseline_source_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "p_stage_demo"
    run_dir.mkdir(parents=True)
    (run_dir / "sp.json").write_text(
        '{"status": "done", "ts": "2026-04-10 14:00:00", "combined_csv": ""}',
        encoding="utf-8",
    )
    (run_dir / "results_all.csv").write_text("id,val\n1,2\n", encoding="utf-8")
    write_baseline_source_artifact(
        run_dir,
        {
            "version": "baseline_source_v1",
            "source_kind": "scoped",
            "source_label": "scoped baseline",
            "baseline_path": "C:/workspace/baselines/by_problem/p_demo/baseline_best.json",
        },
    )

    summary = summarize_optimization_run(run_dir)

    assert summary is not None
    assert summary.baseline_source_kind == "scoped"
    assert summary.baseline_source_label == "scoped baseline"
    assert summary.baseline_source_path == Path("C:/workspace/baselines/by_problem/p_demo/baseline_best.json")
    assert "base=scoped" in format_run_choice(summary)


def test_run_history_reads_coordinator_baseline_source_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "p_coord_demo"
    export_dir = run_dir / "export"
    export_dir.mkdir(parents=True)
    (run_dir / "coordinator.log").write_text("started\n", encoding="utf-8")
    (export_dir / "trials.csv").write_text("trial_id,status,error_text\n1,DONE,\n", encoding="utf-8")
    write_baseline_source_artifact(
        run_dir,
        {
            "version": "baseline_source_v1",
            "source_kind": "global",
            "source_label": "global baseline fallback",
            "baseline_path": "C:/workspace/baselines/baseline_best.json",
        },
    )

    summary = summarize_optimization_run(run_dir)

    assert summary is not None
    assert summary.baseline_source_kind == "global"
    assert summary.baseline_source_label == "global baseline fallback"
    assert summary.baseline_source_path == Path("C:/workspace/baselines/baseline_best.json")
    assert "base=global" in format_run_choice(summary)


def test_active_baseline_contract_roundtrip_history_and_restore_policy(tmp_path: Path) -> None:
    suite_snapshot = _suite_snapshot()
    active = build_active_baseline_contract(
        suite_snapshot=suite_snapshot,
        baseline_path=tmp_path / "baseline_best.json",
        baseline_payload={"param_a": 1.0},
        baseline_score_payload={"score": [0.0, 1.0]},
        baseline_meta={"problem_hash": "ph-active"},
        source_run_dir=tmp_path / "runs" / "p_active",
        policy_mode="review_adopt",
        created_at_utc="2026-04-17T00:05:00Z",
    )

    target = write_active_baseline_contract(active, workspace_dir=tmp_path / "workspace")
    loaded = read_active_baseline_contract(path=target)
    resolved = resolve_active_baseline_handoff(
        workspace_dir=tmp_path / "workspace",
        current_suite_snapshot_hash=str(suite_snapshot["suite_snapshot_hash"]),
    )
    history_item = baseline_history_item_from_contract(active, action="adopt", actor="unit")
    history_path = append_baseline_history_item(history_item, workspace_dir=tmp_path / "workspace")
    history = read_baseline_history(path=history_path)

    assert active["schema_version"] == ACTIVE_BASELINE_CONTRACT_SCHEMA_VERSION
    assert active["handoff_id"] == WS_BASELINE_HANDOFF_ID
    assert len(str(active["active_baseline_hash"])) == 64
    assert active["suite_snapshot_hash"] == suite_snapshot["suite_snapshot_hash"]
    assert loaded["active_baseline_hash"] == active["active_baseline_hash"]
    assert resolved["state"] == "current"
    assert resolved["optimizer_can_consume"] is True
    assert resolved["silent_rebinding_allowed"] is False
    assert history[0]["active_baseline_hash"] == active["active_baseline_hash"]
    assert compare_active_and_historical_baseline(active, history[0])["state"] == "active"

    historical_same_context = build_active_baseline_contract(
        suite_snapshot=suite_snapshot,
        baseline_payload={"param_a": 2.0},
        baseline_meta={"problem_hash": "ph-active"},
        policy_mode="review_adopt",
        created_at_utc="2026-04-17T00:06:00Z",
    )
    compare = compare_active_and_historical_baseline(active, historical_same_context)
    blocked = baseline_review_adopt_restore_policy(
        historical_same_context,
        active_contract=active,
        action="restore",
        explicit=False,
    )
    explicit = baseline_review_adopt_restore_policy(
        historical_same_context,
        active_contract=active,
        action="restore",
        explicit=True,
    )

    assert compare["state"] == "historical_same_context"
    assert compare["silent_rebinding_allowed"] is False
    assert blocked["can_apply"] is False
    assert blocked["requires_explicit_action"] is True
    assert explicit["can_apply"] is True
    assert explicit["silent_rebinding_allowed"] is False


def test_stale_active_baseline_banner_blocks_optimizer_and_silent_rebinding(tmp_path: Path) -> None:
    suite_snapshot = _suite_snapshot()
    active = build_active_baseline_contract(
        suite_snapshot=suite_snapshot,
        baseline_payload={"param_a": 1.0},
        baseline_meta={"problem_hash": "ph-stale"},
        created_at_utc="2026-04-17T00:07:00Z",
    )
    write_active_baseline_contract(active, workspace_dir=tmp_path / "workspace")

    stale = describe_active_baseline_state(
        active,
        current_suite_snapshot_hash="different-suite-hash",
    )
    resolved = resolve_active_baseline_handoff(
        workspace_dir=tmp_path / "workspace",
        current_suite_snapshot_hash="different-suite-hash",
    )
    missing = resolve_active_baseline_handoff(workspace_dir=tmp_path / "empty-workspace")

    assert stale["state"] == "stale"
    assert stale["banner_id"] == BASELINE_STALE_BANNER_ID
    assert "suite_snapshot_hash_changed" in stale["stale_reasons"]
    assert stale["optimizer_can_consume"] is False
    assert resolved["state"] == "stale"
    assert resolved["optimizer_can_consume"] is False
    assert resolved["silent_rebinding_allowed"] is False
    assert missing["state"] == "missing"
    assert missing["silent_rebinding_allowed"] is False
    assert "baseline_best.json" in missing["banner"]


def test_baseline_suite_handoff_launch_gate_blocks_missing_stale_invalid_and_force(tmp_path: Path) -> None:
    missing = baseline_suite_handoff_launch_gate(
        launch_profile="baseline",
        runtime_policy="force",
        workspace_dir=tmp_path / "missing-workspace",
    )

    workspace = tmp_path / "workspace"
    suite_snapshot = _suite_snapshot()
    suite_path = baseline_suite_handoff_snapshot_path(workspace_dir=workspace)
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite_path.write_text(json.dumps(suite_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    current = baseline_suite_handoff_launch_gate(
        launch_profile="baseline",
        runtime_policy="balanced",
        workspace_dir=workspace,
        current_suite_snapshot_hash=str(suite_snapshot["suite_snapshot_hash"]),
    )
    stale = baseline_suite_handoff_launch_gate(
        launch_profile="baseline",
        runtime_policy="force",
        workspace_dir=workspace,
        current_suite_snapshot_hash="different-suite-hash",
    )
    detail_warning = baseline_suite_handoff_launch_gate(
        launch_profile="detail",
        runtime_policy="force",
        workspace_dir=tmp_path / "missing-workspace",
    )

    invalid_snapshot = dict(suite_snapshot)
    invalid_snapshot["validated"] = False
    invalid_snapshot["validation"] = {**dict(invalid_snapshot.get("validation") or {}), "ok": False}
    suite_path.write_text(json.dumps(invalid_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    invalid = baseline_suite_handoff_launch_gate(
        launch_profile="baseline",
        runtime_policy="force",
        workspace_dir=workspace,
    )

    assert missing["state"] == "missing"
    assert missing["baseline_launch_allowed"] is False
    assert missing["runtime_policy_can_bypass"] is False
    assert "runtime_policy не может обойти" in missing["banner"]
    assert current["state"] == "current"
    assert current["baseline_launch_allowed"] is True
    assert stale["state"] == "stale"
    assert stale["baseline_launch_allowed"] is False
    assert stale["runtime_policy"] == "force"
    assert invalid["state"] == "invalid"
    assert invalid["baseline_launch_allowed"] is False
    assert detail_warning["warning_only"] is True
    assert detail_warning["baseline_launch_allowed"] is True
    assert "не блокирует detail/full" in detail_warning["banner"]


def test_optimization_baseline_source_ui_surfaces_ho005_next_to_active_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    suite_snapshot = _suite_snapshot()
    suite_path = baseline_suite_handoff_snapshot_path(workspace_dir=workspace)
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite_path.write_text(json.dumps(suite_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    active = build_active_baseline_contract(
        suite_snapshot=suite_snapshot,
        baseline_payload={"param_a": 1.0},
        baseline_meta={"problem_hash": "ph-ui"},
        created_at_utc="2026-04-17T00:16:00Z",
    )
    write_active_baseline_contract(active, workspace_dir=workspace)

    payload = baseline_suite_handoff_surface_payload(
        workspace_dir=workspace,
        current_suite_snapshot_hash=str(suite_snapshot["suite_snapshot_hash"]),
    )
    surface = build_baseline_center_surface(workspace_dir=workspace)

    class FakeStreamlit:
        def __init__(self) -> None:
            self.lines: list[str] = []

        def write(self, value: object) -> None:
            self.lines.append(str(value))

        def caption(self, value: object) -> None:
            self.lines.append(str(value))

    st = FakeStreamlit()

    assert payload["state"] == "current"
    assert payload["suite_snapshot_hash"] == suite_snapshot["suite_snapshot_hash"]
    assert render_baseline_center_summary(st, surface=surface) is True
    assert any("Baseline suite handoff" in line and "HO-005 / current" in line for line in st.lines)
    assert any(str(suite_snapshot["suite_snapshot_hash"])[:12] in line for line in st.lines)


def test_historical_baseline_mismatch_requires_explicit_adopt_without_rebinding() -> None:
    active = build_active_baseline_contract(
        suite_snapshot=_suite_snapshot(inputs_hash="inputs-hash-1"),
        baseline_payload={"param_a": 1.0},
        baseline_meta={"problem_hash": "ph-active"},
        policy_mode="review_adopt",
        created_at_utc="2026-04-17T00:08:00Z",
    )
    historical = build_active_baseline_contract(
        suite_snapshot=_suite_snapshot(inputs_hash="inputs-hash-2"),
        baseline_payload={"param_a": 2.0},
        baseline_meta={"problem_hash": "ph-historical"},
        policy_mode="restore_only",
        created_at_utc="2026-04-17T00:09:00Z",
    )

    compare = compare_active_and_historical_baseline(active, historical)
    policy = baseline_review_adopt_restore_policy(
        historical,
        active_contract=active,
        current_suite_snapshot_hash=str(historical["suite_snapshot_hash"]),
        current_inputs_snapshot_hash=str(historical["inputs_snapshot_hash"]),
        action="adopt",
        explicit=False,
    )
    explicit = baseline_review_adopt_restore_policy(
        historical,
        active_contract=active,
        current_suite_snapshot_hash=str(historical["suite_snapshot_hash"]),
        current_inputs_snapshot_hash=str(historical["inputs_snapshot_hash"]),
        action="adopt",
        explicit=True,
    )

    assert compare["state"] == "historical_mismatch"
    assert "suite_snapshot_hash" in compare["mismatch_fields"]
    assert "inputs_snapshot_hash" in compare["mismatch_fields"]
    assert "policy_mode" in compare["mismatch_fields"]
    assert compare["required_action"] == "review_and_adopt_explicitly"
    assert compare["silent_rebinding_allowed"] is False
    assert policy["requires_explicit_action"] is True
    assert policy["can_apply"] is False
    assert policy["silent_rebinding_allowed"] is False
    assert explicit["can_apply"] is True


def test_baseline_center_surface_shows_active_history_actions_and_mismatch(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    suite_snapshot = _suite_snapshot()
    suite_path = baseline_suite_handoff_snapshot_path(workspace_dir=workspace)
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite_path.write_text(json.dumps(suite_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    active = build_active_baseline_contract(
        suite_snapshot=suite_snapshot,
        baseline_payload={"param_a": 1.0},
        baseline_meta={"problem_hash": "ph-active"},
        source_run_dir=tmp_path / "runs" / "p_active",
        policy_mode="review_adopt",
        created_at_utc="2026-04-17T00:10:00Z",
    )
    historical = build_active_baseline_contract(
        suite_snapshot=_suite_snapshot(inputs_hash="inputs-hash-2"),
        baseline_payload={"param_a": 2.0},
        baseline_meta={"problem_hash": "ph-historical"},
        source_run_dir=tmp_path / "runs" / "p_historical",
        policy_mode="restore_only",
        created_at_utc="2026-04-17T00:11:00Z",
    )
    write_active_baseline_contract(active, workspace_dir=workspace)
    append_baseline_history_item(
        baseline_history_item_from_contract(active, action="adopt", actor="unit"),
        workspace_dir=workspace,
    )
    mismatch_item = baseline_history_item_from_contract(historical, action="restore", actor="unit")
    append_baseline_history_item(mismatch_item, workspace_dir=workspace)

    surface = build_baseline_center_surface(
        workspace_dir=workspace,
        selected_history_id=str(mismatch_item["history_id"]),
    )
    selected = dict(surface["selected_history"])
    actions = dict(surface["action_strip"])

    assert surface["workspace_id"] == "WS-BASELINE"
    assert surface["pipeline"] == ("HO-005", "active_baseline_contract", "HO-006")
    assert surface["active_baseline"]["active_baseline_hash"] == active["active_baseline_hash"]
    assert surface["active_baseline"]["suite_snapshot_hash"] == suite_snapshot["suite_snapshot_hash"]
    assert selected["compare_state"] == "historical_mismatch"
    assert "inputs_snapshot_hash" in selected["mismatch_fields"]
    assert actions["review"]["enabled"] is True
    assert actions["review"]["read_only"] is True
    assert actions["adopt"]["enabled"] is False
    assert actions["restore"]["enabled"] is False
    assert surface["silent_rebinding_allowed"] is False


def test_baseline_center_apply_requires_explicit_confirmation_and_records_history(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    suite_snapshot = _suite_snapshot()
    suite_path = baseline_suite_handoff_snapshot_path(workspace_dir=workspace)
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite_path.write_text(json.dumps(suite_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    active = build_active_baseline_contract(
        suite_snapshot=suite_snapshot,
        baseline_payload={"param_a": 1.0},
        baseline_meta={"problem_hash": "ph-active"},
        created_at_utc="2026-04-17T00:12:00Z",
    )
    candidate = build_active_baseline_contract(
        suite_snapshot=suite_snapshot,
        baseline_payload={"param_a": 2.0},
        baseline_meta={"problem_hash": "ph-active"},
        created_at_utc="2026-04-17T00:13:00Z",
    )
    write_active_baseline_contract(active, workspace_dir=workspace)
    history_item = baseline_history_item_from_contract(candidate, action="adopt", actor="unit")
    append_baseline_history_item(history_item, workspace_dir=workspace)

    blocked = apply_baseline_center_action(
        action="restore",
        history_id=str(history_item["history_id"]),
        workspace_dir=workspace,
        explicit_confirmation=False,
    )
    after_block = read_active_baseline_contract(workspace_dir=workspace)
    applied = apply_baseline_center_action(
        action="restore",
        history_id=str(history_item["history_id"]),
        workspace_dir=workspace,
        explicit_confirmation=True,
        actor="unit",
        note="confirmed restore",
    )
    after_apply = read_active_baseline_contract(workspace_dir=workspace)
    history = read_baseline_history(workspace_dir=workspace)

    assert blocked["status"] == "blocked"
    assert blocked["wrote_active_contract"] is False
    assert after_block["active_baseline_hash"] == active["active_baseline_hash"]
    assert applied["status"] == "applied"
    assert applied["wrote_active_contract"] is True
    assert after_apply["active_baseline_hash"] == candidate["active_baseline_hash"]
    assert history[-1]["action"] == "restore"
    assert history[-1]["active_baseline_hash"] == candidate["active_baseline_hash"]


def test_baseline_center_evidence_payload_includes_banner_and_relevant_history(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    active = build_active_baseline_contract(
        suite_snapshot=_suite_snapshot(),
        baseline_payload={"param_a": 1.0},
        baseline_meta={"problem_hash": "ph-stale"},
        created_at_utc="2026-04-17T00:14:00Z",
    )
    historical = build_active_baseline_contract(
        suite_snapshot=_suite_snapshot(inputs_hash="inputs-hash-2"),
        baseline_payload={"param_a": 2.0},
        baseline_meta={"problem_hash": "ph-historical"},
        policy_mode="restore_only",
        created_at_utc="2026-04-17T00:15:00Z",
    )
    write_active_baseline_contract(active, workspace_dir=workspace)
    append_baseline_history_item(
        baseline_history_item_from_contract(historical, action="restore", actor="unit"),
        workspace_dir=workspace,
    )

    evidence = baseline_center_evidence_payload(workspace_dir=workspace)

    assert evidence["active_baseline"]["state"] == "current"
    assert evidence["active_baseline"]["active_baseline_hash"] == active["active_baseline_hash"]
    assert evidence["mismatch_state"]["state"] == "historical_mismatch"
    assert evidence["send_bundle_should_include"] is True
    assert evidence["history_excerpt"][0]["active_baseline_hash"] == historical["active_baseline_hash"]
    assert evidence["silent_rebinding_allowed"] is False
