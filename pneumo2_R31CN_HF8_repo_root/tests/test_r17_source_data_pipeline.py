from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from pneumo_solver_ui.r17_source_data_contract import required_full_source_keys, semantic_preserving_r16_seed
from pneumo_solver_ui.r17_source_data_pipeline import (
    build_fillable_template_rows,
    merge_partial_with_manual_rows,
    validate_merged_source_data,
)


def test_build_fillable_template_rows_matches_contract() -> None:
    rows = build_fillable_template_rows()
    keys = [row["key"] for row in rows]
    assert len(rows) == len(required_full_source_keys())
    assert len(set(keys)) == len(keys)
    seed = semantic_preserving_r16_seed()
    seed_keys = {row["key"] for row in rows if row["can_prefill_from_R16"] == "yes"}
    assert seed_keys == set(seed.keys())
    assert any(row["key"] == "верх_Ц1_перед_x_относительно_оси_ступицы_м" and row["prefill_value_from_R16_if_any"] == "0.0" for row in rows)


def test_merge_partial_with_manual_rows_applies_explicit_manual_override() -> None:
    partial = {"верх_Ц1_перед_x_относительно_оси_ступицы_м": 0.0}
    rows = [
        {
            "key": "верх_Ц1_перед_x_относительно_оси_ступицы_м",
            "type": "float",
            "manual_value": "0.12",
        }
    ]
    merged, notes = merge_partial_with_manual_rows(partial, rows)
    assert merged["верх_Ц1_перед_x_относительно_оси_ступицы_м"] == 0.12
    assert any(note.kind == "manual_set" for note in notes)


def test_validate_merged_source_data_partial_allows_missing_full_geometry() -> None:
    partial = semantic_preserving_r16_seed() | {
        "диаметр_поршня_Ц1": 0.1,
        "диаметр_поршня_Ц2": 0.1,
        "диаметр_штока_Ц1": 0.02,
        "диаметр_штока_Ц2": 0.02,
        "ход_штока_Ц1_перед_м": 0.1,
        "ход_штока_Ц1_зад_м": 0.1,
        "ход_штока_Ц2_перед_м": 0.1,
        "ход_штока_Ц2_зад_м": 0.1,
        "низ_Ц1_перед_доля_рычага": 0.4,
        "низ_Ц1_зад_доля_рычага": 0.4,
        "низ_Ц2_перед_доля_рычага": 0.4,
        "низ_Ц2_зад_доля_рычага": 0.4,
        "верх_Ц1_перед_z_относительно_рамы_м": 0.2,
        "верх_Ц1_зад_z_относительно_рамы_м": 0.2,
        "верх_Ц2_перед_z_относительно_рамы_м": 0.2,
        "верх_Ц2_зад_z_относительно_рамы_м": 0.2,
        "верх_Ц1_перед_между_ЛП_ПП_м": 1.0,
        "верх_Ц1_зад_между_ЛЗ_ПЗ_м": 1.0,
        "верх_Ц2_перед_между_ЛП_ПП_м": 1.0,
        "верх_Ц2_зад_между_ЛЗ_ПЗ_м": 1.0,
        "низ_Ц1_перед_ветвь_трапеции": "перед",
        "низ_Ц1_зад_ветвь_трапеции": "перед",
        "низ_Ц2_перед_ветвь_трапеции": "зад",
        "низ_Ц2_зад_ветвь_трапеции": "зад",
    }
    issues = validate_merged_source_data(partial, allow_partial=True)
    assert not any(issue.level == "error" and "доля" in issue.message for issue in issues)


def test_cli_template_and_merge_roundtrip(tmp_path: Path) -> None:
    template_csv = tmp_path / "template.csv"
    merge_csv = tmp_path / "manual.csv"
    partial_json = tmp_path / "partial.json"
    output_json = tmp_path / "merged.json"
    report_md = tmp_path / "report.md"
    report_csv = tmp_path / "report.csv"

    cli = [sys.executable, "-m", "pneumo_solver_ui.tools.r17_source_data_pipeline_cli"]
    subprocess.run(cli + ["template", str(template_csv)], check=True)
    rows = []
    with template_csv.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if row["key"] == "верх_Ц1_перед_x_относительно_оси_ступицы_м":
            row["manual_value"] = "0.03"
        if row["key"] == "низ_Ц1_перед_ветвь_трапеции":
            row["manual_value"] = "перед"
    with merge_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    partial_json.write_text(json.dumps({"верх_Ц1_перед_x_относительно_оси_ступицы_м": 0.0}, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        cli + [
            "merge",
            "--partial-json", str(partial_json),
            "--manual-csv", str(merge_csv),
            "--output-json", str(output_json),
            "--allow-partial",
            "--report-md", str(report_md),
            "--report-csv", str(report_csv),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    data = json.loads(output_json.read_text(encoding="utf-8"))
    assert data["верх_Ц1_перед_x_относительно_оси_ступицы_м"] == 0.03
    assert report_md.exists()
    assert report_csv.exists()
