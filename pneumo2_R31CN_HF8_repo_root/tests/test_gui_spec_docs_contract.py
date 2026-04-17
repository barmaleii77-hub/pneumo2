from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from pneumo_solver_ui.release_gate import (
    load_v32_gap_to_evidence_action_map,
    load_v32_release_gate_hardening_matrix,
    release_gate_reference_metadata,
    v32_release_gate_reference_metadata,
    v32_release_gate_reference_paths,
    v33_release_gate_reference_metadata,
    v33_release_gate_reference_paths,
)
from pneumo_solver_ui.workspace_contract import (
    v32_handoff_ids,
    v32_workspace_ids,
    v32_workspace_reference_paths,
)


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CONTEXT = DOCS / "context"
IMPORTS = CONTEXT / "gui_spec_imports"
FOUNDATIONS = IMPORTS / "foundations"
IMPORTS_V3 = IMPORTS / "v3"
IMPORTS_V12 = IMPORTS / "v12_design_recovery"
IMPORTS_V13 = IMPORTS / "v13_ring_editor_migration"
IMPORTS_V32 = IMPORTS / "v32_connector_reconciled"
IMPORTS_V33 = IMPORTS / "v33_connector_reconciled"
V32_COMPLETENESS = IMPORTS_V32 / "COMPLETENESS_ASSESSMENT.md"
V32_WORKSTREAMS = IMPORTS_V32 / "PARALLEL_CHAT_WORKSTREAMS.md"
V33_COMPLETENESS = IMPORTS_V33 / "COMPLETENESS_ASSESSMENT.md"
V32_RELEASE_ACCEPTANCE_MAP = IMPORTS_V32 / "RELEASE_GATE_ACCEPTANCE_MAP.md"
V32_GATE_HARDENING = IMPORTS_V32 / "RELEASE_GATE_HARDENING_MATRIX.csv"
V32_GAP_MAP = IMPORTS_V32 / "GAP_TO_EVIDENCE_ACTION_MAP.csv"
V32_INPUTS_HANDOFF_EVIDENCE = IMPORTS_V32 / "WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md"
V32_PRODUCER_ANIMATOR_TRUTH_NOTE = IMPORTS_V32 / "PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md"
V32_COMPARE_OBJECTIVE_INTEGRITY_NOTE = IMPORTS_V32 / "COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md"
V32_GEOMETRY_REFERENCE_EVIDENCE_NOTE = IMPORTS_V32 / "GEOMETRY_REFERENCE_EVIDENCE_NOTE.md"
V32_MNEMO_TRUTH_GRAPHICS_NOTE = IMPORTS_V32 / "MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md"
V32_DIAGNOSTICS_EVIDENCE_NOTE = IMPORTS_V32 / "DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md"
V32_RUNTIME_EVIDENCE_NOTE = IMPORTS_V32 / "RUNTIME_RELEASE_EVIDENCE_NOTE.md"
RELEASE_TRIAGE = CONTEXT / "release_readiness" / "WORKTREE_TRIAGE_2026-04-17.md"
V32_16_ACCEPTANCE_NOTE = CONTEXT / "release_readiness" / "V32_16_ACCEPTANCE_NOTE_2026-04-17.md"

CANON_17 = DOCS / "17_WINDOWS_DESKTOP_CAD_GUI_CANON.md"
CANON_18 = DOCS / "18_PNEUMOAPP_WINDOWS_GUI_SPEC.md"
PROJECT_SOURCES = DOCS / "PROJECT_SOURCES.md"
PROJECT_KNOWLEDGE_BASE = DOCS / "00_PROJECT_KNOWLEDGE_BASE.md"
GUI_INDEX = DOCS / "gui_chat_prompts" / "00_INDEX.md"
ANIMATOR_LANE = DOCS / "gui_chat_prompts" / "07_DESKTOP_ANIMATOR.md"
OPTIMIZER_LANE = DOCS / "gui_chat_prompts" / "08_OPTIMIZER_CENTER.md"
RING_LANE = DOCS / "gui_chat_prompts" / "04_RING_EDITOR.md"
RESULTS_LANE = DOCS / "gui_chat_prompts" / "10_TEST_VALIDATION_RESULTS.md"
RELEASE_LANE = DOCS / "gui_chat_prompts" / "13_RELEASE_GATES_KB_ACCEPTANCE.md"
LINEAGE_MD = CONTEXT / "GUI_SPEC_ARCHIVE_LINEAGE.md"
LINEAGE_JSON = CONTEXT / "gui_spec_archive_lineage.json"
PARITY_SUMMARY = CONTEXT / "DESKTOP_WEB_PARITY_SUMMARY.md"
PARITY_JSON = CONTEXT / "desktop_web_parity_map.json"
IMPORTS_README = IMPORTS / "README.md"

STRONG_MOJIBAKE_MARKERS = (
    "Р В Р’В Р вЂ™Р’В Р В Р Р‹Р РЋРЎСџР В Р’В Р вЂ™Р’В ",
    "Р В Р’В Р вЂ™Р’В Р В Р Р‹Р Р†Р вЂљРІвЂћСћР В Р’В Р вЂ™Р’В ",
    "Р В Р’В Р вЂ™Р’В Р В Р’В Р В РІР‚в„–Р В Р’В Р вЂ™Р’В ",
    "Р В Р’В Р вЂ™Р’В Р В Р Р‹Р РЋРІвЂћСћР В Р’В Р вЂ™Р’В ",
    "Р В Р’В Р В РІР‚В Р В Р’В Р Р†Р вЂљРЎв„ў",
    "Р В Р’В Р В РІР‚В Р В Р вЂ Р В РІР‚С™Р вЂ™Р’В ",
)


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _normalized_text_size(path: Path) -> int:
    return len(path.read_bytes().replace(b"\r\n", b"\n"))


