from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.desktop_run_setup_runtime import (
    read_validated_suite_snapshot,
    validated_suite_snapshot_handoff_path,
    write_validated_suite_snapshot,
)
from pneumo_solver_ui.desktop_suite_runtime import (
    DESKTOP_SUITE_OVERRIDES_SCHEMA_VERSION,
    build_desktop_suite_snapshot_context,
    build_run_setup_suite_overrides,
    desktop_suite_handoff_path,
    desktop_suite_overrides_path,
    format_desktop_suite_status_lines,
    read_desktop_suite_handoff_state,
    read_inputs_snapshot_context,
    reset_desktop_suite_overrides,
    save_desktop_suite_overrides,
    write_desktop_suite_handoff_snapshot,
)
from pneumo_solver_ui.desktop_input_model import (
    desktop_input_payload_hash,
    desktop_inputs_snapshot_handoff_path,
    load_base_defaults,
    save_desktop_inputs_snapshot,
)
from pneumo_solver_ui.desktop_ring_editor_model import resolve_ring_inputs_handoff
from pneumo_solver_ui.desktop_shell.command_search import (
    build_shell_command_search_entries,
    rank_shell_command_search_entries,
)
from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs
from pneumo_solver_ui.desktop_spec_shell.registry import build_command_map, build_shell_workspaces
from pneumo_solver_ui.desktop_spec_shell.search import build_search_entries, search_command_palette
from pneumo_solver_ui.desktop_suite_snapshot import (
    VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION,
    WS_SUITE_HANDOFF_ID,
    build_suite_matrix_preview,
    build_validated_suite_snapshot,
    describe_suite_snapshot_state,
    load_suite_rows,
    resolve_suite_inputs_handoff,
    suite_rows_hash,
    validate_suite_rows,
)
from pneumo_solver_ui.optimization_baseline_source import resolve_baseline_suite_handoff


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def _write_ring_refs(tmp_path: Path) -> dict[str, str]:
    road_csv = tmp_path / "ring_road.csv"
    axay_csv = tmp_path / "ring_axay.csv"
    scenario_json = tmp_path / "ring_scenario.json"
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n1,0.01,0.01,0.0,0.0\n", encoding="utf-8")
    axay_csv.write_text("t,ax,ay\n0,0,0\n1,0.1,0.2\n", encoding="utf-8")
    scenario_json.write_text('{"schema_version": "ring_v2", "segments": []}', encoding="utf-8")
    return {
        "road_csv": str(road_csv),
        "axay_csv": str(axay_csv),
        "scenario_json": str(scenario_json),
    }


