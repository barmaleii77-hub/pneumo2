from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CONTEXT = DOCS / "context"
IMPORTS = CONTEXT / "gui_spec_imports"
IMPORTS_V2 = IMPORTS / "v2"
IMPORTS_V3 = IMPORTS / "v3"
CANON_17 = DOCS / "17_WINDOWS_DESKTOP_CAD_GUI_CANON.md"
CANON_18 = DOCS / "18_PNEUMOAPP_WINDOWS_GUI_SPEC.md"
PROJECT_SOURCES = DOCS / "PROJECT_SOURCES.md"
PARITY_SUMMARY = CONTEXT / "DESKTOP_WEB_PARITY_SUMMARY.md"
PARITY_JSON = CONTEXT / "desktop_web_parity_map.json"
GUI_INDEX = DOCS / "gui_chat_prompts" / "00_INDEX.md"
TARGETED_LANE_DOCS = (
    DOCS / "gui_chat_prompts" / "01_MAIN_WINDOW.md",
    DOCS / "gui_chat_prompts" / "02_INPUT_DATA.md",
    DOCS / "gui_chat_prompts" / "03_RUN_SETUP.md",
    DOCS / "gui_chat_prompts" / "04_RING_EDITOR.md",
    DOCS / "gui_chat_prompts" / "06_DESKTOP_MNEMO.md",
    DOCS / "gui_chat_prompts" / "07_DESKTOP_ANIMATOR.md",
    DOCS / "gui_chat_prompts" / "08_OPTIMIZER_CENTER.md",
    DOCS / "gui_chat_prompts" / "09_DIAGNOSTICS_SEND_BUNDLE.md",
    DOCS / "gui_chat_prompts" / "10_TEST_VALIDATION_RESULTS.md",
)

STRONG_MOJIBAKE_MARKERS = (
    "Р В Р’В Р вЂ™Р’В Р В Р Р‹Р РЋРЎСџР В Р’В Р вЂ™Р’В ",
    "Р В Р’В Р вЂ™Р’В Р В Р Р‹Р Р†Р вЂљРІвЂћСћР В Р’В Р вЂ™Р’В ",
    "Р В Р’В Р вЂ™Р’В Р В Р’В Р В РІР‚в„–Р В Р’В Р вЂ™Р’В ",
    "Р В Р’В Р вЂ™Р’В Р В Р Р‹Р РЋРІвЂћСћР В Р’В Р вЂ™Р’В ",
    "Р В Р’В Р В РІР‚В Р В Р’В Р Р†Р вЂљРЎв„ў",
    "Р В Р’В Р В РІР‚В Р В Р вЂ Р В РІР‚С™Р вЂ™Р’В ",
    "Р В РІР‚СљР Р†Р вЂљРЎСљР В РІР‚СљР вЂ™Р’В ",
    "Р В РІР‚СљР В РІР‚РЋР В РІР‚СљР вЂ™Р’В°",
)


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_gui_spec_canon_docs_exist_and_link_active_v3_layer() -> None:
    assert CANON_17.exists()
    assert CANON_18.exists()

    canon_17 = CANON_17.read_text(encoding="utf-8")
    canon_18 = CANON_18.read_text(encoding="utf-8")

    assert "automation_id" in canon_17
    assert "tooltip + help" in canon_17
    assert "Source-of-truth matrix" in canon_17
    assert "Observability hooks" in canon_17
    assert "Command search" in canon_17
    assert "pipeline verification" in canon_17

    assert "## Ц. Active detailed reference layer v3" in canon_18
    assert "## Ч. Workflow graphs и shell-region contract" in canon_18
    assert "## Ш. Базовое окно `1920x1080` и координатный contract" in canon_18
    assert "## Щ. UI element catalog, field registry, help и tooltip registries" in canon_18
    assert "## Ы. Migration matrix `web -> desktop`" in canon_18
    assert "## Ь. Acceptance, pipeline verification и test suite" in canon_18
    assert "## Э. Source-of-truth, keyboard, docking, state и observability matrices" in canon_18
    assert "./context/gui_spec_imports/v3/README.md" in canon_18
    assert "./context/gui_spec_imports/v3/current_macro.dot" in canon_18
    assert "./context/gui_spec_imports/v3/optimized_macro.dot" in canon_18
    assert "./context/gui_spec_imports/v3/current_element_graph.dot" in canon_18
    assert "./context/gui_spec_imports/v3/optimized_element_graph.dot" in canon_18
    assert "./context/gui_spec_imports/v3/ui_element_catalog.csv" in canon_18
    assert "./context/gui_spec_imports/v3/field_catalog.csv" in canon_18
    assert "./context/gui_spec_imports/v3/help_catalog.csv" in canon_18
    assert "./context/gui_spec_imports/v3/tooltip_catalog.csv" in canon_18
    assert "./context/gui_spec_imports/v3/migration_matrix.csv" in canon_18
    assert "./context/gui_spec_imports/v3/source_of_truth_matrix.csv" in canon_18
    assert "./context/gui_spec_imports/v3/keyboard_matrix.csv" in canon_18
    assert "./context/gui_spec_imports/v3/docking_matrix.csv" in canon_18
    assert "./context/gui_spec_imports/v3/ui_state_matrix.csv" in canon_18
    assert "./context/gui_spec_imports/v3/pipeline_observability.csv" in canon_18
    assert "./context/gui_spec_imports/v3/acceptance_criteria.csv" in canon_18
    assert "./context/gui_spec_imports/v3/pipeline_verification.csv" in canon_18
    assert "./context/gui_spec_imports/v3/test_suite.csv" in canon_18
    assert "historical detailed import" in canon_18