def _parse_markdown_table(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    headers: list[str] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells == ["path", "status", "owner_lane", "gate_or_gap", "evidence_required", "tests", "decision"]:
            headers = cells
            continue
        if headers is None:
            continue
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def _dirty_repo_paths_from_git_status() -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT.parent), "status", "--short"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    repo_prefix = f"{ROOT.name}/"
    dirty_paths: set[str] = set()
    for raw_line in result.stdout.splitlines():
        if not raw_line:
            continue
        raw_path = raw_line[3:].strip()
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1].strip()
        if not raw_path.startswith(repo_prefix):
            continue
        rel_path = raw_path.removeprefix(repo_prefix)
        absolute_path = ROOT / rel_path
        if rel_path.endswith("/"):
            for child in absolute_path.rglob("*"):
                if child.is_file():
                    dirty_paths.add(child.relative_to(ROOT).as_posix())
        else:
            dirty_paths.add(rel_path.replace("\\", "/").strip('"'))
    return dirty_paths


def test_v13_import_layer_exists_and_matches_manifest() -> None:
    manifest_path = IMPORTS_V13 / "manifest.json"
    readme_path = IMPORTS_V13 / "README.md"

    assert IMPORTS_V13.exists()
    assert manifest_path.exists()
    assert readme_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    readme_text = readme_path.read_text(encoding="utf-8-sig")

    assert manifest["artifact_id"] == "PNEUMO-GUI-CODEX-V13-RING-EDITOR-MIGRATION"
    assert manifest["file_count"] == len(manifest["files"])
    assert "редактор кольца и миграция web → desktop" in readme_text.lower()

    manifest_names = {str(item["name"]) for item in manifest["files"]}
    actual_names = {path.name for path in IMPORTS_V13.iterdir() if path.is_file()}

    assert actual_names == manifest_names | {"manifest.json"}

    for item in manifest["files"]:
        file_path = IMPORTS_V13 / str(item["name"])
        assert file_path.exists(), file_path.name
        assert _normalized_text_size(file_path) == item["size_bytes"], file_path.name

    assert manifest["counts"] == {
        "screen_blueprints": 4,
        "elements": 62,
        "fields": 44,
        "migration_rows": 18,
        "user_steps": 14,
        "acceptance_gates": 17,
    }

    assert len(_load_csv_rows(IMPORTS_V13 / "ring_editor_screen_blueprints_v13.csv")) == 4
    assert len(_load_csv_rows(IMPORTS_V13 / "ring_editor_element_catalog_v13.csv")) == 62
    assert len(_load_csv_rows(IMPORTS_V13 / "ring_editor_field_catalog_v13.csv")) == 44
    assert len(_load_csv_rows(IMPORTS_V13 / "web_to_desktop_migration_matrix_v13.csv")) == 18
    assert len(_load_csv_rows(IMPORTS_V13 / "ring_editor_user_steps_v13.csv")) == 14
    assert len(_load_csv_rows(IMPORTS_V13 / "ring_editor_acceptance_gates_v13.csv")) == 17


def test_v13_spec_and_contract_files_load_with_expected_ring_guarantees() -> None:
    spec = json.loads(
        (IMPORTS_V13 / "pneumo_gui_codex_spec_v13_ring_editor_migration.json").read_text(
            encoding="utf-8-sig"
        )
    )
    schema = json.loads(
        (IMPORTS_V13 / "ring_editor_schema_contract_v13.json").read_text(encoding="utf-8-sig")
    )
    suite_link = json.loads(
        (IMPORTS_V13 / "ring_to_suite_link_contract_v13.json").read_text(encoding="utf-8-sig")
    )

    assert spec["version"] == "v13"
    assert spec["workspace"]["workspace_id"] == "WS-RING"
    assert spec["schema_contract_ref"] == "ring_editor_schema_contract_v13.json"
    assert spec["suite_link_contract_ref"] == "ring_to_suite_link_contract_v13.json"
    assert "Редактор кольца является единственным пользовательским источником дорожных сценариев." in spec["canonical_decisions"]
    assert spec["next_step_after_v13"].startswith("V14:")

    region_ids = {region["region_id"] for region in spec["workspace"]["regions"]}
    assert region_ids == {"RG-HEADER", "RG-LEFT", "RG-PLAN", "RG-LONG", "RG-CROSSFALL", "RG-FOOTER"}
    assert spec["workspace"]["global_right_inspector_dependency"]["region_id"] == "GLOBAL-RIGHT-INSPECTOR"

    assert schema["single_source_of_truth"] == "ring_editor_workspace"
    assert schema["root_object"] == "ring_scenario"
    assert schema["root_fields"]["segments"]["required"] is True
    assert schema["forbidden"]["secondary_user_source_of_truth_outside_ring_editor"] is True

    assert suite_link["source_of_truth"] == "ring_editor_workspace"
    assert "scenario_json_path" in suite_link["copied_fields_to_test"]
    assert "road_csv_path" in suite_link["copied_fields_to_test"]
    assert "segment geometry" in suite_link["must_not_duplicate"]
    assert any("Из WS-SUITE можно открыть исходный сценарий обратно в WS-RING" == item for item in suite_link["acceptance"])