def _add_ring_lineage(refs: dict[str, str], *, ring_hash: str = "ring-hash-1") -> None:
    Path(refs["scenario_json"]).write_text(
        json.dumps(
            {
                "schema_version": "ring_v2",
                "segments": [],
                "_lineage": {
                    "handoff_id": "HO-004",
                    "ring_source_hash_sha256": ring_hash,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _valid_suite_row(refs: dict[str, str]) -> dict[str, object]:
    return {
        "id": "suite-row-1",
        "имя": "ring_auto_full",
        "тип": "maneuver_csv",
        "включен": True,
        "стадия": 2,
        "dt": 0.01,
        "t_end": 1.0,
        "vx0_м_с": 5.0,
        **refs,
    }


def _write_inputs_snapshot_for_workspace(tmp_path: Path) -> tuple[dict[str, object], Path]:
    workspace = tmp_path / "workspace"
    payload = load_base_defaults()
    payload["масса_рамы"] = 640.0
    payload["макс_шаг_интегрирования_с"] = 0.002
    target = desktop_inputs_snapshot_handoff_path(workspace_dir=workspace)
    saved = save_desktop_inputs_snapshot(payload, target_path=target)
    return payload, saved


def test_validated_suite_snapshot_hash_and_ho005_contract_are_stable(tmp_path: Path) -> None:
    refs = _write_ring_refs(tmp_path)
    suite_rows = [_valid_suite_row(refs)]
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite_rows, ensure_ascii=False), encoding="utf-8")

    snapshot = build_validated_suite_snapshot(
        suite_rows,
        suite_source_path=suite_path,
        inputs_snapshot_ref=tmp_path / "inputs_snapshot.json",
        inputs_snapshot_hash="inputs-hash-1",
        ring_source_ref=refs,
        ring_source_hash="ring-hash-1",
        created_at_utc="2026-04-17T00:00:00Z",
        context_label="unit-test",
    )
    snapshot_again = build_validated_suite_snapshot(
        suite_rows,
        suite_source_path=suite_path,
        inputs_snapshot_ref=tmp_path / "inputs_snapshot.json",
        inputs_snapshot_hash="inputs-hash-1",
        ring_source_ref=refs,
        ring_source_hash="ring-hash-1",
        created_at_utc="2026-04-17T00:01:00Z",
        context_label="unit-test",
    )

    assert snapshot["schema_version"] == VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION
    assert snapshot["handoff_id"] == WS_SUITE_HANDOFF_ID
    assert snapshot["target_workspace"] == "WS-BASELINE"
    assert snapshot["validated"] is True
    assert snapshot["validation"]["ok"] is True
    assert snapshot["upstream_refs"]["inputs"]["handoff_id"] == "HO-003"
    assert snapshot["upstream_refs"]["ring"]["handoff_id"] == "HO-004"
    assert len(str(snapshot["suite_snapshot_hash"])) == 64
    assert snapshot["suite_snapshot_hash"] == snapshot_again["suite_snapshot_hash"]


def test_suite_resolves_inputs_handoff_and_records_frozen_ref_hash(tmp_path: Path) -> None:
    inputs_payload, inputs_path = _write_inputs_snapshot_for_workspace(tmp_path)
    inputs_hash = desktop_input_payload_hash(inputs_payload)
    refs = _write_ring_refs(tmp_path)
    rows = [_valid_suite_row(refs)]

    inputs_handoff = resolve_suite_inputs_handoff(
        workspace_dir=tmp_path / "workspace",
        current_inputs_snapshot_hash=inputs_hash,
    )
    snapshot = build_validated_suite_snapshot(
        rows,
        inputs_snapshot_ref=inputs_handoff["snapshot_path"],
        inputs_snapshot_hash=inputs_handoff["payload_hash"],
        ring_source_ref=refs,
        ring_source_hash="ring-hash-1",
    )
    upstream_inputs = snapshot["upstream_refs"]["inputs"]

    assert inputs_handoff["state"] == "current"
    assert inputs_handoff["handoff_id"] == "HO-003"
    assert inputs_handoff["can_consume"] is True
    assert inputs_handoff["snapshot_path"] == str(inputs_path)
    assert "inputs" not in inputs_handoff
    assert upstream_inputs["handoff_id"] == "HO-003"
    assert upstream_inputs["snapshot_ref"] == str(inputs_path)
    assert upstream_inputs["snapshot_hash"] == inputs_hash
    assert snapshot["validated"] is True


def test_suite_runtime_status_lines_surface_ho003_inputs_handoff(tmp_path: Path) -> None:
    inputs_payload, inputs_path = _write_inputs_snapshot_for_workspace(tmp_path)
    context = read_inputs_snapshot_context(workspace_dir=tmp_path / "workspace")
    status_lines = format_desktop_suite_status_lines(
        {
            "snapshot": {
                "suite_snapshot_hash": "suite-hash",
                "preview": {"row_count": 0, "enabled_count": 0},
                "validation": {"blocking_missing_ref_count": 0, "upstream_ref_error_count": 0},
            },
            "inputs_context": context,
            "existing_state": {"state": "missing", "banner": "missing suite"},
            "state": {},
            "handoff_path": str(tmp_path / "workspace" / "handoffs" / "WS-SUITE" / "validated_suite_snapshot.json"),
        }
    )

    assert context["state"] == "current"
    assert context["path"] == str(inputs_path)
    assert context["payload_hash"] == desktop_input_payload_hash(inputs_payload)
    assert context["can_consume"] is True
    assert status_lines[0].startswith("Снимок исходных данных:")
    assert "доступен=да" in status_lines[0]


def test_desktop_suite_runtime_facade_writes_validated_ho005_with_upstream_hashes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    inputs_payload, inputs_path = _write_inputs_snapshot_for_workspace(tmp_path)
    inputs_hash = desktop_input_payload_hash(inputs_payload)
    refs = _write_ring_refs(tmp_path)
    _add_ring_lineage(refs, ring_hash="ring-hash-1")
    rows = [_valid_suite_row(refs)]
    overrides = build_run_setup_suite_overrides(
        runtime_policy="force",
        cache_policy="reuse",
        export_csv=True,
        export_npz=False,
        record_full=False,
    )

    context = write_desktop_suite_handoff_snapshot(
        rows,
        workspace_dir=workspace,
        overrides=overrides,
        context_label="unit-runtime",
    )
    snapshot = dict(context["snapshot"])
    state = read_desktop_suite_handoff_state(
        workspace_dir=workspace,
        current_inputs_snapshot_hash=inputs_hash,
        current_ring_source_hash="ring-hash-1",
        current_suite_snapshot_hash=str(snapshot["suite_snapshot_hash"]),
    )
    lines = format_desktop_suite_status_lines(context)

    assert Path(str(context["written_path"])) == desktop_suite_handoff_path(workspace_dir=workspace)
    assert snapshot["upstream_refs"]["inputs"]["snapshot_ref"] == str(inputs_path)
    assert snapshot["upstream_refs"]["inputs"]["snapshot_hash"] == inputs_hash
    assert snapshot["upstream_refs"]["ring"]["source_hash"] == "ring-hash-1"
    assert snapshot["suite_rows"][0]["runtime_policy"] == "force"
    assert snapshot["suite_rows"][0]["cache_policy"] == "reuse"
    assert snapshot["suite_rows"][0]["export_csv"] is True
    assert snapshot["suite_rows"][0]["export_npz"] is False
    assert snapshot["validation"]["upstream_ref_error_count"] == 0
    assert snapshot["validated"] is True
    assert state["state"] == "current"
    assert state["handoff_ready"] is True
    assert any("Снимок набора" in line for line in lines)
    assert any("контроль набора" in line for line in lines)


def test_desktop_suite_runtime_blocks_missing_inputs_snapshot_as_upstream_ref(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    rows = [
        {
            "id": "worldroad-row",
            "имя": "worldroad_smoke",
            "тип": "worldroad",
            "включен": True,
            "стадия": 1,
            "dt": 0.01,
            "t_end": 1.0,
        }
    ]

    context = build_desktop_suite_snapshot_context(rows, workspace_dir=workspace)
    snapshot = dict(context["snapshot"])
    validation = dict(snapshot["validation"])
    state = dict(context["state"])

    assert snapshot["validated"] is False
    assert validation["upstream_ref_error_count"] == 1
    assert validation["upstream_ref_errors"][0]["source_workspace"] == "WS-INPUTS"
    assert state["state"] == "invalid"
    assert "missing_upstream_handoff_refs" in state["stale_reasons"]


def test_desktop_suite_overrides_roundtrip_and_reset(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = desktop_suite_overrides_path(workspace_dir=workspace)

    saved = save_desktop_suite_overrides(
        {
            "global": {"dt": 0.02},
            "by_name": {"case_a": {"enabled": False}},
        },
        workspace_dir=workspace,
    )
    payload = json.loads(saved.read_text(encoding="utf-8"))
    reset = reset_desktop_suite_overrides(workspace_dir=workspace)
    reset_payload = json.loads(reset.read_text(encoding="utf-8"))

    assert saved == target
    assert payload["schema_version"] == DESKTOP_SUITE_OVERRIDES_SCHEMA_VERSION
    assert payload["global"]["dt"] == 0.02
    assert payload["by_name"]["case_a"]["enabled"] is False
    assert reset == target
    assert reset_payload["global"] == {}
    assert reset_payload["by_name"] == {}


def test_suite_inputs_handoff_reports_missing_and_stale_without_live_editor_state(tmp_path: Path) -> None:
    missing = resolve_suite_inputs_handoff(workspace_dir=tmp_path / "workspace")
    inputs_payload, _inputs_path = _write_inputs_snapshot_for_workspace(tmp_path)
    stale = resolve_suite_inputs_handoff(
        workspace_dir=tmp_path / "workspace",
        current_inputs_snapshot_hash=desktop_input_payload_hash(dict(inputs_payload, база=9.99)),
    )

    assert missing["state"] == "missing"
    assert missing["can_consume"] is False
    assert "не должен подставлять исходные данные самостоятельно" in missing["banner"]
    assert stale["state"] == "stale"
    assert stale["can_consume"] is False
    assert "inputs_snapshot_hash_changed" in stale["stale_reasons"]


def test_full_handoff_chain_preserves_refs_and_hashes_without_solver_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    inputs_payload, inputs_path = _write_inputs_snapshot_for_workspace(tmp_path)
    inputs_hash = desktop_input_payload_hash(inputs_payload)
    ring_inputs = resolve_ring_inputs_handoff(
        workspace_dir=workspace,
        current_inputs_snapshot_hash=inputs_hash,
    )

    refs = _write_ring_refs(tmp_path)
    ring_hash = "ring-source-hash-chain"
    rows = [
        {
            **_valid_suite_row(refs),
            "handoff_id": "HO-004",
            "source_workspace": "WS-RING",
            "ring_source_hash_sha256": ring_hash,
        }
    ]
    suite_path = tmp_path / "chain_suite.json"
    suite_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    suite_context = write_desktop_suite_handoff_snapshot(
        rows,
        suite_source_path=suite_path,
        workspace_dir=workspace,
        context_label="chain-evidence",
        require_inputs_snapshot=True,
        require_ring_hash_for_ring_refs=True,
    )
    snapshot = dict(suite_context["snapshot"])
    upstream_inputs = dict(snapshot["upstream_refs"]["inputs"])
    upstream_ring = dict(snapshot["upstream_refs"]["ring"])
    baseline = resolve_baseline_suite_handoff(
        workspace_dir=workspace,
        current_suite_snapshot_hash=str(snapshot["suite_snapshot_hash"]),
    )

    assert ring_inputs["state"] == "current"
    assert ring_inputs["handoff_id"] == "HO-002"
    assert ring_inputs["payload_hash"] == inputs_hash
    assert "inputs" not in ring_inputs
    assert suite_context["inputs_context"]["state"] == "current"
    assert suite_context["ring_context"]["state"] == "current"
    assert suite_context["state"]["state"] == "current"
    assert snapshot["validated"] is True
    assert upstream_inputs["handoff_id"] == "HO-003"
    assert upstream_inputs["snapshot_ref"] == str(inputs_path)
    assert upstream_inputs["snapshot_hash"] == inputs_hash
    assert upstream_ring["handoff_id"] == "HO-004"
    assert upstream_ring["source_hash"] == ring_hash
    assert baseline["state"] == "current"
    assert baseline["baseline_can_consume"] is True
    assert baseline["suite_snapshot_hash"] == snapshot["suite_snapshot_hash"]
    assert baseline["inputs_snapshot_hash"] == inputs_hash
    assert baseline["ring_source_hash"] == ring_hash


def test_suite_validation_reports_missing_refs_without_owning_ring_geometry(tmp_path: Path) -> None:
    rows = [
        {
            "имя": "enabled_missing_ring_refs",
            "тип": "maneuver_csv",
            "включен": True,
            "road_csv": str(tmp_path / "missing_road.csv"),
            "axay_csv": str(tmp_path / "missing_axay.csv"),
            "scenario_json": str(tmp_path / "missing_scenario.json"),
        },
        {
            "имя": "disabled_missing_ring_refs",
            "тип": "maneuver_csv",
            "включен": False,
            "road_csv": str(tmp_path / "disabled_missing_road.csv"),
            "axay_csv": str(tmp_path / "disabled_missing_axay.csv"),
            "scenario_json": str(tmp_path / "disabled_missing_scenario.json"),
        },
    ]

    validation = validate_suite_rows(rows)

    assert validation["ok"] is False
    assert validation["blocking_missing_ref_count"] == 3
    assert validation["missing_ref_count"] == 6
    assert any(item["severity"] == "warning" for item in validation["missing_refs"])
    assert validation["ownership_violation_count"] == 0


def test_suite_runtime_overrides_reject_ring_refs_and_geometry_source_data(tmp_path: Path) -> None:
    refs = _write_ring_refs(tmp_path)
    rows = [_valid_suite_row(refs)]
    snapshot = build_validated_suite_snapshot(
        rows,
        inputs_snapshot_hash="inputs-hash-1",
        ring_source_ref=refs,
        ring_source_hash="ring-hash-1",
        overrides={
            "global": {"dt": 0.02},
            "by_name": {
                "ring_auto_full": {
                    "road_csv": str(tmp_path / "replacement.csv"),
                    "segments": [{"name": "not-owned-here"}],
                }
            },
        },
    )

    row = snapshot["suite_rows"][0]
    assert row["dt"] == 0.02
    assert row["road_csv"] == refs["road_csv"]
    assert "segments" not in row
    assert snapshot["validated"] is False
    assert snapshot["validation"]["override_rejection_count"] == 2


def test_suite_matrix_preview_counts_stages_types_and_refs(tmp_path: Path) -> None:
    refs = _write_ring_refs(tmp_path)
    rows = [
        _valid_suite_row(refs),
        {
            "имя": "inertia_roll",
            "тип": "инерция_крен",
            "включен": True,
            "стадия": 0,
            "dt": 0.003,
            "t_end": 1.2,
        },
    ]
    validation = validate_suite_rows(rows)
    preview = build_suite_matrix_preview(rows, validation=validation)

    assert preview["enabled_count"] == 2
    assert preview["stage_counts"] == {"0": 1, "2": 1}
    assert preview["type_counts"]["maneuver_csv"] == 1
    assert preview["type_counts"]["инерция_крен"] == 1
    assert preview["ref_row_count"] == 1
    assert "строк=2" in preview["summary_text"]


def test_stale_suite_banner_detects_inputs_ring_and_suite_hash_drift(tmp_path: Path) -> None:
    refs = _write_ring_refs(tmp_path)
    rows = [_valid_suite_row(refs)]
    snapshot = build_validated_suite_snapshot(
        rows,
        inputs_snapshot_hash="inputs-hash-1",
        ring_source_ref=refs,
        ring_source_hash="ring-hash-1",
    )

    current = describe_suite_snapshot_state(
        snapshot,
        current_inputs_snapshot_hash="inputs-hash-1",
        current_ring_source_hash="ring-hash-1",
        current_suite_snapshot_hash=str(snapshot["suite_snapshot_hash"]),
    )
    stale_inputs = describe_suite_snapshot_state(snapshot, current_inputs_snapshot_hash="inputs-hash-2")
    stale_ring = describe_suite_snapshot_state(snapshot, current_ring_source_hash="ring-hash-2")
    stale_suite = describe_suite_snapshot_state(snapshot, current_suite_snapshot_hash="other-suite-hash")

    assert current["state"] == "current"
    assert "Снимок набора испытаний актуален" in current["banner"]
    assert stale_inputs["state"] == "stale"
    assert "inputs_snapshot_hash_changed" in stale_inputs["stale_reasons"]
    assert stale_ring["state"] == "stale"
    assert "ring_source_hash_changed" in stale_ring["stale_reasons"]
    assert stale_suite["state"] == "stale"
    assert "suite_snapshot_hash_changed" in stale_suite["stale_reasons"]


def test_default_suite_rows_are_loadable_but_not_baseline_ready_when_all_disabled() -> None:
    rows = load_suite_rows(UI_ROOT / "default_suite.json")
    validation = validate_suite_rows(
        rows,
        suite_source_path=UI_ROOT / "default_suite.json",
        repo_root=ROOT,
    )

    assert rows
    assert validation["row_count"] == len(rows)
    assert validation["enabled_count"] == 0
    assert validation["handoff_ready"] is False
    assert "suite_has_no_enabled_rows" in validation["warnings"]


def test_baseline_consumes_ho005_validated_suite_snapshot_without_rebinding(tmp_path: Path) -> None:
    refs = _write_ring_refs(tmp_path)
    rows = [_valid_suite_row(refs)]
    snapshot = build_validated_suite_snapshot(
        rows,
        inputs_snapshot_hash="inputs-hash-1",
        ring_source_ref=refs,
        ring_source_hash="ring-hash-1",
    )
    target = write_validated_suite_snapshot(snapshot, workspace_dir=tmp_path / "workspace")

    loaded = read_validated_suite_snapshot(target)
    resolved = resolve_baseline_suite_handoff(
        workspace_dir=tmp_path / "workspace",
        current_suite_snapshot_hash=str(snapshot["suite_snapshot_hash"]),
    )
    stale = resolve_baseline_suite_handoff(
        workspace_dir=tmp_path / "workspace",
        current_suite_snapshot_hash="old-suite-hash",
    )

    assert target == validated_suite_snapshot_handoff_path(workspace_dir=tmp_path / "workspace")
    assert loaded["suite_snapshot_hash"] == snapshot["suite_snapshot_hash"]
    assert resolved["handoff_id"] == "HO-005"
    assert resolved["state"] == "current"
    assert resolved["baseline_can_consume"] is True
    assert resolved["suite_snapshot_hash"] == snapshot["suite_snapshot_hash"]
    assert stale["state"] == "stale"


def test_command_search_discovers_validated_suite_and_ho005_routes() -> None:
    entries = build_shell_command_search_entries(build_desktop_shell_specs())
    hits = rank_shell_command_search_entries("снимок набора испытаний", entries)
    freeze_hits = rank_shell_command_search_entries("зафиксировать набор", entries)

    assert hits
    assert hits[0].action_value == "test_center"
    assert "снимок набора" in " ".join(hits[0].keywords)
    assert freeze_hits
    assert freeze_hits[0].action_value == "test_center"

    spec_entries = build_search_entries(build_shell_workspaces(), tuple(build_command_map().values()))
    spec_hits = search_command_palette(spec_entries, "снимок набора")
    spec_freeze_hits = search_command_palette(spec_entries, "зафиксировать набор")
    assert spec_hits
    assert spec_hits[0].workspace_id == "test_matrix"
    assert spec_freeze_hits
    assert spec_freeze_hits[0].workspace_id == "test_matrix"


def test_suite_rows_hash_changes_when_enabled_matrix_changes(tmp_path: Path) -> None:
    refs = _write_ring_refs(tmp_path)
    rows = [_valid_suite_row(refs)]
    changed = [dict(rows[0], включен=False)]

    assert suite_rows_hash(rows) != suite_rows_hash(changed)
