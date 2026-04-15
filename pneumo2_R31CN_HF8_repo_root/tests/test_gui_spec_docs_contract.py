from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CONTEXT = DOCS / "context"
IMPORTS = CONTEXT / "gui_spec_imports"
IMPORTS_V3 = IMPORTS / "v3"
IMPORTS_V13 = IMPORTS / "v13_ring_editor_migration"

CANON_17 = DOCS / "17_WINDOWS_DESKTOP_CAD_GUI_CANON.md"
CANON_18 = DOCS / "18_PNEUMOAPP_WINDOWS_GUI_SPEC.md"
PROJECT_SOURCES = DOCS / "PROJECT_SOURCES.md"
GUI_INDEX = DOCS / "gui_chat_prompts" / "00_INDEX.md"
RING_LANE = DOCS / "gui_chat_prompts" / "04_RING_EDITOR.md"
RESULTS_LANE = DOCS / "gui_chat_prompts" / "10_TEST_VALIDATION_RESULTS.md"
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
        assert file_path.stat().st_size == item["size_bytes"], file_path.name

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

    assert "v13_ring_editor_migration/" in imports_readme
    assert "специализированный ring-editor migration" in imports_readme
    assert "WS-RING -> WS-SUITE" in imports_readme

    assert "v13_ring_editor_migration/README.md" in project_sources_text
    assert "ring_editor_schema_contract_v13.json" in project_sources_text
    assert "ring_editor_screen_blueprints_v13.csv" in project_sources_text
    assert "ring_editor_acceptance_gates_v13.csv" in project_sources_text
    assert "ring_to_suite_link_contract_v13.json" in project_sources_text

    assert "gui_spec_imports/v13_ring_editor_migration/README.md" in index_text
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


def test_ring_related_lane_docs_reference_v13_contracts() -> None:
    ring_lane_text = RING_LANE.read_text(encoding="utf-8")
    results_lane_text = RESULTS_LANE.read_text(encoding="utf-8")

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


def test_touched_gui_spec_docs_have_no_strong_mojibake() -> None:
    offenders: list[str] = []
    target_paths = (
        IMPORTS_README,
        PROJECT_SOURCES,
        GUI_INDEX,
        CANON_18,
        PARITY_SUMMARY,
        PARITY_JSON,
        RING_LANE,
        RESULTS_LANE,
        IMPORTS_V13 / "README.md",
    )

    for path in target_paths:
        text = path.read_text(encoding="utf-8")
        bad = [marker for marker in STRONG_MOJIBAKE_MARKERS if marker in text]
        if bad or "????" in text:
            offenders.append(f"{path.name}: {', '.join(bad) if bad else '????'}")

    assert not offenders, "\n".join(offenders)