def test_v13_catalogs_keep_minimal_ring_editor_contract_shape() -> None:
    element_rows = _load_csv_rows(IMPORTS_V13 / "ring_editor_element_catalog_v13.csv")
    field_rows = _load_csv_rows(IMPORTS_V13 / "ring_editor_field_catalog_v13.csv")
    gate_rows = _load_csv_rows(IMPORTS_V13 / "ring_editor_acceptance_gates_v13.csv")
    migration_rows = _load_csv_rows(IMPORTS_V13 / "web_to_desktop_migration_matrix_v13.csv")

    assert set(element_rows[0].keys()) == {
        "element_id",
        "name",
        "type",
        "region_id",
        "x_local_px",
        "y_local_px",
        "width_px",
        "height_px",
        "source_binding",
        "visible_when",
        "enabled_when",
        "tooltip_required",
        "help_required",
        "scroll_behavior",
    }
    assert any(row["element_id"] == "RG-FLD-CLOSURE-POLICY" for row in element_rows)
    assert all(row["tooltip_required"] == "Да" for row in element_rows[:5])
    assert all(row["help_required"] == "Да" for row in element_rows[:5])

    assert set(field_rows[0].keys()) == {
        "field_id",
        "name",
        "data_type",
        "scope",
        "required",
        "tooltip_required",
        "allowed_values",
        "unit",
        "description",
        "display_unit",
    }
    assert any(row["field_id"] == "RG-FLD-CLOSURE-POLICY" and row["allowed_values"] == "closed_c1_periodic|closed_exact|preview_open_only" for row in field_rows)
    assert any(row["field_id"] == "RG-FLD-V0" and row["unit"] == "км/ч" for row in field_rows)

    assert any(row["gate_id"] == "RG-GATE-001" and row["severity"] == "Блокирующий" for row in gate_rows)
    assert any(row["web_feature_id"] == "WEB-RING-003" and row["source_of_truth"] == "Канонический ring_scenario.segments[i]" for row in migration_rows)
    assert any(row["web_feature_id"] == "WEB-RING-005" and "шов кольца" in row["command_search_route"] for row in migration_rows)


def test_project_sources_index_and_import_notes_register_v13_addendum() -> None:
    imports_readme = IMPORTS_README.read_text(encoding="utf-8")
    project_sources_text = PROJECT_SOURCES.read_text(encoding="utf-8")
    index_text = GUI_INDEX.read_text(encoding="utf-8")

    assert "foundations/" in imports_readme
    assert "upstream prompt sources" in imports_readme
    assert "v12_design_recovery/" in imports_readme
    assert "v13_ring_editor_migration/" in imports_readme
    assert "v32_connector_reconciled/" in imports_readme
    assert "v33_connector_reconciled/" in imports_readme
    assert "connector-reconciled" in imports_readme
    assert "COMPLETENESS_ASSESSMENT.md" in imports_readme
    assert "PARALLEL_CHAT_WORKSTREAMS.md" in imports_readme
    assert "RELEASE_GATE_ACCEPTANCE_MAP.md" in imports_readme
    assert "RELEASE_GATE_HARDENING_MATRIX.csv" in imports_readme
    assert "GAP_TO_EVIDENCE_ACTION_MAP.csv" in imports_readme
    assert "PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md" in imports_readme
    assert "COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md" in imports_readme
    assert "GEOMETRY_REFERENCE_EVIDENCE_NOTE.md" in imports_readme
    assert "MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md" in imports_readme
    assert "DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md" in imports_readme
    assert "RUNTIME_RELEASE_EVIDENCE_NOTE.md" in imports_readme
    assert "специализированный ring-editor migration" in imports_readme
    assert "WS-RING -> WS-SUITE" in imports_readme
    assert "GUI_SPEC_ARCHIVE_LINEAGE.md" in imports_readme

    assert "gui_spec_imports/foundations/README.md" in project_sources_text
    assert "prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md" in project_sources_text
    assert "v12_design_recovery/README.md" in project_sources_text
    assert "optimization_control_plane_contract_v12.json" in project_sources_text
    assert "truthful_graphics_contract_v12.json" in project_sources_text
    assert "GUI_SPEC_ARCHIVE_LINEAGE.md" in project_sources_text
    assert "gui_spec_archive_lineage.json" in project_sources_text
    assert "v13_ring_editor_migration/README.md" in project_sources_text
    assert "ring_editor_schema_contract_v13.json" in project_sources_text
    assert "ring_editor_screen_blueprints_v13.csv" in project_sources_text
    assert "ring_editor_acceptance_gates_v13.csv" in project_sources_text
    assert "ring_to_suite_link_contract_v13.json" in project_sources_text
    assert "v32_connector_reconciled/README.md" in project_sources_text
    assert "v32_connector_reconciled/COMPLETENESS_ASSESSMENT.md" in project_sources_text
    assert "v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md" in project_sources_text
    assert "v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md" in project_sources_text
    assert "v32_connector_reconciled/RELEASE_GATE_HARDENING_MATRIX.csv" in project_sources_text
    assert "v32_connector_reconciled/GAP_TO_EVIDENCE_ACTION_MAP.csv" in project_sources_text
    assert "v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md" in project_sources_text
    assert "v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md" in project_sources_text
    assert "v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md" in project_sources_text
    assert "v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md" in project_sources_text
    assert "v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md" in project_sources_text
    assert "v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md" in project_sources_text
    assert "v33_connector_reconciled/README.md" in project_sources_text
    assert "v33_connector_reconciled/COMPLETENESS_ASSESSMENT.md" in project_sources_text
    assert "gui_chat_prompts/13_RELEASE_GATES_KB_ACCEPTANCE.md" in project_sources_text
    assert "context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md" in project_sources_text
    assert "context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md" in project_sources_text
    assert "pneumo_codex_tz_spec_connector_reconciled_v32.zip" in project_sources_text
    assert "pneumo_codex_tz_spec_connector_reconciled_v33.zip" in project_sources_text

    assert "gui_spec_imports/foundations/README.md" in index_text
    assert "prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md" in index_text
    assert "gui_spec_imports/v12_design_recovery/README.md" in index_text
    assert "GUI_SPEC_ARCHIVE_LINEAGE.md" in index_text
    assert "gui_spec_imports/v13_ring_editor_migration/README.md" in index_text
    assert "gui_spec_imports/v32_connector_reconciled/README.md" in index_text
    assert "gui_spec_imports/v33_connector_reconciled/README.md" in index_text
    assert "COMPLETENESS_ASSESSMENT.md" in index_text
    assert "PARALLEL_CHAT_WORKSTREAMS.md" in index_text
    assert "RELEASE_GATE_ACCEPTANCE_MAP.md" in index_text
    assert "RELEASE_GATE_HARDENING_MATRIX.csv" in index_text
    assert "GAP_TO_EVIDENCE_ACTION_MAP.csv" in index_text
    assert "PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md" in index_text
    assert "COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md" in index_text
    assert "GEOMETRY_REFERENCE_EVIDENCE_NOTE.md" in index_text
    assert "MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md" in index_text
    assert "DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md" in index_text
    assert "RUNTIME_RELEASE_EVIDENCE_NOTE.md" in index_text
    assert "WORKTREE_TRIAGE_2026-04-17.md" in index_text
    assert "V32_16_ACCEPTANCE_NOTE_2026-04-17.md" in index_text
    assert "13_RELEASE_GATES_KB_ACCEPTANCE.md" in index_text
    assert "специализированный addendum для `WS-RING`" in index_text
    assert "WS-RING -> WS-SUITE" in index_text