def test_gui_spec_v3_import_layer_exists_and_manifest_matches_files() -> None:
    manifest_path = IMPORTS_V3 / "manifest.json"
    readme_path = IMPORTS_V3 / "README.md"

    assert IMPORTS_V3.exists()
    assert IMPORTS_V2.exists()
    assert manifest_path.exists()
    assert readme_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    readme_text = readme_path.read_text(encoding="utf-8-sig")

    assert "17_WINDOWS_DESKTOP_CAD_GUI_CANON.md" in readme_text
    assert "18_PNEUMOAPP_WINDOWS_GUI_SPEC.md" in readme_text
    assert "active detailed machine-readable reference layer" in readme_text
    assert "historical detailed import" in readme_text
    assert "raw `.zip`" in readme_text

    expected_files = {
        "README.md",
        "manifest.json",
        "CHANGELOG_v3.md",
        "pneumo_gui_codex_spec_v3_refined.json",
        "current_macro.dot",
        "optimized_macro.dot",
        "current_element_graph.dot",
        "optimized_element_graph.dot",
        "ui_element_catalog.csv",
        "field_catalog.csv",
        "help_catalog.csv",
        "tooltip_catalog.csv",
        "migration_matrix.csv",
        "acceptance_criteria.csv",
        "pipeline_verification.csv",
        "test_suite.csv",
        "best_practices_sources.csv",
        "source_of_truth_matrix.csv",
        "ui_state_matrix.csv",
        "keyboard_matrix.csv",
        "docking_matrix.csv",
        "pipeline_observability.csv",
        "graph_delta_v3.csv",
    }

    manifest_entries = {str(item["name"]) for item in manifest["files"]}
    actual_files = {path.name for path in IMPORTS_V3.iterdir() if path.is_file()}

    assert manifest_entries == actual_files
    assert actual_files == expected_files
    assert manifest["main_file"] == "pneumo_gui_codex_spec_v3_refined.json"
    assert manifest["version"] == "3.0.0"
    assert manifest["counts"]["ui_elements"] == 157

    for item in manifest["files"]:
        file_path = IMPORTS_V3 / str(item["name"])
        payload = file_path.read_bytes()
        if file_path.name in {"README.md", "manifest.json"}:
            continue
        assert item["size_bytes"] == len(payload), file_path.name
        assert item["sha256"] == hashlib.sha256(payload).hexdigest(), file_path.name