def test_canon_and_parity_summary_reference_v13_ring_editor_layer() -> None:
    canon_17 = CANON_17.read_text(encoding="utf-8")
    canon_18 = CANON_18.read_text(encoding="utf-8")
    parity_summary = PARITY_SUMMARY.read_text(encoding="utf-8")
    parity_json = PARITY_JSON.read_text(encoding="utf-8")

    assert "command search" in canon_17.lower()
    assert "## П. Специализированный addendum `v13` для `WS-RING`" in canon_18
    assert "## Р. Контракт handoff `WS-RING -> WS-SUITE`" in canon_18
    assert "## С. Ring-level migration gates" in canon_18
    assert "## Т. Историческая линия `PROMPT_V2 + v1…v13` и политика продолжения" in canon_18
    assert "./context/gui_spec_imports/foundations/README.md" in canon_18
    assert "./context/gui_spec_imports/foundations/prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md" in canon_18
    assert "./context/GUI_SPEC_ARCHIVE_LINEAGE.md" in canon_18
    assert "./context/gui_spec_archive_lineage.json" in canon_18
    assert "./context/gui_spec_imports/v12_design_recovery/README.md" in canon_18
    assert "./context/gui_spec_imports/v13_ring_editor_migration/pneumo_gui_codex_spec_v13_ring_editor_migration.json" in canon_18
    assert "./context/gui_spec_imports/v13_ring_editor_migration/ring_editor_schema_contract_v13.json" in canon_18
    assert "./context/gui_spec_imports/v13_ring_editor_migration/ring_to_suite_link_contract_v13.json" in canon_18
    assert "./context/gui_spec_imports/v13_ring_editor_migration/web_to_desktop_migration_matrix_v13.csv" in canon_18

    assert "Специализированное уточнение для `WS-RING`" in parity_summary
    assert "v13_ring_editor_migration" in parity_summary
    assert "ring_to_suite_link_contract_v13.json" in parity_summary
    assert "stale link" in parity_summary

    assert "further refined by v13 ring_editor migration artifacts" in parity_json
    assert "further refined by v13 ring_to_suite link contract" in parity_json


def test_v12_design_recovery_layer_and_lineage_inventory_are_registered() -> None:
    assert FOUNDATIONS.exists()
    assert IMPORTS_V12.exists()
    assert LINEAGE_MD.exists()
    assert LINEAGE_JSON.exists()

    foundations_readme = (FOUNDATIONS / "README.md").read_text(encoding="utf-8")
    prompt_text = (
        FOUNDATIONS / "prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md"
    ).read_text(encoding="utf-8")
    v12_readme = (IMPORTS_V12 / "README.md").read_text(encoding="utf-8-sig")
    lineage_md = LINEAGE_MD.read_text(encoding="utf-8")
    lineage_json = json.loads(LINEAGE_JSON.read_text(encoding="utf-8"))

    assert "Foundational GUI Prompt Sources" in foundations_readme
    assert "PROMPT_V2" in foundations_readme
    assert "Ты — ведущий архитектор пользовательского интерфейса" in prompt_text
    assert "Не предлагай веб‑интерфейс как основу." in prompt_text
    assert "Потеря существующей функциональности при миграции из веб‑версии" in prompt_text
    assert "Preservation and Design Recovery v12" in v12_readme
    assert (IMPORTS_V12 / "pneumo_gui_codex_spec_v12_design_recovery.json").exists()
    assert (IMPORTS_V12 / "ring_editor_canonical_contract_v12.json").exists()
    assert (IMPORTS_V12 / "optimization_control_plane_contract_v12.json").exists()
    assert (IMPORTS_V12 / "truthful_graphics_contract_v12.json").exists()

    assert "PROMPT_V2 + v1–v13" in lineage_md
    assert "PROMPT_V2" in lineage_md
    assert "v12" in lineage_md
    assert "v13" in lineage_md
    assert "implementation-oriented passes" in lineage_md
    assert "design-recovery" in lineage_md

    versions = [item["version"] for item in lineage_json]
    assert versions == ["PROMPT_V2", "v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13"]
    assert any(item["version"] == "PROMPT_V2" and item["repo_layer"] == "docs/context/gui_spec_imports/foundations/" for item in lineage_json)
    assert any(item["version"] == "v12" and item["repo_layer"] == "docs/context/gui_spec_imports/v12_design_recovery/" for item in lineage_json)
    assert any(item["version"] == "v13" and item["repo_layer"] == "docs/context/gui_spec_imports/v13_ring_editor_migration/" for item in lineage_json)


def test_v32_connector_reconciled_digest_is_registered() -> None:
    readme_path = IMPORTS_V32 / "README.md"
    assert readme_path.exists()
    assert V32_COMPLETENESS.exists()
    assert V32_WORKSTREAMS.exists()
    assert V32_RELEASE_ACCEPTANCE_MAP.exists()
    assert V32_GATE_HARDENING.exists()
    assert V32_GAP_MAP.exists()
    assert V32_INPUTS_HANDOFF_EVIDENCE.exists()

    text = readme_path.read_text(encoding="utf-8")
    assert "PNEUMO-CODEX-TZ-SPEC-CONNECTOR-RECONCILED-V32" in text
    assert "pneumo_codex_tz_spec_connector_reconciled_v32.zip" in text
    assert "v33_connector_reconciled" in text
    assert "12 workspaces" in text
    assert "`WS-INPUTS`" in text
    assert "`WS-RING`" in text
    assert "PLAYBOOK_PRODUCER_TRUTH.md" in text
    assert "RELEASE_GATE_HARDENING_MATRIX.csv" in text
    assert "RUNTIME_ARTIFACT_SCHEMA.yaml" in text
    assert "`GAP-001`" in text
    assert "00_READ_FIRST__ABSOLUTE_LAW.md" in text
    assert "COMPLETENESS_ASSESSMENT.md" in text
    assert "PARALLEL_CHAT_WORKSTREAMS.md" in text
    assert "RELEASE_GATE_ACCEPTANCE_MAP.md" in text
    assert "GAP_TO_EVIDENCE_ACTION_MAP.csv" in text
    assert "PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md" in text
    assert "COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md" in text
    assert "GEOMETRY_REFERENCE_EVIDENCE_NOTE.md" in text
    assert "MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md" in text
    assert "DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md" in text
    assert "RUNTIME_RELEASE_EVIDENCE_NOTE.md" in text
    assert "WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md" in text

    completeness = V32_COMPLETENESS.read_text(encoding="utf-8")
    assert "v32 хорош как карта, контракт и acceptance план" in completeness
    assert "self-checksum manifest mismatch" in completeness
    assert "CODEX CONSUMPTION ORDER V30" in completeness
    assert "PB-008 indexed without dedicated markdown playbook" in completeness
    assert "RELEASE_GATE_ACCEPTANCE_MAP.md" in completeness

    workstreams = V32_WORKSTREAMS.read_text(encoding="utf-8")
    assert "V32-01. Кабина проекта и главное окно" in workstreams
    assert "V32-16. Release Gates, KB и acceptance map" in workstreams
    assert "RELEASE_GATE_ACCEPTANCE_MAP.md" in workstreams
    assert "HO-001" in workstreams
    assert "knowledge_base_sync" in workstreams

    handoff_evidence = V32_INPUTS_HANDOFF_EVIDENCE.read_text(encoding="utf-8")
    assert "test_full_handoff_chain_preserves_refs_and_hashes_without_solver_run" in handoff_evidence
    assert "`HO-002`, `HO-003`, `HO-004`, `HO-005`" in handoff_evidence
    assert "does not claim solver correctness" in handoff_evidence


def test_v32_release_gate_acceptance_map_is_executable_docs_contract() -> None:
    hardening_rows = _load_csv_rows(V32_GATE_HARDENING)
    gap_rows = _load_csv_rows(V32_GAP_MAP)
    helper_hardening_rows = load_v32_release_gate_hardening_matrix(ROOT)
    helper_gap_rows = load_v32_gap_to_evidence_action_map(ROOT)
    map_text = V32_RELEASE_ACCEPTANCE_MAP.read_text(encoding="utf-8")
    release_lane_text = RELEASE_LANE.read_text(encoding="utf-8")

    assert len(hardening_rows) == 20
    assert len(gap_rows) == 6
    assert helper_hardening_rows == hardening_rows
    assert helper_gap_rows == gap_rows

    assert {row["HARDENING_ID"] for row in hardening_rows} == {f"RGH-{i:03d}" for i in range(1, 21)}
    assert {row["OPEN_GAP_ID"] for row in gap_rows} == {f"OG-{i:03d}" for i in range(1, 7)}
    assert any(
        row["HARDENING_ID"] == "RGH-011"
        and row["PLAYBOOK_ID"] == "PB-006"
        and row["OPEN_GAP_LINK"] == "OG-003"
        for row in hardening_rows
    )
    assert any(
        row["OPEN_GAP_ID"] == "OG-001"
        and row["PRIORITY"] == "P0"
        and "anim_latest contract" in row["REQUIRED_EVIDENCE"]
        for row in gap_rows
    )

    paths = v32_release_gate_reference_paths(ROOT)
    metadata = v32_release_gate_reference_metadata(ROOT)
    combined_metadata = release_gate_reference_metadata(ROOT)
    assert Path(paths["release_gate_acceptance_map"]) == V32_RELEASE_ACCEPTANCE_MAP
    assert metadata["hardening_rows"] == 20
    assert metadata["open_gap_rows"] == 6
    assert metadata["runtime_closure_claim"] is False
    assert combined_metadata["active_connector"]["source_layer"] == (
        "docs/context/gui_spec_imports/v33_connector_reconciled"
    )
    assert combined_metadata["active_connector"]["runtime_closure_claim"] is False
    assert combined_metadata["workstream_gate_extract"]["source_layer"] == (
        "docs/context/gui_spec_imports/v32_connector_reconciled"
    )
    assert combined_metadata["workstream_gate_extract"]["hardening_rows"] == 20
    assert combined_metadata["workstream_gate_extract"]["open_gap_rows"] == 6
    assert combined_metadata["workstream_gate_extract"]["runtime_closure_claim"] is False

    assert v32_workspace_ids() == (
        "WS-SHELL",
        "WS-PROJECT",
        "WS-INPUTS",
        "WS-RING",
        "WS-SUITE",
        "WS-BASELINE",
        "WS-OPTIMIZATION",
        "WS-ANALYSIS",
        "WS-ANIMATOR",
        "WS-DIAGNOSTICS",
        "WS-SETTINGS",
        "WS-TOOLS",
    )
    assert v32_handoff_ids() == tuple(f"HO-{i:03d}" for i in range(1, 11))
    workspace_paths = v32_workspace_reference_paths(ROOT)
    assert Path(workspace_paths["release_gate_acceptance_map"]) == V32_RELEASE_ACCEPTANCE_MAP

    assert "не объявляет runtime closure" in map_text
    assert "RGH-001" in map_text
    assert "OG-006" in map_text
    assert "WS-RING / HO-004 Live Evidence" in map_text
    assert "RG-GATE-012" in map_text
    assert "RG-GATE-013" in map_text
    assert "RG-GATE-016" in map_text
    assert "release_gate.py" in map_text
    assert "workspace_contract.py" in map_text

    assert "V32-16" in release_lane_text
    assert "RELEASE_GATE_ACCEPTANCE_MAP.md" in release_lane_text
    assert "PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md" in release_lane_text
    assert "COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md" in release_lane_text
    assert "GEOMETRY_REFERENCE_EVIDENCE_NOTE.md" in release_lane_text
    assert "MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md" in release_lane_text
    assert "DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md" in release_lane_text
    assert "RUNTIME_RELEASE_EVIDENCE_NOTE.md" in release_lane_text
    assert "Do not implement domain runtime features here." in release_lane_text
    assert "WORKTREE_TRIAGE_2026-04-17.md" in release_lane_text
    assert "V32_16_ACCEPTANCE_NOTE_2026-04-17.md" in release_lane_text