def test_gui_spec_v3_detailed_json_loads_and_exposes_expected_contract_keys() -> None:
    spec_path = IMPORTS_V3 / "pneumo_gui_codex_spec_v3_refined.json"
    data = json.loads(spec_path.read_text(encoding="utf-8-sig"))

    assert data["идентификатор_схемы"] == "pneumo_gui_codex_spec_v3_refined"
    assert data["версия"] == "3.0.0"
    assert "оболочка_главного_окна" in data
    assert "каталог_элементов_UI_плоский" in data
    assert "каталог_полей_плоский" in data
    assert "каталог_развёрнутой_справки" in data
    assert "каталог_коротких_подсказок" in data
    assert "матрица_миграции_web_в_desktop" in data
    assert "проверка_pipeline_юзер_GUI_юзер" in data
    assert "набор_тестов" in data
    assert "критерии_приёмки" in data
    assert "контракт_поиска_команд" in data
    assert "контракт_подсказок_и_справки" in data
    assert "контракт_стыковки_и_отстыковки" in data
    assert "контракт_источников_истины" in data
    assert "контракт_когнитивной_эргономики" in data
    assert "контракт_состояний_элемента" in data
    assert "контракт_валидации_и_исправления" in data
    assert "контракт_undo_redo" in data
    assert "контракт_пустых_и_недоступных_состояний" in data
    assert "контракт_табличных_поверхностей" in data
    assert "контракт_клавиатурной_карты_расширенный" in data
    assert "контракт_наблюдаемости_pipeline" in data
    assert "контракт_окна_и_title_bar" in data
    assert "контракт_докирования_по_типам_панелей" in data


def test_project_sources_index_and_parity_summary_reference_v3_layer() -> None:
    imports_readme = (IMPORTS / "README.md").read_text(encoding="utf-8")
    index_text = GUI_INDEX.read_text(encoding="utf-8")
    project_sources_text = PROJECT_SOURCES.read_text(encoding="utf-8")
    parity_summary_text = PARITY_SUMMARY.read_text(encoding="utf-8")

    assert "gui_spec_imports/v3/*" in index_text
    assert "Active detailed v3 layer" in index_text
    assert "implementation prompts" in index_text

    assert "v3/" in imports_readme
    assert "active detailed machine-readable reference layer" in imports_readme
    assert "historical detailed import-layer" in imports_readme

    assert "Human-readable canon" in project_sources_text
    assert "Imported detailed reference" in project_sources_text
    assert "docs/context/gui_spec_imports/v3/pneumo_gui_codex_spec_v3_refined.json" in project_sources_text
    assert "docs/context/gui_spec_imports/v3/source_of_truth_matrix.csv" in project_sources_text
    assert "docs/context/gui_spec_imports/v3/pipeline_observability.csv" in project_sources_text
    assert "docs/context/gui_spec_imports/v2/README.md" in project_sources_text
    assert "docs/context/DESKTOP_WEB_PARITY_SUMMARY.md" in project_sources_text
    assert "docs/gui_chat_prompts/00_INDEX.md" in project_sources_text

    assert "17_WINDOWS_DESKTOP_CAD_GUI_CANON.md" in parity_summary_text
    assert "18_PNEUMOAPP_WINDOWS_GUI_SPEC.md" in parity_summary_text
    assert "gui_spec_imports/v3" in parity_summary_text
    assert "desktop_web_parity_map.json" in parity_summary_text
    assert "новый_обязательный_слой" in parity_summary_text
    assert "source_of_truth_matrix.csv" in parity_summary_text


def test_v3_catalogs_keep_basic_machine_readable_contracts() -> None:
    ui_rows = _load_csv_rows(IMPORTS_V3 / "ui_element_catalog.csv")
    field_rows = _load_csv_rows(IMPORTS_V3 / "field_catalog.csv")
    help_rows = _load_csv_rows(IMPORTS_V3 / "help_catalog.csv")
    tooltip_rows = _load_csv_rows(IMPORTS_V3 / "tooltip_catalog.csv")

    automation_ids = [row["automation_id"].strip() for row in ui_rows]
    assert ui_rows
    assert len(automation_ids) == len(set(automation_ids))
    assert all(row["tooltip_id"].strip() for row in ui_rows)
    assert all(row["help_id"].strip() for row in ui_rows)
    assert all(row["workspace_owner"].strip() for row in ui_rows)
    assert all(row["регион"].strip() for row in ui_rows)

    help_ids = {row["id"].strip() for row in help_rows}
    tooltip_help_ids = {row["связанная_помощь"].strip() for row in tooltip_rows}
    assert tooltip_help_ids <= help_ids

    required_field_columns = {
        "id",
        "название",
        "тип",
        "обязательное",
        "help_id",
        "короткая_подсказка",
        "каталог",
        "варианты",
        "единица_измерения",
    }
    assert set(field_rows[0].keys()) == required_field_columns
    numeric_types = {"numeric_editor", "integer_editor", "read_only_numeric", "read_only_integer"}
    numeric_rows = [row for row in field_rows if row["тип"] in numeric_types]
    assert numeric_rows
    assert all(row["единица_измерения"].strip() for row in numeric_rows)