def test_release_readiness_triage_covers_dirty_worktree_with_lane_ownership() -> None:
    assert RELEASE_TRIAGE.exists()

    rows = _parse_markdown_table(RELEASE_TRIAGE)
    assert rows
    assert set(rows[0].keys()) == {
        "path",
        "status",
        "owner_lane",
        "gate_or_gap",
        "evidence_required",
        "tests",
        "decision",
    }

    allowed_statuses = {"keep", "rework", "defer", "needs-review"}
    triage_paths: set[str] = set()
    for row in rows:
        normalized_path = row["path"].strip("`")
        triage_paths.add(normalized_path)
        assert row["status"].strip("`") in allowed_statuses, normalized_path
        assert row["gate_or_gap"].strip("`"), normalized_path
        assert row["evidence_required"].strip("`"), normalized_path
        assert row["tests"].strip("`"), normalized_path
        assert row["decision"].strip("`"), normalized_path
        assert row["owner_lane"].startswith("V32-") or row["status"].strip("`") == "defer", (
            normalized_path
        )

    dirty_paths = _dirty_repo_paths_from_git_status()
    missing_paths = sorted(dirty_paths - triage_paths)
    assert not missing_paths, "\n".join(missing_paths)

    text = RELEASE_TRIAGE.read_text(encoding="utf-8")
    assert "This is not a runtime closure claim." in text
    assert "docs/context/gui_spec_imports/v33_connector_reconciled/README.md" in text
    assert "docs/context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md" in text
    assert text.index("v33_connector_reconciled/README.md") < text.index(
        "v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md"
    )


def test_v32_14_v32_09_producer_animator_truth_note_records_contract_acceptance_without_gap_closure() -> None:
    assert V32_PRODUCER_ANIMATOR_TRUTH_NOTE.exists()

    text = V32_PRODUCER_ANIMATOR_TRUTH_NOTE.read_text(encoding="utf-8")
    assert "V32-14/V32-09 producer and animator truth evidence contracts accepted" in text
    assert "not a release closure claim" in text
    assert "`OG-001`" in text
    assert "`OG-002`" in text
    assert "solver-points contract" in text
    assert "`solver_points`, `hardpoints` and `packaging`" in text
    assert "geometry-acceptance report" in text
    assert "`no_synthetic_geometry`" in text
    assert "`axis_only_honesty_mode`" in text
    assert "tests/test_anim_latest_solver_points_contract_gate.py" in text
    assert "tests/test_anim_export_contract_gate.py" in text
    assert "tests/test_r52_anim_export_contract_blocks.py" in text
    assert "tests/test_geometry_acceptance_release_gate.py" in text
    assert "tests/test_r31bn_cylinder_truth_gate.py" in text
    assert "tests/test_v32_desktop_animator_truth_contract.py" in text
    assert "36 passed" in text
    assert "not a durable release SEND bundle" in text
    assert "complete cylinder packaging passport" in text


def test_v32_06_v32_08_compare_objective_note_records_contract_acceptance_without_runtime_gap_closure() -> None:
    assert V32_COMPARE_OBJECTIVE_INTEGRITY_NOTE.exists()

    text = V32_COMPARE_OBJECTIVE_INTEGRITY_NOTE.read_text(encoding="utf-8")
    assert "V32-06/V32-08 compare and objective integrity contracts accepted" in text
    assert "not a runtime gap\nclosure claim" in text
    assert "`RGH-013`" in text
    assert "`RGH-014`" in text
    assert "`RGH-015`" in text
    assert "Optimization objective contracts persist selected objective stacks" in text
    assert "Resume/staged-resume paths reject or warn" in text
    assert "Run history surfaces current/historical/stale objective state" in text
    assert "Compare sessions carry explicit compare contracts" in text
    assert "tests/test_qt_compare_viewer_compare_contract.py" in text
    assert "tests/test_qt_compare_viewer_session_autoload_source.py" in text
    assert "tests/test_qt_compare_offline_npz_anim_diagnostics.py" in text
    assert "tests/test_qt_compare_viewer_dock_object_names.py" in text
    assert "tests/test_optimization_objective_contract.py" in text
    assert "tests/test_r31cw_optimization_run_history_objective_contract.py" in text
    assert "tests/test_optimization_baseline_source_history.py" in text
    assert "tests/test_optimization_resume_run_dir.py" in text
    assert "tests/test_optimization_staged_resume_run_dir.py" in text
    assert "41 passed" in text
    assert "does not close `OG-003`, `OG-004`, `OG-005`" in text