def test_v3_refined_matrices_have_expected_contract_shape() -> None:
    source_rows = _load_csv_rows(IMPORTS_V3 / "source_of_truth_matrix.csv")
    state_rows = _load_csv_rows(IMPORTS_V3 / "ui_state_matrix.csv")
    keyboard_rows = _load_csv_rows(IMPORTS_V3 / "keyboard_matrix.csv")
    docking_rows = _load_csv_rows(IMPORTS_V3 / "docking_matrix.csv")
    observability_rows = _load_csv_rows(IMPORTS_V3 / "pipeline_observability.csv")
    sources_rows = _load_csv_rows(IMPORTS_V3 / "best_practices_sources.csv")

    assert set(source_rows[0].keys()) == {
        "домен",
        "источник_истины",
        "производные_представления",
        "запрещено",
        "проверка",
    }
    assert {row["домен"] for row in source_rows} >= {
        "Исходные конструктивные параметры",
        "Сценарии дороги и кольца",
        "Набор испытаний",
        "Baseline",
        "Контракт оптимизации",
        "Диагностика",
    }

    assert {row["id"] for row in state_rows} >= {
        "STATE-DEFAULT",
        "STATE-FOCUS",
        "STATE-DIRTY",
        "STATE-WARNING",
        "STATE-ERROR",
    }

    assert any(row["значение"] == "Поиск команд" and row["клавиши"] == "Ctrl+K" for row in keyboard_rows)
    assert any(row["значение"] == "Главное действие шага" and row["клавиши"] == "Ctrl+Enter" for row in keyboard_rows)
    f6_rows = [row for row in keyboard_rows if row["тип"] == "F6_порядок"]
    assert len(f6_rows) >= 5

    assert any(row["панель"] == "правая_панель_свойств_и_справки" and row["можно_на_второй_монитор"] == "True" for row in docking_rows)
    assert any(row["панель"] == "аниматор" and row["можно_плавающее_окно"] == "True" for row in docking_rows)
    assert any(row["панель"] == "диагностика" for row in docking_rows)

    assert {row["event_id"] for row in observability_rows} >= {
        "ui_app_started",
        "ui_workspace_changed",
        "ui_field_changed",
        "ui_validation_state_changed",
        "ui_baseline_started",
    }
    assert all(row["обязательные_поля"].strip() for row in observability_rows)

    assert any(row["источник"] == "Microsoft Learn" for row in sources_rows)
    assert all(row["url"].startswith("https://") for row in sources_rows)


def test_targeted_gui_spec_docs_have_no_strong_mojibake() -> None:
    offenders: list[str] = []
    target_paths = (
        CANON_17,
        CANON_18,
        PROJECT_SOURCES,
        PARITY_SUMMARY,
        PARITY_JSON,
        GUI_INDEX,
        IMPORTS / "README.md",
        IMPORTS_V2 / "README.md",
        IMPORTS_V3 / "README.md",
        *TARGETED_LANE_DOCS,
    )

    for path in target_paths:
        text = path.read_text(encoding="utf-8")
        bad = [marker for marker in STRONG_MOJIBAKE_MARKERS if marker in text]
        if bad or "????" in text:
            offenders.append(f"{path.name}: {', '.join(bad) if bad else '????'}")

    assert not offenders, "\n".join(offenders)


def test_targeted_lane_docs_keep_canonical_reference_blocks_and_v3_links() -> None:
    for path in TARGETED_LANE_DOCS:
        text = path.read_text(encoding="utf-8")

        assert "## Канонический слой" in text, path.name
        assert "docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md" in text, path.name
        assert "docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md" in text, path.name
        assert "docs/context/gui_spec_imports/v3/" in text, path.name
        assert "## Цель lane" in text, path.name
        assert "## Можно менять" in text, path.name
        assert "## Можно читать как источник поведения" in text, path.name
        assert "## Нельзя менять" in text, path.name
        assert "## Правила" in text, path.name