def test_v32_12_geometry_reference_note_records_provenance_acceptance_without_runtime_closure() -> None:
    assert V32_GEOMETRY_REFERENCE_EVIDENCE_NOTE.exists()

    text = V32_GEOMETRY_REFERENCE_EVIDENCE_NOTE.read_text(encoding="utf-8")
    assert "V32-12 geometry reference evidence contracts accepted" in text
    assert "not a runtime closure\nclaim" in text
    assert "`RGH-018`" in text
    assert "`OG-006`" in text
    assert "Selected `anim_latest` JSON/NPZ artifacts" in text
    assert "current or\n  historical artifact contexts" in text
    assert "geometry_reference_evidence.json" in text
    assert "latest_geometry_reference_evidence.json" in text
    assert "road_width_m" in text
    assert "Cylinder packaging passport evidence" in text
    assert "tests/test_desktop_geometry_reference_center_contract.py" in text
    assert "tests/test_geometry_acceptance_release_gate.py" in text
    assert "tests/test_anim_latest_geometry_contract_gate.py" in text
    assert "tests/test_geometry_acceptance_web_and_bundle.py" in text
    assert "tests/test_visual_consumers_geometry_strict.py" in text
    assert "40 passed" in text
    assert "imported-layer/runtime-proof open question" in text
    assert "does not alter solver physics" in text


def test_v32_10_mnemo_truth_graphics_note_records_dataset_provenance_acceptance_without_runtime_closure() -> None:
    assert V32_MNEMO_TRUTH_GRAPHICS_NOTE.exists()

    text = V32_MNEMO_TRUTH_GRAPHICS_NOTE.read_text(encoding="utf-8")
    assert "V32-10 Desktop Mnemo truth-graphics contracts accepted" in text
    assert "not a runtime gap\nclosure claim" in text
    assert "`RGH-003`" in text
    assert "desktop_mnemo_dataset_contract_v1" in text
    assert "source\n  markers for flow, pressure, state, scheme mapping and cylinder snapshot" in text
    assert "canonical nodes/routes" in text
    assert "unavailable/degraded states" in text
    assert "pressure-only mode without silent volume fallback" in text
    assert "tests/test_desktop_mnemo_dataset_contract.py" in text
    assert "tests/test_desktop_mnemo_inline_overlay_contract.py" in text
    assert "tests/test_desktop_mnemo_launcher_contract.py" in text
    assert "tests/test_desktop_mnemo_main_contract.py" in text
    assert "tests/test_desktop_mnemo_page_contract.py" in text
    assert "tests/test_desktop_mnemo_settings_bridge_contract.py" in text
    assert "tests/test_desktop_mnemo_snapshot_contract.py" in text
    assert "tests/test_desktop_mnemo_window_contract.py" in text
    assert "tests/test_pneumo_scheme_mnemo_cache_resource_contract.py" in text
    assert "22 passed" in text
    assert "does not close `OG-001`, `OG-002`, `OG-003`, `OG-004`, `OG-005` or\n  `OG-006`" in text


def test_v32_11_diagnostics_evidence_note_records_lane_acceptance_without_release_closure() -> None:
    assert V32_DIAGNOSTICS_EVIDENCE_NOTE.exists()

    text = V32_DIAGNOSTICS_EVIDENCE_NOTE.read_text(encoding="utf-8")
    assert "V32-11 diagnostics evidence contract accepted" in text
    assert "full `OG-005` closure claim" in text
    assert "`OG-005`" in text
    assert "diagnostics/evidence_manifest.json" in text
    assert "latest_send_bundle.zip" in text
    assert "latest_send_bundle.sha256" in text
    assert "`BND-018`" in text
    assert "geometry/geometry_reference_evidence.json" in text
    assert "latest_geometry_reference_evidence.json" in text
    assert "artifact_freshness_status" in text
    assert "artifact_freshness_relation" in text
    assert "artifact_freshness_status=missing" in text
    assert "artifact_freshness_relation=latest" in text
    assert "geometry_acceptance_gate=MISSING" in text
    assert "road_width_status=derived_from_track_and_wheel_width" in text
    assert "packaging_mismatch_status=mismatch" in text
    assert "`GAP-002`" in text
    assert "`GAP-006`" in text
    assert "`GAP-008`" in text
    assert "reader_and_evidence_surface" in text
    assert "does_not_render_animator_meshes" in text
    assert "CYLINDER_PACKAGING_PASSPORT.json" in text
    assert "meta.geometry.road_width_m" in text
    assert "Geometry Reference Center does not close" in text
    assert "Runtime proof captured" in text
    assert "send_bundles/SEND_" in text
    assert "pb002_missing_required_count=0" in text
    assert "tests/test_v32_diagnostics_send_bundle_evidence.py" in text
    assert "tests/test_health_report_inspect_send_bundle_anim_diagnostics.py" in text
    assert "tests/test_desktop_diagnostics_center_contract.py" in text
    assert "26 passed" in text
    assert "85 passed" in text
    assert "Runtime validation result: `validation ok`" in text
    assert "does not alter solver, optimizer, animator, geometry, or domain calculations" in text


def test_v32_15_runtime_evidence_note_records_hard_gate_acceptance_without_gap_closure() -> None:
    assert V32_RUNTIME_EVIDENCE_NOTE.exists()

    text = V32_RUNTIME_EVIDENCE_NOTE.read_text(encoding="utf-8")
    assert "V32-15 runtime evidence hard-gate contract accepted" in text
    assert "not a release closure claim" in text
    assert "`OG-003`" in text
    assert "`OG-004`" in text
    assert "browser_perf_trace" in text
    assert "viewport_gating" in text
    assert "animator_frame_budget" in text
    assert "tests/test_v32_runtime_evidence_gates.py" in text
    assert "tests/test_r31bu_browser_perf_artifacts.py" in text
    assert "tests/test_r78_animator_playback_speed_stability.py" in text
    assert "tests/test_r42_bundle_stable_road_grid_and_aux_cadence_metrics.py" in text
    assert "47 passed" in text
    assert "hard_fail_count=3" in text
    assert "No measured `browser_perf_trace`" in text
    assert "No current `viewport_gating_report.json`" in text
    assert "No current `animator_frame_budget_evidence.json`" in text
    assert "does not\n  alter solver, optimizer, geometry or domain calculations" in text


def test_v32_16_acceptance_note_records_docs_helper_boundary() -> None:
    assert V32_16_ACCEPTANCE_NOTE.exists()

    text = V32_16_ACCEPTANCE_NOTE.read_text(encoding="utf-8")
    assert "not a runtime closure claim" in text
    assert "docs/context/gui_spec_imports/v33_connector_reconciled" in text
    assert "docs/context/gui_spec_imports/v32_connector_reconciled" in text
    assert "20 hardening rows" in text
    assert "6 open-gap rows" in text
    assert "pneumo_solver_ui/release_gate.py" in text
    assert "pneumo_solver_ui/workspace_contract.py" in text
    assert "tests/test_gui_spec_docs_contract.py" in text
    assert "23 passed" in text
    assert "Diagnostics evidence" in text
    assert "Runtime evidence" in text
    assert "Producer truth" in text


def test_v33_connector_reconciled_digest_is_registered() -> None:
    readme_path = IMPORTS_V33 / "README.md"
    assert readme_path.exists()
    assert V33_COMPLETENESS.exists()

    text = readme_path.read_text(encoding="utf-8")
    assert "pneumo_codex_tz_spec_connector_reconciled_v33.zip" in text
    assert "PACKAGE_INTEGRITY_POLICY.md" in text
    assert "PLAYBOOK_CURRENT_HISTORICAL_STALE_CONTEXT.md" in text
    assert "REPO_CANON_READ_ORDER.csv" in text
    assert "REPO_CANON_GATE_MAPPING.csv" in text
    assert "337" in text
    assert "не объявляет runtime closure" in text

    completeness = V33_COMPLETENESS.read_text(encoding="utf-8")
    assert "Все `336` hashed files совпали с manifest" in completeness
    assert "ISSUE-V33-001" in completeness
    assert "ISSUE-V33-002" in completeness
    assert "SOURCE_CONTEXT/PROMPT_CANONICAL_EXTRACTS_V33.md" in completeness
    assert "active_label_drift_absent: false" in completeness

    paths = v33_release_gate_reference_paths(ROOT)
    metadata = v33_release_gate_reference_metadata(ROOT)
    assert Path(paths["readme"]) == readme_path
    assert Path(paths["completeness_assessment"]) == V33_COMPLETENESS
    assert metadata["source_layer"] == "docs/context/gui_spec_imports/v33_connector_reconciled"
    assert metadata["active_connector_layer"] is True
    assert metadata["runtime_closure_claim"] is False


def test_ring_related_lane_docs_reference_v13_contracts() -> None:
    ring_lane_text = RING_LANE.read_text(encoding="utf-8")
    results_lane_text = RESULTS_LANE.read_text(encoding="utf-8")
    optimizer_lane_text = OPTIMIZER_LANE.read_text(encoding="utf-8")
    animator_lane_text = ANIMATOR_LANE.read_text(encoding="utf-8")

    assert "## Канонический слой" in ring_lane_text
    assert "../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md" in ring_lane_text
    assert "../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md" in ring_lane_text
    assert "ring_editor_schema_contract_v13.json" in ring_lane_text
    assert "ring_editor_screen_blueprints_v13.csv" in ring_lane_text
    assert "ring_to_suite_link_contract_v13.json" in ring_lane_text
    assert "WS-SUITE" in ring_lane_text

    assert "## Канонический слой" in results_lane_text
    assert "../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md" in results_lane_text
    assert "../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md" in results_lane_text
    assert "ring_to_suite_link_contract_v13.json" in results_lane_text
    assert "web_to_desktop_migration_matrix_v13.csv" in results_lane_text
    assert "stale link" in results_lane_text

    assert "## Канонический слой" in optimizer_lane_text
    assert "optimization_control_plane_contract_v12.json" in optimizer_lane_text
    assert "../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md" in optimizer_lane_text
    assert "../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md" in optimizer_lane_text

    assert "## Канонический слой" in animator_lane_text
    assert "truthful_graphics_contract_v12.json" in animator_lane_text
    assert "../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md" in animator_lane_text
    assert "../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md" in animator_lane_text


def test_touched_gui_spec_docs_have_no_strong_mojibake() -> None:
    offenders: list[str] = []
    target_paths = (
        IMPORTS_README,
        PROJECT_KNOWLEDGE_BASE,
        PROJECT_SOURCES,
        GUI_INDEX,
        CANON_18,
        LINEAGE_MD,
        PARITY_SUMMARY,
        PARITY_JSON,
        ANIMATOR_LANE,
        OPTIMIZER_LANE,
        RING_LANE,
        RESULTS_LANE,
        RELEASE_LANE,
        FOUNDATIONS / "README.md",
        FOUNDATIONS / "prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md",
        IMPORTS_V12 / "README.md",
        IMPORTS_V13 / "README.md",
        IMPORTS_V32 / "README.md",
        IMPORTS_V33 / "README.md",
        V32_COMPLETENESS,
        V33_COMPLETENESS,
        V32_WORKSTREAMS,
        V32_RELEASE_ACCEPTANCE_MAP,
        V32_GATE_HARDENING,
        V32_GAP_MAP,
        V32_PRODUCER_ANIMATOR_TRUTH_NOTE,
        V32_COMPARE_OBJECTIVE_INTEGRITY_NOTE,
        V32_GEOMETRY_REFERENCE_EVIDENCE_NOTE,
        V32_MNEMO_TRUTH_GRAPHICS_NOTE,
        V32_DIAGNOSTICS_EVIDENCE_NOTE,
        V32_RUNTIME_EVIDENCE_NOTE,
        RELEASE_TRIAGE,
        V32_16_ACCEPTANCE_NOTE,
    )

    for path in target_paths:
        text = path.read_text(encoding="utf-8")
        bad = [marker for marker in STRONG_MOJIBAKE_MARKERS if marker in text]
        if bad or "????" in text:
            offenders.append(f"{path.name}: {', '.join(bad) if bad else '????'}")

    assert not offenders, "\n".join(offenders)
